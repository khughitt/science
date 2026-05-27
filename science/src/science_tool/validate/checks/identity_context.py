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

from science_tool.commons.assembly import AssemblyRegistryError, available_assembly_keys
from science_tool.commons.errors import CommonsError
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
