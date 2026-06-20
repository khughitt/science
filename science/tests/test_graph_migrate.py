from __future__ import annotations

import shutil
from pathlib import Path

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.registry import RegistryBuilder
from science_tool.graph.migrate import audit_project_sources
from science_tool.graph.sources import load_project_sources


def test_audit_unresolved_topic_includes_commons_hint(tmp_path: Path, monkeypatch) -> None:
    fixture_root = Path(__file__).parent / "fixtures" / "commons" / "valid"
    commons_root = tmp_path / "commons"
    shutil.copytree(fixture_root, commons_root)
    RegistryBuilder(commons_root, CommonsEntityAdapter(commons_root)).rebuild()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))

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
type: "hypothesis"
title: "H1"
related: ["topic:does-not-exist"]
source_refs: []
created: "2026-03-12"
updated: "2026-03-12"
---

Body.
""",
        encoding="utf-8",
    )

    sources = load_project_sources(project)
    rows, _ = audit_project_sources(sources)

    bad = next(row for row in rows if row["target"] == "topic:does-not-exist")
    assert bad["check"] == "unresolved_reference"
    assert "topics/does-not-exist.md" in bad["details"]
    assert "science commons promote" in bad["details"]


def _scaffold_project_with_related(project: Path, related: str) -> None:
    project.mkdir()
    (project / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    manifest_path = project / "knowledge" / "sources" / "local" / "manifest.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text("", encoding="utf-8")
    hypothesis_path = project / "entities" / "hypotheses" / "h1.md"
    hypothesis_path.parent.mkdir(parents=True)
    hypothesis_path.write_text(
        f"""---
id: "hypothesis:h1"
type: "hypothesis"
title: "H1"
related: [{related}]
source_refs: []
created: "2026-03-12"
updated: "2026-03-12"
---

Body.
""",
        encoding="utf-8",
    )


def test_audit_unresolved_nonpromotable_kind_omits_promote_hint(tmp_path: Path) -> None:
    """A non-promotable kind (e.g. question) must not be told to run commons
    promote; the hint should point to prose linking instead."""
    project = tmp_path / "project"
    _scaffold_project_with_related(project, '"question:does-not-exist"')

    sources = load_project_sources(project)
    rows, _ = audit_project_sources(sources)

    bad = next(row for row in rows if row["target"] == "question:does-not-exist")
    assert bad["check"] == "unresolved_reference"
    assert "science commons promote" not in bad["details"]
    assert "prose" in bad["details"].lower()


def test_audit_unresolved_cross_project_address_omits_promote_hint(tmp_path: Path) -> None:
    """An UNREGISTERED cross-project prefix in `related` (no matching peer) still
    fails, and must not suggest commons promote; point to prose linking."""
    project = tmp_path / "project"
    _scaffold_project_with_related(project, '"health-meta:research-question:foo"')

    sources = load_project_sources(project)
    rows, _ = audit_project_sources(sources)

    bad = next(row for row in rows if row["target"] == "health-meta:research-question:foo")
    assert bad["check"] == "unresolved_reference"
    assert "science commons promote" not in bad["details"]
    assert "prose" in bad["details"].lower()


def _scaffold_project_with_related_and_peer(project: Path, related: str, peer_id: str) -> None:
    project.mkdir()
    (project / "science.yaml").write_text(
        "name: demo\n"
        "id: demo\n"
        "knowledge_profiles:\n  local: local\n"
        f"peers:\n  - id: {peer_id}\n    path: ../{peer_id}\n",
        encoding="utf-8",
    )
    manifest_path = project / "knowledge" / "sources" / "local" / "manifest.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text("", encoding="utf-8")
    hypothesis_path = project / "entities" / "hypotheses" / "h1.md"
    hypothesis_path.parent.mkdir(parents=True)
    hypothesis_path.write_text(
        f"""---
id: "hypothesis:h1"
type: "hypothesis"
title: "H1"
related: [{related}]
source_refs: []
created: "2026-03-12"
updated: "2026-03-12"
---

Body.
""",
        encoding="utf-8",
    )


def test_audit_registered_peer_cross_project_ref_accepted(tmp_path: Path) -> None:
    """A scoped `<peer>:<kind>:<slug>` ref whose project_id is a REGISTERED peer is
    accepted (design §B3a forward-compatible form; local resolution deferred to
    federation t068) — no unresolved_reference fail row, consistent with refs check."""
    project = tmp_path / "project"
    _scaffold_project_with_related_and_peer(project, '"cancer-meta:question:001-foo"', "cancer-meta")

    sources = load_project_sources(project)
    rows, has_failures = audit_project_sources(sources)

    assert not any(row["target"] == "cancer-meta:question:001-foo" and row["status"] == "fail" for row in rows)
    assert not has_failures


def test_audit_unresolved_dataset_includes_dataset_commons_hint(tmp_path: Path, monkeypatch) -> None:
    fixture_root = Path(__file__).parent / "fixtures" / "commons" / "valid"
    commons_root = tmp_path / "commons"
    shutil.copytree(fixture_root, commons_root)
    RegistryBuilder(commons_root, CommonsEntityAdapter(commons_root)).rebuild()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))

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
type: "hypothesis"
title: "H1"
related: ["dataset:does-not-exist"]
source_refs: []
created: "2026-03-12"
updated: "2026-03-12"
---

Body.
""",
        encoding="utf-8",
    )

    sources = load_project_sources(project)
    rows, _ = audit_project_sources(sources)

    bad = next(row for row in rows if row["target"] == "dataset:does-not-exist")
    assert bad["check"] == "unresolved_reference"
    assert "datasets/does-not-exist/entity.md" in bad["details"]
    assert "science commons promote dataset --slug does-not-exist --from <project>" in bad["details"]
