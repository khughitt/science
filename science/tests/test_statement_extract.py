import json
from datetime import datetime, timezone
from pathlib import Path

from science_tool.annotation.io import read_sidecar, write_sidecar
from science_tool.annotation.ledger import ledger_set_source_text_hash
from science_tool.annotation.model import (
    AuditLedger,
    HASH_REQUIRED_SOURCE_PREFIXES,
    Sidecar,
)

_NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def test_llm_annot_is_hash_required():
    assert "llm-annot:" in HASH_REQUIRED_SOURCE_PREFIXES


def test_ledger_source_text_hash_defaults_none():
    led = AuditLedger(id="ledger-x", source="s", audited_hashes=(), modified=_NOW)
    assert led.source_text_hash is None


def test_ledger_set_source_text_hash_replaces_and_bumps_modified():
    led = AuditLedger(id="ledger-x", source="s", audited_hashes=(), modified=_NOW)
    later = datetime(2026, 6, 16, tzinfo=timezone.utc)
    updated = ledger_set_source_text_hash(led, "abc123", now=later)
    assert updated.source_text_hash == "abc123"
    assert updated.modified == later
    # idempotent: same hash returns the same object, no modified bump
    assert ledger_set_source_text_hash(updated, "abc123", now=_NOW) is updated


def test_ledger_source_text_hash_trig_round_trip(tmp_path: Path):
    led = AuditLedger(
        id="ledger-claude-sonnet-4-6-paper-annotate-v1",
        source="llm-annot:claude-sonnet-4-6:paper-annotate-v1",
        audited_hashes=("h1", "h2"),
        modified=_NOW,
        source_text_hash="deadbeef",
    )
    path = tmp_path / "p.anno.trig"
    write_sidecar(path, Sidecar(ledgers=(led,)))
    assert "sci:sourceTextHash" in path.read_text(encoding="utf-8")
    back = read_sidecar(path)
    assert back.ledgers[0].source_text_hash == "deadbeef"
    assert back.ledgers[0].audited_hashes == ("h1", "h2")


def test_legacy_ledger_without_predicate_reads_none(tmp_path: Path):
    led = AuditLedger(id="ledger-y", source="lint:x", audited_hashes=(), modified=_NOW)
    path = tmp_path / "q.anno.trig"
    write_sidecar(path, Sidecar(ledgers=(led,)))
    text = path.read_text(encoding="utf-8")
    assert "sci:sourceTextHash" not in text  # None -> predicate omitted
    assert read_sidecar(path).ledgers[0].source_text_hash is None


from science_tool.annotation.pubtator_seed import PersistedPassage
from science_tool.annotation.statement_extract import (
    CANONICAL_SECTIONS,
    _SECTION_NORMALIZE,
    _containing_passage,
    normalize_section,
)


def test_normalize_known_sections():
    assert normalize_section("title") == "title"
    assert normalize_section("abstract") == "abstract"
    assert normalize_section("INTRO") == "introduction"
    assert normalize_section("METHODS") == "methods"
    assert normalize_section("RESULTS") == "results"
    assert normalize_section("DISCUSS") == "discussion"
    assert normalize_section("CONCL") == "conclusion"
    assert normalize_section("FIG") == "figure"
    assert normalize_section("TABLE") == "table"


def test_normalize_unknown_section_is_other():
    assert normalize_section("ACK_FUND") == "other"
    assert normalize_section("") == "other"
    assert normalize_section("passage") == "other"


def test_canonical_sections_closed_set():
    assert CANONICAL_SECTIONS == frozenset({
        "title", "abstract", "introduction", "methods", "results",
        "discussion", "conclusion", "figure", "table", "other",
    })


def test_section_map_values_are_canonical():
    # every normalized output must live in the closed vocabulary
    assert set(_SECTION_NORMALIZE.values()) <= CANONICAL_SECTIONS


def test_containing_passage_finds_enclosing():
    passages = [
        PersistedPassage(section="title", file_char_base=100, length=10),
        PersistedPassage(section="RESULTS", file_char_base=200, length=50),
    ]
    pp = _containing_passage(passages, 210, 5)
    assert pp is not None and pp.section == "RESULTS"
    # span straddling a passage boundary -> None
    assert _containing_passage(passages, 248, 5) is None
    # span outside every passage (e.g. a heading) -> None
    assert _containing_passage(passages, 130, 5) is None


import pytest

from science_tool.annotation.statement_extract import (
    CandidateError,
    FigurativeCandidate,
    MAX_CANDIDATES,
    MAX_FIELD_CHARS,
    StatementCandidate,
    parse_candidates,
)


def _one(**over):
    base = {
        "type": "proposition", "exact": "X drives Y", "prefix": "we found ",
        "suffix": " here.", "stance": "asserted",
    }
    base.update(over)
    return json.dumps({"candidates": [base]})


def test_parse_minimal_valid():
    [c] = parse_candidates(_one())
    assert isinstance(c, StatementCandidate)
    assert c.type == "proposition" and c.stance == "asserted"
    assert c.subject is None and c.subject_concept is None


def test_parse_optional_fields():
    raw = _one(subject="X", object="Y",
               subject_concept="https://identifiers.org/ncbigene:672")
    [c] = parse_candidates(raw)
    assert c.subject == "X" and c.object == "Y"
    assert c.subject_concept == "https://identifiers.org/ncbigene:672"


def test_parse_rejects_unknown_top_level_key():
    raw = json.dumps({"candidates": [], "junk": 1})
    with pytest.raises(CandidateError, match="unknown top-level"):
        parse_candidates(raw)


def test_parse_rejects_unknown_candidate_field():
    with pytest.raises(CandidateError, match="unknown fields"):
        parse_candidates(_one(weight=0.9))


def test_parse_rejects_unknown_type():
    with pytest.raises(CandidateError, match="type"):
        parse_candidates(_one(type="banana"))


def test_parse_rejects_unknown_stance():
    with pytest.raises(CandidateError, match="stance"):
        parse_candidates(_one(stance="maybe"))


def test_parse_rejects_missing_required():
    raw = json.dumps({"candidates": [{"type": "question", "exact": "Q?"}]})
    with pytest.raises(CandidateError, match="missing required"):
        parse_candidates(raw)


def test_parse_rejects_non_string_field():
    with pytest.raises(CandidateError, match="must be a string"):
        parse_candidates(_one(exact=123))


def test_parse_rejects_empty_exact():
    with pytest.raises(CandidateError, match="non-empty"):
        parse_candidates(_one(exact=""))


def test_parse_rejects_over_count():
    many = json.dumps({"candidates": [
        {"type": "proposition", "exact": f"s{i}", "prefix": "",
         "suffix": "", "stance": "asserted"}
        for i in range(MAX_CANDIDATES + 1)
    ]})
    with pytest.raises(CandidateError, match="too many"):
        parse_candidates(many)


def test_parse_rejects_over_length():
    with pytest.raises(CandidateError, match="exceeds"):
        parse_candidates(_one(exact="z" * (MAX_FIELD_CHARS + 1)))


def test_parse_rejects_non_object_input():
    with pytest.raises(CandidateError, match="JSON object"):
        parse_candidates(json.dumps([1, 2]))


def test_parse_rejects_bad_json():
    with pytest.raises(CandidateError, match="not valid JSON"):
        parse_candidates("{not json")


def _fig(**over):
    base = {
        "type": "metaphor", "exact": "the immune system mounts an attack",
        "prefix": "", "suffix": " on pathogens.",
        "source_domain": "warfare", "target_domain": "immune response",
    }
    base.update(over)
    return json.dumps({"candidates": [base]})


def test_parse_figurative_minimal_valid():
    [c] = parse_candidates(_fig())
    assert isinstance(c, FigurativeCandidate)
    assert c.type == "metaphor"
    assert c.source_domain == "warfare" and c.target_domain == "immune response"
    assert c.mapping is None and c.cue is None


def test_parse_analogy_with_optionals():
    [c] = parse_candidates(_fig(type="analogy", mapping="cells as soldiers", cue="like"))
    assert isinstance(c, FigurativeCandidate)
    assert c.type == "analogy" and c.mapping == "cells as soldiers" and c.cue == "like"


def test_parse_mixed_statement_and_figurative():
    raw = json.dumps({"candidates": [
        {"type": "proposition", "exact": "X drives Y", "prefix": "", "suffix": ".",
         "stance": "asserted"},
        {"type": "metaphor", "exact": "a cellular factory", "prefix": "", "suffix": ".",
         "source_domain": "manufacturing", "target_domain": "the cell"},
    ]})
    cands = parse_candidates(raw)
    assert isinstance(cands[0], StatementCandidate)
    assert isinstance(cands[1], FigurativeCandidate)


def test_parse_figurative_missing_domain_fails():
    bad = json.dumps({"candidates": [{
        "type": "metaphor", "exact": "x", "prefix": "", "suffix": "",
        "source_domain": "warfare",  # target_domain missing
    }]})
    with pytest.raises(CandidateError, match="missing required"):
        parse_candidates(bad)


def test_parse_figurative_blank_required_domain_fails():
    with pytest.raises(CandidateError, match="non-empty"):
        parse_candidates(_fig(target_domain="   "))


def test_parse_figurative_blank_optional_fails():
    with pytest.raises(CandidateError, match="non-empty"):
        parse_candidates(_fig(mapping="   "))


def test_parse_figurative_stores_trimmed_value():
    # a valid field with surrounding whitespace is STORED trimmed (not just non-blank)
    [c] = parse_candidates(_fig(source_domain="  warfare  ", mapping="  cells as soldiers  "))
    assert c.source_domain == "warfare"
    assert c.mapping == "cells as soldiers"


def test_parse_figurative_rejects_statement_field():
    # `stance` is a statement-only field -> unknown for figurative
    with pytest.raises(CandidateError, match="unknown fields"):
        parse_candidates(_fig(stance="asserted"))


def test_parse_statement_rejects_figurative_field():
    # `source_domain` is figurative-only -> unknown for a statement
    with pytest.raises(CandidateError, match="unknown fields"):
        parse_candidates(_one(source_domain="warfare"))


def test_parse_figurative_over_length_field():
    with pytest.raises(CandidateError, match="exceeds"):
        parse_candidates(_fig(source_domain="z" * (MAX_FIELD_CHARS + 1)))


from science_tool.annotation.statement_extract import statement_body_json


def test_body_minimal_sorted_compact():
    body = statement_body_json(
        section="results", stance="asserted",
        subject=None, object_=None,
        subject_concept=None, object_concept=None,
    )
    assert body == '{"section":"results","stance":"asserted"}'


def test_body_includes_present_optionals_sorted():
    body = statement_body_json(
        section="results", stance="asserted",
        subject="BRCA1 loss", object_="genomic instability",
        subject_concept="https://identifiers.org/ncbigene:672", object_concept=None,
    )
    # keys sorted: object, section, stance, subject, subject_concept
    assert body == (
        '{"object":"genomic instability","section":"results","stance":"asserted",'
        '"subject":"BRCA1 loss","subject_concept":"https://identifiers.org/ncbigene:672"}'
    )


def test_body_is_byte_stable():
    kw = dict(section="methods", stance="hypothesized", subject="A", object_="B",
              subject_concept=None, object_concept=None)
    assert statement_body_json(**kw) == statement_body_json(**kw)


def test_body_gate_is_none_based_not_falsy():
    # an empty-string optional is EMITTED; a None optional is OMITTED
    body = statement_body_json(
        section="results", stance="asserted", subject="", object_=None,
        subject_concept=None, object_concept=None,
    )
    assert body == '{"section":"results","stance":"asserted","subject":""}'


from science_tool.annotation.statement_extract import find_qualified_spans


def test_anchor_unique_no_context():
    text = "alpha beta gamma"
    assert find_qualified_spans(text, "beta", "", "") == [6]


def test_anchor_not_found():
    assert find_qualified_spans("alpha beta", "delta", "", "") == []


def test_anchor_repeated_quote_is_ambiguous_without_context():
    text = "the cell. the cell."
    assert find_qualified_spans(text, "the cell", "", "") == [0, 10]


def test_anchor_prefix_disambiguates_repeat():
    text = "the cell. the cell."
    # only the second "the cell" is preceded by ". " ... use a distinguishing prefix
    spans = find_qualified_spans(text, "the cell", ". ", "")
    assert spans == [10]


def test_anchor_suffix_disambiguates_repeat():
    text = "the cell grows. the cell dies."
    spans = find_qualified_spans(text, "the cell", "", " dies")
    assert spans == [16]


def test_anchor_requires_adjacent_prefix():
    text = "we found the result here"
    # prefix must be the text IMMEDIATELY before exact
    assert find_qualified_spans(text, "result", "found ", "") == []  # not adjacent
    # returns the start index of `exact` ("result" at 13), not of the prefix
    assert find_qualified_spans(text, "result", "the ", "") == [13]


def test_anchor_empty_exact_returns_empty():
    assert find_qualified_spans("anything", "", "", "") == []


from science_tool.annotation.model import (
    Annotation,
    IriBody,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
)
from science_tool.annotation.statement_extract import (
    active_entity_iris,
    plan_statement,
)

_MODEL = "claude-sonnet-4-6"
_GENE = "https://identifiers.org/ncbigene:672"
# A file whose passage body spans [0, len). Build a simple single-passage doc.
_TEXT = "BRCA1 loss drives genomic instability in these tumors and elsewhere."
_PASSAGES = [PersistedPassage(section="RESULTS", file_char_base=0, length=len(_TEXT))]


def _entity_ann(iri: str, status: Status = Status.OPEN) -> Annotation:
    return Annotation(
        id="e1",
        target=SpecificResource(
            source="P.source.md",
            selector=TextQuoteSelector(exact="BRCA1", prefix="", suffix=" loss"),
        ),
        bodies=(IriBody(iri=iri),),
        motivation=Motivation.IDENTIFYING,
        annotation_type="entity-gene",
        source="pubtator3:2024:seeder-v1",
        status=status,
        creator="x",
        created=_NOW,
        content_hash="h",
        modified=(None if status is Status.OPEN else _NOW),
        modified_by=(None if status is Status.OPEN else "x"),
        match_text="entity-gene|...",
    )


def test_active_entity_iris_includes_open_and_ack_excludes_others():
    sc = Sidecar(annotations=(
        _entity_ann(_GENE, Status.OPEN),
        _entity_ann("https://identifiers.org/mesh:D1", Status.ACK),
        _entity_ann("https://identifiers.org/mesh:D2", Status.DISMISSED),
        _entity_ann("https://identifiers.org/mesh:D3", Status.SUPERSEDED),
    ))
    iris = active_entity_iris(sc)
    assert _GENE in iris
    assert "https://identifiers.org/mesh:D1" in iris
    assert "https://identifiers.org/mesh:D2" not in iris
    assert "https://identifiers.org/mesh:D3" not in iris


def _cand(**over) -> StatementCandidate:
    base = dict(type="proposition", exact="BRCA1 loss drives genomic instability",
                prefix="", suffix=" in these", stance="asserted")
    base.update(over)
    return StatementCandidate(**base)  # type: ignore[arg-type]


def test_plan_statement_anchors_and_builds_body():
    p, reason, dropped = plan_statement(
        _TEXT, _PASSAGES, _cand(), active_iris=set(),
        model=_MODEL, source_md_name="P.source.md",
    )
    assert reason is None and dropped == 0 and p is not None
    assert p.annotation_type == "proposition"
    assert p.motivation is Motivation.CLASSIFYING
    assert p.source_name == "llm-annot:claude-sonnet-4-6:paper-annotate-v1"
    assert p.body.format == "application/json"
    assert '"section":"results"' in p.body.value
    # match_text carries the offset discriminator: type|file_idx:length|normalized_exact
    assert p.match_text.startswith("proposition|0:37|")


def test_plan_statement_quote_not_found():
    p, reason, _ = plan_statement(
        _TEXT, _PASSAGES, _cand(exact="absent text"), active_iris=set(),
        model=_MODEL, source_md_name="P.source.md",
    )
    assert p is None and reason == "extract-quote-not-found"


def test_plan_statement_ambiguous():
    text = "the cell. the cell."
    passages = [PersistedPassage(section="RESULTS", file_char_base=0, length=len(text))]
    p, reason, _ = plan_statement(
        text, passages, _cand(exact="the cell", suffix=""), active_iris=set(),
        model=_MODEL, source_md_name="P.source.md",
    )
    assert p is None and reason == "extract-quote-ambiguous"


def test_plan_statement_outside_passage():
    # passage occupies [10, len); anchor at 0 is outside it
    passages = [PersistedPassage(section="RESULTS", file_char_base=10, length=len(_TEXT) - 10)]
    p, reason, _ = plan_statement(
        _TEXT, passages, _cand(exact="BRCA1 loss", suffix=" drives"), active_iris=set(),
        model=_MODEL, source_md_name="P.source.md",
    )
    assert p is None and reason == "extract-anchored-outside-passage"


def test_plan_statement_keeps_verified_grounding():
    p, reason, dropped = plan_statement(
        _TEXT, _PASSAGES, _cand(subject_concept=_GENE), active_iris={_GENE},
        model=_MODEL, source_md_name="P.source.md",
    )
    assert reason is None and dropped == 0 and p is not None
    assert _GENE in p.body.value


def test_plan_statement_drops_unverified_grounding_keeps_statement():
    p, reason, dropped = plan_statement(
        _TEXT, _PASSAGES,
        _cand(subject_concept="https://identifiers.org/ncbigene:999"),
        active_iris={_GENE},
        model=_MODEL, source_md_name="P.source.md",
    )
    assert reason is None and p is not None  # statement kept
    assert dropped == 1
    assert "ncbigene:999" not in p.body.value  # bad grounding dropped


def test_plan_statement_drops_one_grounding_field_keeps_other():
    p, reason, dropped = plan_statement(
        _TEXT, _PASSAGES,
        _cand(subject_concept=_GENE,
              object_concept="https://identifiers.org/ncbigene:999"),
        active_iris={_GENE},
        model=_MODEL, source_md_name="P.source.md",
    )
    assert reason is None and p is not None and dropped == 1
    assert _GENE in p.body.value  # verified subject kept
    assert "ncbigene:999" not in p.body.value  # unverified object dropped


def test_plan_statement_match_text_distinguishes_repeated_identical():
    text = "X drives Y. Later, X drives Y again."
    passages = [PersistedPassage(section="RESULTS", file_char_base=0, length=len(text))]
    p1, _, _ = plan_statement(
        text, passages, _cand(exact="X drives Y", prefix="", suffix=". Later"),
        active_iris=set(), model=_MODEL, source_md_name="P.source.md",
    )
    p2, _, _ = plan_statement(
        text, passages, _cand(exact="X drives Y", prefix="Later, ", suffix=" again"),
        active_iris=set(), model=_MODEL, source_md_name="P.source.md",
    )
    assert p1 is not None and p2 is not None
    assert p1.match_text != p2.match_text  # different file_idx => distinct dedup keys


from science_tool.annotation.source_text import Passage, SourcePassages, write_source_md
from science_tool.annotation.statement_extract import (
    ExtractReport,
    check_source_changed,
    extract_candidates,
)


def _make_source_md(tmp_path: Path) -> Path:
    abstract = SourcePassages(
        passages=(
            Passage(section="title", bioc_offset=0, text="A study of BRCA1."),
            Passage(
                section="abstract", bioc_offset=18,
                text="BRCA1 loss drives genomic instability in tumors.",
            ),
        ),
        release="2024",
    )
    return write_source_md(
        directory=tmp_path, citekey="Brca2024", abstract=abstract, fulltext=None,
        retrieved_from="https://example.org", license_="unknown", licensed=False,
        pmid="1", doi=None,
    )


def _cands(*objs) -> list[StatementCandidate]:
    return [StatementCandidate(**o) for o in objs]  # type: ignore[arg-type]


def test_extract_end_to_end_writes_and_records_hash(tmp_path: Path):
    src = _make_source_md(tmp_path)
    cands = _cands(dict(
        type="proposition", exact="BRCA1 loss drives genomic instability",
        prefix="", suffix=" in tumors", stance="asserted",
    ))
    report = extract_candidates(
        source_md=src, model=_MODEL, candidates=cands, now=_NOW, actor="paper-annotate",
    )
    assert isinstance(report, ExtractReport)
    assert report.written == 1 and report.skipped == {}
    assert report.source_text_hash_recorded is True
    # sidecar persisted with the statement + the ledger hash
    sidecar = read_sidecar(src.with_name("Brca2024.source.anno.trig"))
    assert any(a.annotation_type == "proposition" for a in sidecar.annotations)
    led = next(l for l in sidecar.ledgers
               if l.source == "llm-annot:claude-sonnet-4-6:paper-annotate-v1")
    assert led.source_text_hash is not None
    # and now --check reports unchanged
    assert check_source_changed(source_md=src, model=_MODEL) is False


def test_extract_identical_rerun_is_idempotent(tmp_path: Path):
    src = _make_source_md(tmp_path)
    cands = _cands(dict(
        type="proposition", exact="BRCA1 loss drives genomic instability",
        prefix="", suffix=" in tumors", stance="asserted",
    ))
    extract_candidates(source_md=src, model=_MODEL, candidates=cands, now=_NOW, actor="a")
    again = extract_candidates(
        source_md=src, model=_MODEL, candidates=cands, now=_NOW, actor="a",
    )
    assert again.written == 0  # all-duplicate
    assert again.source_text_hash_recorded is True  # valid no-op still records


def test_extract_empty_candidates_records_hash(tmp_path: Path):
    src = _make_source_md(tmp_path)
    report = extract_candidates(
        source_md=src, model=_MODEL, candidates=[], now=_NOW, actor="a",
    )
    assert report.written == 0
    assert report.source_text_hash_recorded is True  # valid no-op
    assert report.note is None  # fully processed -> no note
    assert check_source_changed(source_md=src, model=_MODEL) is False


def test_extract_all_unanchored_does_not_record_hash(tmp_path: Path):
    src = _make_source_md(tmp_path)
    cands = _cands(dict(
        type="proposition", exact="text that is absent from the document",
        prefix="", suffix="", stance="asserted",
    ))
    report = extract_candidates(
        source_md=src, model=_MODEL, candidates=cands, now=_NOW, actor="a",
    )
    assert report.written == 0
    assert report.skipped == {"extract-quote-not-found": 1}
    assert report.note is not None and "failed to anchor" in report.note
    assert report.source_text_hash_recorded is False  # failed no-op
    assert check_source_changed(source_md=src, model=_MODEL) is True  # re-run allowed


def test_extract_partial_anchor_failure_does_not_record_hash(tmp_path: Path):
    # one candidate anchors, one does not -> the document is NOT fully processed.
    src = _make_source_md(tmp_path)
    cands = _cands(
        dict(type="proposition", exact="BRCA1 loss drives genomic instability",
             prefix="", suffix=" in tumors", stance="asserted"),
        dict(type="hypothesis", exact="a clause that is absent from the document",
             prefix="", suffix="", stance="hypothesized"),
    )
    report = extract_candidates(
        source_md=src, model=_MODEL, candidates=cands, now=_NOW, actor="a",
    )
    assert report.written == 1  # the good one persisted
    assert report.skipped == {"extract-quote-not-found": 1}
    assert report.source_text_hash_recorded is False  # defective set -> re-run allowed
    assert check_source_changed(source_md=src, model=_MODEL) is True


def test_check_changed_when_no_sidecar(tmp_path: Path):
    src = _make_source_md(tmp_path)
    assert check_source_changed(source_md=src, model=_MODEL) is True


def test_extract_reports_grounding_dropped(tmp_path: Path):
    src = _make_source_md(tmp_path)
    cands = _cands(dict(
        type="proposition", exact="BRCA1 loss drives genomic instability",
        prefix="", suffix=" in tumors", stance="asserted",
        subject_concept="https://identifiers.org/ncbigene:999",  # not a persisted entity
    ))
    report = extract_candidates(
        source_md=src, model=_MODEL, candidates=cands, now=_NOW, actor="a",
    )
    assert report.written == 1 and report.grounding_dropped == 1


from science_tool.annotation.statement_extract import figurative_body_json


def test_figurative_body_minimal_sorted_compact():
    body = figurative_body_json(
        section="discussion", source_domain="warfare",
        target_domain="immune response", mapping=None, cue=None,
    )
    # keys sorted: section, source_domain, target_domain
    assert body == (
        '{"section":"discussion","source_domain":"warfare",'
        '"target_domain":"immune response"}'
    )


def test_figurative_body_includes_present_optionals_sorted():
    body = figurative_body_json(
        section="results", source_domain="a factory", target_domain="the cell",
        mapping="ribosome as machine", cue="like",
    )
    # keys sorted: cue, mapping, section, source_domain, target_domain
    assert body == (
        '{"cue":"like","mapping":"ribosome as machine","section":"results",'
        '"source_domain":"a factory","target_domain":"the cell"}'
    )


def test_figurative_body_omits_absent_optionals():
    body = figurative_body_json(
        section="results", source_domain="a", target_domain="b",
        mapping=None, cue="like",
    )
    assert '"mapping"' not in body and '"cue":"like"' in body
