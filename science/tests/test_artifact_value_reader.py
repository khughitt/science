from decimal import Decimal
from pathlib import Path

import pytest

from science_tool.artifact_value_reader import (
    ArtifactError,
    ReaderError,
    ResolvedArtifact,
    read_scalar,
    resolve_artifact,
)
from science_tool.numeric_binding import ColumnLocator, PointerLocator


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


# --- read_scalar ------------------------------------------------------------
#
# Fixtures under tests/fixtures/numeric_verification/ are built once by the
# committed `_build.py` helper (run it to regenerate, do not hand-edit the
# generated files). `read_scalar` is exercised directly against
# `ResolvedArtifact` values pointed at those fixtures -- no need to route
# through `resolve_artifact` since the fixtures are read-only test data, not
# security-sensitive path input.

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "numeric_verification"
_RESULTS_JSON = ResolvedArtifact(path=_FIXTURES_DIR / "results.json", kind="json")
_NONFINITE_JSON = ResolvedArtifact(path=_FIXTURES_DIR / "nonfinite.json", kind="json")
_SUMMARY_FEATHER = ResolvedArtifact(path=_FIXTURES_DIR / "summary.feather", kind="feather")
_PER_DISEASE_FEATHER = ResolvedArtifact(path=_FIXTURES_DIR / "per_disease.feather", kind="feather")


def test_json_scalar_fidelity_survives_binary_float_corruption():
    # 0.100000000000000005 is not exactly representable in binary float; a
    # float->str round trip collapses it to "0.1". This only passes if the
    # JSON number is parsed directly to Decimal (parse_float=Decimal), never
    # routed through a Python float.
    value = read_scalar(_RESULTS_JSON, PointerLocator(pointer="/that_key"))
    assert value == Decimal("0.100000000000000005")
    assert str(value) != "0.1"


def test_json_pointer_indexes_list_numerically():
    value = read_scalar(_RESULTS_JSON, PointerLocator(pointer="/a/0"))
    assert value == Decimal(1)


def test_json_pointer_unescapes_tilde_one_as_slash():
    value = read_scalar(_RESULTS_JSON, PointerLocator(pointer="/nested/b~1c"))
    assert value == Decimal(42)


def test_json_pointer_unescapes_tilde_zero_as_tilde():
    value = read_scalar(_RESULTS_JSON, PointerLocator(pointer="/nested/d~0e"))
    assert value == Decimal(43)


def test_json_pointer_miss_is_reader_error():
    result = read_scalar(_RESULTS_JSON, PointerLocator(pointer="/does/not/exist"))
    assert isinstance(result, ReaderError)


def test_json_pointer_out_of_range_index_is_reader_error():
    result = read_scalar(_RESULTS_JSON, PointerLocator(pointer="/a/99"))
    assert isinstance(result, ReaderError)


@pytest.mark.parametrize(
    "pointer",
    ["/list_node", "/obj_node", "/bool_node", "/null_node", "/s_node"],
    ids=["list", "dict", "bool", "null", "string"],
)
def test_json_non_scalar_or_non_numeric_node_is_reader_error(pointer):
    result = read_scalar(_RESULTS_JSON, PointerLocator(pointer=pointer))
    assert isinstance(result, ReaderError)


def test_json_nonfinite_literal_is_reader_error():
    result = read_scalar(_NONFINITE_JSON, PointerLocator(pointer="/n"))
    assert isinstance(result, ReaderError)


def test_feather_single_row_hit_no_where():
    value = read_scalar(_SUMMARY_FEATHER, ColumnLocator(column="score"))
    assert value == Decimal("0.978")


def test_feather_keyed_row_hit_proves_union_load():
    # `where` uses "disease", a column distinct from the value column
    # "score" -- this only passes if the reader loads the union of
    # [column] + where.keys(), not just [column].
    value = read_scalar(
        _PER_DISEASE_FEATHER,
        ColumnLocator(column="score", where={"disease": "MESH:D009101"}),
    )
    assert value == Decimal("0.42")


def test_feather_zero_match_is_reader_error():
    result = read_scalar(
        _PER_DISEASE_FEATHER,
        ColumnLocator(column="score", where={"disease": "NOT_A_REAL_DISEASE"}),
    )
    assert isinstance(result, ReaderError)


def test_feather_multi_match_with_where_is_reader_error():
    result = read_scalar(
        _PER_DISEASE_FEATHER,
        ColumnLocator(column="score", where={"disease": "DUP"}),
    )
    assert isinstance(result, ReaderError)


def test_feather_multi_row_no_where_is_reader_error():
    result = read_scalar(_PER_DISEASE_FEATHER, ColumnLocator(column="score"))
    assert isinstance(result, ReaderError)


def test_feather_missing_value_column_is_reader_error():
    result = read_scalar(_PER_DISEASE_FEATHER, ColumnLocator(column="not_a_column"))
    assert isinstance(result, ReaderError)


def test_feather_missing_where_column_is_reader_error():
    result = read_scalar(
        _PER_DISEASE_FEATHER,
        ColumnLocator(column="score", where={"not_a_column": "x"}),
    )
    assert isinstance(result, ReaderError)


def test_feather_nan_cell_is_reader_error():
    result = read_scalar(
        _PER_DISEASE_FEATHER,
        ColumnLocator(column="score", where={"disease": "NAN_ROW"}),
    )
    assert isinstance(result, ReaderError)
