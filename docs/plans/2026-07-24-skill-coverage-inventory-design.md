# Skill-Corpus Surfacing — Packaged Inventory + `covers:` + Overlay (Skill-Coverage sub-plan 3) — Design

> **Status:** design / spec, approved for planning. Part of Plan 2 (the skill-coverage
> layer) of the data-product-vocabulary program. Parent design:
> [`2026-07-23-data-product-vocabulary-and-skill-coverage-design.md`](2026-07-23-data-product-vocabulary-and-skill-coverage-design.md)
> (§"Skills-corpus locator (packaged inventory)", §"Skill overlay (derived, role-typed,
> in-memory)", §"Coverage: two sets, and the states").
> Sibling shipped sub-plans: enrollment
> ([`2026-07-23-skill-coverage-enrollment-implementation.md`](2026-07-23-skill-coverage-enrollment-implementation.md)),
> the gen-3 write-path fix
> ([`2026-07-23-skill-coverage-writepath-implementation.md`](2026-07-23-skill-coverage-writepath-implementation.md)),
> and the `skills_loaded` truth path
> ([`2026-07-24-skill-coverage-skillsloaded-design.md`](2026-07-24-skill-coverage-skillsloaded-design.md)).

## Motivation

Sub-plan 2 built the **demand side** of coverage: a validated, reified record of *which
skill a plan loaded* (`sci:hasSkillLoad` → `sci:skill/<canonical-name>`), deliberately leaving
open the question of whether a loaded id names a real corpus skill or what that skill addresses.
This sub-plan builds the **supply side**: what skills exist, and — for the bio subtree in v1 —
what data-products each one covers. It ships three things: catalog-validated `covers:` on bio
leaves, a packaged and drift-checked machine-readable skill **inventory**, and a role-typed
in-memory **overlay** built from that inventory. The overlay is the exact substrate the
sub-plan-4 `science skills coverage` command joins against the reified `skills_loaded` records.

## Grounding findings that shape the design

- **`skills/INDEX.md` is the complete, authoritative id↔path registry.** It maps each canonical
  **skill id** to its file path (e.g. `` `transcriptomics-scrna-qa`: `skills/bio/transcriptomics/scrna-qa.md` ``).
  Verified **exact**: 60 entries, one per real skill (14 routers + 46 leaves); every listed path
  exists on disk; every real skill file appears in it; and it lists **no** non-skills (the 7
  `skills/meta/templates/*.md` and `INDEX.md` itself are absent). Driving enumeration off INDEX.md
  therefore applies the exclusions automatically and yields the canonical id for free — no fragile
  path-to-id derivation. `skills/sources.yaml` is a non-`.md` sources registry, not a skill.
- **The canonical skill id is the INDEX key, not the frontmatter `name`.** `skills_loaded` authors
  the **qualified** id (`commands/plan-analysis.md:130`: `id: transcriptomics-scrna-qa`), which is
  the INDEX key — **not** the bare frontmatter `name` (`scrna-qa`). Sub-plan 2 canonicalizes and
  emits that same id as `sci:skill/<id>`. So the inventory's identity and the overlay's key **must**
  be the INDEX id; keying by frontmatter `name` would make the sub-plan-4 join silently never match.
  Frontmatter `name` values happen to be unique corpus-wide, but they are the wrong key.
- **Skill/role rule.** For an INDEX entry, the skill is a **router** iff its path basename is
  `SKILL.md`, else a **leaf**. This is the sole role rule.
- **Leaf frontmatter carries `name`, `description`, `archetype`, `sources`** (e.g.
  `skills/bio/functional-genomics-qa.md`: `archetype: measurement-qa`, `sources: [depmap, mageck]`).
  **Every real leaf has `archetype`** — verified across all 46 (the one `.md` without it is
  `skills/meta/templates/router.md`, an excluded template). Routers carry `name`, `description`,
  `provenance` and **no `archetype`** (verified: zero routers declare it). **No leaf or router
  currently declares `covers:`** — it is new.
- **A generate-from-corpus + drift-check precedent exists** — the Codex mirror:
  - `science/src/science_tool/codex_skills.py` exposes an importable
    `generate_codex_skills(repo_root, output_root) -> dict[str, Path]` that parses frontmatter and
    writes generated files into an output root;
  - `scripts/generate_codex_skills.py` is the thin CLI wrapper;
  - `science/tests/test_codex_skills.py` drives the generator into a `tmp_path` and asserts
    properties of the result.
  This sub-plan mirrors the shape: importable builder + `scripts/` wrapper + committed resource +
  drift test.
- **The data-product catalog is authored and closed** — `science_model.data_products` (package
  under `science/model/src/science_model/data_products`), 54 canonical terms with grammar
  `^data-product:[a-z0-9][a-z0-9-]*$` (Plan 1). Relevant bio terms exist and are real:
  `gene-expression-bulk-rna`, `gene-expression-microarray`, `gene-expression-single-cell`,
  `somatic-variant`, `mutational-signature`, `copy-number`, `structural-variant`, `proteomics`,
  `genetic-dependency`, `genetic-perturbation`, `drug-sensitivity`.
- **The `covers:` / overlay authority belongs in `science-model`.** The parent design names "the
  coverage module in `science-model`, alongside the term catalog" as the authority; the catalog a
  `covers:` term is validated against already lives there, so the typed overlay and its validation
  colocate with it. The packaged inventory is a `science_tool` resource; only the raw
  frontmatter-scan/generation touches the corpus tree.

## Design

### 1. Scope and boundaries

Ships: (a) catalog-validated `covers:` frontmatter on the **bio leaf subtree**; (b) a packaged,
drift-checked machine-readable skill **inventory** resource in `science_tool`; (c) a role-typed
in-memory **overlay builder** in `science-model`. Exercised by synthetic in-repo fixtures plus the
real bio-leaf authoring.

Deferred to **sub-plan 4**: the `science skills coverage` command, the `coverage-report` JSON, the
`dataset_usage`-style occurrence join against `skills_loaded`, the coverage **states** and the
`unmapped-skill-reference` / uncovered **WARN diagnostics**. Deferred beyond v1: `covers:` outside
the bio subtree; the method/operation axis; any persistent (on-disk) overlay artifact.

### 2. `covers:` on leaves

A new **optional** leaf frontmatter key, `covers:`, a **list** of canonical data-product term ids
(`data-product:*`). It is authored **only on leaves**; a router carrying `covers:` is a structural
error (§5). It is authored on a bio leaf **only where a data-product maps honestly** — leaves with
no clean mapping stay **uncovered by design** (a real, later-reportable coverage state), never
forced. Each term is **validated against the `data_products` catalog** when the inventory is
generated and again when the overlay is built; an off-catalog term is a **hard error**, never a
silent drop.

Proposed v1 mapping (finalized during implementation; each is authoring-time domain judgment):

| bio leaf | `covers:` |
|---|---|
| `transcriptomics/bulk-rnaseq-qa` | `data-product:gene-expression-bulk-rna` |
| `transcriptomics/microarray-qa` | `data-product:gene-expression-microarray` |
| `transcriptomics/scrna-qa` | `data-product:gene-expression-single-cell` |
| `genomics/somatic-mutation-qa` | `data-product:somatic-variant` |
| `genomics/mutational-signatures-qa` | `data-product:mutational-signature` |
| `genomics/copy-number-sv-qa` | `data-product:copy-number`, `data-product:structural-variant` |
| `proteomics/proteomics-qa` | `data-product:proteomics` |
| `functional-genomics-qa` | `data-product:genetic-dependency`, `data-product:genetic-perturbation`, `data-product:drug-sensitivity` |
| `genomics/driver-selection`, `transcriptomics/cohort-qa`, `transcriptomics/data-integration`, `proteomics/protein-sequence-structure-qa` | *uncovered by design* |

`covers:` term granularity is **exact** — a leaf covers the term(s) it actually addresses, not
their catalog ancestors. Ancestor-aware coverage is explicitly a non-goal (parent design:
"Coverage is exact-term, not ancestor-aware").

### 3. Packaged inventory

A generated, machine-readable resource shipped as **`science_tool` package data**
(`science/src/science_tool/graph/skill_inventory.json`), the natural sibling of the sub-plan-2
`skill_aliases.yaml`. Format is **canonical sorted JSON** (`json.dumps(..., indent=2, sort_keys=True)`
+ trailing newline): the resource is generated and never hand-edited, so a canonical serialization
makes the drift check a deterministic **byte-match**.

**Contents.** A top-level object with a `skills` list; each entry records:

- `id` — the **INDEX key** (the canonical id `skills_loaded` references and sub-plan 2 emits, e.g.
  `transcriptomics-scrna-qa`) — the identity field;
- `name` — the frontmatter `name` (bare, e.g. `scrna-qa`), retained for traceability only;
- `path` — repo-relative path (e.g. `skills/bio/transcriptomics/scrna-qa.md`);
- `role` — `"leaf"` or `"router"` (the role rule);
- `description` — frontmatter `description`;
- `archetype` — leaf only (always present on leaves; omitted for routers);
- `covers` — leaf only, the validated term-id list (**omitted when empty**, so an uncovered leaf
  and a router both simply lack the key — uniform absence, no empty-list noise);
- `sources` — the frontmatter `sources` list when present (leaf-authored), else omitted.

**Generation.** An importable `build_skill_inventory(repo_root: Path, catalog) -> dict` reads
`skills/INDEX.md` as the authoritative id↔path registry, and for each entry reads the file's
frontmatter (parsing the fenced block with `yaml.safe_load` — never `yaml.load`/a custom
type-constructing loader), assigns `role` by the basename rule, and validates `covers:` against the
catalog. It **asserts INDEX↔corpus consistency** — every INDEX path exists, and every real skill
file (a `.md` under `skills/`, excluding `INDEX.md` and `skills/meta/templates/`) appears in INDEX —
so an unregistered new leaf or a stale INDEX path is a hard error, not a silent omission. It returns
the canonical dict. `scripts/generate_skill_inventory.py` is the thin wrapper that serializes it to
the committed resource path. Both mirror `generate_codex_skills` / `scripts/generate_codex_skills.py`.

**Drift check.** A pytest calls `build_skill_inventory` against the live corpus, serializes it with
the same canonical dumper, and asserts **byte-identical** to the committed `skill_inventory.json`.
Any corpus edit (a new leaf, a changed `covers:`, a renamed skill, an INDEX edit) that isn't
regenerated fails the test — the same guarantee the Codex mirror relies on. The failure message
names the regeneration command.

### 4. Role-typed overlay builder

Lives in **`science-model`** (the coverage module, beside the `data_products` catalog).
`build_skill_overlay(inventory: dict, catalog) -> SkillOverlay` turns the loaded inventory into
**role-typed** resources, each identified by its canonical `id` (the INDEX key):

- `LeafSkill` — `id`, `name`, `archetype` (**required**), `covers: list[str]` (each validated
  against the catalog; empty when uncovered), `description`, `sources`;
- `RouterSkill` — `id`, `name`, `description`; **no** `archetype`, **no** `covers`.

`SkillOverlay` exposes lookup **by `id`** and iteration, and is what sub-plan 4 joins against the
reified `sci:skill/<id>` targets (the join key is the canonical INDEX id on both sides). The builder **re-validates** the structural invariants (it does
not trust the JSON blindly, since a resource can be edited): a `covers` term off-catalog, a router
carrying `covers`/`archetype`, or a leaf missing `archetype` is a **structural error** (§5).

**Package split.** `science_tool` owns only the `importlib.resources` **loader**
(`load_skill_inventory() -> dict`, reading the packaged JSON) and the corpus-scanning generator;
`science-model` owns the typed overlay + its validation. The overlay never reads the `skills/` tree
— it consumes the loaded inventory dict, so it works from an installed toolkit that ships no corpus.

### 5. Error handling

All violations are **hard, fail-early errors**, never silent skips or fallbacks:

- a `covers:` term not in the `data_products` catalog — at generation **and** at overlay build;
- a router declaring `covers:` or `archetype:`;
- a leaf missing `archetype:`;
- malformed frontmatter (missing `name`, unparseable block, `covers:` not a list of strings);
- **INDEX↔corpus inconsistency** at generation — an INDEX path that does not exist, or a real
  skill file absent from INDEX (an orphan);
- inventory **drift** (committed resource ≠ freshly generated) — a test failure with the
  regeneration command.

### Data flow

```text
skills/INDEX.md (id↔path) + skills/*.md frontmatter
    ──build_skill_inventory (INDEX-driven scan + consistency + validate covers vs catalog)──▶ skill_inventory.json  (science_tool package data)
skill_inventory.json ──load_skill_inventory (importlib.resources)──▶ dict
dict + data_products catalog ──build_skill_overlay (role-typed, keyed by id, re-validated)──▶ SkillOverlay  (science-model)
                                                                                     └─▶ (sub-plan 4) join sci:skill/<id> vs reified skills_loaded
```

## Testing approach

- **`covers:` catalog validation:** a leaf with an in-catalog term validates; an off-catalog term
  is a hard error at generation and at overlay build.
- **Inventory determinism + drift:** `build_skill_inventory` over the live corpus serializes
  byte-identical to the committed `skill_inventory.json`; a synthetic changed/added leaf changes the
  output (drift is detectable).
- **INDEX-driven identity + consistency:** each entry's `id` is the INDEX key (e.g.
  `transcriptomics-scrna-qa`), not the frontmatter `name` (`scrna-qa`); an INDEX path that does not
  exist, and a real skill file missing from INDEX, are each hard errors at generation.
- **Exclusions + role rule:** `INDEX.md`, `skills/meta/templates/*`, and `sources.yaml` never appear
  in the inventory (they are not INDEX entries); `SKILL.md` paths are `role: router`, others
  `role: leaf`.
- **Overlay role-typing + key:** a leaf yields a `LeafSkill` with `archetype` and validated
  `covers`; a router yields a `RouterSkill` with neither; an **uncovered** leaf builds cleanly with
  empty `covers` (not an error); the overlay is looked up by canonical `id` (the sub-plan-4 join key).
- **Overlay invariants:** a router-with-`covers`, a leaf-without-`archetype`, and an off-catalog
  term each raise a structural error at build.
- **Package boundary:** `build_skill_overlay` consumes a dict and never touches the `skills/` tree
  (works with the corpus absent).

Verification gate: full `science` and `science/model` suites, `ruff check`, `pyright`.

## Out of scope (documented boundaries)

- **The `science skills coverage` command, the `coverage-report`, the occurrence join, the coverage
  states, and the `unmapped-skill-reference` / uncovered diagnostics** — sub-plan 4. This sub-plan
  produces the inventory + overlay; it never joins them against `skills_loaded` or emits a report.
- **`covers:` outside the bio subtree** — later slices, riding the same catalog-validation path.
- **The method/operation axis and any persistent on-disk overlay artifact** — the overlay is
  in-memory, built per consumer.
- **Changing router/leaf structure, archetypes, or the skill taxonomy** — the inventory reflects the
  corpus as-authored.
