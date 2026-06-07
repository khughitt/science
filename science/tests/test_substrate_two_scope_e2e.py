from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.registry import RegistryBuilder
from science_tool.graph.identity_table import build_identity_table
from science_tool.graph.migrate import audit_project_sources
from science_tool.graph.sources import load_project_sources

_COMMONS_FIXTURE = Path(__file__).parent / "fixtures" / "commons" / "valid"
_SHARED_ID = "topic:single-cell-foundation-models"


def _build_commons(tmp_path: Path) -> Path:
    commons_root = tmp_path / "commons"
    shutil.copytree(_COMMONS_FIXTURE, commons_root)
    RegistryBuilder(commons_root, CommonsEntityAdapter(commons_root)).rebuild()
    return commons_root


def _project_owning_and_referencing_shared_id(tmp_path: Path) -> Path:
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    manifest = project_root / "knowledge" / "sources" / "local" / "manifest.yaml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("", encoding="utf-8")
    # A LOCAL owner file for the same id commons owns.
    topic = project_root / "entities" / "topics" / "single-cell-foundation-models.md"
    topic.parent.mkdir(parents=True)
    topic.write_text(f'---\nid: "{_SHARED_ID}"\ntype: "topic"\ntitle: "SCFM (local)"\n---\n', encoding="utf-8")
    # A hypothesis that references the shared id with a BARE ref.
    hyp = project_root / "entities" / "hypotheses" / "h1.md"
    hyp.parent.mkdir(parents=True)
    hyp.write_text(
        f'---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\nrelated: ["{_SHARED_ID}"]\n---\n',
        encoding="utf-8",
    )
    return project_root


def test_load_produces_two_scope_identity_table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = _project_owning_and_referencing_shared_id(tmp_path)

    sources = load_project_sources(project_root)
    scopes = build_identity_table(sources).owner_scopes_by_id()[_SHARED_ID]
    assert "commons" in scopes
    assert len(scopes) == 2  # this-project owner + commons owner


def test_audit_emits_ambiguous_reference_for_two_scope_bare_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = _project_owning_and_referencing_shared_id(tmp_path)

    sources = load_project_sources(project_root)
    rows, has_failures = audit_project_sources(sources)
    ambiguous = [r for r in rows if r["check"] == "ambiguous_reference"]
    assert has_failures is True
    assert len(ambiguous) == 1
    assert ambiguous[0]["target"] == _SHARED_ID
    assert ambiguous[0]["source"] == "hypothesis:h1"
