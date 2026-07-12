# D5 — Entity Schema Convergence: Implementation Plan

> **rev 2.** Rev 1 was reviewed and **rejected as not executable**. Seven contract defects, all
> confirmed. The rev-7 mapping (§"What the corpus says") is unchanged and stands; everything
> around it was rebuilt. See "What rev 1 got wrong" at the end — it is the most useful section
> here, because three of the seven were *design-phasing* errors, not typos.

> **For agentic workers:** implement task-by-task. Steps use checkbox (`- [ ]`) syntax.
> **Every task ends green.** A task that ends with a red suite is a broken task, not a slice.

**Goal:** Make one authoritative, versioned, composable JSON Schema the source of truth for a
project-authored entity kind — and migrate `hypothesis` onto it, splitting the collapsed `status`
into a lifecycle (`status`) and an epistemic conclusion (`verdict`) without fabricating a fact.

**Architecture:** Converge on the schema system that **already exists** (commons'
`entity_schema`: `schema_profile` → `allOf` → Draft 2020-12). Do **not** invent a second one.
Project kinds join via a new **base 2.0** plus a per-kind mixin. Pydantic becomes a *projection*
taken after schema validation — **never a second authority**.

**Tech stack:** Python 3.12+, Pydantic v2, `jsonschema` (Draft 2020-12), Click, `uv`, pytest, rdflib.

**Contract inputs (ruled, not proposals):**
- [`2026-07-12-authoritative-entity-schema-design.md`](2026-07-12-authoritative-entity-schema-design.md) rev 7 — **§7.3, §7.4, §8 (phasing), §9 (D1–D5), §10 rev 7.**
- [`2026-07-12-d4-status-vocabulary-audit.md`](2026-07-12-d4-status-vocabulary-audit.md).

---

## Global constraints

Apply to **every** task; not restated per-task.

1. **No "legacy"/"compatibility" layer.** No heuristic dual-read of `status`.
   **A *versioned* boundary is not a compatibility layer.** The forbidden thing is code that
   *guesses* which meaning applies. An explicit, authored version pin that *declares* it is
   exactly what D5 requires ("introduce target schema versions"). That distinction is what makes
   Task 8's per-project rollout legal — and it is the only reason it is.
2. **Never fabricate a fact.** Write only derivable values. Otherwise **refuse the file, report
   it, exit non-zero.** Traps: no mechanical `disposition: closed` → `retired`; `status: archived`
   has already destroyed its verdict (leave `verdict` **absent**, report the loss); `paper`'s
   `paywalled`/`preprint`/`stub`/`background` are **not** reading states.
3. **Fail early, no silent fallbacks. Composition over inheritance. Explicit over defensive.**
4. **No AI-attribution trailer** on commits or PRs. Use `~/d/` in docs/code.
5. **Run from the package dir** (no root `pyproject.toml`):
   `cd science && uv run --frozen pytest && uv run ruff check && uv run pyright`;
   `cd science/model && uv run --frozen pytest`.
6. **A check that only fires on downstream data MUST be run against downstream data before
   shipping.** This plan exists because a check was green in CI and broke five projects. The
   toolkit repo has **no `entities/` of its own** — green CI proves nothing here.

**Real APIs (rev 1 invented three modules that do not exist — use these):**
- `science_model.frontmatter`: `split_frontmatter(text) -> (dict, str)`, `parse_frontmatter(path)`, `render_frontmatter(fields, body)`, `atomic_write_text(path, text)`.
- `science_tool.entities`: `find_entity`, `_render_markdown`, `_atomic_replace_text`, `valid_statuses`, `default_status`.
- There is **no** `science_tool/migrations/` package, **no** `science migrate` CLI, **no** `science_tool/frontmatter.py`. Task 7 creates the migration module; register its command on `entity_group` (`cli.py:188`).

**Name collision — read before Task 5.** A `verdict/` subsystem and a `science verdict` CLI group
already exist (`src/science_tool/verdict/`): they parse `**Verdict:** [+]` polarity tokens out of
**interpretation** bodies and roll them up per claim. They **never touch hypotheses**
(`grep hypothesis src/science_tool/verdict/*.py` → nothing), so there is no functional collision —
but do **not** wire the new `hypothesis.verdict` field into that subsystem. They are different
concepts that share a word. *(Open question below: whether they should eventually be related.)*

---

## What the corpus actually says (measured — this part is unchanged from rev 1)

147 authored hypotheses across `~/d/*` (excluding the `natural-systems--t664` worktree dupe),
in **9 repos**: `natural-systems` (14), `r/mm30` (30), `r/cbioportal` (12), `protein-landscape` (7),
`science/meta` (7), `health/meta` (6), `seq-feats` (4), `cancer/therapeutics` (3), `3d-attention-bias` (2).

| `status` × `phase` | n |
|---|---|
| `proposed` + `active` | **60** |
| `proposed` + `candidate` | 36 |
| `proposed` + *(absent)* | 28 |
| `weakened` + `active` | 6 |
| `supported` + *(absent)* | 4 |
| `under-investigation` + *(absent)* | 4 |
| `supported` + `active` | 2 |
| `active` + *(absent)* | 2 *(off-vocabulary)* |
| `weakened`+`candidate`, `active`+`active`, `partially-supported`+*(absent)* | 1 each |
| **`retired` + `candidate`** | **1** ← `natural-systems/0009` |
| *(no status)* | 1 ← test fixture |

**The mapping (design §10 rev 7).** `phase` **is** the lifecycle; `status` was only ever the verdict.

| source | → target |
|---|---|
| `phase: candidate` | `status: draft` |
| `phase: active` **or absent** | `status: active` |
| `status: proposed` \| `under-investigation` | **`verdict` absent** — contributes nothing to lifecycle |
| `status: supported`\|`weakened`\|`partially-supported`\|`refuted` | `verdict: <same>` |

→ **145 deterministic, 2 refused.** `disposition:` is authored on **zero of 147** — deleting it
is free.

## And what rev 1 never looked at: the FIELD vocabulary

**36 distinct authored frontmatter keys** across those 147 files:

```
147 kind, title, id, related · 146 status · 143 created, updated · 128 source_refs · 107 phase
 38 required_capabilities · 33 origins · 31 added_by · 28 lens_views · 22 ontology_terms
 17 datasets · 13 external_hypothesis_id, author_stated_evidence, evidence_stance, belief_state
 12 identification, confidence_label, confidence_mechanistic_label · 11 tags · 8 priority
  6 review_state · 3 profile, description, promoted_from, aliases · 2 role, promotion_criteria,
    domain, confidence · 1 composition_rule, capability_scope, rival_model_packet
```

**This is why strictness cannot ship in the same slice as the value migration.** Closing the
schema (`unevaluatedProperties: false`) against a mixin declaring ~15 keys would reject 20+ keys
on real files. **Declaring this vocabulary IS P0**, and P0 precedes P2m (design §8). Rev 1 skipped
it. Phase 0 below is that work.

---

## Phases

| phase | tasks | changes meaning? | ends with |
|---|---|---|---|
| **0 — Declare the fields (P0)** | 1–2 | **No** | every authored key declared or deleted; schema still open |
| **1 — Certify the mapping** | 3–4 | **No** | inventory + adjudication artifact; writes nothing |
| **2 — Schema substrate (P2)** | 5–7 | **No** | base 2.0, mixin, D3 validator — **wired**, strict, green |
| **3 — The atomic slice (P2m)** | 8–10 | **YES** | all 9 repos migrated, graph-diffed, validate exit 0 |
| **4 — Ratchet (P3)** | 11 | No | `hypothesis` → ERROR |

---

## Phase 0 — Declare the field vocabulary (P0)

### Task 1: `science entity field-inventory` — declare-or-delete

**Files:**
- Create: `science/src/science_tool/field_inventory.py`
- Modify: `science/src/science_tool/entities_cli.py`
- Test: `science/tests/test_field_inventory.py`

**Interfaces:**
- Produces: `field_inventory(project_root: Path, kind: str) -> dict[str, int]` — authored key → file count.
  Task 2 consumes it; Task 11's reconciliation gate re-runs it.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_field_inventory.py
from pathlib import Path

from science_tool.field_inventory import field_inventory


def _write(root: Path, name: str, keys: dict) -> None:
    d = root / "entities" / "hypotheses"
    d.mkdir(parents=True, exist_ok=True)
    fm = "\n".join(f'{k}: "{v}"' for k, v in keys.items())
    (d / f"{name}.md").write_text(f"---\n{fm}\n---\n\nbody\n", encoding="utf-8")


def test_counts_authored_keys_only(tmp_path: Path) -> None:
    _write(tmp_path, "0001-a", {"id": "hypothesis:0001-a", "kind": "hypothesis",
                                "title": "T", "status": "proposed", "phase": "active"})
    _write(tmp_path, "0002-b", {"id": "hypothesis:0002-b", "kind": "hypothesis",
                                "title": "T", "status": "proposed"})
    inv = field_inventory(tmp_path, "hypothesis")
    assert inv["status"] == 2
    assert inv["phase"] == 1
    # Internal/derived fields must NOT appear: this reads AUTHORED frontmatter, never the
    # enriched `raw` dict. `_enrich_raw` (sources.py:713) injects `project`, `canonical_id`,
    # `profile`, `type`, `aliases`, `content_preview` -- none of which any author wrote.
    for derived in ("project", "canonical_id", "content_preview", "aliases", "type"):
        assert derived not in inv


def test_ignores_other_kinds(tmp_path: Path) -> None:
    _write(tmp_path, "0001-a", {"id": "question:1", "kind": "question", "title": "T"})
    assert field_inventory(tmp_path, "hypothesis") == {}
```

- [ ] **Step 2: Run and fail**

```bash
cd science && uv run --frozen pytest tests/test_field_inventory.py -q
```
Expected: `ModuleNotFoundError: No module named 'science_tool.field_inventory'`

- [ ] **Step 3: Implement**

```python
# science/src/science_tool/field_inventory.py
"""Count AUTHORED frontmatter keys per kind, across a project.

Reads the authored frontmatter -- `split_frontmatter` on the file's own bytes -- and NOT the
enriched `raw` dict the graph loader builds. `_enrich_raw` (graph/sources.py:713) injects
`kind`, `type`, `canonical_id`, `profile`, `aliases` and `content_preview` before Pydantic
ever sees the record. Inventorying THAT would declare six fields no author has ever written,
and closing a schema around them would then reject every real file.

This is the P0 "declare or delete" instrument (design §8). It must be run, and its output
adjudicated, BEFORE any schema is closed with `unevaluatedProperties: false`.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from science_model.frontmatter import split_frontmatter

from science_tool.entity_scan import iter_entity_markdown


def field_inventory(project_root: Path, kind: str) -> dict[str, int]:
    entities_root = project_root / "entities"
    if not entities_root.is_dir():
        return {}
    counts: Counter[str] = Counter()
    for path in iter_entity_markdown(entities_root):
        fm, _body = split_frontmatter(path.read_text(encoding="utf-8"))
        if fm.get("kind") != kind:
            continue
        counts.update(fm.keys())
    return dict(counts)
```

- [ ] **Step 4: Green**

```bash
cd science && uv run --frozen pytest tests/test_field_inventory.py -q
```
Expected: `2 passed`

- [ ] **Step 5: Wire a report-only CLI command** on `entity_group`, mirroring Task 3's shape
  (`--json` flag; prints `key  count`). No writes.

- [ ] **Step 6: Run it across all 9 repos and reconcile to the 36-key list above**

```bash
for p in ~/d/natural-systems ~/d/r/mm30 ~/d/r/cbioportal ~/d/protein-landscape \
         ~/d/science/meta ~/d/health/meta ~/d/seq-feats ~/d/cancer/therapeutics ~/d/3d-attention-bias; do
  (cd "$p" && uv run science entity field-inventory --kind hypothesis --json)
done | uv run python -c "import sys,json,collections; c=collections.Counter()
for line in sys.stdin.read().split('\n\n'):
    pass"   # merge however you like; the union must equal the 36 keys listed above
```

**If the union is not exactly those 36 keys, STOP** and update this document. The mixin in Task 6
is generated from this list, and a key missing from it becomes a hard validation failure on real
files the moment Task 6 closes the schema.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/field_inventory.py science/src/science_tool/entities_cli.py science/tests/test_field_inventory.py
git commit -m "feat(entities): field-inventory -- declare-or-delete instrument for P0"
```

---

### Task 2: Adjudicate the 36 keys

**Not a code task — a decision task with a written artifact.** Its output is the property list
Task 6 encodes. Every key gets exactly one disposition:

| disposition | meaning | keys |
|---|---|---|
| **declare** | a real authored field → goes in the mixin | `id`, `kind`, `title`, `status`, `created`, `updated`, `related`, `source_refs`, `origins`, `added_by`, `tags`, `ontology_terms`, `datasets`, `description`, `aliases`, `priority`, `domain`, `role`, `lens_views`, `review_state`, `promoted_from`, `promotion_criteria`, `rival_model_packet`, `external_hypothesis_id`, `identification` |
| **declare (P1 subsystem)** | real, but owned by the capability subsystem the design defers | `required_capabilities`, `capability_scope`, `composition_rule` |
| **declare (belief cluster)** | real, but **see the open question below** | `belief_state`, `evidence_stance`, `author_stated_evidence`, `confidence`, `confidence_label`, `confidence_mechanistic_label` |
| **delete** | folds into `status` (rev 7) | `phase` |
| **derived — must NOT be authored** | `_enrich_raw` sets it | `profile` |

- [ ] **Step 1:** Write `docs/plans/2026-07-12-hypothesis-field-adjudication.md` recording the
  table above with, for each key: its file count, whether any code reads it (grep, and **open every
  hit** — `role`, `datasets`, `priority` collide with ordinary English), and its disposition.
- [ ] **Step 2:** Resolve the two open questions below **with the user**. Both are blocking.
- [ ] **Step 3:** Commit the adjudication doc.

> **⚠️ OPEN QUESTION 1 — the belief cluster may be a second `belief` defect.**
> Six keys (`belief_state`, `evidence_stance`, `author_stated_evidence`, `confidence`,
> `confidence_label`, `confidence_mechanistic_label`, 12–13 files each) look like **authored
> epistemic state on a hypothesis**. Design rev 6 ruled that `proposition.belief` must **not**
> become an authored field, because belief is *derived from evidence lines* and an authored
> field would be a second, hand-editable source of truth for a computed quantity. **The same
> argument may apply to these six.** Declaring them in the mixin would ratify them. **Do not
> declare them until this is ruled.** If they must be preserved for now, declare them with an
> explicit `"$comment": "PROVISIONAL — pending the belief-authority ruling"`.

> **⚠️ OPEN QUESTION 2 — should `hypothesis.verdict` be authored at all?**
> The existing `verdict/` subsystem rolls up interpretation polarities per claim. If a
> hypothesis's verdict is *derivable* from the interpretations bearing on it, then an authored
> `verdict:` field is the `belief` mistake again. **Evidence it is not (yet):** the rollup is
> claim-scoped, never hypothesis-scoped, and 9 files author a verdict today with no derivation
> anywhere. So authored is right **for now** — but the plan must say so deliberately rather than
> by omission, and the field should be revisited when interpretation→hypothesis rollup exists.

---

## Phase 1 — Certify the mapping (report-only)

### Task 3: `science entity status-inventory`

**Files:**
- Create: `science/src/science_tool/status_inventory.py`
- Modify: `science/src/science_tool/entities_cli.py`
- Test: `science/tests/test_status_inventory.py`

**Interfaces:**
- Produces `inventory(project_root, *, adjudication: dict[str, Adjudicated] | None = None) -> StatusInventory`.
  `InventoryRow(path, entity_id, status, phase, target_status, target_verdict, target_closure_basis, ambiguity)`;
  `StatusInventory.deterministic` / `.ambiguous`. Task 7 consumes it and **adds no mapping logic of
  its own** — a rule living in the migration but not the inventory would mean the report a human
  approved is not the migration that ran.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_status_inventory.py
from pathlib import Path

import pytest

from science_tool.status_inventory import Adjudicated, inventory


def _hyp(root: Path, name: str, *, status: str | None, phase: str | None) -> None:
    d = root / "entities" / "hypotheses"
    d.mkdir(parents=True, exist_ok=True)
    lines = ["---", f'id: "hypothesis:{name}"', 'kind: "hypothesis"', 'title: "T"']
    if status is not None:
        lines.append(f'status: "{status}"')
    if phase is not None:
        lines.append(f'phase: "{phase}"')
    lines += ["---", "", "body"]
    (d / f"{name}.md").write_text("\n".join(lines), encoding="utf-8")


def test_phase_is_the_lifecycle_status_is_the_verdict(tmp_path: Path) -> None:
    # The 60-file cohort: both template defaults. `phase` owns the lifecycle. `proposed`
    # means "the evidence has not spoken" -- which is ABSENCE, not `draft`.
    _hyp(tmp_path, "0001-a", status="proposed", phase="active")
    row = inventory(tmp_path).rows[0]
    assert (row.target_status, row.target_verdict, row.ambiguity) == ("active", None, None)


def test_absent_phase_defaults_to_active(tmp_path: Path) -> None:
    _hyp(tmp_path, "0002-b", status="proposed", phase=None)
    assert inventory(tmp_path).rows[0].target_status == "active"


def test_candidate_keeps_its_verdict(tmp_path: Path) -> None:
    # Orthogonal axes: a candidate frame CAN carry a verdict.
    _hyp(tmp_path, "0003-c", status="weakened", phase="candidate")
    row = inventory(tmp_path).rows[0]
    assert (row.target_status, row.target_verdict) == ("draft", "weakened")


def test_terminal_status_is_refused_not_guessed(tmp_path: Path) -> None:
    _hyp(tmp_path, "0009-d", status="retired", phase="candidate")
    inv = inventory(tmp_path)
    assert inv.deterministic == [] and len(inv.ambiguous) == 1
    assert inv.ambiguous[0].target_status is None  # never guessed


def test_an_ADJUDICATION_lets_a_refused_file_through(tmp_path: Path) -> None:
    # THE escape from the refusal loop. Without this, `_classify` sees the terminal status
    # forever and 0009 can never migrate, no matter what an author does to the file.
    _hyp(tmp_path, "0009-d", status="retired", phase="candidate")
    adj = {
        "hypothesis:0009-d": Adjudicated(
            status="retired", verdict="weakened", closure_basis="confirmatory null, z=-0.889"
        )
    }
    inv = inventory(tmp_path, adjudication=adj)
    assert inv.ambiguous == []
    row = inv.deterministic[0]
    assert (row.target_status, row.target_verdict) == ("retired", "weakened")
    assert row.target_closure_basis == "confirmatory null, z=-0.889"


def test_adjudication_for_an_unknown_id_is_an_error(tmp_path: Path) -> None:
    # Fail early: a typo'd id in the adjudication file must not silently do nothing.
    _hyp(tmp_path, "0001-a", status="proposed", phase="active")
    with pytest.raises(KeyError):
        inventory(tmp_path, adjudication={"hypothesis:9999-nope": Adjudicated(status="retired")})
```

- [ ] **Step 2: Run and fail** — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# science/src/science_tool/status_inventory.py
"""Plan the hypothesis lifecycle/verdict migration. Writes nothing.

The mapping is design §10 rev 7, and it INVERTS what every earlier revision assumed.
`phase` is the lifecycle; `status` was only ever the verdict. `proposed` and
`under-investigation` are not states -- they are the collapsed field's way of saying "the
evidence has not spoken", which is exactly what an ABSENT verdict already says (D1).
Mapping them to `draft` would have mis-migrated 88 of 147 files.

AMBIGUITY IS ESCAPED BY AN ARTIFACT, NEVER BY SHAPE. A file whose `status` is terminal has
lost its lifecycle, its verdict AND its closure reason at once, and no rule recovers them.
An author supplies all three in an adjudication file, keyed by entity id. Re-reading the
FILE would not help: the author's edit is indistinguishable from the corruption, so the
classifier would refuse it forever -- which is precisely the loop rev 1 shipped.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import yaml
from science_model.frontmatter import split_frontmatter

from science_tool.entity_scan import iter_entity_markdown

_VERDICTS = frozenset({"supported", "weakened", "partially-supported", "refuted"})
_NO_VERDICT = frozenset({"proposed", "under-investigation"})
# An absent `phase` defaults to `active`: the template ships `phase: "active"`,
# hypotheses_cli.py:28 defaults to it, and commands/big-picture.md:62 says so.
_PHASE_TO_STATUS: dict[str | None, str] = {"candidate": "draft", "active": "active", None: "active"}
_LIFECYCLE_WORDS = frozenset({"active", "draft"})


@dataclass(frozen=True, slots=True)
class Adjudicated:
    """An author's explicit decision for a file no rule can migrate."""

    status: str
    verdict: str | None = None
    closure_basis: str | None = None


@dataclass(frozen=True, slots=True)
class InventoryRow:
    path: Path
    entity_id: str
    status: str | None
    phase: str | None
    target_status: str | None
    target_verdict: str | None
    target_closure_basis: str | None
    ambiguity: str | None


@dataclass(frozen=True, slots=True)
class StatusInventory:
    rows: list[InventoryRow]

    @property
    def deterministic(self) -> list[InventoryRow]:
        return [r for r in self.rows if r.ambiguity is None]

    @property
    def ambiguous(self) -> list[InventoryRow]:
        return [r for r in self.rows if r.ambiguity is not None]


def load_adjudication(path: Path) -> dict[str, Adjudicated]:
    """Read an adjudication file: {entity_id: {status, verdict?, closure_basis?}}."""
    if not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        entity_id: Adjudicated(
            status=spec["status"],
            verdict=spec.get("verdict"),
            closure_basis=spec.get("closure_basis"),
        )
        for entity_id, spec in raw.items()
    }


def _classify(
    path: Path, entity_id: str, status: str | None, phase: str | None
) -> InventoryRow:
    def row(**kw) -> InventoryRow:
        return InventoryRow(
            path=path, entity_id=entity_id, status=status, phase=phase,
            target_closure_basis=None, **kw
        )

    if status is None:
        return row(target_status=None, target_verdict=None,
                   ambiguity="no `status`: nothing to derive a verdict from")
    if phase is not None and phase not in _PHASE_TO_STATUS:
        return row(target_status=None, target_verdict=None,
                   ambiguity=f"unknown phase {phase!r} (expected candidate|active)")

    lifecycle = _PHASE_TO_STATUS[phase]

    if status in _NO_VERDICT:
        return row(target_status=lifecycle, target_verdict=None, ambiguity=None)
    if status in _VERDICTS:
        return row(target_status=lifecycle, target_verdict=status, ambiguity=None)
    if status in _LIFECYCLE_WORDS and status == lifecycle:
        # Author wrote a lifecycle word into `status`; `phase` independently agrees.
        return row(target_status=lifecycle, target_verdict=None, ambiguity=None)

    # `retired` / `archived` / anything else. A terminal word in the collapsed field
    # destroyed the lifecycle, the verdict AND the closure reason simultaneously. Nothing
    # is left to recover, and inventing any of the three would be the exact fabrication
    # this design exists to prevent.
    return row(
        target_status=None, target_verdict=None,
        ambiguity=(
            f"status {status!r} is terminal or unknown: the prior verdict and the closure "
            f"reason are unrecoverable. Adjudicate {entity_id} explicitly."
        ),
    )


def inventory(
    project_root: Path, *, adjudication: Mapping[str, Adjudicated] | None = None
) -> StatusInventory:
    adjudication = adjudication or {}
    entities_root = project_root / "entities"
    if not entities_root.is_dir():
        return StatusInventory(rows=[])

    rows: list[InventoryRow] = []
    seen: set[str] = set()
    for path in iter_entity_markdown(entities_root):
        fm, _ = split_frontmatter(path.read_text(encoding="utf-8"))
        if fm.get("kind") != "hypothesis":
            continue
        entity_id = str(fm.get("id") or "")
        seen.add(entity_id)
        status = fm.get("status") or None
        phase = fm.get("phase") or None

        decided = adjudication.get(entity_id)
        if decided is not None:
            rows.append(
                InventoryRow(
                    path=path, entity_id=entity_id, status=status, phase=phase,
                    target_status=decided.status, target_verdict=decided.verdict,
                    target_closure_basis=decided.closure_basis, ambiguity=None,
                )
            )
            continue

        rows.append(
            _classify(
                path, entity_id,
                status if isinstance(status, str) else None,
                phase if isinstance(phase, str) else None,
            )
        )

    unknown = set(adjudication) - seen
    if unknown:
        raise KeyError(f"adjudication names entities that do not exist: {sorted(unknown)}")
    return StatusInventory(rows=rows)
```

- [ ] **Step 4: Green** — `6 passed`.

- [ ] **Step 5: Wire the report-only CLI** (`science entity status-inventory [--json]`), printing
  the deterministic count and each refused file with its `ambiguity`.

- [ ] **Step 6: Run against all 9 repos**

```bash
for p in ~/d/natural-systems ~/d/r/mm30 ~/d/r/cbioportal ~/d/protein-landscape \
         ~/d/science/meta ~/d/health/meta ~/d/seq-feats ~/d/cancer/therapeutics ~/d/3d-attention-bias; do
  echo "=== $p"; (cd "$p" && uv run science entity status-inventory)
done
```
Expected across the 9: **145 deterministic, 1 refused** (`natural-systems/0009`; the second
refusal is a toolkit test fixture, not a project). **Any other refusal ⇒ the mapping is not
certified. STOP.**

- [ ] **Step 7: Commit.**

---

### Task 4: Adjudicate `natural-systems/0009`

**Not a code task.** The one real file no rule can migrate — and the file whose corruption opened
this arc (fb-2026-07-11-005).

- [ ] **Step 1:** Read the hypothesis and its interpretations. The record says the confirmatory
  null was **non-significant (z = −0.889)** — which is `weakened` (failed to confirm), **not**
  `refuted` (met a rejection criterion). It carries `status: retired`, a **task** status, which
  destroyed that distinction.
- [ ] **Step 2:** Have **the author** (not the implementer, not this plan) write
  `~/d/natural-systems/.science/hypothesis-lifecycle.adjudication.yaml`:

```yaml
# Explicit authored decisions for hypotheses whose collapsed `status` destroyed the
# information needed to migrate them. Consumed by `science entity migrate-hypothesis`.
"hypothesis:0009-local-structure-globalization-obstruction":
  status: retired            # lifecycle: no longer an object of active work
  verdict: weakened          # epistemic: the confirmatory null was NON-significant (z=-0.889)
  closure_basis: "Stopped after the confirmatory null failed to reach significance; the
    globalization-obstruction framing was folded into the h5 reframing rather than pursued."
```

- [ ] **Step 3:** Re-run `science entity status-inventory` in natural-systems → **0 refused**.
- [ ] **Step 4:** Commit the adjudication file **in natural-systems**, not in the toolkit.

---

## Phase 2 — The schema substrate

### Task 5: `science-entity-base-2.0` — syntactic kind, so it never needs editing again

**Why a new base:** composition is a pure `allOf` (`validator.py:82-87`), and **an `allOf` can
only narrow.** Base 1.0 pins `kind` to `{"enum": [dataset,paper,topic,theme]}` and `id` to
`^(dataset|paper|topic|theme):…`. No extension can widen either. A base bump is forced.

**Why a *pattern*, not an enum:** there are **50 core kinds**. Rev 1 hand-typed a 26-kind enum
into base 2.0 — both incomplete *and* unevolvable, since adding kind 27 would mean **editing a
versioned schema in place**, which is the one thing versioning exists to forbid. Instead the base
constrains `kind` **syntactically** and **each mixin supplies the exact `const`**. Adding a kind
is then adding a mixin, and base 2.0 is never touched.

**Why it is safe:** every existing mixin already pins its kind — `mixin-dataset-1.0.json` has
`"kind": {"const": "dataset"}`, likewise paper/topic/theme. And `validate_as` **rejects a
base-only profile**, so a mixin is always present. The base's job is shape; the mixin's job is
identity.

**Why commons does not move:** commons records keep pinning `science-entity-base/1.0`. Two base
versions coexist — that is what versioning is *for*. **Zero commons churn.**

**Files:**
- Create: `science/model/src/science_model/schemas/science-entity-base-2.0.json`
- Test: `science/model/tests/test_base_2_0.py`

- [ ] **Step 1: Write the failing test**

```python
# science/model/tests/test_base_2_0.py
import json
from importlib.resources import files

import pytest

from science_model.entity_schema import EntityValidationError, EntityValidator, parse_profile


def _load(name: str) -> dict:
    return json.loads((files("science_model.schemas") / name).read_text(encoding="utf-8"))


def test_base_2_0_constrains_kind_syntactically_not_by_enum() -> None:
    # An enum would have to be edited in place every time a kind is added -- mutating a
    # versioned schema. The mixin's `const` is what pins identity.
    kind = _load("science-entity-base-2.0.json")["properties"]["kind"]
    assert "enum" not in kind
    assert kind["pattern"] == "^[a-z][a-z0-9-]*$"


def test_base_2_0_does_not_require_version_or_schema_profile() -> None:
    # `version` is a commons concept (semver on a shared record). A project entity is
    # versioned by its repo's git history. `schema_profile` is DERIVED for project kinds.
    req = _load("science-entity-base-2.0.json")["required"]
    assert "version" not in req and "schema_profile" not in req
    assert sorted(req) == ["created", "id", "kind", "title", "updated"]


def test_base_1_0_is_byte_untouched() -> None:
    # Commons pins 1.0. If this fails, 369 live commons records are at risk.
    base1 = _load("science-entity-base-1.0.json")
    assert base1["properties"]["kind"]["enum"] == ["dataset", "paper", "topic", "theme"]
    assert "version" in base1["required"]


def test_a_mixin_const_still_narrows_the_kind_under_base_2() -> None:
    # The safety argument, executed.
    with pytest.raises(EntityValidationError):
        EntityValidator().validate_as(
            {"id": "dataset:x", "kind": "hypothesis", "title": "T",
             "created": "2026-07-12", "updated": "2026-07-12",
             "origin": "external", "tier": "raw"},
            parse_profile("science-entity-base/2.0+dataset/1.0"),
        )
```

- [ ] **Step 2: Run and fail** — `SchemaNotFoundError` / no `validate_as`.

- [ ] **Step 3: Create the schema.** Copy `science-entity-base-1.0.json`, keep `$defs`,
  `licenses`, `contributors`, `dataset_usage` and **every `science:merge` annotation** byte-identical,
  and change exactly these:

```json
{
  "$id": "https://schemas.science/science-entity-base-2.0.json",
  "title": "science entity base profile (kind-agnostic; mixins pin identity)",
  "required": ["id", "kind", "title", "created", "updated"],
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^[a-z][a-z0-9-]*:[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
    },
    "kind": {
      "type": "string",
      "pattern": "^[a-z][a-z0-9-]*$",
      "$comment": "Shape only. The mixin's `const` pins the exact kind — so adding a new kind never edits this versioned file."
    },
    "version": {
      "type": "string",
      "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$",
      "science:merge": "forbidden"
    }
  }
}
```

Deltas, and only these: **(a)** `$id`/`title`; **(b)** `required` drops `schema_profile` (derived
for project kinds) and `version` (a commons concept); **(c)** `kind` becomes a pattern; **(d)**
`id` becomes prefix-agnostic, with the suffix widened to 127 chars — hypothesis slugs like
`0009-local-structure-globalization-obstruction` exceed base 1.0's 64.

- [ ] **Step 4: Green** — run the three tests that do not need `validate_as`; the fourth goes
  green at the end of Task 6, in the same commit as `validate_as`.

- [ ] **Step 5: Commit.**

---

### Task 6: Profile plumbing, `validate_as`, and `mixin-hypothesis-1.0`

**One task, because the four tests in Task 5 and the mixin's invariants cannot go green
separately** — and no task may end red.

**Files:**
- Modify: `science/model/src/science_model/entity_schema/profile.py`, `validator.py`
- Create: `science/model/src/science_model/schemas/mixin-hypothesis-1.0.json`
- Test: `science/model/tests/test_project_profiles.py`, `test_mixin_hypothesis.py`

**Interfaces:**
- Produces `EntityValidator.validate_as(entity: dict, profile: ProfileString) -> None` — validate
  against an **explicit** profile. Project entities do **not** carry `schema_profile` in
  frontmatter; it is derived from `kind`. Tasks 8–10 call this.
- Produces `default_profile_for_kind("hypothesis")` → `science-entity-base/2.0+hypothesis/1.0`.

- [ ] **Step 1: Write the failing tests**

```python
# science/model/tests/test_project_profiles.py
import pytest

from science_model.entity_schema import default_profile_for_kind, parse_profile
from science_model.entity_schema.profile import ProfileParseError


def test_hypothesis_derives_a_base_2_profile() -> None:
    assert default_profile_for_kind("hypothesis").render() == "science-entity-base/2.0+hypothesis/1.0"


def test_commons_kinds_stay_on_base_1() -> None:
    # Non-negotiable: 369 live commons records pin base 1.0.
    assert default_profile_for_kind("dataset").render() == "science-entity-base/1.0+dataset/1.0"
    assert default_profile_for_kind("paper").render() == "science-entity-base/1.0+paper/2.0"


def test_unknown_mixin_still_rejected() -> None:
    with pytest.raises(ProfileParseError):
        parse_profile("science-entity-base/2.0+nonsense/1.0")
```

```python
# science/model/tests/test_mixin_hypothesis.py
import json
from importlib.resources import files

import pytest

from science_model.entity_schema import (
    EntityValidationError, EntityValidator, default_profile_for_kind,
)
from science_model.profiles.core import CORE_PROFILE

PROFILE = default_profile_for_kind("hypothesis")
V = EntityValidator()


def _h(**over) -> dict:
    base = {"id": "hypothesis:0001-x", "kind": "hypothesis", "title": "T",
            "created": "2026-07-12", "updated": "2026-07-12", "status": "active"}
    base.update(over)
    return base


def test_lifecycle_vocabulary_is_the_ruled_one() -> None:
    for good in ("draft", "active"):
        V.validate_as(_h(status=good), PROFILE)
    for verdict_word in ("proposed", "under-investigation", "supported", "weakened"):
        with pytest.raises(EntityValidationError):
            V.validate_as(_h(status=verdict_word), PROFILE)


def test_verdict_excludes_the_unassessed_spellings() -> None:
    V.validate_as(_h(verdict="refuted"), PROFILE)
    for bad in ("proposed", "under-investigation"):
        # D1: absence already means "not yet assessed". Admitting these makes three
        # spellings of one state and re-collapses the axis.
        with pytest.raises(EntityValidationError):
            V.validate_as(_h(verdict=bad), PROFILE)


def test_the_axes_are_orthogonal() -> None:
    # The cell the collapsed field could not express.
    V.validate_as(_h(status="superseded", verdict="supported",
                     superseded_by="hypothesis:0002-y"), PROFILE)
    V.validate_as(_h(status="draft", verdict="weakened"), PROFILE)


def test_complete_REQUIRES_a_verdict() -> None:
    # RULED (design rev 6): prohibited outright, NOT dischargeable by closure_basis.
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(status="complete"), PROFILE)
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(status="complete", closure_basis="ran out of time"), PROFILE)
    V.validate_as(_h(status="complete", verdict="supported"), PROFILE)


def test_retired_always_requires_a_closure_basis() -> None:
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(status="retired"), PROFILE)
    V.validate_as(_h(status="retired", closure_basis="no samples left"), PROFILE)


def test_superseded_requires_lineage_or_a_basis() -> None:
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(status="superseded"), PROFILE)
    V.validate_as(_h(status="superseded", superseded_by="hypothesis:0002-y"), PROFILE)
    # `resynthesized_into` is a LIST (archive.py:38, materialize.py:155) -- not a string.
    V.validate_as(_h(status="superseded", resynthesized_into=["hypothesis:0002-y"]), PROFILE)
    V.validate_as(_h(status="superseded", closure_basis="folded into h5"), PROFILE)


def test_phase_and_disposition_are_FORBIDDEN() -> None:
    for gone in ({"phase": "candidate"}, {"disposition": "closed"},
                 {"disposition_basis": "x"}):
        with pytest.raises(EntityValidationError):
            V.validate_as(_h(**gone), PROFILE)


def test_an_arbitrary_unknown_key_is_REJECTED() -> None:
    # Rev 1's test used `phase`, which is explicitly `false` in the schema -- so it proved
    # nothing about unknown keys. THE original defect is that `Entity` is extra="ignore"
    # and silently DROPS anything undeclared. This is the test that actually pins it.
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(role_typo="oops"), PROFILE)


def test_every_authored_field_in_the_corpus_is_DECLARED() -> None:
    # The P0 gate, executed. Task 2 adjudicated 36 keys; if the mixin declares fewer, then
    # closing the schema rejects real files. This is the test that would have caught rev 1.
    schema = json.loads(
        (files("science_model.schemas") / "mixin-hypothesis-1.0.json").read_text(encoding="utf-8")
    )
    base = json.loads(
        (files("science_model.schemas") / "science-entity-base-2.0.json").read_text(encoding="utf-8")
    )
    declared = set(schema["properties"]) | set(base["properties"])
    adjudicated = set(ADJUDICATED_HYPOTHESIS_FIELDS)  # from Task 2's doc; pin it here
    assert adjudicated - {"phase"} <= declared


def test_schema_and_descriptor_agree() -> None:
    # The bidirectional gate. A vocabulary that disagrees with its descriptor is exactly the
    # uncertified instrument that broke five projects.
    schema = json.loads(
        (files("science_model.schemas") / "mixin-hypothesis-1.0.json").read_text(encoding="utf-8")
    )
    descriptor = next(k for k in CORE_PROFILE.entity_kinds if k.name == "hypothesis")
    assert sorted(schema["properties"]["status"]["enum"]) == sorted(descriptor.statuses)
```

> `test_schema_and_descriptor_agree` needs the Task 8 descriptor. **Do not xfail it** (rev 1 did,
> and an xfail is a red suite wearing a hat). Move the descriptor change **into Task 8** and this
> test **into Task 8's file** — it belongs with the change it gates.

- [ ] **Step 2: Run and fail.**

- [ ] **Step 3: Implement the profile plumbing.** In `profile.py` replace line 16 and lines 75–102:

```python
BASE_NAME = "science-entity-base"

# Commons type mixins (base 1.0). Shared across repos; versioned; 369 live records.
COMMONS_MIXIN_NAMES = frozenset({"dataset", "paper", "topic", "theme"})

# Project-authored kinds converging onto the same schema system (base 2.0). This set IS the
# P2m slice list: one entry per migrated kind.
PROJECT_MIXIN_NAMES = frozenset({"hypothesis"})

TYPE_MIXIN_NAMES = COMMONS_MIXIN_NAMES | PROJECT_MIXIN_NAMES
```

```python
_DEFAULT_MIXIN_VERSION: dict[str, str] = {
    "dataset": "1.0", "paper": "2.0", "topic": "2.0", "theme": "2.0",
    "hypothesis": "1.0",
}

# The base version is PER-KIND, not global. Commons kinds pin base 1.0 -- 369 live records
# depend on it and there is no reason to move them. Project kinds need base 2.0, whose
# kind/id constraints admit them (base 1.0's structurally cannot, and an allOf can only
# narrow). Two base versions coexisting is what versioning is FOR.
_BASE_VERSION_FOR_MIXIN: dict[str, str] = {
    **{name: "1.0" for name in COMMONS_MIXIN_NAMES},
    **{name: "2.0" for name in PROJECT_MIXIN_NAMES},
}


def default_profile_for_kind(kind: str) -> ProfileString:
    """The default profile for a kind.

    Project entities do NOT carry `schema_profile` in frontmatter -- it is derived here.
    (Commons records DO carry it: they travel between repos, so the profile must travel with
    the record. A project entity is versioned by the repo that contains it.)
    """
    if kind not in _DEFAULT_MIXIN_VERSION:
        raise ProfileParseError(
            f"unknown kind {kind!r}; expected one of {sorted(_DEFAULT_MIXIN_VERSION)}"
        )
    return parse_profile(
        f"{BASE_NAME}/{_BASE_VERSION_FOR_MIXIN[kind]}+{kind}/{_DEFAULT_MIXIN_VERSION[kind]}"
    )
```

In `validator.py`, add `validate_as`, make `validate` delegate, and **close the composed schema**:

```python
    def validate(self, entity: dict[str, Any]) -> None:
        """Validate against the entity's OWN declared `schema_profile` (the commons path)."""
        profile_str = entity.get("schema_profile")
        if not profile_str:
            raise EntityValidationError("entity is missing required schema_profile field")
        try:
            profile = parse_profile(profile_str)
        except ProfileParseError as exc:
            raise EntityValidationError(f"invalid schema_profile: {exc}") from exc
        self.validate_as(entity, profile)

    def validate_as(self, entity: dict[str, Any], profile: ProfileString) -> None:
        """Validate against an EXPLICIT profile, without mutating the caller's dict."""
        if profile.mixin is None:
            raise EntityValidationError(
                f"schema_profile must include a type mixin (one of {sorted(TYPE_MIXIN_NAMES)}) "
                f"— base-only profiles are not valid for entity payloads"
            )
        composed = self._compose(profile)
        validator = Draft202012Validator(
            composed, format_checker=Draft202012Validator.FORMAT_CHECKER
        )
        errors = sorted(validator.iter_errors(entity), key=lambda e: list(e.absolute_path))
        if errors:
            joined = "; ".join(_format_error(err) for err in errors)
            raise EntityValidationError(f"entity failed schema validation: {joined}", errors=errors)

    def _compose(self, profile: ProfileString) -> dict[str, Any]:
        parts = [self._loader.load(profile.base)]
        if profile.mixin is not None:
            parts.append(self._loader.load(profile.mixin))
        parts.extend(self._loader.load(ext) for ext in profile.extensions)

        # `unevaluatedProperties` -- NOT `additionalProperties`. Inside an allOf,
        # `additionalProperties` in one branch cannot see properties declared by a SIBLING
        # branch, so it would reject every field the mixin declares. `unevaluatedProperties`
        # is evaluated after the whole allOf and sees the union. This is THE line that turns
        # the original defect (extra="ignore" silently dropping undeclared keys) into a loud
        # failure -- and it is why Task 2's field adjudication is a hard prerequisite: an
        # undeclared-but-authored key becomes a validation error the moment this lands.
        strict = profile.mixin.name in PROJECT_MIXIN_NAMES
        composed: dict[str, Any] = {"allOf": parts}
        if strict:
            composed["unevaluatedProperties"] = False
        return composed
```

> **Commons profiles are deliberately NOT closed.** `SharedEntity` is `extra="allow"` by design
> and 369 records rely on it; closing commons is a separate decision with a separate blast radius.
> `strict` is gated on `PROJECT_MIXIN_NAMES` so each kind opts in **as it migrates**.

- [ ] **Step 3b: Write `mixin-hypothesis-1.0.json`.** `properties` must contain **every key Task 2
  adjudicated as *declare*** (25 + 3 capability + up to 6 belief-cluster, pending Open Question 1).
  Abridged below to the fields this slice reasons about — **the implementer writes the full list
  from Task 2's doc, and `test_every_authored_field_in_the_corpus_is_DECLARED` enforces it:**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/mixin-hypothesis-1.0.json",
  "title": "hypothesis type mixin",
  "type": "object",
  "required": ["id", "kind", "status"],
  "properties": {
    "kind": { "const": "hypothesis" },

    "status": {
      "description": "LIFECYCLE. Not the verdict. Sourced from the old `phase` field (design rev 7).",
      "enum": ["draft", "active", "complete", "superseded", "retired", "archived"]
    },
    "verdict": {
      "description": "EPISTEMIC. What the evidence concludes. ABSENT = not yet assessed -- which is why `proposed`/`under-investigation` are NOT admitted: they would be a third spelling of absence.",
      "enum": ["partially-supported", "supported", "weakened", "refuted"]
    },
    "closure_basis": {
      "description": "The AUTHORED reason a terminal entity closed, required when no structural basis exists. The state is derivable; the reason is not.",
      "type": "string", "minLength": 1
    },

    "superseded_by": { "type": "string", "pattern": "^hypothesis:" },
    "resynthesized_into": {
      "type": "array", "items": { "type": "string", "pattern": "^hypothesis:" },
      "$comment": "A LIST — see archive.py:38 and materialize.py:155."
    },
    "archive_ref": { "type": "string" },

    "related": { "type": "array", "items": { "type": "string" } },
    "source_refs": { "type": "array", "items": { "type": "string" } },
    "origins": { "type": "array" },
    "added_by": { "type": "string" },
    "tags": { "type": "array", "items": { "type": "string" } },
    "ontology_terms": { "type": "array", "items": { "type": "string" } },
    "datasets": { "type": "array" },
    "lens_views": { "type": "array" },
    "priority": {},
    "role": { "type": "string" },
    "domain": { "type": "string" },
    "description": { "type": "string" },
    "aliases": { "type": "array", "items": { "type": "string" } },
    "review_state": {},
    "promoted_from": { "type": "string" },
    "promotion_criteria": {},
    "rival_model_packet": {},
    "external_hypothesis_id": { "type": "string" },
    "identification": {},

    "required_capabilities": { "type": "array", "$comment": "P1 subsystem — declared, not yet absorbed." },
    "capability_scope": {},
    "composition_rule": {},

    "phase": false,
    "disposition": false,
    "disposition_basis": false,
    "profile": false
  },

  "allOf": [
    {
      "$comment": "RULED (rev 6): you cannot conclude without concluding something. `closure_basis` does NOT discharge this — admitting `complete` + absent-verdict would give `retired + closure_basis` a second spelling that reads, to every consumer, as though the hypothesis had been resolved.",
      "if": { "properties": { "status": { "const": "complete" } }, "required": ["status"] },
      "then": { "required": ["verdict"] }
    },
    {
      "$comment": "`retired` is the only terminal with no structural basis available to it, so it ALWAYS requires an authored one. This is the fb-005 no-hidden-debt guarantee.",
      "if": { "properties": { "status": { "const": "retired" } }, "required": ["status"] },
      "then": { "required": ["closure_basis"] }
    },
    {
      "$comment": "PRESENCE only. Whether the lineage RESOLVES is a cross-record fact and belongs to resolution.py — the schema cannot see other files. Keying off the status word alone would be unsound: the live-lineage contract explicitly permits a live `superseded` with no lineage.",
      "if": { "properties": { "status": { "const": "superseded" } }, "required": ["status"] },
      "then": { "anyOf": [ { "required": ["superseded_by"] }, { "required": ["resynthesized_into"] }, { "required": ["closure_basis"] } ] }
    },
    {
      "if": { "properties": { "status": { "const": "archived" } }, "required": ["status"] },
      "then": { "anyOf": [ { "required": ["archive_ref"] }, { "required": ["closure_basis"] } ] }
    }
  ]
}
```

> `"phase": false` is the JSON Schema idiom for *"this property must not appear."* It makes the
> deletion **enforced**, not merely intended. `"profile": false` keeps a derived field from being
> hand-authored (3 files do today — Task 8 strips it).

- [ ] **Step 4: Green** — the whole model suite, including Task 5's fourth test.

```bash
cd science/model && uv run --frozen pytest -q
```

- [ ] **Step 5: Commit.**

---

### Task 7: `resolution.py` — the cross-record layer, **wired**

Schema validates **one record in isolation**. It cannot resolve a successor ID or confirm an
archive record exists. **Presence is schema; resolution is a validator.** Without this, a
*present but dangling* `superseded_by:` satisfies the schema and closes the entity with no real
reason behind it — the hole in a subtler dress.

> **Scope, stated honestly.** Design §7.4 lists three cross-record invariants. This task ships
> **two**: successor resolution and archive-record existence. It does **not** ship
> *verdict-has-qualifying-evidence*, because that is a **graph-time** fact (it needs the
> evidence-line edges, which exist only after materialization) and this validator runs at
> **load time**. Rev 1 claimed all three and implemented one. **Design §7.4 is amended to say
> two layers here and a third at graph time** — do not let the doc keep promising what the code
> does not do.

**Files:**
- Create: `science/model/src/science_model/entity_schema/resolution.py`
- Modify: `science/src/science_tool/graph/sources.py`, `entities.py` (`edit_entity`), `validate/checks/`
- Test: `science/model/tests/test_resolution.py`, `science/tests/test_resolution_wiring.py`

- [ ] **Step 1: Write the failing tests** — unit **and wiring**. Rev 1 shipped the module unwired
  and admitted it in its own self-review. **The wiring tests are the point.**

```python
# science/model/tests/test_resolution.py
from science_model.entity_schema.resolution import check_resolution

KNOWN = {"hypothesis:0002-y"}


def test_dangling_successor_is_caught() -> None:
    # The whole reason this module exists: the schema is satisfied, the entity is closed,
    # and the reason it closed does not exist.
    v = check_resolution(
        {"id": "hypothesis:0001-x", "status": "superseded",
         "superseded_by": "hypothesis:9999-nope"},
        known_ids=KNOWN, known_archive_refs=set(),
    )
    assert len(v) == 1 and "9999-nope" in v[0]


def test_resolving_successor_passes() -> None:
    assert check_resolution(
        {"id": "hypothesis:0001-x", "status": "superseded",
         "superseded_by": "hypothesis:0002-y"},
        known_ids=KNOWN, known_archive_refs=set(),
    ) == []


def test_resynthesized_into_is_a_LIST_and_every_member_must_resolve() -> None:
    v = check_resolution(
        {"id": "hypothesis:0001-x", "status": "superseded",
         "resynthesized_into": ["hypothesis:0002-y", "hypothesis:9999-nope"]},
        known_ids=KNOWN, known_archive_refs=set(),
    )
    assert len(v) == 1 and "9999-nope" in v[0]


def test_self_supersession_is_caught() -> None:
    v = check_resolution(
        {"id": "hypothesis:0002-y", "status": "superseded",
         "superseded_by": "hypothesis:0002-y"},
        known_ids=KNOWN, known_archive_refs=set(),
    )
    assert len(v) == 1 and "itself" in v[0]


def test_dangling_archive_ref_is_caught() -> None:
    v = check_resolution(
        {"id": "hypothesis:0001-x", "status": "archived", "archive_ref": "arc:nope"},
        known_ids=KNOWN, known_archive_refs={"arc:real"},
    )
    assert len(v) == 1 and "arc:nope" in v[0]


def test_a_basis_closed_entity_needs_no_structure() -> None:
    assert check_resolution(
        {"id": "hypothesis:0001-x", "status": "superseded", "closure_basis": "folded into h5"},
        known_ids=KNOWN, known_archive_refs=set(),
    ) == []


def test_a_live_entity_is_not_checked() -> None:
    assert check_resolution(
        {"id": "hypothesis:0001-x", "status": "active"},
        known_ids=set(), known_archive_refs=set(),
    ) == []
```

```python
# science/tests/test_resolution_wiring.py
def test_validate_reports_a_dangling_successor(tmp_project) -> None:
    write_hypothesis(tmp_project, "0001-x", status="superseded",
                     extra={"superseded_by": "hypothesis:9999-nope"})
    findings = run_validate(tmp_project)
    assert any("9999-nope" in f.message for f in findings)


def test_edit_entity_refuses_a_dangling_successor(tmp_project) -> None:
    write_hypothesis(tmp_project, "0001-x", status="active")
    with pytest.raises(EntityCommandError, match="9999-nope"):
        edit_entity(tmp_project, "hypothesis:0001-x",
                    status="superseded", superseded_by="hypothesis:9999-nope")
    # FAILS BEFORE WRITING.
    assert 'status: "active"' in (tmp_project / "entities/hypotheses/0001-x.md").read_text()
```

- [ ] **Step 2: Run and fail.**

- [ ] **Step 3: Implement**

```python
# science/model/src/science_model/entity_schema/resolution.py
"""Cross-record invariants — the D3 escape hatch, ENUMERATED.

JSON Schema is the authority for a record's SHAPE and for the PRESENCE of a structural basis.
It validates one record in isolation, so it structurally cannot answer: does this successor ID
resolve? does that archive record exist? Those are cross-record facts.

This is that second layer, and it is deliberately a CLOSED LIST rather than an open-ended
second authority (design §9, D3). Getting the split wrong re-opens the hole it was built to
close: a PRESENT but DANGLING `superseded_by:` satisfies the schema, closes the entity, and
records no real reason for the closure.

NOT HERE: "a verdict has qualifying evidence". That needs the evidence-line EDGES, which exist
only after materialization -- it is a graph-time invariant, and this runs at load time. Design
§7.4 names it; it belongs to a graph check, not to this module. Said plainly so nobody assumes
it is covered.
"""

from __future__ import annotations

from typing import Any

_TERMINALS_WITH_STRUCTURE = frozenset({"superseded", "archived"})


def _lineage_refs(entity: dict[str, Any]) -> list[tuple[str, str]]:
    """(field, ref) pairs. `superseded_by` is scalar; `resynthesized_into` is a LIST."""
    refs: list[tuple[str, str]] = []
    scalar = entity.get("superseded_by")
    if isinstance(scalar, str) and scalar:
        refs.append(("superseded_by", scalar))
    listed = entity.get("resynthesized_into")
    if isinstance(listed, list):
        refs.extend(("resynthesized_into", r) for r in listed if isinstance(r, str) and r)
    return refs


def check_resolution(
    entity: dict[str, Any], *, known_ids: set[str], known_archive_refs: set[str]
) -> list[str]:
    """Violations of cross-record terminal invariants. Empty == clean."""
    if entity.get("status") not in _TERMINALS_WITH_STRUCTURE:
        return []

    entity_id = str(entity.get("id") or "<unknown>")
    violations: list[str] = []

    for field, ref in _lineage_refs(entity):
        if ref == entity_id:
            violations.append(f"{entity_id}: {field} points at itself")
        elif ref not in known_ids:
            violations.append(
                f"{entity_id}: {field} -> {ref!r} does not resolve to any known entity; "
                f"the entity is closed and the reason it closed does not exist"
            )

    archive_ref = entity.get("archive_ref")
    if isinstance(archive_ref, str) and archive_ref and archive_ref not in known_archive_refs:
        violations.append(
            f"{entity_id}: archive_ref -> {archive_ref!r} does not resolve to any archive record"
        )
    return violations
```

- [ ] **Step 3b: WIRE it — three call sites, none optional**
  1. **`graph/sources.py`**, after the whole corpus is loaded (it needs `known_ids`, so it is a
     *second pass*, not per-file): collect all entity ids and archive refs
     (`archive.py`'s index), then `check_resolution` each terminal entity; append a
     `SourceFailure`/warning per violation.
  2. **`validate/checks/`** — a new check surfacing those violations as `Result`s at **WARN**
     (ERROR arrives with Task 11's ratchet, per kind).
  3. **`entities.edit_entity`** — before writing, so a terminal transition with a dangling
     successor **fails before a byte is written** (Task 10).

- [ ] **Step 4: Green** — unit + wiring, both packages, plus `ruff` and `pyright`.

- [ ] **Step 5: Commit.**

---

## Phase 3 — The `hypothesis` P2m slice (this is where meaning changes)

> **ATOMIC PER KIND, ACROSS ALL 9 REPOS.** `default_profile_for_kind` is **global** — the instant
> Task 9 wires schema validation into the load path, *every* project's hypotheses are validated
> against the new mixin. Rev 1 migrated one repo and expected the other eight to keep validating.
> **They cannot.** Two options existed; this is the one taken:
>
> **A per-project version pin.** `science.yaml` gains `entity_schema_version: 2`. The load path
> selects the hypothesis mixin **only** for pinned projects; unpinned projects keep today's
> behaviour (no schema validation for `hypothesis`, WARN-only vocabulary check). The migration
> command **sets the pin as its final act**, atomically with the file rewrites. So each *project*
> migrates atomically, and the *kind* is migrated when all 9 are pinned (Task 11's ratchet
> requires exactly that).
>
> **This is not the forbidden compatibility layer.** That layer is code that *guesses* which
> meaning a file carries. This is an **authored declaration** of which version a project is on —
> which is precisely what D5 means by "introduce target schema versions." The difference is that
> nothing here infers anything.

### Task 8: Descriptor, model, template — and the version pin

**Files:**
- Modify: `science/model/src/science_model/profiles/core.py:32-51`
- Modify: `science/model/src/science_model/entities.py:797-839` (`HypothesisEntity`)
- Modify: `science/src/science_tool/entities.py` (`_LIVE_STATUSES`)
- Modify: `science/model/src/science_model/templates/hypothesis.md` **and** `templates/hypothesis.md` — **two copies; the packaged one is what the Renderer reads**
- Modify: the `science.yaml` schema to admit `entity_schema_version: int`
- Test: `science/model/tests/test_hypothesis_entity.py`

- [ ] **Step 1: Write the failing test**

```python
# science/model/tests/test_hypothesis_entity.py
from science_model.entities import HypothesisEntity
from science_model.profiles.core import CORE_PROFILE


def _kind():
    return next(k for k in CORE_PROFILE.entity_kinds if k.name == "hypothesis")


def test_descriptor_declares_the_lifecycle_not_the_verdict() -> None:
    assert sorted(_kind().statuses) == sorted(
        ["draft", "active", "complete", "superseded", "retired", "archived"]
    )
    assert _kind().default_status == "active"


def test_verdict_and_closure_basis_are_first_class_fields() -> None:
    h = HypothesisEntity(id="hypothesis:1", kind="hypothesis", title="T", project="p",
                         status="active", verdict="refuted")
    assert h.verdict == "refuted"


def test_disposition_is_gone() -> None:
    assert "disposition" not in HypothesisEntity.model_fields
    assert "disposition_basis" not in HypothesisEntity.model_fields


def test_the_projection_does_NOT_reimplement_the_schema_invariants() -> None:
    # D3: JSON Schema is THE authority; Pydantic is a PROJECTION. Rev 1 duplicated
    # `complete requires a verdict` as a model_validator -- which recreates the second
    # authority D3 exists to abolish, and guarantees the two eventually disagree. The
    # projection must be able to REPRESENT anything the schema admits, and must not
    # independently police it. `test_schema_and_projection_agree` is what keeps them honest.
    HypothesisEntity(id="hypothesis:1", kind="hypothesis", title="T", project="p",
                     status="complete")  # no verdict -- the SCHEMA rejects this, not Pydantic


def test_schema_and_projection_agree() -> None:
    # D3 point 4: the CI reconciliation check. This REPLACES the duplicated validators.
    import json
    from importlib.resources import files

    schema = json.loads(
        (files("science_model.schemas") / "mixin-hypothesis-1.0.json").read_text(encoding="utf-8")
    )
    for field in ("status", "verdict", "closure_basis"):
        assert field in HypothesisEntity.model_fields, f"{field} declared in schema, absent from projection"
    descriptor = next(k for k in CORE_PROFILE.entity_kinds if k.name == "hypothesis")
    assert sorted(schema["properties"]["status"]["enum"]) == sorted(descriptor.statuses)
```

- [ ] **Step 2: Run and fail.**

- [ ] **Step 3: Rewrite the descriptor** (`profiles/core.py`):

```python
        EntityKind(
            name="hypothesis",
            canonical_prefix="hypothesis",
            layer="layer/core",
            description="Testable project hypothesis.",
            entity_class=EntityClass.EPISTEMIC,
            category=KindCategory.AUTHORED_CORE,
            template_ready=True,
            shortform="h",
            home="entities/hypotheses",
            strategy="numeric",
            # `status` is the LIFECYCLE, uniformly, on every kind. The old vocabulary
            # (proposed | under-investigation | partially-supported | supported | weakened |
            # refuted | archived) was the epistemic VERDICT wearing the lifecycle's name --
            # which left `archived` as the only lifecycle word a hypothesis had, and pushed
            # authors into hand-rolling `phase` for the rest. The verdict now lives in
            # `verdict`; `phase` folds in here (design rev 7).
            default_status="active",
            statuses=["draft", "active", "complete", "superseded", "retired", "archived"],
        ),
```

> **`archived` must stay.** `consolidate._is_consolidatable` (`consolidate.py:44-49`) returns
> False for a closed vocabulary lacking `archived` — dropping it silently breaks hypothesis
> consolidation.

**Step 3b — `HypothesisEntity`.** Fields only. **No `model_validator`s re-implementing the schema.**

```python
class HypothesisEntity(ProjectEntity):
    """Hypothesis — two orthogonal axes, in two fields.

    `status` (inherited) is the LIFECYCLE. `verdict` is the EPISTEMIC conclusion. Neither may
    be inferred from the other, and the cell that proves it is `superseded` + `supported` —
    formerly supported, now replaced — which the collapsed field could not express at all:
    writing `superseded` OVERWROTE `supported` and destroyed the conclusion.

    `verdict` is ABSENT until the evidence speaks. That absence is load-bearing, and it is why
    `proposed`/`under-investigation` are not verdict values: they say the evidence has NOT
    spoken, which absence already says.

    THE INVARIANTS ARE NOT HERE. `complete` requires a verdict; `retired` requires a
    closure_basis; `superseded` requires lineage or a basis. All three live in
    `mixin-hypothesis-1.0.json`, which is the sole authority (D3). Re-asserting them as
    model_validators would build the second authority D3 abolishes, and the two would drift.
    `test_schema_and_projection_agree` is the gate that keeps this class honest instead.
    """

    verdict: Literal["partially-supported", "supported", "weakened", "refuted"] | None = None
    closure_basis: str | None = None
    superseded_by: str | None = None
    resynthesized_into: list[str] = Field(default_factory=list)
    archive_ref: str | None = None
```

**Step 3c — `_LIVE_STATUSES`** (`science/src/science_tool/entities.py:193-243`): remove the six
verdict words **only if no other kind still declares them**:

```bash
cd science && rg -n '"(proposed|under-investigation|partially-supported|supported|weakened|refuted)"' ../science/model/src/science_model/profiles/
```

`draft`/`active`/`complete`/`retired` are already LIVE; `superseded`/`archived` are HIDDEN. The
guard `test_every_declared_status_still_classified` fails loud if this is wrong — **let it drive.**

**Step 3d — the templates** (both copies): `status: "active"`, delete `phase:`, delete
`disposition:`/`disposition_basis:`, delete both from `_template.frontmatter`.

**Step 3e — `science.yaml`:** admit `entity_schema_version: int | None`. Absent ⇒ version 1
(unmigrated). No project sets it yet — Task 9 does that per repo.

- [ ] **Step 4: Green — both suites, plus ruff and pyright.** Consumers that read the old
  vocabulary are updated in **Task 10**, so run Task 10's edits together with this task's if the
  suite is red at this point. **Do not commit red** (rev 1 explicitly told the implementer to,
  which is both a broken task and a contradiction of its own atomicity claim).

- [ ] **Step 5: Commit.**

---

### Task 9: The migration — two-phase, all-or-none, per repo

**Files:**
- Create: `science/src/science_tool/migrate_hypothesis.py`
- Modify: `science/src/science_tool/entities_cli.py` (register `entity migrate-hypothesis`)
- Test: `science/tests/test_migrate_hypothesis.py`

**Interfaces:**
- Consumes `status_inventory.inventory()` + `load_adjudication()`. **Adds no mapping logic.**

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_migrate_hypothesis.py
def test_refuses_everything_when_any_file_is_ambiguous(tmp_path) -> None:
    _hyp(tmp_path, "0001-a", status="proposed", phase="active")     # deterministic
    _hyp(tmp_path, "0009-d", status="retired", phase="candidate")   # ambiguous
    with pytest.raises(MigrationRefused, match="0009-d"):
        migrate(tmp_path, apply=True)
    assert 'status: "proposed"' in (tmp_path / "entities/hypotheses/0001-a.md").read_text()


def test_an_adjudication_file_unblocks_it(tmp_path) -> None:
    _hyp(tmp_path, "0009-d", status="retired", phase="candidate")
    (tmp_path / ".science").mkdir()
    (tmp_path / ".science/hypothesis-lifecycle.adjudication.yaml").write_text(
        'hypothesis:0009-d:\n  status: retired\n  verdict: weakened\n'
        '  closure_basis: "confirmatory null, z=-0.889"\n', encoding="utf-8")
    migrate(tmp_path, apply=True)
    t = (tmp_path / "entities/hypotheses/0009-d.md").read_text()
    assert 'status: "retired"' in t and 'verdict: "weakened"' in t and "z=-0.889" in t


def test_NOTHING_is_written_if_any_target_fails_schema_validation(tmp_path, monkeypatch) -> None:
    # TWO-PHASE. Rev 1 wrote files in a loop, so an I/O or render failure on file 90 left 89
    # migrated and 58 not -- a corpus with two meanings of `status` live at once, which is
    # exactly the state that forces the compatibility layer D5 forbids.
    _hyp(tmp_path, "0001-a", status="proposed", phase="active")
    _hyp(tmp_path, "0002-b", status="proposed", phase="active")
    monkeypatch.setattr("science_tool.migrate_hypothesis._render", _boom_on("0002-b"))
    with pytest.raises(MigrationRefused):
        migrate(tmp_path, apply=True)
    assert 'status: "proposed"' in (tmp_path / "entities/hypotheses/0001-a.md").read_text()


def test_sets_the_version_pin_as_its_final_act(tmp_path) -> None:
    _hyp(tmp_path, "0001-a", status="proposed", phase="active")
    migrate(tmp_path, apply=True)
    assert "entity_schema_version: 2" in (tmp_path / "science.yaml").read_text()


def test_dry_run_writes_nothing(tmp_path) -> None:
    _hyp(tmp_path, "0001-a", status="proposed", phase="active")
    before = (tmp_path / "entities/hypotheses/0001-a.md").read_text()
    migrate(tmp_path, apply=False)
    assert (tmp_path / "entities/hypotheses/0001-a.md").read_text() == before


def test_body_and_unrelated_frontmatter_survive(tmp_path) -> None:
    _hyp(tmp_path, "0001-a", status="proposed", phase="active",
         extra={"source_refs": ["paper:Smith2020"]}, body="## Rationale\n\nkeep me.")
    migrate(tmp_path, apply=True)
    t = (tmp_path / "entities/hypotheses/0001-a.md").read_text()
    assert "paper:Smith2020" in t and "keep me." in t
```

- [ ] **Step 2: Run and fail.**

- [ ] **Step 3: Implement — render + validate EVERYTHING, then write**

```python
# science/src/science_tool/migrate_hypothesis.py
"""Migrate hypothesis `status`/`phase` -> `status` (lifecycle) + `verdict` (epistemic).

TWO-PHASE AND ALL-OR-NONE. Every target is rendered AND schema-validated before a single byte
is written. A half-migrated corpus carries two incompatible meanings of `status` at once, and
the only way to serve both is the heuristic compatibility layer the design forbids -- so a
failure partway through the write loop would manufacture exactly the state this whole arc
exists to eliminate.

The mapping lives in `status_inventory`, entirely and deliberately. This module applies what
the planner decided and adds no rule of its own: a rule that lived here and not there would
mean the inventory a human read and approved was not the migration that ran.
"""

from __future__ import annotations

from pathlib import Path

from science_model.entity_schema import (
    EntityValidationError, EntityValidator, default_profile_for_kind,
)
from science_model.frontmatter import atomic_write_text, render_frontmatter, split_frontmatter

from science_tool.status_inventory import inventory, load_adjudication

ADJUDICATION_PATH = Path(".science/hypothesis-lifecycle.adjudication.yaml")
_DROPPED = ("phase", "disposition", "disposition_basis", "profile")


class MigrationRefused(Exception):
    """Raised when the corpus cannot be migrated. NOTHING has been written."""


def _render(path: Path, row) -> tuple[Path, str, dict]:
    fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
    fm["status"] = row.target_status
    if row.target_verdict is not None:
        fm["verdict"] = row.target_verdict
    if row.target_closure_basis is not None:
        fm["closure_basis"] = row.target_closure_basis
    for key in _DROPPED:
        fm.pop(key, None)
    return path, render_frontmatter(fm, body), fm


def migrate(project_root: Path, *, apply: bool) -> list[Path]:
    adjudication = load_adjudication(project_root / ADJUDICATION_PATH)
    inv = inventory(project_root, adjudication=adjudication)

    if inv.ambiguous:
        lines = [
            f"{len(inv.ambiguous)} hypothesis file(s) need an author's decision. "
            f"NOTHING has been written.",
            "",
        ]
        for row in inv.ambiguous:
            lines += [f"  {row.path}",
                      f"      status={row.status!r} phase={row.phase!r}",
                      f"      {row.ambiguity}", ""]
        lines.append(
            f"Record each decision in {ADJUDICATION_PATH} (status, verdict, closure_basis) "
            f"and re-run. Do NOT guess: a terminal status has already destroyed the prior "
            f"verdict, and inventing one would fabricate an epistemic conclusion."
        )
        raise MigrationRefused("\n".join(lines))

    # PHASE 1 -- render and validate EVERY target. No writes.
    validator = EntityValidator()
    profile = default_profile_for_kind("hypothesis")
    planned: list[tuple[Path, str]] = []
    failures: list[str] = []
    for row in inv.deterministic:
        try:
            path, text, fm = _render(row.path, row)
        except Exception as exc:  # render failure -- refuse the whole corpus
            failures.append(f"{row.path}: could not render: {exc}")
            continue
        try:
            validator.validate_as(fm, profile)
        except EntityValidationError as exc:
            failures.append(f"{row.path}: migrated form fails its own schema: {exc}")
            continue
        planned.append((path, text))

    if failures:
        raise MigrationRefused(
            "The migrated corpus would not satisfy its own schema. NOTHING has been "
            "written.\n\n" + "\n".join(f"  {f}" for f in failures)
        )

    if not apply:
        return [p for p, _ in planned]

    # PHASE 2 -- write. Every target is already rendered and schema-valid.
    for path, text in planned:
        atomic_write_text(path, text)

    # The version pin, LAST: a project is on schema 2 only once its files actually are.
    _set_entity_schema_version(project_root, 2)
    return [p for p, _ in planned]
```

> `_set_entity_schema_version` writes `entity_schema_version: 2` into `science.yaml`. It is the
> **final** act: a crash before it leaves the project unpinned, and unpinned means "not schema-2",
> so re-running is safe and idempotent.

- [ ] **Step 4: Green** — `6 passed`.

- [ ] **Step 5: Commit.**

---

### Task 10: Consumers — and **only** the hypothesis branch

**Files:**
- `science/src/science_tool/hypotheses_cli.py:28-34,62-64` — `--phase` → `--status`; the `promotion-criteria` section now triggers on `status == "draft"`
- `science/src/science_tool/entities_cli.py:94-125` — add `--verdict`, `--closure-basis`, `--superseded-by`
- `science/src/science_tool/entities.py:935-969` (`edit_entity`) — **the lifecycle boundary**
- `science/src/science_tool/entities.py:1377-1379` (`_validate_status`) — also fix its raw `KeyError` (it indexes `_STATUS_VALUES[kind]` and ignores project-local manifests, unlike `valid_statuses`)
- `science/src/science_tool/graph/materialize.py` — emit `sci:verdict`; **delete** `sci:disposition`
- `science/src/science_tool/graph/attention.py:125-137` — delete the `sci:disposition` terminal-exclusion; use the lifecycle instead
- `science/src/science_tool/validate/checks/dataset_capabilities.py:24-54` — **hypothesis branch only**
- `science/src/science_tool/validate/checks/hypotheses.py:23,64-70,127-136` — delete the `phase` check
- `science/src/science_tool/annotation/promote.py:330-331` — `fields["phase"] = "candidate"` → `fields["status"] = "draft"`
- `commands/big-picture.md:62,213-217` · `commands/add-hypothesis.md:124`

> ### ⛔ DO NOT TOUCH `DEBT_QUESTION_STATUSES`
> Rev 1 rewrote `is_question_debt` to take an `answer_state` — **while questions still encode
> answeredness in `status`, because `question` is a later slice.** That would have silently
> changed which questions count as debt: a live `status: partially-answered` would stop counting
> (it is not in `{active, deferred}` and has no `answer_state`), and `status: answered` would stop
> suppressing demand warnings. **A consumer may only be rewritten in its own kind's slice.**
> `attention.py:25-27` stays exactly as it is until the `question` slice.

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_hypothesis_consumers.py
def test_demand_closed_reads_the_hypothesis_VERDICT_now() -> None:
    # `refuted` was the ONLY hypothesis-specific value any consumer read
    # (dataset_capabilities.py:46). It is a verdict now, not a status.
    assert is_demand_closed(kind="hypothesis", status="active", verdict="refuted") is True
    assert is_demand_closed(kind="hypothesis", status="active", verdict="supported") is False
    assert is_demand_closed(kind="hypothesis", status="retired", verdict=None) is True


def test_QUESTION_demand_closure_is_UNCHANGED() -> None:
    # The question slice has not happened. Its statuses still carry answeredness, and this
    # predicate must keep reading them exactly as it does today.
    assert is_demand_closed(kind="question", status="answered", verdict=None) is True
    assert is_demand_closed(kind="question", status="active", verdict=None) is False


def test_question_debt_is_untouched() -> None:
    from science_tool.graph.attention import DEBT_QUESTION_STATUSES
    assert DEBT_QUESTION_STATUSES == frozenset({"active", "partially-answered", "deferred"})


def test_edit_status_is_the_lifecycle_boundary(tmp_project) -> None:
    # One generic boundary, not four invented verbs (design §9 D4). It schema-validates the
    # target, takes --closure-basis ATOMICALLY with the transition, and FAILS BEFORE WRITING.
    with pytest.raises(EntityCommandError, match="closure_basis"):
        edit_entity(tmp_project, "hypothesis:0001-x", status="retired")
    assert 'status: "active"' in (tmp_project / "entities/hypotheses/0001-x.md").read_text()

    edit_entity(tmp_project, "hypothesis:0001-x", status="retired", closure_basis="no samples")
    t = (tmp_project / "entities/hypotheses/0001-x.md").read_text()
    assert 'status: "retired"' in t and 'closure_basis: "no samples"' in t
```

- [ ] **Step 2: Run and fail.**

- [ ] **Step 3: Implement.** `dataset_capabilities` — change **only** the hypothesis branch:

```python
# questions still carry answeredness in `status` -- the question slice has not run.
_QUESTION_CLOSED = frozenset({"answered", "resolved", "closed", "rejected", "duplicate"})
_CLOSED_LIFECYCLE = frozenset({"superseded", "retired", "archived", "complete",
                               "abandoned", "deprecated"})


def is_demand_closed(*, kind: str, status: str | None, verdict: str | None = None) -> bool:
    """Whether a question/hypothesis still exerts live pull on data.

    Deliberately conservative -- a suppressor should fail toward KEEPING the warning, since a
    false-suppress hides a real coverage gap while a false-keep leaves only a low-value
    warning. So `supported` (can still be strengthened) and `weakened` (verdict still open)
    keep warning; only `refuted` settles the demand.
    """
    if status in _CLOSED_LIFECYCLE:
        return True
    if kind == "hypothesis":
        return verdict == "refuted"          # <- the ONLY change in this slice
    return status in _QUESTION_CLOSED        # <- questions: UNCHANGED
```

`edit_entity` — the generic lifecycle boundary (D4):

```python
def edit_entity(
    project_root: Path, ref: str, *,
    title: str | None = None, status: str | None = None,
    verdict: str | None = None, closure_basis: str | None = None,
    superseded_by: str | None = None,
    related: list[str] | None = None, source_refs: list[str] | None = None,
    updated: date | None = None, today: date | None = None,
) -> EntityWriteResult:
    project_root = project_root.resolve()
    _reject_if_archived(project_root, ref)
    location = find_entity(project_root, ref)
    frontmatter = dict(location.frontmatter)

    if title is not None:
        frontmatter["title"] = title
    if status is not None:
        frontmatter["status"] = status
    if verdict is not None:
        frontmatter["verdict"] = verdict
    if closure_basis is not None:
        frontmatter["closure_basis"] = closure_basis
    if superseded_by is not None:
        frontmatter["superseded_by"] = superseded_by
    if related:
        frontmatter["related"] = _append_unique_string_values(frontmatter.get("related"), related)
    if source_refs:
        frontmatter["source_refs"] = _append_unique_string_values(
            frontmatter.get("source_refs"), source_refs
        )
    frontmatter["updated"] = (updated or today or date.today()).isoformat()

    # THE lifecycle boundary. The composed schema is the authority, so a terminal transition
    # missing its basis fails HERE -- before a byte is written -- rather than landing on disk
    # and surfacing as a validate WARN later. `--closure-basis` is accepted ATOMICALLY with
    # the transition precisely so this can be a single check.
    _schema_validate_or_raise(project_root, location.kind, frontmatter)
    _resolution_check_or_raise(project_root, frontmatter)   # Task 7's cross-record layer

    text = _render_markdown(frontmatter, location.body)
    warnings = _validate_prospective_write(
        project_root=project_root, rel_path=Path(location.rel_path),
        text=text, target_entity_id=location.entity_id,
    )
    _atomic_replace_text(location.path, text)
    return EntityWriteResult(entity_id=location.entity_id, path=location.path, warnings=warnings)
```

where `_schema_validate_or_raise` derives the profile via `default_profile_for_kind`, **skips
kinds not yet in `PROJECT_MIXIN_NAMES`** (an explicit "not migrated", not a fallback), and
re-raises `EntityValidationError` as `EntityCommandError`.

- [ ] **Step 4: Green — everything, both packages, ruff, pyright.**

- [ ] **Step 5: Commit.**

---

### Task 11: Roll out across all 9 repos, with a graph diff

- [ ] **Step 1: For EACH of the 9 repos, in this order** (smallest first — a mistake is cheapest
  in `3d-attention-bias`):

```
3d-attention-bias (2) → cancer/therapeutics (3) → seq-feats (4) → health/meta (6) →
science/meta (7) → protein-landscape (7) → r/cbioportal (12) → natural-systems (14) → r/mm30 (30)
```

For each:

```bash
cd <repo>
uv run science graph build --output /tmp/claude-1000/before-$(basename $PWD).trig
uv run science entity status-inventory              # 0 refused, or adjudicate first
uv run science entity migrate-hypothesis --dry-run  # read the plan
uv run science entity migrate-hypothesis --apply    # two-phase; sets entity_schema_version: 2
uv run science graph build --output /tmp/claude-1000/after-$(basename $PWD).trig
uv run science validate; echo "exit=$?"             # MUST be 0
```

- [ ] **Step 2: Diff the graph and account for every triple.** Expected, and nothing else:
  - `sci:projectStatus` values change per the rev-7 mapping
  - **new** `sci:verdict` triples on exactly the hypotheses that carry one
  - **zero** `sci:disposition` triples before **and** after (never authored)
  - **no** `phase` triples in either (it never reached the graph — `Entity` is `extra="ignore"`)
  - **no** change to any non-hypothesis subject

  **Any unexplained triple means the slice is not atomic. Stop and find it.**

- [ ] **Step 3: With all 9 pinned, run validate everywhere one more time.**

```bash
for p in ~/d/natural-systems ~/d/r/mm30 ~/d/r/cbioportal ~/d/protein-landscape \
         ~/d/science/meta ~/d/health/meta ~/d/seq-feats ~/d/cancer/therapeutics ~/d/3d-attention-bias; do
  echo -n "$p: "; (cd "$p" && uv run science validate >/dev/null 2>&1; echo "exit=$?")
done
```
**All nine exit 0.** This is the step whose absence caused the original incident.

- [ ] **Step 4: Commit each repo separately** (they are separate git repos; several are
  Dropbox-only with no remote — **do not push**).

---

## Phase 4 — The ratchet

### Task 12: `hypothesis` → ERROR

- [ ] **Step 1: Write the failing test**

```python
def test_severity_is_a_property_of_the_KIND() -> None:
    # The original incident: severity graded on `layout_version >= 3`. All five projects were
    # v3, so the gate graded NOTHING and 472 entities errored the moment the check landed.
    assert _severity("hypothesis") is Severity.ERROR   # sources AND consumers certified
    assert _severity("report") is Severity.WARN        # not migrated
    assert _severity("question") is Severity.WARN
```

- [ ] **Step 2: Implement**

```python
# A kind joins this set at the END of its P2m slice -- never before. An uncertified
# instrument may not fail anyone's build.
_CERTIFIED_KINDS: frozenset[str] = frozenset({"hypothesis"})


def _severity(kind: str) -> Severity:
    return Severity.ERROR if kind in _CERTIFIED_KINDS else Severity.WARN
```

- [ ] **Step 3:** Re-run validate across all 9 repos. **All exit 0.**
- [ ] **Step 4: Commit.**

---

## What rev 1 got wrong

Recorded because three of these were **phasing** errors, and phasing errors are the ones that
survive review by looking like schedule rather than substance.

1. **It skipped P0.** The design says *inventory and declare every field, then migrate values*.
   Rev 1 went straight to the value migration and declared ~15 fields against a **36-key** real
   vocabulary. `unevaluatedProperties: false` would have rejected `required_capabilities` (38
   files), `lens_views` (28), and 18 more. Phase 0 exists now.
2. **Its strictness test proved nothing.** It asserted that `phase` is rejected — but `phase` is
   explicitly `false` in the schema. It never tested an *arbitrary* unknown key, which is the
   actual defect (`extra="ignore"` silently dropping undeclared keys).
3. **It would have validated the enriched dict.** `_enrich_raw` (`sources.py:713`) injects
   `project`, `canonical_id`, `profile`, `type`, `aliases`, `content_preview` **before** Pydantic
   sees a record. Closing the schema over that would have declared six fields no author ever wrote.
4. **Its migration could not escape its own refusal.** The refusal said *"fix the file and re-run"* —
   but the classifier re-reads the same terminal `status` and refuses again, forever. `0009` had
   **no path through**. An adjudication artifact fixes it; inferring from file shape cannot.
5. **Its migration was not transactional.** A `write_text` loop leaves a half-migrated corpus on
   any failure — two meanings of `status` live at once, the exact state that forces the forbidden
   compatibility layer. Now: render + schema-validate **everything**, then write.
6. **It migrated one repo and expected eight others to keep working.** `default_profile_for_kind`
   is global; wiring it flips every project at once. There are **9 repos** and 147 files. Fixed by
   an explicit per-project `entity_schema_version` pin — a *declaration*, not a heuristic.
7. **It rebuilt the second authority D3 abolishes.** It duplicated `complete requires a verdict`
   as a Pydantic `model_validator` alongside the JSON Schema `if/then`. Two authorities always
   drift. Replaced by a **reconciliation test**.
8. **It admitted, in its own self-review, that `check_resolution` was never wired** — and shipped
   anyway. Presence enforced, resolution not: the dangling-`superseded_by` hole, reopened by the
   very task written to close it.

**The pattern:** rev 1 reasoned about the *design* and never about the *corpus* or the *call
graph*. Exactly the failure rev 7 of the design caught in itself — and I repeated it one document
later.

## What this plan does NOT do

- **The other 32 kinds.** This builds the machinery and migrates **one**. `question` is the
  natural second (the only kind whose status values actually drive behaviour) — and its consumers
  are deliberately **untouched** here.
- **P1 (absorb `provided_capabilities`/`required_capabilities`).** Declared in the mixin, not
  absorbed.
- **`science:graph` / `science:axis`** (design §3, §5). Not needed to migrate `hypothesis`.
- **Verdict-has-evidence** — a graph-time invariant, not a load-time one (Task 7).
- **The 6 filed defects**, notably **`fb-2026-07-12-006`: every commons dataset is on a crashing
  overlay path today.** Independent of this arc; worth fixing sooner.
- **The 169 residual status-vocabulary WARNs** on other kinds. They stay WARNs until their slices.
