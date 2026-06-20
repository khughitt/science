"""Tests for source-aware promote: default trust, --verify-digests, validation."""
from __future__ import annotations


import pytest
from promote_source_fixtures import init_commons, sourced_project


def test_digest_mismatch_error_names_resource_and_values():
    from science_tool.commons.errors import (
        CommonsError,
        PromoteResourceDigestMismatchError,
    )

    err = PromoteResourceDigestMismatchError(
        slug="walker",
        resource_name="walker-h5ad",
        expected=("sha256:" + "a" * 64, 10),
        actual=("sha256:" + "b" * 64, 11),
        path=None,
    )
    assert isinstance(err, CommonsError)
    assert err.slug == "walker"
    assert err.resource_name == "walker-h5ad"
    assert "walker-h5ad" in str(err)
    assert ("sha256:" + "a" * 64) in str(err)


VALID_HASH = "sha256:" + "a" * 64


def _candidate(tmp_path, resources, project_slug="mm"):
    """Build a minimal dataset PromoteCandidate with the given resources list."""
    from science_tool.commons.promote import PromoteCandidate

    tmp_path.mkdir(parents=True, exist_ok=True)
    dp_path = tmp_path / "datapackage.json"
    dp_path.write_text("{}", encoding="utf-8")  # bytes unused; doc passed directly
    return PromoteCandidate(
        slug="walker",
        slug_normalized="walker",
        project_slug=project_slug,
        project_root=tmp_path,
        overlay_source_path=tmp_path / "doc" / "data-walker.md",
        canonical_fields={},
        project_only_fields={},
        canonical_body={},
        project_only_body={},
        datapackage_source_path=dp_path,
        datapackage_doc={"name": "walker", "resources": resources},
    )


def _sourced(ref="${OUTPUT_ROOT}/scrna/walker2024.h5ad", *, hash_=VALID_HASH, bytes_=14010935296):
    # default ref is a ${OUTPUT_ROOT} token — tests that verify it must set OUTPUT_ROOT.
    return {
        "name": "walker-h5ad",
        "path": "walker2024.h5ad",
        "hash": hash_,
        "bytes": bytes_,
        "source": {"type": "local", "ref": ref},
    }


def test_default_trusts_sourced_resource_without_io(tmp_path, monkeypatch):
    from science_tool.commons import promote

    called = []
    monkeypatch.setattr(
        promote, "stream_sha256_and_bytes",
        lambda p: called.append(p) or ("sha256:" + "f" * 64, 1),
    )
    cand = _candidate(tmp_path, [_sourced()])
    result = promote._dataset_per_resource(cand)
    assert called == []  # NO byte I/O for a sourced resource
    assert result.per_resource == {"walker-h5ad": (VALID_HASH, 14010935296)}
    assert result.verifications == ()


def test_sourced_missing_hash_is_hard_error(tmp_path):
    from science_tool.commons import promote
    from science_tool.commons.errors import PromoteCandidateError

    res = _sourced()
    del res["hash"]
    with pytest.raises(PromoteCandidateError, match="hash"):
        promote._dataset_per_resource(_candidate(tmp_path, [res]))


@pytest.mark.parametrize("bad", ["sha256:zzz", "md5:" + "a" * 32, "nope"])
def test_sourced_invalid_hash_is_hard_error(tmp_path, bad):
    from science_tool.commons import promote
    from science_tool.commons.errors import PromoteCandidateError

    with pytest.raises(PromoteCandidateError, match="hash"):
        promote._dataset_per_resource(_candidate(tmp_path, [_sourced(hash_=bad)]))


@pytest.mark.parametrize("bad", [-1, True, "12", 1.5])
def test_sourced_invalid_bytes_is_hard_error(tmp_path, bad):
    from science_tool.commons import promote
    from science_tool.commons.errors import PromoteCandidateError

    with pytest.raises(PromoteCandidateError, match="bytes"):
        promote._dataset_per_resource(_candidate(tmp_path, [_sourced(bytes_=bad)]))


def test_bad_source_type_is_hard_error(tmp_path):
    from science_tool.commons import promote
    from science_tool.commons.errors import PromoteCandidateError

    res = _sourced()
    res["source"] = {"type": "s3", "ref": "/x"}
    with pytest.raises(PromoteCandidateError, match="source"):
        promote._dataset_per_resource(_candidate(tmp_path, [res]))


def test_path_failing_logical_validation_rejected(tmp_path):
    from science_tool.commons import promote
    from science_tool.commons.errors import PromoteCandidateError

    res = _sourced()
    res["path"] = "../escape.h5ad"
    with pytest.raises(PromoteCandidateError, match="path"):
        promote._dataset_per_resource(_candidate(tmp_path, [res]))


def test_path_failing_logical_validation_rejected_for_colocated(tmp_path):
    from science_tool.commons import promote
    from science_tool.commons.errors import PromoteCandidateError

    # co-located resource (no source) with a parent-escape path
    res = {"name": "bad", "path": "../escape.csv"}
    with pytest.raises(PromoteCandidateError, match="path"):
        promote._dataset_per_resource(_candidate(tmp_path, [res]))


def test_verify_passes_when_local_file_matches(tmp_path, monkeypatch):
    from science_tool.commons import promote
    from science_tool.commons.datapackage import stream_sha256_and_bytes

    (tmp_path / "scrna").mkdir()
    f = tmp_path / "scrna" / "walker2024.h5ad"
    f.write_bytes(b"hello world!")
    real_hash, real_bytes = stream_sha256_and_bytes(f)
    monkeypatch.setenv("OUTPUT_ROOT", str(tmp_path))
    cand = _candidate(tmp_path, [_sourced(hash_=real_hash, bytes_=real_bytes)])
    result = promote._dataset_per_resource(cand, verify_digests=True)
    assert [v.status for v in result.verifications] == ["verified"]


def test_verify_raises_on_drift(tmp_path, monkeypatch):
    from science_tool.commons import promote
    from science_tool.commons.errors import PromoteResourceDigestMismatchError

    (tmp_path / "scrna").mkdir()
    (tmp_path / "scrna" / "walker2024.h5ad").write_bytes(b"different bytes")
    monkeypatch.setenv("OUTPUT_ROOT", str(tmp_path))
    cand = _candidate(tmp_path, [_sourced()])  # stamped hash is all-'a', won't match
    with pytest.raises(PromoteResourceDigestMismatchError):
        promote._dataset_per_resource(cand, verify_digests=True)


def test_verify_hard_errors_when_resolved_but_missing(tmp_path, monkeypatch):
    from science_tool.commons import promote
    from science_tool.commons.errors import PromoteCandidateError

    monkeypatch.setenv("OUTPUT_ROOT", str(tmp_path))  # file never created
    cand = _candidate(tmp_path, [_sourced()])
    with pytest.raises(PromoteCandidateError, match="missing"):
        promote._dataset_per_resource(cand, verify_digests=True)


def test_verify_skips_off_host_when_token_unexpandable(tmp_path, monkeypatch):
    from science_tool.commons import promote

    monkeypatch.delenv("OUTPUT_ROOT", raising=False)
    cand = _candidate(tmp_path, [_sourced()])
    result = promote._dataset_per_resource(cand, verify_digests=True)
    assert [v.status for v in result.verifications] == ["skipped_off_host"]


def test_verify_skips_remote_type(tmp_path):
    from science_tool.commons import promote

    res = _sourced()
    res["source"] = {"type": "zenodo", "ref": "10.5281/zenodo.123"}
    cand = _candidate(tmp_path, [res])
    result = promote._dataset_per_resource(cand, verify_digests=True)
    assert [v.status for v in result.verifications] == ["skipped_remote"]


def test_mixed_colocated_and_sourced_streams_only_colocated(tmp_path, monkeypatch):
    """A dataset with one co-located + one sourced resource streams only the co-located one."""
    from science_tool.commons import promote

    # Real co-located file under the datapackage dir.
    colocated = tmp_path / "counts.csv"
    colocated.write_bytes(b"a,b,c\n1,2,3\n")

    streamed = []
    real_stream = promote.stream_sha256_and_bytes
    monkeypatch.setattr(
        promote, "stream_sha256_and_bytes",
        lambda p: streamed.append(p.name) or real_stream(p),
    )
    resources = [
        {"name": "counts", "path": "counts.csv"},  # co-located, no source
        _sourced(),                                  # sourced, off-repo
    ]
    result = promote._dataset_per_resource(_candidate(tmp_path, resources))
    assert streamed == ["counts.csv"]  # sourced resource was NOT streamed
    assert set(result.per_resource) == {"counts", "walker-h5ad"}
    assert result.per_resource["walker-h5ad"] == (VALID_HASH, 14010935296)


def test_verify_two_sourced_resources_yields_two_verdicts(tmp_path, monkeypatch):
    from science_tool.commons import promote

    monkeypatch.delenv("OUTPUT_ROOT", raising=False)  # both off-host → both skipped
    r1 = _sourced("${OUTPUT_ROOT}/a.h5ad")
    r1["name"], r1["path"] = "res-a", "a.h5ad"
    r2 = _sourced("${OUTPUT_ROOT}/b.h5ad")
    r2["name"], r2["path"] = "res-b", "b.h5ad"
    result = promote._dataset_per_resource(_candidate(tmp_path, [r1, r2]), verify_digests=True)
    assert [v.name for v in result.verifications] == ["res-a", "res-b"]
    assert all(v.status == "skipped_off_host" for v in result.verifications)


def test_validate_resources_skips_filesystem_check_for_sourced(tmp_path):
    from science_tool.commons import promote

    dp_abs = tmp_path / "datapackage.json"
    dp_abs.write_text("{}", encoding="utf-8")
    dp_doc = {"resources": [_sourced()]}  # off-repo file does not exist locally
    # Must NOT raise PromoteResourceMissingError for a sourced resource.
    promote._validate_datapackage_resources("walker", dp_abs, dp_doc)


def test_validate_resources_still_requires_colocated_file(tmp_path):
    from science_tool.commons import promote
    from science_tool.commons.errors import PromoteResourceMissingError

    dp_abs = tmp_path / "datapackage.json"
    dp_abs.write_text("{}", encoding="utf-8")
    dp_doc = {"resources": [{"name": "r1", "path": "missing.txt"}]}
    with pytest.raises(PromoteResourceMissingError):
        promote._validate_datapackage_resources("ds", dp_abs, dp_doc)


def test_validate_resources_rejects_bad_source_at_discovery(tmp_path):
    from science_tool.commons import promote
    from science_tool.commons.errors import PromoteCandidateError

    dp_abs = tmp_path / "datapackage.json"
    dp_abs.write_text("{}", encoding="utf-8")
    res = _sourced()
    res["source"] = {"type": "local", "ref": "relative/path"}
    with pytest.raises(PromoteCandidateError, match="source"):
        promote._validate_datapackage_resources("walker", dp_abs, {"resources": [res]})


def test_plan_promote_aggregates_skip_verdict(tmp_path, monkeypatch):
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        discover_candidates,
        plan_promote,
    )

    proj = sourced_project(tmp_path, "${OUTPUT_ROOT}/scrna/x.h5ad")
    commons = init_commons(tmp_path)

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.delenv("SCIENCE_CONFIG_DIR", raising=False)
    monkeypatch.delenv("OUTPUT_ROOT", raising=False)  # token unexpandable → off-host
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: {"proj-dataset": proj}[slug],
    )

    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    assert discovery.failed_candidates == []
    plan = plan_promote(
        discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET, verify_digests=True
    )
    verifs = plan.resource_verifications.get("fixture-ds", ())
    assert any(v.name == "r1" and v.status == "skipped_off_host" for v in verifs)


def test_plan_promote_no_verify_has_empty_verifications(tmp_path, monkeypatch):
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        discover_candidates,
        plan_promote,
    )

    proj = sourced_project(tmp_path, "${OUTPUT_ROOT}/scrna/x.h5ad")
    commons = init_commons(tmp_path)

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.delenv("SCIENCE_CONFIG_DIR", raising=False)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: {"proj-dataset": proj}[slug],
    )

    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)
    assert plan.resource_verifications.get("fixture-ds", ()) == ()


def test_group_validator_returns_non_primary_verdicts(tmp_path, monkeypatch):
    """A non-primary project's skip verdict is returned, not silently discarded."""
    from science_tool.commons import promote

    monkeypatch.delenv("OUTPUT_ROOT", raising=False)
    primary = _candidate(tmp_path / "a", [_sourced()], project_slug="proj-a")
    secondary = _candidate(tmp_path / "b", [_sourced()], project_slug="proj-b")

    primary_result = promote._dataset_per_resource(primary, verify_digests=True)
    verifications = promote._validate_dataset_group_datapackages(
        canonical_slug="walker",
        primary=primary,
        candidates=[primary, secondary],
        primary_per_resource=primary_result.per_resource,
        verify_digests=True,
    )
    # The group validator returns only the NON-primary candidates' verdicts.
    assert [v.project_slug for v in verifications] == ["proj-b"]
    assert verifications[0].status == "skipped_off_host"


def test_sourced_dataset_promotes_end_to_end_without_streaming(tmp_path, monkeypatch):
    from science_tool.commons import promote as promote_mod
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    proj = sourced_project(tmp_path, "${OUTPUT_ROOT}/scrna/x.h5ad")
    commons = init_commons(tmp_path)

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.delenv("SCIENCE_CONFIG_DIR", raising=False)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: {"proj-dataset": proj}[slug],
    )

    # Spy on streaming: the sourced r1 must NOT be streamed; the co-located r2 must.
    streamed = []
    real_stream = promote_mod.stream_sha256_and_bytes
    monkeypatch.setattr(
        promote_mod,
        "stream_sha256_and_bytes",
        lambda p: streamed.append(p.name) or real_stream(p),
    )

    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    assert discovery.failed_candidates == []
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)
    apply_promote(plan, commons_root=commons, invocation="source-e2e")

    assert "r1.txt" not in streamed       # sourced → never read
    assert "r2.txt" in streamed           # co-located → streamed

    import yaml as y

    parsed = y.safe_load(
        (commons / "datasets/fixture-ds/datapackage.yaml").read_text(encoding="utf-8")
    )
    r1 = next(r for r in parsed["resources"] if r["name"] == "r1")
    assert r1["hash"] == "sha256:" + "a" * 64
    assert r1["bytes"] == 12
    assert r1["source"] == {"type": "local", "ref": "${OUTPUT_ROOT}/scrna/x.h5ad"}
