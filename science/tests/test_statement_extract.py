import json
from datetime import datetime, timezone
from pathlib import Path

from science_tool.annotation.io import read_sidecar, serialize_sidecar, write_sidecar
from science_tool.annotation.ledger import (
    find_or_create_ledger,
    ledger_set_source_text_hash,
)
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
