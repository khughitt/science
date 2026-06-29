import pytest
from pydantic import ValidationError

from science_tool.project_package.core import content_version
from science_tool.project_package.manifest import (
    SCHEMA_VERSION,
    SerializedManifest,
    data_version_chunks,
)

_SHA = "a" * 64


def _valid() -> dict:
    files = [{"path": "science.yaml", "sha256": _SHA, "bytes": 3}]
    payloads = [
        {"path": "data/raw/x.bin", "sha256": _SHA, "bytes": 1, "git_tracked": False}
    ]
    dv = content_version("0", data_version_chunks(files, payloads))
    return {
        "schema_version": SCHEMA_VERSION,
        "project": {"id": "demo", "label": "Demo", "summary": None},
        "data_version": dv,
        "provenance": {"git_commit": "abc123", "tool": "science"},
        "boundary_audit": {"passed": True, "forced": False},
        "files": files,
        "payloads": payloads,
    }


def test_valid_manifest_parses():
    m = SerializedManifest.model_validate(_valid())
    assert m.project.id == "demo"
    assert m.files[0].path == "science.yaml"
    assert m.payloads[0].git_tracked is False


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(schema_version="science-project-serialized.v2"),
        lambda d: d["project"].update(id="../escape"),
        lambda d: d["project"].update(id=""),
        lambda d: d["files"][0].update(path="/abs/path"),
        lambda d: d["files"][0].update(path="../up"),
        lambda d: d["files"][0].update(sha256="a" * 63),
        lambda d: d["files"][0].update(bytes=-1),
        lambda d: d["files"].append(dict(d["files"][0])),
        lambda d: d["payloads"].append(dict(d["payloads"][0])),
        lambda d: d["files"].extend(
            [
                {"path": "z.md", "sha256": _SHA, "bytes": 1},
                {"path": "a.md", "sha256": _SHA, "bytes": 1},
            ]
        ),
        lambda d: d["payloads"].extend(
            [
                {
                    "path": "data/raw/z.bin",
                    "sha256": _SHA,
                    "bytes": 1,
                    "git_tracked": False,
                },
                {
                    "path": "data/raw/a.bin",
                    "sha256": _SHA,
                    "bytes": 1,
                    "git_tracked": False,
                },
            ]
        ),
        lambda d: d["project"].update(unexpected="x"),
        lambda d: d.update(unexpected="x"),
    ],
)
def test_strict_rules_reject(mutate):
    d = _valid()
    mutate(d)
    with pytest.raises(ValidationError):
        SerializedManifest.model_validate(d)


def test_data_version_chunks_are_canonical_and_ordered():
    files = [
        {"path": "a", "sha256": _SHA, "bytes": 1},
        {"path": "b", "sha256": _SHA, "bytes": 2},
    ]
    payloads = [{"path": "p", "sha256": _SHA, "bytes": 9, "git_tracked": True}]
    chunks = data_version_chunks(files, payloads)
    assert chunks == [
        b'{"bytes": 1, "path": "a", "sha256": "%s"}' % _SHA.encode(),
        b'{"bytes": 2, "path": "b", "sha256": "%s"}' % _SHA.encode(),
        b'{"bytes": 9, "git_tracked": true, "path": "p", "sha256": "%s"}'
        % _SHA.encode(),
    ]


def test_serialize_output_parses_through_model(tmp_path):
    import subprocess

    from science_tool.project_package.serialize import _build_manifest, file_resource

    (tmp_path / "entities").mkdir()
    (tmp_path / "science.yaml").write_text("id: demo\nname: Demo\n", encoding="utf-8")
    (tmp_path / "entities" / "q.md").write_text("# q\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)

    files = [
        file_resource(tmp_path, "science.yaml"),
        file_resource(tmp_path, "entities/q.md"),
    ]
    manifest = _build_manifest(
        tmp_path,
        files,
        payloads=[],
        audit_passed=True,
        forced=False,
        git_commit="deadbeef",
    )
    SerializedManifest.model_validate(manifest)
