from science_tool.annotation.model import HASH_REQUIRED_SOURCE_PREFIXES

# A title+abstract record with one body passage (non-persisted in abstract-only mode),
# duplicate-surface mentions in the same passage, and one unnormalized variant.
# NOTE: validate against a live PubTator3 biocjson response before a seeder-v1 release.
BIOC_FIXTURE = {
    "PubTator3": [
        {
            "id": "12345678",
            "infons": {"_release": "2025-01"},
            "passages": [
                {
                    "infons": {"type": "title"},
                    "offset": 0,
                    "text": "BRCA1 and BRCA1 in breast cancer",
                    "annotations": [
                        {
                            "infons": {"identifier": "672", "type": "Gene"},
                            "text": "BRCA1",
                            "locations": [{"offset": 0, "length": 5}],
                        },
                        {
                            "infons": {"identifier": "672", "type": "Gene"},
                            "text": "BRCA1",
                            "locations": [{"offset": 10, "length": 5}],
                        },
                        {
                            "infons": {"identifier": "MESH:D001943", "type": "Disease"},
                            "text": "breast cancer",
                            "locations": [{"offset": 19, "length": 13}],
                        },
                    ],
                },
                {
                    "infons": {"type": "abstract"},
                    "offset": 33,
                    "text": "Tamoxifen treats it in Homo sapiens with rs80357065.",
                    "annotations": [
                        {
                            "infons": {"identifier": "MESH:D013629", "type": "Chemical"},
                            "text": "Tamoxifen",
                            "locations": [{"offset": 33, "length": 9}],
                        },
                        {
                            "infons": {"identifier": "9606", "type": "Species"},
                            "text": "Homo sapiens",
                            "locations": [{"offset": 56, "length": 12}],
                        },
                        {
                            "infons": {"identifier": "rs80357065", "type": "Mutation"},
                            "text": "rs80357065",
                            "locations": [{"offset": 74, "length": 10}],
                        },
                        {
                            "infons": {"identifier": "tmVar:c|SUB|A|1|T", "type": "Mutation"},
                            "text": "rs80357065",
                            "locations": [{"offset": 74, "length": 10}],
                        },
                    ],
                },
                {
                    "infons": {"type": "INTRO"},
                    "offset": 86,
                    "text": "A body sentence mentioning TP53 here.",
                    "annotations": [
                        {
                            "infons": {"identifier": "7157", "type": "Gene"},
                            "text": "TP53",
                            "locations": [{"offset": 113, "length": 4}],
                        }
                    ],
                },
            ],
        }
    ]
}


def test_pubtator3_prefix_is_hash_required():
    assert "pubtator3:" in HASH_REQUIRED_SOURCE_PREFIXES
