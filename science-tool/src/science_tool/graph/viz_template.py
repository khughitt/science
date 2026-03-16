# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "altair>=5",
#     "polars",
#     "rdflib>=7",
# ]
# ///

import marimo

__generated_with = "0.13.0"
app = marimo.App(width="medium")


# ── Config & data loading ────────────────────────────────────────────
@app.cell
def config():
    import marimo as mo

    graph_path_input = mo.ui.text(
        value="knowledge/graph.trig",
        label="Graph path",
        full_width=True,
    )
    mo.md(f"## Knowledge Graph Explorer\n\n{graph_path_input}")
    return graph_path_input, mo


@app.cell
def load_graph(graph_path_input, mo):
    import math
    import random
    from pathlib import Path

    import altair as alt
    import polars as pl

    graph_file = Path(graph_path_input.value)

    # Known namespace prefixes for shortening URIs
    _PREFIX_MAP: dict[str, str] = {
        "http://example.org/project/": "",
        "http://example.org/science/vocab/causal/": "scic:",
        "http://example.org/science/vocab/": "sci:",
        "https://schema.org/": "schema:",
        "https://w3id.org/biolink/vocab/": "biolink:",
        "http://purl.org/spar/cito/": "cito:",
        "http://purl.org/dc/terms/": "dcterms:",
        "http://www.w3.org/2004/02/skos/core#": "skos:",
        "http://www.w3.org/ns/prov#": "prov:",
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
        "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
        "http://www.w3.org/2001/XMLSchema#": "xsd:",
    }

    _LAYER_URIS = {
        "http://example.org/project/graph/knowledge": "knowledge",
        "http://example.org/project/graph/causal": "causal",
        "http://example.org/project/graph/provenance": "provenance",
        "http://example.org/project/graph/datasets": "datasets",
    }

    def shorten_uri(uri: object) -> str:
        """Strip known namespace prefixes to produce readable CURIEs."""
        s = str(uri)
        # Sort by longest prefix first so more specific matches win
        for prefix, short in sorted(_PREFIX_MAP.items(), key=lambda kv: -len(kv[0])):
            if s.startswith(prefix):
                return short + s[len(prefix) :]
        return s

    def layer_name(graph_uri: str | None) -> str:
        if graph_uri is None:
            return "default"
        s = str(graph_uri)
        if s.startswith("urn:x-rdflib:"):
            return "default"
        return _LAYER_URIS.get(s, s)

    # Load the graph
    rows: list[dict[str, str]] = []

    if graph_file.exists():
        from rdflib import Dataset

        ds = Dataset()
        ds.parse(str(graph_file), format="trig")

        for ctx in ds.graphs():
            ctx_id = str(ctx.identifier) if ctx.identifier else None
            ln = layer_name(ctx_id)
            for s, p, o in ctx:
                rows.append(
                    {
                        "subject": shorten_uri(s),
                        "predicate": shorten_uri(p),
                        "object": shorten_uri(o),
                        "layer": ln,
                    }
                )

    df = (
        pl.DataFrame(rows)
        if rows
        else pl.DataFrame(
            schema={"subject": pl.String, "predicate": pl.String, "object": pl.String, "layer": pl.String}
        )
    )

    n_triples = len(df)
    entities = set()
    if n_triples > 0:
        entities = set(df["subject"].to_list()) | set(df["object"].to_list())
    n_entities = len(entities)
    n_predicates = df["predicate"].n_unique() if n_triples > 0 else 0

    mo.md(
        f"Loaded **{n_triples}** triples, "
        f"**{n_entities}** unique entities, "
        f"**{n_predicates}** unique predicates "
        f"from `{graph_file}`"
    )
    return (
        alt,
        df,
        math,
        n_entities,
        n_predicates,
        n_triples,
        pl,
        random,
    )


# ── Stats overview ───────────────────────────────────────────────────
@app.cell
def stats_overview(alt, df, mo, n_entities, n_predicates, n_triples, pl):
    if n_triples == 0:
        _out = mo.vstack([mo.md("## Stats Overview"), mo.md("_No triples loaded._")])
    else:
        _layer_counts = df.group_by("layer").len().rename({"len": "triples"})

        _chart_layers = (
            alt.Chart(_layer_counts.to_pandas())
            .mark_bar()
            .encode(
                x=alt.X("layer:N", title="Layer"),
                y=alt.Y("triples:Q", title="Triples"),
                color=alt.Color("layer:N", legend=None),
                tooltip=["layer", "triples"],
            )
            .properties(width=400, height=250, title="Triples per Layer")
        )

        _stats_callout = mo.callout(
            mo.md(
                f"**Total triples:** {n_triples}  \n"
                f"**Unique entities:** {n_entities}  \n"
                f"**Unique predicates:** {n_predicates}"
            ),
            kind="info",
        )

        _out = mo.vstack(
            [
                mo.md("## Stats Overview"),
                mo.hstack([mo.ui.altair_chart(_chart_layers), _stats_callout], justify="start", gap=2),
            ]
        )
    _out


# ── Entity type breakdown ────────────────────────────────────────────
@app.cell
def entity_types(alt, df, mo, n_triples, pl):
    if n_triples == 0:
        _out = mo.vstack([mo.md("## Entity Type Breakdown"), mo.md("_No data._")])
    else:
        _type_df = (
            df.filter(pl.col("predicate") == "rdf:type")
            .group_by("object")
            .len()
            .rename({"len": "count"})
            .sort("count", descending=True)
        )

        if len(_type_df) == 0:
            _out = mo.vstack([mo.md("## Entity Type Breakdown"), mo.md("_No rdf:type triples found._")])
        else:
            _chart_types = (
                alt.Chart(_type_df.to_pandas())
                .mark_bar()
                .encode(
                    y=alt.Y("object:N", title="Type", sort="-x"),
                    x=alt.X("count:Q", title="Count"),
                    color=alt.Color("object:N", legend=None),
                    tooltip=["object", "count"],
                )
                .properties(width=500, height=max(150, len(_type_df) * 25), title="Entity Types")
            )
            _out = mo.vstack([mo.md("## Entity Type Breakdown"), mo.ui.altair_chart(_chart_types)])
    _out


# ── Predicate frequency ─────────────────────────────────────────────
@app.cell
def predicate_freq(alt, df, mo, n_triples, pl):
    if n_triples == 0:
        _out = mo.vstack([mo.md("## Predicate Frequency"), mo.md("_No data._")])
    else:
        _pred_df = df.group_by(["predicate", "layer"]).len().rename({"len": "count"}).sort("count", descending=True)

        _chart_preds = (
            alt.Chart(_pred_df.to_pandas())
            .mark_bar()
            .encode(
                y=alt.Y("predicate:N", title="Predicate", sort="-x"),
                x=alt.X("count:Q", title="Count"),
                color=alt.Color("layer:N", title="Layer"),
                tooltip=["predicate", "layer", "count"],
            )
            .properties(
                width=500,
                height=max(150, _pred_df["predicate"].n_unique() * 22),
                title="Predicate Frequency by Layer",
            )
        )
        _out = mo.vstack([mo.md("## Predicate Frequency"), mo.ui.altair_chart(_chart_preds)])
    _out


# ── Network graph ────────────────────────────────────────────────────
@app.cell
def network_controls(df, mo, n_triples):
    layers = ["all"] + sorted(df["layer"].unique().to_list()) if n_triples > 0 else ["all"]
    layer_filter = mo.ui.dropdown(options=layers, value="all", label="Layer filter")
    max_edges_slider = mo.ui.slider(start=10, stop=500, step=10, value=200, label="Max edges")
    mo.md(f"## Network Graph\n\n{mo.hstack([layer_filter, max_edges_slider])}")
    return layer_filter, max_edges_slider


@app.cell
def network_graph(alt, df, layer_filter, math, max_edges_slider, mo, n_triples, pl, random):
    if n_triples == 0:
        _out = mo.md("_No data to visualize._")
    else:
        # Filter by layer
        _net_df = df
        if layer_filter.value != "all":
            _net_df = df.filter(pl.col("layer") == layer_filter.value)

        # Limit edges
        _max_e = max_edges_slider.value
        if len(_net_df) > _max_e:
            _net_df = _net_df.head(_max_e)

        if len(_net_df) == 0:
            _out = mo.md("_No edges for selected layer._")
        else:
            # Build node set and degree counts
            _subjects = _net_df["subject"].to_list()
            _objects = _net_df["object"].to_list()
            _all_nodes = list(set(_subjects + _objects))
            _node_idx = {n: i for i, n in enumerate(_all_nodes)}

            _degree: dict[str, int] = {}
            for _n in _subjects + _objects:
                _degree[_n] = _degree.get(_n, 0) + 1

            # Get entity types for coloring
            _type_map: dict[str, str] = {}
            _type_triples = df.filter(pl.col("predicate") == "rdf:type")
            if len(_type_triples) > 0:
                for _row in _type_triples.iter_rows(named=True):
                    _type_map[_row["subject"]] = _row["object"]

            # Fruchterman-Reingold force layout
            _n_nodes = len(_all_nodes)
            _area = 500.0 * 500.0
            _k = math.sqrt(_area / max(_n_nodes, 1))

            random.seed(42)
            _pos_x = [random.uniform(-250, 250) for _ in range(_n_nodes)]
            _pos_y = [random.uniform(-250, 250) for _ in range(_n_nodes)]

            _edges = [(_node_idx[s], _node_idx[o]) for s, o in zip(_subjects, _objects)]

            _temp = 50.0
            for _ in range(50):
                # Repulsion
                _disp_x = [0.0] * _n_nodes
                _disp_y = [0.0] * _n_nodes
                for _i in range(_n_nodes):
                    for _j in range(_i + 1, _n_nodes):
                        _dx = _pos_x[_i] - _pos_x[_j]
                        _dy = _pos_y[_i] - _pos_y[_j]
                        _dist = max(math.sqrt(_dx * _dx + _dy * _dy), 0.01)
                        _force = (_k * _k) / _dist
                        _fx = (_dx / _dist) * _force
                        _fy = (_dy / _dist) * _force
                        _disp_x[_i] += _fx
                        _disp_y[_i] += _fy
                        _disp_x[_j] -= _fx
                        _disp_y[_j] -= _fy

                # Attraction
                for _u, _v in _edges:
                    _dx = _pos_x[_u] - _pos_x[_v]
                    _dy = _pos_y[_u] - _pos_y[_v]
                    _dist = max(math.sqrt(_dx * _dx + _dy * _dy), 0.01)
                    _force = (_dist * _dist) / _k
                    _fx = (_dx / _dist) * _force
                    _fy = (_dy / _dist) * _force
                    _disp_x[_u] -= _fx
                    _disp_y[_u] -= _fy
                    _disp_x[_v] += _fx
                    _disp_y[_v] += _fy

                # Apply with temperature
                for _i in range(_n_nodes):
                    _d = max(math.sqrt(_disp_x[_i] ** 2 + _disp_y[_i] ** 2), 0.01)
                    _scale = min(_d, _temp) / _d
                    _pos_x[_i] += _disp_x[_i] * _scale
                    _pos_y[_i] += _disp_y[_i] * _scale

                _temp *= 0.9

            # Build node dataframe
            _node_records = []
            for _i, _name in enumerate(_all_nodes):
                _node_records.append(
                    {
                        "entity": _name,
                        "x": _pos_x[_i],
                        "y": _pos_y[_i],
                        "degree": _degree.get(_name, 1),
                        "type": _type_map.get(_name, "unknown"),
                    }
                )
            _nodes_pl = pl.DataFrame(_node_records)

            # Build edge dataframe
            _edge_records = []
            _preds = _net_df["predicate"].to_list()
            for _idx, (_u, _v) in enumerate(_edges):
                _edge_records.append(
                    {
                        "x": _pos_x[_u],
                        "y": _pos_y[_u],
                        "x2": _pos_x[_v],
                        "y2": _pos_y[_v],
                        "predicate": _preds[_idx],
                    }
                )
            _edges_pl = pl.DataFrame(_edge_records)

            # Render with altair
            _edge_chart = (
                alt.Chart(_edges_pl.to_pandas())
                .mark_rule(opacity=0.3, color="gray")
                .encode(
                    x=alt.X("x:Q", axis=None),
                    y=alt.Y("y:Q", axis=None),
                    x2="x2:Q",
                    y2="y2:Q",
                    tooltip=["predicate"],
                )
            )

            _node_chart = (
                alt.Chart(_nodes_pl.to_pandas())
                .mark_circle()
                .encode(
                    x=alt.X("x:Q", axis=None),
                    y=alt.Y("y:Q", axis=None),
                    size=alt.Size("degree:Q", scale=alt.Scale(range=[40, 400]), legend=None),
                    color=alt.Color("type:N", title="Entity Type"),
                    tooltip=["entity", "type", "degree"],
                )
            )

            _combined = (
                (_edge_chart + _node_chart)
                .properties(width=600, height=500, title="Network Graph")
                .configure_view(strokeWidth=0)
            )
            _out = mo.ui.altair_chart(_combined)
    _out


# ── Neighborhood explorer ────────────────────────────────────────────
@app.cell
def neighborhood_controls(mo):
    entity_input = mo.ui.text(value="", label="Entity (CURIE or name)", full_width=True)
    hops_slider = mo.ui.slider(start=1, stop=3, step=1, value=1, label="Hops")
    mo.md(f"## Neighborhood Explorer\n\n{mo.hstack([entity_input, hops_slider])}")
    return entity_input, hops_slider


@app.cell
def neighborhood_graph(alt, df, entity_input, hops_slider, math, mo, n_triples, pl, random):
    if n_triples == 0 or not entity_input.value.strip():
        _out = mo.md("_Enter an entity name above to explore its neighborhood._")
    else:
        _center = entity_input.value.strip()
        _hops = hops_slider.value

        # BFS to find ego-graph
        _visited: set[str] = {_center}
        _frontier: set[str] = {_center}
        _ego_edges: list[dict[str, str]] = []

        for _ in range(_hops):
            _next_frontier: set[str] = set()
            for _row in df.iter_rows(named=True):
                _s, _, _o = _row["subject"], _row["predicate"], _row["object"]
                if _s in _frontier:
                    _ego_edges.append(_row)
                    if _o not in _visited:
                        _visited.add(_o)
                        _next_frontier.add(_o)
                elif _o in _frontier:
                    _ego_edges.append(_row)
                    if _s not in _visited:
                        _visited.add(_s)
                        _next_frontier.add(_s)
            _frontier = _next_frontier
            if not _frontier:
                break

        if not _ego_edges:
            _out = mo.md(f"_No triples found for entity `{_center}`._")
        else:
            _ego_df = pl.DataFrame(_ego_edges).unique()
            _ego_subjects = _ego_df["subject"].to_list()
            _ego_objects = _ego_df["object"].to_list()
            _ego_nodes = list(set(_ego_subjects + _ego_objects))
            _ego_node_idx = {n: i for i, n in enumerate(_ego_nodes)}

            _ego_degree: dict[str, int] = {}
            for _n in _ego_subjects + _ego_objects:
                _ego_degree[_n] = _ego_degree.get(_n, 0) + 1

            # Force layout
            _n_n = len(_ego_nodes)
            _area = 400.0 * 400.0
            _k = math.sqrt(_area / max(_n_n, 1))

            random.seed(7)
            _ex = [random.uniform(-200, 200) for _ in range(_n_n)]
            _ey = [random.uniform(-200, 200) for _ in range(_n_n)]
            _e_edges = [(_ego_node_idx[s], _ego_node_idx[o]) for s, o in zip(_ego_subjects, _ego_objects)]

            _temp = 40.0
            for _ in range(50):
                _dx_arr = [0.0] * _n_n
                _dy_arr = [0.0] * _n_n
                for _i in range(_n_n):
                    for _j in range(_i + 1, _n_n):
                        _ddx = _ex[_i] - _ex[_j]
                        _ddy = _ey[_i] - _ey[_j]
                        _dist = max(math.sqrt(_ddx * _ddx + _ddy * _ddy), 0.01)
                        _force = (_k * _k) / _dist
                        _fx = (_ddx / _dist) * _force
                        _fy = (_ddy / _dist) * _force
                        _dx_arr[_i] += _fx
                        _dy_arr[_i] += _fy
                        _dx_arr[_j] -= _fx
                        _dy_arr[_j] -= _fy
                for _u, _v in _e_edges:
                    _ddx = _ex[_u] - _ex[_v]
                    _ddy = _ey[_u] - _ey[_v]
                    _dist = max(math.sqrt(_ddx * _ddx + _ddy * _ddy), 0.01)
                    _force = (_dist * _dist) / _k
                    _fx = (_ddx / _dist) * _force
                    _fy = (_ddy / _dist) * _force
                    _dx_arr[_u] -= _fx
                    _dy_arr[_u] -= _fy
                    _dx_arr[_v] += _fx
                    _dy_arr[_v] += _fy
                for _i in range(_n_n):
                    _d = max(math.sqrt(_dx_arr[_i] ** 2 + _dy_arr[_i] ** 2), 0.01)
                    _scale = min(_d, _temp) / _d
                    _ex[_i] += _dx_arr[_i] * _scale
                    _ey[_i] += _dy_arr[_i] * _scale
                _temp *= 0.9

            _ego_node_records = [
                {
                    "entity": _name,
                    "x": _ex[_i],
                    "y": _ey[_i],
                    "degree": _ego_degree.get(_name, 1),
                    "is_center": "center" if _name == _center else "other",
                }
                for _i, _name in enumerate(_ego_nodes)
            ]
            _ego_nodes_pl = pl.DataFrame(_ego_node_records)

            _ego_preds = _ego_df["predicate"].to_list()
            _ego_edge_records = [
                {
                    "x": _ex[_ego_node_idx[_s]],
                    "y": _ey[_ego_node_idx[_s]],
                    "x2": _ex[_ego_node_idx[_o]],
                    "y2": _ey[_ego_node_idx[_o]],
                    "predicate": _p,
                }
                for _s, _o, _p in zip(_ego_subjects, _ego_objects, _ego_preds)
            ]
            _ego_edges_pl = pl.DataFrame(_ego_edge_records)

            _edge_c = (
                alt.Chart(_ego_edges_pl.to_pandas())
                .mark_rule(opacity=0.4, color="gray")
                .encode(
                    x=alt.X("x:Q", axis=None),
                    y=alt.Y("y:Q", axis=None),
                    x2="x2:Q",
                    y2="y2:Q",
                    tooltip=["predicate"],
                )
            )
            _node_c = (
                alt.Chart(_ego_nodes_pl.to_pandas())
                .mark_circle()
                .encode(
                    x=alt.X("x:Q", axis=None),
                    y=alt.Y("y:Q", axis=None),
                    size=alt.Size("degree:Q", scale=alt.Scale(range=[50, 400]), legend=None),
                    color=alt.Color(
                        "is_center:N",
                        scale=alt.Scale(domain=["center", "other"], range=["#e45756", "#4c78a8"]),
                        title="Role",
                    ),
                    tooltip=["entity", "degree", "is_center"],
                )
            )
            _combined_ego = (
                (_edge_c + _node_c)
                .properties(width=500, height=400, title=f"Neighborhood of {_center} ({_hops} hops)")
                .configure_view(strokeWidth=0)
            )
            _out = mo.ui.altair_chart(_combined_ego)
    _out


# ── Quality dashboard ────────────────────────────────────────────────
@app.cell
def quality_dashboard(df, mo, n_triples, pl):
    if n_triples == 0:
        _out = mo.vstack([mo.md("## Quality Dashboard"), mo.md("_No data._")])
    else:
        # 1. Entities missing definition or provenance
        _typed_entities = set(df.filter(pl.col("predicate") == "rdf:type")["subject"].to_list())
        _has_definition = set(df.filter(pl.col("predicate") == "skos:definition")["subject"].to_list())
        _has_provenance = set(df.filter(pl.col("predicate") == "prov:wasDerivedFrom")["subject"].to_list())
        _missing_def = sorted(_typed_entities - _has_definition)
        _missing_prov = sorted(_typed_entities - _has_provenance)

        _missing_items = []
        for _e in _missing_def[:20]:
            _missing_items.append(f"- `{_e}` — missing `skos:definition`")
        for _e in _missing_prov[:20]:
            if _e not in _missing_def:
                _missing_items.append(f"- `{_e}` — missing `prov:wasDerivedFrom`")

        _missing_panel = mo.md(
            "### Missing Metadata\n\n"
            + ("\n".join(_missing_items) if _missing_items else "_All entities have definitions and provenance._")
        )

        # 2. Low-confidence claims
        _confidence_triples = df.filter(pl.col("predicate") == "sci:confidence")
        _low_conf_items = []
        if len(_confidence_triples) > 0:
            for _row in _confidence_triples.iter_rows(named=True):
                try:
                    _val = float(_row["object"])
                    if _val < 0.5:
                        _low_conf_items.append(f"- `{_row['subject']}` — confidence {_val:.2f}")
                except (ValueError, TypeError):
                    pass

        _confidence_panel = mo.md(
            "### Low-Confidence Claims (< 0.5)\n\n"
            + ("\n".join(_low_conf_items[:20]) if _low_conf_items else "_No low-confidence claims found._")
        )

        # 3. Open questions by maturity
        _maturity_triples = df.filter(pl.col("predicate") == "sci:maturity")
        _question_triples = df.filter((pl.col("predicate") == "rdf:type") & (pl.col("object") == "sci:Question"))
        _question_entities = set(_question_triples["subject"].to_list())

        _maturity_groups: dict[str, list[str]] = {}
        if len(_maturity_triples) > 0:
            for _row in _maturity_triples.iter_rows(named=True):
                if _row["subject"] in _question_entities:
                    _mat = _row["object"]
                    _maturity_groups.setdefault(_mat, []).append(_row["subject"])

        _mat_lines = []
        for _mat, _ents in sorted(_maturity_groups.items()):
            _mat_lines.append(f"**{_mat}** ({len(_ents)})")
            for _e in _ents[:10]:
                _mat_lines.append(f"- `{_e}`")

        _maturity_panel = mo.md(
            "### Open Questions by Maturity\n\n"
            + ("\n".join(_mat_lines) if _mat_lines else "_No open questions found._")
        )

        _out = mo.vstack([mo.md("## Quality Dashboard"), _missing_panel, _confidence_panel, _maturity_panel])
    _out


if __name__ == "__main__":
    app.run()
