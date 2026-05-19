from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "promote_dataset"


def test_streaming_sha256_matches_golden_fixture():
    from science_tool.commons.datapackage import stream_sha256_and_bytes

    h, n = stream_sha256_and_bytes(FIXTURES / "hello.txt")
    assert (
        h
        == "sha256:a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a447"
    )
    assert n == 12


def test_streaming_sha256_is_deterministic_for_multi_chunk_file(tmp_path):
    """Determinism check on a multi-chunk file."""
    big = tmp_path / "big.bin"
    big.write_bytes(b"\x00" * (1024 * 1024 + 7))
    from science_tool.commons.datapackage import stream_sha256_and_bytes

    h, n = stream_sha256_and_bytes(big)
    assert n == 1024 * 1024 + 7
    import hashlib

    expected = hashlib.sha256(b"\x00" * n).hexdigest()
    assert h == f"sha256:{expected}"


def test_streaming_sha256_uses_1MiB_chunks(monkeypatch):
    reads = []

    class RecordingFile:
        def __init__(self):
            self._remaining = b"abc"

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self, size):
            reads.append(size)
            chunk = self._remaining[:size]
            self._remaining = self._remaining[size:]
            return chunk

    def open_recording_file(self, mode):
        assert self == FIXTURES / "hello.txt"
        assert mode == "rb"
        return RecordingFile()

    monkeypatch.setattr(Path, "open", open_recording_file)

    from science_tool.commons.datapackage import stream_sha256_and_bytes

    h, n = stream_sha256_and_bytes(FIXTURES / "hello.txt")
    assert (
        h
        == "sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
    assert n == 3
    assert reads == [1024 * 1024, 1024 * 1024]


def test_render_canonical_datapackage_strips_project_fields_and_injects_hashes():
    from science_tool.commons.datapackage import render_canonical_datapackage_yaml

    project_doc = {
        "name": "mm30-external-ccle-proteomics-2020-01",
        "conformsTo": "mm30",
        "mm30": {"external_source": "Nusinow 2020"},
        "resources": [
            {
                "name": "r1",
                "path": "r1.txt",
                "format": "txt",
                "schema": {"fields": []},
            }
        ],
    }
    hashes = {"r1": ("sha256:abc123", 42)}
    yaml_text = render_canonical_datapackage_yaml(
        project_doc=project_doc,
        canonical_slug="fixture-ds",
        per_resource=hashes,
    )
    import yaml as pyyaml

    parsed = pyyaml.safe_load(yaml_text)
    assert parsed["name"] == "fixture-ds"
    assert "conformsTo" not in parsed
    assert "mm30" not in parsed
    r = parsed["resources"][0]
    assert r["hash"] == "sha256:abc123"
    assert r["bytes"] == 42
    assert r["schema"] == {"fields": []}


def test_parse_canonical_datapackage_yaml_round_trip():
    from science_tool.commons.datapackage import parse_canonical_datapackage_yaml

    yaml_text = """\
name: fixture-ds
resources:
  - name: r1
    path: r1.txt
    hash: sha256:a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a447
    bytes: 12
"""
    desc = parse_canonical_datapackage_yaml(yaml_text)
    assert desc["name"] == "fixture-ds"
    assert desc["resources"][0]["hash"].startswith("sha256:")
    assert desc["resources"][0]["bytes"] == 12


def test_parse_canonical_datapackage_yaml_rejects_missing_hash():
    from science_tool.commons.datapackage import parse_canonical_datapackage_yaml
    from science_tool.commons.errors import CommonsError
    import pytest

    yaml_text = """\
name: fixture-ds
resources:
  - name: r1
    path: r1.txt
"""
    with pytest.raises(CommonsError, match="hash"):
        parse_canonical_datapackage_yaml(yaml_text)
