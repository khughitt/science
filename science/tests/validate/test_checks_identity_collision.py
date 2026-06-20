from __future__ import annotations

from pathlib import Path

import yaml
from science_model.source_ref import SourceRef

from science_tool.graph.identity_table import (
    IdentityDeclaration,
    IdentityTable,
    ParticipationMode,
)
from science_tool.validate.checks.identity_collision import (
    check_forbidden_second_declaration,
    graded_collisions,
)
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


def _owner(cid: str, *, path: str, deprecated: bool = False) -> IdentityDeclaration:
    return IdentityDeclaration(
        canonical_id=cid,
        participation_mode=ParticipationMode.OWNER,
        owner_scope="demo-project",
        adapter="markdown",
        source_ref=SourceRef(adapter_name="markdown", path=path),
        deprecated=deprecated,
    )


def test_graded_two_real_owners_is_error() -> None:
    table = IdentityTable(
        rows=[
            _owner("dataset:x", path="entities/datasets/x.md"),
            _owner("dataset:x", path="entities/datasets/x-dup.md"),
        ]
    )
    graded = graded_collisions(table)
    assert len(graded) == 1
    severity, collision = graded[0]
    assert severity is Severity.ERROR
    assert collision.canonical_id == "dataset:x"
    assert {r.source_ref.path for r in collision.rows} == {
        "entities/datasets/x.md",
        "entities/datasets/x-dup.md",
    }


def test_graded_transitional_shadow_is_warn() -> None:
    # A real markdown owner shadowed by a deprecated aggregate/datapackage stub is a
    # rollout state carried until §B5/§B4 — visible (WARN) but NOT a hard error.
    table = IdentityTable(
        rows=[
            _owner("dataset:x", path="entities/datasets/x.md"),
            _owner("dataset:x", path="knowledge/sources/local/entities.yaml", deprecated=True),
        ]
    )
    graded = graded_collisions(table)
    assert len(graded) == 1
    assert graded[0][0] is Severity.WARN


def test_graded_single_owner_is_not_a_collision() -> None:
    table = IdentityTable(rows=[_owner("dataset:x", path="entities/datasets/x.md")])
    assert graded_collisions(table) == []


def test_graded_two_deprecated_owners_is_warn() -> None:
    table = IdentityTable(
        rows=[
            _owner("dataset:x", path="a", deprecated=True),
            _owner("dataset:x", path="b", deprecated=True),
        ]
    )
    graded = graded_collisions(table)
    assert len(graded) == 1
    assert graded[0][0] is Severity.WARN


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
    (root / "knowledge" / "local").mkdir(parents=True, exist_ok=True)
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _write_dataset_md(root: Path, filename: str, ident: str) -> None:
    d = root / "entities" / "datasets"
    d.mkdir(parents=True, exist_ok=True)
    (d / filename).write_text(
        f'---\nid: "{ident}"\ntype: "dataset"\ntitle: "{ident} {filename}"\n'
        'origin: "external"\n'
        'access:\n  level: "public"\n  verified: false\n---\n',
        encoding="utf-8",
    )


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


def test_two_markdown_owners_flagged_error(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    _write_dataset_md(tmp_path, "x.md", "dataset:x")
    _write_dataset_md(tmp_path, "x-dup.md", "dataset:x")
    results = list(check_forbidden_second_declaration(ctx))
    assert len(results) == 1
    assert results[0].severity is Severity.ERROR
    assert "dataset:x" in results[0].message
    assert results[0].rule == "forbidden-second-declaration"


def test_markdown_owner_with_sibling_datapackage_not_flagged(tmp_path: Path) -> None:
    # The datapackage DEFERS to the markdown owner (Phase 1.5) -> one owner row ->
    # no collision.
    ctx = _ctx(tmp_path)
    _write_dataset_md(tmp_path, "x.md", "dataset:x")
    _write_datapackage(tmp_path, "x", "dataset:x")
    assert list(check_forbidden_second_declaration(ctx)) == []


def test_single_owner_not_flagged(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    _write_dataset_md(tmp_path, "x.md", "dataset:x")
    assert list(check_forbidden_second_declaration(ctx)) == []


# A deprecated entities.yaml aggregate stub is only discovered when the manifest
# keys the profile via `profiles:` (the aggregate scan root), NOT `knowledge_profiles:`
# (what the other tests' _MANIFEST sets), so the WARN path needs this manifest style.
_AGG_MANIFEST = "name: demo-project\nprofile: research\nprofiles: {local: local}\n"


def _agg_ctx(root: Path) -> ValidateContext:
    (root / "science.yaml").write_text(_AGG_MANIFEST, encoding="utf-8")
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _write_aggregate_stub(root: Path, ident: str, kind: str = "dataset") -> None:
    local = root / "knowledge" / "sources" / "local"
    local.mkdir(parents=True, exist_ok=True)
    (local / "entities.yaml").write_text(
        f"entities:\n  - canonical_id: {ident}\n    kind: {kind}\n    title: {ident}\n"
        "    profile: local\n    source_path: knowledge/sources/local/entities.yaml\n",
        encoding="utf-8",
    )


def test_aggregate_stub_shadow_flagged_warn(tmp_path: Path) -> None:
    # A real markdown owner shadowed by a DEPRECATED entities.yaml aggregate stub is a
    # transitional collision (§C3): one non-deprecated owner + one deprecated -> WARN,
    # visible but non-blocking, carried until §B5 retirement. Exercises the WARN grade
    # through the real loader end-to-end (the unit test only hand-builds the table).
    ctx = _agg_ctx(tmp_path)
    _write_dataset_md(tmp_path, "x.md", "dataset:x")
    _write_aggregate_stub(tmp_path, "dataset:x")
    results = list(check_forbidden_second_declaration(ctx))
    assert len(results) == 1
    assert results[0].severity is Severity.WARN
    assert "dataset:x" in results[0].message
    assert results[0].rule == "forbidden-second-declaration"


def test_check_registered_via_canonical_loader() -> None:
    # A real wiring test (mirrors test_overlay_of_check_registered_via_canonical_loader):
    # clear the registry, drop the cached module so _load_canonical_checks() must
    # re-import it from CANONICAL_CHECK_MODULES, and assert the @Check ran. Importing
    # the check at module top would register it even if the module string were missing
    # from the tuple — this proves the tuple entry, not the import.
    import sys

    from science_tool.validate.checks import (
        CANONICAL_CHECKS,
        _load_canonical_checks,
        clear_checks_for_tests,
    )

    original_entries = list(CANONICAL_CHECKS)
    module_name = "science_tool.validate.checks.identity_collision"
    original_module = sys.modules.get(module_name)
    try:
        clear_checks_for_tests()
        sys.modules.pop(module_name, None)
        _load_canonical_checks()
        entries = [e for e in CANONICAL_CHECKS if e.fn.__name__ == "check_forbidden_second_declaration"]
        assert len(entries) == 1
        assert entries[0].order == 50
    finally:
        CANONICAL_CHECKS[:] = original_entries
        if original_module is None:
            sys.modules.pop(module_name, None)
