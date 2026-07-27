# `prereg.prose-path-nondurable` — the prose half of the vehicle doctrine

Branch `prereg-prose-durability`, cut from `f2f5c5e3`.

## The fact

**A pre-registration's substrate is whatever the frozen document says it is,
not whatever the frontmatter happens to list.**

`prereg.vehicle-gitignored` is an ERROR introduced at the **`hygiene`** tier.
It asks a single question of every declared vehicle: will git preserve this
file? A path that fails is not frozen, and once a project's `code_gate:`
reaches `hygiene` the build stops. (The `report` tier is empty; `validate` is
report-only by default and a project advances the ladder explicitly.)

That question is never asked of a path named in prose. The vehicle rules read
`vehicles:` and nothing else, so the same path — the same file, the same
ignore rule, the same regeneration hazard — is an ERROR in frontmatter and
invisible in a bullet list four lines below it.

## Grounding: the check family cannot see its own founding incident

`fb-2026-07-11-024` created the vehicle rules. Its narrative is in the module
docstring of `validate/checks/prereg_vehicles.py`:

> `pre-registration:0026` locked its vehicle as
> `pipeline/graph-analysis/data/graph-export.json, exported 2026-04-30, 244
> models`. That path was in `.gitignore`, so the "frozen" vehicle was an
> untracked build product […] Nine rounds of adversarial review did not catch
> it, because nobody asked whether the named file was durable.

Both `pre-registration:0001` and `pre-registration:0026` still name that path
in prose today. `0001` names it as a declaration, not a reminiscence:

    - **Source:** `pipeline/graph-analysis/data/graph-export.json` field `.limitRelations`

`science validate` reports nothing about either. The instrument built to
prevent that loss does not fire on the path that was lost, in the document that
lost it, because the path is in a bullet rather than a mapping.

### The second incident, on a different substrate

natural-systems `task:t896` (2026-07-27) traced `pre-registration:0014`'s lost
arXiv corpus. The frozen document's **Primary Beta Operationalization** section
— the section enumerating the locked settings — reads:

    The beta value facing hypothesis:0007 […] is the primary output of
    `workflows/formulation-breadth` under these locked settings:

    - local arXiv corpus with the corpus hash recorded in
      `data/processed/arxiv/datapackage.json`;
    - entity labels and synonyms from `scripts/formulation_breadth/entity_config.yaml`;

`data/processed/` is gitignored in that project. `task:t629` regenerated the
corpus on 2026-05-30, the registered hash stopped matching, and nothing in the
repository changed — the descriptor recording the hash was itself untracked.
The hand-run guard `scripts/t392/validate_freeze.py` went red and was not run
again for eight weeks. The corpus is unrecoverable.

Had that bullet been a `vehicles:` entry, `prereg.vehicle-gitignored` would
have failed the build in May, before the loss.

### The evasion, demonstrated live

`0014` declared no vehicles, so `prereg.vehicle-undeclared` fired once
`frozen_because` began reading `amendments:` (`fb-2026-07-26-019`). The remedy
applied in `task:t896` was to declare the two substrates that had survived —
the β snapshot and the frozen matrix.

**That silenced the warning without touching the path that caused the loss.**
`data/processed/arxiv/datapackage.json` remains named in the same frozen
document, still gitignored, still unchecked.

This is the completeness gap in its purest form: `vehicle-undeclared` is
satisfied by the existence of one entry, so its remedy can always be discharged
against the most convenient artifact rather than the load-bearing one. There is
no bad faith required — declaring the recoverable substrates was the correct
thing to do, and it still left the document mis-certified.

## The rule

**`prereg.prose-path-nondurable`**, WARN, in
`validate/checks/prereg_vehicles.py` beside the rules it completes.

> A frozen pre-registration names a slash-containing repo-relative path in
> prose that resolves to a real file or directory which git will not preserve.

**Not `prereg.vehicle-*`.** The rule name is a public contract — it appears in
JSON output, in suppression and acceptance entries, and in downstream
documentation — and `vehicle-` would assert in the identifier the very
inference the rule is forbidden from making. It lives in
`prereg_vehicles.py` because that is where the durability doctrine is
readable, not because a finding is about a vehicle.

**Root-level paths are out of scope.** The grammar requires a `/`, so a path
naming a file at the repository root — `input.parquet` — is never a candidate.
This is a deliberate limit, not an oversight: the anchored grammar is what
keeps ordinary backticked prose (`beta_1`, `README.md`, a bare filename) from
becoming a candidate, and admitting bare filenames would make existence
checking, not the grammar, the primary filter. Widening it would require
re-running and re-certifying the corpus count below, so it is left for a
separate change if the gap is ever observed to matter.

### Predicate

For each pre-registration whose `frozen_because(...)` is not `None`:

1. **Data-gated exemption first.** If the body contains
   `## Vehicle-Admissibility Gate`, emit nothing. A data-gated document commits
   its decision rule before any vehicle is admissible, so discussing candidate
   paths is exactly what it is supposed to do. This is the same exemption
   `vehicle-undeclared` already honours, applied for the same reason.
2. **Body only.** `ctx.body(path)`; frontmatter is excluded, so a declared
   vehicle is never reported twice under two different rules.
3. **Strip fenced code blocks** (``` and `~~~`) **and HTML comments**
   (`<!-- … -->`). A transcript or command example that happens to contain an
   ignored path is illustration, not commitment; a commented-out path is body
   text but is not something the rendered document says at all.
4. **Extract inline code spans** with ``` `([^`\n]+)` ```, then accept a span
   only when its content, after stripping surrounding whitespace, matches the
   path grammar **in full**:

       ^[A-Za-z0-9_.][A-Za-z0-9_./+-]*/[A-Za-z0-9_./+-]*$

   This is the exact grammar behind the 23-finding survey below, stated so the
   count is reproducible. Anchoring at both ends is what does the work: a span
   containing a command, flag, argument list, internal whitespace, or prose
   fails as a whole, so path-shaped arguments are never mined out of
   `` `python x.py --in data/raw/foo` ``. The closed character class also
   excludes URLs, since `:` is not in it.

   The considered alternative — accept any non-empty whitespace-free span and
   let existence decide — was rejected as under-specified rather than wrong.
   Existence filtering would in fact reject most of the extra candidates, but
   the survey count would then depend on what happens to be on disk, and the
   rule's grammar would be defined by its own false-positive filter.
5. **Require a lexically repo-relative path.** Reject absolute paths, reject
   any path with a `..` segment, and normalize a leading `./` away. Normalize
   before both deduplication and comparison against `vehicles[].path`, so
   `./data/x`, `data/x`, and `data/x/` are one path.

   The `..` rejection is load-bearing, not belt and braces: `.` is in the
   grammar's leading character class, so `../secrets/x` matches step 4 and is
   stopped only here. The absolute-path rejection *is* belt and braces — a
   leading `/` already fails step 4 — and is kept because the guarantee should
   not depend on one regex's first character class.
6. **Require existence.** Drop every token that does not resolve under the
   project root. This is the step that turns a heuristic extraction into a
   statement about a real file, so that whatever is reported afterwards is
   decided by git rather than by the grammar.
7. **Drop declared vehicles.** Drop any path equal to a declared
   `vehicles[].path` after normalization. A declared path is the declared
   rules' business, and reporting it here would mean two rules naming one file.

   Exact match only — **no parent-directory clause.** An earlier draft dropped
   directories containing a declared vehicle too, on the theory that they were
   already durable. Under the ordering fixed below that clause is inert in the
   normal case (a directory holding a tracked vehicle is durable anyway) and
   actively wrong in the defective case: if the declared vehicle is itself
   gitignored, a finding on the containing directory is correct information,
   not a duplicate of `vehicle-gitignored`'s finding on the file.
8. **Ask git, tri-state.** Two queries, in this order, each of which can answer
   *yes*, *no*, or *not determined*:

   | query | exit 0 | exit 1 | any other exit |
   |---|---|---|---|
   | `git check-ignore -q -- P` | ignored → **finding** | continue | **unverifiable → no finding** |
   | `git ls-files --error-unmatch -- P` | matched → durable, no finding | fall through → **finding (untracked)** | **unverifiable → no finding** |

   A non-zero exit that is not the expected "no" is a git failure — an
   out-of-worktree path exits 128 on both queries — and must never be read as
   evidence of non-durability. The existing `_git_ok` collapses every non-zero
   exit into `False`, which would silently convert a git error into an
   untracked finding; this rule needs its own tri-state helper rather than
   reusing it.

One finding per `(document, path)`. A path named in five places is one finding.

### Directory semantics, stated as a decision

Git tracks files, not directories, and the two queries above already resolve
directories correctly — but for a reason subtle enough that leaving it implicit
would be a defect. Both facts below were verified against natural-systems:

**`git check-ignore` suppresses paths git considers tracked.** For
`data/processed/arxiv`, whose contents are covered by `.gitignore` but which
holds force-added files, the default query exits **1 (not ignored)** while
`--no-index` exits **0 (ignored)**. So an ignored directory with a force-tracked
descendant falls through to the second query, `ls-files --error-unmatch` matches
those descendants, and the directory is called durable.

That composition is **adopted deliberately**, on two grounds. It agrees with
`_is_ignored` in the declared-vehicle rules, so the two rules can never disagree
about the same path — a rule pair that contradicts each other is worse than
either being slightly wrong. And it is the weaker of the two readings: a
directory with one tracked README and ten thousand ignored data files counts as
durable and is not reported. Under-reporting is the right error here, because
the rule's value rests on a finding always being real.

Consequently the second query needs no special directory branch. `git ls-files
--error-unmatch -- P` is a pathspec query: for a file it means *is this file
tracked*, and for a directory it means *is at least one descendant tracked*.
One command covers both.

### Behaviour when git cannot answer

**Emit nothing** — outside a git worktree, and on any per-path query failure.
Reporting a path as non-durable when git has not answered would assert
something unverified, which is precisely the failure mode this rule exists to
prevent, committed by the rule itself.

The residual coverage gap is stated rather than closed: a frozen
pre-registration in a non-repository gets `prereg.vehicle-unverifiable` when it
declares vehicles and `prereg.vehicle-undeclared` when it declares none, so the
document is never silently certified. What it does not get is any signal about
its prose paths. Extending `vehicle-unverifiable` to cover that is a separate
change with its own corpus story and is out of scope here.

## What a finding proves, and what it does not

This is the rule's most important boundary, and an earlier draft overstated it.

**What the rule proves, mechanically:** a frozen pre-registration names, in
prose, a slash-containing repo-relative path that resolves to a real file or
directory which git will not preserve. Every term there is decided by the
filesystem and by git, never by the checker's judgment.

**What the rule does not prove:** that the path is a substrate, that its
contents were meant to be frozen, or that the document is self-contradictory.
The corpus contains a clean counter-example — protein-landscape's
`results/heldout-taxa-benchmark` names a **future output directory**. Declaring
where results will be written, at a location git ignores, is a perfectly
coherent thing for a frozen pre-registration to do. Nothing about it is a
contradiction.

So the rule is **advisory**: it establishes the durability fact and hands the
load-bearing question to the author, who is the only party that can answer it.

This is why it does not claim `boundary.py`'s standard —

> no heuristic classifier participates in enforcement, so a finding is always a
> genuine self-contradiction in the repository's own configuration.

— and instead follows the `prereg_schedule` precedent, whose own module says
the quiet part directly:

> It remains a PROSE HEURISTIC, which is why the rule is WARN and ungated.

The same holds here. Extraction narrows rather than invents, so a finding is
never fabricated; but "names a non-durable path" is weaker than "contradicts
itself", and the rule must not be gated on the stronger reading it cannot
support. **The message must therefore not call every hit a substrate or a
vehicle** — it reports a non-durable path and asks whether the document depends
on it.

The trigger still matters. Confining the rule to `frozen_because` is what makes
a finding worth raising at all rather than a note about unfinished work:

- A `vehicles:` entry is an **explicit schema declaration**. It is invalid if
  non-durable even in a draft, which is why the declared-vehicle rules run
  regardless of status.
- A prose path is an **inferred commitment**. Before freezing, naming an
  ignored working path is normal. The question is only worth asking once the
  document claims to be frozen.

Running on drafts would dilute the rule's meaning and train users to ignore it.
If earlier feedback proves valuable, it belongs in a separate opt-in authoring
lint, not in this validation rule.

## Corpus measurement

Survey over every project holding pre-registrations, plus `multiple-myeloma`
as an explicit zero row so the certification scope is auditable.

| project | pre-registrations | documents | findings |
|---|---:|---:|---:|
| natural-systems | 34 | 4 | 6 |
| protein-landscape | 3 | 2 | 9 |
| seq-feats | 5 | 1 | 5 |
| 3d-attention-bias | 4 | 2 | 3 |
| multiple-myeloma | — | — | **0** (no `entities/pre-registrations/`; the check returns before any document is read) |
| **total** | **46** | **9** | **23** |

Every finding was read in context. Most are substrate declarations rather than
incidental mentions; the **role** column records what the document appears to
be doing with each path, and is the author's call to confirm, not the rule's to
assert:

| project | document | path | state | apparent role |
|---|---|---|---|---|
| natural-systems | `0001` | `pipeline/graph-analysis/data/graph-export.json` | ignored | `**Source:** … field .limitRelations` |
| natural-systems | `0014` | `data/processed/arxiv/datapackage.json` | ignored | locked-settings bullet |
| natural-systems | `0026` | `pipeline/graph-analysis/data/graph-export.json` | ignored | the `fb-2026-07-11-024` artifact |
| natural-systems | `0026` | `pipeline/graph-analysis/data` | ignored | the containing root |
| natural-systems | `0026` | `pipeline/h03/results/betti.json` | ignored | *"The 11 comes from …, computed on the 172-model instance cohort"* |
| natural-systems | `0028` | `data/processed/formulation-breadth/source-ids.txt` | ignored | substrate table row |
| protein-landscape | `0002`, `0003` | `data/processed/benchmark-frame.parquet` | untracked | *"… by taking the first three"* |
| protein-landscape | `0002` | `data/processed/foldseek-reps-disorder.parquet` | untracked | substrate |
| protein-landscape | `0002` | `data/raw/foldseek/v3/1-AFDBClusters-…tsv.gz` | untracked | substrate |
| protein-landscape | `0003` | `data/processed/heldout-taxa-benchmark`, `…/splits.parquet` | untracked | substrate |
| protein-landscape | `0003` | `data/raw/go` | untracked | substrate |
| protein-landscape | `0003` | `results/heldout-taxa-benchmark`, `…/q81-evaluation` | ignored | output location |
| 3d-attention-bias | `0002`, `0004` | `data/distance_matrices/rnass` | untracked | substrate |
| 3d-attention-bias | `0002` | `data/distance_matrices_random/rnass` | untracked | substrate |
| seq-feats | `0003` | `data/{phase2/cgi,phase2/tfbs,phase3/domains,pilot/sp,pilot/tmr}` | untracked | five substrate directories |

The softest class is **output locations** — protein-landscape's two
`results/heldout-taxa-benchmark` entries name where results will be written
rather than what was consumed. These are still reported, but they are also the
reason the rule is advisory rather than a contradiction detector: a frozen
document may legitimately name an ignored output directory without claiming its
contents are frozen. The rule reports the durability fact, which is true of an
output path, and leaves the load-bearing question to the author. Distinguishing
input from output mechanically would require exactly the semantic judgment this
rule refuses to make.

### Two extraction decisions settled by measurement, not taste

**Backticked-only costs almost no recall.** Scanning bare prose text in
addition to code spans adds **one finding across all 46 documents** while
opening a large false-positive surface. Path-like tokens in these documents are
essentially always in code spans.

**Fence stripping is currently free.** Counts are identical with and without
it on today's corpus. It is specified anyway: a verbatim command block naming
an ignored path is a false positive by construction, and the corpus containing
none today is a fact about today.

## Enforcement

**WARN, and deliberately absent from every tier in `gates.py`.**

Two independent reasons, either of which alone would be sufficient:

- **The rule is advisory by construction.** It proves a durability fact, not a
  contradiction, so it may not carry an ERROR that asserts the stronger claim.
  This reason does not expire when the corpus is clean.
- **Corpus certification forbids it today anyway.** Twenty-three findings
  across four projects means gating would fail four real builds for a contract
  none of them could have met — the same reason `vehicle-undeclared` is
  ungated, recorded in the same place.

`gates.py` gains a comment beside `vehicle-undeclared`'s noting the absence and
both reasons; the rule name is **not** added to any tier set.

A ratchet is therefore **not** simply deferred pending corpus migration. It
would require first narrowing the rule to a predicate that genuinely implies
contradiction — which the output-path counter-example shows this one does not.

### Message and remedies

The message states the fact and asks the question. It names the path, whether
git reports it ignored or untracked, and that the document is frozen — and it
does **not** assert the path is a substrate or a vehicle. Something in the shape
of: *this frozen pre-registration names `P` in prose; git will not preserve it
(ignored). If the document's claims depend on `P`, it is frozen by path, not by
content.*

Remedies, offered conditionally on that "if", roughly in order of cost:

1. If the document does not depend on the path — an output location, an
   illustration — nothing needs to change; accept the finding with that reason.
2. Commit the file, if it is small enough to belong in git.
3. Commit its **descriptor** and register that — a `datapackage.json` is
   kilobytes, and a `class: manifest` boundary root with
   `tracked: [datapackage.json]` is exactly the shape that keeps it in git.
   This is the remedy that would have prevented the `0014` loss.
4. Declare it as a content-addressed dataset entity and add it to `vehicles:`,
   as `vehicle-gitignored` already advises.

## Scope

**In:** the check, its unit tests, corpus certification, a `gates.py` comment,
the feedback filing and its closure, this design and its results document.

**Out:** any change to declared-vehicle rules; extending
`vehicle-unverifiable`; the boundary-side gap (a payload root carrying a
descriptor that wants to be a manifest root) — filed separately, adjacent to
the open `fb-2026-07-27-001`/`-002` MM30 boundary cluster; any migration of the
23 findings in the downstream projects.

## Verification

**Unit tests** in `science/tests/validate/test_checks_prereg_vehicles.py`:

| arm | expectation |
|---|---|
| frozen doc, gitignored prose path | one finding |
| frozen doc, untracked prose path | one finding |
| frozen doc, tracked prose path | silent |
| frozen doc, path that does not resolve | silent |
| frozen doc, path only inside a fenced block | silent |
| frozen doc, path only inside an HTML comment | silent |
| frozen doc, span containing a command with a path argument | silent |
| frozen doc, span containing a URL | silent — `:` is outside the grammar |
| frozen doc, absolute path / path containing `..` | silent |
| frozen doc, path equal to a declared `vehicles[].path` | silent, and not double-reported |
| frozen doc, `./data/x` where `data/x` is declared | silent — normalization before comparison |
| frozen doc, ignored dir containing a declared *gitignored* vehicle | **one finding** — no parent-directory suppression |
| frozen doc, same path named five times | exactly one finding — dedup contract |
| frozen doc, directory with one tracked descendant | silent |
| frozen doc, directory with no tracked descendant | one finding |
| frozen doc, ignored directory holding a force-tracked descendant | silent — the adopted composition, pinned so it cannot regress silently |
| frozen doc, `check-ignore` exits non-zero and non-1 | silent — unverifiable, not "untracked" |
| frozen doc, `ls-files` exits non-zero and non-1 | silent — unverifiable, not "untracked" |
| frozen doc with `## Vehicle-Admissibility Gate` | silent |
| non-frozen doc, gitignored prose path | silent |
| non-repository project | silent |

The two git-failure arms are the ones most likely to be skipped as awkward to
set up and are the reason the rule needs its own tri-state helper; a fake or
injected runner that returns exit 128 is sufficient to pin them.

**Corpus certification** reproduces the table above using Batch T's exact-rule
JSON method — full report per project retained as JSON, findings selected by
exact `rule` equality, no rendered-output substring counting.

**Snapshots.** `science/tests/validate/fixtures/_combined` feeds
`tests/validate/snapshots/`. That fixture has **no
`entities/pre-registrations/` directory**, so the check returns before reading
any document and the snapshots are expected to be byte-identical. A snapshot
diff is therefore a signal that something unintended changed, not a routine
regeneration — investigate it rather than running
`science/scripts/update-validate-snapshots.py`.

## Filing

File against `check:prereg.vehicle-undeclared`, category `gap`, concern
`tooling`, recording the completeness gap with the `0014` and `0026` evidence.
Close it in the results document once the rule ships, per the batch workflow.
