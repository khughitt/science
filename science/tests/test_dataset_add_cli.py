"""Tests for `science dataset add`."""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.cli import main as science_cli

BIO_CNA_PROFILE = "science-entity-base/1.0+dataset/1.0+bio.cna/1.0+bio.identity_context/1.0"


def _add(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli,
        ["dataset", "add", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )


def test_add_creates_candidate_entity(tmp_path: Path) -> None:
    res = _add(tmp_path, "my-set", "--title", "My Set", "--source-url", "https://example.org")
    assert res.exit_code == 0, res.output
    p = tmp_path / "entities" / "datasets" / "my-set.md"
    assert p.exists()
    text = p.read_text(encoding="utf-8")
    assert "dataset:my-set" in text
    assert "status: candidate" in text
    assert "origin: external" in text
    assert "dataset_class: deposit" in text
    assert "license: unknown" in text
    assert "verified: false" in text


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---", 2)[1])


def test_add_refuses_identity_bearing_profile_without_identity(tmp_path: Path) -> None:
    res = _add(tmp_path, "copy-number", "--title", "Copy number", "--schema-profile", BIO_CNA_PROFILE)

    assert res.exit_code == 1
    assert "identity-bearing" in res.output
    assert "--taxon" in res.output
    assert "--assembly" in res.output
    assert not (tmp_path / "entities" / "datasets" / "copy-number.md").exists()


def test_add_refuses_blank_assembly_for_identity_bearing_profile(tmp_path: Path) -> None:
    res = _add(
        tmp_path,
        "copy-number",
        "--title",
        "Copy number",
        "--schema-profile",
        BIO_CNA_PROFILE,
        "--taxon",
        "9606",
        "--assembly",
        "",
    )

    assert res.exit_code == 1
    assert "--assembly" in res.output
    assert "Traceback" not in res.output
    assert not (tmp_path / "entities" / "datasets" / "copy-number.md").exists()


def test_add_refuses_non_positive_taxon(tmp_path: Path) -> None:
    res = _add(
        tmp_path,
        "copy-number",
        "--title",
        "Copy number",
        "--schema-profile",
        BIO_CNA_PROFILE,
        "--taxon",
        "0",
        "--assembly",
        "UNKNOWN",
    )

    assert res.exit_code == 1
    assert "--taxon" in res.output
    assert not (tmp_path / "entities" / "datasets" / "copy-number.md").exists()


def test_add_refuses_malformed_schema_profile(tmp_path: Path) -> None:
    res = _add(tmp_path, "bad-profile", "--title", "Bad", "--schema-profile", "not-a-profile")

    assert res.exit_code == 1
    assert "invalid schema_profile" in res.output
    assert not (tmp_path / "entities" / "datasets" / "bad-profile.md").exists()


def test_add_writes_declared_unresolved_identity_for_unknown_assembly(tmp_path: Path) -> None:
    res = _add(
        tmp_path,
        "copy-number",
        "--title",
        "Copy number",
        "--schema-profile",
        BIO_CNA_PROFILE,
        "--taxon",
        "9606",
        "--assembly",
        "UNKNOWN",
        "--gene-namespace",
        "hgnc_symbol",
        "--protein-namespace",
        "uniprot",
    )

    assert res.exit_code == 0, res.output
    fm = _frontmatter(tmp_path / "entities" / "datasets" / "copy-number.md")
    assert fm["schema_profile"] == BIO_CNA_PROFILE
    assert fm["identity_context"] == {
        "taxon": 9606,
        "assembly": {
            "label": "UNKNOWN",
            "registry": "dataset:assembly-registry",
            "resolution_status": "declared_unresolved",
        },
        "molecular_ids": {
            "gene": {
                "namespace": "hgnc_symbol",
                "registry": "dataset:gene-crosswalk-hgnc",
                "resolution_status": "declared_unresolved",
            },
            "protein": {
                "namespace": "uniprot",
                "registry": "dataset:protein-crosswalk-uniprot",
                "resolution_status": "declared_unresolved",
            },
        },
    }


def test_add_accepts_reference_class_with_source_url(tmp_path: Path) -> None:
    res = _add(
        tmp_path,
        "portal",
        "--title",
        "Portal",
        "--class",
        "reference",
        "--source-url",
        "https://example.org/portal",
    )

    assert res.exit_code == 0, res.output
    text = (tmp_path / "entities" / "datasets" / "portal.md").read_text(encoding="utf-8")
    assert "dataset_class: reference" in text
    assert "source_url: https://example.org/portal" in text


def test_add_reference_requires_source_url(tmp_path: Path) -> None:
    res = _add(tmp_path, "portal", "--title", "Portal", "--class", "reference")

    assert res.exit_code == 1
    assert "--source-url" in res.output


def test_add_rejects_derived(tmp_path: Path) -> None:
    res = _add(tmp_path, "x", "--title", "X", "--origin", "derived")
    assert res.exit_code == 1
    assert "register-run" in res.output


def test_add_rejects_existing_destination(tmp_path: Path) -> None:
    _add(tmp_path, "dup", "--title", "Dup")
    res = _add(tmp_path, "dup", "--title", "Dup again")
    assert res.exit_code == 1
    assert "already exists" in res.output


def test_add_rejects_bad_slug(tmp_path: Path) -> None:
    res = _add(tmp_path, "Bad_Slug", "--title", "Bad")
    assert res.exit_code == 1
    assert "slug" in res.output.lower()


def test_add_with_commons_related_ref_does_not_crash(tmp_path: Path) -> None:
    # A commons-looking related ref must not crash author-time even when no
    # commons store is reachable: add does a local-only prospective validation.
    res = CliRunner().invoke(
        science_cli,
        ["dataset", "add", "linked", "--title", "Linked", "--related", "cycles:paper:Aras2025"],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(tmp_path / "no-commons")},
    )
    assert res.exit_code == 0, res.output
    assert (tmp_path / "entities" / "datasets" / "linked.md").exists()


def _write_entity(tmp_path: Path, rel: str, frontmatter: str, body: str = "# Body\n") -> Path:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")
    return path


def _link(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli,
        ["dataset", "link", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )


def test_dataset_link_adds_dataset_to_question_datasets(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "entities/datasets/my-set.md",
        'id: "dataset:my-set"\ntype: "dataset"\ntitle: "My Set"\n',
    )
    target = _write_entity(
        tmp_path,
        "entities/questions/q.md",
        'id: "question:q"\ntype: "question"\ntitle: "Q"\ndatasets: []\n',
        body="# Q\n\nBody stays.\n",
    )

    res = _link(tmp_path, "my-set", "question:q")

    assert res.exit_code == 0, res.output
    text = target.read_text(encoding="utf-8")
    assert "datasets:\n- dataset:my-set\n" in text
    assert "# Q\n\nBody stays.\n" in text
    assert "linked dataset:my-set -> question:q" in res.output


def test_dataset_link_is_idempotent(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "entities/datasets/my-set.md",
        'id: "dataset:my-set"\ntype: "dataset"\ntitle: "My Set"\n',
    )
    target = _write_entity(
        tmp_path,
        "entities/hypotheses/h.md",
        'id: "hypothesis:h"\ntype: "hypothesis"\ntitle: "H"\ndatasets:\n  - dataset:my-set\n',
    )

    res = _link(tmp_path, "dataset:my-set", "hypothesis:h")

    assert res.exit_code == 0, res.output
    text = target.read_text(encoding="utf-8")
    assert text.count("dataset:my-set") == 1
    assert "already linked dataset:my-set -> hypothesis:h" in res.output


def test_dataset_link_rejects_non_question_hypothesis_target(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "entities/datasets/my-set.md",
        'id: "dataset:my-set"\ntype: "dataset"\ntitle: "My Set"\n',
    )
    _write_entity(
        tmp_path,
        "entities/papers/Paper2026.md",
        'id: "paper:Paper2026"\ntype: "paper"\ntitle: "Paper"\n',
    )

    res = _link(tmp_path, "my-set", "paper:Paper2026")

    assert res.exit_code == 1
    assert "question or hypothesis" in res.output
