from pathlib import Path

from science_tool.numeric_provenance import (
    Anchored, Exempt, NotClaim, NumericClaim, NumericProvenanceConfig,
    SourceCandidate, Unanchored, build_document_context, build_resolution_index,
    classify_structural,
)


def test_types_construct_and_are_frozen():
    claim = NumericClaim(value="7.94", line=42, col=3, paragraph_id=2, section_id=1)
    cand = SourceCandidate(reference="task:t064", origin="frontmatter",
                           field_or_line="source_refs", resolution_status="resolved")
    assert Anchored(claim=claim, candidates=(cand,)).candidates[0].resolution_status == "resolved"
    assert Exempt(claim=claim, reason="stipulated", scope="section").scope == "section"
    assert Unanchored(claim=claim, kind_hint="stipulated", local_evidence=False).kind_hint == "stipulated"
    assert NotClaim(claim=claim, reason="hardware-id").reason == "hardware-id"
    cfg = NumericProvenanceConfig(anchor_patterns=("task:",), spec_class_kinds=frozenset({"plan"}),
                                  provenance_fields=("source_refs",))
    assert "task:" in cfg.anchor_patterns


def _doc(tmp_path: Path, body: str, frontmatter: str = "") -> Path:
    p = tmp_path / "doc.md"
    p.write_text(f"---\n{frontmatter}\n---\n{body}" if frontmatter else body)
    return p


def test_document_context_parses_kind_title_paragraphs(tmp_path):
    path = _doc(tmp_path, "# Results\n\nThe effect was 7.94 fold.\n\nAnother para 12.3.\n",
                frontmatter="kind: interpretation")
    ctx = build_document_context(path)
    assert ctx.kind == "interpretation"
    assert ctx.title == "Results"
    # the two body paragraphs land in distinct paragraph ids
    pid_first = ctx.paragraph_id_per_line[ctx.lines.index("The effect was 7.94 fold.") + 1]
    pid_second = ctx.paragraph_id_per_line[ctx.lines.index("Another para 12.3.") + 1]
    assert pid_first != pid_second


def test_section_scope_is_fail_closed_at_equal_or_higher_heading(tmp_path):
    body = ("## Decision thresholds\n\nUse alpha 0.05.\n\n"
            "## Results\n\nWe saw 7.94 fold.\n")
    path = _doc(tmp_path, body, frontmatter="kind: plan")
    ctx = build_document_context(path)
    sid_alpha = ctx.section_id_per_line[ctx.lines.index("Use alpha 0.05.") + 1]
    sid_result = ctx.section_id_per_line[ctx.lines.index("We saw 7.94 fold.") + 1]
    assert sid_alpha != sid_result   # the second H2 closes the first section


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: demo\n")
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text("## [t064] Do the thing\n\nbody\n")
    (tmp_path / "entities" / "datasets").mkdir(parents=True)
    (tmp_path / "entities" / "datasets" / "xyz.md").write_text("---\nid: dataset:xyz\nkind: dataset\n---\n\nbody\n")
    (tmp_path / "papers").mkdir()
    (tmp_path / "papers" / "references.bib").write_text("@article{Foo2024, title={T}, year={2024}}\n")
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "qap.json").write_text("{}")
    return tmp_path


def test_resolution_index_resolves_real_refs_and_rejects_fakes(tmp_path):
    idx = build_resolution_index(_project(tmp_path))
    assert idx.resolve("task:t064") is True
    assert idx.resolve("task:t999") is False        # finding 5
    assert idx.resolve("dataset:xyz") is True
    assert idx.resolve("dataset:nope") is False
    assert idx.resolve("[@Foo2024]") is True
    assert idx.resolve("cite:Foo2024") is True
    assert idx.resolve("[@Ghost2099]") is False
    assert idx.resolve("results/qap.json") is True
    assert idx.resolve("results/invented.json") is False   # finding 5
    assert idx.resolve("https://example.org/x") is True


def test_resolution_index_rejects_absolute_and_traversal_paths(tmp_path):
    idx = build_resolution_index(_project(tmp_path))
    assert idx.resolve("/etc/hostname") is False
    assert idx.resolve("../../etc/passwd") is False


def test_structural_masks_hardware_and_accession_and_license():
    # col is the number's real 1-based column within `line` (verified via str.find).
    assert classify_structural("3070", "trained on an RTX 3070 GPU", 19) == "hardware-id"
    assert classify_structural("6000", "sequenced on NovaSeq 6000", 22) == "hardware-id"
    assert classify_structural("90084", "association GCST90084 was used", 17) == "accession"
    assert classify_structural("4.0", "released under CC-BY-4.0 terms", 22) == "license-version"


def test_structural_is_context_gated_for_sizes_not_facts():
    # a download size is structural; a genome size is a factual claim
    assert classify_structural("516.9", "the 516.9 MB download completed", 5) == "file-size"
    assert classify_structural("3.2", "the human genome is 3.2 Gb", 21) is None
