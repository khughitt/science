from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from science_model.evidence_broker import Outcome, SurfacePolicy

from science_tool.evidence_broker.hits import parse_hits
from science_tool.evidence_broker.policy import EvidenceOp, EvidenceRequest
from science_tool.evidence_broker.serve import serve

COMMIT = "a" * 40
OPEN = SurfacePolicy(notice="withheld")


def test_parse_hits_preserves_colons_and_nuls_in_content() -> None:
    payload = f"{COMMIT}:a:b.txt".encode() + b"\0" + b"7\0before\0after\n"
    assert parse_hits(payload, COMMIT) == (("a:b.txt", 7),)


def test_parse_hits_uses_lf_not_splitlines() -> None:
    payload = f"{COMMIT}:a.txt".encode() + b"\0" + b"1\0left\rright\n"
    assert parse_hits(payload, COMMIT) == (("a.txt", 1),)


def test_parse_hits_preserves_lf_and_commit_prefix_in_a_path() -> None:
    path = f"a\n{COMMIT}:b.txt"
    payload = f"{COMMIT}:{path}".encode() + b"\0" + b"3\0hit\n"
    assert parse_hits(payload, COMMIT) == ((path, 3),)


@pytest.mark.parametrize(
    "payload",
    [
        b"missing-nuls\n",
        f"{'b' * 40}:a.txt\0".encode() + b"1\0hit\n",
        f"{COMMIT}:a.txt\0zero\0hit\n".encode(),
        f"{COMMIT}:a.txt".encode() + b"\x000\x00hit\n",
        f"{COMMIT}:a.txt".encode() + b"\x001\x00truncated",
    ],
)
def test_parse_hits_refuses_noncanonical_records(payload: bytes) -> None:
    with pytest.raises(ValueError):
        parse_hits(payload, COMMIT)


def _repo(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    for args in (
        ("init", "-q"),
        ("config", "user.email", "p@example.invalid"),
        ("config", "user.name", "P"),
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    (root / "a:b.bin").write_bytes(b"first\nneedle\0tail\n")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "seed"],
        check=True,
        capture_output=True,
    )
    commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True
    ).stdout.decode().strip()
    return root, commit


def test_parse_hits_accepts_the_real_canonical_git_payload(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    result = serve(
        root,
        commit,
        EvidenceRequest(op=EvidenceOp.SEARCH, target="needle"),
        OPEN,
    )
    assert result.outcome is Outcome.SERVED
    assert b"\0tail" in result.payload
    assert parse_hits(result.payload, commit) == (("a:b.bin", 2),)


def test_parse_hits_accepts_a_real_git_lf_filename(tmp_path: Path) -> None:
    root, _commit = _repo(tmp_path)
    path = "a\nb.txt"
    (root / path).write_text("lf-needle\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "add LF filename"],
        check=True,
        capture_output=True,
    )
    commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True
    ).stdout.decode().strip()
    result = serve(
        root,
        commit,
        EvidenceRequest(op=EvidenceOp.SEARCH, target="lf-needle"),
        OPEN,
    )
    assert result.outcome is Outcome.SERVED
    assert f"{commit}:{path}".encode() + b"\0" in result.payload
    assert parse_hits(result.payload, commit) == ((path, 1),)
