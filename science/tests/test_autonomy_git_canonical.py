from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from science_tool.autonomy.git import run_git


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
