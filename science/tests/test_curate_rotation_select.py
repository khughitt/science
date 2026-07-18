"""select_rotation ordering, budgeting, and coverage tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from _fixtures.entity_helpers import write_markdown_entity

from science_tool.curate.rotation import select_rotation

TODAY = date(2026, 7, 18)


def _make_project(tmp_path: Path, files: list[tuple[str, dict[str, object]]]) -> Path:
    root = tmp_path / "proj"
    (root / "entities").mkdir(parents=True)
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: core\n", encoding="utf-8")
    for rel, frontmatter in files:
        write_markdown_entity(root, rel, frontmatter)
    return root


def _plan(pid: str, *, status: str = "active", created: str | None = None, last_reviewed: str | None = None) -> dict:
    frontmatter: dict[str, object] = {"id": f"plan:{pid}", "kind": "plan", "title": "P", "status": status}
    if created is not None:
        frontmatter["created"] = created
    if last_reviewed is not None:
        frontmatter["review_state"] = {"last_reviewed": last_reviewed}
    return frontmatter


def test_total_order_never_and_tiebreaks(tmp_path: Path) -> None:
    root = _make_project(
        tmp_path,
        [
            ("entities/plans/0001.md", _plan("0001", created="2026-01-01", last_reviewed="2026-05-01")),
            ("entities/plans/0002.md", _plan("0002", created="2026-01-01", last_reviewed="2026-05-01")),
            ("entities/plans/0003.md", _plan("0003", created="2026-02-01")),           # never reviewed
            ("entities/plans/0004.md", _plan("0004", created="2026-01-01")),           # never reviewed, older created
            ("entities/plans/0005.md", _plan("0005")),                                  # never reviewed, no created
        ],
    )
    result = select_rotation(root, today=TODAY)
    order = [row["id"] for row in result.rows]
    # never-reviewed first: missing created (DATE_MIN) < 2026-01-01 < 2026-02-01;
    # then the 2026-05-01 pair broken by id.
    assert order == ["plan:0005", "plan:0004", "plan:0003", "plan:0001", "plan:0002"]


def test_rank_and_selected_flags(tmp_path: Path) -> None:
    files = [
        (f"entities/plans/{i:04d}.md", _plan(f"{i:04d}", created="2026-01-01", last_reviewed=f"2026-05-{i:02d}"))
        for i in range(1, 6)
    ]
    root = _make_project(tmp_path, files)  # N=5 <= N_FULL, so budget == 5
    result = select_rotation(root, today=TODAY)
    assert result.pool_size == 5
    assert result.budget == 5
    assert result.coverage_rounds == 1
    assert all(row["rank"] == i + 1 for i, row in enumerate(result.rows))
    assert all(row["selected"] for row in result.rows)


def test_age_days_and_iso_and_never(tmp_path: Path) -> None:
    root = _make_project(
        tmp_path,
        [
            ("entities/plans/0001.md", _plan("0001", created="2026-01-01", last_reviewed="2026-07-08")),
            ("entities/plans/0002.md", _plan("0002", created="2026-01-01")),  # never
        ],
    )
    result = select_rotation(root, today=TODAY)
    by_id = {row["id"]: row for row in result.rows}
    assert by_id["plan:0001"]["last_reviewed"] == "2026-07-08"
    assert by_id["plan:0001"]["age_days"] == 10
    assert by_id["plan:0002"]["last_reviewed"] is None
    assert by_id["plan:0002"]["age_days"] is None


def test_empty_corpus_coverage_rounds_zero(tmp_path: Path) -> None:
    root = _make_project(
        tmp_path,
        [("entities/datasets/d1.md", {"id": "dataset:d1", "kind": "dataset", "title": "D", "status": "active"})],
    )
    result = select_rotation(root, today=TODAY)
    assert result.pool_size == 0
    assert result.budget == 0
    assert result.coverage_rounds == 0
    assert result.rows == []


def test_freshness_null_without_graph(tmp_path: Path) -> None:
    root = _make_project(
        tmp_path,
        [("entities/plans/0001.md", _plan("0001", created="2026-01-01"))],
    )
    result = select_rotation(root, today=TODAY)
    assert result.graph_source == "absent"
    assert result.rows[0]["freshness"] is None


def test_correspondence_row_never_gets_freshness(tmp_path: Path, monkeypatch) -> None:
    """Scope guard: even when the graph is current AND carries a freshnessState for a
    plan, a correspondence-scoped row's freshness stays null."""
    root = _make_project(
        tmp_path,
        [("entities/plans/0001.md", _plan("0001", created="2026-01-01"))],
    )
    monkeypatch.setattr(
        "science_tool.curate.rotation.graph_freshness",
        lambda _root: ("current", {"plan:0001": "needs-review"}),
    )
    result = select_rotation(root, today=TODAY)
    assert result.graph_source == "current"
    assert result.rows[0]["id"] == "plan:0001"
    assert result.rows[0]["freshness"] is None  # plan is correspondence-scoped


def test_epistemic_row_gets_freshness_when_current(tmp_path: Path, monkeypatch) -> None:
    """An epistemic row is enriched with its freshnessState when the graph is current."""
    root = _make_project(
        tmp_path,
        [
            (
                "entities/hypotheses/h1.md",
                {"id": "hypothesis:h1", "kind": "hypothesis", "title": "H", "status": "active", "created": "2026-01-01"},
            )
        ],
    )
    monkeypatch.setattr(
        "science_tool.curate.rotation.graph_freshness",
        lambda _root: ("current", {"hypothesis:h1": "needs-review"}),
    )
    result = select_rotation(root, today=TODAY)
    assert result.rows[0]["freshness"] == "needs-review"


def test_coverage_invariant_ordering(tmp_path: Path) -> None:
    """The n=1 coverage counterexample as an ordering property.

    A reviewed yesterday, B today, created(A) < created(B) so A wins the tie-break.
    Stamping A *today* leaves A at rank 1 (a budget-1 sweep re-selects A, starving
    B). Stamping A strictly after the corpus's pre-round maximum moves A behind B,
    so a budget-1 sweep would then reach B.
    """
    yesterday = "2026-07-17"
    today = "2026-07-18"
    root = _make_project(
        tmp_path,
        [
            ("entities/plans/000a.md", _plan("000a", created="2026-01-01", last_reviewed=yesterday)),
            ("entities/plans/000b.md", _plan("000b", created="2026-02-01", last_reviewed=today)),
        ],
    )
    # Round 0: A (yesterday) sorts ahead of B (today).
    assert select_rotation(root, today=TODAY).rows[0]["id"] == "plan:000a"

    # Stamp A "today" (what `entity review` does) -> A and B tie at today, A wins
    # created tie-break, so A is STILL rank 1: B is starved.
    write_markdown_entity(
        root, "entities/plans/000a.md", _plan("000a", created="2026-01-01", last_reviewed=today)
    )
    assert select_rotation(root, today=TODAY).rows[0]["id"] == "plan:000a"

    # Stamp A strictly after the pre-round maximum (tomorrow) -> A now sorts after
    # B, so B becomes rank 1 and is covered.
    tomorrow = "2026-07-19"
    write_markdown_entity(
        root, "entities/plans/000a.md", _plan("000a", created="2026-01-01", last_reviewed=tomorrow)
    )
    assert select_rotation(root, today=TODAY).rows[0]["id"] == "plan:000b"
