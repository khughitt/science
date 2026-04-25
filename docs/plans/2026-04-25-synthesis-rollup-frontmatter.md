# Synthesis-Rollup Frontmatter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bless `type: "synthesis"` + `report_kind` discriminator + per-kind structured frontmatter as the canonical Science synthesis-rollup shape, with template, command, agent, and validator support so any project's `science:big-picture` output is reproducible and machine-readable.

**Architecture:** Five small surfaces change. (1) New `templates/synthesis.md` carries the canonical frontmatter, with the `report_kind` enum and per-kind required-field list. (2) `commands/big-picture.md` Phase 2 dispatch and Phase 3 rollup write emit the canonical frontmatter (rollup currently emits bare `type: "synthesis-rollup"`, which collides). (3) `agents/hypothesis-synthesizer.md` and `agents/emergent-threads-synthesizer.md` gain explicit per-`report_kind` frontmatter specs. (4) `meta/validate.sh` and `scripts/validate.sh` gain a synthesis-file loop checking `type: synthesis` files carry `report_kind` (enum) plus the per-kind required fields, and is silent on legacy `type: report` files in the same paths. (5) `science-tool/tests/test_validate_script.py` adds tests covering each `report_kind` shape and the legacy-silence guarantee. No Python entity/schema changes — validator is the sole enforcement point, matching `2026-04-25-hypothesis-phase.md`.

**Tech Stack:** Bash (validate.sh), pytest + subprocess (validator tests), Markdown (template + command + agent files).

**Evidence (corrected from `synthesis.md` §3.3 deep-review pass).** Two of four downstream projects ship structured synthesis rollups, but with **different `type:` naming**:

- **mm30** uses `type: "report"` + `report_kind: "hypothesis-synthesis | synthesis-rollup | emergent-threads"` + `id: "report:synthesis-<slug>"`. `synthesized_from: [{hypothesis, file, sha}]` lives **only on the rollup** (`doc/reports/synthesis.md`); per-hypothesis and `_emergent-threads.md` do not carry it. Per-hypothesis files use `hypothesis: "hypothesis:<slug>"` instead. emergent-threads carries `orphan_ids: [...]`.
- **protein-landscape** uses `type: "synthesis"` on per-hypothesis files (`id: "synthesis:<slug>"`) and a separate `type: "emergent-threads"` on the threads file. No `synthesized_from:` field on any file. emergent-threads carries `orphan_question_count`, `orphan_interpretation_count`, `orphan_ids: [...]`.

Both ship the same *shape* (provenance-tracked frontmatter + per-hyp rollups + emergent-threads files), but with incompatible type-naming. Cited in `docs/audits/downstream-project-conventions/projects/{mm30,protein-landscape}.md` §3, §9 and `docs/audits/downstream-project-conventions/synthesis.md` §3.3.

**ID prefix:** `synthesis:<slug>` (matches protein-landscape and the upstream `agents/hypothesis-synthesizer.md` emitter at line 35). mm30's `report:synthesis-<slug>` is a legacy shape; migration is a follow-on.

**Type-naming choice (option B).** Canonize the cleaner `type: "synthesis"` form rather than mm30's `type: "report"` + `report_kind:` reuse. Justifications:

1. `type: synthesis` is more semantically meaningful than overloading `type: report` (mm30's `report` enum is also used by curation-sweeps and audits — synthesis blurs that line).
2. `agents/hypothesis-synthesizer.md` already emits `type: synthesis`; canonizing matches existing upstream code.
3. A single `type:` + `report_kind:` discriminator (rather than mm30's reuse-of-`report` or protein-landscape's split-into-two-types) is the cleanest graph shape.

**`report_kind` enum:** `hypothesis-synthesis | synthesis-rollup | emergent-threads`. **Excludes `curation-sweep`** — that is a separate canonical-promotion candidate (synthesis §6.3, P2 follow-on). Folding it here would conflate two distinct entity classes.

**`synthesized_from:` rule:** required only on `report_kind: synthesis-rollup` (the cross-hypothesis rollup is the natural carrier of sha-tracked source-of-truth links). Per-hypothesis files use `hypothesis:` instead; emergent-threads files use `orphan_ids:` and counts. This matches both projects' actual shipped shape and avoids false-positive warnings on per-hypothesis or threads files.

**Validator silence on legacy `type: report` synthesis files.** mm30's existing 5 per-hypothesis files + rollup + threads file all use `type: report`. The validator new-section logic gates on `type == synthesis`; mm30's files skip the entire new branch and produce no new warnings. This is **not** a permanent compatibility layer — it is the natural consequence of an additive type-conformance check. mm30 migration to `type: synthesis` is a follow-on (see Migration follow-ons below).

**Migration scope:** the upstream Science changes themselves require no in-repo migration. Two **downstream** migrations are flagged as follow-on tasks (not part of this plan): (a) mm30 rename `type: report` → `type: synthesis` + ids `report:synthesis-*` → `synthesis:*`; (b) protein-landscape rename `type: emergent-threads` → `type: synthesis` + `report_kind: emergent-threads`. See "Migration follow-ons" at the end of this plan.

---

## File Structure

Files modified:

- `templates/synthesis.md` — **new file**. Canonical template with per-`report_kind` frontmatter shape and a body skeleton matching `commands/big-picture.md` Phase 3.
- `commands/big-picture.md` — update Phase 3 frontmatter block (use `type: synthesis` + `report_kind: synthesis-rollup` instead of bare `type: "synthesis-rollup"`); add Phase 2 dispatch instructions naming the required `report_kind` per artifact and the per-kind required-fields list; add a Phase 3 contract note pointing to the template and validator.
- `agents/hypothesis-synthesizer.md` — add explicit `report_kind: "hypothesis-synthesis"` to the agent's "Output you produce" frontmatter block. Verify `id: "synthesis:<hyp-id>"` is already in place.
- `agents/emergent-threads-synthesizer.md` — add an explicit "Frontmatter" subsection to "Output you produce" with `id: "synthesis:emergent-threads"`, `type: "synthesis"`, `report_kind: "emergent-threads"`, `generated_at`, `source_commit`, `orphan_question_count`, `orphan_interpretation_count`. Cross-reference the existing `orphan_ids` scaling rule.
- `meta/validate.sh` — add section 11a ("Synthesis frontmatter conformance") between section 11 and section 12.
- `scripts/validate.sh` — mirror the section 11a change (the two scripts are kept in lockstep until managed-artifact-versioning unifies them; sha256 differs at audit time, so the insertion must be applied to both, located by content not absolute line number).
- `science-tool/tests/test_validate_script.py` — add seven tests covering accept-rollup-full / accept-hypothesis-synthesis / accept-emergent-threads / warn-on-rollup-missing-synthesized_from / warn-on-invalid-report_kind / no-warn-on-per-hyp-without-synthesized_from / no-warn-on-legacy-type-report.

No new directories. No file splits. No in-Science-repo migrations. Downstream migrations tracked separately (see Migration follow-ons).

---

## Task 1: Author the canonical synthesis template

**Files:**
- Create: `templates/synthesis.md`

The template documents the per-`report_kind` frontmatter shape and the enum.

- [x] **Step 1: List existing templates to confirm placement**

Run: `ls templates/` — confirm `synthesis.md` does not yet exist; note kebab-case single-word filenames.

- [x] **Step 2: Write `templates/synthesis.md`**

Frontmatter shape (presented as one canonical block with inline comments for the discriminating fields):

```yaml
---
id: "synthesis:{{slug}}"           # synthesis:<hyp-id> | synthesis:rollup | synthesis:emergent-threads
type: "synthesis"
report_kind: "{{kind}}"            # hypothesis-synthesis | synthesis-rollup | emergent-threads
generated_at: "{{ISO 8601}}"
source_commit: "{{40-char sha}}"

# Required only when report_kind == synthesis-rollup:
synthesized_from:                  # cross-hypothesis sha-tracked source-of-truth list
  - hypothesis: "hypothesis:<slug>"
    file: "specs/hypotheses/<slug>.md"
    sha: "{{40-char sha}}"
emergent_threads_sha: "{{40-char sha}}"   # rollup links to its companion threads file

# Required only when report_kind == hypothesis-synthesis:
hypothesis: "hypothesis:<slug>"
provenance_coverage: "{{full|partial|none}}"

# Required only when report_kind == emergent-threads:
orphan_question_count: 0
orphan_interpretation_count: 0
orphan_ids: []                     # full list per the scaling rule in the agent file

# Optional, all kinds:
phase: "active"
---
```

Body skeleton: HTML-comment scaffolds for `## TL;DR`, `## State`, `## Arc`, `## Research fronts`, `## Candidate frames`, `## Knowledge Gaps`, `## Emergent threads`, matching the Phase 3 rollup body. No filler — `science:big-picture` writes body procedurally.

- [x] **Step 3: Verify the template parses as YAML** — `python3 -c "import yaml; t=open('templates/synthesis.md').read(); fm=t.split('---',2)[1]; print(yaml.safe_load(fm))"`. Expected: dict with the top-level keys present (template comments may produce a partial parse; document accepted).

- [x] **Step 4: Commit** — `git commit -m "feat(templates): add canonical synthesis template with report_kind enum"`

---

## Task 2: Update `/science:big-picture` and synthesizer agents to emit the canonical frontmatter

**Files:**
- Modify: `commands/big-picture.md`
- Modify: `agents/hypothesis-synthesizer.md`
- Modify: `agents/emergent-threads-synthesizer.md`

`commands/big-picture.md` Phase 3 currently emits `type: "synthesis-rollup"` (around line 137), which collides with the canonical `type: synthesis` + `report_kind: synthesis-rollup`. The hypothesis-synthesizer agent already emits `id: "synthesis:<hyp-id>"` and `type: "synthesis"` but lacks an explicit `report_kind`. The emergent-threads agent's frontmatter is currently underspecified.

- [x] **Step 1: Update Phase 3 rollup frontmatter in `commands/big-picture.md`**

Find the YAML block under "Phase 3" → "Frontmatter:" (around line 137). Replace `type: "synthesis-rollup"` with three lines: `id: "synthesis:rollup"`, `type: "synthesis"`, `report_kind: "synthesis-rollup"`. Keep `generated_at`, `source_commit`, `synthesized_from`, `emergent_threads_sha` exactly as today.

- [x] **Step 2: Add a Phase 3 contract note**

Immediately before that YAML block, insert a paragraph: "The frontmatter follows the canonical synthesis shape documented in `templates/synthesis.md`. All three artifacts produced by this command (per-hypothesis files, `_emergent-threads.md`, and the project rollup) share `type: synthesis` and differ by `report_kind`. The validator (`meta/validate.sh` section 11a) warns when any `type: synthesis` file omits `report_kind`, and applies per-kind field requirements: `synthesis-rollup` must carry `synthesized_from`; `hypothesis-synthesis` must carry `hypothesis` and `provenance_coverage`; `emergent-threads` must carry `orphan_question_count`, `orphan_interpretation_count`, and `orphan_ids`."

- [x] **Step 3: Update Phase 2 dispatch prompt instructions**

In Phase 2's per-hypothesis dispatch bullets (around line 97), after "Target output path: `doc/reports/synthesis/<hyp-id>.md`." add: "Frontmatter: emit `type: synthesis` + `report_kind: hypothesis-synthesis` + `id: synthesis:<hyp-id>` + `hypothesis: hypothesis:<hyp-id>` + `generated_at` + `source_commit` + `provenance_coverage`. Do *not* emit `synthesized_from:` (the rollup carries that). See `agents/hypothesis-synthesizer.md` for the full output spec."

In the emergent-threads dispatch bullets (around line 119), after "Target output path: `doc/reports/synthesis/_emergent-threads.md`." add: "Frontmatter: emit `type: synthesis` + `report_kind: emergent-threads` + `id: synthesis:emergent-threads` + `generated_at` + `source_commit` + `orphan_question_count` + `orphan_interpretation_count` + `orphan_ids: [...]`. Do *not* emit `synthesized_from:` — emergent-threads is graph-derived, not file-derived."

- [x] **Step 4: Update `agents/hypothesis-synthesizer.md` output frontmatter**

In the "## Output you produce" YAML block, insert `report_kind: "hypothesis-synthesis"` between `type:` and `hypothesis:`. Verify the existing `id: "synthesis:<hyp-id>"` is in place. Do **not** add `synthesized_from:` — per-hypothesis files do not carry it.

- [x] **Step 5: Update `agents/emergent-threads-synthesizer.md` output frontmatter**

The agent currently does not show its own frontmatter block. Add a "### Frontmatter" subsection at the top of "## Output you produce" with:

```yaml
id: "synthesis:emergent-threads"
type: "synthesis"
report_kind: "emergent-threads"
generated_at: "{{ISO 8601}}"
source_commit: "{{40-char sha}}"
orphan_question_count: {{int}}
orphan_interpretation_count: {{int}}
orphan_ids:
  # See the existing 'Scaling for large orphan populations' subsection
```

Cross-reference the existing scaling subsection for `orphan_ids:`.

- [x] **Step 6: Verify section ordering** — `grep -n '^##\|^###' commands/big-picture.md`. Phase ordering unchanged.

- [x] **Step 7: Commit**

```bash
git add commands/big-picture.md agents/hypothesis-synthesizer.md agents/emergent-threads-synthesizer.md
git commit -m "feat(big-picture): emit canonical synthesis frontmatter (type+report_kind, per-kind required fields)"
```

---

## Task 3: Write failing tests for synthesis frontmatter validation

**Files:**
- Modify: `science-tool/tests/test_validate_script.py`

Tests follow the pattern from `2026-04-25-hypothesis-phase.md` Task 2: build a minimal research-profile project, drop synthesis files into `doc/reports/synthesis/`, run the validator, assert on warning output.

- [x] **Step 1: Read existing helper conventions**

`tail -120 science-tool/tests/test_validate_script.py` — confirm `_write_common_files`, `_write_python3_stub`, `_write_science_tool_stub`, `_validate_script_path`, `_validate_env`, and `_write_minimal_research_project` (if hypothesis-phase Task 2 has landed; otherwise inline-define). Reuse if available.

- [x] **Step 2: Add a `_synthesis_body(fields: dict[str, Any]) -> str` helper**

Composes a synthesis file from a frontmatter-fields dict (mapping handles strings, ints, and list values for `synthesized_from`/`orphan_ids`). Writes a YAML frontmatter block plus a one-line body so the file parses but has no real content.

- [x] **Step 3: Add seven tests**

1. `test_validate_accepts_synthesis_rollup_full` — full rollup at `doc/reports/synthesis.md` with `report_kind: synthesis-rollup` + `synthesized_from: [{...}]` + `source_commit:`. Assert no warning.
2. `test_validate_accepts_hypothesis_synthesis` — per-hypothesis file at `doc/reports/synthesis/h01-test.md` with `report_kind: hypothesis-synthesis` + `hypothesis:` + `provenance_coverage:` + `source_commit:`. **No `synthesized_from`.** Assert no warning.
3. `test_validate_accepts_emergent_threads` — `doc/reports/synthesis/_emergent-threads.md` with `report_kind: emergent-threads` + orphan counts + `orphan_ids: []` + `source_commit:`. **No `synthesized_from`.** Assert no warning.
4. `test_validate_warns_on_rollup_missing_synthesized_from` — rollup with `report_kind: synthesis-rollup` but no `synthesized_from:`. Assert "missing synthesized_from" warning.
5. `test_validate_warns_on_invalid_report_kind` — file with `report_kind: rollup` (typo). Assert "invalid report_kind" warning.
6. `test_validate_no_warn_on_per_hyp_without_synthesized_from` — same as test 2; locked-in regression test that per-hypothesis files do **not** require `synthesized_from`.
7. `test_validate_silent_on_legacy_type_report` — file at `doc/reports/synthesis/h1-legacy.md` with `type: report` + `report_kind: hypothesis-synthesis` (mm30's current shape). Assert no synthesis-section warning. **This is the legacy-silence guarantee.**

- [x] **Step 4: Run the tests to confirm they fail (red)**

```bash
cd science-tool && uv run --frozen pytest tests/test_validate_script.py -k "synthesis" -v
```
Expected: tests 4, 5 FAIL (rule not implemented yet); tests 1, 2, 3, 6, 7 PASS trivially (no rule, no warnings).

- [x] **Step 5: Commit the failing tests**

```bash
git add science-tool/tests/test_validate_script.py
git commit -m "test(validate): add tests for synthesis frontmatter rule (per-kind required fields, legacy-silence)"
```

---

## Task 4: Implement synthesis frontmatter validation in `meta/validate.sh` and `scripts/validate.sh`

**Files:**
- Modify: `meta/validate.sh`
- Modify: `scripts/validate.sh` (mirror change; both scripts must stay in lockstep until managed-artifact-versioning unifies them)

Add a new section ("11a. Synthesis frontmatter conformance") between section 11 (Discussion documents) and section 12 (Notes conformance). Iterate `doc/reports/synthesis/*.md` and `doc/reports/synthesis.md`, parse `type:` from frontmatter, gate on `type == synthesis`, then apply the per-`report_kind` field requirements. Warn (not error), matching the script's convention.

Apply the insertion to **both** `meta/validate.sh` and `scripts/validate.sh`. Locate by content (closing `done` of the bias-audit loop, then `# ─── 12. Notes conformance ───` header) rather than absolute line number; the two files have different line counts.

- [x] **Step 1: Read the existing section 11 and 12 boundaries in both files**

```bash
sed -n '407,478p' meta/validate.sh
sed -n '407,486p' scripts/validate.sh
```

- [x] **Step 2: Insert section 11a in `meta/validate.sh`**

Logic skeleton:

```bash
# ─── 11a. Synthesis frontmatter conformance ───
for f in "$DOC_DIR/reports/synthesis"/*.md "$DOC_DIR/reports/synthesis.md"; do
    [ -f "$f" ] || continue
    parsed_type=$(sed -n 's/^type:[[:space:]]*"\?\([^"]*\)"\?$/\1/p' "$f" | head -1)
    [ "$parsed_type" = "synthesis" ] || continue   # silent on legacy type:report and others
    parsed_kind=$(sed -n 's/^report_kind:[[:space:]]*"\?\([^"]*\)"\?$/\1/p' "$f" | head -1)
    case "$parsed_kind" in
        hypothesis-synthesis|synthesis-rollup|emergent-threads) ;;
        "") warn "$f: missing report_kind" ;;
        *)  warn "$f: invalid report_kind '$parsed_kind'" ;;
    esac
    grep -q "^source_commit:" "$f" || warn "$f: missing source_commit"
    case "$parsed_kind" in
        synthesis-rollup)
            grep -q "^synthesized_from:" "$f" || warn "$f: missing synthesized_from" ;;
        hypothesis-synthesis)
            grep -q "^hypothesis:" "$f" || warn "$f: missing hypothesis"
            grep -q "^provenance_coverage:" "$f" || warn "$f: missing provenance_coverage" ;;
        emergent-threads)
            grep -q "^orphan_question_count:" "$f" || warn "$f: missing orphan_question_count"
            grep -q "^orphan_interpretation_count:" "$f" || warn "$f: missing orphan_interpretation_count"
            grep -q "^orphan_ids:" "$f" || warn "$f: missing orphan_ids" ;;
    esac
done
```

Use the script's existing `warn()` helper. Match the test-asserted messages exactly.

- [x] **Step 3: Apply the same insertion to `scripts/validate.sh`** at the equivalent boundary (located by content).

- [x] **Step 4: Run synthesis tests (green)** — `cd science-tool && uv run --frozen pytest tests/test_validate_script.py -k "synthesis" -v`. Expected: all seven PASS.
- [x] **Step 5: Run the full validate-script test suite** — `uv run --frozen pytest tests/test_validate_script.py -v`. Expected: all pass.
- [x] **Step 6: Smoke-test against `meta/` and the repo root** — `cd meta && bash validate.sh 2>&1 | grep -i "synthesis" || echo "no synthesis warnings"`, then `bash scripts/validate.sh 2>&1 | grep -i "synthesis" || echo "no synthesis warnings"`. Expected: no warnings (neither has synthesis files).
- [x] **Step 7: Commit** — `git commit -m "feat(validate): warn on type:synthesis frontmatter missing per-kind required fields (silent on legacy type:report)"`

---

## Task 5: End-to-end verification

**Files:** None modified. Verification-only; no commit.

- [x] **Step 1: Run the full meta-project validator** — `cd meta && bash validate.sh --verbose 2>&1 | tail -40`. Expected: no new errors; synthesis section silent.
- [x] **Step 2: Run the full science-tool test suite** — `cd science-tool && uv run --frozen pytest -x`. Expected: all pass.
- [x] **Step 3: Spot-check downstream validator silence on legacy** — pick mm30 (`type: report` files in `doc/reports/synthesis/`) and run a synthetic validator invocation against a copy. Expected: no synthesis-section warnings (validator gates on `type: synthesis`). This confirms the legacy-silence guarantee in real conditions.
- [x] **Step 4: Verify template ↔ command ↔ agent agree** — `grep -E "^(id|type|report_kind|generated_at|source_commit|synthesized_from|hypothesis|provenance_coverage|orphan_question_count|orphan_interpretation_count|orphan_ids):" templates/synthesis.md` plus the analogous greps in `commands/big-picture.md` and the two agent files. Expected: consistent spelling and casing across all four files; per-kind required fields present where they should be.

---

## Migration follow-ons (NOT part of this plan)

The audit surfaces two downstream migrations. These are tracked separately and do **not** block plan #4 from merging:

1. **mm30:** rename `type: report` → `type: synthesis` and `id: report:synthesis-*` → `id: synthesis:*` across `doc/reports/synthesis/h{1..6}*.md`, `doc/reports/synthesis.md`, and `_emergent-threads.md`. The `report_kind` field stays. The `synthesized_from` field stays on the rollup. File a `[t<NNN>]` entry in mm30's `tasks/active.md` referencing this plan. Until migration, mm30's existing files validate cleanly (legacy-silence rule).
2. **protein-landscape:** rename `type: emergent-threads` → `type: synthesis` + add `report_kind: emergent-threads` on `doc/reports/synthesis/_emergent-threads.md`. Add `report_kind: hypothesis-synthesis` to existing `type: synthesis` per-hypothesis files. File a `[t<NNN>]` entry in protein-landscape's `tasks/active.md`.

Neither migration is part of this implementation plan. The audit's read-only constraint prohibits the orchestrator from making the migration; the project owner files the task.
