"""VCS storage boundary checks.

Two universal, five declaration-derived. All seven are mechanical: no heuristic
classifier participates in enforcement, so a finding is always a genuine
self-contradiction in the repository's own configuration.

"Universal" means the check runs for EVERY project -- declared, undeclared, or
with a broken `boundary:` block -- not that it reads no configuration.
`unanchored-pattern` consults the allowlist (falling back to the built-in
default when there is no usable declaration) because an allowlisted rule is
sanctioned by the declaration or canonical defaults, and telling the project to
anchor a rule whose whole purpose is depth-independence would be wrong advice.

SIGN AWARENESS. `unmanaged_rules` returns negations too, and the three rules
that consume it need them differently:

* `declaration-conflict` RECORDS negations -- a hand-written pin under a
  declared root is the per-case exception the declaration abolishes.
* `unanchored-pattern` and `ignored-undeclared` SKIP them. A negation ignores
  nothing, so "can silently swallow tracked source" and "ignores project
  material" are both false of it, and `unmanaged_allow` rejects `!` patterns,
  which would leave the finding permanently unsilenceable.

See docs/plans/2026-07-26-vcs-storage-boundary-design.md.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import yaml
from pydantic import ValidationError

from science_tool.boundary.config import (
    DEFAULT_UNMANAGED_ALLOW,
    BoundaryConfig,
    StorageClass,
)
from science_tool.boundary.generate import ManagedBlockError, extract_managed_block, render_managed_block
from science_tool.boundary.gitio import (
    BoundaryGitError,
    IgnoreRule,
    git_ignores_case,
    governed_ignore_files,
    indexed_paths,
    indexed_regular_blob,
    is_git_worktree,
    matching_unmanaged_rules,
    read_ignore_file,
    tracked_ignored,
    unmanaged_rules,
    visible_paths,
)
from science_tool.boundary.walk import git_ascii_casefold, iter_repo_files, manifest_candidates, matches_tracked_path
from science_tool.data_root import PROJECT_CONFIG_FILENAME
from science_tool.project_config import ProjectConfigError, load_project_config
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

GITIGNORE = Path(".gitignore")


def _is_unanchored_dir_pattern(pattern: str) -> bool:
    """An EXCLUDE that names a bare directory, matching it at any depth.

    Negations are excluded at the top rather than having their `!` stripped. An
    earlier draft stripped it, so `!archive` was reported with a message about
    swallowing tracked source -- the opposite of what a negation does, and
    unsilenceable because `unmanaged_allow` rejects `!` patterns.
    """
    if pattern.startswith("!"):
        return False
    body = pattern
    if body.startswith("/") or "/" in body.rstrip("/"):
        return False
    return body.endswith("/") or "." not in body


def load_boundary_state(
    project_root: Path,
) -> tuple[BoundaryConfig | None, set[tuple[str, str]], Exception | None]:
    """One declaration snapshot: config, effective allowlist, and load error.

    Falls back to the built-in default on a missing OR broken declaration --
    never to the broken one. Returning the error rather than raising lets the
    caller run the universal checks first and report the invalid declaration
    afterwards. Config and allowlist are returned together so validation cannot
    mix two reads if `science.yaml` changes during a run.
    """
    defaults = {(".gitignore", p) for p in DEFAULT_UNMANAGED_ALLOW}
    try:
        cfg = load_project_config(project_root).boundary
    except (OSError, UnicodeDecodeError, ProjectConfigError, ValidationError, yaml.YAMLError) as exc:
        return None, defaults, exc
    if cfg is None:
        return None, defaults, None
    return cfg, {(a.source, a.pattern) for a in cfg.unmanaged_allow}, None


def unanchored_findings(
    rules: list[IgnoreRule],
    allowed: set[tuple[str, str]],
) -> list[IgnoreRule]:
    """Unanchored EXCLUDES the project has not sanctioned.

    Shared by the validate check and the `boundary check` CLI so the two cannot
    drift. They did: the CLI applied neither the sign filter nor the allowlist,
    so a freshly scaffolded project printed six warnings and then "clean".
    """
    return [r for r in rules if (r.source, r.pattern) not in allowed and _is_unanchored_dir_pattern(r.pattern)]


def _conflict_subjects(project_root: Path, root_path: str) -> list[str]:
    """Every extant path under a declared root, plus generic future shapes.

    NOT sampled. An earlier draft capped this at 500 paths, which made an ERROR
    check probabilistic -- a scoped rule affecting the 501st file was silently
    missed. All paths go into one NUL-framed check-ignore call per peeling round,
    so the cost is a couple of subprocesses regardless of tree size; the
    benchmark below bounds it.
    """
    base = project_root / root_path
    probes = [
        f"{root_path}/probe.bin",
        f"{root_path}/probe.parquet",
        f"{root_path}/d1/probe.bin",
        f"{root_path}/d1/d2/d3/probe.bin",
        f"{root_path}/d1/datapackage.json",
    ]
    return sorted(set(probes) | set(iter_repo_files(project_root, base)))


@Check(section="version-control boundary", order=14)
def check_boundary(ctx: ValidateContext) -> Iterator[Result]:
    root = ctx.project_root
    if not is_git_worktree(root):
        return

    # ---- universal: tracked-ignored -------------------------------------
    for hit in tracked_ignored(root):
        yield Result(
            severity=Severity.ERROR,
            path=Path(hit.path),
            line=None,
            message=(
                f"{hit.path} is tracked but matches ignore rule {hit.pattern!r} "
                f"({hit.source}:{hit.line}). Ignore rules are not retroactive, so git will "
                f"never report this on its own, and ripgrep, editor search and ruff all stop "
                f"seeing the file. Resolve by `git rm --cached` if it belongs outside version "
                f"control, or by moving it / narrowing the rule if it belongs inside. Do not "
                f"use `git add -f` or a `!` negation: that records the conflict instead of "
                f"removing it."
            ),
            rule="boundary.tracked-ignored",
            task=None,
        )

    # ---- declaration load, BEFORE unanchored-pattern needs the allowlist --
    # The load is here rather than later because unanchored-pattern consults the
    # allowlist, but its failure does NOT stop the universal checks: a broken
    # declaration is exactly when an unanchored rule is most likely to be
    # lurking. A load failure falls back to the built-in default allowlist,
    # never to the broken one.
    cfg, allowed, cfg_error = load_boundary_state(root)

    # ---- universal: unanchored-pattern ----------------------------------
    # Skips negations (they ignore nothing) and skips allowlisted rules. The
    # allowlist exemption is what keeps a freshly scaffolded project quiet:
    # `.venv/`, `__pycache__/`, `.mypy_cache/`, `.ipynb_checkpoints/`,
    # `*.egg-info/` and `.worktrees/` are all bare directory names, and six of
    # them warned on day one. Anchoring them would be WRONG -- a nested
    # `inc/shiny/.venv/` must still be ignored -- so depth-independence is the
    # intended behaviour there, and the project has said so by declaring them.
    # MM30's bare `archive` is not in the default allowlist, so the motivating
    # case still fires.
    all_unmanaged = unmanaged_rules(root)
    for rule in unanchored_findings(all_unmanaged, allowed):
        yield Result(
            severity=Severity.WARN,
            path=Path(rule.source),
            line=rule.line,
            message=(
                f"ignore pattern {rule.pattern!r} is unanchored and matches a directory of "
                f"that name at ANY depth. Anchor it (`/{rule.pattern.lstrip('/')}`) so it "
                f"cannot silently swallow tracked source in an unrelated subtree. If the "
                f"depth-independence is deliberate, add it to boundary.unmanaged_allow."
            ),
            rule="boundary.unanchored-pattern",
            task=None,
        )

    if cfg_error is not None:
        # NEVER downgrade a broken declaration to "undeclared": that would
        # disable five checks exactly when the configuration is wrong.
        yield Result(
            severity=Severity.ERROR,
            path=Path(PROJECT_CONFIG_FILENAME),
            line=None,
            message=(f"boundary declaration is invalid, so no declared-root check can run: {cfg_error}"),
            rule="boundary.invalid-declaration",
            task=None,
        )
        return

    if cfg is None or not cfg.roots:
        # Implicit-versioned semantics begin at enrollment.
        return

    gitignore_error: BoundaryGitError | None = None
    try:
        gitignore_text = read_ignore_file(root / GITIGNORE)
    except FileNotFoundError:
        gitignore_text = ""
    except BoundaryGitError as exc:
        gitignore_text = ""
        gitignore_error = exc
    managed_body = extract_managed_block(gitignore_text) if gitignore_error is None else None

    declared = [r.path for r in cfg.roots]
    governed = set(governed_ignore_files(root))

    # ---- declared: generated-drift --------------------------------------
    expected = render_managed_block(cfg)
    indexed_managed_body: str | None = None
    indexed_gitignore = indexed_regular_blob(root, GITIGNORE.as_posix())
    if indexed_gitignore is not None:
        try:
            indexed_managed_body = extract_managed_block(indexed_gitignore.decode("utf-8", "surrogateescape"))
        except ManagedBlockError:
            pass
    if gitignore_error is not None:
        yield Result(
            severity=Severity.ERROR,
            path=GITIGNORE,
            line=None,
            message=(
                "cannot verify the science-managed boundary block because the root "
                f".gitignore is unsafe to read: {gitignore_error}"
            ),
            rule="boundary.generated-drift",
            task=None,
        )
    elif managed_body != expected:
        yield Result(
            severity=Severity.ERROR,
            path=GITIGNORE,
            line=None,
            message=(
                "the science-managed boundary block is missing or stale. Run "
                "`science boundary sync` to regenerate it from science.yaml."
            ),
            rule="boundary.generated-drift",
            task=None,
        )
    elif indexed_managed_body != expected:
        yield Result(
            severity=Severity.ERROR,
            path=GITIGNORE,
            line=None,
            message=(
                "the root .gitignore has the current science-managed boundary block but "
                "does not have a tracked, present, regular worktree source backed by a "
                "stage-0 regular blob containing the current managed block. A clone would "
                "not receive the generated boundary. Stage it explicitly with "
                "`git add -f .gitignore` after reviewing any repository-level exclude "
                "that prevented ordinary staging."
            ),
            rule="boundary.generated-drift",
            task=None,
        )

    # ---- declared: allowlist integrity ----------------------------------
    for entry in cfg.unmanaged_allow:
        # Source membership is checked on its own. An earlier draft also required
        # the pattern to be non-default, which exempted
        # {source: "typo/.gitignore", pattern: ".venv/"} -- a silent no-op.
        if entry.source not in governed:
            yield Result(
                severity=Severity.ERROR,
                path=Path(PROJECT_CONFIG_FILENAME),
                line=None,
                message=(
                    f"boundary.unmanaged_allow names {entry.source!r}, which is not a tracked "
                    f"in-worktree .gitignore file. The entry can never match, so it is a silent "
                    f"no-op rather than an excuse."
                ),
                rule="boundary.invalid-declaration",
                task=None,
            )

    # ---- declared: index invariant --------------------------------------
    # Ignore rules are only a mechanism for reaching the declaration's storage
    # state. An untracked nested .gitignore or machine-local exclude can change
    # the winning rule without appearing in the governed-source universe. The
    # index is the durable fact, so validate it directly and independently of
    # effective rule sign or source.
    ignore_case = git_ignores_case(root)
    for indexed in indexed_paths(root):
        indexed_parts = indexed.split("/")
        for declared_root in cfg.roots:
            root_parts = declared_root.path.split("/")
            if len(indexed_parts) < len(root_parts):
                continue
            indexed_prefix = indexed_parts[: len(root_parts)]
            if ignore_case:
                indexed_prefix = [git_ascii_casefold(part) for part in indexed_prefix]
                root_parts = [git_ascii_casefold(part) for part in root_parts]
            if indexed_prefix != root_parts:
                continue
            relative = "/".join(indexed_parts[len(root_parts) :])

            if declared_root.storage_class is StorageClass.MANIFEST and relative:
                if matches_tracked_path(
                    relative,
                    declared_root.tracked,
                    case_sensitive=not ignore_case,
                ):
                    continue

            if declared_root.storage_class is StorageClass.PAYLOAD:
                detail = "payload roots permit no indexed path at or below the declared root"
            else:
                detail = (
                    f"root-relative path {relative!r} does not match any declared tracked glob "
                    f"{list(declared_root.tracked)!r}"
                )
            yield Result(
                severity=Severity.ERROR,
                path=Path(indexed),
                line=None,
                message=(
                    f"{indexed!r} is indexed at or below {declared_root.storage_class.value} root "
                    f"{declared_root.path!r}, but {detail}. Effective negations and untracked "
                    "ignore sources cannot override science.yaml. Remove the path from the "
                    "index with `git rm --cached -- <path>`."
                ),
                rule="boundary.index-violation",
                task=None,
            )

    by_location = {(r.source, r.line): r for r in all_unmanaged}

    # ---- declared: declaration-conflict ---------------------------------
    # Ask GIT which rules match each declared root. Text prefix comparison
    # cannot: `*.parquet` affects data/external without naming it, and
    # `data/raw` inside inc/.gitignore scopes to inc/, not the repo root.
    # NOTE the ordering -- the allowlist is deliberately NOT consulted here. It
    # excuses undeclared noise; it may never excuse a rule that targets a
    # declared root, or it would reopen the adjudication this check closes.
    conflicted: set[tuple[str, int]] = set()
    for declared_root in declared:
        subjects = _conflict_subjects(root, declared_root)
        for probe, owners in sorted(matching_unmanaged_rules(root, subjects).items()):
            for owner in owners:
                key = (owner.source, owner.line)
                if key not in by_location or key in conflicted:
                    continue  # already reported
                conflicted.add(key)
                yield Result(
                    severity=Severity.ERROR,
                    path=Path(owner.source),
                    line=owner.line,
                    message=(
                        f"hand-written rule {owner.pattern!r} matches {probe} inside declared "
                        f"root {declared_root!r}. The declaration in science.yaml is the single "
                        f"authority for that root; a rule outside the managed block re-opens "
                        f"per-case adjudication. (Detected by evaluating the unmanaged rules in "
                        f"isolation under git's own engine and peeling away each reported rule, "
                        f"so wildcards and nested .gitignore scoping are accounted for and a rule "
                        f"shadowed by the managed block, or by another hand-written rule, is "
                        f"still reported.)"
                    ),
                    rule="boundary.declaration-conflict",
                    task=None,
                )

    # ---- declared: ignored-undeclared -----------------------------------
    for rule in all_unmanaged:
        # A negation ignores nothing, so this predicate is simply false of it --
        # and `unmanaged_allow` rejects `!` patterns, so a finding here could
        # never be silenced. Inside a declared root a negation is still reported,
        # by declaration-conflict above.
        if rule.pattern.startswith("!"):
            continue
        if (rule.source, rule.pattern) in allowed or (
            rule.source,
            rule.line,
        ) in conflicted:
            continue
        yield Result(
            severity=Severity.WARN,
            path=Path(rule.source),
            line=rule.line,
            message=(
                f"rule {rule.pattern!r} ignores project material with no declared storage class. "
                f"Declare a root in science.yaml, or add it to boundary.unmanaged_allow. There is "
                f"no shape heuristic here: a rule is excused because it was declared, never "
                f"because it looks like tooling."
            ),
            rule="boundary.ignored-undeclared",
            task=None,
        )

    # ---- declared: unreachable-tracked ----------------------------------
    visible = visible_paths(root)
    for declared_root in cfg.roots:
        if declared_root.storage_class is not StorageClass.MANIFEST:
            continue
        for candidate in manifest_candidates(root, declared_root):
            if candidate in visible:
                continue
            yield Result(
                severity=Severity.ERROR,
                path=Path(candidate),
                line=None,
                message=(
                    f"{candidate} matches a tracked: glob of manifest root "
                    f"{declared_root.path!r} but git will not surface it -- `git add .` stages "
                    f"nothing and no diagnostic reports a problem. The usual cause is a bare "
                    f"directory exclude stopping git descending. Run `science boundary sync`."
                ),
                rule="boundary.unreachable-tracked",
                task=None,
            )
