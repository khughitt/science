from science_tool.numeric_provenance import (
    Anchored, Exempt, NotClaim, NumericClaim, NumericProvenanceConfig,
    SourceCandidate, Unanchored,
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
