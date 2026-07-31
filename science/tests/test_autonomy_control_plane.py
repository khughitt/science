from __future__ import annotations

import re
from pathlib import Path

import pytest

from science_tool.autonomy.baseline import BaselineError
from science_tool.autonomy.control_plane import (
    CONTROL_PLANE_ENV,
    ControlPlaneError,
    control_plane_root,
    project_key,
    project_metadata_path,
    run_dir,
    run_slug,
)

HANDLE = "2026-07-30-review-plans-a3f1"


def _project(tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    (root / "doc").mkdir(parents=True)
    (root / "science.yaml").write_text(f"name: {name}\n", encoding="utf-8")
    return root


def test_run_dir_is_a_pure_function_of_project_root_and_handle(tmp_path, monkeypatch):
    monkeypatch.setenv(CONTROL_PLANE_ENV, str(tmp_path / "cp"))
    project = _project(tmp_path, "alpha")

    assert run_dir(project, HANDLE) == run_dir(project, HANDLE)
    assert not (tmp_path / "cp").exists(), "resolving a path must create nothing"


def test_two_projects_sharing_a_run_slug_get_different_directories(tmp_path, monkeypatch):
    """A run id is <date>-<agent>-<short-id>. Two projects running the same agent role on
    the same day with the same disambiguator produce the same slug; a single global root
    would let one project's session resolve the other's baseline."""
    monkeypatch.setenv(CONTROL_PLANE_ENV, str(tmp_path / "cp"))

    assert run_dir(_project(tmp_path, "alpha"), HANDLE) != run_dir(
        _project(tmp_path, "beta"), HANDLE
    )


def test_a_fork_does_not_resolve_its_parents_run(tmp_path, monkeypatch):
    """A fork inherits its parent's science.yaml name outright, and shares its base
    commit -- so a collision here would replay successfully and prove nothing."""
    monkeypatch.setenv(CONTROL_PLANE_ENV, str(tmp_path / "cp"))
    parent = _project(tmp_path, "alpha")
    fork = tmp_path / "fork-of-alpha"
    fork.mkdir()
    (fork / "science.yaml").write_text("name: alpha\n", encoding="utf-8")

    assert run_dir(parent, HANDLE) != run_dir(fork, HANDLE)


@pytest.mark.parametrize(
    "hostile",
    ["../../escape", "a/b/c", "x" * 4096, "..", "with\nnewline"],
)
def test_a_hostile_project_name_changes_no_path(tmp_path, monkeypatch, hostile):
    """ProjectConfig.name is an unconstrained str on a model with extra="allow". The
    digest is the whole directory name precisely so a name can never reach a path."""
    monkeypatch.setenv(CONTROL_PLANE_ENV, str(tmp_path / "cp"))
    project = _project(tmp_path, "alpha")
    before = run_dir(project, HANDLE)

    (project / "science.yaml").write_text(f"name: {hostile}\n", encoding="utf-8")

    assert run_dir(project, HANDLE) == before


def test_a_control_plane_root_inside_the_project_is_refused(tmp_path, monkeypatch):
    """An environment variable must not relocate the control plane into the tree the
    actor writes."""
    project = _project(tmp_path, "alpha")
    monkeypatch.setenv(CONTROL_PLANE_ENV, str(project / "state"))

    with pytest.raises(BaselineError):
        control_plane_root(project)


def test_the_control_plane_root_falls_back_to_the_xdg_state_dir(tmp_path, monkeypatch):
    monkeypatch.delenv(CONTROL_PLANE_ENV, raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    assert control_plane_root(_project(tmp_path, "alpha")) == tmp_path / "state" / "science" / "runs"


@pytest.mark.parametrize(
    "hostile",
    [
        "../../other-project/2026-07-30-lens-a3f1",
        "..",
        "/absolute/2026-07-30-lens-a3f1",
        "2026-13-99-lens-a3f1",
        "not-a-run-id",
        "2026-07-30-lens-a3f1/../../escape",
        "2026-07-30-lens-a3f1\x00",
        "",
    ],
)
def test_a_hostile_handle_is_refused_before_any_join(tmp_path, monkeypatch, hostile):
    """The handle is actor-supplied and becomes a path component. Refuse it as a handle,
    not as a path -- a check applied after joining has already lost."""
    monkeypatch.setenv(CONTROL_PLANE_ENV, str(tmp_path / "cp"))

    with pytest.raises(ControlPlaneError):
        run_dir(_project(tmp_path, "alpha"), hostile)


@pytest.mark.parametrize(
    "ungenerated",
    [
        "2026-07-30-a",            # no agent at all; the whole remainder is one token
        "2026-07-30-lens-a3f",     # short id is 3 characters; _SHORT_ID_RE demands 4+
        "2026-07-30-lens-A3F1",    # short id is not lowercase
        "2026-07-30-Lens-a3f1",    # agent is not a kebab-case slug
        "2026-07-30-lens_x-a3f1",  # underscore is not in the agent alphabet
        "2026-07-30--a3f1",        # empty agent
        "2026-W31-4-lens-a3f1",    # ISO week notation; date.fromisoformat accepts it, generate_run_id never emits it
        "20260730XY-lens-a3f1",    # basic format; date.fromisoformat ignores chars 8-9 entirely
        "20260730/x-lens-a3f1",    # a path separator hiding inside what fromisoformat treats as the date
        "2026-02-30-lens-a3f1",    # well-shaped but not a real calendar date
    ],
)
def test_a_handle_no_generate_run_id_call_could_produce_is_refused(
    tmp_path, monkeypatch, ungenerated
):
    """Structure is not enough. A handle that is a safe path component but that
    `generate_run_id` could never have emitted names no run, and resolving it would
    silently create an addressable directory for a run that does not exist.

    The split works despite hyphenated agent slugs because a short id cannot contain a
    hyphen, so the last hyphen is always the boundary."""
    monkeypatch.setenv(CONTROL_PLANE_ENV, str(tmp_path / "cp"))

    with pytest.raises(ControlPlaneError):
        run_dir(_project(tmp_path, "alpha"), ungenerated)


def test_a_hyphenated_agent_slug_still_resolves(tmp_path, monkeypatch):
    """The regression guard for the split: `review-plans` must survive rpartition."""
    monkeypatch.setenv(CONTROL_PLANE_ENV, str(tmp_path / "cp"))

    assert run_slug("run:2026-07-30-review-plans-a3f1") == "2026-07-30-review-plans-a3f1"


@pytest.mark.parametrize("variable", [CONTROL_PLANE_ENV, "XDG_STATE_HOME"])
def test_a_relative_control_plane_root_is_refused(tmp_path, monkeypatch, variable):
    monkeypatch.delenv(CONTROL_PLANE_ENV, raising=False)
    monkeypatch.setenv(variable, "relative/state")

    with pytest.raises(ControlPlaneError):
        control_plane_root(_project(tmp_path, "alpha"))


def test_an_empty_control_plane_env_is_refused_not_silently_defaulted(tmp_path, monkeypatch):
    """`export SCIENCE_CONTROL_PLANE=` must not quietly fall back to the XDG default --
    that is a config error, not an unset variable, and the project's own rule is fail
    early rather than fall back silently.

    XDG_STATE_HOME is different: the XDG Base Directory spec says an empty value there
    MUST be treated as unset, so that variable keeps its existing fallback behaviour and
    is deliberately not covered by this test."""
    monkeypatch.setenv(CONTROL_PLANE_ENV, "")

    with pytest.raises(ControlPlaneError):
        control_plane_root(_project(tmp_path, "alpha"))


def test_the_working_directory_does_not_change_where_a_run_resolves(tmp_path, monkeypatch):
    """The companion guard to the rejection above, and it is deliberately trivial TODAY.

    It holds only because a relative root is refused outright; it is here so that softening
    that rejection into a "helpful" resolve-against-cwd fails this test rather than shipping.
    `start` and `finish` are separate processes and need not share a working directory, so a
    control plane that moved with the cwd would send `finish` to a different baseline, find
    no journal, and report every citation unserved -- a configuration error wearing the
    costume of actor misbehaviour."""
    monkeypatch.setenv(CONTROL_PLANE_ENV, str(tmp_path / "cp"))
    project = _project(tmp_path, "alpha")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    monkeypatch.chdir(tmp_path)
    from_here = run_dir(project, HANDLE)
    monkeypatch.chdir(elsewhere)
    from_there = run_dir(project, HANDLE)

    assert from_here == from_there


def test_both_handle_spellings_resolve_to_one_directory(tmp_path, monkeypatch):
    monkeypatch.setenv(CONTROL_PLANE_ENV, str(tmp_path / "cp"))
    project = _project(tmp_path, "alpha")

    assert run_slug(f"run:{HANDLE}") == HANDLE
    assert run_dir(project, f"run:{HANDLE}") == run_dir(project, HANDLE)


def test_the_run_directory_sits_under_the_project_key(tmp_path, monkeypatch):
    monkeypatch.setenv(CONTROL_PLANE_ENV, str(tmp_path / "cp"))
    project = _project(tmp_path, "alpha")
    key = project_key(project)

    # NOT `key.islower()`: a digest that happened to be all digits has no cased character
    # and would report False, failing on one run in ~10^-13 and never reproducing.
    assert re.fullmatch(r"[0-9a-f]{16}", key)
    assert run_dir(project, HANDLE) == tmp_path / "cp" / key / HANDLE
    assert project_metadata_path(project) == tmp_path / "cp" / key / "project.json"
