# `prereg.vehicle-prose-nondurable` — the prose half of the vehicle doctrine

Branch `prereg-prose-durability`, cut from `f2f5c5e3`.

## The fact

**A pre-registration's substrate is whatever the frozen document says it is,
not whatever the frontmatter happens to list.**

`prereg.vehicle-gitignored` is an ERROR gated from the `report` tier. It asks a
single question of every declared vehicle: will git preserve this file? A path
that fails is not frozen, and the build stops.

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

**`prereg.vehicle-prose-nondurable`**, WARN, in
`validate/checks/prereg_vehicles.py` beside the rules it completes.

> A frozen pre-registration names a repo-relative path in prose that resolves
> to a real file or directory which git will not preserve.

### Predicate

For each pre-registration whose `frozen_because(...)` is not `None`:

1. **Data-gated exemption first.** If the body contains
   `## Vehicle-Admissibility Gate`, emit nothing. A data-gated document commits
   its decision rule before any vehicle is admissible, so discussing candidate
   paths is exactly what it is supposed to do. This is the same exemption
   `vehicle-undeclared` already honours, applied for the same reason.
2. **Body only.** `ctx.body(path)`; frontmatter is excluded, so a declared
   vehicle is never reported twice under two different rules.
3. **Strip fenced code blocks** (``` and `~~~`). A transcript or command
   example that happens to contain an ignored path is illustration, not
   commitment.
4. **Extract inline code spans.** A span is eligible only when its **entire
   content, after trimming surrounding whitespace, is one path** — a span
   containing a command, flag, argument list, internal whitespace, or prose is
   discarded whole. Path-shaped arguments are not mined out of
   `` `python x.py --in data/raw/foo` ``.
5. **Require a lexically repo-relative path.** Reject absolute paths, reject
   any path with a `..` segment, and normalize a leading `./` away. Normalize
   before both deduplication and comparison against `vehicles[].path`, so
   `./data/x`, `data/x`, and `data/x/` are one path.
6. **Require existence.** Drop every token that does not resolve under the
   project root. This is the step that converts a heuristic extraction into a
   mechanical finding.
7. **Drop declared vehicles.** Drop any path equal to a declared
   `vehicles[].path` after normalization, or a parent directory of one. A
   declared path is the declared rules' business, and reporting it here would
   mean two rules naming one file. The parent-directory clause is belt and
   braces rather than load-bearing: a directory holding a tracked declared
   vehicle already has a tracked descendant and is durable by step 8. It
   matters only when the declared vehicle is itself defective, where
   `vehicle-gitignored` or `vehicle-untracked` owns the finding.
8. **Ask git.** Ignored → finding. Otherwise not tracked → finding. Otherwise
   durable, no finding.

One finding per `(document, path)`. A path named in five places is one finding.

### Directory semantics, stated deliberately

Git tracks files, not directories. A directory is therefore treated as
**durable when it contains at least one tracked descendant** (`git ls-files --
<dir>` is non-empty), and reported otherwise.

This is a deliberate narrowing, not an accident of the pathspec query. It is
the weaker of the two available readings — a directory with one tracked README
and ten thousand ignored data files counts as durable and is not reported. The
alternative, reporting a directory unless every descendant is tracked, would
fire on `workflows/formulation-breadth` and most other ordinary source
directories, which are named constantly and correctly. Under-reporting here is
the right error: the rule's value is that a finding is always real.

### Behaviour outside a git repository

**Emit nothing.** Reporting a path as non-durable when git has not been
consulted would assert something unverified — precisely the failure mode this
rule exists to prevent, committed by the rule itself.

The residual coverage gap is stated rather than closed: a frozen
pre-registration in a non-repository gets `prereg.vehicle-unverifiable` when it
declares vehicles and `prereg.vehicle-undeclared` when it declares none, so the
document is never silently certified. What it does not get is any signal about
its prose paths. Extending `vehicle-unverifiable` to cover that is a separate
change with its own corpus story and is out of scope here.

## Why this is a validate check and not a prose lint

`validate/checks/boundary.py` states the doctrine:

> no heuristic classifier participates in enforcement, so a finding is always a
> genuine self-contradiction in the repository's own configuration.

Extraction (steps 3–5) is heuristic. Every heuristic step is a **filter that
only narrows**, and steps 6–8 are mechanical. A surviving finding names a file
that exists and that git demonstrably will not preserve, inside a document that
claims to be frozen. The contradiction is the document's, not the checker's.

The trigger completes that argument. Confining the rule to `frozen_because` is
what makes a finding a contradiction rather than unfinished work:

- A `vehicles:` entry is an **explicit schema declaration**. It is invalid if
  non-durable even in a draft, which is why the declared-vehicle rules run
  regardless of status.
- A prose path is an **inferred commitment**. Before freezing, naming an
  ignored working path is normal. The self-contradiction exists only once the
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

Every finding was read in context. They are substrate declarations, not
incidental mentions:

| project | document | path | state | context |
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
`results/heldout-taxa-benchmark` entries name where results are written rather
than what was consumed. These are still reported: *"this frozen document
commits to a location git will not preserve"* is true of an output path, and
distinguishing input from output would require exactly the semantic judgment
this rule refuses to make.

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

Twenty-three findings across four projects means gating this would fail four
real builds for a contract none of them could have met — the same reason
`vehicle-undeclared` is ungated, recorded in the same place. `gates.py` gains a
comment beside that one noting the absence and its reason; the rule name is
**not** added to any tier set.

The ratchet is deferred until the corpus is migrated, and migration is real
work: several of these paths are large derived data that cannot simply be
committed. The available remedies, in the order the message should offer them:

1. Commit the substrate, if it is small enough to belong in git.
2. Commit its **descriptor** and register that — a `datapackage.json` is
   kilobytes, and a `class: manifest` boundary root with
   `tracked: [datapackage.json]` is exactly the shape that keeps it in git.
   This is the remedy that would have prevented the `0014` loss.
3. Declare it as a content-addressed dataset entity, as
   `vehicle-gitignored` already advises.
4. Accept the finding with a recorded reason, where the substrate is genuinely
   gone or genuinely unfreezable.

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
| frozen doc, span containing a command with a path argument | silent |
| frozen doc, absolute path / path containing `..` | silent |
| frozen doc, path equal to a declared `vehicles[].path` | silent, and not double-reported |
| frozen doc, `./data/x` where `data/x` is declared | silent — normalization before comparison |
| frozen doc, same path named five times | exactly one finding — dedup contract |
| frozen doc, directory with one tracked descendant | silent |
| frozen doc, directory with no tracked descendant | one finding |
| frozen doc with `## Vehicle-Admissibility Gate` | silent |
| non-frozen doc, gitignored prose path | silent |
| non-repository project | silent |

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
