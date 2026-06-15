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
