"""End-to-end CLI tests for `science commons promote dataset --mixin`."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.commons.cli import commons_group


def _make_project_tree(tmp_path: Path) -> Path:
    """Build a minimal project source tree with one bulk RNA-seq dataset,
    committed to git so discovery's `git ls-files` finds it."""
    proj = tmp_path / "proj-rnaseq"
    (proj / "doc" / "datasets").mkdir(parents=True)
    (proj / "data" / "mockrna").mkdir(parents=True)

    (proj / "doc" / "datasets" / "data-mockrna.md").write_text(
        """---
id: dataset:mockrna
type: dataset
title: Mock RNA-seq dataset
description: Synthetic fixture for Phase H CLI tests.
datapackage: data/mockrna/datapackage.json
origin: external
tier: use-now
access:
  level: public
  verified: true
created: "2026-05-19"
updated: "2026-05-19"
species: ["Homo sapiens"]
assay: bulk-rnaseq
n_rows: 20530
n_cols: 100
value_dtype: int32
feature_axis: rows
---

# Mock RNA-seq

Body content.
""",
        encoding="utf-8",
    )
    (proj / "data" / "mockrna" / "datapackage.json").write_text(
        json.dumps(
            {
                "name": "mockrna",
                "resources": [
                    {
                        "name": "counts",
                        "path": "counts.tsv",
                        "format": "tsv",
                        "mediatype": "text/tab-separated-values",
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (proj / "data" / "mockrna" / "counts.tsv").write_text("gene\ts1\n", encoding="utf-8")

    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True)
    subprocess.run(
        [
            "git", "-C", str(proj),
            "-c", "user.email=t@t",
            "-c", "user.name=t",
            "commit", "-q", "-m", "init",
        ],
        check=True,
    )
    return proj


def _init_repo(root: Path) -> None:
    """Init a git repo and set a local user identity."""
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@x"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "test"],
        check=True,
        capture_output=True,
    )


def _setup_proj_and_commons(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path]:
    """Build proj tree + commons layout with everything apply_promote needs."""
    proj = _make_project_tree(tmp_path)

    commons = tmp_path / "commons"
    commons.mkdir()
    (commons / ".migrations").mkdir()
    (commons / "datasets").mkdir()
    _init_repo(commons)
    subprocess.run(
        ["git", "-C", str(commons), "commit", "--allow-empty", "-q", "-m", "init"],
        check=True,
        capture_output=True,
    )

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.delenv("SCIENCE_CONFIG_DIR", raising=False)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: {"proj-rnaseq": proj}[slug],
    )
    return proj, commons


def _invoke_with(
    args: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """Set up proj + commons, then invoke commons_group with extra args."""
    _setup_proj_and_commons(tmp_path, monkeypatch)
    return CliRunner().invoke(
        commons_group,
        ["promote", "dataset", "--from", "proj-rnaseq", "--slug", "mockrna", *args],
    )


def test_promote_dataset_with_matrix_and_rnaseq_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Promote a bulk-rnaseq dataset with --mixin bio.matrix --mixin bio.rnaseq.
    Canonical entity.md carries the four-segment schema_profile and the bio
    fields in canonical (not overlay)."""
    proj, commons = _setup_proj_and_commons(tmp_path, monkeypatch)

    result = CliRunner().invoke(
        commons_group,
        [
            "promote",
            "dataset",
            "--from",
            "proj-rnaseq",
            "--slug",
            "mockrna",
            "--mixin",
            "bio.matrix",
            "--mixin",
            "bio.rnaseq",
            "--apply",
        ],
    )
    assert result.exit_code == 0, result.output

    entity_path = commons / "datasets" / "mockrna" / "entity.md"
    assert entity_path.is_file(), f"expected canonical entity.md at {entity_path}"
    entity = entity_path.read_text()
    assert (
        "schema_profile: "
        "science-entity-base/1.0+dataset/1.0+bio.matrix/1.0+bio.rnaseq/1.0"
        in entity
    )
    # Bio fields landed in canonical:
    assert "value_dtype: int32" in entity
    assert "assay: bulk-rnaseq" in entity
    assert "feature_axis: rows" in entity
    assert "Homo sapiens" in entity

    overlay = (proj / "doc" / "datasets" / "data-mockrna.md").read_text(
        encoding="utf-8"
    )
    assert "assay: bulk-rnaseq" not in overlay
    assert "value_dtype: int32" not in overlay
    assert "feature_axis: rows" not in overlay
    assert "Homo sapiens" not in overlay


def test_two_structural_mixins_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _invoke_with(
        ["--mixin", "bio.matrix", "--mixin", "bio.table", "--apply"],
        tmp_path,
        monkeypatch,
    )
    assert result.exit_code != 0
    assert "structural" in result.output.lower()
    assert not (tmp_path / "commons" / "datasets" / "mockrna" / "entity.md").exists()


def test_two_domain_mixins_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _invoke_with(
        ["--mixin", "bio.rnaseq", "--mixin", "bio.cna", "--apply"],
        tmp_path,
        monkeypatch,
    )
    assert result.exit_code != 0
    assert "domain" in result.output.lower()


def test_reversed_mixin_order_renders_canonical_profile_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _invoke_with(
        ["--mixin", "bio.rnaseq", "--mixin", "bio.matrix", "--apply"],
        tmp_path,
        monkeypatch,
    )

    assert result.exit_code == 0, result.output
    entity = (
        tmp_path / "commons" / "datasets" / "mockrna" / "entity.md"
    ).read_text(encoding="utf-8")
    assert (
        "schema_profile: "
        "science-entity-base/1.0+dataset/1.0+bio.matrix/1.0+bio.rnaseq/1.0"
        in entity
    )
    audit_log = next((tmp_path / "commons" / ".migrations").glob("*.yaml"))
    audit = audit_log.read_text(encoding="utf-8")
    assert audit.index("- bio.matrix/1.0") < audit.index("- bio.rnaseq/1.0")


def test_sugar_form_unknown_mixin_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _invoke_with(
        ["--mixin", "bio.bogus", "--apply"], tmp_path, monkeypatch
    )
    assert result.exit_code != 0
    assert "bio.bogus" in result.output


def test_explicit_form_unknown_mixin_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit form (bio.bogus/1.0) parses syntactically and passes the
    stacking-rule guard; the missing schema surfaces in plan_promote's
    read_merge_policy(active_profile) call and is rewrapped there
    as PromoteMixinResolutionError."""
    result = _invoke_with(
        ["--mixin", "bio.bogus/1.0", "--apply"], tmp_path, monkeypatch
    )
    assert result.exit_code != 0
    assert "bio.bogus" in result.output


def test_resolver_rejects_non_bio_name() -> None:
    """--mixin dataset/1.0 must be rejected -- only bio.* extensions stack."""
    from science_tool.commons.cli import _resolve_mixin_arg
    from science_tool.commons.errors import PromoteMixinResolutionError

    with pytest.raises(PromoteMixinResolutionError, match="bio."):
        _resolve_mixin_arg("dataset/1.0")


def test_resolver_rejects_bio_with_empty_suffix() -> None:
    """--mixin bio./1.0 must be rejected -- bio. needs a non-empty suffix."""
    from science_tool.commons.cli import _resolve_mixin_arg
    from science_tool.commons.errors import PromoteMixinResolutionError

    with pytest.raises(PromoteMixinResolutionError, match="non-empty"):
        _resolve_mixin_arg("bio./1.0")


def test_resolver_rejects_leading_slash() -> None:
    from science_tool.commons.cli import _resolve_mixin_arg
    from science_tool.commons.errors import PromoteMixinResolutionError

    with pytest.raises(PromoteMixinResolutionError):
        _resolve_mixin_arg("/1.0")


def test_resolver_rejects_non_numeric_version() -> None:
    from science_tool.commons.cli import _resolve_mixin_arg
    from science_tool.commons.errors import PromoteMixinResolutionError

    with pytest.raises(PromoteMixinResolutionError, match="integer"):
        _resolve_mixin_arg("bio.matrix/abc")


def test_resolver_picks_numeric_highest_not_lexicographic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If extension-bio-matrix-1.10.json and extension-bio-matrix-1.9.json
    coexist, sugar `bio.matrix` must resolve to 1.10 (numeric max), not 1.9.
    """
    from types import SimpleNamespace

    from science_tool.commons.cli import _resolve_mixin_arg

    fake_resources = [
        SimpleNamespace(name="extension-bio-matrix-1.9.json"),
        SimpleNamespace(name="extension-bio-matrix-1.10.json"),
        SimpleNamespace(name="other-file.json"),
    ]

    class _FakeRoot:
        def iterdir(self):
            return iter(fake_resources)

    monkeypatch.setattr(
        "importlib.resources.files",
        lambda pkg: _FakeRoot(),
    )

    resolved = _resolve_mixin_arg("bio.matrix")
    assert resolved.name == "bio.matrix"
    assert resolved.version == "1.10"


def test_mixin_on_paper_kind_yields_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`promote paper --mixin ...` must fail with Click's `No such option`
    error -- --mixin is not registered on the paper command."""
    _setup_proj_and_commons(tmp_path, monkeypatch)
    result = CliRunner().invoke(
        commons_group,
        [
            "promote",
            "paper",
            "--from",
            "proj-rnaseq",
            "--mixin",
            "bio.rnaseq",
        ],
    )
    assert result.exit_code != 0
    assert "no such option" in result.output.lower() or "--mixin" in result.output
