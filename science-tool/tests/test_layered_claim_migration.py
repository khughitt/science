from __future__ import annotations

import json
from pathlib import Path

from rdflib import Dataset, Literal, Namespace
from rdflib.namespace import PROV, RDF

from science_model.reasoning import (
    ClaimLayer,
    EvidenceRole,
    IdentificationStrength,
    MeasurementModel,
    ProxyDirectness,
    RivalModelPacket,
    SupportScope,
)
from science_tool.graph.materialize import materialize_graph
from science_tool.graph.sources import load_project_sources
from science_tool.graph.store import (
    INITIAL_GRAPH_TEMPLATE,
    SCI_NS,
    add_concept,
    add_edge,
    add_proposition,
    export_graph_payload,
)

PROJECT_NS = Namespace("http://example.org/project/")


def _write_project(root: Path, *, with_layered_metadata: bool) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "science.yaml").write_text(
        "\n".join(
            [
                "name: layered-claims-demo",
                "knowledge_profiles:",
                "  local: local",
                "",
            ]
        ),
        encoding="utf-8",
    )

    prop_dir = root / "specs" / "propositions"
    prop_dir.mkdir(parents=True, exist_ok=True)
    frontmatter_lines = [
        "---",
        'id: "proposition:p01-layered"',
        'type: "proposition"',
        'title: "Layered proposition"',
        'status: "draft"',
        "related: []",
        "source_refs: []",
    ]
    if with_layered_metadata:
        frontmatter_lines.extend(
            [
                'claim_layer: "causal_effect"',
                'identification_strength: "interventional"',
                'proxy_directness: "indirect"',
                'supports_scope: "hypothesis_bundle"',
                'independence_group: "batch-1"',
                'evidence_role: "direct_test"',
                "measurement_model:",
                '  observed_entity: "observation:obs-1"',
                '  latent_construct: "latent:cell-state"',
                '  measurement_relation: "proxy for cell-state"',
                '  rationale: "frontmatter proxy path"',
                '  known_failure_modes: ["batch effect"]',
                '  substitutable_with: ["observation:obs-2"]',
                "rival_model_packet:",
                '  packet_id: "packet:demo"',
                '  target_hypothesis: "hypothesis:h01"',
                '  current_working_model: "model:a"',
                '  alternative_models: ["model:b"]',
                '  shared_observables: ["obs:a"]',
                '  discriminating_predictions: ["pred:1"]',
                '  adjudication_rule: "choose the simplest model"',
            ]
        )
    frontmatter_lines.extend(
        [
            'created: "2026-04-15"',
            "---",
            "",
            "Layered claim body.",
            "",
        ]
    )
    (prop_dir / "p01.md").write_text("\n".join(frontmatter_lines), encoding="utf-8")
    return root


def _write_graph() -> Path:
    graph_path = Path("/tmp/science-layered-claims-upstream-test.graph.trig")
    graph_path.write_text(INITIAL_GRAPH_TEMPLATE, encoding="utf-8")
    return graph_path


def test_load_project_sources_preserves_layered_claim_metadata_from_frontmatter(tmp_path: Path) -> None:
    project = _write_project(tmp_path / "project", with_layered_metadata=True)

    sources = load_project_sources(project)
    entity = next(entity for entity in sources.entities if entity.canonical_id == "proposition:p01-layered")

    assert entity.claim_layer == ClaimLayer.CAUSAL_EFFECT
    assert entity.identification_strength == IdentificationStrength.INTERVENTIONAL
    assert entity.proxy_directness == ProxyDirectness.INDIRECT
    assert entity.supports_scope == SupportScope.HYPOTHESIS_BUNDLE
    assert entity.independence_group == "batch-1"
    assert entity.evidence_role == EvidenceRole.DIRECT_TEST
    assert entity.measurement_model == MeasurementModel(
        observed_entity="observation:obs-1",
        latent_construct="latent:cell-state",
        measurement_relation="proxy for cell-state",
        rationale="frontmatter proxy path",
        known_failure_modes=["batch effect"],
        substitutable_with=["observation:obs-2"],
    )
    assert entity.rival_model_packet == RivalModelPacket(
        packet_id="packet:demo",
        target_hypothesis="hypothesis:h01",
        current_working_model="model:a",
        alternative_models=["model:b"],
        shared_observables=["obs:a"],
        discriminating_predictions=["pred:1"],
        adjudication_rule="choose the simplest model",
    )


def test_materialize_graph_emits_layered_claim_metadata_for_proposition_sources(tmp_path: Path) -> None:
    project = _write_project(tmp_path / "project", with_layered_metadata=True)

    trig_path = materialize_graph(project)
    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    proposition_uri = PROJECT_NS["proposition/p01-layered"]

    assert (proposition_uri, RDF.type, SCI_NS.Proposition) in knowledge
    assert (proposition_uri, SCI_NS.claimLayer, Literal("causal_effect")) in provenance
    assert (proposition_uri, SCI_NS.identificationStrength, Literal("interventional")) in provenance
    assert (proposition_uri, SCI_NS.proxyDirectness, Literal("indirect")) in provenance
    assert (proposition_uri, SCI_NS.supportsScope, Literal("hypothesis_bundle")) in provenance
    assert (proposition_uri, SCI_NS.independenceGroup, Literal("batch-1")) in provenance
    assert (proposition_uri, SCI_NS.evidenceRole, Literal("direct_test")) in provenance
    assert (
        proposition_uri,
        SCI_NS.measurementModel,
        Literal(
            json.dumps(
                {
                    "observed_entity": "observation:obs-1",
                    "latent_construct": "latent:cell-state",
                    "measurement_relation": "proxy for cell-state",
                    "rationale": "frontmatter proxy path",
                    "known_failure_modes": ["batch effect"],
                    "substitutable_with": ["observation:obs-2"],
                }
            ),
        ),
    ) in provenance
    packet_literal = next(provenance.objects(proposition_uri, SCI_NS.rivalModelPacket), None)
    assert packet_literal is not None
    packet_data = json.loads(str(packet_literal))
    assert packet_data["packet_id"] == "packet:demo"
    assert packet_data["target_hypothesis"] == "hypothesis:h01"
    assert packet_data["current_working_model"] == "model:a"
    assert packet_data["alternative_models"] == ["model:b"]
    assert packet_data["shared_observables"] == ["obs:a"]
    assert packet_data["discriminating_predictions"] == ["pred:1"]
    assert packet_data["adjudication_rule"] == "choose the simplest model"


def test_export_graph_payload_includes_layered_claim_metadata_for_claim_backed_edge(tmp_path: Path) -> None:
    graph_path = _write_graph()
    add_concept(graph_path, "Drug", concept_type="sci:Variable", ontology_id=None, source="paper:drug")
    add_concept(graph_path, "Recovery", concept_type="sci:Variable", ontology_id=None, source="paper:recovery")
    add_proposition(
        graph_path,
        text="Drug treatment improves recovery time",
        source="article:layered-claims",
        proposition_id="drug_claim",
        subject="concept/drug",
        predicate="scic:causes",
        obj="concept/recovery",
        claim_layer=ClaimLayer.MECHANISTIC_NARRATIVE,
        identification_strength=IdentificationStrength.INTERVENTIONAL,
        proxy_directness=ProxyDirectness.INDIRECT,
        supports_scope=SupportScope.CROSS_HYPOTHESIS,
        independence_group="batch-2",
        evidence_role=EvidenceRole.MODEL_CRITICISM,
        measurement_model=MeasurementModel(
            observed_entity="observation:obs-2",
            latent_construct="latent:recovery-state",
            measurement_relation="proxy for recovery-state",
            rationale="capture the latent recovery phenotype",
            known_failure_modes=["batch effect"],
            substitutable_with=["observation:obs-3"],
        ),
        rival_model_packet=RivalModelPacket(
            packet_id="packet:drug-vs-null",
            target_hypothesis="hypothesis:h1",
            current_working_model="model:drug",
            alternative_models=["model:null"],
            shared_observables=["obs:recovery"],
            discriminating_predictions=["pred:drug-accelerates"],
            adjudication_rule="prefer the model with fewer unsupported assumptions",
        ),
    )
    add_edge(
        graph_path,
        "concept/drug",
        "scic:causes",
        "concept/recovery",
        "graph/causal",
        claim_refs=["proposition:drug_claim"],
    )

    payload = export_graph_payload(graph_path, overlays=["evidence"])
    edge_id = next(edge.id for edge in payload.edges if edge.claim_ids == ["http://example.org/project/proposition/drug_claim"])
    claim = payload.overlays.evidence["edges"][edge_id]["claims"][0]

    assert claim["claim_layer"] == "mechanistic_narrative"
    assert claim["identification_strength"] == "interventional"
    assert claim["proxy_directness"] == "indirect"
    assert claim["supports_scope"] == "cross_hypothesis"
    assert claim["independence_group"] == "batch-2"
    assert claim["evidence_role"] == "model_criticism"
    assert claim["measurement_model"]["observed_entity"] == "observation:obs-2"
    assert claim["rival_model_packet"]["packet_id"] == "packet:drug-vs-null"


def test_materialize_graph_without_layered_claim_metadata_keeps_legacy_shape(tmp_path: Path) -> None:
    project = _write_project(tmp_path / "legacy", with_layered_metadata=False)

    trig_path = materialize_graph(project)
    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])
    proposition_uri = PROJECT_NS["proposition/p01-layered"]

    assert (proposition_uri, PROV.wasDerivedFrom, None) in provenance
    assert (proposition_uri, SCI_NS.claimLayer, None) not in provenance
    assert (proposition_uri, SCI_NS.measurementModel, None) not in provenance
    assert (proposition_uri, SCI_NS.rivalModelPacket, None) not in provenance
