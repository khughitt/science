from pathlib import Path

import pytest
from pydantic import ValidationError

from science_model.entities import EntityType, EvidenceLineEntity, MechanismEntity
from science_model.frontmatter import (
    PROJECT_CONFIG_FILENAME,
    nearest_project_root,
    parse_entity_file,
    parse_frontmatter,
    project_config_path,
)
from science_model.identity import EntityScope, ExternalId
from science_model.reasoning import DisputeScope, EvidenceRole, EvidenceStance, EvidenceStrength, IndependenceTag


def test_nearest_project_root_finds_ancestor(tmp_path: Path):
    (tmp_path / "science.yaml").write_text("id: p\n", encoding="utf-8")
    nested = tmp_path / "entities" / "hypotheses"
    nested.mkdir(parents=True)
    assert nearest_project_root(nested) == tmp_path


def test_nearest_project_root_returns_none_when_absent(tmp_path: Path):
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert nearest_project_root(nested) is None


def test_project_config_filename_value():
    assert PROJECT_CONFIG_FILENAME == "science.yaml"


def test_project_config_path_appends_filename():
    root = Path("/tmp/some/project")
    assert project_config_path(root) == root / "science.yaml"


def test_project_config_path_is_a_pure_join():
    # No expanduser, no resolve, no filesystem access.
    root = Path("~/rel/proj")
    assert project_config_path(root) == root / "science.yaml"


def test_parse_frontmatter_basic(tmp_path: Path):
    md = tmp_path / "test.md"
    md.write_text("""---
id: "hypothesis:h01-test"
kind: hypothesis
title: "Test hypothesis"
status: proposed
tags: [genomics, ml]
ontology_terms: ["GO:0006915"]
created: 2026-03-01
updated: 2026-03-10
related: ["question:q01"]
source_refs: []
---

This is the body content of the hypothesis.

## Rationale

Some rationale here.
""")
    result = parse_frontmatter(md)
    assert result is not None
    fm, body = result
    assert fm["id"] == "hypothesis:h01-test"
    assert fm["kind"] == "hypothesis"
    assert fm["tags"] == ["genomics", "ml"]
    assert "This is the body content" in body


def test_parse_frontmatter_missing_file(tmp_path: Path):
    result = parse_frontmatter(tmp_path / "nonexistent.md")
    assert result is None


def test_parse_entity_file(tmp_path: Path):
    md = tmp_path / "test.md"
    md.write_text("""---
id: "question:q01-test"
kind: question
title: "What is X?"
status: open
created: 2026-03-01
---

Body text here.
""")
    entity = parse_entity_file(md, project_slug="my-project")
    assert entity is not None
    assert entity.id == "question:q01-test"
    assert entity.kind == "question"
    assert entity.type == EntityType.QUESTION
    assert entity.project == "my-project"
    assert entity.content_preview == "Body text here."


def test_parse_entity_file_infers_type_from_id_prefix(tmp_path: Path):
    """When type is missing but id has a recognized prefix, infer the type."""
    md = tmp_path / "h01.md"
    md.write_text("""---
id: "hypothesis:h01-test"
title: "Hypothesis without explicit type"
status: proposed
created: 2026-03-01
---

Body text.
""")
    entity = parse_entity_file(md, project_slug="test-project")
    assert entity is not None
    assert entity.kind == "hypothesis"
    assert entity.type == EntityType.HYPOTHESIS
    assert entity.id == "hypothesis:h01-test"


def test_parse_entity_file_returns_none_without_type_or_id(tmp_path: Path):
    """Files in non-entity directories with neither type nor a recognizable id prefix are skipped."""
    md = tmp_path / "plain.md"
    md.write_text("""---
title: "No type no id prefix"
status: draft
---

Body text.
""")
    entity = parse_entity_file(md, project_slug="test-project")
    assert entity is None


def test_parse_entity_file_infers_type_from_parent_directory(tmp_path: Path):
    """When type and id are missing, the parent directory name (e.g. 'interpretations/')
    determines the entity type, and the id is derived from the filename stem."""
    interp_dir = tmp_path / "interpretations"
    interp_dir.mkdir()
    md = interp_dir / "2026-04-11-foo-bar.md"
    md.write_text("""---
title: "Foo Bar Analysis"
related: ["question:q01"]
---

Body text.
""")
    entity = parse_entity_file(md, project_slug="test-project")
    assert entity is not None
    assert entity.kind == "interpretation"
    assert entity.type == EntityType.INTERPRETATION
    assert entity.id == "interpretation:2026-04-11-foo-bar"


def test_parse_entity_file_infers_spec_type_from_specs_dir(tmp_path: Path):
    """Files under specs/ without frontmatter id/type are inferred as spec entities."""
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    md = specs_dir / "scope-boundaries.md"
    md.write_text("""---
title: "Scope Boundaries"
---

Body.
""")
    entity = parse_entity_file(md, project_slug="test-project")
    assert entity is not None
    assert entity.id == "spec:scope-boundaries"


def test_parse_entity_file_explicit_id_overrides_path_inference(tmp_path: Path):
    """Explicit id: in frontmatter takes precedence over directory-based inference."""
    interp_dir = tmp_path / "interpretations"
    interp_dir.mkdir()
    md = interp_dir / "anything.md"
    md.write_text("""---
id: "discussion:custom-id"
kind: discussion
title: "Misfiled but explicitly typed"
---

Body.
""")
    entity = parse_entity_file(md, project_slug="test-project")
    assert entity is not None
    assert entity.kind == "discussion"
    assert entity.type == EntityType.DISCUSSION
    assert entity.id == "discussion:custom-id"


def test_legacy_tags_silently_dropped(tmp_path: Path) -> None:
    """After parse-time merge removal, tags: in frontmatter is silently ignored.
    The migrate-tags CLI is the canonical way to migrate legacy tags."""
    md = tmp_path / "h01.md"
    md.write_text(
        '---\nid: "hypothesis:h01-test"\nkind: hypothesis\ntitle: "Test"\n'
        'status: proposed\ntags: [genomics, ml]\nrelated: ["question:q01"]\n'
        "source_refs: []\ncreated: 2026-03-01\n---\nBody.\n"
    )
    entity = parse_entity_file(md, "test-project")
    assert entity is not None
    assert "topic:genomics" not in entity.related
    assert "topic:ml" not in entity.related
    assert "meta:genomics" not in entity.related
    assert "question:q01" in entity.related


def test_parse_entity_file_with_sync_source(tmp_path: Path):
    config = tmp_path / "science.yaml"
    config.write_text("name: test-project\n", encoding="utf-8")
    doc = tmp_path / "doc" / "sync"
    doc.mkdir(parents=True)
    f = doc / "q-from-other.md"
    f.write_text(
        "---\n"
        'id: "question:q-from-other"\n'
        "kind: question\n"
        'title: "Propagated question"\n'
        "sync_source:\n"
        '  project: "aging-clocks"\n'
        '  entity_id: "question:q4-tp53"\n'
        '  sync_date: "2026-03-23"\n'
        "---\n"
        "Body text.\n",
        encoding="utf-8",
    )
    entity = parse_entity_file(f, project_slug="test-project")
    assert entity is not None
    assert entity.sync_source is not None
    assert entity.sync_source.project == "aging-clocks"
    assert entity.sync_source.entity_id == "question:q4-tp53"


def test_parse_entity_file_reads_identity_fields(tmp_path: Path) -> None:
    md = tmp_path / "doc" / "genes" / "EZH2.md"
    md.parent.mkdir(parents=True)
    md.write_text(
        "---\n"
        'id: "gene:EZH2"\n'
        'kind: "gene"\n'
        'title: "EZH2"\n'
        "primary_external_id:\n"
        '  source: "HGNC"\n'
        '  id: "3527"\n'
        '  curie: "HGNC:3527"\n'
        '  provenance: "manual"\n'
        "xrefs:\n"
        '  - source: "NCBIGene"\n'
        '    id: "2146"\n'
        '    curie: "NCBIGene:2146"\n'
        '    provenance: "manual"\n'
        'scope: "shared"\n'
        'deprecated_ids: ["gene:ENX1"]\n'
        'taxon: "NCBITaxon:9606"\n'
        "---\n"
        "Body.\n",
        encoding="utf-8",
    )
    entity = parse_entity_file(md, project_slug="demo")
    assert entity is not None
    assert entity.primary_external_id == ExternalId(
        source="HGNC",
        id="3527",
        curie="HGNC:3527",
        provenance="manual",
    )
    assert entity.xrefs == [
        ExternalId(
            source="NCBIGene",
            id="2146",
            curie="NCBIGene:2146",
            provenance="manual",
        )
    ]
    assert entity.scope == EntityScope.SHARED
    assert entity.deprecated_ids == ["gene:ENX1"]
    assert entity.taxon == "NCBITaxon:9606"


def test_parse_entity_file_preserves_versioned_accession_identity(tmp_path: Path) -> None:
    md = tmp_path / "doc" / "genes" / "TP53.md"
    md.parent.mkdir(parents=True)
    md.write_text(
        "---\n"
        'id: "gene:TP53"\n'
        'kind: "gene"\n'
        'title: "TP53"\n'
        "primary_external_id:\n"
        '  source: "ENSEMBL"\n'
        '  id: "ENST00000381578.7"\n'
        '  curie: "ENSEMBL:ENST00000381578.7"\n'
        '  version: "7"\n'
        '  provenance: "manual"\n'
        "---\n"
        "Body.\n",
        encoding="utf-8",
    )
    entity = parse_entity_file(md, project_slug="demo")
    assert entity is not None
    assert entity.primary_external_id is not None
    assert entity.primary_external_id.id == "ENST00000381578"
    assert entity.primary_external_id.version == "7"
    assert entity.primary_external_id.curie == "ENSEMBL:ENST00000381578"


def test_parse_entity_file_rejects_invalid_scope(tmp_path: Path) -> None:
    md = tmp_path / "doc" / "genes" / "EZH2.md"
    md.parent.mkdir(parents=True)
    md.write_text(
        '---\nid: "gene:EZH2"\nkind: "gene"\ntitle: "EZH2"\nscope: "private"\n---\nBody.\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid scope"):
        parse_entity_file(md, project_slug="demo")


def test_parse_entity_file_rejects_malformed_primary_external_id(tmp_path: Path) -> None:
    md = tmp_path / "doc" / "genes" / "EZH2.md"
    md.parent.mkdir(parents=True)
    md.write_text(
        "---\n"
        'id: "gene:EZH2"\n'
        'kind: "gene"\n'
        'title: "EZH2"\n'
        "primary_external_id:\n"
        '  source: "HGNC"\n'
        '  id: "3527"\n'
        '  curie: "HGNC:3527"\n'
        "---\n"
        "Body.\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="primary_external_id requires provenance"):
        parse_entity_file(md, project_slug="demo")


def test_parse_entity_file_rejects_malformed_xrefs(tmp_path: Path) -> None:
    md = tmp_path / "doc" / "genes" / "EZH2.md"
    md.parent.mkdir(parents=True)
    md.write_text(
        "---\n"
        'id: "gene:EZH2"\n'
        'kind: "gene"\n'
        'title: "EZH2"\n'
        "xrefs:\n"
        '  - source: "NCBIGene"\n'
        '    id: "2146"\n'
        '    curie: "NCBIGene:2146"\n'
        "---\n"
        "Body.\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="xrefs\\[0\\] requires provenance"):
        parse_entity_file(md, project_slug="demo")


def test_parse_entity_file_preserves_legacy_unknown_type(tmp_path: Path) -> None:
    md = tmp_path / "legacy-unknown.md"
    md.write_text(
        '---\nid: "unknown:legacy-record"\ntype: unknown\ntitle: "Legacy unknown"\n---\nBody.\n',
        encoding="utf-8",
    )
    entity = parse_entity_file(md, project_slug="demo")
    assert entity is not None
    assert entity.kind == "unknown"
    assert entity.type == EntityType.UNKNOWN


def test_parse_entity_file_infers_mechanism_from_parent_directory(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    mechanisms_dir = tmp_path / "doc" / "mechanisms"
    mechanisms_dir.mkdir(parents=True)
    md = mechanisms_dir / "test-mechanism.md"
    md.write_text(
        "---\n"
        'id: "mechanism:test-mechanism"\n'
        "type: mechanism\n"
        'title: "Test mechanism"\n'
        "participants:\n"
        '  - "protein:PHF19"\n'
        '  - "concept:prc2-complex"\n'
        "propositions:\n"
        '  - "proposition:ifn-silencing"\n'
        'summary: "PHF19-PRC2 dampens IFN signaling."\n'
        "---\n"
        "Mechanism body.\n",
        encoding="utf-8",
    )
    entity = parse_entity_file(md, project_slug="demo")
    assert entity is not None
    assert isinstance(entity, MechanismEntity)
    assert entity.kind == "mechanism"
    assert entity.type == EntityType.MECHANISM
    assert entity.id == "mechanism:test-mechanism"
    assert entity.file_path == "doc/mechanisms/test-mechanism.md"
    assert entity.participants == ["protein:PHF19", "concept:prc2-complex"]


def test_parse_entity_file_evidence_line_full(tmp_path: Path) -> None:
    """A fully-authored evidence-line markdown round-trips into EvidenceLineEntity."""
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    el_dir = tmp_path / "doc" / "evidence-lines"
    el_dir.mkdir(parents=True)
    md = el_dir / "e1.md"
    md.write_text(
        "---\n"
        'id: "evidence-line:e1"\n'
        'kind: "evidence-line"\n'
        'title: "E1 disputes P1"\n'
        'stance: "disputes"\n'
        'target: "proposition:p1"\n'
        'source: "paper:Smith2020"\n'
        'strength: "strong"\n'
        'independence: "independent"\n'
        'independence_group: "g1"\n'
        'evidence_role: "model_criticism"\n'
        'dispute_scope: "generalization"\n'
        'shared_dataset: "ds:X"\n'
        'shared_lab: "lab-alpha"\n'
        'shared_platform: "platform-Y"\n'
        'shared_cohort: "cohort-Z"\n'
        "---\n"
        "body text\n",
        encoding="utf-8",
    )
    entity = parse_entity_file(md, project_slug="demo")
    assert entity is not None
    assert isinstance(entity, EvidenceLineEntity)
    assert entity.kind == "evidence-line"
    assert entity.type == EntityType.EVIDENCE_LINE
    assert entity.id == "evidence-line:e1"
    assert entity.stance == EvidenceStance.DISPUTES
    assert entity.target == "proposition:p1"
    assert entity.source == "paper:Smith2020"
    assert entity.strength == EvidenceStrength.STRONG
    assert entity.independence == IndependenceTag.INDEPENDENT
    assert entity.independence_group == "g1"
    assert entity.evidence_role == EvidenceRole.MODEL_CRITICISM
    assert entity.dispute_scope == DisputeScope.GENERALIZATION
    assert entity.shared_dataset == "ds:X"
    assert entity.shared_lab == "lab-alpha"
    assert entity.shared_platform == "platform-Y"
    assert entity.shared_cohort == "cohort-Z"


def test_parse_entity_file_round_trips_falsification(tmp_path: Path) -> None:
    from science_model.entities import FalsificationEntity
    from science_model.frontmatter import parse_entity_file

    path = tmp_path / "f01.md"
    path.write_text(
        "---\n"
        'id: "falsification:f01"\n'
        'kind: "falsification"\n'
        'title: "Drug does not improve recovery"\n'
        'status: "active"\n'
        'falsifies: "proposition:drug_causes_recovery"\n'
        'predicted: "Drug improves recovery time"\n'
        'observed: "No improvement in randomized follow-up"\n'
        'decision: "Reject mechanistic interpretation"\n'
        'source_of_prediction: "topic:drug-mechanism"\n'
        "related: []\n"
        "source_refs: []\n"
        "---\n\n# Falsification\n",
        encoding="utf-8",
    )

    entity = parse_entity_file(path, project_slug="demo")

    assert isinstance(entity, FalsificationEntity)
    assert entity.falsifies == "proposition:drug_causes_recovery"
    assert entity.predicted == "Drug improves recovery time"
    assert entity.decision == "Reject mechanistic interpretation"
    assert entity.source_of_prediction == "topic:drug-mechanism"
    assert entity.supersedes_claim is None


def test_parse_entity_file_evidence_line_missing_stance_raises(tmp_path: Path) -> None:
    """Missing stance must raise ValidationError — no silent default allowed."""
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    el_dir = tmp_path / "doc" / "evidence-lines"
    el_dir.mkdir(parents=True)
    md = el_dir / "e2.md"
    md.write_text(
        "---\n"
        'id: "evidence-line:e2"\n'
        'kind: "evidence-line"\n'
        'title: "E2 missing stance"\n'
        'target: "proposition:p1"\n'
        "---\n"
        "body\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        parse_entity_file(md, project_slug="demo")  # missing target


def test_parse_entity_file_evidence_line_missing_target_raises(tmp_path: Path) -> None:
    """Missing target must raise ValidationError — no silent empty-string allowed."""
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    el_dir = tmp_path / "doc" / "evidence-lines"
    el_dir.mkdir(parents=True)
    md = el_dir / "e3.md"
    md.write_text(
        "---\n"
        'id: "evidence-line:e3"\n'
        'kind: "evidence-line"\n'
        'title: "E3 missing target"\n'
        'stance: "supports"\n'
        "---\n"
        "body\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        parse_entity_file(md, project_slug="demo")


def test_base_entity_reasoning_fields_parse_from_frontmatter(tmp_path):
    from science_model.frontmatter import parse_entity_file
    p = tmp_path / "doc" / "propositions" / "p.md"
    p.parent.mkdir(parents=True)
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    p.write_text(
        "---\nid: proposition:p\nkind: proposition\n"
        "independence_group: g1\nproxy_directness: indirect\nclaim_layer: mechanistic_narrative\n---\n# P\n",
        encoding="utf-8",
    )
    ent = parse_entity_file(p, project_slug="demo")
    assert ent.independence_group == "g1"
    assert str(ent.proxy_directness) == "indirect"
    assert str(ent.claim_layer) == "mechanistic_narrative"
