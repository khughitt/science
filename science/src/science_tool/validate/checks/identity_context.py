"""Assembly-identity checks (Pillar C, §5 checks 1 & 3; C1 detect-only, exact-equality).

Reads RAW frontmatter (the closed graph Entity does not surface extension
fields) and resolves declared assembly seqcol digests against the assembly
registry via the Plan 1 substrate `evaluate_key_resolution` (RCM-D2 guardrail 1,
exact-equality RCM-D6). Check 3 (cross-dataset assembly mismatch) is added in a
later task in this same module. See
docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md.

Dataset frontmatter is gathered by TOLERANT FILE DISCOVERY (both
DatapackageAdapter and MarkdownAdapter, via `dataset_frontmatters` in
`validate/_helpers.py`), not via `load_project_sources`: the graph loader
strict-validates every dataset through pydantic and RAISES on a malformed
core-kind entity, which would crash the whole run before this check could
report a defect. Mirrors the reference-collections check.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.assembly import AssemblyRegistryError, available_assembly_keys
from science_tool.commons.assembly_compatibility import (
    AssemblyCompatibilityError,
    CompatibilityRelation,
    load_compatibility_relations,
    relation_for,
)
from science_tool.commons.config import resolve_commons_root
from science_tool.commons.errors import CommonsError
from science_tool.commons.gene_crosswalk import (
    GENE_CROSSWALK_ID,
    SUPPORTED_GENE_NAMESPACES,
)
from science_tool.commons.gene_crosswalk import (
    MEMBER_KEY_COLUMN as _GENE_KEY_COLUMN,
)
from science_tool.commons.member import ResolutionState, evaluate_key_resolution
from science_tool.commons.protein_crosswalk import (
    MEMBER_KEY_COLUMN as _PROTEIN_KEY_COLUMN,
)
from science_tool.commons.protein_crosswalk import (
    PROTEIN_CROSSWALK_ID,
    SUPPORTED_PROTEIN_NAMESPACES,
)
from science_tool.validate._helpers import dataset_frontmatters, raw_frontmatter
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

# bio extensions whose data are assembly-anchored (coordinate-bearing).
_COORDINATE_EXTENSIONS = ("bio.rnaseq", "bio.scrna", "bio.cna")


def _result(severity: Severity, path: str | None, message: str, rule: str) -> Result:
    return Result(severity, Path(path) if path else None, None, message, rule, None)


def _is_coordinate_bearing(profile: str) -> bool:
    return any(f"+{ext}/" in f"+{profile}" for ext in _COORDINATE_EXTENSIONS)


def _assembly_defect(assembly: Any) -> str | None:
    """Return a defect message if the raw assembly block is malformed, else None.

    The graph Entity is closed and local authored frontmatter can bypass the
    JSON schema, so the schema-critical fields are re-enforced here.
    """
    if not isinstance(assembly, dict):
        return "not an object"
    digest = assembly.get("seqcol_digest")
    if not isinstance(digest, str) or not digest.strip():
        return "missing or blank seqcol_digest"
    registry = assembly.get("registry")
    if not isinstance(registry, str) or not registry.startswith("dataset:"):
        return "missing or malformed registry (must be a dataset: reference)"
    if assembly.get("resolution_status") not in ("resolved", "declared_unresolved"):
        return "resolution_status must be 'resolved' or 'declared_unresolved'"
    return None


def evaluate_identity_context(
    datasets: Iterable[dict[str, Any]], *, registry_keys_by_id: Mapping[str, set[str] | None]
) -> Iterator[Result]:
    """Pure core of check 1. `datasets` are raw frontmatter dicts (with `_path`).

    `registry_keys_by_id` maps each declared registry id to its seqcol-digest key
    set, or to None when that registry was attempted but could not be loaded.
    Keys are looked up by the registry the dataset *declares* — never a hard-coded
    default — so naming a foreign/unknown registry cannot silently validate
    against the canonical one. An unloadable/unknown registry yields an INFO
    (unverifiable), never a false ERROR.
    """
    reported_registries: set[str] = set()
    for fm in datasets:
        if fm.get("type") != "dataset":
            continue
        if not _is_coordinate_bearing(str(fm.get("schema_profile") or "")):
            continue
        path = fm.get("_path")
        ident = fm.get("id", "?")
        idc = fm.get("identity_context") or {}
        assembly = idc.get("assembly") if isinstance(idc, dict) else None

        if assembly is None:
            has_freetext = bool(fm.get("reference_genome"))
            detail = (
                "free-text reference_genome is set but identity_context.assembly is not; "
                "migrate to a structured seqcol_digest declaration"
                if has_freetext
                else "coordinate-bearing dataset does not declare identity_context.assembly"
            )
            yield _result(Severity.WARN, path, f"{ident}: {detail}", "identity.assembly-undeclared")
            continue

        defect = _assembly_defect(assembly)
        if defect is not None:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: malformed identity_context.assembly — {defect}",
                "identity.assembly-malformed",
            )
            continue

        digest = str(assembly["seqcol_digest"])
        registry_id = str(assembly["registry"])
        status = assembly["resolution_status"]

        known = registry_id in registry_keys_by_id and registry_keys_by_id[registry_id] is not None
        available = registry_keys_by_id[registry_id] if known else None
        state = evaluate_key_resolution(key=digest, available_keys=available, declared_status=status)
        if state is ResolutionState.UNRESOLVED:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: assembly seqcol_digest {digest!r} does not resolve in {registry_id!r}",
                "identity.assembly-unresolved",
            )
        elif state is ResolutionState.DECLARED_UNRESOLVED:
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: assembly seqcol_digest declared_unresolved (honoured, RCM-D2)",
                "identity.assembly-declared-unresolved",
            )
        elif state is ResolutionState.UNKNOWN and not known and registry_id not in reported_registries:
            reported_registries.add(registry_id)
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: registry {registry_id!r} unavailable; declared seqcol digest cannot be verified",
                "identity.registry-unavailable",
            )
        # RESOLVED passes silently.


@Check(section="assembly identity", order=25)
def check_identity_context_assembly(ctx: ValidateContext) -> Iterator[Result]:
    datasets = dataset_frontmatters(ctx)
    # Load keys for each registry actually declared (no default fallback): a
    # dataset's digest is verified only against the registry it names.
    declared_registries: set[str] = set()
    for fm in datasets:
        idc = fm.get("identity_context") or {}
        assembly = idc.get("assembly") if isinstance(idc, dict) else None
        if isinstance(assembly, dict) and isinstance(assembly.get("registry"), str):
            declared_registries.add(assembly["registry"])
    registry_keys_by_id: dict[str, set[str] | None] = {}
    for registry_id in declared_registries:
        try:
            registry_keys_by_id[registry_id] = available_assembly_keys(registry_id=registry_id)
        except (CommonsError, AssemblyRegistryError):
            registry_keys_by_id[registry_id] = None
    yield from evaluate_identity_context(datasets, registry_keys_by_id=registry_keys_by_id)


def _declared_digest(fm: dict[str, Any]) -> str | None:
    idc = fm.get("identity_context") or {}
    assembly = idc.get("assembly") if isinstance(idc, dict) else None
    if isinstance(assembly, dict) and assembly.get("seqcol_digest"):
        return str(assembly["seqcol_digest"])
    return None


def _has_liftover_remedy(
    derivation: Any,
    *,
    from_digest: str,
    to_digest: str,
    compatibility_relations_by_dataset_id: dict[str, list[CompatibilityRelation] | None] | None,
) -> bool:
    if not isinstance(derivation, dict):
        return False
    transformations = derivation.get("transformations")
    if not isinstance(transformations, list):
        return False

    relations_by_dataset_id = compatibility_relations_by_dataset_id or {}
    for transformation in transformations:
        if not isinstance(transformation, dict):
            continue
        dataset_id = transformation.get("dataset")
        if (
            transformation.get("type") != "liftover"
            or transformation.get("from_seqcol_digest") != from_digest
            or transformation.get("to_seqcol_digest") != to_digest
            or transformation.get("method") != "ucsc_chain"
            or not isinstance(dataset_id, str)
            or not dataset_id.startswith("dataset:")
        ):
            continue

        relations = relations_by_dataset_id.get(dataset_id)
        if relations is None:
            continue
        if (
            relation_for(relations, source_seqcol_digest=from_digest, target_seqcol_digest=to_digest)
            is not None
        ):
            return True
    return False


def evaluate_cross_dataset_assembly(
    datasets: Iterable[dict[str, Any]],
    *,
    compatibility_relations_by_dataset_id: dict[str, list[CompatibilityRelation] | None] | None = None,
) -> Iterator[Result]:
    """Pure core of check 3: flag a derived dataset whose inputs span assemblies.

    A declared liftover transformation remedies a parent-vs-derived mismatch
    only when the referenced liftover dataset resolves to a parsed exact-pair
    compatibility relation.
    """
    dataset_list = list(datasets)
    by_id = {fm.get("id"): fm for fm in dataset_list if fm.get("id")}
    for fm in dataset_list:
        derivation = fm.get("derivation") or {}
        inputs = derivation.get("inputs") if isinstance(derivation, dict) else None
        if not inputs:
            continue
        observed_digests: set[str] = set()
        parent_pairs: set[tuple[str, str]] = set()
        own = _declared_digest(fm)
        if own:
            observed_digests.add(own)
        for input_id in inputs:
            parent = by_id.get(input_id)
            if parent is None:
                continue  # not project-local; C1 scope is project-local inputs
            parent_digest = _declared_digest(parent)
            if parent_digest:
                observed_digests.add(parent_digest)
            if own and parent_digest and own != parent_digest:
                parent_pairs.add((parent_digest, own))

        unresolved_pairs = [
            (parent_digest, own_digest)
            for parent_digest, own_digest in sorted(parent_pairs)
            if not _has_liftover_remedy(
                derivation,
                from_digest=parent_digest,
                to_digest=own_digest,
                compatibility_relations_by_dataset_id=compatibility_relations_by_dataset_id,
            )
        ]
        if unresolved_pairs:
            yield _result(
                Severity.WARN,
                fm.get("_path"),
                f"{fm.get('id', '?')}: derivation inputs span distinct assemblies "
                f"{sorted(observed_digests)} without resolved declared liftover relations for "
                f"{unresolved_pairs}",
                "identity.cross-dataset-assembly-mismatch",
            )
        elif not parent_pairs and len(observed_digests) >= 2:
            yield _result(
                Severity.WARN,
                fm.get("_path"),
                f"{fm.get('id', '?')}: derivation inputs span distinct assemblies {sorted(observed_digests)} "
                f"with no derived target assembly to remedy",
                "identity.cross-dataset-assembly-mismatch",
            )


def _declared_liftover_datasets(datasets: Iterable[dict[str, Any]]) -> set[str]:
    dataset_ids: set[str] = set()
    for fm in datasets:
        derivation = fm.get("derivation") or {}
        transformations = derivation.get("transformations") if isinstance(derivation, dict) else None
        if not isinstance(transformations, list):
            continue
        for transformation in transformations:
            if not isinstance(transformation, dict) or transformation.get("type") != "liftover":
                continue
            dataset_id = transformation.get("dataset")
            if isinstance(dataset_id, str) and dataset_id.startswith("dataset:"):
                dataset_ids.add(dataset_id)
    return dataset_ids


def _load_relations_for_datasets(
    datasets: Iterable[dict[str, Any]],
    *,
    loader: Callable[..., list[CompatibilityRelation]] = load_compatibility_relations,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> dict[str, list[CompatibilityRelation] | None]:
    relations_by_dataset_id: dict[str, list[CompatibilityRelation] | None] = {}
    for dataset_id in _declared_liftover_datasets(datasets):
        try:
            relations_by_dataset_id[dataset_id] = loader(
                dataset_id=dataset_id,
                commons_root=commons_root,
                data_root=data_root,
            )
        except (CommonsError, AssemblyCompatibilityError):
            relations_by_dataset_id[dataset_id] = None
    return relations_by_dataset_id


@Check(section="assembly identity", order=26)
def check_cross_dataset_assembly(ctx: ValidateContext) -> Iterator[Result]:
    datasets = list(dataset_frontmatters(ctx))
    relations = _load_relations_for_datasets(datasets)
    yield from evaluate_cross_dataset_assembly(datasets, compatibility_relations_by_dataset_id=relations)


# --- C2/C3: molecular-id tier identity (declaration-level resolvability) ---


@dataclass(frozen=True, slots=True)
class _TierSpec:
    """Per-tier parameters for the shared declaration-level identity check."""

    tier: str  # the molecular_ids.<tier> key, e.g. "gene" | "protein"
    supported_namespaces: frozenset[str]
    default_registry: str
    key_column: str  # the crosswalk collection's member_key_column const
    profile_token: str  # e.g. "+bio.gene_crosswalk/"
    rule_prefix: str  # e.g. "identity.gene"


def _tier_decl(fm: dict[str, Any], tier: str) -> Any:
    """The raw identity_context.molecular_ids.<tier> declaration, or None."""
    idc = fm.get("identity_context") or {}
    mids = idc.get("molecular_ids") if isinstance(idc, dict) else None
    return mids.get(tier) if isinstance(mids, dict) else None


def tier_declaration_defect(decl: dict[str, Any]) -> str | None:
    """Return a defect message if the raw tier declaration is malformed, else None.

    Raw authored frontmatter bypasses the JSON schema (the closed graph Entity
    drops extension fields), so the schema-critical fields are re-enforced here,
    mirroring C1's `_assembly_defect`: `namespace` required + non-blank; optional
    `registry` a `dataset:` reference; optional `resolution_status` a valid state.
    Tier-independent. Without it, `maybe` would pass like `resolved` and a
    non-`dataset:` registry would degrade to a misleading INFO.
    """
    namespace = decl.get("namespace")
    if not isinstance(namespace, str) or not namespace.strip():
        return "missing or blank namespace"
    registry = decl.get("registry")
    if registry is not None and (not isinstance(registry, str) or not registry.startswith("dataset:")):
        return "registry must be a 'dataset:' reference"
    if decl.get("resolution_status") not in (None, "resolved", "declared_unresolved"):
        return "resolution_status must be 'resolved' or 'declared_unresolved'"
    return None


def _is_crosswalk(meta: dict[str, Any], *, profile_token: str, key_column: str) -> bool:
    profile = str(meta.get("schema_profile") or "")
    return profile_token in f"+{profile}" and meta.get("member_key_column") == key_column


def evaluate_tier_identity(
    datasets: Iterable[dict[str, Any]],
    *,
    spec: _TierSpec,
    registry_meta_by_id: Mapping[str, dict[str, Any] | None],
) -> Iterator[Result]:
    """Pure core of the declaration-level identity check, parameterized per tier.

    For each dataset declaring identity_context.molecular_ids.<spec.tier>, verify
    the namespace is crosswalk-supported and the declared registry resolves to the
    tier's crosswalk collection (member_key_column: spec.key_column). No data
    payload is read. Namespace support is validated BEFORE the declared_unresolved
    escape (every tier namespace is in scope, so an unsupported one is a real
    error). `registry_meta_by_id` maps each declared (or defaulted) registry id to
    its entity metadata, or None when it was attempted but could not be loaded
    (-> INFO, never a false ERROR). A loaded registry of the WRONG type is an
    ERROR. Unlike check 1 this does not resolve a member key: a declaration names
    a namespace, not a single key.
    """
    reported_registries: set[str] = set()
    for fm in datasets:
        if fm.get("type") != "dataset":
            continue
        decl = _tier_decl(fm, spec.tier)
        if decl is None:
            continue
        path = fm.get("_path")
        ident = fm.get("id", "?")
        loc = f"identity_context.molecular_ids.{spec.tier}"
        if not isinstance(decl, dict):
            yield _result(Severity.ERROR, path, f"{ident}: {loc} must be an object", f"{spec.rule_prefix}-malformed")
            continue
        defect = tier_declaration_defect(decl)
        if defect is not None:
            yield _result(
                Severity.ERROR, path, f"{ident}: malformed {loc} -- {defect}", f"{spec.rule_prefix}-malformed"
            )
            continue
        namespace = str(decl["namespace"])  # tier_declaration_defect guaranteed present + non-blank str
        if namespace not in spec.supported_namespaces:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: {spec.tier} namespace {namespace!r} is not crosswalk-supported "
                f"(expected one of {sorted(spec.supported_namespaces)})",
                f"{spec.rule_prefix}-namespace-unsupported",
            )
            continue
        if decl.get("resolution_status") == "declared_unresolved":
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: {spec.tier} identity declared_unresolved (honoured, RCM-D2)",
                f"{spec.rule_prefix}-declared-unresolved",
            )
            continue
        registry_id = decl["registry"] if isinstance(decl.get("registry"), str) else spec.default_registry
        meta = registry_meta_by_id.get(registry_id)
        if meta is None:
            if registry_id not in reported_registries:
                reported_registries.add(registry_id)
                yield _result(
                    Severity.INFO,
                    path,
                    f"{ident}: {spec.tier} registry {registry_id!r} unavailable; "
                    f"declared {spec.tier} namespace cannot be verified",
                    f"{spec.rule_prefix}-registry-unavailable",
                )
            continue
        if not _is_crosswalk(meta, profile_token=spec.profile_token, key_column=spec.key_column):
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: {spec.tier} registry {registry_id!r} is not a {spec.profile_token[1:-1]} collection "
                f"with member_key_column={spec.key_column!r}",
                f"{spec.rule_prefix}-registry-invalid",
            )
        # supported namespace + valid crosswalk -> passes silently.


def _load_registry_meta(
    registry_id: str,
    *,
    local_by_id: dict[str, dict[str, Any]],
    commons_cache: dict[str, dict[str, Any] | None],
) -> dict[str, Any] | None:
    """Load a registry's identifying metadata (schema_profile + member_key_column).

    Project-local datasets first, then the commons directly. Returns None when the
    registry cannot be loaded (commons not configured/available, or absent) -- the
    evaluator reports that as INFO, never a false ERROR. Mirrors the
    reference-collections check's commons lookup.
    """
    if registry_id in local_by_id:
        fm = local_by_id[registry_id]
        return {"schema_profile": fm.get("schema_profile", ""), "member_key_column": fm.get("member_key_column")}
    if registry_id in commons_cache:
        return commons_cache[registry_id]
    root = resolve_commons_root()
    meta: dict[str, Any] | None = None
    if root.is_dir():
        try:
            record = CommonsEntityAdapter(root).load(registry_id)
            body = getattr(record, "body_path", None)
            fm = raw_frontmatter(Path(body)) if body else {}
            meta = {"schema_profile": fm.get("schema_profile", ""), "member_key_column": fm.get("member_key_column")}
        except CommonsError:
            meta = None
    commons_cache[registry_id] = meta
    return meta


def _run_tier_check(ctx: ValidateContext, spec: _TierSpec) -> Iterator[Result]:
    """Gather raw frontmatter, load metadata for each registry a supported,
    non-declared_unresolved tier declares (or defaults to), then evaluate."""
    datasets = dataset_frontmatters(ctx)
    local_by_id = {fm["id"]: fm for fm in datasets if isinstance(fm.get("id"), str) and fm["id"]}
    declared: set[str] = set()
    for fm in datasets:
        decl = _tier_decl(fm, spec.tier)
        if not isinstance(decl, dict) or tier_declaration_defect(decl) is not None:
            continue  # malformed tiers are errored by the evaluator; load no registry for them
        if decl.get("resolution_status") == "declared_unresolved":
            continue
        if str(decl["namespace"]) in spec.supported_namespaces:
            declared.add(decl["registry"] if isinstance(decl.get("registry"), str) else spec.default_registry)
    commons_cache: dict[str, dict[str, Any] | None] = {}
    registry_meta_by_id = {
        registry_id: _load_registry_meta(registry_id, local_by_id=local_by_id, commons_cache=commons_cache)
        for registry_id in declared
    }
    yield from evaluate_tier_identity(datasets, spec=spec, registry_meta_by_id=registry_meta_by_id)


_GENE_SPEC = _TierSpec(
    tier="gene",
    supported_namespaces=SUPPORTED_GENE_NAMESPACES,
    default_registry=GENE_CROSSWALK_ID,
    key_column=_GENE_KEY_COLUMN,
    profile_token="+bio.gene_crosswalk/",
    rule_prefix="identity.gene",
)

_PROTEIN_SPEC = _TierSpec(
    tier="protein",
    supported_namespaces=SUPPORTED_PROTEIN_NAMESPACES,
    default_registry=PROTEIN_CROSSWALK_ID,
    key_column=_PROTEIN_KEY_COLUMN,
    profile_token="+bio.protein_crosswalk/",
    rule_prefix="identity.protein",
)


def evaluate_gene_identity(
    datasets: Iterable[dict[str, Any]], *, registry_meta_by_id: Mapping[str, dict[str, Any] | None]
) -> Iterator[Result]:
    """C2 gene declaration-level evaluator (thin wrapper over the generalized core)."""
    yield from evaluate_tier_identity(datasets, spec=_GENE_SPEC, registry_meta_by_id=registry_meta_by_id)


def evaluate_protein_identity(
    datasets: Iterable[dict[str, Any]], *, registry_meta_by_id: Mapping[str, dict[str, Any] | None]
) -> Iterator[Result]:
    """C3 protein declaration-level evaluator (thin wrapper over the generalized core)."""
    yield from evaluate_tier_identity(datasets, spec=_PROTEIN_SPEC, registry_meta_by_id=registry_meta_by_id)


@Check(section="gene identity", order=27)
def check_gene_identity(ctx: ValidateContext) -> Iterator[Result]:
    yield from _run_tier_check(ctx, _GENE_SPEC)


@Check(section="protein identity", order=28)
def check_protein_identity(ctx: ValidateContext) -> Iterator[Result]:
    yield from _run_tier_check(ctx, _PROTEIN_SPEC)
