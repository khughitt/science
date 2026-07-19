from science_tool.artifact_value_reader import ArtifactError, ResolvedArtifact, resolve_artifact


def test_real_json_under_root_resolves_content_true(tmp_path):
    project_root = tmp_path / "project"
    data_root = tmp_path / "data"
    project_root.mkdir()
    data_root.mkdir()
    (project_root / "result.json").write_text('{"x": 1}')

    resolved = resolve_artifact("result.json", project_root, data_root,
                                 max_json_bytes=1_000_000, max_feather_bytes=1_000_000)

    assert isinstance(resolved, ResolvedArtifact)
    assert resolved.kind == "json"
    assert resolved.path == (project_root / "result.json").resolve()


def test_equal_roots_resolves_not_ambiguous(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "result.json").write_text('{"x": 1}')

    resolved = resolve_artifact("result.json", root, root,
                                 max_json_bytes=1_000_000, max_feather_bytes=1_000_000)

    assert isinstance(resolved, ResolvedArtifact)
    assert resolved.kind == "json"


def test_file_under_two_distinct_roots_is_ambiguous(tmp_path):
    project_root = tmp_path / "project"
    data_root = tmp_path / "data"
    project_root.mkdir()
    data_root.mkdir()
    (project_root / "result.json").write_text('{"x": 1}')
    (data_root / "result.json").write_text('{"x": 2}')

    resolved = resolve_artifact("result.json", project_root, data_root,
                                 max_json_bytes=1_000_000, max_feather_bytes=1_000_000)

    assert isinstance(resolved, ArtifactError)
    assert "ambiguous" in resolved.detail.lower()


def test_symlink_escaping_root_is_rejected(tmp_path):
    project_root = tmp_path / "project"
    data_root = tmp_path / "data"
    outside = tmp_path / "outside"
    project_root.mkdir()
    data_root.mkdir()
    outside.mkdir()
    target = outside / "secret.json"
    target.write_text('{"x": 1}')
    link = project_root / "escape.json"
    link.symlink_to(target)

    # Verify the setup actually escapes the root before asserting on it.
    assert not link.resolve(strict=True).is_relative_to(project_root.resolve())

    resolved = resolve_artifact("escape.json", project_root, data_root,
                                 max_json_bytes=1_000_000, max_feather_bytes=1_000_000)

    assert isinstance(resolved, ArtifactError)


def test_dotdot_ref_is_rejected(tmp_path):
    project_root = tmp_path / "project"
    data_root = tmp_path / "data"
    project_root.mkdir()
    data_root.mkdir()
    (tmp_path / "result.json").write_text('{"x": 1}')

    resolved = resolve_artifact("../result.json", project_root, data_root,
                                 max_json_bytes=1_000_000, max_feather_bytes=1_000_000)

    assert isinstance(resolved, ArtifactError)


def test_absolute_ref_is_rejected(tmp_path):
    project_root = tmp_path / "project"
    data_root = tmp_path / "data"
    project_root.mkdir()
    data_root.mkdir()
    absolute = (project_root / "result.json")
    absolute.write_text('{"x": 1}')

    resolved = resolve_artifact(str(absolute), project_root, data_root,
                                 max_json_bytes=1_000_000, max_feather_bytes=1_000_000)

    assert isinstance(resolved, ArtifactError)


def test_over_cap_json_is_rejected(tmp_path):
    project_root = tmp_path / "project"
    data_root = tmp_path / "data"
    project_root.mkdir()
    data_root.mkdir()
    (project_root / "big.json").write_text('{"x": "0123456789"}')

    resolved = resolve_artifact("big.json", project_root, data_root,
                                 max_json_bytes=4, max_feather_bytes=1_000_000)

    assert isinstance(resolved, ArtifactError)


def test_missing_png_content_false_is_error_not_pass(tmp_path):
    project_root = tmp_path / "project"
    data_root = tmp_path / "data"
    project_root.mkdir()
    data_root.mkdir()

    resolved = resolve_artifact("missing.png", project_root, data_root,
                                 max_json_bytes=1_000_000, max_feather_bytes=1_000_000,
                                 content=False)

    assert isinstance(resolved, ArtifactError)


def test_directory_ref_is_rejected_content_true(tmp_path):
    project_root = tmp_path / "project"
    data_root = tmp_path / "data"
    project_root.mkdir()
    data_root.mkdir()
    (project_root / "some_dir").mkdir()

    resolved = resolve_artifact("some_dir", project_root, data_root,
                                 max_json_bytes=1_000_000, max_feather_bytes=1_000_000,
                                 content=True)

    assert isinstance(resolved, ArtifactError)


def test_directory_ref_is_rejected_content_false(tmp_path):
    project_root = tmp_path / "project"
    data_root = tmp_path / "data"
    project_root.mkdir()
    data_root.mkdir()
    (project_root / "some_dir").mkdir()

    resolved = resolve_artifact("some_dir", project_root, data_root,
                                 max_json_bytes=1_000_000, max_feather_bytes=1_000_000,
                                 content=False)

    assert isinstance(resolved, ArtifactError)


def test_contained_symlink_to_directory_is_rejected(tmp_path):
    project_root = tmp_path / "project"
    data_root = tmp_path / "data"
    project_root.mkdir()
    data_root.mkdir()
    real_dir = project_root / "real_dir"
    real_dir.mkdir()
    link = project_root / "dir_link"
    link.symlink_to(real_dir)

    # Verify the setup: the symlink stays inside root (passes containment)
    # but resolves to a directory (must fail the regular-file check, not
    # the containment check).
    resolved_link = link.resolve(strict=True)
    assert resolved_link.is_relative_to(project_root.resolve())
    assert resolved_link.is_dir()

    resolved = resolve_artifact("dir_link", project_root, data_root,
                                 max_json_bytes=1_000_000, max_feather_bytes=1_000_000,
                                 content=False)

    assert isinstance(resolved, ArtifactError)


def test_real_png_content_false_resolves_opaque(tmp_path):
    project_root = tmp_path / "project"
    data_root = tmp_path / "data"
    project_root.mkdir()
    data_root.mkdir()
    (project_root / "plot.png").write_bytes(b"\x89PNG\r\n")

    resolved = resolve_artifact("plot.png", project_root, data_root,
                                 max_json_bytes=1_000_000, max_feather_bytes=1_000_000,
                                 content=False)

    assert isinstance(resolved, ResolvedArtifact)
    assert resolved.kind == "opaque"
