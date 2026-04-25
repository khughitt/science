# MAV Audit Addendum — `validate.sh` `mav-input` Set

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Depends on:** `docs/plans/2026-04-25-managed-artifact-versioning.md` (the MAV plan). Executes **after** the MAV plan merges. The MAV plan ships the artifact-versioning machinery at managed version `2026.04.25`; this addendum bumps it again with the audit-surfaced upstream fixes so downstream projects pull the corrections via `science-tool project artifacts update`.

**Goal:** Fold the audit-surfaced `mav-input` fixes into canonical `meta/validate.sh` so 3-of-4 downstream projects' generic validator drift collapses on the next managed-artifact update.

**Audit reference:** `docs/audits/downstream-project-conventions/synthesis.md` §9.1 (P1 #7). Project evidence: `docs/audits/downstream-project-conventions/projects/{natural-systems,mm30,protein-landscape,cbioportal}.md` §8.

**Tech Stack:** Bash; Python 3 for embedded YAML parsing; `pytest`.

---

## Scope

In scope (six concrete fixes):

1. Parameterize `LOCAL_PROFILE` from `science.yaml.knowledge_profiles.local` (already present — verify and remove the residual hard-coded `"local"` fallback path so projects with `project_specific` are not silently miscoerced).
2. Sanction `.env` sourcing canonically with an `SCIENCE_VALIDATE_SKIP_DOTENV=1` opt-out env var.
3. Replace the `ontologies` list-shape check with a `knowledge_profiles.curated` list-shape check.
4. Promote graph-audit unparseable output from `warn` to `error`.
5. Sanction `docs/superpowers/` (and a generalized agent-subtree pattern) in the duplicate-doc-root warning.
6. Add a per-type id-prefix conformance check driven by a declarative table.

Out of scope:

- **JSON-payload extractor (`extract_json_payload`)** from protein-landscape. Synthesis §9.1 correctly identifies this as a `science-tool` output-cleanliness bug, not a `validate.sh` change. File a follow-on `science-tool` task in `tasks/active.md` (see "Out-of-scope follow-ons" below).
- **Sanction `workflow/` as an execution root.** Depends on the deferred Bucket C `pipeline` profile-axis design (synthesis §11.2). Without that axis, blanket-allowing `workflow/` regresses the legacy-root warning for `research`-profile projects.
- Downstream `validate.sh` files are **not** updated by this plan. They update via `science-tool project artifacts update validate.sh --project-root .` once the canonical evolves and the MAV updater is installed.

---

## File Structure

Modify:

- `meta/validate.sh` — primary canonical artifact (the file MAV ships).
- `scripts/validate.sh` — repo-root canonical artifact (MAV's package data is sourced from here per the MAV plan's Task 5 sync test). Both files must move together.
- `science-tool/src/science_tool/project_artifacts/data/validate.sh` — packaged copy refreshed by the MAV plan's `cp` step; bumped here only by re-running that copy after `meta/validate.sh` and `scripts/validate.sh` change.
- `science-tool/src/science_tool/project_artifacts/artifacts.py` — bump `version="2026.04.25"` to a new date, append the previous `managed_content_hash` to `previous_hashes` so downstream projects on the prior managed version are reported as `OUTDATED` (not `LOCALLY_MODIFIED`).
- `science-tool/tests/test_project_artifacts.py` — add a regression test confirming the previous-hash transition is honored.

Create:

- `science-tool/tests/test_validate_script.py` — extend (or create alongside the existing test file) with focused script-behavior tests for the six changes.

Do not modify:

- Any downstream project's `validate.sh`. The MAV plan's update path is how those land.
- `science.yaml` schemas, profile/aspect docs, or entity-model artifacts. Those are §9.2 "drift not solvable by MAV" territory.

---

## Managed-version bookkeeping

Per the MAV plan's Task 3 Step 4 rule: before editing `meta/validate.sh`, capture `managed_content_hash(canonical_content)` of the current file, bump `ArtifactDefinition.version`, append the captured hash to `previous_hashes`. Without this, downstream projects on the prior managed version are reported as `LOCALLY_MODIFIED` instead of `OUTDATED`.

---

## Task 1: `LOCAL_PROFILE` parameterization — verify and tighten

**Files:**

- Modify: `meta/validate.sh`, `scripts/validate.sh`
- Test: `science-tool/tests/test_validate_script.py`

**Motivating evidence:**

- `natural-systems/validate.sh` (audit §8): renames `LOCAL_PROFILE="local"` to `LOCAL_PROFILE="project_specific"` and updates the introspection block (lines 87, 115–117 of canonical). natural-systems' `science.yaml` declares `knowledge_profiles: {local: project_specific, curated: []}`.
- mm30 §8: uses `knowledge_profiles: {local: local}` — works with the canonical hard-code coincidentally.
- cbioportal §8: byte-identical to canonical (also uses `local: local`).

**Status check.** Current canonical `meta/validate.sh` (lines 86–119) already reads `knowledge_profiles.local` via a Python introspection block. Hard-coded `"local"` survives only as a fallback when `science.yaml` is missing, `python3` is missing, or the YAML lookup throws. natural-systems' drift is therefore "canonical originally hardcoded `local`; natural-systems was patched before the canonical fix landed." Verify; if confirmed, the fix is to align natural-systems via MAV update.

- [ ] **Step 1: Audit canonical behavior** on a synthetic project with `knowledge_profiles.local: project_specific`. Expected: `LOCAL_PROFILE_DIR` resolves to `knowledge/sources/project_specific`. If it does, no further canonical change is needed.

- [ ] **Step 2: Add a regression test** `test_local_profile_reads_project_specific` that scaffolds a tmpdir project, invokes `validate.sh`, and asserts the Section 16 xref output references `knowledge/sources/project_specific/entities.yaml` rather than `.../local/entities.yaml`.

- [ ] **Step 3: If Step 1 surfaces edge cases** (empty-string value, non-ASCII slug), tighten the Python fallback so it fires only on missing-file/missing-python conditions — not on a present-but-oddly-parsed field.

---

## Task 2: Sanction `.env` sourcing canonically with an opt-out env var

**Files:**

- Modify: `meta/validate.sh`, `scripts/validate.sh`
- Test: `science-tool/tests/test_validate_script.py`

**Motivating evidence:**

- natural-systems §8: adds a `.env` sourcing block (lines 12–19) for `SCIENCE_TOOL_PATH`.
- mm30 §8: same — sources `.env` early and exits if `science-tool` is missing.
- protein-landscape §8: removes the `.env`-sourcing block; relies on the run environment to set `SCIENCE_TOOL_PATH`.
- cbioportal §8: byte-identical (works because `science-tool` is on `PATH` via `uv tool install`).

**Decision.** Sanction `.env` sourcing canonically, with an `SCIENCE_VALIDATE_SKIP_DOTENV=1` opt-out env var.

**Justification** over a `science.yaml` toggle:

1. The canonical file already sources `.env` (lines 12–19); 3/4 projects need it. The sanction recognizes the status quo, doesn't add to it.
2. An env-var opt-out is one bash line; a `science.yaml` toggle requires schema work, validator coverage, and per-project migration.
3. `.env` is a project-local environment concern. `science.yaml` is the portable manifest and shouldn't carry bootstrap toggles. protein-landscape's opt-out is exactly the env-var case: a developer with `SCIENCE_TOOL_PATH` already in the shell.

- [ ] **Step 1: Wrap the existing `.env` block** (lines 12–19) with `[ -z "${SCIENCE_VALIDATE_SKIP_DOTENV:-}" ] &&` so the entire sourcing block is skipped when the opt-out var is set.

- [ ] **Step 2: Document the opt-out** in the script header (one line under `Usage:`).

- [ ] **Step 3: Tests** — `.env` sourced when present and var unset; `.env` skipped when `SCIENCE_VALIDATE_SKIP_DOTENV=1`.

---

## Task 3: Replace `ontologies` list-shape check with `knowledge_profiles.curated`

**Files:**

- Modify: `meta/validate.sh`, `scripts/validate.sh`
- Test: `science-tool/tests/test_validate_script.py`

**Motivating evidence:**

- natural-systems §8: the project's diff against canonical "replaces the `ontologies` list-shape check (3 lines) with a `knowledge_profiles.curated` missing/list-shape check (5 lines)".
- natural-systems' `science.yaml`: `knowledge_profiles: {local: project_specific, curated: []}` — `curated` is the project-facing field; `ontologies` is the older flat list.

**Status check.** Canonical (lines 141–177) already validates `knowledge_profiles.local` (non-empty string) and `ontologies` (list when present). natural-systems' patch suggests the missing axis is `knowledge_profiles.curated`.

- [ ] **Step 1: Extend the embedded Python block** (lines 141–158) with a `knowledge_profiles.curated` list-shape check after the `local` check. Emit `invalid-curated` when type is wrong; missing is allowed.

- [ ] **Step 2: Keep the legacy `ontologies` list-shape check.** Three of four projects still carry the field; removing the check is a separate migration.

- [ ] **Step 3: Add the `invalid-curated` case** to the `case` statement (lines 161–177).

- [ ] **Step 4: Tests** for `curated: []`, `curated: [biology, chemistry]`, `curated: "not-a-list"` (warn/error), and missing-`curated` (no error).

---

## Task 4: Promote graph-audit unparseable output to `error`

**Files:**

- Modify: `meta/validate.sh`, `scripts/validate.sh`
- Test: `science-tool/tests/test_validate_script.py`

**Motivating evidence:**

- natural-systems §8: "the local copy treats unparseable graph-audit output as `warn` ('expected for fresh projects'); canonical treats it as `error`."
- mm30 §8: "mm30 elevates 'graph audit produced unparseable output' to `error`; canonical keeps it `warn`."
- Current canonical line 580: `warn "graph audit produced unparseable output (expected for fresh projects)"`.

The two projects independently arriving at the same hardening (`warn` → `error`) is the strongest cross-project signal in the audit for a one-line canonical change.

- [ ] **Step 1: Change line 580** from `warn` to `error`. Drop "(expected for fresh projects)" from the message — the deferred `science-tool` clean-stdout fix removes that condition once it lands.

- [ ] **Step 2: Verify the gate.** When `science-tool` is missing, `SCIENCE_TOOL` is empty and the entire block (line 553) is skipped — the new `error` cannot fire spuriously. Add a one-line comment near line 553.

- [ ] **Step 3: Test** that the error fires on unparseable stdout and the validator exits non-zero.

---

## Task 5: Sanction `docs/superpowers/` in the duplicate-doc-root warning

**Files:**

- Modify: `meta/validate.sh`, `scripts/validate.sh`
- Test: `science-tool/tests/test_validate_script.py`

**Motivating evidence:**

- protein-landscape §8: "Changed 'duplicate document roots' warning to suppress when `docs/` only contains `docs/superpowers/*` (`find docs -type f ! -path 'docs/superpowers/*' -print -quit`)".
- Synthesis §4.5: 3 of 4 projects (natural-systems, mm30, protein-landscape) carry the `docs/superpowers/{plans,specs}/` subtree.
- Current canonical lines 222–224: blanket warning when both `docs/` and `doc/` exist.

The agent-vs-human authoring split is legitimate specialization, not drift. Canonical should sanction it.

- [ ] **Step 1: Replace the warning block** (lines 222–224) with a `find docs -type f ! -path 'docs/superpowers/*' -print -quit` probe; warn only when extras exist outside the sanctioned subtree.

- [ ] **Step 2: Document the contract** in the script header — adding sanctioned subtrees requires a new plan (synthesis §4.5).

- [ ] **Step 3: Tests** — empty `docs/` (no warn); only `docs/superpowers/...` (no warn); `docs/extra.md` outside the sanctioned subtree (warn).

**Generalization note.** Hardcode the single path for now. A registry-based allow-list (in `science.yaml` or a `science-tool` constant) requires a separate design pass and only needs to land if a third agent-subtree appears.

---

## Task 6: Per-type id-prefix conformance check

**Files:**

- Modify: `meta/validate.sh`, `scripts/validate.sh`
- Test: `science-tool/tests/test_validate_script.py`

**Motivating evidence:**

- Synthesis §9.3 and §5.3: natural-systems' 26-of-31 `id: doc:DATE-slug` instead of `id: report:DATE-slug` would have been caught by a per-type id-prefix grammar rule.
- natural-systems §3 (Reports): "`id` prefix usage: 50 `plan:`, but inventory also surfaces 7 `vis:*` ids ... and 2 `interpretation:*` (test fixtures in `doc/plans/2026-04-08-claim-evidence-population-plan.md`)".
- mm30 §3: paper case-inconsistency (`paper:cohen2021` vs `paper:Walker2024`).
- protein-landscape §3: bare `question:q01..q22` vs slug `question:q23+`.

The pattern is "the `type:` field and the `id:` field must agree on the canonical prefix." A simple per-type table catches the most common drift.

- [ ] **Step 1: Add Section "17. Per-type id-prefix conformance"** before Section 16 (broken prefixes break xrefs).

- [ ] **Step 2: Implement as an embedded Python block** for parity with Section 16. Declarative table:

```python
PREFIX_RULES = {
    "hypothesis": "hypothesis:", "question": "question:", "paper": "paper:",
    "interpretation": "interpretation:", "report": "report:", "discussion": "discussion:",
    "plan": "plan:", "spec": "spec:", "topic": "topic:", "concept": "concept:",
    "dataset": "dataset:", "method": "method:", "synthesis": "synthesis:",
    "pre-registration": "pre-registration:",
}
```

Walk markdown under `$DOC_DIR/` and `$SPECS_DIR/`; if both `type:` and `id:` are present in frontmatter and `type:` is in the table, `id:` must start with the matching prefix. Emit **`warn`** (not `error`) — natural-systems' 26 violations would otherwise turn the validator red on first managed update and block adoption.

- [ ] **Step 3: Opt-out env var** `SCIENCE_VALIDATE_SKIP_ID_PREFIX=1` for projects mid-migration (natural-systems has an open task for report-id fixes).

- [ ] **Step 4: Tests** — matching `type`+`id` (no warn); `type: report` with `id: doc:...` (warn); `type: report` with no `id` (skip — Section 16 catches that); `templates/` (skip; reuse Section 16's exclusion).

- [ ] **Step 5: `pre-registration` dependency.** Synthesis §3.2 has type-promotion in flight. Until then projects use `type: plan` with `id: pre-registration:...`; the table's `plan` row catches the real `type:` value. Note this in a section comment.

---

## Out-of-scope follow-ons

1. **`science-tool` clean-stdout fix.** File in `tasks/active.md`: *"science-tool: emit clean JSON-only stdout from `graph audit/validate/diff` and `inquiry validate`. The `extract_json_payload` workaround in protein-landscape's local `validate.sh` exists because stdout/stderr noise leaks into JSON parsing."*
2. **`workflow/` execution-root sanction.** Hold for synthesis §11.2 profile-axis design; gate the Section 2 legacy-root check on `pipeline`-aspect presence once that lands.
3. **Sanctioned-subtree allow-list generalization** (Task 5). Promote to a registry only if a third agent-subtree appears.
4. **`pre-registration` first-class type** (synthesis §3.2). Task 6's prefix table activates the rule the moment that type promotion ships.

---

## Self-Review Checklist

- Plan only: no implementation, no commits.
- Bumps `ArtifactDefinition.version` and appends the previous hash to `previous_hashes` so MAV reports `OUTDATED`, not `LOCALLY_MODIFIED`, on adopters of the prior managed validator.
- All six fixes carry explicit line-range or block-level citations from §8 of the per-project audits.
- The two excluded items (JSON extractor, `workflow/`-root sanction) are routed to follow-ons.
- Downstream `validate.sh` files are not modified by this plan; they pull updates via `science-tool project artifacts update validate.sh`.
- Touches only `meta/validate.sh`, `scripts/validate.sh`, the packaged copy, the `ArtifactDefinition` registry, and tests.
