from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest
from click.testing import CliRunner
from rdflib import Dataset, Literal, Namespace, URIRef
from rdflib.namespace import RDF, SKOS, XSD

from science_tool.cli import main
from science_tool.graph.materialize import materialize_graph
from science_tool.graph.sources import load_project_sources
from science_tool.graph.store import add_hypothesis, diff_graph_inputs

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
    (project_root / "entities" / "hypotheses").mkdir(parents=True)
    (project_root / "entities" / "questions").mkdir(parents=True)
    (project_root / "tasks").mkdir(parents=True)

    related = '["question:q01-demo", "GO:0008150"]'
    if include_missing_relation:
        related = '["question:q01-demo", "question:q99-missing", "GO:0008150"]'
    if include_case_distinct_urls:
        related = '["question:q01-demo", "https://Example.org/MixedCase", "https://example.org/mixedcase"]'

    (project_root / "entities" / "hypotheses" / "h01-demo.md").write_text(
        "\n".join(
            [
                "---",
                'id: "hypothesis:h01-demo"',
                'kind: "hypothesis"',
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

    (project_root / "entities" / "questions" / "q01-demo.md").write_text(
        "\n".join(
            [
                "---",
                'id: "question:q01-demo"',
                'kind: "question"',
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
        (project_root / "entities" / "hypotheses" / "h02-demo.md").write_text(
            "\n".join(
                [
                    "---",
                    'id: "hypothesis:h02-demo"',
                    'kind: "hypothesis"',
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


def _write_minimal_entity(
    path: Path,
    canonical_id: str,
    kind: str,
    title: str,
    extra_frontmatter: list[str] | None = None,
) -> None:
    lines = [
        "---",
        f'id: "{canonical_id}"',
        f'kind: "{kind}"',
        f'title: "{title}"',
        'status: "active"',
        'created: "2026-05-01"',
        'updated: "2026-05-01"',
        "related: []",
        "source_refs: []",
    ]
    if extra_frontmatter:
        lines.extend(extra_frontmatter)
    lines.extend(["---", "", f"{title} body.", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


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


def test_materialize_emits_inquiry_target_from_frontmatter(tmp_path: Path) -> None:
    """A doc-authored inquiry's `target:` frontmatter must materialize as
    sci:target so the target_exists graph audit can resolve it."""
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(
        project / "entities" / "inquiries" / "demo-inquiry.md",
        "inquiry:demo-inquiry",
        "inquiry",
        "Demo inquiry",
        extra_frontmatter=['target: "question:q01-demo"'],
    )

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    inquiry_uri = PROJECT_NS["inquiry/demo-inquiry"]
    question_uri = PROJECT_NS["question/q01-demo"]
    assert (inquiry_uri, SCI.target, question_uri) in knowledge


def test_materialize_emits_scope_triple_for_project_entity(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)

    trig_path = materialize_graph(project)

    text = trig_path.read_text(encoding="utf-8")
    assert 'sci:scope "project"' in text


def test_materialize_with_commons_topic_emits_scope_and_dual_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil

    from science_tool.commons.adapter import CommonsEntityAdapter
    from science_tool.commons.registry import RegistryBuilder
    from science_tool.graph.materialize import _entity_uri
    from science_tool.graph.store import SCI_NS

    fixture_root = Path(__file__).parent / "fixtures" / "commons" / "valid"
    commons_root = tmp_path / "commons"
    shutil.copytree(fixture_root, commons_root)
    RegistryBuilder(commons_root, CommonsEntityAdapter(commons_root)).rebuild()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")

    project = tmp_path / "project"
    project.mkdir()
    (project / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    manifest_path = project / "knowledge" / "sources" / "local" / "manifest.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text("", encoding="utf-8")
    hypothesis_path = project / "entities" / "hypotheses" / "h1.md"
    hypothesis_path.parent.mkdir(parents=True)
    hypothesis_path.write_text(
        """---
id: "hypothesis:h1"
kind: "hypothesis"
title: "H1"
related: ["topic:single-cell-foundation-models"]
---
""",
        encoding="utf-8",
    )
    overlay_path = project / "overlays" / "topics" / "single-cell-foundation-models.md"
    overlay_path.parent.mkdir(parents=True)
    overlay_path.write_text(
        """---
id: "topic:single-cell-foundation-models"
overlay_of: "topic:single-cell-foundation-models"
relevance: "central to this project"
---

## Project Notes
""",
        encoding="utf-8",
    )

    trig_path = materialize_graph(project)

    ds = Dataset()
    ds.parse(source=str(trig_path), format="trig")
    entity_uri = _entity_uri("topic:single-cell-foundation-models")
    scopes = [obj for _, _, obj, _ in ds.quads((entity_uri, SCI_NS.scope, None, None))]
    derived = {obj for _, _, obj, _ in ds.quads((entity_uri, PROV.wasDerivedFrom, None, None))}
    derived_source_identifiers = {
        str(identifier)
        for source in derived
        for _, _, identifier, _ in ds.quads((source, SCHEMA.identifier, None, None))
    }

    assert any(str(scope) == "cross-project" for scope in scopes)
    assert derived_source_identifiers == {
        str(commons_root / "topics" / "single-cell-foundation-models.md"),
        str(overlay_path),
    }


def test_add_entity_emits_two_provenance_triples_when_overlay_path_present() -> None:
    from rdflib import Graph
    from rdflib.namespace import PROV
    from science_model.entities import Entity

    from science_tool.graph.materialize import _add_entity, _entity_uri

    entity = Entity.model_validate(
        {
            "id": "topic:demo",
            "kind": "topic",
            "title": "Demo",
            "project": "demo",
            "ontology_terms": [],
            "related": [],
            "source_refs": [],
            "content_preview": "",
            "file_path": "/abs/path/canonical.md",
        }
    )
    knowledge = Graph()
    provenance = Graph()
    overlay_paths = {"topic:demo": "/abs/path/overlay.md"}
    _add_entity(
        entity=entity,
        knowledge=knowledge,
        provenance=provenance,
        overlay_paths=overlay_paths,
    )
    entity_uri = _entity_uri("topic:demo")
    derived_from_entity = list(provenance.objects(entity_uri, PROV.wasDerivedFrom))
    assert len(derived_from_entity) == 2


def test_add_entity_emits_one_provenance_triple_without_overlay() -> None:
    from rdflib import Graph
    from rdflib.namespace import PROV
    from science_model.entities import Entity

    from science_tool.graph.materialize import _add_entity, _entity_uri

    entity = Entity.model_validate(
        {
            "id": "topic:demo",
            "kind": "topic",
            "title": "Demo",
            "project": "demo",
            "ontology_terms": [],
            "related": [],
            "source_refs": [],
            "content_preview": "",
            "file_path": "/abs/path/canonical.md",
        }
    )
    knowledge = Graph()
    provenance = Graph()
    _add_entity(entity=entity, knowledge=knowledge, provenance=provenance)
    entity_uri = _entity_uri("topic:demo")
    derived_from_entity = list(provenance.objects(entity_uri, PROV.wasDerivedFrom))
    assert len(derived_from_entity) == 1


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


def test_source_refs_with_cross_project_address_still_fails(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    question = project / "entities" / "questions" / "q01-demo.md"
    question.write_text(
        question.read_text(encoding="utf-8").replace(
            'source_refs: ["hypothesis:h01-demo"]',
            'source_refs: ["cbioportal:doc/background/papers/Mina2020.md"]',
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unresolved references"):
        materialize_graph(project)


def test_evidence_refs_with_cross_project_address_materializes_provenance(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    question = project / "entities" / "questions" / "q01-demo.md"
    question.write_text(
        question.read_text(encoding="utf-8").replace(
            'source_refs: ["hypothesis:h01-demo"]',
            "\n".join(
                [
                    'source_refs: ["hypothesis:h01-demo"]',
                    'evidence_refs: ["cbioportal:doc/background/papers/Mina2020.md"]',
                ]
            ),
        ),
        encoding="utf-8",
    )

    trig_path = materialize_graph(project)
    dataset = Dataset()
    dataset.parse(trig_path, format="trig")
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    assert (
        PROJECT_NS["question/q01-demo"],
        PROV.wasDerivedFrom,
        URIRef("cancer://cbioportal/doc/background/papers/Mina2020.md"),
    ) in provenance


def test_evidence_refs_with_local_ref_materializes_provenance(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    question = project / "entities" / "questions" / "q01-demo.md"
    question.write_text(
        question.read_text(encoding="utf-8").replace(
            'source_refs: ["hypothesis:h01-demo"]',
            "\n".join(
                [
                    "source_refs: []",
                    'evidence_refs: ["hypothesis:h01-demo"]',
                ]
            ),
        ),
        encoding="utf-8",
    )

    trig_path = materialize_graph(project)
    dataset = Dataset()
    dataset.parse(trig_path, format="trig")
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    assert (
        PROJECT_NS["question/q01-demo"],
        PROV.wasDerivedFrom,
        PROJECT_NS["hypothesis/h01-demo"],
    ) in provenance


def test_bibliography_source_refs_do_not_materialize_provenance_edges(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    question = project / "entities" / "questions" / "q01-demo.md"
    question.write_text(
        question.read_text(encoding="utf-8").replace(
            'source_refs: ["hypothesis:h01-demo"]',
            'source_refs: ["cite:Smith2024"]',
        ),
        encoding="utf-8",
    )

    trig_path = materialize_graph(project)
    dataset = Dataset()
    dataset.parse(trig_path, format="trig")
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    targets = {str(target) for target in provenance.objects(PROJECT_NS["question/q01-demo"], PROV.wasDerivedFrom)}
    assert str(PROJECT_NS["hypothesis/h01-demo"]) not in targets
    assert all("cite" not in target.lower() for target in targets)


def test_evidence_refs_with_unknown_local_ref_still_fails(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    question = project / "entities" / "questions" / "q01-demo.md"
    question.write_text(
        question.read_text(encoding="utf-8").replace(
            'source_refs: ["hypothesis:h01-demo"]',
            "\n".join(
                [
                    "source_refs: []",
                    'evidence_refs: ["hypothesis:h99-missing"]',
                ]
            ),
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unresolved references"):
        materialize_graph(project)


def test_materialize_graph_allows_tag_refs_in_related_without_emitting_edges(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    hypothesis_path = project / "entities" / "hypotheses" / "h01-demo.md"
    hypothesis_path.write_text(
        hypothesis_path.read_text(encoding="utf-8").replace(
            'related: ["question:q01-demo", "GO:0008150"]',
            'related: ["question:q01-demo", "tag:draft"]',
        ),
        encoding="utf-8",
    )

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    bridge = dataset.graph(PROJECT_NS["graph/bridge"])

    hypothesis_uri = PROJECT_NS["hypothesis/h01-demo"]
    question_uri = PROJECT_NS["question/q01-demo"]
    tag_uri = PROJECT_NS["external/tag/draft"]

    assert (hypothesis_uri, SKOS.related, question_uri) in knowledge
    assert (hypothesis_uri, SCI.about, tag_uri) not in bridge
    assert (tag_uri, RDF.type, SCI.ExternalTerm) not in bridge


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
    # Declare a genuinely project-local kind so the entity defaults to the
    # configured local profile (core kinds always default to profile: core,
    # regardless of which sources dir they live in).
    (local_sources / "manifest.yaml").write_text(
        "\n".join(
            [
                "name: lab_local",
                "imports: []",
                "strictness: typed-extension",
                "entity_kinds:",
                "  - name: lab-note",
                "    canonical_prefix: lab-note",
                "    layer: layer/extension",
                "    description: Project-local lab note.",
                "relation_kinds: []",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _write_minimal_entity(
        project / "entities" / "lab-notes" / "evaluation.md",
        "lab-note:evaluation",
        "lab-note",
        "Evaluation",
        ['related: ["question:q01-demo"]'],
    )

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    note_uri = PROJECT_NS["lab-note/evaluation"]
    question_uri = PROJECT_NS["question/q01-demo"]

    assert (note_uri, RDF.type, SCI.LabNote) in knowledge
    assert (note_uri, SCI.profile, Literal("lab_local")) in knowledge
    assert (note_uri, SKOS.related, question_uri) in knowledge


def test_materialize_graph_uses_kind_for_domain_rdf_class(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(
        project / "entities" / "genes" / "phf19.md",
        "gene:phf19",
        "gene",
        "PHF19",
        ['related: ["question:q01-demo"]'],
    )

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    gene_uri = PROJECT_NS["gene/phf19"]
    question_uri = PROJECT_NS["question/q01-demo"]

    assert (gene_uri, RDF.type, SCI.Gene) in knowledge
    assert (gene_uri, SKOS.related, question_uri) in knowledge


def test_materialize_graph_emits_mechanism_participants_and_propositions(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(
        project / "entities" / "concepts" / "translation.md",
        "concept:translation",
        "concept",
        "Translation",
    )
    _write_minimal_entity(
        project / "entities" / "concepts" / "cell-state.md",
        "concept:cell-state",
        "concept",
        "Cell state",
    )
    _write_minimal_entity(
        project / "entities" / "propositions" / "anti-coupling.md",
        "proposition:anti-coupling",
        "proposition",
        "Translation and cell state move in opposite directions",
    )
    _write_minimal_entity(
        project / "entities" / "mechanisms" / "anti-coupling-axis.md",
        "mechanism:anti-coupling-axis",
        "mechanism",
        "Anti-coupling axis",
        [
            'summary: "Translation and cell-state programs move in opposite directions."',
            "participants: [concept:translation, concept:cell-state]",
            "propositions: [proposition:anti-coupling]",
        ],
    )

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    mechanism_uri = PROJECT_NS["mechanism/anti-coupling-axis"]
    translation_uri = PROJECT_NS["concept/translation"]
    cell_state_uri = PROJECT_NS["concept/cell-state"]
    proposition_uri = PROJECT_NS["proposition/anti-coupling"]

    assert (mechanism_uri, RDF.type, SCI.Mechanism) in knowledge
    assert (
        mechanism_uri,
        SCHEMA.description,
        Literal("Translation and cell-state programs move in opposite directions."),
    ) in knowledge
    assert (mechanism_uri, SCI.hasParticipant, translation_uri) in knowledge
    assert (mechanism_uri, SCI.hasParticipant, cell_state_uri) in knowledge
    assert (mechanism_uri, SCI.hasProposition, proposition_uri) in knowledge


def test_materialize_graph_emits_theme_node_and_related_edges(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    (project / "entities" / "themes").mkdir(parents=True)
    (project / "entities" / "themes" / "transportability.md").write_text(
        "\n".join(
            [
                "---",
                'id: "theme:transportability"',
                'kind: "theme"',
                'title: "Transportability"',
                'status: "active"',
                'theme_kind: "methodological"',
                'theme_scope: "federation"',
                'related: ["question:q01-demo"]',
                "source_refs: []",
                "evidence_refs: []",
                "---",
                "",
                "# Theme: Transportability",
                "",
            ]
        ),
        encoding="utf-8",
    )

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    theme_uri = PROJECT_NS["theme/transportability"]
    question_uri = PROJECT_NS["question/q01-demo"]

    assert (theme_uri, RDF.type, SCI.Theme) in knowledge
    assert (theme_uri, SKOS.prefLabel, Literal("Transportability")) in knowledge
    assert (theme_uri, SCI.profile, Literal("core")) in knowledge
    assert (theme_uri, SKOS.related, question_uri) in knowledge


def test_materialize_graph_uses_kind_for_task_edge_special_case(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(
        project / "entities" / "tasks" / "t100.md",
        "task:t100",
        "task",
        "Follow-up task",
        ['related: ["hypothesis:h01-demo"]'],
    )

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    task_uri = PROJECT_NS["task/t100"]
    hypothesis_uri = PROJECT_NS["hypothesis/h01-demo"]

    assert (task_uri, SCI.tests, hypothesis_uri) in knowledge


def test_materialize_graph_materializes_structured_entity_confidence_in_provenance(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(
        project / "entities" / "hypotheses" / "h02-confidence.md",
        "hypothesis:h02-confidence",
        "hypothesis",
        "Confidence-backed hypothesis",
        ["confidence: 0.7", "domain: structural-biology"],
    )

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    hypothesis_uri = PROJECT_NS["hypothesis/h02-confidence"]

    assert (hypothesis_uri, SCI.domain, Literal("structural-biology")) in knowledge
    assert (hypothesis_uri, SCI.confidence, Literal("0.7", datatype=XSD.decimal)) in provenance


def test_materialize_graph_resolves_cross_kind_slug_reference(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(
        project / "entities" / "concepts" / "treatment-response.md",
        "concept:treatment-response",
        "concept",
        "Treatment response",
    )
    hypothesis_path = project / "entities" / "hypotheses" / "h01-demo.md"
    hypothesis_path.write_text(
        hypothesis_path.read_text(encoding="utf-8").replace(
            'related: ["question:q01-demo", "GO:0008150"]',
            'related: ["topic:treatment-response"]',
        ),
        encoding="utf-8",
    )

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    hypothesis_uri = PROJECT_NS["hypothesis/h01-demo"]
    concept_uri = PROJECT_NS["concept/treatment-response"]

    assert (hypothesis_uri, SKOS.related, concept_uri) in knowledge


def test_materialize_graph_loads_concept_markdown_owner(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(
        project / "entities" / "concepts" / "treatment-response.md",
        "concept:treatment-response",
        "concept",
        "Treatment response",
        ['summary: "Project-local concept"'],
    )
    hypothesis_path = project / "entities" / "hypotheses" / "h01-demo.md"
    hypothesis_path.write_text(
        hypothesis_path.read_text(encoding="utf-8").replace(
            'related: ["question:q01-demo", "GO:0008150"]',
            'related: ["concept:treatment-response"]',
        ),
        encoding="utf-8",
    )

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    hypothesis_uri = PROJECT_NS["hypothesis/h01-demo"]
    concept_uri = PROJECT_NS["concept/treatment-response"]

    assert (concept_uri, RDF.type, SCI.Concept) in knowledge
    assert (hypothesis_uri, SKOS.related, concept_uri) in knowledge


def test_materialize_graph_applies_structured_relations_with_internal_targets(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    local_sources = project / "knowledge" / "sources" / "local"
    local_sources.mkdir(parents=True)
    _write_minimal_entity(
        project / "entities" / "papers" / "legatiuk2021.md",
        "paper:legatiuk2021",
        "paper",
        "Legatiuk 2021",
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


def test_materialize_graph_applies_source_entity_relations(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    interpretations = project / "entities" / "interpretations"
    interpretations.mkdir(parents=True)
    (interpretations / "old.md").write_text(
        "\n".join(
            [
                "---",
                'id: "interpretation:old"',
                'kind: "interpretation"',
                'title: "Old interpretation"',
                'status: "active"',
                'created: "2026-05-01"',
                'updated: "2026-05-01"',
                "related: []",
                "source_refs: []",
                "---",
                "",
                "Old body.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (interpretations / "new.md").write_text(
        "\n".join(
            [
                "---",
                'id: "interpretation:new"',
                'kind: "interpretation"',
                'title: "New interpretation"',
                'status: "active"',
                'created: "2026-05-02"',
                'updated: "2026-05-02"',
                "related: []",
                "source_refs: []",
                "relations:",
                '  - predicate: "sci:amends"',
                '    target: "interpretation:old"',
                "---",
                "",
                "New body.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    assert (PROJECT_NS["interpretation/new"], SCI.amends, PROJECT_NS["interpretation/old"]) in knowledge


def test_materialize_graph_accepts_conclusion_amends_and_supersedes(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(
        project / "entities" / "interpretations" / "old.md",
        "interpretation:old",
        "interpretation",
        "Old interpretation",
    )
    _write_minimal_entity(
        project / "entities" / "interpretations" / "new.md",
        "interpretation:new",
        "interpretation",
        "New interpretation",
        [
            "relations:",
            '  - predicate: "sci:amends"',
            '    target: "interpretation:old"',
            '  - predicate: "sci:supersedes"',
            '    target: "interpretation:old"',
        ],
    )

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    assert (PROJECT_NS["interpretation/new"], SCI.amends, PROJECT_NS["interpretation/old"]) in knowledge
    assert (PROJECT_NS["interpretation/new"], SCI.supersedes, PROJECT_NS["interpretation/old"]) in knowledge


def test_materialize_graph_preserves_workflow_run_supersedes(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(project / "entities" / "runs" / "old.md", "workflow-run:old-run", "workflow-run", "Old run")
    _write_minimal_entity(
        project / "entities" / "runs" / "new.md",
        "workflow-run:new-run",
        "workflow-run",
        "New run",
        [
            "relations:",
            '  - predicate: "sci:supersedes"',
            '    target: "workflow-run:old-run"',
        ],
    )

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    assert (PROJECT_NS["workflow-run/new-run"], SCI.supersedes, PROJECT_NS["workflow-run/old-run"]) in knowledge


def test_materialize_graph_rejects_invalid_supersedes_pair(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(
        project / "entities" / "interpretations" / "new.md",
        "interpretation:new",
        "interpretation",
        "New interpretation",
    )
    _write_minimal_entity(project / "entities" / "runs" / "old.md", "workflow-run:old-run", "workflow-run", "Old run")
    local_sources = project / "knowledge" / "sources" / "local"
    local_sources.mkdir(parents=True)
    (local_sources / "relations.yaml").write_text(
        "\n".join(
            [
                "relations:",
                '  - subject: "interpretation:new"',
                '    predicate: "sci:supersedes"',
                '    object: "workflow-run:old-run"',
                '    source_path: "knowledge/sources/local/relations.yaml"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=r"invalid authored relation endpoint.*interpretation:new.*sci:supersedes.*workflow-run:old-run.*relations.yaml",
    ):
        materialize_graph(project)


def test_materialize_graph_rejects_invalid_amends_pair(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(project / "entities" / "runs" / "old.md", "workflow-run:old-run", "workflow-run", "Old run")
    _write_minimal_entity(
        project / "entities" / "runs" / "new.md",
        "workflow-run:new-run",
        "workflow-run",
        "New run",
        [
            "relations:",
            '  - predicate: "sci:amends"',
            '    target: "workflow-run:old-run"',
        ],
    )

    with pytest.raises(
        ValueError,
        match=r"invalid authored relation endpoint.*workflow-run:new-run.*sci:amends.*workflow-run:old-run.*new.md",
    ):
        materialize_graph(project)


def test_materialize_graph_rejects_self_supersedes(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(
        project / "entities" / "interpretations" / "same.md",
        "interpretation:same",
        "interpretation",
        "Self replacement",
        [
            "relations:",
            '  - predicate: "sci:supersedes"',
            '    target: "interpretation:same"',
        ],
    )

    with pytest.raises(ValueError, match=r"self-referential authored relation.*interpretation:same.*sci:supersedes"):
        materialize_graph(project)


def test_materialize_graph_rejects_amendment_cycle(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(
        project / "entities" / "interpretations" / "a.md",
        "interpretation:a",
        "interpretation",
        "A",
        [
            "relations:",
            '  - predicate: "sci:amends"',
            '    target: "interpretation:b"',
        ],
    )
    _write_minimal_entity(
        project / "entities" / "interpretations" / "b.md",
        "interpretation:b",
        "interpretation",
        "B",
        [
            "relations:",
            '  - predicate: "sci:amends"',
            '    target: "interpretation:a"',
        ],
    )

    with pytest.raises(
        ValueError,
        match=r"cycle in amendment/supersession relations: interpretation:a -> interpretation:b -> interpretation:a",
    ):
        materialize_graph(project)


def test_materialize_graph_rejects_mixed_amends_supersedes_cycle(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(
        project / "entities" / "interpretations" / "a.md",
        "interpretation:a",
        "interpretation",
        "A",
        [
            "relations:",
            '  - predicate: "sci:amends"',
            '    target: "interpretation:b"',
        ],
    )
    _write_minimal_entity(
        project / "entities" / "interpretations" / "b.md",
        "interpretation:b",
        "interpretation",
        "B",
        [
            "relations:",
            '  - predicate: "sci:supersedes"',
            '    target: "interpretation:a"',
        ],
    )

    with pytest.raises(
        ValueError,
        match=r"cycle in amendment/supersession relations: interpretation:a -> interpretation:b -> interpretation:a",
    ):
        materialize_graph(project)


def test_materialize_graph_applies_structured_relations_with_external_targets(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    local_sources = project / "knowledge" / "sources" / "local"
    local_sources.mkdir(parents=True)
    _write_minimal_entity(
        project / "entities" / "papers" / "legatiuk2021.md",
        "paper:legatiuk2021",
        "paper",
        "Legatiuk 2021",
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
    hypothesis_path = project / "entities" / "hypotheses" / "h01-demo.md"
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
    (project / "entities" / "topics").mkdir(parents=True)
    (project / "entities" / "topics" / "phf19.md").write_text(
        "\n".join(
            [
                "---",
                'id: "topic:phf19"',
                'kind: "topic"',
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


def _write_skip_project(project: Path) -> None:
    (project / "science.yaml").write_text(
        "name: skip-demo\nknowledge_profiles: {local: local}\n", encoding="utf-8"
    )
    (project / "entities").mkdir(parents=True)
    (project / "entities" / "audit-note.md").write_text(
        "---\n"
        'id: "audit:a01-some-review"\n'
        'kind: "audit"\n'
        'title: "A review doc"\n'
        "---\n"
        "# Some review\n",
        encoding="utf-8",
    )


def test_load_project_sources_records_unknown_kind_skip(tmp_path: Path) -> None:
    _write_skip_project(tmp_path)
    sources = load_project_sources(tmp_path)
    skips = [s for s in sources.skipped_entities if s.reason == "unknown_entity_kind"]
    assert len(skips) == 1
    assert "audit-note.md" in skips[0].path
    assert skips[0].kind == "audit"


def test_load_project_sources_records_schema_validation_skip(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: skip-demo\nknowledge_profiles: {local: local}\n", encoding="utf-8"
    )
    (tmp_path / "entities" / "hypotheses").mkdir(parents=True)
    # A core-kind doc missing only its identity (no id) is skipped silently today.
    (tmp_path / "entities" / "hypotheses" / "broken.md").write_text(
        "---\n"
        'kind: "hypothesis"\n'
        'title: "Missing id"\n'
        'status: "active"\n'
        "---\n"
        "# Broken\n",
        encoding="utf-8",
    )
    sources = load_project_sources(tmp_path)
    assert any(
        s.reason == "entity_schema_validation_failed" and "broken.md" in s.path
        for s in sources.skipped_entities
    )


def test_graph_audit_surfaces_unknown_entity_kind(tmp_path: Path) -> None:
    _write_skip_project(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["graph", "audit", "--project-root", str(tmp_path), "--format", "json"])
    payload = json.loads(result.output)
    unknown_rows = [row for row in payload["rows"] if row["check"] == "unknown_entity_kind"]
    assert any("audit-note.md" in row["source"] for row in unknown_rows)
    # Surfaced as a warning, not a hard failure, so the build still passes.
    assert all(row["status"] != "fail" for row in unknown_rows)
    assert result.exit_code == 0


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
    """After unification, Entity should not have a tags field."""
    from science_model.entities import Entity

    assert "tags" not in Entity.model_fields


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


def test_source_authored_hypothesis_and_graph_added_hypothesis_do_not_double_count(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: materialize-entities\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    (tmp_path / "entities" / "hypotheses").mkdir(parents=True)
    (tmp_path / "entities" / "hypotheses" / "h01-source.md").write_text(
        "---\n"
        'id: "hypothesis:h01-source"\n'
        'kind: "hypothesis"\n'
        'title: "Source hypothesis"\n'
        'status: "active"\n'
        "---\n"
        "# Hypothesis: Source hypothesis\n",
        encoding="utf-8",
    )

    graph_path = materialize_graph(tmp_path)
    add_hypothesis(
        graph_path=graph_path,
        text="Graph hypothesis",
        hypothesis_id="h02-graph",
        source="source/manual",
    )
    graph_path = materialize_graph(tmp_path)

    dataset = Dataset()
    dataset.parse(source=str(graph_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    source_uri = PROJECT_NS["hypothesis/h01-source"]
    source_type_triples = list(knowledge.triples((source_uri, RDF.type, None)))

    assert len(source_type_triples) == 1


def test_annotation_uri_minter():
    from science_tool.graph.materialize import _annotation_uri

    uri = _annotation_uri("annotation:papers/smith2020.source#a-7f3a")
    assert str(uri).startswith("http://example.org/project/annotation/")
    assert "smith2020.source" in str(uri)
    assert str(uri).endswith("#a-7f3a")


def test_annotation_source_ref_materializes_wasderivedfrom(tmp_path: Path) -> None:
    """A proposition whose source_refs include an `annotation:` ref AND a resolvable
    entity ref produces BOTH prov:wasDerivedFrom triples in the provenance graph."""
    from science_tool.graph.materialize import _annotation_uri

    project = tmp_path / "demo"
    _write_demo_project(project)  # provides the resolvable entity question:q01-demo
    # Write the proposition fixture directly (NOT via _write_minimal_entity, which already
    # emits `source_refs: []` — passing another block would duplicate the YAML key).
    prop_path = project / "entities" / "propositions" / "demo-claim.md"
    prop_path.parent.mkdir(parents=True, exist_ok=True)
    prop_path.write_text(
        "---\n"
        'id: "proposition:demo-claim"\n'
        'kind: "proposition"\n'
        'title: "Demo claim"\n'
        'status: "active"\n'
        'created: "2026-05-01"\n'
        'updated: "2026-05-01"\n'
        "related: []\n"
        "source_refs:\n"
        '  - "annotation:papers/p.source#a-1"\n'
        '  - "question:q01-demo"\n'
        "---\n\nDemo claim body.\n",
        encoding="utf-8",
    )
    trig_path = materialize_graph(project)
    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    prop_uri = PROJECT_NS["proposition/demo-claim"]
    assert (prop_uri, PROV.wasDerivedFrom, _annotation_uri("annotation:papers/p.source#a-1")) in provenance
    # the resolvable entity ref still materializes via the existing path (paper:<id> behaves identically)
    assert (prop_uri, PROV.wasDerivedFrom, PROJECT_NS["question/q01-demo"]) in provenance
