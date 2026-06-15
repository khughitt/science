# Kind Descriptor & Model Registry — Design (Patchwork Kernel Spec 2)

**Status:** Design / approved direction — pre-implementation

**Spec:** Spec 2 of the patchwork-kernel architecture
(`~/d/science/docs/plans/2026-06-14-patchwork-kernel-architecture-design.md`).
Follows the shipped Spec 4 (Patch Contract keystone + inquiry subsumption).

---

## 0. Thesis

`CORE_PROFILE` (the built-in `ProfileManifest`) becomes the **single source of
truth for authored-core kind facts**, and the **descriptor system** (the
built-in manifests `CORE_PROFILE` + `LOCAL_PROFILE`, each kind carrying a typed
`category`) becomes the one place every kind is declared. The same per-kind facts
are today re-declared across surfaces that already drift:

- `EntityType` enum (`science_model/entities.py`) — 41 members, consumed in ~50 files.
- The registry (`science_tool/graph/entity_registry.py`) — `register_core_kind`
  bindings (46 kinds) + `_CORE_KIND_CLASSES` (kind → `EntityClass`).
- The `entities.py` maps in the tool layer — `_BUILTIN_MARKDOWN_POLICIES`
  (path/strategy), `_DEFAULT_STATUS`, `_STATUS_VALUES`, `_SHORTFORM_ENTITY_KINDS`.
  Since increment 1 (the keystone) these four **derive from `CORE_KINDS`** rather
  than from inline literals (see §0.1).
- `CORE_KINDS` (`science_model/kinds.py`) — the **transitional** descriptor manifest
  shipped by increment 1 (28 file-authored kinds); the current SSOT for the four
  tool maps above. This spec absorbs it into `EntityKind` and deletes it (§0.1).
- `MIGRATED_KINDS` (`science_model/templates.py`).
- `CORE_PROFILE.entity_kinds` (`science_model/profiles/core.py`) — the intended
  SSOT, but currently the **sparsest** surface (23 kinds, most carrying only
  `name`/`canonical_prefix`/`layer`/`description`).
- `LOCAL_PROFILE.entity_kinds` (`science_model/profiles/local.py`) — 3 kinds
  (`model`, `canonical_parameter`, `parameter_binding`), the source-only locals.

Measured drift (today): the **reconciliation universe is 50 kinds** (enum ∪
registry ∪ path policies ∪ status maps ∪ MIGRATED_KINDS). 21 kinds agree across
enum / manifest / registry; the registry has 7 kinds absent from the enum and 23
absent from `CORE_PROFILE`; the enum has 2 kinds (`canonical_parameter`, `model`)
absent from both others; and two kinds (`decision`, `claim-registry`) live **only**
in the path/status maps — absent from enum, registry, and every manifest. This
spec removes that tolerated drift.

This first slice is **promote + populate + reconcile + derive, under strict
drift tests** — *not* codegen, *not* a registry rewrite.

---

## 0.1 Relationship to the shipped keystone (`CORE_KINDS`)

Increment 1 (the keystone, `2026-06-14-kind-descriptor-keystone-design.md`, shipped)
introduced a **transitional** manifest `CORE_KINDS` (`science_model/kinds.py`): a frozen
`KindDescriptor` tuple over the 28 **file-authored** core kinds, plus the
`EntityFilenameStrategy` Literal (moved there from `science_tool/entities.py`). Today the four
tool maps — `_BUILTIN_MARKDOWN_POLICIES`, `_DEFAULT_STATUS`, `_STATUS_VALUES`,
`_SHORTFORM_ENTITY_KINDS` — derive from `CORE_KINDS`, pinned by
`science/tests/test_kind_descriptor_derivation.py` (each map ≡ `CORE_KINDS`-derived ≡ a frozen
copy of the original literal) and `science/model/tests/test_kinds.py` (descriptor
self-consistency).

`CORE_KINDS` was declared transitional from the outset — a typed manifest to be **absorbed once
`EntityKind` carried the same facts**. This spec performs that absorption; it does not build
further on `CORE_KINDS`. Concretely:

- **`EntityKind` (not `CORE_KINDS`) becomes the SSOT.** The four tool maps re-derive from the
  descriptor system (`CORE_PROFILE`, filtered to `category == authored-core` for the markdown
  path/status maps; `shortform` filtered on presence), exactly as §4 specifies.
- **The keystone's 28 file-authored kinds are exactly this spec's `authored-core` set** (§2.3) —
  the kinds that receive path/status/template derivation. Because `CORE_KINDS`'s values were
  transcribed verbatim from the original literals and are guarded green, they are the **verified
  source** for populating each authored-core descriptor's
  `home`/`strategy`/`default_status`/`statuses`/`shortform` during the §3 audit — the audit
  copies from `CORE_KINDS` rather than re-transcribing the inline literals, so the
  transcription risk the keystone already retired is not reintroduced.
- **`science_model/kinds.py` is deleted in this slice** (the final task): `KindDescriptor`,
  `CORE_KINDS`, `CORE_KINDS_BY_NAME`. The `EntityFilenameStrategy` Literal is **relocated** to
  `profiles/schema.py` (the module that owns `EntityKind`); `EntityKind.strategy` is typed
  `EntityFilenameStrategy | None`; `science_tool/entities.py` imports the Literal from
  `science_model.profiles.schema`. (Task 1 defines it in `schema.py` and has `kinds.py` re-export
  it, so every flip in between stays behavior-neutral; the final task repoints the tool import and
  removes `kinds.py`.)
- **The keystone tests are replaced, not dropped.** `test_kind_descriptor_derivation.py`'s guard
  is superseded by §4's per-flip equivalence tests (each derived map ≡ the prior literal captured
  before the flip, now sourced from `CORE_PROFILE`); `test_kinds.py`'s self-consistency checks are
  superseded by §3's reconciliation gate + named-contract tests. No coverage is lost.

This reaches the single-descriptor-per-kind end state the keystone's own roadmap named, and
removes the transitional manifest in the same slice that obsoletes it — so `CORE_KINDS` never
lingers as a second SSOT beside `CORE_PROFILE`.

---

## 1. Scope

**In scope**
- Promote/populate `EntityKind` into the full per-kind fact record.
- A per-kind audit that classifies every kind into a named category.
- Strict reconciliation tests (the gate) enforcing 3-way agreement on the
  authored-core set, with reserved / source-only kinds pinned as named contracts.
- Flip the derived surfaces to compute from the descriptor behind their existing
  public accessors: `_BUILTIN_MARKDOWN_POLICIES`, `_DEFAULT_STATUS`,
  `_STATUS_VALUES`, `_SHORTFORM_ENTITY_KINDS`, `MIGRATED_KINDS`, registry
  `entity_class`. These four tool maps currently derive from `CORE_KINDS`; the flip
  re-points them at `CORE_PROFILE`.
- Absorb and delete the transitional `CORE_KINDS` manifest (`science_model/kinds.py`)
  and relocate the `EntityFilenameStrategy` Literal into `profiles/schema.py` (§0.1).

**Non-goals (explicit)**
- No dynamic or generated `EntityType` — it stays a hand-written `StrEnum`
  enforced by a drift test (preserves `EntityType.TASK` static refs + IDE/type
  checking across ~50 files).
- No codegen tooling. (Reconsiderable later, once the descriptor shape is stable.)
- No collapse of the registry's *resolution* machinery beyond moving per-kind
  *metadata* into the descriptor. Kind → Pydantic-model binding stays in code.
- "JSON-schema mixins" from the kernel overview is dropped: there is no real
  entity-kind mixin surface (only dataset/DAG-specific `.model_json_schema()`
  exports). Recorded here so the omission is deliberate.
- No Source-Compiler / structured-source redesign — that is Spec 3. If the
  `curation-sweep` audit (§4) concludes it is a source/ledger artifact rather
  than an authored kind, this spec only documents + categorizes it.

---

## 2. The descriptor model

### 2.1 Extended `EntityKind` (`science_model/profiles/schema.py`)

`EntityKind` becomes the full per-kind fact record. It already has `name`,
`canonical_prefix`, `layer`, `description`, and optional
`entity_class`/`home`/`strategy`/`default_status`/`statuses`/`structured_source`.
Changes:

- **`entity_class` becomes typed** `EntityClass` (was `str | None`). Absorbs the
  registry's `_CORE_KIND_CLASSES` facts. `EntityClass` is load-bearing for
  freshness/review propagation, so stringly-typing it in the manifest invites the
  exact drift this spec removes.
- **`category`** (new, typed `KindCategory`): `authored-core | reserved |
  source-only`. The named-contract taxonomy (§2.3).
- **`template_ready`** (new, `bool`): "this kind ships a packaged markdown
  template." Replaces membership in `MIGRATED_KINDS`. (Named for what it *is*,
  not the migration that produced it.)
- **`shortform`** (new, `str | None`): the single-letter CLI alias (e.g. `h` →
  `hypothesis`). Absorbs `_SHORTFORM_ENTITY_KINDS` (the fourth tool map the keystone
  derived from `CORE_KINDS`). Derivation filters on *presence*, not `category`, since a
  few non-markdown kinds also carry one; the gate requires each `shortform` unique and
  single-character.
- **`strategy` becomes typed** `EntityFilenameStrategy | None` (was `str | None`),
  absorbing the Literal relocated from `science_model/kinds.py` (§0.1). Full vocabulary:
  `numeric | citekey | singleton | slug | verbatim`.
- **`home` / `strategy` / `default_status` / `statuses` / `shortform` are populated for
  every authored-core kind** (most are blank today), so the markdown path/status/shortform
  maps can derive from them — sourced from the keystone's verified `CORE_KINDS` values (§0.1).
- **`structured_source` stays a loader/source field, orthogonal to `category`.**
  A genuine authored-core kind may still carry structured-source rows via the
  existing `CoreStructuredSource` mechanism. `source-only` (§2.3) is a *semantic
  category*, not the source mechanism.

### 2.2 `EntityClass` placement

Define `EntityClass` in the existing leaf module `science_model/identity.py`
(which already hosts sibling enums `EntityScope` / `ExternalId`), and **keep a
plain re-export from `science_model/entities.py`** (`from science_model.identity
import EntityClass`, listed in `__all__`). `profiles/schema.py` imports it from
`identity.py`. This is cycle-free (`identity.py` is a leaf; `entities.py` does
not import `profiles`) and keeps `profiles/schema.py` lightweight rather than
coupling it to `entities.py`'s heavy transitive imports.

The re-export is the deliberate **stable public path**: existing
`from science_model.entities import EntityClass` sites keep working unchanged, so
Task 1 is genuinely behavior-neutral. (This is a normal public re-export, not a
deprecated compatibility shim — `entities.py` stays a legitimate export surface.)

### 2.3 Kind categories — named contracts, not an allowlist

`KindCategory` (new typed enum in `science_model`):

- **`authored-core`**: full descriptor in `CORE_PROFILE.entity_kinds`; the
  user-authored markdown core. The drift test enforces 3-way equality on exactly
  this set. Path/status/template derivation applies **only** to this category.
- **`reserved`**: built-in sentinel/compatibility kinds — `unknown` (and any pure
  marker). Today `unknown` has **no manifest descriptor** (it is enum + registry
  only). It gains a descriptor in `CORE_PROFILE` with `category=reserved` (it is a
  built-in sentinel, not project-local, so this does not affect profile
  shadowing). Present in `EntityType`, but **excluded** from authored-core
  equality and from all markdown derivation. Pinned by a dedicated named test.
- **`source-only`**: valid entity kinds that are *not* authored markdown core —
  loaded by other means (source rows) — `model`, `canonical_parameter`, and
  `parameter_binding`. These already live in `LOCAL_PROFILE` and **stay there**
  (moving them to `CORE_PROFILE` would change profile/shadowing semantics). The
  change to `LOCAL_PROFILE` is additive only: each gains `category=source-only`.
  Excluded from markdown derivation; each pinned by a named test. Distinct from
  the `structured_source` loader field.

### 2.3.1 Descriptor ownership summary

The descriptor system spans the **two built-in manifests**:
- `CORE_PROFILE` owns authored-core descriptors **and** reserved sentinels
  (`category` distinguishes them).
- `LOCAL_PROFILE` owns source-only descriptors (unchanged location; gains
  `category` tags only).

`CORE_PROFILE` remains the SSOT for *authored-core* facts; "the descriptor
system" (core + local) is the SSOT for *which kinds exist and their category*.
All markdown derivations (§4) filter `category == authored-core` across both
manifests, so reserved/source-only kinds never receive a path policy, status
vocabulary, or template.

### 2.4 Kind → Pydantic-model binding (the irreducible code)

The only per-kind fact that cannot be data is the bound Pydantic class. A
minimal `CORE_KIND_MODELS: dict[str, type[Entity]]` map lives in
**`science_tool/graph/entity_registry.py`** (not `science_model`), so the model
layer is not tightened around tool-registry imports. It lists the ~dozen typed
kinds (`TaskEntity`, `DatasetEntity`, `PaperEntity`, `BookEntity`,
`InquiryEntity`, `EvidenceLineEntity`, …) and defaults to `Entity` /
`ProjectEntity` for kinds with no typed subclass. The registry composes this
code map with the descriptor metadata (`entity_class`, etc.) — `register_core_kind`
reads `entity_class` from the descriptor instead of the standalone
`_CORE_KIND_CLASSES` map, which is removed.

---

## 3. Reconciliation gate (first task, before any consumer flip)

A per-kind audit classifies every kind in the **full reconciliation universe** —
`EntityType ∪ registry ∪ path policies ∪ status maps ∪ MIGRATED_KINDS`
(50 kinds today) — into `authored-core | reserved | source-only`, plus a
**recommend-retire** annotation for kinds the audit judges dead. The universe must
include the map-only kinds (`decision`, `claim-registry`), or the later "derived
equals prior literal" equivalence tests (§4) would break on kinds the gate never
saw.

**This slice is behavior-neutral: it classifies and reconciles, it does not
remove kinds.** Every kind currently present in any surface gets a descriptor
with a `category` (so the derived maps reproduce the current literals exactly).
Kinds the audit recommends retiring are *recorded* here but actually removed in a
**separate, explicitly behavior-changing cleanup slice** with its own tests — so
the §4 value-for-value equivalence claim stays true for this slice. (See §10.)

**Strict drift tests — split by layer to honor `science_model` ⊅ `science_tool`:**

*Model-package tests* (`science/model/tests/`, manifest + enum + category only):
1. `authored-core descriptors ≡ EntityType core projection` (enum minus
   reserved/source-only).
2. **No unclassified enum value** is allowed: every `EntityType` member maps to
   exactly one `KindCategory`.
3. Reserved (`unknown`) and source-only (`model`, `canonical_parameter`,
   `parameter_binding`) descriptors carry the right `category` and are excluded
   from the authored-core projection — each pinned by its own named test (named
   contracts, not a tolerated allowlist).

*Tool/root-suite tests* (`science/tests/`, may import the registry + tool maps):
4. `authored-core descriptors ≡ registry authored-core registered kinds`.

This gate lands green before any derived consumer is changed, so subsequent flips
operate on a reconciled set.

### 3.1 Audit seeds (initial rulings, finalized during the gate task)

- **authored-core** (author full descriptors): `dataset`, `discussion`,
  `inquiry`, `patch-definition`, `plan`, `report`, `synthesis`, `topic`,
  `variable`, `assumption`, `transformation`, `article`, `search`, `spec`,
  `research-package`, `validation-report`, `construct`, `outcome`,
  `pre-registration`, `research-question`, `structural-chain`, `chain-audit`
  (plus the 21 already-agreeing kinds).
- **reserved**: `unknown`.
- **source-only**: `model`, `canonical_parameter`, `parameter_binding` (all
  currently in `LOCAL_PROFILE`; tied to source-row loading).
- **needs ruling**: `curation-sweep` — determine whether it is a real authored
  entity kind or a ledger/source artifact that should compile as an
  artifact/source record (Spec 3). If the latter, document + categorize only;
  do not redesign loading here.
- **map-only, needs ruling**: `decision`, `claim-registry` — present only in the
  path/status maps. In this behavior-neutral slice each is **promoted**: author a
  descriptor carrying its *current* path/status values, add the enum member, and
  register it (so the derived maps still match the literals). If the audit judges
  one genuinely dead, that is recorded as a retire recommendation and executed in
  the separate cleanup slice — not removed here.

---

## 4. Derivation (after the gate is green)

Public accessors stay byte-for-byte identical — `entity_policies()`,
`default_status()`, `valid_statuses()`, shortform expansion, `MIGRATED_KINDS`
membership — only their *internals* flip to compute from the descriptor system
(which, for authored-core kinds, currently means `CORE_PROFILE`). The markdown
maps filter to `category == authored-core`; shortform filters on *presence*;
`entity_class` spans every classified kind (so reserved/source-only carry one too):

- `_BUILTIN_MARKDOWN_POLICIES` ← authored-core descriptor `home` + `strategy`.
- `_DEFAULT_STATUS` ← authored-core descriptor `default_status`.
- `_STATUS_VALUES` ← authored-core descriptor `statuses`.
- `_SHORTFORM_ENTITY_KINDS` ← `{d.shortform: d.name for d in descriptors if d.shortform}`
  (all kinds, not filtered by `category`).
- `MIGRATED_KINDS` ← `{name for authored-core if template_ready}`.
- registry `entity_class` ← descriptor `entity_class` (standalone
  `_CORE_KIND_CLASSES` removed).

These five flips replace the keystone's single `CORE_KINDS`-derivation guard; the
last task then deletes `science_model/kinds.py` and repoints the
`EntityFilenameStrategy` import (§0.1).

Each flip ships a **transitional equivalence test** asserting the derived map
equals the current hand-written map value-for-value (captured *before* the
refactor). These are the safety net for the broad `EntityType` (~50 files) /
registry (~18 files) coupling and prove zero behavior change.

(`valid_statuses()` already falls back to `EntityKind.statuses`; this generalizes
that pattern to the full set rather than introducing a new mechanism.)

---

## 5. Layering & file structure

- **`science_model`** owns the SSOT:
  - `profiles/schema.py` — extended `EntityKind` (typed `entity_class`,
    `category`, `template_ready`, `shortform`, typed `strategy`), `KindCategory`
    enum, the relocated `EntityFilenameStrategy` Literal (§0.1), imports `EntityClass`.
  - `profiles/core.py` — fully populated `CORE_PROFILE` (authored-core + reserved
    sentinels).
  - `profiles/local.py` — `LOCAL_PROFILE` gains `category=source-only` tags
    (no kinds moved).
  - `identity.py` — `EntityClass` (definition lives here).
  - `entities.py` — static `EntityType` enum (unchanged shape) + plain
    `EntityClass` re-export (stable public path).
  - `kinds.py` — **deleted** at the final task (`CORE_KINDS` absorbed into
    `EntityKind`; `EntityFilenameStrategy` relocated to `schema.py`). Until then it
    re-exports the Literal from `schema.py` so intermediate flips stay neutral.
  - model-package drift/contract tests (assertions 1–3 of §3); the keystone's
    `model/tests/test_kinds.py` is removed once §3's gate supersedes it.
- **`science_tool`** consumes/derives:
  - `graph/entity_registry.py` — `CORE_KIND_MODELS` code map; reads
    `entity_class` from descriptor.
  - `entities.py` — `_BUILTIN_MARKDOWN_POLICIES` / `_DEFAULT_STATUS` /
    `_STATUS_VALUES` / `_SHORTFORM_ENTITY_KINDS` become thin derivations over
    `CORE_PROFILE` (re-pointed off `CORE_KINDS`); imports `EntityFilenameStrategy`
    from `science_model.profiles.schema` after the final task.
  - tool/root-suite tests: assertion 4 of §3 (manifest ≡ registry) + the
    per-flip equivalence tests for the tool-layer maps; the keystone's
    `tests/test_kind_descriptor_derivation.py` is replaced by those equivalence tests.
  - (`templates.py` lives in `science_model`) — `MIGRATED_KINDS` derives from the
    manifest (its equivalence test is a model-package test).

Tool → model dependency direction is preserved throughout; no test makes
`science_model` import `science_tool`.

---

## 6. Phasing (single implementation plan, ~7 tasks)

1. Extend `EntityKind` schema (typed `entity_class`, `category`, `template_ready`,
   `shortform`, typed `strategy`) + `KindCategory` enum; relocate
   `EntityFilenameStrategy` into `schema.py` with `kinds.py` re-exporting it; define
   `EntityClass` in `identity.py` with a plain re-export from `entities.py`; add
   `CORE_KIND_MODELS` scaffold in the registry. Behavior-neutral (re-exports keep
   existing imports working).
2. Audit the full 50-kind universe + populate `CORE_PROFILE` (authored-core +
   reserved sentinels) and tag `LOCAL_PROFILE` (source-only); rule on
   `curation-sweep` and the map-only kinds (`decision`, `claim-registry`). Source
   authored-core `home`/`strategy`/`default_status`/`statuses`/`shortform` from the
   keystone's verified `CORE_KINDS` values (§0.1).
3. **Reconciliation drift tests (the gate)** — strict, split by layer
   (§3 assertions 1–3 model-package, 4 tool/root); green once 1 + 2 land.
4. Derive path policies + shortform map (+ equivalence tests).
5. Derive status map + status vocab (+ equivalence tests).
6. Derive `MIGRATED_KINDS` + registry `entity_class` (+ equivalence tests).
7. Remove the now-superseded hand-written map literals (e.g. `_CORE_KIND_CLASSES`)
   **and delete `science_model/kinds.py`** (`CORE_KINDS`/`KindDescriptor`): repoint the
   tool's `EntityFilenameStrategy` import to `schema.py`, replace the keystone's two
   test files with this slice's gate + equivalence tests — not kinds; full suite + ruff.

---

## 7. Testing strategy

- **Drift tests, split by layer** (§3): assertions 1–3 are model-package tests
  (manifest + enum + category only); assertion 4 (manifest ≡ registry) lives in
  the tool/root suite so `science_model` never imports `science_tool`.
- **Named contract tests**: one per reserved / source-only kind, asserting its
  category and its exclusion from authored-core equality.
- **Per-flip equivalence tests**: derived map ≡ prior literal (captured before
  refactor) for path policies, shortform map, status map, status vocab,
  `MIGRATED_KINDS`, registry `entity_class`. These collectively **replace** the
  keystone's `CORE_KINDS`-derivation guard (`tests/test_kind_descriptor_derivation.py`)
  and self-consistency suite (`model/tests/test_kinds.py`), which are removed with
  `kinds.py` — no coverage is lost (§0.1).
- **Full suite + ruff** as the final gate (the existing ~5400-test suite covers
  the broad consumers).

---

## 8. Risks

- **Coupling breadth** (`EntityType` ~50 files, registry ~18) — mitigated by
  keeping `EntityType` static and changing only map internals behind stable
  accessors.
- **Audit surfaces genuinely-dead kinds** — handled by an explicit `retire`
  ruling per orphan (removed, not enshrined); the strict gate forbids silent
  carry-over.
- **Derivation must reproduce current values exactly** — mitigated by capturing
  current map values into equivalence tests *before* refactoring.
- **`curation-sweep` could pull in Spec 3 scope** — capped: if it is a
  source/ledger artifact, only document + categorize; do not redesign loading.
- **`EntityClass` relocation** — behavior-neutral: the definition moves to
  `identity.py` but `entities.py` keeps a plain re-export (stable public path), so
  existing `from science_model.entities import EntityClass` imports are unaffected.
- **Absorbing/deleting `CORE_KINDS`** — low risk: the authored-core descriptor values
  are copied from `CORE_KINDS` (already verbatim-verified against the original literals
  by the keystone guard), the `EntityFilenameStrategy` relocation routes through a
  transitional re-export, and the per-flip equivalence tests re-prove value-for-value
  equality before `kinds.py` is removed. Net: the keystone's guarantees are preserved,
  not re-derived from scratch.

---

## 9. Success criteria

- `CORE_PROFILE` is the single authored source of core-kind facts; path policies,
  status map, status vocab, shortform map, `MIGRATED_KINDS`, and registry
  `entity_class` all derive from it. The transitional `CORE_KINDS` manifest
  (`science_model/kinds.py`) is deleted; `EntityFilenameStrategy` lives in
  `profiles/schema.py`.
- The four strict drift assertions hold; every `EntityType` member is classified;
  reserved / source-only kinds are named contracts with dedicated tests.
- `EntityType` remains a hand-written static enum; no codegen introduced.
- Full suite + ruff green; per-flip equivalence tests prove zero behavior change.

---

## 10. Deferred (follow-on specs / later slices)

- **Dead-kind retirement cleanup** — a separate, explicitly behavior-changing
  slice that removes kinds the §3 audit recommends retiring (from maps, enum,
  registry, descriptors) with its own before/after tests. Kept out of this
  behavior-neutral slice so the value-for-value equivalence guarantee holds.
- Codegen of `EntityType` from the manifest (tooling improvement once the
  descriptor shape is stable).
- Deeper collapse of the registry's resolution machinery.
- Structured-source / source-compiler unification (Spec 3), incl. any
  `curation-sweep` reclassification as a source artifact.
- Relation-kind descriptor consolidation (the manifest already holds
  `relation_kinds`; not touched here).
