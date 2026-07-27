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

**Root-level paths are out of scope**, enforced **after normalization** rather
than by the grammar. The grammar requires a `/`, which is necessary but not
sufficient: `./input.parquet`, `input.parquet/` and `././input.parquet` all
contain one when the grammar matches them, and all denote a file at the
repository root once normalized. Step 5 therefore re-checks for a `/` on the
normalized value, and that check — not the grammar — is what defines the scope.

The limit is deliberate. The `/` requirement is what keeps ordinary backticked
prose (`beta_1`, `README.md`, a bare filename) from becoming a candidate at all,
and admitting bare filenames would make existence checking rather than the
grammar the primary filter. Widening it would require re-running and
re-certifying the corpus count below, so it is left for a separate change if the
gap is ever observed to matter.

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

   This is the exact grammar behind the 16-finding survey below, stated so the
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
5. **Normalize lexically, then require a slash-containing repo-relative path.**
   Normalization is a full lexical resolution — `PurePosixPath` — not a leading
   `./` strip and a trailing `/` strip. It runs before both deduplication and
   comparison against `vehicles[].path`, so `./data/x`, `data/x`, and `data/x/`
   are one path.

   Ad-hoc string surgery is wrong here in three ways that each look fine alone:
   stripping one leading `./` leaves `././input.parquet` as `./input.parquet`,
   still root-level; it turns `.//etc/passwd` into the **absolute**
   `/etc/passwd`, violating the step's own contract; and `rstrip('/')` leaves
   `build/./` as `build/.`. Lexical resolution also collapses redundant
   separators, so `.//etc/passwd` correctly becomes relative `etc/passwd`.

   Three rejections then apply to the normalized value, none redundant:

   - **absolute** — covers `/x` and the POSIX `//x` form.
   - **`..` segment** — load-bearing, since `.` is in the grammar's leading
     character class, so `../secrets/x` matches step 4 and is stopped only here.
   - **no `/`** — the root-level scope limit above, which the grammar cannot
     enforce on its own.
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

**Cohort: every Science project on disk that holds pre-registrations, derived by
discovery rather than by a hand-written list.** Enumerating `science.yaml` under
`~/d` (excluding `.worktrees`, `templates`, `tests`) finds **22 canonical
projects**, of which **11** have a non-empty `entities/pre-registrations/`. All
11 are measured.

The enumeration must not follow *nested* symlinks. `~/d/r/cbioportal` and
`~/d/r/mm30` are aliases of `cancer/data-sources/cbioportal` and
`cancer/cancer-types/multiple-myeloma`, and `~/d/cancer/science/meta` is a third
alias, so a link-following walk reports 25 projects and a 13-row cohort for the
same 11 real ones — inflating every total by counting two projects twice.

The derivation matters. An earlier draft of this section hand-listed four
projects and recorded `multiple-myeloma` as a zero row at path
`~/d/multiple-myeloma`. **That path does not exist** — the real project is
`~/d/cancer/cancer-types/multiple-myeloma`, it holds **61** pre-registrations,
and it fires. The glob returned nothing and the absence was silently recorded as
a measurement. Six further projects were missing from the list entirely. A
certification cohort that is typed by hand can be wrong in exactly the way the
rule under test is about: an absence that looks like a result.

| project | pre-registrations | documents | findings |
|---|---:|---:|---:|
| natural-systems | 34 | 4 | 6 |
| cancer/data-sources/cbioportal | 4 | 2 | 4 |
| cancer/mechanisms/evolution | 4 | 1 | 2 |
| protein-landscape | 3 | 1 | 2 |
| cancer/cancer-types/multiple-myeloma | 61 | 1 | 1 |
| cancer/therapeutics | 4 | 1 | 1 |
| health/comparisons/pan-disease | 14 | 0 | 0 |
| health/processes/post-acute-infection | 6 | 0 | 0 |
| health/processes/cycles | 5 | 0 | 0 |
| seq-feats | 5 | 0 | 0 |
| 3d-attention-bias | 4 | 0 | 0 |
| **total (11 projects)** | **144** | **10** | **16** |

Six of eleven projects fire. Every finding is `ignored`; the corpus currently
produces no `untracked` finding at all.

### Why this replaces an earlier 23/9 figure

Both the cohort and the predicate were wrong, and they moved the count in
opposite directions.

**The cohort was too small** — 4 projects, 46 pre-registrations, against the
real 11 and 144.

**The predicate was fail-open**, which *inflated* the count. The earlier probe
read every non-zero `git check-ignore` exit as "not ignored" and every non-zero
`ls-files` exit as "not tracked", concluding *untracked*. Measured against the
real corpus, that is not a theoretical concern:

    $ git check-ignore -q -- data/phase2/cgi
    fatal: pathspec 'data/phase2/cgi' is beyond a symbolic link
    exit 128

**Every one of seq-feats' 5, 3d-attention-bias' 3, and 7 of protein-landscape's
9 earlier findings was a git error misread as non-durability** — all of them
paths behind a symlink. The tri-state helper removes 15 false findings, and the
three projects that contributed them now report zero.

That is the strongest available argument for the tri-state contract: it is not
hardening against a hypothetical, it is the difference between a 23-finding
instrument that is mostly wrong and a 16-finding one that is not.

### The findings

Every finding was read in context. Most are substrate declarations rather than
incidental mentions; the **apparent role** column records what the document
seems to be doing with each path, and is the author's call to confirm, not the
rule's to assert:

| project | document | path | apparent role |
|---|---|---|---|
| natural-systems | `0001` | `pipeline/graph-analysis/data/graph-export.json` | `**Source:** … field .limitRelations` |
| natural-systems | `0014` | `data/processed/arxiv/datapackage.json` | locked-settings bullet |
| natural-systems | `0026` | `pipeline/graph-analysis/data/graph-export.json` | the `fb-2026-07-11-024` artifact |
| natural-systems | `0026` | `pipeline/graph-analysis/data` | the containing root |
| natural-systems | `0026` | `pipeline/h03/results/betti.json` | *"The 11 comes from …, computed on the 172-model instance cohort"* |
| natural-systems | `0028` | `data/processed/formulation-breadth/source-ids.txt` | substrate table row |
| cbioportal | `0002` | `results/signature-brca-2026-04-22` | output location |
| cbioportal | `0002` | `data/gene_replication_timing.feather` | substrate |
| cbioportal | `0003` | `results/poc-2026-04-17/metadata/samples_annotated.feather` | output location |
| cbioportal | `0003` | `data/mc3.v0.2.8.PUBLIC.maf.gz` | substrate |
| evolution | `0003` | `data/raw/t063-q095-tcga-public-payload/pancan_rnaseq_freeze.tsv.gz` | substrate |
| evolution | `0003` | `data/raw/t063-q095-tcga-public-payload/pancan_mutation_freeze.tsv.gz` | substrate |
| protein-landscape | `0003` | `results/heldout-taxa-benchmark` | output location |
| protein-landscape | `0003` | `results/heldout-taxa-benchmark/q81-evaluation` | output location |
| multiple-myeloma | `0058` | `data/external/ctrp_v2/2015/ctrpv2-sensitivity-long.parquet` | substrate |
| therapeutics | `0001` | `data/raw/nci-almanac/ComboDrugGrowth_Nov2017.zip` | substrate |

**Output locations are 5 of 16**, up from 2 of 23 in the earlier figure — a
larger share of the instrument's output than the first survey suggested. This
strengthens rather than weakens the advisory framing: a rule where nearly a
third of findings name a path whose contents were never claimed to be frozen
must not carry an ERROR asserting a contradiction. It is the reason the rule
reports the durability fact and leaves the load-bearing question to the author.
Distinguishing input from output mechanically would require exactly the semantic
judgment this rule refuses to make.

### Two extraction decisions settled by measurement, not taste

**Backticked-only costs no recall at all.** Scanning bare prose text in addition
to code spans adds **zero findings across all 144 pre-registrations**, while
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
- **Corpus certification forbids it today anyway.** Sixteen findings across
  six of the eleven projects holding pre-registrations means gating would fail
  six real builds for a contract none of them could have met — the same reason
  `vehicle-undeclared` is ungated, recorded in the same place.

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
16 findings in the downstream projects.

## Verification

**Unit tests** in `science/tests/validate/test_checks_prereg_vehicles.py`:

| arm | expectation |
|---|---|
| frozen doc, gitignored prose path | one finding |
| frozen doc, untracked prose path | one finding |
| frozen doc, tracked prose path | silent |
| frozen doc, path that does not resolve | silent |
| frozen doc, path only inside a fenced block | silent |
| frozen doc, fence closed by a different delimiter (`~~~` inside ```` ``` ````) | silent — the block has not ended |
| frozen doc, fence marker with trailing text (```` ```not-a-close ````) | silent — a closer may carry only whitespace |
| frozen doc, fence marker indented 4+ spaces inside an open block | silent — at four spaces it is an indented code block, not a delimiter |
| frozen doc, fence indented 0–3 spaces | works normally as a delimiter |
| frozen doc, opening fence with an info string (```` ```python ````) | silent — the block still opens |
| frozen doc, path only inside an HTML comment | silent |
| frozen doc, span containing a command with a path argument | silent |
| frozen doc, span containing a URL | silent — `:` is outside the grammar |
| frozen doc, path containing `..` | silent |
| frozen doc, absolute path as `/x` or `//x` | silent — both are POSIX-absolute |
| frozen doc, root-level path as `x`, `./x`, `x/`, `././x`, `d/./` | silent — the post-normalization `/` check |
| frozen doc, `.//a/b` | reported as `a/b` — redundant separators collapse |
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
