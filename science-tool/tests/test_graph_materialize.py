from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

from click.testing import CliRunner
from rdflib import Dataset, Literal, Namespace
from rdflib.namespace import RDF, SKOS, XSD

from science_tool.cli import main
from science_tool.graph.materialize import materialize_graph
from science_tool.graph.store import diff_graph_inputs

PROJECT_NS = Namespace("http://example.org/project/")
SCI = Namespace("http://example.org/science/vocab/")
PROV = Namespace("http://www.w3.org/ns/prov#")
SCHEMA = Namespace("https://schema.org/")
CITO = Namespace("http://purl.org/spar/cito/")


def _write_demo_project(
    project_root: Path,
    *,
    include_missing_relation: bool = False,
    include_alias_collision: bool = False,
    include_case_distinct_urls: bool = False,
) -> None:
    project_root.mkdir(parents=True)
    (project_root / "science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "ontologies: [biology]",
                "knowledge_profiles:",
                "  local: local",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (project_root / "specs" / "hypotheses").mkdir(parents=True)
    (project_root / "doc" / "questions").mkdir(parents=True)
    (project_root / "tasks").mkdir(parents=True)

    related = '["question:q01-demo", "GO:0008150"]'
    if include_missing_relation:
        related = '["question:q01-demo", "question:q99-missing", "GO:0008150"]'
    if include_case_distinct_urls:
        related = '["question:q01-demo", "https://Example.org/MixedCase", "https://example.org/mixedcase"]'

    (project_root / "specs" / "hypotheses" / "h01-demo.md").write_text(
        "\n".join(
            [
                "---",
                'id: "hypothesis:h01-demo"',
                'type: "hypothesis"',
                'title: "Demo hypothesis"',
                'status: "proposed"',
                "ontology_terms: [GO:0008150]",
                "source_refs: []",
                f"related: {related}",
                'created: "2026-03-12"',
                'updated: "2026-03-12"',
                "---",
                "",
                "Demo hypothesis body.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    (project_root / "doc" / "questions" / "q01-demo.md").write_text(
        "\n".join(
            [
                "---",
                'id: "question:q01-demo"',
                'type: "question"',
                'title: "Demo question"',
                'status: "open"',
                "ontology_terms: []",
                'source_refs: ["hypothesis:h01-demo"]',
                'related: ["task:t001"]',
                'created: "2026-03-12"',
                'updated: "2026-03-12"',
                "---",
                "",
                "Demo question body.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    if include_alias_collision:
        (project_root / "specs" / "hypotheses" / "h02-demo.md").write_text(
            "\n".join(
                [
                    "---",
                    'id: "hypothesis:h02-demo"',
                    'type: "hypothesis"',
                    'title: "Conflicting alias hypothesis"',
                    "aliases: [H01]",
                    'status: "proposed"',
                    "ontology_terms: []",
                    "source_refs: []",
                    "related: []",
                    'created: "2026-03-12"',
                    'updated: "2026-03-12"',
                    "---",
                    "",
                    "Second hypothesis body.",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    (project_root / "tasks" / "active.md").write_text(
        "\n".join(
            [
                "## [t001] Validate H01",
                "- type: research",
                "- priority: P1",
                "- status: active",
                "- related: [hypothesis:h01-demo, question:q01-demo]",
                "- blocked-by: [task:t002]",
                "- created: 2026-03-12",
                "",
                "Do it.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    (project_root / "tasks" / "done").mkdir(parents=True)
    (project_root / "tasks" / "done" / "2026-03.md").write_text(
        "\n".join(
            [
                "## [t002] Gather evidence",
                "- type: research",
                "- priority: P2",
                "- status: done",
                "- related: [hypothesis:h01-demo]",
                "- created: 2026-03-11",
                "- completed: 2026-03-12",
                "",
                "Done.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_materialize_graph_includes_task_nodes_and_canonical_links(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    task_uri = PROJECT_NS["task/t001"]
    hypothesis_uri = PROJECT_NS["hypothesis/h01-demo"]
    question_uri = PROJECT_NS["question/q01-demo"]

    assert (task_uri, RDF.type, SCI.Task) in knowledge
    assert (task_uri, SCHEMA.identifier, None) in knowledge
    assert (task_uri, SKOS.prefLabel, None) in knowledge
    assert (task_uri, SCI.profile, Literal("core")) in knowledge
    assert (hypothesis_uri, SCI.profile, Literal("core")) in knowledge
    assert (task_uri, SCI.tests, hypothesis_uri) in knowledge
    assert (task_uri, SCI.tests, question_uri) in knowledge


def test_materialize_graph_writes_bridge_layer_for_external_terms(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    bridge = dataset.graph(PROJECT_NS["graph/bridge"])
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    hypothesis_uri = PROJECT_NS["hypothesis/h01-demo"]
    question_uri = PROJECT_NS["question/q01-demo"]
    external_uri = PROJECT_NS["external/go/0008150"]

    assert (hypothesis_uri, SCI.about, external_uri) in bridge
    assert (external_uri, RDF.type, SCI.ExternalTerm) in bridge
    assert (external_uri, SCHEMA.identifier, None) in bridge
    assert (hypothesis_uri, PROV.wasDerivedFrom, None) in provenance
    assert (question_uri, PROV.wasDerivedFrom, hypothesis_uri) in provenance


def test_materialize_graph_uses_configured_local_profile_sources(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    (project / "science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "ontologies: [biology]",
                "knowledge_profiles:",
                "  local: lab_local",
                "",
            ]
        ),
        encoding="utf-8",
    )
    local_sources = project / "knowledge" / "sources" / "lab_local"
    local_sources.mkdir(parents=True)
    (local_sources / "entities.yaml").write_text(
        "\n".join(
            [
                "entities:",
                "  - canonical_id: topic:evaluation",
                "    kind: topic",
                "    title: Evaluation",
                "    related: [question:q01-demo]",
                "",
            ]
        ),
        encoding="utf-8",
    )

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    topic_uri = PROJECT_NS["topic/evaluation"]
    question_uri = PROJECT_NS["question/q01-demo"]

    assert (topic_uri, RDF.type, SCI.Topic) in knowledge
    assert (topic_uri, SCI.profile, Literal("lab_local")) in knowledge
    assert (topic_uri, SKOS.related, question_uri) in knowledge


def test_materialize_graph_materializes_structured_entity_confidence_in_provenance(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    local_sources = project / "knowledge" / "sources" / "local"
    local_sources.mkdir(parents=True)
    (local_sources / "entities.yaml").write_text(
        "\n".join(
            [
                "entities:",
                "  - canonical_id: hypothesis:h02-confidence",
                "    kind: hypothesis",
                "    title: Confidence-backed hypothesis",
                "    confidence: 0.7",
                "    domain: structural-biology",
                "",
            ]
        ),
        encoding="utf-8",
    )

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    hypothesis_uri = PROJECT_NS["hypothesis/h02-confidence"]

    assert (hypothesis_uri, SCI.domain, Literal("structural-biology")) in knowledge
    assert (hypothesis_uri, SCI.confidence, Literal("0.7", datatype=XSD.decimal)) in provenance


def test_materialize_graph_applies_structured_relations_with_internal_targets(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    local_sources = project / "knowledge" / "sources" / "local"
    local_sources.mkdir(parents=True)
    (local_sources / "entities.yaml").write_text(
        "\n".join(
            [
                "entities:",
                "  - canonical_id: paper:legatiuk2021",
                "    kind: paper",
                "    title: Legatiuk 2021",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (local_sources / "relations.yaml").write_text(
        "\n".join(
            [
                "relations:",
                "  - subject: paper:legatiuk2021",
                "    predicate: cito:discusses",
                "    object: question:q01-demo",
                "",
            ]
        ),
        encoding="utf-8",
    )

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    paper_uri = PROJECT_NS["paper/legatiuk2021"]
    question_uri = PROJECT_NS["question/q01-demo"]

    assert (paper_uri, RDF.type, SCI.Paper) in knowledge
    assert (paper_uri, CITO.discusses, question_uri) in knowledge


def test_materialize_graph_applies_structured_relations_with_external_targets(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    local_sources = project / "knowledge" / "sources" / "local"
    local_sources.mkdir(parents=True)
    (local_sources / "entities.yaml").write_text(
        "\n".join(
            [
                "entities:",
                "  - canonical_id: paper:legatiuk2021",
                "    kind: paper",
                "    title: Legatiuk 2021",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (local_sources / "relations.yaml").write_text(
        "\n".join(
            [
                "relations:",
                "  - subject: paper:legatiuk2021",
                "    predicate: cito:discusses",
                "    object: GO:0008150",
                "",
            ]
        ),
        encoding="utf-8",
    )

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    bridge = dataset.graph(PROJECT_NS["graph/bridge"])

    paper_uri = PROJECT_NS["paper/legatiuk2021"]
    external_uri = PROJECT_NS["external/go/0008150"]

    assert (paper_uri, CITO.discusses, external_uri) in knowledge
    assert (external_uri, RDF.type, SCI.ExternalTerm) in bridge
    assert (external_uri, SCHEMA.identifier, Literal("GO:0008150")) in bridge


def test_materialize_graph_accepts_bare_ontology_terms(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    hypothesis_path = project / "specs" / "hypotheses" / "h01-demo.md"
    hypothesis_path.write_text(
        hypothesis_path.read_text(encoding="utf-8").replace(
            "ontology_terms: [GO:0008150]", "ontology_terms: [functor]"
        ),
        encoding="utf-8",
    )

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    bridge = dataset.graph(PROJECT_NS["graph/bridge"])

    hypothesis_uri = PROJECT_NS["hypothesis/h01-demo"]
    external_uri = PROJECT_NS["external/term/functor"]

    assert (hypothesis_uri, SCI.about, external_uri) in bridge
    assert (external_uri, SCHEMA.identifier, Literal("functor")) in bridge


def test_materialize_graph_emits_skos_exact_match_for_same_as_external(tmp_path: Path) -> None:
    """`same_as: [UniProtKB:Q5T6S3]` on a topic emits skos:exactMatch (not sci:about).

    This is the identity assertion that distinguishes 'this topic IS the PHF19 protein'
    from 'this topic IS ABOUT the PHF19 protein' (the latter is what ontology_terms emits).
    """
    project = tmp_path / "demo"
    _write_demo_project(project)
    (project / "doc" / "topics").mkdir(parents=True)
    (project / "doc" / "topics" / "phf19.md").write_text(
        "\n".join(
            [
                "---",
                'id: "topic:phf19"',
                'type: "topic"',
                'title: "PHF19 (PHD finger protein 19)"',
                "ontology_terms: []",
                "source_refs: []",
                "related: []",
                "same_as:",
                '  - "UniProtKB:Q5T6S3"',
                '  - "HGNC:30074"',
                'created: "2026-04-19"',
                'updated: "2026-04-19"',
                "---",
                "",
                "PHF19 is a Polycomb component.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    bridge = dataset.graph(PROJECT_NS["graph/bridge"])

    topic_uri = PROJECT_NS["topic/phf19"]
    uniprot_uri = PROJECT_NS["external/uniprotkb/Q5T6S3"]
    hgnc_uri = PROJECT_NS["external/hgnc/30074"]

    # skos:exactMatch (identity), not sci:about (association)
    assert (topic_uri, SKOS.exactMatch, uniprot_uri) in bridge
    assert (topic_uri, SKOS.exactMatch, hgnc_uri) in bridge
    # Same-as targets must NOT also be linked via sci:about
    assert (topic_uri, SCI.about, uniprot_uri) not in bridge
    # External terms are still registered as ExternalTerm nodes
    assert (uniprot_uri, RDF.type, SCI.ExternalTerm) in bridge
    assert (hgnc_uri, RDF.type, SCI.ExternalTerm) in bridge


def test_materialize_graph_materializes_model_parameter_bindings(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    local_sources = project / "knowledge" / "sources" / "local"
    local_sources.mkdir(parents=True)
    (local_sources / "models.yaml").write_text(
        "\n".join(
            [
                "models:",
                "  - canonical_id: model:navier-stokes",
                '    title: "Navier-Stokes equations"',
                "    profile: local",
                "    source_path: knowledge/sources/local/models.yaml",
                "    domain: fluid-dynamics",
                "    source_refs: [hypothesis:h01-demo]",
                "    related: [question:q01-demo]",
                "    relations:",
                "      - predicate: sci:approximates",
                "        target: model:stokes",
                "  - canonical_id: model:stokes",
                '    title: "Stokes equations"',
                "    profile: local",
                "    source_path: knowledge/sources/local/models.yaml",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (local_sources / "parameters.yaml").write_text(
        "\n".join(
            [
                "parameters:",
                "  - canonical_id: parameter:kinematic-viscosity",
                '    title: "Kinematic viscosity"',
                "    symbol: nu",
                "    profile: local",
                "    source_path: knowledge/sources/local/parameters.yaml",
                "    units: m^2/s",
                "    quantity_group: velocity",
                "    source_refs: [hypothesis:h01-demo]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (local_sources / "bindings.yaml").write_text(
        "\n".join(
            [
                "bindings:",
                "  - model: model:navier-stokes",
                "    parameter: parameter:kinematic-viscosity",
                "    source_path: knowledge/sources/local/bindings.yaml",
                "    symbol: nu",
                "    role: viscosity",
                "    confidence: 1.0",
                "    match_tier: canonical",
                "",
            ]
        ),
        encoding="utf-8",
    )

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    model_uri = PROJECT_NS["model/navier-stokes"]
    parameter_uri = PROJECT_NS["parameter/kinematic-viscosity"]

    assert (model_uri, RDF.type, SCI.Model) in knowledge
    assert (model_uri, SCI.domain, Literal("fluid-dynamics")) in knowledge
    assert (parameter_uri, RDF.type, SCI.CanonicalParameter) in knowledge
    assert (model_uri, SCI.approximates, PROJECT_NS["model/stokes"]) in knowledge
    assert (model_uri, SCI.hasParameter, parameter_uri) in knowledge
    assert (model_uri, PROV.wasDerivedFrom, PROJECT_NS["hypothesis/h01-demo"]) in provenance
    assert (parameter_uri, PROV.wasDerivedFrom, PROJECT_NS["hypothesis/h01-demo"]) in provenance
    assert (None, RDF.type, SCI.ParameterBinding) in provenance
    assert (None, SCI.model, model_uri) in provenance
    assert (None, SCI.parameter, parameter_uri) in provenance
    assert (None, SCI.matchTier, Literal("canonical")) in provenance


def test_materialize_graph_preserves_case_distinct_external_urls(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project, include_case_distinct_urls=True)

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    bridge = dataset.graph(PROJECT_NS["graph/bridge"])

    url_nodes = {
        str(subject)
        for subject, _, _ in bridge.triples((None, RDF.type, SCI.ExternalTerm))
        if "/external/url/" in str(subject)
    }
    assert url_nodes == {
        "http://example.org/project/external/url/https%3A%2F%2FExample.org%2FMixedCase",
        "http://example.org/project/external/url/https%3A%2F%2Fexample.org%2Fmixedcase",
    }


def test_graph_audit_reports_unresolved_references(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project, include_missing_relation=True)

    runner = CliRunner()
    result = runner.invoke(main, ["graph", "audit", "--project-root", str(project), "--format", "json"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert any(
        row["check"] == "unresolved_reference" and row["target"] == "question:q99-missing" for row in payload["rows"]
    )


def test_graph_audit_reports_ambiguous_aliases(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project, include_alias_collision=True)

    runner = CliRunner()
    result = runner.invoke(main, ["graph", "audit", "--project-root", str(project), "--format", "json"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert any(row["check"] == "ambiguous_alias" and row["target"] == "H01" for row in payload["rows"])


def test_graph_build_materializes_project_graph(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)

    runner = CliRunner()
    result = runner.invoke(main, ["graph", "build", "--project-root", str(project)])

    assert result.exit_code == 0


def test_materialize_graph_is_deterministic_for_identical_inputs(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)

    first_path = materialize_graph(project)
    first_text = first_path.read_text(encoding="utf-8")

    time.sleep(1.1)
    second_path = materialize_graph(project)
    second_text = second_path.read_text(encoding="utf-8")

    assert second_path == first_path
    assert second_text == first_text
    trig_path = project / "knowledge" / "graph.trig"
    assert trig_path.exists()
    assert diff_graph_inputs(trig_path, "hash") == []


def test_graph_build_is_deterministic_across_processes(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)

    script = textwrap.dedent(
        """
        import hashlib
        from pathlib import Path

        from science_tool.graph.materialize import materialize_graph

        trig_path = materialize_graph(Path(r"{project_root}"))
        print(hashlib.sha256(trig_path.read_bytes()).hexdigest())
        """
    ).format(project_root=project)

    first_env = os.environ | {"PYTHONHASHSEED": "1"}
    second_env = os.environ | {"PYTHONHASHSEED": "2"}

    first = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        env=first_env,
    )
    second = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        env=second_env,
    )

    assert second.stdout == first.stdout


def test_graph_build_fails_cleanly_on_unresolved_references(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project, include_missing_relation=True)

    runner = CliRunner()
    result = runner.invoke(main, ["graph", "build", "--project-root", str(project)])

    assert result.exit_code != 0
    assert "unresolved references" in result.output.lower()


def test_source_entity_has_no_tags_field():
    """After unification, SourceEntity should not have a tags field."""
    from science_tool.graph.sources import SourceEntity

    assert "tags" not in SourceEntity.model_fields


def test_known_kinds_includes_shared() -> None:
    from science_model.profiles.schema import EntityKind, ProfileManifest

    from science_tool.graph.sources import known_kinds

    shared = ProfileManifest(
        name="shared",
        imports=["core"],
        strictness="curated",
        entity_kinds=[
            EntityKind(
                name="protein-complex",
                canonical_prefix="protein-complex",
                layer="layer/shared",
                description="Shared kind.",
            ),
        ],
        relation_kinds=[],
    )
    kinds = known_kinds(extra_profiles=[shared])
    assert "protein-complex" in kinds
    assert "hypothesis" in kinds  # core kinds still present
