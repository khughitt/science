"""Migrate hypothesis frontmatter to entity schema 2 — two-phase, all-or-none, per project.

`status` becomes the LIFECYCLE and `verdict` the epistemic conclusion; the eight ruled deletes go;
`author_stated_evidence` becomes `source_stated_evidence`. Every target is rendered AND validated
against the project's COMPOSED schema before a single byte is written.

WHY ALL-OR-NONE. A half-migrated corpus carries two incompatible meanings of `status` at once, and
the only way to serve both is the heuristic compatibility layer D5 forbids. A crash partway through
the write loop would manufacture exactly the state this arc exists to eliminate -- so the writes are
journalled, and an interrupted run is RESUMED rather than re-planned (`_resume`). Re-planning after a
partial write does not work: the planner reads the FILES, and a file already migrated no longer
speaks the language it reads.

WHAT THIS MODULE DOES NOT DO. It adds no mapping rule of its own. The status/verdict cross-tab lives
in `status_inventory`, entirely and deliberately: a rule that lived here and not there would mean the
inventory a human read and approved was not the migration that ran.

WHAT IT REFUSES. `confidence` (2 files, 3d-attention-bias). `0.7` and `0.75` name no proposition, no
stance, no source, no strength, and no independence group. The plausible mechanical answer -- call
them priors -- would relabel a POSTERIOR as something that preceded the evidence. The author
decomposes each scalar into proposition-targeted `expert_judgment` evidence lines, or deletes it.
That is authoring work, and a migration that guessed would be manufacturing provenance.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml
from science_model.entity_schema import EntityValidationError
from science_model.frontmatter import (
    atomic_write_text,
    project_config_path,
    render_frontmatter,
    split_frontmatter,
)

from science_tool.entity_profiles import ProjectSchema, load_project_schema
from science_tool.project_config import validated_entity_schema_version
from science_tool.status_inventory import InventoryRow, adjudication_for, inventory

JOURNAL_PATH = Path(".science/hypothesis-migration.journal")

# This migrator's TARGET generation (gen-1 -> gen-2 hypotheses). Local and explicit: it is a
# migration DESTINATION, not the toolkit's armed-generation set. It stays 2 even as new generations
# are armed -- this pass rewrites gen-1 corpora to the gen-2 hypothesis shape and nothing else.
_TARGET_GENERATION = 2

# §7 of the field adjudication. No target, nothing owed -- the mixin marks each `false`, so a
# leftover fails LOUDLY at preflight instead of validating quietly.
DELETED_KEYS: frozenset[str] = frozenset(
    {
        "phase",  # folds into `status` -- design rev 7, `phase` IS the lifecycle
        "belief_state",  # derived: belief.py already computes hypothesis belief (Task 2b)
        "evidence_stance",  # §5b: collapses durable origin with time-varying coverage
        "tags",  # already ruled legacy by the toolkit's OWN health check
        "priority",  # no owned semantics -- the name belongs to `task`
        "role",  # no owned semantics
        "promotion_criteria",  # not a frontmatter key at all: it is a BODY section
        "domain",  # write-only; materialized and never read back
    }
)

# §6. The value survives byte-for-byte; only its home changes. The target is declared by a PROJECT
# EXTENSION, which is exactly why the projection had to stop dropping extension fields first: rename
# into a field the loader discards and you have written a delete with better manners.
RENAMED_KEYS: dict[str, str] = {"author_stated_evidence": "source_stated_evidence"}

# §5b. Not garbage -- UNDER-SPECIFIED, and only the author can finish it. Kept distinct from a delete
# for that reason.
REFUSED_KEYS: frozenset[str] = frozenset({"confidence"})

# NOT migrated, and that is the ruling (2026-07-14): `promoted_from` is a PROJECT EXTENSION
# (protein-landscape). Its `origins` rename was refuted by the model -- `OriginRecord.type` is a
# required enum naming WHO had the idea, and the authored values are source paths naming WHERE the
# entity came from. Any type the migration picked would be fabricated provenance.


class MigrationRefused(RuntimeError):
    """The migration will not proceed. NOTHING has been written."""


@dataclass(frozen=True, slots=True)
class PlannedWrite:
    path: Path
    text: str


def _git_add_date(path: Path) -> str | None:
    """The date this file entered git history.

    ☠️ Never `date.today()`. Base 2.0 requires `created`/`updated`, and the four fixture hypotheses
    have neither -- so the migration must supply them, and a fabricated `created` is precisely the
    manufactured provenance this arc keeps refusing. If git cannot say, the migration refuses and the
    author supplies the date.
    """
    result = subprocess.run(
        ["git", "log", "--diff-filter=A", "--format=%as", "--follow", "--", path.name],
        cwd=path.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    dates = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return dates[-1] if dates else None


def _migrated_frontmatter(row: InventoryRow, frontmatter: dict) -> dict:
    """Apply the field adjudication to ONE file's frontmatter. Adds no mapping rule of its own."""
    migrated = dict(frontmatter)

    for key in DELETED_KEYS:
        migrated.pop(key, None)
    for old, new in RENAMED_KEYS.items():
        if old in migrated:
            migrated[new] = migrated.pop(old)  # byte-for-byte; only the name changes

    migrated["status"] = row.target_status
    if row.target_verdict is not None:
        migrated["verdict"] = row.target_verdict
    if row.target_closure_basis is not None:
        migrated["closure_basis"] = row.target_closure_basis
    return migrated


def _plan(project_root: Path, project_schema: ProjectSchema) -> list[PlannedWrite]:
    """PHASE 1 — render and validate EVERYTHING. Writes nothing, refuses on the first real doubt."""
    rows = inventory(project_root, adjudication=adjudication_for(project_root))
    refusals: list[str] = []
    planned: list[PlannedWrite] = []

    for row in rows.rows:
        if row.ambiguity is not None:
            refusals.append(f"{row.path}: {row.ambiguity}")
            continue

        frontmatter, body = split_frontmatter(row.path.read_text(encoding="utf-8"))

        refused = sorted(REFUSED_KEYS & set(frontmatter))
        if refused:
            refusals.append(
                f"{row.path}: authors {refused!r}, which no rule can migrate. "
                "A `confidence` scalar names no proposition, stance, source, strength or "
                "independence group -- decompose it into `expert_judgment` evidence lines, or "
                "delete it. The migration will not guess (adjudication artifact §5b)."
            )
            continue

        migrated = _migrated_frontmatter(row, frontmatter)

        for field in ("created", "updated"):
            if migrated.get(field):
                continue
            backfilled = _git_add_date(row.path)
            if backfilled is None:
                refusals.append(
                    f"{row.path}: no `{field}`, and git cannot date the file. Base 2.0 requires it "
                    "and the migration will not fabricate one."
                )
                break
            migrated[field] = backfilled
        else:
            try:
                project_schema.validator.validate_as(
                    migrated, project_schema.profile_for("hypothesis")
                )
            except EntityValidationError as exc:
                refusals.append(f"{row.path}: the migrated form fails its own schema: {exc}")
                continue
            planned.append(PlannedWrite(row.path, render_frontmatter(migrated, body)))

    if refusals:
        raise MigrationRefused(
            "The migration was refused. NOTHING has been written.\n\n"
            + "\n".join(f"  {refusal}" for refusal in refusals)
        )
    return planned


def _journal_write(project_root: Path, planned: list[PlannedWrite]) -> None:
    """A real transaction log: for each file, the hash BEFORE and the full text AFTER.

    ☠️ Paths alone are not enough, and that is the whole reason this exists. After a crash the
    rendered plan is gone, and it cannot be rebuilt: re-planning reads the FILES, and a file the
    crashed pass already wrote is `status: draft` with no `phase` -- which the classifier reads as
    "terminal or unknown: adjudicate explicitly". So an interrupted migration would demand the author
    adjudicate files that are already correct. The plan must survive the crash, so it is written down
    before the first byte of it is.
    """
    journal = project_root / JOURNAL_PATH
    journal.parent.mkdir(parents=True, exist_ok=True)
    entries = [
        {
            "path": str(write.path.relative_to(project_root)),
            "before_sha256": hashlib.sha256(write.path.read_bytes()).hexdigest(),
            "after": write.text,
        }
        for write in planned
    ]
    atomic_write_text(journal, json.dumps({"entries": entries}, indent=2) + "\n")


def _is_top_level_pin(line: str) -> bool:
    """Whether `line` is the top-level `entity_schema_version:` key -- not a comment, not nested.

    A substring test conflated three different lines with the real key: a comment
    (`# entity_schema_version: ...`), a key indented under some block, and an existing
    `entity_schema_version: 1`. The first two are not the pin; the third IS the pin and must be
    REPLACED, not read as "already set" and left at 1.
    """
    if line[:1].isspace():
        return False  # indented -> a nested key, not the top-level pin
    stripped = line.lstrip()
    if stripped.startswith("#"):
        return False  # a comment that merely mentions the key
    return stripped.startswith("entity_schema_version:")


def _set_entity_schema_version(project_root: Path, version: int) -> None:
    """Write the pin as a REAL top-level key, replacing any existing one. Text-level, so the project
    config keeps its comments and its key order.

    ☠️ The pin is the sole authority for "this project speaks schema 2", so a migration that thinks it
    wrote the pin but did not is the fail-open at its most dangerous: the files are rewritten, the
    journal is deleted, and the corpus reads as unmigrated forever after. So the match is EXACT (see
    `_is_top_level_pin`), and `_commit` re-reads the file to CONFIRM the pin took before it clears the
    recovery journal.
    """
    path = project_config_path(project_root)
    lines = path.read_text(encoding="utf-8").splitlines()
    key_line = f"entity_schema_version: {version}"
    for index, line in enumerate(lines):
        if _is_top_level_pin(line):
            lines[index] = key_line
            atomic_write_text(path, "\n".join(lines) + "\n")
            return
    atomic_write_text(path, "\n".join([*lines, key_line]).lstrip("\n") + "\n")


def _commit(project_root: Path, planned: list[PlannedWrite]) -> list[Path]:
    """PHASE 2 — journal, write, pin, clear. Every target is already rendered and schema-valid."""
    _journal_write(project_root, planned)
    for write in planned:
        atomic_write_text(write.path, write.text)
    # The pin, LAST: a project is on schema 2 only once its files actually are.
    _set_entity_schema_version(project_root, _TARGET_GENERATION)
    # ...and CONFIRM it took before the recovery journal is cleared. The pin is the sole authority for
    # "migrated", so a silently-unwritten pin would strand a fully-rewritten corpus as unmigrated with
    # no journal to recover from. Read it back through the same authority the loader and writer use.
    raw = yaml.safe_load(project_config_path(project_root).read_text(encoding="utf-8")) or {}
    if validated_entity_schema_version(raw) != _TARGET_GENERATION:
        raise MigrationRefused(
            f"the files were rewritten but {project_config_path(project_root).name} did not end up "
            f"pinned to entity_schema_version: {_TARGET_GENERATION}. The recovery journal is KEPT; "
            "fix the pin by hand, then this project is complete -- do NOT re-run the migration."
        )
    (project_root / JOURNAL_PATH).unlink()
    return [write.path for write in planned]


def resume(project_root: Path) -> list[Path]:
    """Finish an INTERRUPTED write pass from its journal. Never re-plans.

    Three states per file, and the third one is why this refuses instead of pressing on:

    - already the post-image  -> the crashed pass wrote it; nothing to do.
    - still the pre-image     -> the crashed pass did not reach it; write it.
    - NEITHER                 -> the file changed under the migration. REFUSE. A half-migrated
      corpus is the two-meanings-of-`status` state this arc exists to eliminate, and guessing our
      way out of it would be the compatibility layer D5 forbids, wearing a recovery hat.
    """
    project_root = project_root.resolve()
    journal = project_root / JOURNAL_PATH
    if not journal.is_file():
        raise MigrationRefused(f"{JOURNAL_PATH} does not exist: there is no interrupted pass.")

    entries = json.loads(journal.read_text(encoding="utf-8"))["entries"]
    planned: list[PlannedWrite] = []
    refusals: list[str] = []

    for entry in entries:
        path = project_root / entry["path"]
        if not path.is_file():
            refusals.append(f"{entry['path']}: named by the journal, but the file is gone.")
            continue
        current = path.read_bytes()
        if current.decode("utf-8") == entry["after"]:
            continue  # the crashed pass already wrote this one
        if hashlib.sha256(current).hexdigest() != entry["before_sha256"]:
            refusals.append(
                f"{entry['path']}: is neither the pre-image the migration planned against nor the "
                "post-image it planned to write. The file changed under an interrupted migration; "
                "restore it (`git checkout`) and re-run."
            )
            continue
        planned.append(PlannedWrite(path, entry["after"]))

    if refusals:
        raise MigrationRefused(
            "The interrupted migration cannot be resumed. NOTHING further has been written.\n\n"
            + "\n".join(f"  {refusal}" for refusal in refusals)
        )
    return _commit(project_root, planned)


def migrate(project_root: Path, *, apply: bool = False) -> list[Path]:
    """Plan the whole corpus, then -- and only then -- write it.

    Returns the paths that were (or would be) rewritten.
    """
    project_root = project_root.resolve()
    project_schema = load_project_schema(project_root)

    if (project_root / JOURNAL_PATH).is_file():
        raise MigrationRefused(
            f"{JOURNAL_PATH} exists: a previous write pass was INTERRUPTED, so this project is "
            "half-migrated and its files no longer all speak the same language. Re-planning would "
            "read the already-migrated ones as corrupt -- finish that pass with `--resume`."
        )

    planned = _plan(project_root, project_schema)
    if not apply:
        return [write.path for write in planned]
    return _commit(project_root, planned)
