from pathlib import Path

from science_tool.numeric_provenance import (
    Anchored, Exempt, NotClaim, NumericClaim, NumericProvenanceConfig,
    SourceCandidate, Unanchored, assess_numeric_claims, build_document_context,
    build_resolution_index, classify_structural, compute_marker_scopes,
    entity_source_candidates, local_candidates_for_paragraph, marked_scope_for_line,
    paragraph_has_anchor_evidence,
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


def test_resolution_index_resolves_directory_artifacts(tmp_path):
    proj = _project(tmp_path)
    (proj / "outputs").mkdir()               # a directory artifact
    (proj / "outputs" / "run1").mkdir()
    idx = build_resolution_index(proj)
    assert idx.resolve("outputs") is True            # directory exists -> resolves
    assert idx.resolve("outputs/run1") is True
    assert idx.resolve("outputs/nope") is False      # nonexistent -> not resolved
    assert idx.resolve("/etc") is False              # absolute still guarded (even though it exists)
    assert idx.resolve("../outside") is False        # traversal still guarded


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


def test_structural_accession_and_license_require_adjacency():
    # a real count near an accession token must NOT be masked
    s1 = "GCST90441 lists 500 associated loci for this trait"
    assert classify_structural("500", s1, s1.find("500") + 1) is None
    # the accession's own adjacent digits ARE masked
    s2 = "association GCST90084 was used"
    assert classify_structural("90084", s2, s2.find("90084") + 1) == "accession"
    # a number merely near a license token (not adjacent) is NOT masked
    s3 = "the CC-BY-4.0 corpus contained 512 records"
    assert classify_structural("512", s3, s3.find("512") + 1) is None
    # the license version adjacent to the prefix IS masked
    assert classify_structural("4.0", s3, s3.find("4.0") + 1) == "license-version"


def test_structural_does_not_mask_count_after_generic_gwas_word():
    s = "The GWAS 500 cohort showed strong effects"
    assert classify_structural("500", s, s.find("500") + 1) is None
    # a real GCST accession's own adjacent digits are still masked
    s2 = "reported under accession GCST 90084 in the catalog"
    assert classify_structural("90084", s2, s2.find("90084") + 1) == "accession"


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


def test_section_marker_covers_nested_subsections(tmp_path):
    body = ("## Parent\n<!-- stipulated -->\n\n"
            "### Child\n\nChild value 7.94.\n\n"
            "## Other\n\nOther value 3.1.\n")
    path = _doc(tmp_path, body, frontmatter="kind: plan")
    ctx = build_document_context(path)
    scopes = compute_marker_scopes(ctx)
    assert marked_scope_for_line(scopes, ctx.lines.index("Child value 7.94.") + 1) == "section"
    assert marked_scope_for_line(scopes, ctx.lines.index("Other value 3.1.") + 1) is None


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


def test_body_ref_requires_word_boundary(tmp_path):
    idx = build_resolution_index(_project(tmp_path))
    bad = local_candidates_for_paragraph("we recite:Foo2024 here", idx)
    assert all(c.reference != "cite:Foo2024" for c in bad)   # substring match must not fire
    good = local_candidates_for_paragraph("see cite:Foo2024", idx)
    assert any(c.reference == "cite:Foo2024" for c in good)


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


def _assess(tmp_path, body, frontmatter=""):
    idx = build_resolution_index(_project(tmp_path))
    path = _doc(tmp_path, body, frontmatter=frontmatter)
    return assess_numeric_claims(build_document_context(path), idx, _CFG)


def test_unanchored_number_is_the_signal(tmp_path):
    out = _assess(tmp_path, "The improvement was 7.94 fold over baseline.\n",
                  frontmatter="kind: interpretation")
    assert any(isinstance(a, Unanchored) and a.claim.value == "7.94" for a in out)


def test_entity_provenance_anchors_all_numbers(tmp_path):
    # Trailing text after `0.001` (not a bare `.`) so the claim regex's
    # trailing negative-lookahead actually matches it — mirrors
    # test_marked_stipulated_number_is_exempt's same workaround; a number
    # immediately followed by a sentence-final period is never extracted.
    out = _assess(tmp_path, "The improvement was 7.94 fold; p was 0.001 (see notes).\n",
                  frontmatter="kind: interpretation\nsource_refs:\n  - task:t064")
    # guard against the assertion below passing vacuously if extraction drops
    # both numbers
    assert {"7.94", "0.001"} <= {a.claim.value for a in out}
    assert all(isinstance(a, Anchored) for a in out if a.claim.value in {"7.94", "0.001"})


def test_spec_class_kind_sets_kind_hint(tmp_path):
    out = _assess(tmp_path, "Gate coverage at 60% of diseases.\n", frontmatter="kind: plan")
    hit = next(a for a in out if a.claim.value == "60%")
    assert isinstance(hit, Unanchored) and hit.kind_hint == "stipulated"   # finding 1


def test_marked_stipulated_number_is_exempt(tmp_path):
    # Trailing text after `%` (not a bare `.`) so the claim regex's trailing
    # negative-lookahead actually matches — mirrors test_spec_class_kind_sets_kind_hint.
    body = "## Decision thresholds\n<!-- stipulated -->\n\nGate coverage at 60% of diseases.\n"
    out = _assess(tmp_path, body, frontmatter="kind: plan")
    assert any(isinstance(a, Exempt) and a.claim.value == "60%" for a in out)


def test_incidental_body_anchor_does_not_clear_distant_number(tmp_path):
    body = ("Background cites task:t064 for context.\n\n"
            "A separate paragraph reports 7.94 fold.\n")
    out = _assess(tmp_path, body, frontmatter="kind: report")
    hit = next(a for a in out if a.claim.value == "7.94")
    assert isinstance(hit, Unanchored)   # finding 2: paragraph-scoped, not entity-wide


# --- bound_spans suppression seam (Part B, Task 5) ---------------------------

def test_bound_claim_suppressed_from_anchor(tmp_path):
    from science_tool.prose_lint import detect_numeric_anchor
    fm = "numeric_claims:\n  b1:\n    artifact: nope.feather\n    locator: {column: c}"
    p = tmp_path / "e.md"
    # fm is 4 lines, so: L6=---, L7=Bound..., L8=blank, L9=Unbound...
    p.write_text(f"---\n{fm}\n---\nBound 3.14159[^b1] here.\n\nUnbound 2.71828 there.\n")
    lines = {i.line for i in detect_numeric_anchor(p)}
    assert 7 not in lines        # bound line suppressed even though artifact is dangling
    assert 9 in lines            # unbound ungrounded number still flags


def test_same_line_bound_and_unbound_numbers_are_column_discriminated(tmp_path):
    """One line carries both a bound number ([^b1]) and a distinct unbound
    number with no marker. Suppression must be column-scoped, not
    whole-line: the unbound number still flags and the surviving finding's
    column must be the unbound token's, not the bound token's. This
    transitively exercises Task 4's span[1]/span[2] column arithmetic.
    """
    from science_tool.prose_lint import detect_numeric_anchor
    fm = "numeric_claims:\n  b1:\n    artifact: nope.feather\n    locator: {column: c}"
    p = tmp_path / "e.md"
    body_line = "Bound 3.14159[^b1] and unbound 2.71828 apart.\n"
    p.write_text(f"---\n{fm}\n---\n{body_line}")
    issues = detect_numeric_anchor(p)
    line7 = [i for i in issues if i.line == 7]
    assert len(line7) == 1
    assert line7[0].match == "2.71828"
    bound_col = body_line.index("3.14159") + 1
    unbound_col = body_line.index("2.71828") + 1
    assert line7[0].col == unbound_col
    assert line7[0].col != bound_col


def _interp(tmp_path: Path, slug: str) -> None:
    d = tmp_path / "entities" / "interpretations"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slug}.md").write_text(
        f"---\nid: interpretation:{slug}\nkind: interpretation\n---\n\nbody\n"
    )


def test_resolve_full_id_and_unique_numeric_prefix(tmp_path):
    _project(tmp_path)
    _interp(tmp_path, "0007-altview")
    idx = build_resolution_index(tmp_path)
    assert idx.resolve("interpretation:0007-altview") is True   # exact full id
    assert idx.resolve("interpretation:0007") is True           # unique numeric prefix
    assert idx.resolve("interpretation:9999") is False          # fabricated


def test_resolve_ambiguous_numeric_prefix_fails(tmp_path):
    _project(tmp_path)
    _interp(tmp_path, "0013-alpha")
    _interp(tmp_path, "0013-beta")
    idx = build_resolution_index(tmp_path)
    assert idx.resolve("interpretation:0013-alpha") is True     # exact still resolves
    assert idx.resolve("interpretation:0013") is False          # 2 owners -> ambiguous, fail-closed


def test_resolve_non_numeric_prefix_is_not_expanded(tmp_path):
    _project(tmp_path)
    d = tmp_path / "entities" / "datasets"
    (d / "cptac.md").write_text(
        "---\nid: dataset:cptac-gbm-2021-proteogenomics\nkind: dataset\n---\n\nbody\n"
    )
    idx = build_resolution_index(tmp_path)
    assert idx.resolve("dataset:cptac-gbm-2021-proteogenomics") is True  # exact
    assert idx.resolve("dataset:cptac") is False                # non-numeric lead: never a short form


def _refs(para, idx):
    return {c.reference for c in local_candidates_for_paragraph(para, idx)}

def _resolved_refs(para, idx):
    return {c.reference for c in local_candidates_for_paragraph(para, idx) if c.resolution_status == "resolved"}


def test_provenance_entity_ref_extracts_and_resolves(tmp_path):
    _project(tmp_path)
    _interp(tmp_path, "0007-altview")
    idx = build_resolution_index(tmp_path)
    assert "interpretation:0007-altview" in _resolved_refs(
        "value 7.94 (`interpretation:0007-altview`)", idx)          # full id
    assert "interpretation:0007" in _resolved_refs(
        "value 7.94 per `interpretation:0007`.", idx)                # short prefix
    assert "dataset:xyz" in _resolved_refs("value 7.94 in `dataset:xyz`", idx)


def test_dotted_verbatim_paper_id_extracts(tmp_path):
    _project(tmp_path)
    d = tmp_path / "entities" / "papers"
    d.mkdir(parents=True, exist_ok=True)
    # id: is read from frontmatter, not the filename; keep the file name plain.
    (d / "volker2023-source.md").write_text(
        "---\nid: paper:Volker2023.source\nkind: paper\n---\n\nbody\n"
    )
    idx = build_resolution_index(tmp_path)
    assert "paper:Volker2023.source" in _resolved_refs(
        "value 7.94 (`paper:Volker2023.source`)", idx)


def test_dotted_id_not_truncated_before_continuation(tmp_path):
    # Atomic id-body guard: a dotted id followed by @host / /path / :extra must
    # not backtrack to a resolvable shorter id (paper:Volker2023).
    _project(tmp_path)
    d = tmp_path / "entities" / "papers"
    d.mkdir(parents=True, exist_ok=True)
    (d / "volker2023.md").write_text(
        "---\nid: paper:Volker2023\nkind: paper\n---\n\nbody\n"
    )
    idx = build_resolution_index(tmp_path)
    assert "paper:Volker2023" in _resolved_refs("value 7.94 (`paper:Volker2023`)", idx)  # bare id resolves
    for para in (
        "value 7.94 paper:Volker2023.source@host here",
        "value 7.94 paper:Volker2023.source/path here",
        "value 7.94 paper:Volker2023.source:extra here",
    ):
        assert "paper:Volker2023" not in _resolved_refs(para, idx)


def _paper(tmp_path: Path, entity_id: str, fname: str) -> None:
    d = tmp_path / "entities" / "papers"
    d.mkdir(parents=True, exist_ok=True)
    (d / fname).write_text(f"---\nid: {entity_id}\nkind: paper\n---\n\nbody\n")


def test_double_dot_id_masks_no_shorter_ref(tmp_path):
    # No-`..` rule (mirrors _VERBATIM_RE): a malformed id with consecutive dots
    # must extract NOTHING — not even a shorter, resolvable prefix. `paper:bad`
    # is a REAL entity here, so a truncating grammar would mask the number; the
    # no-`..` lookahead must prevent any candidate at that position.
    _project(tmp_path)
    _paper(tmp_path, "paper:bad", "bad.md")
    idx = build_resolution_index(tmp_path)
    assert idx.resolve("paper:bad") is True                       # the short id really exists…
    assert _refs("value 7.94 (`paper:bad..id`)", idx) == set()    # …yet `..` yields no candidate
    assert _resolved_refs("value 7.94 (`paper:bad..id`)", idx) == set()


def test_internal_dot_hyphen_id_extracts_whole(tmp_path):
    # `paper:good.-id` is a legal _VERBATIM_RE form (only `..` is banned);
    # the grammar must extract it whole, not truncate to `paper:good`.
    _project(tmp_path)
    _paper(tmp_path, "paper:good.-id", "good.md")
    idx = build_resolution_index(tmp_path)
    assert "paper:good.-id" in _resolved_refs("value 7.94 (`paper:good.-id`)", idx)


def test_topical_kinds_are_not_extracted(tmp_path):
    _project(tmp_path)
    idx = build_resolution_index(tmp_path)
    # hypothesis / question are not provenance-bearing: no candidate at all
    assert _refs("value 7.94 supports `hypothesis:0001-molecular-truth`.", idx) == set()
    assert _refs("value 7.94 for `question:0016-tissue`.", idx) == set()


def test_embedded_tokens_do_not_yield_resolvable_ref(tmp_path):
    _project(tmp_path)
    _interp(tmp_path, "0007-altview")
    idx = build_resolution_index(tmp_path)
    for para in (
        "see x_interpretation:0007 here",
        "see x-interpretation:0007 here",
        "path/interpretation:0007-altview.md",
        "interpretation:0007@host",
        "interpretation:0007/panel",
    ):
        assert "interpretation:0007" not in _resolved_refs(para, idx)
        assert "interpretation:0007-altview" not in _resolved_refs(para, idx)


def test_dataset_under_guard_boundaries(tmp_path):
    _project(tmp_path)
    idx = build_resolution_index(tmp_path)
    assert "dataset:xyz" not in _resolved_refs("path/dataset:xyz here", idx)   # embedded path
    assert "dataset:xyz" in _resolved_refs("computed from `dataset:xyz`.", idx)  # trailing period ok


def _hypothesis(tmp_path: Path, slug: str) -> None:
    d = tmp_path / "entities" / "hypotheses"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slug}.md").write_text(
        f"---\nid: hypothesis:{slug}\nkind: hypothesis\n---\n\nbody\n"
    )


def test_number_anchored_by_provenance_entity_ref(tmp_path):
    _project(tmp_path)
    _interp(tmp_path, "0007-altview")
    idx = build_resolution_index(tmp_path)
    path = _doc(tmp_path, "The window retained 7399 genes (`interpretation:0007`).",
                frontmatter="kind: interpretation")
    out = assess_numeric_claims(build_document_context(path), idx, _CFG)
    kinds = {type(a).__name__ for a in out if a.claim.value == "7399"}
    assert kinds == {"Anchored"}


def test_number_not_anchored_by_topical_hypothesis_ref(tmp_path):
    # The hypothesis is REAL and resolvable in the index — proving the claim
    # stays Unanchored because `hypothesis` is a topical (non-provenance) KIND,
    # not merely because the ref is fabricated.
    _project(tmp_path)
    _hypothesis(tmp_path, "0001-molecular-truth")
    idx = build_resolution_index(tmp_path)
    assert idx.resolve("hypothesis:0001-molecular-truth") is True  # it exists…
    path = _doc(tmp_path, "The ARI z was 221 (`hypothesis:0001-molecular-truth`).",
                frontmatter="kind: interpretation")
    out = assess_numeric_claims(build_document_context(path), idx, _CFG)
    kinds = {type(a).__name__ for a in out if a.claim.value == "221"}
    assert kinds == {"Unanchored"}   # …yet a topical citation must not clear the claim
