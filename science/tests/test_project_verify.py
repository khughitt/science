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
    extract_bundle,
    load_bundle,
    preflight_against,
    preflight_extract,
    verdict_json,
    verify_project,
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


def test_against_payload_git_tracking_differs(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    subprocess.run(["git", "add", "-f", "data/processed/x.parquet"], cwd=proj, check=True)

    result = _against_result(bundle, proj)
    verdict = verify_project(bundle, against=proj)

    assert result.payloads == PayloadCompare(
        ok=0,
        differ=["data/processed/x.parquet"],
        missing=[],
        extra=[],
    )
    assert verdict.exit_code == 1
    assert verdict.status == "differ"


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


def test_preflight_against_no_head_is_operational(tmp_path: Path):
    repo = tmp_path / "empty-repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

    with pytest.raises(VerifyError, match="no HEAD commit"):
        preflight_against(repo)


def test_preflight_against_bare_repo_is_operational(tmp_path: Path):
    root = tmp_path / "bare.git"
    subprocess.run(["git", "init", "--bare", "-q", str(root)], check=True)

    with pytest.raises(VerifyError, match="git worktree"):
        preflight_against(root)


def test_extract_writes_faithful_tree(tmp_path: Path):
    _, bundle = _make_bundle(tmp_path)
    loaded = load_bundle(bundle)
    dest = tmp_path / "out"
    preflight_extract(dest)

    result = extract_bundle(loaded, dest)

    assert result == dest
    assert (dest / "demo" / "manifest.json").is_file()
    assert (dest / "demo" / "science.yaml").read_bytes() == loaded.members["science.yaml"]
    assert (dest / "demo" / "entities" / "questions" / "q1.md").is_file()
    assert (dest / "demo" / "manifest.json").read_bytes() == loaded.manifest_bytes


def test_extract_into_existing_empty_dir_ok(tmp_path: Path):
    _, bundle = _make_bundle(tmp_path)
    loaded = load_bundle(bundle)
    dest = tmp_path / "out"
    dest.mkdir()
    preflight_extract(dest)

    extract_bundle(loaded, dest)

    assert (dest / "demo" / "science.yaml").is_file()


def test_preflight_extract_non_empty_is_operational(tmp_path: Path):
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "preexisting").write_text("x", encoding="utf-8")

    with pytest.raises(VerifyError):
        preflight_extract(dest)


def test_preflight_extract_file_target_is_operational(tmp_path: Path):
    dest = tmp_path / "out"
    dest.write_text("i am a file", encoding="utf-8")

    with pytest.raises(VerifyError):
        preflight_extract(dest)


def test_preflight_extract_inspect_error_is_operational(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    dest = tmp_path / "out"
    dest.mkdir()

    def broken_iterdir(self: Path):
        if self == dest:
            raise OSError("simulated inspection failure")
        return original_iterdir(self)

    original_iterdir = Path.iterdir
    monkeypatch.setattr(Path, "iterdir", broken_iterdir)

    with pytest.raises(VerifyError, match="cannot inspect --extract target"):
        preflight_extract(dest)


def test_preflight_extract_symlink_target_is_operational(tmp_path: Path):
    target = tmp_path / "target"
    target.mkdir()
    dest = tmp_path / "out"
    try:
        dest.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation is not supported: {exc}")

    with pytest.raises(VerifyError, match="not a directory"):
        preflight_extract(dest)


def test_preflight_extract_broken_symlink_target_is_operational(tmp_path: Path):
    dest = tmp_path / "out"
    try:
        dest.symlink_to(tmp_path / "missing-target")
    except OSError as exc:
        pytest.skip(f"symlink creation is not supported: {exc}")

    with pytest.raises(VerifyError, match="symlink"):
        preflight_extract(dest)


def test_extract_mid_write_error_leaves_existing_dest_untouched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _, bundle = _make_bundle(tmp_path)
    loaded = load_bundle(bundle)
    dest = tmp_path / "out"
    dest.mkdir()

    original_write_bytes = Path.write_bytes

    def flaky_write_bytes(self: Path, data: bytes) -> int:
        if self.name == "science.yaml":
            raise OSError("simulated write failure")
        return original_write_bytes(self, data)

    monkeypatch.setattr(Path, "write_bytes", flaky_write_bytes)

    with pytest.raises(VerifyError):
        extract_bundle(loaded, dest)

    assert dest.exists() and dest.is_dir()
    assert list(dest.iterdir()) == []
    assert list(tmp_path.glob(".verify-extract-*")) == []


def test_verify_project_self_check_only_is_clean(tmp_path: Path):
    _, bundle = _make_bundle(tmp_path)

    result = verify_project(bundle)

    assert result.exit_code == 0
    assert result.status == "clean"
    assert result.bundle_schema_version == "science-project-serialized.v1"
    assert result.project_id == "demo"
    assert result.file_count == 2
    assert result.against is None
    assert result.warnings == []
    assert result.extracted_to is None


def test_verify_project_round_trip_against_clean(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    target = tmp_path / "target"
    _copy_checkout(proj, target)

    result = verify_project(bundle, against=target)

    assert result.exit_code == 0
    assert result.status == "clean"
    assert result.against == _against_result(bundle, target)


def test_verify_project_missing_payload_is_exit_3(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    target = tmp_path / "target"
    _copy_checkout(proj, target)
    (target / "data" / "processed" / "x.parquet").unlink()

    result = verify_project(bundle, against=target)

    assert result.exit_code == 3
    assert result.status == "missing"


def test_verify_project_wraps_payload_inventory_os_error(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    (proj / "data" / "processed" / "x.parquet").unlink()
    (proj / "data" / "processed").rmdir()
    (proj / "data" / "processed").write_text("not a directory\n", encoding="utf-8")

    with pytest.raises(VerifyError, match="payload inventory failed.*data/processed"):
        verify_project(bundle, against=proj)


def test_verify_project_wraps_invalid_configured_data_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    proj, bundle = _make_bundle(tmp_path)
    monkeypatch.setenv("SCIENCE_DATA_ROOT", "relative-data")

    with pytest.raises(VerifyError, match="SCIENCE_DATA_ROOT must be absolute"):
        verify_project(bundle, against=proj)


def test_verify_project_differ_dominates_missing(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    target = tmp_path / "target"
    _copy_checkout(proj, target)
    (target / "science.yaml").write_text("id: demo\nname: Changed\n", encoding="utf-8")
    (target / "data" / "processed" / "x.parquet").unlink()

    result = verify_project(bundle, against=target)

    assert result.exit_code == 1
    assert result.status == "differ"


def test_verify_project_preflight_runs_before_compare(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    proj, bundle = _make_bundle(tmp_path)
    target = tmp_path / "target"
    _copy_checkout(proj, target)
    extract = tmp_path / "out"
    extract.mkdir()
    (extract / "preexisting").write_text("x", encoding="utf-8")

    def fail_if_compared(*args: object, **kwargs: object) -> AgainstResult:
        raise AssertionError("compare should not run after extract preflight failure")

    monkeypatch.setattr(verify, "compare_against", fail_if_compared)

    with pytest.raises(VerifyError, match="not empty"):
        verify_project(bundle, against=target, extract=extract)


def test_verify_project_extract_and_against_combine(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    target = tmp_path / "target"
    _copy_checkout(proj, target)
    extract = tmp_path / "out"

    result = verify_project(bundle, against=target, extract=extract)

    assert result.exit_code == 0
    assert result.status == "clean"
    assert result.against == _against_result(bundle, target)
    assert result.extracted_to == extract
    assert (extract / "demo" / "science.yaml").is_file()


def test_force_built_bundle_warns(tmp_path: Path):
    project = tmp_path / "forced"
    project.mkdir()
    (project / "science.yaml").write_text("id: demo\nname: Demo\n", encoding="utf-8")
    (project / "data" / "processed" / "exp").mkdir(parents=True)
    (project / "data" / "processed" / "exp" / "RESULTS.md").write_text("# results\n", encoding="utf-8")
    _init_repo(project)
    subprocess.run(["git", "add", "-A"], cwd=project, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "forced"], cwd=project, check=True)
    bundle = tmp_path / "forced.tar.gz"
    serialize_project(project, bundle, force=True)

    result = verify_project(bundle)

    assert result.warnings == ["bundle built with --force; payload boundary was not clean at serialize time"]


def test_verdict_json_shape(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    target = tmp_path / "target"
    _copy_checkout(proj, target)
    result = verify_project(bundle, against=target)

    payload = verdict_json(result)

    assert payload == {
        "version": 1,
        "bundle_schema_version": "science-project-serialized.v1",
        "exit_code": 0,
        "status": "clean",
        "self_check": {
            "passed": True,
            "files": 2,
            "data_version": result.data_version,
        },
        "against": {
            "root": str(target),
            "commit": {
                "bundle": result.against.commit.bundle,
                "head": result.against.commit.head,
                "match": True,
            },
            "source": {
                "total": 2,
                "match": 2,
                "differ": [],
                "absent": [],
            },
            "payloads": {
                "ok": 1,
                "differ": [],
                "missing": [],
                "extra": [],
            },
        },
        "warnings": [],
    }
    assert "file_count" not in payload["self_check"]
    assert set(payload["against"]) == {"root", "commit", "source", "payloads"}
