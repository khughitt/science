from __future__ import annotations

from science_tool.commons.assembly_compatibility import CompatibilityRelation
from science_tool.validate.checks.identity_context import (
    evaluate_cross_dataset_assembly,
    evaluate_datapackage_identity_stamps,
    evaluate_gene_identity,
    evaluate_identity_context,
    evaluate_protein_identity,
    required_identity_tiers,
)
from science_tool.validate.result import Severity

_REGISTRY = "dataset:assembly-registry"
_REGISTRY_KEYS = {"g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp", "5K4odB173rjao1Cnbk5BnvLt9V7aPAa2"}
_KEYS_BY_ID = {_REGISTRY: set(_REGISTRY_KEYS)}
_COORD_PROFILE = "science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0+bio.identity_context/1.0"


def _ds(profile: str, **fm) -> dict:
    return {"type": "dataset", "id": "dataset:x", "schema_profile": profile, "_path": "data/x/entity.md", **fm}


def _assembly(digest: str, *, status: str = "resolved", registry: str = _REGISTRY) -> dict:
    return {"seqcol_digest": digest, "registry": registry, "resolution_status": status}


def _identity() -> dict:
    return {
        "taxon": 9606,
        "assembly": _assembly("g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp"),
        "molecular_ids": {
            "gene": {
                "namespace": "hgnc_id",
                "registry": "dataset:hgnc",
                "resolution_status": "resolved",
            }
        },
    }


def test_datapackage_identity_stamp_disagreement_errors() -> None:
    identity = _identity()
    ds = _ds("science-pkg-entity-1.0", identity_context=identity)
    datapackage = {"science": {"identity_context": {**identity, "taxon": 10090}}}

    results = list(evaluate_datapackage_identity_stamps([ds], {"dataset:x": ("data/x/datapackage.yaml", datapackage)}))

    assert [(r.severity, r.rule) for r in results] == [(Severity.ERROR, "identity.datapackage-stamp-disagreement")]


def test_datapackage_identity_stamp_absent_is_skipped() -> None:
    ds = _ds("science-pkg-entity-1.0", identity_context=_identity())

    assert list(evaluate_datapackage_identity_stamps([ds], {"dataset:x": ("data/x/datapackage.yaml", {})})) == []


def test_resolved_assembly_passes_silently() -> None:
    ds = _ds(
        _COORD_PROFILE, identity_context={"taxon": 9606, "assembly": _assembly("g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp")}
    )
    # RESOLVED is silent: no WARN/ERROR/INFO at all.
    assert list(evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID)) == []


def test_unresolved_assembly_errors() -> None:
    ds = _ds(_COORD_PROFILE, identity_context={"taxon": 9606, "assembly": _assembly("NOT_IN_REGISTRY")})
    errors = [
        r for r in evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID) if r.severity is Severity.ERROR
    ]
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


def test_cna_without_assembly_errors() -> None:
    ds = _ds(
        "science-entity-base/1.0+dataset/1.0+bio.cna/1.0+bio.identity_context/1.0",
        identity_context={"taxon": 9606},
    )

    errors = [
        r for r in evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID) if r.severity is Severity.ERROR
    ]

    assert [r.rule for r in errors] == ["identity.assembly-undeclared"]


def test_declared_unresolved_assembly_without_seqcol_digest_passes_declaration_gate() -> None:
    ds = _ds(
        "science-entity-base/1.0+dataset/1.0+bio.cna/1.0+bio.identity_context/1.0",
        identity_context={
            "taxon": 9606,
            "assembly": {"registry": _REGISTRY, "resolution_status": "declared_unresolved"},
        },
    )

    results = list(evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID))

    assert not [
        r
        for r in results
        if r.severity is Severity.ERROR and r.rule in {"identity.assembly-undeclared", "identity.assembly-malformed"}
    ]


def test_declared_unresolved_assembly_with_unknown_seqcol_digest_passes_malformed_gate() -> None:
    ds = _ds(
        "science-entity-base/1.0+dataset/1.0+bio.cna/1.0+bio.identity_context/1.0",
        identity_context={
            "taxon": 9606,
            "assembly": {
                "seqcol_digest": "UNKNOWN",
                "registry": _REGISTRY,
                "resolution_status": "declared_unresolved",
            },
        },
    )

    results = list(evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID))

    assert not [r for r in results if r.severity is Severity.ERROR and r.rule == "identity.assembly-malformed"]


def test_geneset_without_gene_tier_errors() -> None:
    ds = _ds(
        "science-entity-base/1.0+dataset/1.0+bio.geneset/1.0+bio.identity_context/1.0",
        identity_context={"taxon": 9606},
    )

    errors = [
        r for r in evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID) if r.severity is Severity.ERROR
    ]

    assert [r.rule for r in errors] == ["identity.gene-undeclared"]


def test_base_profile_clinical_table_requires_no_identity_context() -> None:
    ds = _ds("science-pkg-entity-1.0")

    assert list(evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID)) == []


def test_identity_bearing_profile_without_taxon_errors() -> None:
    ds = _ds(
        "science-entity-base/1.0+dataset/1.0+bio.cna/1.0+bio.identity_context/1.0",
        identity_context={"assembly": _assembly("g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp")},
    )

    errors = [
        r for r in evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID) if r.severity is Severity.ERROR
    ]

    assert [r.rule for r in errors] == ["identity.taxon-undeclared"]


def test_variant_declaration_requires_taxon() -> None:
    ds = _ds(
        "science-entity-base/1.0+dataset/1.0+bio.table/1.0+bio.identity_context/1.0",
        identity_context={
            "molecular_ids": {"variant": {"namespace": "vrs", "resolution_status": "declared_unresolved"}}
        },
    )

    errors = [
        r for r in evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID) if r.severity is Severity.ERROR
    ]

    assert required_identity_tiers(ds["schema_profile"], ds["identity_context"]) == {"variant"}
    assert [r.rule for r in errors] == ["identity.taxon-undeclared"]


def test_required_identity_tiers_from_schema_profile_and_variant_presence() -> None:
    cases = [
        ("science-pkg-entity-1.0", {}, set()),
        ("science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0", {}, {"assembly"}),
        ("science-entity-base/1.0+dataset/1.0+bio.scrna/1.0", {}, {"assembly"}),
        ("science-entity-base/1.0+dataset/1.0+bio.cna/1.0", {}, {"assembly"}),
        ("science-entity-base/1.0+dataset/1.0+bio.geneset/1.0", {}, {"gene"}),
        ("science-entity-base/1.0+dataset/1.0+bio.gene_crosswalk/1.0", {}, {"gene"}),
        ("science-entity-base/1.0+dataset/1.0+bio.protein_crosswalk/1.0", {}, {"protein"}),
        ("science-pkg-entity-1.0", {"molecular_ids": {"variant": {}}}, {"variant"}),
    ]

    for schema_profile, identity_context, expected in cases:
        assert required_identity_tiers(schema_profile, identity_context) == expected


def test_freetext_reference_genome_without_identity_context_errors() -> None:
    ds = _ds("science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0", reference_genome="GRCh38")
    errors = [
        r for r in evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID) if r.severity is Severity.ERROR
    ]
    assert [r.rule for r in errors] == ["identity.taxon-undeclared", "identity.assembly-undeclared"]


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
    ds = _ds(
        _COORD_PROFILE, identity_context={"taxon": 9606, "assembly": _assembly("g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp")}
    )
    results = list(evaluate_identity_context([ds], registry_keys_by_id={_REGISTRY: None}))
    assert not [r for r in results if r.severity is Severity.ERROR]
    assert [r for r in results if r.rule == "identity.registry-unavailable"]


def test_malformed_assembly_not_a_dict_errors() -> None:
    ds = _ds(_COORD_PROFILE, identity_context={"taxon": 9606, "assembly": "GRCh38"})
    errors = [
        r for r in evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID) if r.severity is Severity.ERROR
    ]
    assert len(errors) == 1 and errors[0].rule == "identity.assembly-malformed"


def test_missing_seqcol_digest_errors() -> None:
    ds = _ds(
        _COORD_PROFILE,
        identity_context={"taxon": 9606, "assembly": {"registry": _REGISTRY, "resolution_status": "resolved"}},
    )
    errors = [
        r for r in evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID) if r.severity is Severity.ERROR
    ]
    assert len(errors) == 1 and errors[0].rule == "identity.assembly-malformed"


def test_missing_registry_errors() -> None:
    ds = _ds(
        _COORD_PROFILE,
        identity_context={"taxon": 9606, "assembly": {"seqcol_digest": "X", "resolution_status": "resolved"}},
    )
    errors = [
        r for r in evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID) if r.severity is Severity.ERROR
    ]
    assert len(errors) == 1 and errors[0].rule == "identity.assembly-malformed"


def test_bad_resolution_status_errors() -> None:
    ds = _ds(_COORD_PROFILE, identity_context={"taxon": 9606, "assembly": _assembly("X", status="maybe")})
    errors = [
        r for r in evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID) if r.severity is Severity.ERROR
    ]
    assert len(errors) == 1 and errors[0].rule == "identity.assembly-malformed"


def _with_assembly(id_: str, digest: str, **extra) -> dict:
    return {
        "id": id_,
        "type": "dataset",
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0+bio.identity_context/1.0",
        "_path": f"data/{id_.split(':')[-1]}/entity.md",
        "identity_context": {"taxon": 9606, "assembly": {"seqcol_digest": digest, "resolution_status": "resolved"}},
        **extra,
    }


def test_inputs_spanning_two_assemblies_warns() -> None:
    a = _with_assembly("dataset:a", "DIGEST_38")
    b = _with_assembly("dataset:b", "DIGEST_37")
    derived = _with_assembly(
        "dataset:c",
        "DIGEST_38",
        derivation={"inputs": ["dataset:a", "dataset:b"]},
    )
    warns = [
        r
        for r in evaluate_cross_dataset_assembly([a, b, derived])
        if r.rule == "identity.cross-dataset-assembly-mismatch"
    ]
    assert len(warns) == 1


def test_inputs_single_assembly_no_warn() -> None:
    a = _with_assembly("dataset:a", "DIGEST_38")
    derived = _with_assembly("dataset:c", "DIGEST_38", derivation={"inputs": ["dataset:a"]})
    assert list(evaluate_cross_dataset_assembly([a, derived])) == []


def test_no_derivation_inputs_no_warn() -> None:
    a = _with_assembly("dataset:a", "DIGEST_38")
    assert list(evaluate_cross_dataset_assembly([a])) == []


_LIFTOVER_DATASET = "dataset:assembly-liftover-grch37-grch38"


def _relation(source: str, target: str) -> CompatibilityRelation:
    return CompatibilityRelation(
        source_seqcol_digest=source,
        target_seqcol_digest=target,
        relation="liftover_possible",
        method="ucsc_chain",
        chain_resource="chains/srcToTgt.over.chain.gz",
        direction="forward",
        source_label="source",
        target_label="target",
        source_url="https://example.test/srcToTgt.over.chain.gz",
        chain_sha256="sha256:" + "a" * 64,
    )


def test_cross_dataset_mismatch_with_declared_liftover_passes() -> None:
    a = _with_assembly("dataset:a", "DIGEST_37")
    derived = _with_assembly(
        "dataset:c",
        "DIGEST_38",
        derivation={
            "inputs": ["dataset:a"],
            "transformations": [
                {
                    "type": "liftover",
                    "from_seqcol_digest": "DIGEST_37",
                    "to_seqcol_digest": "DIGEST_38",
                    "method": "ucsc_chain",
                    "dataset": _LIFTOVER_DATASET,
                }
            ],
        },
    )

    assert (
        list(
            evaluate_cross_dataset_assembly(
                [a, derived],
                compatibility_relations_by_dataset_id={_LIFTOVER_DATASET: [_relation("DIGEST_37", "DIGEST_38")]},
            )
        )
        == []
    )


def test_cross_dataset_mismatch_with_frontmatter_only_still_warns() -> None:
    a = _with_assembly("dataset:a", "DIGEST_37")
    derived = _with_assembly(
        "dataset:c",
        "DIGEST_38",
        derivation={
            "inputs": ["dataset:a"],
            "transformations": [
                {
                    "type": "liftover",
                    "from_seqcol_digest": "DIGEST_37",
                    "to_seqcol_digest": "DIGEST_38",
                    "method": "ucsc_chain",
                    "dataset": _LIFTOVER_DATASET,
                }
            ],
        },
    )

    warns = [
        r
        for r in evaluate_cross_dataset_assembly(
            [a, derived], compatibility_relations_by_dataset_id={_LIFTOVER_DATASET: []}
        )
        if r.rule == "identity.cross-dataset-assembly-mismatch"
    ]
    assert len(warns) == 1


def test_cross_dataset_mismatch_with_wrong_liftover_target_warns() -> None:
    a = _with_assembly("dataset:a", "DIGEST_37")
    derived = _with_assembly(
        "dataset:c",
        "DIGEST_38",
        derivation={
            "inputs": ["dataset:a"],
            "transformations": [
                {
                    "type": "liftover",
                    "from_seqcol_digest": "DIGEST_37",
                    "to_seqcol_digest": "OTHER",
                    "method": "ucsc_chain",
                    "dataset": _LIFTOVER_DATASET,
                }
            ],
        },
    )

    warns = [
        r
        for r in evaluate_cross_dataset_assembly(
            [a, derived],
            compatibility_relations_by_dataset_id={_LIFTOVER_DATASET: [_relation("DIGEST_37", "DIGEST_38")]},
        )
        if r.rule == "identity.cross-dataset-assembly-mismatch"
    ]
    assert len(warns) == 1


def test_cross_dataset_mismatch_with_multiple_lifted_parents_passes() -> None:
    a = _with_assembly("dataset:a", "DIGEST_37")
    b = _with_assembly("dataset:b", "DIGEST_36")
    derived = _with_assembly(
        "dataset:c",
        "DIGEST_38",
        derivation={
            "inputs": ["dataset:a", "dataset:b"],
            "transformations": [
                {
                    "type": "liftover",
                    "from_seqcol_digest": "DIGEST_37",
                    "to_seqcol_digest": "DIGEST_38",
                    "method": "ucsc_chain",
                    "dataset": _LIFTOVER_DATASET,
                },
                {
                    "type": "liftover",
                    "from_seqcol_digest": "DIGEST_36",
                    "to_seqcol_digest": "DIGEST_38",
                    "method": "ucsc_chain",
                    "dataset": _LIFTOVER_DATASET,
                },
            ],
        },
    )

    assert (
        list(
            evaluate_cross_dataset_assembly(
                [a, b, derived],
                compatibility_relations_by_dataset_id={
                    _LIFTOVER_DATASET: [
                        _relation("DIGEST_37", "DIGEST_38"),
                        _relation("DIGEST_36", "DIGEST_38"),
                    ]
                },
            )
        )
        == []
    )


def test_cross_dataset_mismatch_with_partial_lifted_parents_warns() -> None:
    a = _with_assembly("dataset:a", "DIGEST_37")
    b = _with_assembly("dataset:b", "DIGEST_36")
    derived = _with_assembly(
        "dataset:c",
        "DIGEST_38",
        derivation={
            "inputs": ["dataset:a", "dataset:b"],
            "transformations": [
                {
                    "type": "liftover",
                    "from_seqcol_digest": "DIGEST_37",
                    "to_seqcol_digest": "DIGEST_38",
                    "method": "ucsc_chain",
                    "dataset": _LIFTOVER_DATASET,
                },
                {
                    "type": "liftover",
                    "from_seqcol_digest": "DIGEST_36",
                    "to_seqcol_digest": "DIGEST_38",
                    "method": "ucsc_chain",
                    "dataset": _LIFTOVER_DATASET,
                },
            ],
        },
    )

    warns = [
        r
        for r in evaluate_cross_dataset_assembly(
            [a, b, derived],
            compatibility_relations_by_dataset_id={_LIFTOVER_DATASET: [_relation("DIGEST_37", "DIGEST_38")]},
        )
        if r.rule == "identity.cross-dataset-assembly-mismatch"
    ]
    assert len(warns) == 1


def test_load_relations_fallback_keeps_warning_when_dataset_unresolvable() -> None:
    from science_tool.commons.errors import CommonsError
    from science_tool.validate.checks.identity_context import _load_relations_for_datasets

    def boom(*args, **kwargs):
        raise CommonsError("boom")

    a = _with_assembly("dataset:a", "DIGEST_37")
    derived = _with_assembly(
        "dataset:c",
        "DIGEST_38",
        derivation={
            "inputs": ["dataset:a"],
            "transformations": [
                {
                    "type": "liftover",
                    "from_seqcol_digest": "DIGEST_37",
                    "to_seqcol_digest": "DIGEST_38",
                    "method": "ucsc_chain",
                    "dataset": _LIFTOVER_DATASET,
                }
            ],
        },
    )

    relation_map = _load_relations_for_datasets([a, derived], loader=boom)

    assert relation_map == {_LIFTOVER_DATASET: None}
    warns = [
        r
        for r in evaluate_cross_dataset_assembly([a, derived], compatibility_relations_by_dataset_id=relation_map)
        if r.rule == "identity.cross-dataset-assembly-mismatch"
    ]
    assert len(warns) == 1


def test_identity_context_not_a_dict_treated_as_undeclared_errors() -> None:
    # A coordinate-bearing dataset whose identity_context is not an object must
    # not crash; it falls through to declaration-gate errors.
    ds = _ds(_COORD_PROFILE, identity_context="GRCh38")
    results = list(evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID))
    errors = [r for r in results if r.severity is Severity.ERROR]
    assert [r.rule for r in errors] == ["identity.taxon-undeclared", "identity.assembly-undeclared"]


# ---------------------------------------------------------------------------
# Check 2: gene namespace & registry resolvability (declaration-level, C2)
# ---------------------------------------------------------------------------

_GENE_REGISTRY = "dataset:gene-crosswalk-hgnc"
_VALID_GENE_META = {
    "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.gene_crosswalk/1.0",
    "member_key_column": "gene_key",
}
_GENE_META_BY_ID = {_GENE_REGISTRY: _VALID_GENE_META}


def test_tier_declaration_defect_is_public_and_registry_agnostic() -> None:
    from science_tool.validate.checks.identity_context import tier_declaration_defect

    assert tier_declaration_defect({"namespace": "vrs"}) is None
    assert tier_declaration_defect({"namespace": ""}) == "missing or blank namespace"
    assert tier_declaration_defect({"namespace": "vrs", "registry": "x"}) == "registry must be a 'dataset:' reference"
    assert tier_declaration_defect({"namespace": "vrs", "resolution_status": "maybe"}) == (
        "resolution_status must be 'resolved' or 'declared_unresolved'"
    )


def _gene_ds(gene, id_="dataset:g") -> dict:
    return {
        "type": "dataset",
        "id": id_,
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0+bio.identity_context/1.0",
        "_path": "data/g/entity.md",
        "identity_context": {"taxon": 9606, "molecular_ids": {"gene": gene}},
    }


def test_gene_supported_namespace_with_valid_registry_passes_silently() -> None:
    ds = _gene_ds({"namespace": "hgnc_id", "canonical": True})
    assert list(evaluate_gene_identity([ds], registry_meta_by_id=_GENE_META_BY_ID)) == []


def test_gene_default_registry_used_when_unspecified() -> None:
    ds = _gene_ds({"namespace": "entrez"})  # no explicit registry -> default
    assert list(evaluate_gene_identity([ds], registry_meta_by_id=_GENE_META_BY_ID)) == []


def test_gene_unsupported_namespace_errors() -> None:
    ds = _gene_ds({"namespace": "refseq"})
    errs = [
        r for r in evaluate_gene_identity([ds], registry_meta_by_id=_GENE_META_BY_ID) if r.severity is Severity.ERROR
    ]
    assert len(errs) == 1 and errs[0].rule == "identity.gene-namespace-unsupported"


def test_gene_declared_unresolved_infos() -> None:
    ds = _gene_ds({"namespace": "hgnc_id", "resolution_status": "declared_unresolved"})
    res = list(evaluate_gene_identity([ds], registry_meta_by_id=_GENE_META_BY_ID))
    assert not [r for r in res if r.severity is Severity.ERROR]
    assert [r for r in res if r.rule == "identity.gene-declared-unresolved"]


def test_gene_declared_unresolved_with_unsupported_namespace_still_errors() -> None:
    # declared_unresolved does not excuse a non-gene namespace: namespace support
    # is validated FIRST. The gene tier must use a recognized gene namespace.
    ds = _gene_ds({"namespace": "refseq", "resolution_status": "declared_unresolved"})
    errs = [
        r for r in evaluate_gene_identity([ds], registry_meta_by_id=_GENE_META_BY_ID) if r.severity is Severity.ERROR
    ]
    assert len(errs) == 1 and errs[0].rule == "identity.gene-namespace-unsupported"


def test_gene_wrong_registry_type_errors() -> None:
    # points at a real dataset that is NOT a gene crosswalk
    meta = {
        "dataset:assembly-registry": {
            "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.assembly_registry/1.0",
            "member_key_column": "seqcol_digest",
        }
    }
    ds = _gene_ds({"namespace": "hgnc_id", "registry": "dataset:assembly-registry"})
    errs = [r for r in evaluate_gene_identity([ds], registry_meta_by_id=meta) if r.severity is Severity.ERROR]
    assert len(errs) == 1 and errs[0].rule == "identity.gene-registry-invalid"


def test_gene_unloadable_registry_infos_not_errors() -> None:
    ds = _gene_ds({"namespace": "hgnc_id"})
    res = list(evaluate_gene_identity([ds], registry_meta_by_id={_GENE_REGISTRY: None}))
    assert not [r for r in res if r.severity is Severity.ERROR]
    assert [r for r in res if r.rule == "identity.gene-registry-unavailable"]


def test_gene_not_a_dict_errors() -> None:
    ds = _gene_ds("hgnc_id")  # the gene tier must be an object
    errs = [
        r for r in evaluate_gene_identity([ds], registry_meta_by_id=_GENE_META_BY_ID) if r.severity is Severity.ERROR
    ]
    assert len(errs) == 1 and errs[0].rule == "identity.gene-malformed"


def test_gene_missing_namespace_errors() -> None:
    ds = _gene_ds({"canonical": True})
    errs = [
        r for r in evaluate_gene_identity([ds], registry_meta_by_id=_GENE_META_BY_ID) if r.severity is Severity.ERROR
    ]
    assert len(errs) == 1 and errs[0].rule == "identity.gene-malformed"


def test_gene_malformed_registry_errors() -> None:
    # raw frontmatter bypasses the schema: a non-'dataset:' registry must ERROR
    # as malformed, not degrade to a misleading registry-unavailable INFO.
    ds = _gene_ds({"namespace": "hgnc_id", "registry": "gene-crosswalk-hgnc"})
    errs = [
        r for r in evaluate_gene_identity([ds], registry_meta_by_id=_GENE_META_BY_ID) if r.severity is Severity.ERROR
    ]
    assert len(errs) == 1 and errs[0].rule == "identity.gene-malformed"


def test_gene_bad_resolution_status_errors() -> None:
    # 'maybe' must not be treated like 'resolved' and pass silently.
    ds = _gene_ds({"namespace": "hgnc_id", "resolution_status": "maybe"})
    errs = [
        r for r in evaluate_gene_identity([ds], registry_meta_by_id=_GENE_META_BY_ID) if r.severity is Severity.ERROR
    ]
    assert len(errs) == 1 and errs[0].rule == "identity.gene-malformed"


def test_dataset_without_gene_decl_ignored() -> None:
    ds = {
        "type": "dataset",
        "id": "dataset:x",
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0+bio.identity_context/1.0",
        "_path": "data/x/entity.md",
        "identity_context": {"taxon": 9606},
    }
    assert list(evaluate_gene_identity([ds], registry_meta_by_id=_GENE_META_BY_ID)) == []


# ---------------------------------------------------------------------------
# Check 3: protein namespace & registry resolvability (declaration-level, C3)
# ---------------------------------------------------------------------------

_PROTEIN_REGISTRY = "dataset:protein-crosswalk-uniprot"
_VALID_PROTEIN_META = {
    "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.protein_crosswalk/1.0",
    "member_key_column": "protein_key",
}
_PROTEIN_META_BY_ID = {_PROTEIN_REGISTRY: _VALID_PROTEIN_META}


def _protein_ds(protein, id_="dataset:p") -> dict:
    return {
        "type": "dataset",
        "id": id_,
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.proteomics/1.0+bio.identity_context/1.0",
        "_path": "data/p/entity.md",
        "identity_context": {"taxon": 9606, "molecular_ids": {"protein": protein}},
    }


def test_protein_supported_namespace_with_valid_registry_passes_silently() -> None:
    ds = _protein_ds({"namespace": "uniprot", "canonical": True})
    assert list(evaluate_protein_identity([ds], registry_meta_by_id=_PROTEIN_META_BY_ID)) == []


def test_protein_default_registry_used_when_unspecified() -> None:
    ds = _protein_ds({"namespace": "ensembl_protein"})
    assert list(evaluate_protein_identity([ds], registry_meta_by_id=_PROTEIN_META_BY_ID)) == []


def test_protein_unsupported_namespace_errors() -> None:
    ds = _protein_ds({"namespace": "entrez"})
    errs = [
        r
        for r in evaluate_protein_identity([ds], registry_meta_by_id=_PROTEIN_META_BY_ID)
        if r.severity is Severity.ERROR
    ]
    assert len(errs) == 1 and errs[0].rule == "identity.protein-namespace-unsupported"


def test_protein_declared_unresolved_infos() -> None:
    ds = _protein_ds({"namespace": "uniprot", "resolution_status": "declared_unresolved"})
    res = list(evaluate_protein_identity([ds], registry_meta_by_id=_PROTEIN_META_BY_ID))
    assert not [r for r in res if r.severity is Severity.ERROR]
    assert [r for r in res if r.rule == "identity.protein-declared-unresolved"]


def test_protein_declared_unresolved_with_unsupported_namespace_still_errors() -> None:
    ds = _protein_ds({"namespace": "entrez", "resolution_status": "declared_unresolved"})
    errs = [
        r
        for r in evaluate_protein_identity([ds], registry_meta_by_id=_PROTEIN_META_BY_ID)
        if r.severity is Severity.ERROR
    ]
    assert len(errs) == 1 and errs[0].rule == "identity.protein-namespace-unsupported"


def test_protein_wrong_registry_type_errors() -> None:
    meta = {
        "dataset:gene-crosswalk-hgnc": {
            "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.gene_crosswalk/1.0",
            "member_key_column": "gene_key",
        }
    }
    ds = _protein_ds({"namespace": "uniprot", "registry": "dataset:gene-crosswalk-hgnc"})
    errs = [r for r in evaluate_protein_identity([ds], registry_meta_by_id=meta) if r.severity is Severity.ERROR]
    assert len(errs) == 1 and errs[0].rule == "identity.protein-registry-invalid"


def test_protein_unloadable_registry_infos_not_errors() -> None:
    ds = _protein_ds({"namespace": "uniprot"})
    res = list(evaluate_protein_identity([ds], registry_meta_by_id={_PROTEIN_REGISTRY: None}))
    assert not [r for r in res if r.severity is Severity.ERROR]
    assert [r for r in res if r.rule == "identity.protein-registry-unavailable"]


def test_protein_malformed_registry_errors() -> None:
    ds = _protein_ds({"namespace": "uniprot", "registry": "protein-crosswalk-uniprot"})
    errs = [
        r
        for r in evaluate_protein_identity([ds], registry_meta_by_id=_PROTEIN_META_BY_ID)
        if r.severity is Severity.ERROR
    ]
    assert len(errs) == 1 and errs[0].rule == "identity.protein-malformed"


def test_protein_bad_resolution_status_errors() -> None:
    ds = _protein_ds({"namespace": "uniprot", "resolution_status": "maybe"})
    errs = [
        r
        for r in evaluate_protein_identity([ds], registry_meta_by_id=_PROTEIN_META_BY_ID)
        if r.severity is Severity.ERROR
    ]
    assert len(errs) == 1 and errs[0].rule == "identity.protein-malformed"


def test_protein_not_a_dict_errors() -> None:
    ds = _protein_ds("uniprot")
    errs = [
        r
        for r in evaluate_protein_identity([ds], registry_meta_by_id=_PROTEIN_META_BY_ID)
        if r.severity is Severity.ERROR
    ]
    assert len(errs) == 1 and errs[0].rule == "identity.protein-malformed"


def test_dataset_without_protein_decl_ignored() -> None:
    ds = {
        "type": "dataset",
        "id": "dataset:q",
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.proteomics/1.0+bio.identity_context/1.0",
        "_path": "data/q/entity.md",
        "identity_context": {"taxon": 9606},
    }
    assert list(evaluate_protein_identity([ds], registry_meta_by_id=_PROTEIN_META_BY_ID)) == []
