"""data/validate.sh: managed shim header and delegation command."""

import hashlib
from importlib import resources
from pathlib import Path

from science_tool.project_artifacts.hashing import body_hash
from science_tool.project_artifacts.header import ParsedHeader, parse_header
from science_tool.project_artifacts.loader import load_packaged_registry
from science_tool.project_artifacts.registry_schema import HeaderKind, HeaderProtocol

SHEBANG = HeaderProtocol(kind=HeaderKind.SHEBANG_COMMENT, comment_prefix="#")
SHIM_VERSION = "2026.05.21.1"
SHIM_BODY = 'exec uv run science validate "$@"\n'
SHIM_HASH = hashlib.sha256(SHIM_BODY.encode("utf-8")).hexdigest()


def _canonical_path() -> Path:
    files = resources.files("science_tool.project_artifacts")
    with resources.as_file(files / "data" / "validate.sh") as p:
        return Path(p)


def test_canonical_exists_and_has_shebang() -> None:
    p = _canonical_path()
    assert p.exists()
    raw = p.read_bytes()
    assert raw.startswith(b"#!/usr/bin/env bash\n")


def test_canonical_header_parses() -> None:
    parsed = parse_header(_canonical_path().read_bytes(), SHEBANG)
    assert parsed == ParsedHeader(name="validate.sh", version=SHIM_VERSION, hash=SHIM_HASH)


def test_current_hash_matches_body() -> None:
    raw = _canonical_path().read_bytes()
    expected = body_hash(raw, SHEBANG)
    reg = load_packaged_registry()
    art = next(a for a in reg.artifacts if a.name == "validate.sh")
    assert art.current_hash == expected


def test_canonical_body_is_validate_cli_shim() -> None:
    lines = _canonical_path().read_text(encoding="utf-8").splitlines(keepends=True)
    assert lines[4:] == [SHIM_BODY]
