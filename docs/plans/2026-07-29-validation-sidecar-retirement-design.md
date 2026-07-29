# Validation sidecar retirement — design

**Date:** 2026-07-29
**Status:** approved, awaiting implementation plan
**Amends:** [`2026-07-27-finding-convergence-design.md`](2026-07-27-finding-convergence-design.md)
**Supersedes:** [`2026-07-28-finding-convergence-plan-2-producer-cutover.md`](2026-07-28-finding-convergence-plan-2-producer-cutover.md) Step 3, sidecar paragraph
**Blocked on:** `finding-convergence-plan-3` merging to `main`

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

`validate/runner.py:145` calls `_install_python_sidecar(ctx)`, which builds a
module spec from `<project_root>/validate_local.py`, inserts the project root on
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

### 1.2 The extension point has been silently dead

This is not hypothetical drift. `ValidateContext.papers_dir` and the two live
`reviews-are-not-evidence` sidecars resolve papers as `doc/papers/`, while
`ProjectPaths` places entities under `entities/`. Observed state:

| project | `doc/papers/` | `entities/papers/` | guardrail behaviour |
|---|---|---|---|
| `~/d/cancer/mechanisms/evolution` | absent | 15 files | returns on line 1: `"doc/papers/ not present; guardrail checks skipped"` |
| `~/d/health/meta` | 1 file | 131 files | reports `"0 reviews-are-not-evidence violations"` against a near-empty set |

Nine `status:background` papers exist across those two projects' `entities/papers/`
trees. The guardrail has been reporting a **pass** while scanning a directory the
papers had already left.

This reframes the layout mismatch. It is not a migration chore to fold into the
work; it is the evidence that a project-owned check drifted out of the canonical
layout and no surface noticed. A check that lists its own scope has a hole by
construction, and a project-owned check has no one watching the list. That is the
argument for centralizing the policy, independent of §1.1.

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

That is the **proximate cause** of the protein-landscape crash recorded in the
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

The supersession is recorded in both documents. Plan 2 is not rewritten — it
shipped, and the rest of it stands.

## 3. Scope

### 3.1 Removals

- `validate/runner.py`: `hook`, `HookFn`, `HookName`, `_HOOKS`, `_HOOK_NAMES`,
  `_dispatch_hooks`, `_clear_hooks`, `_install_python_sidecar`,
  `_PythonSidecarState`, and the `SCIENCE_VALIDATE_DISABLE_SIDECAR` branch.
- `validate/__init__.py`: the `hook` export.
- `project_artifacts/port_validate_sidecar.py` and its CLI entry point — the
  porting command targeted `validate.local.sh → validate_local.py`, a migration
  whose destination no longer exists.
- `ValidateContext.papers_dir`, `.provenance_dir`, `.themes_dir`. These carry the
  stale `doc/`-rooted paths from §1.2 and have **zero production consumers** —
  the only reference in the tree is `tests/validate/test_context.py:24-26`,
  which asserts their stale values. Delete the fields and those assertions
  together; a field whose sole consumer is a test pinning it to a wrong value is
  how §1.2 stayed invisible.

The legacy `validate.local.sh` detection and its `RULE_SIDECAR_REMOVED` finding
are **retained** — that path never executed project code.

### 3.2 A distinct rule for the Python sidecar

`RULE_SIDECAR_REMOVED` (`validate.sidecar-removed`, `validate/runtime.py:35`)
already means *legacy `validate.local.sh` present*. Reusing it for
`validate_local.py` would collapse two distinct project conditions under one rule
id, defeating the identity stability the convergence program makes load-bearing.

Add a second rule, `validate.python-sidecar-removed`, to
`VALIDATION_RUNTIME_PRODUCER`. Both rules remain owned by the runtime producer
and validated through `validate_producer_result`.

A project carrying `validate_local.py` therefore gets one structured finding
naming the file and pointing at the migration guide. The file is never imported,
never added to `sys.path`, and never executed. `--json` output stays valid.

### 3.3 Promoting `reviews-are-not-evidence`

Promote to `validate/checks/papers.py` as a canonical check with a declared
`FindingRule` and stable identity qualifiers.

**Take health/meta's variant.** It is a strict superset of evolution's: both walk
`evidence_refs:` blocks under themes, synthesis reports, and hypotheses, but
health/meta additionally checks `doc/provenance/*.yaml` for `source_ref`,
`evidence_tier`, and `review_typed_source`. Evolution's is the same check with
the provenance arm absent.

Rebase every root onto the canonical entity layout: `entities/papers` for the
`status: background` set, and `entities/themes`, `entities/reports/synthesis`,
`entities/hypotheses` for citation sites. Resolve the provenance root against
current layout conventions rather than porting `doc/provenance` verbatim.

Every `Severity.INFO` row in both sidecars ("checks skipped", "checks pass",
"0 violations") becomes a `ValidationNotice`. Per Plan 2 Step 4, only
`prose-lints.config` and `prose-lints.advisory` remain INFO findings.

Delete `~/d/health/meta/validate_local.py` and
`~/d/cancer/mechanisms/evolution/validate_local.py`.

### 3.4 Documentation

Edit canonical sources only, then regenerate committed mirrors — the pattern
established by the [coding-agent design](2026-07-27-coding-agent-support-design.md)
("Generated artifacts: commit them and verify exact fresh-generation equality").

- `docs/conventions/validate.md` — remove the Python-sidecar discovery contract
  and the `SCIENCE_VALIDATE_DISABLE_SIDECAR` row.
- `docs/migration/2026-05-19-validate-local-sh-porting-guide.md` — retarget from
  "port your shell sidecar to Python" to "sidecars are retired; here is where
  each kind of check goes now."
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

- leave `science validate` and its `--json` output entirely;
- become plain project-owned commands the project invokes itself;
- have **nothing enforcing that they run**.

This is a real regression in enforcement and is recorded as such. It is not
mitigated by a hook, a config key, or a validate.sh extension point — each of
those would reopen §1.1. Each project documents the command in its own
`AGENTS.md`; whether either check later earns promotion to a canonical check is a
separate question, out of scope here.

## 5. Verification

Per the [concept-slice inventory](2026-07-28-schema-closure-concept-slice-inventory.md)
§"real-project comparison", parity is established finding-by-finding, not by
summary counts.

**Toolkit regression coverage:**

1. A project containing `validate_local.py` produces valid structured JSON with
   exactly one `validate.python-sidecar-removed` finding, and no traceback.
2. The sidecar module is never imported and never executed — assert on
   `sys.modules` and on a sentinel side effect the fixture sidecar would produce
   if run.
3. A project-authored `FindingRule` cannot enter the registry.
4. `validate.python-sidecar-removed` and `validate.sidecar-removed` are distinct
   rules with independent identity; a project carrying both files gets both
   findings.
5. The promoted `reviews-are-not-evidence` check has stable rule identity and
   fires on a fixture with a `status: background` paper cited from
   `entities/hypotheses`.
6. **The check can fail.** A mutation that points the check at a non-existent
   root must turn the fixture red. §1.2 is the case study in why a check that
   only ever passes is unfalsifiable.

**Real-project comparison,** with expected deltas declared in advance rather than
reconciled to zero:

| project | baseline | expected delta |
|---|---|---|
| `~/d/health/meta` | takeable | guardrail newly fires on background papers under `entities/papers/` — the 9-paper set is the ground truth, not noise |
| `~/d/cancer/mechanisms/evolution` | takeable | same; its guardrail previously short-circuited on line 1 |
| `~/d/science/meta` | takeable | t034 findings disappear from validate output (§4) |
| `~/d/protein-landscape` | **none — crashes today** | first successful run; compare against the crash, and confirm the original command emits valid JSON |

The evolution and health/meta "after" states will contain findings the "before"
state was structurally incapable of producing. Reconciling those to zero would be
tuning the instrument to preserve a false pass.

## 6. Out of scope

- **The task-storage migration warning.** Recent schema work treats the
  pre-split storage layout as an explicit migration blocker — `cbioportal` and
  `~/d/health/processes/post-acute-infection` are both graph-blocked on it. It is
  recorded as follow-up, not hidden behind a fallback.
- **Plan 3.** `finding-convergence-plan-3` carries 8 unmerged commits touching
  `runner.py` and `runtime.py`. This work lands after it merges; starting sooner
  guarantees a conflict in exactly the files both change.
- **Repairing the Plan 2 export gap.** Exporting `FindingRule` and
  `ValidationNotice` for sidecar consumption is the rejected alternative (§1.3),
  not a parallel track.
