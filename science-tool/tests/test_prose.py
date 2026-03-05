from pathlib import Path

from science_tool.prose import scan_prose


def test_scan_prose_extracts_frontmatter_ontology_terms(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text(
        '---\nontology_terms:\n  - "biolink:Gene"\n  - "NCBIGene:672"\n---\n\nSome text.\n',
        encoding="utf-8",
    )
    result = scan_prose(tmp_path)
    assert len(result) == 1
    assert result[0]["path"] == "doc.md"
    assert result[0]["frontmatter_terms"] == ["biolink:Gene", "NCBIGene:672"]


def test_scan_prose_extracts_inline_curie_annotations(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text(
        "BRCA1 [`NCBIGene:672`] is a tumor suppressor gene associated with\n"
        "breast cancer [`MONDO:0016419`].\n",
        encoding="utf-8",
    )
    result = scan_prose(tmp_path)
    assert len(result) == 1
    annotations = result[0]["inline_annotations"]
    assert len(annotations) == 2
    assert annotations[0] == {"term": "BRCA1", "curie": "NCBIGene:672", "line": 1}
    assert annotations[1] == {"term": "breast cancer", "curie": "MONDO:0016419", "line": 2}


def test_scan_prose_handles_both_frontmatter_and_inline(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text(
        '---\nontology_terms:\n  - "biolink:Gene"\n---\n\nBRCA1 [`NCBIGene:672`] is important.\n',
        encoding="utf-8",
    )
    result = scan_prose(tmp_path)
    assert len(result) == 1
    assert result[0]["frontmatter_terms"] == ["biolink:Gene"]
    assert len(result[0]["inline_annotations"]) == 1


def test_scan_prose_skips_files_without_annotations(tmp_path: Path) -> None:
    doc = tmp_path / "plain.md"
    doc.write_text("Just plain text without any annotations.\n", encoding="utf-8")
    result = scan_prose(tmp_path)
    assert len(result) == 0


def test_scan_prose_recurses_into_subdirectories(tmp_path: Path) -> None:
    subdir = tmp_path / "sub"
    subdir.mkdir()
    doc = subdir / "nested.md"
    doc.write_text(
        '---\nontology_terms:\n  - "MONDO:0016419"\n---\n\nNested doc.\n',
        encoding="utf-8",
    )
    result = scan_prose(tmp_path)
    assert len(result) == 1
    assert result[0]["path"] == "sub/nested.md"


def test_scan_prose_ignores_non_markdown_files(tmp_path: Path) -> None:
    txt = tmp_path / "notes.txt"
    txt.write_text('---\nontology_terms:\n  - "biolink:Gene"\n---\n', encoding="utf-8")
    result = scan_prose(tmp_path)
    assert len(result) == 0


def test_scan_prose_empty_frontmatter_terms_not_reported(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("---\nontology_terms: []\n---\n\nNo annotations.\n", encoding="utf-8")
    result = scan_prose(tmp_path)
    assert len(result) == 0
