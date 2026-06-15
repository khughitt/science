import json

import pytest

from science_tool.annotation.pubtator_seed import BiocRelation, parse_bioc_relations, predicate_for, relation_body_json

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
