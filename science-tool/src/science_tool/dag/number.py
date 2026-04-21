"""Bidirectional .dot <-> edges.yaml edge-ID sync for science-tool DAGs.

Lifted from mm30's ``doc/figures/dags/_number_edges.py``.

Reads each source ``.dot`` file, assigns sequential edge IDs in order of
appearance, writes a ``<slug>-numbered.dot`` variant with ``[N]`` prefixed on
every edge label, and emits a ``<slug>.edges.yaml`` stub with
``(id, source, target, source_label, target_label, original_label,
edge_style)`` extracted for downstream evidence curation.

By default an existing ``.edges.yaml`` is preserved — it contains curated
evidence.  Pass ``force_stubs=True`` only when intentionally resetting
curation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from science_tool.dag.paths import DagPaths
from science_tool.dag.render import EDGE_RE, _discover_slugs, _flatten_multiline_attrs

# Match a node definition:  name [label="...", fillcolor="...", ...];
_NODE_RE = re.compile(r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\[(?P<attrs>[^\]]*)\]\s*;?\s*$")
_LABEL_RE = re.compile(r'label\s*=\s*"([^"]*)"')
_STYLE_RE = re.compile(r'style\s*=\s*(?:"([^"]*)"|([A-Za-z]+))')


@dataclass
class _Edge:
    id: int
    src: str
    tgt: str
    label: str = ""
    style: str = "solid"
    src_label: str = ""
    tgt_label: str = ""


@dataclass
class _ParsedDag:
    nodes: dict[str, str] = field(default_factory=dict)  # name -> human label
    edges: list[_Edge] = field(default_factory=list)


def _extract_node_label(attrs: str) -> str:
    m = _LABEL_RE.search(attrs)
    if not m:
        return ""
    return m.group(1).replace("\\n", " ").strip()


def _parse_dag(dot_path: Path) -> _ParsedDag:
    parsed = _ParsedDag()
    edge_id = 0
    raw = dot_path.read_text()
    flat = _flatten_multiline_attrs(raw)
    for line in flat.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue

        # Node definitions (inside or outside clusters).
        nm = _NODE_RE.match(line)
        if nm and "->" not in line:
            attrs = nm.group("attrs")
            if "label=" in attrs:
                parsed.nodes[nm.group("name")] = _extract_node_label(attrs)
                continue

        # Edge definitions.
        em = EDGE_RE.match(line)
        if em:
            src = em.group("src")
            tgt = em.group("tgt")
            attrs = em.group("attrs") or ""
            label = ""
            if "label=" in attrs:
                lm = _LABEL_RE.search(attrs)
                if lm:
                    label = lm.group(1).replace("\\n", " ").strip()
            style = "solid"
            sm = _STYLE_RE.search(attrs)
            if sm:
                style = sm.group(1) or sm.group(2) or "solid"
            edge_id += 1
            parsed.edges.append(_Edge(id=edge_id, src=src, tgt=tgt, label=label, style=style))

    # Resolve src/tgt human labels.
    for e in parsed.edges:
        e.src_label = parsed.nodes.get(e.src, e.src)
        e.tgt_label = parsed.nodes.get(e.tgt, e.tgt)
    return parsed


def _emit_numbered_dot(dot_path: Path, parsed: _ParsedDag, out_path: Path) -> None:
    """Rewrite the DOT with [N] prefixed to every edge label.

    Walks the source in order, matching each edge line against EDGE_RE and
    injecting the label. When an edge already has a label, prefix [N]; when
    it has no label, add label="[N]".
    """
    text_lines = _flatten_multiline_attrs(dot_path.read_text()).splitlines()
    out_lines: list[str] = []
    edge_iter = iter(parsed.edges)
    current: _Edge | None = None

    def next_edge() -> _Edge | None:
        nonlocal current
        try:
            current = next(edge_iter)
        except StopIteration:
            current = None
        return current

    for line in text_lines:
        em = EDGE_RE.match(line)
        if em:
            edge = next_edge()
            if edge is None:
                out_lines.append(line)
                continue
            src = em.group("src")
            tgt = em.group("tgt")
            assert src == edge.src and tgt == edge.tgt, f"edge mismatch: {src}->{tgt} vs {edge.src}->{edge.tgt}"
            attrs = em.group("attrs") or ""
            tag = f"[{edge.id}]"
            if "label=" in attrs:
                new_attrs = _LABEL_RE.sub(lambda m: f'label="{tag} {m.group(1)}"', attrs, count=1)
            else:
                add = f'label="{tag}"'
                new_attrs = add if not attrs.strip() else f"{attrs.strip()}, {add}"
            out_lines.append(f"{em.group('indent')}{src} -> {tgt} [{new_attrs}];")
        else:
            out_lines.append(line)
    out_path.write_text("\n".join(out_lines) + "\n")


def _emit_edge_stubs(parsed: _ParsedDag, out_path: Path, dag_slug: str) -> None:
    payload = {
        "dag": dag_slug,
        "source_dot": f"doc/figures/dags/{dag_slug}.dot",
        "edges": [
            {
                "id": e.id,
                "source": e.src,
                "target": e.tgt,
                "source_label": e.src_label,
                "target_label": e.tgt_label,
                "original_label": e.label,
                "edge_style": e.style,
                # Placeholders for curation.
                "relation": "",
                "edge_status": "",
                "identification": "",
                "description": "",
                "data_support": [],
                "lit_support": [],
            }
            for e in parsed.edges
        ],
    }
    out_path.write_text(yaml.safe_dump(payload, sort_keys=False, width=100))


def number_one(dag_dir: Path, slug: str, *, force_stubs: bool = False) -> None:
    """Number edges in one DAG's .dot, sync with edges.yaml.

    Writes ``<slug>-numbered.dot`` with ``[N]`` prefixed on every edge label.
    Creates ``<slug>.edges.yaml`` if it does not exist; preserves it when
    ``force_stubs=False`` (default).  Pass ``force_stubs=True`` to
    intentionally reset curation.
    """
    dot_path = dag_dir / f"{slug}.dot"
    parsed = _parse_dag(dot_path)
    _emit_numbered_dot(dot_path, parsed, dag_dir / f"{slug}-numbered.dot")
    stub_path = dag_dir / f"{slug}.edges.yaml"
    if stub_path.exists() and not force_stubs:
        return
    _emit_edge_stubs(parsed, stub_path, slug)


def number_all(paths: DagPaths, *, force_stubs: bool = False) -> None:
    """Number edges across every discovered DAG.

    Discovers slugs from ``paths.dag_dir`` when ``paths.dags`` is ``None``.
    """
    slugs = list(paths.dags) if paths.dags else _discover_slugs(paths.dag_dir)
    for slug in slugs:
        number_one(paths.dag_dir, slug, force_stubs=force_stubs)
