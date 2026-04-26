"""Per-artifact header protocol parse/write.

v1 supports shebang_comment only. Other kinds parse-validate at the
registry level but raise NotImplementedError when actually exercised here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from science_tool.project_artifacts.registry_schema import HeaderKind, HeaderProtocol


_SHEBANG_RE = re.compile(rb"^#![^\n]*\n")
_HEADER_LINE_RE = re.compile(rb"^#\s*science-managed-(?P<key>artifact|version|source-sha256):\s*(?P<value>\S+)\s*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_VERSION_RE = re.compile(r"^\d{4}\.\d{2}\.\d{2}(?:\.\d+)?$")


@dataclass(frozen=True)
class ParsedHeader:
    name: str
    version: str
    hash: str


def parse_header(file_bytes: bytes, protocol: HeaderProtocol) -> ParsedHeader | None:
    """Return the ParsedHeader if present and well-formed, else None."""
    if protocol.kind is not HeaderKind.SHEBANG_COMMENT:
        raise NotImplementedError("v1 supports shebang_comment only")

    shebang = _SHEBANG_RE.match(file_bytes)
    if shebang is None:
        return None
    after_shebang = file_bytes[shebang.end() :]
    lines = after_shebang.split(b"\n", 3)
    if len(lines) < 3:
        return None

    parsed: dict[str, str] = {}
    for line in lines[:3]:
        m = _HEADER_LINE_RE.match(line)
        if m is None:
            return None
        parsed[m.group("key").decode()] = m.group("value").decode()

    expected_keys = {"artifact", "version", "source-sha256"}
    if set(parsed) != expected_keys:
        return None

    if not _VERSION_RE.match(parsed["version"]):
        return None
    if not _SHA256_RE.match(parsed["source-sha256"]):
        return None

    return ParsedHeader(name=parsed["artifact"], version=parsed["version"], hash=parsed["source-sha256"])


def header_bytes(name: str, version: str, hash_: str, protocol: HeaderProtocol) -> bytes:
    """Render the header lines for inclusion in a fully-rendered canonical bytes file.

    Does NOT include the shebang — the canonical author writes the shebang explicitly.
    Does NOT include trailing newlines beyond each header line.
    """
    if protocol.kind is not HeaderKind.SHEBANG_COMMENT:
        raise NotImplementedError("v1 supports shebang_comment only")
    return (
        f"# science-managed-artifact: {name}\n".encode()
        + f"# science-managed-version: {version}\n".encode()
        + f"# science-managed-source-sha256: {hash_}\n".encode()
    )
