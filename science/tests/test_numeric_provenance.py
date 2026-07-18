from pathlib import Path

from science_tool.numeric_provenance import (
    Anchored, Exempt, NotClaim, NumericClaim, NumericProvenanceConfig,
    SourceCandidate, Unanchored, build_document_context, build_resolution_index,
    classify_structural, compute_marker_scopes, entity_source_candidates,
    local_candidates_for_paragraph, marked_scope_for_line, paragraph_has_anchor_evidence,
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


def test_structural_does_not_overmask_claims_near_structural_tokens():
    # a real count near a hardware word must NOT be masked
    assert classify_structural(
        "4096", "the GPU processed 4096 samples", "the GPU processed 4096 samples".find("4096") + 1
    ) is None
    # the fps count near RTX must NOT be masked (only the model number 3070 is)
    assert classify_structural(
        "45", "the RTX 3070 achieved 45 fps", "the RTX 3070 achieved 45 fps".find("45") + 1
    ) is None
    assert classify_structural(
        "3070", "the RTX 3070 achieved 45 fps", "the RTX 3070 achieved 45 fps".find("3070") + 1
    ) == "hardware-id"
    # a genome size followed later by 'file'/'archived' must NOT be file-size
    assert classify_structural(
        "3.2",
        "the 3.2 Gb genome file was archived",
        "the 3.2 Gb genome file was archived".find("3.2") + 1,
    ) is None


def test_document_marker_covers_whole_body(tmp_path):
    path = _doc(tmp_path, "The alpha is 0.05 and power 0.8.\n", frontmatter="kind: plan\nstipulated: true")
    ctx = build_document_context(path)
    scopes = compute_marker_scopes(ctx)
    line = ctx.lines.index("The alpha is 0.05 and power 0.8.") + 1
    assert marked_scope_for_line(scopes, line) == "document"


def test_section_marker_is_fail_closed(tmp_path):
    body = ("## Decision thresholds\n<!-- stipulated -->\n\nUse alpha 0.05.\n\n"
            "## Results\n\nWe saw 7.94 fold.\n")
    path = _doc(tmp_path, body, frontmatter="kind: plan")
    ctx = build_document_context(path)
    scopes = compute_marker_scopes(ctx)
    assert marked_scope_for_line(scopes, ctx.lines.index("Use alpha 0.05.") + 1) == "section"
    assert marked_scope_for_line(scopes, ctx.lines.index("We saw 7.94 fold.") + 1) is None


def test_block_marker_covers_only_fenced_lines(tmp_path):
    body = ("We saw 7.94 fold.\n\n<!-- stipulated:start -->\nalpha 0.05\n<!-- stipulated:end -->\n\nAnd 3.1 more.\n")
    path = _doc(tmp_path, body, frontmatter="kind: interpretation")
    ctx = build_document_context(path)
    scopes = compute_marker_scopes(ctx)
    assert marked_scope_for_line(scopes, ctx.lines.index("alpha 0.05") + 1) == "block"
    assert marked_scope_for_line(scopes, ctx.lines.index("We saw 7.94 fold.") + 1) is None
    assert marked_scope_for_line(scopes, ctx.lines.index("And 3.1 more.") + 1) is None


_CFG = NumericProvenanceConfig(
    anchor_patterns=("task:", r"\[@"),
    spec_class_kinds=frozenset({"pre-registration", "plan"}),
    provenance_fields=("source_refs", "task_links", "input"),
)


def test_frontmatter_provenance_resolves(tmp_path):
    idx = build_resolution_index(_project(tmp_path))
    path = _doc(tmp_path, "The effect was 7.94 fold.\n",
                frontmatter="kind: interpretation\nsource_refs:\n  - task:t064")
    ctx = build_document_context(path)
    cands = entity_source_candidates(ctx, idx, _CFG)
    assert any(c.reference == "task:t064" and c.resolution_status == "resolved" for c in cands)


def test_fabricated_task_ref_does_not_anchor(tmp_path):
    idx = build_resolution_index(_project(tmp_path))
    path = _doc(tmp_path, "The effect was 7.94 fold.\n",
                frontmatter="kind: interpretation\nsource_refs:\n  - task:t999")
    ctx = build_document_context(path)
    cands = entity_source_candidates(ctx, idx, _CFG)
    assert any(c.reference == "task:t999" for c in cands)   # candidate present, not silently dropped
    assert all(c.resolution_status == "unresolved" for c in cands)   # finding 5


def test_interpretation_artifact_existence_checked(tmp_path):
    idx = build_resolution_index(_project(tmp_path))
    good = _doc(tmp_path, "Value 7.94.\n", frontmatter="kind: interpretation\nartifact: results/qap.json")
    assert any(c.resolution_status == "resolved" for c in entity_source_candidates(
        build_document_context(good), idx, _CFG))
    bad = tmp_path / "bad.md"
    bad.write_text("---\nkind: interpretation\nartifact: results/invented.json\n---\nValue 7.94.\n")
    bad_cands = entity_source_candidates(build_document_context(bad), idx, _CFG)
    assert any(c.reference == "results/invented.json" for c in bad_cands)   # candidate present, not silently dropped
    assert all(c.resolution_status == "unresolved" for c in bad_cands)


def test_related_is_excluded(tmp_path):
    idx = build_resolution_index(_project(tmp_path))
    path = _doc(tmp_path, "Value 7.94.\n", frontmatter="kind: interpretation\nrelated:\n  - task:t064")
    cands = entity_source_candidates(build_document_context(path), idx, _CFG)
    assert all(c.reference != "task:t064" for c in cands)   # finding 2 (related != source)


def test_local_body_ref_resolves_only_when_it_exists(tmp_path):
    idx = build_resolution_index(_project(tmp_path))
    good = local_candidates_for_paragraph("The effect (task:t064) was 7.94 fold.", idx)
    assert any(c.reference == "task:t064" and c.resolution_status == "resolved" for c in good)
    bad = local_candidates_for_paragraph("The effect (task:t999) was 7.94 fold.", idx)
    assert any(c.reference == "task:t999" for c in bad)   # candidate present, not silently dropped
    assert all(c.resolution_status == "unresolved" for c in bad)


def test_wiki_link_is_topical_not_a_candidate(tmp_path):
    idx = build_resolution_index(_project(tmp_path))
    cands = local_candidates_for_paragraph("See [[Related Topic]] for background, value 7.94.", idx)
    assert cands == ()


def test_generic_anchor_pattern_is_evidence_not_candidate(tmp_path):
    idx = build_resolution_index(_project(tmp_path))
    para = "see config/thresholds.yaml for the 0.05 cutoff"
    assert paragraph_has_anchor_evidence(para, (r"config/",)) is True
    assert local_candidates_for_paragraph(para, idx) == ()   # a bare config/ path is not a typed source ref


def test_anchor_evidence_empty_patterns_is_false():
    assert paragraph_has_anchor_evidence("see config/thresholds.yaml for 0.05", ()) is False
