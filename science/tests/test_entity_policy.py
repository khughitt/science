from __future__ import annotations

from datetime import date
from pathlib import Path

from science_tool.entities import _entity_ref_matches, generate_entity_id, path_for_entity, resolve_path_policy


def test_question_policy_is_entities_numeric() -> None:
    policy = resolve_path_policy("question")
    assert policy.root == Path("entities/questions")
    assert policy.strategy == "numeric"


def test_hypothesis_policy_moved_out_of_specs() -> None:
    policy = resolve_path_policy("hypothesis")
    assert policy.root == Path("entities/hypotheses")
    assert policy.strategy == "numeric"


def test_paper_policy_is_citekey() -> None:
    policy = resolve_path_policy("paper")
    assert policy.root == Path("entities/papers")
    assert policy.strategy == "citekey"


def test_synthesis_and_report_have_policies() -> None:
    assert resolve_path_policy("synthesis").root == Path("entities/synthesis")
    assert resolve_path_policy("report").root == Path("entities/reports")


def test_evidence_line_root_is_not_naive_pluralization() -> None:
    assert resolve_path_policy("evidence-line").root == Path("entities/evidence-lines")
    assert resolve_path_policy("pre-registration").root == Path("entities/pre-registrations")


def test_singletons_are_in_the_policy_table() -> None:
    from science_tool.entities import singleton_path

    assert resolve_path_policy("research-question").strategy == "singleton"
    assert singleton_path("research-question") == Path("entities/research-question.md")
    assert singleton_path("claim-registry") == Path("entities/claim-registry.yaml")


def test_first_numeric_entity_starts_at_0001(tmp_path) -> None:
    eid = generate_entity_id(tmp_path, "question", "Model Granularity", None, None)
    assert eid == "question:0001-model-granularity"


def test_numeric_increments_from_siblings(tmp_path) -> None:
    d = tmp_path / "entities" / "questions"
    d.mkdir(parents=True)
    (d / "0001-existing.md").write_text("x", encoding="utf-8")
    (d / "0007-other.md").write_text("x", encoding="utf-8")
    eid = generate_entity_id(tmp_path, "question", "New One", None, None)
    assert eid == "question:0008-new-one"


def test_numeric_scan_tolerates_legacy_letter_prefix(tmp_path) -> None:
    d = tmp_path / "entities" / "hypotheses"
    d.mkdir(parents=True)
    (d / "h03-legacy.md").write_text("x", encoding="utf-8")
    eid = generate_entity_id(tmp_path, "hypothesis", "Next", None, None)
    assert eid == "hypothesis:0004-next"


def test_citekey_requires_explicit_id(tmp_path) -> None:
    import pytest
    from science_tool.entities import EntityCommandError

    with pytest.raises(EntityCommandError):
        generate_entity_id(tmp_path, "paper", "Some Title", None, None)
    eid = generate_entity_id(tmp_path, "paper", "", "paper:Adams2025", None)
    assert eid == "paper:Adams2025"


def test_explicit_numeric_id_must_be_canonical(tmp_path) -> None:
    import pytest
    from science_tool.entities import EntityCommandError

    # Legacy letter-prefixed and wrong-width ids must be rejected, so --id
    # cannot reintroduce drift under entities/questions/.
    # signature: generate_entity_id(project_root, kind, title, entity_id, slug)
    with pytest.raises(EntityCommandError):
        generate_entity_id(tmp_path, "question", "", "question:q01-old-shape", None)
    with pytest.raises(EntityCommandError):
        generate_entity_id(tmp_path, "question", "", "question:5-too-short", None)
    ok = generate_entity_id(tmp_path, "question", "", "question:0005-good", None)
    assert ok == "question:0005-good"


def test_path_for_entity_uses_policy_root(tmp_path) -> None:
    p = path_for_entity("question", "question:0008-new-one", date(2026, 6, 3))
    assert p == Path("entities/questions/0008-new-one.md")
    pp = path_for_entity("paper", "paper:Adams2025", date(2026, 6, 3))
    assert pp == Path("entities/papers/Adams2025.md")


def test_shortform_resolves_zero_padded_id() -> None:
    assert _entity_ref_matches("question:0005-model-granularity", "q5")
    assert _entity_ref_matches("hypothesis:0003-attractor", "h3")
    assert not _entity_ref_matches("question:0005-model-granularity", "h5")  # wrong kind


def test_shortform_still_matches_legacy_unpadded_id() -> None:
    # during transition, legacy ids like question:5-foo must still resolve
    assert _entity_ref_matches("question:5-foo", "q5")
