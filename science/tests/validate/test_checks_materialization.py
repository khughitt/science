"""A top-level frontmatter field that materializes no triples is an ERROR (fb-2026-07-11-017).

The graph reads supersession/amendment from a `relations:` entry with the predicate, never
from a top-level `supersedes:`/`amends:` key. Such a key looks authoritative and produces
ZERO triples, silently -- and big-picture then derives a wrong `provenance_coverage`.

`workflow-run.supersedes` is the ONE legitimate top-level use (read by qa_audit/runs.py:47),
so the exception is that exact (kind, key) PAIR -- not a blanket pass for the kind.
"""

from __future__ import annotations

from pathlib import Path

from science_tool.validate.checks.materialization import check_non_materializing_fields
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


def _entity(root: Path, rel: str, *, entity_id: str, kind: str, extra: str) -> None:
    """Seed one entity markdown file. `extra` is raw frontmatter lines (already newline-terminated)."""
    path = root / "entities" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\nid: "{entity_id}"\nkind: {kind}\ntitle: "T"\nstatus: "active"\n{extra}---\n\nBody.\n',
        encoding="utf-8",
    )


def _results(root: Path) -> list:
    (root / "science.yaml").write_text("name: fixture\nprofile: research\n", encoding="utf-8")
    ctx = ValidateContext.from_project_root(root, strict=False, verbose=False)
    return list(check_non_materializing_fields(ctx))


def test_top_level_supersedes_on_interpretation_is_an_error(tmp_path: Path) -> None:
    _entity(
        tmp_path, "interpretations/0001-x.md",
        entity_id="interpretation:0001-x", kind="interpretation",
        extra="supersedes: interpretation:0000-y\n",
    )
    results = _results(tmp_path)
    assert [r.severity for r in results] == [Severity.ERROR]
    msg = results[0].message
    # every required element (design §2)
    assert "interpretation:0001-x" in msg     # the entity id
    assert "top-level 'supersedes:'" in msg   # the authored key, not just the predicate
    assert "relations:" in msg                # the replacement form
    assert "sci:supersedes" in msg            # the predicate
    assert "target" in msg and "<target-id>" in msg   # current field name, schematic target
    assert "interpretation:0000-y" not in msg  # must NOT echo the authored value
    assert results[0].rule == "non-materializing-field"


def test_top_level_amends_on_interpretation_is_an_error(tmp_path: Path) -> None:
    _entity(
        tmp_path, "interpretations/0001-x.md",
        entity_id="interpretation:0001-x", kind="interpretation",
        extra="amends: interpretation:0000-y\n",
    )
    results = _results(tmp_path)
    assert [r.severity for r in results] == [Severity.ERROR]
    assert "interpretation:0001-x" in results[0].message
    assert "top-level 'amends:'" in results[0].message
    assert "sci:amends" in results[0].message


def test_relations_form_is_accepted(tmp_path: Path) -> None:
    _entity(
        tmp_path, "interpretations/0001-x.md",
        entity_id="interpretation:0001-x", kind="interpretation",
        extra="relations:\n  - predicate: sci:supersedes\n    target: interpretation:0000-y\n",
    )
    assert _results(tmp_path) == []


def test_supersedes_on_workflow_run_is_accepted(tmp_path: Path) -> None:
    """The (workflow-run, supersedes) pair is a REAL field read by qa_audit/runs.py:47."""
    _entity(
        tmp_path, "workflow-runs/0001-x.md",
        entity_id="workflow-run:0001-x", kind="workflow-run",
        extra="supersedes: workflow-run:0000-y\n",
    )
    assert _results(tmp_path) == []


def test_amends_on_workflow_run_is_an_error(tmp_path: Path) -> None:
    """The exclusion is PAIR-specific: workflow-run does not get a blanket pass."""
    _entity(
        tmp_path, "workflow-runs/0001-x.md",
        entity_id="workflow-run:0001-x", kind="workflow-run",
        extra="amends: workflow-run:0000-y\n",
    )
    results = _results(tmp_path)
    assert [r.severity for r in results] == [Severity.ERROR]
    assert "sci:amends" in results[0].message


def test_malformed_non_string_kind_still_flags_and_does_not_crash(tmp_path: Path) -> None:
    """A list/mapping `kind` is UNHASHABLE; an unguarded `(kind, key)` frozenset lookup would
    raise, and the runner would abort the whole check (skipping later entities). The key must
    still receive its rule, and the check must not error out."""
    _entity(
        tmp_path, "interpretations/0001-x.md",
        entity_id="interpretation:0001-x", kind="[oops]",  # YAML flow sequence -> unhashable list
        extra="supersedes: interpretation:0000-y\n",
    )
    results = _results(tmp_path)
    assert [r.severity for r in results] == [Severity.ERROR]
    assert results[0].rule == "non-materializing-field"


def test_null_valued_supersedes_is_an_error(tmp_path: Path) -> None:
    """Guards against `fm.get(key) is None`-style detection: presence is the defect, not value."""
    _entity(
        tmp_path, "interpretations/0001-x.md",
        entity_id="interpretation:0001-x", kind="interpretation",
        extra="supersedes: null\n",
    )
    assert [r.severity for r in _results(tmp_path)] == [Severity.ERROR]


def test_empty_list_supersedes_is_an_error(tmp_path: Path) -> None:
    _entity(
        tmp_path, "interpretations/0001-x.md",
        entity_id="interpretation:0001-x", kind="interpretation",
        extra="supersedes: []\n",
    )
    assert [r.severity for r in _results(tmp_path)] == [Severity.ERROR]


def test_clean_entity_yields_nothing(tmp_path: Path) -> None:
    """Non-vacuity guard: with no offending key, the check is silent -- so the ERROR cases
    prove it can fire, not that it fires on everything."""
    _entity(
        tmp_path, "interpretations/0001-x.md",
        entity_id="interpretation:0001-x", kind="interpretation",
        extra="",
    )
    assert _results(tmp_path) == []
