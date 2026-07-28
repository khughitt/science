"""A pre-registration must freeze its vehicle by CONTENT, not by path.

fb-2026-07-11-024 (natural-systems t830). `pre-registration:0026` locked its
vehicle as `pipeline/graph-analysis/data/graph-export.json, exported 2026-04-30,
244 models`. That path was in `.gitignore`, so the "frozen" vehicle was an
untracked build product whose content was a pure function of the working tree.
Executing the registered refresh re-ran the pipeline's first rule, regenerating
the vehicle from a catalogue that had since drifted 244 -> 248 models and
destroying the registered export irrecoverably. The 248-cohort observed
secondaries were then computed AND SEEN, making a downstream cohort decision
post-observation. Nine rounds of adversarial review did not catch it, because
nobody asked whether the named file was durable.

Freezing by path rather than by content is the flaw. Durability is mechanically
checkable, so it is checked here rather than left to review.

`data/` gets no exemption. It is gitignored by design in the standard layout,
which is precisely why it cannot by itself freeze anything: a vehicle living
there must be declared as a content-addressed dataset entity instead.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path, PurePosixPath
from typing import Any

from science_model.audit import FindingRule
from science_model.audit.fingerprint import canonical_json

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.entities import resolve_path_policy
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.prereg_frozen import frozen_because
from science_tool.validate.result import Severity

# Data-gated mode commits the decision rule before any vehicle is admissible,
# so it legitimately names none. The template section is the declaration.
_DATA_GATED_MARKER = "## Vehicle-Admissibility Gate"

_RULE_PROSE = "prereg.prose-path-nondurable"

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
# Captures the delimiter run so a fence is closed only by its OWN character, at
# least as long -- a `~~~` line inside a ``` block is content, not the closer.
# Indentation is capped at three spaces per CommonMark: at four it is an indented
# code block, so a 4-space ``` inside an open fence is CONTENT. An unbounded
# `^[ \t]*` closes on it and exposes the rest of the block.
_FENCE_LINE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
# The exact grammar behind the design's 16-finding corpus survey. Anchored at
# both ends: a span containing a command, flag, argument or prose fails as a
# whole, so path-shaped arguments are never mined out of a command example. The
# closed class also excludes URLs, since `:` is not in it. It requires a `/`,
# but that is NOT sufficient to keep root-level paths out of scope -- see
# `_normalize`.
_PATH_GRAMMAR = re.compile(r"^[A-Za-z0-9_.][A-Za-z0-9_./+-]*/[A-Za-z0-9_./+-]*$")


SECTION, RULES = declare_validation_rules(
    section_id="prereg-vehicles",
    section_title="prereg vehicles",
    section_order=116,
    rule_ids=(
        "prereg.prose-path-nondurable",
        "prereg.vehicle-gitignored",
        "prereg.vehicle-hash-drift",
        "prereg.vehicle-missing",
        "prereg.vehicle-uncontent-addressed",
        "prereg.vehicle-undeclared",
        "prereg.vehicle-untracked",
        "prereg.vehicle-unverifiable",
    ),
    severities=frozenset({"error", "warn", "info"}),
)


def _result(
    severity: Severity,
    relative: str,
    message: str,
    rule: FindingRule,
    *,
    key: list[str],
) -> CheckObservation:
    return validation_observation(
        severity=severity,
        path=Path(relative),
        line=None,
        message=message,
        rule=rule,
        task=None,
        qualifiers={"key": key},
    )


def _git_ok(root: Path, *args: str) -> bool:
    """True when git exits 0. Used for the two boolean queries below."""
    completed = subprocess.run(["git", *args], cwd=root, capture_output=True)
    return completed.returncode == 0


def _git_query(root: Path, *args: str) -> bool | None:
    """git's answer, or None when git did not answer at all.

    `_git_ok` above collapses every non-zero exit into False. That is right
    for `_is_ignored`, which is consumed positively (`if _is_ignored(...)` at
    the declared-vehicle callsite): a git error reads as "not ignored", and
    the check falls through to the tracked query rather than firing. It is
    WRONG for `_is_tracked`, which is consumed NEGATIVELY (`if not
    _is_tracked(...)`): there, `_git_ok`'s collapse turns a git error into
    "not tracked", which fires the gated `prereg.vehicle-untracked` ERROR from
    an undetermined answer rather than a real one. That is a known
    pre-existing fail-open in `_is_tracked`, left unchanged here — this branch
    deliberately scopes declared-vehicle rule changes out, so fixing it would
    alter certified corpus behaviour outside this change's boundary. It is
    filed separately (see the module's incident trail).

    This function exists because the new prose rule cannot inherit either
    caller's excuse: `check-ignore` and `ls-files --error-unmatch` both exit
    128 on failure (an out-of-worktree path, a broken repository), and the
    prose rule's finding asserts that git demonstrably will not preserve a
    path. Reading a 128 as "no" would manufacture that assertion out of an
    error, so the prose rule needs the tri-state answer below rather than
    `_git_ok`'s collapse.
    """
    completed = subprocess.run(["git", *args], cwd=root, capture_output=True)
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    return None


def _is_ignored(root: Path, relative: str) -> bool:
    return _git_ok(root, "check-ignore", "-q", "--", relative)


def _is_tracked(root: Path, relative: str) -> bool:
    return _git_ok(root, "ls-files", "--error-unmatch", "--", relative)


def _vehicle_entries(frontmatter: dict[str, Any]) -> list[Any]:
    declared = frontmatter.get("vehicles")
    if declared is None:
        return []
    if not isinstance(declared, list):
        return [declared]
    return declared


def _strip_fenced_blocks(body: str) -> str:
    """Blank every line inside a fenced code block, delimiters included.

    Tracks the OPENING delimiter, because CommonMark closes a fence only with a
    run of the SAME character, at least as long, followed by nothing but
    whitespace. Two distinct mistakes both end a block early and expose every
    path in its remainder: toggling on a `~~~` line inside a ``` block, and
    closing on ```` ```not-a-close ````. The trailing-text rule applies only
    when a block is already open -- an OPENING fence may carry an info string,
    so ```` ```python ```` must still open.
    """
    lines: list[str] = []
    opener: str | None = None
    for line in body.splitlines():
        match = _FENCE_LINE.match(line)
        if match is not None:
            marker = match.group(1)
            if opener is None:
                opener = marker
                continue
            if marker[0] == opener[0] and len(marker) >= len(opener) and not line[match.end(1) :].strip():
                opener = None
                continue
            # Neither an opener nor a valid closer: content inside the block.
        lines.append("" if opener is not None else line)
    return "\n".join(lines)


def _normalize(token: str) -> str | None:
    """A slash-containing, lexically repo-relative path, or None.

    Normalization is delegated to `PurePosixPath` rather than done with string
    surgery, because the ad-hoc version is wrong in three ways that all look
    fine in isolation: stripping one leading `./` leaves `././input.parquet` as
    `./input.parquet`, turns `.//etc/passwd` into the ABSOLUTE `/etc/passwd`
    -- breaking this function's own contract -- and `rstrip('/')` leaves
    `build/./` as `build/.`. `PurePosixPath` collapses `.` segments and
    redundant separators, and knows that a leading `//` is POSIX-absolute.

    Three rejections then apply, and none is redundant:

    * absolute -- `PurePosixPath.is_absolute()` covers `/x` and `//x`.
    * `..` -- load-bearing, since `.` is in the grammar's leading character
      class, so `../secrets/x` matches the grammar and is stopped only here.
    * no `/` after normalization -- the design puts root-level paths out of
      scope, and the GRAMMAR CANNOT ENFORCE THAT: `./input.parquet` contains a
      `/` when it is matched and denotes a root-level path once normalized.

    The `part != "."` filter below is belt-and-braces, not load-bearing:
    `PurePosixPath` already collapses `.` segments on its own (`.parts` never
    contains one), as stated above. The filter is kept anyway because removing
    it is a behaviour-adjacent edit on a hot path for no measurable gain.
    """
    candidate = token.strip()
    if not candidate:
        return None
    pure = PurePosixPath(candidate)
    if pure.is_absolute():
        return None
    parts = [part for part in pure.parts if part != "."]
    if not parts or any(part == ".." for part in parts):
        return None
    normalized = "/".join(parts)
    if "/" not in normalized:
        return None
    return normalized


def _candidate_paths(body: str) -> list[str]:
    """Normalized repo-relative paths this document names in prose.

    HTML comments are stripped BEFORE fences: a comment may contain a fence
    marker, and opening on it would desynchronise the fence state and swallow
    the rest of the document.
    """
    text = _strip_fenced_blocks(_HTML_COMMENT.sub("", body))
    found: list[str] = []
    seen: set[str] = set()
    for span in _INLINE_CODE.findall(text):
        stripped = span.strip()
        if not _PATH_GRAMMAR.match(stripped):
            continue
        candidate = _normalize(stripped)
        if candidate is None or candidate in seen:
            continue
        seen.add(candidate)
        found.append(candidate)
    return found


def _nondurable_state(root: Path, relative: str) -> str | None:
    """'ignored' or 'untracked', or None when durable or undeterminable.

    Ignored is asked first because it is the stronger statement. Note that
    `git check-ignore` suppresses paths git considers tracked, so an ignored
    directory holding a force-added file answers "not ignored" here and is then
    called durable by the tracked query below. That composition is deliberate:
    it agrees with `_is_ignored` above, so the two rules can never disagree
    about one path, and under-reporting is the right error for an advisory rule.
    """
    ignored = _git_query(root, "check-ignore", "-q", "--", relative)
    if ignored is None:
        return None
    if ignored:
        return "ignored"
    matched = _git_query(root, "ls-files", "--error-unmatch", "--", relative)
    if matched is None or matched:
        return None
    return "untracked"


def _prose_message(relative: str, candidate: str, state: str) -> str:
    """State only what git proves; make every consequence conditional.

    Git establishes that the path is ignored or untracked -- that it will not
    be preserved. It does NOT establish that regenerating the file destroys
    anything: a frozen pre-registration may legitimately name a future OUTPUT
    directory. So the loss language sits behind the author's "if", and the
    message never calls the path a substrate or a vehicle.
    """
    state_text = {"ignored": "gitignored", "untracked": "not tracked by git"}[state]
    return (
        f"{relative} is frozen and names {candidate!r} in prose, which is {state_text}, "
        f"so git will not preserve it. If this document's claims depend on {candidate!r}, "
        f"it is frozen by path rather than by content: git holds no copy to compare "
        f"against, so nothing here can detect a change to the file, and regenerating or "
        f"overwriting it could leave the document certifying content that no longer exists. "
        f"Commit the file, commit and register its descriptor, or declare it as a "
        f"content-addressed dataset entity and add it to 'vehicles:'. If the document does "
        f"not depend on it -- an output location, an illustration -- record that and accept "
        f"this finding."
    )


def _check_prose_paths(
    ctx: ValidateContext,
    relative: str,
    body: str,
    entries: list[Any],
) -> Iterator[CheckObservation]:
    """Yield `prereg.prose-path-nondurable` for each non-durable path this document names in prose.

    Two suppressions here are not self-evident from the code:

    * A candidate already present in `entries` (a declared `vehicles[].path`,
      after normalization) is skipped. That path is the declared-vehicle
      rules' business; reporting it here too would mean one file, two rules.
    * A candidate that does not resolve under the project root (`.exists()`
      is False) is skipped rather than reported as, say, "destroyed" or
      "renamed". Those are indistinguishable from "illustrative" or "a future
      output path stated in advance" from outside the document, and this rule
      refuses to guess. The honest consequence: once a non-durable path named
      here has actually been lost, this rule goes quiet about it. It is a
      hazard detector, never a loss detector.
    """
    declared: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("path"):
            continue
        normalized = _normalize(str(entry["path"]))
        if normalized is not None:
            declared.add(normalized)

    for candidate in _candidate_paths(body):
        if candidate in declared:
            continue
        if not (ctx.project_root / candidate).exists():
            continue
        state = _nondurable_state(ctx.project_root, candidate)
        if state is None:
            continue
        yield _result(
            Severity.WARN,
            relative,
            _prose_message(relative, candidate, state),
            RULES["prereg.prose-path-nondurable"],
            key=["prose-path", candidate],
        )


@Check(section=SECTION, order=13, producer_id="validate.prereg-vehicles", rules=tuple(RULES.values()))
def check_prereg_vehicles(ctx: ValidateContext) -> Iterator[CheckObservation]:
    entities_root = ctx.project_root / resolve_path_policy("pre-registration").root
    if not entities_root.is_dir():
        return
    is_repo = (ctx.project_root / ".git").exists()

    for path in sorted(entities_root.glob("*.md")):
        if not path.is_file():
            continue
        frontmatter = ctx.frontmatter(path)
        if str(frontmatter.get("kind", "")) != "pre-registration":
            continue
        relative = path.relative_to(ctx.project_root).as_posix()
        entries = _vehicle_entries(frontmatter)
        freeze_reason = frozen_because(frontmatter)
        body = ctx.body(path)
        data_gated = _DATA_GATED_MARKER in body

        # `continue` became `elif` so the prose scan below runs for BOTH the
        # declared and the undeclared branch. A document that declares one
        # vehicle is exactly where the prose gap hides: declaring the
        # recoverable substrate silences `vehicle-undeclared` while a
        # non-durable path named in prose goes unexamined.
        if not entries:
            if freeze_reason is not None and not data_gated:
                yield _result(
                    Severity.WARN,
                    relative,
                    f"{relative} is frozen ({freeze_reason}) but declares no 'vehicles:'. A "
                    f"pre-registration that names its data only in prose is frozen by path, not by "
                    f"content: declare each vehicle as 'path' + 'sha256', or state the "
                    f"'{_DATA_GATED_MARKER} (data-gated mode)' section if no vehicle is admissible yet.",
                    RULES["prereg.vehicle-undeclared"],
                    key=["vehicles"],
                )
        elif not is_repo:
            yield _result(
                Severity.WARN,
                relative,
                f"{relative} declares vehicles but {ctx.project_root} is not a git repository, so "
                f"their durability cannot be verified.",
                RULES["prereg.vehicle-unverifiable"],
                key=["repository"],
            )
        else:
            seen_entries: set[str] = set()
            for entry in entries:
                entry_key = canonical_json(entry).decode("utf-8")
                if entry_key in seen_entries:
                    continue
                seen_entries.add(entry_key)
                yield from _check_vehicle(ctx, relative, entry, entry_key=entry_key)

        if is_repo and freeze_reason is not None and not data_gated:
            yield from _check_prose_paths(ctx, relative, body, entries)


def _check_vehicle(
    ctx: ValidateContext,
    relative: str,
    entry: Any,
    *,
    entry_key: str | None = None,
) -> Iterator[CheckObservation]:
    """Report the FIRST way this vehicle fails to be frozen, if any.

    The conditions are ordered by how fundamental they are: an unresolvable or
    non-durable path makes its recorded hash moot, so reporting the hash as well
    would be noise.
    """
    semantic_entry = entry_key or canonical_json(entry).decode("utf-8")
    if not isinstance(entry, dict) or not entry.get("path"):
        yield _result(
            Severity.ERROR,
            relative,
            f"{relative} has a 'vehicles:' entry with no 'path': {entry!r}.",
            RULES["prereg.vehicle-uncontent-addressed"],
            key=["vehicle-entry", semantic_entry],
        )
        return

    declared_path = str(entry["path"])
    digest = entry.get("sha256")
    if not digest:
        yield _result(
            Severity.ERROR,
            relative,
            f"{relative} freezes vehicle {declared_path!r} by path alone. Record its 'sha256:' — a "
            f"path names where the data was, not which data it was.",
            RULES["prereg.vehicle-uncontent-addressed"],
            key=["vehicle-entry", semantic_entry],
        )
        return

    target = ctx.project_root / declared_path
    if not target.is_file():
        yield _result(
            Severity.ERROR,
            relative,
            f"{relative} freezes vehicle {declared_path!r}, which does not exist.",
            RULES["prereg.vehicle-missing"],
            key=["vehicle-entry", semantic_entry],
        )
        return

    if _is_ignored(ctx.project_root, declared_path):
        yield _result(
            Severity.ERROR,
            relative,
            f"{relative} freezes vehicle {declared_path!r}, which is gitignored. An ignored file is "
            f"a local build product, not a frozen record: regenerating it destroys the registered "
            f"content irrecoverably. Commit it, or declare it as a content-addressed dataset entity.",
            RULES["prereg.vehicle-gitignored"],
            key=["vehicle-entry", semantic_entry],
        )
        return

    if not _is_tracked(ctx.project_root, declared_path):
        yield _result(
            Severity.ERROR,
            relative,
            f"{relative} freezes vehicle {declared_path!r}, which is not tracked by git. An "
            f"uncommitted file cannot be recovered once overwritten.",
            RULES["prereg.vehicle-untracked"],
            key=["vehicle-entry", semantic_entry],
        )
        return

    actual = hashlib.sha256(target.read_bytes()).hexdigest()
    if actual != str(digest):
        yield _result(
            Severity.ERROR,
            relative,
            f"{relative} freezes vehicle {declared_path!r} at sha256 {str(digest)[:12]}…, but the "
            f"file on disk is {actual[:12]}…. The registered content is gone even though the path "
            f"still resolves.",
            RULES["prereg.vehicle-hash-drift"],
            key=["vehicle-entry", semantic_entry],
        )
