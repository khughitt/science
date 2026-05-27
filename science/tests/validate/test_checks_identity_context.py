from __future__ import annotations

from science_tool.validate.checks.identity_context import evaluate_identity_context
from science_tool.validate.result import Severity

_REGISTRY = "dataset:assembly-registry"
_REGISTRY_KEYS = {"g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp", "5K4odB173rjao1Cnbk5BnvLt9V7aPAa2"}
_KEYS_BY_ID = {_REGISTRY: set(_REGISTRY_KEYS)}
_COORD_PROFILE = "science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0+bio.identity_context/1.0"


def _ds(profile: str, **fm) -> dict:
    return {"type": "dataset", "id": "dataset:x", "schema_profile": profile, "_path": "data/x/entity.md", **fm}


def _assembly(digest: str, *, status: str = "resolved", registry: str = _REGISTRY) -> dict:
    return {"seqcol_digest": digest, "registry": registry, "resolution_status": status}


def test_resolved_assembly_passes_silently() -> None:
    ds = _ds(_COORD_PROFILE, identity_context={"taxon": 9606, "assembly": _assembly("g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp")})
    # RESOLVED is silent: no WARN/ERROR/INFO at all.
    assert list(evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID)) == []


def test_unresolved_assembly_errors() -> None:
    ds = _ds(_COORD_PROFILE, identity_context={"taxon": 9606, "assembly": _assembly("NOT_IN_REGISTRY")})
    errors = [r for r in evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID) if r.severity is Severity.ERROR]
    assert len(errors) == 1
    assert errors[0].rule == "identity.assembly-unresolved"


def test_declared_unresolved_assembly_infos() -> None:
    ds = _ds(
        "science-entity-base/1.0+dataset/1.0+bio.cna/1.0+bio.identity_context/1.0",
        identity_context={"taxon": 9606, "assembly": _assembly("WHATEVER", status="declared_unresolved")},
    )
    results = list(evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID))
    assert not [r for r in results if r.severity is Severity.ERROR]
    assert [r for r in results if r.rule == "identity.assembly-declared-unresolved"]


def test_freetext_reference_genome_without_identity_context_warns() -> None:
    ds = _ds("science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0", reference_genome="GRCh38")
    warns = [r for r in evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID) if r.severity is Severity.WARN]
    assert len(warns) == 1
    assert warns[0].rule == "identity.assembly-undeclared"


def test_non_coordinate_dataset_ignored() -> None:
    ds = _ds("science-entity-base/1.0+dataset/1.0+bio.table/1.0")
    assert list(evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID)) == []


def test_foreign_registry_is_not_validated_against_default() -> None:
    # The digest IS a default-registry key, but the dataset declares a different
    # registry. It must NOT silently validate against the default's keys.
    ds = _ds(
        _COORD_PROFILE,
        identity_context={
            "taxon": 9606,
            "assembly": _assembly("g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp", registry="dataset:not-assembly-registry"),
        },
    )
    results = list(evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID))
    assert not [r for r in results if r.severity is Severity.ERROR]
    assert not [r for r in results if r.rule == "identity.assembly-declared-unresolved"]
    assert [r for r in results if r.rule == "identity.registry-unavailable"]


def test_registry_unavailable_cannot_falsely_error() -> None:
    # The declared registry maps to None (attempted but not loadable): a declared
    # resolved digest is reported INFO (unverifiable), never ERROR.
    ds = _ds(_COORD_PROFILE, identity_context={"taxon": 9606, "assembly": _assembly("g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp")})
    results = list(evaluate_identity_context([ds], registry_keys_by_id={_REGISTRY: None}))
    assert not [r for r in results if r.severity is Severity.ERROR]
    assert [r for r in results if r.rule == "identity.registry-unavailable"]


def test_malformed_assembly_not_a_dict_errors() -> None:
    ds = _ds(_COORD_PROFILE, identity_context={"taxon": 9606, "assembly": "GRCh38"})
    errors = [r for r in evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID) if r.severity is Severity.ERROR]
    assert len(errors) == 1 and errors[0].rule == "identity.assembly-malformed"


def test_missing_seqcol_digest_errors() -> None:
    ds = _ds(
        _COORD_PROFILE,
        identity_context={"taxon": 9606, "assembly": {"registry": _REGISTRY, "resolution_status": "resolved"}},
    )
    errors = [r for r in evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID) if r.severity is Severity.ERROR]
    assert len(errors) == 1 and errors[0].rule == "identity.assembly-malformed"


def test_missing_registry_errors() -> None:
    ds = _ds(
        _COORD_PROFILE,
        identity_context={"taxon": 9606, "assembly": {"seqcol_digest": "X", "resolution_status": "resolved"}},
    )
    errors = [r for r in evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID) if r.severity is Severity.ERROR]
    assert len(errors) == 1 and errors[0].rule == "identity.assembly-malformed"


def test_bad_resolution_status_errors() -> None:
    ds = _ds(_COORD_PROFILE, identity_context={"taxon": 9606, "assembly": _assembly("X", status="maybe")})
    errors = [r for r in evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID) if r.severity is Severity.ERROR]
    assert len(errors) == 1 and errors[0].rule == "identity.assembly-malformed"
