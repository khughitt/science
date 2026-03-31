"""Tests for research package schema and validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_model.packages.schema import (
    CodeExcerpt,
    FigureRef,
    Provenance,
    ProvenanceInput,
    ResearchExtension,
    ResearchPackageDescriptor,
    ResourceSchema,
    VegaLiteSpec,
)


def _valid_provenance() -> dict:
    return {
        "workflow": "workflows/theme-validation/Snakefile",
        "config": "workflows/theme-validation/config.yaml",
        "last_run": "2026-03-30T10:00:00Z",
        "git_commit": "abc123def456",
        "repository": "https://github.com/user/repo",
        "inputs": [{"path": "src/foo.ts", "sha256": "aabb"}],
        "scripts": ["scripts/foo.ts"],
    }


def _valid_package() -> dict:
    return {
        "name": "theme-instability-bifurcation",
        "title": "Instability & Bifurcation",
        "profile": "science-research-package",
        "version": "1.0.0",
        "resources": [{"name": "scores", "path": "data/scores.csv"}],
        "research": {
            "cells": "cells.json",
            "figures": [],
            "vegalite_specs": [],
            "code_excerpts": [],
            "provenance": _valid_provenance(),
        },
    }


class TestResearchPackageDescriptor:
    def test_valid_package(self) -> None:
        pkg = ResearchPackageDescriptor(**_valid_package())
        assert pkg.name == "theme-instability-bifurcation"
        assert pkg.profile == "science-research-package"

    def test_rejects_wrong_profile(self) -> None:
        data = _valid_package()
        data["profile"] = "wrong-profile"
        with pytest.raises(ValidationError):
            ResearchPackageDescriptor(**data)

    def test_rejects_missing_provenance(self) -> None:
        data = _valid_package()
        del data["research"]["provenance"]
        with pytest.raises(ValidationError):
            ResearchPackageDescriptor(**data)

    def test_allows_empty_collections(self) -> None:
        pkg = ResearchPackageDescriptor(**_valid_package())
        assert pkg.research.figures == []
        assert pkg.research.vegalite_specs == []
        assert pkg.research.code_excerpts == []

    def test_target_route_optional(self) -> None:
        data = _valid_package()
        pkg = ResearchPackageDescriptor(**data)
        assert pkg.research.target_route is None

        data["research"]["target_route"] = "/guide/theme/chaos"
        pkg2 = ResearchPackageDescriptor(**data)
        assert pkg2.research.target_route == "/guide/theme/chaos"

    def test_resource_schema_field_alias(self) -> None:
        r = ResourceSchema(name="test", path="data/test.csv", **{"schema": {"fields": []}})
        assert r.schema_ == {"fields": []}

    def test_code_excerpt_lines_tuple(self) -> None:
        exc = CodeExcerpt(
            name="test", path="excerpts/test.ts", source="scripts/test.ts",
            lines=(10, 50), github_permalink="",
        )
        assert exc.lines == (10, 50)

    def test_github_permalink_defaults_empty(self) -> None:
        exc = CodeExcerpt(
            name="test", path="excerpts/test.ts", source="scripts/test.ts", lines=(1, 10),
        )
        assert exc.github_permalink == ""

    def test_vegalite_spec(self) -> None:
        spec = VegaLiteSpec(name="chart", path="figures/chart.vl.json")
        assert spec.caption is None

    def test_provenance_input(self) -> None:
        inp = ProvenanceInput(path="src/foo.ts", sha256="abc123")
        assert inp.sha256 == "abc123"


from science_model.packages.cells import (
    Cell,
    CodeReferenceCell,
    DataTableCell,
    FigureCell,
    NarrativeCell,
    ProvenanceCell,
    VegaLiteCell,
    parse_cells,
)


class TestCellSchema:
    def test_narrative_cell(self) -> None:
        cell = NarrativeCell(type="narrative", content="prose/01-intro.md")
        assert cell.content == "prose/01-intro.md"

    def test_data_table_cell(self) -> None:
        cell = DataTableCell(type="data-table", resource="scores")
        assert cell.columns is None
        assert cell.caption is None

    def test_data_table_cell_with_columns(self) -> None:
        cell = DataTableCell(type="data-table", resource="scores", columns=["a", "b"], caption="My table")
        assert cell.columns == ["a", "b"]

    def test_figure_cell(self) -> None:
        cell = FigureCell(type="figure", ref="confusion-matrix")
        assert cell.ref == "confusion-matrix"

    def test_vegalite_cell(self) -> None:
        cell = VegaLiteCell(type="vegalite", ref="chart", caption="My chart")
        assert cell.caption == "My chart"

    def test_code_reference_cell(self) -> None:
        cell = CodeReferenceCell(type="code-reference", excerpt="kappa")
        assert cell.description is None

    def test_provenance_cell(self) -> None:
        cell = ProvenanceCell(type="provenance")
        assert cell.type == "provenance"

    def test_parse_cells_from_list(self) -> None:
        raw = [
            {"type": "narrative", "content": "prose/01.md"},
            {"type": "data-table", "resource": "scores"},
            {"type": "provenance"},
        ]
        cells = parse_cells(raw)
        assert len(cells) == 3
        assert isinstance(cells[0], NarrativeCell)
        assert isinstance(cells[1], DataTableCell)
        assert isinstance(cells[2], ProvenanceCell)

    def test_parse_cells_rejects_unknown_type(self) -> None:
        with pytest.raises(ValueError, match="Unknown cell type"):
            parse_cells([{"type": "unknown"}])
