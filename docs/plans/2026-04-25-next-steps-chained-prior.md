# Chained-Prior Next-Steps Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bless `prior:` as the canonical chain field for `doc/meta/next-steps-YYYY-MM-DD.md` ledgers, ship a `templates/next-steps.md` template, teach `commands/next-steps.md` to auto-populate the field, and add a non-erroring broken-link check to `meta/validate.sh` — without migrating existing downstream files.

**Evidence (from `docs/audits/downstream-project-conventions/synthesis.md` §3.4):** 4/4 audited projects produce date-stamped `doc/meta/next-steps-YYYY-MM-DD.md`. Two chain explicitly: mm30 declares `mode: full, prior: doc/meta/next-steps-<earlier>.md` (per `projects/mm30.md` §4); protein-landscape declares `prior_analyses: [meta:next-steps-YYYY-MM-DD]` (per `projects/protein-landscape.md` §4). natural-systems and cbioportal produce the files without explicit chain fields. Field name varies; body shape is convergent.

**Architecture decisions:**

1. **Canonical field name:** `prior:` (single string). Rationale: a next-steps ledger is monotone in time — each file has at most one immediate predecessor — so `prior_analyses: [single-element-list]` is over-shaped for the actual relation. mm30's `prior:` is the simpler shape and matches `prior:` semantics already used elsewhere in Science (e.g., `prior:` in plan frontmatter would naturally extend the same field name). protein-landscape's `prior_analyses: [...]` is treated as an accepted variant — not erroring, not auto-emitted.
2. **Canonical entity type:** `type: meta`. Rationale: this is what protein-landscape already uses (per `projects/protein-landscape.md` §4: "10/11 have YAML frontmatter (`type: meta`, ...)"), it requires no new canonical type registration, and it composes with §6.3's "sanctioned project-local entity-kind extension" workstream (a project that wants `type: next-steps` can register it as a local typed extension). The `id:` shape is `meta:next-steps-YYYY-MM-DD`.
3. **`prior:` value shape:** entity-id reference (`meta:next-steps-YYYY-MM-DD`) preferred; relative path (`doc/meta/next-steps-YYYY-MM-DD.md`) accepted. The validator resolves both.
4. **Body shape:** unconstrained beyond what `commands/next-steps.md` already emits. Section 9 of `meta/validate.sh` (and `scripts/validate.sh`) already checks for required body sections; no new body rules.

**Tech Stack:** Markdown (template + command file), Bash (validate.sh chain-resolution check), pytest + subprocess (validator tests). No Python tool changes.

---

## File Structure

Files modified:

- `commands/next-steps.md` — extend "Setup" / "Mode Detection" / "Writing" sections so the skill (a) emits canonical frontmatter (`id`, `type: meta`, `created`, `prior`), and (b) auto-populates `prior:` by globbing `doc/meta/next-steps-*.md`, sorting by date in the filename, and selecting the most recent predecessor that pre-dates today's file at write time.
- `meta/validate.sh` — extend section 9 ("Research gap analysis conformance") with a new sub-check: for each `doc/meta/next-steps-*.md` carrying `prior:`, resolve the referenced file/id and `warn` (not error) if missing. Skip silently when `prior:` is absent. Treat `prior_analyses:` as an accepted-variant — present-and-resolvable is fine; do not warn on the field name itself.
- `scripts/validate.sh` — same change as `meta/validate.sh` (the two scripts are kept in lockstep for now; managed-artifact-versioning is the longer-term plan).
- `science-tool/tests/test_validate_script.py` — add tests for the new chain-resolution check (resolvable id, resolvable path, broken link warns, absent field is silent, accepted-variant `prior_analyses:` does not warn).

Files created:

- `templates/next-steps.md` — new template, frontmatter-only with placeholder body sections matching `commands/next-steps.md`'s "Writing" block.

No file splits, no migrations of existing downstream files. Tight scope.

---

## Task 1: Add `templates/next-steps.md`

**Files:**
- Create: `templates/next-steps.md`

The template establishes the canonical frontmatter. The body sections mirror `commands/next-steps.md` Writing block so a hand-edited next-steps file matches what the skill emits.

- [ ] **Step 1: Inspect a peer template** (e.g., `templates/finding.md`, `templates/discussion.md`) to mirror frontmatter conventions (`id`, `type`, `title`, `created`, `updated`, `related: []`).

- [ ] **Step 2: Write the template.** Frontmatter:

  ```yaml
  ---
  id: "meta:next-steps-YYYY-MM-DD"
  type: "meta"
  title: "Next Steps — YYYY-MM-DD"
  created: "YYYY-MM-DD"
  updated: "YYYY-MM-DD"
  prior: "meta:next-steps-YYYY-MM-DD"  # entity id of immediate predecessor; omit for first-ever file
  related: []
  ---
  ```

  Body: H1 title plus the section headings the validator already enforces (`Recent Progress`, `Current State`, `Coverage Gaps`, `Recommended Next Actions`), each empty under an HTML comment instructing the author to populate via `/science:next-steps`.

- [ ] **Step 3: Verify frontmatter parses as YAML** with `python3 -c "import yaml; ..."`.

---

## Task 2: Update `commands/next-steps.md` to emit canonical frontmatter and auto-populate `prior:`

**Files:**
- Modify: `commands/next-steps.md`

Current behavior: the "Writing" section shows a body-only template with no frontmatter. Change: prepend a frontmatter block, and add a "Resolve `prior:`" sub-step before writing.

- [ ] **Step 1:** In the "Writing" section's fenced markdown block (currently starts with `# Next Steps — YYYY-MM-DD`), insert the canonical frontmatter (per Task 1 shape) above the H1.

- [ ] **Step 2:** Add a new "Resolve prior link" subsection under "## After Writing" (or before "Save to ..." in step 1). The selection rule is **load-bearing for delta-mode semantics** (delta-mode appends to today's file rather than creating a new one, so the predecessor must be the most recent file *strictly before* today, not today itself):

  > Before writing, list `doc/meta/next-steps-*.md`. **Exclude any file dated today** (delta-mode appends to that file rather than creating a new one). From the remaining files, select the one with the lexically-greatest `YYYY-MM-DD` in its filename. Set `prior: meta:next-steps-<that-date>` in the new file's frontmatter. If no predecessor exists (this is the first next-steps file in the project), omit the `prior:` field entirely.

- [ ] **Step 3:** In "Mode Detection", clarify that delta-mode (append `## Update — HH:MM`) does not change the file's `prior:` — the chain link is per-file, not per-update.

- [ ] **Step 4:** Add one sentence noting that projects which currently use `prior_analyses:` (protein-landscape) need not migrate; the validator accepts both.

---

## Task 3: Write failing tests for the chain-resolution validator check

**Files:**
- Modify: `science-tool/tests/test_validate_script.py`

Tests use the existing `_write_common_files` / `subprocess.run` fixture pattern. Each test sets up a minimal project, drops one or more `doc/meta/next-steps-*.md` files with crafted `prior:` values, runs the validator, and asserts on the warning output.

- [ ] **Step 1:** Add a `_write_next_steps_file(root, date, prior=None, body_sections=...)` helper that emits a frontmatter-bearing file with the four required body sections (so unrelated section-9 checks pass).

- [ ] **Step 2:** Add six tests:

  - `test_validate_resolves_prior_by_entity_id` — two files; later one's `prior: meta:next-steps-<earlier>`. Expect no `broken prior link` warning.
  - `test_validate_resolves_prior_by_path` — `prior: doc/meta/next-steps-<earlier>.md`. Expect no warning.
  - `test_validate_warns_on_broken_prior_link` — file references `meta:next-steps-2025-01-01` that does not exist. Expect a warning containing `broken prior link` and the bad reference.
  - `test_validate_silent_when_prior_absent` — single file with no `prior:`. Expect no warning, no error.
  - `test_validate_accepts_prior_analyses_variant_inline` — file uses inline-list shape `prior_analyses: [meta:next-steps-<earlier>]` (synthetic shape for completeness) referencing an existing file. Expect no `broken prior link` warning.
  - `test_validate_accepts_prior_analyses_variant_block_list` — file uses YAML block-list shape (the form protein-landscape actually ships in `doc/meta/next-steps-2026-04-19.md`):
    ```yaml
    prior_analyses:
      - "meta:next-steps-2026-04-12"
    ```
    Expect no `broken prior link` warning. **This is the load-bearing test** — the shape protein-landscape actually uses in production. **(Clarification: out-of-scope for this plan to require `prior_analyses:` resolution; the test asserts the validator does not error on the field name alone. Resolving the variant's targets is a future cycle.)**

- [ ] **Step 3:** Run the new tests and confirm `test_validate_warns_on_broken_prior_link` fails (the check does not yet exist), the others pass trivially today.

---

## Task 4: Implement the chain-resolution check in `meta/validate.sh` and `scripts/validate.sh`

**Files:**
- Modify: `meta/validate.sh:374-393` (section 9)
- Modify: `scripts/validate.sh:382-393` (mirror change; both scripts must stay in lockstep until the managed-artifact-versioning plan unifies them)

- [ ] **Step 1:** Inside the existing `for f in "$DOC_DIR/meta/next-steps-"*.md; do` loop, after the section-presence check, add:

  ```bash
  # Chain link resolution. Accept entity-id (meta:next-steps-YYYY-MM-DD)
  # or relative path (doc/meta/next-steps-YYYY-MM-DD.md). Absence is fine.
  prior_value=$(sed -n "s/^prior:[[:space:]]*['\"]\\{0,1\\}\\([^'\"]*\\)['\"]\\{0,1\\}[[:space:]]*$/\\1/p" "$f" | head -n 1 || true)
  if [ -n "$prior_value" ]; then
      # Strip optional meta: prefix and resolve to a path
      candidate_path=""
      case "$prior_value" in
          meta:next-steps-*) candidate_path="$DOC_DIR/meta/${prior_value#meta:}.md" ;;
          *.md) candidate_path="$prior_value" ;;
          *) candidate_path="$prior_value" ;;
      esac
      if [ ! -f "$candidate_path" ]; then
          warn "${f}: broken prior link '${prior_value}' (resolved to ${candidate_path})"
      fi
  fi
  ```

- [ ] **Step 2:** Run the test suite from Task 3; confirm all six tests pass.

- [ ] **Step 3:** Run `bash meta/validate.sh --verbose` and `bash scripts/validate.sh --verbose` from the repo root. Confirm no new warnings (the meta-project has no next-steps files yet; the repo root has none either).

- [ ] **Step 4:** Verify the change does **not** error or warn on `prior_analyses:` field-name presence — it simply does not parse it (consistent with the Task 3 accepted-variant test). Mention this explicitly in a comment above the new block.

---

## Task 5: End-to-end verification

**Files:** none modified.

- [ ] **Step 1:** Run `cd science-tool && uv run --frozen pytest tests/test_validate_script.py -v` — expect all tests pass (existing + six new).

- [ ] **Step 2:** Run `bash meta/validate.sh --verbose` and `bash scripts/validate.sh --verbose`. Bottom-line summary should be unchanged from a pre-change baseline modulo informational lines.

- [ ] **Step 3:** Manually exercise `commands/next-steps.md` against the meta-project: skill emits a file with frontmatter, no `prior:` field (since none exist yet). Re-run a day later (or simulate by creating two files with different dates) and verify the second file's `prior:` resolves to the first.

- [ ] **Step 4:** Confirm no migration of downstream projects. mm30, protein-landscape, natural-systems, cbioportal are untouched. Their migration is a separate cycle.

- [ ] **Step 5:** No commit (verification only).
