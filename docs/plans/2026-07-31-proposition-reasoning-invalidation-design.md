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

### 3.4 Rejected approaches

- Deleting every absent owned key violates preserve-by-default and erases unrelated metadata.
- Special-casing workbench propositions inside `render_update` is a smaller raw diff but hides a
  writer-specific rule in the shared renderer. Conditional invalidation belongs in the existing
  per-writer ownership contract.

## 4. Design

### 4.1 One shared reasoning-field tuple

`dag/entity_frontmatter.py` defines the ordered five-field tuple once. Synthesis imports it as its
candidate/write field set, and workbench proposition ownership uses it as its invalidation trigger
set. This avoids importing `annotation.synthesize` from the writer module and therefore avoids the
existing circular dependency.

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

The unchanged-timestamp probe in `workbench_apply` calls the same renderer. A byte-identical
recompile keeps `reasoning_source`, remains byte-identical, and writes nothing.

### 4.4 Certify the merged typed entity

After parsing the rendered text, `certify_persisted` continues to validate the durable base
shape. It then validates the frontmatter as the same concrete entity type as the writer input,
using the already-constructed entity's model dump to supply non-persisted required skeleton
fields.

This catches relational interlock failures introduced by merging preserved and generated values
before any file is written. It does not close unknown project extension fields; the entity models
already preserve extras, and project-schema validation remains responsible for admitting them.

No new error class is needed. A failed typed merge remains a `PersistedShapeError`: the proposed
persisted result is invalid and is not written.

## 5. Scope

**In:** workbench proposition polarity canonicalization; conditional `reasoning_source`
invalidation; typed certification of the merged writer result; focused regressions for compile,
apply, and the shared renderer.

**Out:** general deletion semantics for absent owned keys; explicit-null syntax in workbench
YAML; evidence-line clearing behavior; corpus repair; the legacy triple; mm30 validation triage.

## 6. Tests

The smallest complete regression set is:

1. A workbench update from `affects` / `positive` to `binds` with omitted polarity persists
   `not_applicable`, clears `reasoning_source`, and reloads as `PropositionEntity`.
2. Changing each of the five reasoning fields clears the stamp. A non-reasoning workbench change
   preserves it.
3. An idempotent compile and the apply path's unchanged-timestamp probe preserve the stamp and
   write nothing.
4. A deliberately invalid merged proposition raises `PersistedShapeError` before writing,
   mutation-certifying the typed validation rather than only asserting the corrected polarity.
5. Existing synthesis containment and evidence-line preservation tests remain green.

## 7. Accepted behavior change

A newly created workbench proposition with a sign-less predicate and omitted polarity now writes
`polarity: not_applicable` instead of omitting the key. This is the canonical representation
already produced by synthesis and removes the create/update discrepancy.

No corpus files are changed by this implementation slice.
