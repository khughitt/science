# Concept Source Ownership Design

**Date:** 2026-07-02

**Status:** Draft for review

## Goal

Clarify what owns concept-like nodes used by inquiry and model workflows:
variables, unknowns, concepts, assumptions, transformations, boundary refs,
flow-edge endpoints, and causal treatment/outcome refs.

This is a contract-first audit. It documents current executable behavior, the
target ownership contract, and the first cleanup slices needed to align docs,
commands, tests, and later schema or CLI behavior. It does not make behavior
changes by itself.

## Problem

Science now has a source-first inquiry path:

- `entities/patches/<slug>.md` with `type: patch-definition` and
  `patch_type: inquiry` owns the authored inquiry profile.
- `science graph build` compiles that source into a dedicated `sci:Inquiry`
  graph and patch-membership view.
- `knowledge/graph.trig` is derived state and is overwritten by graph build.

The remaining ambiguity is concept ownership. Inquiry docs and examples often
need refs such as `concept:<treatment>`, `concept:<input>`, or
`concept:<unknown>`, but the system does not currently provide one coherent
durable authoring path for those refs.

The sharp contradiction:

1. The model declares `concept` as an authored core kind. In
   `science/model/src/science_model/profiles/core.py`, `concept` is
   `AUTHORED_CORE`, has `home="entities/concepts"`, and uses slug identity.
2. The entity writer blocks that path. `science/src/science_tool/entities.py`
   raises `EntityCommandError("Source-authored concepts are not supported; use graph add concept instead")`
   for `kind == "concept"`.
3. `science graph add concept` writes directly to `knowledge/graph.trig`, which
   `science graph build` regenerates from source files.
4. This checkout has no `entities/concepts/` directory, so the model-declared
   home is not exercised by current projects here.

The nearest sibling strengthens the contradiction. `construct` is also an
`AUTHORED_CORE` reference kind, has `home="entities/constructs"`, and uses slug
identity. It is not blocked by the entity writer. The `concept` behavior is
therefore not a broad policy against source-authored reference kinds; it is a
lone special case that diverges from its near-identical sibling.

Therefore, "stable project concept lives in `entities/concepts/*.md`" is a
target contract implied by the model, not current supported CLI behavior.
Guidance must not describe it as an available routine workflow until the CLI
and tests support it.

## Current Executable Behavior

| Item | Current behavior |
|---|---|
| Stable project concept | Core profile declares `entities/concepts`, but `science entity create concept ...` is blocked. Lightweight `concept:*` rows may be loaded from `knowledge/sources/<profile>/terms.yaml` or aggregate sources. |
| Direct concept graph mutation | `science graph add concept ...` writes a node into `knowledge/graph.trig`. It is exploratory/non-durable because graph build overwrites the file. |
| Stable project construct | Core profile declares `entities/constructs`, and the entity writer does not special-case-block `construct`. This makes the `concept` block an internal CLI/model asymmetry rather than a general authored-reference policy. |
| Boundary ref | Authored in `entities/patches/<slug>.md` under `inquiry.boundary_roles`; patch-membership derivation treats it as an existing ref and raises `PatchMembershipError` during graph build if it cannot resolve. |
| Flow-edge endpoint | Authored in `inquiry.flow_edges`; patch-membership derivation treats subject/object refs as existing refs and hard-errors during graph build if they cannot resolve. |
| Flow-edge claim | Authored in `claim_refs`; patch-membership derivation treats each as an existing proposition-like ref and hard-errors during graph build if it cannot resolve. Graph export later warns and skips missing evidence-overlay claim bundles when reading already materialized graph state. |
| Causal treatment/outcome | Authored as `inquiry.treatment` and `inquiry.outcome`; causal profiles require both, and patch-membership derivation treats both as existing refs. Graph export later warns and skips missing treatment/outcome overlay refs when they are absent from exported member nodes. |
| Unknown | Authored as a ref in `inquiry.unknowns`; compiler adds `sci:Unknown` as an additive marker on the referenced existing node. It is not a standalone unknown owner. |
| Assumption | Authored as a structured record in `inquiry.assumptions`; compiler mints an inquiry-local assumption URI and optional provenance. |
| Transformation | Authored as a structured record in `inquiry.transformations`; compiler mints an inquiry-local transformation URI with tool, params, and validation refs. |

The "must resolve" contract is enforced by graph build through patch-membership
derivation, not by every downstream graph reader. Export surfaces should remain
tolerant enough to render partial or older graph state with warnings, but source
authoring guidance should still treat unresolved inquiry endpoint refs as build
errors.

## Target Ownership Contract

The durable contract should distinguish reusable semantic owners from
inquiry-local compiled nodes.

| Item | Durable owner |
|---|---|
| Stable project concept | Either a supported source-owned `concept` record or a lightweight local-profile term row. The model already points at `entities/concepts`; the CLI does not yet support it. |
| Domain concept | The most specific registered domain kind available, such as `gene`, `protein`, `disease`, `pathway`, `method`, or `dataset`. |
| Boundary ref | Existing source ref only. Do not invent a boundary ref inside the inquiry block without a source owner. |
| Flow-edge endpoint | Existing source ref only. Edges connect owned things; they do not create endpoint owners. |
| Flow-edge claim | Existing `proposition:*` ref when the edge is backed by an explicit truth-apt assertion. |
| Causal treatment/outcome | Existing source refs, usually domain kinds or durable project concepts. |
| Unknown | Existing source ref marked as unknown in the inquiry. If the missing thing has no source owner, describe it in prose and defer the marker. |
| Assumption | Inquiry-local record in `entities/patches/<slug>.md`; compiler-minted graph node. Promote to a separate entity only when it becomes a reusable proposition, method, concept, or evidence-bearing claim. |
| Transformation | Inquiry-local record in `entities/patches/<slug>.md`; compiler-minted graph node. Promote to workflow/method/dataset/proposition records only when it needs independent lifecycle, reuse, or evidence. |

This contract preserves the source-first rule while allowing two maturity
levels for concepts:

- **Term row:** lightweight semantic identity in
  `knowledge/sources/<profile>/terms.yaml` when a term is real enough to
  resolve but does not need prose, lifecycle, or relations.
- **Entity owner:** Markdown source record when the concept needs body prose,
  lifecycle status, aliases, source refs, or relationships. The model declares
  this path, but the CLI currently blocks it.

In current live project practice, both concept-specific durable tiers are weak:
`terms.yaml` is exercised here only in tests, and `entities/concepts` has no
active project examples in this checkout. Until one of those paths becomes a
routine supported workflow, the only reliable durable choices for a
concept-like thing are a more specific registered domain/source kind or prose
deferral.

## Design Principles

1. Existing refs first. Inquiry graph fields should select and connect owned
   things; they should not be a hidden entity-authoring surface.
2. Inquiry-local means local. Assumptions and transformations are intentionally
   compiler-minted local nodes unless promoted to a normal entity kind.
3. Unknown is a marker, not a kind. `sci:Unknown` marks an existing unresolved
   variable, confounder, mechanism, or other ref.
4. Direct graph mutation is exploratory. Any `science graph add concept`
   guidance must say it does not survive `science graph build`.
5. Do not invent unsupported entity kinds. Guidance should route to registered
   domain kinds, term rows, supported source entities, or prose deferral.
6. Make contradictions visible. Documentation should name the current
   `concept` CLI/model mismatch until a behavior change resolves it.

## Guidance Implications

### `sketch-model`

The command should keep its source-first posture but should not show
`concept:<input>` placeholders as if they can always be minted during the
sketch. It should explain three cases:

- use an existing source ref when available;
- add a lightweight term row when a local concept needs a resolvable ref and a
  project has a local profile source;
- keep the idea in prose when no supported source owner exists yet.

### `specify-model`

The command can keep direct `science graph add concept` only as an exploratory
inspection path. For specified models, every durable endpoint should resolve
through source-owned refs or local-profile terms, while assumptions and
transformations stay in the patch source.

### `plan-pipeline`

The transformation example should make clear that `inquiry.transformations`
does not create general project concepts. `validated_by` should point to an
existing source ref or be left blank until a real validation artifact exists.

### User Guide

`docs/user-guide/epistemic-model.md` already states the compiler behavior for
boundary roles, flow edges, assumptions, transformations, and unknowns. The
missing durable-doc content is the `concept` mismatch and the maturity ladder
from prose-only term to `terms.yaml` row to source-owned entity.

`docs/user-guide/entities.md` already describes `terms.yaml` as a lightweight
semantic row and says to promote rows when they accumulate prose or lifecycle
work. It should not imply `science entity create concept ...` works until the
CLI supports that path.

## Open Decisions

### 1. Should `science entity create concept ...` be enabled?

The model already declares the path, so enabling it would align behavior with
the core profile. This likely needs tests for path policy, default status,
materialization, health, and archive behavior. It should also update or remove
the explicit block in `entities.py`.

The `construct` sibling suggests this may be a small behavioral slice rather
than a new subsystem: remove the `concept` special case, then prove concept
authoring follows the same source-entity path as other authored-core reference
kinds.

### 2. Should local-profile term authoring get a CLI helper?

Today, `terms.yaml` is a valid lightweight source surface, but routine authoring
appears to be manual. A small helper could make the recommended "term row"
middle state executable without forcing every concept into Markdown.

### 3. Should `graph add concept` be deprecated or relabeled?

The command still has value for exploratory graph work and legacy workflows,
but its help text and command docs should not present it as durable source
authoring. If retained, the CLI should print the same non-durable warning as the
docs.

### 4. Should inquiry validation distinguish missing endpoint owners from
missing optional validation refs?

Boundary refs, flow endpoints, treatment, outcome, and claim refs are
load-bearing. Transformation `validated_by` is useful but may be intentionally
blank while planning. Diagnostics should preserve that difference.

## Recommended First Slice

Keep the first implementation slice docs-and-tests only:

1. Add guard tests that pin the ownership contract:
   - concept source ownership is currently a known mismatch, not silently
     documented as available CLI behavior;
   - `sketch-model`, `specify-model`, and `plan-pipeline` do not present
     unresolved `concept:<...>` placeholders as durable owner creation;
   - generated Codex mirrors stay aligned.
   Use stable anchors and stable sentence assertions, following the existing
   `science/tests/test_user_guide_docs.py` marker/anchor pattern, rather than
   broad prose-scanning tests that fail on harmless reflow.
2. Update `docs/user-guide/epistemic-model.md` with an explicit ownership table
   for inquiry refs and local nodes.
3. Update `docs/user-guide/entities.md` to state the current `concept` mismatch
   and the supported `terms.yaml` lightweight path.
4. Tighten `commands/sketch-model.md`, `commands/specify-model.md`, and
   `commands/plan-pipeline.md` around existing refs, term rows, prose deferral,
   assumptions, transformations, and non-durable graph mutation.
5. Regenerate Codex skills for changed command docs.

## Later Slices

After the docs contract is pinned, choose one behavior path:

- enable `science entity create concept ...` to match the core profile;
- add a `terms.yaml` authoring helper for lightweight local concepts;
- relabel or deprecate `science graph add concept` as exploratory-only;
- add sharper inquiry validation diagnostics for unresolved endpoint owners.

Those behavior changes should be planned separately because they affect source
loading, entity path policy, generated graph semantics, and project migration.

## Non-Goals

- Do not change CLI behavior in the contract document.
- Do not move existing project concept records.
- Do not introduce new entity kinds such as `variable` or `unknown`.
- Do not make inquiry patches a hidden store for reusable project concepts.
- Do not remove `science graph add concept` without a separate deprecation plan.
