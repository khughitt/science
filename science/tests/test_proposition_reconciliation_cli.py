import json
from datetime import datetime, timezone
from pathlib import Path

from click.testing import CliRunner

from science_tool.annotation import io as anno_io
from science_tool.annotation.cli import annotate_group
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.proposition_reconciliation import judgment_id
from science_tool.annotation.proposition_reconciliation_decisions import DEFAULT_DECISION_LOG
from test_proposition_resynthesis import (
    _draft_payload,
    _factorization_project,
)

_CREATED = datetime(2026, 6, 30, tzinfo=timezone.utc)


def _manifest(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: test\nknowledge_profiles:\n  local: local\n",
        encoding="utf-8",
    )


def _proposition(
    root: Path,
    slug: str,
    title: str,
    *,
    source_refs: tuple[str, ...] = (),
) -> None:
    path = root / "entities" / "propositions" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    refs = ""
    if source_refs:
        refs = "source_refs:\n" + "".join(f"  - {ref}\n" for ref in source_refs)
    path.write_text(
        f"---\nid: proposition:{slug}\ntype: proposition\ntitle: {title}\n"
        "status: active\nsubject: BRCA1 loss\npredicate: affects\n"
        f"object: genomic instability\npolarity: positive\n{refs}---\n\nClaim.\n",
        encoding="utf-8",
    )


def _ann(annotation_id: str, promoted_to: str) -> Annotation:
    body = json.dumps({"section": "results", "stance": "asserted"})
    return Annotation(
        id=annotation_id,
        target=SpecificResource(
            source="x.source.md",
            selector=TextQuoteSelector(exact=annotation_id, prefix="", suffix=""),
        ),
        bodies=(TextualBody(value=body, format="application/json"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="proposition",
        source="llm-annot:m:paper-annotate-v1",
        status=Status.OPEN,
        creator="paper-annotate",
        created=_CREATED,
        content_hash="0" * 64,
        promoted_to=promoted_to,
    )


def _paper_sidecar(root: Path, citekey: str, annotations: tuple[Annotation, ...]) -> Path:
    md = root / "entities" / "papers" / f"{citekey}.source.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("Results show the claim.\n", encoding="utf-8")
    sidecar_path = anno_io.sidecar_for_markdown(md)
    anno_io.write_sidecar(sidecar_path, Sidecar(annotations=annotations))
    return sidecar_path


def _review_for_candidate(candidate: dict, canonical: str = "proposition:a") -> dict:
    return {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate["candidate_id"],
                "judgment_id": judgment_id("same_claim", "same_claim", candidate["propositions"]),
                "lane": "same_claim",
                "decision": "same_claim",
                "canonical_proposition": canonical,
                "members": candidate["propositions"],
                "rationale": "Same signed relation over same endpoints.",
                "confidence": "high",
            }
        ],
    }


def _related_but_distinct_review_for_candidate(candidate: dict) -> dict:
    return {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate["candidate_id"],
                "judgment_id": judgment_id("same_claim", "related_but_distinct", candidate["propositions"]),
                "lane": "same_claim",
                "decision": "related_but_distinct",
                "members": candidate["propositions"],
                "rationale": "Related but not a duplicate claim.",
                "confidence": "high",
            }
        ],
    }


def _related_but_distinct_plan(root: Path, runner: CliRunner) -> Path:
    _manifest(root)
    _proposition(root, "a", "BRCA1 loss increases genomic instability")
    _proposition(root, "b", "Loss of BRCA1 raises genome instability")
    generated = runner.invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(root), "--format", "json"],
    )
    candidate = json.loads(generated.output)["same_claim_candidates"][0]
    review_path = root / "review.json"
    review_path.write_text(
        json.dumps(_related_but_distinct_review_for_candidate(candidate)),
        encoding="utf-8",
    )
    plan_path = root / "plan.json"
    plan_result = runner.invoke(
        annotate_group,
        [
            "plan-proposition-reconciliation",
            "--root",
            str(root),
            "--input",
            str(review_path),
            "--output",
            str(plan_path),
            "--format",
            "json",
        ],
    )
    assert plan_result.exit_code == 0, plan_result.output
    return plan_path


def _record_related_but_distinct_decision(root: Path, runner: CliRunner) -> dict:
    _manifest(root)
    _proposition(root, "a", "BRCA1 loss increases genomic instability")
    _proposition(root, "b", "Loss of BRCA1 raises genome instability")
    generated = runner.invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(root), "--format", "json"],
    )
    assert generated.exit_code == 0, generated.output
    candidate = json.loads(generated.output)["same_claim_candidates"][0]
    review_path = root / "review.json"
    review_path.write_text(
        json.dumps(_related_but_distinct_review_for_candidate(candidate)),
        encoding="utf-8",
    )
    plan_path = root / "plan.json"
    plan_result = runner.invoke(
        annotate_group,
        [
            "plan-proposition-reconciliation",
            "--root",
            str(root),
            "--input",
            str(review_path),
            "--output",
            str(plan_path),
            "--format",
            "json",
        ],
    )
    assert plan_result.exit_code == 0, plan_result.output
    record_result = runner.invoke(
        annotate_group,
        [
            "record-proposition-reconciliation-decisions",
            "--root",
            str(root),
            "--input",
            str(plan_path),
            "--apply",
            "--format",
            "json",
        ],
    )
    assert record_result.exit_code == 0, record_result.output
    return candidate


def test_reconcile_propositions_json(tmp_path: Path):
    _manifest(tmp_path)
    _proposition(tmp_path, "a", "BRCA1 loss increases genomic instability")
    _proposition(tmp_path, "b", "Loss of BRCA1 raises genome instability")

    result = CliRunner().invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(tmp_path), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["summary"]["same_claim_candidates"] == 1
    assert payload["same_claim_candidates"][0]["propositions"] == [
        "proposition:a",
        "proposition:b",
    ]


def test_reconcile_propositions_suppresses_reviewed_decision_by_default(tmp_path: Path):
    runner = CliRunner()
    candidate = _record_related_but_distinct_decision(tmp_path, runner)

    result = runner.invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(tmp_path), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["summary"]["reviewed_decisions"] == 1
    assert payload["summary"]["same_claim_candidates"] == 0
    assert payload["summary"]["generated_same_claim_candidates"] == 1
    assert payload["same_claim_candidates"] == []
    assert payload["reviewed_decisions"]["active"][0]["candidate_id"] == candidate["candidate_id"]

    scaffold = runner.invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(tmp_path), "--format", "scaffold"],
    )
    assert scaffold.exit_code == 0, scaffold.output
    scaffold_payload = json.loads(scaffold.output)
    assert scaffold_payload["summary"]["same_claim_candidates"] == 0
    assert scaffold_payload["same_claim_candidates"] == []


def test_reconcile_propositions_show_reviewed_keeps_annotated_candidate(tmp_path: Path):
    runner = CliRunner()
    _record_related_but_distinct_decision(tmp_path, runner)

    result = runner.invoke(
        annotate_group,
        [
            "reconcile-propositions",
            "--all",
            "--show-reviewed",
            "--root",
            str(tmp_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["summary"]["same_claim_candidates"] == 1
    assert len(payload["same_claim_candidates"]) == 1
    assert payload["same_claim_candidates"][0]["reviewed_decision_id"].startswith(
        "reconcile-decision:"
    )

    scaffold = runner.invoke(
        annotate_group,
        [
            "reconcile-propositions",
            "--all",
            "--show-reviewed",
            "--root",
            str(tmp_path),
            "--format",
            "scaffold",
        ],
    )
    assert scaffold.exit_code == 0, scaffold.output
    scaffold_payload = json.loads(scaffold.output)
    assert scaffold_payload["summary"]["same_claim_candidates"] == 1
    assert scaffold_payload["same_claim_candidates"][0]["reviewed_decision_id"].startswith(
        "reconcile-decision:"
    )


def test_reconcile_propositions_table(tmp_path: Path):
    _manifest(tmp_path)
    _proposition(tmp_path, "a", "BRCA1 loss increases genomic instability")
    _proposition(tmp_path, "b", "Loss of BRCA1 raises genome instability")

    result = CliRunner().invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert "same_claim" in result.output
    assert "proposition:a" in result.output


def test_validate_proposition_reconciliation_cli(tmp_path: Path):
    _manifest(tmp_path)
    _proposition(tmp_path, "a", "BRCA1 loss increases genomic instability")
    _proposition(tmp_path, "b", "Loss of BRCA1 raises genome instability")
    generated = CliRunner().invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(tmp_path), "--format", "json"],
    )
    payload = json.loads(generated.output)
    candidate = payload["same_claim_candidates"][0]
    review = {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate["candidate_id"],
                "judgment_id": judgment_id("same_claim", "same_claim", candidate["propositions"]),
                "lane": "same_claim",
                "decision": "same_claim",
                "canonical_proposition": "proposition:a",
                "members": candidate["propositions"],
                "rationale": "Same signed relation over same endpoints.",
                "confidence": "high",
            }
        ],
    }
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")

    result = CliRunner().invoke(
        annotate_group,
        [
            "validate-proposition-reconciliation",
            "--root",
            str(tmp_path),
            "--input",
            str(review_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["status"] == "ok"


def test_reconcile_propositions_rejects_multiple_scopes(tmp_path: Path):
    _manifest(tmp_path)
    result = CliRunner().invoke(
        annotate_group,
        [
            "reconcile-propositions",
            "--all",
            "--proposition",
            "proposition:a",
            "--root",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "choose exactly one scope" in result.output


def test_plan_proposition_reconciliation_cli_json(tmp_path: Path):
    _manifest(tmp_path)
    _proposition(tmp_path, "a", "BRCA1 loss increases genomic instability")
    _proposition(tmp_path, "b", "Loss of BRCA1 raises genome instability")
    generated = CliRunner().invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(tmp_path), "--format", "json"],
    )
    candidate = json.loads(generated.output)["same_claim_candidates"][0]
    review_path = tmp_path / "review.json"
    review_path.write_text(
        json.dumps(_review_for_candidate(candidate)),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        annotate_group,
        [
            "plan-proposition-reconciliation",
            "--root",
            str(tmp_path),
            "--input",
            str(review_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["schema_version"] == 1
    assert payload["summary"]["ready_actions"] == 1
    assert payload["actions"][0]["kind"] == "canonicalize_propositions"
    assert payload["actions"][0]["writes"] == []


def test_plan_proposition_reconciliation_cli_table_and_output(tmp_path: Path):
    _manifest(tmp_path)
    _proposition(tmp_path, "a", "BRCA1 loss increases genomic instability")
    _proposition(tmp_path, "b", "Loss of BRCA1 raises genome instability")
    generated = CliRunner().invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(tmp_path), "--format", "json"],
    )
    candidate = json.loads(generated.output)["same_claim_candidates"][0]
    review_path = tmp_path / "review.json"
    output_path = tmp_path / "plan.json"
    review_path.write_text(
        json.dumps(_review_for_candidate(candidate)),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        annotate_group,
        [
            "plan-proposition-reconciliation",
            "--root",
            str(tmp_path),
            "--input",
            str(review_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "proposition reconciliation action plan:" in result.output
    assert "canonicalize_propositions" in result.output
    assert json.loads(output_path.read_text(encoding="utf-8"))["summary"]["ready_actions"] == 1


def test_plan_proposition_reconciliation_cli_accepts_repeated_input(tmp_path: Path):
    _manifest(tmp_path)
    _proposition(tmp_path, "a", "BRCA1 loss increases genomic instability")
    _proposition(tmp_path, "b", "Loss of BRCA1 raises genome instability")
    generated = CliRunner().invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(tmp_path), "--format", "json"],
    )
    candidate = json.loads(generated.output)["same_claim_candidates"][0]
    review_a = tmp_path / "review-a.json"
    review_b = tmp_path / "review-b.json"
    review_a.write_text(json.dumps(_review_for_candidate(candidate)), encoding="utf-8")
    review_b.write_text(json.dumps(_review_for_candidate(candidate)), encoding="utf-8")

    result = CliRunner().invoke(
        annotate_group,
        [
            "plan-proposition-reconciliation",
            "--root",
            str(tmp_path),
            "--input",
            str(review_a),
            "--input",
            str(review_b),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["source_reviews"] == [str(review_a), str(review_b)]
    assert payload["summary"]["blocked_actions"] == 2
    assert any(
        blocker["reason"] == "action_conflict" for action in payload["actions"] for blocker in action["blockers"]
    )


def test_record_reconciliation_decisions_dry_run_does_not_write_default_log(
    tmp_path: Path,
):
    runner = CliRunner()
    plan_path = _related_but_distinct_plan(tmp_path, runner)

    result = runner.invoke(
        annotate_group,
        [
            "record-proposition-reconciliation-decisions",
            "--root",
            str(tmp_path),
            "--input",
            str(plan_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["summary"]["would_append"] == 1
    assert payload["summary"]["appended"] == 0
    assert not (tmp_path / DEFAULT_DECISION_LOG).exists()


def test_record_reconciliation_decisions_apply_is_idempotent(
    tmp_path: Path,
):
    runner = CliRunner()
    plan_path = _related_but_distinct_plan(tmp_path, runner)

    first = runner.invoke(
        annotate_group,
        [
            "record-proposition-reconciliation-decisions",
            "--root",
            str(tmp_path),
            "--input",
            str(plan_path),
            "--apply",
            "--format",
            "json",
        ],
    )
    second = runner.invoke(
        annotate_group,
        [
            "record-proposition-reconciliation-decisions",
            "--root",
            str(tmp_path),
            "--input",
            str(plan_path),
            "--apply",
            "--format",
            "json",
        ],
    )

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    first_payload = json.loads(first.output)
    second_payload = json.loads(second.output)
    assert first_payload["summary"]["would_append"] == 1
    assert first_payload["summary"]["appended"] == 1
    assert second_payload["summary"]["already_recorded"] == 1
    log_path = tmp_path / DEFAULT_DECISION_LOG
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 1


def test_record_reconciliation_decisions_rejects_invalid_json_input(tmp_path: Path):
    _manifest(tmp_path)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text("{not json", encoding="utf-8")

    result = CliRunner().invoke(
        annotate_group,
        [
            "record-proposition-reconciliation-decisions",
            "--root",
            str(tmp_path),
            "--input",
            str(plan_path),
        ],
    )

    assert result.exit_code != 0
    assert "is not valid JSON" in result.output


def test_record_reconciliation_decisions_rejects_non_object_json_input(tmp_path: Path):
    _manifest(tmp_path)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text("[]", encoding="utf-8")

    result = CliRunner().invoke(
        annotate_group,
        [
            "record-proposition-reconciliation-decisions",
            "--root",
            str(tmp_path),
            "--input",
            str(plan_path),
        ],
    )

    assert result.exit_code != 0
    assert "must contain a JSON object" in result.output


def test_record_reconciliation_decisions_relative_decisions_path_is_project_rooted(
    tmp_path: Path,
    monkeypatch,
):
    runner = CliRunner()
    project_root = tmp_path / "project"
    project_root.mkdir()
    plan_path = _related_but_distinct_plan(project_root, runner)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        annotate_group,
        [
            "record-proposition-reconciliation-decisions",
            "--root",
            str(project_root),
            "--input",
            str(plan_path),
            "--decisions",
            "custom/decisions.jsonl",
            "--apply",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["summary"]["appended"] == 1
    assert (project_root / "custom" / "decisions.jsonl").exists()
    assert not (tmp_path / "custom" / "decisions.jsonl").exists()


def test_plan_proposition_reconciliation_cli_rejects_empty_review(tmp_path: Path):
    _manifest(tmp_path)
    empty_review = tmp_path / "empty-review.json"
    empty_review.write_text(
        json.dumps(
            {
                "source": "llm-review:claude:proposition-reconcile-v1",
                "judgments": [],
            }
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        annotate_group,
        [
            "plan-proposition-reconciliation",
            "--root",
            str(tmp_path),
            "--input",
            str(empty_review),
        ],
    )

    assert result.exit_code != 0
    assert f"{empty_review} produced no judgments" in result.output


def test_plan_proposition_reconciliation_cli_rejects_empty_review_even_with_valid_input(
    tmp_path: Path,
):
    _manifest(tmp_path)
    _proposition(tmp_path, "a", "BRCA1 loss increases genomic instability")
    _proposition(tmp_path, "b", "Loss of BRCA1 raises genome instability")
    generated = CliRunner().invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(tmp_path), "--format", "json"],
    )
    candidate = json.loads(generated.output)["same_claim_candidates"][0]
    review_path = tmp_path / "review.json"
    empty_review = tmp_path / "empty-review.json"
    review_path.write_text(json.dumps(_review_for_candidate(candidate)), encoding="utf-8")
    empty_review.write_text(
        json.dumps(
            {
                "source": "llm-review:claude:proposition-reconcile-v1",
                "judgments": [],
            }
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        annotate_group,
        [
            "plan-proposition-reconciliation",
            "--root",
            str(tmp_path),
            "--input",
            str(review_path),
            "--input",
            str(empty_review),
        ],
    )

    assert result.exit_code != 0
    assert f"{empty_review} produced no judgments" in result.output


def test_plan_proposition_reconciliation_cli_includes_review_path_for_stale_candidate(
    tmp_path: Path,
):
    _manifest(tmp_path)
    _proposition(tmp_path, "a", "BRCA1 loss increases genomic instability")
    _proposition(tmp_path, "b", "Loss of BRCA1 raises genome instability")
    generated = CliRunner().invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(tmp_path), "--format", "json"],
    )
    candidate = json.loads(generated.output)["same_claim_candidates"][0]
    review = _review_for_candidate(candidate)
    review["judgments"][0]["candidate_id"] = "reconcile:candidate:stale"
    bad_review = tmp_path / "bad-review.json"
    bad_review.write_text(json.dumps(review), encoding="utf-8")

    result = CliRunner().invoke(
        annotate_group,
        [
            "plan-proposition-reconciliation",
            "--root",
            str(tmp_path),
            "--input",
            str(bad_review),
        ],
    )

    assert result.exit_code != 0
    assert str(bad_review) in result.output
    assert "candidate_id is stale or unknown" in result.output


def test_plan_proposition_reconciliation_cli_rejects_invalid_review(tmp_path: Path):
    _manifest(tmp_path)
    review_path = tmp_path / "review.json"
    review_path.write_text("{not json", encoding="utf-8")

    result = CliRunner().invoke(
        annotate_group,
        [
            "plan-proposition-reconciliation",
            "--root",
            str(tmp_path),
            "--input",
            str(review_path),
        ],
    )

    assert result.exit_code != 0
    assert "is not valid JSON" in result.output
    assert str(review_path) in result.output


def test_apply_proposition_reconciliation_cli_applies_ready_canonicalization(
    tmp_path: Path,
):
    _manifest(tmp_path)
    _proposition(
        tmp_path,
        "a",
        "BRCA1 loss increases genomic instability",
        source_refs=("paper:A2020", "annotation:entities/papers/A2020.source#a1"),
    )
    _proposition(
        tmp_path,
        "b",
        "Loss of BRCA1 raises genome instability",
        source_refs=("paper:B2021", "annotation:entities/papers/B2021.source#b1"),
    )
    _paper_sidecar(tmp_path, "A2020", (_ann("a1", "proposition:a"),))
    _paper_sidecar(tmp_path, "B2021", (_ann("b1", "proposition:b"),))
    generated = CliRunner().invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(tmp_path), "--format", "json"],
    )
    candidate = json.loads(generated.output)["same_claim_candidates"][0]
    review_path = tmp_path / "review.json"
    review_path.write_text(
        json.dumps(_review_for_candidate(candidate)),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        annotate_group,
        [
            "apply-proposition-reconciliation",
            "--root",
            str(tmp_path),
            "--input",
            str(review_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["schema_version"] == 1
    assert payload["status"] == "ok"
    assert payload["summary"]["selected_actions"] == 1
    assert len(payload["changed_paths"]) > 0
    assert all(not path.startswith(str(tmp_path)) for path in payload["changed_paths"])
    assert all(not path.startswith(str(tmp_path)) for path in payload["written_paths"])
    assert any(path.startswith("entities/propositions/") for path in payload["changed_paths"])
    assert any(path.startswith("entities/propositions/") for path in payload["written_paths"])
    duplicate_text = (tmp_path / "entities" / "propositions" / "b.md").read_text(encoding="utf-8")
    assert "status: superseded" in duplicate_text
    assert "superseded_by: proposition:a" in duplicate_text


def test_apply_proposition_reconciliation_cli_table_uses_relative_paths(tmp_path: Path):
    _manifest(tmp_path)
    _proposition(
        tmp_path,
        "a",
        "BRCA1 loss increases genomic instability",
        source_refs=("paper:A2020", "annotation:entities/papers/A2020.source#a1"),
    )
    _proposition(
        tmp_path,
        "b",
        "Loss of BRCA1 raises genome instability",
        source_refs=("paper:B2021", "annotation:entities/papers/B2021.source#b1"),
    )
    _paper_sidecar(tmp_path, "A2020", (_ann("a1", "proposition:a"),))
    _paper_sidecar(tmp_path, "B2021", (_ann("b1", "proposition:b"),))
    generated = CliRunner().invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(tmp_path), "--format", "json"],
    )
    candidate = json.loads(generated.output)["same_claim_candidates"][0]
    review_path = tmp_path / "review.json"
    review_path.write_text(
        json.dumps(_review_for_candidate(candidate)),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        annotate_group,
        [
            "apply-proposition-reconciliation",
            "--root",
            str(tmp_path),
            "--input",
            str(review_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert str(tmp_path) not in result.output
    assert "changed paths:" in result.output
    assert "  entities/propositions/" in result.output


def test_apply_proposition_reconciliation_cli_rejects_empty_review(tmp_path: Path):
    _manifest(tmp_path)
    empty_review = tmp_path / "empty-review.json"
    empty_review.write_text(
        json.dumps(
            {
                "source": "llm-review:claude:proposition-reconcile-v1",
                "judgments": [],
            }
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        annotate_group,
        [
            "apply-proposition-reconciliation",
            "--root",
            str(tmp_path),
            "--input",
            str(empty_review),
        ],
    )

    assert result.exit_code != 0
    assert "produced no judgments" in result.output


def test_apply_proposition_reconciliation_cli_rejects_non_canonicalization_action(
    tmp_path: Path,
):
    _manifest(tmp_path)
    _proposition(tmp_path, "a", "BRCA1 loss increases genomic instability")
    _proposition(tmp_path, "b", "Loss of BRCA1 raises genome instability")
    generated = CliRunner().invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(tmp_path), "--format", "json"],
    )
    candidate = json.loads(generated.output)["same_claim_candidates"][0]
    review_path = tmp_path / "related-review.json"
    review_path.write_text(
        json.dumps(_related_but_distinct_review_for_candidate(candidate)),
        encoding="utf-8",
    )
    planned = CliRunner().invoke(
        annotate_group,
        [
            "plan-proposition-reconciliation",
            "--root",
            str(tmp_path),
            "--input",
            str(review_path),
            "--format",
            "json",
        ],
    )
    action_id = json.loads(planned.output)["actions"][0]["action_id"]

    result = CliRunner().invoke(
        annotate_group,
        [
            "apply-proposition-reconciliation",
            "--root",
            str(tmp_path),
            "--input",
            str(review_path),
            "--action",
            action_id,
        ],
    )

    assert result.exit_code != 0
    assert "not executable by Half C" in result.output


def test_scaffold_proposition_resynthesis_cli_writes_draft(tmp_path: Path):
    ctx = _factorization_project(tmp_path)
    output_path = tmp_path / "resynthesis-draft.json"

    result = CliRunner().invoke(
        annotate_group,
        [
            "scaffold-proposition-resynthesis",
            "--root",
            str(tmp_path),
            "--input",
            str(ctx["review_path"]),
            "--output",
            str(output_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    draft = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["status"] == "ok"
    assert payload["selected_action_id"] == ctx["action"].action_id
    assert payload["output_path"] == str(output_path)
    assert payload["draft"] == draft
    assert draft["action_id"] == ctx["action"].action_id
    assert draft["input_annotations"] == list(ctx["action"].inputs["annotations"])
    assert draft["new_propositions"] == []
    assert draft["annotation_assignments"] == []


def test_scaffold_proposition_resynthesis_cli_writes_project_relative_source_review_for_relative_input(
    tmp_path: Path,
    monkeypatch,
):
    project_root = tmp_path / "project"
    project_root.mkdir()
    ctx = _factorization_project(project_root)
    output_path = project_root / "resynthesis-draft.json"
    monkeypatch.chdir(tmp_path)

    scaffolded = CliRunner().invoke(
        annotate_group,
        [
            "scaffold-proposition-resynthesis",
            "--root",
            "project",
            "--input",
            "project/review.json",
            "--output",
            "project/resynthesis-draft.json",
            "--format",
            "json",
        ],
    )

    assert scaffolded.exit_code == 0, scaffolded.output
    draft = json.loads(output_path.read_text(encoding="utf-8"))
    assert draft["source_review"] == "review.json"

    populated = _draft_payload({**ctx, "review_path": Path("review.json")})
    populated["source_review"] = draft["source_review"]
    output_path.write_text(json.dumps(populated), encoding="utf-8")

    validated = CliRunner().invoke(
        annotate_group,
        [
            "validate-proposition-resynthesis",
            "--root",
            "project",
            "--input",
            "project/resynthesis-draft.json",
            "--format",
            "json",
        ],
    )

    assert validated.exit_code == 0, validated.output


def test_validate_proposition_resynthesis_cli_reports_valid_draft(tmp_path: Path):
    ctx = _factorization_project(tmp_path)
    draft_path = tmp_path / "resynthesis-draft.json"
    draft_path.write_text(json.dumps(_draft_payload(ctx)), encoding="utf-8")

    result = CliRunner().invoke(
        annotate_group,
        [
            "validate-proposition-resynthesis",
            "--root",
            str(tmp_path),
            "--input",
            str(draft_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["schema_version"] == 1
    assert payload["status"] == "ok"
    assert payload["summary"] == {
        "replacement_propositions": 2,
        "moved_annotations": 2,
        "retained_annotations": 0,
        "planned_changed_paths": 2,
        "planned_noop_paths": 0,
        "errors": 0,
        "warnings": 0,
    }
    assert payload["expected_annotation_targets"] == {
        "annotation:entities/papers/A2020.source#a1": "proposition:broad-positive",
        "annotation:entities/papers/B2021.source#b1": "proposition:broad-negative",
    }


def test_apply_proposition_resynthesis_cli_applies_valid_draft(tmp_path: Path):
    ctx = _factorization_project(tmp_path)
    draft_path = tmp_path / "resynthesis-draft.json"
    draft_path.write_text(json.dumps(_draft_payload(ctx)), encoding="utf-8")

    result = CliRunner().invoke(
        annotate_group,
        [
            "apply-proposition-resynthesis",
            "--root",
            str(tmp_path),
            "--input",
            str(draft_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["schema_version"] == 1
    assert payload["status"] == "ok"
    assert payload["summary"]["replacement_propositions"] == 2
    assert payload["summary"]["rewritten_annotations"] == 2
    assert all(not path.startswith(str(tmp_path)) for path in payload["changed_paths"])
    assert "entities/propositions/broad-positive.md" in payload["changed_paths"]
    assert "entities/propositions/broad-negative.md" in payload["changed_paths"]
    assert (
        anno_io.read_sidecar(tmp_path / "entities" / "papers" / "A2020.source.anno.trig")
        .annotations[0]
        .promoted_to
        == "proposition:broad-positive"
    )


def test_validate_proposition_resynthesis_cli_includes_input_path_on_malformed_json(
    tmp_path: Path,
):
    _factorization_project(tmp_path)
    draft_path = tmp_path / "malformed-draft.json"
    draft_path.write_text("{not json", encoding="utf-8")

    result = CliRunner().invoke(
        annotate_group,
        [
            "validate-proposition-resynthesis",
            "--root",
            str(tmp_path),
            "--input",
            str(draft_path),
        ],
    )

    assert result.exit_code != 0
    assert str(draft_path) in result.output
    assert "is not valid JSON" in result.output
