from __future__ import annotations

import json
import shutil
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main
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
kind: "hypothesis"
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
kind: "hypothesis"
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
kind: "hypothesis"
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
kind: "hypothesis"
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


def test_audit_paper_datasets_bare_freetext_is_descriptive(tmp_path: Path) -> None:
    """A paper's `datasets:` field is descriptive provenance: bare free-text names
    (e.g. "UniRef50") are NOT structural dataset references and must not produce
    audit failures. An explicit `dataset:<slug>` ref in the same field still resolves
    (and still fails when the dataset entity is absent)."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    manifest_path = project / "knowledge" / "sources" / "local" / "manifest.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text("", encoding="utf-8")
    paper_path = project / "entities" / "papers" / "Adams2025.md"
    paper_path.parent.mkdir(parents=True)
    paper_path.write_text(
        """---
id: "paper:Adams2025"
kind: "paper"
title: "A paper that uses several datasets"
status: "active"
datasets:
  - UniRef50
  - Swiss-Prot
  - TAPE (secondary structure)
  - "dataset:does-not-exist"
source_refs: []
created: "2026-04-23"
updated: "2026-04-23"
---

Body.
""",
        encoding="utf-8",
    )

    sources = load_project_sources(project)
    rows, _ = audit_project_sources(sources)

    dataset_field_fails = [
        row for row in rows if row.get("field") == "datasets" and row.get("status") == "fail"
    ]
    bad_targets = {row["target"] for row in dataset_field_fails}
    # Bare free-text names are descriptive, not references → no failure rows.
    assert "UniRef50" not in bad_targets
    assert "Swiss-Prot" not in bad_targets
    assert "TAPE (secondary structure)" not in bad_targets
    # An explicit dataset: ref still audits and fails when absent.
    assert "dataset:does-not-exist" in bad_targets


def _write_paper_dataset_project(root: Path, *, conflict: bool = False) -> Path:
    root.mkdir()
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    (root / "entities" / "papers").mkdir(parents=True)
    paper = root / "entities" / "papers" / "smith.md"
    if conflict:
        paper.write_text(
            "\n".join(
                [
                    "---",
                    "id: paper:smith",
                    "kind: paper",
                    "dataset_usage:",
                    "  - ref: dataset:gtex-v8",
                    "    role: cited",
                    "datasets:",
                    "  - dataset:gtex-v8",
                    "---",
                    "",
                    "Body.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    else:
        paper.write_text(
            "\n".join(
                [
                    "---",
                    "id: paper:smith",
                    "kind: paper",
                    "datasets:",
                    "  - dataset:gtex-v8",
                    "---",
                    "",
                    "Body.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    return paper


def test_graph_migrate_paper_datasets_dry_run_json_exit_10_for_pending(tmp_path: Path) -> None:
    root = tmp_path / "project"
    paper = _write_paper_dataset_project(root)

    result = CliRunner().invoke(
        main,
        ["graph", "migrate-paper-datasets", "--project-root", str(root), "--format", "json"],
    )

    assert result.exit_code == 10
    payload = json.loads(result.output)
    assert payload["apply"] is False
    assert payload["changed_files"] == [str(paper)]
    assert payload["conflict_count"] == 0
    assert "datasets:" in paper.read_text(encoding="utf-8")


def test_graph_migrate_paper_datasets_apply_rewrites_and_exits_zero(tmp_path: Path) -> None:
    root = tmp_path / "project"
    paper = _write_paper_dataset_project(root)

    result = CliRunner().invoke(
        main,
        ["graph", "migrate-paper-datasets", "--project-root", str(root), "--format", "json", "--apply"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["apply"] is True
    assert payload["changed_files"] == [str(paper)]
    text = paper.read_text(encoding="utf-8")
    assert "datasets:" not in text
    assert "dataset_usage:" in text


def test_graph_migrate_paper_datasets_conflict_exits_20_and_leaves_file(tmp_path: Path) -> None:
    root = tmp_path / "project"
    paper = _write_paper_dataset_project(root, conflict=True)
    original = paper.read_text(encoding="utf-8")

    result = CliRunner().invoke(
        main,
        ["graph", "migrate-paper-datasets", "--project-root", str(root), "--format", "json", "--apply"],
    )

    assert result.exit_code == 20
    payload = json.loads(result.output)
    assert payload["conflicts"][0]["reason"] == "role-conflict"
    assert paper.read_text(encoding="utf-8") == original


def test_graph_migrate_paper_datasets_table_mentions_mode_and_conflicts(tmp_path: Path) -> None:
    root = tmp_path / "project"
    _write_paper_dataset_project(root, conflict=True)

    result = CliRunner().invoke(
        main,
        ["graph", "migrate-paper-datasets", "--project-root", str(root), "--format", "table"],
    )

    assert result.exit_code == 20
    assert "Paper Dataset Migration" in result.output
    assert "role-conflict" in result.output
