from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.verdict.cli import verdict_group


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "verdict"
REGISTRY_PATH = FIXTURE_DIR / "claim-registry.yaml"


def test_parse_doc_and_emits_json_with_resolved_tokens() -> None:
    result = CliRunner().invoke(verdict_group, ["parse", str(FIXTURE_DIR / "doc_and.md")])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["interpretation_id"] == "interpretation:fixture-and"
    assert payload["composite_token"] == "[+]"
    assert payload["rule_derived_composite"] == "[+]"
    assert payload["rule_disagrees_with_body"] is False
    assert payload["unresolved_claim_ids"] == []


def test_parse_with_registry_populates_unresolved_claim_id() -> None:
    result = CliRunner().invoke(
        verdict_group,
        [
            "parse",
            str(FIXTURE_DIR / "extras" / "doc_unresolved_claim.md"),
            "--registry",
            str(REGISTRY_PATH),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["unresolved_claim_ids"] == ["hunknown#not-in-registry"]


def test_parse_majority_disagreement_emits_body_and_derived_tokens() -> None:
    result = CliRunner().invoke(
        verdict_group,
        ["parse", str(FIXTURE_DIR / "doc_majority_disagrees.md")],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["composite_token"] == "[~]"
    assert payload["rule_derived_composite"] == "[-]"
    assert payload["rule_disagrees_with_body"] is True


def test_parse_help_does_not_expose_strict() -> None:
    result = CliRunner().invoke(verdict_group, ["parse", "--help"])

    assert result.exit_code == 0, result.output
    assert "--strict" not in result.output


def test_rollup_all_json_emits_single_group_with_tally() -> None:
    result = CliRunner().invoke(
        verdict_group,
        ["rollup", "--scope", "all", "--root", str(FIXTURE_DIR), "--output", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["scope"] == "all"
    assert payload["n_documents"] == 6
    assert payload["groups"]["all"]["n"] == 6
    assert payload["groups"]["all"]["tally"]["[+]"] == 2
    assert payload["groups"]["all"]["tally"]["[~]"] == 3
    assert payload["groups"]["all"]["tally"]["[⌀]"] == 1
    assert payload["groups"]["all"]["documents"] == [
        "interpretation:fixture-and",
        "interpretation:fixture-bimodal",
        "interpretation:fixture-majority-disagrees",
        "interpretation:fixture-non-adjudicating",
        "interpretation:fixture-reframed",
        "interpretation:fixture-weighted-majority",
    ]
    assert "interpretation_ids" not in payload["groups"]["all"]


def test_rollup_defaults_root_to_current_working_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shutil.copy(FIXTURE_DIR / "doc_and.md", tmp_path / "doc_and.md")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(verdict_group, ["rollup", "--scope", "all", "--output", "json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["n_documents"] == 1
    assert payload["groups"]["all"]["documents"] == ["interpretation:fixture-and"]


def test_rollup_help_shows_clean_root_default() -> None:
    result = CliRunner().invoke(verdict_group, ["rollup", "--help"])

    assert result.exit_code == 0, result.output
    assert "current working directory" in result.output
    assert "bound method" not in result.output
    assert "PathBase.cwd" not in result.output


def test_rollup_help_describes_strict_validation_warnings() -> None:
    result = CliRunner().invoke(verdict_group, ["rollup", "--help"])

    assert result.exit_code == 0, result.output
    assert "validation warnings" in result.output


def test_rollup_claim_without_registry_errors() -> None:
    result = CliRunner().invoke(
        verdict_group,
        ["rollup", "--scope", "claim", "--root", str(FIXTURE_DIR.parent)],
    )

    assert result.exit_code != 0
    assert "registry" in result.stderr.lower()


def test_rollup_claim_with_registry_json_groups_by_claim() -> None:
    result = CliRunner().invoke(
        verdict_group,
        [
            "rollup",
            "--scope",
            "claim",
            "--root",
            str(FIXTURE_DIR),
            "--registry",
            str(REGISTRY_PATH),
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["scope"] == "claim"
    assert payload["groups"]["h1#edge5-ifn-arm"]["n"] == 1
    assert payload["groups"]["h1#edge5-ifn-arm"]["documents"] == ["interpretation:fixture-and"]
    assert "interpretation_ids" not in payload["groups"]["h1#edge5-ifn-arm"]


def test_rollup_claim_tally_uses_claim_polarity_not_document_composite() -> None:
    result = CliRunner().invoke(
        verdict_group,
        [
            "rollup",
            "--scope",
            "claim",
            "--root",
            str(FIXTURE_DIR),
            "--registry",
            str(REGISTRY_PATH),
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    group = payload["groups"]["t204#v140_6-multitype-non-pc-absorption"]
    assert group["documents"] == ["interpretation:fixture-non-adjudicating"]
    assert group["tally"]["[-]"] == 1
    assert group["tally"]["[⌀]"] == 0


def test_rollup_claim_auto_discovers_registry_under_root_specs(tmp_path: Path) -> None:
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    shutil.copy(FIXTURE_DIR / "doc_and.md", tmp_path / "doc_and.md")
    shutil.copy(REGISTRY_PATH, specs_dir / "claim-registry.yaml")

    result = CliRunner().invoke(
        verdict_group,
        ["rollup", "--scope", "claim", "--root", str(tmp_path), "--output", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["scope"] == "claim"
    assert payload["groups"]["h1#edge5-ifn-arm"]["documents"] == ["interpretation:fixture-and"]


def test_rollup_by_claim_alias_matches_scope_claim() -> None:
    runner = CliRunner()

    by_scope = runner.invoke(
        verdict_group,
        [
            "rollup",
            "--scope",
            "claim",
            "--root",
            str(FIXTURE_DIR),
            "--registry",
            str(REGISTRY_PATH),
            "--output",
            "json",
        ],
    )
    by_alias = runner.invoke(
        verdict_group,
        [
            "rollup",
            "--by-claim",
            "--root",
            str(FIXTURE_DIR),
            "--registry",
            str(REGISTRY_PATH),
            "--output",
            "json",
        ],
    )

    assert by_scope.exit_code == 0, by_scope.output
    assert by_alias.exit_code == 0, by_alias.output
    assert json.loads(by_alias.stdout) == json.loads(by_scope.stdout)


def test_rollup_scope_all_conflicts_with_by_claim() -> None:
    result = CliRunner().invoke(
        verdict_group,
        ["rollup", "--scope", "all", "--by-claim", "--root", str(FIXTURE_DIR)],
    )

    assert result.exit_code != 0
    assert "conflict" in result.stderr.lower() or "cannot" in result.stderr.lower()


def test_rollup_strict_exits_nonzero_on_unresolved_claim(tmp_path: Path) -> None:
    shutil.copy(FIXTURE_DIR / "extras" / "doc_unresolved_claim.md", tmp_path / "doc_unresolved_claim.md")

    result = CliRunner().invoke(
        verdict_group,
        [
            "rollup",
            "--root",
            str(tmp_path),
            "--registry",
            str(REGISTRY_PATH),
            "--output",
            "json",
            "--strict",
        ],
    )

    assert result.exit_code != 0
    assert "unresolved" in result.stderr.lower()


def test_rollup_strict_exits_nonzero_on_validation_warning(tmp_path: Path) -> None:
    path = tmp_path / "missing-body-verdict.md"
    path.write_text(
        """---
id: "interpretation:missing-body-verdict"
verdict:
  composite: "[+]"
  rule: "and"
  claims:
    - id: "h1#edge5-ifn-arm"
      polarity: "[+]"
---

## Verdict

This file intentionally has no body verdict clause.
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        verdict_group,
        [
            "rollup",
            "--root",
            str(tmp_path),
            "--registry",
            str(REGISTRY_PATH),
            "--output",
            "json",
            "--strict",
        ],
    )

    assert result.exit_code != 0
    assert "missing body verdict" in result.stderr.lower()


def test_rollup_non_strict_unresolved_warns_to_stderr_and_keeps_stdout_json(tmp_path: Path) -> None:
    shutil.copy(FIXTURE_DIR / "extras" / "doc_unresolved_claim.md", tmp_path / "doc_unresolved_claim.md")

    result = CliRunner().invoke(
        verdict_group,
        ["rollup", "--root", str(tmp_path), "--registry", str(REGISTRY_PATH), "--output", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["groups"]["all"]["n"] == 1
    assert payload["groups"]["all"]["documents"] == ["interpretation:fixture-unresolved"]
    assert "unresolved" in result.stderr.lower()
