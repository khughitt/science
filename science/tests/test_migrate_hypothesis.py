"""`science entity migrate-hypothesis` — two-phase, all-or-none, and it REFUSES rather than guess.

The migration applies the field adjudication
(`docs/plans/2026-07-12-hypothesis-field-adjudication.md`) and adds no mapping rule of its own: the
status/verdict cross-tab lives in `status_inventory`, so the inventory a human read and approved IS
the migration that runs.

The two properties worth stating out loud, because both were once claimed without a test:

1. **ALL-OR-NONE.** A half-migrated corpus carries two meanings of `status` at once, and the only way
   to serve both is the compatibility layer D5 forbids.
2. **A CRASH IS RESUMABLE.** The plan said "re-running is safe and idempotent". It was not: the rerun
   re-plans from the FILES, and a file the crashed pass already wrote no longer speaks the language
   the planner reads. The journal is what makes the claim true.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from science_tool.migrate_hypothesis import (
    JOURNAL_PATH,
    MigrationRefused,
    migrate,
    resume,
)

# The two real project extensions this migration touches, in miniature: evolution's rename TARGET,
# and protein-landscape's `promoted_from` -- the field whose `origins` rename was refuted.
EXTENSION = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://schemas.science/extension-acme-provenance-1.0.json",
    "type": "object",
    "properties": {
        "source_stated_evidence": {"type": "string"},
        "promoted_from": {"type": "string"},
    },
}


def _project(tmp_path: Path, *, extensions: bool = False) -> Path:
    config: dict[str, object] = {"name": "p", "id": "p"}
    if extensions:
        config["entity_extensions"] = {"hypothesis": ["acme.provenance/1.0"]}
        (tmp_path / "schemas").mkdir(exist_ok=True)
        (tmp_path / "schemas" / "extension-acme-provenance-1.0.json").write_text(
            json.dumps(EXTENSION), encoding="utf-8"
        )
    (tmp_path / "science.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    (tmp_path / "entities/hypotheses").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _hyp(tmp_path: Path, slug: str, *, body: str = "Body.", **frontmatter: object) -> Path:
    fields: dict[str, object] = {
        "id": f"hypothesis:{slug}",
        "kind": "hypothesis",
        "title": "H",
        "created": "2026-07-11",
        "updated": "2026-07-11",
    }
    fields.update(frontmatter)
    path = tmp_path / "entities/hypotheses" / f"{slug}.md"
    path.write_text(f"---\n{yaml.safe_dump(fields, sort_keys=False)}---\n\n{body}\n", encoding="utf-8")
    return path


def _fm(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8").split("---")[1])


def test_the_cross_tab_lands_on_BOTH_axes(tmp_path: Path) -> None:
    project = _project(tmp_path)
    path = _hyp(project, "0001-a", status="weakened", phase="candidate")

    migrate(project, apply=True)

    fm = _fm(path)
    assert (fm["status"], fm["verdict"]) == ("draft", "weakened")  # lifecycle, conclusion
    assert "phase" not in fm


def test_the_eight_DELETES_are_stripped(tmp_path: Path) -> None:
    project = _project(tmp_path)
    path = _hyp(
        project,
        "0001-a",
        status="proposed",
        phase="active",
        belief_state="believed",
        evidence_stance="literature-supported",
        tags=["x"],
        priority="P1",
        role="working-model",
        promotion_criteria="something",
        domain="bio",
    )

    migrate(project, apply=True)

    fm = _fm(path)
    for key in (
        "phase",
        "belief_state",
        "evidence_stance",
        "tags",
        "priority",
        "role",
        "promotion_criteria",
        "domain",
    ):
        assert key not in fm, f"{key} survived the migration"


def test_the_RENAME_preserves_the_string_byte_for_byte(tmp_path: Path) -> None:
    """And it renames into a PROJECT-EXTENSION field.

    Which is why the projection had to stop dropping extension fields first: rename into a field the
    loader discards and the migration has written a delete with better manners.
    """
    project = _project(tmp_path, extensions=True)
    path = _hyp(
        project,
        "0001-a",
        status="proposed",
        phase="active",
        author_stated_evidence="reported in Fig 3; n=12",
    )

    migrate(project, apply=True)

    fm = _fm(path)
    assert "author_stated_evidence" not in fm
    assert fm["source_stated_evidence"] == "reported in Fig 3; n=12"


def test_promoted_from_is_LEFT_ALONE(tmp_path: Path) -> None:
    """☠️ Ruled 2026-07-14: `promoted_from` -> `origins` is NOT PERFORMABLE.

    `OriginRecord.type` is a required enum -- `user | assistant | literature` -- recording WHO
    originated the idea. The three authored values are one source path, recording WHERE the entity
    was promoted from. Different facts, and no rule turns one into the other, so any `OriginType` the
    migration picked would be fabricated provenance. It is a project-extension field, and the
    migration does not touch it.

    Note what the project must DECLARE for this to pass: `promoted_from` is UNDECLARED in the core
    mixin (never `false` -- `false` would make the extension unsatisfiable), so it is admitted only
    where its owner claims it. That is the ownership contract working, not a loophole.
    """
    project = _project(tmp_path, extensions=True)
    path = _hyp(
        project,
        "0001-a",
        status="proposed",
        phase="active",
        promoted_from="knowledge/sources/local/entities.yaml",
    )

    migrate(project, apply=True)

    fm = _fm(path)
    assert fm["promoted_from"] == "knowledge/sources/local/entities.yaml"
    assert "origins" not in fm  # nothing was synthesized


def test_CONFIDENCE_is_REFUSED_not_converted(tmp_path: Path) -> None:
    """The refusal that a future implementer will be most tempted to optimize away.

    `0.7` looks like a prior. It is not: the project describes these as *current epistemic certainty
    based on evidence gathered so far* -- a POSTERIOR. Calling it a prior would fabricate chronology,
    and two scalars name no proposition, stance, source, strength, or independence group.
    """
    project = _project(tmp_path)
    _hyp(project, "0001-a", status="proposed", phase="active", confidence=0.7)

    with pytest.raises(MigrationRefused, match="confidence"):
        migrate(project, apply=True)


def test_ONE_ambiguous_file_refuses_the_WHOLE_corpus(tmp_path: Path) -> None:
    project = _project(tmp_path)
    clean = _hyp(project, "0001-a", status="proposed", phase="active")
    _hyp(project, "0042-x", status="retired", phase="candidate")  # terminal: unrecoverable

    with pytest.raises(MigrationRefused, match="0042-x"):
        migrate(project, apply=True)

    assert _fm(clean)["status"] == "proposed"  # untouched: all-or-none


def test_an_ADJUDICATION_unblocks_a_refused_file(tmp_path: Path) -> None:
    # `complete` + `refuted` -- the shape the AUTHOR ruled for natural-systems/0009. The evidence
    # spoke, so the verdict IS the closure reason and `closure_basis` stays absent.
    project = _project(tmp_path)
    path = _hyp(project, "0009-d", status="retired", phase="candidate")
    (project / ".science").mkdir()
    (project / ".science/hypothesis-lifecycle.adjudication.yaml").write_text(
        "hypothesis:0009-d:\n  status: complete\n  verdict: refuted\n", encoding="utf-8"
    )

    migrate(project, apply=True)

    fm = _fm(path)
    assert (fm["status"], fm["verdict"]) == ("complete", "refuted")
    assert "closure_basis" not in fm


def test_a_project_with_NO_adjudication_file_migrates_fine(tmp_path: Path) -> None:
    # `adjudication_for`, not `load_adjudication`: absence is NORMAL (most projects need none), and
    # the fail-loud reader would turn every un-adjudicated root into a crash.
    project = _project(tmp_path)
    _hyp(project, "0001-a", status="proposed", phase="active")

    assert len(migrate(project, apply=True)) == 1


def test_a_missing_date_is_backfilled_from_GIT_never_from_TODAY(tmp_path: Path) -> None:
    """The four fixture hypotheses have no `created`/`updated`, and base 2.0 requires both.

    A fabricated `created` is manufactured provenance. The date comes from the file's real add-commit
    -- and asserting *some* date would pass for a fabricated one, so this asserts THE date.
    """
    project = _project(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=project, check=True)
    path = _hyp(project, "0001-a", status="proposed", phase="active")
    frontmatter = _fm(path)
    del frontmatter["created"], frontmatter["updated"]
    path.write_text(f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n\nBody.\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=project, check=True)
    subprocess.run(
        ["git", "commit", "-qm", "add"],
        cwd=project,
        check=True,
        env={"GIT_AUTHOR_DATE": "2026-03-04T00:00:00", "GIT_COMMITTER_DATE": "2026-03-04T00:00:00", "PATH": "/usr/bin:/bin"},
    )

    migrate(project, apply=True)

    assert _fm(path)["created"] == "2026-03-04"  # THE date, not A date


def test_a_dry_run_writes_NOTHING(tmp_path: Path) -> None:
    project = _project(tmp_path)
    path = _hyp(project, "0001-a", status="proposed", phase="active")
    before = path.read_text(encoding="utf-8")

    assert migrate(project, apply=False) == [path]

    assert path.read_text(encoding="utf-8") == before
    assert not (project / "science.yaml").read_text(encoding="utf-8").count("entity_schema_version")


def test_the_PIN_is_the_final_act(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _hyp(project, "0001-a", status="proposed", phase="active")

    migrate(project, apply=True)

    assert "entity_schema_version: 2" in (project / "science.yaml").read_text(encoding="utf-8")
    assert not (project / JOURNAL_PATH).exists()  # the journal is consumed, so absence means "clean"


def test_the_body_and_unrelated_frontmatter_SURVIVE(tmp_path: Path) -> None:
    project = _project(tmp_path)
    path = _hyp(
        project,
        "0001-a",
        status="proposed",
        phase="active",
        source_refs=["paper:Smith2020"],
        body="## Rationale\n\nkeep me.",
    )

    migrate(project, apply=True)

    text = path.read_text(encoding="utf-8")
    assert "paper:Smith2020" in text and "keep me." in text


def test_a_CRASH_after_the_first_write_is_RESUMABLE(tmp_path: Path, monkeypatch) -> None:
    """☠️ THE REGRESSION THE PLAN SHIPPED WITHOUT, under the claim that it could not happen.

    "The pin is written last, so a crash leaves the project unpinned, and unpinned means not-schema-2,
    so just re-run it." The second step does not follow. The rerun does not read the pin -- it reads
    the FILES, through `status_inventory._classify`. A file the crashed pass already migrated is
    `status: draft` with NO `phase`, so the classifier defaults the absent phase to `active`, finds
    `draft != active`, matches no branch, and refuses: "terminal or unknown: adjudicate explicitly."

    So a process killed after the first write left a corpus the migration REFUSED TO RESUME and
    demanded the author adjudicate -- file by file, for files that were already correct. The journal
    is what makes the original claim true, and this is the failure injection that proves it.
    """
    project = _project(tmp_path)
    first = _hyp(project, "0001-a", status="proposed", phase="active")
    second = _hyp(project, "0002-b", status="supported", phase="active")

    import science_tool.migrate_hypothesis as module

    real_write = module.atomic_write_text
    written: list[Path] = []

    def _die_on_the_second_write(path: Path, text: str) -> None:
        if path.suffix == ".md":
            if written:
                raise OSError("disk went away mid-migration")
            written.append(path)
        real_write(path, text)

    monkeypatch.setattr(module, "atomic_write_text", _die_on_the_second_write)
    with pytest.raises(OSError, match="disk went away"):
        migrate(project, apply=True)

    # The half-migrated state: one file written, one not, no pin -- and a journal that says so.
    assert (project / JOURNAL_PATH).is_file()
    assert "entity_schema_version" not in (project / "science.yaml").read_text(encoding="utf-8")

    # A plain re-run must NOT re-plan over a corpus that is half in the new language.
    monkeypatch.setattr(module, "atomic_write_text", real_write)
    with pytest.raises(MigrationRefused, match="INTERRUPTED"):
        migrate(project, apply=True)

    resume(project)

    assert _fm(first)["status"] == "active"
    assert (_fm(second)["status"], _fm(second)["verdict"]) == ("active", "supported")
    assert "entity_schema_version: 2" in (project / "science.yaml").read_text(encoding="utf-8")
    assert not (project / JOURNAL_PATH).exists()


def test_resume_REFUSES_a_file_that_changed_under_the_migration(tmp_path: Path, monkeypatch) -> None:
    # The third state, and the one that must never be guessed through: the file is neither the
    # pre-image the migration planned against nor the post-image it planned to write.
    project = _project(tmp_path)
    _hyp(project, "0001-a", status="proposed", phase="active")
    second = _hyp(project, "0002-b", status="supported", phase="active")

    import science_tool.migrate_hypothesis as module

    real_write = module.atomic_write_text
    written: list[Path] = []

    def _die_on_the_second_write(path: Path, text: str) -> None:
        if path.suffix == ".md":
            if written:
                raise OSError("boom")
            written.append(path)
        real_write(path, text)

    monkeypatch.setattr(module, "atomic_write_text", _die_on_the_second_write)
    with pytest.raises(OSError):
        migrate(project, apply=True)
    monkeypatch.setattr(module, "atomic_write_text", real_write)

    second.write_text(second.read_text(encoding="utf-8") + "\nedited by someone else\n", encoding="utf-8")

    with pytest.raises(MigrationRefused, match="neither the pre-image"):
        resume(project)
