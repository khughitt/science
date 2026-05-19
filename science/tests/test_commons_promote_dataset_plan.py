from pathlib import Path

import pytest

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
    from science_tool.commons.datapackage import (
        parse_canonical_datapackage_yaml,
        render_canonical_datapackage_yaml,
    )

    valid_hash = (
        "sha256:"
        "a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a447"
    )
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
    hashes = {"r1": (valid_hash, 42)}
    yaml_text = render_canonical_datapackage_yaml(
        project_doc=project_doc,
        canonical_slug="fixture-ds",
        per_resource=hashes,
    )

    parsed = parse_canonical_datapackage_yaml(yaml_text)
    assert parsed["name"] == "fixture-ds"
    assert "conformsTo" not in parsed
    assert "mm30" not in parsed
    r = parsed["resources"][0]
    assert r["hash"] == valid_hash
    assert r["bytes"] == 42
    assert r["schema"] == {"fields": []}


def test_render_canonical_datapackage_uses_path_metadata_alias():
    from science_tool.commons.datapackage import parse_canonical_datapackage_yaml
    from science_tool.commons.datapackage import render_canonical_datapackage_yaml

    valid_hash = (
        "sha256:"
        "a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a447"
    )
    yaml_text = render_canonical_datapackage_yaml(
        project_doc={
            "name": "project-ds",
            "resources": [{"name": "r1", "path": "r1.txt"}],
        },
        canonical_slug="fixture-ds",
        per_resource={"r1.txt": (valid_hash, 12)},
    )

    parsed = parse_canonical_datapackage_yaml(yaml_text)
    assert parsed["resources"][0]["hash"] == valid_hash
    assert parsed["resources"][0]["bytes"] == 12


def test_render_canonical_datapackage_rejects_missing_computed_metadata():
    from science_tool.commons.datapackage import render_canonical_datapackage_yaml
    from science_tool.commons.errors import CommonsError
    import pytest

    project_doc = {
        "name": "project-ds",
        "resources": [
            {
                "name": "r1",
                "path": "r1.txt",
                "hash": "sha256:" + "f" * 64,
                "bytes": 999,
            }
        ],
    }

    with pytest.raises(CommonsError, match="metadata"):
        render_canonical_datapackage_yaml(
            project_doc=project_doc,
            canonical_slug="fixture-ds",
            per_resource={},
        )


def test_render_canonical_datapackage_rejects_conflicting_metadata_aliases():
    from science_tool.commons.datapackage import render_canonical_datapackage_yaml
    from science_tool.commons.errors import CommonsError
    import pytest

    project_doc = {
        "name": "project-ds",
        "resources": [{"name": "r1", "path": "r1.txt"}],
    }

    with pytest.raises(CommonsError, match="conflicting"):
        render_canonical_datapackage_yaml(
            project_doc=project_doc,
            canonical_slug="fixture-ds",
            per_resource={
                "r1": ("sha256:" + "a" * 64, 12),
                "r1.txt": ("sha256:" + "b" * 64, 12),
            },
        )


def test_render_canonical_datapackage_rejects_cross_resource_alias_collision():
    from science_tool.commons.datapackage import render_canonical_datapackage_yaml
    from science_tool.commons.errors import CommonsError
    import pytest

    project_doc = {
        "name": "project-ds",
        "resources": [
            {"name": "r1", "path": "r2.txt"},
            {"name": "r2.txt", "path": "r3.txt"},
        ],
    }

    with pytest.raises(CommonsError, match="ambiguous resource alias"):
        render_canonical_datapackage_yaml(
            project_doc=project_doc,
            canonical_slug="fixture-ds",
            per_resource={
                "r2.txt": ("sha256:" + "a" * 64, 12),
                "r3.txt": ("sha256:" + "b" * 64, 13),
            },
        )


def test_render_canonical_datapackage_rejects_missing_or_empty_resources():
    from science_tool.commons.datapackage import render_canonical_datapackage_yaml
    from science_tool.commons.errors import CommonsError
    import pytest

    for project_doc in ({"name": "project-ds"}, {"name": "project-ds", "resources": []}):
        with pytest.raises(CommonsError, match="resources"):
            render_canonical_datapackage_yaml(
                project_doc=project_doc,
                canonical_slug="fixture-ds",
                per_resource={},
            )


def test_render_canonical_datapackage_rejects_non_list_resources():
    from science_tool.commons.datapackage import render_canonical_datapackage_yaml
    from science_tool.commons.errors import CommonsError
    import pytest

    with pytest.raises(CommonsError, match="resources"):
        render_canonical_datapackage_yaml(
            project_doc={"name": "project-ds", "resources": {"path": "r1.txt"}},
            canonical_slug="fixture-ds",
            per_resource={},
        )


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


def _plan_one(tmp_path, monkeypatch):
    """Helper: discover + plan the fixture project. Returns the single decision."""
    import shutil
    import subprocess

    src = Path(__file__).parent / "fixtures" / "promote" / "proj-dataset"
    proj = tmp_path / "proj-dataset"
    shutil.copytree(src, proj)
    entity_source = proj / "doc" / "datasets" / "data-fixture-ds.md"
    entity_source.write_text(
        entity_source.read_text(encoding="utf-8").replace(
            "ontologies:\n  - test-ontology\n", ""
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(proj),
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-q",
            "-m",
            "init",
        ],
        check=True,
    )
    commons = tmp_path / "commons"
    commons.mkdir()
    subprocess.run(["git", "init", "-q", str(commons)], check=True)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda s: proj,
    )
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        discover_candidates,
        plan_promote,
    )

    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)
    return plan.decisions[0], plan, commons


class DatasetCanonicalEntityNotWired(Exception):
    pass


def _canonical_entity_content(decision):
    expected_path = Path("datasets/fixture-ds/entity.md")
    entity = next(
        (
            a
            for a in decision.canonical_artifacts
            if a.path == expected_path
        ),
        None,
    )
    if entity is None:
        raise DatasetCanonicalEntityNotWired(
            f"missing canonical entity artifact at {expected_path}; got "
            f"{[a.path for a in decision.canonical_artifacts]}"
        )
    return entity.content


def _canonical_entity_frontmatter(decision):
    import yaml

    content = _canonical_entity_content(decision)
    _, fm_raw, _ = content.split("---\n", 2)
    return yaml.safe_load(fm_raw) or {}


def _canonical_entity_body(decision):
    content = _canonical_entity_content(decision)
    _, _, body = content.split("---\n", 2)
    return body


@pytest.mark.xfail(
    reason="lands in Task 16",
    strict=True,
    raises=DatasetCanonicalEntityNotWired,
)
def test_dataset_canonical_entity_emits_required_base_fields(tmp_path, monkeypatch):
    d, _, _ = _plan_one(tmp_path, monkeypatch)

    fm = _canonical_entity_frontmatter(d)

    assert fm["schema_profile"] == "science-entity-base/1.0+dataset/1.0"
    assert fm["id"] == "dataset:fixture-ds"
    assert fm["type"] == "dataset"
    assert fm["title"] == "Fixture dataset"
    assert fm["version"] == "1.0.0"
    assert "created" in fm
    assert "updated" in fm


@pytest.mark.xfail(
    reason="lands in Task 16",
    strict=True,
    raises=DatasetCanonicalEntityNotWired,
)
def test_dataset_canonical_entity_datapackage_points_at_sibling(tmp_path, monkeypatch):
    d, _, _ = _plan_one(tmp_path, monkeypatch)

    fm = _canonical_entity_frontmatter(d)

    assert fm["datapackage"] == "datapackage.yaml"


@pytest.mark.xfail(
    reason="lands in Task 16",
    strict=True,
    raises=DatasetCanonicalEntityNotWired,
)
def test_dataset_canonical_entity_preserves_tier_verbatim(tmp_path, monkeypatch):
    d, _, _ = _plan_one(tmp_path, monkeypatch)

    content = _canonical_entity_content(d)

    assert "tier: evaluate-next" in content


@pytest.mark.xfail(
    reason="lands in Task 16",
    strict=True,
    raises=DatasetCanonicalEntityNotWired,
)
def test_dataset_canonical_entity_body_is_preserved(tmp_path, monkeypatch):
    d, _, _ = _plan_one(tmp_path, monkeypatch)

    body = _canonical_entity_body(d)

    assert "Project-only body content goes here" in body


def test_render_dataset_recipe_stub_content():
    from science_tool.commons.promote import _render_dataset_recipe_stub

    text = _render_dataset_recipe_stub(
        slug="fixture-ds",
        source_hint="Nusinow 2020 CCLE proteomics",
    )

    assert "Recipe back-fill needed" in text
    assert "Nusinow 2020" in text
    assert "<source>" not in text


def test_render_dataset_recipe_stub_handles_missing_source_hint():
    from science_tool.commons.promote import _render_dataset_recipe_stub

    text = _render_dataset_recipe_stub(slug="fixture-ds", source_hint=None)

    assert "Recipe back-fill needed" in text
    assert "unspecified" in text.lower()


def test_dataset_dropped_fields_records_unrouted_keys():
    """Project keys not in canonical or overlay buckets are recorded as dropped."""
    from science_tool.commons.promote import _dataset_dropped_fields

    raw_fm = {
        "id": "dataset:x",
        "type": "dataset",
        "schema_profile": "science-entity-base/1.0+dataset/1.0",
        "version": "1.0.0",
        "title": "T",
        "datapackage": "data/x/datapackage.json",
        "origin": "external",
        "tier": "track",
        "access": {"level": "public", "verified": True},
        "tags": ["a"],
        "ontologies": ["bio"],
        "datasets": ["dataset:y"],
        "overlay_of": "dataset:x",
        "pin_version": "1.0.0",
        "pin_effective_version": "1.0.0",
        "relevance": "high",
        "_sentinel": True,
    }
    canonical_fields = {
        "title": "T",
        "datapackage": "data/x/datapackage.json",
        "origin": "external",
        "tier": "track",
        "access": {"level": "public", "verified": True},
        "tags": ["a"],
    }
    project_only_fields = {"relevance": "high"}
    dropped = _dataset_dropped_fields(
        raw_fm,
        canonical_fields=canonical_fields,
        project_only_fields=project_only_fields,
    )
    assert dropped == ["datasets", "ontologies"]
