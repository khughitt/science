# P3 Domain Grounding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only domain-grounding layer that computes proposition grounding from existing evidence-line belief machinery and projects it onto P2 prose decomposition units.

**Architecture:** Add a source-agnostic `science_tool.graph.grounding` core that resolves proposition refs, expands evidence targets through `_evidence_targets_for_uri`, calls `collect_evidence_units` and `aggregate_belief`, and returns typed grounding results. Add `science_tool.annotation.prose_grounding` as the prose-specific projection that joins P2 units to `promoted_to` by fingerprint, writes `data/prose-grounding/<slug>/grounding.json`, and exposes the same payload through the annotation CLI.

**Tech Stack:** Python 3.13, Click, rdflib `Dataset`/`Graph`, pytest, existing `science_tool.graph.belief`, existing P2 `ProseDecompositionStore`.

---

## Source Documents

- Design: `docs/plans/2026-06-18-prose-epistemics-p3-domain-grounding-design.md`
- Parent umbrella: `docs/plans/2026-06-17-prose-epistemics-umbrella-design.md`
- P2 design: `docs/plans/2026-06-18-prose-epistemics-p2-internal-prose-design.md`

## File Structure

- Create `science/src/science_tool/graph/grounding.py`
  - Source-agnostic grounding core.
  - Owns `GroundingStatus`, `GroundingError`, `GroundingResult`, graph loading, target resolution, floor validation, and JSON conversion.
  - Depends on `science_tool.graph.belief`, `science_tool.graph.store._evidence_targets_for_uri`, `_graph_uri`, and `_load_dataset`.

- Create `science/tests/test_grounding.py`
  - Unit tests for the grounding core using in-memory rdflib graphs and a small serialized TriG graph.

- Create `science/src/science_tool/annotation/prose_grounding.py`
  - P2-specific projection from latest decomposition/index state to prose grounding rows.
  - Owns `ProseGroundingError`, report dataclasses, summary calculation, payload conversion, artifact path, and timestamp-churn-safe artifact writing.
  - Depends on `ProseDecompositionStore`, `artifact_unit_ref`, and `ground_proposition`.

- Create `science/tests/test_prose_grounding.py`
  - Projection and artifact writer tests.

- Modify `science/src/science_tool/annotation/cli.py`
  - Add `ground-prose-decomposition` command to the existing annotation CLI group.
  - Keep P2 command family naming consistent with `ingest-/check-/promote-prose-decomposition`.

- Modify `science/tests/test_annotate_prose_decomposition_cli.py`
  - Add CLI tests for JSON output, write mode, and clean errors.

## Implementation Notes

- Run all commands from `science/` unless a step says otherwise.
- Use sandbox-safe pytest temp dirs:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p3-example tests/test_grounding.py
```

- Use `rtk git` in commit commands.
- Do not call P2 promotion or write `.anno.trig` sidecars in P3.
- Do not add evidence-line authoring, domain-paper ingestion, or natural-systems content migration.

---

### Task 1: Grounding Core

**Files:**
- Create: `science/src/science_tool/graph/grounding.py`
- Test: `science/tests/test_grounding.py`

- [ ] **Step 1: Write failing grounding-core tests**

Create `science/tests/test_grounding.py` with this content:

```python
from pathlib import Path

import pytest
from rdflib import Dataset, Graph, Literal, RDF, URIRef

from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS


TARGET = PROJECT_NS["proposition/p"]
LINE_A = PROJECT_NS["evidence-line/a"]
LINE_B = PROJECT_NS["evidence-line/b"]
LINE_DISPUTE = PROJECT_NS["evidence-line/dispute"]


def _graphs() -> tuple[Graph, Graph]:
    knowledge = Graph()
    provenance = Graph()
    knowledge.add((TARGET, RDF.type, SCI_NS.Proposition))
    return knowledge, provenance


def _support(
    knowledge: Graph,
    provenance: Graph,
    line: URIRef,
    *,
    group: str,
    role: str = "direct_test",
) -> None:
    knowledge.add((line, RDF.type, SCI_NS.EvidenceLine))
    knowledge.add((line, CITO_NS.supports, TARGET))
    provenance.add((line, SCI_NS.evidenceStrength, Literal("strong")))
    provenance.add((line, SCI_NS.evidenceIndependence, Literal("independent")))
    provenance.add((line, SCI_NS.independenceGroup, Literal(group)))
    provenance.add((line, SCI_NS.evidenceRole, Literal(role)))
    provenance.add((line, SCI_NS.evidenceType, Literal("empirical_data_evidence")))


def test_ground_proposition_no_evidence_is_unbacked() -> None:
    from science_tool.graph.grounding import GroundingStatus, ground_proposition

    knowledge, provenance = _graphs()

    result = ground_proposition("proposition:p", knowledge, provenance)

    assert result.target_ref == "proposition:p"
    assert result.status == GroundingStatus.UNBACKED
    assert result.belief_magnitude == "speculative"
    assert result.belief_display == "speculative"
    assert result.floor == "supported"
    assert result.support_units == 0
    assert result.dispute_units == 0
    assert result.policy_id == "core-default"
    assert result.policy_version == "1"


def test_ground_proposition_one_support_is_below_supported_floor() -> None:
    from science_tool.graph.grounding import GroundingStatus, ground_proposition

    knowledge, provenance = _graphs()
    _support(knowledge, provenance, LINE_A, group="g1")

    result = ground_proposition("proposition:p", knowledge, provenance)

    assert result.status == GroundingStatus.BELOW_FLOOR
    assert result.belief_magnitude == "fragile"
    assert result.support_units == 1
    assert result.to_json()["status"] == "below_floor"


def test_ground_proposition_two_supports_are_grounded() -> None:
    from science_tool.graph.grounding import GroundingStatus, ground_proposition

    knowledge, provenance = _graphs()
    _support(knowledge, provenance, LINE_A, group="g1", role="proxy_support")
    _support(knowledge, provenance, LINE_B, group="g2", role="proxy_support")

    result = ground_proposition("proposition:p", knowledge, provenance)

    assert result.status == GroundingStatus.GROUNDED
    assert result.belief_magnitude == "supported"
    assert result.support_units == 2


def test_ground_proposition_contested_flag_is_preserved() -> None:
    from science_tool.graph.grounding import ground_proposition

    knowledge, provenance = _graphs()
    _support(knowledge, provenance, LINE_A, group="g1", role="proxy_support")
    _support(knowledge, provenance, LINE_B, group="g2", role="proxy_support")
    knowledge.add((LINE_DISPUTE, RDF.type, SCI_NS.EvidenceLine))
    knowledge.add((LINE_DISPUTE, CITO_NS.disputes, TARGET))
    provenance.add((LINE_DISPUTE, SCI_NS.evidenceStrength, Literal("strong")))
    provenance.add((LINE_DISPUTE, SCI_NS.evidenceIndependence, Literal("independent")))
    provenance.add((LINE_DISPUTE, SCI_NS.independenceGroup, Literal("g3")))
    provenance.add((LINE_DISPUTE, SCI_NS.evidenceRole, Literal("model_criticism")))
    provenance.add((LINE_DISPUTE, SCI_NS.disputeScope, Literal("generalization")))

    result = ground_proposition("proposition:p", knowledge, provenance)

    assert result.status.value == "grounded"
    assert result.contested is True
    assert result.diagnostic_units == 1


def test_ground_proposition_invalid_floor_fails() -> None:
    from science_tool.graph.grounding import GroundingError, ground_proposition

    knowledge, provenance = _graphs()

    with pytest.raises(GroundingError, match="unknown grounding floor"):
        ground_proposition("proposition:p", knowledge, provenance, floor="confident")


def test_ground_proposition_missing_target_fails() -> None:
    from science_tool.graph.grounding import GroundingError, ground_proposition

    knowledge, provenance = Graph(), Graph()

    with pytest.raises(GroundingError, match="not found in knowledge graph"):
        ground_proposition("proposition:missing", knowledge, provenance)


def test_load_grounding_graphs_reads_named_graphs(tmp_path: Path) -> None:
    from science_tool.graph.grounding import load_grounding_graphs
    from science_tool.graph.store import _graph_uri

    dataset = Dataset()
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    knowledge.add((TARGET, RDF.type, SCI_NS.Proposition))
    provenance.add((TARGET, SCI_NS.claimLayer, Literal("empirical_regularity")))
    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir(parents=True)
    dataset.serialize(destination=str(graph_path), format="trig")

    loaded_knowledge, loaded_provenance = load_grounding_graphs(graph_path)

    assert (TARGET, RDF.type, SCI_NS.Proposition) in loaded_knowledge
    assert (TARGET, SCI_NS.claimLayer, Literal("empirical_regularity")) in loaded_provenance
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p3-grounding-red tests/test_grounding.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.graph.grounding'`.

- [ ] **Step 3: Implement `science_tool.graph.grounding`**

Create `science/src/science_tool/graph/grounding.py`:

```python
"""Read-only proposition grounding from materialized evidence-line belief."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from rdflib import RDF, Graph, URIRef

from science_tool.graph.belief import BeliefMagnitude, aggregate_belief, collect_evidence_units
from science_tool.graph.io import PROJECT_NS, SCI_NS
from science_tool.graph.store import _evidence_targets_for_uri, _graph_uri, _load_dataset


DEFAULT_GROUNDING_FLOOR = BeliefMagnitude.SUPPORTED.value


class GroundingError(ValueError):
    """Raised when proposition grounding cannot be computed from the supplied graph."""


class GroundingStatus(StrEnum):
    GROUNDED = "grounded"
    BELOW_FLOOR = "below_floor"
    UNBACKED = "unbacked"


@dataclass(frozen=True)
class GroundingResult:
    target_ref: str
    status: GroundingStatus
    belief_magnitude: str
    belief_display: str
    floor: str
    contested: bool
    support_units: int
    dispute_units: int
    diagnostic_units: int
    excluded_units: int
    flagged_ungrouped_units: int
    capped_by_refutation: bool
    authored_capped: bool
    qa_dataset_capped: bool
    policy_id: str
    policy_version: str

    def to_json(self) -> dict[str, object]:
        return {
            "target_ref": self.target_ref,
            "status": self.status.value,
            "belief_magnitude": self.belief_magnitude,
            "belief_display": self.belief_display,
            "floor": self.floor,
            "contested": self.contested,
            "support_units": self.support_units,
            "dispute_units": self.dispute_units,
            "diagnostic_units": self.diagnostic_units,
            "excluded_units": self.excluded_units,
            "flagged_ungrouped_units": self.flagged_ungrouped_units,
            "capped_by_refutation": self.capped_by_refutation,
            "authored_capped": self.authored_capped,
            "qa_dataset_capped": self.qa_dataset_capped,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
        }


_MAGNITUDE_ORDER = [
    BeliefMagnitude.SPECULATIVE.value,
    BeliefMagnitude.FRAGILE.value,
    BeliefMagnitude.SUPPORTED.value,
    BeliefMagnitude.WELL_SUPPORTED.value,
]


def load_grounding_graphs(graph_path: Path) -> tuple[Graph, Graph]:
    if not graph_path.exists():
        raise GroundingError(f"graph file is missing: {graph_path}")
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    if len(knowledge) == 0:
        raise GroundingError(f"knowledge graph is empty or missing in {graph_path}")
    return knowledge, provenance


def ground_proposition(
    ref_or_uri: str | URIRef,
    knowledge: Graph,
    provenance: Graph,
    *,
    floor: str = DEFAULT_GROUNDING_FLOOR,
) -> GroundingResult:
    floor = _validate_floor(floor)
    target_uri = _target_uri(ref_or_uri)
    _require_proposition_target(knowledge, target_uri, ref_or_uri)
    units = collect_evidence_units(
        knowledge,
        provenance,
        _evidence_targets_for_uri(knowledge, target_uri),
    )
    belief = aggregate_belief(units)
    magnitude = belief.magnitude.value
    status = _grounding_status(
        support_count=len(belief.support_units),
        magnitude=magnitude,
        floor=floor,
    )
    return GroundingResult(
        target_ref=_target_ref(target_uri),
        status=status,
        belief_magnitude=magnitude,
        belief_display=belief.display(),
        floor=floor,
        contested=belief.contested,
        support_units=len(belief.support_units),
        dispute_units=len(belief.dispute_units),
        diagnostic_units=len(belief.diagnostics),
        excluded_units=len(belief.excluded),
        flagged_ungrouped_units=len(belief.flagged_ungrouped),
        capped_by_refutation=belief.capped_by_refutation,
        authored_capped=belief.authored_capped,
        qa_dataset_capped=belief.qa_dataset_capped,
        policy_id=belief.policy_id,
        policy_version=belief.policy_version,
    )


def ground_propositions(
    refs_or_uris: list[str | URIRef],
    knowledge: Graph,
    provenance: Graph,
    *,
    floor: str = DEFAULT_GROUNDING_FLOOR,
) -> list[GroundingResult]:
    return [ground_proposition(ref, knowledge, provenance, floor=floor) for ref in refs_or_uris]


def _validate_floor(floor: str) -> str:
    if floor not in _MAGNITUDE_ORDER:
        raise GroundingError(f"unknown grounding floor: {floor}")
    return floor


def _grounding_status(*, support_count: int, magnitude: str, floor: str) -> GroundingStatus:
    if support_count == 0:
        return GroundingStatus.UNBACKED
    if _MAGNITUDE_ORDER.index(magnitude) >= _MAGNITUDE_ORDER.index(floor):
        return GroundingStatus.GROUNDED
    return GroundingStatus.BELOW_FLOOR


def _target_uri(ref_or_uri: str | URIRef) -> URIRef:
    if isinstance(ref_or_uri, URIRef):
        return ref_or_uri
    if ref_or_uri.startswith("http://") or ref_or_uri.startswith("https://"):
        return URIRef(ref_or_uri)
    if not ref_or_uri.startswith("proposition:"):
        raise GroundingError("grounding target must be a proposition:<slug> ref")
    slug = ref_or_uri.split(":", 1)[1]
    if not slug:
        raise GroundingError("grounding target proposition slug must not be empty")
    return PROJECT_NS[f"proposition/{slug}"]


def _target_ref(target_uri: URIRef) -> str:
    text = str(target_uri)
    prefix = str(PROJECT_NS["proposition/"])
    if text.startswith(prefix):
        return "proposition:" + text[len(prefix):]
    return text


def _require_proposition_target(knowledge: Graph, target_uri: URIRef, original: str | URIRef) -> None:
    if (target_uri, RDF.type, SCI_NS.Proposition) not in knowledge:
        raise GroundingError(f"proposition target not found in knowledge graph: {original}")
```

- [ ] **Step 4: Run grounding-core tests**

Run:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p3-grounding-green tests/test_grounding.py
```

Expected: PASS, all tests in `tests/test_grounding.py`.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
rtk git add science/src/science_tool/graph/grounding.py science/tests/test_grounding.py
rtk git commit -m "feat(grounding): add proposition grounding core"
```

Expected: commit succeeds.

---

### Task 2: Prose Grounding Projection

**Files:**
- Create: `science/src/science_tool/annotation/prose_grounding.py`
- Test: `science/tests/test_prose_grounding.py`

- [ ] **Step 1: Write failing prose projection tests**

Create `science/tests/test_prose_grounding.py`:

```python
import json
from pathlib import Path

import pytest
from rdflib import Dataset, Literal, RDF

from science_tool.annotation.prose_decomposition import (
    ProseDecompositionStore,
    compute_source_hash,
    parse_submitted_decomposition,
)
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS
from science_tool.graph.store import _graph_uri


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "docs" / "example.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        "# Section\n\n"
        "Basalt flows record the cooling history.\n\n"
        "Ash layers date the eruption sequence.\n",
        encoding="utf-8",
    )
    return source


def _artifact_payload(
    tmp_path: Path,
    *,
    artifact_id: str = "decomp-1",
    unit_id: str = "u001",
    quote: str = "Basalt flows record the cooling history.",
) -> dict:
    source = _source(tmp_path)
    return {
        "schema_version": 1,
        "source": {
            "kind": "prose-source",
            "slug": "example",
            "path": str(source),
            "title": "Example",
            "content_hash": compute_source_hash(source),
        },
        "artifact": {"id": artifact_id, "generated_at": "2026-06-18T12:00:00Z", "producer": "offline-agent"},
        "units": [
            {
                "unit_id": unit_id,
                "disposition": "candidate",
                "locator": {"regime": "markdown-heading-path", "value": ["Section"]},
                "payload": {
                    "type": "proposition",
                    "exact": quote,
                    "prefix": "",
                    "suffix": "",
                    "stance": "asserted",
                },
            },
            {
                "unit_id": "s001",
                "disposition": "skip",
                "reason": {"code": "not_a_claim", "detail": "Heading only."},
                "locator": {
                    "regime": "markdown-heading-path-with-quote",
                    "value": ["Section"],
                    "quote": {"exact": "Basalt flows", "prefix": "", "suffix": ""},
                },
            },
        ],
    }


def _persist_artifact(tmp_path: Path, payload: dict):
    artifact = parse_submitted_decomposition(json.dumps(payload), project_root=tmp_path)
    store = ProseDecompositionStore(tmp_path)
    store.persist(artifact)
    return artifact, store


def _write_graph(tmp_path: Path, *, supports: int) -> Path:
    dataset = Dataset()
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    target = PROJECT_NS["proposition/basalt-cooling"]
    knowledge.add((target, RDF.type, SCI_NS.Proposition))
    for index in range(supports):
        line = PROJECT_NS[f"evidence-line/s{index}"]
        knowledge.add((line, RDF.type, SCI_NS.EvidenceLine))
        knowledge.add((line, CITO_NS.supports, target))
        provenance.add((line, SCI_NS.evidenceStrength, Literal("strong")))
        provenance.add((line, SCI_NS.evidenceIndependence, Literal("independent")))
        provenance.add((line, SCI_NS.independenceGroup, Literal(f"g{index}")))
        provenance.add((line, SCI_NS.evidenceRole, Literal("proxy_support")))
        provenance.add((line, SCI_NS.evidenceType, Literal("empirical_data_evidence")))
    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir(parents=True)
    dataset.serialize(destination=str(graph_path), format="trig")
    return graph_path


def test_build_prose_grounding_report_joins_promoted_unit_by_fingerprint(tmp_path: Path) -> None:
    from science_tool.annotation.prose_grounding import build_prose_grounding_report

    artifact, store = _persist_artifact(tmp_path, _artifact_payload(tmp_path))
    store.record_promotion("example", artifact.units[0].fingerprint, "proposition:basalt-cooling")
    graph_path = _write_graph(tmp_path, supports=2)

    report = build_prose_grounding_report(
        project_root=tmp_path,
        source_ref="prose-source:example",
        graph_path=graph_path,
        generated_at="2026-06-18T12:00:00Z",
    )

    payload = report.to_json()
    assert payload["source_ref"] == "prose-source:example"
    assert payload["decomposition_artifact_id"] == "decomp-1"
    assert payload["grounding_policy"] == {
        "floor": "supported",
        "belief_policy_id": "core-default",
        "belief_policy_version": "1",
    }
    assert payload["summary"]["grounded_units"] == 1
    assert payload["summary"]["skipped_units"] == 1
    candidate = payload["units"][0]
    assert candidate["unit_id"] == "u001"
    assert candidate["fingerprint"] == artifact.units[0].fingerprint
    assert candidate["proposition_ref"] == "proposition:basalt-cooling"
    assert candidate["status"] == "grounded"
    assert candidate["grounding"]["belief_magnitude"] == "supported"
    skip = payload["units"][1]
    assert skip["status"] == "skipped"
    assert skip["skip_reason"] == "not_a_claim"


def test_build_prose_grounding_report_keeps_promoted_link_across_unit_renumber(tmp_path: Path) -> None:
    from science_tool.annotation.prose_grounding import build_prose_grounding_report

    first, store = _persist_artifact(tmp_path, _artifact_payload(tmp_path, unit_id="u001"))
    store.record_promotion("example", first.units[0].fingerprint, "proposition:basalt-cooling")
    second_payload = _artifact_payload(tmp_path, artifact_id="decomp-2", unit_id="u777")
    store.persist(parse_submitted_decomposition(json.dumps(second_payload), project_root=tmp_path))
    graph_path = _write_graph(tmp_path, supports=2)

    report = build_prose_grounding_report(
        project_root=tmp_path,
        source_ref="prose-source:example",
        graph_path=graph_path,
        generated_at="2026-06-18T12:00:00Z",
    )

    candidate = report.to_json()["units"][0]
    assert candidate["unit_id"] == "u777"
    assert candidate["proposition_ref"] == "proposition:basalt-cooling"
    assert candidate["status"] == "grounded"


def test_build_prose_grounding_report_classifies_unpromoted_and_below_floor(tmp_path: Path) -> None:
    from science_tool.annotation.prose_grounding import build_prose_grounding_report

    artifact, store = _persist_artifact(tmp_path, _artifact_payload(tmp_path))
    store.record_promotion("example", artifact.units[0].fingerprint, "proposition:basalt-cooling")
    graph_path = _write_graph(tmp_path, supports=1)

    report = build_prose_grounding_report(
        project_root=tmp_path,
        source_ref="prose-source:example",
        graph_path=graph_path,
        generated_at="2026-06-18T12:00:00Z",
    )

    payload = report.to_json()
    assert payload["summary"]["below_floor_units"] == 1
    assert payload["units"][0]["status"] == "below_floor"
    assert payload["units"][0]["grounding"]["belief_magnitude"] == "fragile"


def test_build_prose_grounding_report_classifies_unpromoted_candidate(tmp_path: Path) -> None:
    from science_tool.annotation.prose_grounding import build_prose_grounding_report

    _persist_artifact(tmp_path, _artifact_payload(tmp_path))
    graph_path = _write_graph(tmp_path, supports=0)

    report = build_prose_grounding_report(
        project_root=tmp_path,
        source_ref="prose-source:example",
        graph_path=graph_path,
        generated_at="2026-06-18T12:00:00Z",
    )

    payload = report.to_json()
    assert payload["summary"]["unpromoted_units"] == 1
    assert payload["units"][0]["status"] == "unpromoted"
    assert payload["units"][0]["proposition_ref"] is None


def test_build_prose_grounding_report_missing_promoted_proposition_fails(tmp_path: Path) -> None:
    from science_tool.annotation.prose_grounding import ProseGroundingError, build_prose_grounding_report

    artifact, store = _persist_artifact(tmp_path, _artifact_payload(tmp_path))
    store.record_promotion("example", artifact.units[0].fingerprint, "proposition:missing")
    graph_path = _write_graph(tmp_path, supports=0)

    with pytest.raises(ProseGroundingError, match="not found in knowledge graph"):
        build_prose_grounding_report(
            project_root=tmp_path,
            source_ref="prose-source:example",
            graph_path=graph_path,
            generated_at="2026-06-18T12:00:00Z",
        )
```

- [ ] **Step 2: Run the failing prose projection tests**

Run:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p3-prose-red tests/test_prose_grounding.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.annotation.prose_grounding'`.

- [ ] **Step 3: Implement `science_tool.annotation.prose_grounding`**

Create `science/src/science_tool/annotation/prose_grounding.py`:

```python
"""Project graph grounding results back onto P2 prose decomposition units."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from science_tool.annotation.prose_decomposition import (
    DecompositionArtifact,
    DecompositionError,
    DecompositionUnit,
    ProseDecompositionStore,
    artifact_unit_ref,
)
from science_tool.graph.grounding import (
    DEFAULT_GROUNDING_FLOOR,
    GroundingError,
    GroundingResult,
    GroundingStatus,
    ground_proposition,
    load_grounding_graphs,
)


class ProseGroundingError(ValueError):
    """Raised when prose decomposition state cannot be joined to graph grounding."""


@dataclass(frozen=True)
class ProseGroundingReport:
    payload: dict[str, object]

    def to_json(self) -> dict[str, object]:
        return self.payload


def prose_grounding_path(project_root: Path, source_slug: str) -> Path:
    return project_root / "data" / "prose-grounding" / source_slug / "grounding.json"


def build_prose_grounding_report(
    *,
    project_root: Path,
    source_ref: str,
    graph_path: Path,
    generated_at: str,
    floor: str = DEFAULT_GROUNDING_FLOOR,
) -> ProseGroundingReport:
    slug = _source_slug(source_ref)
    store = ProseDecompositionStore(project_root)
    try:
        artifact = store.load_latest(slug)
        index = store.load_index(slug)
        knowledge, provenance = load_grounding_graphs(graph_path)
    except (DecompositionError, GroundingError) as exc:
        raise ProseGroundingError(str(exc)) from exc

    units_index = index.get("units")
    if not isinstance(units_index, dict):
        raise ProseGroundingError("prose decomposition index units must be an object")

    rows: list[dict[str, object]] = []
    policy: dict[str, object] | None = None
    current_fingerprints = {unit.fingerprint for unit in artifact.units}
    for unit in artifact.units:
        index_row = units_index.get(unit.fingerprint)
        if not isinstance(index_row, dict):
            raise ProseGroundingError(f"prose decomposition index row must be an object: {unit.fingerprint}")
        row, result = _row_for_current_unit(
            artifact=artifact,
            unit=unit,
            index_row=index_row,
            knowledge=knowledge,
            provenance=provenance,
            floor=floor,
        )
        if result is not None:
            policy = _policy_from_grounding(result)
        rows.append(row)

    for fingerprint, raw_row in units_index.items():
        if fingerprint in current_fingerprints:
            continue
        if not isinstance(raw_row, dict):
            raise ProseGroundingError(f"prose decomposition index row must be an object: {fingerprint}")
        if raw_row.get("stale") is True:
            rows.append(_stale_row(fingerprint, raw_row))

    if policy is None:
        policy = {"floor": floor, "belief_policy_id": "core-default", "belief_policy_version": "1"}

    graph_path_text = _project_relative_path(project_root, graph_path)
    return ProseGroundingReport(
        {
            "schema_version": 1,
            "source_ref": source_ref,
            "decomposition_artifact_id": artifact.artifact.artifact_id,
            "graph_path": graph_path_text,
            "generated_at": generated_at,
            "grounding_policy": policy,
            "summary": _summary(rows),
            "units": rows,
        }
    )


def write_prose_grounding_report(*, project_root: Path, report: ProseGroundingReport) -> bool:
    payload = report.to_json()
    source_ref = payload.get("source_ref")
    if not isinstance(source_ref, str):
        raise ProseGroundingError("grounding report source_ref must be a string")
    path = prose_grounding_path(project_root, _source_slug(source_ref))
    canonical = _canonical_json_text(payload)
    if path.exists():
        existing_text = path.read_text(encoding="utf-8")
        existing_payload = json.loads(existing_text)
        if _without_generated_at(existing_payload) == _without_generated_at(payload):
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(canonical, encoding="utf-8")
    tmp.replace(path)
    return True


def _row_for_current_unit(
    *,
    artifact: DecompositionArtifact,
    unit: DecompositionUnit,
    index_row: dict[str, object],
    knowledge,
    provenance,
    floor: str,
) -> tuple[dict[str, object], GroundingResult | None]:
    base = {
        "unit_id": unit.unit_id,
        "fingerprint": unit.fingerprint,
        "disposition": unit.disposition,
        "artifact_ref": artifact_unit_ref(artifact, unit),
    }
    if unit.disposition == "skip":
        return {
            **base,
            "status": "skipped",
            "skip_reason": unit.reason_code,
            "skip_detail": unit.reason_detail,
        }, None
    promoted_to = index_row.get("promoted_to")
    if promoted_to is None:
        return {**base, "status": "unpromoted", "proposition_ref": None, "grounding": None}, None
    if not isinstance(promoted_to, str):
        raise ProseGroundingError(f"promoted_to must be a string: {unit.fingerprint}")
    if not promoted_to.startswith("proposition:"):
        raise ProseGroundingError(f"promoted_to must be a proposition ref: {promoted_to}")
    try:
        grounding = ground_proposition(promoted_to, knowledge, provenance, floor=floor)
    except GroundingError as exc:
        raise ProseGroundingError(str(exc)) from exc
    return {
        **base,
        "status": grounding.status.value,
        "proposition_ref": promoted_to,
        "grounding": _grounding_payload(grounding),
    }, grounding


def _grounding_payload(result: GroundingResult) -> dict[str, object]:
    data = result.to_json()
    data.pop("target_ref", None)
    data.pop("status", None)
    data["belief_policy_id"] = data.pop("policy_id")
    data["belief_policy_version"] = data.pop("policy_version")
    return data


def _policy_from_grounding(result: GroundingResult) -> dict[str, object]:
    return {
        "floor": result.floor,
        "belief_policy_id": result.policy_id,
        "belief_policy_version": result.policy_version,
    }


def _stale_row(fingerprint: str, index_row: dict[str, object]) -> dict[str, object]:
    return {
        "unit_id": index_row.get("latest_unit_id", ""),
        "fingerprint": fingerprint,
        "disposition": index_row.get("latest_disposition", ""),
        "artifact_ref": index_row.get("artifact_unit_ref", ""),
        "status": "stale",
        "proposition_ref": index_row.get("promoted_to"),
        "grounding": None,
    }


def _summary(rows: list[dict[str, object]]) -> dict[str, int]:
    current_candidates = [row for row in rows if row.get("disposition") == "candidate" and row.get("status") != "stale"]
    return {
        "current_candidate_units": len(current_candidates),
        "promoted_units": sum(1 for row in current_candidates if row.get("proposition_ref")),
        "grounded_units": sum(1 for row in current_candidates if row.get("status") == GroundingStatus.GROUNDED.value),
        "below_floor_units": sum(1 for row in current_candidates if row.get("status") == GroundingStatus.BELOW_FLOOR.value),
        "unbacked_units": sum(1 for row in current_candidates if row.get("status") == GroundingStatus.UNBACKED.value),
        "unpromoted_units": sum(1 for row in current_candidates if row.get("status") == "unpromoted"),
        "skipped_units": sum(1 for row in rows if row.get("status") == "skipped"),
        "stale_units": sum(1 for row in rows if row.get("status") == "stale"),
        "contested_units": sum(
            1
            for row in current_candidates
            if isinstance(row.get("grounding"), dict) and row["grounding"].get("contested") is True
        ),
    }


def _source_slug(source_ref: str) -> str:
    prefix = "prose-source:"
    if not isinstance(source_ref, str) or not source_ref.startswith(prefix):
        raise ProseGroundingError("--source must use prose-source:<slug>")
    slug = source_ref[len(prefix):]
    if not slug:
        raise ProseGroundingError("source slug must not be empty")
    return slug


def _project_relative_path(project_root: Path, path: Path) -> str:
    resolved_root = project_root.resolve()
    resolved_path = path.resolve()
    try:
        return resolved_path.relative_to(resolved_root).as_posix()
    except ValueError:
        return str(path)


def _canonical_json_text(payload: dict[str, object]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _without_generated_at(payload: dict[str, object]) -> dict[str, object]:
    clone = dict(payload)
    clone.pop("generated_at", None)
    return clone
```

- [ ] **Step 4: Run prose projection tests**

Run:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p3-prose-green tests/test_prose_grounding.py
```

Expected: PASS, all tests in `tests/test_prose_grounding.py`.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
rtk git add science/src/science_tool/annotation/prose_grounding.py science/tests/test_prose_grounding.py
rtk git commit -m "feat(prose): project grounding onto decomposition units"
```

Expected: commit succeeds.

---

### Task 3: Artifact Writer Churn Guard

**Files:**
- Modify: `science/tests/test_prose_grounding.py`
- Modify: `science/src/science_tool/annotation/prose_grounding.py`

- [ ] **Step 1: Add a failing artifact writer test**

Append this test to `science/tests/test_prose_grounding.py`:

```python
def test_write_prose_grounding_report_skips_timestamp_only_rewrite(tmp_path: Path) -> None:
    from science_tool.annotation.prose_grounding import (
        build_prose_grounding_report,
        prose_grounding_path,
        write_prose_grounding_report,
    )

    artifact, store = _persist_artifact(tmp_path, _artifact_payload(tmp_path))
    store.record_promotion("example", artifact.units[0].fingerprint, "proposition:basalt-cooling")
    graph_path = _write_graph(tmp_path, supports=2)
    first = build_prose_grounding_report(
        project_root=tmp_path,
        source_ref="prose-source:example",
        graph_path=graph_path,
        generated_at="2026-06-18T12:00:00Z",
    )
    second = build_prose_grounding_report(
        project_root=tmp_path,
        source_ref="prose-source:example",
        graph_path=graph_path,
        generated_at="2026-06-18T12:30:00Z",
    )

    assert write_prose_grounding_report(project_root=tmp_path, report=first) is True
    path = prose_grounding_path(tmp_path, "example")
    first_text = path.read_text(encoding="utf-8")
    assert write_prose_grounding_report(project_root=tmp_path, report=second) is False

    assert path.read_text(encoding="utf-8") == first_text
```

- [ ] **Step 2: Run the focused test**

Run:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p3-writer tests/test_prose_grounding.py::test_write_prose_grounding_report_skips_timestamp_only_rewrite
```

Expected: PASS if Task 2 already implemented the churn guard. If it fails, the failure should show the file was rewritten when only `generated_at` changed.

- [ ] **Step 3: Tighten writer implementation only if the focused test fails**

If the focused test fails, replace `write_prose_grounding_report` and `_without_generated_at` in `science/src/science_tool/annotation/prose_grounding.py` with:

```python
def write_prose_grounding_report(*, project_root: Path, report: ProseGroundingReport) -> bool:
    payload = report.to_json()
    source_ref = payload.get("source_ref")
    if not isinstance(source_ref, str):
        raise ProseGroundingError("grounding report source_ref must be a string")
    path = prose_grounding_path(project_root, _source_slug(source_ref))
    if path.exists():
        existing_payload = json.loads(path.read_text(encoding="utf-8"))
        if _without_generated_at(existing_payload) == _without_generated_at(payload):
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(_canonical_json_text(payload), encoding="utf-8")
    tmp.replace(path)
    return True


def _without_generated_at(payload: dict[str, object]) -> dict[str, object]:
    clone = dict(payload)
    clone.pop("generated_at", None)
    return clone
```

- [ ] **Step 4: Run prose grounding tests**

Run:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p3-prose-writer tests/test_prose_grounding.py
```

Expected: PASS, all tests in `tests/test_prose_grounding.py`.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
rtk git add science/src/science_tool/annotation/prose_grounding.py science/tests/test_prose_grounding.py
rtk git commit -m "fix(prose): avoid timestamp-only grounding artifact churn"
```

Expected: commit succeeds. If Step 3 required no implementation change, the commit contains only the new regression test.

---

### Task 4: Annotation CLI Command

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py`
- Modify: `science/tests/test_annotate_prose_decomposition_cli.py`

- [ ] **Step 1: Add failing CLI tests**

Add these imports near the top of `science/tests/test_annotate_prose_decomposition_cli.py`, with the existing imports:

```python
from rdflib import Dataset, Literal, RDF

from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS
from science_tool.graph.store import _graph_uri
```

Then append these helpers and tests to the same file:

```python
def _write_grounding_graph(root: Path, *, supports: int) -> Path:
    dataset = Dataset()
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    target = PROJECT_NS["proposition/basalt-cooling"]
    knowledge.add((target, RDF.type, SCI_NS.Proposition))
    for index in range(supports):
        line = PROJECT_NS[f"evidence-line/cli-s{index}"]
        knowledge.add((line, RDF.type, SCI_NS.EvidenceLine))
        knowledge.add((line, CITO_NS.supports, target))
        provenance.add((line, SCI_NS.evidenceStrength, Literal("strong")))
        provenance.add((line, SCI_NS.evidenceIndependence, Literal("independent")))
        provenance.add((line, SCI_NS.independenceGroup, Literal(f"cli-g{index}")))
        provenance.add((line, SCI_NS.evidenceRole, Literal("proxy_support")))
        provenance.add((line, SCI_NS.evidenceType, Literal("empirical_data_evidence")))
    graph_path = root / "knowledge" / "graph.trig"
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    dataset.serialize(destination=str(graph_path), format="trig")
    return graph_path


def _ingest_and_mark_promoted(root: Path) -> None:
    ingest = CliRunner().invoke(
        annotate_group,
        ["ingest-prose-decomposition", str(_artifact_file(root)), "--root", str(root)],
    )
    assert ingest.exit_code == 0, ingest.output
    store = ProseDecompositionStore(root)
    artifact = store.load_latest("example")
    store.record_promotion("example", artifact.units[0].fingerprint, "proposition:basalt-cooling")


def test_ground_prose_decomposition_json_output(tmp_path):
    _ingest_and_mark_promoted(tmp_path)
    graph_path = _write_grounding_graph(tmp_path, supports=2)

    result = CliRunner().invoke(
        annotate_group,
        [
            "ground-prose-decomposition",
            "--source",
            "prose-source:example",
            "--root",
            str(tmp_path),
            "--graph",
            str(graph_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["source_ref"] == "prose-source:example"
    assert payload["summary"]["grounded_units"] == 1
    assert payload["units"][0]["status"] == "grounded"


def test_ground_prose_decomposition_write_persists_artifact(tmp_path):
    _ingest_and_mark_promoted(tmp_path)
    graph_path = _write_grounding_graph(tmp_path, supports=2)

    result = CliRunner().invoke(
        annotate_group,
        [
            "ground-prose-decomposition",
            "--source",
            "prose-source:example",
            "--root",
            str(tmp_path),
            "--graph",
            str(graph_path),
            "--write",
        ],
    )

    assert result.exit_code == 0, result.output
    path = tmp_path / "data" / "prose-grounding" / "example" / "grounding.json"
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["summary"]["grounded_units"] == 1
    assert "wrote prose grounding" in result.output


def test_ground_prose_decomposition_rejects_bad_source_ref(tmp_path):
    result = CliRunner().invoke(
        annotate_group,
        ["ground-prose-decomposition", "--source", "paper:x", "--root", str(tmp_path)],
    )

    assert result.exit_code != 0
    assert "--source must use prose-source:<slug>" in result.output


def test_ground_prose_decomposition_missing_graph_fails(tmp_path):
    _ingest_and_mark_promoted(tmp_path)

    result = CliRunner().invoke(
        annotate_group,
        [
            "ground-prose-decomposition",
            "--source",
            "prose-source:example",
            "--root",
            str(tmp_path),
            "--graph",
            str(tmp_path / "knowledge" / "missing.trig"),
        ],
    )

    assert result.exit_code != 0
    assert "graph file is missing" in result.output
```

- [ ] **Step 2: Run the failing CLI tests**

Run:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p3-cli-red tests/test_annotate_prose_decomposition_cli.py -k ground_prose_decomposition
```

Expected: FAIL with Click output saying no such command `ground-prose-decomposition`.

- [ ] **Step 3: Add CLI imports**

In `science/src/science_tool/annotation/cli.py`, add this import near the existing prose imports:

```python
from science_tool.annotation.prose_grounding import (
    DEFAULT_GROUNDING_FLOOR,
    ProseGroundingError,
    build_prose_grounding_report,
    write_prose_grounding_report,
)
```

If `DEFAULT_GROUNDING_FLOOR` is not exported from `prose_grounding.py`, add this line there near imports:

```python
from science_tool.graph.grounding import DEFAULT_GROUNDING_FLOOR
```

- [ ] **Step 4: Add the `ground-prose-decomposition` command**

Insert this command in `science/src/science_tool/annotation/cli.py` after `promote_prose_decomposition_cmd`:

```python
@annotate_group.command("ground-prose-decomposition")
@click.option("--source", "source_ref", required=True)
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option("--graph", "graph_path", default=Path("knowledge/graph.trig"), type=click.Path(dir_okay=False, path_type=Path))
@click.option("--floor", default=DEFAULT_GROUNDING_FLOOR)
@click.option("--write", "do_write", is_flag=True, default=False)
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def ground_prose_decomposition_cmd(
    source_ref: str,
    root: Path | None,
    graph_path: Path,
    floor: str,
    do_write: bool,
    fmt: str,
) -> None:
    """Ground the latest internal-prose decomposition against evidence-line belief."""
    project_root = (root or Path.cwd()).resolve()
    if not graph_path.is_absolute():
        graph_path = project_root / graph_path
    try:
        report = build_prose_grounding_report(
            project_root=project_root,
            source_ref=source_ref,
            graph_path=graph_path,
            generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            floor=floor,
        )
        wrote = write_prose_grounding_report(project_root=project_root, report=report) if do_write else False
    except ProseGroundingError as exc:
        raise click.ClickException(str(exc)) from exc

    payload = report.to_json()
    if fmt == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    summary = payload["summary"]
    assert isinstance(summary, dict)
    click.echo(
        f"grounded prose decomposition for {source_ref}: "
        f"grounded={summary['grounded_units']} "
        f"below_floor={summary['below_floor_units']} "
        f"unbacked={summary['unbacked_units']} "
        f"unpromoted={summary['unpromoted_units']} "
        f"skipped={summary['skipped_units']} "
        f"stale={summary['stale_units']}"
    )
    if do_write:
        action = "wrote" if wrote else "unchanged"
        click.echo(f"{action} prose grounding artifact")
```

- [ ] **Step 5: Run CLI tests**

Run:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p3-cli-green tests/test_annotate_prose_decomposition_cli.py -k ground_prose_decomposition
```

Expected: PASS, selected CLI tests.

- [ ] **Step 6: Run all prose CLI tests**

Run:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p3-cli-all tests/test_annotate_prose_decomposition_cli.py
```

Expected: PASS, all tests in `tests/test_annotate_prose_decomposition_cli.py`.

- [ ] **Step 7: Commit Task 4**

Run:

```bash
rtk git add science/src/science_tool/annotation/cli.py science/tests/test_annotate_prose_decomposition_cli.py
rtk git commit -m "feat(annotate): add prose grounding command"
```

Expected: commit succeeds.

---

### Task 5: Regression and Polish

**Files:**
- Modify if needed: `science/src/science_tool/graph/grounding.py`
- Modify if needed: `science/src/science_tool/annotation/prose_grounding.py`
- Modify if needed: `science/src/science_tool/annotation/cli.py`

- [ ] **Step 1: Run focused P3 test suite**

Run:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p3-focused tests/test_grounding.py tests/test_prose_grounding.py tests/test_annotate_prose_decomposition_cli.py
```

Expected: PASS.

- [ ] **Step 2: Run P2 regression**

Run:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p2-regression tests/test_prose_decomposition.py tests/test_internal_prose_adapter.py tests/test_prose_source_entity.py tests/test_prose_promote.py tests/test_annotate_prose_decomposition_cli.py
```

Expected: PASS. This proves P3 did not break ingest/check/promote.

- [ ] **Step 3: Run belief regression**

Run:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-belief-regression tests/test_belief_aggregate.py tests/test_belief_collect.py tests/test_belief_cli.py tests/test_belief_e2e.py
```

Expected: PASS. This proves P3 did not alter the belief algorithm.

- [ ] **Step 4: Run P1 paper extract/promote regression**

Run:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-test-tmp PYTHONPATH=src:model/src rtk uv run --frozen pytest -q --basetemp=/tmp/science-p1-regression tests/test_text_source_adapter.py tests/test_annotate_extract_cli.py tests/test_annotate_promote_cli.py
```

Expected: PASS. rdflib deprecation warnings are acceptable if tests pass.

- [ ] **Step 5: Run ruff**

Run:

```bash
rtk uv run --frozen ruff check src/science_tool/graph/grounding.py src/science_tool/annotation/prose_grounding.py src/science_tool/annotation/cli.py tests/test_grounding.py tests/test_prose_grounding.py tests/test_annotate_prose_decomposition_cli.py
```

Expected: `All checks passed!`

- [ ] **Step 6: Fix any deterministic lint or import issues**

If ruff reports import ordering in `science/src/science_tool/annotation/cli.py`, reorder only the added imports so the file passes. If tests reveal a mismatch between the implementation and the plan's expected field names, preserve the field names from the design:

```python
"below_floor_units"
"unbacked_units"
"unpromoted_units"
"grounding_policy"
"belief_policy_id"
"belief_policy_version"
```

Run the failing command again after each change until it passes.

- [ ] **Step 7: Commit regression/polish changes**

Run:

```bash
rtk git status --short
rtk git add science/src/science_tool/graph/grounding.py science/src/science_tool/annotation/prose_grounding.py science/src/science_tool/annotation/cli.py science/tests/test_grounding.py science/tests/test_prose_grounding.py science/tests/test_annotate_prose_decomposition_cli.py
rtk git commit -m "test(prose): verify P3 grounding regressions"
```

Expected: commit succeeds if Step 6 changed files. If `rtk git status --short` shows no changes after Step 5, skip this commit and record that no polish changes were needed.

---

## Acceptance Criteria

- `science_tool.graph.grounding.ground_proposition(...)` returns source-agnostic grounding results for proposition refs.
- The grounding core uses `_evidence_targets_for_uri(...)` before `collect_evidence_units(...)`.
- The default grounding floor is `supported`.
- `unbacked` means no eligible support; `below_floor` means eligible support exists but magnitude is below floor.
- `science_tool.annotation.prose_grounding.build_prose_grounding_report(...)` joins P2 index state by fingerprint, not `unit_id`.
- `data/prose-grounding/<slug>/grounding.json` is written only when substantive payload changes.
- `science annotate ground-prose-decomposition` supports JSON output and write mode.
- P1 extract/promote, P2 prose decomposition/promote, and belief aggregation regressions pass.

## Self-Review Notes

- Spec coverage: Tasks 1-4 cover the grounding core, prose projection, durable JSON artifact, CLI, error/status model, fingerprint join, `_evidence_targets_for_uri`, and generated-at churn guard. Task 5 covers regression requirements.
- Placeholder scan: checked for red-flag tokens and instructions that require inventing unspecified behavior; none remain.
- Type consistency: `GroundingResult`, `GroundingStatus`, `ProseGroundingReport`, `build_prose_grounding_report`, and `write_prose_grounding_report` are introduced before later tasks reference them.
