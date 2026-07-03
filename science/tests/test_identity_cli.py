from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from science_model.frontmatter import parse_frontmatter
from science_tool.cli import main as science_cli
from science_tool.commons.assembly import ASSEMBLY_REGISTRY_ID, AssemblyEntry


_HG38_DIGEST = "g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp"


def _run(root: Path, *args: str):
    return CliRunner().invoke(
        science_cli,
        ["dataset", "identity", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(root), "SCIENCE_COMMONS_ROOT": str(root / "no-commons")},
    )


def _write_dataset(root: Path, slug: str, *, frontmatter: dict | None = None, body: str = "# Body\n") -> Path:
    fm = {
        "id": f"dataset:{slug}",
        "type": "dataset",
        "title": slug.title(),
        "status": "candidate",
    }
    if frontmatter:
        fm.update(frontmatter)
    path = root / "entities" / "datasets" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n" + body, encoding="utf-8")
    return path


def _frontmatter(path: Path) -> dict:
    parsed = parse_frontmatter(path)
    assert parsed is not None
    return parsed[0]


def test_resolve_writes_declared_unresolved_assembly(tmp_path: Path) -> None:
    path = _write_dataset(tmp_path, "x", frontmatter={"unrelated": {"kept": True}}, body="# Existing\n\nBody.\n")

    res = _run(tmp_path, "resolve", "dataset:x", "--taxon", "9606", "--assembly", "UNKNOWN")

    assert res.exit_code == 0, res.output
    fm = _frontmatter(path)
    assert fm["unrelated"] == {"kept": True}
    assert fm["identity_context"]["taxon"] == 9606
    assert fm["identity_context"]["assembly"] == {
        "label": "UNKNOWN",
        "registry": ASSEMBLY_REGISTRY_ID,
        "resolution_status": "declared_unresolved",
    }
    assert "# Existing\n\nBody." in path.read_text(encoding="utf-8")
    assert "declared_unresolved" in res.output


def test_resolve_writes_seqcol_digest_for_resolved_assembly(tmp_path: Path, monkeypatch) -> None:
    path = _write_dataset(tmp_path, "x")

    def fake_resolve_assembly(label_or_digest: str, *, registry_id: str, commons_root=None, data_root=None):
        assert label_or_digest == "hg38"
        assert registry_id == ASSEMBLY_REGISTRY_ID
        return AssemblyEntry(seqcol_digest=_HG38_DIGEST, label="hg38", accession="GCF_000001405.40")

    monkeypatch.setattr("science_tool.commons.assembly.resolve_assembly", fake_resolve_assembly)

    res = _run(tmp_path, "resolve", "dataset:x", "--assembly", "hg38")

    assert res.exit_code == 0, res.output
    assert _frontmatter(path)["identity_context"]["assembly"] == {
        "label": "hg38",
        "registry": ASSEMBLY_REGISTRY_ID,
        "seqcol_digest": _HG38_DIGEST,
        "resolution_status": "resolved",
    }


def test_resolve_is_idempotent_for_same_declaration(tmp_path: Path) -> None:
    path = _write_dataset(tmp_path, "x")

    first = _run(tmp_path, "resolve", "dataset:x", "--taxon", "9606", "--assembly", "UNKNOWN")
    after_first = path.read_text(encoding="utf-8")
    second = _run(tmp_path, "resolve", "dataset:x", "--taxon", "9606", "--assembly", "UNKNOWN")

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert path.read_text(encoding="utf-8") == after_first
    assert "unchanged dataset:x" in second.output


def test_resolve_batches_over_dataset_glob(tmp_path: Path) -> None:
    paths = [_write_dataset(tmp_path, "one"), _write_dataset(tmp_path, "two")]

    res = _run(tmp_path, "resolve", "dataset:*", "--taxon", "9606")

    assert res.exit_code == 0, res.output
    assert "updated dataset:one" in res.output
    assert "updated dataset:two" in res.output
    assert _frontmatter(paths[0])["identity_context"]["taxon"] == 9606
    assert _frontmatter(paths[1])["identity_context"]["taxon"] == 9606


def test_show_prints_current_identity_context(tmp_path: Path) -> None:
    _write_dataset(
        tmp_path,
        "x",
        frontmatter={
            "identity_context": {
                "taxon": 9606,
                "assembly": {"label": "UNKNOWN", "resolution_status": "declared_unresolved"},
            }
        },
    )

    res = _run(tmp_path, "show", "dataset:x")

    assert res.exit_code == 0, res.output
    assert "taxon: 9606" in res.output
    assert "resolution_status: declared_unresolved" in res.output


def test_suggest_emits_scaffold_without_editing(tmp_path: Path) -> None:
    path = _write_dataset(tmp_path, "x")
    before = path.read_text(encoding="utf-8")

    res = _run(tmp_path, "suggest", "dataset:x")

    assert res.exit_code == 0, res.output
    assert path.read_text(encoding="utf-8") == before
    assert "suggested identity_context scaffold" in res.output
    assert "taxon:" in res.output


def test_stamp_updates_datapackage_only_when_requested(tmp_path: Path) -> None:
    dp = tmp_path / "data" / "x" / "datapackage.yaml"
    dp.parent.mkdir(parents=True, exist_ok=True)
    dp.write_text(yaml.safe_dump({"name": "x", "resources": []}, sort_keys=False), encoding="utf-8")
    path = _write_dataset(tmp_path, "x", frontmatter={"datapackage": "data/x/datapackage.yaml"})

    without_stamp = _run(tmp_path, "resolve", "dataset:x", "--taxon", "9606")
    dp_after_without_stamp = yaml.safe_load(dp.read_text(encoding="utf-8"))
    with_stamp = _run(tmp_path, "resolve", "dataset:x", "--taxon", "9606", "--stamp")
    dp_after_stamp = yaml.safe_load(dp.read_text(encoding="utf-8"))

    assert without_stamp.exit_code == 0, without_stamp.output
    assert with_stamp.exit_code == 0, with_stamp.output
    assert "science" not in dp_after_without_stamp
    assert dp_after_stamp["science"]["identity_context"] == _frontmatter(path)["identity_context"]


def test_missing_dataset_exits_nonzero_with_clear_message(tmp_path: Path) -> None:
    res = _run(tmp_path, "resolve", "dataset:missing", "--taxon", "9606")

    assert res.exit_code != 0
    assert "no such dataset" in res.output.lower()
    assert "dataset:missing" in res.output
