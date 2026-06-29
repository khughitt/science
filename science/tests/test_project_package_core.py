import hashlib
from pathlib import Path

from science_tool.project_package.core import (
    FileResource,
    content_version,
    file_resource,
)


def test_file_resource_hashes_and_sizes(tmp_path: Path):
    (tmp_path / "a.txt").write_bytes(b"hello")
    fr = file_resource(tmp_path, "a.txt")
    assert fr == FileResource(
        path="a.txt",
        sha256=hashlib.sha256(b"hello").hexdigest(),
        bytes=5,
    )


def test_content_version_is_separator_free_concat():
    expected = hashlib.sha256(b"ab" + b"cd").hexdigest()[:12]
    assert content_version("2026-06-29", [b"ab", b"cd"]) == f"2026-06-29+{expected}"


def test_content_version_ignores_chunk_boundaries():
    v1 = content_version("0", [b"a", b"bc"])
    v2 = content_version("0", [b"ab", b"c"])
    # No length prefixes/separators: different chunking, same concatenation → same digest.
    assert v1 == v2
