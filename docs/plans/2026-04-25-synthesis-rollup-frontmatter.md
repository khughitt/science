# Synthesis-Rollup Frontmatter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bless the synthesis-rollup frontmatter shape (`type: synthesis` + `report_kind` enum + SHA-tracked `synthesized_from[]` + `source_commit` + `generated_at`) as canonical Science, with template, command, agent, and validator support so any project's `science:big-picture` output is reproducible and machine-readable.

**Architecture:** Five small surfaces change. (1) New `templates/synthesis.md` carries the canonical frontmatter. (2) `commands/big-picture.md` Phase 2 dispatch and Phase 3 rollup write emit the canonical frontmatter (rollup currently emits bare `type: "synthesis-rollup"`, which collides). (3) `agents/hypothesis-synthesizer.md` and `agents/emergent-threads-synthesizer.md` gain explicit `report_kind` and SHA-tracked `synthesized_from` fields. (4) `meta/validate.sh` gains a synthesis-file loop checking `type: synthesis` files carry `report_kind` (enum), `source_commit`, and `synthesized_from`. (5) `science-tool/tests/test_validate_script.py` adds tests. No Python entity/schema changes — validator is the sole enforcement point, matching `2026-04-25-hypothesis-phase.md`.

**Tech Stack:** Bash (validate.sh), pytest + subprocess (validator tests), Markdown (template + command + agent files).

**Evidence:** mm30 ships the full shape at `doc/reports/synthesis/h{1..6}*.md`, `doc/reports/synthesis.md`, and `doc/reports/synthesis/_emergent-threads.md` with `report_kind: hypothesis-synthesis | synthesis-rollup | curation-sweep`, `source_commit`, `synthesized_from: [{hypothesis, file, sha}]`, `emergent_threads_sha`, `orphan_question_count`, `provenance_coverage` (`docs/audits/downstream-project-conventions/projects/mm30.md` §3, §9). protein-landscape replicates at `doc/reports/synthesis/{_emergent-threads.md, h0[1-3]-*.md}` with `source_commit`, `provenance_coverage`, `orphan_question_count`, `orphan_interpretation_count`, `orphan_ids: [...]` (`docs/audits/downstream-project-conventions/projects/protein-landscape.md` §3, §9). P1 #4 in `docs/audits/downstream-project-conventions/synthesis.md` §3.3.

**ID prefix:** `synthesis:<slug>` (not `report:`). `agents/hypothesis-synthesizer.md` already emits `id: "synthesis:<hyp-id>"`; mm30/protein-landscape per-hypothesis files use the same form. `report:` is overloaded across projects (`synthesis.md` §5.3). Project-local `report:` ids remain orthogonal.

**Migration scope:** None. mm30 and protein-landscape already produce the shape; cbioportal's outlier and natural-systems' partial syntheses are out of scope.

---

## File Structure

Files modified:

- `templates/synthesis.md` — **new file**. Canonical template with the blessed frontmatter shape and a body skeleton matching `commands/big-picture.md` Phase 3.
- `commands/big-picture.md` — update Phase 3 frontmatter block (use `type: synthesis` + `report_kind: synthesis-rollup` instead of bare `type: "synthesis-rollup"`); add Phase 2 dispatch instructions naming the required `report_kind` per artifact; add a Phase 3 contract note pointing to the template and validator.
- `agents/hypothesis-synthesizer.md` — add `report_kind: "hypothesis-synthesis"` and `synthesized_from: [{...}]` to the agent's "Output you produce" frontmatter block.
- `agents/emergent-threads-synthesizer.md` — add an explicit frontmatter spec with `id`, `type: synthesis`, `report_kind: emergent-threads`, `generated_at`, `source_commit`, `synthesized_from: []`, and the orphan counts. Keep the existing `orphan_ids:` scaling rule verbatim.
- `meta/validate.sh` — add section 11a ("Synthesis frontmatter conformance") between section 11 and section 12.
- `scripts/validate.sh` — mirror the section 11a change (the two scripts are kept in lockstep until managed-artifact-versioning unifies them; sha256 differs at audit time, so this insertion must be applied to both).
- `science-tool/tests/test_validate_script.py` — add five tests covering accept-full / warn-on-missing-source_commit / warn-on-missing-synthesized_from / warn-on-invalid-report_kind / no-false-positive-on-non-synthesis-reports.

No new directories. No file splits. No downstream-project migrations.

---

## Task 1: Author the canonical synthesis template

**Files:**
- Create: `templates/synthesis.md`

The template documents the full frontmatter shape and the `report_kind` enum.

- [ ] **Step 1: List existing templates to confirm placement**

Run: `ls templates/` — confirm `synthesis.md` does not yet exist; note kebab-case single-word filenames.

- [ ] **Step 2: Write `templates/synthesis.md`**

Frontmatter fields with placeholders: `id: "synthesis:{{slug}}"` (e.g. `synthesis:h01-...`, `synthesis:rollup`, `synthesis:emergent-threads`); `type: "synthesis"`; `report_kind: "{{hypothesis-synthesis | synthesis-rollup | emergent-threads | curation-sweep}}"` with inline-comment semantics; `generated_at`; `source_commit`; `synthesized_from:` array of `{hypothesis, file, sha}` triples (one per hypothesis for `synthesis-rollup`; one self-entry for `hypothesis-synthesis`; empty `[]` for `emergent-threads` and `curation-sweep`); optional `provenance_coverage` (required for `hypothesis-synthesis`); optional `orphan_question_count` / `orphan_interpretation_count` / `orphan_ids: []` (emergent-threads scaling rule); optional `emergent_threads_sha` (rollup only).

Body skeleton: HTML-comment scaffolds for `## TL;DR`, `## State`, `## Arc`, `## Research fronts`, `## Candidate frames`, `## Knowledge Gaps`, `## Emergent threads`, matching the Phase 3 rollup body. No filler — `science:big-picture` writes body procedurally.

- [ ] **Step 3: Verify the template parses as YAML** — `python3 -c "import yaml; t=open('templates/synthesis.md').read(); fm=t.split('---',2)[1]; print(yaml.safe_load(fm))"`. Expected: dict with all top-level keys present.

- [ ] **Step 4: Commit** — `git commit -m "feat(templates): add canonical synthesis template with report_kind enum"`

---

## Task 2: Update `/science:big-picture` and synthesizer agents to emit the canonical frontmatter

**Files:**
- Modify: `commands/big-picture.md`
- Modify: `agents/hypothesis-synthesizer.md`
- Modify: `agents/emergent-threads-synthesizer.md`

`commands/big-picture.md` Phase 3 currently emits `type: "synthesis-rollup"` for the rollup, which conflicts with the canonical (`type: synthesis` + `report_kind: synthesis-rollup`). The hypothesis-synthesizer agent emits `id: synthesis:<id>` and `type: synthesis` but lacks `report_kind` and `synthesized_from`. The emergent-threads agent's frontmatter is currently underspecified.

- [ ] **Step 1: Update Phase 3 rollup frontmatter in `commands/big-picture.md`**

Find the YAML block under "Phase 3" → "Frontmatter:" (around line 137). Replace `type: "synthesis-rollup"` with three lines: `id: "synthesis:rollup"`, `type: "synthesis"`, `report_kind: "synthesis-rollup"`. Keep `generated_at`, `source_commit`, `synthesized_from`, `emergent_threads_sha`, `orphan_question_count` exactly as today.

- [ ] **Step 2: Add a Phase 3 contract note**

Immediately before that YAML block, insert a paragraph: "The frontmatter follows the canonical synthesis shape documented in `templates/synthesis.md`. All four artifacts produced by this command (per-hypothesis files, `_emergent-threads.md`, and the project rollup) share `type: synthesis` and differ only by `report_kind`. The validator at `meta/validate.sh` warns when any `type: synthesis` file omits `report_kind`, `source_commit`, or `synthesized_from` (an empty list is acceptable for `emergent-threads` and `curation-sweep`)."

- [ ] **Step 3: Update Phase 2 dispatch prompt instructions**

In Phase 2's per-hypothesis dispatch bullets (around line 97), after "Target output path: `doc/reports/synthesis/<hyp-id>.md`." add a bullet naming the required frontmatter contract for `report_kind: hypothesis-synthesis` and the `synthesized_from: [{hypothesis, file, sha}]` triple, pointing to `agents/hypothesis-synthesizer.md` for the full shape.

In the emergent-threads dispatch bullets (around line 119), after "Target output path: `doc/reports/synthesis/_emergent-threads.md`." add a bullet naming `report_kind: emergent-threads` and `synthesized_from: []` (emergent-threads is graph-derived, not file-derived; provenance is in `source_commit`).

- [ ] **Step 4: Update `agents/hypothesis-synthesizer.md` output frontmatter**

In the "## Output you produce" YAML block (around lines 33-42), insert `report_kind: "hypothesis-synthesis"` between `type:` and `hypothesis:`, and add a `synthesized_from:` block immediately after `source_commit:` with the single triple `{hypothesis: "hypothesis:<hyp-id>", file: "specs/hypotheses/<hyp-id>.md", sha: "<sha provided by dispatcher>"}`.

- [ ] **Step 5: Update `agents/emergent-threads-synthesizer.md` output frontmatter**

The agent currently does not show its own frontmatter block. Add a "### Frontmatter" subsection at the top of "## Output you produce" with: `id: "synthesis:emergent-threads"`, `type: "synthesis"`, `report_kind: "emergent-threads"`, `generated_at`, `source_commit`, `synthesized_from: []`, `orphan_question_count`, `orphan_interpretation_count`. Cross-reference the existing "Scaling for large orphan populations" subsection for `orphan_ids:` — do not duplicate that text.

- [ ] **Step 6: Verify section ordering**

```bash
grep -n '^##\|^###' commands/big-picture.md
```
Expected: phase ordering unchanged (Phase 1 → Phase 2 → Phase 3 → Phase 4 → Staleness check → --since handling → Output to user).

- [ ] **Step 7: Commit**

```bash
git add commands/big-picture.md agents/hypothesis-synthesizer.md agents/emergent-threads-synthesizer.md
git commit -m "feat(big-picture): emit canonical synthesis frontmatter (type+report_kind+synthesized_from)"
```

---

## Task 3: Write failing tests for synthesis frontmatter validation

**Files:**
- Modify: `science-tool/tests/test_validate_script.py`

Tests follow the pattern from `2026-04-25-hypothesis-phase.md` Task 2: build a minimal research-profile project, drop synthesis files into `doc/reports/synthesis/`, run the validator, assert on warning output.

- [ ] **Step 1: Read existing helper conventions**

`tail -120 science-tool/tests/test_validate_script.py` — confirm `_write_common_files`, `_write_python3_stub`, `_write_science_tool_stub`, `_validate_script_path`, `_validate_env`, and `_write_minimal_research_project` (if hypothesis-phase Task 2 has landed; otherwise inline-define). Reuse if available.

- [ ] **Step 2: Add a `_synthesis_body(fields: dict[str, str]) -> str` helper**

Composes a synthesis file from a frontmatter-fields dict. Writes a YAML frontmatter block plus a one-line body so the file parses but has no real content.

- [ ] **Step 3: Add five tests**

1. `test_validate_accepts_synthesis_with_full_frontmatter` — full frontmatter at `doc/reports/synthesis/h01-test.md`. Assert no synthesis warning.
2. `test_validate_warns_on_synthesis_missing_source_commit` — omit `source_commit`. Assert "missing source_commit" warning.
3. `test_validate_warns_on_synthesis_missing_synthesized_from` — omit `synthesized_from`. Assert "missing synthesized_from" warning.
4. `test_validate_warns_on_synthesis_invalid_report_kind` — `report_kind: rollup`. Assert "invalid report_kind" warning.
5. `test_validate_ignores_non_synthesis_reports` — `doc/reports/2026-04-20-some-other-report.md` with `type: report`. Assert no synthesis warning (no false positive on broader `doc/reports/`).

- [ ] **Step 4: Run the tests to confirm they fail (red)**

```bash
cd science-tool && uv run --frozen pytest tests/test_validate_script.py -k "synthesis" -v
```
Expected: tests 2, 3, 4 FAIL; tests 1 and 5 PASS trivially.

- [ ] **Step 5: Commit the failing tests**

```bash
git add science-tool/tests/test_validate_script.py
git commit -m "test(validate): add tests for synthesis frontmatter rule"
```

---

## Task 4: Implement synthesis frontmatter validation in `meta/validate.sh` and `scripts/validate.sh`

**Files:**
- Modify: `meta/validate.sh`
- Modify: `scripts/validate.sh` (mirror change; both scripts must stay in lockstep until managed-artifact-versioning unifies them)

Add a new section ("11a. Synthesis frontmatter conformance") between section 11 (Discussion documents) and section 12 (Notes conformance). Iterate `doc/reports/synthesis/*.md` and `doc/reports/synthesis.md`, parse `type:` using the same `sed` pattern as line 530 (`parsed_type`). Warn (not error), matching the script's overall convention.

Apply the insertion to **both** `meta/validate.sh` and `scripts/validate.sh`. Their section-11/12 boundaries are at slightly different line numbers; locate by content (closing `done` of the bias-audit loop, then the `# ─── 12. Notes conformance ───` header) rather than absolute line.

- [ ] **Step 1: Read the existing section 11 and 12 boundaries**

`sed -n '407,478p' meta/validate.sh` — locate the closing `done` of the bias-audit loop (around line 475) and the start of section 12.

- [ ] **Step 2: Insert section 11a**

After the bias-audit `done` and before `# ─── 12. Notes conformance ───`: (1) glob `$DOC_DIR/reports/synthesis/*.md` and `$DOC_DIR/reports/synthesis.md`, skip if neither exists; (2) parse `type:` from frontmatter for each; (3) if `type == synthesis`, parse `report_kind` and check presence of `source_commit:` and `synthesized_from:` via `grep -q`; (4) warn when `report_kind` is missing or not in `{hypothesis-synthesis, synthesis-rollup, emergent-threads, curation-sweep}`, when `source_commit` is missing, or when `synthesized_from` is missing (presence-only — empty `[]` is acceptable for `emergent-threads` and `curation-sweep`). Warning messages match test assertions: "missing source_commit", "missing synthesized_from", "invalid report_kind '<value>'".

- [ ] **Step 3: Run synthesis tests (green)** — `cd science-tool && uv run --frozen pytest tests/test_validate_script.py -k "synthesis" -v`. Expected: all five PASS.
- [ ] **Step 4: Run the full validate-script test suite** — `uv run --frozen pytest tests/test_validate_script.py -v`. Expected: all pass.
- [ ] **Step 5: Smoke-test against `meta/` and the repo root** — `cd meta && bash validate.sh 2>&1 | grep -i "synthesis" || echo "no synthesis warnings"`, then `bash scripts/validate.sh 2>&1 | grep -i "synthesis" || echo "no synthesis warnings"`. Expected: no warnings from either invocation.
- [ ] **Step 6: Commit** — `git commit -m "feat(validate): warn on synthesis frontmatter missing report_kind/source_commit/synthesized_from"`

---

## Task 5: End-to-end verification

**Files:** None modified. Verification-only; no commit.

- [ ] **Step 1: Run the full meta-project validator** — `cd meta && bash validate.sh --verbose 2>&1 | tail -40`. Expected: no new errors; synthesis section silent (meta has no synthesis files).
- [ ] **Step 2: Run the full science-tool test suite** — `cd science-tool && uv run --frozen pytest -x`. Expected: all pass.
- [ ] **Step 3: Spot-check downstream synthesis files** if available: `grep -L "^report_kind:" /home/keith/d/r/mm30/doc/reports/synthesis/*.md` and same for `^source_commit:`. Expected: empty output (mm30 already declares both — the evidence motivating the canonical shape). Anything surfacing is documentation only; no migration here.
- [ ] **Step 4: Verify template ↔ command ↔ agent agree** — `grep -E "^(id|type|report_kind|generated_at|source_commit|synthesized_from):" templates/synthesis.md` plus the analogous greps in `commands/big-picture.md` and the two agent files. Expected: consistent spelling and casing across all four files.
