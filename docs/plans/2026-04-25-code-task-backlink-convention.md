# Code/Notebook → Task Back-Link Convention Plan

**Goal:** document a sanctioned set of code → task linkage patterns, framed as guidance, not as a validator-enforced requirement.

**Context:** addresses P1 #9 from the downstream conventions audit synthesis (`docs/audits/downstream-project-conventions/synthesis.md` §6.4 brief; §8.2 in full). All four audited projects show weak code-side linkage to tasks/questions/hypotheses (forward direction `entity → code` is fine in plan/interpretation prose; reverse direction is filename-dependent at best). The synthesis is explicit: case-by-case rather than universal sidecar.

**Scope:** documentation only. No validator rules. No `science-tool` commands. No mandatory adoption.

---

## Evidence (from the audit)

Four patterns observed in the wild, each fit-for-purpose at one or more projects:

1. **Filename tag** — cbioportal's `code/notebooks/{q011_length_adjustment_topn_comparison.py, t070_poc_comparison.py, t131_three_way_ranking_comparison.py}` (`docs/audits/downstream-project-conventions/projects/cbioportal.md` §6). Three task-tagged marimo notebooks; the prefix is the entire convention.
2. **Comment-block header** — implied by the audit's recommendation (`synthesis.md` §8.2: "a `# task: tNNN` comment-block convention is sufficient"). Used informally in cbioportal docstrings; not a uniform shape today.
3. **Descriptor sidecar field** — protein-landscape's 19 `descriptors/<artifact>.parquet.descriptor.json` files (`docs/audits/downstream-project-conventions/projects/protein-landscape.md` §6, §9 / §7) carry `git_commit, command, parameters, inputs[{path, sha256}], outputs[{path, sha256, row_count}]` — but no `task:` / `question:` field. Closing that gap is the most valuable addition for artifact-producing scripts.
4. **Commit-message tag** — cbioportal and protein-landscape both use Conventional-Commits-style task tags in commit subjects (`fix(t131): thread random_seed`, `feat(t128): retroactive datapackage manifests`). Documented in synthesis §8.2 as one of the three real observed patterns; both projects already enforce shape via `commitlint.config.mjs` + `.husky/commit-msg`.

Two further projects confirm the same gap without yet shipping a fix:

- **mm30** (`docs/audits/downstream-project-conventions/projects/mm30.md` §6): "weak — a few `scripts/hypotheses/h*` directory names align with hypothesis IDs; otherwise code does not declare which task/hypothesis it implements." Suggests `scripts/hypotheses/<h>/manifest.yaml` could carry `produces:` / `consumes:`.
- **natural-systems** (`docs/audits/downstream-project-conventions/projects/natural-systems.md` §6): "weak from code → entities. Reverse direction is well-populated; code files do not carry sidecar metadata or in-source provenance frontmatter."

---

## File Structure

Files modified (no code, no new files in `templates/`, `scripts/`, or `science-tool/`):

- `docs/project-organization-profiles.md` — add a new section "Code → task back-link" near the existing "Research Analysis Naming" section.
- `docs/conventions/README.md` — *new*, ~10-15 line scope doc establishing `docs/conventions/` as the home for cross-cutting convention references (one short doc per recurring pattern, written for both human readers and adopting agents). Sets the bar so the directory does not become a graveyard of one-off files.
- `docs/conventions/code-task-backlinks.md` — *new*, ~50-75 line reference doc. Holds the four sanctioned patterns and the descriptor optional-field list. Cross-linked from `project-organization-profiles.md` and `docs/conventions/README.md`.

**Justification for new `docs/conventions/` directory.** `docs/` already has `process/`, `specs/`, `audits/`, `plans/`, `templates/`. A `conventions/` sibling fills a real gap: cross-cutting reference docs that don't fit the other categories — too short and reference-shaped to be a `plan`, too generally-applicable to be a `spec`, too prescriptive to be a `process` doc. Other recurring conventions surfaced by the audit (datapackage extension shape from Bucket C, status-enum schema, multi-axis profile axis labels) will land here too once their design passes complete. The seed `README.md` makes the directory's scope explicit.

No CLAUDE.md/AGENTS.md exists at the Science repo root today; nothing to modify there. Downstream projects' CLAUDE.md/AGENTS.md are out of scope (they will pick up the convention by reference if they choose to adopt it).

---

## Task 1: Seed `docs/conventions/` with a scope README

**Files:** Create: `docs/conventions/README.md`.

Short scoping doc (~10-15 lines). Content:

- One-line statement: this directory holds cross-cutting convention references — short, prescriptive docs describing recurring shapes that aren't a fit for `plans/`, `specs/`, or `process/`.
- Bar for entries: each doc should describe a pattern observed in two or more downstream projects (or a deliberately-promoted single-project pattern with a clear cross-project rationale), be self-contained, and be linkable from `docs/project-organization-profiles.md`.
- A short index pointing at the first entry: `code-task-backlinks.md`. New entries (datapackage extension, status-enum schema, multi-axis profile axis labels) will be appended as their design passes complete.

Acceptance: README exists; index lists `code-task-backlinks.md`; renders cleanly.

---

## Task 2: Write the convention reference doc

**Files:** Create: `docs/conventions/code-task-backlinks.md`.

Single page. Sections:

1. **Status callout.** A one-line note at the top: "Pattern 3 (descriptor sidecar field) names optional fields whose canonical schema is pending Bucket C / P1 #8 (datapackage `<project>:` extension profile). Field names below are stable; if Bucket C namespaces them, this doc updates in lockstep."
2. **When to use which pattern** — one short paragraph, then a table mapping artifact shape → recommended pattern:
   - Notebook (Jupyter/marimo, 1-10 per project) → filename tag.
   - Standalone analysis script that produces a tracked artifact → descriptor sidecar field.
   - Standalone script where filename can't carry the tag (already named for its function, or referenced by import) → comment-block header.
   - Commit subject for any change to a script or notebook → commit-message tag (orthogonal to the in-file patterns; works alongside any of them).
   - Library code under `src/<pkg>/` → no metadata required. Entity → file linkage in plan/interpretation prose is enough.
3. **Pattern 1: Filename tag.** Format: `<task-id>_<slug>.py` for tasks, `q<NNN>_<slug>.py` for questions, `h<NN>_<slug>.py` for hypothesis-scoped scripts. Multiple tags allowed via repeated prefix or short delimiter (e.g., `q011_t070_compare.py`). Cite cbioportal's three notebooks as the canonical example. Note: the slug after the tag is descriptive prose; the tag is the load-bearing part.
4. **Pattern 2: Comment-block header.** Format: a single line near the top of the script body, after the docstring or shebang:
   ```python
   # task: t131
   # task: t131, q011  # multiple tags allowed
   ```
   Allowed in any source language using `#` comments; equivalent forms (`// task: tNNN`, `% task: tNNN`) are sanctioned for non-`#` languages. Place after the module docstring; do not embed in the docstring (keeps the docstring clean for help/tooling).
5. **Pattern 3: Descriptor sidecar field.** Document four optional fields on artifact-producer descriptor JSONs:
   - `task: "tNNN"` (or `task: ["tNNN", "tMMM"]`)
   - `question: "qNNN"` (or list)
   - `hypothesis: "hNN"` (or list)
   - `interpretation: "<interpretation-id>"` (or list)
   Each field is optional and additive on top of the descriptor's existing `git_commit` / `command` / `inputs[]` / `outputs[]`. **Status: pending Bucket C namespace decision** — when P1 #8 (datapackage `<project>:` extension profile + descriptor sidecar shape) lands, these field names become part of the canonical descriptor schema. They may end up at top level or under a `science:` block. The names themselves are stable; only nesting may change. Projects already shipping descriptors (protein-landscape today) MAY adopt the field names early.
6. **Pattern 4: Commit-message tag.** Format: Conventional-Commits-style with the task id in the scope: `<type>(t<NNN>): <subject>`, e.g., `fix(t131): thread random_seed`. Multiple tags via comma: `fix(t131,q011): ...`. Both audit projects that use this pattern (cbioportal and protein-landscape) already enforce shape via `commitlint.config.mjs` + a `.husky/commit-msg` hook; that enforcement is project-side and not standardized here. Note: this pattern is *orthogonal* to the in-file patterns — a single commit can touch a notebook with Pattern 1 and a script with Pattern 2, and the commit-tag still applies.
7. **Non-rules.** One short list:
   - None of these patterns are validator-enforced upstream. Project-side commitlint is fine for Pattern 4 if a project wants it.
   - Adoption is per-project and per-artifact; mixing patterns within a project is fine.
   - Library code (e.g., `src/<pkg>/`) does not need any of these.
   - The reverse direction (entity → code via plan / interpretation `Files:` lists) remains the primary linkage; these conventions only close the code-side gap where it's cheap to do so.

Acceptance: file exists; renders cleanly; has at least one literal example for each of the four patterns; cross-links to `project-organization-profiles.md` and the audit synthesis.

---

## Task 3: Cross-link from `project-organization-profiles.md`

**Files:** Modify: `docs/project-organization-profiles.md`.

Add a short new section immediately after "Research Analysis Naming" titled `Code → Task Back-Link`. Roughly eight lines:

- One-line statement of the goal (close the code-side linkage gap where cheap).
- Four bullets, one per pattern, with a one-phrase summary and a link out to `docs/conventions/code-task-backlinks.md`.
- Closing line: "Guidance only; no validator rules. See `docs/conventions/` for the full convention catalog."

Keep the section under ~14 lines so the parent doc stays scannable. Do not duplicate content from the reference doc.

Acceptance: section present; renders; links to `docs/conventions/code-task-backlinks.md` and `docs/conventions/README.md` resolve.

---

## Dependencies and tensions

- **Bucket C dependency (P1 #8).** The descriptor-sidecar portion (Pattern 3) names four optional fields (`task`, `question`, `hypothesis`, `interpretation`) that will eventually be part of the canonical descriptor schema. This plan ships the field names early as a sanctioned optional convention; Bucket C's design pass will formalize the schema and may rename, restructure, or namespace these fields (e.g., under a `science:` block per `synthesis.md` §3.5/§7.1). **Tension to resolve at Bucket C time:** if Bucket C decides on a namespaced shape (e.g., `science.task: tNNN` rather than top-level `task: tNNN`), this convention doc must update Pattern 3 in lockstep, and any descriptors emitted in the interim will need a one-shot field rename. The risk is small (only protein-landscape ships descriptors today, with 19 files), but it is real. Mitigation: when Bucket C runs, the design session must explicitly decide whether to keep top-level or move under a namespace, and this doc is updated as part of that landing.
- **No tension with P1 #2, #4, #6, #7, #10** (the other Bucket A/B plans): they touch entity types, synthesis frontmatter, task lifecycle, MAV, and next-steps chaining respectively — none touch code-artifact metadata.

---

## Out of Scope

- Validator rules for any of the three patterns. (`scripts/validate.sh` is unchanged.)
- A `science-tool` command to emit/lint back-links.
- Migrating existing downstream projects to the convention. (Adoption is opt-in; downstream cycles are separate.)
- Defining the full descriptor schema. (Bucket C / P1 #8.)
- The mm30-suggested `scripts/hypotheses/<h>/manifest.yaml` `produces:` / `consumes:` shape — flagged in `mm30.md` §6 as project-grown and hypothesis-specific; not promoted to a Science-wide pattern by this plan. Revisit if a second project shows the same shape.
