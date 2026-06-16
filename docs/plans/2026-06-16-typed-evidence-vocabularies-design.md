# Typed Evidence Vocabularies — Design (patchwork kernel Spec 5)

**Status:** approved (design review 2026-06-16).
**Builds on:** the BeliefPolicy keystone (Spec 5 Slice A) and Authored-Confidence-as-Input (Slice B). See `docs/plans/2026-06-16-belief-policy-keystone-design.md` and `docs/plans/2026-06-16-authored-confidence-design.md`. Kernel context: `docs/plans/2026-06-14-patchwork-kernel-architecture-design.md` §Spec 5 ("type evidence vocabularies").

## Goal

Collapse the duplicated evidence vocabularies onto **one typed SSOT**: the **model enums own the vocabulary**, and the **tool's ordinal ranks reconcile against them** through a build gate. Fill the single remaining gap — there is no `EvidenceType` enum and `EvidenceLineEntity.evidence_type` is a bare `str`, while `evidence_role`, `strength`, `independence`, and `dispute_scope` on that same entity are already typed enums.

Scope is the **three belief-scoring vocabularies**: `evidence_type`, `evidence_role`, `strength`. The already-typed, non-rank-bearing vocabularies (`independence`, `dispute_scope`, `proxy_directness`) are out of scope (§Boundary).

## Current state (the duplication)

- **Model** (`science_model/reasoning.py`) defines `StrEnum`s for `EvidenceRole`, `EvidenceStance`, `EvidenceStrength`, `IndependenceTag`, `DisputeScope`, `ProxyDirectness`. There is **no `EvidenceType`**.
- **`EvidenceLineEntity`** (`science_model/entities.py`) types `evidence_role: EvidenceRole`, `strength: EvidenceStrength`, `independence: IndependenceTag`, `dispute_scope: DisputeScope` — but `evidence_type: str | None` (untyped).
- **`belief_weights.py`** (tool) re-declares the same tokens as bare string constants (`ROLE_DIRECT_TEST = "direct_test"`, …) and rank dicts (`EVIDENCE_TYPE_RANK`, `EVIDENCE_ROLE_RANK`, `STRENGTH_RANK`) with **no linkage** back to the model enums — drift-prone.

The canonical `evidence_type` value set is confirmed by both `EVIDENCE_TYPE_RANK` and `model/templates/proposition.md`: `empirical_data`, `benchmark`, `simulation`, `literature`, `expert_judgment` (authored with an `_evidence` suffix for all but `expert_judgment`).

## §1 Vocabulary SSOT (model)

Add to `science_model/reasoning.py`:

```python
class EvidenceType(StrEnum):
    """Category of evidence backing an evidence line (normalized token form)."""
    EMPIRICAL_DATA = "empirical_data"
    BENCHMARK = "benchmark"
    SIMULATION = "simulation"
    LITERATURE = "literature"
    EXPERT_JUDGMENT = "expert_judgment"
```

Enum **values are the normalized tokens** (no `_evidence` suffix). `EvidenceRole`/`EvidenceStrength` already exist and are unchanged. The model is now the sole home of the vocabulary tokens for all three in-scope axes.

## §2 Type the field + canonicalize at parse

`EvidenceLineEntity.evidence_type: EvidenceType | None = None`, with a Pydantic `field_validator(mode="before")` that strips the `_evidence` suffix before coercion. Consequences:

- Both authored spellings parse to the same member: `empirical_data_evidence` **and** `empirical_data` → `EvidenceType.EMPIRICAL_DATA`; `expert_judgment_evidence` **and** `expert_judgment` → `EvidenceType.EXPERT_JUDGMENT`.
- **Unknown values raise** at parse (Pydantic enum coercion) — the intended enforcement, exactly matching how `evidence_role` already behaves.
- **No project-data migration is required**: existing suffixed files still parse. This is the deciding advantage of canonicalize-at-parse over enforcing a single strict spelling — strict spelling would force a repo/project migration without adding semantic rigor, because both spellings already denote the same normalized token.
- The **stored/model value is the canonical member**, so the suffix asymmetry disappears at the type boundary.

## §3 Normalization API (explicit shapes, per-layer unknown policy)

There is **one suffix-normalization SSOT (the model)** consumed by two layers with deliberately different unknown-policies:

- **Model — `canonical_evidence_type_token(value: str | None) -> str | None`** (in `reasoning.py`): pure string→string suffix strip (`"x_evidence"` → `"x"`; `None` → `None`). It does **not** validate membership. The `EvidenceLineEntity` validator calls it, then lets Pydantic's `EvidenceType` coercion **raise on unknown**. So "unknown raises" lives at the enum boundary, not in the helper.
- **Tool — `belief_weights.normalize_evidence_type(value: str | None) -> str`** (existing signature retained): delegates the suffix strip to `canonical_evidence_type_token` (single SSOT), returns the token string, and **degrades gracefully** — an unknown token simply falls through to rank 0 via `EVIDENCE_TYPE_RANK.get(token, 0)`. This path reads arbitrary **graph literals** (non-model data), so it must not raise. Behavior is identical to today's `normalize_evidence_type`.

This keeps Slice B's `is_authored_assertion` (which calls `normalize_evidence_type`) working unchanged through the one normalization home.

## §4 Rank reconciliation (tool)

`belief_weights.py` imports the three model enums (tool→model is allowed; no cycle — the earlier "imports nothing internal" note was only about avoiding a `belief.py` cycle *within* the package, not about the lower model layer).

- The rank dicts key off enum members: `EVIDENCE_TYPE_RANK = {EvidenceType.EMPIRICAL_DATA: 4, …}`, etc. Because `StrEnum` members are `str`, lookups by either the member or its string value resolve identically — no call-site churn.
- The loose token constants (`ROLE_DIRECT_TEST`, …) are **sourced from the enum** (`ROLE_DIRECT_TEST = EvidenceRole.DIRECT_TEST`) rather than re-spelled, so the enum is the single source while existing importers (e.g. `belief_policy`) stay byte-for-byte compatible. `DIAGNOSTIC_ROLES`/`GATED_PROXY` are unchanged (`StrEnum` members compare equal to their strings).
- **Reconciliation gate** — an import-time assertion plus tests, mirroring the `MAGNITUDE_NAMES` reconciliation shipped in Slice B. Three precise invariants:
  - **Type:** `set(EVIDENCE_TYPE_RANK) == {m for m in EvidenceType}` (every type ranked; no orphan ranks).
  - **Role:** `set(EVIDENCE_ROLE_RANK) == set(EvidenceRole) - DIAGNOSTIC_ROLES` — exactly the **non-diagnostic** roles are ranked; diagnostic roles (`negative_control`, `model_criticism`) are intentionally unranked, and every `DIAGNOSTIC_ROLES` member must be a valid `EvidenceRole`.
  - **Strength:** `set(STRENGTH_RANK) == {m for m in EvidenceStrength}`.

## §5 Behavior

- **Belief scoring is behavior-neutral on conforming data**: identical ranks → identical magnitudes, snapshots, and scalar bands. No fixture or rank value changes meaning.
- **Representation normalization (intentional, called out):** because the model now stores the canonical member, newly materialized graphs emit `empirical_data` where they previously emitted `empirical_data_evidence` (`str(entity.evidence_type)`). Belief scoring is unaffected (it normalizes anyway), but **materialized provenance literals and human-readable summaries are not guaranteed byte-identical** for projects re-materialized after this slice. This is deliberate vocabulary normalization, not a regression.
- The only new **rejection** is a genuinely-unknown `evidence_type` at parse — the intended enforcement.

## §6 Components & files

Model (`science_model`):
- `reasoning.py` — add `EvidenceType`; add `canonical_evidence_type_token`.
- `entities.py` — type `EvidenceLineEntity.evidence_type` to `EvidenceType | None` + suffix-normalizing `field_validator(mode="before")`.

Tool (`science_tool`):
- `graph/belief_weights.py` — import enums; re-key rank dicts; source token constants from enums; `normalize_evidence_type` delegates to model; add reconciliation assertion.

Tests:
- model tests for `EvidenceType` + the validator (both forms → canonical; unknown raises).
- tool reconciliation tests (3 invariants, like `MAGNITUDE_NAMES`).
- belief regression net for scoring neutrality.
- fixture sweep: any test constructing `EvidenceLineEntity` with a non-canonical or bogus `evidence_type`.

## §7 Testing strategy

- **Red→green per change**, TDD, mirroring the Slice B execution.
- Model: parametrized validator test — `{empirical_data_evidence, empirical_data}` → `EMPIRICAL_DATA`; `{expert_judgment, expert_judgment_evidence}` → `EXPERT_JUDGMENT`; `"bogus"`/`"bogus_evidence"` → `ValidationError`.
- Tool: reconciliation invariants as explicit asserts; `normalize_evidence_type` parity test (same outputs as before for known + unknown tokens); `is_authored_assertion` still recognizes both `expert_judgment` spellings (Slice B contract preserved).
- Full belief + evidence-line regression net (the Slice B net) green.

## §8 Boundary (deferred / out of scope)

- Reconciliation of `independence` / `dispute_scope` / `proxy_directness` — already model-typed, not rank-bearing.
- The descriptor-table enrichment (brainstorming Approach B) — three small vocabularies don't warrant the Kind-Descriptor framework.
- Typing the **tool-internal** `EvidenceUnit.evidence_type` — it is a graph-literal projection, guaranteed canonical upstream once parse enforces the vocabulary; typing it now would expand blast radius for no semantic gain. Stays `str | None` this slice.
- Normalizing the authored `_evidence` suffix convention in project files — unnecessary, since both spellings are accepted and canonicalized at parse.

## Success criteria

1. `EvidenceType` is the sole vocabulary home for evidence types; `belief_weights` token constants/ranks derive from the model enums.
2. `EvidenceLineEntity.evidence_type` is typed and enforced at parse; both authored spellings accepted and stored as the canonical member; unknowns raise.
3. One suffix-normalization SSOT (model), with model-validator-raises vs. tool-reader-degrades policies explicit.
4. Reconciliation gate (assert + 3 tests) keeps rank tables in lock-step with the enums, accounting for unranked diagnostic roles.
5. Belief scoring behavior-neutral on conforming data; the materialized-literal representation change is the one documented, intentional difference.
