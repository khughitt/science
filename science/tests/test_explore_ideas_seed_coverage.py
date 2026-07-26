"""fb-2026-07-25-004: the Phase-1 brief's scope boundary must be a stated fact.

The filing reports that missing `specs/` scope files degrade the brief silently.
Grounding found the sharper case: `science entity migrate-specs` moves those
documents to `entities/specs/NNNN-slug.md`, so in a migrated project the
boundary EXISTS while the legacy path the command reads does not. Absent and
unreachable are different failures and the diagnostic must tell them apart.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from _fixtures.entity_helpers import seed_project
from science_tool.cli import main
from science_tool.explore_ideas_seed import compute_seed_coverage


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _canonical_spec(root: Path, number: str, slug: str, entity_id: str | None = None) -> Path:
    path = root / "entities" / "specs" / f"{number}-{slug}.md"
    _write(
        path,
        "---\n"
        f"id: spec:{entity_id or f'{number}-{slug}'}\n"
        "kind: spec\n"
        f"title: {slug.replace('-', ' ').title()}\n"
        "---\n\nBody.\n",
    )
    return path


def test_migrated_scope_boundary_is_found_in_the_canonical_layout(tmp_path: Path) -> None:
    # The natural-systems shape: `entities/specs/0037-scope-boundaries.md`
    # exists and `specs/scope-boundaries.md` does not.
    seed_project(tmp_path)
    _canonical_spec(tmp_path, "0037", "scope-boundaries")

    seed = compute_seed_coverage(tmp_path)

    assert seed.scope_source == "declared"
    scope = next(s for s in seed.sources if s.name == "scope-boundaries")
    assert scope.path == "entities/specs/0037-scope-boundaries.md"
    assert scope.layout == "canonical"


def test_legacy_scope_boundary_is_found_and_marked_unmigrated(tmp_path: Path) -> None:
    # `create-project` still scaffolds the legacy path, so this is a live case.
    # It resolves, but the layout is reported so the staleness is visible.
    seed_project(tmp_path)
    _write(tmp_path / "specs" / "scope-boundaries.md", "# Scope\n\nIn scope: X.\n")

    seed = compute_seed_coverage(tmp_path)

    assert seed.scope_source == "declared"
    scope = next(s for s in seed.sources if s.name == "scope-boundaries")
    assert scope.path == "specs/scope-boundaries.md"
    assert scope.layout == "legacy"


def test_canonical_layout_wins_over_a_stale_legacy_copy(tmp_path: Path) -> None:
    # A half-finished migration leaves both. The canonical one is authoritative.
    seed_project(tmp_path)
    _canonical_spec(tmp_path, "0037", "scope-boundaries")
    _write(tmp_path / "specs" / "scope-boundaries.md", "# Stale\n")

    scope = next(s for s in compute_seed_coverage(tmp_path).sources if s.name == "scope-boundaries")

    assert scope.layout == "canonical"


def test_absent_scope_boundary_is_reported_as_absent(tmp_path: Path) -> None:
    # meta / post-acute-infection / evolution: no boundary document anywhere.
    seed_project(tmp_path)

    seed = compute_seed_coverage(tmp_path)

    assert seed.scope_source == "absent"
    scope = next(s for s in seed.sources if s.name == "scope-boundaries")
    assert scope.path is None
    assert scope.layout is None


def test_spec_renamed_but_aliased_still_resolves(tmp_path: Path) -> None:
    # Migration preserves the pre-migration id as an alias. A project that also
    # retitled the file would read as absent on filename matching alone, while
    # the document sits in plain view.
    seed_project(tmp_path)
    _write(
        tmp_path / "entities" / "specs" / "0012-where-this-work-stops.md",
        "---\n"
        "id: spec:0012-where-this-work-stops\n"
        "kind: spec\n"
        "aliases:\n"
        "  - spec:scope-boundaries\n"
        "title: Where this work stops\n"
        "---\n\nBody.\n",
    )

    scope = next(s for s in compute_seed_coverage(tmp_path).sources if s.name == "scope-boundaries")

    assert scope.source == "declared"
    assert scope.path == "entities/specs/0012-where-this-work-stops.md"


def test_research_question_is_resolved_independently(tmp_path: Path) -> None:
    # The two brief inputs are separate facts: one can be declared while the
    # other is absent, and collapsing them would hide that.
    seed_project(tmp_path)
    _canonical_spec(tmp_path, "0003", "research-question")

    sources = {s.name: s for s in compute_seed_coverage(tmp_path).sources}

    assert sources["research-question"].source == "declared"
    assert sources["scope-boundaries"].source == "absent"


def test_seed_coverage_carries_the_topic_diagnostic_too(tmp_path: Path) -> None:
    # seed_coverage is the whole Phase-4 header block, not just the scope half.
    seed_project(tmp_path)

    payload = compute_seed_coverage(tmp_path).to_dict()

    for key in ("n_topics", "n_substantive", "stub_ratio", "stub_dominated", "scope_source", "brief_sources"):
        assert key in payload


def test_cli_json_reports_scope_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_project(tmp_path)
    _canonical_spec(tmp_path, "0037", "scope-boundaries")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(main, ["explore-ideas", "seed-coverage", "--format", "json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["scope_source"] == "declared"


def test_cli_text_names_the_absent_boundary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(main, ["explore-ideas", "seed-coverage"])

    assert result.exit_code == 0, result.output
    assert "scope_source: absent" in result.output
    assert "cannot cite a declared boundary" in result.output


def test_cli_text_flags_an_unmigrated_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_project(tmp_path)
    _write(tmp_path / "specs" / "scope-boundaries.md", "# Scope\n")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(main, ["explore-ideas", "seed-coverage"])

    assert result.exit_code == 0, result.output
    assert "unmigrated" in result.output
