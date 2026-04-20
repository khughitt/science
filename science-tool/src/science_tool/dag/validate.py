"""Comprehensive validation for the DAG YAML + .dot layer.

Composes existing Phase 1 shape + ref checks with cross-file topology,
acyclicity, posterior-sanity, and JSON-schema-conformance checks.
``--strict`` adds migration-completeness gates.
"""

from __future__ import annotations

import functools
import json
import math
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

import jsonschema
import yaml

from science_tool.dag.paths import DagPaths
from science_tool.dag.refs import RefResolutionError, validate_ref_entry
from science_tool.dag.schema import EdgesYamlFile

Severity = Literal["error", "strict_error"]


@dataclass(frozen=True)
class ValidationFinding:
    """One check-failure entry."""

    dag: str
    edge_id: int | None
    rule: str
    severity: Severity
    message: str
    location: str | None

    def to_json(self) -> dict:  # type: ignore[type-arg]
        return {
            "dag": self.dag,
            "edge_id": self.edge_id,
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "location": self.location,
        }


@dataclass(frozen=True)
class ValidationReport:
    """Result of a ``validate_project()`` invocation."""

    today: date
    strict: bool
    findings: tuple[ValidationFinding, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not any(self._blocks(f) for f in self.findings)

    def _blocks(self, f: ValidationFinding) -> bool:
        return f.severity == "error" or (self.strict and f.severity == "strict_error")

    def to_json(self) -> dict:  # type: ignore[type-arg]
        return {
            "today": self.today.isoformat(),
            "strict": self.strict,
            "ok": self.ok,
            "findings": [f.to_json() for f in self.findings],
        }


def _discover_edge_yaml_files(paths: DagPaths) -> list[Path]:
    """Return the list of <slug>.edges.yaml files to validate."""
    if paths.dags is not None:
        return [paths.dag_dir / f"{slug}.edges.yaml" for slug in paths.dags]
    return sorted(paths.dag_dir.glob("*.edges.yaml"))


def _check_shape_and_refs(yaml_path: Path, project_root: Path) -> tuple[list[ValidationFinding], EdgesYamlFile | None]:
    """Run Pydantic shape validation and per-entry ref resolution.

    Returns (findings, parsed_model_or_None). If shape validation fails the
    model is None and ref checks are skipped.
    """
    findings: list[ValidationFinding] = []
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    try:
        model = EdgesYamlFile.model_validate(raw)
    except ValueError as exc:
        fallback_dag = yaml_path.stem.removesuffix(".edges")
        findings.append(
            ValidationFinding(
                dag=raw.get("dag", fallback_dag) if isinstance(raw, dict) else fallback_dag,
                edge_id=None,
                rule="shape",
                severity="error",
                message=str(exc),
                location=yaml_path.name,
            )
        )
        return findings, None

    for edge in model.edges:
        for ref_list_name in ("data_support", "lit_support", "eliminated_by"):
            entries = getattr(edge, ref_list_name, None) or []
            for entry in entries:
                try:
                    validate_ref_entry(entry, project_root)
                except RefResolutionError as exc:
                    findings.append(
                        ValidationFinding(
                            dag=model.dag,
                            edge_id=edge.id,
                            rule="refs",
                            severity="error",
                            message=str(exc),
                            location=yaml_path.name,
                        )
                    )
    return findings, model


def _check_posterior_sanity(model: EdgesYamlFile, yaml_path: Path) -> list[ValidationFinding]:
    """Numeric-sanity checks on posterior blocks."""
    findings: list[ValidationFinding] = []
    for edge in model.edges:
        post = edge.posterior
        if post is None:
            continue
        if post.beta is not None and not math.isfinite(post.beta):
            findings.append(
                ValidationFinding(
                    dag=model.dag,
                    edge_id=edge.id,
                    rule="posterior_finite",
                    severity="error",
                    message=f"posterior.beta is not finite (got {post.beta!r})",
                    location=yaml_path.name,
                )
            )
        if post.hdi_low is not None and post.hdi_high is not None and post.hdi_low > post.hdi_high:
            findings.append(
                ValidationFinding(
                    dag=model.dag,
                    edge_id=edge.id,
                    rule="posterior_hdi_ordered",
                    severity="error",
                    message=(f"posterior.hdi_low ({post.hdi_low}) > posterior.hdi_high ({post.hdi_high})"),
                    location=yaml_path.name,
                )
            )
        if post.prob_sign is not None and not (0.0 <= post.prob_sign <= 1.0):
            findings.append(
                ValidationFinding(
                    dag=model.dag,
                    edge_id=edge.id,
                    rule="posterior_prob_sign_range",
                    severity="error",
                    message=(f"posterior.prob_sign ({post.prob_sign}) is outside [0, 1]"),
                    location=yaml_path.name,
                )
            )
    return findings


_DOT_NODE_RE = re.compile(r"^\s*([A-Za-z_][\w]*)\s*(?:\[|;|$)")
_DOT_EDGE_RE = re.compile(r"^\s*([A-Za-z_][\w]*)\s*->\s*([A-Za-z_][\w]*)\s*(?:\[|;|$)")


def _parse_dot_topology(dot_path: Path) -> tuple[frozenset[str], frozenset[tuple[str, str]]]:
    """Parse nodes + directed edges from a .dot file.

    Regex-based: matches only simple ``id`` and ``id -> id`` statements. Skips
    comment lines (``//`` and ``/* */``), graph attributes, and nested
    subgraph declarations — attributes inside ``[...]`` are tolerated but
    multi-line attribute blocks are not supported. This mirrors the style of
    the existing number.py.

    Explicitly NOT handled (silently ignored by the regexes):
    - Edge chains: ``a -> b -> c;`` (author must split into two statements).
    - Quoted identifiers: ``"a-b" -> "c";``.
    - Port syntax: ``a:f1 -> b:f2;``.
    - Anonymous subgraph edge lists: ``{a b} -> c;``.
    These are all valid DOT but uncommon in mm30's curated DAGs. If a future
    project uses them, extend the regex set or swap in a real DOT parser.
    """
    text = dot_path.read_text(encoding="utf-8")

    # Strip block comments.
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)

    nodes: set[str] = set()
    edges: set[tuple[str, str]] = set()
    for raw_line in text.splitlines():
        line = re.sub(r"//.*$", "", raw_line).strip()
        if not line or line.startswith(("digraph", "graph", "subgraph", "}", "{")):
            continue
        # Skip top-level graph/edge/node attribute lines. This set is a
        # secondary safety net: most attribute lines are already rejected by
        # the edge/node regex terminators (``\[|;|$``), which don't match
        # ``key=value`` without trailing punctuation. The set below catches
        # the handful of lines that DO end in ``;`` and would otherwise be
        # mistaken for node declarations.
        stripped = line.split("=", 1)[0].strip()
        if stripped in {"rankdir", "labelloc", "label", "fontsize", "node", "edge", "style", "color"}:
            continue

        edge_m = _DOT_EDGE_RE.match(line)
        if edge_m:
            src, tgt = edge_m.group(1), edge_m.group(2)
            nodes.add(src)
            nodes.add(tgt)
            edges.add((src, tgt))
            continue

        node_m = _DOT_NODE_RE.match(line)
        if node_m:
            name = node_m.group(1)
            # Filter out keywords that look like identifiers.
            if name not in {"digraph", "graph", "subgraph", "node", "edge"}:
                nodes.add(name)
    return frozenset(nodes), frozenset(edges)


def _check_topology_parsed(
    model: EdgesYamlFile,
    dot_nodes: frozenset[str],
    dot_edges: frozenset[tuple[str, str]],
    dot_path: Path,
    yaml_path: Path,
) -> list[ValidationFinding]:
    """Cross-check YAML edges against pre-parsed .dot topology."""
    findings: list[ValidationFinding] = []
    yaml_edges: set[tuple[str, str]] = {(e.source, e.target) for e in model.edges}

    # YAML edges whose source/target is absent from .dot nodes.
    for edge in model.edges:
        missing_nodes = [n for n in (edge.source, edge.target) if n not in dot_nodes]
        if missing_nodes:
            findings.append(
                ValidationFinding(
                    dag=model.dag,
                    edge_id=edge.id,
                    rule="topology_node_mismatch",
                    severity="error",
                    message=(
                        f"YAML edge {edge.source!r} -> {edge.target!r} references "
                        f"node(s) {missing_nodes!r} not present in {dot_path.name}"
                    ),
                    location=yaml_path.name,
                )
            )

    # .dot edges that have no matching YAML record.
    for src, tgt in sorted(dot_edges - yaml_edges):
        findings.append(
            ValidationFinding(
                dag=model.dag,
                edge_id=None,
                rule="topology_missing_in_yaml",
                severity="error",
                message=(f".dot edge {src!r} -> {tgt!r} has no matching YAML record"),
                location=yaml_path.name,
            )
        )

    # YAML edges whose (source, target) pair is absent from .dot — only
    # emit when both endpoints exist as nodes (otherwise topology_node_mismatch
    # already covers it).
    for src, tgt in sorted(yaml_edges - dot_edges):
        if src in dot_nodes and tgt in dot_nodes:
            findings.append(
                ValidationFinding(
                    dag=model.dag,
                    edge_id=None,
                    rule="topology_missing_in_dot",
                    severity="error",
                    message=(f"YAML edge {src!r} -> {tgt!r} has no matching .dot edge"),
                    location=yaml_path.name,
                )
            )

    return findings


def _find_cycle(edges: frozenset[tuple[str, str]]) -> list[str] | None:
    """Return the node path of a cycle if one exists, else None."""
    graph: dict[str, list[str]] = {}
    for src, tgt in edges:
        graph.setdefault(src, []).append(tgt)
        graph.setdefault(tgt, [])

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in graph}

    def dfs(start: str) -> list[str] | None:
        stack: list[tuple[str, int]] = [(start, 0)]
        while stack:
            node, child_idx = stack[-1]
            if child_idx == 0:
                color[node] = GRAY
            children = graph.get(node, [])
            if child_idx >= len(children):
                color[node] = BLACK
                stack.pop()
                continue
            stack[-1] = (node, child_idx + 1)
            nxt = children[child_idx]
            if color[nxt] == GRAY:
                # Reconstruct cycle: all nodes on the current DFS stack are
                # GRAY (on the active path); nxt is the entry point of the
                # cycle.  Collect frames from the first occurrence of nxt
                # onwards, then append nxt to close the cycle.
                path: list[str] = [frame for frame, _ in stack]
                idx = next(i for i, (frame, _) in enumerate(stack) if frame == nxt)
                return path[idx:] + [nxt]
            if color[nxt] == WHITE:
                stack.append((nxt, 0))
        return None

    for node in sorted(graph):
        if color[node] == WHITE:
            cycle = dfs(node)
            if cycle is not None:
                return cycle
    return None


def _check_acyclicity(
    model: EdgesYamlFile, dot_edges: frozenset[tuple[str, str]], yaml_path: Path
) -> list[ValidationFinding]:
    cycle = _find_cycle(dot_edges)
    if cycle is None:
        return []
    path_str = " -> ".join(cycle)
    return [
        ValidationFinding(
            dag=model.dag,
            edge_id=None,
            rule="acyclicity",
            severity="error",
            message=f"cycle detected in .dot topology: {path_str}",
            location=yaml_path.name,
        )
    ]


_SCHEMA_PATH = Path(__file__).with_name("edges.schema.json")


@functools.lru_cache(maxsize=1)
def _load_schema() -> dict:  # type: ignore[type-arg]
    return json.loads(Path(_SCHEMA_PATH).read_text(encoding="utf-8"))


def _check_jsonschema_conformance(
    raw: dict,  # type: ignore[type-arg]
    dag_name: str,
    yaml_path: Path,
) -> list[ValidationFinding]:
    """Validate the raw YAML dict against the committed JSON Schema.

    Produces a finding per ValidationError. Schema-driven errors whose
    substance is already reported by Pydantic ``shape`` will duplicate; that
    is intentional — the purpose of this check is to act as a drift tripwire
    on the schema artifact.
    """
    try:
        schema = _load_schema()
    except FileNotFoundError:
        return [
            ValidationFinding(
                dag=dag_name,
                edge_id=None,
                rule="jsonschema_conformance",
                severity="error",
                message=(
                    f"edges.schema.json not found at {_SCHEMA_PATH}; "
                    "regenerate with `science-tool dag schema --output ...`"
                ),
                location=yaml_path.name,
            )
        ]

    findings: list[ValidationFinding] = []
    validator = jsonschema.Draft202012Validator(schema)
    for err in validator.iter_errors(raw):
        path_str = "/".join(str(p) for p in err.absolute_path) or "<root>"
        findings.append(
            ValidationFinding(
                dag=dag_name,
                edge_id=None,
                rule="jsonschema_conformance",
                severity="error",
                message=f"{path_str}: {err.message}",
                location=yaml_path.name,
            )
        )
    return findings


def _check_identification_explicit(
    raw: dict,  # type: ignore[type-arg]
    model: EdgesYamlFile,
    yaml_path: Path,
) -> list[ValidationFinding]:
    """Flag edges where 'identification' key is absent from the raw YAML."""
    findings: list[ValidationFinding] = []
    raw_edges = raw.get("edges") if isinstance(raw, dict) else None
    if not isinstance(raw_edges, list):
        return findings
    for raw_edge, edge in zip(raw_edges, model.edges, strict=False):
        if isinstance(raw_edge, dict) and "identification" not in raw_edge:
            findings.append(
                ValidationFinding(
                    dag=model.dag,
                    edge_id=edge.id,
                    rule="identification_missing",
                    severity="strict_error",
                    message=(
                        f"edge {edge.id} ({edge.source} -> {edge.target}) "
                        "is missing explicit 'identification:' key"
                    ),
                    location=yaml_path.name,
                )
            )
    return findings


def _check_description_nonempty(
    model: EdgesYamlFile,
    yaml_path: Path,
) -> list[ValidationFinding]:
    """Flag ref entries (data_support, lit_support, eliminated_by) with empty description."""
    findings: list[ValidationFinding] = []
    for edge in model.edges:
        for ref_list_name in ("data_support", "lit_support", "eliminated_by"):
            entries = getattr(edge, ref_list_name, None) or []
            for entry in entries:
                if not entry.description or not entry.description.strip():
                    findings.append(
                        ValidationFinding(
                            dag=model.dag,
                            edge_id=edge.id,
                            rule="description_nonempty",
                            severity="strict_error",
                            message=(
                                f"edge {edge.id}.{ref_list_name}[] has an entry "
                                f"with empty description"
                            ),
                            location=yaml_path.name,
                        )
                    )
    return findings


def _check_orphan_dot_nodes(
    model: EdgesYamlFile,
    dot_nodes: frozenset[str],
    dot_edges: frozenset[tuple[str, str]],
    yaml_path: Path,
) -> list[ValidationFinding]:
    """Flag .dot nodes that appear in no edge (neither as source nor target)."""
    connected: set[str] = set()
    for s, t in dot_edges:
        connected.add(s)
        connected.add(t)
    orphans = sorted(dot_nodes - connected)
    if not orphans:
        return []
    return [
        ValidationFinding(
            dag=model.dag,
            edge_id=None,
            rule="dot_nodes_unused",
            severity="strict_error",
            message=f"orphan .dot node(s): {orphans}",
            location=yaml_path.name,
        )
    ]


def _check_cross_dag_node_consistency(
    per_dag_nodes: dict[str, frozenset[str]],
) -> list[ValidationFinding]:
    """Detect case-differing node names across DAGs (e.g. 'prc2' vs 'PRC2').

    A name is inconsistent iff its case-insensitive bucket has >= 2 distinct
    case variants across DAGs.
    """
    findings: list[ValidationFinding] = []
    buckets: dict[str, set[tuple[str, str]]] = {}  # lower -> {(dag, variant)}
    for dag, nodes in per_dag_nodes.items():
        for node in nodes:
            buckets.setdefault(node.lower(), set()).add((dag, node))
    for lower, entries in sorted(buckets.items()):
        variants = {node for _, node in entries}
        if len(variants) < 2:
            continue
        variants_sorted = sorted(variants)
        findings.append(
            ValidationFinding(
                dag="",
                edge_id=None,
                rule="cross_dag_node_consistency",
                severity="strict_error",
                message=(
                    f"node name appears with inconsistent case across DAGs: "
                    f"{variants_sorted}"
                ),
                location=None,
            )
        )
    return findings


def validate_project(
    paths: DagPaths,
    *,
    strict: bool = False,
    today: date | None = None,
) -> ValidationReport:
    """Validate every DAG YAML under ``paths.dag_dir``.

    Always-on checks (block exit 0): shape + refs.
    Subsequent tasks will add: posterior sanity, topology, acyclicity,
    jsonschema conformance. Strict-only checks come last.
    """
    if today is None:
        today = date.today()
    # dag_dir defaults to <root>/doc/figures/dags under the research profile,
    # so three parents up recovers the project root.
    project_root = paths.dag_dir.parents[2]
    findings: list[ValidationFinding] = []
    per_dag_nodes: dict[str, frozenset[str]] = {}

    for yaml_path in _discover_edge_yaml_files(paths):
        if not yaml_path.exists():
            findings.append(
                ValidationFinding(
                    dag=yaml_path.stem.removesuffix(".edges"),
                    edge_id=None,
                    rule="shape",
                    severity="error",
                    message=f"edges.yaml file not found: {yaml_path}",
                    location=yaml_path.name,
                )
            )
            continue

        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        f, model = _check_shape_and_refs(yaml_path, project_root)
        findings.extend(f)
        if model is None:
            continue  # shape broken; skip downstream checks on this file

        # JSON-schema conformance tripwire (runs on the raw dict).
        findings.extend(_check_jsonschema_conformance(raw, model.dag, yaml_path))
        findings.extend(_check_posterior_sanity(model, yaml_path))

        if model.source_dot is not None:
            # source_dot may be project-root-relative (e.g. "doc/figures/dags/foo.dot")
            # or a bare filename (e.g. "foo.dot").
            candidate = project_root / model.source_dot
            dot_path = candidate if candidate.exists() else yaml_path.parent / model.source_dot
        else:
            dot_path = yaml_path.parent / f"{model.dag}.dot"

        if dot_path.exists():
            dot_nodes, dot_edges = _parse_dot_topology(dot_path)
            per_dag_nodes[model.dag] = dot_nodes
            findings.extend(_check_topology_parsed(model, dot_nodes, dot_edges, dot_path, yaml_path))
            findings.extend(_check_acyclicity(model, dot_edges, yaml_path))
            # Strict-only: orphan .dot nodes.
            findings.extend(_check_orphan_dot_nodes(model, dot_nodes, dot_edges, yaml_path))
        else:
            findings.append(
                ValidationFinding(
                    dag=model.dag,
                    edge_id=None,
                    rule="source_dot_missing",
                    severity="error",
                    message=f"source .dot file not found: {dot_path}",
                    location=yaml_path.name,
                )
            )

        # Strict-only checks (emitted regardless of `strict`; gating is in
        # ValidationReport.ok).
        findings.extend(_check_identification_explicit(raw, model, yaml_path))
        findings.extend(_check_description_nonempty(model, yaml_path))

    # Cross-DAG strict-only check (runs after all per-DAG loops complete).
    findings.extend(_check_cross_dag_node_consistency(per_dag_nodes))

    return ValidationReport(today=today, strict=strict, findings=tuple(findings))
