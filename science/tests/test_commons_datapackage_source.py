"""Tests for the datapackage `source` descriptor (ResourceSource + validate_source)."""
from __future__ import annotations

import textwrap

import pytest

from science_tool.commons.datapackage import (
    OUTPUT_ROOT_TOKEN,
    SOURCE_TYPES,
    Resolved,
    ResourceSource,
    Unexpandable,
    parse_canonical_datapackage_yaml,
    read_datapackage,
    render_canonical_datapackage_yaml,
    resolve_local_ref,
    validate_source,
)
from science_tool.commons.errors import CommonsDatapackageError, CommonsError

VALID_HASH = "sha256:" + "a" * 64


def _write_dp(tmp_path, body: str):
    p = tmp_path / "datapackage.yaml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def test_source_types_enum():
    assert SOURCE_TYPES == frozenset({"local", "zenodo", "github", "url", "daemon"})
    assert OUTPUT_ROOT_TOKEN == "${OUTPUT_ROOT}"


@pytest.mark.parametrize(
    "ref",
    [
        "/data/proj/mm30/8.0/scrna/walker2024.h5ad",  # absolute
        "${OUTPUT_ROOT}",                              # bare token
        "${OUTPUT_ROOT}/scrna/walker2024.h5ad",        # token + subpath
    ],
)
def test_validate_source_accepts_local_ref(ref):
    src = validate_source({"type": "local", "ref": ref})
    assert src == ResourceSource(type="local", ref=ref)


@pytest.mark.parametrize(
    "ref",
    [
        "scrna/walker2024.h5ad",        # plain relative
        "",                             # empty
        "   ",                          # whitespace
        "${OUTPUT_ROOT}foo",            # token not followed by '/' or end
        "${SCRATCH}/x.h5ad",            # a different token
        "${OUTPUT_ROOT/x",              # syntactically broken token
        "${OUTPUT_ROOT}/",              # bare token + trailing slash, no subpath
    ],
)
def test_validate_source_rejects_bad_local_ref(ref):
    with pytest.raises(ValueError):
        validate_source({"type": "local", "ref": ref})


def test_validate_source_accepts_url():
    src = validate_source({"type": "url", "ref": "https://example.org/x.h5ad"})
    assert src == ResourceSource(type="url", ref="https://example.org/x.h5ad")


@pytest.mark.parametrize(
    "ref",
    [
        "ftp://example.org/x",  # wrong scheme
        "example.org/x",        # no scheme
        "",                     # empty
        "https://",             # scheme but no host
        "https:///x.h5ad",      # scheme + path but empty host
    ],
)
def test_validate_source_rejects_bad_url(ref):
    with pytest.raises(ValueError):
        validate_source({"type": "url", "ref": ref})


@pytest.mark.parametrize("type_", ["zenodo", "github", "daemon"])
def test_validate_source_accepts_opaque_remote(type_):
    src = validate_source({"type": type_, "ref": "10.5281/zenodo.123"})
    assert src.type == type_ and src.ref == "10.5281/zenodo.123"


@pytest.mark.parametrize("type_", ["zenodo", "github", "daemon"])
def test_validate_source_rejects_blank_opaque_remote(type_):
    with pytest.raises(ValueError):
        validate_source({"type": type_, "ref": "   "})


def test_validate_source_rejects_unknown_type():
    with pytest.raises(ValueError, match="type"):
        validate_source({"type": "s3", "ref": "/x"})


def test_validate_source_rejects_non_mapping():
    with pytest.raises(ValueError):
        validate_source("local")


def test_validate_source_rejects_missing_or_nonstring_ref():
    with pytest.raises(ValueError):
        validate_source({"type": "local"})
    with pytest.raises(ValueError):
        validate_source({"type": "local", "ref": 123})


def test_validate_source_rejects_missing_type():
    with pytest.raises(ValueError, match="type"):
        validate_source({"ref": "/data/x.h5ad"})


def test_resolve_absolute_ref_existing(tmp_path, monkeypatch):
    monkeypatch.delenv("OUTPUT_ROOT", raising=False)
    f = tmp_path / "x.h5ad"
    f.write_bytes(b"abc")
    res = resolve_local_ref(str(f))
    assert isinstance(res, Resolved)
    assert res.path == f and res.exists is True


def test_resolve_absolute_ref_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("OUTPUT_ROOT", raising=False)
    res = resolve_local_ref(str(tmp_path / "nope.h5ad"))
    assert isinstance(res, Resolved) and res.exists is False


def test_resolve_token_unexpandable_when_env_unset(monkeypatch):
    monkeypatch.delenv("OUTPUT_ROOT", raising=False)
    assert isinstance(resolve_local_ref("${OUTPUT_ROOT}/scrna/x.h5ad"), Unexpandable)


def test_resolve_bare_token_unexpandable_when_env_unset(monkeypatch):
    monkeypatch.delenv("OUTPUT_ROOT", raising=False)
    res = resolve_local_ref("${OUTPUT_ROOT}")
    assert isinstance(res, Unexpandable) and res.ref == "${OUTPUT_ROOT}"


def test_resolve_token_expands_against_env(tmp_path, monkeypatch):
    (tmp_path / "scrna").mkdir()
    f = tmp_path / "scrna" / "x.h5ad"
    f.write_bytes(b"abc")
    monkeypatch.setenv("OUTPUT_ROOT", str(tmp_path))
    res = resolve_local_ref("${OUTPUT_ROOT}/scrna/x.h5ad")
    assert isinstance(res, Resolved) and res.path == f and res.exists is True


def test_resolve_bare_token_expands_to_root(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_ROOT", str(tmp_path))
    res = resolve_local_ref("${OUTPUT_ROOT}")
    assert isinstance(res, Resolved) and res.path == tmp_path


def test_resolve_raises_when_output_root_blank(monkeypatch):
    monkeypatch.setenv("OUTPUT_ROOT", "   ")
    with pytest.raises(ValueError, match="OUTPUT_ROOT"):
        resolve_local_ref("${OUTPUT_ROOT}/x.h5ad")


def test_resolve_raises_when_output_root_relative(monkeypatch):
    monkeypatch.setenv("OUTPUT_ROOT", "relative/dir")
    with pytest.raises(ValueError, match="OUTPUT_ROOT"):
        resolve_local_ref("${OUTPUT_ROOT}/x.h5ad")


def test_read_datapackage_surfaces_source(tmp_path):
    p = _write_dp(
        tmp_path,
        f"""\
        name: ds
        resources:
          - name: walker
            path: walker2024.h5ad
            hash: {VALID_HASH}
            bytes: 14010935296
            source:
              type: local
              ref: ${{OUTPUT_ROOT}}/scrna/walker2024.h5ad
        """,
    )
    desc = read_datapackage(p)
    src = desc.resources[0].source
    assert src is not None
    assert src.type == "local"
    assert src.ref == "${OUTPUT_ROOT}/scrna/walker2024.h5ad"


def test_read_datapackage_source_absent_is_none(tmp_path):
    p = _write_dp(
        tmp_path,
        f"""\
        name: ds
        resources:
          - name: r1
            path: r1.txt
            hash: {VALID_HASH}
            bytes: 12
        """,
    )
    assert read_datapackage(p).resources[0].source is None


def test_read_datapackage_rejects_bad_source(tmp_path):
    p = _write_dp(
        tmp_path,
        f"""\
        name: ds
        resources:
          - name: r1
            path: r1.txt
            hash: {VALID_HASH}
            bytes: 12
            source:
              type: local
              ref: relative/path.h5ad
        """,
    )
    with pytest.raises(CommonsDatapackageError, match="source"):
        read_datapackage(p)


def test_parse_canonical_validates_source():
    text = textwrap.dedent(
        f"""\
        name: ds
        resources:
          - name: r1
            path: r1.txt
            hash: {VALID_HASH}
            bytes: 12
            source:
              type: bogus
              ref: x
        """
    )
    with pytest.raises(CommonsError, match="source"):
        parse_canonical_datapackage_yaml(text)


def test_render_preserves_source_verbatim():
    project_doc = {
        "name": "ds",
        "resources": [
            {
                "name": "walker",
                "path": "walker2024.h5ad",
                "source": {
                    "type": "local",
                    "ref": "${OUTPUT_ROOT}/scrna/walker2024.h5ad",
                },
            }
        ],
    }
    rendered = render_canonical_datapackage_yaml(
        project_doc=project_doc,
        canonical_slug="ds",
        per_resource={"walker": (VALID_HASH, 14010935296)},
    )
    parsed = parse_canonical_datapackage_yaml(rendered)
    r = parsed["resources"][0]
    assert r["source"] == {"type": "local", "ref": "${OUTPUT_ROOT}/scrna/walker2024.h5ad"}
    assert r["hash"] == VALID_HASH and r["bytes"] == 14010935296
