"""Validate DAG DOT topology against compiled relational propositions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

from science_model.propositions import PropositionEntity

from science_tool.dag.paths import DagPaths
from science_tool.dag.proposition_edges import load_relational_propositions

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


def _discover_dot_files(paths: DagPaths) -> list[Path]:
    if paths.dags is not None:
        return [paths.dag_dir / f"{slug}.dot" for slug in paths.dags]
    return sorted(
        path
        for path in paths.dag_dir.glob("*.dot")
        if not path.name.endswith(("-auto.dot", "-numbered.dot", ".reference"))
    )


def _project_root_from_paths(paths: DagPaths) -> Path:
    if paths.project_root is not None:
        return paths.project_root
    # Fallback is only for default-layout tests that construct DagPaths directly.
    return paths.dag_dir.parents[2]


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
                # cycle. Collect frames from the first occurrence of nxt
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


def _check_acyclicity_for_dot(
    dag: str,
    dot_edges: frozenset[tuple[str, str]],
    dot_path: Path,
) -> list[ValidationFinding]:
    cycle = _find_cycle(dot_edges)
    if cycle is None:
        return []
    path_str = " -> ".join(cycle)
    return [
        ValidationFinding(
            dag=dag,
            edge_id=None,
            rule="acyclicity",
            severity="error",
            message=f"cycle detected in .dot topology: {path_str}",
            location=dot_path.name,
        )
    ]


def _check_orphan_dot_nodes_for_dot(
    dag: str,
    dot_nodes: frozenset[str],
    dot_edges: frozenset[tuple[str, str]],
    dot_path: Path,
) -> list[ValidationFinding]:
    """Flag .dot nodes that appear in no edge (neither as source nor target)."""
    connected: set[str] = set()
    for source, target in dot_edges:
        connected.add(source)
        connected.add(target)
    orphans = sorted(dot_nodes - connected)
    if not orphans:
        return []
    return [
        ValidationFinding(
            dag=dag,
            edge_id=None,
            rule="dot_nodes_unused",
            severity="strict_error",
            message=f"orphan .dot node(s): {orphans}",
            location=dot_path.name,
        )
    ]


def _check_legacy_dag_metadata(
    propositions: list[PropositionEntity],
    per_dag_edges: dict[str, frozenset[tuple[str, str]]],
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for prop in propositions:
        if prop.legacy_patch is None or prop.legacy_patch not in per_dag_edges:
            continue
        if prop.subject is None or prop.object is None:
            continue
        if (prop.subject, prop.object) in per_dag_edges[prop.legacy_patch]:
            continue

        legacy_ref = (
            f"{prop.legacy_patch}#{prop.legacy_edge_id}"
            if prop.legacy_edge_id is not None
            else prop.legacy_patch
        )
        findings.append(
            ValidationFinding(
                dag=prop.legacy_patch,
                edge_id=prop.legacy_edge_id,
                rule="legacy_dag_edge_unresolved",
                severity="error",
                message=(
                    f"legacy DAG metadata {legacy_ref} points to proposition "
                    f"{prop.id!r} ({prop.subject} -> {prop.object}), but that edge is absent from "
                    f"{prop.legacy_patch}.dot."
                ),
                location=None,
            )
        )
    return findings


def _check_cross_dag_node_consistency(
    per_dag_nodes: dict[str, frozenset[str]],
) -> list[ValidationFinding]:
    """Detect case-differing node names across DAGs (e.g. 'prc2' vs 'PRC2').

    A name is inconsistent iff its case-insensitive bucket has >= 2 distinct
    case variants across DAGs.

    Note: DAGs whose ``.dot`` file was missing (and therefore emitted a
    ``source_dot_missing`` error earlier) are absent from ``per_dag_nodes`` and
    are not audited here. The cross-DAG check is a hygiene signal that piggy-
    backs on whatever nodes were successfully parsed.
    """
    findings: list[ValidationFinding] = []
    buckets: dict[str, set[tuple[str, str]]] = {}  # lower -> {(dag, variant)}
    for dag, nodes in per_dag_nodes.items():
        for node in nodes:
            buckets.setdefault(node.lower(), set()).add((dag, node))
    for _lower, entries in sorted(buckets.items()):
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
                message=(f"node name appears with inconsistent case across DAGs: {variants_sorted}"),
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
    """Validate DAG DOT files against compiled relational proposition edges."""
    if today is None:
        today = date.today()

    project_root = _project_root_from_paths(paths)
    dot_files = _discover_dot_files(paths)
    propositions = load_relational_propositions(project_root)
    proposition_pairs = {(prop.subject, prop.object) for prop in propositions}

    findings: list[ValidationFinding] = []
    per_dag_nodes: dict[str, frozenset[str]] = {}
    per_dag_edges: dict[str, frozenset[tuple[str, str]]] = {}

    for dot_path in dot_files:
        dag = dot_path.stem
        if not dot_path.exists():
            findings.append(
                ValidationFinding(
                    dag=dag,
                    edge_id=None,
                    rule="source_dot_missing",
                    severity="error",
                    message=f"source .dot file not found: {dot_path}",
                    location=dot_path.name,
                )
            )
            continue

        dot_nodes, dot_edges = _parse_dot_topology(dot_path)
        per_dag_nodes[dag] = dot_nodes
        per_dag_edges[dag] = dot_edges

        findings.extend(_check_acyclicity_for_dot(dag, dot_edges, dot_path))
        if strict:
            findings.extend(_check_orphan_dot_nodes_for_dot(dag, dot_nodes, dot_edges, dot_path))

        for source, target in sorted(dot_edges):
            if (source, target) in proposition_pairs:
                continue
            findings.append(
                ValidationFinding(
                    dag=dag,
                    edge_id=None,
                    rule="proposition_edge_missing",
                    severity="error",
                    message=(
                        f"DOT edge {source!r} -> {target!r} ({source} -> {target}) has no compiled "
                        "relational proposition. Author or compile a matching workbench row."
                    ),
                    location=dot_path.name,
                )
            )

    findings.extend(_check_legacy_dag_metadata(propositions, per_dag_edges))

    if strict:
        findings.extend(_check_cross_dag_node_consistency(per_dag_nodes))

    return ValidationReport(today=today, strict=strict, findings=tuple(findings))
