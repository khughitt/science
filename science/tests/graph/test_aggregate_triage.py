from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.graph.aggregate_triage import AggregateBucket, _bucket, classify_aggregate_rows
from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo-project\nprofile: research\nprofiles: {local: local}\n"
_AGG = "knowledge/sources/local/entities.yaml"


# --- Pure rule-matrix unit tests (no loading, no kind registration) ----------
# `decision`/`latent` are LOCAL profile kinds (not core-registered), so they would
# be skipped by the synthetic loader. Test the full six-bucket matrix + precedence
# directly on the pure _bucket helper, which takes (kind, source_path,
# has_real_owner, self_sourced) and needs no project on disk.
@pytest.mark.parametrize(
    "kind,source_path,has_real_owner,self_sourced,has_pei,expected",
    [
        ("concept", _AGG, False, True, False, AggregateBucket.COINED),
        ("latent", None, False, True, False, AggregateBucket.COINED),
        ("decision", "knowledge/x", False, True, False, AggregateBucket.COINED),  # self-sourced decision
        ("decision", "core/decisions.md", False, False, False, AggregateBucket.DECISION_LOG),
        ("article", _AGG, False, True, False, AggregateBucket.EXTERNAL_REF),
        ("concept", "refs.bib", False, False, False, AggregateBucket.EXTERNAL_REF),  # .bib source
        ("decision", "migration:audit", False, False, False, AggregateBucket.CRUFT),
        ("concept", "migration:audit", False, True, False, AggregateBucket.CRUFT),  # cruft before coined
        ("question", None, False, True, False, AggregateBucket.QUESTION_DEFERRED),  # 4c: bare question -> deferred
        ("topic", _AGG, False, True, False, AggregateBucket.COINED),  # 4c: vocab kind -> coined
        ("concept", _AGG, True, True, False, AggregateBucket.SHADOW),  # shadow wins over coined
        ("decision", "core/decisions.md", True, False, False, AggregateBucket.SHADOW),  # shadow before decision-log
        ("decision", "migration:audit", True, False, False, AggregateBucket.SHADOW),  # shadow before cruft
    ],
)
def test_bucket_rule_matrix(kind, source_path, has_real_owner, self_sourced, has_pei, expected) -> None:
    bucket, evidence = _bucket(kind, source_path, has_real_owner, self_sourced, has_pei)
    assert bucket is expected
    assert evidence  # every row carries a non-empty basis


# --- Integration tests (load -> classify plumbing; CORE kinds only) ----------
def _write_project(root: Path, entries: list[dict]) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    agg = root / "knowledge" / "sources" / "local"
    agg.mkdir(parents=True, exist_ok=True)
    (agg / "entities.yaml").write_text(yaml.safe_dump({"entities": entries}), encoding="utf-8")


def _write_dataset_md(root: Path, slug: str, ident: str) -> None:
    d = root / "entities" / "datasets"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slug}.md").write_text(
        f'---\nid: "{ident}"\ntype: "dataset"\ntitle: "{ident}"\n'
        'origin: "external"\naccess:\n  level: "public"\n  verified: false\n---\n',
        encoding="utf-8",
    )


def _lightweight(cid: str, kind: str, source_path: str) -> dict:
    return {"canonical_id": cid, "kind": kind, "title": cid, "source_path": source_path}


def _dataset_stub(cid: str, source_path: str) -> dict:
    return {
        "canonical_id": cid,
        "kind": "dataset",
        "title": cid,
        "origin": "external",
        "access": {"level": "public", "verified": False},
        "source_path": source_path,
    }


def _classify(root: Path):
    sources = load_project_sources(root, include_commons=False, strict_core_schema=False, strict_identity=False)
    return {t.canonical_id: t for t in classify_aggregate_rows(sources)}


def test_integration_core_kinds(tmp_path: Path) -> None:
    # Uses only core-registered kinds. `article:lit` is canonicalized to `paper:lit`
    # at load (the transition-window paper rename), while `kind` stays "article" — so
    # the row keys by paper:lit but still buckets external-ref.
    _write_dataset_md(tmp_path, "shadowed", "dataset:shadowed")
    _write_project(
        tmp_path,
        [
            _dataset_stub("dataset:shadowed", _AGG),
            _lightweight("concept:coined", "concept", _AGG),
            _lightweight("article:lit", "article", _AGG),
        ],
    )
    by_id = _classify(tmp_path)
    assert by_id["dataset:shadowed"].bucket is AggregateBucket.SHADOW
    assert by_id["dataset:shadowed"].has_real_owner is True
    assert by_id["concept:coined"].bucket is AggregateBucket.COINED
    assert by_id["concept:coined"].has_real_owner is False
    assert "article:lit" not in by_id  # canonicalized away
    assert by_id["paper:lit"].bucket is AggregateBucket.EXTERNAL_REF
    assert by_id["paper:lit"].kind == "article"


def test_empty_source_path_is_self_sourced(tmp_path: Path) -> None:
    # An explicit empty source_path must count as self-sourced (design): a coinable
    # kind with source_path "" buckets as coined, not ambiguous.
    _write_project(tmp_path, [_lightweight("concept:empty", "concept", "")])
    by_id = _classify(tmp_path)
    assert by_id["concept:empty"].bucket is AggregateBucket.COINED
