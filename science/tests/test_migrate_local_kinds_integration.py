from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from science_tool.entity_layout_migration import migrate_layout

# Real migrate_layout return shape (verified against entity_layout_migration.py):
#   report["applied"]              bool — mirrors the `apply` argument
#   report["moves"]                list[dict] — one entry per file moved
#   report["singletons"]           list[dict]
#   report["id_map"]               dict[str, str] — old_id -> new_id
#   report["collisions"]           list[dict]
#   report["unresolved_references"] dict[str, list[str]] — file_rel -> [token, ...]
#   report["undated_entities"]     list[dict]
#   report["graph_validation"]     str == "passed"  — ONLY present when apply=True
#                                  and the post-move graph audit succeeds.
#                                  Not present in dry-run reports.

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

_SCIENCE_YAML = "name: t\nlayout_version: 2\nknowledge_profiles:\n  local: local\n"


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"],
        cwd=root,
        check=True,
    )


def test_migrate_applies_local_kind_and_bumps_version(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", _SCIENCE_YAML)
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", _LOCAL_PROFILE)
    # one core kind + one local kind, with a cross-reference core -> local.
    # Slug derivation for "h01-x": _LEGACY_LOCAL_RE strips "h01" prefix, remainder
    # "x" is too short (<2 chars) so slug falls through to the stem "h01-x".
    # New id: "hypothesis:0001-h01-x", path: entities/hypotheses/0001-h01-x.md
    _write(
        tmp_path,
        "specs/hypotheses/h01-x.md",
        '---\nid: "hypothesis:h01-x"\ntype: hypothesis\ncreated: "2026-01-01"\n'
        'title: X\nstatus: proposed\nupdated: "2026-01-01"\nrelated: ["design:foo"]\n---\nSee design:foo.\n',
    )
    # design:foo -> design:0001-foo (slug "foo" is 3 chars, fine)
    # path: entities/design/0001-foo.md
    _write(
        tmp_path,
        "doc/design/foo.md",
        '---\nid: "design:foo"\ntype: design\ncreated: "2026-01-02"\n'
        'title: Foo\nstatus: active\nupdated: "2026-01-02"\n---\nbody\n',
    )
    _git_init(tmp_path)

    report = migrate_layout(tmp_path, apply=True)

    assert report["applied"] is True
    # graph_validation is only set after a successful post-move audit (apply=True path).
    assert report.get("graph_validation") == "passed"
    # local-kind file moved + renumbered
    assert (tmp_path / "entities/design/0001-foo.md").is_file()
    assert not (tmp_path / "doc/design/foo.md").exists()
    # core kind file moved + renumbered (stem "h01-x" → slug "h01-x" → 0001-h01-x)
    assert (tmp_path / "entities/hypotheses/0001-h01-x.md").is_file()
    assert not (tmp_path / "specs/hypotheses/h01-x.md").exists()
    # core -> local reference rewritten everywhere (frontmatter + body)
    h = (tmp_path / "entities/hypotheses/0001-h01-x.md").read_text()
    assert "design:0001-foo" in h
    assert "design:foo" not in h
    # version bumped
    manifest = yaml.safe_load((tmp_path / "science.yaml").read_text())
    assert manifest["layout_version"] == 3


def test_migrate_dry_run_surfaces_unmapped_local_ref(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", _SCIENCE_YAML)
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", _LOCAL_PROFILE)
    _write(
        tmp_path,
        "doc/design/foo.md",
        '---\nid: "design:foo"\ntype: design\ncreated: "2026-01-02"\n'
        'title: Foo\nstatus: active\nupdated: "2026-01-02"\n---\nDangling design:ghost.\n',
    )
    _git_init(tmp_path)

    report = migrate_layout(tmp_path, apply=False)
    # Under Unit A a dangling ref in a prose BODY is a non-blocking warning, surfaced
    # in unresolved_warnings (dict[str, list[str]]: file_rel -> [token, ...]); only
    # structural (audited-field) dangling refs go to unresolved_references.
    flat = [t for toks in report["unresolved_warnings"].values() for t in toks]
    assert "design:ghost" in flat  # dry-run surfaces the unmapped local-kind ref
