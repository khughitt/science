# BeliefPolicy keystone — design (patchwork kernel Spec 5, Slice A)

> Patchwork kernel **Spec 5 — Proposition, Evidence, and Belief Semantics**, keystone slice.
> Scope locked to **built-in default policy only** (no project-selectable policies, no
> per-branch parameterization, no scalar unification, no weighting-semantics change).

## Goal

Make the belief policy **explicit, versioned, recorded, and comparable** by extracting
today's implicit aggregation knobs into a single frozen `BeliefPolicy` object, threading
it through `aggregate_belief`, recording its identity on every `BeliefResult` and in
persisted belief records, and refusing to combine belief results computed under different
policies. The extraction is **behavior-neutral**: the one built-in `DEFAULT_BELIEF_POLICY`
reproduces today's `aggregate_belief` output exactly.

This slice creates the socket that later Spec 5 slices (typed evidence vocabularies,
authored-confidence-as-input, dataset-QA seam, proposition-as-edge) plug into. It changes
no belief math.

## Architecture

The belief engine already produces a structured `BeliefResult`
(`science/src/science_tool/graph/belief.py:253`); aggregation rules live as module-level
constants in `belief_weights.py` plus literals inside `aggregate_belief` /
`is_decisive_refutation`. We lift those constants into a frozen `BeliefPolicy`, give
`aggregate_belief` a keyword-only `policy` parameter defaulting to `DEFAULT_BELIEF_POLICY`,
and have the helpers read knobs from the policy instead of module globals. Because the
parameter is keyword-only with a default, **none of the ~9 external call sites change** and
the change is provably behavior-neutral.

`DEFAULT_BELIEF_POLICY` is built **from** the existing `belief_weights.py` constants, so
there is a single source of truth for the values — no duplication, no divergence risk with
the Phase-2 scalar that still reads those globals.

## Components & files

### New: `graph/belief_policy.py`

`BeliefPolicy` — a frozen dataclass holding **only today's implicit knobs**:

- rank tables: `evidence_type_rank`, `evidence_role_rank`, `strength_rank`
- reduction / vocabulary constants: `gated_proxy`, `diagnostic_roles`, the independence
  tokens (`independent`, `shared_source`, `circular`), `scope_whole_claim`
- magnitude thresholds: the literals currently inside `aggregate_belief`
  (`0 → SPECULATIVE`, `1 → FRAGILE`, `2+ clean support WITH a direct_test → WELL_SUPPORTED`,
  else `SUPPORTED`)
- refutation-cap conditions: the predicate constants from `is_decisive_refutation`
  (independent + strong + direct_test + whole_claim)
- identity: `policy_id: str`, `version: str`

**Immutability must be real** (frozen dataclass alone does not deep-freeze container
fields). The mapping fields are stored as read-only mappings — `Mapping[str, int]` backed by
`types.MappingProxyType` over a private copy — and the token-set fields are `frozenset`.
The constructor normalizes any incoming `dict`/`set` into these immutable forms so a caller
cannot mutate a policy's tables after construction.

`DEFAULT_BELIEF_POLICY` — the single built-in policy, constructed from the
`belief_weights.py` constants, with `policy_id="core-default"`, `version="1"`. It must
reproduce today's `aggregate_belief` output exactly.

`belief_policy.py` imports only from `belief_weights.py` (which imports nothing internal),
so it sits below `belief.py` in the import graph — no cycle.

### Modify: `graph/belief.py`

- `aggregate_belief(units, *, policy: BeliefPolicy = DEFAULT_BELIEF_POLICY) -> BeliefResult`.
  Thread `policy` through the helpers that read the constants — `reduce_units`,
  `is_decisive_refutation`, `quality_key`, `is_proxy_gated`, `is_diagnostic`, and the
  ordinal `*_steps` reads — so they consume policy fields rather than module globals.
- `BeliefResult` gains `policy_id: str` and `policy_version: str`, **with defaults sourced
  from `DEFAULT_BELIEF_POLICY`** (`policy_id = DEFAULT_BELIEF_POLICY.policy_id`,
  `policy_version = DEFAULT_BELIEF_POLICY.version`). `aggregate_belief` sets them explicitly
  from its `policy` argument; the default covers direct constructors (e.g. the
  `test_bundle_belief_rollup.py:21` helper) so no call-site edit is forced. Confirmed no
  import cycle: `belief.py` already imports `DEFAULT_BELIEF_POLICY` for the parameter
  default.

### Modify: `graph/bundle_belief.py`

- `roll_up_weakest_link` adds the **comparability guard**: if the members do not all share
  the same `(policy_id, policy_version)`, raise `MixedBeliefPolicyError(ValueError)`. On
  success the `BundleBeliefResult` is stamped with the shared `policy_id` / `policy_version`
  (new fields on `BundleBeliefResult`). This is latent today — every member in a single
  build uses `DEFAULT_BELIEF_POLICY` — but it is the invariant federation / multi-policy
  views require, and it fails loudly rather than silently averaging across policies.

### Modify: persistence (two surfaces)

These are the only two places a belief result's identity escapes the engine today.

- `graph/belief_snapshot.py` `snapshot_records()` — add `policy_id` / `policy_version` to
  both row branches (the `BundleBeliefResult` branch and the single-claim `BeliefResult`
  branch) of the JSONL belief history. The snapshot `_key` (dedup identity) is unchanged;
  the policy fields are additive row content.
- `model/patch.py` — emit `SCI_NS.beliefPolicyId` and `SCI_NS.beliefPolicyVersion`
  alongside the existing `SCI_NS.beliefMagnitude` patch-summary triples (the only place
  belief identity reaches RDF today).

## Boundary (explicit, deferred)

- The **Phase-2 log-odds scalar** (`belief_scalar.py`, `DELTA_ENVELOPE`, `CONFIG_VERSION`)
  is **not** folded into `BeliefPolicy`. It is a separate projection with its own version
  stamp; unifying the two version identities is a later slice. `belief_weights.py` globals
  stay in place (the scalar still reads them), and `DEFAULT_BELIEF_POLICY` is built from the
  same globals, so the two cannot diverge.
- Deferred entirely: project-authored / selectable policies; dormant `agent` / `trust` /
  authored-confidence fields; full per-branch parameterization into data; any change to
  evidence weighting semantics.

## Testing (TDD, behavior-neutral)

1. **Behavior-neutral equivalence:** for representative unit sets,
   `aggregate_belief(units) == aggregate_belief(units, policy=DEFAULT_BELIEF_POLICY)`, and
   the **entire existing belief suite stays green** (`test_belief_aggregate`,
   `test_belief_collect`, `test_belief_reduce`, `test_belief_refutation`,
   `test_belief_scalar*`, `test_belief_e2e`, `test_bundle_belief_rollup`,
   `test_evidence_line_belief_checks`, `test_epistemic_edges_e2e`) — the real regression net.
2. **Stamping:** `aggregate_belief(units).policy_id == "core-default"` and
   `.policy_version == "1"`.
3. **Seam proof (not decorative):** a policy derived from the default but with one knob
   changed (e.g. a magnitude threshold, or a rank-table entry) produces a *different*
   `aggregate_belief` result than the default on a crafted unit set — proving the knob is
   actually read — while `DEFAULT_BELIEF_POLICY` is untouched.
4. **Immutability:** attempting to mutate a policy's rank table
   (`policy.evidence_type_rank["x"] = 9`) raises (`TypeError` from the read-only mapping);
   the token-set fields are `frozenset`.
5. **Comparability guard:** `roll_up_weakest_link` with members of differing policy identity
   raises `MixedBeliefPolicyError`; with a shared identity it succeeds and the
   `BundleBeliefResult` carries that `policy_id` / `policy_version`.
6. **Persistence:** snapshot rows (both branches) carry `policy_id` / `policy_version`, and
   the patch RDF summary carries `SCI_NS.beliefPolicyId` / `SCI_NS.beliefPolicyVersion`.

## Success criteria

- Belief policy is a single explicit, versioned, deeply-immutable object.
- Every `BeliefResult` and every persisted belief record (snapshot JSONL + patch RDF)
  records the policy identity that produced it.
- Belief results computed under different policies cannot be silently combined.
- No behavior change: the full existing suite is green and the default reproduces today's
  output exactly.
