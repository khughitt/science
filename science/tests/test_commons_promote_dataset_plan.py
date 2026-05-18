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
