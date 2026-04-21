"""DAG rendering with precedence matrix and eliminated-edge support.

Lifted from mm30's ``doc/figures/dags/_render_styled.py`` (t186).
Single-source-of-truth rendering:
  - Topology (nodes, subgraphs, clusters) from ``<slug>.dot``
  - Semantics (status, identification, posterior, etc.) from ``<slug>.edges.yaml``

Produces ``<slug>-auto.dot`` and ``<slug>-auto.png`` with per-edge styling derived
from the YAML:

| edge_status | color     | penwidth | style  |
|-------------|-----------|----------|--------|
| supported   | #2e7d32   | 2.5      | solid  |
| tentative   | #1565c0   | 1.6      | solid  |
| structural  | #757575   | 1.0      | solid  |
| unknown     | #c62828   | 1.2      | dashed |
| eliminated  | #9e9e9e   | 1.0      | dotted |

``eliminated`` is for edges whose hypothesized mechanism has been retracted or
ruled out by subsequent evidence.  The edge stays in the DAG as a provenance
record; a ``[✗]`` marker is prepended to the label.

Overrides:
  - Posterior HDI crosses zero → force ``style=dashed`` (uncertainty cue).
  - Posterior |β| present → scale penwidth = 1.6 + |β|·4, capped at 4.5.
  - Identification marker appended to label:
      interventional → "[I]", longitudinal → "[L]"
      (observational / structural / none → unmarked).
  - Posterior auto-label suffix: "β=±0.XX" and "HR=X.X" when available.
  - ``edge_status: eliminated`` wins over posterior-based styling (the
    mechanism has been retracted; visual should not imply live support).

YAML is read directly via ``yaml.safe_load``; schema validation is a separate
concern (the render path must tolerate legacy ``doi: null`` entries and other
not-yet-migrated data).
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

import yaml

from science_tool.dag.paths import DagPaths

log = logging.getLogger(__name__)

STATUS_STYLES = {
    "supported": {"color": "#2e7d32", "penwidth": 2.5, "style": "solid"},
    "tentative": {"color": "#1565c0", "penwidth": 1.6, "style": "solid"},
    "structural": {"color": "#757575", "penwidth": 1.0, "style": "solid"},
    "unknown": {"color": "#c62828", "penwidth": 1.2, "style": "dashed"},
    "eliminated": {"color": "#9e9e9e", "penwidth": 1.0, "style": "dotted"},
}

IDENT_MARKERS = {
    "interventional": "[I]",
    "longitudinal": "[L]",
    "observational": "",
    "structural": "",
    "none": "",
    "": "",
}


# Identification-axis modifiers — applied on TOP of the edge_status color/width.
# Intent: identification strength is visually legible at a glance, not buried
# in the [I]/[L] label markers. Interventional gets a double-line color
# ("COLOR:white:COLOR" in graphviz parallel-line syntax). Longitudinal keeps a
# single line but gets a thicker arrowhead. Observational is the default.
def identification_color(base_color: str, ident: str) -> str:
    if ident == "interventional":
        # Double-line: same color above and below a thin white gap.
        return f"{base_color}:#ffffff:{base_color}"
    return base_color


def identification_arrowhead(ident: str) -> str:
    if ident == "longitudinal":
        return "vee"
    return "normal"


# Edge regex copied from _number_edges.py
EDGE_RE = re.compile(
    r"^(?P<indent>\s*)(?P<src>[A-Za-z_][A-Za-z0-9_]*)\s*->\s*"
    r"(?P<tgt>[A-Za-z_][A-Za-z0-9_]*)\s*(?:\[(?P<attrs>[^\]]*)\])?\s*;?\s*$"
)


def _flatten_multiline_attrs(text: str) -> str:
    buf = ""
    depth = 0
    for ch in text:
        if ch == "[":
            depth += 1
            buf += ch
        elif ch == "]":
            depth -= 1
            buf += ch
        elif ch == "\n" and depth > 0:
            buf += " "
        else:
            buf += ch
    return buf


def _format_beta(beta: float) -> str:
    sign = "+" if beta >= 0 else "−"
    return f"β={sign}{abs(beta):.2f}"


def style_for_edge(edge: dict) -> dict:  # type: ignore[type-arg]
    """Compute graphviz style attributes from an edge's YAML record."""
    status = edge.get("edge_status") or "tentative"
    ident = edge.get("identification") or "observational"
    base = STATUS_STYLES.get(status, STATUS_STYLES["tentative"]).copy()

    # Posterior adjustments.
    post = edge.get("posterior") or {}
    beta = post.get("beta")
    hdi_low = post.get("hdi_low")
    hdi_high = post.get("hdi_high")
    hr = post.get("hr")

    # Eliminated wins over posterior-driven sizing: if the mechanism has
    # been retracted, the visual must not imply live support via a thick line.
    if status == "eliminated":
        pass  # keep STATUS_STYLES["eliminated"] values
    else:
        if beta is not None:
            try:
                base["penwidth"] = min(4.5, 1.6 + abs(float(beta)) * 4.0)
            except (TypeError, ValueError):
                pass

        if hdi_low is not None and hdi_high is not None:
            try:
                if float(hdi_low) <= 0 <= float(hdi_high):
                    base["style"] = "dashed"
            except (TypeError, ValueError):
                pass

        if status == "structural" and ident == "structural":
            base["style"] = "dotted"

    # Label construction.
    original = edge.get("original_label", "") or ""
    parts = []
    eid = edge.get("id")
    if eid is not None:
        parts.append(f"[{eid}]")
    if status == "eliminated":
        parts.append("[✗]")
    if original:
        # Strip prior [N] prefix from numbered variants; keep base text only.
        parts.append(re.sub(r"^\[\d+\]\s*", "", original))
    suffix_bits = []
    if beta is not None:
        try:
            b = float(beta)
            if abs(b) >= 0.05:
                suffix_bits.append(_format_beta(b))
        except (TypeError, ValueError):
            pass
    if hr is not None:
        try:
            suffix_bits.append(f"HR={float(hr):.1f}")
        except (TypeError, ValueError):
            pass
    marker = IDENT_MARKERS.get(ident, "")
    if marker:
        suffix_bits.append(marker)

    label = " ".join(parts).strip()
    if suffix_bits:
        label = (label + "\\n" + " · ".join(suffix_bits)).strip()

    ident_color = identification_color(base["color"], ident)
    attrs = {
        "color": f'"{ident_color}"',
        "penwidth": f"{base['penwidth']:.1f}",
        "style": f'"{base["style"]}"',
        "arrowhead": identification_arrowhead(ident),
        "label": f'"{label}"',
        "fontsize": "10",
        "fontcolor": f'"{base["color"]}"',
    }
    return attrs


def emit_styled_dot(dot_path: Path, edges: list[dict], out_path: Path) -> None:  # type: ignore[type-arg]
    """Rewrite the topology DOT with auto-styled edges + a legend subgraph."""
    text = _flatten_multiline_attrs(dot_path.read_text())
    lines = text.splitlines()
    out: list[str] = []
    edge_iter = iter(edges)

    def next_edge() -> dict | None:  # type: ignore[type-arg]
        try:
            return next(edge_iter)
        except StopIteration:
            return None

    # Inject a header banner so the auto-styled version is visually distinct.
    banner_inserted = False
    for line in lines:
        # Replace graph-level label with an auto-styling banner.
        if not banner_inserted and re.match(r"\s*label=<", line):
            m = re.match(r"(\s*)(label=<.+?>);?\s*$", line)
            if m:
                indent = m.group(1)
                original = m.group(2)
                auto_banner = (
                    '<br/><font point-size="9" color="#555"><i>'
                    "auto-styled from edges.yaml — color=edge_status, width=|β|, "
                    "style=HDI-crosses-zero-dashed, [I]=interventional, [L]=longitudinal"
                    "</i></font>"
                )
                # Inject the banner right before the closing `>`.
                new_label = re.sub(r">\s*$", auto_banner + ">", original)
                out.append(f"{indent}{new_label};")
                banner_inserted = True
                continue

        em = EDGE_RE.match(line)
        if em:
            edge = next_edge()
            if edge is None:
                out.append(line)
                continue
            assert em.group("src") == edge["source"] and em.group("tgt") == edge["target"], (
                f"edge mismatch {em.group('src')}->{em.group('tgt')} "
                f"vs {edge['source']}->{edge['target']} (id={edge['id']})"
            )
            attrs = style_for_edge(edge)
            attr_str = ", ".join(f"{k}={v}" for k, v in attrs.items())
            out.append(f"{em.group('indent')}{edge['source']} -> {edge['target']} [{attr_str}];")
            continue

        out.append(line)

    # Append a legend subgraph before the closing brace.
    # Two axes: color/width = edge_status; double-line/arrowhead = identification.
    legend = [
        "",
        "  // --- Auto-legend (two-axis: edge_status + identification) ---",
        "  subgraph cluster_autolegend {",
        "    label=<<b>Legend</b> (auto-styled)  —  color/width = edge_status; double-line = interventional; vee arrow = longitudinal>;",
        '    fontsize=10; color="#999"; style="rounded"; margin=12;',
        "    node [shape=plaintext, fontsize=9];",
        '    lg_supp_a [label="supported"]; lg_supp_b [label=""];',
        '    lg_tent_a [label="tentative"]; lg_tent_b [label=""];',
        '    lg_struct_a [label="structural"]; lg_struct_b [label=""];',
        '    lg_unk_a [label="unknown"]; lg_unk_b [label=""];',
        '    lg_elim_a [label="[✗] eliminated"]; lg_elim_b [label=""];',
        '    lg_int_a [label="[I] interventional"]; lg_int_b [label=""];',
        '    lg_long_a [label="[L] longitudinal"]; lg_long_b [label=""];',
        '    lg_supp_a -> lg_supp_b [color="#2e7d32", penwidth=2.5, style="solid", arrowhead=normal];',
        '    lg_tent_a -> lg_tent_b [color="#1565c0", penwidth=1.6, style="solid", arrowhead=normal];',
        '    lg_struct_a -> lg_struct_b [color="#757575", penwidth=1.0, style="dotted", arrowhead=normal];',
        '    lg_unk_a -> lg_unk_b [color="#c62828", penwidth=1.2, style="dashed", arrowhead=normal];',
        '    lg_elim_a -> lg_elim_b [color="#9e9e9e", penwidth=1.0, style="dotted", arrowhead=normal];',
        '    lg_int_a -> lg_int_b [color="#2e7d32:#ffffff:#2e7d32", penwidth=2.5, style="solid", arrowhead=normal];',
        '    lg_long_a -> lg_long_b [color="#2e7d32", penwidth=2.5, style="solid", arrowhead=vee];',
        "  }",
    ]
    # Insert legend before the closing `}` of the outermost digraph.
    # We find the last `}` in the output.
    for i in range(len(out) - 1, -1, -1):
        if out[i].strip() == "}":
            out[i:i] = legend
            break

    out_path.write_text("\n".join(out) + "\n")


def render_png(dot_path: Path, png_path: Path, dpi: int = 150) -> None:
    """Render a .dot file to PNG via graphviz.

    Logs a warning and returns without raising if graphviz is not installed or
    returns a non-zero exit code.  Tests that don't need PNGs should not require
    graphviz to be present.
    """
    try:
        result = subprocess.run(
            ["dot", "-Tpng", f"-Gdpi={dpi}", str(dot_path), "-o", str(png_path)],
            check=False,
            capture_output=True,
        )
        if result.returncode != 0:
            log.warning(
                "graphviz dot exited with code %d for %s: %s",
                result.returncode,
                dot_path,
                result.stderr.decode(errors="replace").strip(),
            )
    except FileNotFoundError:
        log.warning("graphviz `dot` not found; skipping PNG render for %s", dot_path)


def _discover_slugs(dag_dir: Path) -> list[str]:
    """Find every <slug>.edges.yaml file (sorted)."""
    return sorted(p.stem.replace(".edges", "") for p in dag_dir.glob("*.edges.yaml"))


def render_one(dag_dir: Path, slug: str) -> None:
    """Render one slug — reads <slug>.dot + <slug>.edges.yaml, writes <slug>-auto.{dot,png}."""
    dot_path = dag_dir / f"{slug}.dot"
    yaml_path = dag_dir / f"{slug}.edges.yaml"
    data = yaml.safe_load(yaml_path.read_text())
    edges = data["edges"]
    out_dot = dag_dir / f"{slug}-auto.dot"
    out_png = dag_dir / f"{slug}-auto.png"
    emit_styled_dot(dot_path, edges, out_dot)
    render_png(out_dot, out_png)


def render_all(paths: DagPaths) -> None:
    """Render every discovered DAG's -auto.dot + -auto.png."""
    slugs = list(paths.dags) if paths.dags else _discover_slugs(paths.dag_dir)
    for slug in slugs:
        render_one(paths.dag_dir, slug)
