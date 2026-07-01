# t037 Agent / Tool Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the t037 v1.1 design through the same layered sequence that worked for t034: pilot extraction, v1.2 patch, validator prototype, prototype findings, and v1.3 patch.

**Architecture:** Keep t037 as a meta-project schema-design track, not production integration yet. The design doc remains the contract; pilot and prototype artifacts pressure-test authorability and decidability; the standalone prototype proves the core rules can be enforced before anything is folded into `meta/validate.sh`.

**Tech Stack:** Markdown design artifacts in `meta/doc/plans`, Python 3 standalone validator prototype, project validation via `cd meta && bash validate.sh --verbose`.

---

## Scope

This plan implements the next t037 research/development loop from:

- Design contract: `meta/doc/plans/historical/2026-05-07-t037-agent-tool-operations-extension-design.md`
- Source synthesis: `meta/doc/background/papers/synthesis-2026-05-06-scientific-agents-knowledge-graphs.md`
- Source paper summaries: `Ding2025.md`, `Yu2026.md`, `Si2025.md`
- Contract dependency: `meta/doc/plans/2026-05-06-evidence-payload-core-and-extension-contract.md`
- Precedent: the t034 artifact sequence in `meta/doc/plans/2026-05-06-t034-*`

Out of scope for this plan:

- Production registry storage.
- Integration into `meta/validate.sh`.
- Updating the t025 reason-code registry.
- Graph-evolution schema work owned by t038.

Those become follow-up tasks after the t037 v1.3 prototype loop is stable.

## File Map

Create:

- `meta/doc/plans/historical/2026-05-07-t037-pilot-extraction.md`
  - Owns the authoring pressure-test for the v1.1 schema.
- `meta/doc/plans/historical/2026-05-07-t037-agent-tool-operation-validator-prototype.py`
  - Standalone validator prototype for `agent-tool-operation` structural and reason-code rules.
- `meta/doc/plans/historical/2026-05-07-t037-validator-prototype-findings.md`
  - Reports prototype coverage, test outcomes, and v1.3 patch candidates.

Modify:

- `meta/doc/plans/historical/2026-05-07-t037-agent-tool-operations-extension-design.md`
  - Patch v1.1 -> v1.2 after pilot findings.
  - Patch v1.2 -> v1.3 after validator findings.

Optional if the task owner wants task bookkeeping in the same pass:

- `meta/tasks/active.md`
  - Update t037 status or notes only after the v1.3 design is written.

---

### Task 0: Verify or Apply the v1.1 Audit Baseline

**Files:**
- Modify if needed: `meta/doc/plans/historical/2026-05-07-t037-agent-tool-operations-extension-design.md`
- Read: `meta/doc/plans/2026-05-06-evidence-payload-core-and-extension-contract.md`

- [ ] **Step 1: Verify the design is labeled v1.1**

Run:

```bash
sed -n '1,8p' meta/doc/plans/historical/2026-05-07-t037-agent-tool-operations-extension-design.md
```

Expected: line 1 says `t037 draft v1.1`, and the status block starts with `**Status:** v1.1 draft (2026-05-07)`.

- [ ] **Step 2: Verify the v1.1 audit rules are canonical in the design**

Run:

```bash
rg -n "pipeline-runner|absence-sensitive roles|direct capability calls|agent-source-unvalidated.*validation_status_detail: unvalidated|agent-evaluation.*does not declare `agent-source-unvalidated`|Registry-resolved validation view" meta/doc/plans/historical/2026-05-07-t037-agent-tool-operations-extension-design.md
```

Expected: every pattern appears. These are the v1.1 audit baseline rules that Tasks 1-5 depend on:

- `pipeline-runner` is in the role taxonomy.
- The absence-sensitive role set is enumerated.
- Direct command/skill/tool calls require a one-step `tool_chain_ref`.
- `agent-source-unvalidated` is local to `agent-tool-operation`.
- `agent-evaluation` does not declare `agent-source-unvalidated`.
- Reason-code validation for safety and chains uses a registry-resolved operation view.

- [ ] **Step 3: Verify t022 enum support**

Run:

```bash
rg -n "support_direction: enum.*methodological-input.*quality-record.*operation-record|validation_role: enum.*quality-record-only.*record-only" meta/doc/plans/2026-05-06-evidence-payload-core-and-extension-contract.md
```

Expected: t022 v2.3 lists `support_direction` values including `methodological-input`, `quality-record`, and `operation-record`, and `validation_role` values including `quality-record-only` and `record-only`. If this check fails, add a coordination finding to the pilot extraction before authoring payloads.

- [ ] **Step 4: Patch v1 -> v1.1 if any baseline check fails**

If Steps 1 or 2 fail, patch `2026-05-07-t037-agent-tool-operations-extension-design.md` with the audit-review changes before continuing:

- Update the status block to `v1.1 draft`.
- Add `pipeline-runner` to `agent_role`.
- Add the explicit absence-sensitive role set.
- Add the direct-capability one-step `tool_chain_ref` rule.
- Canonicalize `agent-source-unvalidated` as an operation-local rule.
- Remove `agent-source-unvalidated` from `agent-evaluation` contributions.
- Add the registry-resolved validation-view rule.

Re-run Steps 1 and 2 after patching. Do not proceed to Task 1 until both pass.

---

### Task 1: Pilot Extraction Against v1.1

**Files:**
- Create: `meta/doc/plans/historical/2026-05-07-t037-pilot-extraction.md`
- Read: `meta/doc/plans/historical/2026-05-07-t037-agent-tool-operations-extension-design.md`
- Read: `meta/doc/background/papers/Ding2025.md`
- Read: `meta/doc/background/papers/Yu2026.md`
- Read: `meta/doc/background/papers/Si2025.md`

- [ ] **Step 1: Read the design and source summaries**

Run:

```bash
sed -n '1,220p' meta/doc/plans/historical/2026-05-07-t037-agent-tool-operations-extension-design.md
sed -n '220,520p' meta/doc/plans/historical/2026-05-07-t037-agent-tool-operations-extension-design.md
sed -n '1,220p' meta/doc/background/papers/Ding2025.md
sed -n '1,220p' meta/doc/background/papers/Yu2026.md
sed -n '1,220p' meta/doc/background/papers/Si2025.md
rg -n "support_direction: enum.*methodological-input.*quality-record.*operation-record|validation_role: enum.*quality-record-only.*record-only" meta/doc/plans/2026-05-06-evidence-payload-core-and-extension-contract.md
```

Expected: all files render; no missing source file; t022 v2.3 supports the enum values used by t037. If the t022 check fails, add it as a coordination finding before authoring payloads.

- [ ] **Step 2: Create the pilot extraction document**

Create `meta/doc/plans/historical/2026-05-07-t037-pilot-extraction.md` with this structure:

```markdown
# t037 Pilot Extraction (3 operation/evaluation cases, v1.1)

> **Status:** Pilot extraction (2026-05-07). Empirical pressure-test of `[t037]` v1.1 (`meta/doc/plans/historical/2026-05-07-t037-agent-tool-operations-extension-design.md`).
>
> **Goal:** find gaps between the v1.1 agent/tool operation schema and what authors can actually populate from current project content. Surfaces ref-heaviness, registry-state ambiguity, reason-code decidability gaps, and worked-example drift.

**Sources:**
- `meta/doc/background/papers/Ding2025.md`
- `meta/doc/background/papers/Yu2026.md`
- `meta/doc/background/papers/Si2025.md`
- one project-local operation chosen from existing Science paper-summary or synthesis workflow traces, if enough context exists in the repo

**Method:** author the payload(s) that the source content actually supports. Use only the project's existing summaries and files. Score extraction fields with the same scale used in t034:

| Score | Meaning |
|---|---|
| 2 | Stated explicitly or mechanically determined by the schema. |
| 1 | Clearly inferable from the source. |
| 0 | Ambiguous; multiple plausible values. |
| x | Not present in source and not authoring-stage; would require external lookup or a real run trace. |
| A | Authoring/mechanical field. |

## Extraction 1 - Ding2025 -> agent-tool-operation

## Extraction 2 - Yu2026 -> agent-evaluation

## Extraction 3 - Si2025 -> agent-evaluation

## Extraction 4 - project-local operation record, if authorable

## Cross-case findings

### Cross-case check - context refs vs input refs

Did the extractions consistently place formal derivation inputs in `core.input_artifact_refs` and "what the agent saw" in `extension/agent-tool-operation.context_ref_set`? Record every ambiguous case.

## Proposed v1.2 patches

## Residual audit prompts
```

- [ ] **Step 3: Author Extraction 1 (Ding2025 -> operation record)**

Use the v1.1 `agent-tool-operation` fields. The payload should test:

- `agent_role: hypothesis-generator` or `tool-planner`, depending on the most faithful reading.
- `tool_chain_ref` as a required one-step-or-more chain reference.
- `context_selection_method: kg-filter`.
- `safety_policy_ref` and `safety_check_status`.
- `agent-source-unvalidated` and `tool-chain-unvalidated` authoring.
- Whether `information-absence-undetected` should fire for `hypothesis-generator` with no abstention support.

Record field scores in a table with these rows:

```markdown
| Field | Score | Note |
|---|---:|---|
| core.artifact_type | 2 | `agent-tool-operation` follows from the design. |
| core.input_artifact_refs | 1 | KG context is described, exact view ref is author-created. |
| core.method_ref | 0 | The paper defines the architecture, but the concrete workflow is not in the summary. |
| core.support_direction | 2 | `operation-record` by extension rule. |
| core.validation_role | 2 | `record-only` by extension rule. |
| core.reason_codes | 1 | Depends on inferred validation/safety state. |
| extension/agent-tool-operation.agent_role | 1 | Planner/executor/summarizer roles are named, exact primary role depends on chosen operation. |
| extension/agent-tool-operation.tool_chain_ref | A | Author-created registry ref. |
| extension/agent-tool-operation.context_ref_set | 1 | SciToolKG context explicit; exact kg-view ref absent. |
| extension/agent-tool-operation.safety_check_status | 1 | Safety module explicit; exact check result not given. |
| extension/agent-tool-operation.validation_status_detail | 1 | Benchmark exists, this exact operation unvalidated. |
```

- [ ] **Step 4: Author Extraction 2 (Yu2026 -> agent evaluation)**

Use `agent-evaluation` fields. The payload should test:

- `evaluation_competency: information-absence-detection`.
- `result` authorability from the summary.
- `metric_set` authorability from the summary.
- `evaluated_operation_refs: []` semantics for dataset-level coverage.
- Whether `information-absence-undetected` is declared on partial/fail only.

- [ ] **Step 5: Author Extraction 3 (Si2025 -> bias evaluation)**

Use `agent-evaluation` fields. The payload should test:

- `evaluation_competency: bias-detection`.
- `bayes_factor_evidence`.
- `agent-bias-risk` biconditional behavior.
- Whether `strengthen-belief` remains forbidden despite Bayes-factor evidence.

- [ ] **Step 6: Attempt one project-local operation record**

Search for a recent operation-like artifact:

```bash
rg -n "generated_at:|source_commit:|workflow|pipeline|agent|synthesis" meta/doc/background/papers meta/doc/plans meta/tasks
```

If enough context exists, author one operation record for a paper-summary or synthesis generation. If not, add a section titled `Project-local operation attempt` explaining which fields were unauthorable and why.

- [ ] **Step 7: Summarize pilot findings and patch proposals**

End the pilot with exactly these sections:

```markdown
## Cross-case findings

## Proposed v1.2 patches

## Residual audit prompts
```

Patch proposals should be concrete and numbered `P-pilot-1`, `P-pilot-2`, etc.

- [ ] **Step 8: Validate the project**

Run:

```bash
cd meta && bash validate.sh --verbose
```

Expected: validation exits 0. Existing warnings about `h05`, unverified-marker counts, or stale graph inputs may remain unchanged.

---

### Task 2: Patch Design to v1.2 From Pilot Findings

**Files:**
- Modify: `meta/doc/plans/historical/2026-05-07-t037-agent-tool-operations-extension-design.md`
- Read: `meta/doc/plans/historical/2026-05-07-t037-pilot-extraction.md`

- [ ] **Step 1: Read the pilot's proposed patches**

Run:

```bash
rg -n "P-pilot-|Cross-case findings|Residual audit prompts" meta/doc/plans/historical/2026-05-07-t037-pilot-extraction.md
```

Expected: each proposed patch has a numbered identifier.

- [ ] **Step 2: Update the design status block**

Modify the top status block in `2026-05-07-t037-agent-tool-operations-extension-design.md` so the current line is `v1.2 draft (2026-05-07)` and names `meta/doc/plans/historical/2026-05-07-t037-pilot-extraction.md` as the source of the patch set. Move the v1.1 audit text into a separate prior-history paragraph immediately below it. The v1.2 status paragraph must list every `P-pilot-*` patch from Task 1 in concrete prose.

- [ ] **Step 3: Apply each pilot patch in the owning section**

For each `P-pilot-*`, update the specific section it affects:

- Registry schemas if the patch changes durable entity fields.
- `agent-tool-operation` if the patch changes operation payload fields or validation rules.
- `agent-evaluation` if the patch changes evaluation payload fields or Bayes-factor semantics.
- H03 reason-code table if the patch changes code ownership, blocking flags, or trigger rules.
- Worked examples if the patch changes authoring conventions.
- Validation machinery candidates if the patch changes validator rule scope.

- [ ] **Step 4: Add a `Pilot-driven authoring conventions` section if needed**

If two or more pilot findings are authoring conventions rather than schema fields, add a `Pilot-driven authoring conventions` section after `H03 reason-code additions`. Each convention gets a short bold title and one precise authoring rule. Do not add compatibility layers or legacy aliases.


- [ ] **Step 5: Check for stale v1.1 references**

Run:

```bash
rg -n "v1.1 draft|v1.1 design|v1.1 schema|P-pilot-|\\.\\.\\." meta/doc/plans/historical/2026-05-07-t037-agent-tool-operations-extension-design.md
```

Expected:

- `v1.1` appears only in prior-status/history text.
- `P-pilot-*` appears in the status block and relevant changed sections.
- No literal `...` remains in the status block.

- [ ] **Step 6: Validate the project**

Run:

```bash
cd meta && bash validate.sh --verbose
```

Expected: validation exits 0 with only pre-existing warnings.

---

### Task 3: Build the Standalone `agent-tool-operation` Validator Prototype

**Files:**
- Create: `meta/doc/plans/historical/2026-05-07-t037-agent-tool-operation-validator-prototype.py`
- Read: `meta/doc/plans/historical/2026-05-07-t037-agent-tool-operations-extension-design.md`
- Reference: `meta/doc/plans/2026-05-06-t034-mr-graph-model-validator-prototype.py`

- [ ] **Step 1: Create the prototype file header and rule constants**

Create the Python file with:

```python
#!/usr/bin/env python3
"""
Prototype validator for t037 v1.2 `agent-tool-operation` structural and
reason-code biconditional rules.

Standalone runner. NOT integrated into meta/validate.sh; this is a study.

Run with: python meta/doc/plans/historical/2026-05-07-t037-agent-tool-operation-validator-prototype.py
Exits 0 if all tests match expectations; nonzero otherwise.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Literal

EXT_KEY = "extension/agent-tool-operation"

AGENT_ROLES: set[str] = {
    "paper-reader",
    "field-extractor",
    "synthesis-author",
    "hypothesis-generator",
    "causal-prior-elicitor",
    "tool-planner",
    "tool-executor",
    "pipeline-runner",
    "graph-editor",
    "validator",
    "critic",
    "safety-reviewer",
    "task-editor",
}

ABSENCE_SENSITIVE_ROLES: set[str] = {
    "paper-reader",
    "field-extractor",
    "synthesis-author",
    "hypothesis-generator",
    "causal-prior-elicitor",
    "validator",
    "critic",
}

RETRIEVAL_METHODS: set[str] = {
    "rag-retrieval",
    "kg-filter",
    "web-search",
    "file-search",
}

PERMITTED_ROLES: set[str] = {
    "record-only",
    "quality-record-only",
    "prioritize-attention",
    "gate-update",
}

BLOCKING_CODES: set[str] = {
    "agent-source-unvalidated",
    "tool-chain-unvalidated",
    "safety-check-missing",
    "information-absence-undetected",
}


@dataclass(frozen=True)
class Issue:
    severity: Literal["error", "warning"]
    path: str
    rule: str
    msg: str

    def __str__(self) -> str:
        return f"[{self.severity:5}] {self.rule:8} {self.path}: {self.msg}"
```

- [ ] **Step 2: Add registry-resolved fixture support**

Add this dataclass below `Issue`:

```python
@dataclass(frozen=True)
class ResolvedOperationView:
    """Materialized registry state needed by t037 biconditional rules."""

    invokes_capability: bool = True
    # v1 prototype collapse: the real registry will expose per-protocol results.
    tool_chain_has_passed_validation: bool = False
    applicable_safety_policy: bool = False
```

- [ ] **Step 3: Implement `validate_agent_tool_operation`**

Implement these rules:

| Rule | Meaning |
|---|---|
| ato-1 | extension absent -> no issues. |
| ato-2 | `agent_role` is required and in `AGENT_ROLES`. |
| ato-3 | `validation_role: strengthen-belief` is forbidden. |
| ato-4 | if `ResolvedOperationView.invokes_capability`, `tool_chain_ref` is required. |
| ato-5 | safety policy consistency: if no applicable policy, `safety_check_status` must be `not-applicable` and `safety-check-missing` must not be declared; if applicable policy and status is `skipped` or `unknown`, `safety-check-missing` must be declared. |
| ato-6 | `agent-source-unvalidated` iff `agent_model_version` is present and `validation_status_detail: unvalidated`. |
| ato-7 | `tool-chain-unvalidated` iff `tool_chain_ref` is present and resolved chain has no passed validation. |
| ato-8 | `context-retrieval-uncertain` iff `context_selection_method` is in `RETRIEVAL_METHODS` and context is not complete-for-task. |
| ato-9 | `information-absence-undetected` iff abstention is unsupported for an absence-sensitive role. |
| ato-10 | `target_artifact_refs` is non-empty unless `abstention_reason` is present. |

Use the same `Issue` shape and rule-id style as the t034 prototypes.

- [ ] **Step 4: Add test fixtures**

Add fixture functions equivalent to these cases:

| Test | Expected rules |
|---|---|
| `01-minimal-valid` | none |
| `02-strengthen-forbidden` | ato-3 |
| `03-unknown-agent-role` | ato-2 |
| `04-direct-capability-without-chain` | ato-4 |
| `05-no-safety-policy-not-applicable-clean` | none |
| `06-safety-code-overdeclared` | ato-5 |
| `07-safety-policy-skipped-missing-code` | ato-5 |
| `08-agent-unvalidated-missing-code` | ato-6 |
| `09-agent-unvalidated-overdeclared` | ato-6 |
| `10-tool-chain-unvalidated-missing-code` | ato-7 |
| `11-tool-chain-unvalidated-overdeclared` | ato-7 |
| `12-context-retrieval-uncertain-missing-code` | ato-8 |
| `13-context-retrieval-uncertain-overdeclared` | ato-8 |
| `14-explicit-context-partial-no-code-clean` | none |
| `15-information-absence-missing-code` | ato-9 |
| `16-information-absence-overdeclared-non-sensitive-role` | ato-9 |
| `17-no-target-without-abstention` | ato-10 |
| `18-no-extension-no-issues` | none |
| `19-v12-pilot-adapted-ding` | none |
| `20-v12-pilot-adapted-paper-reader` | none |

- [ ] **Step 5: Add runner**

Use the t034 runner pattern:

```python
def _rules(issues: list[Issue]) -> set[str]:
    return {i.rule for i in issues}


def run_tests() -> int:
    tests = [
        t01_minimal_valid,
        t02_strengthen_forbidden,
        t03_unknown_agent_role,
        t04_direct_capability_without_chain,
        t05_no_safety_policy_not_applicable_clean,
        t06_safety_code_overdeclared,
        t07_safety_policy_skipped_missing_code,
        t08_agent_unvalidated_missing_code,
        t09_agent_unvalidated_overdeclared,
        t10_tool_chain_unvalidated_missing_code,
        t11_tool_chain_unvalidated_overdeclared,
        t12_context_retrieval_uncertain_missing_code,
        t13_context_retrieval_uncertain_overdeclared,
        t14_explicit_context_partial_no_code_clean,
        t15_information_absence_missing_code,
        t16_information_absence_overdeclared_non_sensitive_role,
        t17_no_target_without_abstention,
        t18_no_extension_no_issues,
        t19_v12_pilot_adapted_ding,
        t20_v12_pilot_adapted_paper_reader,
    ]
    failures = 0
    for fn in tests:
        name, payload, resolved_view, expected = fn()
        issues = validate_agent_tool_operation(payload, resolved_view)
        got = _rules(issues)
        if got != expected:
            failures += 1
            print(f"FAIL {name}: expected {sorted(expected)}, got {sorted(got)}")
            for issue in issues:
                print(f"  {issue}")
        else:
            print(f"PASS {name}: {sorted(got)}")
    print(f"{len(tests) - failures}/{len(tests)} tests passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run_tests())
```

- [ ] **Step 6: Run the prototype**

Run:

```bash
python meta/doc/plans/historical/2026-05-07-t037-agent-tool-operation-validator-prototype.py
```

Expected: all tests pass. If any test fails, patch the prototype or the v1.2 design rule before proceeding.

---

### Task 4: Write Validator Prototype Findings

**Files:**
- Create: `meta/doc/plans/historical/2026-05-07-t037-validator-prototype-findings.md`
- Read: `meta/doc/plans/historical/2026-05-07-t037-agent-tool-operation-validator-prototype.py`
- Read: `meta/doc/plans/historical/2026-05-07-t037-agent-tool-operations-extension-design.md`

- [ ] **Step 1: Run the prototype and capture result**

Run:

```bash
python meta/doc/plans/historical/2026-05-07-t037-agent-tool-operation-validator-prototype.py
```

Expected: all tests pass.

- [ ] **Step 2: Create the findings document**

Create `meta/doc/plans/historical/2026-05-07-t037-validator-prototype-findings.md` with:

```markdown
# t037 v1.2 `agent-tool-operation` Validator Prototype - Findings

> **Status:** Findings (2026-05-07). Companion to the validator script at `meta/doc/plans/historical/2026-05-07-t037-agent-tool-operation-validator-prototype.py`.
>
> **Goal:** prove that the load-bearing t037 operation-record rules are decidable from payload state plus a registry-resolved operation view.

## What the prototype implements

## Test outcome

## What this discharges

## What the prototype showed about v1.2's rules

## What the prototype does NOT validate

- `agent-evaluation` extension rules are not validated by this prototype; they are deferred to a follow-up validator slice.
- Cross-payload propagation through `pipeline_provenance_ref` and `input_artifact_refs` is not validated by this prototype.
- Registry construction is not validated; the prototype consumes a simplified `ResolvedOperationView` fixture.

## v1.3 patch candidates

## Next steps
```

- [ ] **Step 3: Fill `What the prototype implements`**

List all implemented rule IDs (`ato-1` through `ato-10`) with one sentence each.

- [ ] **Step 4: Fill `Test outcome`**

Add a table with all prototype tests and their pass/fail status:

```markdown
| Test | Probe | Outcome |
|---|---|---|
| 01-minimal-valid | positive case | passes |
```

- [ ] **Step 5: Fill `v1.3 patch candidates`**

Every prototype ambiguity becomes a concrete candidate patch.

Use patch identifiers `P-proto-1`, `P-proto-2`, and so on. Each item must name the affected rule or section, state the exact design change, and state the prototype behavior that motivated it. If the prototype surfaces no semantic changes, state that explicitly and recommend a v1.3 status-only patch confirming decidability.

---

### Task 5: Patch Design to v1.3 From Prototype Findings

**Files:**
- Modify: `meta/doc/plans/historical/2026-05-07-t037-agent-tool-operations-extension-design.md`
- Read: `meta/doc/plans/historical/2026-05-07-t037-validator-prototype-findings.md`

- [ ] **Step 1: Read v1.3 candidates**

Run:

```bash
rg -n "v1.3 patch candidates|P-proto-[0-9]+|^[0-9]+\\." meta/doc/plans/historical/2026-05-07-t037-validator-prototype-findings.md
```

Expected: concrete patch candidates or explicit "no semantic changes" statement.

- [ ] **Step 2: Update design status history**

Patch the top status block so the current line is `v1.3 draft (2026-05-07)` and names `meta/doc/plans/historical/2026-05-07-t037-validator-prototype-findings.md` as the source of the patch set. Keep separate prior-history paragraphs for v1.2 pilot patches and v1.1 audit patches. The v1.3 status paragraph must list every `P-proto-*` patch in concrete prose.

- [ ] **Step 3: Apply validator-driven rule changes**

Patch every section affected by the findings:

- Rule constants or enum lists in prose.
- Reason-code contribution text.
- Registry-resolved validation-view language.
- Worked examples.
- Validation machinery candidates.
- Open questions, if a question was resolved.

- [ ] **Step 4: Verify no stale version labels**

Run:

```bash
rg -n "v1.2 draft|v1.2 design|v1.1 draft|\\.\\.\\." meta/doc/plans/historical/2026-05-07-t037-agent-tool-operations-extension-design.md
```

Expected: prior version labels appear only in status-history text; no literal `...`.

---

### Task 6: Final Validation and Task Closeout Notes

**Files:**
- Read: all files created/modified by this plan
- Optional modify: `meta/tasks/active.md`

- [ ] **Step 1: Run the prototype**

Run:

```bash
python meta/doc/plans/historical/2026-05-07-t037-agent-tool-operation-validator-prototype.py
```

Expected: all tests pass.

- [ ] **Step 2: Run project validation**

Run:

```bash
cd meta && bash validate.sh --verbose
```

Expected: validation exits 0. Existing warnings are acceptable if unchanged.

- [ ] **Step 3: Review git diff**

Run:

```bash
git status --short
git diff --stat
```

Expected changed files:

- `meta/doc/plans/historical/2026-05-07-t037-agent-tool-operations-extension-design.md`
- `meta/doc/plans/historical/2026-05-07-t037-agent-tool-operations-implementation-plan.md`
- `meta/doc/plans/historical/2026-05-07-t037-pilot-extraction.md`
- `meta/doc/plans/historical/2026-05-07-t037-agent-tool-operation-validator-prototype.py`
- `meta/doc/plans/historical/2026-05-07-t037-validator-prototype-findings.md`
- optional `meta/tasks/active.md`

- [ ] **Step 4: Optional task note update**

If updating task notes, append a short status note for t037 in the task queue using the project’s existing task format. Do not mark t037 done unless the v1.3 design, pilot, prototype, and findings are all present and verified.

---

## Self-Review Checklist

- [ ] Every v1.1 design section has a corresponding plan task:
  - Registry/entity split -> Task 1 pilot and Task 3 registry-resolved validator.
  - `agent-tool-operation` rules -> Tasks 3 and 4.
  - `agent-evaluation` rules -> Task 1 pilot and Task 4 findings.
  - H03 reason-code rules -> Tasks 1, 3, 4, 5.
  - t034 co-load interlock -> Task 1 pilot and Task 5 final patch.
- [ ] No production integration is implied before the prototype findings exist.
- [ ] No direct `strengthen-belief` path is introduced for operation records or agent evaluations.
- [ ] Every validation command has an expected result.
- [ ] Every created file has a single owner and purpose.

## Execution Options

Plan complete and saved to `meta/doc/plans/historical/2026-05-07-t037-agent-tool-operations-implementation-plan.md`. Two execution options:

1. **Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
