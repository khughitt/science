# science/tests/test_entity_import_cli.py
"""CLI: science entities import (report-then-apply)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main


def _sha(plan_file: Path) -> str:
    return hashlib.sha256(plan_file.read_bytes()).hexdigest()


def _apply(root: Path, plan_file: Path):
    """Apply a saved plan through the mandatory approval envelope (sha over the file bytes)."""
    return CliRunner().invoke(
        main,
        ["entities", "import", "--apply-plan", str(plan_file),
         "--project-root", str(root), "--expected-plan-sha256", _sha(plan_file)],
    )


def _project(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "science.yaml").write_text("name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8")
    (tmp_path / "entities" / "plans").mkdir(parents=True, exist_ok=True)
    loose = tmp_path / "doc" / "plans"
    loose.mkdir(parents=True, exist_ok=True)
    (loose / "x.md").write_text("# A Thing\n\nbody\n", encoding="utf-8")
    return tmp_path


def _preview(root: Path, source: Path, *extra: str) -> tuple[dict, Path]:
    plan_file = root / "preview.json"
    result = CliRunner().invoke(
        main,
        ["entities", "import", str(source), "--kind", "plan", "--project-root", str(root),
         "--save-plan", str(plan_file), *extra],
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output), plan_file


def test_dry_run_then_apply_use_the_same_id(tmp_path: Path) -> None:
    root = _project(tmp_path)
    source = root / "doc" / "plans" / "x.md"

    payload, plan_file = _preview(root, source)
    assert source.exists(), "dry run moved the file"
    assert list((root / "entities" / "plans").iterdir()) == [], "dry run created an entity"
    previewed = payload["entity_id"]
    assert previewed == "plan:0001-a-thing"

    r2 = _apply(root, plan_file)
    assert r2.exit_code == 0, r2.output
    assert json.loads(r2.output)["applied"]["id"] == previewed
    assert not source.exists()
    assert (root / "entities" / "plans" / "0001-a-thing.md").exists()


def test_apply_plan_saved_inside_the_corpus_does_not_self_drift(tmp_path: Path) -> None:
    """A `.json` plan is scannable and its body repeats the moving source path.

    If apply did not exclude the plan artifact it was handed, the fresh scan would
    read the plan file as a new referrer to the source and reject the replay as
    drift -- making a plan saved anywhere under the project unappliable. The plan
    artifact must also not be rewritten in place.
    """
    root = _project(tmp_path)
    source = root / "doc" / "plans" / "x.md"
    _payload, plan_file = _preview(root, source)  # writes preview.json INTO the corpus
    assert plan_file.parent == root, "this test only means something with the plan inside the corpus"
    before = plan_file.read_text(encoding="utf-8")

    result = _apply(root, plan_file)

    assert result.exit_code == 0, result.output  # not rejected as self-drift
    assert (root / "entities" / "plans" / "0001-a-thing.md").exists()
    assert plan_file.read_text(encoding="utf-8") == before, "the rewriter edited its own plan artifact"


def test_apply_refuses_when_the_previewed_number_was_claimed_between_invocations(tmp_path: Path) -> None:
    """The sequence the whole report-then-apply design exists for.

    v3 re-planned inside the --apply invocation, so this silently landed 0002
    while the operator had approved a report describing 0001.
    """
    root = _project(tmp_path)
    source = root / "doc" / "plans" / "x.md"
    _payload, plan_file = _preview(root, source)

    # Something else claims 0001 while the operator reads the report. No `kind:`
    # field, matching test_entity_import.py's own squatter fixture: the number
    # collision is detected by claim_number_in_dir's filename scan, which does not
    # care about frontmatter, and a `kind`-less record is skipped by the corpus-wide
    # schema audit rather than failing it (it lacks enough frontmatter to validate).
    (root / "entities" / "plans" / "0001-squatter.md").write_text(
        "---\nid: plan:0001-squatter\n---\n", encoding="utf-8"
    )

    result = _apply(root, plan_file)

    assert result.exit_code != 0, "applied a plan whose number was taken"
    assert "0001" in result.output
    assert source.exists(), "source consumed by a refused apply"
    assert not (root / "entities" / "plans" / "0002-a-thing.md").exists(), "silently minted a different id"


def test_apply_refuses_when_a_referrer_changed_between_invocations(tmp_path: Path) -> None:
    root = _project(tmp_path)
    source = root / "doc" / "plans" / "x.md"
    referrer = root / "entities" / "plans" / "0009-ref.md"
    referrer.write_text(
        "---\nid: plan:0009-ref\nkind: plan\ntitle: Ref\nstatus: active\n"
        "related:\n- doc/plans/x.md\n---\n\nbody\n",
        encoding="utf-8",
    )
    _payload, plan_file = _preview(root, source)

    referrer.write_text(
        "---\nid: plan:0009-ref\nkind: plan\ntitle: Ref\nstatus: active\n"
        "related:\n- doc/plans/x.md\n---\n\nbody edited meanwhile\n",
        encoding="utf-8",
    )

    result = _apply(root, plan_file)

    assert result.exit_code != 0
    assert source.exists()


def test_dry_run_payload_carries_the_plan_without_save_plan(tmp_path: Path) -> None:
    """--save-plan is a convenience; the payload IS the plan."""
    root = _project(tmp_path)
    source = root / "doc" / "plans" / "x.md"

    result = CliRunner().invoke(
        main, ["entities", "import", str(source), "--kind", "plan", "--project-root", str(root)]
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["number"] == 1
    assert payload["ref_report"]["manual"] == []
    assert isinstance(payload["ref_report"]["edits"], list)


def test_apply_plan_rejects_a_plan_from_another_project(tmp_path: Path) -> None:
    root_a = _project(tmp_path / "a")
    root_b = _project(tmp_path / "b")
    _payload, plan_file = _preview(root_a, root_a / "doc" / "plans" / "x.md")

    result = _apply(root_b, plan_file)

    assert result.exit_code != 0, "applied a plan built against a different corpus"


def test_source_and_apply_plan_are_mutually_exclusive(tmp_path: Path) -> None:
    root = _project(tmp_path)
    source = root / "doc" / "plans" / "x.md"
    _payload, plan_file = _preview(root, source)

    result = CliRunner().invoke(
        main,
        ["entities", "import", str(source), "--kind", "plan", "--apply-plan", str(plan_file),
         "--project-root", str(root)],
    )

    assert result.exit_code != 0


def test_output_is_json_only(tmp_path: Path) -> None:
    root = _project(tmp_path)
    source = root / "doc" / "plans" / "x.md"

    result = CliRunner().invoke(main, ["entities", "import", str(source), "--kind", "plan", "--project-root", str(root)])

    assert result.exit_code == 0, result.output
    json.loads(result.output)


def test_bad_status_exits_nonzero_without_mutating(tmp_path: Path) -> None:
    root = _project(tmp_path)
    source = root / "doc" / "plans" / "x.md"

    result = CliRunner().invoke(
        main,
        ["entities", "import", str(source), "--kind", "plan", "--status", "proposed",
         "--project-root", str(root)],
    )

    assert result.exit_code != 0
    assert source.exists()
    assert list((root / "entities" / "plans").iterdir()) == []


def test_explicit_title_overrides_heading(tmp_path: Path) -> None:
    root = _project(tmp_path)
    source = root / "doc" / "plans" / "x.md"

    _payload, plan_file = _preview(root, source, "--title", "Explicit Title")
    result = _apply(root, plan_file)

    assert result.exit_code == 0, result.output
    assert (root / "entities" / "plans" / "0001-explicit-title.md").exists()


def test_save_plan_refuses_to_overwrite_the_source(tmp_path: Path) -> None:
    """--save-plan at the source path would destroy it during a 'preview'."""
    root = _project(tmp_path)
    source = root / "doc" / "plans" / "x.md"
    before = source.read_bytes()

    result = CliRunner().invoke(
        main,
        ["entities", "import", str(source), "--kind", "plan", "--project-root", str(root),
         "--save-plan", str(source)],
    )

    assert result.exit_code != 0
    assert "overwrite the source" in result.output
    assert source.read_bytes() == before, "the preview clobbered the source"


def test_save_plan_refuses_to_overwrite_an_existing_file(tmp_path: Path) -> None:
    root = _project(tmp_path)
    source = root / "doc" / "plans" / "x.md"
    occupied = root / "notes.txt"
    occupied.write_text("PRECIOUS\n", encoding="utf-8")

    result = CliRunner().invoke(
        main,
        ["entities", "import", str(source), "--kind", "plan", "--project-root", str(root),
         "--save-plan", str(occupied)],
    )

    assert result.exit_code != 0
    assert "--overwrite-plan" in result.output
    assert occupied.read_text(encoding="utf-8") == "PRECIOUS\n", "an existing file was clobbered"


def test_save_plan_replaces_with_the_overwrite_flag(tmp_path: Path) -> None:
    root = _project(tmp_path)
    source = root / "doc" / "plans" / "x.md"
    target = root / "old-plan.json"
    target.write_text("STALE\n", encoding="utf-8")

    result = CliRunner().invoke(
        main,
        ["entities", "import", str(source), "--kind", "plan", "--project-root", str(root),
         "--save-plan", str(target), "--overwrite-plan"],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(target.read_text(encoding="utf-8"))["entity_id"] == "plan:0001-a-thing"


def test_save_plan_to_a_missing_parent_dir_is_a_clean_error(tmp_path: Path) -> None:
    root = _project(tmp_path)
    source = root / "doc" / "plans" / "x.md"
    result = CliRunner().invoke(
        main,
        ["entities", "import", str(source), "--kind", "plan", "--project-root", str(root),
         "--save-plan", str(root / "no" / "such" / "dir" / "plan.json")],
    )
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    # CliRunner swallows an uncaught exception into result.exception without ever
    # printing it, so exit_code != 0 alone does not prove the CLI handled this
    # cleanly -- a raw FileNotFoundError propagating out of the command also exits
    # nonzero with empty output. Pin down that it is specifically a SystemExit
    # (click's clean-error exit), not the raw OSError leaking past click's handling.
    assert isinstance(result.exception, SystemExit), result.exception
    assert "cannot write --save-plan" in result.output


# ---- approval envelope (uniform with archive / mark-superseded) --------------


def test_apply_plan_requires_expected_sha(tmp_path: Path) -> None:
    root = _project(tmp_path)
    source = root / "doc" / "plans" / "x.md"
    _payload, plan_file = _preview(root, source)

    result = CliRunner().invoke(
        main, ["entities", "import", "--apply-plan", str(plan_file), "--project-root", str(root)]
    )

    assert result.exit_code != 0
    assert "--expected-plan-sha256" in result.output
    assert source.exists(), "a refused apply moved the source"
    assert list((root / "entities" / "plans").iterdir()) == []


def test_apply_plan_rejects_a_sha_that_does_not_match_the_bytes(tmp_path: Path) -> None:
    root = _project(tmp_path)
    source = root / "doc" / "plans" / "x.md"
    _payload, plan_file = _preview(root, source)

    result = CliRunner().invoke(
        main, ["entities", "import", "--apply-plan", str(plan_file),
               "--project-root", str(root), "--expected-plan-sha256", "0" * 64]
    )

    assert result.exit_code != 0
    assert "approval envelope" in result.output
    assert source.exists(), "a refused apply moved the source"
    assert list((root / "entities" / "plans").iterdir()) == []


def test_apply_plan_rejects_a_swapped_plan_file(tmp_path: Path) -> None:
    """The envelope binds the exact approved bytes: editing the file after preview refuses."""
    root = _project(tmp_path)
    source = root / "doc" / "plans" / "x.md"
    payload, plan_file = _preview(root, source)
    approved_sha = payload["plan_sha256"]

    plan_file.write_bytes(plan_file.read_bytes() + b" ")  # a one-byte edit after approval
    result = CliRunner().invoke(
        main, ["entities", "import", "--apply-plan", str(plan_file),
               "--project-root", str(root), "--expected-plan-sha256", approved_sha]
    )

    assert result.exit_code != 0
    assert "approval envelope" in result.output
    assert source.exists()


def test_save_plan_emits_plan_sha256_matching_the_file(tmp_path: Path) -> None:
    root = _project(tmp_path)
    payload, plan_file = _preview(root, root / "doc" / "plans" / "x.md")
    assert payload["plan_sha256"] == _sha(plan_file)


def test_expected_sha_without_apply_plan_is_rejected(tmp_path: Path) -> None:
    root = _project(tmp_path)
    source = root / "doc" / "plans" / "x.md"

    result = CliRunner().invoke(
        main, ["entities", "import", str(source), "--kind", "plan",
               "--project-root", str(root), "--expected-plan-sha256", "abc"]
    )

    assert result.exit_code != 0
    assert "requires --apply-plan" in result.output
