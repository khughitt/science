# science/tests/test_findings_storage.py
import threading
from datetime import UTC, datetime

import pytest
from science_model.audit import (
    AuditFindingRecord,
    EntitySubject,
    Occurrence,
    Transition,
    finding_fingerprint,
    occurrence_key,
)

from science_tool.findings import storage as finding_storage
from science_tool.findings.storage import (
    CASES_DIRNAME,
    MAX_CASE_BYTES,
    CaseStorageError,
    case_path,
    case_store,
    load_case,
    load_cases,
    write_case,
)

NOW = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
SUBJECT = EntitySubject(ref="dataset:gtex-v8")
RULE = "dataset.cached-field-drift"
QUALS = {"field": "year"}


def _occurrence(
    finding_id: str,
    *,
    ingestion_ref: str = "ing:1",
    quals: dict | None = None,
    message: str = "drifted",
) -> Occurrence:
    # The occurrence's qualifiers must agree with the record's identity on every
    # identity-bearing key, so this helper takes them rather than hardcoding one set.
    return Occurrence(
        idempotency_key=occurrence_key(
            producer_id="dataset_anomalies",
            ingestion_ref=ingestion_ref,
            finding_id=finding_id,
        ),
        producer_id="dataset_anomalies",
        ingestion_ref=ingestion_ref,
        observed_at=NOW,
        severity="warn",
        message=message,
        qualifiers=dict(QUALS if quals is None else quals),
        evidence=(),
    )


def _record(
    quals: dict | None = None, *, message: str = "drifted"
) -> AuditFindingRecord:
    quals = QUALS if quals is None else quals
    finding_id = finding_fingerprint(
        rule_id=RULE, subject=SUBJECT, identity_qualifiers=quals
    )
    return AuditFindingRecord(
        finding_id=finding_id,
        fingerprint_version=1,
        rule_id=RULE,
        subject=SUBJECT,
        identity_qualifiers=quals,
        occurrences=(_occurrence(finding_id, quals=quals, message=message),),
        transitions=(
            Transition(from_status=None, to_status="proposed", actor="ingest", at=NOW,
                       reason="detected"),
        ),
        status="proposed",
    )


def test_case_path_carries_the_rule_slug_and_the_full_digest(tmp_path):
    record = _record()
    path = case_path(tmp_path, record)
    assert path.parent == tmp_path / CASES_DIRNAME
    assert path.name == f"dataset-cached-field-drift--{record.finding_id}.md"


def test_write_then_load_round_trips(tmp_path):
    record = _record()
    path = write_case(tmp_path, record)
    assert load_case(tmp_path, path) == record


def test_exposed_case_serialization_is_the_exact_checked_write_payload(tmp_path):
    record = _record()

    name, encoded = finding_storage.serialize_case(record)
    path = write_case(tmp_path, record)

    assert path.name == name
    assert path.read_bytes() == encoded


def test_write_is_an_upsert_not_a_write_once(tmp_path):
    record = _record()
    write_case(tmp_path, record)
    grown = record.with_occurrence(_occurrence(record.finding_id, ingestion_ref="ing:2"))
    write_case(tmp_path, grown)
    assert len(load_case(tmp_path, case_path(tmp_path, record)).occurrences) == 2


def test_write_refuses_an_oversized_payload_before_creating_a_temp(
    tmp_path, monkeypatch
):
    record = _record(message="é" * (MAX_CASE_BYTES // 2 + 1))
    create_called = False
    real_create = finding_storage.create_regular_file_at

    def tracked_create(dir_fd, name):
        nonlocal create_called
        create_called = True
        return real_create(dir_fd, name)

    monkeypatch.setattr(finding_storage, "create_regular_file_at", tracked_create)

    with pytest.raises(CaseStorageError, match="exceeds"):
        write_case(tmp_path, record)

    assert create_called is False
    assert list((tmp_path / CASES_DIRNAME).iterdir()) == []


def test_concurrent_writers_never_commit_or_mutate_another_writers_temp(
    tmp_path, monkeypatch
):
    first = _record()
    second = first.with_occurrence(
        _occurrence(first.finding_id, ingestion_ref="ing:2")
    )
    first_waiting = threading.Event()
    second_partial = threading.Event()
    allow_second_to_finish = threading.Event()
    first_committed = threading.Event()
    errors = []

    real_fdopen = finding_storage.os.fdopen
    real_replace_at = finding_storage.replace_at

    class InterleavedHandle:
        def __init__(self, handle, writer):
            self._handle = handle
            self._writer = writer

        def __enter__(self):
            self._handle.__enter__()
            return self

        def __exit__(self, exc_type, exc, traceback):
            return self._handle.__exit__(exc_type, exc, traceback)

        def write(self, text):
            if self._writer == "case-writer-1":
                first_waiting.set()
                if not second_partial.wait(timeout=5):
                    raise AssertionError("second writer never reached its partial write")
                return self._handle.write(text)
            if self._writer == "case-writer-2":
                split = len(text) // 2
                written = self._handle.write(text[:split])
                self._handle.flush()
                second_partial.set()
                if not allow_second_to_finish.wait(timeout=5):
                    raise AssertionError("second writer was never released")
                return written + self._handle.write(text[split:])
            return self._handle.write(text)

    def interleaved_fdopen(descriptor, *args, **kwargs):
        return InterleavedHandle(
            real_fdopen(descriptor, *args, **kwargs),
            threading.current_thread().name,
        )

    def tracked_replace_at(dir_fd, source, target):
        real_replace_at(dir_fd, source, target)
        if threading.current_thread().name == "case-writer-1":
            first_committed.set()

    def run_writer(record):
        try:
            write_case(tmp_path, record)
        except BaseException as exc:
            errors.append(exc)

    monkeypatch.setattr(finding_storage.os, "fdopen", interleaved_fdopen)
    monkeypatch.setattr(finding_storage, "replace_at", tracked_replace_at)

    writer_1 = threading.Thread(
        target=run_writer, args=(first,), name="case-writer-1"
    )
    writer_2 = threading.Thread(
        target=run_writer, args=(second,), name="case-writer-2"
    )
    writer_1.start()
    writer_2_started = False
    try:
        assert first_waiting.wait(timeout=5)
        writer_2.start()
        writer_2_started = True
        assert second_partial.wait(timeout=5)
        assert first_committed.wait(timeout=5)

        # Writer 2 still has only half its payload written. The committed name must
        # therefore be writer 1's complete inode, not writer 2's open temp inode.
        assert load_case(tmp_path, case_path(tmp_path, first)) == first
    finally:
        allow_second_to_finish.set()
        second_partial.set()
        writer_1.join(timeout=5)
        if writer_2_started:
            writer_2.join(timeout=5)

    assert not writer_1.is_alive()
    assert not writer_2.is_alive()
    assert errors == []
    assert load_case(tmp_path, case_path(tmp_path, second)) == second
    assert not any(
        entry.name.endswith(".tmp")
        for entry in (tmp_path / CASES_DIRNAME).iterdir()
    )


def test_frontmatter_carries_doc_kind_and_never_an_entity_kind(tmp_path):
    text = write_case(tmp_path, _record()).read_text(encoding="utf-8")
    assert "doc_kind: audit-case" in text
    assert "\nkind:" not in text
    assert "\nid:" not in text


def test_load_refuses_a_filename_whose_digest_disagrees(tmp_path):
    record = _record()
    path = write_case(tmp_path, record)
    moved = path.with_name(f"dataset-cached-field-drift--{'0' * 64}.md")
    path.rename(moved)
    with pytest.raises(CaseStorageError, match="filename digest"):
        load_case(tmp_path, moved)


def test_load_refuses_a_filename_whose_slug_disagrees(tmp_path):
    record = _record()
    path = write_case(tmp_path, record)
    moved = path.with_name(f"some-other-rule--{record.finding_id}.md")
    path.rename(moved)
    with pytest.raises(CaseStorageError, match="filename slug"):
        load_case(tmp_path, moved)


def test_load_refuses_an_extensionless_case_filename(tmp_path):
    record = _record()
    path = write_case(tmp_path, record)
    extensionless = path.with_suffix("")
    path.rename(extensionless)

    with pytest.raises(CaseStorageError, match=r"canonical \.md extension"):
        load_case(tmp_path, extensionless)


def test_load_refuses_a_record_whose_finding_id_is_not_its_own_fingerprint(tmp_path):
    record = _record()
    path = write_case(tmp_path, record)
    text = path.read_text(encoding="utf-8")
    # Edit only the identity qualifier, leaving finding_id alone: the recomputed
    # fingerprint no longer matches what the file claims.
    tampered = text.replace("field: year", "field: month")
    assert tampered != text
    path.write_text(tampered, encoding="utf-8")
    with pytest.raises(CaseStorageError, match="recomputed fingerprint"):
        load_case(tmp_path, path)


def test_write_refuses_a_symlinked_cases_directory(tmp_path):
    real = tmp_path / "elsewhere"
    real.mkdir()
    link_parent = tmp_path / "doc" / "audits"
    link_parent.mkdir(parents=True)
    (link_parent / "cases").symlink_to(real, target_is_directory=True)
    with pytest.raises(CaseStorageError, match="symlink"):
        write_case(tmp_path, _record())


def test_write_refuses_a_symlinked_PARENT_of_the_cases_directory(tmp_path):
    # `doc/audits` is the link, `cases/` under it is real. Checking only the final
    # directory would miss this entirely.
    real = tmp_path / "elsewhere"
    (real / "cases").mkdir(parents=True)
    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "audits").symlink_to(real, target_is_directory=True)
    with pytest.raises(CaseStorageError, match="symlink"):
        write_case(tmp_path, _record())


def test_write_creates_nothing_inside_a_symlinked_parents_target(tmp_path):
    # The link target does NOT yet contain `cases/`. A `mkdir(parents=True)` that runs
    # before validation would create it there, outside the project, and the later
    # refusal would arrive after the damage. Nothing must appear in the target.
    real = tmp_path / "elsewhere"
    real.mkdir()
    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "audits").symlink_to(real, target_is_directory=True)
    with pytest.raises(CaseStorageError, match="symlink|not a directory"):
        write_case(tmp_path, _record())
    assert list(real.iterdir()) == []


def test_load_refuses_a_case_reached_through_a_symlinked_parent(tmp_path):
    write_case(tmp_path, _record())
    real_cases = tmp_path / "doc" / "audits" / "cases"
    moved = tmp_path / "moved-cases"
    real_cases.rename(moved)
    real_cases.symlink_to(moved, target_is_directory=True)
    with pytest.raises(CaseStorageError, match="symlink"):
        load_cases(tmp_path)


def test_load_cases_returns_every_case_sorted_by_finding_id(tmp_path):
    write_case(tmp_path, _record())
    # Built through the constructor, not model_copy: the finding_id, the occurrence
    # keys, and the identity qualifiers must agree, and only construction checks that.
    write_case(tmp_path, _record(quals={"field": "url"}))
    loaded = load_cases(tmp_path)
    assert [r.finding_id for r in loaded] == sorted(r.finding_id for r in loaded)
    assert len(loaded) == 2


def test_load_cases_on_a_project_with_no_cases_returns_empty(tmp_path):
    assert load_cases(tmp_path) == []


def test_load_cases_refuses_a_DANGLING_cases_symlink(tmp_path):
    # `Path.exists()` follows links, so this reads as absent and would report "no
    # findings" for a store that was redirected somewhere that no longer exists.
    # Absence must mean nothing is there under any name.
    (tmp_path / "doc" / "audits").mkdir(parents=True)
    (tmp_path / "doc" / "audits" / "cases").symlink_to(
        tmp_path / "gone", target_is_directory=True
    )
    with pytest.raises(CaseStorageError, match="symlink"):
        load_cases(tmp_path)


def test_load_cases_refuses_an_INTERMEDIATE_link_whose_target_lacks_cases(tmp_path):
    # `doc/audits` is a link to a real directory with no `cases/` in it. Any check
    # that asks the filesystem about the FULL pathname before walking gets
    # FileNotFoundError here -- indistinguishable from "nothing stored yet" -- and
    # reports clean about a store that was redirected.
    target = tmp_path / "elsewhere"
    target.mkdir()
    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "audits").symlink_to(target, target_is_directory=True)
    with pytest.raises(CaseStorageError, match="symlink"):
        load_cases(tmp_path)


def test_load_cases_refuses_a_DANGLING_intermediate_link(tmp_path):
    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "audits").symlink_to(tmp_path / "gone", target_is_directory=True)
    with pytest.raises(CaseStorageError, match="symlink"):
        load_cases(tmp_path)


def test_load_cases_refuses_a_cases_path_that_is_not_a_directory(tmp_path):
    (tmp_path / "doc" / "audits").mkdir(parents=True)
    (tmp_path / "doc" / "audits" / "cases").write_text("nope", encoding="utf-8")
    with pytest.raises(CaseStorageError, match="not a directory"):
        load_cases(tmp_path)


def test_load_case_refuses_a_case_reached_through_a_symlinked_parent(tmp_path):
    # `load_case` takes the project root precisely so it walks components. Given only
    # a path, it would open whatever the link pointed at.
    write_case(tmp_path, _record())
    real_cases = tmp_path / "doc" / "audits" / "cases"
    moved = tmp_path / "moved-cases"
    real_cases.rename(moved)
    real_cases.symlink_to(moved, target_is_directory=True)
    with pytest.raises(CaseStorageError, match="symlink"):
        load_case(tmp_path, case_path(tmp_path, _record()))


def test_load_case_refuses_a_path_outside_the_project(tmp_path):
    outside = tmp_path.parent / "stray.md"
    outside.write_text("---\ndoc_kind: audit-case\n---\n", encoding="utf-8")
    with pytest.raises(CaseStorageError, match="outside the project root"):
        load_case(tmp_path, outside)


def test_load_case_refuses_a_file_with_no_frontmatter(tmp_path):
    path = write_case(tmp_path, _record())
    path.write_text("just a body, no frontmatter\n", encoding="utf-8")
    with pytest.raises(CaseStorageError, match="frontmatter"):
        load_case(tmp_path, path)


def test_load_case_refuses_malformed_yaml_as_a_storage_error(tmp_path):
    # `yaml.YAMLError` is not in this module's declared error channel; unwrapped, it
    # would reach the CLI as an unhandled exception.
    path = write_case(tmp_path, _record())
    path.write_text("---\ndoc_kind: [unclosed\n---\nbody\n", encoding="utf-8")
    with pytest.raises(CaseStorageError, match="not valid YAML"):
        load_case(tmp_path, path)


def test_load_case_refuses_a_path_outside_the_case_store(tmp_path):
    # Inside the project, but not in `cases/`. Cases are read only from the canonical
    # store, so a case-shaped file elsewhere in the tree is not one.
    (tmp_path / "doc").mkdir()
    stray = tmp_path / "doc" / "x.md"
    stray.write_text("---\ndoc_kind: audit-case\n---\n", encoding="utf-8")
    with pytest.raises(CaseStorageError, match="not under doc/audits/cases"):
        load_case(tmp_path, stray)


def test_write_never_unlinks_an_unowned_temp_file(tmp_path):
    # A writer cannot distinguish another active writer's temp from a crash leftover.
    # Writer-unique names make that distinction unnecessary: leave names this writer
    # did not create alone, and clean up only its own temp.
    record = _record()
    write_case(tmp_path, record)
    temp = case_path(tmp_path, record).with_name(
        f".{case_path(tmp_path, record).name}.tmp"
    )
    temp.write_text("stale", encoding="utf-8")
    write_case(tmp_path, record)
    assert temp.read_text(encoding="utf-8") == "stale"
    assert load_case(tmp_path, case_path(tmp_path, record)) == record


def test_the_stores_presence_check_is_anchored_like_every_other_operation(tmp_path):
    # `has()` is what decides whether a write happens, so it must not be the one
    # method that accepts a name `paths.py` never validated: an inline `lstat` would
    # answer about a file OUTSIDE the held directory and then write inside it.
    write_case(tmp_path, _record())
    with case_store(tmp_path, create=False) as store:
        with pytest.raises(CaseStorageError):
            store.has("../outside.md")
        with pytest.raises(CaseStorageError):
            store.has("nested/case.md")
