# Proposition Reasoning Invalidation Design

**Status:** approved for implementation

## 1. What this is

Writer containment stopped whole-model dumps from erasing curated proposition data. It also
made a smaller pre-existing update defect visible: an owned field omitted by
`render_entity_text(..., exclude_none=True)` is currently interpreted as "preserve the value on
disk." That is correct for optional workbench metadata, but wrong when another owned field makes
the preserved value invalid.

The same update can leave `reasoning_source` claiming that synthesis authored reasoning values
which the workbench subsequently replaced.

This slice fixes those two update semantics. It does not repair the 697-record corpus or decide
the legacy triple's fate.

## 2. Reproduction and root cause

Start with a valid synthesized proposition:

```yaml
predicate: affects
polarity: positive
claim_layer: causal_effect
reasoning_source: llm-synth:m:proposition-synthesize-v1
```

Then compile a workbench row for the same proposition with `predicate: binds`, no `polarity`, and
a different `claim_layer`. The workbench builds a valid `PropositionEntity` with
`polarity=None`. `render_entity_text` omits that `None`, and `render_update` only overwrites owned
keys present in the generated mapping. The persisted result is therefore:

```yaml
predicate: binds
polarity: positive
claim_layer: structural_claim
reasoning_source: llm-synth:m:proposition-synthesize-v1
```

That result has two defects:

1. `PropositionEntity` rejects it because `binds` is sign-less and cannot carry a signed
   polarity.
2. `reasoning_source` still attributes the changed reasoning fields to synthesis.

`certify_persisted` does not catch the first defect because it validates only the durable base
shape, not the merged typed entity.

## 3. Rulings

### 3.1 Missing optional writer values preserve persisted values

An omitted generated key remains a patch omission, not a general deletion request. Changing
`render_update` to delete every absent owned key would erase `legacy_relation_label`,
`legacy_patch`, `legacy_edge_id`, and other optional metadata when a workbench row does not carry
them. It would also change evidence-line update semantics.

Preserve-by-default remains the renderer rule.

### 3.2 Polarity is canonicalized as a predicate dependency

When a workbench row names a sign-less predicate and omits polarity, the lifted proposition uses
`polarity: not_applicable`. This matches the existing synthesis rule and replaces any stale signed
polarity on update. An explicit invalid polarity still fails through `PropositionEntity`.

For a sign-meaningful predicate, omitted polarity continues to fail model construction; the
workbench must supply `positive`, `negative`, or `unsigned`.

### 3.3 A synthesis stamp attests to the current reasoning values

`reasoning_source` means the named synthesizer authored the proposition's current `subject`,
`object`, `predicate`, `polarity`, and `claim_layer`. If the workbench changes any of those five
effective persisted values, it clears the stamp.

An idempotent recompile does not clear the stamp. Changes outside those five fields do not clear
it either.

Clearing the stamp is invalidation authority, not write ownership. The workbench may remove an
attestation invalidated by values it owns, but it may never mint or replace that attestation.
Accordingly, `clear_on_change` and `owned` must be disjoint for every `Ownership`.

### 3.4 Rejected approaches

- Deleting every absent owned key violates preserve-by-default and erases unrelated metadata.
- Special-casing workbench propositions inside `render_update` is a smaller raw diff but hides a
  writer-specific rule in the shared renderer. Conditional invalidation belongs in the existing
  per-writer ownership contract.

## 4. Design

### 4.1 One shared reasoning-field tuple

`dag/entity_frontmatter.py` defines the ordered five-field tuple once as the fields a synthesis
stamp attests to. Synthesis imports it as its candidate/write field set, and workbench proposition
ownership uses it as its invalidation trigger set. This avoids importing `annotation.synthesize`
from the writer module and therefore avoids the existing circular dependency.

The ownership declarations remain beside their writers. Only the field identity shared by the
two writers moves to their common module.

### 4.2 Ownership carries conditional invalidation

`Ownership` gains two empty-by-default sets:

```python
change_triggers: frozenset[str] = frozenset()
clear_on_change: frozenset[str] = frozenset()
```

Only `WORKBENCH_PROPOSITION` sets them:

```python
change_triggers = frozenset(PROPOSITION_REASONING_FIELDS)
clear_on_change = frozenset({"reasoning_source"})
```

`Ownership` construction rejects overlap between `owned` and `clear_on_change`. This preserves
the allowlist's meaning: a writer cannot first write an owned value and then silently delete it.
`reasoning_source` deliberately remains outside `PROPOSITION_OWNED_KEYS`; the workbench can
invalidate it but cannot author it.

No renderer special-cases a writer or entity kind. Synthesis, promotion, and evidence-line
ownership retain empty sets and therefore retain their current behavior.

### 4.3 `render_update` compares effective values

The renderer keeps its present merge order:

1. copy persisted frontmatter except renderer-derived keys;
2. overwrite owned keys that exist in the generated mapping;
3. compare each configured trigger's value in the persisted and effective merged mappings;
4. if any trigger changed, remove every `clear_on_change` key;
5. stamp dates, render, and certify.

The comparison happens after the preserve-by-default merge. Therefore a missing generated field
whose persisted value is retained is not falsely treated as a change.

An absent persisted `polarity` and a newly canonicalized `not_applicable` compare unequal. That
representation change therefore clears an existing stamp. This is the simpler conservative rule:
the persisted reasoning representation changed under the workbench. Corpus measurement found no
sign-less proposition with absent polarity, so it changes no current record.

The unchanged-timestamp probe in `workbench_apply` calls the same renderer. A byte-identical
recompile keeps `reasoning_source`, remains byte-identical, and writes nothing.

### 4.4 Certify the merged typed entity

After parsing the rendered text, `certify_persisted` continues to validate the durable base
shape. It then validates the frontmatter as the same concrete entity type as the writer input.

Typed validation may fill only these six deliberately non-persisted required skeleton keys, and
only when each key is absent from the merged frontmatter:

```python
TYPED_VALIDATION_SKELETON_KEYS = frozenset(
    {"project", "ontology_terms", "related", "source_refs", "content_preview", "file_path"}
)
```

The values come from the already-valid writer entity's JSON-mode dump. Persisted values always
win. No other dump key may enter the validation input: a blanket
`{**entity.model_dump(), **frontmatter}` would certify values that are absent from the file about
to be written.

This fill is load-bearing for evidence lines. Across the seven measured proposition/evidence-line
corpora, all 40 base-valid evidence lines fail raw typed validation because required skeleton
fields are absent; the explicit six-key fill rescues all 40. Proposition defaults already cover
the same fields, but both kinds use the one explicit rule.

This catches relational interlock failures introduced by merging preserved and generated values
before any file is written. No live writer can currently produce such a proposition after the
polarity canonicalization in §3.2; the guard protects future ownership changes. It does not close
unknown project extension fields; the entity models already preserve extras, and project-schema
validation remains responsible for admitting them.

No new error class is needed. A failed typed merge remains a `PersistedShapeError`: the proposed
persisted result is invalid and is not written.

## 5. Scope

**In:** workbench proposition polarity canonicalization; conditional `reasoning_source`
invalidation; typed certification of the merged writer result; focused regressions for compile,
apply, and the shared renderer.

**Out:** general deletion semantics for absent owned keys; explicit-null syntax in workbench
YAML; evidence-line clearing behavior; corpus repair; the legacy triple; mm30 validation triage.
Downstream validation or staleness consumers will observe a missing `reasoning_source` after a
real workbench reasoning change; that is the intended externally visible invalidation, not a
separate migration.

## 6. Tests

The smallest complete regression set is:

1. A workbench update from `affects` / `positive` to `binds` with omitted polarity persists
   `not_applicable`, clears `reasoning_source`, and reloads as `PropositionEntity`.
2. Changing each of the five reasoning fields clears the stamp. A non-reasoning workbench change
   preserves it.
3. An idempotent compile and the apply path's unchanged-timestamp probe preserve the stamp and
   write nothing.
4. A reasoning field omitted by the workbench is preserved through a simultaneous non-reasoning
   change, and the stamp remains. This pins the compare-after-effective-merge ordering.
5. A direct `render_update` test uses an `Ownership` that owns `predicate` but omits `polarity`;
   the stale signed polarity then conflicts with a generated sign-less predicate and typed
   certification raises `PersistedShapeError`. This deliberately exercises a future-ownership
   guard that no live writer can currently trip.
6. An evidence-line render fails raw typed validation on the six skeleton fields, passes writer
   certification through the explicit absent-only fill, and persists none of those skeleton
   values.
7. A writer with empty `change_triggers` clears nothing, pinning unchanged synthesis and
   evidence-line renderer behavior.
8. Constructing an `Ownership` whose `owned` and `clear_on_change` overlap raises immediately.

## 7. Accepted behavior change

A created or updated workbench proposition with a sign-less predicate and omitted polarity now
writes `polarity: not_applicable` instead of omitting or preserving the key. This is the canonical
representation already produced by synthesis and removes the create/update discrepancy. If an
older record ever carries a synthesis stamp with sign-less predicate and absent polarity, adding
the canonical value clears that stamp; the measured population is zero.

No corpus files are changed by this implementation slice.
