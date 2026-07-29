# Validation sidecar retirement — design

**Date:** 2026-07-29
**Status:** approved, awaiting implementation plan
**Amends:** [`2026-07-27-finding-convergence-design.md`](2026-07-27-finding-convergence-design.md)
**Supersedes:** [`2026-07-28-finding-convergence-plan-2-producer-cutover.md`](2026-07-28-finding-convergence-plan-2-producer-cutover.md) Step 3, sidecar paragraph
**Sequenced after:** `finding-convergence-plan-3` (§6)

## 0. Summary

`science validate` imports and executes `validate_local.py` from the project
root. This design retires that extension point entirely: the toolkit stops
importing project Python, the `hook` API is deleted, and the one genuinely
reusable project-authored check is promoted into the canonical check set. Two
project-specific checks lose their enforcement site; that cost is accepted and
recorded rather than mitigated.

No compatibility layer. No shim for the `hook` decorator. A project that still
carries a sidecar gets a structured finding, not a traceback.

## 1. Justification

Two independent grounds. Either alone would be sufficient; together they close
the question.

### 1.1 The sidecar is a control-plane violation

`validate/runner.py` calls `_install_python_sidecar(ctx)`, which builds a module
spec from `<project_root>/validate_local.py`, inserts the project root on
`sys.path`, and executes the module inside the validator process. Hook functions
registered by that module then run at `pre_validation`, `extra_checks`, and
`post_validation`.

The autonomy envelope's §0 is titled "The control plane sits outside the actor"
and requires that an actor "cannot alter the code that judges it"
([autonomy-envelope design](2026-07-24-autonomy-envelope-design.md), §0 and §4).
A worktree-writable Python file executed in-process by the judging tool is the
most direct available violation of that property. The same document rules that a
project needing a different autonomous surface "is a design conversation, not a
config key" — which is precisely what this document is.

### 1.2 The extension point drifted out of the layout unnoticed

The two live `reviews-are-not-evidence` sidecars, and `ValidateContext`'s own
`papers_dir` field, resolve papers as `doc/papers/`. `ProjectPaths` places
entities under `entities/`. Observed state:

| project | `doc/papers/` | `entities/papers/` | background | guardrail behaviour |
|---|---|---|---|---|
| `~/d/cancer/mechanisms/evolution` | absent | 15 files | **0** | returns on its first branch: `"doc/papers/ not present; guardrail checks skipped"` |
| `~/d/health/meta` | 1 file | 131 files | **9** | reports `"0 violations"` after scanning a near-empty directory |

The reproduction is unambiguous. Running `science validate --format json` in
evolution today raises `TypeError: Result.__init__() missing 1 required
positional argument: 'qualifiers'` at `validate_local.py:17` — which is the
`"doc/papers/ not present"` skip line. The check never got past its own scope
test.

The correct reading is narrow and worth stating precisely, because §5 depends on
it. Evolution has **no** background papers, so a correctly-scoped check there
would emit a notice, not a warning; the defect is that it emitted the *wrong*
notice, for a reason unrelated to the corpus. Health/meta has all nine, but they
are cited under `source_refs:`, not `evidence_refs:` — for example
`entities/themes/0007-observation-and-measurement-bias.md` lists
`paper:Mitchell2023` and `paper:Tasci2022` under `source_refs`, while its
`evidence_refs` block contains only reports. Its two `paper:Tasci2022`
provenance records already carry `evidence_tier: background` and
`review_typed_source: true`.

So the corpus is currently **compliant**. What was lost was not detection of
present violations but the guardrail's ability to observe its own subject at all.
A project-owned check drifted out of the canonical layout and no surface noticed,
because a project-owned check has no one watching its scope. That is the argument
for centralizing the policy, and it stands whether or not the corpus is clean.

### 1.3 What is *not* the justification

After Plan 2's producer cutover, all four live sidecars are broken three ways:

| project | rule | `qualifiers` | `Severity.INFO` |
|---|---|---|---|
| `~/d/science/meta` (t034) | `"evidence-payloads"` — str | missing | yes |
| `~/d/health/meta` | `"reviews-are-not-evidence"` — str | missing | yes |
| `~/d/cancer/mechanisms/evolution` | `"reviews-are-not-evidence"` — str | missing | yes |
| `~/d/protein-landscape` | `"expensive-pipeline-artifacts"` — str | missing | yes |

`Result` now requires a `FindingRule` object and a `qualifiers` argument;
`_dispatch_hooks` raises `TypeError` on any non-policy `INFO`. Meanwhile
`science_tool/validate/__init__.py` exports `Result`, `Severity`,
`ValidateContext`, `hook`, `RunResult`, and `run` — but neither `FindingRule` nor
`ValidationNotice`. Plan 2 therefore shipped a sidecar contract that no sidecar
could satisfy, and migrated none of its four consumers.

That is the **proximate cause** of the crashes — the one reproduced above in
evolution, and the protein-landscape instance recorded in the
[method-slice inventory](2026-07-29-schema-closure-method-slice-inventory.md)
§"Pre-existing conditions". It is deliberately not the justification for this
design: repairing it by exporting the two missing symbols and migrating four
sidecars is a smaller, available fix. This design rejects that fix on the grounds
in §1.1 and §1.2, not on grounds of repair cost.

## 2. Relationship to the finding-convergence program

The [finding-convergence design](2026-07-27-finding-convergence-design.md) §6
already forbids project-authored rule policy: "There is no hand-maintained
central rule list and no project-authored policy." Project configuration's only
role is contributing trusted kind descriptors by activating a profile or ontology
catalog.

However, [Plan 2](2026-07-28-finding-convergence-plan-2-producer-cutover.md)
Step 3 explicitly **preserved** the sidecar under a registry constraint:

> Python sidecar hooks may return only `Result` objects carrying an
> already-registered toolkit `FindingRule`; wrapping them under the runtime
> producer does not authorize a project-created declaration, because registry
> lookup still rejects it.

That paragraph is superseded here. The program's position becomes: project code
does not run inside validation at all, registry-constrained or otherwise. §6's
"no project-authored policy" is extended to "no project-authored *execution*".

**The supersession is recorded in this amendment only.** Plan 2 shipped and
remains a historical record of what was built; it is not edited. A reader who
starts from Plan 2 reaches this document through the program index, not through
an in-place correction.

## 3. Scope

### 3.1 Removals — toolkit

- `validate/runner.py`: `hook`, `HookFn`, `HookName`, `_HOOKS`, `_HOOK_NAMES`,
  `_dispatch_hooks`, `_clear_hooks`, `_install_python_sidecar`,
  `_PythonSidecarState`, and the sidecar-disabling environment-variable branch.
- **`run()`'s `enable_python_sidecar` parameter**, not merely the env-var branch.
  It has a production caller — `graph/health_checks/validate.py` passes it
  `False` — which must be updated in the same change. Deleting the branch while
  leaving the parameter would leave a keyword that silently does nothing.
- `validate/__init__.py`: the `hook` export.
- `project_artifacts/port_validate_sidecar.py` and its CLI entry point — the
  porting command targeted `validate.local.sh → validate_local.py`, a migration
  whose destination no longer exists. Remove its `budget/registry.py` entry
  (`"single generated-sidecar path"`) and its tests with it.
- `project_artifacts/registry.yaml`: the `validate.sh` artifact still advertises
  `extension_protocol: {kind: python_sidecar, sidecar_path: validate_local.py}`
  with a contract paragraph describing `@hook(...)` registration. **Replace** it
  with `{kind: none, rationale: ...}` — `extension_protocol` is a required field
  on `Artifact` (`registry_schema.py`), and `ExtensionKind.NONE` is a valid
  pairing for `consumer: direct_execute`. Deleting the block outright fails
  schema validation.

  **No version or hash migration.** The `validate.sh` body does not change — only
  its metadata — so `current_hash` is unchanged, and the registry's
  `_no_duplicate_hash` validator explicitly rejects a `current_hash` that also
  appears in `previous_hashes`. The registry's version semantics describe artifact
  *bytes*, and it has no vocabulary for a metadata-only revision. Bumping the
  version here would require redesigning those semantics, which is out of scope:
  leave `version`, `current_hash`, `previous_hashes`, and `migrations` untouched.
- `ValidateContext.papers_dir`, `.provenance_dir`, `.themes_dir`. These carry the
  stale `doc/`-rooted paths from §1.2 and have **zero production consumers** —
  the only reference in the tree is `tests/validate/test_context.py:24-26`,
  which asserts their stale values. Delete the fields and those assertions
  together; a field whose sole consumer is a test pinning it to a wrong value is
  how §1.2 stayed invisible.

The legacy `validate.local.sh` detection and its `RULE_SIDECAR_REMOVED` finding
are **retained** — that path never executed project code.

### 3.2 A distinct rule for the Python sidecar

`RULE_SIDECAR_REMOVED` (`validate.sidecar-removed`, `validate/runtime.py`)
already means *legacy `validate.local.sh` present*. Reusing it for
`validate_local.py` would collapse two distinct project conditions under one rule
id, defeating the identity stability the convergence program makes load-bearing.

Add a second rule to `VALIDATION_RUNTIME_PRODUCER`, frozen as:

| field | value |
|---|---|
| id | `validate.python-sidecar-removed` |
| severity | `ERROR` |
| subject | `ProjectSubject` (`type: "project"`) |
| identity qualifiers | none — empty |

Empty qualifiers are correct because the condition is per-project and
unrepeatable: a project either carries the file or does not.

A project carrying `validate_local.py` therefore gets one structured finding
naming the file and pointing at the migration guide. The file is never imported,
never added to `sys.path`, and never executed. `--format json` output stays
valid.

### 3.3 Promoting `reviews-are-not-evidence`

Promote to `validate/checks/papers.py` as a canonical check.

**Take health/meta's variant.** It is a strict superset of evolution's: both walk
`evidence_refs:` blocks under themes, synthesis reports, and hypotheses, but
health/meta additionally checks provenance records for `source_ref`,
`evidence_tier`, and `review_typed_source`. Evolution's is the same check with
the provenance arm absent.

#### Roots — pinned, not left to implementation

Leaving roots to implementation would recreate exactly the scope drift §1.2
diagnoses. Every root resolves through the canonical path policy:

| arm | root |
|---|---|
| background paper set | `resolve_path_policy("paper").root` |
| citation sites | `resolve_path_policy("theme").root` |
| citation sites | `resolve_path_policy("report").root` |
| citation sites | `resolve_path_policy("hypothesis").root` |
| provenance records | `ctx.doc_dir / "provenance"` |

Two corrections to the sidecars' assumptions are folded in. `entities/reports/synthesis`
**does not exist** in either project — reports live flat under the `report` root,
so the check walks that root rather than a `synthesis/` subdirectory. And there
is **no canonical `entities/provenance` kind**; health/meta's records remain
under `doc/provenance/*.yaml`. The provenance arm is therefore the one
deliberately non-entity root in the check, and is written as such rather than
being quietly migrated to an entity kind that does not exist.

#### Finding contract — frozen

Identity now drives acceptance and ingestion, so "stable identity qualifiers" is
insufficient. Three rules, all `WARN`, all `PathSubject` (`type: "path"`), each
with an identity-bearing `paper_ref` qualifier:

| rule id | fires when |
|---|---|
| `papers.background-review-evidence-ref` | an `evidence_refs:` block at a citation site cites a `status: background` paper |
| `papers.background-review-source-typing` | a provenance record's `source_ref` names a background paper without `review_typed_source: true` |
| `papers.background-review-evidence-tier` | a provenance record's `source_ref` names a background paper without `evidence_tier: background` |

They are **three rules, not one with a qualifier discriminator**, because a
single provenance record can violate both typing conditions at once; sharing a
rule id would collide on identity.

The same frozen identity constrains deduplication. Finding identity is
`(rule, path, paper_ref)`, so the evidence-ref arm must deduplicate per
`(path, paper_ref)` across the **entire file**, not per `evidence_refs:` block.
The sidecars deduplicated with a `seen` set scoped inside each block, which is
a behaviour change, not a port: a paper cited from two blocks in one file
produced two rows there and would now produce two identical identities, which
the producer boundary rejects.

The check runs in **both the `full` and `commit` profiles** and is **not**
conditional on `--all`. A guardrail that only runs in the slow path is a
guardrail that stops running.

Every `Severity.INFO` row in both sidecars ("checks skipped", "checks pass",
"0 violations") becomes a `ValidationNotice`. Per Plan 2 Step 4, only
`prose-lints.config` and `prose-lints.advisory` remain INFO findings.

### 3.4 Documentation

Edit canonical sources only, then regenerate committed mirrors — the pattern
established by the [coding-agent design](2026-07-27-coding-agent-support-design.md)
("Generated artifacts: commit them and verify exact fresh-generation equality").

- `docs/conventions/validate.md` — remove the Python-sidecar discovery contract
  and the sidecar-disabling environment-variable row.
- `docs/migration/2026-05-19-validate-local-sh-porting-guide.md` — retarget from
  "port your shell sidecar to Python" to "sidecars are retired; here is where
  each kind of check goes now."
- `docs/migration/managed-artifacts-template.md` — **not historical**, and still
  instructs projects to migrate logic *into* a sidecar. Update or retire it;
  leaving it is an active instruction to recreate what this design removes.
- Regenerate `skills/generated/science-command-preamble/references/docs/conventions/validate.md`.
  Never hand-edit files under `skills/generated/`.

## 4. The residue — accepted loss

Two sidecar checks are genuinely project-specific and are **not** promoted:

- `~/d/science/meta` — t034 evidence-payload validation, which shells into the
  project's own `t034_validator` package.
- `~/d/protein-landscape` — expensive-pipeline-artifact presence, which shells
  into project pipeline state.

`validate.sh` is now a four-line managed shim (`exec uv run science validate "$@"`),
hash-tracked in `project_artifacts/registry.yaml` with byte-replace migrations.
**There is no project-owned section in it.** Consequently these two checks:

- leave `science validate` and its `--format json` output entirely;
- become plain project-owned commands the project invokes itself;
- have **nothing enforcing that they run**.

This is a real regression in enforcement and is recorded as such. It is not
mitigated by a hook, a config key, or a validate.sh extension point — each of
those would reopen §1.1.

### 4.1 Consumer deletions — all four

Realizing §4 requires deleting every sidecar, not only the two whose policy is
promoted:

| file | reason |
|---|---|
| `~/d/health/meta/validate_local.py` | policy promoted (§3.3) |
| `~/d/cancer/mechanisms/evolution/validate_local.py` | policy promoted (§3.3) |
| `~/d/science/meta/validate_local.py` | becomes a project-owned command |
| `~/d/protein-landscape/validate_local.py` | becomes a project-owned command |

### 4.2 Rollout must be atomic per consumer

A consumer that deletes its sidecar before installing the toolkit that carries
the replacement has no policy at all in the interval. Three of the four pin the
toolkit by revision, so deletion and adoption are separate acts that must not be
separated:

| project | pin site | current revision |
|---|---|---|
| `~/d/health/meta` | explicit `rev` in `pyproject.toml` `[tool.uv.sources]`, plus `uv.lock` | `3b72db60` (pre–Plan 2) |
| `~/d/cancer/mechanisms/evolution` | unqualified Git source; revision resolved in `uv.lock` | `ed6b50dc` |
| `~/d/protein-landscape` | unqualified Git source; revision resolved in `uv.lock` | `ed6b50dc` |
| `~/d/science/meta` | editable, in-repository | n/a |

The rollout therefore requires, in order:

1. The toolkit commit is **reachable from the public default branch** —
   `origin/main` on `khughitt/science`. A consumer cannot resolve an unpushed
   revision, so no consumer commit may be authored before the push lands.
2. Each consumer's change is **one commit**: pin and/or lock update, sidecar
   deletion, and documentation change together. Never a commit that only deletes.

Science/meta is exempt from the pin step — its toolkit source is editable and
in-repository, so toolkit and consumer change move together by construction. Its
sidecar deletion and documentation repair still land as one commit.

### 4.3 Consumer documentation

Each affected project's `AGENTS.md` records the change. For science/meta this is
a **repair, not an addition**: its current documentation states that t034
validation is invoked through `validate_local.py`, which will be false. Protein-
landscape documents its artifact-checker command. Health/meta and evolution
record that the guardrail is now a toolkit check and that the project no longer
owns it.

Whether the t034 or artifact checks later earn promotion to canonical checks is a
separate question, out of scope here.

## 5. Verification

### 5.1 Baseline availability — three distinct states

Sidecar-source incompatibility and observed crash are not the same thing. All
four sidecar sources are incompatible with the Plan 2 API (§1.3), but what a
project does today depends on which toolkit revision it has installed:

| project | installed toolkit | today |
|---|---|---|
| `~/d/cancer/mechanisms/evolution` | locked at `ed6b50dc` (post–Plan 2) | **crashes** |
| `~/d/protein-landscape` | locked at `ed6b50dc` (post–Plan 2) | **crashes** |
| `~/d/science/meta` | editable, in-repository | **crashes** |
| `~/d/health/meta` | pinned `rev = 3b72db60` (pre–Plan 2) | **runs**; exit 0, valid JSON |

Health/meta's pinned toolkit predates the producer cutover, so it still executes
its sidecar. `.venv/bin/science validate --format json` exits 0 with 153
warnings. **Its baseline is available and must be taken.**

That baseline also sharpens §1.2. It contains **zero** rows from the guardrail:
`doc/papers/` holds only an `archive/` subdirectory and no paper files, so the
check ran, found an empty background set, and reported "checks pass" — an INFO
that does not even reach the summary (`infos: 0`). The guardrail executed
successfully and contributed nothing observable, while nine background papers
sat in `entities/papers/`. The after-state's notice is therefore a net addition
of observability, not a diff against an existing row.

For the three crashing projects there is no before-state to diff against. The
comparison is defined in two parts:

1. **Canonical-validator baseline.** Run every project with sidecars disabled, so
   the toolkit's own checks execute and produce a real finding set. This is the
   before-state for everything in §3.1 and §3.4, and it must be finding-by-finding
   identical after the change — the retirement must not perturb canonical output.

   **One toolkit revision for all four.** The baseline must be taken with a single
   post–Plan 3, pre-retirement revision run against every project root — not with
   each project's own installed revision. Health/meta sits at `3b72db60` and the
   others at `ed6b50dc`; comparing those to a post-retirement toolkit would
   conflate this change with every unrelated change between those revisions.
   Plan 3 merging and the branch rebasing onto it is therefore a **precondition**
   of baseline capture, not merely of landing.

   Notices are not carried in `--format json`. Where a notice is the expected
   output, assert it through `RunResult.notices` or verbose text rendering.
2. **Intended-policy evaluation.** Evaluate the promoted check of §3.3 separately,
   against the corpus, on its own terms. It has no predecessor output to match,
   because its predecessor never observed its subject.

### 5.2 Expected delta — no new policy findings

Per §1.2, the corpus is currently compliant. The honest prediction is therefore:

| project | expected after promotion |
|---|---|
| `~/d/cancer/mechanisms/evolution` | notice: no `status: background` papers. **Zero warnings.** |
| `~/d/health/meta` | notice: 9 background papers, 0 violations — none cited under `evidence_refs`, and both `paper:Tasci2022` provenance records already carry `evidence_tier: background` and `review_typed_source: true`. **Zero warnings.** |
| `~/d/science/meta` | t034 findings absent from validate output (§4) |
| `~/d/protein-landscape` | artifact findings absent from validate output (§4) |

The delivered value is **restored scope observability and accurate notices**, not
newly-detected violations. An earlier draft of this design predicted warnings in
both projects; the corpus does not support that, and the prediction has been
withdrawn. Recording an expected-violation count that the corpus cannot produce
would be the same error as tuning evidence to fit a conclusion — and would have
made a passing run look like a missed detection.

The §1.2 false-pass evidence is unaffected by this. It establishes that the check
could not see its subject, which is true regardless of whether the subject
contained violations.

### 5.3 Regression coverage

1. A project containing `validate_local.py` produces valid structured JSON
   containing **exactly one occurrence of `validate.python-sidecar-removed`**,
   and no traceback. (Not "exactly one finding overall" — canonical checks
   continue to emit their own.)
2. The sidecar module is never imported and never executed — assert on
   `sys.modules` and on a sentinel side effect the fixture sidecar would produce
   if run.
3. A project-authored `FindingRule` cannot enter the registry.
4. `validate.python-sidecar-removed` and `validate.sidecar-removed` are distinct
   rules with independent identity; a project carrying both files gets both
   findings.
5. Each of the three §3.3 rules has stable identity and fires on a fixture
   exercising it, including a provenance record violating both typing conditions
   simultaneously — which must yield two findings, not one.
6. The promoted check is present in both `full` and `commit` profile runs.
7. **The check can fail.** A mutation pointing the check at a non-existent root
   must turn the fixture red. §1.2 is the case study in why a check that only
   ever passes is unfalsifiable — and §5.2 means the real corpus cannot supply
   that falsification, so the fixture must.

## 6. Out of scope

- **The task-storage migration warning.** Recent schema work treats the
  pre-split storage layout as an explicit migration blocker — `cbioportal` and
  `~/d/health/processes/post-acute-infection` are both graph-blocked on it. It is
  recorded as follow-up, not hidden behind a fallback.
- **Plan 3.** `finding-convergence-plan-3` carries 7 unmerged commits. It
  modifies neither `runner.py` nor `runtime.py`, and currently merges cleanly
  with `main` — there is **no** guaranteed textual conflict, and an earlier draft
  of this design claimed one in error. Sequencing after it remains correct for a
  different reason: it changes `validate/findings.py`, `validate/acceptance.py`,
  and `findings/acceptance_migration.py`, so it moves the finding and acceptance
  interfaces this work declares new rules against. Landing after it means
  declaring against stable interfaces and establishing the intended baseline
  once. This is a coordination and interface-stability dependency, not a merge
  hazard.
- **Repairing the Plan 2 export gap.** Exporting `FindingRule` and
  `ValidationNotice` for sidecar consumption is the rejected alternative (§1.3),
  not a parallel track.
