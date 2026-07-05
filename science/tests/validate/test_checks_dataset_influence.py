from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from science_tool.graph.paper_dataset_migration import is_paper_dataset_role_conflict
from science_tool.validate.checks import CANONICAL_CHECKS, clear_checks_for_tests
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

_MANIFEST = "name: demo\nknowledge_profiles:\n  local: local\n"


def _rules(results):
    return [(r.severity, r.rule) for r in results]


def _ctx(root: Path) -> ValidateContext:
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _fm(**extra):
    return {
        "id": "paper:Adams2025",
        "kind": "paper",
        "_path": "entities/papers/Adams2025.md",
        **extra,
    }


def _write_project(root: Path) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")


def _write_dataset_usage_paper(root: Path, ref: str = "dataset:gtex-v8") -> None:
    (root / "entities" / "papers").mkdir(parents=True)
    (root / "entities" / "papers" / "Adams2025.md").write_text(
        f"---\nid: paper:Adams2025\nkind: paper\ntitle: Adams\ndataset_usage:\n"
        f"  - ref: {ref}\n    role: analyzed\n    overlap: full\n---\n",
        encoding="utf-8",
    )


def _write_dataset(root: Path, slug: str, extra: str = "") -> None:
    dp_dir = root / "data" / slug
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(
        "profiles: [science-pkg-entity-1.0]\n"
        f"id: dataset:{slug}\n"
        "kind: dataset\n"
        f"title: {slug}\n"
        "status: active\n"
        "tier: use-now\n"
        "datapackage: datapackage.yaml\n"
        f"{extra}",
        encoding="utf-8",
    )


def _write_initialized_commons(root: Path) -> Path:
    commons = root / "commons"
    for dirname in (".git", "datasets", "papers", "topics", "themes"):
        (commons / dirname).mkdir(parents=True)
    return commons


def _write_geneset_collection(root: Path, dataset_ref: str) -> None:
    dp_dir = root / "data" / "reactome"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(
        "profiles: [science-pkg-entity-1.0]\n"
        "id: dataset:reactome-v89\n"
        "kind: dataset\n"
        "title: Reactome\n"
        "status: active\n"
        "origin: external\n"
        "tier: use-now\n"
        "datapackage: datapackage.yaml\n"
        "schema_profile: science-entity-base/1.0+dataset/1.0+bio.geneset/1.0\n"
        "source_class: reference\n"
        "access: {level: public, verified: true}\n"
        "member_key_column: set_key\n"
        "members_resource: sets\n"
        "n_sets: 1\n"
        "set_size_summary: {min: 2, median: 2, max: 2}\n"
        "identifier_space: {tier: gene, namespace: hgnc_id, resolution_status: declared_unresolved}\n"
        "resources:\n"
        "  - name: sets\n"
        "    path: sets.csv\n",
        encoding="utf-8",
    )
    (dp_dir / "sets.csv").write_text(
        "set_key,name,member_ids,dataset_usage\n"
        f'R-HSA-1,Cell cycle,HGNC:1;HGNC:2,"[{{""ref"":""{dataset_ref}"",""role"":""set_definition_source""}}]"\n',
        encoding="utf-8",
    )


def test_malformed_dataset_usage_errors() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [_fm(dataset_usage={"ref": "dataset:gtex-v8", "role": "analyzed"})],
            dataset_ref_status={"dataset:gtex-v8": "resolved"},
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [(Severity.ERROR, "dataset-influence.dataset-usage-malformed")]


def test_paper_datasets_invalid_entry_errors() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [_fm(datasets=["paper:Other"])],
            dataset_ref_status={},
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [(Severity.ERROR, "dataset-influence.paper-datasets-invalid")]


def test_paper_datasets_bare_alias_errors_even_when_canonicalizer_resolves() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [_fm(datasets=["gtex"])],
            dataset_ref_status={"dataset:gtex-v8": "resolved"},
            row_usage_refs=[],
            canonicalize_dataset_ref=lambda ref: "dataset:gtex-v8" if ref == "gtex" else ref,
        )
    )

    assert _rules(results) == [(Severity.ERROR, "dataset-influence.paper-datasets-invalid")]


def test_paper_datasets_empty_mapping_errors() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [_fm(datasets={})],
            dataset_ref_status={},
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [(Severity.ERROR, "dataset-influence.paper-datasets-invalid")]


def test_paper_datasets_empty_string_errors() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [_fm(datasets="")],
            dataset_ref_status={},
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [(Severity.ERROR, "dataset-influence.paper-datasets-invalid")]


def test_legacy_paper_datasets_warns_when_not_equivalent() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [_fm(datasets=["dataset:gtex-v8"])],
            dataset_ref_status={"dataset:gtex-v8": "resolved"},
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [(Severity.WARN, "dataset-influence.paper-datasets-legacy")]


def test_paper_datasets_conflict_warns_and_explicit_wins() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [
                _fm(
                    datasets=["dataset:gtex-v8"],
                    dataset_usage=[{"ref": "dataset:gtex-v8", "role": "cited"}],
                )
            ],
            dataset_ref_status={"dataset:gtex-v8": "resolved"},
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [(Severity.WARN, "dataset-influence.paper-datasets-conflict")]


def test_paper_datasets_analyzed_full_is_refinement_not_conflict() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [
                _fm(
                    datasets=["dataset:gtex-v8"],
                    dataset_usage=[{"ref": "dataset:gtex-v8", "role": "analyzed", "overlap": "full"}],
                )
            ],
            dataset_ref_status={"dataset:gtex-v8": "resolved"},
            row_usage_refs=[],
        )
    )

    assert results == []


def test_dataset_usage_reference_role_is_valid_non_dependence() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [_fm(dataset_usage=[{"ref": "dataset:ontology", "role": "reference"}])],
            dataset_ref_status={"dataset:ontology": "resolved"},
            row_usage_refs=[],
        )
    )

    assert results == []


def test_dataset_self_reference_errors() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [
                {
                    "id": "dataset:self",
                    "kind": "dataset",
                    "_path": "data/self/datapackage.yaml",
                    "dataset_usage": [{"ref": "dataset:self", "role": "analyzed"}],
                }
            ],
            dataset_ref_status={"dataset:self": "resolved"},
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [(Severity.ERROR, "dataset-influence.self-reference")]


def test_dataset_derivation_inputs_self_reference_errors() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [
                {
                    "id": "dataset:self",
                    "kind": "dataset",
                    "_path": "data/self/datapackage.yaml",
                    "derivation": {"inputs": ["dataset:self"]},
                }
            ],
            dataset_ref_status={"dataset:self": "resolved"},
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [(Severity.ERROR, "dataset-influence.self-reference")]


def test_unresolved_refs_use_pinned_severities() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [
                _fm(
                    dataset_usage=[
                        {"ref": "dataset:unknown-a", "role": "analyzed", "overlap": "full"},
                        {"ref": "dataset:unknown-b", "role": "training", "overlap": "full"},
                    ]
                )
            ],
            dataset_ref_status={
                "dataset:unknown-a": "unavailable",
                "dataset:unknown-b": "missing",
            },
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [
        (Severity.INFO, "dataset-influence.ref-unresolved-unavailable"),
        (Severity.WARN, "dataset-influence.ref-unresolved"),
    ]


def test_check_dataset_influence_resolves_local_dataset_ref(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool.validate.checks.dataset_influence import check_dataset_influence

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "empty-commons"))
    _write_project(tmp_path)
    _write_dataset_usage_paper(tmp_path)
    dp_dir = tmp_path / "data" / "gtex"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(
        "profiles: [science-pkg-entity-1.0]\nid: dataset:gtex-v8\nkind: dataset\ntitle: GTEx\n"
        "origin: external\ntier: use-now\ndatapackage: datapackage.yaml\naccess: {level: public, verified: true}\n",
        encoding="utf-8",
    )

    assert list(check_dataset_influence(_ctx(tmp_path))) == []


def test_check_dataset_influence_resolves_local_markdown_dataset_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A markdown dataset descriptor in entities/datasets/ resolves a paper's dataset_usage ref.

    Regression: the resolver loaded entity_frontmatters (entities/ + data/ datapackages)
    but not dataset_frontmatters (entities/datasets/ markdown), so markdown-only datasets were
    invisible to resolution and every dataset_usage ref to them warned ref-unresolved.
    """
    from science_tool.validate.checks.dataset_influence import check_dataset_influence

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "empty-commons"))
    _write_project(tmp_path)
    _write_dataset_usage_paper(tmp_path, ref="dataset:swan")
    ds_dir = tmp_path / "entities" / "datasets"
    ds_dir.mkdir(parents=True)
    (ds_dir / "swan.md").write_text(
        '---\nid: "dataset:swan"\nkind: "dataset"\ntitle: "SWAN"\n'
        'status: "active"\norigin: "external"\ntier: "use-now"\n---\n\nSWAN cohort.\n',
        encoding="utf-8",
    )

    assert list(check_dataset_influence(_ctx(tmp_path))) == []


def test_check_dataset_influence_resolves_local_dataset_alias_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.validate.checks.dataset_influence import check_dataset_influence

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "missing-commons"))
    _write_project(tmp_path)
    _write_dataset_usage_paper(tmp_path, ref="dataset:gtex")
    _write_dataset(
        tmp_path,
        "gtex-v8",
        "aliases: [dataset:gtex]\norigin: external\naccess: {level: public, verified: true}\n",
    )

    assert list(check_dataset_influence(_ctx(tmp_path))) == []


def test_check_dataset_influence_dataset_usage_requires_raw_dataset_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.validate.checks.dataset_influence import check_dataset_influence

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "missing-commons"))
    _write_project(tmp_path)
    _write_dataset_usage_paper(tmp_path, ref="gtex")
    _write_dataset(
        tmp_path,
        "gtex-v8",
        "aliases: [gtex]\norigin: external\naccess: {level: public, verified: true}\n",
    )

    results = list(check_dataset_influence(_ctx(tmp_path)))

    assert _rules(results) == [(Severity.ERROR, "dataset-influence.dataset-usage-malformed")]


def test_check_dataset_influence_legacy_paper_datasets_bare_alias_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.validate.checks.dataset_influence import check_dataset_influence

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "missing-commons"))
    _write_project(tmp_path)
    _write_dataset(
        tmp_path,
        "gtex-v8",
        "aliases: [dataset:gtex, gtex]\norigin: external\naccess: {level: public, verified: true}\n",
    )
    (tmp_path / "entities" / "papers").mkdir(parents=True)
    (tmp_path / "entities" / "papers" / "Adams2025.md").write_text(
        "---\nid: paper:Adams2025\nkind: paper\ntitle: Adams\ndatasets: [gtex]\n---\n",
        encoding="utf-8",
    )

    results = list(check_dataset_influence(_ctx(tmp_path)))

    assert _rules(results) == [(Severity.ERROR, "dataset-influence.paper-datasets-invalid")]


def test_check_dataset_influence_uses_manual_aliases_for_dataset_usage_refs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.validate.checks.dataset_influence import check_dataset_influence

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "missing-commons"))
    _write_project(tmp_path)
    mappings = tmp_path / "knowledge" / "sources" / "local" / "mappings.yaml"
    mappings.parent.mkdir(parents=True)
    mappings.write_text('aliases:\n  "dataset:gtex": "dataset:gtex-v8"\n', encoding="utf-8")
    _write_dataset_usage_paper(tmp_path, ref="dataset:gtex")
    _write_dataset(
        tmp_path,
        "gtex-v8",
        "origin: external\naccess: {level: public, verified: true}\n",
    )

    assert list(check_dataset_influence(_ctx(tmp_path))) == []


def test_check_dataset_influence_manual_alias_to_non_dataset_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.validate.checks.dataset_influence import check_dataset_influence

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "missing-commons"))
    _write_project(tmp_path)
    mappings = tmp_path / "knowledge" / "sources" / "local" / "mappings.yaml"
    mappings.parent.mkdir(parents=True)
    mappings.write_text('aliases:\n  "dataset:gtex": "paper:Adams2025"\n', encoding="utf-8")
    (tmp_path / "entities" / "papers").mkdir(parents=True)
    (tmp_path / "entities" / "papers" / "Adams2025.md").write_text(
        "---\n"
        "id: paper:Adams2025\n"
        "kind: paper\n"
        "title: Adams\n"
        "dataset_usage:\n"
        "  - ref: dataset:gtex\n"
        "    role: analyzed\n"
        "    overlap: full\n"
        "---\n",
        encoding="utf-8",
    )

    results = list(check_dataset_influence(_ctx(tmp_path)))

    assert _rules(results) == [(Severity.ERROR, "dataset-influence.ref-not-dataset")]


def test_check_dataset_influence_paper_datasets_alias_to_non_dataset_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.validate.checks.dataset_influence import check_dataset_influence

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "missing-commons"))
    _write_project(tmp_path)
    mappings = tmp_path / "knowledge" / "sources" / "local" / "mappings.yaml"
    mappings.parent.mkdir(parents=True)
    mappings.write_text('aliases:\n  "dataset:gtex": "paper:Smith2024"\n', encoding="utf-8")
    (tmp_path / "entities" / "papers").mkdir(parents=True)
    (tmp_path / "entities" / "papers" / "Adams2025.md").write_text(
        "---\nid: paper:Adams2025\nkind: paper\ntitle: Adams\ndatasets: [dataset:gtex]\n---\n",
        encoding="utf-8",
    )
    (tmp_path / "entities" / "papers" / "Smith2024.md").write_text(
        "---\nid: paper:Smith2024\nkind: paper\ntitle: Smith\naliases: [dataset:smith]\n---\n",
        encoding="utf-8",
    )

    results = list(check_dataset_influence(_ctx(tmp_path)))

    assert _rules(results) == [
        (Severity.WARN, "dataset-influence.paper-datasets-legacy"),
        (Severity.ERROR, "dataset-influence.ref-not-dataset"),
    ]


def test_check_dataset_influence_derivation_input_alias_to_non_dataset_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.validate.checks.dataset_influence import check_dataset_influence

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "missing-commons"))
    _write_project(tmp_path)
    mappings = tmp_path / "knowledge" / "sources" / "local" / "mappings.yaml"
    mappings.parent.mkdir(parents=True)
    mappings.write_text('aliases:\n  "dataset:gtex": "paper:Smith2024"\n', encoding="utf-8")
    _write_dataset(
        tmp_path,
        "derived",
        "origin: derived\nderivation:\n  kind: aggregate\n  inputs:\n    - dataset:gtex\n",
    )
    (tmp_path / "entities" / "papers").mkdir(parents=True)
    (tmp_path / "entities" / "papers" / "Smith2024.md").write_text(
        "---\nid: paper:Smith2024\nkind: paper\ntitle: Smith\naliases: [dataset:smith]\n---\n",
        encoding="utf-8",
    )

    results = list(check_dataset_influence(_ctx(tmp_path)))

    assert _rules(results) == [(Severity.ERROR, "dataset-influence.ref-not-dataset")]


def test_check_dataset_influence_dataset_usage_alias_self_reference_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.validate.checks.dataset_influence import check_dataset_influence

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "missing-commons"))
    _write_project(tmp_path)
    _write_dataset(
        tmp_path,
        "derived",
        "aliases: [dataset:derived-alias]\n"
        "origin: derived\n"
        "dataset_usage:\n"
        "  - ref: dataset:derived-alias\n"
        "    role: upstream\n",
    )

    results = list(check_dataset_influence(_ctx(tmp_path)))

    assert _rules(results) == [(Severity.ERROR, "dataset-influence.self-reference")]


def test_check_dataset_influence_derivation_input_alias_resolves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.validate.checks.dataset_influence import check_dataset_influence

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "missing-commons"))
    _write_project(tmp_path)
    _write_dataset(
        tmp_path,
        "gtex-v8",
        "aliases: [dataset:gtex]\norigin: external\naccess: {level: public, verified: true}\n",
    )
    _write_dataset(
        tmp_path,
        "derived",
        "origin: derived\nderivation:\n  kind: aggregate\n  inputs:\n    - dataset:gtex\n",
    )

    assert list(check_dataset_influence(_ctx(tmp_path))) == []


def test_check_dataset_influence_derivation_inputs_require_raw_dataset_refs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.validate.checks.dataset_influence import check_dataset_influence

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "missing-commons"))
    _write_project(tmp_path)
    _write_dataset(
        tmp_path,
        "gtex-v8",
        "aliases: [gtex]\norigin: external\naccess: {level: public, verified: true}\n",
    )
    _write_dataset(
        tmp_path,
        "derived",
        "origin: derived\nderivation:\n  kind: aggregate\n  inputs:\n    - gtex\n",
    )

    results = list(check_dataset_influence(_ctx(tmp_path)))

    assert _rules(results) == [(Severity.ERROR, "dataset-influence.derivation-inputs-invalid")]


def test_check_dataset_influence_geneset_row_alias_resolves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool.validate.checks.dataset_influence import check_dataset_influence

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "missing-commons"))
    _write_project(tmp_path)
    _write_dataset(
        tmp_path,
        "gtex-v8",
        "aliases: [dataset:gtex]\norigin: external\naccess: {level: public, verified: true}\n",
    )
    _write_geneset_collection(tmp_path, dataset_ref="dataset:gtex")

    assert list(check_dataset_influence(_ctx(tmp_path))) == []


def test_check_dataset_influence_unbuilt_commons_ref_infos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool.validate.checks.dataset_influence import check_dataset_influence

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "missing-commons"))
    _write_project(tmp_path)
    _write_dataset_usage_paper(tmp_path)

    results = list(check_dataset_influence(_ctx(tmp_path)))

    assert _rules(results) == [(Severity.INFO, "dataset-influence.ref-unresolved-unavailable")]


def test_check_dataset_influence_empty_commons_dir_ref_infos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool.validate.checks.dataset_influence import check_dataset_influence

    commons = tmp_path / "empty-commons"
    commons.mkdir()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    _write_project(tmp_path)
    _write_dataset_usage_paper(tmp_path)

    results = list(check_dataset_influence(_ctx(tmp_path)))

    assert _rules(results) == [(Severity.INFO, "dataset-influence.ref-unresolved-unavailable")]


def test_check_dataset_influence_built_commons_missing_ref_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.validate.checks.dataset_influence import check_dataset_influence

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(_write_initialized_commons(tmp_path)))
    _write_project(tmp_path)
    _write_dataset_usage_paper(tmp_path)

    results = list(check_dataset_influence(_ctx(tmp_path)))

    assert _rules(results) == [(Severity.WARN, "dataset-influence.ref-unresolved")]


def test_dataset_influence_registration_after_genesets() -> None:
    clear_checks_for_tests()

    import science_tool.validate.checks.dataset_influence as dataset_influence
    import science_tool.validate.checks.genesets as genesets

    importlib.reload(genesets)
    importlib.reload(dataset_influence)

    ordered = [(entry.section, entry.order, entry.fn.__module__) for entry in CANONICAL_CHECKS]
    genesets_index = next(index for index, entry in enumerate(ordered) if entry[0] == "gene-set collections")
    influence_index = next(index for index, entry in enumerate(ordered) if entry[0] == "dataset influence")
    assert influence_index == genesets_index + 1


def test_row_usage_refs_unresolved_uses_pinned_severities() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [],
            dataset_ref_status={
                "dataset:row-a": "unavailable",
                "dataset:row-b": "missing",
            },
            row_usage_refs=[
                ("dataset:row-a", "geneset:one", "doc/gene-sets.tsv"),
                ("dataset:row-b", "geneset:two", "doc/gene-sets.tsv"),
            ],
        )
    )

    assert _rules(results) == [
        (Severity.INFO, "dataset-influence.ref-unresolved-unavailable"),
        (Severity.WARN, "dataset-influence.ref-unresolved"),
    ]


# Sub-task 4: severity-contract unit tests


def test_ref_not_dataset_is_error() -> None:
    """A dataset_usage ref that resolves to a non-dataset entity is a hard ERROR."""
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [_fm(dataset_usage=[{"ref": "dataset:gtex-v8", "role": "analyzed", "overlap": "full"}])],
            dataset_ref_status={"dataset:gtex-v8": "non_dataset"},
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [(Severity.ERROR, "dataset-influence.ref-not-dataset")]


def test_malformed_dataset_usage_bad_role_is_error() -> None:
    """A dataset_usage entry with an unrecognised role is a hard ERROR."""
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [_fm(dataset_usage=[{"ref": "dataset:gtex-v8", "role": "consulted"}])],
            dataset_ref_status={"dataset:gtex-v8": "resolved"},
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [(Severity.ERROR, "dataset-influence.dataset-usage-malformed")]


def test_malformed_dataset_usage_bad_overlap_is_error() -> None:
    """A dataset_usage entry with an unrecognised overlap value is a hard ERROR."""
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [_fm(dataset_usage=[{"ref": "dataset:gtex-v8", "role": "analyzed", "overlap": "some"}])],
            dataset_ref_status={"dataset:gtex-v8": "resolved"},
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [(Severity.ERROR, "dataset-influence.dataset-usage-malformed")]


# Sub-task 2d: dependence-role dataset_usage with overlap=unknown warns


@pytest.mark.parametrize("role", ["analyzed", "set_definition_source", "training", "upstream"])
def test_dependence_role_with_overlap_unknown_warns(role: str) -> None:
    """A dependence-role dataset_usage with overlap=unknown emits a WARN."""
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [_fm(dataset_usage=[{"ref": "dataset:gtex-v8", "role": role, "overlap": "unknown"}])],
            dataset_ref_status={"dataset:gtex-v8": "resolved"},
            row_usage_refs=[],
        )
    )

    rule_pairs = _rules(results)
    assert (Severity.WARN, "dataset-influence.overlap-unknown-candidate") in rule_pairs


def test_dependence_role_with_omitted_overlap_warns() -> None:
    """A dependence-role dataset_usage with no overlap key (defaults to unknown) emits a WARN."""
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [_fm(dataset_usage=[{"ref": "dataset:gtex-v8", "role": "analyzed"}])],
            dataset_ref_status={"dataset:gtex-v8": "resolved"},
            row_usage_refs=[],
        )
    )

    rule_pairs = _rules(results)
    assert (Severity.WARN, "dataset-influence.overlap-unknown-candidate") in rule_pairs


def test_dependence_role_with_overlap_full_does_not_warn() -> None:
    """A dependence-role dataset_usage with overlap=full must NOT emit the overlap-unknown WARN."""
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [_fm(dataset_usage=[{"ref": "dataset:gtex-v8", "role": "analyzed", "overlap": "full"}])],
            dataset_ref_status={"dataset:gtex-v8": "resolved"},
            row_usage_refs=[],
        )
    )

    rule_pairs = _rules(results)
    assert (Severity.WARN, "dataset-influence.overlap-unknown-candidate") not in rule_pairs


def test_dependence_role_with_overlap_partial_does_not_warn() -> None:
    """A dependence-role dataset_usage with overlap=partial must NOT emit the overlap-unknown WARN."""
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [_fm(dataset_usage=[{"ref": "dataset:gtex-v8", "role": "analyzed", "overlap": "partial"}])],
            dataset_ref_status={"dataset:gtex-v8": "resolved"},
            row_usage_refs=[],
        )
    )

    rule_pairs = _rules(results)
    assert (Severity.WARN, "dataset-influence.overlap-unknown-candidate") not in rule_pairs


@pytest.mark.parametrize("role", ["validation_source", "cited"])
def test_non_dependence_role_with_overlap_unknown_does_not_warn(role: str) -> None:
    """Non-dependence roles with overlap=unknown must NOT emit the overlap-unknown WARN."""
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [_fm(dataset_usage=[{"ref": "dataset:gtex-v8", "role": role, "overlap": "unknown"}])],
            dataset_ref_status={"dataset:gtex-v8": "resolved"},
            row_usage_refs=[],
        )
    )

    rule_pairs = _rules(results)
    assert (Severity.WARN, "dataset-influence.overlap-unknown-candidate") not in rule_pairs


@pytest.mark.parametrize("role", ["validation_source", "cited"])
def test_non_dependence_role_with_omitted_overlap_does_not_warn(role: str) -> None:
    """Non-dependence roles with no overlap key must NOT emit the overlap-unknown WARN."""
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [_fm(dataset_usage=[{"ref": "dataset:gtex-v8", "role": role}])],
            dataset_ref_status={"dataset:gtex-v8": "resolved"},
            row_usage_refs=[],
        )
    )

    rule_pairs = _rules(results)
    assert (Severity.WARN, "dataset-influence.overlap-unknown-candidate") not in rule_pairs


def test_role_conflict_true_when_not_analyzed():
    assert is_paper_dataset_role_conflict({"role": "compared"}) is True
    assert is_paper_dataset_role_conflict({}) is True


def test_role_conflict_false_when_analyzed():
    assert is_paper_dataset_role_conflict({"role": "analyzed"}) is False
    assert is_paper_dataset_role_conflict({"role": "analyzed", "overlap": "full"}) is False
