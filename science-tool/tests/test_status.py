"""Drift classification: 7 states across (header?, hash known?, pin?)."""

from pathlib import Path


from science_tool.project_artifacts.registry_schema import (
    Artifact,
    Pin,
)
from science_tool.project_artifacts.status import Status, classify


def _artifact(current_hash: str, prev: list[tuple[str, str]] | None = None) -> Artifact:
    return Artifact.model_validate(
        {
            "name": "validate.sh",
            "source": "data/validate.sh",
            "install_target": "validate.sh",
            "description": "d",
            "content_type": "text",
            "newline": "lf",
            "mode": "0755",
            "consumer": "direct_execute",
            "header_protocol": {"kind": "shebang_comment", "comment_prefix": "#"},
            "extension_protocol": {
                "kind": "sourced_sidecar",
                "sidecar_path": "validate.local.sh",
                "hook_namespace": "SCIENCE_VALIDATE_HOOKS",
            },
            "mutation_policy": {},
            "version": "2026.04.26",
            "current_hash": current_hash,
            "previous_hashes": [{"version": v, "hash": h} for v, h in (prev or [])],
            "migrations": [],
            "changelog": {"2026.04.26": "x"},
        }
    )


def _write(
    path: Path, body: bytes, *, with_header: bool = True, hash_in_header: str = "a" * 64, version: str = "2026.04.26"
) -> None:
    if with_header:
        content = (
            b"#!/usr/bin/env bash\n"
            b"# science-managed-artifact: validate.sh\n"
            + f"# science-managed-version: {version}\n".encode()
            + f"# science-managed-source-sha256: {hash_in_header}\n".encode()
            + body
        )
    else:
        content = body
    path.write_bytes(content)


def test_missing(tmp_path: Path) -> None:
    art = _artifact("a" * 64)
    assert classify(tmp_path / "validate.sh", art, []) is Status.MISSING


def test_untracked_no_header(tmp_path: Path) -> None:
    art = _artifact("a" * 64)
    target = tmp_path / "validate.sh"
    _write(target, b"echo hi\n", with_header=False)
    assert classify(target, art, []) is Status.UNTRACKED


def test_current(tmp_path: Path) -> None:
    import hashlib

    body = b"echo body\n"
    h = hashlib.sha256(body).hexdigest()
    art = _artifact(h)
    target = tmp_path / "validate.sh"
    _write(target, body, hash_in_header=h)
    assert classify(target, art, []) is Status.CURRENT


def test_stale(tmp_path: Path) -> None:
    import hashlib

    body = b"echo body\n"
    body_h = hashlib.sha256(body).hexdigest()
    art = _artifact("0" * 64, prev=[("2026.04.20", body_h)])
    target = tmp_path / "validate.sh"
    _write(target, body, hash_in_header=body_h, version="2026.04.20")
    assert classify(target, art, []) is Status.STALE


def test_locally_modified(tmp_path: Path) -> None:
    art = _artifact("a" * 64)
    target = tmp_path / "validate.sh"
    _write(target, b"echo modified\n", hash_in_header="a" * 64)
    assert classify(target, art, []) is Status.LOCALLY_MODIFIED


def test_pinned_current(tmp_path: Path) -> None:
    import hashlib

    body = b"echo old body\n"
    body_h = hashlib.sha256(body).hexdigest()
    art = _artifact("a" * 64, prev=[("2026.04.20", body_h)])
    pin = Pin(name="validate.sh", pinned_to="2026.04.20", pinned_hash=body_h, rationale="r", revisit_by="2026-06-01")
    target = tmp_path / "validate.sh"
    _write(target, body, hash_in_header=body_h, version="2026.04.20")
    assert classify(target, art, [pin]) is Status.PINNED


def test_pinned_but_locally_modified(tmp_path: Path) -> None:
    import hashlib

    pinned_h = hashlib.sha256(b"echo pinned\n").hexdigest()
    art = _artifact("a" * 64, prev=[("2026.04.20", pinned_h)])
    pin = Pin(name="validate.sh", pinned_to="2026.04.20", pinned_hash=pinned_h, rationale="r", revisit_by="2026-06-01")
    target = tmp_path / "validate.sh"
    _write(target, b"echo not pinned bytes\n", hash_in_header=pinned_h, version="2026.04.20")
    assert classify(target, art, [pin]) is Status.PINNED_BUT_LOCALLY_MODIFIED
