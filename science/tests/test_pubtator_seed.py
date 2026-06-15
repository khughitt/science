import pytest

from science_tool.annotation.model import HASH_REQUIRED_SOURCE_PREFIXES
from science_tool.annotation.pubtator_seed import (
    annotation_type_for,
    concept_iri_for,
)

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


@pytest.mark.parametrize(
    "pubtator_type,expected",
    [
        ("Gene", "entity-gene"),
        ("Disease", "entity-disease"),
        ("Chemical", "entity-chemical"),
        ("Species", "entity-species"),
        ("CellLine", "entity-cellline"),
        ("Mutation", "entity-variant"),
        ("DNAMutation", "entity-variant"),
        ("SNP", "entity-variant"),
        ("Variant", "entity-variant"),
        ("ProteinMutation", "entity-variant"),
        ("Unsupported", None),
    ],
)
def test_annotation_type_for(pubtator_type, expected):
    assert annotation_type_for(pubtator_type) == expected


@pytest.mark.parametrize(
    "pubtator_type,identifier,expected",
    [
        ("Gene", "672", "https://identifiers.org/ncbigene:672"),
        ("Gene", "Gene:672", "https://identifiers.org/ncbigene:672"),
        ("Gene", "672;675", "https://identifiers.org/ncbigene:672"),
        ("Species", "9606", "https://identifiers.org/taxonomy:9606"),
        ("Disease", "MESH:D001943", "https://identifiers.org/mesh:D001943"),
        ("Disease", "D001943", "https://identifiers.org/mesh:D001943"),
        ("Chemical", "MESH:D013629", "https://identifiers.org/mesh:D013629"),
        ("Mutation", "rs80357065", "https://identifiers.org/dbsnp:rs80357065"),
        ("Mutation", "RS#:80357065", "https://identifiers.org/dbsnp:rs80357065"),
        ("CellLine", "CVCL_0031", "https://identifiers.org/cellosaurus:CVCL_0031"),
        ("Mutation", "tmVar:c|SUB|A|1|T", None),
        ("Gene", "", None),
        ("Gene", None, None),
        ("Disease", "OMIM:114480", None),
        ("CellLine", "12345", None),
        ("Unsupported", "1", None),
    ],
)
def test_concept_iri_for(pubtator_type, identifier, expected):
    assert concept_iri_for(pubtator_type, identifier) == expected
