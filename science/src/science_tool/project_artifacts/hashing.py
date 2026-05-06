"""Body hash for managed artifacts: SHA256 of bytes after the header."""

from __future__ import annotations

import hashlib

from science_tool.project_artifacts.header import parse_header
from science_tool.project_artifacts.registry_schema import HeaderKind, HeaderProtocol


def body_hash(file_bytes: bytes, protocol: HeaderProtocol) -> str:
    """Hex SHA256 of *file_bytes* with the header stripped.

    If no parseable header is present, hashes the full bytes — this is what
    drift detection wants for `untracked` and pre-managed-system files.
    """
    if protocol.kind is not HeaderKind.SHEBANG_COMMENT:
        raise NotImplementedError("v1 supports shebang_comment only")

    parsed = parse_header(file_bytes, protocol)
    if parsed is None:
        return hashlib.sha256(file_bytes).hexdigest()

    # Strip shebang + 3 header lines. We know parse_header succeeded, so the
    # structure is well-formed.
    nl_count = 0
    body_start = len(file_bytes)
    for i, byte in enumerate(file_bytes):
        if byte == 0x0A:  # newline
            nl_count += 1
            if nl_count == 4:
                body_start = i + 1
                break

    return hashlib.sha256(file_bytes[body_start:]).hexdigest()
