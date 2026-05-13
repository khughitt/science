# Typed Synthesis Nodes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the `t023` typed synthesis-node contract as validated evidence payload extensions, family metadata, routing helpers, and derivation-edge helpers.

**Architecture:** Synthesis nodes remain normal `t022` `EvidencePayload` records whose primary extension name equals the synthesis family artifact type. A small `science_tool.synthesis_payload` module owns synthesis-family metadata, the required `synthesis-operation` extension body, family-level permission ceilings, deterministic routing helpers, and derivation-edge extraction. Existing `science_tool.evidence_payload` continues to own the generic core/extension contract and effective reason-code propagation.

**Tech Stack:** Python 3.11, Pydantic v2, pytest, Ruff, Pyright, existing `science_tool.evidence_payload` models.

---

## Scope Check

This plan implements the near-term `t023` software surface only:

- Synthesis payloads are `t022` payloads, not a separate store.
- `extension/synthesis-operation` is required for every synthesis family.
- The family taxonomy, reserved `decision-analytic-score` family, owner metadata, default permission, max permission, and routing rules are machine-readable.
- Effective reason codes remain computed through the existing `effective_reason_codes()` path.
- Derivation edges are exposed as a pure helper for later graph materialization.

This plan does not implement `[t042]` lifecycle/replay, artifact supersession, graph invalidation, or storage/indexing of synthesis payload files. Those remain out of scope.

## File Structure

- `science/src/science_tool/evidence_payload.py`
  - Add `create-hypothesis` to `ValidationRole`, because `t023` uses it as a permission ceiling and authorable validation role.
- `science/src/science_tool/synthesis_payload.py`
  - New focused module for synthesis-family metadata, `SynthesisOperation`, validation wrapper, routing helper, and derivation-edge helper.
- `science/tests/test_evidence_payload_contract.py`
  - Add a regression test proving `create-hypothesis` is accepted by the generic payload model and registry.
- `science/tests/test_synthesis_payload.py`
  - New tests for `synthesis-operation`, reserved family rejection, permission ceilings, routing, and derivation edges.
- `science/src/science_tool/__init__.py`
  - No change. Consumers should import from `science_tool.synthesis_payload` directly, matching the package's existing module style.

---

### Task 1: Add `create-hypothesis` Validation Role

**Files:**
- Modify: `science/src/science_tool/evidence_payload.py`
- Modify: `science/tests/test_evidence_payload_contract.py`

- [ ] **Step 1: Write the failing test**

Append this test to `science/tests/test_evidence_payload_contract.py`:

```python
def test_payload_accepts_create_hypothesis_validation_role() -> None:
    payload = _payload(
        "ev-2026-candidate-hypothesis",
        core={
            "validation_role": "create-hypothesis",
            "proposition_refs": [],
            "support_direction": "methodological-input",
        },
    )

    _registry().validate_payload(payload)

    assert payload.core.validation_role == "create-hypothesis"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run --project science pytest science/tests/test_evidence_payload_contract.py::test_payload_accepts_create_hypothesis_validation_role -q
```

Expected: FAIL with a Pydantic literal validation error because `create-hypothesis` is not in `ValidationRole`.

- [ ] **Step 3: Add the role to the generic payload contract**

Modify the `ValidationRole` declaration in `science/src/science_tool/evidence_payload.py` from:

```python
ValidationRole = Literal["strengthen-belief", "prioritize-attention", "gate-update", "quality-record-only", "record-only"]
```

to:

```python
ValidationRole = Literal[
    "strengthen-belief",
    "prioritize-attention",
    "create-hypothesis",
    "gate-update",
    "quality-record-only",
    "record-only",
]
```

- [ ] **Step 4: Run the focused test**

Run:

```bash
uv run --project science pytest science/tests/test_evidence_payload_contract.py::test_payload_accepts_create_hypothesis_validation_role -q
```

Expected: PASS.

- [ ] **Step 5: Run the existing evidence-payload contract tests**

Run:

```bash
uv run --project science pytest science/tests/test_evidence_payload_contract.py -q
```

Expected: all tests in `test_evidence_payload_contract.py` pass.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/evidence_payload.py science/tests/test_evidence_payload_contract.py
git commit -m "feat: allow hypothesis-creation validation role"
```

---

### Task 2: Add Synthesis Family Registry And Payload Validation

**Files:**
- Create: `science/src/science_tool/synthesis_payload.py`
- Create: `science/tests/test_synthesis_payload.py`

- [ ] **Step 1: Write failing tests for synthesis-family validation**

Create `science/tests/test_synthesis_payload.py` with this content:

```python
from __future__ import annotations

from typing import Any

import pytest

from science_tool.evidence_payload import EvidencePayload, PayloadValidationError
from science_tool.synthesis_payload import (
    SYNTHESIS_OPERATION_EXTENSION,
    SYNTHESIS_PRIMARY_EXTENSION_NAMES,
    SynthesisOperation,
    build_synthesis_registry,
    validate_synthesis_payload,
)


def _synthesis_payload(payload_id: str, **overrides: Any) -> EvidencePayload:
    core: dict[str, Any] = {
        "payload_id": payload_id,
        "artifact_type": "bayesian-model-comparison",
        "extensions": ["bayesian-model-comparison", "synthesis-operation"],
        "created_at": "2026-05-08T10:00:00Z",
        "input_artifact_refs": ["study:gronau-input"],
        "method_ref": "paper:Gronau2021",
        "agent_ref": "agent:synthesis-runner",
        "pipeline_provenance_ref": "pipeline:bma-synthesis-v1",
        "proposition_refs": ["prop:model-a-over-null"],
        "comparison_target": "model-set",
        "support_direction": "supports",
        "validation_role": "prioritize-attention",
        "validation_status": "pending",
        "uncertainty_summary": "PMP(model-a)=0.72",
        "reason_codes": [],
    }
    core.update(overrides.pop("core", {}))
    extension_sections: dict[str, dict[str, Any]] = {
        "bayesian-model-comparison": {},
        "synthesis-operation": {
            "output_artifact_refs": ["payload:bma-model-summary"],
            "operator_assumption_refs": ["assumption:prior-model-probabilities-explicit"],
        },
    }
    extension_sections.update(overrides.pop("extension_sections", {}))
    return EvidencePayload.model_validate({"core": core, "extension_sections": extension_sections, **overrides})


def test_synthesis_operation_section_parses_required_refs() -> None:
    payload = _synthesis_payload("syn-2026-bma")

    validate_synthesis_payload(payload)

    operation = SynthesisOperation.model_validate(payload.extension_sections["synthesis-operation"])
    assert operation.output_artifact_refs == ["payload:bma-model-summary"]
    assert operation.operator_assumption_refs == ["assumption:prior-model-probabilities-explicit"]


def test_all_non_reserved_synthesis_families_register_primary_extensions() -> None:
    registry = build_synthesis_registry()

    for name in SYNTHESIS_PRIMARY_EXTENSION_NAMES:
        spec = registry.extension(name)
        assert spec.name == name
        assert spec.artifact_type == name
        assert SYNTHESIS_OPERATION_EXTENSION in spec.co_required_extensions


def test_reserved_decision_analytic_score_is_rejected_for_production_payloads() -> None:
    payload = _synthesis_payload(
        "syn-2026-mcda",
        core={
            "artifact_type": "decision-analytic-score",
            "extensions": ["decision-analytic-score", "synthesis-operation"],
            "validation_role": "record-only",
            "proposition_refs": [],
            "comparison_target": "n-a",
            "support_direction": "operation-record",
        },
        extension_sections={"decision-analytic-score": {}},
    )

    with pytest.raises(PayloadValidationError, match="reserved synthesis family"):
        validate_synthesis_payload(payload)


def test_synthesis_payload_requires_synthesis_operation_extension() -> None:
    payload = _synthesis_payload(
        "syn-2026-missing-operation",
        core={"extensions": ["bayesian-model-comparison"]},
        extension_sections={"synthesis-operation": {}},
    )

    with pytest.raises(PayloadValidationError, match="co-required extension 'synthesis-operation'"):
        validate_synthesis_payload(payload)


def test_family_permission_ceiling_blocks_strengthen_belief_for_feature_selection() -> None:
    payload = _synthesis_payload(
        "syn-2026-feature-selection",
        core={
            "artifact_type": "feature-selection-synthesis",
            "extensions": ["feature-selection-synthesis", "synthesis-operation"],
            "validation_role": "strengthen-belief",
            "proposition_refs": ["prop:selected-feature-supports-biology"],
        },
        extension_sections={"feature-selection-synthesis": {}},
    )

    with pytest.raises(PayloadValidationError, match="exceeds max permission"):
        validate_synthesis_payload(payload)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
uv run --project science pytest science/tests/test_synthesis_payload.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.synthesis_payload'`.

- [ ] **Step 3: Add the synthesis payload module**

Create `science/src/science_tool/synthesis_payload.py` with this content:

```python
"""Typed synthesis payload family metadata and validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from science_tool.evidence_payload import (
    EvidencePayload,
    EvidencePayloadRegistry,
    ExtensionSpec,
    PayloadValidationError,
    ValidationRole,
)


SYNTHESIS_OPERATION_EXTENSION = "synthesis-operation"
SynthesisPermission = ValidationRole


class SynthesisOperation(BaseModel):
    """Common operation section required by every synthesis-family payload."""

    model_config = ConfigDict(extra="forbid")

    output_artifact_refs: list[str] = Field(default_factory=list)
    operator_assumption_refs: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class SynthesisFamilySpec:
    """Cross-cutting metadata for a t023 synthesis family."""

    family: str
    default_permission: SynthesisPermission
    max_permission: SynthesisPermission
    primary_owner: str | None
    typical_outputs: tuple[str, ...]
    reserved: bool = False


_PERMISSION_RANK: dict[SynthesisPermission, int] = {
    "record-only": 0,
    "quality-record-only": 1,
    "prioritize-attention": 2,
    "create-hypothesis": 3,
    "gate-update": 4,
    "strengthen-belief": 5,
}


SYNTHESIS_FAMILIES: dict[str, SynthesisFamilySpec] = {
    "effect-size-pooling": SynthesisFamilySpec(
        family="effect-size-pooling",
        default_permission="prioritize-attention",
        max_permission="strengthen-belief",
        primary_owner="task:t022",
        typical_outputs=("pooled effect payload", "heterogeneity diagnostics"),
    ),
    "hypothesis-support-synthesis": SynthesisFamilySpec(
        family="hypothesis-support-synthesis",
        default_permission="prioritize-attention",
        max_permission="strengthen-belief",
        primary_owner="task:t022",
        typical_outputs=("support payload", "posterior/probability summary"),
    ),
    "bayesian-model-comparison": SynthesisFamilySpec(
        family="bayesian-model-comparison",
        default_permission="prioritize-attention",
        max_permission="strengthen-belief",
        primary_owner="task:t022",
        typical_outputs=("posterior model probabilities", "Bayes factors", "inclusion probabilities"),
    ),
    "diagnostic-test-synthesis": SynthesisFamilySpec(
        family="diagnostic-test-synthesis",
        default_permission="prioritize-attention",
        max_permission="strengthen-belief",
        primary_owner="task:t022",
        typical_outputs=("sensitivity/specificity payload", "latent-class diagnostic summary"),
    ),
    "truth-discovery": SynthesisFamilySpec(
        family="truth-discovery",
        default_permission="prioritize-attention",
        max_permission="strengthen-belief",
        primary_owner="task:t024",
        typical_outputs=("truth labels", "source reliability scores", "conflict diagnostics"),
    ),
    "decision-analytic-score": SynthesisFamilySpec(
        family="decision-analytic-score",
        default_permission="record-only",
        max_permission="prioritize-attention",
        primary_owner=None,
        typical_outputs=("MCDA score sets", "curation rankings", "triage lists"),
        reserved=True,
    ),
    "data-cleaning-repair": SynthesisFamilySpec(
        family="data-cleaning-repair",
        default_permission="quality-record-only",
        max_permission="prioritize-attention",
        primary_owner="task:t024",
        typical_outputs=("cleaned values", "repair uncertainty", "transformation record"),
    ),
    "causal-meta-analysis": SynthesisFamilySpec(
        family="causal-meta-analysis",
        default_permission="prioritize-attention",
        max_permission="strengthen-belief",
        primary_owner="task:t026",
        typical_outputs=("causal effect estimate", "transport/estimand diagnostics"),
    ),
    "causal-discovery-synthesis": SynthesisFamilySpec(
        family="causal-discovery-synthesis",
        default_permission="prioritize-attention",
        max_permission="create-hypothesis",
        primary_owner="task:t034",
        typical_outputs=("graph object", "graph posterior", "candidate causal propositions"),
    ),
    "llm-prior-constraint-synthesis": SynthesisFamilySpec(
        family="llm-prior-constraint-synthesis",
        default_permission="record-only",
        max_permission="prioritize-attention",
        primary_owner="task:t034",
        typical_outputs=("weak priors", "constraints", "variable proposals"),
    ),
    "mechanistic-network-synthesis": SynthesisFamilySpec(
        family="mechanistic-network-synthesis",
        default_permission="prioritize-attention",
        max_permission="create-hypothesis",
        primary_owner="task:t034",
        typical_outputs=("candidate mechanism graph", "module/pathway hypothesis"),
    ),
    "mediation-synthesis": SynthesisFamilySpec(
        family="mediation-synthesis",
        default_permission="prioritize-attention",
        max_permission="strengthen-belief",
        primary_owner="task:t034",
        typical_outputs=("direct effect payloads", "indirect effect payloads"),
    ),
    "mendelian-randomization-graph-synthesis": SynthesisFamilySpec(
        family="mendelian-randomization-graph-synthesis",
        default_permission="prioritize-attention",
        max_permission="strengthen-belief",
        primary_owner="task:t034",
        typical_outputs=("MR graph posterior", "MR effect estimate"),
    ),
    "graph-diagnostic-synthesis": SynthesisFamilySpec(
        family="graph-diagnostic-synthesis",
        default_permission="quality-record-only",
        max_permission="quality-record-only",
        primary_owner="task:t034",
        typical_outputs=("compatibility checks", "graph validation report"),
    ),
    "graph-estimate-synthesis": SynthesisFamilySpec(
        family="graph-estimate-synthesis",
        default_permission="prioritize-attention",
        max_permission="create-hypothesis",
        primary_owner="task:t035",
        typical_outputs=("conditional-dependence graph", "common/unique component graph"),
    ),
    "graph-posterior-synthesis": SynthesisFamilySpec(
        family="graph-posterior-synthesis",
        default_permission="prioritize-attention",
        max_permission="create-hypothesis",
        primary_owner="task:t035",
        typical_outputs=("graph samples", "edge inclusion table", "posterior summary"),
    ),
    "integrative-clustering-synthesis": SynthesisFamilySpec(
        family="integrative-clustering-synthesis",
        default_permission="prioritize-attention",
        max_permission="create-hypothesis",
        primary_owner="task:t035",
        typical_outputs=("cluster assignments", "subtype hypotheses"),
    ),
    "feature-selection-synthesis": SynthesisFamilySpec(
        family="feature-selection-synthesis",
        default_permission="prioritize-attention",
        max_permission="prioritize-attention",
        primary_owner="task:t035",
        typical_outputs=("selected-feature set", "relevance posterior", "stability report"),
    ),
    "module-discovery-synthesis": SynthesisFamilySpec(
        family="module-discovery-synthesis",
        default_permission="prioritize-attention",
        max_permission="create-hypothesis",
        primary_owner="task:t035",
        typical_outputs=("module/pathway membership artifact",),
    ),
    "predictive-integration-synthesis": SynthesisFamilySpec(
        family="predictive-integration-synthesis",
        default_permission="quality-record-only",
        max_permission="prioritize-attention",
        primary_owner="task:t035",
        typical_outputs=("predictive model", "risk score", "validation artifact"),
    ),
}


SYNTHESIS_PRIMARY_EXTENSION_NAMES: tuple[str, ...] = tuple(
    family for family, spec in SYNTHESIS_FAMILIES.items() if not spec.reserved
)


def build_synthesis_registry() -> EvidencePayloadRegistry:
    """Build a registry containing t023 synthesis families and the shared operation extension."""

    registry = EvidencePayloadRegistry()
    registry.register_extension(
        ExtensionSpec(
            name=SYNTHESIS_OPERATION_EXTENSION,
            artifact_type=SYNTHESIS_OPERATION_EXTENSION,
            required_fields=["output_artifact_refs", "operator_assumption_refs"],
            owning_task="task:t023",
        )
    )
    for family, spec in SYNTHESIS_FAMILIES.items():
        if spec.reserved:
            continue
        registry.register_extension(
            ExtensionSpec(
                name=family,
                artifact_type=family,
                co_required_extensions=[SYNTHESIS_OPERATION_EXTENSION],
                owning_task=spec.primary_owner,
            )
        )
    return registry


def validate_synthesis_payload(payload: EvidencePayload, registry: EvidencePayloadRegistry | None = None) -> None:
    """Validate t023 synthesis-family constraints on top of the generic payload contract."""

    family = payload.core.artifact_type
    try:
        spec = SYNTHESIS_FAMILIES[family]
    except KeyError as exc:
        raise PayloadValidationError(f"unknown synthesis family {family!r}") from exc
    if spec.reserved:
        raise PayloadValidationError(f"reserved synthesis family {family!r} cannot be used in production payloads")
    if not payload.core.extensions or payload.core.extensions[0] != family:
        raise PayloadValidationError(
            f"synthesis payload primary extension must be {family!r}; got {payload.core.extensions!r}"
        )
    if _PERMISSION_RANK[payload.core.validation_role] > _PERMISSION_RANK[spec.max_permission]:
        raise PayloadValidationError(
            f"validation_role {payload.core.validation_role!r} exceeds max permission {spec.max_permission!r} "
            f"for synthesis family {family!r}"
        )

    active_registry = registry or build_synthesis_registry()
    active_registry.validate_payload(payload)
    SynthesisOperation.model_validate(payload.extension_sections[SYNTHESIS_OPERATION_EXTENSION])
```

- [ ] **Step 4: Run the synthesis payload tests**

Run:

```bash
uv run --project science pytest science/tests/test_synthesis_payload.py -q
```

Expected: PASS.

- [ ] **Step 5: Run the evidence payload and synthesis payload tests together**

Run:

```bash
uv run --project science pytest science/tests/test_evidence_payload_contract.py science/tests/test_synthesis_payload.py -q
```

Expected: all tests in both files pass.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/synthesis_payload.py science/tests/test_synthesis_payload.py
git commit -m "feat: add typed synthesis payload registry"
```

---

### Task 3: Add Routing And Derivation Edge Helpers

**Files:**
- Modify: `science/src/science_tool/synthesis_payload.py`
- Modify: `science/tests/test_synthesis_payload.py`

- [ ] **Step 1: Write failing tests for routing and derivation edges**

Modify the `from science_tool.synthesis_payload import (...)` block in `science/tests/test_synthesis_payload.py` so it includes the two new helpers:

```python
from science_tool.synthesis_payload import (
    SYNTHESIS_OPERATION_EXTENSION,
    SYNTHESIS_PRIMARY_EXTENSION_NAMES,
    SynthesisOperation,
    build_synthesis_registry,
    derivation_edges,
    route_synthesis_family,
    validate_synthesis_payload,
)
```

Then append these tests to `science/tests/test_synthesis_payload.py`:

```python

def test_route_synthesis_family_sends_bma_to_model_comparison() -> None:
    assert route_synthesis_family("bayesian-model-averaging") == "bayesian-model-comparison"
    assert route_synthesis_family("bayes-factor-model-set") == "bayesian-model-comparison"


def test_route_synthesis_family_prefers_effect_pooling_for_pooled_effects() -> None:
    assert route_synthesis_family("pooled-effect-estimate") == "effect-size-pooling"
    assert route_synthesis_family("meta-analysis-effect-size") == "effect-size-pooling"


def test_route_synthesis_family_distinguishes_graph_posterior_from_graph_estimate() -> None:
    assert route_synthesis_family("graph-posterior") == "graph-posterior-synthesis"
    assert route_synthesis_family("conditional-dependence-graph") == "graph-estimate-synthesis"


def test_route_synthesis_family_rejects_unknown_operator() -> None:
    with pytest.raises(PayloadValidationError, match="no synthesis-family route"):
        route_synthesis_family("ambiguous-literature-summary")


def test_derivation_edges_emit_inputs_outputs_propositions_method_and_agent() -> None:
    payload = _synthesis_payload("syn-2026-bma")

    edges = derivation_edges(payload)

    assert edges == [
        ("syn-2026-bma", "consumes", "study:gronau-input"),
        ("syn-2026-bma", "uses-method", "paper:Gronau2021"),
        ("syn-2026-bma", "performed-by", "agent:synthesis-runner"),
        ("syn-2026-bma", "targets-proposition", "prop:model-a-over-null"),
        ("syn-2026-bma", "produced", "payload:bma-model-summary"),
        ("payload:bma-model-summary", "derived-from-synthesis", "syn-2026-bma"),
    ]


def test_derivation_edges_skip_empty_proposition_refs() -> None:
    payload = _synthesis_payload(
        "syn-2026-graph",
        core={
            "artifact_type": "graph-posterior-synthesis",
            "extensions": ["graph-posterior-synthesis", "synthesis-operation"],
            "proposition_refs": [],
            "comparison_target": "n-a",
            "support_direction": "methodological-input",
            "validation_role": "prioritize-attention",
            "uncertainty_summary": "edge inclusion table: 102 rows",
        },
        extension_sections={"graph-posterior-synthesis": {}},
    )

    edges = derivation_edges(payload)

    assert not any(edge[1] == "targets-proposition" for edge in edges)
    assert ("syn-2026-graph", "produced", "payload:bma-model-summary") in edges
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
uv run --project science pytest science/tests/test_synthesis_payload.py -k "route_synthesis_family or derivation_edges" -q
```

Expected: FAIL because `route_synthesis_family` and `derivation_edges` do not exist.

- [ ] **Step 3: Add routing aliases and derivation-edge helper**

Append this code to `science/src/science_tool/synthesis_payload.py`:

```python
SynthesisDerivationEdge = tuple[str, str, str]


_ROUTE_ALIASES: dict[str, str] = {
    "bayesian-model-averaging": "bayesian-model-comparison",
    "bayes-factor-model-set": "bayesian-model-comparison",
    "posterior-model-probability": "bayesian-model-comparison",
    "pooled-effect-estimate": "effect-size-pooling",
    "meta-analysis-effect-size": "effect-size-pooling",
    "direct-hypothesis-support": "hypothesis-support-synthesis",
    "diagnostic-test-accuracy": "diagnostic-test-synthesis",
    "truth-label-estimation": "truth-discovery",
    "source-reliability-estimation": "truth-discovery",
    "data-cleaning": "data-cleaning-repair",
    "repair-uncertainty": "data-cleaning-repair",
    "causal-meta-analysis": "causal-meta-analysis",
    "causal-discovery-run": "causal-discovery-synthesis",
    "llm-causal-prior": "llm-prior-constraint-synthesis",
    "mechanistic-network": "mechanistic-network-synthesis",
    "mediation-analysis": "mediation-synthesis",
    "mendelian-randomization-graph": "mendelian-randomization-graph-synthesis",
    "graph-diagnostic": "graph-diagnostic-synthesis",
    "conditional-dependence-graph": "graph-estimate-synthesis",
    "graph-estimate": "graph-estimate-synthesis",
    "graph-posterior": "graph-posterior-synthesis",
    "integrative-clustering": "integrative-clustering-synthesis",
    "feature-selection": "feature-selection-synthesis",
    "module-discovery": "module-discovery-synthesis",
    "predictive-integration": "predictive-integration-synthesis",
}


def route_synthesis_family(operator: str) -> str:
    """Return the canonical synthesis family for a known operator/output route key."""

    try:
        return _ROUTE_ALIASES[operator]
    except KeyError as exc:
        raise PayloadValidationError(f"no synthesis-family route for operator {operator!r}") from exc


def derivation_edges(payload: EvidencePayload) -> list[SynthesisDerivationEdge]:
    """Return t023 derivation edges implied by a synthesis payload."""

    operation = SynthesisOperation.model_validate(payload.extension_sections[SYNTHESIS_OPERATION_EXTENSION])
    source = payload.core.payload_id
    edges: list[SynthesisDerivationEdge] = []

    for ref in payload.core.input_artifact_refs:
        edges.append((source, "consumes", ref))
    if payload.core.method_ref is not None:
        edges.append((source, "uses-method", payload.core.method_ref))
    if payload.core.agent_ref is not None:
        edges.append((source, "performed-by", payload.core.agent_ref))
    for ref in payload.core.proposition_refs:
        edges.append((source, "targets-proposition", ref))
    for ref in operation.output_artifact_refs:
        edges.append((source, "produced", ref))
        edges.append((ref, "derived-from-synthesis", source))
    return edges
```

- [ ] **Step 4: Run the focused routing and edge tests**

Run:

```bash
uv run --project science pytest science/tests/test_synthesis_payload.py -k "route_synthesis_family or derivation_edges" -q
```

Expected: PASS.

- [ ] **Step 5: Run all synthesis payload tests**

Run:

```bash
uv run --project science pytest science/tests/test_synthesis_payload.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/synthesis_payload.py science/tests/test_synthesis_payload.py
git commit -m "feat: add synthesis routing and derivation edges"
```

---

### Task 4: Add Contract Documentation And Full Verification

**Files:**
- Create: `science/docs/typed-synthesis-nodes.md`
- Modify: `science/tests/test_synthesis_payload.py`

- [ ] **Step 1: Add one documentation consistency test**

Add this import to the top of `science/tests/test_synthesis_payload.py`:

```python
from pathlib import Path
```

Modify the `from science_tool.synthesis_payload import (...)` block in `science/tests/test_synthesis_payload.py` so it includes `SYNTHESIS_FAMILIES`:

```python
from science_tool.synthesis_payload import (
    SYNTHESIS_FAMILIES,
    SYNTHESIS_OPERATION_EXTENSION,
    SYNTHESIS_PRIMARY_EXTENSION_NAMES,
    SynthesisOperation,
    build_synthesis_registry,
    derivation_edges,
    route_synthesis_family,
    validate_synthesis_payload,
)
```

Then append this test to `science/tests/test_synthesis_payload.py`:

```python

def test_typed_synthesis_docs_list_every_family() -> None:
    docs = Path(__file__).resolve().parents[1] / "docs" / "typed-synthesis-nodes.md"
    text = docs.read_text()

    for family in SYNTHESIS_FAMILIES:
        assert f"`{family}`" in text
```

- [ ] **Step 2: Run the documentation test to verify it fails**

Run:

```bash
uv run --project science pytest science/tests/test_synthesis_payload.py::test_typed_synthesis_docs_list_every_family -q
```

Expected: FAIL with `FileNotFoundError` because `science/docs/typed-synthesis-nodes.md` does not exist.

- [ ] **Step 3: Create the implementation-facing docs**

Create `science/docs/typed-synthesis-nodes.md` with this content:

````markdown
# Typed Synthesis Nodes

Typed synthesis nodes implement `meta/doc/plans/2026-05-07-t023-typed-synthesis-nodes-design.md`.

Near term, a synthesis node is an `EvidencePayload` whose `core.artifact_type` is a synthesis-family artifact type. There is no separate synthesis store. Every synthesis payload lists its family as the primary extension and also loads `synthesis-operation`.

Required shape:

```yaml
core:
  payload_id: syn-2026-example
  artifact_type: bayesian-model-comparison
  extensions: [bayesian-model-comparison, synthesis-operation]
  input_artifact_refs: [study:input]
  proposition_refs: [prop:model-a-over-null]
  validation_role: prioritize-attention
  validation_status: pending
  reason_codes: []
extension/bayesian-model-comparison: {}
extension/synthesis-operation:
  output_artifact_refs: [payload:model-summary]
  operator_assumption_refs: [assumption:prior-model-probabilities-explicit]
```

Families:

- `effect-size-pooling`
- `hypothesis-support-synthesis`
- `bayesian-model-comparison`
- `diagnostic-test-synthesis`
- `truth-discovery`
- `decision-analytic-score`
- `data-cleaning-repair`
- `causal-meta-analysis`
- `causal-discovery-synthesis`
- `llm-prior-constraint-synthesis`
- `mechanistic-network-synthesis`
- `mediation-synthesis`
- `mendelian-randomization-graph-synthesis`
- `graph-diagnostic-synthesis`
- `graph-estimate-synthesis`
- `graph-posterior-synthesis`
- `integrative-clustering-synthesis`
- `feature-selection-synthesis`
- `module-discovery-synthesis`
- `predictive-integration-synthesis`

`decision-analytic-score` is reserved. Validators reject production payloads with that family until an owning task defines a detailed schema.

Routing rules:

- Model-set posterior probabilities, Bayes factors, and BMA outputs route to `bayesian-model-comparison`.
- Pooled numeric effect estimates route to `effect-size-pooling`.
- Direct proposition support aggregation routes to `hypothesis-support-synthesis`.
- Diagnostic accuracy outputs route to `diagnostic-test-synthesis`.
- Source reliability or truth-label estimation routes to `truth-discovery`.
- Causal outputs route to causal families and require downstream guardrails before belief strengthening.
- Noncausal graph, clustering, feature-selection, module, and predictive integration outputs route to graph-valued families.

Effective reason codes are computed views. Source-authored payloads store only `core.reason_codes` plus extension-local reason codes.
````

- [ ] **Step 4: Run the documentation test**

Run:

```bash
uv run --project science pytest science/tests/test_synthesis_payload.py::test_typed_synthesis_docs_list_every_family -q
```

Expected: PASS.

- [ ] **Step 5: Run focused test suite**

Run:

```bash
uv run --project science pytest science/tests/test_evidence_payload_contract.py science/tests/test_synthesis_payload.py -q
```

Expected: PASS.

- [ ] **Step 6: Run formatting and static checks**

Run:

```bash
uv run --project science ruff format science/src/science_tool/evidence_payload.py science/src/science_tool/synthesis_payload.py science/tests/test_evidence_payload_contract.py science/tests/test_synthesis_payload.py
uv run --project science ruff check science/src/science_tool/evidence_payload.py science/src/science_tool/synthesis_payload.py science/tests/test_evidence_payload_contract.py science/tests/test_synthesis_payload.py
uv run --project science pyright science/src/science_tool/evidence_payload.py science/src/science_tool/synthesis_payload.py
```

Expected:

- Ruff format exits 0.
- Ruff check exits 0.
- Pyright exits 0 with no errors in the checked files.

- [ ] **Step 7: Run project validation from the meta project**

Run:

```bash
bash validate.sh --verbose
```

from `meta/`.

Expected: exits 0. Existing unrelated warnings may remain: invalid `h05` phase, existing `[UNVERIFIED]` markers, and stale graph inputs.

- [ ] **Step 8: Commit**

```bash
git add science/docs/typed-synthesis-nodes.md science/tests/test_synthesis_payload.py
git commit -m "docs: document typed synthesis payload contract"
```

---

## Implementation Notes

- Use `apply_patch` for manual edits.
- Keep `science_tool.evidence_payload` generic. Do not move the synthesis-family table into that module.
- Do not add a CLI in this plan. No existing payload CLI exists, and the design only needs a reusable validation/library surface.
- Do not write `effective_reason_codes` into source-authored payloads. It remains computed.
- Do not implement lifecycle, replay, invalidation, or artifact supersession; those belong to `t042`.

## Self-Review Checklist

- Spec coverage:
  - Payload relationship to `t022`: Task 2 validates synthesis families as normal `EvidencePayload` records.
  - `synthesis-operation` contract: Task 2 adds `SynthesisOperation` and required co-extension validation.
  - Taxonomy and permissions: Task 2 adds `SYNTHESIS_FAMILIES` with default and max permissions.
  - Reserved `decision-analytic-score`: Task 2 rejects production use.
  - Routing rules: Task 3 adds `route_synthesis_family()`.
  - Graph derivation edges: Task 3 adds `derivation_edges()`.
  - Computed effective reason codes: Task 2 reuses `EvidencePayloadRegistry.validate_payload()` and Task 4 documents source-authored versus computed code state.
  - `t042` boundary: Task 4 documents that lifecycle/replay remains out of scope.
- Marker scan:
  - Checked for prohibited markers and unspecified test steps.
- Type consistency:
  - `SynthesisOperation`, `SynthesisFamilySpec`, `SYNTHESIS_FAMILIES`, `build_synthesis_registry()`, `validate_synthesis_payload()`, `route_synthesis_family()`, and `derivation_edges()` are introduced before later steps reference them.
