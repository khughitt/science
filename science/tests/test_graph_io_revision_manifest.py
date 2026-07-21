from pathlib import Path

import pytest

from science_tool.graph.io import build_input_manifest


def _seed_project(root: Path, science_yaml: str) -> None:
    (root / "science.yaml").write_text(science_yaml, encoding="utf-8")
    (root / "doc" / "reports").mkdir(parents=True)
    (root / "doc" / "reports" / "health-report.json").write_text('{"generated": true}\n', encoding="utf-8")
    (root / "doc" / "notes.md").write_text("# Notes\n", encoding="utf-8")
    (root / "knowledge").mkdir()


def test_entities_dir_is_in_the_walk_set(tmp_path: Path) -> None:
    """`entities/` MUST be walked.

    It was omitted from `include_dirs` for two months: a project could add a brand-new
    hypothesis and `science graph diff` would still report the graph "up to date", so
    /science:update-graph's "no files stale -> stop" gate would skip a needed rebuild and
    leave the entity permanently absent from the graph (fb-2026-07-11-016, -023).

    The fix landed in bbedacbe WITHOUT a guard -- the original report even noted that no
    test asserted anything about `entities/`. This is that guard: delete `pp.entities_dir`
    from `build_input_manifest` and this test must go red.
    """
    _seed_project(tmp_path, "name: fixture\nprofile: research\n")
    (tmp_path / "entities" / "hypotheses").mkdir(parents=True)
    (tmp_path / "entities" / "hypotheses" / "0001-x.md").write_text(
        "---\nid: hypothesis:0001-x\nkind: hypothesis\n---\n", encoding="utf-8"
    )

    manifest = build_input_manifest(tmp_path / "knowledge" / "graph.trig")

    assert "entities" in manifest["walked"]
    assert "entities/hypotheses/0001-x.md" in manifest["files"]


def test_build_input_manifest_excludes_configured_generated_report(tmp_path: Path) -> None:
    _seed_project(
        tmp_path,
        "name: fixture\n"
        "profile: research\n"
        "graph:\n"
        "  revision_manifest_excludes:\n"
        "    - doc/reports/health-report.json\n",
    )

    manifest = build_input_manifest(tmp_path / "knowledge" / "graph.trig")["files"]

    assert "doc/notes.md" in manifest
    assert "doc/reports/health-report.json" not in manifest


def test_build_input_manifest_excludes_configured_wildcard_report_pattern(tmp_path: Path) -> None:
    _seed_project(
        tmp_path,
        "name: fixture\n"
        "profile: research\n"
        "graph:\n"
        "  revision_manifest_excludes:\n"
        "    - doc/reports/*.json\n",
    )

    manifest = build_input_manifest(tmp_path / "knowledge" / "graph.trig")["files"]

    assert "doc/notes.md" in manifest
    assert "doc/reports/health-report.json" not in manifest


def test_build_input_manifest_keeps_report_without_configured_exclude(tmp_path: Path) -> None:
    _seed_project(tmp_path, "name: fixture\nprofile: research\n")

    manifest = build_input_manifest(tmp_path / "knowledge" / "graph.trig")["files"]

    assert "doc/reports/health-report.json" in manifest


def test_build_input_manifest_excludes_curation_ledgers_by_default(tmp_path: Path) -> None:
    """Curation ledgers under `doc/curations/` are transient tidying logs that
    contribute no triples; every project must inherit the exclude without setting
    the knob (fb-2026-07-17-001, D2 Option C). No `graph.revision_manifest_excludes`
    is configured here."""
    _seed_project(tmp_path, "name: fixture\nprofile: research\n")
    (tmp_path / "doc" / "curations").mkdir(parents=True)
    (tmp_path / "doc" / "curations" / "curation-sweep-2026-07-16.md").write_text(
        "---\ndoc_kind: curation-sweep\n---\n", encoding="utf-8"
    )

    manifest = build_input_manifest(tmp_path / "knowledge" / "graph.trig")["files"]

    assert "doc/curations/curation-sweep-2026-07-16.md" not in manifest


def test_build_input_manifest_excludes_next_steps_ledgers_but_keeps_durable_meta(tmp_path: Path) -> None:
    """The transient/durable split is NOT directory-aligned: `doc/meta/` mixes
    transient `*-next-steps.md` ledgers with durable crosswalks/memos, so the default
    glob is `doc/meta/*-next-steps.md`, not `doc/meta/*` (fb-2026-07-17-001 ASK b)."""
    _seed_project(tmp_path, "name: fixture\nprofile: research\n")
    (tmp_path / "doc" / "meta").mkdir(parents=True)
    (tmp_path / "doc" / "meta" / "2026-07-16-next-steps.md").write_text("# Next steps\n", encoding="utf-8")
    (tmp_path / "doc" / "meta" / "2026-06-19-case-definition-crosswalk.md").write_text("# Crosswalk\n", encoding="utf-8")

    manifest = build_input_manifest(tmp_path / "knowledge" / "graph.trig")["files"]

    assert "doc/meta/2026-07-16-next-steps.md" not in manifest
    assert "doc/meta/2026-06-19-case-definition-crosswalk.md" in manifest


def test_build_input_manifest_unions_configured_excludes_with_defaults(tmp_path: Path) -> None:
    """A project that adds its own exclude still inherits the ledger defaults, and a
    project that re-declares the default set (as post-acute-infection does) is idempotent
    — no duplication error."""
    _seed_project(
        tmp_path,
        "name: fixture\n"
        "profile: research\n"
        "graph:\n"
        "  revision_manifest_excludes:\n"
        "    - doc/reports/*.json\n",
    )
    (tmp_path / "doc" / "curations").mkdir(parents=True)
    (tmp_path / "doc" / "curations" / "curation-sweep-2026-07-16.md").write_text("# Sweep\n", encoding="utf-8")

    manifest = build_input_manifest(tmp_path / "knowledge" / "graph.trig")["files"]

    # configured custom exclude honored
    assert "doc/reports/health-report.json" not in manifest
    # default ledger exclude still applies alongside the project's own list
    assert "doc/curations/curation-sweep-2026-07-16.md" not in manifest
    # durable prose untouched
    assert "doc/notes.md" in manifest


def test_build_input_manifest_includes_project_readme(tmp_path: Path) -> None:
    _seed_project(tmp_path, "name: fixture\nprofile: research\n")
    (tmp_path / "README.md").write_text("# Fixture\n", encoding="utf-8")

    manifest = build_input_manifest(tmp_path / "knowledge" / "graph.trig")["files"]

    assert "README.md" in manifest


def test_build_input_manifest_excludes_python_bytecode_cache(tmp_path: Path) -> None:
    _seed_project(tmp_path, "name: fixture\nprofile: software\n")
    package = tmp_path / "src" / "tooling"
    cache = package / "__pycache__"
    cache.mkdir(parents=True)
    (package / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (cache / "module.cpython-314.pyc").write_bytes(b"bytecode")

    manifest = build_input_manifest(tmp_path / "knowledge" / "graph.trig")["files"]

    assert "src/tooling/module.py" in manifest
    assert "src/tooling/__pycache__/module.cpython-314.pyc" not in manifest


def test_build_input_manifest_rejects_absolute_exclude_pattern(tmp_path: Path) -> None:
    _seed_project(
        tmp_path,
        "name: fixture\n"
        "profile: research\n"
        "graph:\n"
        "  revision_manifest_excludes:\n"
        "    - /tmp/outside.json\n",
    )

    with pytest.raises(ValueError, match="revision_manifest_excludes"):
        build_input_manifest(tmp_path / "knowledge" / "graph.trig")


@pytest.mark.parametrize(
    "entry",
    [
        '    - ""\n',
        "    - 12\n",
        "    - ../outside.json\n",
    ],
)
def test_build_input_manifest_rejects_invalid_exclude_pattern_entries(tmp_path: Path, entry: str) -> None:
    _seed_project(
        tmp_path,
        "name: fixture\n"
        "profile: research\n"
        "graph:\n"
        "  revision_manifest_excludes:\n"
        f"{entry}",
    )

    with pytest.raises(ValueError, match="revision_manifest_excludes"):
        build_input_manifest(tmp_path / "knowledge" / "graph.trig")


def test_build_input_manifest_rejects_falsy_non_list_exclude_config(tmp_path: Path) -> None:
    _seed_project(
        tmp_path,
        "name: fixture\n"
        "profile: research\n"
        "graph:\n"
        "  revision_manifest_excludes: false\n",
    )

    with pytest.raises(ValueError, match="revision_manifest_excludes"):
        build_input_manifest(tmp_path / "knowledge" / "graph.trig")
