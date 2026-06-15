# science/src/science_tool/annotation/ledger.py
"""Audit-ledger operations.

The ledger tracks which (sentence, source-version) pairs have been
audited so re-runs skip clean sentences. See spec §Re-audit cache.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from science_tool.annotation.model import AuditLedger, Sidecar


def find_or_create_ledger(
    sidecar: Sidecar, source_version: str, *, now: datetime
) -> tuple[Sidecar, AuditLedger]:
    """Return ``(sidecar, ledger)``; sidecar is unchanged if the ledger exists."""
    for existing in sidecar.ledgers:
        if existing.source == source_version:
            return sidecar, existing
    new_ledger = AuditLedger(
        id=_ledger_id_for(source_version),
        source=source_version,
        audited_hashes=(),
        modified=now,
    )
    new_sidecar = replace(sidecar, ledgers=sidecar.ledgers + (new_ledger,))
    return new_sidecar, new_ledger


def ledger_contains_hash(ledger: AuditLedger, content_hash: str) -> bool:
    return content_hash in ledger.audited_hashes


def ledger_append_hash(
    ledger: AuditLedger, content_hash: str, *, now: datetime
) -> AuditLedger:
    """Return a new ledger with ``content_hash`` appended; idempotent."""
    if content_hash in ledger.audited_hashes:
        return ledger
    return replace(
        ledger,
        audited_hashes=ledger.audited_hashes + (content_hash,),
        modified=now,
    )


def ledger_set_source_text_hash(
    ledger: AuditLedger, source_text_hash: str, *, now: datetime
) -> AuditLedger:
    """Return a ledger with the document-level source_text_hash set; idempotent.

    Unchanged hash returns the SAME object (no modified bump), so a re-run that
    re-records an identical hash produces no sidecar churn.
    """
    if ledger.source_text_hash == source_text_hash:
        return ledger
    return replace(
        ledger,
        source_text_hash=source_text_hash,
        modified=now,
    )


def _ledger_id_for(source_version: str) -> str:
    """Mint a stable ledger ID from a source-version string.

    ``llm-audit:gap-d-v1`` → ``ledger-gap-d-v1``
    ``lint:bare-author-year`` → ``ledger-bare-author-year``
    """
    _, _, suffix = source_version.partition(":")
    safe = suffix.replace(":", "-").replace("/", "-")
    return f"ledger-{safe}"
