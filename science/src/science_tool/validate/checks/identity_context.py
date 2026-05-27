"""Assembly-identity checks (Pillar C, §5 checks 1 & 3; C1 detect-only, exact-equality).

Reads RAW frontmatter (the closed graph Entity does not surface extension
fields) and resolves declared assembly seqcol digests against the assembly
registry via the Plan 1 substrate `evaluate_key_resolution` (RCM-D2 guardrail 1,
exact-equality RCM-D6). Check 3 (cross-dataset assembly mismatch) is added in a
later task in this same module. See
docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md.

Dataset frontmatter is gathered by TOLERANT FILE DISCOVERY (DatapackageAdapter),
not via `load_project_sources`: the graph loader strict-validates every dataset
through pydantic and RAISES on a malformed core-kind entity, which would crash
the whole run before this check could report a defect. Mirrors the
reference-collections check.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import yaml

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.assembly import AssemblyRegistryError, available_assembly_keys
from science_tool.commons.config import resolve_commons_root
from science_tool.commons.errors import CommonsError
from science_tool.commons.gene_crosswalk import (
    GENE_CROSSWALK_ID,
    MEMBER_KEY_COLUMN as _GENE_KEY_COLUMN,
    SUPPORTED_GENE_NAMESPACES,
)
from science_tool.commons.member import ResolutionState, evaluate_key_resolution
from science_tool.graph.storage_adapters.datapackage import DatapackageAdapter
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

# bio extensions whose data are assembly-anchored (coordinate-bearing).
_COORDINATE_EXTENSIONS = ("bio.rnaseq", "bio.scrna", "bio.cna")


def _result(severity: Severity, path: str | None, message: str, rule: str) -> Result:
    return Result(severity, Path(path) if path else None, None, message, rule, None)


def _raw_frontmatter(path: Path) -> dict[str, Any]:
    """Raw frontmatter for either an entity.md (fenced YAML) or a datapackage.yaml."""
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        data = yaml.safe_load(text) or {}
    elif text.startswith("---"):
        end = text.find("\n---", 3)
        data = yaml.safe_load(text[3:end]) if end != -1 else {}
    else:
        data = {}
    return data if isinstance(data, dict) else {}


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
    datasets: Iterable[dict[str, Any]], *, registry_keys_by_id: dict[str, set[str] | None]
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


def _dataset_frontmatters(ctx: ValidateContext) -> list[dict[str, Any]]:
    """Raw frontmatter for every project dataset entity, by tolerant file discovery.

    `DatapackageAdapter.discover` finds dataset entity packages without
    strict-validating them through the graph loader (which RAISES on a malformed
    core-kind entity and would crash the run). Each dict carries `_path`
    (project-relative) for diagnostics. Mirrors the reference-collections check.
    """
    out: list[dict[str, Any]] = []
    for ref in DatapackageAdapter().discover(ctx.project_root):
        abs_path = ctx.project_root / ref.path
        if not abs_path.is_file():
            continue
        fm = _raw_frontmatter(abs_path)
        if fm.get("type") != "dataset":
            continue
        fm["_path"] = ref.path
        out.append(fm)
    return out


@Check(section="assembly identity", order=25)
def check_identity_context_assembly(ctx: ValidateContext) -> Iterator[Result]:
    datasets = _dataset_frontmatters(ctx)
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


def evaluate_cross_dataset_assembly(datasets: Iterable[dict[str, Any]]) -> Iterator[Result]:
    """Pure core of check 3: flag a derived dataset whose inputs span assemblies.

    Detect-only for C1 — the liftover remedy lands in C4 (§5 check 3).
    """
    by_id = {fm.get("id"): fm for fm in datasets if fm.get("id")}
    for fm in datasets:
        derivation = fm.get("derivation") or {}
        inputs = derivation.get("inputs") if isinstance(derivation, dict) else None
        if not inputs:
            continue
        digests: set[str] = set()
        own = _declared_digest(fm)
        if own:
            digests.add(own)
        for input_id in inputs:
            parent = by_id.get(input_id)
            if parent is None:
                continue  # not project-local; C1 scope is project-local inputs
            parent_digest = _declared_digest(parent)
            if parent_digest:
                digests.add(parent_digest)
        if len(digests) >= 2:
            yield _result(
                Severity.WARN,
                fm.get("_path"),
                f"{fm.get('id', '?')}: derivation inputs span distinct assemblies {sorted(digests)} "
                f"with no liftover available (detect-only; remedy in C4)",
                "identity.cross-dataset-assembly-mismatch",
            )


@Check(section="assembly identity", order=26)
def check_cross_dataset_assembly(ctx: ValidateContext) -> Iterator[Result]:
    yield from evaluate_cross_dataset_assembly(_dataset_frontmatters(ctx))


# --- C2: gene identity (check 2 — declaration-level resolvability) ---


def _gene_decl(fm: dict[str, Any]) -> Any:
    """The raw identity_context.molecular_ids.gene declaration, or None."""
    idc = fm.get("identity_context") or {}
    mids = idc.get("molecular_ids") if isinstance(idc, dict) else None
    return mids.get("gene") if isinstance(mids, dict) else None


def _gene_defect(gene: dict[str, Any]) -> str | None:
    """Return a defect message if the raw gene tier is malformed, else None.

    Raw authored frontmatter bypasses the JSON schema (the closed graph Entity
    drops extension fields), so the schema-critical fields are re-enforced here,
    mirroring C1's `_assembly_defect`: `namespace` is required and non-blank;
    `registry`, if present, must be a `dataset:` reference; `resolution_status`,
    if present, must be one of the two valid states. Without this, `maybe` would
    pass like `resolved` and a non-`dataset:` registry would degrade to INFO.
    """
    namespace = gene.get("namespace")
    if not isinstance(namespace, str) or not namespace.strip():
        return "missing or blank namespace"
    registry = gene.get("registry")
    if registry is not None and (not isinstance(registry, str) or not registry.startswith("dataset:")):
        return "registry must be a 'dataset:' reference"
    if gene.get("resolution_status") not in (None, "resolved", "declared_unresolved"):
        return "resolution_status must be 'resolved' or 'declared_unresolved'"
    return None


def _is_gene_crosswalk(meta: dict[str, Any]) -> bool:
    profile = str(meta.get("schema_profile") or "")
    return "+bio.gene_crosswalk/" in f"+{profile}" and meta.get("member_key_column") == _GENE_KEY_COLUMN


def evaluate_gene_identity(
    datasets: Iterable[dict[str, Any]], *, registry_meta_by_id: dict[str, dict[str, Any] | None]
) -> Iterator[Result]:
    """Pure core of check 2 (declaration-level). For each dataset declaring
    identity_context.molecular_ids.gene, verify the namespace is crosswalk-
    supported and the declared registry resolves to a bio.gene_crosswalk
    collection (member_key_column: gene_key). No data payload is read.

    Namespace support is validated BEFORE the declared_unresolved escape: for the
    gene tier every gene namespace is in C2's scope, so an unsupported gene
    namespace is a real error that declared_unresolved must not excuse.
    `registry_meta_by_id` maps each declared (or defaulted) registry id to its
    entity metadata {schema_profile, member_key_column}, or None when it was
    attempted but could not be loaded (-> INFO, never a false ERROR). A loaded
    registry of the WRONG type is an ERROR -- a wrong registry must not quietly
    pass. Unlike check 1 this does not resolve a member key: a gene declaration
    names a namespace, not a single key.
    """
    reported_registries: set[str] = set()
    for fm in datasets:
        if fm.get("type") != "dataset":
            continue
        gene = _gene_decl(fm)
        if gene is None:
            continue
        path = fm.get("_path")
        ident = fm.get("id", "?")
        if not isinstance(gene, dict):
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: identity_context.molecular_ids.gene must be an object",
                "identity.gene-malformed",
            )
            continue
        defect = _gene_defect(gene)
        if defect is not None:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: malformed identity_context.molecular_ids.gene -- {defect}",
                "identity.gene-malformed",
            )
            continue
        namespace = str(gene["namespace"])  # _gene_defect guaranteed present + non-blank str
        if namespace not in SUPPORTED_GENE_NAMESPACES:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: gene namespace {namespace!r} is not crosswalk-supported "
                f"(expected one of {sorted(SUPPORTED_GENE_NAMESPACES)})",
                "identity.gene-namespace-unsupported",
            )
            continue
        if gene.get("resolution_status") == "declared_unresolved":
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: gene identity declared_unresolved (honoured, RCM-D2)",
                "identity.gene-declared-unresolved",
            )
            continue
        registry_id = gene["registry"] if isinstance(gene.get("registry"), str) else GENE_CROSSWALK_ID
        meta = registry_meta_by_id.get(registry_id)
        if meta is None:
            if registry_id not in reported_registries:
                reported_registries.add(registry_id)
                yield _result(
                    Severity.INFO,
                    path,
                    f"{ident}: gene registry {registry_id!r} unavailable; declared gene namespace cannot be verified",
                    "identity.gene-registry-unavailable",
                )
            continue
        if not _is_gene_crosswalk(meta):
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: gene registry {registry_id!r} is not a bio.gene_crosswalk collection "
                f"with member_key_column={_GENE_KEY_COLUMN!r}",
                "identity.gene-registry-invalid",
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
            fm = _raw_frontmatter(Path(body)) if body else {}
            meta = {"schema_profile": fm.get("schema_profile", ""), "member_key_column": fm.get("member_key_column")}
        except CommonsError:
            meta = None
    commons_cache[registry_id] = meta
    return meta


@Check(section="gene identity", order=27)
def check_gene_identity(ctx: ValidateContext) -> Iterator[Result]:
    datasets = _dataset_frontmatters(ctx)
    local_by_id = {fm["id"]: fm for fm in datasets if isinstance(fm.get("id"), str) and fm["id"]}
    # Load metadata for each registry actually declared (or defaulted) by a gene
    # tier whose namespace is supported and which is not declared_unresolved.
    declared: set[str] = set()
    for fm in datasets:
        gene = _gene_decl(fm)
        if not isinstance(gene, dict) or _gene_defect(gene) is not None:
            continue  # malformed tiers are errored by the evaluator; load no registry for them
        if gene.get("resolution_status") == "declared_unresolved":
            continue
        namespace = str(gene["namespace"])
        if namespace in SUPPORTED_GENE_NAMESPACES:
            declared.add(gene["registry"] if isinstance(gene.get("registry"), str) else GENE_CROSSWALK_ID)
    commons_cache: dict[str, dict[str, Any] | None] = {}
    registry_meta_by_id = {
        registry_id: _load_registry_meta(registry_id, local_by_id=local_by_id, commons_cache=commons_cache)
        for registry_id in declared
    }
    yield from evaluate_gene_identity(datasets, registry_meta_by_id=registry_meta_by_id)
