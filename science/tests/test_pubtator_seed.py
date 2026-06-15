from datetime import datetime, timezone

import httpx
import pytest

from science_tool.annotation.io import read_sidecar, sidecar_for_markdown
from science_tool.annotation.model import HASH_REQUIRED_SOURCE_PREFIXES, IriBody, Motivation
from science_tool.annotation.pubtator_seed import (
    BiocMention,
    PairedPassage,
    PersistedPassage,
    SeedReport,
    annotation_type_for,
    concept_iri_for,
    pair_passages,
    parse_bioc_entity_annotations,
    plan_mention,
    seed_pubtator,
)
from science_tool.annotation.source_text import Passage, SourcePassages, SourceTextError
from science_tool.annotation.sources.base import PlannedAnnotation
from science_tool.paper_fetch import FetchConfig

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


def test_parse_bioc_entity_annotations():
    mentions, dropped = parse_bioc_entity_annotations(BIOC_FIXTURE)
    assert dropped == {}  # fixture is all well-formed, single-location
    # 3 (title) + 4 (abstract) + 1 (intro) = 8 mention rows, all preserved in order.
    assert len(mentions) == 8
    first = mentions[0]
    assert isinstance(first, BiocMention)
    assert (first.pubtator_type, first.identifier, first.text) == ("Gene", "672", "BRCA1")
    assert (first.offset, first.length) == (0, 5)
    # The two BRCA1 mentions in the title differ only by offset.
    assert mentions[0].offset == 0 and mentions[1].offset == 10
    assert mentions[0].text == mentions[1].text == "BRCA1"
    # The duplicate-tagged abstract span yields two rows (rsID + tmVar).
    variants = [m for m in mentions if m.pubtator_type == "Mutation"]
    assert {m.identifier for m in variants} == {"rs80357065", "tmVar:c|SUB|A|1|T"}


def test_parse_bioc_entity_annotations_empty():
    assert parse_bioc_entity_annotations({"PubTator3": []}) == ([], {})
    assert parse_bioc_entity_annotations({}) == ([], {})


def test_parse_bioc_entity_annotations_counts_malformed_and_multilocation():
    record = {
        "PubTator3": [
            {
                "infons": {},
                "passages": [
                    {
                        "infons": {"type": "title"},
                        "offset": 0,
                        "text": "G here",
                        "annotations": [
                            # empty type -> malformed
                            {"infons": {"type": ""}, "text": "G", "locations": [{"offset": 0, "length": 1}]},
                            # empty locations -> malformed
                            {"infons": {"type": "Gene"}, "text": "G", "locations": []},
                            # discontinuous span -> multi-location (not truncated)
                            {"infons": {"type": "Gene"}, "text": "G", "locations": [
                                {"offset": 0, "length": 1}, {"offset": 5, "length": 1}]},
                            # well-formed
                            {"infons": {"identifier": "1", "type": "Gene"}, "text": "G", "locations": [
                                {"offset": 0, "length": 1}]},
                        ],
                    }
                ],
            }
        ]
    }
    mentions, dropped = parse_bioc_entity_annotations(record)
    assert len(mentions) == 1
    assert dropped == {"malformed-bioc-annotation": 2, "multi-location-mention": 1}


# --- pair_passages tests ------------------------------------------------------


def _bioc(*sections):
    # sections: (section, bioc_offset, text)
    return SourcePassages(
        passages=tuple(Passage(section=s, bioc_offset=o, text=t) for s, o, t in sections),
        release="2025-01",
    )


def test_pair_passages_skips_nonpersisted_body():
    # Persisted = title + abstract only (abstract-only paper); BioC also has a body.
    file_text = "HEADER\n\nTitle text\n\nAbstract text\n"
    persisted = [
        PersistedPassage(section="title", file_char_base=8, length=10),     # "Title text"
        PersistedPassage(section="abstract", file_char_base=20, length=13),  # "Abstract text"
    ]
    assert file_text[8:18] == "Title text"
    assert file_text[20:33] == "Abstract text"
    bioc = _bioc(
        ("title", 0, "Title text"),
        ("abstract", 11, "Abstract text"),
        ("INTRO", 25, "Body text not persisted"),
    )
    paired = pair_passages(file_text, persisted, bioc)
    assert paired == [
        PairedPassage(bioc_offset=0, bioc_len=10, file_char_base=8),
        PairedPassage(bioc_offset=11, bioc_len=13, file_char_base=20),
    ]


def test_pair_passages_duplicate_text_pairs_by_order():
    # Two persisted passages with identical text pair to successive BioC occurrences.
    file_text = "H\n\nDUP\n\nDUP\n"
    persisted = [
        PersistedPassage(section="a", file_char_base=3, length=3),  # first "DUP"
        PersistedPassage(section="b", file_char_base=8, length=3),  # second "DUP"
    ]
    assert file_text[3:6] == "DUP" and file_text[8:11] == "DUP"
    bioc = _bioc(("a", 0, "DUP"), ("b", 100, "DUP"))
    paired = pair_passages(file_text, persisted, bioc)
    assert [p.file_char_base for p in paired] == [3, 8]
    assert [p.bioc_offset for p in paired] == [0, 100]


def test_pair_passages_drift_fails_loud():
    from science_tool.annotation.source_text import SourceTextError

    file_text = "H\n\nPersisted only here\n"
    persisted = [PersistedPassage(section="a", file_char_base=3, length=19)]
    assert file_text[3:22] == "Persisted only here"
    bioc = _bioc(("a", 0, "Different text entirely"))
    with pytest.raises(SourceTextError, match="not found in re-fetched BioC"):
        pair_passages(file_text, persisted, bioc)


def test_pair_passages_section_disambiguates_duplicate_text():
    # Two persisted passages share the text "DUP" but differ by section; a NON-persisted
    # body passage of the same text sits between them in BioC order. Section-aware
    # pairing must map the abstract entry to the abstract BioC passage (offset 100),
    # never the intervening body passage (offset 50).
    file_text = "H\n\nDUP\n\nDUP\n"
    persisted = [
        PersistedPassage(section="title", file_char_base=3, length=3),
        PersistedPassage(section="abstract", file_char_base=8, length=3),
    ]
    assert file_text[3:6] == "DUP" and file_text[8:11] == "DUP"
    bioc = _bioc(
        ("title", 0, "DUP"),
        ("INTRO", 50, "DUP"),       # non-persisted body, identical text
        ("abstract", 100, "DUP"),
    )
    paired = pair_passages(file_text, persisted, bioc)
    assert [p.bioc_offset for p in paired] == [0, 100]


# --- plan_mention tests -------------------------------------------------------

# Reusable mini-file: header + a single persisted abstract passage "BRCA1 and BRCA1".
_FILE = "---\nkind: paper-source\n---\n\n## Abstract\n\nBRCA1 and BRCA1\n"
_BASE = _FILE.index("BRCA1")  # absolute file index where the passage body begins


def _paired_for_abstract():
    from science_tool.annotation.pubtator_seed import PairedPassage
    # The abstract passage is BioC offset 0, 15 chars ("BRCA1 and BRCA1"), at _BASE.
    return [PairedPassage(bioc_offset=0, bioc_len=15, file_char_base=_BASE)]


def test_plan_mention_builds_annotation():
    m = BiocMention(pubtator_type="Gene", identifier="672", text="BRCA1", offset=0, length=5)
    planned, reason = plan_mention(
        _FILE, _paired_for_abstract(), m, release="2025-01", source_md_name="x.source.md"
    )
    assert reason is None
    assert isinstance(planned, PlannedAnnotation)
    assert planned.annotation_type == "entity-gene"
    assert planned.motivation is Motivation.IDENTIFYING
    assert planned.body == IriBody(iri="https://identifiers.org/ncbigene:672")
    assert planned.source_name == "pubtator3:2025-01:seeder-v1"
    assert planned.target.source == "x.source.md"
    assert planned.target.selector.exact == "BRCA1"
    file_idx = _BASE  # first BRCA1 sits at the passage base
    assert planned.match_text == f"entity-gene|https://identifiers.org/ncbigene:672|{file_idx}:5|BRCA1"


def test_plan_mention_two_same_surface_in_one_passage_distinct():
    m1 = BiocMention(pubtator_type="Gene", identifier="672", text="BRCA1", offset=0, length=5)
    m2 = BiocMention(pubtator_type="Gene", identifier="672", text="BRCA1", offset=10, length=5)
    p1, _ = plan_mention(_FILE, _paired_for_abstract(), m1, release="2025-01", source_md_name="x.source.md")
    p2, _ = plan_mention(_FILE, _paired_for_abstract(), m2, release="2025-01", source_md_name="x.source.md")
    assert p1 is not None and p2 is not None
    assert p1.match_text != p2.match_text
    assert p1.target.selector.prefix != p2.target.selector.prefix
    assert p1.target.selector.prefix == ""           # first BRCA1 is at the passage start
    assert p2.target.selector.prefix == "BRCA1 and "  # second BRCA1 anchored after the first


def test_plan_mention_skips_unnormalized():
    m = BiocMention(pubtator_type="Mutation", identifier="tmVar:c|SUB|A|1|T", text="BRCA1", offset=0, length=5)
    planned, reason = plan_mention(_FILE, _paired_for_abstract(), m, release="2025-01", source_md_name="x.source.md")
    assert planned is None and reason == "unnormalized-concept"


def test_plan_mention_skips_unsupported_type():
    m = BiocMention(pubtator_type="Anatomy", identifier="x", text="BRCA1", offset=0, length=5)
    planned, reason = plan_mention(_FILE, _paired_for_abstract(), m, release="2025-01", source_md_name="x.source.md")
    assert planned is None and reason == "unsupported-type"


def test_plan_mention_skips_nonpersisted_passage():
    m = BiocMention(pubtator_type="Gene", identifier="7157", text="TP53", offset=500, length=4)
    planned, reason = plan_mention(_FILE, _paired_for_abstract(), m, release="2025-01", source_md_name="x.source.md")
    assert planned is None and reason == "non-persisted-passage"


def test_plan_mention_slice_mismatch_fails_loud():
    m = BiocMention(pubtator_type="Gene", identifier="672", text="XXXXX", offset=0, length=5)
    with pytest.raises(SourceTextError, match="slice"):
        plan_mention(_FILE, _paired_for_abstract(), m, release="2025-01", source_md_name="x.source.md")


# --- seed_pubtator orchestrator tests -----------------------------------------

NOW = datetime(2026, 6, 15, tzinfo=timezone.utc)


def _cfg(tmp_path):
    return FetchConfig(email="t@example.com", cache_dir=tmp_path / "cache")


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _paper_entity(tmp_path):
    """Create a paper entity whose pmid resolves, under doc/background/papers/."""
    d = tmp_path / "doc" / "background" / "papers"
    d.mkdir(parents=True)
    (d / "doe2020.md").write_text("---\nkind: paper\npmid: 12345678\n---\n\n# Doe 2020\n")
    return d / "doe2020.md"


def _bioc_handler(request: httpx.Request) -> httpx.Response:
    # PubTator3 BioC export endpoint -> the fixture; Europe PMC -> empty.
    if "pubtator3-api" in str(request.url):
        return httpx.Response(200, json=BIOC_FIXTURE)
    return httpx.Response(200, json={"resultList": {"result": []}})


def test_seed_pubtator_end_to_end(tmp_path):
    from science_tool.annotation.source_text import persist_source

    entity = _paper_entity(tmp_path)
    cfg = _cfg(tmp_path)
    # Phase 1: write a real .source.md (abstract floor only; INTRO body is non-persisted).
    persist_source(
        project_root=tmp_path, identifier="12345678", cfg=cfg, http=_client(_bioc_handler)
    )
    source_md = entity.parent / "doe2020.source.md"
    assert source_md.exists()

    # Phase 2a: seed.
    report = seed_pubtator(
        project_root=tmp_path,
        identifier="12345678",
        cfg=cfg,
        actor="tester",
        now=NOW,
        http=_client(_bioc_handler),
    )
    assert isinstance(report, SeedReport)
    # 2 BRCA1 (gene) + 1 disease + 1 chemical + 1 species + 1 rsID variant = 6 written.
    assert report.written == 6
    # Skips: 1 tmVar (unnormalized) + 1 TP53 (non-persisted INTRO body).
    assert report.skipped.get("unnormalized-concept") == 1
    assert report.skipped.get("non-persisted-passage") == 1

    sidecar = read_sidecar(sidecar_for_markdown(source_md))
    assert len(sidecar.annotations) == 6
    assert all(a.content_hash for a in sidecar.annotations)


def test_seed_pubtator_idempotent_rerun(tmp_path):
    from science_tool.annotation.source_text import persist_source

    _paper_entity(tmp_path)
    cfg = _cfg(tmp_path)
    persist_source(project_root=tmp_path, identifier="12345678", cfg=cfg, http=_client(_bioc_handler))
    first = seed_pubtator(project_root=tmp_path, identifier="12345678", cfg=cfg, actor="t", now=NOW, http=_client(_bioc_handler))
    second = seed_pubtator(project_root=tmp_path, identifier="12345678", cfg=cfg, actor="t", now=NOW, http=_client(_bioc_handler))
    assert first.written == 6
    assert second.written == 0  # 4-tuple skip -> fully idempotent


def test_seed_pubtator_missing_source_md_fails_loud(tmp_path):
    _paper_entity(tmp_path)  # entity exists, but no .source.md
    cfg = _cfg(tmp_path)
    with pytest.raises(SourceTextError, match="persist-source"):
        seed_pubtator(project_root=tmp_path, identifier="12345678", cfg=cfg, actor="t", now=NOW, http=_client(_bioc_handler))


def test_seed_pubtator_no_bioc_record_is_noop(tmp_path):
    from science_tool.annotation.source_text import persist_source

    _paper_entity(tmp_path)
    cfg = _cfg(tmp_path)

    def epmc_only(request: httpx.Request) -> httpx.Response:
        if "pubtator3-api" in str(request.url):
            return httpx.Response(200, json={"PubTator3": []})
        return httpx.Response(
            200,
            json={"resultList": {"result": [{"abstractText": "An abstract.", "license": "CC-BY"}]}},
        )

    persist_source(project_root=tmp_path, identifier="12345678", cfg=cfg, http=_client(epmc_only))
    report = seed_pubtator(project_root=tmp_path, identifier="12345678", cfg=cfg, actor="t", now=NOW, http=_client(epmc_only))
    assert report.written == 0
    assert report.note is not None
