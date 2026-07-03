from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from science_tool.dag.paths import DagPaths
from science_tool.dag.render import render_all, render_one
from science_tool.dag.validate import _parse_dot_topology

FIXTURE_ROOT = Path(__file__).parent / "fixtures/mm30"
DAGS_DIR = FIXTURE_ROOT / "doc/figures/dags"
SLUGS = ("h1-prognosis", "h1-progression", "h2-subtype-architecture", "h1-h2-bridge")


@pytest.fixture
def render_workspace(tmp_path: Path) -> Path:
    """Copy mm30 fixtures to a writable tmp location; return the dag_dir."""
    dst = tmp_path / "doc/figures/dags"
    dst.mkdir(parents=True)
    for p in DAGS_DIR.iterdir():
        if p.suffix == ".dot":
            shutil.copy2(p, dst / p.name)
    return dst


def _proposition_edge(
    source: str,
    target: str,
    *,
    edge_id: int | None = None,
    refuted: bool = False,
    original_label: str = "affects",
) -> dict:
    edge = {
        "source": source,
        "target": target,
        "polarity": "positive",
        "belief_magnitude": "supported",
        "claim_layer": "causal_effect",
        "refuted": refuted,
        "has_grounding_evidence": True,
        "identification": "observational",
        "original_label": original_label,
    }
    if edge_id is not None:
        edge["id"] = edge_id
    return edge


def _proposition_edges_for_dot(
    dot_path: Path,
    *,
    refuted_pairs: set[tuple[str, str]] | None = None,
) -> list[dict]:
    _, dot_edges = _parse_dot_topology(dot_path)
    refuted_pairs = refuted_pairs or set()
    return [
        _proposition_edge(
            source,
            target,
            edge_id=index,
            refuted=(source, target) in refuted_pairs,
        )
        for index, (source, target) in enumerate(sorted(dot_edges), start=1)
    ]


def _all_mm30_proposition_edges(dag_dir: Path) -> list[dict]:
    edges: list[dict] = []
    for slug in SLUGS:
        refuted = {("state", "rib"), ("state", "e2f")} if slug == "h1-h2-bridge" else set()
        edges.extend(_proposition_edges_for_dot(dag_dir / f"{slug}.dot", refuted_pairs=refuted))
    return edges


def test_render_discovers_dot_slugs_without_edges_yaml(tmp_path: Path) -> None:
    dag_dir = tmp_path / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (dag_dir / "claim.dot").write_text("digraph claim {\n  a -> b;\n}\n", encoding="utf-8")

    paths = DagPaths(dag_dir=dag_dir, tasks_dir=tmp_path / "tasks", dags=None)
    render_all(
        paths,
        proposition_edges=[
            {
                "source": "a",
                "target": "b",
                "polarity": "positive",
                "belief_magnitude": "speculative",
                "claim_layer": "causal_effect",
                "refuted": False,
                "has_grounding_evidence": False,
                "identification": "observational",
                "original_label": "affects",
            }
        ],
    )

    assert (dag_dir / "claim-auto.dot").exists()


def test_render_refuses_yaml_only_fallback(tmp_path: Path) -> None:
    dag_dir = tmp_path / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (dag_dir / "claim.dot").write_text("digraph claim {\n  a -> b;\n}\n", encoding="utf-8")
    (dag_dir / "claim.edges.yaml").write_text(
        "dag: claim\nedges:\n  - id: 1\n    source: a\n    target: b\n    edge_status: supported\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="no compiled proposition edge"):
        render_one(dag_dir, "claim", proposition_edges=[])


def test_render_fails_before_partial_write_when_dot_edge_unbacked(tmp_path: Path) -> None:
    dag_dir = tmp_path / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (dag_dir / "claim.dot").write_text("digraph claim {\n  a -> b;\n  b -> c;\n}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="b -> c"):
        render_one(
            dag_dir,
            "claim",
            proposition_edges=[
                {
                    "source": "a",
                    "target": "b",
                    "polarity": "positive",
                    "belief_magnitude": "speculative",
                    "claim_layer": "causal_effect",
                    "refuted": False,
                    "has_grounding_evidence": False,
                    "identification": "observational",
                }
            ],
        )
    assert not (dag_dir / "claim-auto.dot").exists()


def test_render_fails_before_partial_write_when_block_commented_dot_edge_unbacked(tmp_path: Path) -> None:
    dag_dir = tmp_path / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (dag_dir / "claim.dot").write_text("digraph claim {\n  a -> b; /* comment */\n}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="a -> b"):
        render_one(dag_dir, "claim", proposition_edges=[])
    assert not (dag_dir / "claim-auto.dot").exists()


def test_render_fails_before_partial_write_when_duplicate_dot_edge_occurrence_unbacked(tmp_path: Path) -> None:
    dag_dir = tmp_path / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (dag_dir / "claim.dot").write_text("digraph claim {\n  a -> b;\n  a -> b;\n}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="a -> b"):
        render_one(
            dag_dir,
            "claim",
            proposition_edges=[
                {
                    "source": "a",
                    "target": "b",
                    "polarity": "positive",
                    "belief_magnitude": "speculative",
                    "claim_layer": "causal_effect",
                    "refuted": False,
                    "has_grounding_evidence": False,
                    "identification": "observational",
                }
            ],
        )
    assert not (dag_dir / "claim-auto.dot").exists()


def test_render_all_fails_before_any_partial_write_when_later_dot_edge_unbacked(tmp_path: Path) -> None:
    dag_dir = tmp_path / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (dag_dir / "a.dot").write_text("digraph a {\n  a_source -> a_target;\n}\n", encoding="utf-8")
    (dag_dir / "b.dot").write_text("digraph b {\n  b_source -> b_target;\n}\n", encoding="utf-8")

    paths = DagPaths(dag_dir=dag_dir, tasks_dir=tmp_path / "tasks", dags=("a", "b"))

    with pytest.raises(ValueError, match="b_source -> b_target"):
        render_all(
            paths,
            proposition_edges=[
                {
                    "source": "a_source",
                    "target": "a_target",
                    "polarity": "positive",
                    "belief_magnitude": "speculative",
                    "claim_layer": "causal_effect",
                    "refuted": False,
                    "has_grounding_evidence": False,
                    "identification": "observational",
                }
            ],
        )

    assert not (dag_dir / "a-auto.dot").exists()
    assert not (dag_dir / "b-auto.dot").exists()


def test_render_one_handles_eliminated_edge(render_workspace: Path) -> None:
    # h1-h2-bridge fixture has 2 eliminated edges (state->rib, state->e2f).
    render_one(
        render_workspace,
        "h1-h2-bridge",
        proposition_edges=_proposition_edges_for_dot(
            render_workspace / "h1-h2-bridge.dot",
            refuted_pairs={("state", "rib"), ("state", "e2f")},
        ),
    )
    dot = (render_workspace / "h1-h2-bridge-auto.dot").read_text()
    # Both eliminated edges must carry the #9e9e9e color and [✗] marker.
    assert dot.count("#9e9e9e") >= 2, "expected at least 2 eliminated-grey edges"
    assert dot.count("[✗]") >= 2, "expected at least 2 [✗] eliminated markers"


def test_render_one_uses_compact_inline_legend(render_workspace: Path) -> None:
    render_one(
        render_workspace,
        "h1-prognosis",
        proposition_edges=_proposition_edges_for_dot(render_workspace / "h1-prognosis.dot"),
    )
    dot = (render_workspace / "h1-prognosis-auto.dot").read_text()

    assert "lg_supp_a" not in dot
    assert "lg_long_b" not in dot
    assert 'cellspacing="0" cellpadding="3"' in dot
    assert '<font color="#2e7d32">&#9473;&#9473;&#9654;</font> supported' in dot
    assert '<font color="#2e7d32">&#9473;&#9473;&#9670;</font> interventional' in dot
    assert '<font color="#2e7d32">&#9473;&#9473;&#8857;</font> longitudinal' in dot


def test_render_one_structural_invariants(render_workspace: Path) -> None:
    proposition_edges = _proposition_edges_for_dot(render_workspace / "h1-progression.dot")
    render_one(render_workspace, "h1-progression", proposition_edges=proposition_edges)
    dot = (render_workspace / "h1-progression-auto.dot").read_text()
    for edge in proposition_edges:
        assert f"[{edge['id']}]" in dot, f"edge id [{edge['id']}] missing from rendered .dot"


def test_render_discovers_slugs_when_whitelist_absent(render_workspace: Path) -> None:
    paths = DagPaths(dag_dir=render_workspace, tasks_dir=render_workspace.parent, dags=None)
    render_all(paths, proposition_edges=_all_mm30_proposition_edges(render_workspace))
    for slug in SLUGS:
        assert (render_workspace / f"{slug}-auto.dot").exists()


def test_render_png_failure_is_non_fatal(render_workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If graphviz `dot` is absent/fails, render_all should log-and-continue."""
    import subprocess

    def _fail(*a: object, **kw: object) -> None:
        raise FileNotFoundError("simulated missing graphviz")

    monkeypatch.setattr(subprocess, "run", _fail)
    paths = DagPaths(dag_dir=render_workspace, tasks_dir=render_workspace.parent, dags=None)
    render_all(paths, proposition_edges=_all_mm30_proposition_edges(render_workspace))  # must NOT raise
    # .dot was still written:
    for slug in SLUGS:
        assert (render_workspace / f"{slug}-auto.dot").exists()
