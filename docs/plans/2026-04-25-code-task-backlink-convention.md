# Code/Notebook → Task Back-Link Convention Plan

**Goal:** document a sanctioned set of code → task linkage patterns, framed as guidance, not as a validator-enforced requirement.

**Context:** addresses P1 #9 from the downstream conventions audit synthesis (`docs/audits/downstream-project-conventions/synthesis.md` §6.4 brief; §8.2 in full). All four audited projects show weak code-side linkage to tasks/questions/hypotheses (forward direction `entity → code` is fine in plan/interpretation prose; reverse direction is filename-dependent at best). The synthesis is explicit: case-by-case rather than universal sidecar.

**Scope:** documentation only. No validator rules. No `science-tool` commands. No mandatory adoption.

---

## Evidence (from the audit)

Three patterns observed in the wild, each fit-for-purpose at one or more projects:

1. **Filename tag** — cbioportal's `code/notebooks/{q011_length_adjustment_topn_comparison.py, t070_poc_comparison.py, t131_three_way_ranking_comparison.py}` (`docs/audits/downstream-project-conventions/projects/cbioportal.md` §6). Three task-tagged marimo notebooks; the prefix is the entire convention.
2. **Comment-block header** — implied by the audit's recommendation (`synthesis.md` §8.2: "a `# task: tNNN` comment-block convention is sufficient"). Used informally in cbioportal docstrings; not a uniform shape today.
3. **Descriptor sidecar field** — protein-landscape's 19 `descriptors/<artifact>.parquet.descriptor.json` files (`docs/audits/downstream-project-conventions/projects/protein-landscape.md` §6, §9 / §7) carry `git_commit, command, parameters, inputs[{path, sha256}], outputs[{path, sha256, row_count}]` — but no `task:` / `question:` field. Closing that gap is the most valuable addition for artifact-producing scripts.

Two further projects confirm the same gap without yet shipping a fix:

- **mm30** (`docs/audits/downstream-project-conventions/projects/mm30.md` §6): "weak — a few `scripts/hypotheses/h*` directory names align with hypothesis IDs; otherwise code does not declare which task/hypothesis it implements." Suggests `scripts/hypotheses/<h>/manifest.yaml` could carry `produces:` / `consumes:`.
- **natural-systems** (`docs/audits/downstream-project-conventions/projects/natural-systems.md` §6): "weak from code → entities. Reverse direction is well-populated; code files do not carry sidecar metadata or in-source provenance frontmatter."

---

## File Structure

Files modified (no code, no new files in `templates/`, `scripts/`, or `science-tool/`):

- `docs/project-organization-profiles.md` — add a new section "Code → task back-link" near the existing "Research Analysis Naming" section.
- `docs/conventions/code-task-backlinks.md` — *new*, ~40-60 line reference doc. Holds the three sanctioned patterns and the descriptor optional-field list. Cross-linked from `project-organization-profiles.md`.

No CLAUDE.md/AGENTS.md exists at the Science repo root today; nothing to modify there. Downstream projects' CLAUDE.md/AGENTS.md are out of scope (they will pick up the convention by reference if they choose to adopt it).

---

## Task 1: Write the convention reference doc

**Files:** Create: `docs/conventions/code-task-backlinks.md`.

Single page. Sections:

1. **When to use which pattern** — one short paragraph, then a table mapping artifact shape → recommended pattern:
   - Notebook (Jupyter/marimo, 1-10 per project) → filename tag.
   - Standalone analysis script that produces a tracked artifact → descriptor sidecar field.
   - Standalone script where filename can't carry the tag (already named for its function, or referenced by import) → comment-block header.
   - Library code under `src/<pkg>/` → no metadata required. Entity → file linkage in plan/interpretation prose is enough.
2. **Pattern 1: Filename tag.** Format: `<task-id>_<slug>.py` for tasks, `q<NNN>_<slug>.py` for questions, `h<NN>_<slug>.py` for hypothesis-scoped scripts. Multiple tags allowed via repeated prefix or short delimiter (e.g., `q011_t070_compare.py`). Cite cbioportal's three notebooks as the canonical example. Note: the slug after the tag is descriptive prose; the tag is the load-bearing part.
3. **Pattern 2: Comment-block header.** Format: a single line near the top of the script body, after the docstring or shebang:
   ```python
   # task: t131
   # task: t131, q011  # multiple tags allowed
   ```
   Allowed in any source language using `#` comments; equivalent forms (`// task: tNNN`, `% task: tNNN`) are sanctioned for non-`#` languages. Place after the module docstring; do not embed in the docstring (keeps the docstring clean for help/tooling).
4. **Pattern 3: Descriptor sidecar field.** Document four optional fields on artifact-producer descriptor JSONs:
   - `task: "tNNN"` (or `task: ["tNNN", "tMMM"]`)
   - `question: "qNNN"` (or list)
   - `hypothesis: "hNN"` (or list)
   - `interpretation: "<interpretation-id>"` (or list)
   Each field is optional and additive on top of the descriptor's existing `git_commit` / `command` / `inputs[]` / `outputs[]`. State explicitly that the canonical descriptor schema itself is a Bucket C deliverable (P1 #8, datapackage `<project>:` extension profile + descriptor sidecar shape — see `docs/plans/2026-04-25-conventions-audit-p1-rollout.md` Bucket C). When Bucket C lands, these field names will be added to the canonical descriptor schema. Until then, projects already shipping descriptors (protein-landscape today) MAY adopt the field names early; the names are stable.
5. **Non-rules.** One short list:
   - This is not validator-enforced.
   - Adoption is per-project and per-artifact; mixing patterns within a project is fine.
   - Library code (e.g., `src/<pkg>/`) does not need any of these.
   - The reverse direction (entity → code via plan / interpretation `Files:` lists) remains the primary linkage; these conventions only close the code-side gap where it's cheap to do so.

Acceptance: file exists; renders cleanly; has at least one literal example for each of the three patterns; cross-links to `project-organization-profiles.md` and the audit synthesis.

---

## Task 2: Cross-link from `project-organization-profiles.md`

**Files:** Modify: `docs/project-organization-profiles.md`.

Add a short new section immediately after "Research Analysis Naming" titled `Code → Task Back-Link`. Roughly six lines:

- One-line statement of the goal (close the code-side linkage gap where cheap).
- Three bullets, one per pattern, with a one-phrase summary and a link out to `docs/conventions/code-task-backlinks.md`.
- Closing line: "Guidance only; no validator rules."

Keep the section under ~12 lines so the parent doc stays scannable. Do not duplicate content from the reference doc.

Acceptance: section present; renders; link to `docs/conventions/code-task-backlinks.md` resolves.

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
