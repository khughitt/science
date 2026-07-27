"""Cases are project-state, not knowledge, and not writable by an autonomous actor.

Both properties hold with NO change to `autonomy/policy.py` or to the graph writer;
these guards assert that, so a later edit cannot quietly break either.
"""

from __future__ import annotations

from science_model.autonomous_runs import RunTier

from science_tool.autonomy.changes import (
    ChangeSet,
    ChangeType,
    PathChange,
    entity_kind_for_path,
)
from science_tool.autonomy.path_gate import evaluate
from science_tool.findings.storage import CASES_DIRNAME
from science_tool.graph.io import DEFAULT_REVISION_MANIFEST_EXCLUDES


def test_a_case_path_is_unclassified_and_therefore_denied():
    rel = f"{CASES_DIRNAME}/dataset-stale-review--{'a' * 64}.md"
    assert entity_kind_for_path(rel) is None


def test_the_path_gate_denies_an_actor_writing_a_case():
    rel = f"{CASES_DIRNAME}/dataset-stale-review--{'a' * 64}.md"
    change_set = ChangeSet(
        base_commit="a" * 40,
        head_commit="b" * 40,
        changes=(
            PathChange(
                path=rel,
                change_type=ChangeType.ADDED,
                entity_kind=None,
                fields=(),
            ),
        ),
    )
    verdict = evaluate(change_set, tier=RunTier.BELIEF_NEUTRAL, report_path=None)
    assert not verdict.allowed
    assert any(d.path == rel for d in verdict.denials)


def test_cases_are_excluded_from_the_revision_manifest():
    assert f"{CASES_DIRNAME}/*.md" in DEFAULT_REVISION_MANIFEST_EXCLUDES


def test_a_case_directory_is_not_an_entity_home():
    # `cases` must not be in the directory->kind map, or a case would infer
    # `kind: finding` -- a live epistemic kind (design §5).
    from science_model.frontmatter import _DIR_TO_KIND

    assert "cases" not in _DIR_TO_KIND
    assert "audits" not in _DIR_TO_KIND
