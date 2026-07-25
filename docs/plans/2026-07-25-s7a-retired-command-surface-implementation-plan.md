# S7a Retired Command Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the toolkit's 22 already-retired CLI commands unreachable by discovery and immediately self-describing when invoked, with a single manifest owning the fact.

**Architecture:** Two plain dicts (`RETIREMENTS`, `RETIRED_GROUPS`) become the sole declaration of which commands are retired and what replaces them. A `RetiredCommand` raises from `parse_args` — ahead of all click parameter handling — and carries `hidden=True` and no parameters; a `RetiredGroup` owns the cases where no child is named. `budget/registry.py` computes its retired exemptions from the manifest instead of listing them, and a parametrized guard test binds the live command tree back to the manifest.

**Tech Stack:** Python ≥3.11, click ≥8.1, pytest, uv — the floors declared in
`science/pyproject.toml`, with pyright targeting 3.11. **This plan does not change
either floor.** Every behaviour in it was measured on click 8.3.1, the version in
`uv.lock`; the APIs it relies on (`Context.resilient_parsing`, `Command.parse_args`,
`Group.resolve_command`, `hidden=`) are stable across click 8.x, so no compatibility
work is scoped here. If a future change needs to *raise* the floor, that is its own
task with its own verification.

**Design:** [`meta/doc/plans/2026-07-25-s7a-retired-command-surface-design.md`](../../meta/doc/plans/2026-07-25-s7a-retired-command-surface-design.md)

## Global Constraints

- All commands run from `science/` — this repo has **no root `pyproject.toml`**. `cd science` first.
- Tests: `uv run --frozen pytest`. Lint: `uv run ruff check`. Types: `uv run pyright`.
- The full suite takes ~2–3 min, longer than the default 120s command timeout. Run **scoped** selections during tasks; pass an explicit long `timeout` for any full-suite run.
- Never run two pytest suites concurrently in the same worktree — they race on shared test-output paths.
- Conventional commits. **No AI-attribution trailer or footer** on commits, PRs, or comments.
- Composition over inheritance where there is a choice; explicit over defensive; fail early instead of silent fallbacks.
- **No "legacy"/"compatibility" layers.** These commands are already retired; this makes the retirement legible, it does not extend it.
- No `Unified` prefix on component names.
- Use `~/d/` or relative paths in docs and code, never `/home/keith/` or `/mnt/ssd/`.
- Work happens on branch `system-cohesion` in the worktree `.worktrees/system-cohesion`. **Verify the branch before every commit** — this repo lives in Dropbox and HEAD can move between sessions.

---

## File Structure

| File | Responsibility |
|---|---|
| `science/src/science_tool/cli_retirement.py` | **Create.** The manifests (`RETIREMENTS`, `RETIRED_GROUPS`), the two click classes, and `register_retirements()`. The only place the fact is stated. |
| `science/src/science_tool/cli.py` | **Modify.** One call to `register_retirements(main)` after the last `add_command`. |
| `science/src/science_tool/inquiry_cli.py` | **Modify.** Delete 5 command definitions (59 lines) and `_retired_mutator`. |
| `science/src/science_tool/graph/cli.py` | **Modify.** Delete 17 command definitions and the `graph add` group definition (389 lines) and `_retired_writer`. |
| `science/src/science_tool/budget/registry.py` | **Modify.** Derive the 22 retired `EXEMPTIONS` entries from `RETIREMENTS`. |
| `science/tests/test_cli_retirement.py` | **Create.** The guard: manifest ↔ live tree, no params, unlisted, behaviour on every leaf, six group shapes, completion. |
| `science/tests/test_graph_cli.py` | **Modify.** Rewrite one assertion in `test_graph_add_paper_command_is_removed`. |
| `science/tests/test_inquiry_cli.py` | **Modify.** Delete one method, rename its class. |
| `docs/user-guide/cli-and-workflows.md` | **Modify.** One line: retired commands are unlisted. |

**Why one module rather than per-package manifests:** `budget/registry.py` must import the manifest, and it currently imports only stdlib. A single leaf module with no intra-package imports keeps that edge acyclic and keeps the fact in one file, which is the entire point of the sub-project.

---

## Task 1: The retirement module

Self-contained. Creates the manifests and both click classes, and proves their mechanics against a synthetic command tree. Does not touch the live CLI.

**Files:**
- Create: `science/src/science_tool/cli_retirement.py`
- Test: `science/tests/test_cli_retirement_mechanics.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `RETIREMENTS: dict[str, str]` — 22 entries, invocation path → complete forward text.
  - `RETIRED_GROUPS: dict[str, str]` — 1 entry, same shape.
  - `RetiredCommand(name: str, *, path: str, forward: str)` — a `click.Command`.
  - `RetiredGroup(name: str, *, path: str, forward: str, **kwargs)` — a `click.Group`.
  - `register_retirements(root: click.Group) -> None`.

- [ ] **Step 1: Write the failing mechanics test**

Create `science/tests/test_cli_retirement_mechanics.py`:

```python
"""Mechanics of the retirement classes, against a synthetic tree.

Deliberately does not import the real CLI: this file proves the classes behave,
`test_cli_retirement.py` proves the real tree uses them.
"""

from __future__ import annotations

import click
import pytest
from click.shell_completion import ShellComplete
from click.testing import CliRunner

from science_tool.cli_retirement import RetiredCommand, RetiredGroup


GROUP_FORWARD = "Author the entity instead."
LEAF_FORWARD = "Run `science entity create concept <title>`."
SOLO_FORWARD = "Run `science entity create thing <title>`."


@pytest.fixture
def tree() -> click.Group:
    @click.group()
    def root() -> None:
        """Root."""

    outer = click.Group("outer")
    root.add_command(outer)

    group = RetiredGroup("add", path="outer add", forward=GROUP_FORWARD)
    outer.add_command(group)
    group.add_command(RetiredCommand("concept", path="outer add concept", forward=LEAF_FORWARD))

    outer.add_command(RetiredCommand("solo", path="outer solo", forward=SOLO_FORWARD))
    return root


def test_leaf_errors_before_parameter_validation(tree: click.Group) -> None:
    """The defect this sub-project exists to fix: no correct call is required first."""
    result = CliRunner().invoke(tree, ["outer", "solo"])

    assert result.exit_code == 1
    assert "outer solo is retired" in result.output
    assert "Missing" not in result.output


def test_leaf_errors_on_direct_help(tree: click.Group) -> None:
    result = CliRunner().invoke(tree, ["outer", "solo", "--help"])

    assert result.exit_code == 1
    assert "outer solo is retired" in result.output


def test_leaf_ignores_arbitrary_arguments(tree: click.Group) -> None:
    result = CliRunner().invoke(tree, ["outer", "solo", "a", "b", "--nope", "x"])

    assert result.exit_code == 1
    assert "outer solo is retired" in result.output


def test_leaf_declares_no_parameters(tree: click.Group) -> None:
    assert tree.commands["outer"].commands["solo"].params == []


def test_retired_nodes_are_hidden(tree: click.Group) -> None:
    listing = CliRunner().invoke(tree, ["outer", "--help"]).output

    assert "solo" not in listing
    assert "add" not in listing


@pytest.mark.parametrize(
    ("args", "owner", "forward"),
    [
        (["outer", "add"], "outer add", GROUP_FORWARD),
        (["outer", "add", "--help"], "outer add", GROUP_FORWARD),
        (["outer", "add", "bogus"], "outer add", GROUP_FORWARD),
        (["outer", "add", "concept"], "outer add concept", LEAF_FORWARD),
        (["outer", "add", "concept", "--help"], "outer add concept", LEAF_FORWARD),
        (["outer", "add", "concept", "x", "--path", "/tmp"], "outer add concept", LEAF_FORWARD),
    ],
)
def test_group_and_leaf_cases_are_answered_by_their_owner(
    tree: click.Group, args: list[str], owner: str, forward: str
) -> None:
    """A named child answers for itself; only the unnamed cases fall to the group.

    Asserts the complete message, not just the path. A hard-coded group message that
    ignored its `forward` argument entirely would satisfy a path-only assertion.
    """
    result = CliRunner().invoke(tree, args)

    assert f"{owner} is retired. {forward}" in result.output


def test_unknown_child_keeps_usage_exit_code(tree: click.Group) -> None:
    """Naming a command that does not exist is a usage error: exit 2, not 1."""
    result = CliRunner().invoke(tree, ["outer", "add", "bogus"])

    assert result.exit_code == 2


def test_completion_does_not_raise(tree: click.Group) -> None:
    """Click builds contexts with resilient_parsing=True; raising there is a crash."""
    completer = ShellComplete(tree, {}, "root", "_ROOT_COMPLETE")

    for args in (["outer", "add"], ["outer", "add", "concept"], ["outer", "solo"]):
        completer.get_completions(args, "")


def test_registering_under_a_missing_parent_fails_at_the_boundary(tree: click.Group) -> None:
    from science_tool import cli_retirement

    with pytest.raises(RuntimeError, match="no command 'nope'"):
        cli_retirement._resolve_parent(tree, ["nope"])


def test_registering_under_a_leaf_fails_at_the_boundary(tree: click.Group) -> None:
    """A manifest path naming a leaf as a parent must fail here, not later.

    The descent loop only checks nodes it passes *through*; the terminal node needs its
    own check, or this returns a Command and blows up on `.add_command` far from the
    malformed declaration.
    """
    from science_tool import cli_retirement

    with pytest.raises(RuntimeError, match="is not a group"):
        cli_retirement._resolve_parent(tree, ["outer", "solo"])
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd science && uv run --frozen pytest tests/test_cli_retirement_mechanics.py -q
```

Expected: collection error — `ModuleNotFoundError: No module named 'science_tool.cli_retirement'`.

- [ ] **Step 3: Write the module**

Create `science/src/science_tool/cli_retirement.py`:

```python
"""Which CLI commands are retired, and what replaces them.

This module is the sole declaration of that fact. Two consumers derive from it: the CLI
registers the manifests as real commands, and ``budget/registry.py`` computes its
retired exemptions from ``RETIREMENTS`` rather than repeating the list.

The classes here are the *enforcement mechanism*, not the declaration. A retired command
must be unreachable by discovery (``hidden=True``, no parameters) and must answer before
click validates anything (``parse_args``), because the defect this replaces was a
retirement message that only appeared once the caller had already constructed a
completely correct invocation.
"""

from __future__ import annotations

import click

#: Shared by the five retired inquiry mutators. The slug is deliberately absent: the
#: error fires before parsing, so we have not read one, and the caller supplied it.
INQUIRY_MUTATION_FORWARD = (
    "Edit the inquiry's patch source under `entities/patches/`, then run `science graph build`."
)

_GRAPH_BUILD = "then run `science graph build`."

#: Invocation path -> the complete message tail after "<path> is retired. ".
#:
#: Each value is the whole tail, including the trailing build step. An earlier design
#: factored that step into a shared formatter; keeping it inline lets a message that
#: should NOT end in a build step say so, and keeps these strings byte-identical to what
#: the previous per-command helpers emitted.
RETIREMENTS: dict[str, str] = {
    "inquiry add-node": INQUIRY_MUTATION_FORWARD,
    "inquiry add-edge": INQUIRY_MUTATION_FORWARD,
    "inquiry add-assumption": INQUIRY_MUTATION_FORWARD,
    "inquiry add-transformation": INQUIRY_MUTATION_FORWARD,
    "inquiry set-estimand": INQUIRY_MUTATION_FORWARD,
    "graph migrate-addresses": f"Address direction is canonical at build, {_GRAPH_BUILD}",
    "graph stamp-revision": f"The compiler stamps revisions, {_GRAPH_BUILD}",
    "graph import": f"Raw-triple import is retired; author the source records, {_GRAPH_BUILD}",
    "graph add concept": (
        "Run `science entity create concept <title>` "
        f"(or edit entities/concepts/<slug>.md), {_GRAPH_BUILD}"
    ),
    "graph add article": (
        "Run `science entity create paper <title> --id <citekey>` "
        f"(or edit entities/papers/<citekey>.md with a doi: field), {_GRAPH_BUILD}"
    ),
    "graph add proposition": f"Run `science propositions create <title>`, {_GRAPH_BUILD}",
    "graph add observation": f"Run `science entity create observation <title>`, {_GRAPH_BUILD}",
    "graph add evidence": (
        "Run `science evidence-lines create --target <ref> --stance <supports|disputes>`, "
        f"{_GRAPH_BUILD}"
    ),
    "graph add hypothesis": f"Run `science hypotheses create <title>`, {_GRAPH_BUILD}",
    "graph add question": f"Run `science questions create <title>`, {_GRAPH_BUILD}",
    "graph add edge": (
        "Author the relation in `relations.yaml` (or `relations:` frontmatter) with the "
        f"target graph_layer; claim-cited edges use inquiry flow_edges, {_GRAPH_BUILD}"
    ),
    "graph add finding": f"Run `science entity create finding <title>`, {_GRAPH_BUILD}",
    "graph add interpretation": f"Run `science interpretations create <title>`, {_GRAPH_BUILD}",
    "graph add discussion": f"Run `science discussions create <title>`, {_GRAPH_BUILD}",
    "graph add falsification": (
        "Run `science entity create falsification <title>` "
        f"(set falsifies: to the proposition ref), {_GRAPH_BUILD}"
    ),
    "graph add story": (
        "Run `science entity create story <title>` "
        f"(author synthesizes/organizedBy edges in relations.yaml), {_GRAPH_BUILD}"
    ),
    "graph add mechanism": f"Run `science entity create mechanism <title>`, {_GRAPH_BUILD}",
}

#: Groups retired in their own right, for the cases where no child is named.
#:
#: The text names executable replacements rather than a category. Because the group is
#: hidden, this message is the only thing an agent working from an old transcript sees
#: for a name that no longer resolves -- telling it what it may not do without telling it
#: what to do would reproduce, one level up, the defect this module exists to remove.
RETIRED_GROUPS: dict[str, str] = {
    "graph add": (
        "Author the entity instead — `science entity create <kind> <title>`, or a typed "
        "wrapper such as `science hypotheses create <title>`; author edges in "
        "`relations.yaml` or `relations:` frontmatter. Then run `science graph build`."
    ),
}


class RetiredCommand(click.Command):
    """A command that exists only to name its replacement."""

    def __init__(self, name: str, *, path: str, forward: str) -> None:
        super().__init__(name, params=[], hidden=True, help=f"Retired. {forward}")
        self.path = path
        self.forward = forward

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        if ctx.resilient_parsing:
            return super().parse_args(ctx, args)
        raise click.ClickException(f"{self.path} is retired. {self.forward}")


class RetiredGroup(click.Group):
    """A group whose every child is retired, answering for the cases naming no child."""

    def __init__(self, name: str, *, path: str, forward: str, **kwargs: object) -> None:
        super().__init__(name, hidden=True, **kwargs)  # type: ignore[arg-type]
        self.path = path
        self.forward = forward

    def _message(self) -> str:
        return f"{self.path} is retired. {self.forward}"

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        if ctx.resilient_parsing:
            return super().parse_args(ctx, args)
        if not args or args[0] in ("-h", "--help"):
            raise click.ClickException(self._message())
        return super().parse_args(ctx, args)

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            # Naming a command that does not exist is a usage error: UsageError exits 2,
            # ClickException exits 1, and downgrading that would change the contract for
            # every mistyped subcommand.
            raise click.UsageError(self._message(), ctx) from None


def _resolve_parent(root: click.Group, parts: list[str]) -> click.Group:
    node: click.Command = root
    for part in parts:
        if not isinstance(node, click.Group):
            raise RuntimeError(f"cannot attach retirement: {node.name!r} is not a group")
        child = node.commands.get(part)
        if child is None:
            raise RuntimeError(f"cannot attach retirement: no command {part!r} under {node.name!r}")
        node = child
    if not isinstance(node, click.Group):
        # The loop only checks nodes it must descend *through*; the terminal node is
        # never tested by it. Without this, a manifest path naming a leaf as a parent
        # returns a Command and fails later with AttributeError on .add_command --
        # far from the malformed declaration that caused it.
        raise RuntimeError(f"cannot attach retirement: {node.name!r} is not a group")
    return node


def register_retirements(root: click.Group) -> None:
    """Attach every declared retirement to the live command tree.

    Groups first: a retired leaf may name a retired group as its parent.
    """
    for path, forward in RETIRED_GROUPS.items():
        *parent_parts, name = path.split()
        _resolve_parent(root, parent_parts).add_command(
            RetiredGroup(name, path=path, forward=forward)
        )
    for path, forward in RETIREMENTS.items():
        *parent_parts, name = path.split()
        _resolve_parent(root, parent_parts).add_command(
            RetiredCommand(name, path=path, forward=forward)
        )
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd science && uv run --frozen pytest tests/test_cli_retirement_mechanics.py -q
```

Expected: 13 passed.

- [ ] **Step 5: Lint and type-check**

```bash
cd science && uv run ruff check src/science_tool/cli_retirement.py tests/test_cli_retirement_mechanics.py && uv run pyright src/science_tool/cli_retirement.py
```

Expected: both clean. If pyright objects to `**kwargs: object` on `RetiredGroup.__init__`, narrow it to the kwargs actually used rather than widening to `Any`.

- [ ] **Step 6: Commit**

```bash
cd ..   # repo root of the worktree
git branch --show-current   # must print: system-cohesion
git add science/src/science_tool/cli_retirement.py science/tests/test_cli_retirement_mechanics.py
git commit -m "feat(cli): declare retired commands in one manifest

RetiredCommand raises from parse_args, ahead of click's parameter
handling, so the retirement no longer requires a completely correct
invocation to surface. RetiredGroup answers only the cases naming no
child, and keeps UsageError's exit 2 for an unknown subcommand.

Both classes short-circuit under ctx.resilient_parsing: click builds
contexts that way during shell completion, where raising is a crash
rather than an error report.

Not yet wired to the live CLI."
```

---

## Task 2: Wire the registration and delete the dead parameters

Replaces 22 hand-written command bodies (448 lines, almost all of it parameters that can never be read) with the manifest, and repairs the two tests this necessarily breaks.

**Files:**
- Modify: `science/src/science_tool/cli.py` (after the final `main.add_command(...)`, currently near line 240)
- Modify: `science/src/science_tool/inquiry_cli.py:212-278` and `:25-28`
- Modify: `science/src/science_tool/graph/cli.py:193-209, 275-282, 822-830, 861-1246` and `:38-39`
- Modify: `science/tests/test_graph_cli.py:509-513`
- Modify: `science/tests/test_inquiry_cli.py:244-250`
- Modify: `docs/user-guide/cli-and-workflows.md:22`
- Test: `science/tests/test_cli_retirement.py` (create; structural assertions only — behaviour lands in Task 3)

**Interfaces:**
- Consumes: `RETIREMENTS`, `RETIRED_GROUPS`, `RetiredCommand`, `RetiredGroup`, `register_retirements` from Task 1.
- Produces: a live command tree in which every retired path is a `RetiredCommand`, and `graph add` is a `RetiredGroup`.

- [ ] **Step 1: Write the failing structural guard**

Create `science/tests/test_cli_retirement.py`:

```python
"""The guard: the live command tree and the retirement manifest cannot drift.

Assertions are parametrized over the manifests, so a twenty-third retirement is
covered the moment it is declared rather than when someone remembers to add a case.
"""

from __future__ import annotations

import click
import pytest

from science_tool.cli import main
from science_tool.cli_retirement import RETIRED_GROUPS, RETIREMENTS, RetiredCommand, RetiredGroup


def _nodes(cmd: click.Command, path: tuple[str, ...] = ()) -> list[tuple[str, click.Command]]:
    found = [(" ".join(path), cmd)]
    if isinstance(cmd, click.Group):
        for name, sub in sorted(cmd.commands.items()):
            found.extend(_nodes(sub, (*path, name)))
    return found


def _live_retired_leaves() -> dict[str, RetiredCommand]:
    return {
        path: cmd
        for path, cmd in _nodes(main)
        if isinstance(cmd, RetiredCommand)
    }


def _live_retired_groups() -> dict[str, RetiredGroup]:
    return {
        path: cmd
        for path, cmd in _nodes(main)
        if isinstance(cmd, RetiredGroup)
    }


def test_live_retired_leaves_match_the_manifest() -> None:
    assert set(_live_retired_leaves()) == set(RETIREMENTS)


def test_live_retired_groups_match_the_manifest() -> None:
    assert set(_live_retired_groups()) == set(RETIRED_GROUPS)


@pytest.mark.parametrize("path", sorted(RETIREMENTS))
def test_retired_command_declares_no_parameters(path: str) -> None:
    """Unreachable parameters are not documentation; they are maintenance."""
    assert _live_retired_leaves()[path].params == []


@pytest.mark.parametrize("path", sorted(RETIREMENTS) + sorted(RETIRED_GROUPS))
def test_retired_node_is_hidden(path: str) -> None:
    """--help must not be able to disagree with the manifest about what is live."""
    nodes = {**_live_retired_leaves(), **_live_retired_groups()}
    assert nodes[path].hidden is True
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd science && uv run --frozen pytest tests/test_cli_retirement.py -q
```

Expected: FAIL. `test_live_retired_leaves_match_the_manifest` reports an empty left side — nothing in the live tree is a `RetiredCommand` yet.

- [ ] **Step 3: Wire the registration**

In `science/src/science_tool/cli.py`, add the import near the other `science_tool` imports:

```python
from science_tool.cli_retirement import register_retirements
```

and add this immediately after the final `main.add_command(...)` line (currently `main.add_command(paper_fetch_command)`), before the `if __name__ == "__main__":` block:

```python
# Retired commands are declared in cli_retirement.RETIREMENTS, not here. This must run
# after every group is attached: the manifest resolves parents by walking the live tree.
register_retirements(main)
```

- [ ] **Step 3b: Prove the manifest reproduces today's graph messages verbatim**

This must run **before** Step 5 deletes the seventeen `_retired_writer(...)` call sites,
which are the only remaining witness to what those messages said.

**The comparison must read the old call *arguments*, not re-derive them from the new
manifest.** An earlier draft of this step passed each manifest string, minus its suffix,
back through `_retired_writer` and compared the result to the manifest string — which is
the identity function, and passes for a manifest entry reading `WRONG, then run
\`science graph build\`.` It proved nothing. Extract the old arguments from the AST
instead. Run from `science/`:

```bash
uv run --frozen python - <<'EOF'
import ast, pathlib
from science_tool.cli_retirement import RETIREMENTS

tree = ast.parse(pathlib.Path("src/science_tool/graph/cli.py").read_text())
old = {}
for node in ast.walk(tree):
    if not isinstance(node, ast.FunctionDef):
        continue
    for inner in ast.walk(node):
        if (
            isinstance(inner, ast.Raise)
            and isinstance(inner.exc, ast.Call)
            and getattr(inner.exc.func, "id", "") == "_retired_writer"
        ):
            cmd, forward_path = (ast.literal_eval(a) for a in inner.exc.args)
            old[cmd] = f"{cmd} is retired. {forward_path}, then run `science graph build`."

bad = [
    cmd for cmd in old
    if old[cmd] != f"{cmd} is retired. {RETIREMENTS.get(cmd, '<MISSING>')}"
]
missing = sorted(set(old) - set(RETIREMENTS))
print(f"extracted {len(old)} old messages")
print("MISMATCH:", bad) if bad else print(f"{len(old)}/{len(old)} reproduce verbatim")
print("MISSING FROM MANIFEST:", missing) if missing else None
EOF
```

Expected: `extracted 17 old messages` then `17/17 reproduce verbatim`, and no
`MISSING` line. If any path mismatches, fix the manifest string — do **not** relax
`test_retired_graph_writer_commands_report_forward_path`, which is the contract this
preserves.

The five inquiry messages deliberately do *not* reproduce verbatim: they drop the slug
interpolation, per design §3.4. `TestInquiryMutatorsRetired` asserts only that the output
contains `"retired"`, so it holds either way.

- [ ] **Step 4: Delete the retired inquiry commands**

In `science/src/science_tool/inquiry_cli.py`, delete lines 212–278 — the five command definitions `inquiry_add_node`, `inquiry_add_edge`, `inquiry_add_assumption`, `inquiry_add_transformation`, `inquiry_set_estimand`, with their decorators. Then delete the now-unused helper at lines 25–28:

```python
def _retired_mutator(slug: str) -> click.ClickException:
    return click.ClickException(
        f"Inquiry graph mutation is retired. Edit entities/patches/{slug}.md and run `science graph build`."
    )
```

Leave `inquiry_group`, `list`, `show`, `validate`, `init`, `import`, `export-chirho`, and `export-pgmpy` untouched.

- [ ] **Step 5: Delete the retired graph commands and the `graph add` group**

In `science/src/science_tool/graph/cli.py`, delete these ranges **from the bottom up**, so earlier deletions do not shift later line numbers:

1. Lines 861–1246 — the `@graph_group.group("add")` definition of `graph_add` and all fourteen subcommand definitions beneath it.
2. Lines 822–830 — `graph_import`.
3. Lines 275–282 — `graph_stamp_revision`.
4. Lines 193–209 — `graph_migrate_addresses`.

Then delete the now-unused helper at lines 38–39:

```python
def _retired_writer(command: str, forward_path: str) -> click.ClickException:
    return click.ClickException(f"{command} is retired. {forward_path}, then run `science graph build`.")
```

- [ ] **Step 6: Remove imports left unused by the deletions**

```bash
cd science && uv run ruff check src/science_tool/graph/cli.py src/science_tool/inquiry_cli.py
```

Ruff reports `F401` for every import the deleted bodies were the last user of. Delete exactly those, then re-run until clean. Do not delete an import ruff has not flagged.

- [ ] **Step 7: Run the structural guard to verify it passes**

```bash
cd science && uv run --frozen pytest tests/test_cli_retirement.py tests/test_cli_retirement_mechanics.py -q
```

Expected: all pass — 2 set-equality assertions, 22 parameter assertions, 23 hidden assertions, plus Task 1's 13.

- [ ] **Step 8: Repair `test_graph_add_paper_command_is_removed`**

`paper` was removed outright, not retired, so `graph add paper` now reaches `RetiredGroup.resolve_command`. The exit code is unchanged; the message is not. In `science/tests/test_graph_cli.py`, replace:

```python
def test_graph_add_paper_command_is_removed() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["graph", "add", "paper", "A title", "--story", "story:s01"])
    assert result.exit_code == 2
    assert "No such command 'paper'" in result.output
```

with:

```python
def test_graph_add_paper_command_is_removed() -> None:
    """`paper` is not a command, and the whole `graph add` group is retired.

    The exit code stays 2 -- naming a command that does not exist is a usage error --
    but the message now names a replacement instead of only reporting the mistake.
    """
    runner = CliRunner()
    result = runner.invoke(main, ["graph", "add", "paper", "A title", "--story", "story:s01"])
    assert result.exit_code == 2
    assert "graph add is retired" in result.output
    assert "science entity create" in result.output
```

- [ ] **Step 9: Repair `TestInquiryAddEdge`**

In `science/tests/test_inquiry_cli.py`, delete the method `test_edge_claim_help_uses_proposition_language` entirely (lines 245–250). Its subject was the `--claim` option's help text on two retired commands, and Step 4/5 deleted those parameters — there is no live surface to re-point it at.

Keep `test_compiled_edge_with_relation_claim_attaches_claim_to_edge`, which tests live inquiry compilation. Rename the enclosing class so it describes what survives:

```python
class TestInquiryFlowEdgeClaims:
```

- [ ] **Step 10: Document that retired commands are unlisted**

In `docs/user-guide/cli-and-workflows.md`, line 22, change:

```
| Retired | No longer executes; use the replacement source-authoring or build-from-source path. |
```

to:

```
| Retired | No longer executes and is unlisted in `--help`; invoking one names the replacement source-authoring or build-from-source path. |
```

- [ ] **Step 11: Run every affected suite**

```bash
cd science && uv run --frozen pytest \
  tests/test_cli_retirement.py tests/test_cli_retirement_mechanics.py \
  tests/test_graph_cli.py tests/test_inquiry_cli.py tests/test_inquiry_cli_subsumption.py \
  tests/test_inquiry_e2e.py tests/test_entities_cli.py tests/test_distill.py \
  tests/test_user_guide_docs.py tests/test_command_docs.py -q
```

Expected: all pass. In particular `test_retired_graph_writer_commands_report_forward_path` passes **unchanged** — it asserts `"<command> is retired"`, the forward key, and `"science graph build"`, all of which the manifest preserves verbatim.

`test_entities_cli.py` and `test_distill.py` are in this list because they assert retirement messages directly and would otherwise be missed: `test_entities_cli.py` at lines 1231, 1374, 1395, 1422, and 1444 asserts `"graph add <kind> is retired"`, and `test_distill.py` at lines 260–261 and 272 asserts `"graph import is retired"` and `"Raw-triple import is retired"`. Neither file's name suggests it touches this change.

If `test_user_guide_docs.py` fails on the Step 10 edit, the doc test asserts that row byte-for-byte; update the assertion to match the new wording rather than reverting the doc.

**Do not run the full suite here.** `AGENTS.md` reserves full-suite runs for the top-level agent: a foreground run exceeds the 120s default timeout, auto-backgrounds, and a subagent that yields waiting on it will not reliably resume. The final gate is at the end of this plan.

- [ ] **Step 12: Commit**

```bash
cd ..   # repo root of the worktree
git branch --show-current   # must print: system-cohesion
git add science/src/science_tool/cli.py science/src/science_tool/inquiry_cli.py \
        science/src/science_tool/graph/cli.py science/tests/test_cli_retirement.py \
        science/tests/test_graph_cli.py science/tests/test_inquiry_cli.py \
        docs/user-guide/cli-and-workflows.md
git commit -m "refactor(cli): register retirements from the manifest

Deletes 22 command bodies -- 448 lines, almost all of it parameters
that could never be read, since every body was a single raise.

Two observable changes, both deliberate. --help on a retired command
now errors instead of printing usage, which costs the vocabulary test
whose subject was the --claim option help on two retired commands; the
live compilation test in that class is kept and the class renamed. An
unknown graph add subcommand now names the retirement, keeping exit 2."
```

---

## Task 3: Guard the behaviour, not just the shape

Task 2's guard proves the tree is wired from the manifest. This proves it *behaves* — including the two things no other assertion in the repo covers.

**Files:**
- Modify: `science/tests/test_cli_retirement.py`

**Interfaces:**
- Consumes: `RETIREMENTS`, `RETIRED_GROUPS`, and the helpers defined in Task 2's test file.
- Produces: nothing consumed downstream.

- [ ] **Step 1: Write the failing behaviour assertions**

Append to `science/tests/test_cli_retirement.py`:

```python
@pytest.mark.parametrize("path", sorted(RETIREMENTS))
@pytest.mark.parametrize("suffix", [[], ["--help"]], ids=["bare", "help"])
def test_retired_command_answers_without_a_correct_invocation(path: str, suffix: list[str]) -> None:
    """The regression test for the original defect.

    Every pre-existing test invoked these with full valid arguments, which is exactly
    why nobody noticed that constructing a correct call was a precondition for learning
    the call was impossible. The `--help` case additionally covers a behaviour this
    change makes deliberately, replacing the coverage lost with the old vocabulary test.
    """
    result = CliRunner().invoke(main, path.split() + suffix)

    assert result.exit_code != 0
    assert f"{path} is retired. {RETIREMENTS[path]}" in result.output


@pytest.mark.parametrize(
    ("args", "owner"),
    [
        (["graph", "add"], "graph add"),
        (["graph", "add", "--help"], "graph add"),
        (["graph", "add", "bogus"], "graph add"),
        (["graph", "add", "concept"], "graph add concept"),
        (["graph", "add", "concept", "--help"], "graph add concept"),
        (["graph", "add", "concept", "x", "--path", "/tmp"], "graph add concept"),
    ],
)
def test_group_owned_and_leaf_owned_cases_stay_distinct(args: list[str], owner: str) -> None:
    """Only the shapes naming no child fall to the group; the rest keep their own path.

    Asserts the complete manifest text for whichever owner answers, so a group message
    that ignored `RETIRED_GROUPS` and hard-coded its guidance would fail here.
    """
    forward = RETIRED_GROUPS.get(owner) or RETIREMENTS[owner]
    result = CliRunner().invoke(main, args)

    assert f"{owner} is retired. {forward}" in result.output


def test_unknown_subcommand_keeps_the_usage_exit_code() -> None:
    assert CliRunner().invoke(main, ["graph", "add", "bogus"]).exit_code == 2


def test_shell_completion_over_retired_surfaces_does_not_raise() -> None:
    """Completion builds contexts with resilient_parsing=True.

    Invisible to every other assertion here, because completion never goes through
    normal invocation. Measured against an unguarded draft, both of these raised
    ClickException straight out of ShellComplete.
    """
    completer = ShellComplete(main, {}, "science", "_SCIENCE_COMPLETE")

    for args in (["graph", "add"], ["graph", "add", "concept"], ["inquiry", "add-node"]):
        completer.get_completions(args, "")
```

Add to that file's imports:

```python
from click.shell_completion import ShellComplete
from click.testing import CliRunner
```

- [ ] **Step 2: Run it**

```bash
cd science && uv run --frozen pytest tests/test_cli_retirement.py -q
```

Expected: PASS. These assertions describe Task 2's behaviour, so they are green on arrival — Task 1's mechanics tests were the RED-first proof for this logic, against a synthetic tree, before the live one existed.

- [ ] **Step 3: Prove the guard can fail**

Temporarily edit `science/src/science_tool/cli_retirement.py` to make `RetiredCommand.parse_args` fall through to `super().parse_args(ctx, args)` unconditionally, then:

```bash
cd science && uv run --frozen pytest tests/test_cli_retirement.py -q
```

Expected: the `bare` parametrization of `test_retired_command_answers_without_a_correct_invocation` fails for every leaf that has a required parameter — which is the original defect, reproduced. **Revert the edit** and re-run to confirm green.

A guard that has never been observed to fail is decoration. This step is the only evidence that it is not.

- [ ] **Step 4: Commit**

```bash
cd ..   # repo root of the worktree
git branch --show-current   # must print: system-cohesion
git add science/tests/test_cli_retirement.py
git commit -m "test(cli): guard retirement behaviour, not just registration

Covers bare and --help invocation for all 22 leaves, the six group and
leaf dispatch shapes, the usage exit code for an unknown subcommand,
and shell completion under resilient parsing -- which no other
assertion in the suite reaches, because completion never goes through
normal invocation."
```

---

## Task 4: Derive the budget exemptions

Removes the last surface that independently repeats the retired list.

**Files:**
- Modify: `science/src/science_tool/budget/registry.py:67` (the `EXEMPTIONS` literal) and the 22 retired entries within it
- Test: `science/tests/test_cli_retirement.py`

**Interfaces:**
- Consumes: `RETIREMENTS` from Task 1.
- Produces: `EXEMPTIONS` containing exactly the same 22 retired keys, computed.

**This task is a behaviour-preserving refactor, not TDD.** The registry already holds
exactly the right 22 keys; what is wrong is that it holds them *independently*. Step 1's
test is therefore a **characterization test** — green before and after — and Step 3
changes the source so those keys can no longer be edited in two places. Step 4 is the
real gate: it proves the derivation reproduces the set exactly.

- [ ] **Step 1: Write the characterization test (expected green)**

Append to `science/tests/test_cli_retirement.py`:

```python
def test_budget_exemptions_are_derived_from_the_manifest() -> None:
    """The registry must not be a second place the retired list can be edited.

    An equality assertion between two hand-written lists detects drift; it does not
    remove the second authority. This asserts derivation: every manifest entry is
    exempt for the retirement reason, and no other entry claims that reason.
    """
    from science_tool.budget.registry import EXEMPTIONS

    reason = "fixed retired-command error"
    assert {path for path, why in EXEMPTIONS.items() if why == reason} == set(RETIREMENTS)
```

- [ ] **Step 2: Run it**

```bash
cd science && uv run --frozen pytest tests/test_cli_retirement.py::test_budget_exemptions_are_derived_from_the_manifest -q
```

Expected: PASS — the hand-written list currently happens to agree. That is the point: the test cannot distinguish a coincidence from a derivation, which is why Step 3 changes the source rather than adding a check.

- [ ] **Step 3: Replace the 22 literal entries with a derivation**

In `science/src/science_tool/budget/registry.py`, add to the imports:

```python
from science_tool.cli_retirement import RETIREMENTS
```

Delete all 22 entries whose value is `"fixed retired-command error"` from the `EXEMPTIONS` literal — the `graph add *`, `graph import`, `graph migrate-addresses`, `graph stamp-revision`, and `inquiry add-*` / `inquiry set-estimand` keys. Leave every other entry.

Immediately after the `EXEMPTIONS` literal closes, add:

```python
# Retired commands are exempt by construction: cli_retirement.RETIREMENTS owns which
# commands are retired, and a fixed error string cannot grow with project size. Listing
# them here as well would make this a second place the retired set could be edited.
#
# Deliberately RETIREMENTS only, not RETIRED_GROUPS: test_budget_boundary asserts that
# every classified path is live, where "live" comes from _leaf_commands -- which recurses
# through groups and yields only non-groups. An entry for `graph add` would fail as a
# table naming a command absent from the CLI tree.
EXEMPTIONS.update(dict.fromkeys(RETIREMENTS, "fixed retired-command error"))
```

- [ ] **Step 4: Verify the derivation and the budget contracts**

```bash
cd science && uv run --frozen pytest tests/test_cli_retirement.py tests/test_budget_registry.py tests/test_budget_boundary.py -q
```

Expected: all pass. `test_every_leaf_command_is_classified` still finds no unclassified or stale paths, and `test_classification_partition_has_the_audited_cardinality` still sees `exempt: 67` — the derivation reproduces exactly the 22 keys it replaced, so the count is unchanged.

If the cardinality assertion fails, the derivation added or dropped a key: diff `set(RETIREMENTS)` against the 22 keys deleted in Step 3 before touching the expected count.

- [ ] **Step 5: Check for an import cycle**

```bash
cd science && uv run --frozen python -c "import science_tool.budget.registry; print('ok')"
```

Expected: `ok`. `budget/registry.py` previously imported only stdlib; `cli_retirement` imports only click, so the new edge is acyclic.

- [ ] **Step 6: Lint and types**

```bash
cd science && uv run ruff check && uv run pyright
```

Expected: both clean. **Do not run the full suite here** — see the final gate below.

- [ ] **Step 7: Commit**

```bash
cd ..   # repo root of the worktree
git branch --show-current   # must print: system-cohesion
git add science/src/science_tool/budget/registry.py science/tests/test_cli_retirement.py
git commit -m "refactor(budget): derive retired exemptions from the manifest

The registry listed the same 22 paths the CLI declared. Reconciling two
authorities with a test detects drift; it does not remove the second
authority. EXEMPTIONS now computes those entries from RETIREMENTS.

Derives from RETIREMENTS only, not RETIRED_GROUPS: test_budget_boundary
requires every classified path to be live, and _leaf_commands never
yields a group."
```

---

## Final gate — top-level agent only

**Not a delegated task.** `AGENTS.md` reserves full-suite runs for the top-level agent,
because a foreground run exceeds the 120s default timeout, auto-backgrounds, and a
subagent that yields waiting on it will not reliably resume. Run this once, after Task 4
is committed.

- [ ] **Run the full suite**

```bash
cd science && uv run --frozen pytest -q
```

Pass an explicit 600000 ms timeout. Expected: no failures beyond any already failing on
`main` before this branch — establish that baseline first if it is not already known.

This gate exists because the third design-review round found a broken test,
`test_graph_add_paper_command_is_removed`, that no targeted search would have surfaced:
it concerned a command that was *removed* rather than retired, so it lived under a
different name and asserted a different thing. Step 11 of Task 2 now names two more such
files (`test_entities_cli.py`, `test_distill.py`) found only by grepping for the message
text rather than the concept. There is no reason to believe that list is complete —
only the suite settles it.

- [ ] **Run the model suite**

```bash
cd science/model && uv run --frozen pytest -q
```

Expected: unaffected. Included because the two package suites are independent and a
green `science` suite says nothing about `science-model`.

## Self-Review

**Spec coverage.** Design §3.1 `RetiredCommand` → Task 1. §3.2 `RetiredGroup`, including the `UsageError` choice and the six shapes → Tasks 1 and 3. §3.3 manifests as owner, the complete-`forward` rule, and the registry derivation → Tasks 1 and 4. §3.4 the dropped slug interpolation → Task 1's `INQUIRY_MUTATION_FORWARD`. §4 guard assertions 1–6 → Tasks 2 (1–3), 3 (4–6), 4 (registry). §6 scope → the file table. §7.1 the `graph add paper` repair → Task 2 Step 8; §7.2 the `--help` break and the test deletion → Task 2 Step 9. §8 verification → Task 2 Steps 11–12, Task 4 Step 6. §9 is explicitly deferred and has no task, correctly.

**Placeholders.** None. Every code step carries the literal content, every command carries its expected result, and all 22 forward strings are written out rather than described.

**Type consistency.** `path` and `forward` are the constructor keywords in Task 1 and are used with those names in Tasks 2–4. `register_retirements(root: click.Group) -> None` is called with `main` in Task 2. `_nodes` is defined in Task 2's test file and reused by Task 3's additions to the same file. `RETIREMENTS` and `RETIRED_GROUPS` keep their names and `dict[str, str]` shape throughout.

**Two deviations from strict TDD, both stated rather than hidden.**

Task 3's assertions are green on arrival, because Task 2 necessarily implements the behaviour they describe. The RED-first proof for that logic is Task 1, which tests the same mechanics against a synthetic tree before the live one exists — and Task 3 Step 3 re-establishes falsifiability directly by breaking the implementation and observing the guard fail.

Task 4 is a behaviour-preserving refactor with a **characterization test**, green before and after. Its gate is not a red-to-green transition but Step 4's proof that the derivation reproduces the 22 keys exactly, holding both `test_every_leaf_command_is_classified` and the pinned `exempt: 67` cardinality. An earlier draft labelled its Step 1 "write the failing derivation test" while Step 2 correctly expected a pass — a contradiction that would have told the implementer their environment was broken.

**Full-suite placement.** Tasks 2 and 4 originally ended in full-suite runs, which conflicts with `AGENTS.md` under the recommended subagent execution: a foreground full run auto-backgrounds past the 120s default and a yielding subagent will not reliably resume. Both are replaced by scoped selections, with a single full-suite gate outside the delegated tasks.
