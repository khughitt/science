from __future__ import annotations

import ast
import os
import subprocess
from pathlib import Path

import pytest
from science_model.evidence_broker import SurfacePolicy

from science_tool.evidence_broker.policy import EvidenceOp, EvidenceRequest
from science_tool.evidence_broker.serve import Outcome, serve

OPEN = SurfacePolicy(notice="withheld")
UTF8_LOCALE = "en_US.UTF-8"


def _configured_repo(tmp_path: Path, name: str, config: dict[str, str]) -> tuple[Path, str]:
    """A repository the ACTOR configured. `.git/config` is untracked and invisible to the
    path gate, so every key here is one the actor can set during its own run."""
    root = tmp_path / name
    root.mkdir()
    for args in (
        ("init", "-q"),
        ("config", "user.email", "p@example.invalid"),
        ("config", "user.name", "P"),
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    for key, value in config.items():
        subprocess.run(
            ["git", "-C", str(root), "config", key, value], check=True, capture_output=True
        )
    # Non-ASCII, so `[[:alpha:]]` classifies differently under C and under UTF-8.
    (root / "sample.txt").write_text("éalpha\nplain\nalpha.beta\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
    # DATES ARE PINNED. `_LOG_ARGV` renders `%aI`, so two fixture repositories built a
    # second apart would produce different bytes and the log comparison would fail for a
    # reason that has nothing to do with configuration -- a false alarm on the exact test
    # meant to catch a real one.
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "seed"],
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
            "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
        },
    )
    commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True
    ).stdout.decode().strip()
    return root, commit


def _search(pattern: str) -> EvidenceRequest:
    return EvidenceRequest(op=EvidenceOp.SEARCH, target=pattern)


def _payload(tmp_path: Path, name: str, config: dict[str, str], request) -> bytes:
    root, commit = _configured_repo(tmp_path, name, config)
    served = serve(root, commit, request, OPEN)
    # The commit differs per fixture; strip it so the comparison is about RENDERING.
    return served.payload.replace(commit.encode(), b"<commit>")


HOSTILE_GREP_CONFIGS = (
    ("fixed", {"grep.patternType": "fixed"}),
    ("basic", {"grep.patternType": "basic"}),
    ("perl", {"grep.patternType": "perl"}),
    ("colour", {"color.ui": "always", "color.grep": "always"}),
    ("column", {"grep.column": "true"}),
    ("quote", {"core.quotePath": "true"}),
    ("nolineno", {"grep.lineNumber": "false"}),
)


@pytest.mark.parametrize("name,config", HOSTILE_GREP_CONFIGS)
def test_grep_renders_identically_under_hostile_configuration(
    tmp_path: Path, name: str, config: dict[str, str]
):
    """`grep.patternType` decides what the caller's PATTERN MEANS, not merely how output
    looks, so an inherited value makes one request two different queries. The rest change
    rendering. Replay compares bytes, so either kind refuses an honest run."""
    baseline = _payload(tmp_path, "baseline", {}, _search("alpha.beta"))
    assert _payload(tmp_path, name, config, _search("alpha.beta")) == baseline


HOSTILE_LOG_CONFIGS = (
    ("date", {"log.date": "rfc"}),
    ("decorate", {"log.decorate": "full"}),
    ("abbrev", {"log.abbrevCommit": "true"}),
    ("pretty", {"format.pretty": "oneline"}),
    ("signature", {"log.showSignature": "true"}),
)


@pytest.mark.parametrize("name,config", HOSTILE_LOG_CONFIGS)
def test_log_renders_identically_under_hostile_configuration(
    tmp_path: Path, name: str, config: dict[str, str]
):
    request = EvidenceRequest(op=EvidenceOp.HISTORY, target="sample.txt")
    baseline = _payload(tmp_path, "log-baseline", {}, request)
    assert _payload(tmp_path, name, config, request) == baseline


@pytest.mark.parametrize("locale", ["C", UTF8_LOCALE, "fr_FR.UTF-8"])
def test_a_posix_class_replays_identically_across_parent_locales(
    tmp_path: Path, locale: str, monkeypatch
):
    """Run as a REPLAY across differing parent locales, since that is the failure being
    prevented: `[[:alpha:]]` matches a different character set under C than under UTF-8,
    so an unpinned locale makes two honest replays of one query disagree."""
    baseline = _payload(tmp_path, "locale-baseline", {}, _search("[[:alpha:]]alpha"))
    monkeypatch.setenv("LC_ALL", locale)
    monkeypatch.setenv("LANG", locale)
    monkeypatch.setenv("LANGUAGE", locale.split(".")[0])
    assert _payload(tmp_path, f"locale-{locale}", {}, _search("[[:alpha:]]alpha")) == baseline


def test_the_defined_miss_classifier_survives_a_translated_parent(tmp_path: Path, monkeypatch):
    """git's DIAGNOSTIC text is localized and the classifier reads it. Under a translated
    parent an absent path would fall through to "anything else raises" -- an ordinary miss
    becoming a halted run. `LANGUAGE` selects git's catalogue; `LC_ALL=C` must defeat it."""
    root, commit = _configured_repo(tmp_path, "translated", {})
    monkeypatch.setenv("LANGUAGE", "fr")
    served = serve(root, commit, EvidenceRequest(op=EvidenceOp.READ, target="nope.txt"), OPEN)
    assert served.outcome is Outcome.MISS_ABSENT


GIT_TOUCHING = ("verify_commit", "_serve_read", "_serve_search", "_serve_history")


def _package_dir() -> Path:
    import science_tool.evidence_broker as package

    # Located from the module, not from the working directory: a relative path here would
    # make the guard's reach depend on where pytest was invoked from.
    return Path(package.__file__).parent


def _module_asts() -> dict[str, ast.Module]:
    """EVERY module in the package. A guard that parses one file has already decided where
    the defect will be, which is the assumption a new module exists to violate."""
    return {
        path.name: ast.parse(path.read_text(encoding="utf-8"))
        for path in sorted(_package_dir().glob("*.py"))
    }


def test_every_git_call_in_the_package_sits_in_a_known_helper():
    """Derived from the code, not from a list someone maintains -- same spirit as
    `tests/test_instrument_boundary.py`. A `run_git` call added to `policy.py`, or to a
    module that does not exist yet, fails here rather than quietly acquiring an unaudited
    path to git."""
    callers: dict[str, set[str]] = {}
    for name, tree in _module_asts().items():
        callers[name] = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and any(
                isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Name)
                and inner.func.id == "run_git"
                for inner in ast.walk(node)
            )
        }
    assert callers.pop("serve.py") == set(GIT_TOUCHING)
    assert all(not found for found in callers.values()), f"git reached from: {callers}"


def test_authorize_precedes_every_git_call_in_serve():
    """ORDERING, not membership. Asserting only that `serve` CONTAINS a call to
    `authorize` passes when a helper is invoked above it -- which is exactly the defect
    this guard exists to catch, and exactly the shape the first draft shipped.

    THIS IS A STRUCTURAL PROXY, NOT A PROOF OF DOMINANCE. Source position is not control
    flow: a call textually below `authorize` could still run first through a construct this
    check cannot see. It is cheap and it catches the mistake people actually make -- moving
    a line. `test_a_denied_read_makes_no_git_call_at_all` is the behavioural guard, and it
    is the one that would survive a cleverer rearrangement; this one localizes the failure
    to a line number when it fires.
    """
    serve_fn = next(
        node
        for node in ast.walk(_module_asts()["serve.py"])
        if isinstance(node, ast.FunctionDef) and node.name == "serve"
    )
    positions: dict[str, list[tuple[int, int]]] = {}
    for inner in ast.walk(serve_fn):
        if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name):
            positions.setdefault(inner.func.id, []).append((inner.lineno, inner.col_offset))

    assert "authorize" in positions, "serve does not authorize at all"
    assert len(positions["authorize"]) == 1, "one authorization, so there is one thing to order"
    authorized_at = positions["authorize"][0]

    reached = {name: positions[name] for name in GIT_TOUCHING if name in positions}
    assert set(reached) == set(GIT_TOUCHING), f"serve does not dispatch to {set(GIT_TOUCHING) - set(reached)}"
    for name, sites in reached.items():
        for site in sites:
            assert site > authorized_at, f"{name} is called at {site}, before authorize at {authorized_at}"


#: MATCHED BY SHAPE, NOT BY ROSTER. An enumeration of `os` spawn names is a list someone has
#: to keep complete against a stdlib that has ~20 of them (`spawnl`, `spawnlp`, `spawnvp`,
#: `spawnvpe`, `posix_spawnp`, the whole `exec*` family), and the one left off the list is the
#: one a mutation reaches for. `_spawns` matches the family by prefix instead, and the call
#: check ignores the receiver entirely -- so `os.spawnvp`, `o.system` under an aliased import,
#: and a bare `system(...)` after `from os import system` all land the same way.
_SPAWNING_MODULES = frozenset({"subprocess", "pty", "multiprocessing"})
_SPAWNING_PREFIXES = ("exec", "spawn", "popen", "posix_spawn", "fork")
#: `import_module` and `__import__` are here because a dynamic import defeats the import check
#: above: without them, `importlib.import_module("subprocess").run(...)` passes.
_SPAWNING_NAMES = frozenset({"system", "startfile", "import_module", "__import__"})


def _spawns(name: str) -> bool:
    lowered = name.lower()
    return lowered in _SPAWNING_NAMES or lowered.startswith(_SPAWNING_PREFIXES)


def test_the_broker_makes_no_direct_subprocess_call():
    """A git call that skips `run_git` is a call the actor can turn into arbitrary
    execution inside the control plane, and no layer of this design would report it.

    AN AST CHECK, NOT A TEXT SCAN. Searching each module for the substring `subprocess`
    reads as stricter and is simply broken: `policy.py`'s own docstring explains why a NUL
    cannot cross `subprocess`'s argv boundary, and the guard would reject the module for
    documenting the reason it exists. A guard that forbids discussing the hazard forces the
    explanation out of the code, which is the opposite of what it was written for.

    STILL A STRUCTURAL PROXY. `getattr(os, "sys" + "tem")` defeats it, as does any other
    computed name. The claim is bounded accordingly: no module in this package *spells* a
    process launch. That is worth asserting because it is the spelling a refactor or a
    convenience helper would actually use.
    """
    for name, tree in _module_asts().items():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # alias.name, not alias.asname: `import subprocess as sp` is still an import.
                    assert alias.name.split(".")[0] not in _SPAWNING_MODULES, f"{name}: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                assert root not in _SPAWNING_MODULES, f"{name}: from {node.module}"
                for alias in node.names:
                    # Catches `from os import system`, where the module is innocent and the
                    # imported name is not.
                    assert not _spawns(alias.name), f"{name}: from {node.module} import {alias.name}"
            elif isinstance(node, ast.Call):
                func = node.func
                called = (
                    func.attr
                    if isinstance(func, ast.Attribute)
                    else func.id
                    if isinstance(func, ast.Name)
                    else None
                )
                assert called is None or not _spawns(called), f"{name}: calls {called}"
