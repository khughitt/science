from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.validate.checks.orphan_datapackage_owner import check_orphan_datapackage_owner
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

_MANIFEST = (
    "name: demo-project\n"
    "created: 2026-01-01\n"
    "last_modified: 2026-01-02\n"
    "status: active\n"
    "summary: Demo project\n"
    "profile: research\n"
    "layout_version: {version}\n"
    "knowledge_profiles:\n"
    "  local: knowledge/local\n"
)


def _ctx(root: Path, *, version: int = 1) -> ValidateContext:
    (root / "science.yaml").write_text(_MANIFEST.format(version=version), encoding="utf-8")
    (root / "knowledge" / "local").mkdir(parents=True, exist_ok=True)
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _write_datapackage(root: Path, slug: str, ident: str) -> None:
    pkg = root / "data" / slug
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "name": slug,
                "id": ident,
                "type": "dataset",
                "title": ident,
                "origin": "external",
                "access": {"level": "public", "verified": False},
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.parametrize("version", [1, 3])
def test_orphan_datapackage_owner_errors_regardless_of_layout_version(tmp_path: Path, version: int) -> None:
    # Phase 2b cutover: an orphan is ALWAYS an error now that promotion tooling
    # exists (no longer WARN pre-v3, ERROR at v3 — layout_version is no longer
    # read). The loader still synthesizes a transitional owner so the project
    # loads; only this conformance severity flipped.
    ctx = _ctx(tmp_path, version=version)
    _write_datapackage(tmp_path, "ds1", "dataset:ds1")
    results = list(check_orphan_datapackage_owner(ctx))
    assert len(results) == 1
    assert results[0].severity is Severity.ERROR
    assert "dataset:ds1" in results[0].message
    assert "promote-orphans" in results[0].message


def test_non_orphan_datapackage_not_flagged(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    # A real markdown owner of the same id -> the datapackage DEFERS (Task 1), so no
    # datapackage owner declaration remains -> nothing to flag.
    (tmp_path / "entities" / "datasets").mkdir(parents=True)
    (tmp_path / "entities" / "datasets" / "x.md").write_text(
        '---\nid: "dataset:x"\ntype: "dataset"\ntitle: "X md"\n'
        'origin: "external"\n'
        'access:\n  level: "public"\n  verified: false\n---\n',
        encoding="utf-8",
    )
    _write_datapackage(tmp_path, "x", "dataset:x")
    assert list(check_orphan_datapackage_owner(ctx)) == []
