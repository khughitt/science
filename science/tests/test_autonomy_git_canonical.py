from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path

import pytest

from science_tool.autonomy.git import GitError, GitOutputTooLarge, history_traversal_error, run_git


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    for args in (
        ("init", "-q"),
        ("config", "user.email", "probe@example.invalid"),
        ("config", "user.name", "Probe"),
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    # Non-ASCII content: `[[:alpha:]]` classifies these differently under C and UTF-8.
    (root / "sample.txt").write_text("éalpha\nplain\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "seed"], check=True, capture_output=True
    )
    return root


UTF8_LOCALE = "en_US.UTF-8"
GREP_ARGV = ("grep", "-n", "-e", "[[:alpha:]]alpha", "HEAD")


def _bare_git(root: Path, overrides: dict[str, str], *args: str) -> subprocess.CompletedProcess:
    """git WITHOUT this module's hardening, for negative controls."""
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, env={**os.environ, **overrides}
    )


def test_grep_output_does_not_depend_on_the_parent_locale(tmp_path: Path, monkeypatch):
    """A POSIX class means different things under C and under UTF-8, so an unpinned
    locale makes two honest replays of one query disagree -- and correspondence refuses
    on disagreement.

    The negative control comes FIRST. Locale data is not guaranteed to be installed, and
    when it is missing the C library falls back to C -- so the two outputs would be equal
    for a reason that has nothing to do with the fix, and this test would pass green
    against unpatched code. Skipping is honest; passing would be a lie.
    """
    root = _repo(tmp_path)
    control_c = _bare_git(root, {"LC_ALL": "C", "LANG": "C"}, *GREP_ARGV).stdout
    control_utf8 = _bare_git(
        root, {"LC_ALL": UTF8_LOCALE, "LANG": UTF8_LOCALE}, *GREP_ARGV
    ).stdout
    if control_c == control_utf8:
        pytest.skip(
            f"{UTF8_LOCALE} data is unavailable here, so the hazard does not reproduce and "
            "the guard would pass vacuously"
        )

    monkeypatch.setenv("LC_ALL", "C")
    monkeypatch.setenv("LANG", "C")
    under_c = run_git(root, *GREP_ARGV).stdout

    monkeypatch.setenv("LC_ALL", UTF8_LOCALE)
    monkeypatch.setenv("LANG", UTF8_LOCALE)
    under_utf8 = run_git(root, *GREP_ARGV).stdout

    assert under_c == under_utf8


def test_a_missing_path_is_reported_in_a_pinned_locale(tmp_path: Path, monkeypatch):
    """The defined-miss classifier reads git's stderr. Localized text would not match,
    and an ordinary absent path would halt the run instead of answering.

    `fr_FR.UTF-8` is not what selects git's French catalogue -- `LANGUAGE` is, and it
    works over any installed UTF-8 locale. `fr_FR.UTF-8` itself is not installed on every
    machine that has git's French `.mo` file, so pinning the test to that locale name
    would make the negative control skip even where the hazard is real. Using `LANGUAGE=fr`
    over the UTF-8 locale this suite already depends on (`en_US.UTF-8`) reaches the same
    catalogue without a second locale-generation dependency.
    """
    root = _repo(tmp_path)
    missing = ("show", "HEAD:no-such-file.txt")
    english = _bare_git(root, {"LC_ALL": "C", "LANGUAGE": ""}, *missing).stderr
    translated = _bare_git(
        root, {"LC_ALL": UTF8_LOCALE, "LANGUAGE": "fr"}, *missing
    ).stderr
    if english == translated:
        pytest.skip(
            "git's French message catalogue is unavailable here, so git's diagnostics do "
            "not translate and the guard would pass vacuously"
        )

    monkeypatch.setenv("LC_ALL", UTF8_LOCALE)
    monkeypatch.setenv("LANGUAGE", "fr")
    completed = run_git(root, *missing)

    assert completed.returncode != 0
    assert completed.stderr == english


FAKE_SIGNATURE = """-----BEGIN PGP SIGNATURE-----

 not a real signature; git must still hand it to the configured program
 -----END PGP SIGNATURE-----"""

SIGNED_LOG_ARGV = ("log", "--pretty=format:%H %aI", "SIGNED")


def _signed_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A repo whose `SIGNED` ref carries a `gpgsig` header, plus the marker path a
    configured `gpg.program` would touch. No signing key is involved: git hands the
    block to the program before deciding whether it is well formed."""
    root = _repo(tmp_path)
    marker = tmp_path / "EXECUTED"
    spawn = root / "spawn.sh"
    spawn.write_text(f"#!/bin/sh\ntouch {marker}\ncat\n", encoding="utf-8")
    spawn.chmod(0o755)

    def git(*args: str) -> str:
        out = subprocess.run(
            ["git", "-C", str(root), *args], check=True, capture_output=True
        )
        return out.stdout.decode().strip()

    ident = "Probe <probe@example.invalid> 0 +0000"
    body = (
        f"tree {git('rev-parse', 'HEAD^{tree}')}\n"
        f"parent {git('rev-parse', 'HEAD')}\n"
        f"author {ident}\ncommitter {ident}\n"
        f"gpgsig {FAKE_SIGNATURE}\n\nsigned\n"
    )
    sha = subprocess.run(
        ["git", "-C", str(root), "hash-object", "-t", "commit", "-w", "--stdin"],
        input=body.encode("utf-8"), check=True, capture_output=True,
    ).stdout.decode().strip()
    git("update-ref", "refs/heads/SIGNED", sha)

    for key, value in (("log.showSignature", "true"), ("gpg.program", "./spawn.sh")):
        git("config", key, value)
    return root, marker


def test_signature_verification_still_spawns_the_configured_program(tmp_path: Path):
    """The negative control. Both keys AND a signed object are required -- each alone is
    harmless, which is why this is a composite. If this ever stops failing under bare git,
    the guard below proves nothing and the pair should be revisited, not deleted."""
    root, marker = _signed_repo(tmp_path)

    subprocess.run(["git", "-C", str(root), *SIGNED_LOG_ARGV], capture_output=True)

    assert marker.exists()


def test_run_git_never_reaches_signature_verification(tmp_path: Path):
    """Two assertions, because there are two ways to get this wrong, and the marker only
    catches one. The marker proves the attacker's binary did not run. The EMPTY STDERR
    proves no verification was attempted at all -- hardening `gpg.program=` instead leaves
    verification enabled, and git then tries to run a program regardless: the blanked name
    (`error: cannot run : No such file or directory`) here, or the default `gpg` on PATH in
    a repo where the attacker configured no program. Both write to stderr; neither clears
    the marker, so `assert not marker.exists()` alone would green-light the weak fix."""
    root, marker = _signed_repo(tmp_path)

    completed = run_git(root, *SIGNED_LOG_ARGV)

    assert not marker.exists()
    assert completed.stderr == b""
    assert len(completed.stdout.splitlines()) == 2  # the signed commit and its parent


def _filtered_repo(tmp_path: Path) -> tuple[Path, str, bytes]:
    """A repository whose configuration WOULD mangle a checkout, and its committed bytes."""
    root = tmp_path / "filtered"
    root.mkdir()
    for args in (
        ("init", "-q"),
        ("config", "user.email", "probe@example.invalid"),
        ("config", "user.name", "Probe"),
        ("config", "core.autocrlf", "true"),
        ("config", "filter.probe.smudge", "sed s/alpha/MANGLED/"),
        ("config", "filter.probe.clean", "cat"),
        ("config", "diff.probe.textconv", "sed s/alpha/MANGLED/"),
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    (root / ".gitattributes").write_text("a.txt diff=probe filter=probe\n", encoding="utf-8")
    committed = b"alpha\nbeta\n"
    (root / "a.txt").write_bytes(committed)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "seed"], check=True, capture_output=True
    )
    commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True
    ).stdout.decode().strip()
    return root, commit, committed


def test_cat_file_blob_serves_the_object_not_a_filtered_checkout(tmp_path: Path):
    """`read` must serve what the commit holds, not what a checkout would produce.

    The repository configures a smudge filter, a textconv driver and `core.autocrlf`, all
    reachable through `.gitattributes` and all owned by the actor. `cat-file blob` is a raw
    object read, so none of them applies -- which is why `read` can be a pure function of the
    commit. The control below proves the configuration is genuinely live, so that INERT here
    means "this command ignores it" rather than "the fixture forgot to set it".
    """
    root, commit, committed = _filtered_repo(tmp_path)

    completed = run_git(root, "cat-file", "blob", f"{commit}:a.txt")

    assert completed.returncode == 0
    assert completed.stdout == committed
    assert completed.stderr == b""


def test_cat_file_type_is_unaffected_by_the_same_configuration(tmp_path: Path):
    """The other half of `read`. Production runs BOTH spellings, so both are held to the
    module's rule -- a probe of a subcommand that merely resembles the one that ships is
    not a probe of the one that ships."""
    root, commit, _committed = _filtered_repo(tmp_path)

    completed = run_git(root, "cat-file", "-t", f"{commit}:a.txt")

    assert completed.returncode == 0
    assert completed.stdout.strip() == b"blob"
    assert completed.stderr == b""


def test_the_filter_fixture_is_live(tmp_path: Path):
    """Negative control for the test above: a checkout DOES mangle, so INERT is a finding.

    The working-tree file is unlinked first. Without that, git's stat-cache optimism
    considers `a.txt` already up to date with the index and skips rewriting it -- even
    under `checkout-index -f` -- so the smudge filter never runs and this control would
    pass for a reason that has nothing to do with the configuration under test.
    """
    root, _commit, committed = _filtered_repo(tmp_path)
    (root / "a.txt").unlink()
    subprocess.run(
        ["git", "-C", str(root), "checkout", "--", "a.txt"], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(root), "checkout-index", "-f", "--", "a.txt"],
        check=True,
        capture_output=True,
    )

    assert (root / "a.txt").read_bytes() != committed


def _commit(repo: Path, name: str, body: str) -> None:
    """Write `body` to `name` and commit it. The commit MESSAGE is the file name, not the body:
    a 4 KiB commit message would work but makes `git log` output unreadable when a test fails."""
    (repo / name).write_text(body, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-f", name], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", name],
        check=True,
        capture_output=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e"},
    )


@pytest.fixture
def three_commit_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "src"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True, capture_output=True)
    for text in ("one", "two", "three"):
        _commit(repo, "f.txt", text)
    return repo


def test_stdout_overflow_refuses_and_does_not_truncate(three_commit_repo: Path) -> None:
    """Refuse, never truncate. A truncated answer is a wrong answer that looks like an answer."""
    _commit(three_commit_repo, "big.txt", "x" * 4096)
    commit = run_git(three_commit_repo, "rev-parse", "HEAD").stdout.decode().strip()

    with pytest.raises(GitOutputTooLarge) as caught:
        run_git(three_commit_repo, "cat-file", "blob", f"{commit}:big.txt", stdout_limit=64)

    assert caught.value.stream == "stdout"
    assert caught.value.limit == 64
    assert 64 < caught.value.consumed <= 64 + (1 << 16)


def test_a_payload_at_the_limit_is_served(three_commit_repo: Path) -> None:
    """The boundary is inclusive; a payload of exactly `stdout_limit` bytes is not an overflow.

    Without this pair, an off-by-one that refused every payload would pass the test above.
    """
    body = "y" * 100
    _commit(three_commit_repo, "exact.txt", body)
    commit = run_git(three_commit_repo, "rev-parse", "HEAD").stdout.decode().strip()

    completed = run_git(
        three_commit_repo, "cat-file", "blob", f"{commit}:exact.txt", stdout_limit=len(body)
    )

    assert completed.returncode == 0
    assert completed.stdout == body.encode()


def test_stderr_is_bounded_on_every_call(three_commit_repo: Path, monkeypatch) -> None:
    """`stderr` is captured alongside stdout on EVERY call and is actor-influenced.

    §3.2.1 records `.git/objects/info/alternates` emitting a warning on ordinary commands, so an
    unbounded diagnostic is an unbounded allocation on a path the actor reaches without asking.
    """
    monkeypatch.setattr("science_tool.autonomy.git.MAX_GIT_STDERR_BYTES", 32)
    alternates = three_commit_repo / ".git" / "objects" / "info"
    alternates.mkdir(parents=True, exist_ok=True)
    (alternates / "alternates").write_text("/" + "n" * 4096 + "\n", encoding="utf-8")

    with pytest.raises(GitOutputTooLarge) as caught:
        run_git(three_commit_repo, "cat-file", "-t", "HEAD")

    assert caught.value.stream == "stderr"


def test_a_large_stdin_payload_does_not_deadlock(three_commit_repo: Path) -> None:
    """The regression guard for the shape this task replaces.

    Writing all of stdin before reading anything deadlocks once the child's own output fills its
    pipe: the child blocks on stdout, stops reading stdin, and the parent blocks on stdin.
    MEASURED with `cat` and a 4 MiB write -- never returns. `check-ignore --stdin -z --verbose`
    both consumes a large stdin and emits a large stdout, so it exercises both directions at once.

    THE `.gitignore` IS WHAT MAKES THIS TEST ABLE TO FAIL. With no ignore rule, `check-ignore
    --verbose` matches nothing and emits ZERO bytes on stdout -- MEASURED, exit 1, 0 bytes -- so
    the child never blocks, the parent drains stdin freely, and the write-first implementation
    PASSES. Committing `*` makes every path produce a verbose line (~23 bytes each; 46 bytes for
    two paths, measured), so 50k paths push well past the pipe buffer in both directions.

    THE ALARM IS LOAD-BEARING. `pytest-timeout` is not a dependency of this package, and a
    deadlock's failure mode is SILENCE -- without this the regression hangs the suite instead of
    failing it, which is worse than not testing it at all. SIGALRM is POSIX-only; this suite
    already runs Linux-only tooling, and a handler that raises propagates through the blocked
    write (PEP 475 retries on EINTR only when the handler does NOT raise).
    """

    def _timeout(signum, frame):
        raise TimeoutError("run_git deadlocked writing stdin while the child wrote stdout")

    _commit(three_commit_repo, ".gitignore", "*\n")
    # NUL-TERMINATED, not NUL-separated: `-z` framing means a trailing record without its
    # terminator is incomplete, and git may hold it rather than answer.
    paths = b"".join(f"dir{n}/file{n}.txt\0".encode() for n in range(50000))
    previous = signal.signal(signal.SIGALRM, _timeout)
    signal.alarm(30)
    try:
        completed = run_git(
            three_commit_repo,
            "check-ignore",
            "--stdin",
            "-z",
            "--verbose",
            "--no-index",
            input=paths,
        )
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)

    assert completed.returncode == 0, "every path should match the `*` rule"
    assert len(completed.stdout) > (1 << 16), (
        "the child produced less than one pipe buffer of output, so this test could not have "
        "deadlocked even against the write-first implementation"
    )


def test_the_config_preflight_is_bounded(three_commit_repo: Path, monkeypatch) -> None:
    """The preflight runs before EVERY `run_git` call and its size is the actor's to choose.

    `include.path` pulls in arbitrary files, so this is unbounded input on the path that executes
    most often -- and it is spent before the request it precedes is even authorized.
    """
    monkeypatch.setattr("science_tool.autonomy.git.MAX_CONFIG_LIST_BYTES", 64)
    included = three_commit_repo / "extra.config"
    included.write_text(
        "".join(f"[filter \"d{n}\"]\n\tclean = cat\n" for n in range(200)), encoding="utf-8"
    )
    subprocess.run(
        ["git", "-C", str(three_commit_repo), "config", "include.path", str(included)],
        check=True,
        capture_output=True,
    )

    with pytest.raises(GitError):
        run_git(three_commit_repo, "rev-parse", "HEAD")


def test_a_planted_shallow_file_does_not_shorten_history(three_commit_repo: Path) -> None:
    """The actor writes `.git/shallow` AFTER the run opens; a check at open cannot see it.

    Unpinned, this is 2 commits at exit 0 -- a silently shortened answer to a pinned commit.
    """
    commit = run_git(three_commit_repo, "rev-parse", "HEAD").stdout.decode().strip()
    parent = run_git(three_commit_repo, "rev-parse", "HEAD~1").stdout.decode().strip()

    before = run_git(three_commit_repo, "log", "--pretty=format:%H", commit).stdout
    (three_commit_repo / ".git" / "shallow").write_text(f"{parent}\n", encoding="utf-8")
    after = run_git(three_commit_repo, "log", "--pretty=format:%H", commit).stdout

    assert after == before
    assert len(before.decode().split()) == 3


def test_a_partial_clone_fails_rather_than_fetching(tmp_path: Path, three_commit_repo: Path) -> None:
    """A promisor remote is an egress channel, not just a source of non-determinism.

    `uploadpack.allowFilter` MUST be set on the serving side: it defaults to false, and without
    it the filtered clone comes back COMPLETE and this test passes against the defect.
    """
    subprocess.run(
        ["git", "-C", str(three_commit_repo), "config", "uploadpack.allowFilter", "true"],
        check=True,
        capture_output=True,
    )
    clone = tmp_path / "partial"
    subprocess.run(
        ["git", "clone", "-q", "--filter=tree:0", "--no-checkout",
         f"file://{three_commit_repo}", str(clone)],
        check=True,
        capture_output=True,
    )
    # PRECONDITION, and it must not be built out of the thing under test: derive the OID from the
    # SOURCE repository and check absence with our own explicit pin. Unpinned `cat-file -e` in the
    # clone exits 0 AND fetches the object in, destroying the condition it was establishing.
    tree = run_git(three_commit_repo, "rev-parse", "HEAD~1^{tree}").stdout.decode().strip()
    probe = subprocess.run(
        ["git", "-C", str(clone), "cat-file", "-e", tree],
        capture_output=True,
        env={**os.environ, "GIT_NO_LAZY_FETCH": "1"},
    )
    assert probe.returncode != 0, "the filter did not take; check uploadpack.allowFilter"

    commit = run_git(clone, "rev-parse", "HEAD").stdout.decode().strip()
    completed = run_git(clone, "log", "--pretty=format:%H", commit, "--", "f.txt")

    assert completed.returncode != 0
    assert b"unable to read tree" in completed.stderr


def test_a_complete_repository_has_no_history_traversal_error(three_commit_repo: Path) -> None:
    """The baseline half of the pair below, and the assertion the PROXY cannot satisfy.

    MEASURED, git 2.55: `rev-parse --is-shallow-repository` reads `true` for a COMPLETE repository
    under `GIT_SHALLOW_FILE=/dev/null`, so swapping this probe for it turns this test red.
    """
    commit = run_git(three_commit_repo, "rev-parse", "HEAD").stdout.decode().strip()

    assert history_traversal_error(three_commit_repo, commit) is None


def test_a_planted_shallow_file_is_not_a_history_traversal_error(three_commit_repo: Path) -> None:
    """The diagnostic answers to the OBJECTS, not to the actor's file.

    Unpinning the detector so `--is-shallow-repository` could see a genuine boundary would also let
    it see this one -- an actor could refuse its own run's open by writing a file. Every object is
    present here, so history is traversable and the plant means nothing.
    """
    commit = run_git(three_commit_repo, "rev-parse", "HEAD").stdout.decode().strip()
    parent = run_git(three_commit_repo, "rev-parse", "HEAD~1").stdout.decode().strip()
    (three_commit_repo / ".git" / "shallow").write_text(f"{parent}\n", encoding="utf-8")

    assert history_traversal_error(three_commit_repo, commit) is None


def test_a_genuine_shallow_clone_is_a_history_traversal_error(
    tmp_path: Path, three_commit_repo: Path
) -> None:
    """Objects genuinely absent: git's own words come back for the operator message."""
    clone = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", f"file://{three_commit_repo}", str(clone)],
        check=True,
        capture_output=True,
    )
    commit = run_git(clone, "rev-parse", "HEAD").stdout.decode().strip()

    reason = history_traversal_error(clone, commit)

    assert reason is not None
    assert "Failed to traverse parents" in reason
