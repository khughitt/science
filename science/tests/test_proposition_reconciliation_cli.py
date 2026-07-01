import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.annotation.cli import annotate_group
from science_tool.annotation.proposition_reconciliation import judgment_id


def _manifest(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: test\nknowledge_profiles:\n  local: local\n",
        encoding="utf-8",
    )


def _proposition(root: Path, slug: str, title: str) -> None:
    path = root / "entities" / "propositions" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nid: proposition:{slug}\ntype: proposition\ntitle: {title}\n"
        "status: active\nsubject: BRCA1 loss\npredicate: affects\n"
        "object: genomic instability\npolarity: positive\n---\n\nClaim.\n",
        encoding="utf-8",
    )


def _review_for_candidate(candidate: dict, canonical: str = "proposition:a") -> dict:
    return {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate["candidate_id"],
                "judgment_id": judgment_id(
                    "same_claim", "same_claim", candidate["propositions"]
                ),
                "lane": "same_claim",
                "decision": "same_claim",
                "canonical_proposition": canonical,
                "members": candidate["propositions"],
                "rationale": "Same signed relation over same endpoints.",
                "confidence": "high",
            }
        ],
    }


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
                "judgment_id": judgment_id(
                    "same_claim", "same_claim", candidate["propositions"]
                ),
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
        blocker["reason"] == "action_conflict"
        for action in payload["actions"]
        for blocker in action["blockers"]
    )


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
