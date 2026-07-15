# Non-materializing frontmatter fields — design (fb-2026-07-11-017)

**Status:** design approved; ready for the implementation plan.

**Origin.** This closes the last live defect from the instrument-result convergence
plan. That plan attempted the fix as its Task 6, then **withdrew** it: a flat key
vocabulary either cried wolf (from the loader alone) or legitimized its own founding
bug (tree-wide), because the offending key is *live on one kind and dead on another*.
The plan punted the kind-awareness to "the Kind Descriptor keystone." That keystone now
exists (the D5 authoritative-entity-schema work, merged to local `main` at `537f52c1`),
so the fix is unblocked — with the twist that the specific fact it needs lives *outside*
the schema (see §3).

## 1. The defect

The graph's source of truth for both edges is a `relations:` entry with the corresponding
predicate. The shared `relations:` representation and its admission/materialization are
declared by the `RelationKind` descriptors in `profiles/core.py` (`sci:supersedes` ~688,
`sci:amends` ~719). For supersession specifically, `consolidation.py:12-14` names the
canonical edge (`predicate: sci:supersedes`, authored on the successor) and explicitly
distinguishes it from both top-level `supersedes:` ("silently dropped") and `sci:amends`
("which revises, not replaces"). A **top-level** `supersedes:` / `amends:` frontmatter key
looks authoritative but materializes **zero** triples, silently. Downstream,
`big-picture` derives `provenance_coverage` from these chains, so the silent drop
produces a wrong `thin` rating.

MM30 authored two interpretations in the top-level form; the graph has 0 `sci:supersedes`
triples project-wide. The defect is confirmed **still live after D5**: a schema-2
hypothesis with a stray top-level `supersedes:` loads clean with no warning. The
`unevaluatedProperties: false` referenced in `mixin-hypothesis-1.0.json` is prose inside a
`$comment`, not an enforced schema keyword, so nothing rejects the key at load.

## 2. The check

A new canonical check `check_non_materializing_fields`
(`science/src/science_tool/validate/checks/materialization.py`), registered in
`CANONICAL_CHECK_MODULES`. For each entity markdown under `entities/`, it inspects
**top-level** frontmatter for keys that name a graph relation predicate but are authored
in the flat (non-materializing) form:

| Top-level key | Graph predicate | Illegitimate on |
|---------------|-----------------|-----------------|
| `supersedes`  | `sci:supersedes`| every kind **except `workflow-run`** |
| `amends`      | `sci:amends`    | every kind (no legitimate top-level reader exists) |

**Trigger on presence, not value.** The key `supersedes: null` or `supersedes: []` is
still a finding — the defect is the authoritative-looking *spelling*, independent of
value.

**Message.** Required elements, each asserted by a test: (a) the offending **entity id**;
(b) the offending **key**; (c) the required **`relations:` + predicate** replacement form,
using the current relation field name **`target`** (the schema requires `["predicate",
"target"]`; the withdrawn plan's `object:` spelling is stale). Because the authored value
may be `null`, a list, or an id of any kind, the replacement is **schematic** — it must
**not** echo the authored value or assume the target's kind:

```
interpretation:0001-x: top-level 'supersedes:' materializes no triples and is silently
ignored by the graph. Author it as a relations: entry instead:
  relations:
    - predicate: sci:supersedes
      target: <target-id>
```

## 3. Kind-awareness — the crux

Legitimacy here is **behavioral, not schema-declared.** `workflow-run` carries a real
top-level `supersedes` field *only* because `qa_audit/runs.py:47` reads
`fm.get("supersedes")` for the QA-audit chain. It is **not** a declared field on any kind
descriptor, so "is this a declared field on the kind?" cannot distinguish legitimate from
illegitimate — deriving purely from the D5 schema would falsely flag `workflow-run`.

The faithful encoding is therefore a small explicit **legit-reader set**:

```python
# (kind, key) pairs where a top-level key is a REAL field with a live consumer, so it
# must NOT be flagged. This is a behavioral fact (a reader), not a schema declaration,
# which is exactly why it can't be derived from the kind descriptor.
_LEGIT_TOP_LEVEL: frozenset[tuple[str, str]] = frozenset({
    ("workflow-run", "supersedes"),  # read by qa_audit/runs.py:47 for the QA-audit chain
})
```

Everything in the non-materializing key set is illegitimate unless `(kind, key)` is in
this set. Sole audited toolkit reader of these keys: `qa_audit/runs.py:47`. There is no
legitimate top-level reader of `amends`.

## 4. Severity — unconditional ERROR, outside `kind_severity`

Every applicable finding is an **unconditional ERROR**. This rule judges *whether authored
information has any effect at all* — not whether a kind's status/verdict vocabulary is
certified — so it is **not** routed through the D5 `kind_severity.severity_for_kind`
ratchet. A silent no-op is worse than a wrong value: the author's intent was recorded
nowhere. The finding is unambiguous on every kind the rule applies to.

## 5. Rollout

The check ships in the toolkit. Downstream projects install `science` from a **pinned**
git source, so they pick it up only on their next pin bump — no surprise `validate`
breakage, unlike the D5 status-vocab check that fired across five projects at once.

**In-repo scan is clean.** `meta/entities/` and the static Markdown fixtures carry no
offenders; the only authored top-level occurrence is the *legitimate* `supersedes:` in
`templates/workflow-run.md`, and the QA-audit tests construct workflow-run examples
dynamically. The migration policy — *migrate genuine offenders, never soften the rule* —
therefore stands but requires no corpus edits now. MM30's two interpretations are a
separate migration: bumping MM30's pin only *surfaces* the two errors — MM30 must then
rewrite them into the `relations:` form. That migration is out of scope for this toolkit
change and happens in MM30's repo, alongside or after its pin bump.

## 6. Testing

- `supersedes:` on an interpretation → one ERROR whose message contains the entity id, the
  key, `relations:`, and `sci:supersedes`.
- `amends:` on an interpretation → one ERROR naming the entity id and `sci:amends`.
- The `relations:` form (predicate + target) → clean, no findings.
- `supersedes:` on a `workflow-run` entity → clean (the legit-reader exclusion).
- **`amends:` on a `workflow-run` entity → ERROR.** The exclusion is *pair*-specific
  (`(workflow-run, supersedes)` only), not a blanket pass for the kind.
- **`supersedes: null` on an interpretation → ERROR.** Guards against an implementation
  that tests `fm.get(key) is None` and so misses a valueless key.
- `supersedes: []` (empty list) on an interpretation → still one ERROR (presence, not value).
- A non-vacuity guard: with no offending key present, the check yields nothing — proving
  it can be silent, so the ERROR cases prove it can fire.

## 7. Files

- Create: `science/src/science_tool/validate/checks/materialization.py`
- Modify: `science/src/science_tool/validate/checks/__init__.py` (register `"materialization"`)
- Create: `science/tests/validate/test_checks_materialization.py`

## 8. Out of scope

- The full 23 relation predicates. Only `supersedes`/`amends` have a demonstrated
  top-level-misauthoring failure mode and a `relations:` equivalent; adding the rest would
  be speculative (YAGNI).
- Migrating MM30 (a separate pinned consumer).
- Any change to the graph materialization path — the `relations:` form already works; this
  is purely an authoring-time guard.
