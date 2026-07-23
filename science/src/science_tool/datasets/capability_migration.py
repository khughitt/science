"""Migrate dataset capability frontmatter to entity schema 3 -- transactional, all-or-none, per project.

The ONLY gen-2 -> gen-3 difference is the SHAPE of the two capability fields. `dataset/3.0` retypes
`provided_capabilities`/`required_capabilities` from the legacy value-keyed shape
(`{assay: gene-expression, modality: microarray}`) to `{data_product, qualifiers}` objects drawn from
the packaged term catalog. This migrator rewrites those two fields entry-by-entry through an
adjudicated crosswalk, and pins the project to schema 3 -- and does nothing else. An entity that
authors neither capability field is already gen-3-valid and is left untouched.

WHY ALL-OR-NONE, and why a crash is RESUMED not re-planned -- both mirror `migrate_hypothesis.py`
exactly, deliberately (the plan tracks the duplication). The planner reads the FILES; a file already
rewritten to the `{data_product, qualifiers}` shape no longer speaks the legacy language the crosswalk
reads, so re-planning after a partial write cannot work. The writes are journalled (pre-image hash +
full post-image), the pin is set LAST and CONFIRMED before the journal is cleared, and an interrupted
run is finished with `--resume`.

WHAT IT REFUSES. A crosswalk `Refused` disposition, or a raw capability shape the crosswalk does not
map at all, aborts the whole pass with NOTHING written -- the author resolves it (extend the crosswalk,
or fix the entity) and re-runs. A `Dropped` disposition is recorded in the dry-run report and the
entry is removed. Every planned post-image is validated against the composed gen-3 profile before a
byte is written, so a rewrite that produced an invalid entity aborts too.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from science_model.data_products import load_catalog
from science_model.entity_schema import EntityValidationError, ProfileParseError
from science_model.frontmatter import (
    atomic_write_text,
    project_config_path,
    render_frontmatter,
    split_frontmatter,
)

from science_tool.datasets.capability_crosswalk import (
    Crosswalk,
    CrosswalkError,
    Dropped,
    Mapped,
    Refused,
)
from science_tool.datasets.capability_shape import gen3_shape_issue
from science_tool.entity_scan import iter_entity_markdown
from science_tool.entity_profiles import ProjectSchema, load_project_schema
from science_tool.migrate_hypothesis import (
    MigrationRefused,
    PlannedWrite,
    _set_entity_schema_version,
)
from science_tool.project_config import validated_entity_schema_version

__all__ = ["migrate", "resume", "MigrationRefused"]

JOURNAL_PATH = Path(".science/capability-migration.journal")

# This migrator's TARGET generation (gen-2 -> gen-3 dataset capabilities). Local and explicit: a
# migration DESTINATION, not the toolkit's armed-generation set.
_TARGET_GENERATION = 3

# The two fields whose SHAPE changed in dataset/3.0. Nothing else is touched.
_CAPABILITY_FIELDS = ("provided_capabilities", "required_capabilities")


@dataclass
class _ReportEntry:
    path: Path
    field: str
    entry: dict
    disposition: str  # "mapped: <term>" or "dropped: <rationale>"


@dataclass
class _PlanResult:
    planned: list[PlannedWrite] = field(default_factory=list)
    refusals: list[str] = field(default_factory=list)
    report: list[_ReportEntry] = field(default_factory=list)


def _rewrite_field(
    path: Path, field_name: str, entries: list, crosswalk: Crosswalk, result: _PlanResult
) -> tuple[list, bool]:
    """Rewrite ONE capability field's list of entries. Returns (new_list, changed).

    Refusals and unmapped shapes are collected into `result.refusals` (the caller aborts on any).
    """
    new_entries: list = []
    changed = False
    for entry in entries:
        if not isinstance(entry, dict):
            result.refusals.append(f"{path}: {field_name} entry {entry!r} is not a mapping")
            continue
        try:
            outcome = crosswalk.rewrite(entry)
        except CrosswalkError as exc:
            result.refusals.append(f"{path}: {field_name}: {exc}")
            continue
        if isinstance(outcome, Mapped):
            new_entries.append(outcome.capability)
            result.report.append(
                _ReportEntry(path, field_name, entry, f"mapped: {outcome.capability['data_product']}")
            )
            changed = True
        elif isinstance(outcome, Dropped):
            result.report.append(_ReportEntry(path, field_name, entry, f"dropped: {outcome.rationale}"))
            changed = True
        elif isinstance(outcome, Refused):
            result.refusals.append(f"{path}: {field_name} entry {entry!r} refused: {outcome.rationale}")
    return new_entries, changed


def _plan(
    project_root: Path, crosswalk: Crosswalk, project_schema: ProjectSchema
) -> _PlanResult:
    """PHASE 1 -- rewrite and validate EVERYTHING. Writes nothing, collects every refusal."""
    result = _PlanResult()

    for md in iter_entity_markdown(project_root / "entities"):
        frontmatter, body = split_frontmatter(md.read_text(encoding="utf-8"))
        if not any(f in frontmatter for f in _CAPABILITY_FIELDS):
            continue  # the only gen-2 -> gen-3 difference is the capability shape; nothing owed here

        migrated = dict(frontmatter)
        file_changed = False
        for field_name in _CAPABILITY_FIELDS:
            if field_name not in migrated:
                continue
            entries = migrated[field_name]
            if not isinstance(entries, list):
                result.refusals.append(f"{md}: {field_name} is not a list")
                continue
            rewritten, changed = _rewrite_field(md, field_name, entries, crosswalk, result)
            migrated[field_name] = rewritten
            file_changed = file_changed or changed

        if not file_changed:
            continue

        kind = frontmatter.get("kind")
        if not isinstance(kind, str) or not kind:
            result.refusals.append(f"{md}: entity has no `kind`; cannot select a validation profile")
            continue
        try:
            profile = project_schema.profile_for(kind)
        except ProfileParseError:
            profile = None  # a kind with no composed gen-3 profile (e.g. question)
        if profile is not None:
            try:
                project_schema.validator.validate_as(migrated, profile)
            except EntityValidationError as exc:
                result.refusals.append(f"{md}: the migrated form fails its own gen-3 schema: {exc}")
                continue
        else:
            # No composed profile for this kind; validate the rewritten capability fields directly
            # via the canonical shape parser. Empty/absent is valid; only a malformed shape refuses.
            malformed = False
            for field_name in _CAPABILITY_FIELDS:
                if field_name in migrated and gen3_shape_issue(migrated[field_name]) == "malformed":
                    result.refusals.append(
                        f"{md}: {field_name} post-image is not a valid gen-3 capability shape"
                    )
                    malformed = True
            if malformed:
                continue
        result.planned.append(PlannedWrite(md, render_frontmatter(migrated, body)))

    return result


def _print_report(report: list[_ReportEntry]) -> None:
    """The Task-12 review artifact: every entry that would change, and how."""
    if not report:
        print("No capability rewrites planned.")
        return
    by_path: dict[Path, list[_ReportEntry]] = {}
    for entry in report:
        by_path.setdefault(entry.path, []).append(entry)
    for path in sorted(by_path):
        print(f"{path}:")
        for entry in by_path[path]:
            print(f"  {entry.field}: {entry.entry!r} -> {entry.disposition}")


def _journal_write(project_root: Path, planned: list[PlannedWrite]) -> None:
    """A real transaction log: for each file, the hash BEFORE and the full text AFTER.

    Paths alone are not enough, and that is the whole reason this exists: after a crash the rendered
    plan is gone and cannot be rebuilt, because re-planning reads the FILES and a file the crashed
    pass already rewrote no longer carries the legacy capability shape the crosswalk reads. The plan
    must survive the crash, so it is written down before the first byte of it is.
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


def _commit(project_root: Path, planned: list[PlannedWrite]) -> list[Path]:
    """PHASE 2 -- journal, write, pin, clear. Every target is already rendered and schema-valid."""
    _journal_write(project_root, planned)
    for write in planned:
        atomic_write_text(write.path, write.text)
    # The pin, LAST: a project is on schema 3 only once its files actually are.
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

    Three states per file, and the third is why this refuses instead of pressing on:

    - already the post-image  -> the crashed pass wrote it; nothing to do.
    - still the pre-image      -> the crashed pass did not reach it; write it.
    - NEITHER                  -> the file changed under the migration. REFUSE and keep the journal.
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


def migrate(project_root: Path, *, crosswalk_path: Path, apply: bool = False) -> list[Path]:
    """Plan the whole corpus, then -- and only then -- write it.

    Returns the paths that were (or would be) rewritten.
    """
    project_root = project_root.resolve()
    if (project_root / JOURNAL_PATH).is_file():
        raise MigrationRefused(
            f"{JOURNAL_PATH} exists: a previous write pass was INTERRUPTED, so this project is "
            "half-migrated and its files no longer all speak the same language. Re-planning would "
            "read the already-migrated ones as corrupt -- finish that pass with `--resume`."
        )

    catalog = load_catalog()
    crosswalk = Crosswalk.load(crosswalk_path, catalog_ids=set(catalog.by_id))
    project_schema = load_project_schema(project_root, generation=_TARGET_GENERATION)

    result = _plan(project_root, crosswalk, project_schema)
    if result.refusals:
        raise MigrationRefused(
            "The migration was refused. NOTHING has been written.\n\n"
            + "\n".join(f"  {refusal}" for refusal in result.refusals)
        )
    if not apply:
        _print_report(result.report)
        return [write.path for write in result.planned]
    return _commit(project_root, result.planned)
