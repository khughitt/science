from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.validate.checks.aggregate_stub import check_lone_aggregate_stub
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

_MANIFEST = "name: demo-project\nprofile: research\nprofiles: {local: local}\n"


def _ctx(root: Path) -> ValidateContext:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _write_aggregate(root: Path, entries: list[dict]) -> None:
    agg = root / "knowledge" / "sources" / "local"
    agg.mkdir(parents=True, exist_ok=True)
    (agg / "entities.yaml").write_text(yaml.safe_dump({"entities": entries}), encoding="utf-8")


def _write_dataset_md(root: Path, slug: str, ident: str) -> None:
    d = root / "entities" / "datasets"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slug}.md").write_text(
        f'---\nid: "{ident}"\nkind: "dataset"\ntitle: "{ident}"\n'
        'origin: "external"\naccess:\n  level: "public"\n  verified: false\n---\n',
        encoding="utf-8",
    )


def test_lone_stub_warns(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    _write_aggregate(
        tmp_path,
        [
            {
                "canonical_id": "concept:lonely",
                "kind": "concept",
                "title": "Lonely",
                "source_path": "knowledge/sources/local/entities.yaml",
            }
        ],
    )
    results = list(check_lone_aggregate_stub(ctx))
    assert len(results) == 1
    assert results[0].severity is Severity.WARN
    assert results[0].rule == "lone-aggregate-stub"
    assert "concept:lonely" in results[0].message


def test_shadowed_stub_not_flagged_here(tmp_path: Path) -> None:
    # A shadowed stub is a collision -> forbidden-second-declaration's surface, not this
    # check's (single-surface principle).
    ctx = _ctx(tmp_path)
    _write_dataset_md(tmp_path, "shadowed", "dataset:shadowed")
    _write_aggregate(
        tmp_path,
        [
            {
                "canonical_id": "dataset:shadowed",
                "kind": "dataset",
                "title": "Shadowed",
                "origin": "external",
                "access": {"level": "public", "verified": False},
                "source_path": "knowledge/sources/local/entities.yaml",
            }
        ],
    )
    assert list(check_lone_aggregate_stub(ctx)) == []


def test_real_owner_no_aggregate_not_flagged(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    _write_dataset_md(tmp_path, "real", "dataset:real")
    assert list(check_lone_aggregate_stub(ctx)) == []


def test_check_registered_via_canonical_loader() -> None:
    # Real wiring test: clear the registry, drop the cached module so
    # _load_canonical_checks() must re-import it from CANONICAL_CHECK_MODULES, and
    # assert the @Check ran. Importing the check at module top would register it even
    # if the tuple entry were missing -- this proves the tuple entry, not the import.
    import sys

    from science_tool.validate.checks import (
        CANONICAL_CHECKS,
        _load_canonical_checks,
        clear_checks_for_tests,
    )

    original_entries = list(CANONICAL_CHECKS)
    module_name = "science_tool.validate.checks.aggregate_stub"
    original_module = sys.modules.get(module_name)
    try:
        clear_checks_for_tests()
        sys.modules.pop(module_name, None)
        _load_canonical_checks()
        entries = [e for e in CANONICAL_CHECKS if e.fn.__name__ == "check_lone_aggregate_stub"]
        assert len(entries) == 1
        assert entries[0].order == 51
    finally:
        CANONICAL_CHECKS[:] = original_entries
        if original_module is None:
            sys.modules.pop(module_name, None)
