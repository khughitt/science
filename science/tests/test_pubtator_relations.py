import json

import pytest

from science_tool.annotation.model import Motivation, TextualBody
from science_tool.annotation.pubtator_seed import (
    BiocMention,
    BiocRelation,
    PairedPassage,
    ResolvedMention,
    parse_bioc_relations,
    plan_relation,
    predicate_for,
    relation_body_json,
    resolve_persisted_mentions,
)

# Real-shape relation record (pinned from live PubTator3, PMID 28483577, 2026-06-15).
REL_RECORD = {
    "PubTator3": [
        {
            "relations": [
                {
                    "id": "R1",
                    "infons": {
                        "score": "0.5056",
                        "role1": {"identifier": "MESH:D000068298", "type": "Chemical"},
                        "role2": {"identifier": "MESH:D000068759", "type": "Chemical"},
                        "type": "Cotreatment",
                    },
                },
                {
                    "id": "R2",
                    "infons": {
                        "score": "0.9988",
                        "role1": {"identifier": "MESH:D000068298", "type": "Chemical"},
                        "role2": {"identifier": "MESH:D007249", "type": "Disease"},
                        "type": "Negative_Correlation",
                    },
                },
            ]
        }
    ]
}


def test_parse_bioc_relations_real_shape():
    rels, dropped = parse_bioc_relations(REL_RECORD)
    assert dropped == {}
    assert rels == [
        BiocRelation("Chemical", "MESH:D000068298", "Chemical", "MESH:D000068759", "Cotreatment", 0.5056),
        BiocRelation("Chemical", "MESH:D000068298", "Disease", "MESH:D007249", "Negative_Correlation", 0.9988),
    ]


def test_parse_bioc_relations_counts_malformed():
    rec = {
        "PubTator3": [
            {
                "relations": [
                    {"infons": {"role1": {"identifier": "X", "type": "Gene"}, "type": "Association"}},  # no role2
                    {"infons": {"role1": {"identifier": "X", "type": "Gene"},
                                "role2": {"identifier": "Y", "type": "Gene"}}},  # no type
                    "not-a-dict",
                    {"infons": {"role1": {"identifier": None, "type": "Gene"},
                                "role2": {"identifier": "Y", "type": "Gene"},
                                "type": "Association"}},  # role identifier not a str
                ]
            }
        ]
    }
    rels, dropped = parse_bioc_relations(rec)
    assert rels == []
    assert dropped == {"malformed-bioc-relation": 4}


def test_parse_bioc_relations_non_numeric_score_is_none():
    rec = {
        "PubTator3": [
            {
                "relations": [
                    {"infons": {"role1": {"identifier": "1", "type": "Gene"},
                                "role2": {"identifier": "2", "type": "Gene"},
                                "type": "Association", "score": "n/a"}}
                ]
            }
        ]
    }
    rels, _ = parse_bioc_relations(rec)
    assert rels[0].score is None


def test_parse_bioc_relations_bool_score_is_none():
    rec = {
        "PubTator3": [
            {
                "relations": [
                    {"infons": {"role1": {"identifier": "1", "type": "Gene"},
                                "role2": {"identifier": "2", "type": "Gene"},
                                "type": "Association", "score": True}}
                ]
            }
        ]
    }
    rels, _ = parse_bioc_relations(rec)
    assert rels[0].score is None


def test_parse_bioc_relations_no_relations_key():
    assert parse_bioc_relations({"PubTator3": [{"passages": []}]}) == ([], {})


@pytest.mark.parametrize(
    "rel_type,curie,source",
    [
        ("Association", "biolink:associated_with", "biolink"),
        ("Positive_Correlation", "biolink:positively_correlated_with", "biolink"),
        ("Negative_Correlation", "biolink:negatively_correlated_with", "biolink"),
        ("Bind", "biolink:directly_physically_interacts_with", "biolink"),
        ("Drug_Interaction", "biolink:interacts_with", "biolink"),
        ("Cotreatment", "sci:cotreatment", "sci"),
        ("Comparison", "sci:comparison", "sci"),
        ("Conversion", "sci:conversion", "sci"),
    ],
)
def test_predicate_for_known_types(rel_type, curie, source):
    assert predicate_for(rel_type) == (curie, source, None)


def test_predicate_for_is_case_insensitive():
    assert predicate_for("negative_correlation") == ("biolink:negatively_correlated_with", "biolink", None)
    assert predicate_for("COTREATMENT") == ("sci:cotreatment", "sci", None)


def test_predicate_for_unexpected_type_sanitized():
    # Unknown type -> sci:pubtator_<slug>, raw type preserved, never dropped.
    assert predicate_for("Some New/Weird Type!") == (
        "sci:pubtator_some_new_weird_type_",
        "sci",
        "Some New/Weird Type!",
    )


def test_relation_body_json_deterministic_and_sorted():
    body = relation_body_json(
        subject_iri="https://identifiers.org/ncbigene:672",
        object_iri="https://identifiers.org/mesh:D001943",
        predicate="biolink:associated_with",
        predicate_source="biolink",
        raw_predicate_type=None,
        score=0.97,
    )
    # Compact separators, sorted keys, byte-stable.
    assert body == (
        '{"object":"https://identifiers.org/mesh:D001943",'
        '"predicate":"biolink:associated_with",'
        '"predicate_source":"biolink",'
        '"score":0.97,'
        '"subject":"https://identifiers.org/ncbigene:672"}'
    )
    assert json.loads(body)["score"] == 0.97


def test_relation_body_json_omits_optional_fields():
    body = relation_body_json(
        subject_iri="a", object_iri="b",
        predicate="sci:cotreatment", predicate_source="sci",
        raw_predicate_type=None, score=None,
    )
    obj = json.loads(body)
    assert "score" not in obj
    assert "raw_predicate_type" not in obj


def test_relation_body_json_includes_raw_predicate_type_when_present():
    body = relation_body_json(
        subject_iri="a", object_iri="b",
        predicate="sci:pubtator_weird", predicate_source="sci",
        raw_predicate_type="Weird", score=None,
    )
    assert json.loads(body)["raw_predicate_type"] == "Weird"


# --- Task 5: relation targeting (plan_relation + resolve_persisted_mentions) --

# A single passage spanning file indices [0, 40); bioc offset 0.
_PASSAGE = PairedPassage(bioc_offset=0, bioc_len=40, file_char_base=0)
_TEXT = "BRCA1 raises risk of breast cancer a lot."
#         0....5         ........21...........  (BRCA1 @0:5, breast cancer @21:13)

GENE = "https://identifiers.org/ncbigene:672"
DIS = "https://identifiers.org/mesh:D001943"


def _mentions():
    return {
        GENE: [ResolvedMention(iri=GENE, file_idx=0, length=5, passage=_PASSAGE)],
        DIS: [ResolvedMention(iri=DIS, file_idx=21, length=13, passage=_PASSAGE)],
    }


def _rel(subj=("Gene", "672"), obj=("Disease", "MESH:D001943"), rtype="Association", score=0.9):
    return BiocRelation(subj[0], subj[1], obj[0], obj[1], rtype, score)


def test_plan_relation_minimal_covering_span():
    planned, reason = plan_relation(
        _TEXT, _rel(), _mentions(), release="2025-01", source_md_name="x.source.md"
    )
    assert reason is None
    assert planned is not None
    # Covering span = BRCA1 start (0) .. breast cancer end (34).
    assert planned.target.selector.exact == _TEXT[0:34]
    assert planned.annotation_type == "relation"
    assert planned.motivation == Motivation.LINKING
    assert isinstance(planned.body, TextualBody)
    assert planned.body.format == "application/json"
    body = json.loads(planned.body.value)
    assert body["subject"] == GENE and body["object"] == DIS
    assert body["predicate"] == "biolink:associated_with"
    # match_text = predicate|subj|obj|span_start:span_length
    assert planned.match_text == f"biolink:associated_with|{GENE}|{DIS}|0:34"
    assert planned.source_name == "pubtator3:2025-01:seeder-v1"


def test_plan_relation_picks_closest_pair():
    # Two gene mentions; the nearer one to the disease wins the minimal span.
    mentions = {
        GENE: [
            ResolvedMention(iri=GENE, file_idx=0, length=5, passage=_PASSAGE),
            ResolvedMention(iri=GENE, file_idx=15, length=5, passage=_PASSAGE),
        ],
        DIS: [ResolvedMention(iri=DIS, file_idx=21, length=13, passage=_PASSAGE)],
    }
    planned, _ = plan_relation(_TEXT, _rel(), mentions, release="r", source_md_name="x")
    # Closest gene (file_idx 15) .. disease end (34): span [15, 34).
    assert planned.target.selector.exact == _TEXT[15:34]
    assert planned.match_text.endswith("|15:19")


def test_plan_relation_unnormalized_concept_skips():
    planned, reason = plan_relation(
        _TEXT, _rel(obj=("Disease", "OMIM:99999")), _mentions(),
        release="r", source_md_name="x",
    )
    assert planned is None and reason == "relation-unnormalized-concept"


def test_plan_relation_no_persisted_mentions_skips():
    # Object concept resolves but has no persisted mention.
    planned, reason = plan_relation(
        _TEXT, _rel(obj=("Gene", "7157")), _mentions(), release="r", source_md_name="x"
    )
    assert planned is None and reason == "relation-no-persisted-mentions"


def test_plan_relation_cross_passage_skips():
    other = PairedPassage(bioc_offset=100, bioc_len=20, file_char_base=100)
    mentions = {
        GENE: [ResolvedMention(iri=GENE, file_idx=0, length=5, passage=_PASSAGE)],
        DIS: [ResolvedMention(iri=DIS, file_idx=100, length=13, passage=other)],
    }
    planned, reason = plan_relation(_TEXT + " " * 80 + "breast cancer", _rel(), mentions, release="r", source_md_name="x")
    assert planned is None and reason == "relation-cross-passage"


def test_resolve_persisted_mentions_groups_by_iri():
    file_text = "BRCA1 and breast cancer"  # BRCA1 @0:5, breast cancer @10:13
    paired = [PairedPassage(bioc_offset=0, bioc_len=23, file_char_base=0)]
    mentions = [
        BiocMention(pubtator_type="Gene", identifier="672", text="BRCA1", offset=0, length=5),
        BiocMention(pubtator_type="Disease", identifier="MESH:D001943", text="breast cancer", offset=10, length=13),
        BiocMention(pubtator_type="Gene", identifier="7157", text="TP53", offset=500, length=4),  # non-persisted
    ]
    grouped = resolve_persisted_mentions(file_text, paired, mentions)
    assert set(grouped) == {GENE, DIS}  # TP53 (non-persisted) excluded
    assert grouped[GENE][0].file_idx == 0
    assert grouped[DIS][0].file_idx == 10


def test_plan_relation_self_relation_spans_two_distinct_mentions():
    # Bind(672, 672): two BRCA1 mentions -> span covers BOTH, not a single token.
    same = {
        GENE: [
            ResolvedMention(iri=GENE, file_idx=0, length=5, passage=_PASSAGE),
            ResolvedMention(iri=GENE, file_idx=13, length=4, passage=_PASSAGE),
        ]
    }
    rel = _rel(subj=("Gene", "672"), obj=("Gene", "672"), rtype="Bind")
    planned, reason = plan_relation(_TEXT, rel, same, release="r", source_md_name="x")
    assert reason is None
    # span [0, 17): from first BRCA1 start to second mention end — covers both, not just [0,5).
    assert planned.target.selector.exact == _TEXT[0:17]
    assert planned.match_text.endswith("|0:17")


def test_plan_relation_self_relation_single_mention_skips():
    one = {GENE: [ResolvedMention(iri=GENE, file_idx=0, length=5, passage=_PASSAGE)]}
    rel = _rel(subj=("Gene", "672"), obj=("Gene", "672"), rtype="Bind")
    planned, reason = plan_relation(_TEXT, rel, one, release="r", source_md_name="x")
    assert planned is None and reason == "relation-self-single-mention"


def test_two_predicates_same_span_both_survive_merge():
    from datetime import datetime, timezone

    from science_tool.annotation.audit import merge_planned
    from science_tool.annotation.model import Sidecar

    mentions = _mentions()  # GENE @0:5, DIS @21:13 in one passage
    p1, _ = plan_relation(_TEXT, _rel(rtype="Association"), mentions, release="r", source_md_name="x.source.md")
    p2, _ = plan_relation(_TEXT, _rel(rtype="Negative_Correlation"), mentions, release="r", source_md_name="x.source.md")
    # Same exact span, different predicate -> distinct identity via match_text.
    assert p1.target.selector.exact == p2.target.selector.exact
    assert p1.match_text != p2.match_text
    _, written = merge_planned(Sidecar(), [p1, p2], actor="t", now=datetime(2026, 6, 15, tzinfo=timezone.utc))
    assert len(written) == 2  # both survive the merge 4-tuple, no collapse
