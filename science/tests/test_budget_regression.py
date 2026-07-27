"""Actual emitted sizes for every wired command, in every supported format.

The boundary guards prove classification and wiring; this proves size.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import build_inquiry_graph
from science_model.tasks import Task

from science_tool import tasks as task_module
from science_tool.budget.measure import visible_len
from science_tool.budget.control import CONTROL_NOTICE_MAX_CHARS
from science_tool.budget.registry import BUDGETS
from science_tool.cli import main
from science_tool.graph.store import INITIAL_GRAPH_TEMPLATE, _graph_uri, _load_dataset, _resolve_term, _save_dataset

TASK_IDS = {f"t{i:03d}" for i in range(400)}
DATA_RECORD_PATHS = {
    f"data/stranded-record-with-a-long-name-{i:05d}.md" for i in range(3_000)
}


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "science.yaml").write_text("id: demo\nname: demo\n")
    active_dir = tmp_path / "tasks" / "active"
    active_dir.mkdir(parents=True)
    for i in range(400):
        task = Task(
            id=f"t{i:03d}",
            title=f"Task {i} with a deliberately long title to exercise wrapping behaviour",
            priority="P2",
            status="active" if i < 5 else "proposed",
            related=[
                "question:q0000-a-long-question-slug",
                "hypothesis:h0000-another-long-slug",
                # Preserve one task-specific validation finding per row so the
                # complete health-output assertions retain their original load.
                f"task:t{i:03d}.bad",
            ],
            created=date(2026, 1, 1),
            description=(
                f"Body paragraph for task {i}, long enough to matter multiplied "
                "by the backlog size."
            ),
        )
        (active_dir / f"{task.id}-task-{i}.md").write_text(
            task_module.render_task_file(task),
            encoding="utf-8",
        )
    entities = tmp_path / "entities" / "questions"
    entities.mkdir(parents=True)
    for i in range(300):
        entity_id = "question:q0000-a-long-question-slug" if i == 0 else f"question:q{i:04d}"
        (entities / f"{i:04d}-q.md").write_text(
            f"---\nid: {entity_id}\nkind: question\ntitle: Question {i}\n---\n\n" + ("body " * 300)
        )
    hypotheses = tmp_path / "entities" / "hypotheses"
    hypotheses.mkdir()
    (hypotheses / "0000-h.md").write_text(
        "---\nid: hypothesis:h0000-another-long-slug\nkind: hypothesis\n"
        "title: Referenced hypothesis\n---\n\n"
    )
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for i in range(3_000):
        (data_dir / f"stranded-record-with-a-long-name-{i:05d}.md").write_text("x")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _invoke(args: list[str]):
    return CliRunner().invoke(main, args, prog_name="science")


def _scope_project(args: list[str], project: Path) -> list[str]:
    """Make inventory tests independent of its import-time Path.cwd() default."""
    if args[:2] == ["entities", "inventory"]:
        return [*args, "--project-root", str(project)]
    return args


@pytest.mark.parametrize(
    ("command_path", "args"),
    [
        ("tasks list", ["tasks", "list"]),
        ("tasks list", ["tasks", "list", "--status", "proposed"]),
        ("tasks list", ["tasks", "list", "--status", "proposed", "--format", "json"]),
        ("health", ["health"]),
        ("health", ["health", "--format", "json"]),
        ("health", ["health", "--severity", "all"]),
        ("project index", ["project", "index"]),
        ("project index", ["project", "index", "--format", "json"]),
    ],
)
def test_command_stays_within_its_ceiling(project: Path, command_path: str, args: list[str]) -> None:
    result = _invoke(args)
    assert result.exit_code == 0, result.output
    ceiling = BUDGETS[command_path].max_chars
    assert visible_len(result.output) <= ceiling, f"{args} emitted {visible_len(result.output)} > {ceiling}"


@pytest.mark.parametrize(
    ("command_path", "args"),
    [
        ("entities inventory", ["entities", "inventory"]),
        ("data audit", ["data", "audit"]),
        ("data audit", ["data", "audit", "--format", "json"]),
    ],
)
def test_bulk_dump_refuses_rather_than_flooding(project: Path, command_path: str, args: list[str]) -> None:
    """DOCUMENT-shaped commands refuse; they never emit a partial payload."""
    result = _invoke(_scope_project(args, project))
    assert result.exit_code != 0
    assert "--output" in result.output
    assert visible_len(result.output) <= BUDGETS[command_path].max_chars


def _task_ids(text: str) -> set[str]:
    return set(re.findall(r"\bt\d{3}\b", text))


def _data_record_paths(text: str) -> set[str]:
    return set(re.findall(r"data/stranded-record-with-a-long-name-\d{5}\.md", text))


def test_tasks_json_output_file_is_complete(project: Path) -> None:
    target = project / "tasks.json"
    result = _invoke(["tasks", "list", "--all", "--format", "json", "--output", str(target)])
    assert result.exit_code == 0, result.output

    payload = json.loads(target.read_text())
    assert {row["id"] for row in payload["rows"]} == TASK_IDS
    assert len(payload["rows"]) == 400
    assert payload["meta"]["returned_count"] == 400
    assert payload["meta"]["active_total"] == 400
    assert "truncation" not in payload


def test_tasks_table_output_file_is_complete(project: Path) -> None:
    target = project / "tasks.txt"
    result = _invoke(["tasks", "list", "--all", "--output", str(target)])
    assert result.exit_code == 0, result.output

    written = target.read_text()
    assert _task_ids(written) == TASK_IDS
    assert "showing " not in written
    assert "complete output:" not in written


def test_health_json_output_file_is_complete_and_unprojected(project: Path) -> None:
    target = project / "health.json"
    result = _invoke(["health", "--format", "json", "--output", str(target)])
    assert result.exit_code == 0, result.output

    written = target.read_text()
    payload = json.loads(written)
    assert _task_ids(written) == TASK_IDS
    assert len(payload["validation"]) > 40
    assert payload["total_issues"] > 40
    assert "section_omitted" not in payload
    assert "displayed_issues" not in payload


def test_health_table_output_file_is_complete_and_unprojected(project: Path) -> None:
    target = project / "health.txt"
    result = _invoke(["health", "--output", str(target)])
    assert result.exit_code == 0, result.output

    written = target.read_text()
    assert _task_ids(written) == TASK_IDS
    assert "finding(s) hidden" not in written
    assert "showing " not in written


def test_inventory_output_file_contains_every_entity(project: Path) -> None:
    # The storage adapter's split-active support lands in Task 15. Exercise its
    # already-supported done-ledger path here without weakening the 400-task oracle.
    active_dir = project / "tasks" / "active"
    tasks = [task_module.parse_task_file(path) for path in sorted(active_dir.glob("*.md"))]
    for path in active_dir.glob("*.md"):
        path.unlink()
    done_dir = project / "tasks" / "done"
    done_dir.mkdir()
    done_tasks = [
        task.model_copy(update={"status": "done", "completed": date(2026, 1, 2)})
        for task in tasks
    ]
    (done_dir / "2026-01.md").write_text(
        task_module.render_tasks(done_tasks),
        encoding="utf-8",
    )

    target = project / "inventory.json"
    result = _invoke(
        [
            "entities",
            "inventory",
            "--project-root",
            str(project),
            "--output",
            str(target),
        ]
    )
    assert result.exit_code == 0, result.output

    payload = json.loads(target.read_text())
    assert payload["schema_version"] == "2"
    assert len(payload["entities"]) == 701
    assert sum(entity["kind"] == "question" for entity in payload["entities"]) == 300
    assert sum(entity["kind"] == "task" for entity in payload["entities"]) == 400
    assert sum(entity["kind"] == "hypothesis" for entity in payload["entities"]) == 1


def test_data_audit_text_output_file_contains_every_record(project: Path) -> None:
    target = project / "audit.txt"
    result = _invoke(["data", "audit", "--output", str(target)])
    assert result.exit_code == 1, result.output

    written = target.read_text()
    assert _data_record_paths(written) == DATA_RECORD_PATHS
    assert written.count("data/stranded-record-with-a-long-name-") == 3_000


def test_data_audit_json_output_file_contains_every_record(project: Path) -> None:
    target = project / "audit.json"
    result = _invoke(["data", "audit", "--format", "json", "--output", str(target)])
    assert result.exit_code == 1, result.output

    payload = json.loads(target.read_text())
    data_paths = [
        row["path"]
        for row in payload["violations"]
        if row["path"].startswith("data/stranded-record-with-a-long-name-")
    ]
    assert payload["version"] == 1
    assert len(data_paths) == 3_000
    assert set(data_paths) == DATA_RECORD_PATHS


@pytest.mark.parametrize(
    ("args", "target_name"),
    [
        (["tasks", "list", "--status", "proposed", "--format", "json"], "tasks.json"),
        (["tasks", "list", "--status", "proposed"], "tasks.txt"),
        (["health", "--format", "json"], "health.json"),
        (["health"], "health.txt"),
        (["entities", "inventory"], "inventory.json"),
        (["data", "audit"], "audit.txt"),
        (["data", "audit", "--format", "json"], "audit.json"),
    ],
)
def test_no_success_message_when_the_command_fails(
    project: Path, args: list[str], target_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The sole payload-sink bypass must follow a successful flush, not sit in `finally`."""
    from science_tool.budget import sink as sink_module

    def _boom(self: object) -> None:
        raise RuntimeError("render failed")

    monkeypatch.setattr(sink_module.BoundedSink, "flush", _boom)
    result = _invoke([*_scope_project(args, project), "--output", str(project / target_name)])
    assert result.exit_code != 0
    assert "wrote" not in result.output


def test_tasks_list_json_reports_the_full_total(project: Path) -> None:
    result = _invoke(["tasks", "list", "--status", "proposed", "--format", "json"])
    assert json.loads(result.output)["truncation"]["total"] == 395


def test_escape_hint_extension_tracks_the_output_format(project: Path) -> None:
    """The truncation footer must name a file whose extension matches what was truncated:
    a default text/table run gets a .txt escape, a --format json run gets a .json escape.
    A .json name over a rendered table is exactly the mismatch this guards against."""
    text = _invoke(["tasks", "list", "--all"])
    assert "--output tasks.txt" in text.output
    assert "tasks.json" not in text.output

    js = _invoke(["tasks", "list", "--all", "--format", "json"])
    assert json.loads(js.output)["truncation"]["complete_via"].endswith("--output tasks.json")


@pytest.mark.parametrize(
    ("args", "target_name"),
    [
        (["tasks", "list", "--all"], "task report with spaces.txt"),
        (["health"], "health report with spaces.txt"),
        (["entities", "inventory"], "inventory report with spaces.json"),
        (["data", "audit"], "audit report with spaces.txt"),
    ],
)
def test_file_success_control_notices_are_single_line_and_bounded(
    project: Path,
    args: list[str],
    target_name: str,
) -> None:
    target = project / target_name
    result = _invoke([*_scope_project(args, project), "--output", str(target)])
    assert result.exit_code in {0, 1}, result.output
    assert result.output.count("\n") == 1
    assert visible_len(result.output.rstrip("\n")) <= CONTROL_NOTICE_MAX_CHARS


@pytest.fixture
def graph_audit_overflow_project(tmp_path: Path) -> Path:
    """50 questions, each with one unresolved `related` target -> 50 audit fail rows.

    `graph audit` runs the audit-only compiler phase (`materialization_audit` ->
    `_compile(stop_after="audit")`), which never gates on failures, so an entity's
    markdown alone (no `graph.trig`) is enough to exercise it -- unlike commands
    that read a materialized graph.
    """
    from _fixtures.entity_helpers import seed_project, write_markdown_entity

    seed_project(tmp_path)
    for i in range(50):
        write_markdown_entity(
            tmp_path,
            f"entities/questions/q{i:03d}.md",
            {
                "id": f"question:q{i:03d}",
                "kind": "question",
                "title": f"Question {i}",
                "related": [f"hypothesis:missing-{i:03d}"],
            },
        )
    return tmp_path


def test_graph_audit_stdout_stays_within_its_ceiling(graph_audit_overflow_project: Path) -> None:
    result = _invoke(["graph", "audit", "--project-root", str(graph_audit_overflow_project)])
    assert result.exit_code == 1, result.output  # exit code from the FULL (unprojected) verdict
    ceiling = BUDGETS["graph audit"].max_chars
    assert visible_len(result.output) <= ceiling


def test_graph_audit_output_file_is_complete_and_stdout_is_a_control_notice(
    graph_audit_overflow_project: Path,
) -> None:
    target = graph_audit_overflow_project / "audit.json"
    result = _invoke(
        [
            "graph",
            "audit",
            "--project-root",
            str(graph_audit_overflow_project),
            "--format",
            "json",
            "--output",
            str(target),
        ]
    )
    assert result.exit_code == 1, result.output  # exit code from the FULL verdict, even on the file-sink path
    assert result.output.count("\n") == 1
    assert "wrote 50 rows to" in result.output

    payload = json.loads(target.read_text())
    assert len(payload["rows"]) == 50
    assert {row["check"] for row in payload["rows"]} == {"unresolved_reference"}
    assert "truncation" not in payload


def test_project_index_output_file_is_complete_and_stdout_is_a_control_notice(project: Path) -> None:
    target = project / "index.json"
    result = _invoke(["project", "index", "--format", "json", "--output", str(target)])
    assert result.exit_code == 0, result.output
    assert result.output.count("\n") == 1
    assert "wrote 301 rows to" in result.output

    payload = json.loads(target.read_text())
    assert len(payload["rows"]) == 301
    assert sum(row["kind"] == "question" for row in payload["rows"]) == 300
    assert sum(row["kind"] == "hypothesis" for row in payload["rows"]) == 1


@pytest.fixture
def tasks_blockers_overflow_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """One task blocked by 50 refs to nonexistent entities -> 50 unresolved blocker rows.

    An unresolved ref costs one cheap dict lookup (`ReadinessResolver.resolve_ref`), so
    this needs no entity fixtures at all.
    """
    (tmp_path / "science.yaml").write_text("id: demo\nname: demo\n")
    active_dir = tmp_path / "tasks" / "active"
    active_dir.mkdir(parents=True)
    task = Task(
        id="t001",
        title="Task blocked by many unresolved refs",
        priority="P2",
        status="blocked",
        blocked_by=[f"dataset:missing-{i:03d}" for i in range(50)],
        created=date(2026, 1, 1),
        description="Body.",
    )
    (active_dir / "t001-task-blocked-by-many-unresolved-refs.md").write_text(
        task_module.render_task_file(task),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_tasks_blockers_stdout_stays_within_its_ceiling_and_reports_truncation(
    tasks_blockers_overflow_project: Path,
) -> None:
    result = _invoke(["tasks", "blockers", "t001"])
    assert result.exit_code == 0, result.output
    ceiling = BUDGETS["tasks blockers"].max_chars
    assert visible_len(result.output) <= ceiling
    assert "showing 40 of 50 blockers" in result.output
    assert "complete output:" in result.output

    js = _invoke(["tasks", "blockers", "t001", "--format", "json"])
    payload = json.loads(js.output)
    assert len(payload["blockers"]) == 40
    assert payload["truncation"]["total"] == 50
    assert payload["truncation"]["omitted"] == 10


def test_tasks_blockers_output_file_is_complete(tasks_blockers_overflow_project: Path) -> None:
    target = tasks_blockers_overflow_project / "blockers.json"
    result = _invoke(["tasks", "blockers", "t001", "--format", "json", "--output", str(target)])
    assert result.exit_code == 0, result.output
    assert result.output.count("\n") == 1
    assert "wrote 50 blockers to" in result.output

    payload = json.loads(target.read_text())
    assert len(payload["blockers"]) == 50
    assert {row["ref"] for row in payload["blockers"]} == {f"dataset:missing-{i:03d}" for i in range(50)}
    assert "truncation" not in payload


@pytest.fixture
def skills_lint_overflow_root(tmp_path: Path) -> Path:
    """50 skill leaves with no frontmatter block -> well over 40 lint issues.

    Each file trips `missing-frontmatter` plus follow-on checks (companion skills,
    halt-on, provenance) that all key off the same absent frontmatter block.
    """
    root = tmp_path / "skills"
    root.mkdir()
    for i in range(50):
        (root / f"leaf{i:03d}.md").write_text("no frontmatter here\n")
    return root


def test_skills_lint_stdout_stays_within_its_ceiling_and_reports_truncation(
    skills_lint_overflow_root: Path,
) -> None:
    result = _invoke(["skills", "lint", "--root", str(skills_lint_overflow_root)])
    assert result.exit_code == 1, result.output  # exit code from the FULL issue list
    ceiling = BUDGETS["skills lint"].max_chars
    assert visible_len(result.output) <= ceiling
    assert "showing 40 of" in result.output
    assert "complete output:" in result.output

    js = _invoke(["skills", "lint", "--root", str(skills_lint_overflow_root), "--format", "json"])
    payload = json.loads(js.output)
    assert len(payload["issues"]) == 40
    assert payload["truncation"]["total"] > 40


def test_skills_lint_output_file_is_complete(skills_lint_overflow_root: Path, tmp_path: Path) -> None:
    target = tmp_path / "lint.json"
    result = _invoke(
        ["skills", "lint", "--root", str(skills_lint_overflow_root), "--format", "json", "--output", str(target)]
    )
    assert result.exit_code == 1, result.output  # exit code from the FULL issue list, even on the file-sink path
    assert result.output.count("\n") == 1
    assert "wrote " in result.output and " issues to" in result.output

    payload = json.loads(target.read_text())
    assert len(payload["issues"]) > 40
    assert "truncation" not in payload


@pytest.fixture
def annotate_list_overflow_root(tmp_path: Path) -> Path:
    """50 open annotations in one sidecar -> 50 growable list rows."""
    from datetime import datetime, timezone

    from science_tool.annotation.io import write_sidecar
    from science_tool.annotation.model import (
        Annotation,
        Motivation,
        Sidecar,
        SpecificResource,
        Status,
        TextQuoteSelector,
        TextualBody,
    )

    anns = tuple(
        Annotation(
            id=f"a-{i:03d}",
            target=SpecificResource(
                source="x.md",
                selector=TextQuoteSelector(exact="A short sample sentence.", prefix="Before. ", suffix=" After."),
            ),
            bodies=(TextualBody(value="m"),),
            motivation=Motivation.CLASSIFYING,
            annotation_type="bare-author-year",
            source="lint:foo-v1",
            status=Status.OPEN,
            creator="t",
            created=datetime(2026, 5, 11, tzinfo=timezone.utc),
            content_hash="sha256:d",
            match_text="m",
        )
        for i in range(50)
    )
    write_sidecar(tmp_path / "a.anno.trig", Sidecar(annotations=anns))
    return tmp_path


def test_annotate_list_stdout_stays_within_its_ceiling_and_reports_truncation(
    annotate_list_overflow_root: Path,
) -> None:
    result = _invoke(["annotate", "list", "--root", str(annotate_list_overflow_root)])
    assert result.exit_code == 0, result.output
    ceiling = BUDGETS["annotate list"].max_chars
    assert visible_len(result.output) <= ceiling
    assert "showing 40 of 50 annotation(s)" in result.output
    assert "complete output:" in result.output

    js = _invoke(["annotate", "list", "--root", str(annotate_list_overflow_root), "--format", "json"])
    payload = json.loads(js.output)
    assert len(payload["annotations"]) == 40
    assert payload["summary"]["total_annotations"] == 50
    assert payload["truncation"]["total"] == 50
    assert payload["truncation"]["omitted"] == 10


def test_annotate_list_output_file_is_complete(annotate_list_overflow_root: Path) -> None:
    target = annotate_list_overflow_root / "annotations.json"
    result = _invoke(
        [
            "annotate",
            "list",
            "--root",
            str(annotate_list_overflow_root),
            "--format",
            "json",
            "--output",
            str(target),
        ]
    )
    assert result.exit_code == 0, result.output
    assert result.output.count("\n") == 1
    assert "wrote 50 annotation(s) to" in result.output

    payload = json.loads(target.read_text())
    assert len(payload["annotations"]) == 50
    assert {row["id"] for row in payload["annotations"]} == {f"a-{i:03d}" for i in range(50)}
    assert "truncation" not in payload


@pytest.fixture
def sync_projects_overflow_config(tmp_path: Path) -> Path:
    """50 registered projects -> 50 growable list rows.

    `ensure_registered` resolves the project path but never requires it to exist,
    so this needs no per-project directory fixtures.
    """
    from science_tool.registry.config import ensure_registered

    config_path = tmp_path / "config.yaml"
    for i in range(50):
        ensure_registered(tmp_path / f"proj-{i:03d}", f"proj-{i:03d}", config_path)
    return config_path


def test_sync_projects_stdout_stays_within_its_ceiling_and_reports_truncation(
    sync_projects_overflow_config: Path,
) -> None:
    result = _invoke(["sync", "projects", "--config", str(sync_projects_overflow_config)])
    assert result.exit_code == 0, result.output
    ceiling = BUDGETS["sync projects"].max_chars
    assert visible_len(result.output) <= ceiling
    assert "showing 40 of 50 project(s)" in result.output
    assert "complete output:" in result.output

    js = _invoke(["sync", "projects", "--config", str(sync_projects_overflow_config), "--format", "json"])
    payload = json.loads(js.output)
    assert len(payload["projects"]) == 40
    assert payload["truncation"]["total"] == 50


def test_sync_projects_output_file_is_complete(sync_projects_overflow_config: Path, tmp_path: Path) -> None:
    target = tmp_path / "projects.json"
    result = _invoke(
        [
            "sync",
            "projects",
            "--config",
            str(sync_projects_overflow_config),
            "--format",
            "json",
            "--output",
            str(target),
        ]
    )
    assert result.exit_code == 0, result.output
    assert result.output.count("\n") == 1
    assert "wrote 50 projects to" in result.output

    payload = json.loads(target.read_text())
    assert len(payload["projects"]) == 50
    assert {row["name"] for row in payload["projects"]} == {f"proj-{i:03d}" for i in range(50)}
    assert "truncation" not in payload


@pytest.fixture
def big_picture_validate_overflow_project(tmp_path: Path) -> Path:
    """One known entity + 50 synthesis files, each with one dangling reference.

    `validate_synthesis_file` refuses (unwired) when the project has no known IDs at
    all -- one real question entity keeps reference validation wired while the 50
    synthesis files each cite a distinct, never-registered interpretation.
    """
    (tmp_path / "entities" / "questions").mkdir(parents=True)
    (tmp_path / "entities" / "questions" / "q1.md").write_text(
        '---\nid: "question:q1"\nkind: "question"\ntitle: "Q1"\n---\n\nBody.\n', encoding="utf-8"
    )
    synth_dir = tmp_path / "entities" / "synthesis"
    synth_dir.mkdir(parents=True)
    for i in range(50):
        (synth_dir / f"{i:03d}.md").write_text(
            f'---\nid: "synthesis:{i:03d}"\n---\n\nSee interpretation:i{i:03d}-fake for details.\n',
            encoding="utf-8",
        )
    return tmp_path


def test_big_picture_validate_stdout_stays_within_its_ceiling_and_reports_truncation(
    big_picture_validate_overflow_project: Path,
) -> None:
    result = _invoke(["big-picture", "validate", "--project-root", str(big_picture_validate_overflow_project)])
    assert result.exit_code == 1, result.output  # exit code from the FULL issue list
    ceiling = BUDGETS["big-picture validate"].max_chars
    assert visible_len(result.output) <= ceiling
    assert "showing 40 of 50 issue(s)" in result.output
    assert "complete output:" in result.output

    js = _invoke(
        ["big-picture", "validate", "--project-root", str(big_picture_validate_overflow_project), "--format", "json"]
    )
    assert js.exit_code == 1, js.output
    payload = json.loads(js.output)
    assert len(payload["issues"]) == 40
    assert payload["truncation"]["total"] == 50


def test_big_picture_validate_output_file_is_complete(
    big_picture_validate_overflow_project: Path, tmp_path: Path
) -> None:
    target = tmp_path / "validate.json"
    result = _invoke(
        [
            "big-picture",
            "validate",
            "--project-root",
            str(big_picture_validate_overflow_project),
            "--format",
            "json",
            "--output",
            str(target),
        ]
    )
    assert result.exit_code == 1, result.output  # exit code from the FULL issue list, even on the file-sink path
    assert result.output.count("\n") == 1
    assert "wrote the complete validation report to" in result.output

    payload = json.loads(target.read_text())
    assert len(payload["issues"]) == 50
    assert "truncation" not in payload


@pytest.fixture
def research_package_build_overflow_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """A workflow config + 50 cells each citing a distinct unknown resource.

    `validate_package`'s cell loop yields one error per bad cell, scaling with the
    package's own cells.json rather than any pre-existing corpus. `cells_file`
    resolves relative to CWD, so this chdirs into tmp_path.
    """
    (tmp_path / "results").mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text("title: Test\nworkflow_name: wf\n", encoding="utf-8")
    cells = [{"type": "data-table", "resource": f"missing-{i:03d}"} for i in range(50)]
    (tmp_path / "cells.json").write_text(json.dumps(cells), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path, config_path


def test_research_package_build_stdout_stays_within_its_ceiling_and_reports_truncation(
    research_package_build_overflow_config: tuple[Path, Path],
) -> None:
    tmp_path, config_path = research_package_build_overflow_config
    result = _invoke(
        [
            "research-package",
            "build",
            "--results",
            str(tmp_path / "results"),
            "--config",
            str(config_path),
            "--output",
            str(tmp_path / "out1"),
        ]
    )
    assert result.exit_code == 1, result.output  # exit code from the FULL error list
    ceiling = BUDGETS["research-package build"].max_chars
    assert visible_len(result.output) <= ceiling
    assert "showing 40 of 50 error(s)" in result.output
    # The reconstructed escape must preserve the real, required package-directory
    # --output value, not the report-escape hint that collides with its flag name.
    assert f"--output {tmp_path / 'out1'}" in result.output
    assert "--report-output research-package-build.txt" in result.output

    js = _invoke(
        [
            "research-package",
            "build",
            "--results",
            str(tmp_path / "results"),
            "--config",
            str(config_path),
            "--output",
            str(tmp_path / "out2"),
            "--format",
            "json",
        ]
    )
    assert js.exit_code == 1, js.output
    payload = json.loads(js.output)
    assert len(payload["errors"]) == 40
    assert payload["truncation"]["total"] == 50


def test_research_package_build_report_output_file_is_complete(
    research_package_build_overflow_config: tuple[Path, Path],
) -> None:
    tmp_path, config_path = research_package_build_overflow_config
    target = tmp_path / "build-report.json"
    result = _invoke(
        [
            "research-package",
            "build",
            "--results",
            str(tmp_path / "results"),
            "--config",
            str(config_path),
            "--output",
            str(tmp_path / "out3"),
            "--format",
            "json",
            "--report-output",
            str(target),
        ]
    )
    assert result.exit_code == 1, result.output  # exit code from the FULL error list, even on the file-sink path
    assert result.output.count("\n") == 1
    assert "wrote the complete build report to" in result.output
    assert (tmp_path / "out3" / "datapackage.json").exists()  # the real --output build still ran

    payload = json.loads(target.read_text())
    assert len(payload["errors"]) == 50
    assert "truncation" not in payload


@pytest.fixture
def benchmark_list_overflow_project(tmp_path: Path) -> Path:
    """50 minimal benchmark-capable dataset entities -> 50 growable list rows."""
    datasets_dir = tmp_path / "entities" / "datasets"
    datasets_dir.mkdir(parents=True)
    for i in range(50):
        (datasets_dir / f"ds-{i:03d}.md").write_text(
            f"---\n"
            f"id: dataset:ds-{i:03d}\n"
            f"kind: dataset\n"
            f"title: Dataset {i}\n"
            f"dataset_class: deposit\n"
            f"benchmark:\n"
            f"  domains: [biology]\n"
            f"  benchmark_kinds: [classification]\n"
            f"  tasks:\n"
            f"    - id: task-{i:03d}\n"
            f"---\n\nbody\n",
            encoding="utf-8",
        )
    return tmp_path


def _invoke_benchmark_list(project_root: Path, *args: str):
    return CliRunner().invoke(
        main,
        ["benchmark", "list", *args],
        prog_name="science",
        env={"SCIENCE_PROJECT_ROOT": str(project_root), "SCIENCE_COMMONS_ROOT": str(project_root / "no-commons")},
    )


def test_benchmark_list_stdout_stays_within_its_ceiling_and_reports_truncation(
    benchmark_list_overflow_project: Path,
) -> None:
    result = _invoke_benchmark_list(benchmark_list_overflow_project)
    assert result.exit_code == 0, result.output
    ceiling = BUDGETS["benchmark list"].max_chars
    assert visible_len(result.output) <= ceiling
    assert "showing 40 of 50 rows" in result.output
    assert "complete output:" in result.output

    js = _invoke_benchmark_list(benchmark_list_overflow_project, "--format", "json")
    payload = json.loads(js.output)
    assert len(payload["rows"]) == 40
    assert payload["truncation"]["total"] == 50
    assert payload["truncation"]["omitted"] == 10
    assert payload["summary"]["dataset_class"]["deposit"] == 50  # the summary reflects the FULL rows


def test_benchmark_list_output_file_is_complete(benchmark_list_overflow_project: Path, tmp_path: Path) -> None:
    target = tmp_path / "benchmarks.json"
    result = _invoke_benchmark_list(benchmark_list_overflow_project, "--format", "json", "--output", str(target))
    assert result.exit_code == 0, result.output
    assert result.output.count("\n") == 1
    assert "wrote the complete benchmark list to" in result.output

    payload = json.loads(target.read_text())
    assert len(payload["rows"]) == 50
    assert {row["id"] for row in payload["rows"]} == {f"dataset:ds-{i:03d}" for i in range(50)}
    assert "truncation" not in payload


@pytest.fixture
def explore_ideas_gaps_overflow_project(tmp_path: Path) -> Path:
    """50 applied report blocks pointing at entities that were never created.

    Each unresolved `applied_as` becomes exactly one GapEntity carrying one
    `missing_entity` error gap -- 50 growable list rows without creating any entity file.
    """
    explorations = tmp_path / "doc" / "explorations"
    explorations.mkdir(parents=True)
    blocks = "\n".join(
        f"```yaml\ncandidate_id: cand-{i:03d}\ndecision: applied\napplied_as: question:missing-{i:03d}\n```\n"
        for i in range(50)
    )
    (explorations / "report.md").write_text(blocks, encoding="utf-8")
    return tmp_path


def _invoke_explore_ideas_gaps(*args: str):
    return CliRunner().invoke(main, ["explore-ideas", "gaps", *args], prog_name="science")


def test_explore_ideas_gaps_stdout_stays_within_its_ceiling_and_reports_truncation(
    explore_ideas_gaps_overflow_project: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(explore_ideas_gaps_overflow_project)
    result = _invoke_explore_ideas_gaps("--from", "report")
    assert result.exit_code == 0, result.output
    ceiling = BUDGETS["explore-ideas gaps"].max_chars
    assert visible_len(result.output) <= ceiling
    assert "showing 40 of 50 entities" in result.output
    assert "complete output:" in result.output

    js = _invoke_explore_ideas_gaps("--from", "report", "--format", "json")
    payload = json.loads(js.output)
    assert len(payload["entities"]) == 40
    assert payload["counts"]["entities"] == 50  # the summary reflects the FULL result
    assert payload["truncation"]["total"] == 50
    assert payload["truncation"]["omitted"] == 10


def test_explore_ideas_gaps_output_file_is_complete(
    explore_ideas_gaps_overflow_project: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(explore_ideas_gaps_overflow_project)
    target = explore_ideas_gaps_overflow_project / "gaps.json"
    result = _invoke_explore_ideas_gaps("--from", "report", "--format", "json", "--output", str(target))
    assert result.exit_code == 0, result.output
    assert result.output.count("\n") == 1
    assert "wrote the complete gap report to" in result.output

    payload = json.loads(target.read_text())
    assert len(payload["entities"]) == 50
    assert {entity["candidate_id"] for entity in payload["entities"]} == {f"cand-{i:03d}" for i in range(50)}
    assert "truncation" not in payload


@pytest.fixture
def dag_audit_overflow_project(tmp_path: Path) -> Path:
    """A 50-edge chain DAG with no compiled propositions -> 50 growable findings."""
    project = tmp_path / "project"
    dag_dir = project / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (project / "science.yaml").write_text("profile: research\n", encoding="utf-8")
    edges = "\n".join(f"  n{i} -> n{i + 1};" for i in range(50))
    (dag_dir / "h1.dot").write_text(f"digraph h1 {{\n{edges}\n}}\n", encoding="utf-8")
    (project / "tasks").mkdir()
    return project


def _invoke_dag_audit(project_root: Path, *args: str):
    return CliRunner().invoke(main, ["dag", "audit", "--project", str(project_root), *args], prog_name="science")


def test_dag_audit_stdout_stays_within_its_ceiling_and_reports_truncation(dag_audit_overflow_project: Path) -> None:
    result = _invoke_dag_audit(dag_audit_overflow_project)
    assert result.exit_code == 1, result.output
    ceiling = BUDGETS["dag audit"].max_chars
    assert visible_len(result.output) <= ceiling
    assert "showing 40 of 50 findings" in result.output
    assert "complete output:" in result.output

    js = _invoke_dag_audit(dag_audit_overflow_project, "--format", "json")
    payload = json.loads(js.output)
    assert len(payload["validation"]["findings"]) == 40
    assert payload["truncation"]["findings"]["total"] == 50
    assert payload["truncation"]["findings"]["omitted"] == 10
    assert "mutations" not in payload["truncation"]


def test_dag_audit_output_file_is_complete(dag_audit_overflow_project: Path, tmp_path: Path) -> None:
    target = tmp_path / "audit.json"
    result = _invoke_dag_audit(dag_audit_overflow_project, "--format", "json", "--output", str(target))
    assert result.exit_code == 1, result.output  # exit code from the FULL findings, even on the file-sink path
    assert result.output.count("\n") == 1
    assert "wrote the complete audit report to" in result.output

    payload = json.loads(target.read_text())
    assert len(payload["validation"]["findings"]) == 50
    assert "truncation" not in payload


@pytest.fixture
def peers_list_overflow_project(tmp_path: Path) -> Path:
    """50 declared peers pointing at nonexistent paths -> 50 growable list rows."""
    host = tmp_path / "host"
    host.mkdir()
    peers_yaml = "\n".join(f"  - id: peer-{i:03d}\n    path: ../missing-{i:03d}" for i in range(50))
    (host / "science.yaml").write_text(
        f'name: host\nid: host\nprofile: research\nresearch_question: "..."\npeers:\n{peers_yaml}\n',
        encoding="utf-8",
    )
    return host


def _invoke_peers_list(project_root: Path, *args: str):
    return CliRunner().invoke(
        main, ["peers", "list", "--project-root", str(project_root), *args], prog_name="science"
    )


def test_peers_list_stdout_stays_within_its_ceiling_and_reports_truncation(peers_list_overflow_project: Path) -> None:
    result = _invoke_peers_list(peers_list_overflow_project)
    assert result.exit_code == 0, result.output
    ceiling = BUDGETS["peers list"].max_chars
    assert visible_len(result.output) <= ceiling
    assert "showing 40 of 50 peers" in result.output
    assert "complete output:" in result.output

    js = _invoke_peers_list(peers_list_overflow_project, "--format", "json")
    payload = json.loads(js.output)
    assert len(payload["peers"]) == 40
    assert payload["truncation"]["total"] == 50
    assert payload["truncation"]["omitted"] == 10


def test_peers_list_output_file_is_complete(peers_list_overflow_project: Path, tmp_path: Path) -> None:
    target = tmp_path / "peers.json"
    result = _invoke_peers_list(peers_list_overflow_project, "--format", "json", "--output", str(target))
    assert result.exit_code == 0, result.output
    assert result.output.count("\n") == 1
    assert "wrote the complete peer list to" in result.output

    payload = json.loads(target.read_text())
    assert len(payload["peers"]) == 50
    assert "truncation" not in payload


@pytest.fixture
def sync_status_overflow_config(tmp_path: Path) -> Path:
    """50 recorded per-project sync states -> 50 growable `projects` list rows."""
    from datetime import datetime, timedelta

    from science_tool.registry.state import ProjectSyncState, SyncState, save_sync_state

    config_path = tmp_path / "config.yaml"
    config_path.write_text("sync:\n  stale_after_days: 7\n", encoding="utf-8")
    state = SyncState(
        last_sync=datetime.now() - timedelta(days=1),
        projects={
            f"proj-{i:03d}": ProjectSyncState(
                last_synced=datetime.now(),
                entity_count=i,
                entity_hash=f"{i:04d}" + "a" * 60,
            )
            for i in range(50)
        },
    )
    save_sync_state(state, tmp_path / "sync_state.yaml")
    return config_path


def test_sync_status_stdout_stays_within_its_ceiling_and_reports_truncation(
    sync_status_overflow_config: Path,
) -> None:
    result = _invoke(["sync", "status", "--config", str(sync_status_overflow_config)])
    assert result.exit_code == 0, result.output
    ceiling = BUDGETS["sync status"].max_chars
    assert visible_len(result.output) <= ceiling
    assert "showing 40 of 50 projects" in result.output
    assert "complete output:" in result.output

    js = _invoke(["sync", "status", "--config", str(sync_status_overflow_config), "--format", "json"])
    payload = json.loads(js.output)
    assert len(payload["projects"]) == 40
    assert payload["truncation"]["total"] == 50
    assert payload["truncation"]["omitted"] == 10


def test_sync_status_output_file_is_complete(sync_status_overflow_config: Path, tmp_path: Path) -> None:
    target = tmp_path / "status.json"
    result = _invoke(
        ["sync", "status", "--config", str(sync_status_overflow_config), "--format", "json", "--output", str(target)]
    )
    assert result.exit_code == 0, result.output
    assert result.output.count("\n") == 1
    assert "wrote the complete sync status to" in result.output

    payload = json.loads(target.read_text())
    assert len(payload["projects"]) == 50
    assert "truncation" not in payload


@pytest.fixture
def tasks_summary_overflow_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """45 active tasks, each in a distinct group -> 45 growable `by_group` members.

    Status and priority are held constant so only `by_group` overflows the 40-item cap,
    proving the bespoke projector caps each breakdown independently.
    """
    active_dir = tmp_path / "tasks" / "active"
    active_dir.mkdir(parents=True)
    for i in range(45):
        task = Task(
            id=f"t{i:03d}",
            title=f"Task {i}",
            priority="P2",
            status="proposed",
            group=f"group-{i:03d}",
            created=date(2026, 1, 1),
            description="",
        )
        (active_dir / f"{task.id}-task-{i}.md").write_text(
            task_module.render_task_file(task),
            encoding="utf-8",
        )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_tasks_summary_stdout_stays_within_its_ceiling_and_reports_truncation(
    tasks_summary_overflow_project: Path,
) -> None:
    result = _invoke(["tasks", "summary"])
    assert result.exit_code == 0, result.output
    ceiling = BUDGETS["tasks summary"].max_chars
    assert visible_len(result.output) <= ceiling
    assert "omitted: {'by_group': 5}" in result.output
    assert "complete output:" in result.output

    js = _invoke(["tasks", "summary", "--format", "json"])
    payload = json.loads(js.output)
    assert len(payload["by_group"]) == 40
    assert payload["by_group_omitted"] == 5
    assert "by_status_omitted" not in payload
    assert payload["total"] == 45


def test_tasks_summary_output_file_is_complete(tasks_summary_overflow_project: Path, tmp_path: Path) -> None:
    target = tmp_path / "summary.json"
    result = _invoke(["tasks", "summary", "--format", "json", "--output", str(target)])
    assert result.exit_code == 0, result.output
    assert result.output.count("\n") == 1
    assert "wrote the complete task summary to" in result.output

    payload = json.loads(target.read_text())
    assert len(payload["by_group"]) == 45
    assert "by_group_omitted" not in payload


_INQUIRY_EXPORT_PGMPY_EDGE_COUNT = 350


@pytest.fixture
def inquiry_export_pgmpy_overflow_graph(tmp_path: Path) -> Path:
    """A causal inquiry with enough unclaimed edges that the pgmpy export exceeds 20,000 chars.

    Each of ``_INQUIRY_EXPORT_PGMPY_EDGE_COUNT`` boundary variables directly causes a shared
    outcome with no attached relation claim, so every edge contributes both a model tuple line
    and a "no attached relation claim" TODO line (``export_pgmpy.py``).
    """
    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir(parents=True)
    graph_path.write_text(INITIAL_GRAPH_TEMPLATE, encoding="utf-8")

    n = _INQUIRY_EXPORT_PGMPY_EDGE_COUNT
    build_inquiry_graph(
        graph_path,
        slug="overflowdag",
        title="Overflow DAG",
        profile="causal",
        focal="hypothesis:h0",
        treatment="concept:x0000",
        outcome="concept:y",
        boundary_roles=[
            *({"ref": f"concept:x{i:04d}", "role": "BoundaryIn"} for i in range(n)),
            {"ref": "concept:y", "role": "BoundaryOut"},
        ],
    )

    dataset = _load_dataset(graph_path)
    causal = dataset.graph(_graph_uri("graph/causal"))
    causes = _resolve_term("scic:causes")
    outcome_uri = _resolve_term("concept:y")
    for i in range(n):
        causal.add((_resolve_term(f"concept:x{i:04d}"), causes, outcome_uri))
    _save_dataset(dataset, graph_path)
    return graph_path


def test_inquiry_export_pgmpy_stdout_refuses_rather_than_flooding(
    inquiry_export_pgmpy_overflow_graph: Path,
) -> None:
    """DOCUMENT-shaped: stdout refuses whole rather than emitting a partial script."""
    result = _invoke(["inquiry", "export-pgmpy", "overflowdag", "--path", str(inquiry_export_pgmpy_overflow_graph)])
    assert result.exit_code != 0, result.output
    assert "--output" in result.output
    ceiling = BUDGETS["inquiry export-pgmpy"].max_chars
    assert visible_len(result.output) <= ceiling
    # No partial script content leaks past the refusal.
    assert "DiscreteBayesianNetwork" not in result.output
    assert "x0000" not in result.output


def test_inquiry_export_pgmpy_output_file_is_complete(
    inquiry_export_pgmpy_overflow_graph: Path, tmp_path: Path
) -> None:
    """``--output PATH`` still writes the complete, unbudgeted script."""
    target = tmp_path / "overflowdag.py"
    result = _invoke(
        [
            "inquiry",
            "export-pgmpy",
            "overflowdag",
            "--path",
            str(inquiry_export_pgmpy_overflow_graph),
            "--output",
            str(target),
        ]
    )
    assert result.exit_code == 0, result.output
    assert "wrote the pgmpy script to" in result.output

    written = target.read_text()
    assert visible_len(written) > BUDGETS["inquiry export-pgmpy"].max_chars
    n = _INQUIRY_EXPORT_PGMPY_EDGE_COUNT
    assert written.count('"),') == n  # one model-tuple line per unclaimed edge
    assert written.count("has no attached relation claim") == n
    assert all(f'("x{i:04d}", "y")' in written for i in range(n))
