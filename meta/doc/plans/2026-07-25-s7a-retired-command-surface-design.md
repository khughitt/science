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

**`RetiredGroup` must not raise in `parse_args`.** Doing so would answer before
resolving which subcommand was asked for, collapsing fourteen forward paths into one
generic message — the opposite of the goal. Instead it keeps normal group dispatch and
carries `hidden=True`, so its fourteen children stay ordinary `RetiredCommand`
instances and each raises its own forward path from its own `parse_args`. The group
overrides only two behaviours:

- **an unknown subcommand** errors naming the group's retirement, rather than click's
  "No such command", so a misremembered name still lands on the forward path;
- **`graph add` with no subcommand, and `graph add --help`,** error the same way
  instead of printing the empty listing.

So `graph add` is retired at the group level *and* its fourteen leaves are retired
individually. That is not redundancy: the leaves own the forward paths, and the group
owns the two cases where no leaf is named.

The fourteen forward paths stay written out, one per subcommand. They are not derived
from a pattern: `concept` → `science entity create concept`, but `proposition` →
`science propositions create`, and `edge` → author `relations.yaml`. An explicit
table is correct here.

### 3.3 The 22 declarations

Each site collapses to one registration call, deleting roughly 400 lines of
parameters that can never be read.

```python
retire(inquiry_group, "add-node", forward=INQUIRY_MUTATION_FORWARD)
retire(graph_add, "concept", forward="Run `science entity create concept <title>` "
                                     "(or edit entities/concepts/<slug>.md)")
```

The five inquiry commands share one forward string (they already do, via
`_retired_mutator`); the seventeen `graph` commands each keep their own, verbatim.

### 3.4 One accepted loss

The five inquiry commands currently interpolate the slug — *"Edit
`entities/patches/someslug.md`"*. Without parsing, the slug is unavailable, so the
message becomes *"Edit the inquiry's patch source under `entities/patches/`."*

The agent supplied the slug; the message was not telling it anything it did not have.
Dropping it also stops the message implying we validated a slug we never read. The
seventeen `graph` messages interpolate nothing and are preserved verbatim.

## 4. The guard

`science/tests/test_cli_retirement.py`. It derives the retired set by walking `main`'s
command tree and collecting **leaf `RetiredCommand` instances** — `RetiredGroup` is a
container and is excluded, since `budget/registry.py` keys invocations, and
`graph add` alone is not one. The derived set is therefore 22, not 23. It then
asserts:

1. **The derived set equals `budget/registry.py`'s `"fixed retired-command error"`
   set.** The two surfaces that agree today by luck agree by construction after.
2. **No retired command declares parameters.** Belt for §3.1.
3. **No retired command appears in its parent's `--help`.**
4. **Every retired command errors on a *bare* invocation, with no arguments.**
5. **`graph add` errors bare, on `--help`, and on an unknown subcommand** — the three
   cases §3.2 gives the group to own.

Assertion 4 is the regression test for the actual defect. Every existing test invokes
these with full valid arguments — which is precisely why nobody noticed that a correct
call was a precondition for learning the call was impossible.

## 5. Effect on the fact

`--help` stops being a surface. It is derived from `hidden`, so it cannot dissent.
The budget registry is bound to the code by assertion 1. The user guide stays prose.

**One owner, two derived, one prose** — the S1a pattern at a scale small enough to
prove it on.

## 6. Scope

| In | Out |
|---|---|
| `RetiredCommand` / `RetiredGroup` module | Any command not already retired |
| The 22 declarations; deleting their parameters | Whether the 39 groups carve the space well (S7b) |
| `test_cli_retirement.py` | The `graph add` family's Tier 2/3 deletion (kernel-closure) |
| One line in `cli-and-workflows.md` | Generalizing the ratchet across fact classes (S0) |

## 7. Compatibility

Retired commands already fail. Every invocation that works today continues to work;
every invocation that fails today continues to fail, earlier and with the same forward
path. The user-visible changes are that retired commands leave `--help`, and that a
*wrong* invocation of one now reports the retirement instead of a usage error.

Per repo convention there is no compatibility layer and no deprecation window: the
commands are already retired, and this makes the retirement legible rather than
extending it.

## 8. Verification

- `test_cli_retirement.py` passes, including a demonstration that assertion 4 fails
  before the change.
- `test_graph_cli.py` and `test_inquiry_cli.py` pass unchanged — they assert the
  forward path, which still holds when the error fires earlier.
- `test_user_guide_docs.py:128` still passes: retired `graph add` surfaces continue to
  "fail with forward-path guidance."
- `uv run ruff check` and `uv run pyright` clean.

## 9. Open question deferred to S7b

`graph add` is fully retired, so the group is dead weight the moment this ships.
Whether it is *deleted* — rather than hidden — belongs with the kernel-closure Tier
2/3 retirement, which owns that decision. This design deliberately does not pre-empt
it.
