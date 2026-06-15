from science_tool.annotation.pubtator_seed import BiocRelation, parse_bioc_relations

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
