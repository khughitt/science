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
    # `alphaXbeta`, `alpha1` and `gammaadelta` are grammar-boundary bait for `GREP_PATTERNS`
    # below -- `alpha.beta` alone cannot tell `fixed` from `basic` from `extended` from `perl`
    # apart for this content, and the certification is worth nothing if it can't.
    (root / "sample.txt").write_text(
        "éalpha\nplain\nalpha.beta\nalphaXbeta\nalpha1\ngammaadelta\n", encoding="utf-8"
    )
    # A non-ASCII FILENAME, not merely non-ASCII content: `core.quotePath` has nothing to
    # decide until a path itself contains a byte above 0x80.
    (root / "café.txt").write_text("alpha.beta\n", encoding="utf-8")
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


#: `grep.patternType=basic` and `core.quotePath=true` and `grep.lineNumber=false` are git's
#: OWN DEFAULTS (measured, git 2.55: `git config --get` on each is unset in a fresh repo, and
#: the documented default values are `basic` behaviour, `true`, and `false` respectively) --
#: a repository "configured" to its own default is configurationally IDENTICAL to the
#: baseline, so the row cannot fail for any pattern or content, and was proving nothing.
#: `extended`, `false` and `true` below are the values that actually diverge from default.
HOSTILE_GREP_CONFIGS = (
    ("fixed", {"grep.patternType": "fixed"}),
    ("extended", {"grep.patternType": "extended"}),
    ("perl", {"grep.patternType": "perl"}),
    ("colour", {"color.ui": "always", "color.grep": "always"}),
    ("column", {"grep.column": "true"}),
    ("quote", {"core.quotePath": "false"}),
    ("nolineno", {"grep.lineNumber": "true"}),
)

#: THREE PATTERNS, not one. `alpha.beta` alone cannot separate `fixed` from `basic` from
#: `extended` from `perl` against this fixture, because `.` means "any character" in every
#: one of those grammars -- a hostile `grep.patternType` this argv failed to pin could
#: reproduce the baseline's bytes by COINCIDENCE rather than by being defeated, and the
#: suite would never know the difference. Each pattern below isolates one grammar boundary,
#: measured on git 2.55 against the fixture's `alphaXbeta` / `alpha1` / `gammaadelta` lines:
#:   dot   -- `.` matches any character in fixed-vs-not only: `fixed` sees 1 line
#:            (`alpha.beta` itself); `basic`/`extended`/`perl` all see 2 (+ `alphaXbeta`).
#:   digit -- `\d` is a PCRE escape. `perl` matches `alpha1`; `basic`/`extended`/`fixed`
#:            treat `\d` as a literal `d` and match nothing.
#:   plus  -- `+` is a quantifier only outside basic regex. `extended`/`perl` match
#:            `gammaadelta` (`a+` = one-or-more `a`); `basic`/`fixed` treat `+` as a literal
#:            character and match nothing.
GREP_PATTERNS: tuple[tuple[str, str], ...] = (
    ("dot", "alpha.beta"),
    ("digit", r"alpha\d"),
    ("plus", "gamma+delta"),
)


@pytest.mark.parametrize("name,config", HOSTILE_GREP_CONFIGS)
def test_grep_renders_identically_under_hostile_configuration(
    tmp_path: Path, name: str, config: dict[str, str]
):
    """`grep.patternType` decides what the caller's PATTERN MEANS, not merely how output
    looks, so an inherited value makes one request two different queries. The rest change
    rendering. Replay compares bytes, so either kind refuses an honest run."""
    for label, pattern in GREP_PATTERNS:
        baseline = _payload(tmp_path, f"baseline-{label}", {}, _search(pattern))
        assert _payload(tmp_path, f"{name}-{label}", config, _search(pattern)) == baseline


def test_grep_dash_e_is_pinned_against_an_unconfigured_repository(tmp_path: Path):
    """`-E` cannot be certified DIFFERENTIALLY at all: git's default grammar is basic, so an
    unconfigured baseline and an unconfigured "hostile" repo degrade in lockstep the moment
    `-E` is removed -- there is no comparison between two default repos that would ever
    notice its absence. This is a NON-differential assertion instead: `gamma+delta` matches
    `gammaadelta` only under extended-regex semantics (`+` is a literal character in basic
    regex, which is what an unconfigured repo uses). If the served payload contains it at
    all, something forced extended grammar -- and nothing in this repository's configuration
    did.
    """
    root, commit = _configured_repo(tmp_path, "e-flag", {})
    served = serve(root, commit, _search("gamma+delta"), OPEN)
    assert b"gammaadelta" in served.payload


#: The attribute stack, which `.git/config` does not reach and `-c` therefore cannot harden.
#: BOTH LAYERS, because they are neutralized by nothing in common: `.gitattributes` need not be
#: committed to take effect (so the path gate never sees it) and `$GIT_DIR/info/attributes` has
#: no config key at all. `--attr-source` replaces only the tracked-`.gitattributes` layer, so it
#: answers neither.
HOSTILE_ATTRIBUTE_LAYERS: tuple[tuple[str, str], ...] = (
    ("worktree", ".gitattributes"),
    ("info", ".git/info/attributes"),
)


@pytest.mark.parametrize("name,relative", HOSTILE_ATTRIBUTE_LAYERS)
def test_grep_serves_the_baseline_bytes_under_a_hostile_attribute_stack(
    tmp_path: Path, name: str, relative: str
):
    """MEASURED, git 2.55: with `* binary` in either layer, `git grep` answers
    `Binary file <commit>:sample.txt matches` AT EXIT 0 instead of the `-z` record carrying a
    line number and the matched line. `_serve_search` sees a zero exit and returns SERVED, so
    the broker reports success over a payload with no line numbers and no content -- the actor
    decides what the auditor is shown, and nothing in the design notices.

    This asserts the SERVED BYTES against the baseline repository's, not merely that some
    payload came back: `Binary file ... matches` is itself a payload, and a test that only
    checked the outcome would pass against the very defect it names.
    """
    baseline = _payload(tmp_path, f"attr-baseline-{name}", {}, _search("alpha.beta"))
    root, commit = _configured_repo(tmp_path, f"attr-hostile-{name}", {})
    blinding = root / relative
    blinding.parent.mkdir(parents=True, exist_ok=True)
    blinding.write_text("* binary\n", encoding="utf-8")
    # NOT committed, and not `git add`ed: the working-tree layer takes effect as it lies on
    # disk, so the path gate and every tracked-content check are blind to it by construction.
    served = serve(root, commit, _search("alpha.beta"), OPEN)

    assert served.outcome is Outcome.SERVED
    assert served.payload.replace(commit.encode(), b"<commit>") == baseline


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


#: `log.follow` needs its own fixture, because follow is about a RENAME and `_configured_repo`
#: has none -- against a repository where nothing was ever renamed the key is inert, and a row
#: added to `HOSTILE_LOG_CONFIGS` would have passed no matter what `_LOG_ARGV` said.
HOSTILE_FOLLOW_CONFIGS = (("follow", {"log.follow": "true"}),)


def _renamed_repo(tmp_path: Path, name: str, config: dict[str, str]) -> tuple[Path, str]:
    """`old.txt` renamed to `new.txt`, then modified. Three commits, DATES PINNED for the same
    reason `_configured_repo` pins them: `%aI` renders into the compared bytes."""
    root = tmp_path / name
    root.mkdir()
    dated = {
        **os.environ,
        "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
        "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
    }

    def _git(*args: str, env: dict[str, str] | None = None) -> None:
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, env=env)

    for args in (("init", "-q"), ("config", "user.email", "p@example.invalid"), ("config", "user.name", "P")):
        _git(*args)
    for key, value in config.items():
        _git("config", key, value)
    (root / "old.txt").write_text("first\n", encoding="utf-8")
    _git("add", "-A")
    _git("commit", "-q", "-m", "before the rename", env=dated)
    _git("mv", "old.txt", "new.txt")
    _git("commit", "-q", "-m", "the rename", env=dated)
    (root / "new.txt").write_text("first\nsecond\n", encoding="utf-8")
    _git("add", "-A")
    _git("commit", "-q", "-m", "after the rename", env=dated)
    commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True
    ).stdout.decode().strip()
    return root, commit


@pytest.mark.parametrize("name,config", HOSTILE_FOLLOW_CONFIGS)
def test_log_selects_the_same_commits_under_a_hostile_follow_configuration(
    tmp_path: Path, name: str, config: dict[str, str]
):
    """`log.follow` decides WHICH COMMITS ARE SELECTED, not how they render -- the only row in
    this file that changes the answer rather than its spelling. MEASURED, git 2.55: history for
    `new.txt` reports two commits by default and three under `log.follow=true`, so one honest
    replay would carry the pre-rename commit and the other would not, and §5.3 refuses on
    disagreement.

    THE POLICY IS `OPEN` ON PURPOSE. Follow arms only when exactly one pathspec is given, so any
    policy with a deny prefix hands `log` its exclusions and disarms the key by accident. An
    empty deny policy is legitimate, is what most of this suite uses, and is the case where the
    key bites -- a test written against `CLOSED` would pass with `--no-follow` removed.
    """
    request = EvidenceRequest(op=EvidenceOp.HISTORY, target="new.txt")
    root, commit = _renamed_repo(tmp_path, "follow-baseline", {})
    baseline = serve(root, commit, request, OPEN).payload
    hostile_root, hostile_commit = _renamed_repo(tmp_path, name, config)
    served = serve(hostile_root, hostile_commit, request, OPEN)

    assert served.outcome is Outcome.SERVED
    # Same content and same pinned dates, so the two repositories' commits are the same objects
    # and the payloads are comparable byte for byte.
    assert served.payload == baseline


@pytest.mark.parametrize("locale", ["C", UTF8_LOCALE, "fr_FR.UTF-8"])
def test_a_posix_class_replays_identically_across_parent_locales(
    tmp_path: Path, locale: str, monkeypatch
):
    """Run as a REPLAY across differing parent locales, since that is the failure being
    prevented: `[[:alpha:]]` matches a different character set under C than under UTF-8,
    so an unpinned locale makes two honest replays of one query disagree.

    THIS TEST'S DISCRIMINATING POWER DEPENDS ON THE RUNNER'S AMBIENT LOCALE, which is
    documented nowhere else. `baseline` is built under whatever `LC_ALL`/`LANG` this process
    already inherited -- on this machine, and on most UTF-8-default systems, that is a
    UTF-8 locale. Under that ambient locale, the `C` and `fr_FR.UTF-8` parametrizations
    discriminate (they force ASCII-only classification against a baseline that doesn't) and
    `en_US.UTF-8` does not (it matches the ambient locale, so nothing splits) -- measured on
    this runner. Under an ambient `LC_ALL=C`, it would run exactly backwards: `en_US.UTF-8`
    would discriminate and `C` would not, because `C` would then be what the baseline already
    used. Either way `run_git`'s own `LC_ALL=C`/`LANG=C` pin is what makes every parametrization
    pass regardless of the ambient locale, which is the property under test -- the point is
    not that all three rows discriminate on every machine, but that none of them needs to,
    since the pin removes the parent's locale from the outcome entirely.

    `fr_FR.UTF-8` is not installed here (`locale -a` lists no `fr_FR` variant), so glibc
    silently falls back to `C` for it -- measured identical to the `C` row's own behaviour.
    It is not a third, independently-verified locale on this machine, only a duplicate of
    the `C` row; kept rather than dropped because `LC_ALL=C` still has to defeat whatever the
    parent set, and on a machine where `fr_FR.UTF-8` *is* installed this row tests something
    the `C` row does not."""
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
    """EVERY module in the package, RECURSIVELY. A guard that parses only the top level has
    already decided no defect will arrive through a subpackage, which is exactly the
    assumption a subpackage exists to violate -- plan 3 adds modules to this package, so
    this is not hypothetical. Keyed by path relative to the package root rather than by bare
    filename, since `rglob` can otherwise collide two `__init__.py` files onto one key."""
    return {
        str(path.relative_to(_package_dir())): ast.parse(path.read_text(encoding="utf-8"))
        for path in sorted(_package_dir().rglob("*.py"))
    }


def _names_run_git(func: ast.expr) -> bool:
    """`run_git(...)` and `git.run_git(...)` are the same call and must land the same way.

    MEASURED: a module doing `from science_tool.autonomy import git` and then
    `git.run_git(repo_root, "cat-file", "blob", ...)` passed BOTH derived guards --
    `test_every_git_call_in_the_package_sits_in_a_known_helper`, because the call's `func` is an
    `ast.Attribute` rather than an `ast.Name`, and `test_the_broker_makes_no_direct_subprocess_
    call`, because `science_tool` is not a spawning module and `run_git` is not a spawning name.
    An unauthorized, unaudited path to git, admitted silently by both. The receiver is ignored
    for the same reason the spawn check ignores it: the import spelling is not the hazard.
    """
    if isinstance(func, ast.Name):
        return func.id == "run_git"
    return isinstance(func, ast.Attribute) and func.attr == "run_git"


def _run_git_callers(tree: ast.Module) -> set[str]:
    """Every scope a `run_git(...)` call sits in: a function or async function's name,
    or `"<module level>"` for a call inside neither.

    A per-`FunctionDef` walk that asks "is this call inside a function" has no case for
    "inside nothing at all" -- a module-level `run_git(...)` statement, reachable on import,
    would be invisible to it. It also has no case for `async def`, which `isinstance(...,
    ast.FunctionDef)` alone does not match. This walks the tree once, tracking the nearest
    enclosing (async or sync) function by name as it descends, so both gaps close together.
    """
    callers: set[str] = set()

    def visit(node: ast.AST, scope: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, child.name)
                continue
            if isinstance(child, ast.Call) and _names_run_git(child.func):
                callers.add(scope)
            visit(child, scope)

    visit(tree, "<module level>")
    return callers


def test_every_git_call_in_the_package_sits_in_a_known_helper():
    """Derived from the code, not from a list someone maintains -- same spirit as
    `tests/test_instrument_boundary.py`. A `run_git` call added to `policy.py`, to a module
    that does not exist yet, to a subpackage, to module scope, inside an `async def`, or
    spelled `git.run_git(...)` through a module import, fails here rather than quietly
    acquiring an unaudited path to git."""
    callers: dict[str, set[str]] = {
        name: _run_git_callers(tree) for name, tree in _module_asts().items()
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
#: NOT the bare prefix `"exec"`: it rejects an innocuous `execute_plan()` (measured --
#: plan 3 adds a CLI handler to this package, so that false positive is a landmine, not a
#: hypothetical). Every `os` exec function is `exec` + `l` or `v` (+ optional `p`/`e`):
#: `execl`, `execle`, `execlp`, `execlpe`, `execv`, `execve`, `execvp`, `execvpe`. Narrowing
#: to `execl`/`execv` keeps all eight and drops everything that merely starts with `exec`.
#:
#: `create_subprocess` is `asyncio`'s pair, `create_subprocess_exec` and
#: `create_subprocess_shell`. Neither matches any other prefix or name here, and `asyncio` is
#: not a spawning MODULE (it is a legitimate import for reasons having nothing to do with
#: launching processes), so without this prefix both spellings passed every check in this file.
_SPAWNING_PREFIXES = (
    "execl",
    "execv",
    "spawn",
    "popen",
    "posix_spawn",
    "fork",
    "create_subprocess",
)
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
    modules = _module_asts()
    # Otherwise this guard (and every other one that reads `_module_asts()`) passes
    # vacuously over zero modules if package discovery ever breaks -- it never asserted it
    # saw the modules it claims to cover. Measured: an empty directory passes every loop
    # below with nothing to check.
    assert {"serve.py", "policy.py"} <= set(modules)
    for name, tree in modules.items():
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
