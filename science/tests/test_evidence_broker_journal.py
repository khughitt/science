from __future__ import annotations

import fcntl
import json
import os
import stat
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from science_model.evidence_broker import (
    MAX_BUDGET,
    MAX_INLINE_INPUTS,
    MAX_INLINE_LINES,
    MAX_TARGET_CHARS,
    ExposureEntry,
    InlineInput,
    Outcome,
)
from science_tool.autonomy.baseline import BaselineError
from science_tool.evidence_broker import journal as journal_module
from science_tool.evidence_broker.journal import (
    MAX_ENTRY_BYTES,
    MAX_JOURNAL_BYTES,
    JournalError,
    append_request,
    count_requests,
    create_journal,
    journal_lock,
    open_journal,
    read_journal,
)
from science_tool.findings.paths import open_lock_at

COMMIT = "a" * 40


def _entry(target: str = "a.md", outcome: Outcome = Outcome.SERVED) -> ExposureEntry:
    return ExposureEntry(
        op="read", target=target, commit=COMMIT, sha256="e" * 64, outcome=outcome
    )


def _append(journal: Path, project: Path, entry: ExposureEntry) -> None:
    with open_journal(journal, project_root=project) as handle:
        append_request(handle, entry)


def _read(journal: Path, project: Path) -> tuple[ExposureEntry, ...]:
    with open_journal(journal, project_root=project) as handle:
        return read_journal(handle)


def test_create_then_append_then_read(tmp_path: Path) -> None:
    journal, project = tmp_path / "j.jsonl", tmp_path / "project"
    project.mkdir()
    create_journal(
        journal,
        project_root=project,
        inline=(InlineInput(target="prompt.md", sha256="f" * 64, lines=12),),
    )
    _append(journal, project, _entry())
    entries = _read(journal, project)
    assert [entry.op for entry in entries] == ["inline", "read"]
    assert count_requests(entries) == 1


def test_inline_seeding_costs_nothing(tmp_path: Path) -> None:
    journal, project = tmp_path / "j.jsonl", tmp_path / "project"
    project.mkdir()
    inline = tuple(
        InlineInput(target=f"in{number}.md", sha256="f" * 64, lines=1)
        for number in range(5)
    )
    create_journal(journal, project_root=project, inline=inline)
    assert count_requests(_read(journal, project)) == 0


def test_a_refusal_is_counted(tmp_path: Path) -> None:
    journal, project = tmp_path / "j.jsonl", tmp_path / "project"
    project.mkdir()
    create_journal(journal, project_root=project, inline=())
    _append(journal, project, _entry(outcome=Outcome.REFUSED))
    assert count_requests(_read(journal, project)) == 1


@pytest.mark.parametrize(
    "plant",
    [
        pytest.param(lambda journal, decoy: journal.symlink_to(decoy), id="symlink"),
        pytest.param(lambda journal, decoy: os.link(decoy, journal), id="hardlink"),
        pytest.param(lambda journal, _decoy: os.mkfifo(journal), id="fifo"),
    ],
)
def test_a_journal_replaced_after_creation_is_refused_not_followed(
    tmp_path: Path, plant
) -> None:
    journal, project = tmp_path / "run" / "j.jsonl", tmp_path / "project"
    project.mkdir()
    journal.parent.mkdir()
    decoy = tmp_path / "decoy.md"
    decoy.write_text("", encoding="utf-8")
    create_journal(journal, project_root=project, inline=())
    journal.unlink()
    plant(journal, decoy)
    reader = None
    if stat.S_ISFIFO(os.lstat(journal).st_mode):
        reader = os.open(journal, os.O_RDONLY | os.O_NONBLOCK)
    try:
        with pytest.raises(JournalError):
            _append(journal, project, _entry())
    finally:
        if reader is not None:
            os.close(reader)
    assert decoy.read_text(encoding="utf-8") == ""


def test_a_symlinked_run_directory_is_refused(tmp_path: Path) -> None:
    journal, project = tmp_path / "run" / "j.jsonl", tmp_path / "project"
    project.mkdir()
    (tmp_path / "real").mkdir()
    (tmp_path / "run").symlink_to(tmp_path / "real")
    with pytest.raises(JournalError, match="run directory"):
        _read(journal, project)


def test_a_journal_larger_than_the_bound_is_an_error(tmp_path: Path) -> None:
    journal, project = tmp_path / "run" / "j.jsonl", tmp_path / "project"
    project.mkdir()
    journal.parent.mkdir()
    create_journal(journal, project_root=project, inline=())
    os.truncate(journal, MAX_JOURNAL_BYTES + 1)
    with pytest.raises(JournalError, match="could not read journal.*exceeds"):
        _read(journal, project)


def test_an_entry_over_the_line_bound_is_refused_before_it_is_written(tmp_path: Path) -> None:
    journal, project = tmp_path / "run" / "j.jsonl", tmp_path / "project"
    project.mkdir()
    journal.parent.mkdir()
    create_journal(journal, project_root=project, inline=())
    forged = ExposureEntry.model_construct(
        op="read",
        target="a" * MAX_ENTRY_BYTES,
        pathspec=None,
        commit=COMMIT,
        sha256="e" * 64,
        outcome=Outcome.SERVED,
    )
    with pytest.raises(JournalError, match="bound"):
        _append(journal, project, forged)
    assert _read(journal, project) == ()


def test_the_bound_admits_the_actual_maximally_encoded_events() -> None:
    astral = "\U00010000" * MAX_TARGET_CHARS
    request = ExposureEntry(
        op="history",
        target=astral,
        pathspec=astral,
        commit=COMMIT,
        sha256="e" * 64,
        outcome=Outcome.MISS_NO_COMMITS,
    )
    inline = InlineInput(target=astral, sha256="e" * 64, lines=MAX_INLINE_LINES)
    request_line = (journal_module._encode_request(request) + "\n").encode()
    inline_line = (journal_module._encode_inline(inline) + "\n").encode()
    assert len(request_line) <= MAX_ENTRY_BYTES
    assert len(inline_line) <= MAX_ENTRY_BYTES
    assert (
        MAX_BUDGET * len(request_line) + MAX_INLINE_INPUTS * len(inline_line)
        <= MAX_JOURNAL_BYTES
    )


def test_an_over_bound_inline_event_is_refused_before_the_journal_is_created(
    tmp_path: Path,
) -> None:
    journal, project = tmp_path / "run" / "j.jsonl", tmp_path / "project"
    project.mkdir()
    forged = InlineInput.model_construct(target="a.md", sha256="e" * MAX_ENTRY_BYTES, lines=1)
    with pytest.raises(JournalError, match="bound"):
        create_journal(journal, project_root=project, inline=(forged,))
    assert not journal.parent.exists()


def test_the_journal_read_and_the_append_address_one_inode(tmp_path: Path) -> None:
    journal, project = tmp_path / "run" / "j.jsonl", tmp_path / "project"
    project.mkdir()
    journal.parent.mkdir()
    create_journal(journal, project_root=project, inline=())
    with open_journal(journal, project_root=project) as handle:
        append_request(handle, _entry("first.md"))
        assert count_requests(read_journal(handle)) == 1
        journal.unlink()
        journal.write_text("", encoding="utf-8")
        append_request(handle, _entry("second.md"))
        assert count_requests(read_journal(handle)) == 2
    assert journal.read_text(encoding="utf-8") == ""


def test_a_short_write_does_not_truncate_an_entry(tmp_path: Path, monkeypatch) -> None:
    journal, project = tmp_path / "run" / "j.jsonl", tmp_path / "project"
    project.mkdir()
    journal.parent.mkdir()
    create_journal(journal, project_root=project, inline=())
    real = os.write
    with open_journal(journal, project_root=project) as handle:

        def one_byte_at_a_time(fd: int, data) -> int:
            return real(fd, bytes(data)[:1]) if fd == handle.fd else real(fd, data)

        monkeypatch.setattr(os, "write", one_byte_at_a_time)
        append_request(handle, _entry())
        monkeypatch.undo()
        assert count_requests(read_journal(handle)) == 1


def test_create_makes_nothing_through_a_symlinked_ancestor(tmp_path: Path) -> None:
    project, elsewhere = tmp_path / "project", tmp_path / "elsewhere"
    project.mkdir()
    elsewhere.mkdir()
    (tmp_path / "cp").symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(JournalError, match="run directory"):
        create_journal(tmp_path / "cp" / "run-x" / "j.jsonl", project_root=project, inline=())
    assert list(elsewhere.iterdir()) == []


def test_creating_over_an_existing_journal_refuses(tmp_path: Path) -> None:
    journal, project = tmp_path / "j.jsonl", tmp_path / "project"
    project.mkdir()
    create_journal(journal, project_root=project, inline=())
    with pytest.raises(JournalError, match="already"):
        create_journal(journal, project_root=project, inline=())


def test_a_journal_inside_the_project_refuses(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    with pytest.raises(BaselineError, match="inside the project"):
        create_journal(project / "j.jsonl", project_root=project, inline=())


def test_a_truncated_line_is_an_error_not_an_empty_journal(tmp_path: Path) -> None:
    journal, project = tmp_path / "j.jsonl", tmp_path / "project"
    project.mkdir()
    create_journal(journal, project_root=project, inline=())
    _append(journal, project, _entry())
    journal.write_text(journal.read_text(encoding="utf-8")[:-8], encoding="utf-8")
    with pytest.raises(JournalError):
        _read(journal, project)


def test_appends_never_rewrite(tmp_path: Path) -> None:
    journal, project = tmp_path / "j.jsonl", tmp_path / "project"
    project.mkdir()
    create_journal(journal, project_root=project, inline=())
    _append(journal, project, _entry("a.md"))
    first = journal.read_text(encoding="utf-8")
    _append(journal, project, _entry("b.md"))
    assert journal.read_text(encoding="utf-8").startswith(first)


@pytest.mark.parametrize("payload", ["[]", "null", "1", '"a string"'])
def test_valid_json_of_the_wrong_shape_is_a_journal_error(
    tmp_path: Path, payload: str
) -> None:
    journal, project = tmp_path / "j.jsonl", tmp_path / "project"
    project.mkdir()
    create_journal(journal, project_root=project, inline=())
    journal.write_text(payload + "\n", encoding="utf-8")
    with pytest.raises(JournalError, match="JSON object"):
        _read(journal, project)


def test_the_journal_is_one_object_per_line(tmp_path: Path) -> None:
    journal, project = tmp_path / "j.jsonl", tmp_path / "project"
    project.mkdir()
    create_journal(journal, project_root=project, inline=())
    _append(journal, project, _entry())
    lines = journal.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["event"] == "request"


def test_journal_lock_blocks_a_second_lock(tmp_path: Path) -> None:
    journal, project = tmp_path / "j.jsonl", tmp_path / "project"
    project.mkdir()
    create_journal(journal, project_root=project, inline=())
    with journal_lock(journal, project_root=project) as handle:
        competing = open_lock_at(handle.dir_fd, handle.name + ".lock")
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(competing, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(competing)


def test_two_locked_writers_leave_complete_lines(tmp_path: Path) -> None:
    """Smoke test only: short regular-file appends may stay atomic even without the lock."""
    journal, project = tmp_path / "j.jsonl", tmp_path / "project"
    project.mkdir()
    create_journal(journal, project_root=project, inline=())

    def append_many(prefix: str) -> None:
        with journal_lock(journal, project_root=project) as handle:
            for number in range(50):
                append_request(handle, _entry(f"{prefix}-{number}.md"))

    with ThreadPoolExecutor(max_workers=2) as pool:
        tuple(pool.map(append_many, ("a", "b")))
    assert len(_read(journal, project)) == 100
