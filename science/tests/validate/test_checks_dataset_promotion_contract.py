from __future__ import annotations

import json
from pathlib import Path

import pytest

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.registry import RegistryBuilder
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

_MANIFEST = (
    "name: demo-project\n"
    "created: 2026-01-01\n"
    "last_modified: 2026-01-02\n"
    "status: active\n"
    "summary: Demo project\n"
    "profile: research\n"
    "layout_version: 1\n"
    "knowledge_profiles:\n"
    "  local: knowledge/local\n"
)


def _ctx(root: Path) -> ValidateContext:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _write_resource(root: Path, relative_path: str, text: str = "value\n") -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_datapackage(
    root: Path,
    *,
    path: str = "data/processed/demo/datapackage.json",
    resources: list[dict[str, object]] | None = None,
) -> None:
    datapackage_path = root / path
    datapackage_path.parent.mkdir(parents=True, exist_ok=True)
    if resources is None:
        resources = [
            {"name": "table", "path": "table.csv"},
            {"name": "table-qa", "path": "qa/table-qa.json"},
        ]
    datapackage_path.write_text(
        json.dumps({"name": "demo-dataset", "resources": resources}, indent=2) + "\n",
        encoding="utf-8",
    )
    for resource in resources:
        resource_path = resource.get("path")
        if isinstance(resource_path, str):
            _write_resource(root, str(datapackage_path.parent / resource_path))


def _write_commons_dataset(root: Path, *, slug: str = "demo-dataset", version: str = "1.0.0") -> Path:
    commons = root / "commons"
    dataset_dir = commons / "datasets" / slug
    dataset_dir.mkdir(parents=True, exist_ok=True)
    (dataset_dir / "entity.md").write_text(
        "---\n"
        "schema_profile: science-entity-base/1.0+dataset/1.0\n"
        f"id: dataset:{slug}\n"
        "type: dataset\n"
        "title: Demo Dataset\n"
        f"version: \"{version}\"\n"
        "created: \"2026-01-01\"\n"
        "updated: \"2026-01-01\"\n"
        "status: active\n"
        "datapackage: datapackage.yaml\n"
        "origin: derived\n"
        "tier: use-now\n"
        "derivation:\n"
        "  kind: workflow\n"
        "  workflow_recipe: workflow:demo\n"
        "  inputs: []\n"
        "---\n"
        "# Demo Dataset\n",
        encoding="utf-8",
    )
    (dataset_dir / "datapackage.yaml").write_text(
        "name: demo-dataset\nresources: []\n",
        encoding="utf-8",
    )
    RegistryBuilder(commons, CommonsEntityAdapter(commons)).rebuild()
    return commons


def _write_descriptor(
    root: Path,
    *,
    slug: str = "demo-dataset",
    extra_frontmatter: str = "",
    datapackage: str = "data/processed/demo/datapackage.json",
    source_refs: str = "source_refs:\n  - task:t001\n",
) -> Path:
    path = root / "doc" / "datasets" / f"data-{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"id: dataset:{slug}\n"
        "type: dataset\n"
        "title: Demo Dataset\n"
        "profiles: [science-pkg-entity-1.0]\n"
        "origin: derived\n"
        "tier: use-now\n"
        "derivation:\n"
        "  kind: workflow\n"
        "  workflow_recipe: workflow:demo\n"
        "  inputs: []\n"
        f"datapackage: {datapackage}\n"
        f"{source_refs}"
        f"{extra_frontmatter}"
        "---\n"
        "# Demo Dataset\n",
        encoding="utf-8",
    )
    return path


def _rules(results: list) -> list[str | None]:
    return [result.rule for result in results]


def test_clean_candidate_dataset_descriptor_passes_contract(tmp_path: Path) -> None:
    from science_tool.validate.checks.dataset_promotion_contract import (
        check_dataset_promotion_contract,
    )

    _write_datapackage(tmp_path)
    _write_descriptor(tmp_path)

    results = list(check_dataset_promotion_contract(_ctx(tmp_path)))

    assert results == []


def test_plain_dataset_reference_doc_is_not_a_promotion_candidate(tmp_path: Path) -> None:
    from science_tool.validate.checks.dataset_promotion_contract import (
        check_dataset_promotion_contract,
    )

    path = tmp_path / "doc" / "datasets" / "data-reference-only.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "id: dataset:reference-only\n"
        "type: dataset\n"
        "title: Reference-only Dataset\n"
        "status: active\n"
        "source_refs: []\n"
        "---\n"
        "# Reference-only Dataset\n",
        encoding="utf-8",
    )

    results = list(check_dataset_promotion_contract(_ctx(tmp_path)))

    assert results == []


def test_candidate_descriptor_requires_resolvable_datapackage(tmp_path: Path) -> None:
    from science_tool.validate.checks.dataset_promotion_contract import (
        check_dataset_promotion_contract,
    )

    _write_descriptor(tmp_path, datapackage="data/processed/missing/datapackage.json")

    results = list(check_dataset_promotion_contract(_ctx(tmp_path)))

    assert _rules(results) == ["dataset-promotion.datapackage-unresolved"]
    assert results[0].severity is Severity.ERROR
    assert "datapackage file does not exist" in results[0].message


def test_candidate_descriptor_requires_qa_resource(tmp_path: Path) -> None:
    from science_tool.validate.checks.dataset_promotion_contract import (
        check_dataset_promotion_contract,
    )

    _write_datapackage(
        tmp_path,
        resources=[{"name": "table", "path": "table.csv"}],
    )
    _write_descriptor(tmp_path)

    results = list(check_dataset_promotion_contract(_ctx(tmp_path)))

    assert _rules(results) == ["dataset-promotion.qa-resource-missing"]
    assert results[0].severity is Severity.ERROR
    assert "no QA resource" in results[0].message


def test_candidate_descriptor_accepts_qc_report_as_qa_resource(tmp_path: Path) -> None:
    from science_tool.validate.checks.dataset_promotion_contract import (
        check_dataset_promotion_contract,
    )

    _write_datapackage(
        tmp_path,
        resources=[
            {"name": "table", "path": "table.csv"},
            {"name": "dataset-qc-report", "path": "qc_report.json"},
        ],
    )
    _write_descriptor(tmp_path)

    results = list(check_dataset_promotion_contract(_ctx(tmp_path)))

    assert results == []


def test_candidate_descriptor_requires_source_refs(tmp_path: Path) -> None:
    from science_tool.validate.checks.dataset_promotion_contract import (
        check_dataset_promotion_contract,
    )

    _write_datapackage(tmp_path)
    _write_descriptor(tmp_path, source_refs="source_refs: []\n")

    results = list(check_dataset_promotion_contract(_ctx(tmp_path)))

    assert _rules(results) == ["dataset-promotion.source-refs-missing"]
    assert results[0].severity is Severity.ERROR


def test_pinned_overlay_requires_resolvable_source_datapackage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from science_tool.validate.checks.dataset_promotion_contract import (
        check_dataset_promotion_contract,
    )

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(_write_commons_dataset(tmp_path)))
    _write_descriptor(
        tmp_path,
        extra_frontmatter=(
            "overlay_of: dataset:demo-dataset\n"
            "pin_version: \"1.0.0\"\n"
            "source: data/processed/missing/datapackage.json\n"
        ),
    )

    results = list(check_dataset_promotion_contract(_ctx(tmp_path)))

    assert _rules(results) == ["dataset-promotion.source-unresolved"]
    assert results[0].severity is Severity.ERROR


def test_pinned_overlay_requires_resolvable_commons_canonical(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from science_tool.validate.checks.dataset_promotion_contract import (
        check_dataset_promotion_contract,
    )

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "missing-commons"))
    _write_datapackage(tmp_path)
    _write_descriptor(
        tmp_path,
        extra_frontmatter=(
            "overlay_of: dataset:demo-dataset\n"
            "pin_version: \"1.0.0\"\n"
            "source: data/processed/demo/datapackage.json\n"
        ),
    )

    results = list(check_dataset_promotion_contract(_ctx(tmp_path)))

    assert _rules(results) == ["dataset-promotion.pin-unresolved"]
    assert results[0].severity is Severity.ERROR
    assert "commons canonical could not be resolved" in results[0].message


def test_pinned_overlay_requires_matching_commons_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from science_tool.validate.checks.dataset_promotion_contract import (
        check_dataset_promotion_contract,
    )

    monkeypatch.setenv(
        "SCIENCE_COMMONS_ROOT",
        str(_write_commons_dataset(tmp_path, version="2.0.0")),
    )
    _write_datapackage(tmp_path)
    _write_descriptor(
        tmp_path,
        extra_frontmatter=(
            "overlay_of: dataset:demo-dataset\n"
            "pin_version: \"1.0.0\"\n"
            "source: data/processed/demo/datapackage.json\n"
        ),
    )

    results = list(check_dataset_promotion_contract(_ctx(tmp_path)))

    assert _rules(results) == ["dataset-promotion.pin-version-mismatch"]
    assert results[0].severity is Severity.ERROR
    assert "pins 1.0.0 but commons canonical is 2.0.0" in results[0].message


def test_pinned_overlay_with_resolvable_source_passes_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from science_tool.validate.checks.dataset_promotion_contract import (
        check_dataset_promotion_contract,
    )

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(_write_commons_dataset(tmp_path)))
    _write_datapackage(tmp_path)
    _write_descriptor(
        tmp_path,
        extra_frontmatter=(
            "overlay_of: dataset:demo-dataset\n"
            "pin_version: \"1.0.0\"\n"
            "source: data/processed/demo/datapackage.json\n"
        ),
    )

    results = list(check_dataset_promotion_contract(_ctx(tmp_path)))

    assert results == []
