"""Preconditions for the ``graph/health.py`` instruments (silent-instrument ruling).

Every helper here used to answer ``[]`` when it could not scan its input, and
``science health`` rendered that as a clean bill of health. These tests pin the
distinction the ``InstrumentResult`` type exists to force:

- ``unwired`` — the check COULD NOT RUN. Its rows are meaningless.
- ``empty``   — the check RAN and genuinely found nothing.

The second half of the file is the mirror image, and matters just as much: a
spurious ``unwired`` is as dishonest as a spurious ``empty``, so the two helpers
that have NO precondition are pinned to ``empty`` on a clean project.
"""

from __future__ import annotations

from pathlib import Path

from science_tool.graph.health import build_health_report
from science_tool.graph.health_checks.agent_context import collect_agent_context_findings
from science_tool.graph.health_checks.dataset_anomalies import check_dataset_anomalies
from science_tool.graph.health_checks.identity_policy import collect_identity_policy_findings
from science_tool.graph.health_checks.invalid_entity_aspects import collect_invalid_entity_aspects
from science_tool.graph.health_checks.legacy_task_type import collect_legacy_task_type
from science_tool.graph.health_checks.lingering_tags import collect_lingering_tags
from science_tool.graph.health_checks.tooling_scaffold import collect_tooling_scaffold_findings
from science_tool.graph.health_checks.unregistered_ref_kinds import collect_unregistered_ref_kinds
from science_tool.graph.health_checks.unresolved_refs import collect_unresolved_refs
from science_tool.graph.health_checks.validate import collect_validation_findings


def _seed_manifest(root: Path) -> None:
    (root / "science.yaml").write_text("name: test\n", encoding="utf-8")


def _seed_entity(root: Path) -> None:
    path = root / "entities" / "hypotheses" / "h01.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '---\nid: "hypothesis:h01"\nkind: "hypothesis"\ntitle: "H1"\n'
        'status: "proposed"\nrelated: []\nsource_refs: []\ncreated: "2026-04-13"\n---\nBody.\n',
        encoding="utf-8",
    )


def _scaffold_valid_project(root: Path) -> None:
    """A project every health check can actually run against, and that validates clean."""
    from science_tool.curate.agents_md import BEGIN_MARKER, END_MARKER

    (root / "science.yaml").write_text(
        "name: test\nprofile: research\nlayout_version: 3\nstatus: active\n"
        "summary: A test project.\ncreated: 2026-04-13\nlast_modified: 2026-04-13\n"
        "knowledge_profiles:\n  local: local\n",
        encoding="utf-8",
    )
    for name in ("doc", "knowledge", "tasks", "code", "papers", "data", "models", "results"):
        (root / name).mkdir()
    (root / "entities" / "datasets").mkdir(parents=True)
    (root / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    (root / "AGENTS.md").write_text(f"# Agents\n\n{BEGIN_MARKER}\n{END_MARKER}\n", encoding="utf-8")
    (root / "README.md").write_text("# Test\n", encoding="utf-8")
    (root / "tasks" / "active.md").write_text("# Active tasks\n", encoding="utf-8")
    (root / "entities" / "research-question.md").write_text(
        '---\nid: "question:rq"\nkind: "question"\ntitle: "RQ"\nstatus: "open"\n'
        'created: "2026-04-13"\nupdated: "2026-04-13"\n---\nWhat?\n',
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        '[project]\nname = "t"\nversion = "0.0"\n[dependency-groups]\ndev = ["science"]\n',
        encoding="utf-8",
    )
    (root / ".env").write_text("SCIENCE_TOOL_PATH=/dev/null\n", encoding="utf-8")


# --------------------------------------------------------------------------
# unwired: the check could not run
# --------------------------------------------------------------------------


def test_unresolved_refs_unwired_when_no_entities_loaded(tmp_path: Path) -> None:
    """`load_project_sources` does not raise on an unscannable project — it returns
    zero entities. Auditing zero entities finds zero dangling refs, which is not a
    fact about the project's references."""
    _seed_manifest(tmp_path)

    result = collect_unresolved_refs(tmp_path)

    assert result.status == "unwired"
    assert result.code == "project_sources_empty"


def test_unregistered_ref_kinds_unwired_when_no_entities_loaded(tmp_path: Path) -> None:
    _seed_manifest(tmp_path)

    result = collect_unregistered_ref_kinds(tmp_path)

    assert result.status == "unwired"
    assert result.code == "project_sources_empty"


def test_identity_policy_unwired_when_no_entities_loaded(tmp_path: Path) -> None:
    _seed_manifest(tmp_path)

    result = collect_identity_policy_findings(tmp_path)

    assert result.status == "unwired"
    assert result.code == "project_sources_empty"


def test_lingering_tags_unwired_when_no_scan_dir_exists(tmp_path: Path) -> None:
    """doc/, entities/ and tasks/ are each skipped when absent. All three absent means
    the scan visited no file at all."""
    _seed_manifest(tmp_path)

    result = collect_lingering_tags(tmp_path)

    assert result.status == "unwired"
    assert result.code == "scan_dirs_missing"


def test_lingering_tags_runs_when_only_one_scan_dir_exists(tmp_path: Path) -> None:
    _seed_manifest(tmp_path)
    _seed_entity(tmp_path)

    result = collect_lingering_tags(tmp_path)

    assert result.status == "empty"


def test_legacy_task_type_unwired_when_tasks_dir_missing(tmp_path: Path) -> None:
    _seed_manifest(tmp_path)

    result = collect_legacy_task_type(tmp_path)

    assert result.status == "unwired"
    assert result.code == "tasks_dir_missing"


def test_agent_context_unwired_when_no_context_file_exists(tmp_path: Path) -> None:
    _seed_manifest(tmp_path)

    result = collect_agent_context_findings(tmp_path)

    assert result.status == "unwired"
    assert result.code == "agent_context_files_absent"


def test_agent_context_runs_when_overview_exists(tmp_path: Path) -> None:
    _seed_manifest(tmp_path)
    overview = tmp_path / "core" / "overview.md"
    overview.parent.mkdir(parents=True)
    overview.write_text("# Overview\n\nShort.\n", encoding="utf-8")

    result = collect_agent_context_findings(tmp_path)

    assert result.status == "empty"


def test_invalid_entity_aspects_unwired_when_aspect_catalog_missing(tmp_path: Path) -> None:
    """`load_project_aspects` raises FileNotFoundError when science.yaml is absent. The
    catalog the check validates AGAINST failed to load — it cannot answer "no invalid
    aspects"."""
    (tmp_path / "entities").mkdir()

    result = collect_invalid_entity_aspects(tmp_path)

    assert result.status == "unwired"
    assert result.code == "aspect_catalog_missing"


def test_invalid_entity_aspects_unwired_when_entities_dir_missing(tmp_path: Path) -> None:
    _seed_manifest(tmp_path)

    result = collect_invalid_entity_aspects(tmp_path)

    assert result.status == "unwired"
    assert result.code == "entities_dir_missing"


def test_dataset_anomalies_empty_not_unwired_when_datasets_dir_missing(tmp_path: Path) -> None:
    """A missing entities/datasets/ is a TRUE zero, not a failure to run.

    entities/datasets/ is optional (commands/catalog-benchmarks.md: "if present"), so a
    project that catalogues no datasets genuinely has no dataset anomalies. Calling this
    `unwired` would print a COULD-NOT-RUN row on every uncatalogued project -- amplifying
    exactly the skip-warning spam fb-2026-07-10-021 complains about. A spurious unwired
    is as dishonest as a spurious empty.
    """
    _seed_manifest(tmp_path)

    result = check_dataset_anomalies(tmp_path)

    assert result.status == "empty"
    assert result.code == "no_datasets_dir"


def test_dataset_anomalies_empty_when_datasets_dir_is_empty(tmp_path: Path) -> None:
    _seed_manifest(tmp_path)
    (tmp_path / "entities" / "datasets").mkdir(parents=True)

    result = check_dataset_anomalies(tmp_path)

    assert result.status == "empty"


# --------------------------------------------------------------------------
# NO unwired state: these two ran, and their empty return is a true zero
# --------------------------------------------------------------------------


def test_tooling_scaffold_empty_on_a_scaffolded_project(tmp_path: Path) -> None:
    """The ABSENCE of pyproject.toml/.env IS this check's finding, so it can always run.
    A compliant scaffold is a TRUE zero, never unwired."""
    _seed_manifest(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "t"\nversion = "0.0"\n[dependency-groups]\ndev = ["science"]\n',
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text("SCIENCE_TOOL_PATH=/dev/null\n", encoding="utf-8")

    result = collect_tooling_scaffold_findings(tmp_path)

    assert result.status == "empty"


def test_tooling_scaffold_reports_the_bare_directory_as_findings(tmp_path: Path) -> None:
    result = collect_tooling_scaffold_findings(tmp_path)

    assert result.status == "ok"
    assert {row["code"] for row in result.rows} == {"pyproject_missing", "env_missing"}


def test_validation_context_error_is_a_finding_not_unwired(tmp_path: Path) -> None:
    """A ValidateContextError is already converted into an ERROR FINDING. That is a
    result, not a failure to check — it must not be laundered into `unwired`."""
    result = collect_validation_findings(tmp_path)

    assert result.status == "ok"
    assert [row["rule"] for row in result.rows] == ["validate.context"]


def test_validation_empty_on_a_project_with_nothing_to_flag(tmp_path: Path) -> None:
    _scaffold_valid_project(tmp_path)

    result = collect_validation_findings(tmp_path)

    assert result.status == "empty"


# --------------------------------------------------------------------------
# The report: an unwired check must not read as a clean bill of health
# --------------------------------------------------------------------------


def test_report_surfaces_unwired_checks_distinctly(tmp_path: Path) -> None:
    _seed_manifest(tmp_path)

    report = build_health_report(tmp_path, skip_checks={"validate"})

    unwired = {row["check"]: row["code"] for row in report["unwired_checks"]}
    assert unwired["unresolved_refs"] == "project_sources_empty"
    assert unwired["legacy_task_type"] == "tasks_dir_missing"
    # dataset_anomalies is NOT here: a missing entities/datasets/ is a true zero.
    assert "dataset_anomalies" not in unwired
    # ... and the rows of an unwired check are NOT presented as findings.
    assert report["unresolved_refs"] == []


def test_report_has_no_unwired_checks_when_every_check_can_run(tmp_path: Path) -> None:
    _scaffold_valid_project(tmp_path)

    report = build_health_report(tmp_path)

    assert report["unwired_checks"] == []


def test_health_renderer_refuses_to_call_an_unscannable_project_clean(tmp_path: Path) -> None:
    """The whole point. An empty project used to print "Project is clean" — the report
    of a sweep in which almost nothing ran."""
    from click.testing import CliRunner

    from science_tool.cli import main

    _seed_manifest(tmp_path)

    result = CliRunner().invoke(
        main,
        ["health", "--project-root", str(tmp_path), "--check", "unresolved_refs"],
    )

    assert result.exit_code == 0, result.output
    assert "Project is clean" not in result.output
    assert "COULD NOT RUN" in result.output


def test_health_json_output_carries_unwired_checks(tmp_path: Path) -> None:
    import json

    from click.testing import CliRunner

    from science_tool.cli import main

    _seed_manifest(tmp_path)

    result = CliRunner().invoke(
        main,
        ["health", "--project-root", str(tmp_path), "--format", "json", "--check", "legacy_task_type"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["unwired_checks"] == [
        {
            "check": "legacy_task_type",
            "code": "tasks_dir_missing",
            "reason": "tasks/ does not exist; no task file was read",
        }
    ]
    assert payload["total_issues"] == 0  # the check found nothing because it never ran
