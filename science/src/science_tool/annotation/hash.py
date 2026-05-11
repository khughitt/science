# science/src/science_tool/annotation/hash.py
"""Content-hash function for annotation re-audit caching.

See docs/plans/2026-05-10-annotation-system-spec.md §Re-audit cache.
"""

from __future__ import annotations

import hashlib

# Domain separator between the two inputs to prevent
# (text="ab", source="cdef") colliding with (text="abc", source="def").
_SEP = b"\x1e"  # ASCII RS (record separator)


def content_hash(exact_text: str, source_version: str) -> str:
    """Return ``"sha256:<hex>"`` for the (text, source-version) pair.

    Used as the cache key for `sci:AuditLedger.audited_hashes`. Two inputs
    are joined with a record-separator byte to prevent boundary collisions.
    """
    h = hashlib.sha256()
    h.update(exact_text.encode("utf-8"))
    h.update(_SEP)
    h.update(source_version.encode("utf-8"))
    return f"sha256:{h.hexdigest()}"
