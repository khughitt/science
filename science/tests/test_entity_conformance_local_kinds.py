from __future__ import annotations

from pathlib import Path

from science_tool.validate.checks.entity_conformance import (
    check_entity_filename_conformance,
    check_entity_location_coherence,
)
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

_LOCAL_PROFILE = """\
name: t-local
imports:
  - core
strictness: typed-extension
entity_kinds:
  - name: design
    canonical_prefix: design
    layer: layer/local
    description: Design.
relation_kinds: []
"""


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _ctx(root: Path) -> ValidateContext:
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _seed_profile(root: Path, *, layout_version: int) -> None:
    _write(
        root,
        "science.yaml",
        f"name: t\nlayout_version: {layout_version}\nknowledge_profiles:\n  local: local\n",
    )
    _write(root, "knowledge/sources/local/manifest.yaml", _LOCAL_PROFILE)


def test_local_kind_stranded_in_doc_is_flagged(tmp_path: Path) -> None:
    _seed_profile(tmp_path, layout_version=3)
    _write(tmp_path, "doc/design/x.md", '---\nid: "design:x"\ntype: design\n---\nb\n')
    results = list(check_entity_location_coherence(_ctx(tmp_path)))
    msgs = [r.message for r in results]
    assert any("design entity outside its home" in m for m in msgs)


def test_local_kind_stranded_severity_is_version_gated(tmp_path: Path) -> None:
    # v2 → WARN (transition); v3 → ERROR (cutover). Same stranded file.
    _seed_profile(tmp_path, layout_version=2)
    _write(tmp_path, "doc/design/x.md", '---\nid: "design:x"\ntype: design\n---\nb\n')
    warn = [r for r in check_entity_location_coherence(_ctx(tmp_path)) if "outside its home" in r.message]
    assert warn and all(r.severity is Severity.WARN for r in warn)

    _seed_profile(tmp_path, layout_version=3)
    err = [r for r in check_entity_location_coherence(_ctx(tmp_path)) if "outside its home" in r.message]
    assert err and all(r.severity is Severity.ERROR for r in err)


def test_local_kind_nonconforming_filename_flagged(tmp_path: Path) -> None:
    # A numeric-strategy local kind whose file is not NNNN-slug must be flagged.
    _seed_profile(tmp_path, layout_version=3)
    _write(
        tmp_path,
        "entities/design/bad.md",
        '---\nid: "design:bad"\ntype: design\ntitle: Bad\nstatus: active\n'
        'created: "2026-01-01"\nupdated: "2026-01-01"\n---\nb\n',
    )
    msgs = [r.message for r in check_entity_filename_conformance(_ctx(tmp_path))]
    assert any("non-conforming design filename 'bad.md'" in m for m in msgs)


def test_local_kind_conforming_filename_is_clean(tmp_path: Path) -> None:
    _seed_profile(tmp_path, layout_version=3)
    _write(
        tmp_path,
        "entities/design/0001-good.md",
        '---\nid: "design:0001-good"\ntype: design\ntitle: Good\nstatus: active\n'
        'created: "2026-01-01"\nupdated: "2026-01-01"\n---\nb\n',
    )
    msgs = [r.message for r in check_entity_filename_conformance(_ctx(tmp_path))]
    assert not any("non-conforming design" in m for m in msgs)


def test_core_and_local_stranded_both_flagged(tmp_path: Path) -> None:
    # With a local profile loaded, BOTH a stranded core kind and a stranded local
    # kind must be flagged (project-awareness must not hide core kinds).
    _seed_profile(tmp_path, layout_version=3)
    _write(tmp_path, "doc/design/x.md", '---\nid: "design:x"\ntype: design\n---\nb\n')
    _write(tmp_path, "doc/questions/q.md", '---\nid: "question:q"\ntype: question\n---\nb\n')
    msgs = [r.message for r in check_entity_location_coherence(_ctx(tmp_path))]
    assert any("design entity outside its home" in m for m in msgs)
    assert any("question entity outside its home" in m for m in msgs)
