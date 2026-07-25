# S7a — the retired command surface

**Date:** 2026-07-25
**Status:** Design, approved. Ready for an implementation plan.
**Program:** [`2026-07-25-ideal-core-target.md`](2026-07-25-ideal-core-target.md) §6
**Inventory:** [`2026-07-25-multi-surface-fact-inventory.md`](2026-07-25-multi-surface-fact-inventory.md)

## 1. What the target document got wrong

The target's §6 said retired commands are "registered, callable, and advertise
themselves with encouraging help text. Nothing in-band warns an agent off," and set
the goal: *a retired command is unregistered, or it errors naming the replacement.*

**Measured against the code, that goal is already met.** All 22 retired command
bodies — not the 7 the target named, which was the user guide's list rather than the
code's — raise a `ClickException` naming a replacement. Each body is a *single*
statement; none does work first. There are tests
(`test_graph_cli.py:167`, `TestInquiryMutatorsRetired`). `budget/registry.py` carries
exactly 22 entries reading `"fixed retired-command error"`, agreeing with the code
name for name. `docs/user-guide/cli-and-workflows.md:22` defines a formal **Retired**
status and applies it.

The retired set:

| Group | Count | Commands |
|---|---|---|
| `inquiry` | 5 | `add-node`, `add-edge`, `add-assumption`, `add-transformation`, `set-estimand` |
| `graph` | 3 | `migrate-addresses`, `stamp-revision`, `import` |
| `graph add` | 14 | `concept`, `article`, `proposition`, `observation`, `evidence`, `hypothesis`, `question`, `edge`, `finding`, `interpretation`, `discussion`, `falsification`, `story`, `mechanism` |

## 2. The defect that is actually there

Four surfaces answer "is this command retired?" Three agree on 22. The fourth — the
one an agent reads first — says zero.

| Surface | Answer |
|---|---|
| Command body (`raise _retired_*`) | 22 |
| `budget/registry.py` | 22, agreeing |
| `docs/user-guide/cli-and-workflows.md` | a **Retired** status row |
| `--help` output | **0** |

This produces two failures, and the second is the expensive one.

**(a) The listing advertises the dead as live.**

```
$ science inquiry --help
  add-node            Add a node to an inquiry, optionally with a...
  add-assumption      Add an assumption to an inquiry with provenance.
  list                List all inquiries.
```

Nothing separates `add-node` from `list`. An agent choosing a command from `--help`
has no in-band signal at the moment of choice.

**(b) The retirement sits behind parameter validation.**

```
$ science inquiry set-estimand someslug
Error: Missing option '--treatment'.
```

Click validates parameters before invoking the callback, so the retirement message is
unreachable until the invocation is *completely correct*. An agent reads a usage error
as its own mistake and retries with more arguments. **The system requires you to
succeed at constructing the call before it will tell you the call is impossible** —
a retry loop by construction, and the concrete cost of the target's principle 2.

Neither failure is drift. The fact is currently *consistent*; nothing holds it that
way, and `--help` was never wired to it at all.

## 3. Design

### 3.1 `RetiredCommand`

A `click.Command` subclass in its own module. This is the sole declaration of the
fact.

```python
class RetiredCommand(click.Command):
    """A command that exists only to name its replacement."""

    def __init__(self, name: str, *, forward: str) -> None:
        super().__init__(name, params=[], hidden=True, help=f"Retired. {forward}")
        self.forward = forward

    def parse_args(self, ctx, args):
        raise click.ClickException(f"`{ctx.command_path}` is retired. {self.forward}")
```

Each clause carries its weight:

- **`parse_args`** is click's first touch of `argv`. Raising there puts the error
  ahead of all parameter handling — fix (b), structurally, rather than as a
  convention someone must remember.
- **`params=[]`** leaves nothing to advertise and no unreachable declarations to
  maintain.
- **`hidden=True`** removes it from the listing — fix (a).

**Accepted consequence:** `science inquiry add-node --help` errors rather than
printing usage. Asking for help on a retired command should say it is retired.

### 3.2 `RetiredGroup`

`graph add` has fourteen subcommands and **all fourteen are retired**. Hiding them
individually would leave `science graph add --help` printing a header over an empty
command list — a group advertising that it exists and does nothing.

`graph add` therefore becomes a retired *group*: hidden from `science graph --help`,
holding its fourteen distinct forward paths, and answering with the one matching
whatever subcommand was requested. `graph add concept` still points at
`science entity create concept`; `graph add hypothesis` still at
`science hypotheses create`. Only the empty shell is lost.

The group must answer three cases itself — bare `graph add`, `graph add --help`, and an
unknown subcommand — while leaving the fourteen children to answer for themselves. Two
click 8.3 mechanics decide the implementation, and both were verified against the
installed version rather than reasoned about:

- **`no_args_is_help` defaults to `True` on `Group`,** so a bare invocation prints
  usage and exits 2 *before* dispatch.
- **`--help` is eager,** handled during parameter processing, also before dispatch.

Overriding `resolve_command` therefore catches neither: measured, bare `graph add`
exits 2 with a usage block and `graph add --help` exits 0, both without reaching the
override. Overriding `parse_args` to raise unconditionally would catch both but also
swallow `graph add concept`, collapsing fourteen forward paths into one generic
message.

**The resolution is to intercept in `parse_args` only for the two argument-shapes that
name no child, then delegate:**

```python
class RetiredGroup(click.Group):
    def parse_args(self, ctx, args):
        if not args or args[0] in ("-h", "--help"):
            raise self._retired(ctx)
        return super().parse_args(ctx, args)

    def resolve_command(self, ctx, args):
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            raise self._retired(ctx) from None
```

Intercepting ahead of `super()` subsumes both eager paths, so `no_args_is_help` never
fires and needs no setting; and `resolve_command` converts only the unknown-child
`UsageError`, leaving known children to dispatch normally. Verified behaviour:

| Invocation | Answers with |
|---|---|
| `graph add` | the group's retirement |
| `graph add --help` | the group's retirement |
| `graph add bogus` | the group's retirement |
| `graph add concept` | **`concept`'s own forward path** |
| `graph add concept --help` | **`concept`'s own forward path** |
| `graph add concept x --path /tmp` | **`concept`'s own forward path** |

So `graph add` is retired at the group level *and* its fourteen leaves are retired
individually. That is not redundancy: the leaves own the forward paths, and the group
owns only the cases where no leaf is named.

The fourteen forward paths stay written out, one per subcommand. They are not derived
from a pattern: `concept` → `science entity create concept`, but `proposition` →
`science propositions create`, and `edge` → author `relations.yaml`. An explicit
table is correct here.

### 3.3 The manifest is the owner

A first draft had the CLI declare the retirements and a test assert that
`budget/registry.py` agreed. That is not one owner — it is two authorities plus a
reconciliation, which is the very shape this program exists to remove. An equality
test makes drift *detectable*; it does not make it *impossible*.

So the owner is a plain mapping in the retirement module, keyed by invocation path:

```python
RETIREMENTS: dict[str, str] = {
    "inquiry add-node": INQUIRY_MUTATION_FORWARD,
    ...
    "graph add concept": "Run `science entity create concept <title>` "
                         "(or edit entities/concepts/<slug>.md), "
                         "then run `science graph build`.",
}
```

Both consumers derive from it:

- **The CLI** registers each entry as a `RetiredCommand` on the group its key names.
- **`budget/registry.py`** computes its exemptions instead of listing them:

  ```python
  EXEMPTIONS = {
      ...,
      **{path: "fixed retired-command error" for path in RETIREMENTS},
  }
  ```

`budget/registry.py` currently imports only stdlib, and the manifest introduces no
cycle — nothing in the retirement module imports budget.

Now the registry *cannot* disagree, and §5's claim is true rather than aspirational.
The residual risk the guard must cover changes accordingly: not "do the two lists
match?" but "did someone register a `RetiredCommand` that the manifest does not name?"

**Each `forward` is the complete message tail, verbatim.** Today `_retired_writer`
appends `, then run \`science graph build\`.` to all seventeen graph messages and
`_retired_mutator` ends the five inquiry messages the same way; `test_graph_cli.py:176`
asserts `"science graph build"` appears. A `forward` that carried only the fragment
would silently drop that suffix and fail the unchanged graph tests. Repeating the
suffix seventeen times is the boring choice and the correct one — it also lets a
message that should *not* end in a build step say so, which the shared formatter could
not express.

Each of the 22 sites collapses to one manifest entry, deleting roughly 400 lines of
parameters that can never be read.

### 3.4 One accepted loss

The five inquiry commands currently interpolate the slug — *"Edit
`entities/patches/someslug.md`"*. Without parsing, the slug is unavailable, so the
message becomes *"Edit the inquiry's patch source under `entities/patches/`."*

The agent supplied the slug; the message was not telling it anything it did not have.
Dropping it also stops the message implying we validated a slug we never read. The
seventeen `graph` messages interpolate nothing and are preserved verbatim.

## 4. The guard

`science/tests/test_cli_retirement.py`. It derives the live retired set by walking
`main`'s command tree and collecting **leaf `RetiredCommand` instances** —
`RetiredGroup` is a container and is excluded, since `RETIREMENTS` keys invocations and
`graph add` alone is not one. The derived set is 22, not 23. It then asserts:

1. **The live CLI tree matches `RETIREMENTS` exactly, in both directions.** Since
   `budget/registry.py` now *computes* its entries (§3.3), the registry can no longer
   disagree and needs no assertion. What remains guardable is registration: a
   `RetiredCommand` reachable in the CLI but absent from the manifest, or a manifest
   entry that never got registered.
2. **No retired command declares parameters.** Belt for §3.1.
3. **No retired command appears in its parent's `--help`.**
4. **Every retired command errors on a *bare* invocation, with no arguments.**
5. **`graph add` errors bare, on `--help`, and on an unknown subcommand, while
   `graph add concept` still answers with `concept`'s own forward path** — the four
   rows of §3.2's table that distinguish group-owned from leaf-owned cases.

Assertion 4 is the regression test for the actual defect. Every existing test invokes
these with full valid arguments — which is precisely why nobody noticed that a correct
call was a precondition for learning the call was impossible.

## 5. Effect on the fact

`--help` stops being a surface: it is derived from `hidden` and cannot dissent. The
budget registry stops being a surface: it is derived from `RETIREMENTS` and cannot
dissent. The user guide stays prose.

**One owner, two derived, one prose** — the S1a pattern at a scale small enough to
prove it on. Note what changed to earn that sentence: the first draft claimed it while
leaving the registry a second hand-written list reconciled by a test. A test that
compares two authorities detects drift; it does not remove the second authority. The
distinction is the program's whole thesis, and the design had to be corrected to
respect it.

## 6. Scope

| In | Out |
|---|---|
| `RETIREMENTS` manifest + `RetiredCommand` / `RetiredGroup` | Any command not already retired |
| The 22 declarations; deleting their parameters | Whether the 39 groups carve the space well (S7b) |
| Deriving `budget/registry.py`'s exemptions from the manifest | The `graph add` family's Tier 2/3 deletion (kernel-closure) |
| `test_cli_retirement.py` | Generalizing the ratchet across fact classes (S0) |
| Deleting `TestInquiryAddEdge` (§7) | Migrating "relation claim" in the causal exporters (§7) |
| One line in `cli-and-workflows.md` | |

## 7. Compatibility, and the one behaviour deliberately broken

Every invocation that *executes work* today continues to; every invocation that fails
today continues to fail, earlier and with the same forward path.

**But one currently-succeeding invocation is deliberately broken: `--help` on a retired
command.** Today `science inquiry add-edge --help` and `science graph add edge --help`
both exit 0 and print a usage block. Under §3.1 they error. That is the accepted
consequence stated in §3.1, and it is a real break, not a no-op — an earlier draft of
this section claimed nothing working stopped working, which was false.

**It has a test.** `test_inquiry_cli.py:242`,
`TestInquiryAddEdge.test_edge_claim_help_uses_proposition_language`, asserts
`exit_code == 0` for both of those `--help` invocations *and* that the output contains
`"Supporting proposition reference"` — the help string on the `--claim` option.

That test must be **deleted, not rewritten**, because its subject ceases to exist.
`"Supporting proposition reference"` appears in exactly two places in the source —
`inquiry_cli.py:229` and `graph/cli.py:1084` — both on retired commands, and §3.1
deletes their parameters. There is no live surface to re-point it at.

The test was a vocabulary guard ("proposition", not "relation claim") that happened to
be riding on a dead command's option. Deleting it loses that guard, and the honest
observation is that **the vocabulary it guarded was never fully migrated anyway**:
`relation claim` is still live in `causal/export_chirho.py:131` and
`causal/export_pgmpy.py:446`, asserted by `test_causal_cli.py:320`. Whether the causal
exporters should adopt the same vocabulary is a real question and **out of scope for
S7a** — recorded here so it does not disappear with the test.

Per repo convention there is no compatibility layer and no deprecation window: the
commands are already retired, and this makes the retirement legible rather than
extending it.

## 8. Verification

- `test_cli_retirement.py` passes, including a demonstration that assertions 4 and 5
  fail before the change.
- `test_graph_cli.py` passes **unchanged** — it asserts `"<command> is retired"`, the
  forward key, and `"science graph build"`, all of which still hold once §3.3 keeps
  each `forward` complete.
- `test_inquiry_cli.py` passes with `TestInquiryAddEdge` **removed** per §7;
  `TestInquiryMutatorsRetired` passes unchanged.
- `test_user_guide_docs.py:128` still passes: retired `graph add` surfaces continue to
  "fail with forward-path guidance."
- The full `science` suite. A scan of every `--help` invocation in `tests/` against the
  22 retired names found `test_inquiry_cli.py:246` and nothing else, so §7's single
  deletion is expected to be the only test casualty — but the scan matches on line
  shape, and only the suite settles it.
- `uv run ruff check` and `uv run pyright` clean.

## 9. Open question deferred to S7b

`graph add` is fully retired, so the group is dead weight the moment this ships.
Whether it is *deleted* — rather than hidden — belongs with the kernel-closure Tier
2/3 retirement, which owns that decision. This design deliberately does not pre-empt
it.
