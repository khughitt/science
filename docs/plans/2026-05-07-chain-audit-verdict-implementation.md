# Chain-Audit Verdict — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote structural chains and their audit verdicts to first-class graph entities so the existing `bears_on` machinery propagates freshness automatically when chain components or shape change. Closes the gap surfaced by the natural-systems t473 stress test.

**Architecture:** Two new EPISTEMIC entity kinds (`structural-chain`, `chain-audit`), two new relation kinds (`has_link`, `audits`), one targeted extension to `bears_on.target_kinds`, ordered serialization via `sci:linkSequence` RDF list + flat `sci:hasLink` triples, and explicit reference-audit coverage for the new frontmatter fields. Verdict-block integration with `verdict/parser.py` is enforced through a Pydantic cross-field validator. No edits to existing entities or to the validator shell scripts.

**Tech Stack:** Python 3.12, Pydantic v2, rdflib (Dataset, URIRef, RDF lists), pytest. Codebase: `science/model/` (data model package), `science/src/science_tool/` (tool package).

**Spec:** `docs/plans/2026-05-07-chain-audit-verdict-design.md`.

---

## File structure

| File | Responsibility | Action |
|---|---|---|
| `science/model/src/science_model/entities.py` | Entity Pydantic models | Add `BayesFactorEvidence`, `StructuralChainEntity`, `ChainAuditEntity` |
| `science/model/src/science_model/profiles/core.py` | Core profile manifest | Register new kinds; add `has_link`/`audits`; extend `bears_on.target_kinds` |
| `science/src/science_tool/graph/entity_registry.py` | Runtime kind class registry | Register new kinds with `entity_class=EPISTEMIC` |
| `science/src/science_tool/graph/freshness.py` | `bears_on` derivers | Add `derive_bears_on_from_chain_links` and `derive_bears_on_from_audits` |
| `science/src/science_tool/graph/materialize.py` | Frontmatter → triples | Emit `sci:hasLink`, `sci:linkSequence` (RDF list), `sci:audits`; wire new derivers |
| `science/src/science_tool/graph/migrate.py` | Reference auditing | Extend `_audit_entity` for `chain[]`, `audits`, `proposition_refs[]` |
| `science/model/tests/test_chain_entities.py` | New — model tests | All Pydantic-level rules |
| `science/tests/test_chain_materialize.py` | New — materialization tests | Triple emission + reorder regression |
| `science/tests/test_chain_bears_on.py` | New — derivation tests | Inverse rules + closure |
| `science/tests/test_chain_freshness_integration.py` | New — end-to-end | Propagation through chain → chain-audit |
| `science/tests/test_chain_audit_references.py` | New — reference auditing | Dangling refs in new fields |
| `docs/claim-and-evidence-model.md` | Project doc | Brief section on chain-audit semantics |

`scripts/validate.sh` and `meta/validate.sh` are shims; the managed body at `science/src/science_tool/project_artifacts/data/validate.sh` does **not** need changes — the orchestrator already invokes the Python validators that pick up our additions (Pydantic, `audit_project_sources`, `relation_allows_kinds`).

---

## Working environment

All commands assume CWD `~/d/science`. Tests run via `uv run --project science pytest <path>` or `uv run --project science/model pytest <path>` depending on package. Use `-v` for visibility.

Each task ends with a commit. Commit message convention: `feat(chain-audit): <task scope>` for additive code, `test(chain-audit): <task scope>` if a task is test-only.

---

## Task 1: `BayesFactorEvidence` Pydantic model

**Files:**
- Modify: `science/model/src/science_model/entities.py`
- Create: `science/model/tests/test_chain_entities.py`

- [ ] **Step 1.1: Write the failing test**

Create `science/model/tests/test_chain_entities.py`:

```python
"""Tests for chain-audit entity models (StructuralChain, ChainAudit, BayesFactorEvidence)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_model.entities import BayesFactorEvidence


class TestBayesFactorEvidence:
    def test_minimal_evidence_for(self):
        bf = BayesFactorEvidence(
            hypothesis_ref="hypothesis:foo",
            null_baseline="uniform random link substitution",
            interpretation="evidence-for",
        )
        assert bf.bf10 is None
        assert bf.interpretation == "evidence-for"

    def test_accepts_all_four_interpretations(self):
        for interp in ("evidence-for", "evidence-against", "mixed", "inconclusive"):
            bf = BayesFactorEvidence(
                hypothesis_ref="hypothesis:foo",
                null_baseline="uniform",
                interpretation=interp,
            )
            assert bf.interpretation == interp

    def test_rejects_evidence_for_risk(self):
        # evidence-for-risk is intentionally dropped from chain-audit's enum
        # (t037-specific risk framing has no clean predicted-direction-agnostic mapping).
        with pytest.raises(ValidationError):
            BayesFactorEvidence(
                hypothesis_ref="hypothesis:foo",
                null_baseline="uniform",
                interpretation="evidence-for-risk",
            )

    def test_rejects_unknown_interpretation(self):
        with pytest.raises(ValidationError):
            BayesFactorEvidence(
                hypothesis_ref="hypothesis:foo",
                null_baseline="uniform",
                interpretation="bogus",
            )

    def test_bf10_optional(self):
        bf = BayesFactorEvidence(
            hypothesis_ref="hypothesis:foo",
            null_baseline="uniform",
            interpretation="evidence-for",
            bf10=3.5,
        )
        assert bf.bf10 == 3.5

    def test_rejects_non_positive_bf10(self):
        with pytest.raises(ValidationError):
            BayesFactorEvidence(
                hypothesis_ref="hypothesis:foo",
                null_baseline="uniform",
                interpretation="evidence-for",
                bf10=0.0,
            )
        with pytest.raises(ValidationError):
            BayesFactorEvidence(
                hypothesis_ref="hypothesis:foo",
                null_baseline="uniform",
                interpretation="evidence-for",
                bf10=-1.0,
            )

    def test_rejects_empty_null_baseline(self):
        with pytest.raises(ValidationError):
            BayesFactorEvidence(
                hypothesis_ref="hypothesis:foo",
                null_baseline="",
                interpretation="evidence-for",
            )
```

- [ ] **Step 1.2: Run the test to verify it fails**

```bash
uv run --project science/model pytest science/model/tests/test_chain_entities.py -v
```

Expected: ImportError or `cannot import name 'BayesFactorEvidence'`.

- [ ] **Step 1.3: Implement `BayesFactorEvidence`**

In `science/model/src/science_model/entities.py`, add after the existing imports (Pydantic `BaseModel` is already imported):

```python
from enum import StrEnum


class ChainAuditInterpretation(StrEnum):
    EVIDENCE_FOR = "evidence-for"
    EVIDENCE_AGAINST = "evidence-against"
    MIXED = "mixed"
    INCONCLUSIVE = "inconclusive"


class BayesFactorEvidence(BaseModel):
    """Bayes-factor-style evidence carried by a chain-audit.

    `interpretation` is the load-bearing field; `bf10` is optional because
    many chain audits are categorical (no numeric BF available).
    """

    hypothesis_ref: str
    null_baseline: str
    interpretation: ChainAuditInterpretation
    bf10: float | None = None

    @model_validator(mode="after")
    def _validate_bf10_positive(self) -> "BayesFactorEvidence":
        if self.bf10 is not None and self.bf10 <= 0:
            raise ValueError("bf10 must be a positive number when set")
        return self

    @model_validator(mode="after")
    def _validate_null_baseline_nonempty(self) -> "BayesFactorEvidence":
        if not self.null_baseline.strip():
            raise ValueError("null_baseline must be non-empty")
        return self
```

`StrEnum` may already be imported in entities.py — if so, don't re-import. `model_validator` is already imported (used by `EpistemicReviewState`).

- [ ] **Step 1.4: Run tests to verify pass**

```bash
uv run --project science/model pytest science/model/tests/test_chain_entities.py -v
```

Expected: 7 passed.

- [ ] **Step 1.5: Commit**

```bash
git add science/model/src/science_model/entities.py science/model/tests/test_chain_entities.py
git commit -m "feat(chain-audit): add BayesFactorEvidence model"
```

---

## Task 2: `StructuralChainEntity` model

**Files:**
- Modify: `science/model/src/science_model/entities.py`
- Modify: `science/model/tests/test_chain_entities.py`

- [ ] **Step 2.1: Write the failing test**

Append to `test_chain_entities.py`:

```python
from datetime import date

from science_model.entities import StructuralChainEntity


def _chain_kwargs(**overrides):
    """Common required fields for a structural-chain instance."""
    base = dict(
        id="chain:fp",
        canonical_id="natural-systems/chain:fp",
        kind="structural-chain",
        title="FP chain",
        project="natural-systems",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="core/chains/fp.md",
        chain=["mechanism:a", "mechanism:b", "mechanism:c"],
    )
    base.update(overrides)
    return base


class TestStructuralChainEntity:
    def test_minimal_three_link(self):
        entity = StructuralChainEntity(**_chain_kwargs())
        assert entity.kind == "structural-chain"
        assert len(entity.chain) == 3

    def test_two_links_minimum_accepted(self):
        entity = StructuralChainEntity(**_chain_kwargs(chain=["mechanism:a", "mechanism:b"]))
        assert len(entity.chain) == 2

    def test_rejects_single_link(self):
        with pytest.raises(ValidationError):
            StructuralChainEntity(**_chain_kwargs(chain=["mechanism:a"]))

    def test_rejects_empty_chain(self):
        with pytest.raises(ValidationError):
            StructuralChainEntity(**_chain_kwargs(chain=[]))

    def test_rejects_duplicate_links(self):
        with pytest.raises(ValidationError):
            StructuralChainEntity(
                **_chain_kwargs(chain=["mechanism:a", "mechanism:b", "mechanism:a"])
            )

    def test_title_required(self):
        # Entity.title is required at the base class; missing it should ValidationError.
        kwargs = _chain_kwargs()
        del kwargs["title"]
        with pytest.raises(ValidationError):
            StructuralChainEntity(**kwargs)
```

- [ ] **Step 2.2: Run to verify failure**

```bash
uv run --project science/model pytest science/model/tests/test_chain_entities.py::TestStructuralChainEntity -v
```

Expected: ImportError on `StructuralChainEntity`.

- [ ] **Step 2.3: Implement `StructuralChainEntity`**

Append to `science/model/src/science_model/entities.py` (place after `Entity` and other entity subclasses; follow the existing `ProjectEntity` / `MechanismEntity` pattern for an `Entity` subclass):

```python
class StructuralChainEntity(Entity):
    """A first-class structural decomposition: an ordered chain of ≥2 entity refs.

    Chain links are restricted at the relation-kind layer to mechanism, model,
    proposition, observation, or finding. Link-kind enforcement happens at
    materialize-time via `relation_allows_kinds(has_link, ...)` — this model
    only enforces shape (length, no duplicates).
    """

    chain: list[str]

    @model_validator(mode="after")
    def _validate_chain_shape(self) -> "StructuralChainEntity":
        if len(self.chain) < 2:
            raise ValueError("structural-chain requires at least two links")
        if len(set(self.chain)) != len(self.chain):
            raise ValueError("structural-chain links must be distinct (no duplicates)")
        return self
```

- [ ] **Step 2.4: Run to verify pass**

```bash
uv run --project science/model pytest science/model/tests/test_chain_entities.py::TestStructuralChainEntity -v
```

Expected: 6 passed.

- [ ] **Step 2.5: Commit**

```bash
git add science/model/src/science_model/entities.py science/model/tests/test_chain_entities.py
git commit -m "feat(chain-audit): add StructuralChainEntity model"
```

---

## Task 3: `ChainAuditEntity` model with verdict↔BF consistency

**Files:**
- Modify: `science/model/src/science_model/entities.py`
- Modify: `science/model/tests/test_chain_entities.py`

- [ ] **Step 3.1: Write the failing test**

Append to `test_chain_entities.py`:

```python
from science_model.entities import ChainAuditEntity


def _audit_kwargs(**overrides):
    base = dict(
        id="chain-audit:fp-2026-05",
        canonical_id="natural-systems/chain-audit:fp-2026-05",
        kind="chain-audit",
        title="FP coupling audit (2026-05)",
        project="natural-systems",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="doc/audits/fp-2026-05.md",
        audits="chain:fp",
        proposition_refs=[],
        bayes_factor_evidence=BayesFactorEvidence(
            hypothesis_ref="hypothesis:fp-coupling",
            null_baseline="uniform random link substitution",
            interpretation="evidence-against",
        ),
        verdict={
            "composite": "[-]",
            "rule": "single-claim",
            "claims": [
                {
                    "id": "claim:fp-coupling-load-bearing",
                    "polarity": "[-]",
                    "strength": "load-bearing",
                    "evidence_summary": "Removing FP eliminates the coupling.",
                }
            ],
        },
    )
    base.update(overrides)
    return base


class TestChainAuditEntity:
    def test_minimal_audit(self):
        entity = ChainAuditEntity(**_audit_kwargs())
        assert entity.audits == "chain:fp"
        assert entity.bayes_factor_evidence.interpretation == "evidence-against"

    def test_audits_required(self):
        kwargs = _audit_kwargs()
        del kwargs["audits"]
        with pytest.raises(ValidationError):
            ChainAuditEntity(**kwargs)

    def test_bayes_factor_evidence_required(self):
        kwargs = _audit_kwargs()
        del kwargs["bayes_factor_evidence"]
        with pytest.raises(ValidationError):
            ChainAuditEntity(**kwargs)

    def test_verdict_required(self):
        kwargs = _audit_kwargs()
        del kwargs["verdict"]
        with pytest.raises(ValidationError):
            ChainAuditEntity(**kwargs)

    def test_verdict_bf_consistency_evidence_for_maps_to_positive(self):
        bf = BayesFactorEvidence(
            hypothesis_ref="hypothesis:fp-coupling",
            null_baseline="uniform",
            interpretation="evidence-for",
        )
        verdict = {
            "composite": "[+]",
            "rule": "single-claim",
            "claims": [{"id": "claim:x", "polarity": "[+]"}],
        }
        entity = ChainAuditEntity(**_audit_kwargs(bayes_factor_evidence=bf, verdict=verdict))
        assert entity.verdict["composite"] == "[+]"

    def test_verdict_bf_consistency_mismatch_rejected(self):
        # interpretation: evidence-against → expected composite [-]; but verdict says [+].
        verdict = {
            "composite": "[+]",
            "rule": "single-claim",
            "claims": [{"id": "claim:x", "polarity": "[+]"}],
        }
        with pytest.raises(ValidationError) as excinfo:
            ChainAuditEntity(**_audit_kwargs(verdict=verdict))
        assert "interpretation" in str(excinfo.value).lower() or "composite" in str(excinfo.value).lower()

    def test_verdict_bf_consistency_full_mapping(self):
        cases = [
            ("evidence-for", "[+]"),
            ("evidence-against", "[-]"),
            ("mixed", "[~]"),
            ("inconclusive", "[?]"),
        ]
        for interp, token in cases:
            bf = BayesFactorEvidence(
                hypothesis_ref="hypothesis:fp-coupling",
                null_baseline="uniform",
                interpretation=interp,
            )
            verdict = {
                "composite": token,
                "rule": "single-claim",
                "claims": [{"id": "claim:x", "polarity": token}],
            }
            entity = ChainAuditEntity(**_audit_kwargs(bayes_factor_evidence=bf, verdict=verdict))
            assert entity.verdict["composite"] == token
```

- [ ] **Step 3.2: Run to verify failure**

```bash
uv run --project science/model pytest science/model/tests/test_chain_entities.py::TestChainAuditEntity -v
```

Expected: ImportError on `ChainAuditEntity`.

- [ ] **Step 3.3: Implement `ChainAuditEntity`**

Append to `science/model/src/science_model/entities.py`:

```python
_INTERPRETATION_TO_COMPOSITE: dict[ChainAuditInterpretation, str] = {
    ChainAuditInterpretation.EVIDENCE_FOR: "[+]",
    ChainAuditInterpretation.EVIDENCE_AGAINST: "[-]",
    ChainAuditInterpretation.MIXED: "[~]",
    ChainAuditInterpretation.INCONCLUSIVE: "[?]",
}


class ChainAuditEntity(Entity):
    """A verdict over a structural-chain.

    Carries both a `verdict:` block (compatible with verdict/parser.py) and a
    `bayes_factor_evidence:` block. The validator enforces consistency
    between `verdict.composite` and `bayes_factor_evidence.interpretation`
    via the documented mapping table.
    """

    audits: str
    proposition_refs: list[str] = Field(default_factory=list)
    bayes_factor_evidence: BayesFactorEvidence
    verdict: dict
    rationale: str = ""

    @model_validator(mode="after")
    def _validate_verdict_consistency(self) -> "ChainAuditEntity":
        composite = self.verdict.get("composite")
        if composite is None:
            raise ValueError("verdict.composite is required on chain-audit")
        expected = _INTERPRETATION_TO_COMPOSITE[self.bayes_factor_evidence.interpretation]
        if composite != expected:
            raise ValueError(
                f"verdict.composite ({composite!r}) inconsistent with "
                f"bayes_factor_evidence.interpretation "
                f"({self.bayes_factor_evidence.interpretation.value!r}); "
                f"expected composite {expected!r}"
            )
        return self
```

`Field` is already imported at the top of entities.py.

- [ ] **Step 3.4: Run to verify pass**

```bash
uv run --project science/model pytest science/model/tests/test_chain_entities.py -v
```

Expected: all model tests pass (Tasks 1+2+3 = ~20 passed).

- [ ] **Step 3.5: Commit**

```bash
git add science/model/src/science_model/entities.py science/model/tests/test_chain_entities.py
git commit -m "feat(chain-audit): add ChainAuditEntity with verdict↔BF consistency"
```

---

## Task 4: Register kinds in core profile and entity registry

**Files:**
- Modify: `science/model/src/science_model/profiles/core.py`
- Modify: `science/src/science_tool/graph/entity_registry.py`
- Modify: `science/model/tests/test_bears_on_relation.py` (existing test will need its expected set updated in Task 6, but kind registration is checked independently here)
- Create: `science/tests/test_chain_kinds_registered.py`

- [ ] **Step 4.1: Write the failing test**

Create `science/tests/test_chain_kinds_registered.py`:

```python
"""Verify structural-chain and chain-audit are registered as core EPISTEMIC kinds."""

from __future__ import annotations

from science_model.entities import EntityClass
from science_model.profiles.core import CORE_PROFILE
from science_tool.graph.entity_registry import EntityRegistry


def test_structural_chain_in_core_profile():
    kinds = {k.name for k in CORE_PROFILE.entity_kinds}
    assert "structural-chain" in kinds


def test_chain_audit_in_core_profile():
    kinds = {k.name for k in CORE_PROFILE.entity_kinds}
    assert "chain-audit" in kinds


def test_structural_chain_kind_class_is_epistemic():
    registry = EntityRegistry.with_core_types()
    assert registry.kind_class("structural-chain") == EntityClass.EPISTEMIC


def test_chain_audit_kind_class_is_epistemic():
    registry = EntityRegistry.with_core_types()
    assert registry.kind_class("chain-audit") == EntityClass.EPISTEMIC
```

- [ ] **Step 4.2: Run to verify failure**

```bash
uv run --project science pytest science/tests/test_chain_kinds_registered.py -v
```

Expected: AssertionError ("structural-chain" not in kinds).

- [ ] **Step 4.3: Register the kinds in the core profile**

In `science/model/src/science_model/profiles/core.py`, find the `entity_kinds` list inside `CORE_PROFILE` (around line 24). Append two `EntityKind` entries (the existing entries each have `name`, `canonical_prefix`, `layer`, `description`):

```python
        EntityKind(
            name="structural-chain",
            canonical_prefix="chain",
            layer="layer/core",
            description="Ordered structural decomposition: ≥2 entity refs forming a chain whose verdicts are carried by chain-audit.",
        ),
        EntityKind(
            name="chain-audit",
            canonical_prefix="chain-audit",
            layer="layer/core",
            description="Verdict over a structural-chain. Carries verdict+bayes_factor_evidence with enforced consistency.",
        ),
```

- [ ] **Step 4.4: Register the kinds in the entity registry**

In `science/src/science_tool/graph/entity_registry.py`, find `_CORE_KIND_CLASSES` (the dict mapping kind name → `EntityClass`) and add:

```python
    "structural-chain": EntityClass.EPISTEMIC,
    "chain-audit": EntityClass.EPISTEMIC,
```

Then in `with_core_types()`, after the existing `register_core_kind(...)` calls for the specialized kinds (mechanism, theme, etc., near line 104), add:

```python
        r.register_core_kind(
            "structural-chain",
            StructuralChainEntity,
            entity_class=_CORE_KIND_CLASSES["structural-chain"],
        )
        r.register_core_kind(
            "chain-audit",
            ChainAuditEntity,
            entity_class=_CORE_KIND_CLASSES["chain-audit"],
        )
```

Add the import at the top:

```python
from science_model.entities import (
    # ... existing imports ...
    ChainAuditEntity,
    StructuralChainEntity,
)
```

- [ ] **Step 4.5: Run to verify pass**

```bash
uv run --project science pytest science/tests/test_chain_kinds_registered.py -v
```

Expected: 4 passed.

- [ ] **Step 4.6: Commit**

```bash
git add science/model/src/science_model/profiles/core.py science/src/science_tool/graph/entity_registry.py science/tests/test_chain_kinds_registered.py
git commit -m "feat(chain-audit): register structural-chain and chain-audit as EPISTEMIC kinds"
```

---

## Task 5: Add `has_link` and `audits` relation kinds

**Files:**
- Modify: `science/model/src/science_model/profiles/core.py`
- Create: `science/model/tests/test_chain_relations.py`

- [ ] **Step 5.1: Write the failing test**

Create `science/model/tests/test_chain_relations.py`:

```python
"""Tests for has_link and audits relation kinds in the core profile."""

from __future__ import annotations

from science_model.profiles.core import CORE_PROFILE
from science_model.relations import relation_allows_kinds


def _relation(name: str):
    return next(r for r in CORE_PROFILE.relation_kinds if r.name == name)


class TestHasLink:
    def test_declared(self):
        assert "has_link" in {r.name for r in CORE_PROFILE.relation_kinds}

    def test_predicate(self):
        assert _relation("has_link").predicate == "sci:hasLink"

    def test_source_restricted_to_structural_chain(self):
        assert _relation("has_link").source_kinds == ["structural-chain"]

    def test_target_kinds_match_allowlist(self):
        expected = {"mechanism", "model", "proposition", "observation", "finding"}
        assert set(_relation("has_link").target_kinds) == expected

    def test_relation_allows_valid_pair(self):
        assert relation_allows_kinds(_relation("has_link"), "structural-chain", "mechanism")
        assert relation_allows_kinds(_relation("has_link"), "structural-chain", "finding")

    def test_relation_rejects_invalid_target_kind(self):
        # task is not in the link allowlist
        assert not relation_allows_kinds(_relation("has_link"), "structural-chain", "task")

    def test_relation_rejects_non_chain_source(self):
        assert not relation_allows_kinds(_relation("has_link"), "hypothesis", "mechanism")


class TestAudits:
    def test_declared(self):
        assert "audits" in {r.name for r in CORE_PROFILE.relation_kinds}

    def test_predicate(self):
        assert _relation("audits").predicate == "sci:audits"

    def test_source_restricted_to_chain_audit(self):
        assert _relation("audits").source_kinds == ["chain-audit"]

    def test_target_restricted_to_structural_chain(self):
        assert _relation("audits").target_kinds == ["structural-chain"]

    def test_relation_allows_valid_pair(self):
        assert relation_allows_kinds(_relation("audits"), "chain-audit", "structural-chain")

    def test_relation_rejects_non_audit_source(self):
        assert not relation_allows_kinds(_relation("audits"), "interpretation", "structural-chain")

    def test_relation_rejects_non_chain_target(self):
        assert not relation_allows_kinds(_relation("audits"), "chain-audit", "hypothesis")
```

- [ ] **Step 5.2: Run to verify failure**

```bash
uv run --project science/model pytest science/model/tests/test_chain_relations.py -v
```

Expected: KeyError / StopIteration on `next(...)` because the relations aren't declared yet.

- [ ] **Step 5.3: Add the relation kinds**

In `science/model/src/science_model/profiles/core.py`, add to the `relation_kinds` list (find the existing `bears_on` `RelationKind(...)` declaration; add these adjacent for readability):

```python
        RelationKind(
            name="has_link",
            predicate="sci:hasLink",
            source_kinds=["structural-chain"],
            target_kinds=["mechanism", "model", "proposition", "observation", "finding"],
            layer="layer/core",
            description=(
                "Ordered structural-chain link. Targets are restricted to the "
                "structural building blocks. Order is carried in the materialized "
                "graph by sci:linkSequence (RDF list)."
            ),
        ),
        RelationKind(
            name="audits",
            predicate="sci:audits",
            source_kinds=["chain-audit"],
            target_kinds=["structural-chain"],
            layer="layer/core",
            description=(
                "A chain-audit asserts a verdict over a structural-chain. "
                "Mirrors the shape of `tests` (single target by convention)."
            ),
        ),
```

- [ ] **Step 5.4: Run to verify pass**

```bash
uv run --project science/model pytest science/model/tests/test_chain_relations.py -v
```

Expected: all tests pass.

- [ ] **Step 5.5: Commit**

```bash
git add science/model/src/science_model/profiles/core.py science/model/tests/test_chain_relations.py
git commit -m "feat(chain-audit): add has_link and audits relation kinds"
```

---

## Task 6: Extend `bears_on.target_kinds`

**Files:**
- Modify: `science/model/src/science_model/profiles/core.py`
- Modify: `science/model/tests/test_bears_on_relation.py`

- [ ] **Step 6.1: Update the existing exact-match test to include the new kinds**

The existing `test_bears_on_targets_match_target_kinds_exactly` in `science/model/tests/test_bears_on_relation.py` asserts the EXACT set. Read it; update the `expected` set to include `"structural-chain"` and `"chain-audit"`:

```python
    expected = {
        "assumption",
        "chain-audit",
        "discussion",
        "finding",
        "hypothesis",
        "interpretation",
        "mechanism",
        "observation",
        "proposition",
        "question",
        "report",
        "story",
        "structural-chain",
        "theme",
        "validation-report",
    }
```

- [ ] **Step 6.2: Add a new test asserting `relation_allows_kinds` for the new targets**

Append to `science/model/tests/test_bears_on_relation.py`:

```python
def test_bears_on_allows_structural_chain_as_target():
    bears_on = next(r for r in CORE_PROFILE.relation_kinds if r.name == "bears_on")
    assert relation_allows_kinds(bears_on, "mechanism", "structural-chain")
    assert relation_allows_kinds(bears_on, "finding", "structural-chain")


def test_bears_on_allows_chain_audit_as_target():
    bears_on = next(r for r in CORE_PROFILE.relation_kinds if r.name == "bears_on")
    assert relation_allows_kinds(bears_on, "structural-chain", "chain-audit")


def test_bears_on_still_rejects_dataset_target():
    # Regression: bears_on must not accept operational kinds.
    bears_on = next(r for r in CORE_PROFILE.relation_kinds if r.name == "bears_on")
    assert not relation_allows_kinds(bears_on, "interpretation", "dataset")
```

Add `from science_model.relations import relation_allows_kinds` at the top of the file if not already imported.

- [ ] **Step 6.3: Run to verify failure**

```bash
uv run --project science/model pytest science/model/tests/test_bears_on_relation.py -v
```

Expected: the exact-match test and the two new "allows" tests fail.

- [ ] **Step 6.4: Extend `bears_on.target_kinds` in core.py**

In `science/model/src/science_model/profiles/core.py`, find the `bears_on` `RelationKind` and add `"structural-chain"` and `"chain-audit"` to its `target_kinds` list (alphabetical order matches the test's expected set).

- [ ] **Step 6.5: Run to verify pass**

```bash
uv run --project science/model pytest science/model/tests/test_bears_on_relation.py -v
```

Expected: all tests pass.

- [ ] **Step 6.6: Commit**

```bash
git add science/model/src/science_model/profiles/core.py science/model/tests/test_bears_on_relation.py
git commit -m "feat(chain-audit): extend bears_on.target_kinds for new EPISTEMIC kinds"
```

---

## Task 7: Materialize chain triples (`sci:hasLink`, `sci:linkSequence`, `sci:audits`)

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py`
- Create: `science/tests/test_chain_materialize.py`

- [ ] **Step 7.1: Write the failing test**

Create `science/tests/test_chain_materialize.py`:

```python
"""Tests for chain-related triple emission during materialize."""

from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import Dataset, URIRef
from rdflib.namespace import RDF

from science_tool.graph.materialize import build_dataset
from science_tool.graph.store import PROJECT_NS, SCI_NS


def _write(tmp_path: Path, rel: str, body: str) -> None:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)


def _minimal_project(tmp_path: Path) -> Path:
    """Materialize a project with three mechanism entities + one chain + one chain-audit."""
    _write(tmp_path, "science.yaml", "name: test\nproject_id: test\nprofile: core\n")
    for slug in ("a", "b", "c"):
        _write(
            tmp_path,
            f"core/mechanisms/{slug}.md",
            f"""---
id: mechanism:{slug}
kind: mechanism
title: "Mechanism {slug}"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
---
""",
        )
    _write(
        tmp_path,
        "core/chains/abc.md",
        """---
id: chain:abc
kind: structural-chain
title: "A → B → C chain"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
chain:
  - mechanism:a
  - mechanism:b
  - mechanism:c
---
""",
    )
    _write(
        tmp_path,
        "doc/audits/abc-2026-05.md",
        """---
id: chain-audit:abc-2026-05
kind: chain-audit
title: "ABC audit"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
audits: chain:abc
proposition_refs: []
bayes_factor_evidence:
  hypothesis_ref: hypothesis:abc-coupling
  null_baseline: "uniform"
  interpretation: evidence-against
verdict:
  composite: "[-]"
  rule: single-claim
  claims:
    - id: claim:abc
      polarity: "[-]"
---
""",
    )
    return tmp_path


def test_has_link_triples_emitted(tmp_path):
    project = _minimal_project(tmp_path)
    dataset = build_dataset(project)
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    chain_uri = URIRef(f"{PROJECT_NS}entity/chain/abc")
    targets = {str(o) for _, _, o in knowledge.triples((chain_uri, SCI_NS.hasLink, None))}
    assert len(targets) == 3
    assert any(t.endswith("/mechanism/a") for t in targets)
    assert any(t.endswith("/mechanism/b") for t in targets)
    assert any(t.endswith("/mechanism/c") for t in targets)


def test_link_sequence_rdf_list_emitted(tmp_path):
    """sci:linkSequence carries order via rdf:first / rdf:rest / rdf:nil."""
    project = _minimal_project(tmp_path)
    dataset = build_dataset(project)
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    chain_uri = URIRef(f"{PROJECT_NS}entity/chain/abc")
    head_triples = list(knowledge.triples((chain_uri, SCI_NS.linkSequence, None)))
    assert len(head_triples) == 1, "exactly one linkSequence triple per chain"
    head = head_triples[0][2]

    # Walk the rdf:list
    ordered = []
    cur = head
    while cur != RDF.nil:
        first = next(knowledge.triples((cur, RDF.first, None)))[2]
        ordered.append(str(first))
        cur = next(knowledge.triples((cur, RDF.rest, None)))[2]
    assert len(ordered) == 3
    assert ordered[0].endswith("/mechanism/a")
    assert ordered[1].endswith("/mechanism/b")
    assert ordered[2].endswith("/mechanism/c")


def test_audits_triple_emitted(tmp_path):
    project = _minimal_project(tmp_path)
    dataset = build_dataset(project)
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    audit_uri = URIRef(f"{PROJECT_NS}entity/chain-audit/abc-2026-05")
    chain_uri = URIRef(f"{PROJECT_NS}entity/chain/abc")
    triples = list(knowledge.triples((audit_uri, SCI_NS.audits, chain_uri)))
    assert len(triples) == 1
```

Note on `build_dataset`: the test uses the materializer's top-level entry point. If the import path differs, read `materialize.py` to find the correct symbol (commonly named `build_dataset`, `materialize_project`, or similar) and update the import.

- [ ] **Step 7.2: Run to verify failure**

```bash
uv run --project science pytest science/tests/test_chain_materialize.py -v
```

Expected: all three tests fail (no triples emitted yet, or import error).

- [ ] **Step 7.3: Implement triple emission**

In `science/src/science_tool/graph/materialize.py`, find the section where `_add_relations` (or equivalent) handles per-entity-kind triple emission (around lines 240–290 you'll see `hasParticipant`, `hasProposition`, etc. — the same place is where new kinds' relations should be emitted).

Add a helper:

```python
def _emit_chain_triples(
    knowledge: Graph,
    entity: Entity,
    entity_uri: URIRef,
    canonical_resolver,  # whatever signature surrounding code uses to resolve refs
) -> None:
    """Emit sci:hasLink (flat) + sci:linkSequence (RDF list) for a structural-chain."""
    if entity.kind != "structural-chain":
        return
    chain = getattr(entity, "chain", None) or []
    link_uris: list[URIRef] = []
    for ref in chain:
        target_uri = _entity_uri(canonical_resolver(ref))
        knowledge.add((entity_uri, SCI_NS.hasLink, target_uri))
        link_uris.append(target_uri)
    # Build RDF list head→...→nil for sci:linkSequence
    if link_uris:
        from rdflib import BNode
        from rdflib.namespace import RDF
        nodes = [BNode() for _ in link_uris]
        for i, (node, link_uri) in enumerate(zip(nodes, link_uris)):
            knowledge.add((node, RDF.first, link_uri))
            rest = nodes[i + 1] if i + 1 < len(nodes) else RDF.nil
            knowledge.add((node, RDF.rest, rest))
        knowledge.add((entity_uri, SCI_NS.linkSequence, nodes[0]))


def _emit_audits_triple(
    knowledge: Graph,
    entity: Entity,
    entity_uri: URIRef,
    canonical_resolver,
) -> None:
    if entity.kind != "chain-audit":
        return
    audits_ref = getattr(entity, "audits", None)
    if audits_ref:
        knowledge.add((entity_uri, SCI_NS.audits, _entity_uri(canonical_resolver(audits_ref))))
```

Then call both helpers from the per-entity emission loop (alongside the existing `hasParticipant`/`hasProposition` calls). Use whatever resolver signature surrounding code uses — read 230–290 to match the existing pattern; the test exercises the integration so the implementation is correct only if the test passes.

- [ ] **Step 7.4: Run to verify pass**

```bash
uv run --project science pytest science/tests/test_chain_materialize.py -v
```

Expected: 3 passed.

- [ ] **Step 7.5: Commit**

```bash
git add science/src/science_tool/graph/materialize.py science/tests/test_chain_materialize.py
git commit -m "feat(chain-audit): materialize sci:hasLink, sci:linkSequence, sci:audits triples"
```

---

## Task 8: `derive_bears_on_from_chain_links` (inverse rule)

**Files:**
- Modify: `science/src/science_tool/graph/freshness.py`
- Create: `science/tests/test_chain_bears_on.py`

- [ ] **Step 8.1: Write the failing test**

Create `science/tests/test_chain_bears_on.py`:

```python
"""Tests for chain-link → bears_on inverse derivation and audits derivation."""

from __future__ import annotations

from rdflib import Dataset, URIRef

from science_tool.graph.freshness import (
    derive_bears_on_from_chain_links,
)
from science_tool.graph.store import PROJECT_NS, SCI_NS


def _u(local: str) -> URIRef:
    return URIRef(PROJECT_NS[local])


def _make_dataset_with(triples):
    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    for s, p, o in triples:
        knowledge.add((s, p, o))
    return ds


def _bears_on_pairs(ds):
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    return {(str(s), str(o)) for s, _, o in knowledge.triples((None, SCI_NS.bearsOn, None))}


def test_chain_link_emits_inverse_bears_on():
    """structural-chain sci:hasLink mechanism → mechanism bears_on chain (inverse)."""
    ds = _make_dataset_with(
        [(_u("entity/chain/abc"), SCI_NS.hasLink, _u("entity/mechanism/a"))]
    )
    derive_bears_on_from_chain_links(ds)
    pairs = _bears_on_pairs(ds)
    assert (str(_u("entity/mechanism/a")), str(_u("entity/chain/abc"))) in pairs


def test_three_link_chain_emits_three_bears_on():
    chain = _u("entity/chain/abc")
    ds = _make_dataset_with([
        (chain, SCI_NS.hasLink, _u("entity/mechanism/a")),
        (chain, SCI_NS.hasLink, _u("entity/mechanism/b")),
        (chain, SCI_NS.hasLink, _u("entity/mechanism/c")),
    ])
    derive_bears_on_from_chain_links(ds)
    pairs = _bears_on_pairs(ds)
    assert (str(_u("entity/mechanism/a")), str(chain)) in pairs
    assert (str(_u("entity/mechanism/b")), str(chain)) in pairs
    assert (str(_u("entity/mechanism/c")), str(chain)) in pairs
```

- [ ] **Step 8.2: Run to verify failure**

```bash
uv run --project science pytest science/tests/test_chain_bears_on.py::test_chain_link_emits_inverse_bears_on -v
```

Expected: ImportError or AssertionError.

- [ ] **Step 8.3: Implement `derive_bears_on_from_chain_links`**

In `science/src/science_tool/graph/freshness.py`, add (placed near the other deriver functions; mirror the inverse-rule shape from `derive_bears_on_from_typed_edges`):

```python
def derive_bears_on_from_chain_links(dataset: Dataset) -> None:
    """Emit `bears_on` triples from sci:hasLink (inverse).

    Rule: `?c sci:hasLink ?x` -> `?x bears_on ?c` (chain link bears on its chain).

    Source kind discipline (chain must be a structural-chain) is enforced at
    materialize-time by `relation_allows_kinds`; this deriver assumes any
    `sci:hasLink` triple already passed validation.
    """
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    for s, _, o in knowledge.triples((None, SCI_NS.hasLink, None)):
        if not isinstance(s, URIRef) or not isinstance(o, URIRef):
            continue
        knowledge.add((o, SCI_NS.bearsOn, s))
        _emit_bears_on_edge(knowledge, o, s, 1)
```

- [ ] **Step 8.4: Run to verify pass**

```bash
uv run --project science pytest science/tests/test_chain_bears_on.py -v
```

Expected: 2 passed.

- [ ] **Step 8.5: Commit**

```bash
git add science/src/science_tool/graph/freshness.py science/tests/test_chain_bears_on.py
git commit -m "feat(chain-audit): derive bears_on from chain links (inverse)"
```

---

## Task 9: `derive_bears_on_from_audits` + wire both new derivers into the pipeline

**Files:**
- Modify: `science/src/science_tool/graph/freshness.py`
- Modify: `science/src/science_tool/graph/materialize.py`
- Modify: `science/tests/test_chain_bears_on.py`

- [ ] **Step 9.1: Append to the test file**

```python
from science_tool.graph.freshness import derive_bears_on_from_audits


def test_audits_emits_bears_on():
    """chain-audit sci:audits chain → chain bears_on chain-audit."""
    ds = _make_dataset_with(
        [(_u("entity/chain-audit/x"), SCI_NS.audits, _u("entity/chain/abc"))]
    )
    derive_bears_on_from_audits(ds)
    pairs = _bears_on_pairs(ds)
    assert (str(_u("entity/chain/abc")), str(_u("entity/chain-audit/x"))) in pairs
```

- [ ] **Step 9.2: Run to verify failure**

```bash
uv run --project science pytest science/tests/test_chain_bears_on.py::test_audits_emits_bears_on -v
```

Expected: ImportError on `derive_bears_on_from_audits`.

- [ ] **Step 9.3: Implement `derive_bears_on_from_audits`**

In `freshness.py`:

```python
def derive_bears_on_from_audits(dataset: Dataset) -> None:
    """Emit `bears_on` triples from sci:audits.

    Rule: `?a sci:audits ?c` -> `?c bears_on ?a` (chain bears on the audit
    that asserts a verdict over it). Mirrors the `tests` predicate's shape.
    """
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    for s, _, o in knowledge.triples((None, SCI_NS.audits, None)):
        if not isinstance(s, URIRef) or not isinstance(o, URIRef):
            continue
        knowledge.add((o, SCI_NS.bearsOn, s))
        _emit_bears_on_edge(knowledge, o, s, 1)
```

- [ ] **Step 9.4: Wire both new derivers into the materialize pipeline**

In `science/src/science_tool/graph/materialize.py`, find the block where the existing derivers run (you'll see `derive_bears_on_from_typed_edges`, `derive_bears_on_from_pre_registrations`, `derive_bears_on_from_provenance`, then `close_bears_on`). Insert the two new calls **before** `close_bears_on`, **after** `derive_bears_on_from_typed_edges`:

```python
    derive_bears_on_from_typed_edges(dataset, kind_class=kind_class)
    derive_bears_on_from_chain_links(dataset)
    derive_bears_on_from_audits(dataset)
    derive_bears_on_from_pre_registrations(
        dataset,
        pre_registration_targets=pre_registration_targets,
        kind_class=kind_class,
    )
    derive_bears_on_from_provenance(dataset, kind_class=kind_class)
    close_bears_on(dataset, kind_class=kind_class)
```

Update the imports at the top of `materialize.py`:

```python
from science_tool.graph.freshness import (
    EntityFreshnessInfo,
    close_bears_on,
    derive_bears_on_from_audits,
    derive_bears_on_from_chain_links,
    derive_bears_on_from_pre_registrations,
    derive_bears_on_from_provenance,
    derive_bears_on_from_typed_edges,
    derive_freshness,
)
```

- [ ] **Step 9.5: Run to verify pass**

```bash
uv run --project science pytest science/tests/test_chain_bears_on.py -v
```

Expected: 3 passed (previous 2 + new audits test).

- [ ] **Step 9.6: Commit**

```bash
git add science/src/science_tool/graph/freshness.py science/src/science_tool/graph/materialize.py science/tests/test_chain_bears_on.py
git commit -m "feat(chain-audit): derive bears_on from audits and wire chain derivers into pipeline"
```

---

## Task 10: End-to-end freshness propagation through chain-audit

**Files:**
- Create: `science/tests/test_chain_freshness_integration.py`

This task verifies the full chain: edit a chain-link entity's `updated`, run materialize, observe the chain-audit go `needs-review` with `triggered_by` populated.

- [ ] **Step 10.1: Write the integration test**

Create `science/tests/test_chain_freshness_integration.py`:

```python
"""End-to-end test: chain-link change propagates to chain-audit freshness."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from rdflib import URIRef

from science_tool.graph.materialize import build_dataset
from science_tool.graph.store import PROJECT_NS, SCI_NS


def _write(tmp_path: Path, rel: str, body: str) -> None:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)


def _project_with_chain_audit(tmp_path: Path, *, fp_updated: str, audit_reviewed: str) -> Path:
    _write(tmp_path, "science.yaml", "name: test\nproject_id: test\nprofile: core\n")
    for slug, updated in (("a", "2026-05-01"), ("b", fp_updated), ("c", "2026-05-01")):
        _write(
            tmp_path,
            f"core/mechanisms/{slug}.md",
            f"""---
id: mechanism:{slug}
kind: mechanism
title: "Mechanism {slug}"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: {updated}
---
""",
        )
    _write(
        tmp_path,
        "core/chains/abc.md",
        """---
id: chain:abc
kind: structural-chain
title: "ABC chain"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
chain:
  - mechanism:a
  - mechanism:b
  - mechanism:c
---
""",
    )
    _write(
        tmp_path,
        "doc/audits/abc-2026-05.md",
        f"""---
id: chain-audit:abc-2026-05
kind: chain-audit
title: "ABC audit"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
audits: chain:abc
proposition_refs: []
review_state:
  last_reviewed: {audit_reviewed}
bayes_factor_evidence:
  hypothesis_ref: hypothesis:abc
  null_baseline: "uniform"
  interpretation: evidence-against
verdict:
  composite: "[-]"
  rule: single-claim
  claims:
    - id: claim:abc
      polarity: "[-]"
---
""",
    )
    return tmp_path


def _freshness_state(dataset, audit_uri: URIRef) -> str | None:
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    triples = list(knowledge.triples((audit_uri, SCI_NS.freshnessState, None)))
    if not triples:
        return None
    return str(triples[0][2])


def test_audit_fresh_when_links_unchanged_since_review(tmp_path):
    project = _project_with_chain_audit(
        tmp_path, fp_updated="2026-05-01", audit_reviewed="2026-05-02"
    )
    dataset = build_dataset(project)
    audit_uri = URIRef(f"{PROJECT_NS}entity/chain-audit/abc-2026-05")
    assert _freshness_state(dataset, audit_uri) == "fresh"


def test_audit_needs_review_when_link_updates_after_review(tmp_path):
    """Mechanism B updated 2026-05-10, audit reviewed 2026-05-02 → needs-review."""
    project = _project_with_chain_audit(
        tmp_path, fp_updated="2026-05-10", audit_reviewed="2026-05-02"
    )
    dataset = build_dataset(project)
    audit_uri = URIRef(f"{PROJECT_NS}entity/chain-audit/abc-2026-05")
    assert _freshness_state(dataset, audit_uri) == "needs-review"

    # triggered_by should include mechanism:b (the link that updated).
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    triggered_uris = {
        str(o) for _, _, o in knowledge.triples((audit_uri, SCI_NS.triggeredBy, None))
    }
    assert any(t.endswith("/mechanism/b") for t in triggered_uris)
```

If the freshness state predicate name differs from `SCI_NS.freshnessState`, read `freshness.py`'s `derive_freshness` to find the actual predicate and update accordingly. Same for `triggeredBy`.

- [ ] **Step 10.2: Run to verify**

```bash
uv run --project science pytest science/tests/test_chain_freshness_integration.py -v
```

Expected: both pass. If they fail, the wiring from Task 9 is missing or transitive closure isn't picking up the new bears_on edges; debug by inspecting the materialized graph.

- [ ] **Step 10.3: Commit**

```bash
git add science/tests/test_chain_freshness_integration.py
git commit -m "test(chain-audit): end-to-end freshness propagation through chain-audit"
```

---

## Task 11: Reorder-detection regression

**Files:**
- Modify: `science/tests/test_chain_materialize.py`

The spec commits to ordered serialization via `sci:linkSequence`. This task adds a regression test: same link set in different order produces a different materialized graph (different RDF list rest-chain), so a reorder-without-`updated`-bump still propagates as needs-review on next build.

- [ ] **Step 11.1: Write the regression test**

Append to `science/tests/test_chain_materialize.py`:

```python
def _project_with_chain_order(tmp_path: Path, order: list[str]) -> Path:
    _write(tmp_path, "science.yaml", "name: test\nproject_id: test\nprofile: core\n")
    for slug in ("a", "b", "c"):
        _write(
            tmp_path,
            f"core/mechanisms/{slug}.md",
            f"""---
id: mechanism:{slug}
kind: mechanism
title: "Mechanism {slug}"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
---
""",
        )
    chain_yaml = "\n".join(f"  - {ref}" for ref in order)
    _write(
        tmp_path,
        "core/chains/abc.md",
        f"""---
id: chain:abc
kind: structural-chain
title: "ABC chain"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
chain:
{chain_yaml}
---
""",
    )
    return tmp_path


def _ordered_links(dataset, chain_uri: URIRef) -> list[str]:
    from rdflib.namespace import RDF
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    head = next(knowledge.triples((chain_uri, SCI_NS.linkSequence, None)))[2]
    out = []
    cur = head
    while cur != RDF.nil:
        out.append(str(next(knowledge.triples((cur, RDF.first, None)))[2]))
        cur = next(knowledge.triples((cur, RDF.rest, None)))[2]
    return out


def test_reorder_same_links_changes_link_sequence(tmp_path):
    """Reordering the same link set without bumping `updated` must still
    change the materialized graph (different rdf:rest chain in linkSequence)."""
    chain_uri = URIRef(f"{PROJECT_NS}entity/chain/abc")

    dataset_abc = build_dataset(_project_with_chain_order(
        tmp_path / "abc",
        ["mechanism:a", "mechanism:b", "mechanism:c"],
    ))
    dataset_cba = build_dataset(_project_with_chain_order(
        tmp_path / "cba",
        ["mechanism:c", "mechanism:b", "mechanism:a"],
    ))

    abc_order = _ordered_links(dataset_abc, chain_uri)
    cba_order = _ordered_links(dataset_cba, chain_uri)
    assert abc_order != cba_order
    assert abc_order[0].endswith("/mechanism/a")
    assert cba_order[0].endswith("/mechanism/c")
```

- [ ] **Step 11.2: Run to verify pass**

```bash
uv run --project science pytest science/tests/test_chain_materialize.py::test_reorder_same_links_changes_link_sequence -v
```

Expected: pass. If the test fails because `sci:linkSequence` was implemented as a set rather than an ordered list, the implementation in Task 7 needs to be revisited.

- [ ] **Step 11.3: Commit**

```bash
git add science/tests/test_chain_materialize.py
git commit -m "test(chain-audit): regress on reorder-detection via sci:linkSequence"
```

---

## Task 12: Extend `_audit_entity` for chain, audits, proposition_refs

**Files:**
- Modify: `science/src/science_tool/graph/migrate.py`
- Create: `science/tests/test_chain_audit_references.py`

`audit_project_sources()` iterates explicit named-field branches; new fields aren't auto-discovered. This task adds branches for `chain[]`, `audits`, and `proposition_refs[]` so dangling refs in those fields surface in the audit output.

- [ ] **Step 12.1: Write the failing test**

Create `science/tests/test_chain_audit_references.py`:

```python
"""Tests for reference auditing of chain, audits, and proposition_refs fields."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.graph.migrate import audit_project_sources


def _write(tmp_path: Path, rel: str, body: str) -> None:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)


def _project_with_dangling_chain_link(tmp_path: Path) -> Path:
    _write(tmp_path, "science.yaml", "name: test\nproject_id: test\nprofile: core\n")
    # mechanism:a exists; mechanism:b does NOT — this is the dangling ref
    _write(
        tmp_path,
        "core/mechanisms/a.md",
        """---
id: mechanism:a
kind: mechanism
title: "A"
project: test
ontology_terms: []
related: []
source_refs: []
---
""",
    )
    _write(
        tmp_path,
        "core/chains/ab.md",
        """---
id: chain:ab
kind: structural-chain
title: "AB chain"
project: test
ontology_terms: []
related: []
source_refs: []
chain:
  - mechanism:a
  - mechanism:b
---
""",
    )
    return tmp_path


def test_dangling_chain_link_surfaces_in_audit(tmp_path):
    project = _project_with_dangling_chain_link(tmp_path)
    rows = audit_project_sources(project)
    dangling = [r for r in rows if "mechanism:b" in str(r) and "chain:ab" in str(r)]
    assert dangling, f"expected dangling-ref row for mechanism:b, got {rows!r}"


def test_dangling_audits_ref_surfaces(tmp_path):
    _write(tmp_path, "science.yaml", "name: test\nproject_id: test\nprofile: core\n")
    _write(
        tmp_path,
        "doc/audits/x.md",
        """---
id: chain-audit:x
kind: chain-audit
title: "X audit"
project: test
ontology_terms: []
related: []
source_refs: []
audits: chain:does-not-exist
proposition_refs: []
bayes_factor_evidence:
  hypothesis_ref: hypothesis:foo
  null_baseline: uniform
  interpretation: evidence-against
verdict:
  composite: "[-]"
  rule: single-claim
  claims:
    - id: claim:x
      polarity: "[-]"
---
""",
    )
    rows = audit_project_sources(tmp_path)
    dangling = [r for r in rows if "chain:does-not-exist" in str(r)]
    assert dangling


def test_dangling_proposition_ref_in_chain_audit_surfaces(tmp_path):
    _write(tmp_path, "science.yaml", "name: test\nproject_id: test\nprofile: core\n")
    _write(
        tmp_path,
        "core/chains/abc.md",
        """---
id: chain:abc
kind: structural-chain
title: "ABC"
project: test
ontology_terms: []
related: []
source_refs: []
chain:
  - mechanism:a
  - mechanism:b
---
""",
    )
    _write(
        tmp_path,
        "core/mechanisms/a.md",
        """---
id: mechanism:a
kind: mechanism
title: "A"
project: test
ontology_terms: []
related: []
source_refs: []
---
""",
    )
    _write(
        tmp_path,
        "core/mechanisms/b.md",
        """---
id: mechanism:b
kind: mechanism
title: "B"
project: test
ontology_terms: []
related: []
source_refs: []
---
""",
    )
    _write(
        tmp_path,
        "doc/audits/abc.md",
        """---
id: chain-audit:abc
kind: chain-audit
title: "ABC audit"
project: test
ontology_terms: []
related: []
source_refs: []
audits: chain:abc
proposition_refs:
  - proposition:does-not-exist
bayes_factor_evidence:
  hypothesis_ref: hypothesis:foo
  null_baseline: uniform
  interpretation: evidence-against
verdict:
  composite: "[-]"
  rule: single-claim
  claims:
    - id: claim:x
      polarity: "[-]"
---
""",
    )
    rows = audit_project_sources(tmp_path)
    dangling = [r for r in rows if "proposition:does-not-exist" in str(r)]
    assert dangling
```

The exact assertion shape may need adjustment based on `AuditRow`'s representation — read `migrate.py` lines 295–320 to see the row shape and adapt the assertions if needed (e.g., check `r.field == "chain"` instead of substring).

- [ ] **Step 12.2: Run to verify failure**

```bash
uv run --project science pytest science/tests/test_chain_audit_references.py -v
```

Expected: all three tests fail (no rows for the dangling refs).

- [ ] **Step 12.3: Extend `_audit_entity`**

In `science/src/science_tool/graph/migrate.py`, find `_audit_entity` (around line 296). It iterates `entity.related`, `entity.commits_to`, `entity.source_refs`, etc. Append three new branches:

```python
    for target in getattr(entity, "chain", None) or []:
        rows.extend(
            _audit_reference(
                entity,
                "chain",
                target,
                resolver,
                ext_prefixes=ext_prefixes,
                allow_cross_kind_fallback=False,
                allow_tag=False,
            )
        )
    audits_target = getattr(entity, "audits", None)
    if audits_target:
        rows.extend(
            _audit_reference(
                entity,
                "audits",
                audits_target,
                resolver,
                ext_prefixes=ext_prefixes,
                allow_cross_kind_fallback=False,
                allow_tag=False,
            )
        )
    for target in getattr(entity, "proposition_refs", None) or []:
        rows.extend(
            _audit_reference(
                entity,
                "proposition_refs",
                target,
                resolver,
                ext_prefixes=ext_prefixes,
                allow_cross_kind_fallback=False,
                allow_tag=False,
            )
        )
```

`allow_cross_kind_fallback=False` because chain links and audits targets are kind-restricted (the relation kind enforces the allowlist; cross-kind silently passing would defeat this). `allow_tag=False` because tag refs aren't valid here.

- [ ] **Step 12.4: Run to verify pass**

```bash
uv run --project science pytest science/tests/test_chain_audit_references.py -v
```

Expected: 3 passed.

- [ ] **Step 12.5: Commit**

```bash
git add science/src/science_tool/graph/migrate.py science/tests/test_chain_audit_references.py
git commit -m "feat(chain-audit): audit references in chain, audits, proposition_refs fields"
```

---

## Task 13: Verify validate.sh and `science graph validate` end-to-end

**Files:**
- Modify: `science/tests/test_chain_freshness_integration.py` (append a smoke test)

No managed-validator-body changes are needed — Pydantic + `relation_allows_kinds` + `audit_project_sources` enforce all 12 spec rules. This task verifies the orchestrator end-to-end.

- [ ] **Step 13.1: Append a smoke test**

Append to `science/tests/test_chain_freshness_integration.py`:

```python
import subprocess


def test_validate_passes_on_well_formed_chain_audit(tmp_path):
    project = _project_with_chain_audit(
        tmp_path, fp_updated="2026-05-01", audit_reviewed="2026-05-02"
    )
    # Run `science graph validate` on the materialized output. Build first.
    build_dataset(project)
    result = subprocess.run(
        ["science", "graph", "validate", "--format", "json", "--path", str(project / ".graph" / "graph.trig")],
        capture_output=True,
        text=True,
        cwd=project,
    )
    # Allowable: process exits 0 OR exits non-zero with no chain-related errors
    # in stderr/stdout. We assert no error explicitly mentions chain/audit fields.
    combined = (result.stdout + result.stderr).lower()
    assert "structural-chain" not in combined or "error" not in combined, (
        f"validate complained about chain-audit setup: {combined}"
    )


def test_validate_flags_dangling_chain_link(tmp_path):
    """Build a project with a dangling chain link; expect audit_project_sources to flag it.
    This is the public-API surface that `science graph validate` consults."""
    from science_tool.graph.migrate import audit_project_sources

    _write(tmp_path, "science.yaml", "name: test\nproject_id: test\nprofile: core\n")
    _write(
        tmp_path,
        "core/mechanisms/a.md",
        """---
id: mechanism:a
kind: mechanism
title: "A"
project: test
ontology_terms: []
related: []
source_refs: []
---
""",
    )
    _write(
        tmp_path,
        "core/chains/ab.md",
        """---
id: chain:ab
kind: structural-chain
title: "AB"
project: test
ontology_terms: []
related: []
source_refs: []
chain:
  - mechanism:a
  - mechanism:b
---
""",
    )
    rows = audit_project_sources(tmp_path)
    assert any("mechanism:b" in str(r) for r in rows)
```

- [ ] **Step 13.2: Run to verify**

```bash
uv run --project science pytest science/tests/test_chain_freshness_integration.py -v
```

Expected: all four tests in the file pass.

- [ ] **Step 13.3: Run the full chain-audit test suite as a regression sweep**

```bash
uv run --project science/model pytest science/model/tests/test_chain_entities.py science/model/tests/test_chain_relations.py science/model/tests/test_bears_on_relation.py -v
uv run --project science pytest science/tests/test_chain_kinds_registered.py science/tests/test_chain_materialize.py science/tests/test_chain_bears_on.py science/tests/test_chain_freshness_integration.py science/tests/test_chain_audit_references.py -v
```

Expected: every test passes.

- [ ] **Step 13.4: Commit**

```bash
git add science/tests/test_chain_freshness_integration.py
git commit -m "test(chain-audit): smoke-test science graph validate orchestrator"
```

---

## Task 14: Project documentation update

**Files:**
- Modify: `docs/claim-and-evidence-model.md`

- [ ] **Step 14.1: Add a brief section**

Open `docs/claim-and-evidence-model.md`. Find a sensible insertion point near the existing discussion of evidence flow / `bears_on`. Add a section:

```markdown
## Chain-shaped audit verdicts

Some findings are verdicts over an *ordered structural decomposition* — e.g.,
"particle-advection → Fokker-Planck → heat-equation" — rather than over a flat
proposition. The framework supports this via two EPISTEMIC kinds:

- **`structural-chain`** holds an ordered list of ≥2 entity refs (mechanism, model,
  proposition, observation, or finding). The chain is a first-class entity so it
  can be reused across multiple verdicts and over time.
- **`chain-audit`** carries a verdict over a chain, with both a `verdict:` block
  (compatible with the project's existing `verdict/parser.py` rollup surface) and
  a `bayes_factor_evidence:` block. The validator enforces consistency between
  `verdict.composite` and `bayes_factor_evidence.interpretation` per a fixed
  mapping (`evidence-for`→`[+]`, `evidence-against`→`[-]`, `mixed`→`[~]`,
  `inconclusive`→`[?]`).

Freshness propagation is automatic: when any chain link's underlying entity
updates, OR the chain itself is edited (links added, removed, or reordered —
order is preserved as an RDF list under `sci:linkSequence`), the chain-audit
goes `needs-review` on the next `graph build`.

See `docs/plans/2026-05-07-chain-audit-verdict-design.md` for the full design.
```

- [ ] **Step 14.2: Commit**

```bash
git add docs/claim-and-evidence-model.md
git commit -m "docs(chain-audit): describe chain-shaped audit verdicts"
```

---

## Self-review checklist (run after all tasks complete)

- [ ] **Spec coverage:** every numbered design decision (1–9) and validator rule (1–12) maps to a task.
  - Decision 1 (two kinds) — Tasks 2, 3
  - Decision 2 (strict registration) — Task 12 (audit) + Task 5 (relation kinds)
  - Decision 3 (link kind allowlist) — Task 5 (`has_link.target_kinds`)
  - Decision 4 (BF-style) — Task 1
  - Decision 5 (dedicated `chain-audit`) — Task 3
  - Decision 6 (`has_link` not `has_participant`) — Task 5
  - Decision 7 (`audits` mirrors `tests`) — Task 5
  - Decision 8 (verdict integration required) — Task 3 (consistency validator)
  - Decision 9 (`sci:linkSequence` ordered) — Tasks 7, 11
  - Validator rules 1–4 (chain shape) — Task 2 + Task 5 (link kind allowlist)
  - Validator rules 5–7 (chain-audit shape) — Tasks 1, 3
  - Validator rules 8–9 (verdict↔BF consistency) — Task 3
  - Validator rules 10–11 (relation contracts) — Task 5
  - Validator rule 12 (`bears_on` extension) — Task 6
  - Reference audit coverage — Task 12

- [ ] **Run the full chain-audit suite one more time** to verify nothing regressed:

```bash
uv run --project science/model pytest science/model/tests/test_chain_entities.py science/model/tests/test_chain_relations.py science/model/tests/test_bears_on_relation.py
uv run --project science pytest science/tests/test_chain_kinds_registered.py science/tests/test_chain_materialize.py science/tests/test_chain_bears_on.py science/tests/test_chain_freshness_integration.py science/tests/test_chain_audit_references.py
```

- [ ] **Run the project's existing test sweep** to verify no regressions:

```bash
uv run --project science/model pytest
uv run --project science pytest
```

- [ ] **Run `validate.sh` from the science root and from a downstream project (e.g., `meta/`)** to verify the orchestrator still passes:

```bash
bash validate.sh --verbose
cd meta && bash validate.sh --verbose && cd ..
```
