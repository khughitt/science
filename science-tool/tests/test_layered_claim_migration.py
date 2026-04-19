from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from rdflib import Dataset, Literal, Namespace
from rdflib.namespace import PROV, RDF
from pydantic import ValidationError

from science_model.reasoning import (
    ClaimLayer,
    EvidenceRole,
    IdentificationStrength,
    MeasurementModel,
    ProxyDirectness,
    RivalModelPacket,
    SupportScope,
)
from science_tool.graph import sources as sources_module
from science_tool.graph.migrate import build_layered_claim_migration_report
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


def _write_scan_project(root: Path, propositions: list[dict[str, object]]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "science.yaml").write_text(
        "\n".join(
            [
                "name: layered-claims-scan-demo",
                "knowledge_profiles:",
                "  local: local",
                "",
            ]
        ),
        encoding="utf-8",
    )

    prop_dir = root / "specs" / "propositions"
    prop_dir.mkdir(parents=True, exist_ok=True)
    for proposal in propositions:
        proposition_id = str(proposal["id"])
        title = str(proposal["title"])
        body = str(proposal["body"])
        extra_frontmatter = proposal.get("frontmatter")
        lines = [
            "---",
            f'id: "{proposition_id}"',
            'type: "proposition"',
            f'title: "{title}"',
            'status: "draft"',
            "related: []",
            "source_refs: []",
        ]
        if isinstance(extra_frontmatter, dict):
            for key, value in extra_frontmatter.items():
                if isinstance(value, str):
                    lines.append(f'{key}: "{value}"')
                elif isinstance(value, list):
                    rendered = ", ".join(f'"{item}"' for item in value)
                    lines.append(f"{key}: [{rendered}]")
                elif isinstance(value, dict):
                    lines.append(f"{key}:")
                    for nested_key, nested_value in value.items():
                        if isinstance(nested_value, str):
                            lines.append(f'  {nested_key}: "{nested_value}"')
                        elif isinstance(nested_value, list):
                            rendered = ", ".join(f'"{item}"' for item in nested_value)
                            lines.append(f"  {nested_key}: [{rendered}]")
                else:
                    lines.append(f"{key}: {value}")
        lines.extend(
            [
                'created: "2026-04-15"',
                "---",
                "",
                body,
                "",
            ]
        )
        file_name = proposition_id.split(":", 1)[1]
        (prop_dir / f"{file_name}.md").write_text("\n".join(lines), encoding="utf-8")
    return root


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


class _FakeTypedRecord:
    def __init__(self, *, canonical_id: str, title: str, profile: str, source_path: str) -> None:
        self.canonical_id = canonical_id
        self.title = title
        self.profile = profile
        self.source_path = source_path
        self.symbol = "symbol:demo"
        self.units = None
        self.quantity_group = None
        self.domain = "biology"
        self.aliases = ["alias-1"]
        self.source_refs = ["source:1"]
        self.related = ["related:1"]
        self.ontology_terms = ["term:1"]
        self.relations: list[dict[str, str]] = []

    def model_dump(self, mode: str = "json") -> dict[str, object]:
        return {
            "canonical_id": self.canonical_id,
            "title": self.title,
            "profile": self.profile,
            "source_path": self.source_path,
            "domain": self.domain,
            "aliases": self.aliases,
            "source_refs": self.source_refs,
            "related": self.related,
            "ontology_terms": self.ontology_terms,
            "claim_layer": "causal_effect",
            "identification_strength": "interventional",
            "proxy_directness": "indirect",
            "supports_scope": "project_wide",
            "independence_group": "batch-9",
            "evidence_role": "direct_test",
            "measurement_model": {
                "observed_entity": "observation:obs-9",
                "latent_construct": "latent:state",
            },
            "rival_model_packet": {
                "packet_id": "packet:9",
                "current_working_model": "model:working",
            },
        }


def test_model_and_parameter_source_loading_ignores_layered_claim_metadata_from_typed_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_model = _FakeTypedRecord(
        canonical_id="model:demo",
        title="Model Demo",
        profile="local",
        source_path="models.yaml",
    )
    fake_parameter = _FakeTypedRecord(
        canonical_id="parameter:demo",
        title="Parameter Demo",
        profile="local",
        source_path="parameters.yaml",
    )

    def fake_load_typed_records(
        project_root: Path,
        *,
        local_profile: str,
        file_name: str,
        root_key: str,
        model: type[object],
    ) -> list[object]:
        if file_name == "models.yaml":
            return [fake_model]
        if file_name == "parameters.yaml":
            return [fake_parameter]
        return []

    monkeypatch.setattr(sources_module, "_load_typed_records", fake_load_typed_records)

    model_entities, _ = sources_module._load_model_sources(tmp_path / "project", local_profile="local")
    parameter_entities, _ = sources_module._load_parameter_sources(tmp_path / "project", local_profile="local")

    for entity in model_entities + parameter_entities:
        assert entity.claim_layer is None
        assert entity.identification_strength is None
        assert entity.proxy_directness is None
        assert entity.supports_scope is None
        assert entity.independence_group is None
        assert entity.evidence_role is None
        assert entity.measurement_model is None
        assert entity.rival_model_packet is None


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
        source="paper:layered-claims",
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


@pytest.mark.parametrize(
    ("field_name", "payload"),
    [
        ("measurement_model", {"latent_construct": "latent:state"}),
        ("rival_model_packet", {"current_working_model": "model:working"}),
    ],
)
def test_add_proposition_validates_raw_reasoning_metadata_dicts(
    tmp_path: Path,
    field_name: str,
    payload: dict[str, object],
) -> None:
    graph_path = _write_graph()

    with pytest.raises(ValidationError):
        add_proposition(
            graph_path,
            text="Raw dict validation should reject incomplete metadata",
            source="paper:layered-claims",
            proposition_id="raw-dict-validation",
            **{field_name: payload},
        )


def test_materialize_graph_without_layered_claim_metadata_keeps_legacy_shape(tmp_path: Path) -> None:
    project = _write_project(tmp_path / "legacy", with_layered_metadata=False)

    first_trig_path = materialize_graph(project)
    first_dataset = Dataset()
    first_dataset.parse(source=str(first_trig_path), format="trig")
    first_snapshot = {
        (str(subject), str(predicate), str(obj), str(graph))
        for subject, predicate, obj, graph in first_dataset.quads((None, None, None, None))
    }

    second_trig_path = materialize_graph(project)
    second_dataset = Dataset()
    second_dataset.parse(source=str(second_trig_path), format="trig")
    second_snapshot = {
        (str(subject), str(predicate), str(obj), str(graph))
        for subject, predicate, obj, graph in second_dataset.quads((None, None, None, None))
    }
    provenance = second_dataset.graph(PROJECT_NS["graph/provenance"])
    proposition_uri = PROJECT_NS["proposition/p01-layered"]

    assert first_snapshot == second_snapshot
    assert (proposition_uri, PROV.wasDerivedFrom, None) in provenance
    assert (proposition_uri, SCI_NS.claimLayer, None) not in provenance
    assert (proposition_uri, SCI_NS.measurementModel, None) not in provenance
    assert (proposition_uri, SCI_NS.rivalModelPacket, None) not in provenance


def test_layered_claim_migration_report_infers_safe_fields(tmp_path: Path) -> None:
    project = _write_scan_project(
        tmp_path / "scan-project",
        [
            {
                "id": "proposition:p01",
                "title": "Safe inference",
                "body": "A CRISPR knockout benchmark defines the model structure for this comparison.",
            }
        ],
    )

    report = build_layered_claim_migration_report(project)
    row = report["rows"][0]

    assert row["inferred_identification_strength"] == "interventional"
    assert row["inferred_claim_layer"] == "structural_claim"
    assert row["todos"] == []
    assert row["warnings"] == []


def test_layered_claim_migration_report_emits_todo_for_ambiguous_proposition(tmp_path: Path) -> None:
    project = _write_scan_project(
        tmp_path / "scan-project",
        [
            {
                "id": "proposition:p02",
                "title": "Ambiguous proposition",
                "body": "This result is interesting but not yet classified.",
            }
        ],
    )

    report = build_layered_claim_migration_report(project)
    row = report["rows"][0]

    assert row["inferred_claim_layer"] is None
    assert row["inferred_identification_strength"] is None
    assert row["todos"]
    assert any("TODO" in todo for todo in row["todos"])


def test_layered_claim_migration_report_warns_on_proxy_overclaim(tmp_path: Path) -> None:
    project = _write_scan_project(
        tmp_path / "scan-project",
        [
            {
                "id": "proposition:p03",
                "title": "Proxy proposition",
                "body": "This proxy tracks the latent cell state but has no explicit measurement model.",
            }
        ],
    )

    report = build_layered_claim_migration_report(project)
    row = report["rows"][0]

    assert row["warnings"]
    assert any("proxy" in warning.lower() for warning in row["warnings"])
    assert any("measurement" in warning.lower() for warning in row["warnings"])
    assert row["todos"]


def test_layered_claim_migration_report_warns_on_unsupported_mechanistic_claim(tmp_path: Path) -> None:
    project = _write_scan_project(
        tmp_path / "scan-project",
        [
            {
                "id": "proposition:p04",
                "title": "Mechanistic claim",
                "body": "PHF19 activates PRC2 and IFN signaling through a mechanistic cascade.",
            }
        ],
    )

    report = build_layered_claim_migration_report(project)
    row = report["rows"][0]

    assert row["warnings"]
    assert any("mechanistic" in warning.lower() for warning in row["warnings"])
    assert row["todos"]


def test_layered_claim_migration_report_does_not_require_identification_for_authored_structural_claim(
    tmp_path: Path,
) -> None:
    project = _write_scan_project(
        tmp_path / "scan-project",
        [
            {
                "id": "proposition:p04b",
                "title": "Structural proposition",
                "body": "This benchmark defines the model structure for the comparison.",
                "frontmatter": {
                    "claim_layer": "structural_claim",
                },
            }
        ],
    )

    report = build_layered_claim_migration_report(project)
    row = report["rows"][0]

    assert row["authored_claim_layer"] == "structural_claim"
    assert row["todos"] == []


def test_layered_claim_migration_report_runtime_guard(tmp_path: Path) -> None:
    propositions = [
        {
            "id": f"proposition:p{i:03d}",
            "title": f"Prop {i}",
            "body": "This is a plain empirical association description for a synthetic corpus.",
        }
        for i in range(120)
    ]
    project = _write_scan_project(tmp_path / "scan-project", propositions)

    start = time.perf_counter()
    report = build_layered_claim_migration_report(project)
    elapsed = time.perf_counter() - start

    assert elapsed < 30
    assert report["summary"]["proposition_count"] == 120


def test_graph_migrate_command_includes_layered_claim_scan_payload(tmp_path: Path) -> None:
    from click.testing import CliRunner

    from science_tool.cli import main

    project = _write_scan_project(
        tmp_path / "scan-project",
        [
            {
                "id": "proposition:p05",
                "title": "Observed association",
                "body": "This empirical association links the observed marker to stage.",
            }
        ],
    )

    runner = CliRunner()
    result = runner.invoke(main, ["graph", "migrate", "--project-root", str(project), "--format", "json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)

    assert "layered_claim_migration" in payload
    assert payload["layered_claim_migration"]["summary"]["proposition_count"] == 1
    row = payload["layered_claim_migration"]["rows"][0]
    assert row["proposition"] == "proposition:p05"
    assert row["inferred_identification_strength"] == "observational"
