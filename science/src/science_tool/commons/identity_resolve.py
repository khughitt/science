"""Offline identity-context resolution helpers for authoring paths.

This module normalizes declarations against local commons artifacts only. Missing
or unavailable commons data degrades to ``declared_unresolved`` with structured
messages; it never attempts live network fallback.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from science_tool.commons import assembly
from science_tool.commons.assembly import ASSEMBLY_REGISTRY_ID, AssemblyRegistryError
from science_tool.commons.errors import CommonsError
from science_tool.commons.gene_crosswalk import GENE_CROSSWALK_ID, SUPPORTED_GENE_NAMESPACES
from science_tool.commons.protein_crosswalk import PROTEIN_CROSSWALK_ID, SUPPORTED_PROTEIN_NAMESPACES

ResolutionStatus = Literal["resolved", "declared_unresolved"]
MessageLevel = Literal["info", "warning", "error"]


@dataclass(frozen=True, slots=True)
class IdentityResolutionMessage:
    level: MessageLevel
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class ResolvedIdentity:
    identity_context: dict[str, Any]
    messages: tuple[IdentityResolutionMessage, ...]


@dataclass(frozen=True, slots=True)
class NamespaceResolution:
    namespace: str
    registry: str
    resolution_status: ResolutionStatus
    messages: tuple[IdentityResolutionMessage, ...] = ()


@dataclass(frozen=True, slots=True)
class RegistryAvailability:
    available: bool
    tier: str | None = None


@dataclass(frozen=True, slots=True)
class _NamespaceSpec:
    tier: str
    registry: str


@dataclass(frozen=True, slots=True)
class _AssemblyLabelResolution:
    seqcol_digest: str | None
    messages: tuple[IdentityResolutionMessage, ...] = ()


def _message(level: MessageLevel, path: str, message: str) -> IdentityResolutionMessage:
    return IdentityResolutionMessage(level=level, path=path, message=message)


def _registry_available(
    registry: str,
    *,
    expected_tier: str,
    registries: Mapping[str, Any] | None,
    path: str,
) -> tuple[bool, tuple[IdentityResolutionMessage, ...]]:
    if registries is None or registry not in registries:
        return (
            False,
            (
                _message(
                    "warning",
                    path,
                    f"registry {registry!r} unavailable; namespace cannot be verified",
                ),
            ),
        )
    entry = registries[registry]
    if entry is None or entry is False:
        return (
            False,
            (
                _message(
                    "warning",
                    path,
                    f"registry {registry!r} unavailable; namespace cannot be verified",
                ),
            ),
        )
    if isinstance(entry, RegistryAvailability):
        available = entry.available
        tier = entry.tier
    elif isinstance(entry, Mapping):
        available = entry.get("available")
        tier = entry.get("tier")
    else:
        return (
            False,
            (
                _message(
                    "error",
                    path,
                    f"invalid registry metadata for {registry!r}; expected explicit availability metadata",
                ),
            ),
        )
    if not isinstance(available, bool):
        return (
            False,
            (
                _message(
                    "error",
                    path,
                    f"invalid registry metadata for {registry!r}; expected boolean 'available'",
                ),
            ),
        )
    if not available:
        return (
            False,
            (
                _message(
                    "warning",
                    path,
                    f"registry {registry!r} unavailable; namespace cannot be verified",
                ),
            ),
        )
    if tier != expected_tier:
        return (
            False,
            (
                _message(
                    "error",
                    path,
                    f"registry {registry!r} metadata tier {tier!r} does not match expected tier {expected_tier!r}",
                ),
            ),
        )
    return True, ()


def _namespace_spec(namespace: str) -> _NamespaceSpec | None:
    if namespace in SUPPORTED_GENE_NAMESPACES:
        return _NamespaceSpec(tier="gene", registry=GENE_CROSSWALK_ID)
    if namespace in SUPPORTED_PROTEIN_NAMESPACES:
        return _NamespaceSpec(tier="protein", registry=PROTEIN_CROSSWALK_ID)
    return None


def _resolve_assembly_label(
    label: str,
    registry: str,
    *,
    path: str,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> _AssemblyLabelResolution:
    try:
        entry = assembly.resolve_assembly(
            label,
            registry_id=registry,
            commons_root=commons_root,
            data_root=data_root,
        )
    except (CommonsError, AssemblyRegistryError) as exc:
        return _AssemblyLabelResolution(
            seqcol_digest=None,
            messages=(
                _message(
                    "warning",
                    path,
                    f"assembly registry {registry!r} unavailable; {label!r} cannot be verified: {exc}",
                ),
            ),
        )
    if entry is None:
        return _AssemblyLabelResolution(
            seqcol_digest=None,
            messages=(
                _message(
                    "warning",
                    path,
                    f"assembly label or digest {label!r} did not resolve in registry {registry!r}",
                ),
            ),
        )
    return _AssemblyLabelResolution(seqcol_digest=entry.seqcol_digest)


def resolve_assembly_label(
    label: str,
    registry: str,
    *,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> str | None:
    """Resolve an assembly label or seqcol digest through the local registry."""
    return _resolve_assembly_label(
        label,
        registry,
        path="identity_context.assembly",
        commons_root=commons_root,
        data_root=data_root,
    ).seqcol_digest


def resolve_namespace(
    namespace: str,
    registry: str,
    *,
    registries: Mapping[str, Any] | None = None,
    path: str = "identity_context.molecular_ids",
) -> NamespaceResolution:
    """Resolve a molecular-id namespace declaration against local registry identity.

    ``registries`` is an explicit availability map keyed by registry id. Values
    must use ``RegistryAvailability`` or mappings with ``{"available": bool,
    "tier": "gene"}``/``{"available": bool, "tier": "protein"}``.
    """
    namespace = namespace.strip()
    spec = _namespace_spec(namespace)
    if spec is None:
        return NamespaceResolution(
            namespace=namespace,
            registry=registry,
            resolution_status="declared_unresolved",
            messages=(
                _message(
                    "error",
                    path,
                    f"unsupported namespace {namespace!r}; expected one of "
                    f"{sorted(SUPPORTED_GENE_NAMESPACES | SUPPORTED_PROTEIN_NAMESPACES)}",
                ),
            ),
        )
    if registry != spec.registry:
        return NamespaceResolution(
            namespace=namespace,
            registry=registry,
            resolution_status="declared_unresolved",
            messages=(
                _message(
                    "error",
                    path,
                    f"{spec.tier} namespace {namespace!r} must use registry {spec.registry!r}, got {registry!r}",
                ),
            ),
        )
    available, availability_messages = _registry_available(
        registry,
        expected_tier=spec.tier,
        registries=registries,
        path=path,
    )
    if not available:
        return NamespaceResolution(
            namespace=namespace,
            registry=registry,
            resolution_status="declared_unresolved",
            messages=availability_messages,
        )
    return NamespaceResolution(namespace=namespace, registry=registry, resolution_status="resolved")


def _default_registry_for_namespace(namespace: str) -> str:
    spec = _namespace_spec(namespace.strip())
    return spec.registry if spec is not None else ""


def _resolve_assembly_decl(
    identity_context: dict[str, Any],
    messages: list[IdentityResolutionMessage],
    *,
    commons_root: Path | None,
    data_root: Path | None,
) -> None:
    decl = identity_context.get("assembly")
    if not isinstance(decl, dict):
        return
    if decl.get("resolution_status") in {"resolved", "declared_unresolved"}:
        return

    label = decl.get("label")
    if not isinstance(label, str) or not label.strip():
        seqcol_digest = decl.get("seqcol_digest")
        label = seqcol_digest if isinstance(seqcol_digest, str) and seqcol_digest.strip() else None
    if label is None:
        return

    registry_value = decl.get("registry")
    registry = registry_value if isinstance(registry_value, str) else ASSEMBLY_REGISTRY_ID
    resolution = _resolve_assembly_label(
        label.strip(),
        registry,
        path="identity_context.assembly",
        commons_root=commons_root,
        data_root=data_root,
    )
    decl["registry"] = registry
    if resolution.seqcol_digest is None:
        decl["resolution_status"] = "declared_unresolved"
        messages.extend(resolution.messages)
        return
    decl["seqcol_digest"] = resolution.seqcol_digest
    decl["resolution_status"] = "resolved"
    messages.extend(resolution.messages)


def _resolve_molecular_id_decls(
    identity_context: dict[str, Any],
    messages: list[IdentityResolutionMessage],
    *,
    registries: Mapping[str, Any] | None,
) -> None:
    molecular_ids = identity_context.get("molecular_ids")
    if not isinstance(molecular_ids, dict):
        return
    for tier, decl in molecular_ids.items():
        if not isinstance(decl, dict):
            continue
        if tier == "variant":
            continue
        if decl.get("resolution_status") == "resolved":
            continue
        namespace = decl.get("namespace")
        path = f"identity_context.molecular_ids.{tier}"
        if not isinstance(namespace, str) or not namespace.strip():
            decl["resolution_status"] = "declared_unresolved"
            messages.append(_message("error", path, "missing or blank namespace"))
            continue
        registry_value = decl.get("registry")
        if isinstance(registry_value, str) and registry_value.strip():
            registry = registry_value
        else:
            registry = _default_registry_for_namespace(namespace)
        resolution = resolve_namespace(namespace, registry, registries=registries, path=path)
        decl["namespace"] = resolution.namespace
        decl["registry"] = resolution.registry
        decl["resolution_status"] = resolution.resolution_status
        messages.extend(resolution.messages)


def resolve_identity(
    ctx: dict[str, Any],
    *,
    registries: Mapping[str, Any] | None = None,
    mode: Literal["declare"] = "declare",
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> ResolvedIdentity:
    """Resolve or degrade a raw ``identity_context`` declaration.

    The default authoring path is non-throwing for unavailable commons artifacts:
    it returns a normalized copy plus messages. ``mode`` is intentionally narrow
    until another call site needs a distinct policy.
    """
    if mode != "declare":
        raise ValueError(f"unsupported identity resolution mode {mode!r}")
    if not isinstance(ctx, dict):
        raise TypeError("identity context must be a dict")

    identity_context = deepcopy(ctx)
    messages: list[IdentityResolutionMessage] = []
    _resolve_assembly_decl(identity_context, messages, commons_root=commons_root, data_root=data_root)
    _resolve_molecular_id_decls(identity_context, messages, registries=registries)
    return ResolvedIdentity(identity_context=identity_context, messages=tuple(messages))
