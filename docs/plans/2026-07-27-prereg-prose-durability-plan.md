# `prereg.prose-path-nondurable` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Report, as an ungated WARN, when a frozen pre-registration names a
slash-containing repo-relative path in prose that resolves to a real file or
directory git will not preserve.

**Architecture:** Four helpers plus one integration point, all added to the
existing `validate/checks/prereg_vehicles.py`. Text extraction narrows a
document's inline code spans to candidate paths; a tri-state git wrapper answers
*ignored* / *untracked* / *could not determine*; the check yields one WARN per
`(document, path)`. No existing rule changes behaviour.

**Tech Stack:** Python 3.13, plain stdlib (`re`, `subprocess`, `pathlib`),
pytest with real `git init` repositories in `tmp_path`.

**Design:** `docs/plans/2026-07-27-prereg-prose-durability-design.md`. Read it
before starting. Where this plan and the design disagree, the design wins and
the plan is the bug.

## Global Constraints

- **Rule name is exactly `prereg.prose-path-nondurable`.** Not `vehicle-`
  prefixed. It is a public contract (JSON output, acceptance entries,
  downstream docs).
- **Severity is `Severity.WARN`, and the rule name is added to NO tier in
  `gates.py`.** Adding it to a tier is a plan violation.
- **The message must assert only what git proves.** Git state establishes that
  a path is ignored or untracked — that git will not preserve it. It does NOT
  establish that regenerating the file destroys anything of value, because the
  path may be a future output location. Every consequence must sit behind the
  conditional *"if this document's claims depend on it"*.
- **Never read a git failure as a negative answer.** Exit 0 and exit 1 are
  answers; anything else means *not determined* and produces no finding.
- **No existing test may change.** The only permitted edit to an existing test
  is the one added assertion in Task 6.
- Working directory for all commands: `science/` inside the worktree
  (`.worktrees/prereg-prose-durability/science`), except Task 1 and Task 8,
  which run from the worktree root.
- Test command: `uv run --frozen pytest <path> -q`.
- Commit style: conventional commits. **No AI-attribution trailer or footer.**

## File Structure

| File | Responsibility |
|---|---|
| `science/src/science_tool/validate/checks/prereg_vehicles.py` | *(modify)* all new helpers and the integration point. The rule belongs beside the durability doctrine it completes; the file is ~180 lines and stays readable. |
| `science/tests/validate/test_checks_prereg_vehicles.py` | *(modify)* all new tests, appended. Existing tests untouched except Task 6's single added assertion. |
| `science/src/science_tool/validate/gates.py` | *(modify)* comment only — records that the rule is deliberately absent, and why. |
| `docs/plans/2026-07-27-prereg-prose-durability-results.md` | *(create)* corpus certification results. |

## Task order

Filing comes **first** and closure **last**, per the batch workflow: the entry
records a defect that exists now, and it cannot honestly be closed until
certification has measured what shipped.

---

### Task 1: File the feedback entry

Runs **before** any implementation. The store is CLI-managed and lives outside
every project tree, at `~/.config/science/feedback/`. **Do not hand-write a YAML
file there** — the id must be allocated by the tool.

**Files:**
- Create: `~/.config/science/feedback/fb-2026-07-27-0NN.yaml` (id allocated by
  the CLI; not in the repository)

**Interfaces:**
- Consumes: nothing.
- Produces: an `fb-` id, needed by Task 7's results document and Task 8.

- [ ] **Step 1: Reuse an existing target string rather than inventing one**

Run from the worktree root:

```bash
uv run --frozen --directory science science feedback targets
```

Confirm `check:prereg.vehicle-undeclared` is the existing spelling and use it
verbatim below. If it is absent, use the closest existing `check:` target rather
than coining a new namespace.

- [ ] **Step 2: File the entry**

```bash
uv run --frozen --directory science science feedback add \
  --target "check:prereg.vehicle-undeclared" \
  --category gap \
  --concern tooling \
  --project natural-systems \
  --summary "prereg.vehicle-undeclared is satisfied by one declared vehicle, so its remedy can be discharged against the most convenient artifact while the load-bearing substrate stays undeclared" \
  --detail "$(cat <<'EOF'
Surfaced by natural-systems task:t896.

pre-registration:0014's Primary Beta Operationalization section -- the section
enumerating the LOCKED settings -- names its corpus in a bullet:

  - local arXiv corpus with the corpus hash recorded in
    `data/processed/arxiv/datapackage.json`;

data/processed/ is gitignored in that project. task:t629 regenerated the corpus
on 2026-05-30, the registered hash stopped matching, and NOTHING IN THE
REPOSITORY CHANGED, because the descriptor recording the hash was itself
untracked. The hand-run guard scripts/t392/validate_freeze.py went red and was
not run again for eight weeks. The corpus is unrecoverable.

Had that bullet been a vehicles: entry, prereg.vehicle-gitignored (ERROR, gated
at the hygiene tier) would have failed the build in May, before the loss.

THE EVASION, DEMONSTRATED LIVE. 0014 declared no vehicles, so
prereg.vehicle-undeclared fired once frozen_because began reading amendments:
(fb-2026-07-26-019). The remedy applied in t896 was to declare the two
substrates that had SURVIVED. That silenced the warning without touching the
path that caused the loss, which remains named in the same frozen document,
still gitignored, still unchecked. No bad faith is required -- declaring the
recoverable substrates was correct -- and the document is still mis-certified.

THE CHECK FAMILY CANNOT SEE ITS OWN FOUNDING INCIDENT. pre-registration:0001
and 0026 both still name pipeline/graph-analysis/data/graph-export.json, the
artifact destroyed in fb-2026-07-11-024 that caused these rules to exist. 0001
names it as a declaration, not a reminiscence: "**Source:**
`pipeline/graph-analysis/data/graph-export.json` field .limitRelations".
science validate reports nothing about either.
EOF
)"
```

- [ ] **Step 3: Record the allocated id**

The command prints the id. Note it — Task 7 writes it into the results document
and Task 8 closes it. Verify with:

```bash
uv run --frozen --directory science science feedback show «fb-id»
```

Confirm the detail survived the heredoc intact (the backticks and the
`- local arXiv corpus` bullet in particular) and the status is `open`.

- [ ] **Step 4: No commit**

The feedback store is outside the repository. There is nothing to commit in this
task; `git status` must still be clean.

---

### Task 2: Tri-state git wrapper

The existing `_git_ok` collapses every non-zero exit into `False`. Reusing it
would read a git failure as "not tracked" and manufacture a finding out of an
error. Verified exit codes: `check-ignore -q` and `ls-files --error-unmatch`
both return **0** (yes), **1** (no), **128** (failure, e.g. a path outside the
worktree).

**Files:**
- Modify: `science/src/science_tool/validate/checks/prereg_vehicles.py`
- Test: `science/tests/validate/test_checks_prereg_vehicles.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `_git_query(root: Path, *args: str) -> bool | None` — `True` on
  exit 0, `False` on exit 1, `None` on any other exit.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/validate/test_checks_prereg_vehicles.py`:

```python
def test_git_query_maps_zero_to_true(project: Path) -> None:
    from science_tool.validate.checks.prereg_vehicles import _git_query

    project.joinpath(".gitignore").write_text("build/\n", encoding="utf-8")
    _write_vehicle(project, "build/a.json")

    assert _git_query(project, "check-ignore", "-q", "--", "build/a.json") is True


def test_git_query_maps_one_to_false(project: Path) -> None:
    from science_tool.validate.checks.prereg_vehicles import _git_query

    _write_vehicle(project, "inputs/a.json")

    assert _git_query(project, "check-ignore", "-q", "--", "inputs/a.json") is False


def test_git_query_maps_any_other_exit_to_none(project: Path) -> None:
    """A git failure is not a negative answer.

    `_git_ok` returns False for exit 128, which would let an out-of-worktree
    path or a broken repository be reported as non-durable.
    """
    from science_tool.validate.checks.prereg_vehicles import _git_query

    assert _git_query(project, "check-ignore", "-q", "--", "../outside") is None
    assert _git_query(project, "ls-files", "--error-unmatch", "--", "../outside") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --frozen pytest tests/validate/test_checks_prereg_vehicles.py -q -k git_query`

Expected: FAIL — `ImportError: cannot import name '_git_query'`.

- [ ] **Step 3: Write the implementation**

In `science/src/science_tool/validate/checks/prereg_vehicles.py`, immediately
after the existing `_git_ok` function:

```python
def _git_query(root: Path, *args: str) -> bool | None:
    """git's answer, or None when git did not answer at all.

    `_git_ok` above collapses every non-zero exit into False, which is right
    for its two callers because they act only on a positive. It is WRONG for a
    rule whose finding asserts that git demonstrably will not preserve a path:
    `check-ignore` and `ls-files --error-unmatch` both exit 128 on failure (an
    out-of-worktree path, a broken repository), and reading that as "no" would
    manufacture findings out of errors.
    """
    completed = subprocess.run(["git", *args], cwd=root, capture_output=True)
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --frozen pytest tests/validate/test_checks_prereg_vehicles.py -q`

Expected: PASS, 24 tests (21 existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/checks/prereg_vehicles.py \
        science/tests/validate/test_checks_prereg_vehicles.py
git commit -m "feat(validate): tri-state git wrapper for durability queries"
```

---

### Task 3: Candidate path extraction

Pure text functions, no filesystem or git. The grammar is fixed by the design
because the corpus count depends on it.

Two subtleties carry their own tests because both are silent when wrong:

- **Normalization must be fully lexical, and the scope re-checked after it.**
  `./input.parquet` and `input.parquet/` both satisfy the grammar — the `/` is
  there when it is matched — and both denote a root-level path, which the design
  puts out of scope. Ad-hoc string surgery is not enough: a single `./` strip
  leaves `././input.parquet` as `./input.parquet` (still root-level), turns
  `.//etc/passwd` into the absolute `/etc/passwd` (violating the function's own
  contract), and leaves `build/./` as `build/.`. Use `PurePosixPath` for the
  normalization, then reject absolute paths, `..` segments, and any result with
  no `/`.
- **Fence matching has three CommonMark constraints, and getting any one wrong
  ends a block early and exposes every path in its remainder.** A fence is
  closed only by (a) its *own* delimiter character, at least as long — a `~~~`
  line inside a ``` ``` ``` block is content; (b) a marker followed by nothing
  but whitespace — ```` ```not-a-close ```` is content; and (c) a marker indented
  **0–3 spaces** — at four it is an indented code block, so an indented ```` ``` ````
  inside an open fence is content. An *opening* fence may carry an info string
  (```` ```python ````), which is why the trailing-text rule applies only once a
  block is open. All three have tests.

**Files:**
- Modify: `science/src/science_tool/validate/checks/prereg_vehicles.py`
- Test: `science/tests/validate/test_checks_prereg_vehicles.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `_candidate_paths(body: str) -> list[str]` — normalized,
  order-preserving, de-duplicated, slash-containing repo-relative paths.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/validate/test_checks_prereg_vehicles.py`:

```python
def test_candidate_paths_accepts_a_bare_backticked_path() -> None:
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    assert _candidate_paths("uses `data/raw/foo.json` as input") == ["data/raw/foo.json"]


def test_candidate_paths_rejects_a_span_that_is_not_only_a_path() -> None:
    """Path-shaped arguments are not mined out of commands."""
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    assert _candidate_paths("run `python x.py --in data/raw/foo`") == []


def test_candidate_paths_rejects_urls() -> None:
    """`:` is outside the grammar."""
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    assert _candidate_paths("see `https://example.com/x`") == []


def test_candidate_paths_rejects_root_level_names_in_every_normalized_form() -> None:
    """Root-level paths are out of scope, and the GRAMMAR does not enforce it.

    Every form here contains a `/` when the grammar matches it and denotes a
    root-level path once normalized. `././input.parquet` and `build/./` are the
    forms a single `./`-strip and `rstrip('/')` would let through, which is why
    normalization must be fully lexical.
    """
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    body = (
        "`input.parquet` and `./input.parquet` and `input.parquet/` "
        "and `././input.parquet` and `build/./`"
    )

    assert _candidate_paths(body) == []


def test_candidate_paths_rejects_absolute_paths_however_they_are_spelled() -> None:
    """`//etc/passwd` is POSIX-absolute too, and `PurePosixPath` knows it."""
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    assert _candidate_paths("`/etc/passwd` and `//etc/passwd` and `../secrets/x`") == []


def test_candidate_paths_collapses_redundant_separators() -> None:
    """`.//etc/passwd` is relative `etc/passwd` in POSIX, not the absolute path.

    A naive two-character `./` strip would emit `/etc/passwd` and break the
    function's own repo-relative contract.
    """
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    assert _candidate_paths("`.//etc/passwd` and `a//b/c`") == ["etc/passwd", "a/b/c"]


def test_candidate_paths_ignores_fenced_blocks() -> None:
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    body = "before\n\n```\n`data/raw/foo.json`\n```\n\nafter\n"

    assert _candidate_paths(body) == []


def test_candidate_paths_respects_fence_delimiters() -> None:
    """A `~~~` line inside a backtick fence is content, not the closer.

    Toggling on any fence marker would end the block at `~~~` and expose
    `b/two.json`, which is still inside fenced Markdown.
    """
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    body = "```\n`a/one.json`\n~~~\n`b/two.json`\n```\n\nafter `c/three.json`\n"

    assert _candidate_paths(body) == ["c/three.json"]


def test_candidate_paths_does_not_close_a_fence_on_a_marker_with_trailing_text() -> None:
    """Per CommonMark a CLOSING fence may be followed only by whitespace."""
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    body = "```\n`a/one.json`\n```not-a-close\n`b/two.json`\n```\n\nafter `c/three.json`\n"

    assert _candidate_paths(body) == ["c/three.json"]


def test_candidate_paths_does_not_close_a_fence_on_an_over_indented_marker() -> None:
    """Four spaces makes it an indented code block, not a fence delimiter.

    Verified against the alternative: with an unbounded `^[ \\t]*` this returns
    `['b/two.json']` -- a path that is still inside fenced Markdown.
    """
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    body = "```\n`a/one.json`\n    ```\n`b/two.json`\n```\n\nafter `c/three.json`\n"

    assert _candidate_paths(body) == ["c/three.json"]


def test_candidate_paths_accepts_a_three_space_indented_fence() -> None:
    """0-3 spaces is still a fence; the cap must not break ordinary indentation."""
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    body = "   ```\n`a/one.json`\n   ```\n\nafter `c/three.json`\n"

    assert _candidate_paths(body) == ["c/three.json"]


def test_candidate_paths_allows_an_opening_info_string() -> None:
    """The trailing-text rule applies to CLOSERS only; ```python still opens."""
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    body = "```python\n`a/one.json`\n```\n\nafter `c/three.json`\n"

    assert _candidate_paths(body) == ["c/three.json"]


def test_candidate_paths_ignores_html_comments() -> None:
    """A commented-out path is body text but is not something the document says."""
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    assert _candidate_paths("<!-- was `data/raw/foo.json` -->") == []


def test_candidate_paths_ignores_a_fence_inside_an_html_comment() -> None:
    """Comments are stripped first, so a commented fence cannot desynchronise
    the fence state and swallow the rest of the document."""
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    body = "<!--\n```\n-->\n\nuses `data/raw/foo.json`\n"

    assert _candidate_paths(body) == ["data/raw/foo.json"]


def test_candidate_paths_normalizes_leading_dot_slash_and_trailing_slash() -> None:
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    assert _candidate_paths("`./data/raw/` and `data/raw`") == ["data/raw"]


def test_candidate_paths_deduplicates_preserving_first_appearance() -> None:
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    body = "`b/two.json` then `a/one.json` then `b/two.json`"

    assert _candidate_paths(body) == ["b/two.json", "a/one.json"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --frozen pytest tests/validate/test_checks_prereg_vehicles.py -q -k candidate_paths`

Expected: FAIL — `ImportError: cannot import name '_candidate_paths'`.

- [ ] **Step 3: Write the implementation**

Add `import re` to the imports in
`science/src/science_tool/validate/checks/prereg_vehicles.py` (alphabetically
after `hashlib`), and extend the existing `pathlib` import to
`from pathlib import Path, PurePosixPath`. Then add these module constants below
`_DATA_GATED_MARKER`:

```python
_RULE_PROSE = "prereg.prose-path-nondurable"

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
# Captures the delimiter run so a fence is closed only by its OWN character, at
# least as long -- a `~~~` line inside a ``` block is content, not the closer.
# Indentation is capped at three spaces per CommonMark: at four it is an indented
# code block, so a 4-space ``` inside an open fence is CONTENT. An unbounded
# `^[ \t]*` closes on it and exposes the rest of the block.
_FENCE_LINE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
# The exact grammar behind the design's 23-finding corpus survey. Anchored at
# both ends: a span containing a command, flag, argument or prose fails as a
# whole, so path-shaped arguments are never mined out of a command example. The
# closed class also excludes URLs, since `:` is not in it. It requires a `/`,
# but that is NOT sufficient to keep root-level paths out of scope -- see
# `_normalize`.
_PATH_GRAMMAR = re.compile(r"^[A-Za-z0-9_.][A-Za-z0-9_./+-]*/[A-Za-z0-9_./+-]*$")
```

Then add the functions, after `_vehicle_entries`:

```python
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
            if (
                marker[0] == opener[0]
                and len(marker) >= len(opener)
                and not line[match.end(1) :].strip()
            ):
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --frozen pytest tests/validate/test_checks_prereg_vehicles.py -q`

Expected: PASS, 40 tests (21 existing + 3 + 16).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/checks/prereg_vehicles.py \
        science/tests/validate/test_checks_prereg_vehicles.py
git commit -m "feat(validate): extract candidate repo-relative paths from prereg prose"
```

---

### Task 4: Durability resolution

Turns a candidate path into `"ignored"`, `"untracked"`, or nothing. The
directory behaviour is emergent from git's defaults rather than written in our
code, so it is pinned by test.

**Files:**
- Modify: `science/src/science_tool/validate/checks/prereg_vehicles.py`
- Test: `science/tests/validate/test_checks_prereg_vehicles.py`

**Interfaces:**
- Consumes: `_git_query` (Task 2).
- Produces: `_nondurable_state(root: Path, relative: str) -> str | None` —
  `"ignored"`, `"untracked"`, or `None` when durable or undeterminable.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/validate/test_checks_prereg_vehicles.py`:

```python
def test_nondurable_state_reports_an_ignored_file(project: Path) -> None:
    from science_tool.validate.checks.prereg_vehicles import _nondurable_state

    project.joinpath(".gitignore").write_text("build/\n", encoding="utf-8")
    _write_vehicle(project, "build/a.json")

    assert _nondurable_state(project, "build/a.json") == "ignored"


def test_nondurable_state_reports_an_untracked_file(project: Path) -> None:
    from science_tool.validate.checks.prereg_vehicles import _nondurable_state

    _write_vehicle(project, "inputs/a.json")

    assert _nondurable_state(project, "inputs/a.json") == "untracked"


def test_nondurable_state_is_silent_for_a_tracked_file(project: Path) -> None:
    from science_tool.validate.checks.prereg_vehicles import _nondurable_state

    _write_vehicle(project, "inputs/a.json")
    _git(project, "add", "inputs/a.json")
    _git(project, "commit", "-qm", "add")

    assert _nondurable_state(project, "inputs/a.json") is None


def test_nondurable_state_treats_a_directory_with_a_tracked_descendant_as_durable(
    project: Path,
) -> None:
    """`ls-files --error-unmatch` is a pathspec query, so one command answers
    both "is this file tracked" and "does this directory hold a tracked file"."""
    from science_tool.validate.checks.prereg_vehicles import _nondurable_state

    _write_vehicle(project, "inputs/a.json")
    _git(project, "add", "inputs/a.json")
    _git(project, "commit", "-qm", "add")

    assert _nondurable_state(project, "inputs") is None


def test_nondurable_state_reports_a_directory_with_no_tracked_descendant(
    project: Path,
) -> None:
    from science_tool.validate.checks.prereg_vehicles import _nondurable_state

    _write_vehicle(project, "inputs/a.json")

    assert _nondurable_state(project, "inputs") == "untracked"


def test_an_ignored_directory_holding_a_force_added_file_is_treated_as_durable(
    project: Path,
) -> None:
    """Pins the adopted composition, which is emergent rather than written.

    `git check-ignore` suppresses paths git considers tracked, so an ignored
    directory holding a force-added file exits 1 (not ignored) under the
    default query -- `--no-index` would exit 0 -- and falls through to the
    tracked query, which matches the force-added file. Adopted deliberately:
    it keeps this rule in agreement with `_is_ignored` in the declared-vehicle
    rules, and under-reporting is the right error for an advisory rule. Verified
    against natural-systems `data/processed/arxiv`.
    """
    from science_tool.validate.checks.prereg_vehicles import _nondurable_state

    project.joinpath(".gitignore").write_text("build/\n", encoding="utf-8")
    _write_vehicle(project, "build/kept.json")
    _git(project, "add", "-f", "build/kept.json")
    _git(project, "commit", "-qm", "force-add")

    assert _nondurable_state(project, "build") is None


def test_nondurable_state_is_silent_when_the_ignore_query_fails(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """First query fails: a git failure must never become a finding."""
    from science_tool.validate.checks import prereg_vehicles

    monkeypatch.setattr(prereg_vehicles, "_git_query", lambda *args, **kwargs: None)

    assert prereg_vehicles._nondurable_state(project, "inputs/a.json") is None


def test_nondurable_state_is_silent_when_the_tracked_query_fails(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SECOND query fails, which a blanket `lambda: None` never reaches.

    Without this arm the `matched is None` branch is untested: the function
    short-circuits at `check-ignore`, so an implementation written as a bare
    `if matched:` would pass the whole suite while silently reporting every
    unverifiable path as untracked.
    """
    from science_tool.validate.checks import prereg_vehicles

    def fake_query(root: Path, *args: str) -> bool | None:
        return False if args[0] == "check-ignore" else None

    monkeypatch.setattr(prereg_vehicles, "_git_query", fake_query)

    assert prereg_vehicles._nondurable_state(project, "inputs/a.json") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --frozen pytest tests/validate/test_checks_prereg_vehicles.py -q -k "nondurable_state or force_added"`

(The `-k` expression must be quoted — an unquoted `or` is shell syntax.)

Expected: FAIL — `ImportError: cannot import name '_nondurable_state'`.

- [ ] **Step 3: Write the implementation**

Add after `_candidate_paths` in
`science/src/science_tool/validate/checks/prereg_vehicles.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --frozen pytest tests/validate/test_checks_prereg_vehicles.py -q`

Expected: PASS, 48 tests.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/checks/prereg_vehicles.py \
        science/tests/validate/test_checks_prereg_vehicles.py
git commit -m "feat(validate): resolve a repo path to its git durability state"
```

---

### Task 5: The rule

Wires the helpers into `check_prereg_vehicles` and produces the finding. The
integration restructures three `continue` statements into `if/elif/else` so the
prose scan can run for **both** the declared and undeclared branches, and yields
its findings last per document.

**Files:**
- Modify: `science/src/science_tool/validate/checks/prereg_vehicles.py:69-109`
- Test: `science/tests/validate/test_checks_prereg_vehicles.py`

**Interfaces:**
- Consumes: `_candidate_paths` (Task 3), `_nondurable_state` (Task 4),
  `_normalize` (Task 3), `_result`, `_vehicle_entries`, `frozen_because`,
  `_DATA_GATED_MARKER`, `_RULE_PROSE`.
- Produces: findings on rule `prereg.prose-path-nondurable`, severity WARN.

- [ ] **Step 1: Write the tests**

Twelve tests. **Only five are red-green** — the other seven assert *quiet*
behaviour that is already quiet today and are regression pins against a
future over-firing implementation. Both kinds are required; do not skip the
seven because they pass immediately.

| test | before implementation |
|---|---|
| `..._naming_an_ignored_path_in_prose_warns` | **FAIL** |
| `..._naming_an_untracked_path_in_prose_warns` | **FAIL** |
| `..._message_does_not_assert_the_path_is_a_substrate` | **FAIL** |
| `..._ignored_directory_holding_a_defective_declared_vehicle...` | **FAIL** |
| `..._named_five_times_is_one_finding` | **FAIL** |
| `..._tracked_prose_path_is_silent` | pass (pin) |
| `..._prose_path_that_does_not_resolve_is_silent` | pass (pin) |
| `..._declared_vehicle_is_not_also_reported...` | pass (pin) |
| `..._unfrozen_prereg_naming_an_ignored_path_is_silent` | pass (pin) |
| `..._data_gated_prereg_naming_an_ignored_path_is_silent` | pass (pin) |
| `..._outside_a_git_repository_are_silent` | pass (pin) |
| `..._silent_when_git_cannot_answer` | pass (pin) |

Append to `science/tests/validate/test_checks_prereg_vehicles.py`:

```python
def test_frozen_prereg_naming_an_ignored_path_in_prose_warns(project: Path) -> None:
    """The `fb-2026-07-11-024` shape, in a bullet instead of frontmatter."""
    project.joinpath(".gitignore").write_text("pipeline/**/data/\n", encoding="utf-8")
    _write_vehicle(project, "pipeline/graph-analysis/data/graph-export.json")
    vehicle = _write_vehicle(project, "inputs/ok.json")
    _git(project, "add", "inputs/ok.json")
    _git(project, "commit", "-qm", "add vehicle")
    _write_prereg(
        project,
        vehicles=_vehicle_block("inputs/ok.json", _sha256(vehicle)),
        body="- **Source:** `pipeline/graph-analysis/data/graph-export.json`\n",
    )

    results = list(check_prereg_vehicles(_ctx(project)))

    assert _rules(results) == ["prereg.prose-path-nondurable"]
    assert results[0].severity.value == "warn"
    assert "pipeline/graph-analysis/data/graph-export.json" in results[0].message


def test_frozen_prereg_naming_an_untracked_path_in_prose_warns(project: Path) -> None:
    """Not ignored, but never committed -- still not preserved."""
    _write_vehicle(project, "data/processed/frame.parquet")
    _write_prereg(project, body="built from `data/processed/frame.parquet`\n")

    results = list(check_prereg_vehicles(_ctx(project)))

    assert _rules(results) == ["prereg.vehicle-undeclared", "prereg.prose-path-nondurable"]
    assert "not tracked by git" in results[1].message


def test_the_prose_message_does_not_assert_the_path_is_a_substrate(project: Path) -> None:
    """The rule proves a durability fact, not that the path is load-bearing.

    Selecting by rule matters: `vehicle-undeclared` is yielded first for this
    document, so `results[0]` is not the finding under test.
    """
    project.joinpath(".gitignore").write_text("build/\n", encoding="utf-8")
    _write_vehicle(project, "build/out.json")
    _write_prereg(project, body="results land in `build/out.json`\n")

    results = list(check_prereg_vehicles(_ctx(project)))
    prose = [r for r in results if r.rule == "prereg.prose-path-nondurable"]

    assert len(prose) == 1
    message = prose[0].message
    # The remedy legitimately names the `vehicles:` FIELD, so a blanket ban on
    # the word would be wrong. What is forbidden is calling the PATH one, and
    # asserting a consequence git does not establish.
    assert "substrate" not in message
    assert f"vehicle {'build/out.json'!r}" not in message
    # Git proves non-preservation. It does NOT prove that regenerating the file
    # changes any bytes, or that no copy exists elsewhere, so the consequence
    # must stay hedged and conditional.
    assert "irrecoverably" not in message
    assert "would leave" not in message
    assert "could leave" in message
    assert "git will not preserve it" in message
    assert "if this document's claims depend on" in message.lower()


def test_a_tracked_prose_path_is_silent(project: Path) -> None:
    _write_vehicle(project, "workflows/breadth/config.yaml")
    _git(project, "add", "workflows/breadth/config.yaml")
    _git(project, "commit", "-qm", "add config")
    _write_prereg(project, body="settings from `workflows/breadth/config.yaml`\n")

    assert _rules(list(check_prereg_vehicles(_ctx(project)))) == ["prereg.vehicle-undeclared"]


def test_a_prose_path_that_does_not_resolve_is_silent(project: Path) -> None:
    """"Destroyed", "illustrative" and "renamed" are indistinguishable."""
    _write_prereg(project, body="once lived at `pipeline/gone/export.json`\n")

    assert _rules(list(check_prereg_vehicles(_ctx(project)))) == ["prereg.vehicle-undeclared"]


def test_a_declared_vehicle_is_not_also_reported_as_a_prose_path(project: Path) -> None:
    """One file, one rule. Exact normalized match, including `./` forms."""
    project.joinpath(".gitignore").write_text("build/\n", encoding="utf-8")
    vehicle = _write_vehicle(project, "build/a.json")
    _write_prereg(
        project,
        vehicles=_vehicle_block("build/a.json", _sha256(vehicle)),
        body="the vehicle is `./build/a.json`\n",
    )

    assert _rules(list(check_prereg_vehicles(_ctx(project)))) == ["prereg.vehicle-gitignored"]


def test_an_ignored_directory_holding_a_defective_declared_vehicle_is_reported(
    project: Path,
) -> None:
    """No parent-directory suppression: the containing root is real information.

    The directory must be NESTED. A bare `build` has no `/` and is out of scope
    by the root-level rule, so it would never be a candidate at all.
    """
    project.joinpath(".gitignore").write_text("artifacts/build/\n", encoding="utf-8")
    vehicle = _write_vehicle(project, "artifacts/build/a.json")
    _write_prereg(
        project,
        vehicles=_vehicle_block("artifacts/build/a.json", _sha256(vehicle)),
        body="under `artifacts/build`\n",
    )

    assert _rules(list(check_prereg_vehicles(_ctx(project)))) == [
        "prereg.vehicle-gitignored",
        "prereg.prose-path-nondurable",
    ]


def test_a_prose_path_named_five_times_is_one_finding(project: Path) -> None:
    project.joinpath(".gitignore").write_text("build/\n", encoding="utf-8")
    _write_vehicle(project, "build/a.json")
    body = "".join(f"line {n} mentions `build/a.json`\n" for n in range(5))
    _write_prereg(project, body=body)

    results = list(check_prereg_vehicles(_ctx(project)))

    assert _rules(results) == ["prereg.vehicle-undeclared", "prereg.prose-path-nondurable"]


def test_an_unfrozen_prereg_naming_an_ignored_path_is_silent(project: Path) -> None:
    """A prose path is an inferred commitment; before freezing it is normal work."""
    project.joinpath(".gitignore").write_text("build/\n", encoding="utf-8")
    _write_vehicle(project, "build/a.json")
    _write_prereg(project, status="active", body="working from `build/a.json`\n")

    assert list(check_prereg_vehicles(_ctx(project))) == []


def test_a_data_gated_prereg_naming_an_ignored_path_is_silent(project: Path) -> None:
    """Data-gated mode legitimately discusses candidate paths."""
    project.joinpath(".gitignore").write_text("build/\n", encoding="utf-8")
    _write_vehicle(project, "build/a.json")
    _write_prereg(
        project,
        body="## Vehicle-Admissibility Gate (data-gated mode)\n\ncandidate `build/a.json`\n",
    )

    assert list(check_prereg_vehicles(_ctx(project))) == []


def test_prose_paths_outside_a_git_repository_are_silent(tmp_path: Path) -> None:
    """Never claim non-durability when git has not answered."""
    tmp_path.joinpath("science.yaml").write_text("name: f\nprofile: research\n", encoding="utf-8")
    tmp_path.joinpath("entities", "pre-registrations").mkdir(parents=True)
    _write_vehicle(tmp_path, "build/a.json")
    _write_prereg(tmp_path, body="from `build/a.json`\n")

    assert _rules(list(check_prereg_vehicles(_ctx(tmp_path)))) == ["prereg.vehicle-undeclared"]


def test_the_rule_is_silent_when_git_cannot_answer(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The caller's half of the tri-state contract."""
    from science_tool.validate.checks import prereg_vehicles

    project.joinpath(".gitignore").write_text("build/\n", encoding="utf-8")
    _write_vehicle(project, "build/a.json")
    _write_prereg(project, body="from `build/a.json`\n")
    monkeypatch.setattr(prereg_vehicles, "_git_query", lambda *args, **kwargs: None)

    assert _rules(list(check_prereg_vehicles(_ctx(project)))) == ["prereg.vehicle-undeclared"]
```

- [ ] **Step 2: Run tests to verify the expected five fail**

Run: `uv run --frozen pytest tests/validate/test_checks_prereg_vehicles.py -q`

Expected: **exactly five failures**, matching the table above. The 48 earlier
tests and the seven regression pins PASS. If a *different* count fails, stop and
reconcile before implementing — a pin failing now means the current behaviour is
not what this plan assumes.

- [ ] **Step 3: Write the message builder and the prose scan**

Add after `_nondurable_state` in
`science/src/science_tool/validate/checks/prereg_vehicles.py`:

```python
def _prose_message(relative: str, candidate: str, state: str) -> str:
    """State only what git proves; make every consequence conditional.

    Git establishes that the path is ignored or untracked -- that it will not
    be preserved. It does NOT establish that regenerating the file destroys
    anything: a frozen pre-registration may legitimately name a future OUTPUT
    directory. So the loss language sits behind the author's "if", and the
    message never calls the path a substrate or a vehicle.
    """
    state_text = "gitignored" if state == "ignored" else "not tracked by git"
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
) -> Iterator[Result]:
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
        yield _result(Severity.WARN, relative, _prose_message(relative, candidate, state), _RULE_PROSE)
```

- [ ] **Step 4: Restructure the loop body to call it**

In `check_prereg_vehicles`, replace the block from `entries = _vehicle_entries(frontmatter)`
through the closing `yield from _check_vehicle(ctx, relative, entry)` with:

```python
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
                    "prereg.vehicle-undeclared",
                )
        elif not is_repo:
            yield _result(
                Severity.WARN,
                relative,
                f"{relative} declares vehicles but {ctx.project_root} is not a git repository, so "
                f"their durability cannot be verified.",
                "prereg.vehicle-unverifiable",
            )
        else:
            for entry in entries:
                yield from _check_vehicle(ctx, relative, entry)

        if is_repo and freeze_reason is not None and not data_gated:
            yield from _check_prose_paths(ctx, relative, body, entries)
```

- [ ] **Step 5: Run the full check suite**

Run: `uv run --frozen pytest tests/validate/test_checks_prereg_vehicles.py -q`

Expected: PASS, 60 tests. If an *existing* test now fails, the restructure
changed behaviour — revert Step 4 and redo it, do not edit the existing test.

- [ ] **Step 6: Run the whole validate suite and typecheck**

```bash
uv run --frozen pytest tests/validate -q
uv run --frozen pyright src/science_tool/validate/checks/prereg_vehicles.py
```

Expected: all pass, no new type errors.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/validate/checks/prereg_vehicles.py \
        science/tests/validate/test_checks_prereg_vehicles.py
git commit -m "feat(validate): prereg.prose-path-nondurable"
```

---

### Task 6: Record the deliberate gate absence

**Files:**
- Modify: `science/src/science_tool/validate/gates.py:82-87`
- Modify: `science/tests/validate/test_checks_prereg_vehicles.py` (one added assertion)

**Interfaces:**
- Consumes: the rule name from Task 5.
- Produces: nothing. This task adds a comment and an assertion; it must NOT add
  the rule to any tier set.

- [ ] **Step 1: Add the assertion**

In `science/tests/validate/test_checks_prereg_vehicles.py`, in
`test_durability_failures_gate_the_build_but_undeclared_does_not`, add after
the existing `assert "prereg.vehicle-unverifiable" not in gated` line:

```python
    assert "prereg.prose-path-nondurable" not in gated
```

- [ ] **Step 2: Confirm it passes, then prove it can fail**

Run: `uv run --frozen pytest tests/validate/test_checks_prereg_vehicles.py -q -k gate`

Expected: PASS. This assertion is a **regression pin**, not a red-green cycle —
it passes on day one and its job is to fail if someone later gates the rule.
Prove it is wired up: temporarily add `"prereg.prose-path-nondurable"` to the
`hygiene` frozenset in `gates.py`, re-run (expect FAIL), then **revert the
frozenset edit**.

- [ ] **Step 3: Add the explanatory comment**

In `science/src/science_tool/validate/gates.py`, immediately after the existing
`prereg.vehicle-unverifiable` comment lines that close the `hygiene` frozenset:

```python
            # `prereg.prose-path-nondurable` is deliberately ABSENT from every tier, for two
            # independent reasons. (1) It is advisory by construction: it proves that a frozen
            # document names a path git will not preserve, NOT that the path is load-bearing.
            # A pre-registration may legitimately name an ignored OUTPUT directory, so an ERROR
            # would assert a contradiction the predicate does not establish. This reason does not
            # expire when the corpus is clean. (2) Certification forbids it today anyway: 16
            # findings across 6 of the 11 projects holding pre-registrations. A ratchet is
            # therefore not merely deferred pending migration -- it would first require a
            # narrower predicate that genuinely implies contradiction. See
            # docs/plans/2026-07-27-prereg-prose-durability-design.md.
```

- [ ] **Step 4: Verify nothing changed behaviourally**

Run: `uv run --frozen pytest tests/validate -q`

Expected: PASS, and `git diff science/src/science_tool/validate/gates.py` shows
comment lines only — no change inside any `frozenset({...})`.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/gates.py \
        science/tests/validate/test_checks_prereg_vehicles.py
git commit -m "docs(gates): record why prose-path-nondurable is ungated"
```

---

### Task 7: Corpus certification

Reproduce the design's table with the shipped code. If the numbers differ from
the design, **the results document records the measured numbers** and the
discrepancy is investigated before the branch merges — do not edit the design to
match a surprise.

**Files:**
- Create: `docs/plans/2026-07-27-prereg-prose-durability-results.md`

**Interfaces:**
- Consumes: the shipped rule from Tasks 5–6; the `fb-` id from Task 1.
- Produces: nothing consumed by later tasks except the numbers Task 8 cites.

- [ ] **Step 1: Confirm the snapshot fixture is unaffected**

Run: `uv run --frozen pytest tests/validate -q -m snapshot`

Expected: PASS with no snapshot diff. `tests/validate/fixtures/_combined` has no
`entities/pre-registrations/` directory, so the check returns before reading any
document. **A snapshot diff here means something unintended changed — investigate
it; do not run `scripts/update-validate-snapshots.py`.**

- [ ] **Step 2: Derive the cohort, then validate every member**

**Do not hand-list the projects.** The design's first survey did, and it was
wrong twice: it named `~/d/multiple-myeloma`, which does not exist (the project
is `~/d/cancer/cancer-types/multiple-myeloma`, holds 61 pre-registrations, and
fires), and it omitted six other projects entirely. A glob against a wrong path
returns nothing, and nothing is indistinguishable from a clean result.

One block, so `CERT_DIR` is in scope throughout — a fresh agent shell does not
carry a variable between fenced blocks.

```bash
set -euo pipefail
CERT_DIR=/tmp/prose-path-nondurable-cert
rm -rf "$CERT_DIR"
mkdir -p "$CERT_DIR"

# `-H` follows ONLY the command-line `~/d` symlink, not nested ones. `-L` also
# descends alias trees and double-counts the same project: `~/d/r/cbioportal` ->
# `cancer/data-sources/cbioportal` and `~/d/r/mm30` ->
# `cancer/cancer-types/multiple-myeloma`. With `-L` this yields 25 projects and a
# 13-row cohort for the same 11 real ones, inflating every total.
find -H ~/d -maxdepth 5 -name science.yaml \
     -not -path "*/.worktrees/*" -not -path "*/templates/*" -not -path "*/tests/*" \
     -printf '%h\n' | sort > "$CERT_DIR/all-projects.txt"

# No `2>/dev/null` on the inner find: a real failure must surface, not be
# mistaken for "this project has no pre-registrations". The directory test is
# what handles the ordinary absent case.
: > "$CERT_DIR/cohort.tsv"
while IFS= read -r root; do
  [ -d "$root/entities/pre-registrations" ] || continue
  count=$(find "$root/entities/pre-registrations" -maxdepth 1 -name '*.md' | wc -l)
  # An explicit `if`, not `[ ... ] && printf`: under `set -e` a false test as the
  # last statement in the loop body would abort the whole discovery pass.
  if [ "$count" -gt 0 ]; then
    printf '%s\t%s\n' "$count" "$root" >> "$CERT_DIR/cohort.tsv"
  fi
done < "$CERT_DIR/all-projects.txt"

echo "projects discovered: $(wc -l < "$CERT_DIR/all-projects.txt")"
echo "cohort:"; cat "$CERT_DIR/cohort.tsv"

cohort_rows=$(wc -l < "$CERT_DIR/cohort.tsv")
if [ "$cohort_rows" -ne 11 ]; then
  echo "FATAL: cohort has $cohort_rows rows, expected 11. The project layout has" >&2
  echo "changed since this plan was written; the design's table needs remeasuring," >&2
  echo "not reinterpreting. Do not proceed." >&2
  exit 1
fi

# `science validate` exits 1 when a report CONTAINS error findings, having
# written the JSON successfully -- a normal outcome for several projects. Run it
# as an `if` condition so `set -e` does not abort on that expected non-zero, and
# treat only a missing or empty report as fatal.
while IFS=$'\t' read -r count root; do
  slug=$(printf '%s' "$root" | sed "s|^$HOME/d/||; s|/|__|g")
  out="$CERT_DIR/$slug.json"
  if uv run --frozen science validate --project-root "$root" --format json --output "$out"; then
    rc=0
  else
    rc=$?
  fi
  if [ ! -s "$out" ]; then
    echo "FATAL: $root exited $rc and wrote no usable report at $out" >&2
    exit 1
  fi
  printf 'ok  rc=%-3s %5s pre-regs  %s\n' "$rc" "$count" "$slug"
done < "$CERT_DIR/cohort.tsv"

reports=$(find "$CERT_DIR" -maxdepth 1 -name '*.json' | wc -l)
if [ "$reports" -ne 11 ]; then
  echo "FATAL: $reports reports written, expected 11" >&2
  exit 1
fi
echo "reports written: $reports"
```

Expected output: `projects discovered: 22`, **11 cohort rows** totalling 144
pre-registrations, 11 reports, no `FATAL`. Several projects will print `rc=1`;
that is expected and is not a certification failure — it means the project has
error-severity findings from other rules.

The block asserts the cohort size rather than only printing it, so a layout
change halts certification instead of silently recertifying a different corpus.

- [ ] **Step 3: Measure findings AND pre-registration totals**

Selecting by exact `rule` equality — substring counting on rendered output
silently miscounts. Pre-registration counts come from `cohort.tsv`, since the
JSON report does not carry that number.

**It fails hard on a missing report.** An earlier draft treated an absent file
as zero findings, which would have "certified" a project that was never
validated — the certification would read identically whether a project has no
findings or was skipped entirely.

```bash
uv run --frozen python - <<'PY'
import collections
import json
import pathlib

CERT_DIR = pathlib.Path("/tmp/prose-path-nondurable-cert")
RULE = "prereg.prose-path-nondurable"
HOME_D = str(pathlib.Path.home() / "d") + "/"

rows = []
for line in (CERT_DIR / "cohort.tsv").read_text().splitlines():
    count, root = line.split("\t")
    slug = root.replace(HOME_D, "").replace("/", "__")
    report = CERT_DIR / f"{slug}.json"
    if not report.is_file():
        raise SystemExit(
            f"MISSING REPORT: {report}. Certification is invalid -- a project that was "
            f"never validated must not be recorded as zero findings. Re-run Step 2."
        )
    hits = [r for r in json.loads(report.read_text())["results"] if r.get("rule") == RULE]
    docs = collections.Counter(r.get("path") for r in hits)
    rows.append((root.replace(HOME_D, ""), int(count), len(docs), hits))

rows.sort(key=lambda r: (-len(r[3]), r[0]))
print(f"{'project':46} {'pre-regs':>9} {'docs':>5} {'findings':>9}")
for name, npre, ndocs, hits in rows:
    print(f"{name:46} {npre:9} {ndocs:5} {len(hits):9}")
print(
    f"{'TOTAL (' + str(len(rows)) + ' projects)':46} "
    f"{sum(r[1] for r in rows):9} {sum(r[2] for r in rows):5} {sum(len(r[3]) for r in rows):9}"
)
print("\n=== design predicted: 11 projects, 144 pre-registrations, 10 documents, 16 findings\n")
for name, _, _, hits in rows:
    for hit in hits:
        print(f"  {name:40} {hit.get('path')}\n      {hit.get('message')}")
PY
```

- [ ] **Step 4: Write the results document**

Create `docs/plans/2026-07-27-prereg-prose-durability-results.md` from this
skeleton, filling every `«…»` from the Step 3 output. Do not leave a `«…»` in
the committed file.

```markdown
# `prereg.prose-path-nondurable` — certification results

Measured against `docs/plans/2026-07-27-prereg-prose-durability-design.md` at
commit «sha».

## Measurement method

The validator ran against every project in the measured fleet. Each complete
report was retained as JSON and findings were selected by exact `rule`
equality; no rendered-output substring count was used. Pre-registration totals
were counted from each project's `entities/pre-registrations/` directory.

    «paste the Step 2 and Step 3 commands verbatim»

## Result

One row per cohort member, in the order Step 3 printed them. The cohort is
whatever Step 2 derived — do not copy this list from the design; copy it from
the run.

| project | pre-registrations | documents | findings |
|---|---:|---:|---:|
| «project» | «n» | «n» | «n» |
| … | | | |
| **total («n» projects)** | **«n»** | **«n»** | **«n»** |

Design predicted 11 projects, 144 pre-registrations, 10 documents, 16 findings.
Measured: «n»/«n»/«n»/«n» — «matches, or: differs because …».

## Findings

| project | document | path | state |
|---|---|---|---|
| «…» | «…» | «…» | «ignored/untracked» |

## Gate status

`prereg.prose-path-nondurable` appears in no tier of `gates.py`; pinned by
`test_durability_failures_gate_the_build_but_undeclared_does_not`.

## Snapshots

`tests/validate/fixtures/_combined` has no `entities/pre-registrations/`
directory, so `-m snapshot` produced no diff, as predicted.

## Filing

`«fb-id»` against `check:prereg.vehicle-undeclared`, filed before
implementation. **Status: open — closed in Task 8, which rewrites this section.**
```

Write it as `open`. Task 8 closes the entry and then updates this section; a
results document that claims a closure which has not happened is the same class
of defect this whole branch is about.

If the measured total differs from the design's, record the measured numbers
here and investigate before merging. Do not edit the design to match a surprise —
a discrepancy means either the implementation or the design's survey is wrong,
and which one it is matters.

- [ ] **Step 5: Commit**

```bash
git add docs/plans/2026-07-27-prereg-prose-durability-results.md
git commit -m "docs(plans): certify prose-path-nondurable against the corpus"
```

---

### Task 8: Close the feedback entry

Runs last, because the resolution cites what certification measured.

**Files:**
- Modify: `~/.config/science/feedback/«fb-id».yaml` (via CLI)
- Modify: `docs/plans/2026-07-27-prereg-prose-durability-results.md` (`## Filing`)

**Interfaces:**
- Consumes: the `fb-` id from Task 1 and the measured numbers from Task 7.
- Produces: nothing.

- [ ] **Step 1: Close the entry with the measured resolution**

Replace `«n»` with the certified finding and document counts from Task 7:

```bash
uv run --frozen --directory science science feedback update «fb-id» \
  --status addressed \
  --resolution "Shipped prereg.prose-path-nondurable (WARN, ungated): a frozen pre-registration naming a slash-containing repo-relative path in prose that git will not preserve is now reported. Certified against the corpus at «n» findings across «n» documents. ADVISORY by construction -- it proves the durability fact and leaves the load-bearing question to the author, since a frozen document may legitimately name an ignored output directory -- so it is deliberately absent from every gate tier and the general completeness gap in vehicle-undeclared remains open by design."
```

- [ ] **Step 2: Verify the closure actually took**

```bash
uv run --frozen --directory science science feedback show «fb-id»
```

Expected: status `addressed`, resolution present, original detail intact. **Do
not proceed to Step 3 unless this shows `addressed`** — Step 3 records the
closure as fact, and recording an unverified state is the defect this branch
exists to prevent.

- [ ] **Step 3: Update the results document to record the closure**

In `docs/plans/2026-07-27-prereg-prose-durability-results.md`, replace the
`## Filing` section's `Status: open — closed in Task 8, which rewrites this
section.` with the confirmed state: `addressed`, plus the resolution's first
sentence.

- [ ] **Step 4: Commit the results-document update**

```bash
git add docs/plans/2026-07-27-prereg-prose-durability-results.md
git commit -m "docs(feedback): close the prereg vehicle-completeness filing"
```

The feedback store itself is outside the repository, so this commit contains
only the results-document change; `git status` must be clean afterwards.

---

## Final verification

- [ ] `uv run --frozen pytest -q` from `science/` — full suite green, 60 tests
      in `tests/validate/test_checks_prereg_vehicles.py`.
- [ ] `uv run --frozen pytest -q -m snapshot` — no snapshot diff.
- [ ] `git diff --check` — clean.
- [ ] `grep -rn "vehicle-prose" science/ docs/plans/*-design.md` — no hits; the
      rule is `prereg.prose-path-nondurable` everywhere. (Scoped away from this
      plan, which names the old string once in this very line.)
- [ ] `grep -n "prose-path-nondurable" science/src/science_tool/validate/gates.py`
      — appears in a comment only, never inside a `frozenset({...})`.
- [ ] `uv run --frozen --directory science science feedback show «fb-id»` —
      status `addressed`.
