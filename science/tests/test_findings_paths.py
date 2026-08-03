# science/tests/test_findings_paths.py
import os
import stat
from pathlib import Path

import pytest

from science_tool.findings import paths as finding_paths
from science_tool.findings.paths import (
    PathExistsError,
    PathSafetyError,
    create_regular_file_at,
    exists_at,
    mkdir_inside,
    open_dir_anchored,
    open_dir_inside,
    open_dir_inside_if_present,
    open_lock_at,
    open_record_at,
    project_relative,
    read_inside_bounded,
    read_regular_fd,
    read_regular_file_at,
    replace_at,
    resolve_inside,
    unlink_at,
    write_all,
)


def test_open_dir_anchored_refuses_a_symlinked_component(tmp_path: Path) -> None:
    (tmp_path / "real").mkdir()
    (tmp_path / "real" / "leaf").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "real")
    with pytest.raises(PathSafetyError, match="component at"):
        open_dir_anchored(tmp_path / "link" / "leaf")


def test_open_dir_anchored_refuses_a_relative_directory() -> None:
    with pytest.raises(PathSafetyError, match="absolute"):
        open_dir_anchored(Path("relative/dir"))


@pytest.mark.parametrize(
    "plant",
    [
        pytest.param(lambda d, t: (d / "j").symlink_to(t), id="symlink"),
        pytest.param(lambda d, t: os.link(t, d / "j"), id="hardlink"),
        pytest.param(lambda d, _t: os.mkfifo(d / "j"), id="fifo"),
    ],
)
def test_open_record_at_refuses_a_planted_target(tmp_path: Path, plant) -> None:
    directory, target = tmp_path / "d", tmp_path / "target"
    directory.mkdir()
    target.write_text("", encoding="utf-8")
    plant(directory, target)
    reader = None
    if stat.S_ISFIFO(os.lstat(directory / "j").st_mode):
        reader = os.open(directory / "j", os.O_RDONLY | os.O_NONBLOCK)
    fd = open_dir_anchored(directory)
    try:
        with pytest.raises(PathSafetyError):
            open_record_at(fd, "j")
    finally:
        os.close(fd)
        if reader is not None:
            os.close(reader)
    assert target.read_text(encoding="utf-8") == ""


def test_open_record_at_does_not_create(tmp_path: Path) -> None:
    fd = open_dir_anchored(tmp_path)
    try:
        with pytest.raises(PathSafetyError):
            open_record_at(fd, "absent")
    finally:
        os.close(fd)
    assert not (tmp_path / "absent").exists()


def test_open_dir_anchored_create_stops_at_a_link_having_made_nothing(
    tmp_path: Path,
) -> None:
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "elsewhere")
    with pytest.raises(PathSafetyError, match="component at"):
        open_dir_anchored(tmp_path / "link" / "a" / "b", create=True)
    assert list((tmp_path / "elsewhere").iterdir()) == []


def test_read_regular_fd_reads_without_moving_the_descriptor_offset(tmp_path: Path) -> None:
    target = tmp_path / "f"
    target.write_text("payload", encoding="utf-8")
    descriptor = os.open(target, os.O_RDONLY)
    try:
        assert read_regular_fd(descriptor, 1024) == "payload"
        assert os.lseek(descriptor, 0, os.SEEK_CUR) == 0
    finally:
        os.close(descriptor)


def test_read_regular_file_bytes_at_preserves_non_utf8_bytes(tmp_path: Path) -> None:
    target = tmp_path / "actor-output"
    target.write_bytes(b"{\"invalid\": \"\xff\"}\n")
    descriptor = open_dir_anchored(tmp_path)
    try:
        assert finding_paths.read_regular_file_bytes_at(
            descriptor, target.name, 1024
        ) == target.read_bytes()
    finally:
        os.close(descriptor)


def test_write_all_completes_a_short_write(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "f"
    target.write_bytes(b"")
    descriptor = os.open(target, os.O_WRONLY | os.O_APPEND)
    real = os.write

    def one_byte_at_a_time(fd: int, data) -> int:
        return real(fd, bytes(data)[:1]) if fd == descriptor else real(fd, data)

    monkeypatch.setattr(os, "write", one_byte_at_a_time)
    try:
        write_all(descriptor, b"0123456789")
    finally:
        os.close(descriptor)
    assert target.read_bytes() == b"0123456789"

# --- resolve_inside: the check-only primitive -------------------------------------


def test_resolve_inside_returns_the_path_when_every_component_is_real(tmp_path):
    (tmp_path / "doc" / "audits" / "cases").mkdir(parents=True)
    target = tmp_path / "doc" / "audits" / "cases" / "x.md"
    target.write_text("hi", encoding="utf-8")
    assert resolve_inside(tmp_path, "doc/audits/cases/x.md") == target


def test_resolve_inside_refuses_a_symlinked_INTERMEDIATE_component(tmp_path):
    # The leaf is a real file; `doc/audits` is the link. A check that only looked at
    # the final component would pass this.
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "cases").mkdir(parents=True)
    (elsewhere / "cases" / "x.md").write_text("hi", encoding="utf-8")
    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "audits").symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(PathSafetyError, match="symlink"):
        resolve_inside(tmp_path, "doc/audits/cases/x.md")


def test_resolve_inside_refuses_a_symlinked_leaf(tmp_path):
    (tmp_path / "real.md").write_text("hi", encoding="utf-8")
    (tmp_path / "link.md").symlink_to(tmp_path / "real.md")
    with pytest.raises(PathSafetyError, match="symlink"):
        resolve_inside(tmp_path, "link.md")


def test_resolve_inside_refuses_absolute_and_traversal(tmp_path):
    for bad in ("/etc/passwd", "../outside.md", "a/../b"):
        with pytest.raises(PathSafetyError):
            resolve_inside(tmp_path, bad)


def test_resolve_inside_tolerates_a_not_yet_existing_leaf(tmp_path):
    (tmp_path / "doc" / "audits" / "cases").mkdir(parents=True)
    assert resolve_inside(tmp_path, "doc/audits/cases/new.md").name == "new.md"


def test_resolve_inside_judges_the_leaf_through_the_held_parent_descriptor(
    tmp_path,
    monkeypatch,
):
    """A parent pathname swap cannot change which leaf is judged.

    The directory initially named ``checked`` contains a symlink and therefore must
    be refused.  At the first leaf ``lstat`` we move that directory aside and put a
    different, all-regular directory under the pathname.  A pathname walk follows
    the replacement and accepts it; a descriptor walk judges the symlink through the
    parent descriptor it already opened.
    """
    checked = tmp_path / "checked"
    replacement = tmp_path / "replacement"
    moved = tmp_path / "moved"
    checked.mkdir()
    replacement.mkdir()
    (tmp_path / "outside.md").write_text("outside", encoding="utf-8")
    (checked / "leaf.md").symlink_to(tmp_path / "outside.md")
    (replacement / "leaf.md").write_text("replacement", encoding="utf-8")

    real_lstat = os.lstat
    swapped = False

    def swapping_lstat(path, *args, **kwargs):
        nonlocal swapped
        if not swapped and os.fspath(path).endswith("leaf.md"):
            checked.rename(moved)
            replacement.rename(checked)
            swapped = True
        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", swapping_lstat)

    with pytest.raises(PathSafetyError, match="symlink"):
        resolve_inside(tmp_path, "checked/leaf.md")

    assert swapped


@pytest.mark.parametrize("dangling", [False, True])
def test_resolve_inside_refuses_leaf_links_even_when_the_target_is_outside_or_absent(
    tmp_path,
    dangling,
):
    parent = tmp_path / "doc"
    parent.mkdir()
    target = tmp_path.parent / f"{tmp_path.name}-outside.md"
    if not dangling:
        target.write_text("outside", encoding="utf-8")
    (parent / "leaf.md").symlink_to(target)

    with pytest.raises(PathSafetyError, match="symlink"):
        resolve_inside(tmp_path, "doc/leaf.md")


def test_resolve_inside_refuses_a_project_root_replaced_by_a_symlink_during_capture(
    tmp_path,
    monkeypatch,
):
    project = tmp_path / "project"
    moved_project = tmp_path / "moved-project"
    target = tmp_path / "outside"
    (project / "doc").mkdir(parents=True)
    (target / "doc").mkdir(parents=True)
    (project / "outside.md").write_text("outside", encoding="utf-8")
    (project / "doc" / "leaf.md").symlink_to(project / "outside.md")
    (target / "doc" / "leaf.md").write_text("replacement", encoding="utf-8")

    real_open = finding_paths.os.open
    swapped = False

    def swapping_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        value = os.fspath(path)
        if not swapped and (
            value == os.fspath(project)
            or (value == project.name and dir_fd is not None)
        ):
            project.rename(moved_project)
            project.symlink_to(target, target_is_directory=True)
            swapped = True
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(finding_paths.os, "open", swapping_open)

    with pytest.raises(PathSafetyError, match="project root"):
        resolve_inside(project, "doc/leaf.md")

    assert swapped


# --- mkdir_inside: refuse before mutating ------------------------------------------


def test_mkdir_inside_creates_the_whole_chain(tmp_path):
    created = mkdir_inside(tmp_path, "doc/audits/cases")
    assert created == tmp_path / "doc" / "audits" / "cases"
    assert created.is_dir()
    # Idempotent: an existing chain is not an error.
    assert mkdir_inside(tmp_path, "doc/audits/cases") == created


def test_mkdir_inside_refuses_a_symlinked_component_AND_CREATES_NOTHING_BEYOND_IT(
    tmp_path,
):
    # This is the ordering bug in its pure form. `doc/audits` is a link to a directory
    # that does NOT contain `cases/`. `Path.mkdir(parents=True)` would follow the link
    # and create `cases/` in the target -- outside the project -- and only then would a
    # validation step refuse the path, with the directory already made.
    target = tmp_path / "elsewhere"
    target.mkdir()
    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "audits").symlink_to(target, target_is_directory=True)

    with pytest.raises(PathSafetyError, match="symlink or not a directory"):
        mkdir_inside(tmp_path, "doc/audits/cases")

    assert list(target.iterdir()) == [], "a directory was created in the link target"


def test_mkdir_inside_refuses_a_component_that_is_a_regular_file(tmp_path):
    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "audits").write_text("not a directory", encoding="utf-8")
    with pytest.raises(PathSafetyError, match="symlink or not a directory"):
        mkdir_inside(tmp_path, "doc/audits/cases")


# --- open_dir_inside_if_present: absence and access, from ONE walk ------------------


def test_if_present_yields_a_descriptor_for_a_real_chain(tmp_path):
    (tmp_path / "doc" / "audits" / "cases").mkdir(parents=True)
    with open_dir_inside_if_present(tmp_path, "doc/audits/cases") as dir_fd:
        assert dir_fd is not None
        assert os.listdir(dir_fd) == []


def test_if_present_yields_None_only_when_a_component_is_genuinely_missing(tmp_path):
    with open_dir_inside_if_present(tmp_path, "doc/audits/cases") as dir_fd:
        assert dir_fd is None
    (tmp_path / "doc").mkdir()
    with open_dir_inside_if_present(tmp_path, "doc/audits/cases") as dir_fd:
        assert dir_fd is None


def test_if_present_REFUSES_an_intermediate_link_whose_target_lacks_the_rest(tmp_path):
    # THE silent-empty case. `doc/audits` is a link to a real directory that has no
    # `cases/`. `lstat` on the full pathname follows `doc/audits`, finds no `cases`,
    # and raises FileNotFoundError -- which a caller reads as "nothing stored". The
    # store was redirected, not emptied, and that must be loud.
    target = tmp_path / "elsewhere"
    target.mkdir()
    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "audits").symlink_to(target, target_is_directory=True)

    with pytest.raises(FileNotFoundError):
        os.lstat(tmp_path / "doc" / "audits" / "cases")   # what the naive check does

    with pytest.raises(PathSafetyError, match="symlink or not a directory"):
        with open_dir_inside_if_present(tmp_path, "doc/audits/cases"):
            pass


def test_if_present_refuses_a_DANGLING_intermediate_link(tmp_path):
    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "audits").symlink_to(tmp_path / "gone", target_is_directory=True)
    with pytest.raises(PathSafetyError, match="symlink or not a directory"):
        with open_dir_inside_if_present(tmp_path, "doc/audits/cases"):
            pass


def test_if_present_refuses_a_DANGLING_final_link(tmp_path):
    (tmp_path / "doc" / "audits").mkdir(parents=True)
    (tmp_path / "doc" / "audits" / "cases").symlink_to(
        tmp_path / "gone", target_is_directory=True
    )
    with pytest.raises(PathSafetyError, match="symlink or not a directory"):
        with open_dir_inside_if_present(tmp_path, "doc/audits/cases"):
            pass


def test_an_inaccessible_project_root_is_a_safety_error_not_absence(tmp_path):
    # "The project does not exist" must not be reachable through the same branch as
    # "the project has no cases yet", or a typo'd root reports a clean audit.
    with pytest.raises(PathSafetyError, match="project root"):
        with open_dir_inside_if_present(tmp_path / "no-such-project", "doc"):
            pass


def test_an_unresolvable_project_root_is_a_path_error_too(tmp_path, monkeypatch):
    """`resolve()` is a syscall, not string arithmetic.

    It calls `getcwd` for a relative path, so a deleted working directory raises
    `OSError` there -- outside every `except PathSafetyError` that `storage.py` and
    `ingest.py` write to build their own errors. A refusal nobody can catch is not a
    refusal, so the resolve is inside the channel like everything else here.
    """
    doomed = tmp_path / "doomed"
    doomed.mkdir()
    monkeypatch.chdir(doomed)
    doomed.rmdir()

    with pytest.raises(PathSafetyError, match="could not resolve project root"):
        mkdir_inside(Path("relative-root"), "doc/audits/cases")


def test_project_root_parent_traversal_is_refused_not_lexically_collapsed(tmp_path):
    base = tmp_path / "base"
    project = tmp_path / "project"
    base.mkdir()
    project.mkdir()

    with pytest.raises(PathSafetyError, match=r"\.\."):
        mkdir_inside(base / ".." / "project", "doc/audits/cases")

    assert not (project / "doc").exists()


def test_project_root_swap_to_a_symlink_refuses_before_creating_anything(
    tmp_path, monkeypatch
):
    project = tmp_path / "project"
    moved_project = tmp_path / "moved-project"
    target = tmp_path / "elsewhere"
    project.mkdir()
    target.mkdir()

    real_open = finding_paths.os.open
    swapped = False

    def swapping_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        value = os.fspath(path)
        if not swapped and (
            value == os.fspath(project)
            or (value == project.name and dir_fd is not None)
        ):
            project.rename(moved_project)
            project.symlink_to(target, target_is_directory=True)
            swapped = True
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(finding_paths.os, "open", swapping_open)

    with pytest.raises(PathSafetyError, match="project root"):
        mkdir_inside(project, "doc/audits/cases")

    assert swapped
    assert list(target.iterdir()) == [], "creation followed the swapped root symlink"


def test_project_root_is_captured_before_replacement_by_another_real_directory(
    tmp_path,
    monkeypatch,
):
    project = tmp_path / "project"
    moved_project = tmp_path / "moved-project"
    replacement = tmp_path / "replacement"
    (project / "doc").mkdir(parents=True)
    (replacement / "doc").mkdir(parents=True)
    (project / "doc" / "leaf.md").symlink_to(tmp_path / "outside.md")
    (replacement / "doc" / "leaf.md").write_text("outside tree", encoding="utf-8")
    original_inode = project.stat().st_ino

    real_open = finding_paths.os.open
    swapped = False

    def swap() -> None:
        nonlocal swapped
        project.rename(moved_project)
        replacement.rename(project)
        swapped = True

    def swapping_open(path, flags, mode=0o777, *, dir_fd=None):
        value = os.fspath(path)
        if not swapped and value == os.fspath(project):
            # The vulnerable resolve-then-open shape reaches this absolute reopen
            # without a descriptor. Replace the root before that reopen.
            swap()
            return real_open(path, flags, mode, dir_fd=dir_fd)
        if not swapped and value == project.name and dir_fd is not None:
            # A component walk captures the real directory first. Replacing its
            # pathname afterwards must not redirect the remaining judgment.
            descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
            assert os.fstat(descriptor).st_ino == original_inode
            try:
                swap()
            except BaseException:
                os.close(descriptor)
                raise
            return descriptor
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(finding_paths.os, "open", swapping_open)

    with pytest.raises(PathSafetyError, match="symlink"):
        resolve_inside(project, "doc/leaf.md")

    assert swapped
    assert (project / "doc" / "leaf.md").read_text(encoding="utf-8") == "outside tree"


def test_project_root_walk_stays_anchored_when_an_intermediate_ancestor_is_swapped(
    tmp_path,
    monkeypatch,
):
    container = tmp_path / "container"
    ancestor = container / "owner"
    moved_ancestor = container / "moved-owner"
    replacement_ancestor = container / "replacement-owner"
    project = ancestor / "project"
    replacement_project = replacement_ancestor / "project"
    (project / "doc").mkdir(parents=True)
    (replacement_project / "doc").mkdir(parents=True)
    (project / "doc" / "leaf.md").symlink_to(tmp_path / "outside.md")
    (replacement_project / "doc" / "leaf.md").write_text(
        "outside tree",
        encoding="utf-8",
    )
    original_ancestor_inode = ancestor.stat().st_ino

    real_open = finding_paths.os.open
    swapped = False

    def swap() -> None:
        nonlocal swapped
        ancestor.rename(moved_ancestor)
        replacement_ancestor.rename(ancestor)
        swapped = True

    def swapping_open(path, flags, mode=0o777, *, dir_fd=None):
        value = os.fspath(path)
        if not swapped and value == os.fspath(project):
            # The vulnerable absolute reopen follows the replacement ancestor.
            swap()
            return real_open(path, flags, mode, dir_fd=dir_fd)
        if not swapped and value == ancestor.name and dir_fd is not None:
            # The safe walk opens the ancestor through its held parent before the
            # rename, so later components remain below the captured directory.
            descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
            assert os.fstat(descriptor).st_ino == original_ancestor_inode
            try:
                swap()
            except BaseException:
                os.close(descriptor)
                raise
            return descriptor
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(finding_paths.os, "open", swapping_open)

    with pytest.raises(PathSafetyError, match="symlink"):
        resolve_inside(project, "doc/leaf.md")

    assert swapped
    assert (
        project / "doc" / "leaf.md"
    ).read_text(encoding="utf-8") == "outside tree"


# --- leaf names: a `*_at` argument is one entry, never a path -----------------------


def test_every_at_operation_refuses_a_name_that_escapes_the_anchor(tmp_path):
    # `openat` resolves relative to the descriptor, so `../outside.txt` walks straight
    # back out and the anchoring guarantee is void. Reproduced before this check
    # existed: the read below returned the outside file's contents.
    (tmp_path / "anchored").mkdir()
    (tmp_path / "outside.txt").write_text("SECRET", encoding="utf-8")
    with open_dir_inside(tmp_path, "anchored") as dir_fd:
        for bad in ("../outside.txt", "a/b", "", ".", "..", "a\\b"):
            with pytest.raises(PathSafetyError):
                exists_at(dir_fd, bad)
            with pytest.raises(PathSafetyError):
                read_regular_file_at(dir_fd, bad, 1024)
            with pytest.raises(PathSafetyError):
                create_regular_file_at(dir_fd, bad)
            with pytest.raises(PathSafetyError):
                open_lock_at(dir_fd, bad)
            with pytest.raises(PathSafetyError):
                unlink_at(dir_fd, bad)
            with pytest.raises(PathSafetyError):
                replace_at(dir_fd, bad, "ok.md")
            with pytest.raises(PathSafetyError):
                replace_at(dir_fd, "ok.md", bad)
    assert (tmp_path / "outside.txt").read_text(encoding="utf-8") == "SECRET"


def test_exists_at_reports_a_dangling_link_as_present(tmp_path):
    # `stat` would follow the link, find nothing, and answer "absent" -- and the
    # caller would then write straight through it. `lstat` sees the entry itself.
    (tmp_path / "anchored").mkdir()
    (tmp_path / "anchored" / "case.md").symlink_to(tmp_path / "gone.md")
    with open_dir_inside(tmp_path, "anchored") as dir_fd:
        assert exists_at(dir_fd, "case.md") is True
        assert exists_at(dir_fd, "absent.md") is False


# --- project_relative ---------------------------------------------------------------


def test_project_relative_returns_the_relative_spelling(tmp_path):
    assert project_relative(tmp_path, tmp_path / "doc" / "x.md") == "doc/x.md"
    assert project_relative(tmp_path, Path("doc/x.md")) == "doc/x.md"


def test_project_relative_refuses_a_path_outside_the_project(tmp_path):
    outside = tmp_path.parent / "not-in-here.json"
    with pytest.raises(PathSafetyError, match="outside the project root"):
        project_relative(tmp_path, outside)
    with pytest.raises(PathSafetyError, match=r"\.\."):
        project_relative(tmp_path, tmp_path / ".." / "escape.json")


# --- reads: regular files only, never blocking, never following ---------------------


def test_read_inside_bounded_reads_a_real_file(tmp_path):
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / "report.json").write_text("{}", encoding="utf-8")
    assert read_inside_bounded(tmp_path, tmp_path / "runs" / "report.json", 1024) == "{}"


def test_read_inside_bounded_retries_short_reads_until_eof(tmp_path, monkeypatch):
    path = tmp_path / "report.json"
    payload = "complete despite short reads"
    path.write_text(payload, encoding="utf-8")
    real_pread = finding_paths.os.pread

    def short_read(descriptor, max_bytes, offset):
        return real_pread(descriptor, min(max_bytes, 2), offset)

    monkeypatch.setattr(finding_paths.os, "pread", short_read)

    assert read_inside_bounded(tmp_path, path, 1024) == payload


def test_read_inside_bounded_detects_growth_past_the_bound(tmp_path, monkeypatch):
    path = tmp_path / "report.json"
    path.write_bytes(b"0123456789")
    real_pread = finding_paths.os.pread
    grew = False

    def short_read_then_grow(descriptor, max_bytes, offset):
        nonlocal grew
        chunk = real_pread(descriptor, min(max_bytes, 5), offset)
        if not grew:
            with path.open("ab") as handle:
                handle.write(b"!")
            grew = True
        return chunk

    monkeypatch.setattr(finding_paths.os, "pread", short_read_then_grow)

    with pytest.raises(PathSafetyError, match="exceeds"):
        read_inside_bounded(tmp_path, path, 10)


def test_read_inside_bounded_refuses_a_symlinked_PARENT(tmp_path):
    # The leaf is a real file inside the link target, so a leaf-only `O_NOFOLLOW`
    # check reads it happily.
    target = tmp_path / "elsewhere"
    target.mkdir()
    (target / "report.json").write_text("{}", encoding="utf-8")
    (tmp_path / "runs").symlink_to(target, target_is_directory=True)
    with pytest.raises(PathSafetyError, match="symlink or not a directory"):
        read_inside_bounded(tmp_path, tmp_path / "runs" / "report.json", 1024)


def test_read_inside_bounded_refuses_a_symlinked_leaf(tmp_path):
    (tmp_path / "real.json").write_text("{}", encoding="utf-8")
    (tmp_path / "link.json").symlink_to(tmp_path / "real.json")
    with pytest.raises(PathSafetyError, match="following a symlink"):
        read_inside_bounded(tmp_path, tmp_path / "link.json", 1024)


def test_read_inside_bounded_refuses_an_oversize_file(tmp_path):
    (tmp_path / "a.json").write_text("x" * 100, encoding="utf-8")
    with pytest.raises(PathSafetyError, match="exceeds"):
        read_inside_bounded(tmp_path, tmp_path / "a.json", 10)


def test_read_inside_bounded_refuses_invalid_utf8_as_a_path_error(tmp_path):
    # A raw UnicodeDecodeError would escape this module's declared error channel and
    # reach the CLI as an unhandled exception.
    (tmp_path / "a.json").write_bytes(b"\xff\xfe not utf-8")
    with pytest.raises(PathSafetyError, match="not valid UTF-8"):
        read_inside_bounded(tmp_path, tmp_path / "a.json", 1024)


def test_read_refuses_a_FIFO_instead_of_blocking_on_it(tmp_path):
    # A plain O_RDONLY on a FIFO with no writer blocks forever. O_NONBLOCK plus an
    # S_ISREG check turns a hang into a refusal.
    os.mkfifo(tmp_path / "report.json")
    with pytest.raises(PathSafetyError, match="not a regular file"):
        read_inside_bounded(tmp_path, tmp_path / "report.json", 1024)


def test_read_refuses_a_directory(tmp_path):
    (tmp_path / "a.json").mkdir()
    with pytest.raises(PathSafetyError, match="not a regular file"):
        read_inside_bounded(tmp_path, tmp_path / "a.json", 1024)


# --- writes and locks: never truncate anything --------------------------------------


def test_create_regular_file_at_refuses_a_planted_HARD_LINK(tmp_path):
    # O_NOFOLLOW is silent about hard links, so an O_TRUNC open here would empty
    # `victim.txt` through its second name. O_EXCL refuses instead.
    victim = tmp_path / "victim.txt"
    victim.write_text("KEEP", encoding="utf-8")
    os.link(victim, tmp_path / ".case.md.tmp")
    with open_dir_inside(tmp_path, "") as dir_fd:
        with pytest.raises(PathExistsError, match="already exists"):
            create_regular_file_at(dir_fd, ".case.md.tmp")
    assert victim.read_text(encoding="utf-8") == "KEEP"


def test_an_existing_entry_raises_the_narrow_error_a_retry_may_catch(tmp_path):
    # `PathExistsError` is a `PathSafetyError`, but catching the base class around an
    # exclusive create would "recover" from a redirected directory by deleting a name.
    (tmp_path / "x.tmp").write_text("", encoding="utf-8")
    with open_dir_inside(tmp_path, "") as dir_fd:
        with pytest.raises(PathExistsError):
            create_regular_file_at(dir_fd, "x.tmp")
    assert issubclass(PathExistsError, PathSafetyError)


def test_open_lock_at_does_not_truncate_an_existing_file(tmp_path):
    victim = tmp_path / "victim.txt"
    victim.write_text("KEEP", encoding="utf-8")
    os.link(victim, tmp_path / ".ingest.lock")
    with open_dir_inside(tmp_path, "") as dir_fd:
        with pytest.raises(PathSafetyError, match="links"):
            open_lock_at(dir_fd, ".ingest.lock")
    assert victim.read_text(encoding="utf-8") == "KEEP"


def test_open_lock_at_refuses_a_HARD_LINKED_lock(tmp_path):
    # Not truncating prevents the data loss, but a hard-linked lock is still a lock on
    # somebody else's inode: whoever planted the link chooses what this project
    # serializes against, and can hold that flock to stall or observe ingestion.
    victim = tmp_path / "elsewhere.dat"
    victim.write_text("x", encoding="utf-8")
    os.link(victim, tmp_path / ".ingest.lock")
    with open_dir_inside(tmp_path, "") as dir_fd:
        with pytest.raises(PathSafetyError, match="has 2 links"):
            open_lock_at(dir_fd, ".ingest.lock")


def test_open_lock_at_accepts_a_lock_the_project_solely_owns(tmp_path):
    with open_dir_inside(tmp_path, "") as dir_fd:
        first = open_lock_at(dir_fd, ".ingest.lock")   # creates it
        os.close(first)
        second = open_lock_at(dir_fd, ".ingest.lock")  # reopens the same one
        os.close(second)


def test_open_lock_at_refuses_a_FIFO(tmp_path):
    os.mkfifo(tmp_path / ".ingest.lock")
    with open_dir_inside(tmp_path, "") as dir_fd:
        with pytest.raises(PathSafetyError, match="not a regular file"):
            open_lock_at(dir_fd, ".ingest.lock")


def test_open_lock_at_refuses_a_symlinked_lock(tmp_path):
    (tmp_path / "outside.lock").write_text("", encoding="utf-8")
    (tmp_path / ".ingest.lock").symlink_to(tmp_path / "outside.lock")
    with open_dir_inside(tmp_path, "") as dir_fd:
        with pytest.raises(PathSafetyError, match="could not open lock"):
            open_lock_at(dir_fd, ".ingest.lock")


def test_a_held_descriptor_keeps_operating_in_the_directory_it_verified(tmp_path):
    # THE reason operations are anchored rather than re-resolved. The pathname
    # `real/` is swapped for a different directory after the walk; a pathname-based
    # write would land in the attacker's directory, the descriptor does not.
    (tmp_path / "real").mkdir()
    (tmp_path / "evil").mkdir()
    with open_dir_inside(tmp_path, "real") as dir_fd:
        (tmp_path / "real").rename(tmp_path / "moved")
        (tmp_path / "evil").rename(tmp_path / "real")

        descriptor = create_regular_file_at(dir_fd, ".x.tmp")
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write("written")
        replace_at(dir_fd, ".x.tmp", "x.md")
        assert read_regular_file_at(dir_fd, "x.md", 1024) == "written"

    assert (tmp_path / "moved" / "x.md").exists(), "the write followed the pathname"
    assert not (tmp_path / "real" / "x.md").exists()
