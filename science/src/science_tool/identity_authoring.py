"""Shared authoring helpers for dataset ``identity_context`` declarations."""

from __future__ import annotations

from typing import Any

from science_model.entity_schema.loader import SchemaLoader, SchemaNotFoundError
from science_model.entity_schema.profile import ProfileParseError, parse_profile

BASE_DATASET_SCHEMA_PROFILE = "science-entity-base/1.0+dataset/1.0"
ASSEMBLY_REGISTRY_ID = "dataset:assembly-registry"
GENE_CROSSWALK_ID = "dataset:gene-crosswalk-hgnc"
PROTEIN_CROSSWALK_ID = "dataset:protein-crosswalk-uniprot"
IDENTITY_CONTEXT_EXTENSION = "bio.identity_context"

_TIER_FLAG_BY_NAME = {
    "assembly": "--assembly",
    "gene": "--gene-namespace",
    "protein": "--protein-namespace",
    "variant": "identity_context.molecular_ids.variant",
}


class IdentityAuthoringError(ValueError):
    """Raised when an authoring command lacks required identity declarations."""


def build_identity_context(
    *,
    taxon: int | None = None,
    assembly: str | None = None,
    gene_namespace: str | None = None,
    protein_namespace: str | None = None,
) -> dict[str, Any]:
    """Build a normalized ``identity_context`` from lifecycle CLI flags."""
    identity_context: dict[str, Any] = {}
    if taxon is not None:
        if taxon < 1:
            raise IdentityAuthoringError("--taxon must be a positive NCBI taxonomy id")
        identity_context["taxon"] = taxon
    if assembly is not None:
        assembly = assembly.strip()
        if not assembly:
            raise IdentityAuthoringError("--assembly must be a non-blank label, digest, or UNKNOWN")
        identity_context["assembly"] = {
            "label": assembly,
            "registry": ASSEMBLY_REGISTRY_ID,
        }
        if assembly.strip().upper() == "UNKNOWN":
            identity_context["assembly"]["resolution_status"] = "declared_unresolved"

    molecular_ids: dict[str, Any] = {}
    if gene_namespace is not None:
        molecular_ids["gene"] = {
            "namespace": gene_namespace,
            "registry": GENE_CROSSWALK_ID,
        }
    if protein_namespace is not None:
        molecular_ids["protein"] = {
            "namespace": protein_namespace,
            "registry": PROTEIN_CROSSWALK_ID,
        }
    if molecular_ids:
        identity_context["molecular_ids"] = molecular_ids

    if not identity_context:
        return {}
    from science_tool.commons.identity_resolve import resolve_identity

    resolved = resolve_identity(identity_context)
    errors = [message for message in resolved.messages if message.level == "error"]
    if errors:
        details = "; ".join(f"{message.path}: {message.message}" for message in errors)
        raise IdentityAuthoringError(details)
    return resolved.identity_context


def require_profile_identity(schema_profile: str, identity_context: Any) -> None:
    """Fail when an identity-bearing profile lacks its required declarations."""
    try:
        profile = parse_profile(schema_profile)
    except ProfileParseError as exc:
        raise IdentityAuthoringError(f"invalid schema_profile: {exc}") from exc
    if profile.mixin is None or profile.mixin.name != "dataset":
        raise IdentityAuthoringError("invalid schema_profile: dataset lifecycle requires a dataset schema_profile")
    loader = SchemaLoader()
    for component in (profile.base, profile.mixin, *profile.extensions):
        try:
            loader.load(component)
        except SchemaNotFoundError as exc:
            raise IdentityAuthoringError(f"unknown schema_profile component {component.render()!r}: {exc}") from exc

    from science_tool.validate.checks.identity_context import required_identity_tiers

    required_tiers = required_identity_tiers(schema_profile, identity_context)
    requires_taxon = required_tiers or any(ext.name == IDENTITY_CONTEXT_EXTENSION for ext in profile.extensions)
    if not requires_taxon:
        return

    missing: list[str] = []
    if not _has_taxon(identity_context):
        missing.append("--taxon")
    for tier in sorted(required_tiers):
        if not _has_tier(identity_context, tier):
            missing.append(_TIER_FLAG_BY_NAME[tier])

    if not missing:
        return
    missing_flags = ", ".join(missing)
    raise IdentityAuthoringError(
        "identity-bearing schema_profile requires explicit identity declarations "
        f"({missing_flags}); use --assembly UNKNOWN when the assembly is intentionally unresolved"
    )


def _has_taxon(identity_context: Any) -> bool:
    return isinstance(identity_context, dict) and identity_context.get("taxon") not in (None, "")


def _has_tier(identity_context: Any, tier: str) -> bool:
    if not isinstance(identity_context, dict):
        return False
    if tier == "assembly":
        return identity_context.get("assembly") is not None
    molecular_ids = identity_context.get("molecular_ids")
    return isinstance(molecular_ids, dict) and molecular_ids.get(tier) is not None
