# Annotation Base-Shape Remediation Design

**Status:** approved for implementation

## 1. What this is

This is piece 3 of the schema-first closure program
(`meta/doc/plans/2026-07-26-schema-first-closure-design.md`): the corpus repair that piece 1
deliberately did not do. Writer containment stopped the debt growing; it backfilled nothing.

**792 proposition and evidence-line records are refused by `validate_persisted_base_shape`, so the
typed contained update paths — workbench compile/apply and annotation synthesis — refuse to update
them.** 769 carry `title: ''`; 23 carry unquoted YAML dates. The two sets are disjoint.

The refusal is not universal, and the design must not claim it is. Promotion accrual reaches
`append_entity_source_ref`, which renders through `render_entity_source_refs` and
`_atomic_replace_text` without `certify_persisted`, so it can still rewrite an invalid record — and
advances `updated` when it does. Only the paths that certify a typed entity are blocked.

The umbrella design named this cost when it made the rule (§5.4, "Accepted cost, stated plainly")
and argued for "sequencing piece 3 promptly rather than for weakening the rule." That cost is now
being paid, and 681 of the 792 blocked records — 86% — are in a single project, mm30.

This slice repairs the records. It does not arm the `proposition` or `evidence-line` mixins; the
umbrella sequences those as separate closure slices after remediation.

## 2. Reproduction and measurement

### 2.1 The blockage is real and controlled in both directions

A real legacy record from `~/d/cancer/cancer-types/multiple-myeloma`, run through
`update_entity_file` with `WORKBENCH_PROPOSITION`:

```
legacy record as-is:      PersistedShapeError … was NOT written
title repaired on disk:   UPDATE SUCCEEDED
```

The control matters: it establishes that the empty title is the *whole* reason the record is
unwritable on that path, not merely one of several.

### 2.2 The population is frozen

| | at piece 1 | now |
|---|---|---|
| proposition / evidence-line records | 864 | 1087 |
| refused by base shape | 771 | 792 |
| …for empty `title` | **769** | **769** |

The corpus grew by 223 records while the empty-title population did not move. Containment works,
and this is remediation of a closed population rather than a moving target.

### 2.3 Distribution

Empty title, by kind: 337 propositions, 432 evidence lines — matching the umbrella's own figures
exactly. Unquoted dates: 21 evidence lines in `~/d/cancer/mechanisms/evolution`, 2 propositions in
`meta`, zero overlap with the 769.

By project: mm30 681, cbioportal 72, evolution 21, protein-landscape 16, meta 2.

Scans enumerate projects by discovery (`rglob("science.yaml")`) and exclude `.venv`,
`site-packages`, and `.worktrees` — a packaged template carries `kind:` frontmatter and otherwise
reads as a record.

### 2.4 Every record is mechanically repairable

The create path derives titles from fields these records already carry. Running those derivations
over the whole population yields complete inputs for **337 of 337** propositions and **432 of 432**
evidence lines, with zero missing fields.

## 3. Rulings

### 3.1 Scope is a predicate over two kinds, not a defect roster

**A proposition or evidence-line record is in scope iff `validate_persisted_base_shape` refuses
it.**

Defining scope by the check rather than by a list of known defects means a defect class nobody
enumerated cannot be silently missed. The kind boundary is explicit because §7 excludes other
kinds carrying the same date defect.

Measured residue after repair: zero. No record in scope lacks a repair.

### 3.2 Titles are reconstructed by the writer's own derivation

The repair calls the same derivation the create path calls, on values the record already carries.
**The repaired title matches what the create path would have minted, exactly.** The record as a
whole does not: it retains its dumped defaults and, until the next write, differs in date quoting
(§3.4). Only the title is claimed.

The derivations are refactored to accept only their real inputs, and are shared by both callers:

```python
derive_proposition_title(*, subject: str, predicate: str, object: str) -> str
derive_evidence_line_title(*, stance: str | None, target_id: str,
                           source: str | None, evidence_type: EvidenceType | str | None) -> str
```

`_proposition_title(row)` and `_evidence_line_title(stub, target_id=…)` are **replaced, not
wrapped**. Each has exactly one call site — inside `_proposition_for_row` and
`_evidence_line_for_stub` — which pass scalars. `WorkbenchRow.patch` is a required field under
`extra="forbid"`, so a row-taking signature would force the migration to fabricate patch
membership it has no business inventing. Neither a fabricated `WorkbenchRow` nor a second copy of
the formula appears anywhere.

They live in `dag/entity_frontmatter.py`, the module both writers already share, on the precedent
that put `PROPOSITION_REASONING_FIELDS` there for the same reason.

**When `evidence_type` supplies the title tail, it is resolved as
`EvidenceType(canonical_evidence_type_token(raw))` — canonicalization *and* membership coercion.**
The create path never sees a raw token: `EvidenceStub` canonicalizes in a `mode="before"` validator
and then coerces to `EvidenceType`, so the suffix is stripped and membership enforced before the
title is derived. A migration reading persisted frontmatter *does* see raw tokens, and would
otherwise derive `… — empirical_data_evidence` where the create path derived `… — empirical_data`.

Canonicalization alone is not enough. `canonical_evidence_type_token` is documented as "pure
string→string (does NOT validate membership)" — `garbage_evidence` becomes `garbage`, which is not
an `EvidenceType` member. Without the coercion the migration would mint a title from a token the
create path would have rejected. The coercion raising routes the record into the §4.1 unsupported
path, which is the correct outcome: a record whose evidence type is unknown is not one this command
can repair.

Its currently-reachable population is zero, and the design says so rather than implying a repair it
does not perform: 368 of the 432 in-scope evidence lines do carry suffixed tokens (250
`empirical_data_evidence`, 118 `literature_evidence`), but **all 432 carry a `source`**, and the
tail prefers `source`, so no title in this corpus differs either way. The requirement is on the
derivation's correctness, not on this corpus.

### 3.3 `updated` is not stamped

`updated` claims when the record's content last changed. A title that was always implied by the
record's own `subject`/`predicate`/`object`, and a quoting fix, change nothing the record asserts —
the writer simply failed to persist them. Stamping would put a false content-change date on 769
records at once, and the next real workbench update stamps it correctly anyway.

No provenance key is added either: it would be a key on 792 records that no reader consumes, and
the base-shape contract would then have to admit it.

### 3.4 One serializer, and it is the canonical one

The repair renders through `science_model.frontmatter.render_frontmatter`, whose docstring names
"new or explicitly-migrated writers" as its audience. It coerces `created`/`updated` to ISO strings
itself, so this design carries **no hand-rolled date normalization**.

`dag/entity_frontmatter.render_from_frontmatter` is deliberately not used.
`tests/test_frontmatter_boundary.py` lists it in `_ALLOWED_EMITTERS` as
`"pending-normalization: no created/updated force-quoting on RMW path"` — a divergent legacy
emitter on the format-normalization worklist. A migration must not emit the format the boundary
test is tracking as wrong.

**Accepted consequence.** The 792 records currently carry single-quoted (769) or bare (23)
`created`; the canonical block force-*double*-quotes `created`/`updated`. The repair therefore also
performs that normalization, and the workbench emitter reverts it on the next update of that
record:

```
after canonical repair:      created: "2026-06-14"   updated: "2026-06-14"
after one workbench update:  created: '2026-06-14'   updated: '2026-08-02'
```

Neither form is refused by base shape, so no guarantee is affected — this is churn, not
correctness. It stops when the deferred format-normalization phase retrofits the emitter (§7).

### 3.5 Rejected approaches

- **Prettified titles** (de-slugged prose) read better beside the 255 authored ones, but they are
  not what the create path mints, so repaired and newly-minted records would diverge — and every
  future mint stays mechanical, so it moves the seam rather than removing it.
- **Authored prose per record** is 769 judgment calls with no mechanical certification, and many of
  these records have an empty `## Summary`, so there is often nothing to derive prose from.
- **Titles only**, skipping the 23 date records, would leave "piece 3 landed" not meaning "the
  corpus is unblocked."
- **Full normalization** (also stripping the ~20 never-authored dumped defaults each legacy record
  carries) deletes data nothing currently refuses and reaches the deferred legacy triple.

## 4. The command

`science entity migrate-annotation-base-shape`, beside the existing `entity migrate-hypothesis` and
`entity migrate-specs`. **Its help text states the proposition/evidence-line boundary
unmistakably** — the command intentionally excludes other kinds carrying the same date defect, and
a reader must not have to infer that.

It operates file-level via `directory.glob("*.md")`, following `migrate_specs.py`. It does not load
the project: the repair is a frontmatter rewrite, and coupling it to project load would make it
unavailable exactly when a project is too broken to load.

Report-first, `--apply` to write, per this repo's convention.

### 4.1 The repair algorithm, exactly

Scope is defined by validation (§3.1); this defines what the command is permitted to *change*. Per
candidate file, in order:

1. Parse with `parse_markdown_entity_file_preserving_body`.
2. If `validate_persisted_base_shape` accepts the record → **skip it, byte for byte.** No render,
   no rewrite. A base-valid record is never touched, so canonical re-rendering never leaks onto
   records that did not need repair.
3. Otherwise, if the frontmatter's `title` is **exactly the empty string `""`** → derive the title
   per §3.2 and set it. This is the only key the command may author.
4. Render the resulting mapping with `render_frontmatter`, which coerces YAML `date` values to ISO
   strings (§3.4). This is the whole of the date repair — there is no separate date step.
5. Re-parse the rendered text and run the §5.2 guards and `validate_persisted_base_shape`.
6. If anything is still refused, or any guard fails → the record is **unsupported**: record it as a
   refusal and repair nothing.

**Step 3's condition is exactly `title == ""`, not falsiness.** A missing `title` key, an explicit
`title: null`, or a malformed non-string title are all *unsupported*, not repairable. Each would
still satisfy the `{title}` parsed-value allowlist in §5.2 if the command authored over it, so the
allowlist alone cannot enforce this — the condition has to be stated here and tested directly. The
command replaces a title the writer failed to persist; it never replaces one an author may have
intended.

**Preflight atomicity.** The command plans every record and collects *all* refusals before writing
anything. If any in-scope record has no available repair, it names every such record and writes
nothing at all. Partial application is refused, not reported.

Writes are per-file atomic and a rerun is idempotent, which together are sufficient recovery from a
crash mid-run. This migration deliberately does **not** use the snapshot/journal/replay machinery
`migrate_specs.py` carries; that exists for file moves and semantic cutovers, where a half-finished
run leaves a state no rerun can reconstruct. Rewriting independent frontmatter blocks is not such a
state.

## 5. Certification

### 5.1 The parsed-value diff, defined

"Parsed-value diff" compares the before and after frontmatter mappings **after normalizing
`created`/`updated` to ISO strings**. Raw YAML changes those values' type — `datetime.date` on the
way in, `str` on the way out — so the 23 date records are semantics-free only under that
normalization. Stating the normalization is what makes the guard meaningful instead of tautological.

### 5.2 Migration-time guard, run per repository

For every repaired file: the frontmatter key set is unchanged, the body is byte-identical, and the
parsed-value diff is a subset of `{title}`.

**The source file is read with `parse_markdown_entity_file_preserving_body`** — or equivalently
`open(newline="")` plus `split_frontmatter`. `Path.read_text()` applies universal-newline
translation, so a body whose line endings the render changed would compare equal and the guard
would false-green on exactly the corruption it exists to catch. Naming the reader is part of the
guard, not an implementation detail.

The post-image is **not** read from disk. Preflight plans in memory, so the comparison is against
the rendered text, reparsed with `split_frontmatter`. That is already exact — newline translation
is a file-read concern, not a string concern — and it keeps the guard where it belongs: before any
file is written, not after.

Measured across all 792 with the canonical renderer:

```
records: 792   bodies changed: 0   unexpected: 0
  769  ('title',)
   23  (none)
```

### 5.3 Post-condition

Zero proposition or evidence-line records refused by `validate_persisted_base_shape`, corpus-wide.

### 5.4 Durable tests in the toolkit suite

1. A title-only repair produces exactly the derivation's output, **for both kinds** — one
   proposition case and one evidence-line case, since they are two different derivations and a
   single-kind test leaves one uncovered. Both **mutation-certified** by breaking the derivation
   and watching it go red.
2. A date-only repair, with no title change.
3. One repairable record plus **two** unsupported records under `--apply`: no file changes at all,
   and the error names **both** unsupported records. Two, not one, because the ruling is that
   preflight collects *all* refusals before writing — with a single unsupported record, a command
   that aborts on the first refusal it meets passes and the aggregation is never tested. This test
   pins preflight atomicity; a per-file loop passes every other test in this list.

   **The two unsupported fixtures are `title: null` and `title: 0`.** They are the fixtures that
   discriminate §4.1's `title == ""` from a naïve `if not title`, which would repair both. A
   record with the `title` key *missing* does not discriminate: §5.2's key-set guard catches it
   independently, so it would fail for the wrong reason and leave the condition untested. Choosing
   the fixtures is part of the test, not an implementer's detail.
4. A base-valid record with an authored title is byte-identical after `--apply`, while an invalid
   neighbour in the same directory is repaired. This pins step 2 of §4.1 — without it, a command
   that canonically re-renders everything in scope passes every other test while rewriting records
   it had no business touching.
5. Dry-run writes nothing.

### 5.5 What is deliberately not a durable invariant

"Every title equals its derivation" must never become a guard. 255 records already carry authored
prose, `title` is in `CREATE_ONLY_KEYS`, and the update path preserves author replacements by
design. The derivation is a floor for records that never got one, not a canonical form. Only the
§5.3 post-condition is permanent.

## 6. Rollout

Five project roots, one commit each: mm30 681, cbioportal 72, evolution 21, protein-landscape 16,
meta 2. Four of those are repositories external to the toolkit; **`meta` is a project root inside
this repository**, so its corpus commit lands here alongside the toolkit change — as a separate
commit, but not a separate repository.

Expected diff shape, measured: 719 files at 6 changed lines (title, `created`, `updated`), 21 at 4,
and 52 spread across 7–12 lines where a long scalar additionally unwraps from PyYAML's 80-column
default to the canonical `width=10_000`. Those unwraps are pure reflow — the parsed values are
identical, which §5.2 asserts rather than assumes.

Verification uses the §5.3 scan. It does **not** use `science validate`: that command writes entity
and task files as a side effect of running, so repeated runs inflate their own error counts and a
before/after comparison is only valid between restored-identical trees.

## 7. Scope

**In:** the base-shape repair of 792 proposition and evidence-line records; the shared scalar title
derivations; the `migrate-annotation-base-shape` command; the five corpus commits.

**Out:**

- The ~20 never-authored dumped defaults each legacy record carries (`accessions`, `blocked_by`,
  `same_as`, `xrefs`, and the rest) — nothing refuses them.
- The legacy triple (`legacy_relation_label`, `legacy_patch`, `legacy_edge_id`), deferred by the
  reasoning-invalidation design and untouched here.
- The remaining unquoted-date records in other kinds (plan, question, report, interpretation,
  discussion, topic, probe, method, paper). That fix is kind-agnostic and wants its own branch.
- Retrofitting the workbench emitter's `created`/`updated` force-quoting. That belongs to the
  deferred format-normalization phase, and it is what makes §3.4's churn temporary.
- Arming the `proposition` and `evidence-line` mixins. The umbrella sequences those as separate
  atomic closure slices after remediation.
- Containing the promotion accrual path. `append_entity_source_ref` writes without
  `certify_persisted` (§1), so it remains an uncontained update path after this slice. Remediation
  removes the records it could currently corrupt, but not the hole; closing that is a containment
  change, not a corpus change.
