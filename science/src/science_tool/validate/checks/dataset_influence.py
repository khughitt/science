"""Dataset influence/provenance checks for Pillar B1."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any, Literal

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.aliases import load_manual_aliases
from science_tool.commons.config import resolve_commons_root
from science_tool.commons.errors import CommonsError
from science_tool.commons.geneset import GenesetCollectionError, parse_geneset_rows
from science_tool.commons.geneset_resources import is_geneset_frontmatter, read_member_rows
from science_tool.graph.dataset_independence import DEPENDENCE_ROLES
from science_tool.graph.paper_dataset_migration import is_paper_dataset_role_conflict
from science_tool.validate._helpers import dataset_frontmatters, entity_frontmatters
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

DatasetRefStatus = Literal["resolved", "missing", "unavailable", "non_dataset"]


_COMMONS_LAYOUT_DIRS = (".git", "datasets", "papers", "topics", "themes")
_ROLES = ("analyzed", "set_definition_source", "validation_source", "cited", "upstream", "training", "reference")
_OVERLAPS = ("full", "partial", "unknown")


def _identity_dataset_ref(ref: str) -> str:
    return ref


def _result(severity: Severity, path: str | None, message: str, rule: str) -> Result:
    return Result(severity, Path(path) if path else None, None, message, rule, None)


def _usage_defect(entry: Any) -> str | None:
    if not isinstance(entry, dict):
        return "entry is not an object"
    ref = entry.get("ref")
    if not isinstance(ref, str) or not ref.startswith("dataset:"):
        return "ref must be a 'dataset:' reference"
    if entry.get("role") not in _ROLES:
        return f"role must be one of {list(_ROLES)}"
    overlap = entry.get("overlap")
    if overlap is not None and overlap not in _OVERLAPS:
        return f"overlap must be one of {list(_OVERLAPS)}"
    return None


def _iter_usage_entries(fm: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    usage = fm.get("dataset_usage")
    if usage is None:
        return [], None
    if not isinstance(usage, list):
        return [], f"dataset_usage must be a list, got {type(usage).__name__}"
    entries: list[dict[str, Any]] = []
    for index, entry in enumerate(usage):
        defect = _usage_defect(entry)
        if defect is not None:
            return [], f"dataset_usage[{index}] malformed -- {defect}"
        entries.append(entry)
    return entries, None


def _derivation_input_defect(raw_ref: Any) -> str | None:
    if not isinstance(raw_ref, str):
        return "entry is not a string"
    if not raw_ref.startswith("dataset:"):
        return "entry must be a 'dataset:' reference"
    return None


def evaluate_dataset_influence(
    frontmatters: Iterable[dict[str, Any]],
    *,
    dataset_ref_status: dict[str, DatasetRefStatus],
    row_usage_refs: Iterable[tuple[str, str, str]],
    canonicalize_dataset_ref: Callable[[str], str] = _identity_dataset_ref,
) -> Iterator[Result]:
    refs_to_check: list[tuple[str, str, str]] = []
    for fm in frontmatters:
        ident = str(fm.get("id") or "?")
        path = fm.get("_path")
        kind = fm.get("kind") or fm.get("type")
        usage_entries, defect = _iter_usage_entries(fm)
        if defect is not None:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: {defect}",
                "dataset-influence.dataset-usage-malformed",
            )
            continue

        for entry in usage_entries:
            ref = canonicalize_dataset_ref(str(entry["ref"]))
            if kind == "dataset" and ref == ident:
                yield _result(
                    Severity.ERROR,
                    path,
                    f"{ident}: dataset_usage must not reference itself",
                    "dataset-influence.self-reference",
                )
                continue
            refs_to_check.append((ref, ident, str(path or "")))
            role = entry["role"]
            if role in DEPENDENCE_ROLES and (entry.get("overlap") or "unknown") == "unknown":
                yield _result(
                    Severity.WARN,
                    path,
                    f"{ident}: dataset_usage {ref!r} has a dependence role ({role}) with overlap=unknown"
                    " — B2 treats it as a candidate (no shared-source collapse) until overlap is curated to full",
                    "dataset-influence.overlap-unknown-candidate",
                )

        derivation = fm.get("derivation")
        if kind == "dataset" and isinstance(derivation, dict):
            inputs = derivation.get("inputs")
            if isinstance(inputs, list):
                for index, raw_ref in enumerate(inputs):
                    defect = _derivation_input_defect(raw_ref)
                    if defect is not None:
                        yield _result(
                            Severity.ERROR,
                            path,
                            f"{ident}: derivation.inputs[{index}] invalid -- {defect}",
                            "dataset-influence.derivation-inputs-invalid",
                        )
                        continue
                    ref = canonicalize_dataset_ref(raw_ref)
                    if ref == ident:
                        yield _result(
                            Severity.ERROR,
                            path,
                            f"{ident}: derivation.inputs must not reference itself",
                            "dataset-influence.self-reference",
                        )
                    refs_to_check.append((ref, ident, str(path or "")))

        if kind == "paper":
            raw_datasets = fm.get("datasets")
            if raw_datasets is None:
                raw_datasets = []
            if not isinstance(raw_datasets, list):
                yield _result(
                    Severity.ERROR,
                    path,
                    f"{ident}: datasets must be a list of dataset: refs",
                    "dataset-influence.paper-datasets-invalid",
                )
                continue
            explicit_by_ref = {canonicalize_dataset_ref(str(entry["ref"])): entry for entry in usage_entries}
            for raw_ref in raw_datasets:
                if not isinstance(raw_ref, str) or not raw_ref.startswith("dataset:"):
                    yield _result(
                        Severity.ERROR,
                        path,
                        f"{ident}: paper.datasets entry {raw_ref!r} is not a dataset: ref",
                        "dataset-influence.paper-datasets-invalid",
                    )
                    continue
                ref = canonicalize_dataset_ref(raw_ref)
                if ref in explicit_by_ref:
                    entry = explicit_by_ref[ref]
                    if is_paper_dataset_role_conflict(entry):
                        yield _result(
                            Severity.WARN,
                            path,
                            f"{ident}: paper.datasets {ref!r} conflicts with explicit dataset_usage; explicit entry materializes",
                            "dataset-influence.paper-datasets-conflict",
                        )
                    continue
                yield _result(
                    Severity.WARN,
                    path,
                    f"{ident}: legacy paper.datasets {ref!r} should migrate to dataset_usage",
                    "dataset-influence.paper-datasets-legacy",
                )
                refs_to_check.append((ref, ident, str(path or "")))

    refs_to_check.extend(row_usage_refs)
    for ref, consumer, path in refs_to_check:
        status = dataset_ref_status.get(ref, "missing")
        if status == "resolved":
            continue
        if status == "unavailable":
            yield _result(
                Severity.INFO,
                path,
                f"{consumer}: dataset ref {ref!r} cannot be checked because registry resources are unavailable",
                "dataset-influence.ref-unresolved-unavailable",
            )
        elif status == "non_dataset":
            yield _result(
                Severity.ERROR,
                path,
                f"{consumer}: dataset ref {ref!r} resolves to a non-dataset entity",
                "dataset-influence.ref-not-dataset",
            )
        else:
            yield _result(
                Severity.WARN,
                path,
                f"{consumer}: dataset ref {ref!r} does not resolve to a local or commons dataset",
                "dataset-influence.ref-unresolved",
            )


def _dataset_ref_statuses(
    ctx: ValidateContext,
    refs: set[str],
    frontmatters: Iterable[dict[str, Any]],
) -> dict[str, DatasetRefStatus]:
    local_kinds = _local_entity_kinds(frontmatters)
    # Markdown dataset descriptors (entities/datasets/) live outside the entity scan roots,
    # so entity_frontmatters never surfaces them; fold in dataset_frontmatters (both
    # markdown + datapackage backends) or every dataset_usage ref to a markdown-only
    # local dataset would warn ref-unresolved despite the descriptor existing.
    for ds_fm in _local_entity_kinds(dataset_frontmatters(ctx)).items():
        local_kinds.setdefault(*ds_fm)
    root = resolve_commons_root()
    commons_available = _has_initialized_commons_layout(root)
    adapter = CommonsEntityAdapter(root) if commons_available else None
    out: dict[str, DatasetRefStatus] = {}
    for ref in refs:
        local_kind = local_kinds.get(ref)
        if local_kind is not None:
            out[ref] = "resolved" if local_kind == "dataset" else "non_dataset"
            continue
        if adapter is None:
            out[ref] = "unavailable"
            continue
        try:
            record = adapter.load(ref)
        except CommonsError:
            out[ref] = "missing"
            continue
        kind = record.frontmatter.get("kind") or record.frontmatter.get("type")
        out[ref] = "resolved" if kind == "dataset" else "non_dataset"
    return out


def _local_entity_kinds(frontmatters: Iterable[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for fm in frontmatters:
        ident = fm.get("id")
        kind = fm.get("kind") or fm.get("type")
        if isinstance(ident, str) and ident and isinstance(kind, str) and kind:
            out[ident] = kind
    return out


class _DatasetRefResolver:
    def __init__(
        self,
        frontmatters: Iterable[dict[str, Any]],
        *,
        manual_aliases: dict[str, str] | None = None,
    ) -> None:
        aliases: dict[str, str | None] = {}
        for fm in frontmatters:
            ident = fm.get("id")
            if not isinstance(ident, str) or not ident:
                continue
            self._register(aliases, ident, ident)
            self._register(aliases, ident.lower(), ident)
            raw_aliases = fm.get("aliases")
            if not isinstance(raw_aliases, list):
                continue
            for alias in raw_aliases:
                if isinstance(alias, str) and alias:
                    self._register(aliases, alias, ident)
                    self._register(aliases, alias.lower(), ident)
        for alias, canonical_id in (manual_aliases or {}).items():
            self._register(aliases, alias, canonical_id)
            self._register(aliases, alias.lower(), canonical_id)
        self._aliases = aliases

    @staticmethod
    def _register(aliases: dict[str, str | None], alias: str, canonical_id: str) -> None:
        existing = aliases.get(alias)
        if existing is None and alias in aliases:
            return
        if existing is not None and existing != canonical_id:
            aliases[alias] = None
            return
        aliases[alias] = canonical_id

    def resolve(self, ref: str) -> str:
        canonical = self._aliases.get(ref)
        if canonical is None and ref in self._aliases:
            return ref
        if canonical is None:
            canonical = self._aliases.get(ref.lower())
        return ref if canonical is None else canonical


def _has_initialized_commons_layout(root: Path) -> bool:
    return root.is_dir() and all((root / dirname).is_dir() for dirname in _COMMONS_LAYOUT_DIRS)


def _local_profile(ctx: ValidateContext) -> str:
    profiles = ctx.manifest.get("knowledge_profiles")
    if isinstance(profiles, dict) and isinstance(profiles.get("local"), str):
        return profiles["local"]
    return "local"


def _collect_refs(
    frontmatters: list[dict[str, Any]],
    row_usage_refs: list[tuple[str, str, str]],
    canonicalize_dataset_ref: Callable[[str], str],
) -> set[str]:
    refs = {ref for ref, _consumer, _path in row_usage_refs}
    for fm in frontmatters:
        usage = fm.get("dataset_usage")
        if isinstance(usage, list):
            for entry in usage:
                raw_ref = entry.get("ref") if isinstance(entry, dict) else None
                if isinstance(raw_ref, str) and raw_ref.startswith("dataset:"):
                    refs.add(canonicalize_dataset_ref(raw_ref))
        datasets = fm.get("datasets")
        if isinstance(datasets, list):
            refs.update(
                canonicalize_dataset_ref(raw_ref)
                for raw_ref in datasets
                if isinstance(raw_ref, str) and raw_ref.startswith("dataset:")
            )
        derivation = fm.get("derivation")
        if isinstance(derivation, dict) and isinstance(derivation.get("inputs"), list):
            refs.update(
                canonicalize_dataset_ref(raw_ref)
                for raw_ref in derivation["inputs"]
                if isinstance(raw_ref, str) and raw_ref.startswith("dataset:")
            )
    return refs


def _row_usage_refs(
    ctx: ValidateContext, frontmatters: list[dict[str, Any]], canonicalize_dataset_ref: Callable[[str], str]
) -> list[tuple[str, str, str]]:
    refs: list[tuple[str, str, str]] = []
    for fm in frontmatters:
        if not is_geneset_frontmatter(fm):
            continue
        ident = fm.get("id")
        path = str(fm.get("_path") or "")
        if not isinstance(ident, str) or not ident:
            continue
        raw_rows = read_member_rows(ctx.project_root, fm)
        if raw_rows is None or isinstance(raw_rows, Exception):
            continue
        try:
            rows = parse_geneset_rows(raw_rows)
        except GenesetCollectionError:
            continue
        for row in rows:
            for usage in row.dataset_usage:
                refs.append((canonicalize_dataset_ref(str(usage["ref"])), f"{ident}#{row.set_key}", path))
    return refs


@Check(section="dataset influence", order=36)
def check_dataset_influence(ctx: ValidateContext) -> Iterator[Result]:
    frontmatters = entity_frontmatters(ctx)
    resolver = _DatasetRefResolver(
        frontmatters,
        manual_aliases=load_manual_aliases(ctx.project_root, local_profile=_local_profile(ctx)),
    )
    row_refs = _row_usage_refs(ctx, frontmatters, resolver.resolve)
    statuses = _dataset_ref_statuses(ctx, _collect_refs(frontmatters, row_refs, resolver.resolve), frontmatters)
    yield from evaluate_dataset_influence(
        frontmatters,
        dataset_ref_status=statuses,
        row_usage_refs=row_refs,
        canonicalize_dataset_ref=resolver.resolve,
    )
