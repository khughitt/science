"""DAG rendering with channel-driven proposition edge styling.

Lifted from mm30's ``doc/figures/dags/_render_styled.py`` (t186).
Single-source-of-truth rendering:
  - Topology (nodes, subgraphs, clusters) from ``<slug>.dot``
  - Semantics (status, identification, posterior, etc.) from compiled
    proposition edge dicts

Produces ``<slug>-auto.dot`` and ``<slug>-auto.png`` with per-edge styling.

Two rendering modes are selected automatically per edge record:

**Channel-driven mode** (design §6) — used when the orthogonal channel fields
``polarity``, ``belief_magnitude``, ``claim_layer``, ``refuted``, and
``has_grounding_evidence``. Styling derives from the independent
channels:

  - ``polarity``              → hue  (positive/negative/unsigned/not_applicable
                                       each get a distinct colour)
  - ``identification``        → line-style + arrowhead
  - ``belief_magnitude``      → penwidth base intensity
  - ``contested``             → dashed-style overlay + ``[?]`` label marker
  - ``derived_edge_status``   → computed via ``derived_edge_status(...)`` and
                                  surfaced in the returned attrs dict; NOT used
                                  as a styling source.

``eliminated`` is for edges whose hypothesized mechanism has been retracted or
ruled out by subsequent evidence.  The edge stays in the DAG as a provenance
record; a ``[✗]`` marker is prepended to the label.

Overrides (both modes):
  - Posterior HDI crosses zero → force ``style=dashed`` (uncertainty cue).
  - Posterior |β| present → scale penwidth = 1.6 + |β|·4, capped at 4.5.
  - Identification encoded by arrowhead:
      observational/structural/none → normal, interventional → diamond,
      longitudinal → odot.
  - Posterior auto-label suffix: "β=±0.XX" and "HR=X.X" when available.
  - ``refuted: true`` wins over posterior-based sizing (the mechanism has been
    retracted; visual should not imply live support).

Every DOT edge must have a compiled proposition edge with the same
``source``/``target`` pair. Render fails before writing derived artifacts when
the proposition view does not cover the DOT topology.
"""

from __future__ import annotations

import logging
import re
import subprocess
from collections import Counter, defaultdict, deque
from pathlib import Path

from science_tool.dag.paths import DagPaths
from science_tool.dag.validate import _dot_edge_occurrences
from science_tool.graph.derived_status import derived_edge_status

log = logging.getLogger(__name__)

ELIMINATED_STYLE = {"color": "#9e9e9e", "penwidth": 1.0, "style": "dotted"}

# ---------------------------------------------------------------------------
# Channel-driven styling constants (design §6)
# ---------------------------------------------------------------------------

# polarity → hue. Colour signals direction-of-effect, not epistemic status.
POLARITY_HUES = {
    "positive": "#2e7d32",    # green  — promotes / increases
    "negative": "#b71c1c",    # dark-red — suppresses / decreases
    "unsigned": "#1565c0",    # blue  — effect exists, sign not claimed
    "not_applicable": "#546e7a",  # blue-grey — no causal direction axis
}

# belief_magnitude → penwidth base (before posterior |β| scaling).
MAGNITUDE_PENWIDTH = {
    "well_supported": 2.5,
    "supported": 2.5,
    "fragile": 1.6,
    "speculative": 1.2,
}
_DEFAULT_MAGNITUDE_PENWIDTH = 1.0

# Sentinel: presence of ANY of these keys switches to channel-driven mode.
_CHANNEL_FIELDS = frozenset({"polarity", "belief_magnitude", "claim_layer", "refuted", "has_grounding_evidence"})


def identification_arrowhead(ident: str) -> str:
    if ident == "interventional":
        return "diamond"
    if ident == "longitudinal":
        return "odot"
    return "normal"


# Edge regex copied from _number_edges.py
EDGE_RE = re.compile(
    r"^(?P<indent>\s*)(?P<src>[A-Za-z_][A-Za-z0-9_]*)\s*->\s*"
    r"(?P<tgt>[A-Za-z_][A-Za-z0-9_]*)\s*(?:\[(?P<attrs>[^\]]*)\])?\s*;?\s*$"
)


def _match_dot_edge_line(line: str) -> re.Match[str] | None:
    comment_stripped = re.sub(r"/\*.*?\*/", "", line)
    comment_stripped = re.sub(r"//.*$", "", comment_stripped)
    return EDGE_RE.match(comment_stripped)


def _strip_dot_comments_from_line(line: str, *, in_block_comment: bool) -> tuple[str, bool]:
    stripped = []
    i = 0
    while i < len(line):
        if in_block_comment:
            end = line.find("*/", i)
            if end == -1:
                return "".join(stripped), True
            i = end + 2
            in_block_comment = False
            continue

        line_comment = line.find("//", i)
        block_comment = line.find("/*", i)
        if line_comment == -1 and block_comment == -1:
            stripped.append(line[i:])
            break
        if line_comment != -1 and (block_comment == -1 or line_comment < block_comment):
            stripped.append(line[i:line_comment])
            break

        stripped.append(line[i:block_comment])
        i = block_comment + 2
        in_block_comment = True

    return "".join(stripped), in_block_comment


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


def _style_base_from_channels(edge: dict) -> tuple[dict, str]:  # type: ignore[type-arg]
    """Return (base_style_dict, derived_status_str) driven by orthogonal channels.

    Called only when channel fields are present on the edge record.  ``base``
    holds the mutable colour / penwidth / style that subsequent adjustments
    (posterior, HDI, identification) may further modify.
    """
    polarity = edge.get("polarity") or "unsigned"
    belief_magnitude = edge.get("belief_magnitude") or "speculative"
    claim_layer = edge.get("claim_layer") or "causal_effect"
    refuted = bool(edge.get("refuted", False))
    has_grounding = bool(edge.get("has_grounding_evidence", False))

    des = derived_edge_status(
        belief_magnitude=belief_magnitude,
        refuted=refuted,
        claim_layer=claim_layer,
        has_grounding_evidence=has_grounding,
    )

    # Hue comes from polarity, not from derived_edge_status.
    color = POLARITY_HUES.get(polarity, POLARITY_HUES["unsigned"])

    # Intensity (penwidth base) comes from belief_magnitude.
    penwidth = MAGNITUDE_PENWIDTH.get(belief_magnitude, _DEFAULT_MAGNITUDE_PENWIDTH)

    # Style defaults to solid; identification and posterior may override below.
    style = "solid"

    # eliminated keeps its muted grey regardless of polarity (mechanism retracted).
    if des.status == "eliminated":
        color = ELIMINATED_STYLE["color"]
        penwidth = ELIMINATED_STYLE["penwidth"]
        style = ELIMINATED_STYLE["style"]
    elif des.status == "unknown":
        style = "dashed"

    return {"color": color, "penwidth": penwidth, "style": style}, des.status


def style_for_edge(edge: dict) -> dict:  # type: ignore[type-arg]
    """Compute graphviz style attributes from a proposition-backed edge."""
    ident = edge.get("identification") or "observational"

    missing_channels = sorted(_CHANNEL_FIELDS - set(edge.keys()))
    if missing_channels:
        raise ValueError(f"proposition edge missing channel field(s): {', '.join(missing_channels)}")

    base, derived_status = _style_base_from_channels(edge)
    status = derived_status

    # Posterior adjustments (both modes — eliminated always wins).
    post = edge.get("posterior") or {}
    beta = post.get("beta")
    hdi_low = post.get("hdi_low")
    hdi_high = post.get("hdi_high")
    hr = post.get("hr")

    # Eliminated wins over posterior-driven sizing.
    if status == "eliminated":
        pass  # keep eliminated values
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

    # contested overlay: switch to dashed and add a [?] label marker.
    contested = bool(edge.get("contested", False))
    if contested and status not in ("eliminated",):
        base["style"] = "dashed"

    # Label construction.
    original = edge.get("original_label", "") or ""
    parts = []
    eid = edge.get("id")
    if eid is not None:
        parts.append(f"[{eid}]")
    if status == "eliminated":
        parts.append("[✗]")
    if contested:
        parts.append("[?]")
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
    label = " ".join(parts).strip()
    if suffix_bits:
        label = (label + "\\n" + " · ".join(suffix_bits)).strip()

    attrs = {
        "color": f'"{base["color"]}"',
        "penwidth": f"{base['penwidth']:.1f}",
        "style": f'"{base["style"]}"',
        "arrowhead": identification_arrowhead(ident),
        "label": f'"{label}"',
        "fontsize": "10",
        "fontcolor": f'"{base["color"]}"',
        "derived_edge_status": derived_status,
    }
    return attrs


def _edge_lookup(edges: list[dict]) -> defaultdict[tuple[str, str], deque[dict]]:  # type: ignore[type-arg]
    lookup: defaultdict[tuple[str, str], deque[dict]] = defaultdict(deque)
    for edge in edges:
        lookup[(edge["source"], edge["target"])].append(edge)
    return lookup


def emit_styled_dot(dot_path: Path, edges: list[dict], out_path: Path) -> None:  # type: ignore[type-arg]
    """Rewrite the topology DOT with auto-styled edges + a legend subgraph."""
    text = _flatten_multiline_attrs(dot_path.read_text())
    lines = text.splitlines()
    out: list[str] = []
    edges_by_pair = _edge_lookup(edges)

    # Inject a header banner so the auto-styled version is visually distinct.
    banner_inserted = False
    in_block_comment = False
    for line in lines:
        uncommented_line, in_block_comment = _strip_dot_comments_from_line(
            line,
            in_block_comment=in_block_comment,
        )
        # Replace graph-level label with an auto-styling banner.
        if not banner_inserted and re.match(r"\s*label=<", uncommented_line):
            m = re.match(r"(\s*)(label=<.+?>);?\s*$", uncommented_line)
            if m:
                indent = m.group(1)
                original = m.group(2)
                auto_banner = (
                    '<br/><font point-size="9" color="#555"><i>'
                    "auto-styled from proposition edges — color=polarity, width=belief/|β|, "
                    "style=derived status + HDI, arrowhead=identification"
                    "</i></font>"
                )
                # Inject the banner right before the closing `>`.
                new_label = re.sub(r">\s*$", auto_banner + ">", original)
                out.append(f"{indent}{new_label};")
                banner_inserted = True
                continue

        em = EDGE_RE.match(uncommented_line)
        if em:
            queue = edges_by_pair[(em.group("src"), em.group("tgt"))]
            if not queue:
                out.append(line)
                continue
            edge = queue.popleft()
            attrs = style_for_edge(edge)
            # Exclude meta-keys that are not valid graphviz attributes.
            dot_attrs = {k: v for k, v in attrs.items() if k != "derived_edge_status"}
            attr_str = ", ".join(f"{k}={v}" for k, v in dot_attrs.items())
            out.append(f"{em.group('indent')}{edge['source']} -> {edge['target']} [{attr_str}];")
            continue

        out.append(line)

    # Append a compact footer legend before the closing brace. Keep samples as
    # inline glyphs so Graphviz does not allocate a separate mini-graph.
    legend = [
        "",
        "  // --- Auto-footer legend (polarity, belief, and identification) ---",
        "  subgraph cluster_auto_footer_legend {",
        "    rank=sink;",
        '    label="";',
        '    color="#bdbdbd"; style="rounded"; margin=4;',
        "    node [shape=plaintext, fontsize=9];",
        '    footer_legend [label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="3" color="#bdbdbd">',
        (
            '      <tr><td bgcolor="#f5f5f5"><b>Auto legend</b></td>'
            '<td bgcolor="#f5f5f5"><b>polarity/belief</b>: color / width / style</td>'
            '<td bgcolor="#f5f5f5"><b>identification</b>: arrowhead</td></tr>'
        ),
        (
            '      <tr><td align="left">belief</td>'
            '<td align="left"><font color="#2e7d32">&#9473;&#9473;&#9654;</font> supported &nbsp; '
            '<font color="#1565c0">&#9472;&#9472;&#9654;</font> tentative &nbsp; '
            '<font color="#757575">&#8943;&#9654;</font> structural</td>'
            '<td align="left"><font color="#2e7d32">&#9473;&#9473;&#9654;</font> normal: '
            "observational / structural / none</td></tr>"
        ),
        (
            '      <tr><td align="left"></td>'
            '<td align="left"><font color="#c62828">&#9548;&#9548;&#9654;</font> unknown &nbsp; '
            '<font color="#9e9e9e">&#8943;&#9654;</font> [x] eliminated</td>'
            '<td align="left"><font color="#2e7d32">&#9473;&#9473;&#9670;</font> interventional &nbsp; '
            '<font color="#2e7d32">&#9473;&#9473;&#8857;</font> longitudinal</td></tr>'
        ),
        "    </table>>];",
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
    """Find every source <slug>.dot file (sorted)."""
    return sorted(
        p.stem
        for p in dag_dir.glob("*.dot")
        if not (
            p.name.endswith("-auto.dot")
            or p.name.endswith("-numbered.dot")
            or p.name.endswith(".reference")
        )
    )


def _assert_dot_edges_backed(slug: str, dot_path: Path, edges: list[dict]) -> None:  # type: ignore[type-arg]
    """Fail before writing if any DOT edge occurrence lacks a compiled proposition edge."""
    dot_edge_counts = Counter(_dot_edge_occurrences(dot_path))
    available_counts = Counter((str(edge["source"]), str(edge["target"])) for edge in edges)
    missing = sorted(
        edge_pair
        for edge_pair, dot_count in dot_edge_counts.items()
        if available_counts[edge_pair] < dot_count
    )
    if missing:
        missing_text = ", ".join(f"{source} -> {target}" for source, target in missing)
        raise ValueError(f"{slug}: no compiled proposition edge for DOT edge(s): {missing_text}")


def render_one(
    dag_dir: Path,
    slug: str,
    *,
    proposition_edges: list[dict],  # type: ignore[type-arg]
) -> None:
    """Render one slug to <slug>-auto.{dot,png}.

    Topology comes from ``<slug>.dot``. Edge SEMANTICS come from
    ``proposition_edges`` - the compiled relational propositions are the
    epistemic source of truth, styled in channel mode with a DERIVED
    ``derived_edge_status``.
    """
    dot_path = dag_dir / f"{slug}.dot"
    out_dot = dag_dir / f"{slug}-auto.dot"
    out_png = dag_dir / f"{slug}-auto.png"
    _assert_dot_edges_backed(slug, dot_path, proposition_edges)
    emit_styled_dot(dot_path, proposition_edges, out_dot)
    render_png(out_dot, out_png)


def render_all(
    paths: DagPaths,
    *,
    proposition_edges: list[dict],  # type: ignore[type-arg]
) -> None:
    """Render every discovered DAG's -auto.dot + -auto.png.

    ``proposition_edges`` are the compiled-proposition edges shared across every
    slug. Each DOT edge must have a matching compiled proposition edge.
    """
    slugs = list(paths.dags) if paths.dags else _discover_slugs(paths.dag_dir)
    for slug in slugs:
        _assert_dot_edges_backed(slug, paths.dag_dir / f"{slug}.dot", proposition_edges)
    for slug in slugs:
        render_one(paths.dag_dir, slug, proposition_edges=proposition_edges)
