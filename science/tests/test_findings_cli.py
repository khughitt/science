import json

import pytest
from click.testing import CliRunner

import science_tool.findings.cli as findings_cli
from science_tool.findings.acceptance_migration import AcceptanceMigration, EntryMigration
from science_tool.findings.cli import findings_group
from science_tool.findings.ingest import ingestion_authority
from science_tool.findings.producers import FindingProducer, build_registry
from science_tool.validate.acceptance import AcceptedValidationEntry, classify_acceptance_entry


REGISTRY = build_registry(
    [
        FindingProducer(
            producer_id="dataset_anomalies",
            namespace="health_checks",
            source_module="graph/health_checks/test.py",
            rules=(),
            sections=(),
            metrics_schema=None,
            remediators=frozenset(),
        )
    ],
    active_kinds=frozenset(),
)


def _patch_registry(monkeypatch, registry=REGISTRY):
    """Swap the registry half of `ingestion_authority` for the test double.

    Keeps the real project-derived `IngestionContext`, so identity-collision and
    malformed-configuration behavior is exercised unchanged.
    """

    def _fake(project_root):
        _real_registry, context = ingestion_authority(project_root)
        return registry, context

    monkeypatch.setattr(findings_cli, "ingestion_authority", _fake)


def _report_json() -> dict:
    return {
        "schema_version": 2,
        "fingerprint_version": 1,
        "ingestion_ref": "ing:1",
        "generated_at": "2026-07-27T12:00:00+00:00",
        "findings": [],
        "accepted": [],
        "metrics": {},
        "unwired": [],
        "totals": {
            "findings_total": 0,
            "findings_by_severity": {},
            "accepted_total": 0,
            "unwired_total": 0,
        },
        "meta": {
            "producers_run": ["dataset_anomalies"],
            "total_duration_seconds": 0.0,
            "timings": [],
        },
    }


def _attestation_args() -> list[str]:
    return [
        "--attest-ingestion-ref",
        "ing:1",
        "--attest-generated-at",
        "2026-07-27T12:00:00+00:00",
        "--attest-producer-id",
        "dataset_anomalies",
    ]


def test_ingest_reports_what_it_did(tmp_path, monkeypatch):
    _patch_registry(monkeypatch)
    report = tmp_path / "report.json"
    report.write_text(json.dumps(_report_json()), encoding="utf-8")
    result = CliRunner().invoke(
        findings_group,
        [
            "ingest",
            str(report),
            "--project-root",
            str(tmp_path),
            "--format",
            "json",
            *_attestation_args(),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["records_written"] == 0


def test_ingest_exits_nonzero_on_a_refused_report(tmp_path):
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
    result = CliRunner().invoke(
        findings_group,
        [
            "ingest",
            str(report),
            "--project-root",
            str(tmp_path),
            *_attestation_args(),
        ],
    )
    assert result.exit_code == 2
    assert "schema_version" in result.output


@pytest.mark.parametrize(
    "missing_option",
    [
        "--attest-ingestion-ref",
        "--attest-generated-at",
        "--attest-producer-id",
    ],
)
def test_ingest_requires_each_explicit_attestation_flag(tmp_path, missing_option):
    report = tmp_path / "report.json"
    report.write_text(json.dumps(_report_json()), encoding="utf-8")
    attestation = _attestation_args()
    index = attestation.index(missing_option)
    del attestation[index : index + 2]

    result = CliRunner().invoke(
        findings_group,
        [
            "ingest",
            str(report),
            "--project-root",
            str(tmp_path),
            *attestation,
        ],
    )

    assert result.exit_code == 2
    assert f"Missing option '{missing_option}'" in result.output


def test_ingest_refuses_a_report_attestation_mismatch(tmp_path, monkeypatch):
    _patch_registry(monkeypatch)
    report = tmp_path / "report.json"
    report.write_text(json.dumps(_report_json()), encoding="utf-8")
    result = CliRunner().invoke(
        findings_group,
        [
            "ingest",
            str(report),
            "--project-root",
            str(tmp_path),
            "--attest-ingestion-ref",
            "different",
            "--attest-generated-at",
            "2026-07-27T12:00:00+00:00",
            "--attest-producer-id",
            "dataset_anomalies",
        ],
    )

    assert result.exit_code == 2
    assert "ingestion_ref" in result.output
    assert not (tmp_path / "doc" / "audits" / "cases").exists()


def test_ingest_cli_refuses_graph_identity_collisions_before_case_writes(
    tmp_path,
    monkeypatch,
):
    _patch_registry(monkeypatch)
    for name in ("q1.md", "q1-duplicate.md"):
        path = tmp_path / "entities" / "questions" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\nid: question:q1\nkind: question\ntitle: Q1\n---\n",
            encoding="utf-8",
        )
    report = tmp_path / "report.json"
    report.write_text(json.dumps(_report_json()), encoding="utf-8")

    result = CliRunner().invoke(
        findings_group,
        [
            "ingest",
            str(report),
            "--project-root",
            str(tmp_path),
            *_attestation_args(),
        ],
    )

    assert result.exit_code == 2
    assert "question:q1" in result.output
    assert not (tmp_path / "doc" / "audits" / "cases").exists()


def test_ingest_cli_wraps_malformed_graph_configuration_as_a_refusal(
    tmp_path,
    monkeypatch,
):
    _patch_registry(monkeypatch)
    (tmp_path / "science.yaml").write_text(
        "name: [unterminated\n",
        encoding="utf-8",
    )
    report = tmp_path / "report.json"
    report.write_text(json.dumps(_report_json()), encoding="utf-8")

    result = CliRunner().invoke(
        findings_group,
        [
            "ingest",
            str(report),
            "--project-root",
            str(tmp_path),
            *_attestation_args(),
        ],
    )

    assert result.exit_code == 2
    assert "refused:" in result.output
    assert not (tmp_path / "doc" / "audits" / "cases").exists()


@pytest.mark.parametrize("configuration", ["- not-a-mapping\n", "42\n"])
def test_ingest_cli_refuses_non_mapping_graph_configuration(
    tmp_path,
    monkeypatch,
    configuration,
):
    _patch_registry(monkeypatch)
    (tmp_path / "science.yaml").write_text(configuration, encoding="utf-8")
    report = tmp_path / "report.json"
    report.write_text(json.dumps(_report_json()), encoding="utf-8")

    result = CliRunner().invoke(
        findings_group,
        [
            "ingest",
            str(report),
            "--project-root",
            str(tmp_path),
            *_attestation_args(),
        ],
    )

    assert result.exit_code == 2
    assert "mapping" in result.output
    assert not (tmp_path / "doc" / "audits" / "cases").exists()


def test_ingest_cli_wraps_commons_context_failures_as_zero_write_refusals(
    tmp_path,
    monkeypatch,
):
    from science_tool.commons.errors import CommonsError

    def fail_authority(_project_root):
        raise CommonsError("commons identity context unavailable")

    monkeypatch.setattr(findings_cli, "ingestion_authority", fail_authority)
    report = tmp_path / "report.json"
    report.write_text(json.dumps(_report_json()), encoding="utf-8")

    result = CliRunner().invoke(
        findings_group,
        [
            "ingest",
            str(report),
            "--project-root",
            str(tmp_path),
            *_attestation_args(),
        ],
    )

    assert result.exit_code == 2
    assert "commons identity context unavailable" in result.output
    assert not (tmp_path / "doc" / "audits" / "cases").exists()


def test_list_on_a_project_with_no_cases_is_empty_and_exits_zero(tmp_path):
    result = CliRunner().invoke(findings_group, ["list", "--project-root", str(tmp_path), "--format", "json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == []


@pytest.mark.parametrize("name", ["notes.md", ".hidden.md"])
def test_list_refuses_every_markdown_leaf_that_is_not_a_bound_case(tmp_path, name):
    cases = tmp_path / "doc" / "audits" / "cases"
    cases.mkdir(parents=True)
    (cases / name).write_text("not a case", encoding="utf-8")

    result = CliRunner().invoke(findings_group, ["list", "--project-root", str(tmp_path)])

    assert result.exit_code == 2
    assert name in result.output


def test_an_unknown_status_is_rejected_rather_than_matching_nothing(tmp_path):
    result = CliRunner().invoke(
        findings_group,
        ["list", "--project-root", str(tmp_path), "--status", "confirmd"],
    )
    assert result.exit_code == 2
    assert "confirmd" in result.output


def test_the_offered_statuses_are_the_models_statuses(tmp_path):
    from science_model.audit import CASE_STATUSES

    result = CliRunner().invoke(findings_group, ["list", "--help"])
    assert result.exit_code == 0
    for status in CASE_STATUSES:
        assert status in result.output
    assert set(CASE_STATUSES) == {"proposed", "confirmed", "dismissed", "promoted"}


def _legacy_config() -> str:
    return """# top-level comment
name: \"quoted project\"
profile: research
health:
  before: \"keep quoted\"
  accepted_validation:
    # old acceptance comment
    - rule: manifest.check
      severity: warning
      path: science.yaml
      task: task:one
      message_contains:
        - missing profile
      reason: reviewed
  after: "keep after"
unrelated:
  quoted: "still quoted"
"""


def _entry(finding_id: str, *, accepted_on: str | None = None) -> AcceptedValidationEntry:
    raw = {
        "finding_id": finding_id,
        "fingerprint_version": 1,
        "severity_scope": ["warn"],
        "reason": "reviewed",
    }
    if accepted_on is not None:
        raw["accepted_on"] = accepted_on
    return AcceptedValidationEntry.model_validate(raw)


def _migration(*rows: EntryMigration) -> AcceptanceMigration:
    return AcceptanceMigration(entries=rows, indeterminate_producers=())


def _migrated_result(_project_root):
    return _migration(EntryMigration(0, "migrated", _entry("a" * 64), "matched exactly one current finding"))


def test_migrate_acceptances_is_dry_run_by_default(tmp_path, monkeypatch):
    original = _legacy_config()
    path = tmp_path / "science.yaml"
    path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(findings_cli, "run_acceptance_migration", _migrated_result, raising=False)

    result = CliRunner().invoke(
        findings_group,
        ["migrate-acceptances", "--project-root", str(tmp_path), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["can_apply"] is True
    assert payload["applied"] is False
    assert path.read_text(encoding="utf-8") == original


@pytest.mark.parametrize("verdict", ["invalid", "stale", "ambiguous", "duplicate", "indeterminate"])
def test_migrate_acceptances_refuses_every_blocking_verdict_without_writing(tmp_path, monkeypatch, verdict):
    original = _legacy_config()
    path = tmp_path / "science.yaml"
    path.write_text(original, encoding="utf-8")
    classifier_error = classify_acceptance_entry("scalar").error

    def blocking_result(_project_root):
        return _migration(
            EntryMigration(0, verdict, None, classifier_error if verdict == "invalid" else f"{verdict} detail"),
            EntryMigration(1, "stale", None, "second problem"),
        )

    monkeypatch.setattr(findings_cli, "run_acceptance_migration", blocking_result, raising=False)
    result = CliRunner().invoke(
        findings_group,
        ["migrate-acceptances", "--project-root", str(tmp_path), "--format", "json"],
    )

    assert result.exit_code == 2, result.output
    payload = json.loads(result.output)
    assert [entry["verdict"] for entry in payload["entries"]] == [verdict, "stale"]
    assert payload["entries"][0]["detail"] == (classifier_error if verdict == "invalid" else f"{verdict} detail")
    assert path.read_text(encoding="utf-8") == original
    if verdict == "invalid":
        table_result = CliRunner().invoke(
            findings_group,
            ["migrate-acceptances", "--project-root", str(tmp_path)],
        )
        assert table_result.exit_code == 2
        assert classifier_error in table_result.output


def test_migrate_acceptances_apply_skips_all_current_entries(tmp_path, monkeypatch):
    original = _legacy_config()
    path = tmp_path / "science.yaml"
    path.write_text(original, encoding="utf-8")

    def current_result(_project_root):
        return _migration(
            EntryMigration(0, "already-current", _entry("a" * 64, accepted_on="2026-07-01"), "entry is already current")
        )

    monkeypatch.setattr(findings_cli, "run_acceptance_migration", current_result, raising=False)
    result = CliRunner().invoke(
        findings_group,
        ["migrate-acceptances", "--project-root", str(tmp_path), "--apply", "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["applied"] is False
    assert path.read_text(encoding="utf-8") == original


def test_migrate_acceptances_apply_round_trips_only_acceptance_entries(tmp_path, monkeypatch):
    original = _legacy_config()
    path = tmp_path / "science.yaml"
    path.write_text(original, encoding="utf-8")

    def mixed_result(_project_root):
        return _migration(
            EntryMigration(
                0, "already-current", _entry("c" * 64, accepted_on="2026-07-01"), "entry is already current"
            ),
            EntryMigration(1, "migrated", _entry("a" * 64), "matched exactly one current finding"),
        )

    writes: list[tuple[object, str]] = []

    def record_atomic_write(path, text):
        writes.append((path, text))
        path.write_text(text, encoding="utf-8")

    monkeypatch.setattr(findings_cli, "run_acceptance_migration", mixed_result, raising=False)
    monkeypatch.setattr(findings_cli, "atomic_write_text", record_atomic_write, raising=False)
    result = CliRunner().invoke(
        findings_group,
        ["migrate-acceptances", "--project-root", str(tmp_path), "--apply", "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["applied"] is True
    assert len(writes) == 1
    rewritten = path.read_text(encoding="utf-8")
    assert "# top-level comment" in rewritten
    assert 'name: "quoted project"' in rewritten
    assert 'before: "keep quoted"' in rewritten
    assert 'after: "keep after"' in rewritten
    assert 'quoted: "still quoted"' in rewritten
    assert rewritten.index("before:") < rewritten.index("accepted_validation:") < rewritten.index("after:")
    assert "rule:" not in rewritten
    assert "severity:" not in rewritten
    assert "path:" not in rewritten
    assert "task:" not in rewritten
    assert "message_contains:" not in rewritten
    assert "finding_id: " + "a" * 64 in rewritten
    assert "fingerprint_version: 1" in rewritten
    assert "severity_scope:\n        - warn" in rewritten
    assert "reason: reviewed" in rewritten
    assert "accepted_on:" in rewritten
    assert "2026-07-01" in rewritten
    assert rewritten.count("accepted_on:") == 1


def test_migrate_acceptances_apply_refuses_a_concurrent_config_edit(tmp_path, monkeypatch):
    original = _legacy_config()
    path = tmp_path / "science.yaml"
    path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(findings_cli, "run_acceptance_migration", _migrated_result, raising=False)

    real_apply = findings_cli.apply_migrated_config

    def mutate_before_write(_project_root, *, expected_original, rendered):
        path.write_text(expected_original + "# concurrent edit\n", encoding="utf-8")
        real_apply(
            tmp_path,
            expected_original=expected_original,
            rendered=rendered,
        )

    monkeypatch.setattr(findings_cli, "apply_migrated_config", mutate_before_write, raising=False)
    result = CliRunner().invoke(
        findings_group,
        ["migrate-acceptances", "--project-root", str(tmp_path), "--apply", "--format", "json"],
    )

    assert result.exit_code == 2, result.output
    assert "changed after migration classification" in json.loads(result.output)["error"]
    assert path.read_text(encoding="utf-8") == original + "# concurrent edit\n"


def test_migrate_acceptances_apply_refuses_a_config_edit_during_classification(tmp_path, monkeypatch):
    original = _legacy_config()
    path = tmp_path / "science.yaml"
    path.write_text(original, encoding="utf-8")

    def mutate_during_classification(_project_root):
        path.write_text(original + "# concurrent edit\n", encoding="utf-8")
        return _migrated_result(tmp_path)

    monkeypatch.setattr(
        findings_cli,
        "run_acceptance_migration",
        mutate_during_classification,
        raising=False,
    )
    result = CliRunner().invoke(
        findings_group,
        ["migrate-acceptances", "--project-root", str(tmp_path), "--apply", "--format", "json"],
    )

    assert result.exit_code == 2, result.output
    assert "changed after migration classification" in json.loads(result.output)["error"]
    assert path.read_text(encoding="utf-8") == original + "# concurrent edit\n"


@pytest.mark.parametrize(
    ("root_exists", "config_text", "error_fragment"),
    [
        (False, None, "No such file"),
        (True, None, "No such file"),
        (True, "health:\n  accepted_validation: scalar\n", "must be a list"),
        (True, "health: [\n", "expected the node content"),
    ],
)
def test_migrate_acceptances_refuses_missing_or_invalid_required_config(
    tmp_path,
    root_exists,
    config_text,
    error_fragment,
):
    project_root = tmp_path / "project"
    if root_exists:
        project_root.mkdir()
    if config_text is not None:
        (project_root / "science.yaml").write_text(config_text, encoding="utf-8")

    result = CliRunner().invoke(
        findings_group,
        ["migrate-acceptances", "--project-root", str(project_root), "--format", "json"],
    )

    assert result.exit_code == 2, result.output
    payload = json.loads(result.output)
    assert payload["can_apply"] is False
    assert error_fragment in payload["error"]


@pytest.mark.parametrize(
    "config_text",
    [
        "name: no-health\n",
        "health:\n  other_setting: true\n",
    ],
)
def test_migrate_acceptances_treats_absent_optional_acceptance_containers_as_empty(
    tmp_path,
    config_text,
):
    path = tmp_path / "science.yaml"
    path.write_text(config_text, encoding="utf-8")

    result = CliRunner().invoke(
        findings_group,
        ["migrate-acceptances", "--project-root", str(tmp_path), "--apply", "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "applied": False,
        "can_apply": True,
        "needs_write": False,
        "indeterminate_producers": [],
        "entries": [],
    }
    assert path.read_text(encoding="utf-8") == config_text
