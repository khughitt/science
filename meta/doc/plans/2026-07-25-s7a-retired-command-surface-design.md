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

A `click.Command` subclass in its own module. It is the **runtime enforcement
mechanism**, not the declaration — §3.3's manifests own the fact, and this class is
what makes the declaration binding at the CLI boundary.

```python
class RetiredCommand(click.Command):
    """A command that exists only to name its replacement."""

    def __init__(self, name: str, *, path: str, forward: str) -> None:
        super().__init__(name, params=[], hidden=True, help=f"Retired. {forward}")
        self.path = path
        self.forward = forward

    def parse_args(self, ctx, args):
        if ctx.resilient_parsing:
            return super().parse_args(ctx, args)
        raise click.ClickException(f"{self.path} is retired. {self.forward}")
```

Each clause carries its weight:

- **`parse_args`** is click's first touch of `argv`. Raising there puts the error
  ahead of all parameter handling — fix (b), structurally, rather than as a
  convention someone must remember.
- **`params=[]`** leaves nothing to advertise and no unreachable declarations to
  maintain.
- **`hidden=True`** removes it from the listing — fix (a).
- **`ctx.resilient_parsing`** must short-circuit to `super()`. Click builds contexts
  with `resilient_parsing=True` during shell completion, where raising is not an error
  report but a crash: measured against the unguarded draft, completing `graph add` and
  `graph add concept` both raised `ClickException` out of `ShellComplete`. A retired
  command should be absent from completion — which `hidden=True` already achieves —
  not poison it.
- **`path`** is the manifest key, and the message uses it rather than
  `ctx.command_path`. Two reasons, both measured. Backticks around the path break
  `test_graph_cli.py:175`, which asserts the contiguous substring
  `"graph add concept is retired"`; ``` `main graph add concept` is retired ``` does
  not contain it. And `ctx.command_path` is prefixed by the program name, which is
  `main` under `CliRunner` but `science` in real use — so the same code would emit
  two different messages depending on who called it. The manifest key is exactly
  `"graph add concept"`, making the message byte-identical to what `_retired_writer`
  emits today.

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
    def __init__(self, name: str, *, path: str, forward: str, **kwargs) -> None:
        super().__init__(name, hidden=True, **kwargs)
        self.path = path
        self.forward = forward

    def _message(self) -> str:
        return f"{self.path} is retired. {self.forward}"

    def parse_args(self, ctx, args):
        if ctx.resilient_parsing:
            return super().parse_args(ctx, args)
        if not args or args[0] in ("-h", "--help"):
            raise click.ClickException(self._message())
        return super().parse_args(ctx, args)

    def resolve_command(self, ctx, args):
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            raise click.UsageError(self._message(), ctx) from None
```

**The unknown-child path raises `UsageError`, not `ClickException`** — naming a command
that does not exist *is* a usage error, and `UsageError` exits 2 where `ClickException`
exits 1. This is not a stylistic choice: `test_graph_cli.py:509`,
`test_graph_add_paper_command_is_removed`, asserts `exit_code == 2` for
`graph add paper`. Raising `ClickException` there would silently downgrade the exit code
of every mistyped subcommand. Verified: with `UsageError` the exit code stays 2 and the
message names the retirement.

The group's `path` and `forward` come from `RETIRED_GROUPS` (§3.3), not from anywhere
implicit. An earlier draft left `_retired`'s message with no stated source, which would
have made `graph add` the one retirement not owned by the manifest.

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

So the owner is two plain mappings in the retirement module, keyed by invocation path:

```python
RETIREMENTS: dict[str, str] = {          # 22 leaf commands
    "inquiry add-node": INQUIRY_MUTATION_FORWARD,
    ...
    "graph add concept": "Run `science entity create concept <title>` "
                         "(or edit entities/concepts/<slug>.md), "
                         "then run `science graph build`.",
}

RETIRED_GROUPS: dict[str, str] = {       # groups that are retired in their own right
    "graph add": "Author the entity instead — `science entity create <kind> <title>`, "
                 "or a typed wrapper such as `science hypotheses create <title>`; "
                 "author edges in `relations.yaml` or `relations:` frontmatter. "
                 "Then run `science graph build`.",
}
```

`RETIRED_GROUPS` exists because §3.2 gives `graph add` three behaviours of its own, and
those need a stated source like everything else. Without it, the group would be the one
retirement the manifest did not own.

**The group's forward text must be executable, not a category.** §2's whole complaint
is that an agent gets told what it may not do without being told what to do; "use the
source-authoring commands" reproduces that failure at the group level. Because the
group is now hidden, this message is the *only* thing an agent working from an old
transcript will see for a name that no longer resolves — so it names the actual
commands and the actual file.

Consumers derive from them:

- **The CLI** registers each `RETIREMENTS` entry as a `RetiredCommand` on the group its
  key names, and each `RETIRED_GROUPS` entry as a `RetiredGroup`.
- **`budget/registry.py`** computes its exemptions instead of listing them:

  ```python
  EXEMPTIONS = {
      ...,
      **{path: "fixed retired-command error" for path in RETIREMENTS},
  }
  ```

**The registry derives from `RETIREMENTS` only — deliberately, not by oversight.**
`test_budget_boundary.py:52` asserts `classified - live` is empty, where `live` comes
from `_leaf_commands`, which recurses *through* groups and yields only non-groups.
`graph add` is therefore never "live", and an `EXEMPTIONS` entry for it would fail that
assertion as a table naming a command absent from the CLI tree. Keeping the derivation
to the 22 leaves also preserves the `exempt: 67` cardinality that
`test_classification_partition_has_the_audited_cardinality` pins.

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

`science/tests/test_cli_retirement.py`. It walks `main`'s command tree twice —
collecting leaf `RetiredCommand` instances, and separately `RetiredGroup` instances —
then asserts:

1. **The live leaf set matches `RETIREMENTS`, and the live group set matches
   `RETIRED_GROUPS`, both in both directions.** Since `budget/registry.py` now
   *computes* its entries (§3.3), the registry can no longer disagree and needs no
   assertion. What remains guardable is registration: a retired command or group
   reachable in the CLI but absent from its manifest, or a manifest entry never
   registered.
2. **No retired command declares parameters.** Belt for §3.1.
3. **No retired command or group appears in its parent's `--help`.**
4. **Every one of the 22 leaves errors on a *bare* invocation *and* on `--help`,** in
   both cases naming its own forward path. Parametrized over `RETIREMENTS`, so a
   twenty-third retirement is covered the moment it is declared.
5. **All six shapes of §3.2's table**, so the group-owned and leaf-owned cases stay
   distinguished: `graph add`, `graph add --help`, and `graph add bogus` answer with
   the group's forward path, while `graph add concept`, `graph add concept --help`, and
   `graph add concept x --path /tmp` answer with `concept`'s. `graph add bogus`
   additionally asserts `exit_code == 2`, pinning §3.2's `UsageError` choice.
6. **A completion context over the retired surfaces returns instead of raising** —
   the `resilient_parsing` contract from §3.1, which is invisible to every other
   assertion here because completion never goes through normal invocation.

Assertion 4 carries two loads. Its bare-invocation half is the regression test for the
original defect — every existing test invokes these with full valid arguments, which is
precisely why nobody noticed that a correct call was a precondition for learning the
call was impossible. Its `--help` half replaces the coverage lost when §7 deletes the
old vocabulary test: `--help` on a retired command is a behaviour this design
deliberately changes, and a deliberate change with no test is just an undocumented one.

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
| `RETIREMENTS` + `RETIRED_GROUPS` manifests; `RetiredCommand` / `RetiredGroup` | Any command not already retired |
| The 22 leaf declarations and 1 group declaration; deleting their parameters | Whether the 39 groups carve the space well (S7b) |
| Deriving `budget/registry.py`'s exemptions from `RETIREMENTS` | The `graph add` family's Tier 2/3 deletion (kernel-closure) |
| `test_cli_retirement.py` | Generalizing the ratchet across fact classes (S0) |
| Deleting one method from `TestInquiryAddEdge` and renaming the class (§7) | Migrating "relation claim" in the causal exporters (§7) |
| One line in `cli-and-workflows.md` | |

## 7. Compatibility, and the two behaviours deliberately changed

Every invocation that *executes work* today continues to. Two observable behaviours
change, both deliberately, and each costs a test.

### 7.1 An unknown `graph add` subcommand now names the retirement

Today `science graph add paper` answers `No such command 'paper'` and exits 2.
Under §3.2 it answers with the group's retirement and forward path, still exiting 2 —
`UsageError` is chosen precisely to hold that exit code.

`test_graph_cli.py:509`, `test_graph_add_paper_command_is_removed`, asserts both the
exit code and the old message. **Its exit-code assertion survives; its message
assertion must be rewritten** to expect the retirement text. The test's intent — that
`paper` is not a command anyone can call — is still served, and served better: the new
message tells the caller where to go instead of only that they were wrong.

An earlier draft of §8 claimed `test_graph_cli.py` passes wholly unchanged. That was
false, and it was false because I checked the retired-command tests and did not check
the tests about commands that were *removed rather than retired*.

### 7.2 `--help` on a retired command now errors

Today `science inquiry add-edge --help` and `science graph add edge --help`
both exit 0 and print a usage block. Under §3.1 they error. That is the accepted
consequence stated in §3.1, and it is a real break, not a no-op — an earlier draft of
this section claimed nothing working stopped working, which was false.

**It has a test.** `test_inquiry_cli.py:242`,
`TestInquiryAddEdge.test_edge_claim_help_uses_proposition_language`, asserts
`exit_code == 0` for both of those `--help` invocations *and* that the output contains
`"Supporting proposition reference"` — the help string on the `--claim` option.

That **test method** must be deleted, not rewritten, because its subject ceases to
exist. `"Supporting proposition reference"` appears in exactly two places in the
source — `inquiry_cli.py:229` and `graph/cli.py:1084` — both on retired commands, and
§3.1 deletes their parameters. There is no live surface to re-point it at.

**Only the method goes, not the class.** `TestInquiryAddEdge` also contains
`test_compiled_edge_with_relation_claim_attaches_claim_to_edge`, which builds an
inquiry graph and asserts that a flow edge's `claim_refs` materialize as
`sci:backedByClaim` and *not* `sci:validatedBy`. That is live inquiry-compilation
behaviour with nothing to do with retired CLI help, and it must be retained — under a
class renamed to describe what survives, since "AddEdge" will no longer name anything
the class tests.

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
- `test_retired_graph_writer_commands_report_forward_path` passes **unchanged** — it
  asserts `"<command> is retired"`, the forward key, and `"science graph build"`. All
  three hold once §3.3 keeps each `forward` complete and §3.1 builds the message from
  the manifest key without backticks. Verified to *fail* under the earlier backticked
  draft, so it is a checked claim.
- `test_graph_add_paper_command_is_removed` passes with its **message assertion
  rewritten** per §7.1; its `exit_code == 2` assertion is unchanged.
- **Shell completion does not raise.** A test constructing a completion context for
  `graph add` and `graph add concept` — the two shapes measured to raise without the
  `resilient_parsing` guard — and asserting it returns rather than throwing.
- `test_inquiry_cli.py` passes with **one method** removed per §7 and its class
  renamed; `test_compiled_edge_with_relation_claim_attaches_claim_to_edge` and
  `TestInquiryMutatorsRetired` pass unchanged.
- `test_budget_boundary.py` and `test_budget_registry.py` pass unchanged — §3.3 keeps
  the derivation to the 22 leaves, preserving both the `classified - live` emptiness
  and the pinned `exempt: 67` cardinality.
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
