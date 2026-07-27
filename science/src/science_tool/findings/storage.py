"""Canonical case files under `doc/audits/cases/` (design §5).

NOT `entities/` and NOT any directory named `findings/`: `EntityKind.FINDING` is a
live epistemic kind, and `_infer_kind_from_path` keys on `path.parent.name` with no
root anchoring, so a `findings/` directory anywhere would infer that kind. `cases`
is absent from `_DIR_TO_KIND`.

Unlike `write_run_record`, which is write-once via `O_EXCL`, a case is UPSERTED:
occurrences accumulate. The write is therefore temp-file-plus-rename -- but the temp
file is created `O_EXCL` and the rename is `os.replace(..., src_dir_fd=, dst_dir_fd=)`,
both inside the SAME held descriptor as the read that preceded them.

`CaseStore` exists so that the directory is walked ONCE per operation and every
subsequent access goes through that descriptor. Functions that take a `project_root`
and a name would each re-resolve the path, which is the check/use gap in miniature.

Loaders validate the filename against the contents. A case whose slug, digest, or
stored `finding_id` disagrees with the fingerprint recomputed from its own immutable
fields is a LOAD ERROR -- never a silent repair or rename.
"""

from __future__ import annotations

import os
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import yaml
from pydantic import ValidationError
from science_model.audit import DOC_KIND, AuditFindingRecord, finding_fingerprint, rule_slug
from science_model.frontmatter import render_frontmatter, split_frontmatter

from science_tool.findings.paths import (
    PathSafetyError,
    create_regular_file_at,
    exists_at,
    open_dir_inside,
    open_dir_inside_if_present,
    open_lock_at,
    project_relative,
    read_regular_file_at,
    replace_at,
    unlink_at,
)

CASES_DIRNAME = "doc/audits/cases"
LOCK_NAME = ".ingest.lock"

#: A case is frontmatter plus one comment line. Anything approaching this is a file
#: someone else's tooling wrote into `cases/`, and reading it unbounded is the same
#: mistake as reading an unbounded report.
MAX_CASE_BYTES = 4 * 1024 * 1024

_BODY = (
    "<!-- Project-state case about repository or corpus hygiene. Not a KG entity: "
    "carries no `kind:`/`id:`, never materializes into the knowledge graph, never "
    "affects belief or attention. See "
    "docs/plans/2026-07-27-finding-convergence-design.md -->\n"
)


class CaseStorageError(ValueError):
    """A case file could not be written, read, or trusted."""


def cases_dir(project_root: Path) -> Path:
    return project_root / CASES_DIRNAME


def case_filename(record: AuditFindingRecord) -> str:
    return f"{rule_slug(record.rule_id)}--{record.finding_id}.md"


def case_path(project_root: Path, record: AuditFindingRecord) -> Path:
    return cases_dir(project_root) / case_filename(record)


def serialize_case(record: AuditFindingRecord) -> tuple[str, bytes]:
    """Return the deterministic, size-checked bytes written for one case.

    This is the shared write-feasibility boundary: ingestion can preflight every
    classified record before beginning its write phase, and `CaseStore.write` consumes
    the exact same serialization contract.
    """
    name = case_filename(record)
    payload = {
        "doc_kind": DOC_KIND,
        # `Transition.from_status=None` is required for the genesis transition.
        # Recursive `exclude_none` would silently make the stored record invalid.
        **record.model_dump(mode="json"),
    }
    encoded = render_frontmatter(payload, _BODY).encode("utf-8")
    if len(encoded) > MAX_CASE_BYTES:
        raise CaseStorageError(
            f"case {name!r} is {len(encoded)} bytes, which exceeds "
            f"{MAX_CASE_BYTES}"
        )
    return name, encoded


def _parse_case(name: str, text: str) -> AuditFindingRecord:
    """Validate one case's text against its own filename.

    YAML errors are wrapped: `split_frontmatter` calls `yaml.safe_load`, which raises
    `yaml.YAMLError` -- a type no caller of this module has any reason to catch, and
    one that would escape the CLI's declared error channel entirely.
    """
    if not name.endswith(".md"):
        raise CaseStorageError(f"{name} does not have the canonical .md extension")
    try:
        frontmatter, _body = split_frontmatter(text)
    except yaml.YAMLError as exc:
        raise CaseStorageError(f"{name}: frontmatter is not valid YAML: {exc}") from exc
    if not frontmatter:
        raise CaseStorageError(f"{name} has no parsable frontmatter")
    if frontmatter.get("doc_kind") != DOC_KIND:
        raise CaseStorageError(
            f"{name} is not a {DOC_KIND}; got doc_kind={frontmatter.get('doc_kind')!r}"
        )
    fields = {k: v for k, v in frontmatter.items() if k != "doc_kind"}
    try:
        record = AuditFindingRecord.model_validate(fields)
    except ValidationError as exc:
        # `ValidationError` alone, not `Exception`. Everything this call is expected to
        # raise arrives as one: `RecordError` and `FingerprintError` are both
        # `ValueError`s raised inside validators, and pydantic wraps those. A blanket
        # `except Exception` would also swallow a `TypeError` or an `AttributeError`
        # from a bug in the record model and report it as a malformed FILE -- sending
        # the reader to edit a case that is not actually wrong.
        raise CaseStorageError(f"{name} is not a valid case: {exc}") from exc

    stem = name[: -len(".md")]
    if "--" not in stem:
        raise CaseStorageError(f"{name} is not `<rule-slug>--<digest>.md`")
    slug, _, digest = stem.rpartition("--")
    expected_slug = rule_slug(record.rule_id)
    if slug != expected_slug:
        raise CaseStorageError(
            f"{name}: filename slug {slug!r} != {expected_slug!r} for rule "
            f"{record.rule_id!r}"
        )
    if digest != record.finding_id:
        raise CaseStorageError(
            f"{name}: filename digest does not match finding_id {record.finding_id!r}"
        )
    recomputed = finding_fingerprint(
        rule_id=record.rule_id,
        subject=record.subject,
        identity_qualifiers=record.identity_qualifiers,
    )
    if recomputed != record.finding_id:
        raise CaseStorageError(
            f"{name}: recomputed fingerprint {recomputed!r} != stored finding_id "
            f"{record.finding_id!r}; a case never acquires a new identity by being edited"
        )
    return record


class CaseStore:
    """Case operations anchored to ONE directory descriptor.

    A validated pathname is not a validated file: every later `open()` of that string
    resolves its components again, and whatever was swapped in between is what gets
    opened. Holding the descriptor removes the second resolution -- `os.listdir(fd)`,
    `os.open(..., dir_fd=fd)`, and `os.replace(..., src_dir_fd=fd, dst_dir_fd=fd)` all
    act inside the directory the walk actually verified, whatever its pathname now
    names.
    """

    def __init__(self, dir_fd: int) -> None:
        self._dir_fd = dir_fd

    def names(self) -> list[str]:
        try:
            entries = os.listdir(self._dir_fd)
        except OSError as exc:
            raise CaseStorageError(f"could not list the case store: {exc}") from exc
        return sorted(n for n in entries if n.endswith(".md"))

    def has(self, name: str) -> bool:
        """Through the anchored primitive, like every other operation here.

        Doing the `lstat` inline would make this the one method in the class that
        accepts a name `paths.py` has not validated -- and `has()` is what decides
        whether a write happens.
        """
        try:
            return exists_at(self._dir_fd, name)
        except PathSafetyError as exc:
            raise CaseStorageError(str(exc)) from exc

    def read(self, name: str) -> AuditFindingRecord:
        try:
            text = read_regular_file_at(self._dir_fd, name, MAX_CASE_BYTES)
        except PathSafetyError as exc:
            raise CaseStorageError(str(exc)) from exc
        except OSError as exc:
            raise CaseStorageError(f"could not read {name!r}: {exc}") from exc
        return _parse_case(name, text)

    def write(self, record: AuditFindingRecord) -> str:
        name, encoded = serialize_case(record)
        try:
            temp, descriptor = self._create_temp(name)
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(encoded)
                replace_at(self._dir_fd, temp, name)
            except BaseException:
                unlink_at(self._dir_fd, temp)
                raise
        except PathSafetyError as exc:
            raise CaseStorageError(str(exc)) from exc
        except OSError as exc:
            raise CaseStorageError(f"could not write case {name!r}: {exc}") from exc
        return name

    def _create_temp(self, case_name: str) -> tuple[str, int]:
        """Create one writer-owned temp without touching any pre-existing name."""
        temp = f".{case_name}.{secrets.token_hex(16)}.tmp"
        return temp, create_regular_file_at(self._dir_fd, temp)

    def lock(self) -> int:
        """The caller owns the returned descriptor and must close it."""
        return open_lock_at(self._dir_fd, LOCK_NAME)


@contextmanager
def case_store(project_root: Path, *, create: bool) -> Iterator[CaseStore]:
    """Walk to `doc/audits/cases/` once and hold it open for the whole operation.

    Both failure modes of the walk are converted here so nothing outside this module's
    declared error channel escapes. The only `FileNotFoundError` the walk itself can
    raise is a missing component; every operation on the yielded store converts its own
    `OSError` before it could reach this handler.
    """
    try:
        with open_dir_inside(project_root, CASES_DIRNAME, create=create) as dir_fd:
            yield CaseStore(dir_fd)
    except FileNotFoundError as exc:
        raise CaseStorageError(f"{cases_dir(project_root)} does not exist") from exc
    except PathSafetyError as exc:
        raise CaseStorageError(str(exc)) from exc


def write_case(project_root: Path, record: AuditFindingRecord) -> Path:
    with case_store(project_root, create=True) as store:
        name = store.write(record)
    # A display path for callers and tests. It is NOT re-opened by this module: every
    # operation above happened through the descriptor.
    return cases_dir(project_root) / name


def load_case(project_root: Path, path: Path) -> AuditFindingRecord:
    """Read one case named by path. The path is relativized and its directory walked;
    the read itself happens through the resulting descriptor."""
    try:
        relative = project_relative(project_root, path)
    except PathSafetyError as exc:
        raise CaseStorageError(str(exc)) from exc
    parent, _, name = relative.rpartition("/")
    if parent != CASES_DIRNAME:
        raise CaseStorageError(
            f"{path} is not under {CASES_DIRNAME}; cases are read only from the "
            "canonical store"
        )
    with case_store(project_root, create=False) as store:
        return store.read(name)


@contextmanager
def optional_case_store(project_root: Path) -> Iterator[CaseStore | None]:
    """`None` when the store is GENUINELY absent -- decided by the SAME walk that
    opens it, so presence and access are never two separate answers."""
    try:
        with open_dir_inside_if_present(project_root, CASES_DIRNAME) as dir_fd:
            yield None if dir_fd is None else CaseStore(dir_fd)
    except PathSafetyError as exc:
        raise CaseStorageError(str(exc)) from exc


def load_cases(project_root: Path) -> list[AuditFindingRecord]:
    """Every stored case, or `[]` only when the store is GENUINELY absent.

    ONE walk. Asking "does it exist?" and then opening it are two resolutions of the
    same name, and the name can refer to two different real directories across them --
    which is the check/use gap `CaseStore` exists to close, reintroduced at a larger
    granularity.

    Absence is never decided by `lstat`/`exists()` on the full pathname: those follow
    every intermediate component, so a symlinked `doc/audits` whose target has no
    `cases/` raises `FileNotFoundError` and would be reported as "no findings" for a
    store that was redirected. A redirected or replaced store is an unavailable
    instrument and must fail loudly.
    """
    with optional_case_store(project_root) as store:
        if store is None:
            return []
        records = [store.read(name) for name in store.names()]
    return sorted(records, key=lambda r: r.finding_id)
