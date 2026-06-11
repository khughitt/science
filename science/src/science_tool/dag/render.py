"""DAG rendering with precedence matrix and eliminated-edge support.

Lifted from mm30's ``doc/figures/dags/_render_styled.py`` (t186).
Single-source-of-truth rendering:
  - Topology (nodes, subgraphs, clusters) from ``<slug>.dot``
  - Semantics (status, identification, posterior, etc.) from ``<slug>.edges.yaml``

Produces ``<slug>-auto.dot`` and ``<slug>-auto.png`` with per-edge styling.

Two rendering modes are selected automatically per edge record:

**Channel-driven mode** (design §6) — used when the orthogonal channel fields
``polarity``, ``belief_magnitude``, ``claim_layer``, ``refuted``, and
``has_grounding_evidence`` are present.  Styling derives from the independent
channels:

  - ``polarity``              → hue  (positive/negative/unsigned/not_applicable
                                       each get a distinct colour)
  - ``identification``        → line-style + arrowhead
  - ``belief_magnitude``      → penwidth base intensity
  - ``contested``             → dashed-style overlay + ``[?]`` label marker
  - ``derived_edge_status``   → computed via ``derived_edge_status(...)`` and
                                  surfaced in the returned attrs dict for legacy
                                  consumers; NOT used as a styling source.

**Legacy mode** — used when channel fields are absent; reads the authored
``edge_status`` field and maps it to the historic STATUS_STYLES table exactly
as before (full backward compatibility for existing edges.yaml records).

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

Overrides (both modes):
  - Posterior HDI crosses zero → force ``style=dashed`` (uncertainty cue).
  - Posterior |β| present → scale penwidth = 1.6 + |β|·4, capped at 4.5.
  - Identification encoded by arrowhead:
      observational/structural/none → normal, interventional → diamond,
      longitudinal → odot.
  - Posterior auto-label suffix: "β=±0.XX" and "HR=X.X" when available.
  - ``edge_status: eliminated`` / ``refuted: true`` wins over posterior-based
    sizing (the mechanism has been retracted; visual should not imply live
    support).

YAML is read directly via ``yaml.safe_load``; schema validation is a separate
concern (the render path must tolerate legacy ``doi: null`` entries and other
not-yet-migrated data). YAML records whose ``source``/``target`` pair is absent
from the DOT are treated as claim-only evidence records and are not rendered.
"""

from __future__ import annotations

import logging
import re
import subprocess
from collections import defaultdict, deque
from pathlib import Path

import yaml

from science_tool.dag.paths import DagPaths
from science_tool.graph.derived_status import derived_edge_status

log = logging.getLogger(__name__)

STATUS_STYLES = {
    "supported": {"color": "#2e7d32", "penwidth": 2.5, "style": "solid"},
    "tentative": {"color": "#1565c0", "penwidth": 1.6, "style": "solid"},
    "structural": {"color": "#757575", "penwidth": 1.0, "style": "solid"},
    "unknown": {"color": "#c62828", "penwidth": 1.2, "style": "dashed"},
    "eliminated": {"color": "#9e9e9e", "penwidth": 1.0, "style": "dotted"},
}

# ---------------------------------------------------------------------------
# Channel-driven styling constants (design §6)
# ---------------------------------------------------------------------------

# polarity → hue.  Deliberately distinct from STATUS_STYLES so that a reader
# can see that colour signals direction-of-effect, not epistemic status.
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
        color = STATUS_STYLES["eliminated"]["color"]
        penwidth = STATUS_STYLES["eliminated"]["penwidth"]
        style = STATUS_STYLES["eliminated"]["style"]
    elif des.status == "unknown":
        style = "dashed"

    return {"color": color, "penwidth": penwidth, "style": style}, des.status


def style_for_edge(edge: dict) -> dict:  # type: ignore[type-arg]
    """Compute graphviz style attributes from an edge's YAML record.

    Selects channel-driven mode when orthogonal channel fields are present,
    otherwise falls back to the legacy authored ``edge_status`` path.

    The returned dict always contains a ``derived_edge_status`` key (channel
    mode: computed via ``derived_edge_status(...)``; legacy mode: the authored
    ``edge_status`` value or ``"tentative"`` when absent) for use by legacy
    ``science dag`` consumers.
    """
    ident = edge.get("identification") or "observational"

    # --- Select rendering mode ---
    use_channels = bool(_CHANNEL_FIELDS & set(edge.keys()))

    if use_channels:
        base, derived_status = _style_base_from_channels(edge)
        status = derived_status  # used for eliminated-guard below
    else:
        # Legacy mode: authored edge_status drives colour / penwidth / style.
        # Task 5f: edges.yaml is RETIRED as the epistemic source-of-truth — the
        # primary path sources channel-mode edges from compiled propositions
        # (proposition_edges.edges_from_propositions). This branch survives ONLY
        # behind the deprecated edges.yaml legacy-import adapter (render falls
        # back to it, loudly via DeprecationWarning, when no propositions are
        # compiled), so authored edge_status is never a status SoT for the
        # proposition-sourced view. It is retained — not deleted — because many
        # not-yet-migrated edges.yaml fixtures still carry authored edge_status
        # with no channel fields; deleting it would break their backward-compatible
        # rendering. It can be removed once every input carries channel fields.
        status = edge.get("edge_status") or "tentative"
        base = STATUS_STYLES.get(status, STATUS_STYLES["tentative"]).copy()
        derived_status = status

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
                    "style=HDI-crosses-zero-dashed, arrowhead=identification"
                    "</i></font>"
                )
                # Inject the banner right before the closing `>`.
                new_label = re.sub(r">\s*$", auto_banner + ">", original)
                out.append(f"{indent}{new_label};")
                banner_inserted = True
                continue

        em = EDGE_RE.match(line)
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
        "  // --- Auto-footer legend (two-axis: edge_status + identification) ---",
        "  subgraph cluster_auto_footer_legend {",
        "    rank=sink;",
        '    label="";',
        '    color="#bdbdbd"; style="rounded"; margin=4;',
        "    node [shape=plaintext, fontsize=9];",
        '    footer_legend [label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="3" color="#bdbdbd">',
        (
            '      <tr><td bgcolor="#f5f5f5"><b>Auto legend</b></td>'
            '<td bgcolor="#f5f5f5"><b>edge_status</b>: color / width / style</td>'
            '<td bgcolor="#f5f5f5"><b>identification</b>: arrowhead</td></tr>'
        ),
        (
            '      <tr><td align="left">status</td>'
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
    """Find every <slug>.edges.yaml file (sorted)."""
    return sorted(p.stem.replace(".edges", "") for p in dag_dir.glob("*.edges.yaml"))


def render_one(
    dag_dir: Path,
    slug: str,
    *,
    proposition_edges: list[dict] | None = None,  # type: ignore[type-arg]
) -> None:
    """Render one slug to <slug>-auto.{dot,png}.

    Topology comes from ``<slug>.dot``. Edge SEMANTICS come from
    ``proposition_edges`` when supplied — the compiled relational propositions
    are the epistemic source-of-truth (Task 5f), styled in channel mode with a
    DERIVED ``edge_status``.

    When ``proposition_edges`` is ``None``, the renderer falls back to the
    RETIRED ``<slug>.edges.yaml`` legacy-import adapter (a ``DeprecationWarning``
    is emitted on read). The authored ``edge_status`` in that file is not the
    epistemic status SoT; it survives only as the legacy-mode styling input.
    """
    dot_path = dag_dir / f"{slug}.dot"
    if proposition_edges is None:
        edges = _load_legacy_edges(dag_dir / f"{slug}.edges.yaml")
    else:
        edges = proposition_edges
    out_dot = dag_dir / f"{slug}-auto.dot"
    out_png = dag_dir / f"{slug}-auto.png"
    emit_styled_dot(dot_path, edges, out_dot)
    render_png(out_dot, out_png)


def _load_legacy_edges(yaml_path: Path) -> list[dict]:  # type: ignore[type-arg]
    """Read raw edge dicts from a RETIRED ``<slug>.edges.yaml`` (Task 5f).

    Emits the edges.yaml retirement ``DeprecationWarning`` so that falling back
    to the authored file is loud, never silent. Returns the raw edge dicts (the
    render path tolerates not-yet-migrated legacy fields).
    """
    import warnings

    from science_tool.dag.schema import _EDGES_YAML_DEPRECATION

    warnings.warn(_EDGES_YAML_DEPRECATION, DeprecationWarning, stacklevel=2)
    data = yaml.safe_load(yaml_path.read_text())
    return data["edges"]


def render_all(
    paths: DagPaths,
    *,
    proposition_edges: list[dict] | None = None,  # type: ignore[type-arg]
) -> None:
    """Render every discovered DAG's -auto.dot + -auto.png.

    ``proposition_edges`` (when supplied) are the compiled-proposition edges
    shared across every slug; topology filtering per slug happens in
    ``emit_styled_dot`` (edges whose source/target pair is absent from a DAG's
    DOT are simply not drawn there).
    """
    slugs = list(paths.dags) if paths.dags else _discover_slugs(paths.dag_dir)
    for slug in slugs:
        render_one(paths.dag_dir, slug, proposition_edges=proposition_edges)
