from __future__ import annotations

from pathlib import Path

from science_tool.entities import resolve_path_policy


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
