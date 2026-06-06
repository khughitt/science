# v2→v3 entity-layout migration readiness — multi-project audit

**Date:** 2026-06-06
**Scope:** All 19 non-transient Science projects registered in `~/.config/science/config.yaml`
(excluding the 3 `natural-systems/.worktrees/*` worktrees, the ephemeral
`/tmp/science-guide-example`, and MM30 itself — MM30 is the downstream migration target).
**Method:** read-only `uv run --frozen science entities migrate --project-root .` dry-run per
project (each resolves the editable `~/d/science/science` checkout, i.e. the just-merged
local-kind tooling), then per-token classification by a sub-agent into
**G**ap (migrator is wrong) / **M**echanical (genuine, safely fixable) / **D**eep (genuine,
needs judgment).

> **Why read-only first (deviation from "fix mechanically on the fly"):** classification had
> to precede edits. The audit confirms most apparent "undated entity" / "unresolved reference"
> blockers are migrator **false positives** — editing the projects to satisfy them would be
> wrong. The genuinely-mechanical fix set is small (see §3); the leverage is in the tooling
> gaps (§2).

---

## 1. Readiness table

| Project | ready | moves | collisions | undated | unresolved files/tokens | dominant issue |
|---|---|---|---|---|---|---|
| cancer-ovarian | ✅ yes | 2 | 0 | 0 | 0/0 | clean |
| cancer-head-and-neck | ✅ yes | 2 | 0 | 0 | 0/0 | clean |
| cancer-prostate | ✅ yes | 2 | 0 | 0 | 0/0 | clean |
| cancer-breast | ✅ yes | 2 | 0 | 0 | 0/0 | clean |
| health-immunity | ✅ yes | 7 | 0 | 0 | 0/0 | clean |
| **natural-systems** | 💥 CRASH | — | — | — | — | **manifest validation aborts tool (G7)** |
| **protein-landscape** | 💥 CRASH | 296* | 0 | 6 | 11/26 | **manifest validation aborts tool (G7)** |
| cats | ⚠️ no | 1 | 0 | 1 | 0/0 | 1 real undated (M) |
| cancer-therapeutics | ⚠️ no | 57 | 0 | 5 | 3/3 | synthesis-undated + code-fence/x-proj |
| science-meta | ⚠️ no | 123 | 0 | 7 | 4/7 | synthesis-undated + code-fence |
| cancer-pre-cancer | ⚠️ no | 17 | 0 | 1 | 5/24 | wikilinks + x-proj + 1 undated |
| cbioportal | ⚠️ no | 338 | 0 | 17 | 22/14 | short-form prose refs + synthesis-undated |
| 3d-attention-bias | ⚠️ no | 93 | 0 | 41 | 9/71 | nonentity files + kg-yaml + committed: |
| cancer-meta | ⚠️ no | 176 | 0 | 1 | 19/74 | wikilinks + code-fence + x-proj |
| health-cycles | ⚠️ no | 375 | 0 | 5 | 10/18 | synthesis-undated + near-match topics (D) |
| pan-disease | ⚠️ no | 150 | 4 | 9 | 11/23 | code-fence + wikilink + x-proj + filename-alias collision |
| health-meta | ⚠️ no | 348 | 0 | 0 | 17/62 | wikilinks + x-proj + line-wrap |
| cancer-evolution | ⚠️ no | 366 | 0 | 0 | 20/104 | wikilinks (57!) + x-proj + report:N-M |
| seq-feats | ⚠️ no | 202 | 0 | 43 | 6/120 | entities.yaml audit-stub drift + nonentity files (deep) |

\* counts where the tool crashed are from static inspection / a patched bypass run.

**5 projects already migrate cleanly.** All 5 are small leaf projects (≤7 moves, no local
kinds, no cross-project prose). Every project with real research history is blocked — almost
entirely by tooling gaps, not by its own content.

---

## 2. Tooling-gap taxonomy (the deliverable)

Ordered by severity × prevalence.

### TIER 0 — hard-crash regressions introduced by the just-merged local-kind work

**G7 — strict local-kind manifest validation aborts the entire migration (no JSON output).**
Our new `load_local_entity_policies` raises `EntityCommandError` (→ tool exits) when a local
kind violates `name == canonical_prefix` or when its `home` directory-name collides with a core
kind directory. Two existing manifests trip this and the **whole** migrate dies — including core
kinds that are perfectly fine:
- **natural-systems** `knowledge/sources/project_specific/manifest.yaml`: kind `meta` declares
  `canonical_prefix: doc` (entities actually use `meta:` ids). → `Error: local kind 'meta' has
  canonical_prefix 'doc'; they must be equal`. Zero output.
- **protein-landscape** `manifest.yaml`: kind `methods` home defaults to `entities/methods`
  which collides with the core `method` directory; kind `paper-synthesis` has
  `canonical_prefix: synthesis`. Both vestigial (0 entities). Tool aborts before any JSON.

This is the clearest "overfit to MM30" evidence: MM30's manifest happened to satisfy the strict
rules; these did not. Pre-merge, local kinds were *ignored*, so these manifests were tolerated.
**Design question for the user (strictness philosophy):** should one malformed/vestigial local
kind abort the tool for the whole project, or should the loader skip-with-warning that kind and
still migrate the rest? ("Fail early / explicit" argues for the hard error + project-side fix;
robustness argues for graceful degradation. The two affected kinds are vestigial, so a project
fix is cheap — but the brittleness will recur.)

### TIER 1 — pervasive reference false-positives (block nearly every non-trivial project)

**G1 — `[[wikilink]]` citation syntax flagged as unresolved refs.** The migrator treats
`[[CiteKey]]` / `[[slug]]` as policed reference tokens but cannot map them to the existing
`paper:CiteKey` (or `question:slug`) entity. Largest single gap by volume:
- cancer-evolution: **57 of 104 tokens** (`[[AuthorYYYY]]`); health-meta: 29; cancer-meta: 14;
  cancer-pre-cancer: 21; pan-disease: several. All targets exist locally as `paper:*`/`question:*`.
- Fix direction: either resolve `[[Key]]` against the id_map across kinds (paper-citation
  convention), or exclude `[[Key]]` bibliography citations from the policed-ref scan.

**G2 — the scanner reads inside fenced code blocks (```…```) and inline code spans (`…`).**
Example/template entity-ids embedded in documentation are flagged:
- science-meta (5, ```yaml schema examples), cancer-meta (many `question:q00x` in ```markdown），
  pan-disease (`hypothesis:disease-label-misalignment` etc. in ```markdown; `meta:doc` from a
  backtick path span), cancer-therapeutics (```markdown template), 3d-attention-bias (```yaml),
  health-meta (```bash CLI examples).
- Fix direction: strip fenced + inline code before reference extraction.

**G3 — line-wrap / ellipsis truncation inside inline code** (`` `interpretation:bias-dark-\n
frontier` `` → `interpretation:bias-dark`; `` `question:q12-...` `` → `question:q12`). Seen in
protein-landscape, pan-disease, health-meta, cbioportal, cancer-evolution. **Largely subsumed by
G2** (all occur inside code spans); fixing G2 removes most of these.

### TIER 2 — structural false-positives

**G5 — cross-project pointers flagged as unresolved.** Every meta/child project references
sibling/parent entities that are *intentionally* not local: `hypothesis:h00-working-model`
(→science-meta), `hypothesis:h4-attractor-convergence` (→MM30), federation themes annotated
"(in ~/d/cancer/meta)", `meta:question:*` namespaced ids, etc. By definition unresolvable
locally. Needs a principled exclusion (recognize an explicit cross-project ref form, or a
declared federation namespace) so they are non-blocking. **Design work.**

**G10 — the scanner policbones `knowledge/sources/*.yaml` graph/alias files.** Alias *source*
keys (LHS of `mappings.yaml` entries) and graph-only entity defs in `entities.yaml`/`relations.yaml`
are treated as references needing resolution:
- protein-landscape/cats: ~9 `mappings.yaml` alias-source keys each; 3d-attention-bias: 20
  `topic:*` defined only in `entities.yaml` (no `.md`); health-cycles: `question:NN` in a
  `mappings.yaml` comment. Fix: exclude the knowledge-source YAML layer (or at least alias-LHS
  keys and comments) from ref scanning.

**G8 — non-entity files under entity dirs pulled in as (undated) entities.** Files with **no
entity frontmatter** (no `id:`) are treated as migratable:
- 3d-attention-bias: 25 `doc/background/papers/*.md` bibliography summaries + 9 numbered
  `doc/background/topics/*.md` narratives + 3 `doc/discussions/*.md`, all frontmatter-less.
- pan-disease: `specs/hypotheses/cohort-adjudication-h01.md`, `h01-cohort.md` — prose audit docs
  with no `id:`, treated as hypotheses.
- seq-feats: 43 frontmatter-less papers/topics.
- Fix direction: require entity frontmatter (or an explicit `id:`) before treating a file as a
  migratable entity; otherwise leave/ignore. (Borderline — some projects may *intend* these as
  entities; see Deep.)

### TIER 3 — minor

**G6 — bare short-form prose refs** (`hypothesis:h03` where the id is `hypothesis:h03-…`).
cbioportal (10 tokens), pre-cancer, others. The rewriter resolves them but the unresolved-scan
does not. Decide whether short-forms are first-class (then teach the scanner) or not.

**G9 — date field aliases.** Entities carry a date under a non-`created:` key:
`generated_at:` on `/science:big-picture` synthesis files (systematic — appears in
protein-landscape, science-meta, pan-disease, health-cycles, cancer-therapeutics, cbioportal),
and `committed:` on 3d-attention-bias pre-registrations. The migrator flags them undated.
Fix: accept `generated_at:`/`committed:` as a creation-date fallback, **or** have big-picture
emit `created:`. The synthesis-file case alone accounts for most "undated" counts in 6 projects.

**G4 — obvious placeholders/wildcards** (`hNN`, `h01-*`, `question:066-<slug>`,
`analysis-plan:t015-*`, `question:NN`). pan-disease, cancer-evolution, health-cycles,
3d-attention-bias, cancer-therapeutics. Mostly inside code spans → subsumed by G2; a few in
prose tables need a wildcard/placeholder guard.

**G-novel — `report:N-M` line-range notation** (cancer-evolution: `report:198-210` citing script
line ranges) and **filename-only alias collisions** (pan-disease: 4 `…/interpretation.md` files
in distinct date-dirs collide on the `interpretation:interpretation` alias because the alias is
built from filename, ignoring the date-prefixed parent dir → the 4 reported `collisions`). The
latter is a **real collision-generation gap**, not just a scan gap.

---

## 3. Genuinely-mechanical fixes (safe; small set)

These are real entities with a recoverable date and no gap interpretation. Candidates to fix
on-the-fly (one commit per repo), **but** several overlap G9 (better fixed in tooling):

- **cats**: `doc/plans/kg-project-migration-guide.md` — add frontmatter `created: 2026-03-18`
  (git). (No frontmatter at all today.)
- **cancer-meta**: `specs/research-question.md` — `created: 2026-05-21`.
- **cancer-pre-cancer**: `specs/research-question.md` — `created: 2026-05-21`; the 21 wikilink
  tokens are G1, not mechanical.
- **cancer-pre-cancer / cancer-evolution**: 1 slug typo each (M) — `question:021-ou-expression-evolution`
  → `…-human-tumors`.

Everything else tagged "M" by the sub-agents is really G9 (synthesis `generated_at:` files) or
G8 (frontmatter-less nonentity files) and should be fixed in the **tooling**, not the projects.

---

## 4. Genuine deep issues (leave to the owning project)

- **seq-feats**: `entities.yaml` accumulated `migration:audit` stubs with bare-numeric ids
  (`question:NN-…`) conflicting with the `qNN-…` file convention; 6 questions exist only as
  inline sections with 3 competing id variants each (`q31`/`Q31`/`question:31`). Needs real
  reconciliation (~63 tokens). Worst-off project.
- **health-cycles**: ~8 short `topic:*` refs that are near-matches to longer local topic ids
  (`topic:chronotype` vs `topic:chronotype-and-circadian-phenotyping`) or genuinely dangling —
  alias-vs-create-vs-rename is a content decision.
- **cbioportal**: `meta:big-picture-2026-04-28` — dangling ref in task `related:` to a synthesis
  artifact never materialized as a file.
- **health-meta**: `topic:mutation-rate-normalization` dangling.

---

## 5. Recommended remediation order

1. **TIER 0 (G7)** — decide strictness philosophy; unblocks natural-systems + protein-landscape
   (both fully dead today). Smallest change, highest unblock.
2. **G9 (synthesis `generated_at:`)** — one fix clears most "undated" counts across 6 projects.
3. **G2 (skip code fences/spans)** — clears the largest prose false-positive class; subsumes G3
   and most of G4.
4. **G1 (`[[wikilink]]` handling)** — clears the single largest token volume (cancer-evolution,
   health-meta).
5. **G10 (skip knowledge-source YAML)**, **G8 (require entity frontmatter)**,
   **G-novel (date-dir-scoped alias to fix filename collisions)**.
6. **G5 (cross-project refs)** — most design-heavy; do last / separately.

After 1–5, re-run the audit; expectation is that all projects except seq-feats (deep content
debt) reach ready with **zero project-side edits**.
