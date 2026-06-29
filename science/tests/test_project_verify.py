import gzip
import io
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

from science_tool.project_package.serialize import serialize_project
from science_tool.project_package.verify import (
    AgainstResult,
    BundleIntegrityError,
    CommitCompare,
    PayloadCompare,
    SourceCompare,
    VerifyError,
    compare_against,
    load_bundle,
    preflight_against,
)
import science_tool.project_package.verify as verify


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)


def _make_project(root: Path) -> None:
    (root / "entities" / "questions").mkdir(parents=True)
    (root / "science.yaml").write_text("id: demo\nname: Demo\n", encoding="utf-8")
    (root / "entities" / "questions" / "q1.md").write_text("# q\n", encoding="utf-8")
    # data/ is gitignored (the normal symlink-hydrated payload case): an
    # UNtracked payload, so serialize records it without a TRACKED_PAYLOAD
    # boundary violation. Tracking it would make serialize refuse without --force.
    (root / ".gitignore").write_text("data/\n", encoding="utf-8")
    (root / "data" / "processed").mkdir(parents=True)
    (root / "data" / "processed" / "x.parquet").write_bytes(b"PAYLOAD")
    _init_repo(root)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=root, check=True)


def _make_bundle(tmp_path: Path) -> tuple[Path, Path]:
    proj = tmp_path / "proj"
    proj.mkdir()
    _make_project(proj)
    bundle = tmp_path / "bundle.tar.gz"
    serialize_project(proj, bundle)
    return proj, bundle


def _copy_checkout(source: Path, target: Path) -> None:
    shutil.copytree(source, target)


def _against_result(bundle_path: Path, target: Path) -> AgainstResult:
    loaded = load_bundle(bundle_path)
    head = preflight_against(target)
    return compare_against(loaded, target, head)


def _write_bundle(path: Path, members: dict[str, bytes]) -> None:
    raw = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for name, data in sorted(members.items()):
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mtime = 0
                tar.addfile(info, io.BytesIO(data))
    path.write_bytes(raw.getvalue())


def _write_raw_bundle(path: Path, members: list[tuple[str, bytes]]) -> None:
    raw = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for name, data in members:
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mtime = 0
                tar.addfile(info, io.BytesIO(data))
    path.write_bytes(raw.getvalue())


def test_load_bundle_self_check_passes(tmp_path: Path):
    _, bundle = _make_bundle(tmp_path)
    loaded = load_bundle(bundle)
    assert loaded.project_id == "demo"
    assert "science.yaml" in loaded.members
    assert "manifest.json" not in loaded.members
    assert loaded.manifest.payloads[0].path == "data/processed/x.parquet"


def test_load_bundle_missing_file_is_operational(tmp_path: Path):
    with pytest.raises(VerifyError):
        load_bundle(tmp_path / "nope.tar.gz")


def test_load_bundle_not_a_tar_is_integrity(tmp_path: Path):
    bad = tmp_path / "bad.tar.gz"
    bad.write_bytes(b"not a gzip stream")
    with pytest.raises(BundleIntegrityError):
        load_bundle(bad)


def test_load_bundle_root_level_manifest_is_integrity(tmp_path: Path):
    bad = tmp_path / "bad.tar.gz"
    _write_bundle(bad, {"manifest.json": b"{}"})  # no project-id prefix
    with pytest.raises(BundleIntegrityError):
        load_bundle(bad)


def test_load_bundle_mixed_prefixes_is_integrity(tmp_path: Path):
    _, bundle = _make_bundle(tmp_path)
    # repack original members plus one under a different prefix
    with tarfile.open(bundle, "r:gz") as tar:
        members = {m.name: tar.extractfile(m).read() for m in tar.getmembers()}
    members["other/stray.md"] = b"x"
    bad = tmp_path / "mixed.tar.gz"
    _write_bundle(bad, members)
    with pytest.raises(BundleIntegrityError):
        load_bundle(bad)


def test_load_bundle_tampered_byte_is_integrity(tmp_path: Path):
    _, bundle = _make_bundle(tmp_path)
    with tarfile.open(bundle, "r:gz") as tar:
        members = {m.name: tar.extractfile(m).read() for m in tar.getmembers()}
    members["demo/science.yaml"] = members["demo/science.yaml"] + b"TAMPER"
    bad = tmp_path / "tampered.tar.gz"
    _write_bundle(bad, members)
    with pytest.raises(BundleIntegrityError):
        load_bundle(bad)


def test_load_bundle_extra_member_is_integrity(tmp_path: Path):
    _, bundle = _make_bundle(tmp_path)
    with tarfile.open(bundle, "r:gz") as tar:
        members = {m.name: tar.extractfile(m).read() for m in tar.getmembers()}
    members["demo/entities/questions/stray.md"] = b"# stray\n"
    bad = tmp_path / "extra.tar.gz"
    _write_bundle(bad, members)
    with pytest.raises(BundleIntegrityError):
        load_bundle(bad)


def test_load_bundle_edited_data_version_is_integrity(tmp_path: Path):
    _, bundle = _make_bundle(tmp_path)
    with tarfile.open(bundle, "r:gz") as tar:
        members = {m.name: tar.extractfile(m).read() for m in tar.getmembers()}
    manifest = json.loads(members["demo/manifest.json"])
    manifest["data_version"] = "0+deadbeefdead"
    members["demo/manifest.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    bad = tmp_path / "dv.tar.gz"
    _write_bundle(bad, members)
    with pytest.raises(BundleIntegrityError):
        load_bundle(bad)


def test_load_bundle_prefix_ne_project_id_is_integrity(tmp_path: Path):
    _, bundle = _make_bundle(tmp_path)
    with tarfile.open(bundle, "r:gz") as tar:
        members = {m.name.replace("demo/", "other/", 1): tar.extractfile(m).read() for m in tar.getmembers()}
    bad = tmp_path / "prefix.tar.gz"
    _write_bundle(bad, members)
    with pytest.raises(BundleIntegrityError):
        load_bundle(bad)


def test_load_bundle_symlink_member_is_integrity(tmp_path: Path):
    _, bundle = _make_bundle(tmp_path)
    with tarfile.open(bundle, "r:gz") as tar:
        members = {m.name: tar.extractfile(m).read() for m in tar.getmembers()}
    raw = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for name, data in sorted(members.items()):
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            link = tarfile.TarInfo("demo/evil-link")
            link.type = tarfile.SYMTYPE
            link.linkname = "/etc/passwd"
            tar.addfile(link)
    bad = tmp_path / "symlink.tar.gz"
    bad.write_bytes(raw.getvalue())
    with pytest.raises(BundleIntegrityError):
        load_bundle(bad)


def test_load_bundle_hardlink_member_is_integrity(tmp_path: Path):
    _, bundle = _make_bundle(tmp_path)
    with tarfile.open(bundle, "r:gz") as tar:
        members = {m.name: tar.extractfile(m).read() for m in tar.getmembers()}
    raw = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for name, data in sorted(members.items()):
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            link = tarfile.TarInfo("demo/evil-hardlink")
            link.type = tarfile.LNKTYPE
            link.linkname = "demo/science.yaml"
            tar.addfile(link)
    bad = tmp_path / "hardlink.tar.gz"
    bad.write_bytes(raw.getvalue())
    with pytest.raises(BundleIntegrityError):
        load_bundle(bad)


def test_load_bundle_duplicate_member_is_integrity(tmp_path: Path):
    _, bundle = _make_bundle(tmp_path)
    with tarfile.open(bundle, "r:gz") as tar:
        members = [(m.name, tar.extractfile(m).read()) for m in tar.getmembers()]
    # Append a second copy of an existing source member (same arcname twice).
    dup_name, dup_data = next((n, d) for n, d in members if n.endswith("science.yaml"))
    raw = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for name, data in [*members, (dup_name, dup_data)]:
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
    bad = tmp_path / "dup.tar.gz"
    bad.write_bytes(raw.getvalue())
    with pytest.raises(BundleIntegrityError):
        load_bundle(bad)


def test_load_bundle_member_count_over_limit_is_integrity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(verify, "MAX_ARCHIVE_MEMBERS", 1)
    bad = tmp_path / "too-many.tar.gz"
    _write_bundle(
        bad,
        {
            "demo/manifest.json": b"{}",
            "demo/science.yaml": b"id: demo\n",
        },
    )
    with pytest.raises(BundleIntegrityError, match="member count exceeds limit"):
        load_bundle(bad)


def test_load_bundle_member_size_over_limit_is_integrity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(verify, "MAX_MEMBER_BYTES", 3)
    bad = tmp_path / "too-large.tar.gz"
    _write_bundle(bad, {"demo/manifest.json": b"{}{}"})
    with pytest.raises(BundleIntegrityError, match="exceeds size limit"):
        load_bundle(bad)


def test_load_bundle_total_uncompressed_bytes_over_limit_is_integrity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(verify, "MAX_TOTAL_UNCOMPRESSED_BYTES", 4)
    bad = tmp_path / "too-large-total.tar.gz"
    _write_bundle(
        bad,
        {
            "demo/manifest.json": b"{}",
            "demo/science.yaml": b"xxx",
        },
    )
    with pytest.raises(
        BundleIntegrityError,
        match="total uncompressed size exceeds limit",
    ):
        load_bundle(bad)


def test_load_bundle_absolute_member_path_is_integrity(tmp_path: Path):
    bad = tmp_path / "absolute.tar.gz"
    _write_raw_bundle(bad, [("/demo/manifest.json", b"{}")])
    with pytest.raises(BundleIntegrityError, match="unsafe archive member path"):
        load_bundle(bad)


def test_load_bundle_traversal_member_path_is_integrity(tmp_path: Path):
    bad = tmp_path / "traversal.tar.gz"
    _write_raw_bundle(bad, [("demo/../manifest.json", b"{}")])
    with pytest.raises(BundleIntegrityError, match="unsafe archive member path"):
        load_bundle(bad)


def test_against_clean_checkout_matches(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    target = tmp_path / "target"
    _copy_checkout(proj, target)

    result = _against_result(bundle, target)

    head = subprocess.run(
        ["git", "-C", str(target), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert result == AgainstResult(
        root=str(target),
        commit=CommitCompare(bundle=head, head=head, match=True),
        source=SourceCompare(total=2, match=2, differ=[], absent=[]),
        payloads=PayloadCompare(ok=1, differ=[], missing=[], extra=[]),
    )


def test_against_payload_missing(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    target = tmp_path / "target"
    _copy_checkout(proj, target)
    (target / "data" / "processed" / "x.parquet").unlink()

    result = _against_result(bundle, target)

    assert result.payloads == PayloadCompare(
        ok=0,
        differ=[],
        missing=["data/processed/x.parquet"],
        extra=[],
    )


def test_against_payload_differs(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    target = tmp_path / "target"
    _copy_checkout(proj, target)
    (target / "data" / "processed" / "x.parquet").write_bytes(b"CHANGED")

    result = _against_result(bundle, target)

    assert result.payloads == PayloadCompare(
        ok=0,
        differ=["data/processed/x.parquet"],
        missing=[],
        extra=[],
    )


def test_against_payload_extra_is_non_fatal(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    target = tmp_path / "target"
    _copy_checkout(proj, target)
    (target / "data" / "processed" / "extra.parquet").write_bytes(b"EXTRA")

    result = _against_result(bundle, target)

    assert result.payloads == PayloadCompare(
        ok=1,
        differ=[],
        missing=[],
        extra=["data/processed/extra.parquet"],
    )


def test_against_source_differs(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    target = tmp_path / "target"
    _copy_checkout(proj, target)
    (target / "science.yaml").write_text("id: demo\nname: Changed\n", encoding="utf-8")

    result = _against_result(bundle, target)

    assert result.source == SourceCompare(
        total=2,
        match=1,
        differ=["science.yaml"],
        absent=[],
    )


def test_against_source_absent(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    target = tmp_path / "target"
    _copy_checkout(proj, target)
    (target / "entities" / "questions" / "q1.md").unlink()

    result = _against_result(bundle, target)

    assert result.source == SourceCompare(
        total=2,
        match=1,
        differ=[],
        absent=["entities/questions/q1.md"],
    )


def test_against_commit_differs_after_new_commit(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    target = tmp_path / "target"
    _copy_checkout(proj, target)
    (target / "doc").mkdir()
    (target / "doc" / "note.md").write_text("note\n", encoding="utf-8")
    subprocess.run(["git", "add", "doc/note.md"], cwd=target, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "new commit"], cwd=target, check=True)

    result = _against_result(bundle, target)

    assert result.commit.match is False
    assert result.commit.bundle != result.commit.head
    assert result.source == SourceCompare(total=2, match=2, differ=[], absent=[])
    assert result.payloads == PayloadCompare(ok=1, differ=[], missing=[], extra=[])


def test_preflight_against_non_git_is_operational(tmp_path: Path):
    root = tmp_path / "not-git"
    root.mkdir()

    with pytest.raises(VerifyError, match="git worktree"):
        preflight_against(root)


def test_preflight_against_bare_repo_is_operational(tmp_path: Path):
    root = tmp_path / "bare.git"
    subprocess.run(["git", "init", "--bare", "-q", str(root)], check=True)

    with pytest.raises(VerifyError, match="git worktree"):
        preflight_against(root)
