# science/tests/test_spec_entity_s3a.py
"""S3a guards: `spec` is creatable, importable, and enters the S2 curation loop.

Each test here would FAIL before the science-model descriptor change (Task 1):
`resolve_path_policy("spec")` raises `Unsupported source-authored entity kind: spec`
until the kind has a home/strategy. They lock in the zero-breakage claim.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.entities import create_entity
from science_tool.entity_import import plan_import


def _project(root: Path) -> Path:
    # Create the project in a SUBDIRECTORY of tmp_path so callers can save the import
    # plan under tmp_path itself — i.e. OUTSIDE the project root, as the design requires.
    root.mkdir(parents=True, exist_ok=True)
    (root / "science.yaml").write_text(
        "name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8"
    )
    return root


def _loose(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_science_entity_create_spec_writes_under_entities_specs(tmp_path: Path) -> None:
    root = _project(tmp_path / "project")

    create_entity(root, "spec", "My Design Doc")

    dest = root / "entities" / "specs" / "0001-my-design-doc.md"
    assert dest.is_file()
    frontmatter, _body = _split(dest.read_text(encoding="utf-8"))
    assert frontmatter["id"] == "spec:0001-my-design-doc"
    assert frontmatter["kind"] == "spec"
    assert frontmatter["status"] == "active"


def test_plan_import_spec_proposes_numeric_id_and_home(tmp_path: Path) -> None:
    root = _project(tmp_path / "project")
    source = _loose(root, "docs/loose.md", "# My Spec\n\nbody\n")

    plan = plan_import(root, source, kind="spec")

    assert plan.entity_id == "spec:0001-my-spec"
    assert plan.dest_rel == "entities/specs/0001-my-spec.md"
    assert plan.status == "active"


def _split(text: str) -> tuple[dict, str]:
    assert text.startswith("---\n")
    _, fm, body = text.split("---\n", 2)
    return yaml.safe_load(fm), body


def test_cli_import_spec_roundtrip_rewrites_link_and_reports_manual_hit(tmp_path: Path) -> None:
    import json

    from click.testing import CliRunner

    from science_tool.cli import main

    root = _project(tmp_path / "project")
    source = _loose(root, "docs/loose.md", "# My Spec\n\nbody\n")

    # A structured referrer: a markdown link to the loose doc gets repointed on apply.
    referrer = root / "entities" / "questions" / "0001-ref.md"
    referrer.parent.mkdir(parents=True, exist_ok=True)
    referrer.write_text(
        "---\nid: question:0001-ref\nkind: question\ntitle: Ref\nstatus: active\n"
        "related: []\nsource_refs: []\n---\n\nSee [design](../../docs/loose.md).\n",
        encoding="utf-8",
    )

    # A prose-only path mention: reported as a manual hit, never rewritten.
    (root / "notes.md").write_text("The design lives at docs/loose.md for now.\n", encoding="utf-8")

    plan_path = tmp_path / "p.json"  # OUTSIDE the project tree (tmp_path is root's parent)
    runner = CliRunner()

    preview = runner.invoke(
        main,
        ["entities", "import", str(source), "--kind", "spec",
         "--project-root", str(root), "--save-plan", str(plan_path)],
    )
    assert preview.exit_code == 0, preview.output

    # The preview JSON surfaces the prose mention as a manual hit.
    preview_payload = json.loads(preview.output)
    manual_files = {hit["rel_path"] for hit in preview_payload["ref_report"]["manual"]}
    assert "notes.md" in manual_files

    apply = runner.invoke(
        main,
        ["entities", "import", "--apply-plan", str(plan_path), "--project-root", str(root)],
    )
    assert apply.exit_code == 0, apply.output

    # The spec entity landed; the loose source is gone.
    assert (root / "entities" / "specs" / "0001-my-spec.md").is_file()
    assert not source.exists()

    # The structured markdown link was rewritten to the exact new relative path.
    assert "[design](../specs/0001-my-spec.md)" in referrer.read_text(encoding="utf-8")
    assert "docs/loose.md" not in referrer.read_text(encoding="utf-8")


def test_created_spec_enters_eligible_corpus(tmp_path: Path) -> None:
    from science_tool.curate.rotation import eligible_corpus

    root = _project(tmp_path / "project")
    create_entity(root, "spec", "My Design Doc")

    ids = {e.id for e in eligible_corpus(root)}
    assert "spec:0001-my-design-doc" in ids


def test_review_entity_stamps_last_reviewed_on_an_imported_spec(tmp_path: Path) -> None:
    # The design requires exercising the curation loop on an IMPORTED spec, not only a
    # created one: import + apply first, then review the resulting entity id.
    from datetime import date

    from science_tool.entity_import import apply_import
    from science_tool.entity_review import review_entity

    root = _project(tmp_path / "project")
    source = _loose(root, "docs/loose.md", "# My Spec\n\nbody\n")
    plan = plan_import(root, source, kind="spec")
    apply_import(root, plan)

    path, changed = review_entity(
        root, plan.entity_id, note="Read; no change.", today=date(2026, 7, 18)
    )

    assert changed is True
    frontmatter, _body = _split(path.read_text(encoding="utf-8"))
    assert frontmatter["review_state"]["last_reviewed"] == "2026-07-18"
    assert frontmatter["review_state"]["last_review_note"] == "Read; no change."
