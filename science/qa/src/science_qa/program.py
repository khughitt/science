from __future__ import annotations

from dataclasses import dataclass

from science_qa.aspects import CHECK_FAMILY, CHECK_REQUIRED, CheckSpec, Invocation
from science_qa.aspects import gene_expression_qc as gx
from science_qa.aspects import general, numeric_column, scrna_qc, tabular
from science_qa.context import TableContext


class ProgramError(Exception):
    """Raised when an unknown program is requested."""


@dataclass(frozen=True)
class Program:
    name: str
    substrate: type
    checks: list[CheckSpec]


# --- family expand callables (program declares WHAT; config supplies items) ---

def _expand_unique_key(config) -> list[Invocation]:
    groups: list[list[str]] = []
    if config.unique_key:
        groups.append([config.unique_key])
    groups.extend([list(g) for g in config.unique_keys])
    # Dedupe overlapping groups (a field can be both unique:true and the primaryKey)
    # so the same key never yields two invocations -> two flags. Order preserved.
    deduped: list[list[str]] = []
    for g in groups:
        if g not in deduped:
            deduped.append(g)
    return [Invocation(columns=g, requires=tuple(g)) for g in deduped]


def _expand_required_complete(config) -> list[Invocation]:
    return [Invocation(columns=[c], requires=(c,)) for c in config.required_complete]


def _expand_categoricals(config) -> list[Invocation]:
    return [Invocation(columns=[c], requires=(c,), params={"spec": spec, "base_dir": config.base_dir})
            for c, spec in config.categoricals.items()]


def _expand_exclusive_flags(config) -> list[Invocation]:
    return [Invocation(columns=list(pair), requires=tuple(pair)) for pair in config.exclusive_flags]


def _expand_type_conformance(config) -> list[Invocation]:
    return [Invocation(columns=[c], requires=(c,), params={"expected": exp})
            for c, exp in config.expected_types.items()]


def _expand_polarity(config) -> list[Invocation]:
    return [Invocation(columns=[c], requires=(c,)) for c in config.polarity]


def _expand_ranges(config) -> list[Invocation]:
    return [Invocation(columns=[c], requires=(c,), params={"bounds": b}) for c, b in config.ranges.items()]


def _expand_missing_sentinels(config) -> list[Invocation]:
    if not config.missing_sentinels:
        return []
    return [Invocation(columns=None, params={"sentinels": list(config.missing_sentinels)})]  # selector-driven


def _expand_bounds(config) -> list[Invocation]:
    return [Invocation(columns=[c], requires=(c,), params={"bounds": b})
            for c, b in config.bounds.items()]


def _expand_doublet(config) -> list[Invocation]:
    # one *optional* invocation: doublet_score is legitimately optional -> not-applicable when absent
    params = config.aspect_params.get("scrna-qc-table", {})
    return [Invocation(requires=("doublet_score",), columns=["doublet_score"], optional=True, params=params)]


def _scrna_param(config) -> dict:
    return config.aspect_params.get("scrna-qc-table", {})


_SCRNA_QC_TABLE = Program(
    name="scrna-qc-table",
    substrate=TableContext,
    checks=[
        CheckSpec("general", "non_empty", CHECK_REQUIRED, TableContext, general.non_empty),
        CheckSpec("general", "missing_fraction", CHECK_REQUIRED, TableContext, general.missing_fraction),
        CheckSpec("tabular", "unique_key", CHECK_FAMILY, TableContext, tabular.unique_key, expand=_expand_unique_key),
        CheckSpec("tabular", "required_complete", CHECK_FAMILY, TableContext, tabular.required_complete, expand=_expand_required_complete),
        CheckSpec("tabular", "categoricals", CHECK_FAMILY, TableContext, tabular.categoricals, expand=_expand_categoricals),
        CheckSpec("tabular", "exclusive_flags", CHECK_FAMILY, TableContext, tabular.exclusive_flags, expand=_expand_exclusive_flags),
        CheckSpec("tabular", "type_conformance", CHECK_FAMILY, TableContext, tabular.type_conformance, expand=_expand_type_conformance),
        CheckSpec("numeric-column", "zero_fraction", CHECK_REQUIRED, TableContext, numeric_column.zero_fraction, selector={"dtype": "numeric"}),
        CheckSpec("numeric-column", "low_variance", CHECK_REQUIRED, TableContext, numeric_column.low_variance, selector={"dtype": "numeric"}),
        CheckSpec("numeric-column", "polarity", CHECK_FAMILY, TableContext, numeric_column.polarity, expand=_expand_polarity),
        CheckSpec("numeric-column", "range", CHECK_FAMILY, TableContext, numeric_column.ranges, expand=_expand_ranges),
        CheckSpec("numeric-column", "missing_sentinel", CHECK_FAMILY, TableContext, numeric_column.missing_sentinels, selector={"dtype": "numeric"}, expand=_expand_missing_sentinels),
        CheckSpec("gene-expression-qc-table", "required_column", CHECK_REQUIRED, TableContext, gx.required_column),
        CheckSpec("gene-expression-qc-table", "library_size_positive", CHECK_REQUIRED, TableContext, gx.library_size_positive, requires=("total_counts",)),
        CheckSpec("gene-expression-qc-table", "degenerate_cell", CHECK_REQUIRED, TableContext, gx.degenerate_cell, requires=("total_counts", "n_genes_by_counts")),
        CheckSpec("scrna-qc-table", "gates", CHECK_REQUIRED, TableContext, scrna_qc.gates, requires=("total_counts", "n_genes_by_counts", "pct_counts_mt")),
        CheckSpec("scrna-qc-table", "doublet_ceiling", CHECK_FAMILY, TableContext, scrna_qc.doublet_ceiling, expand=_expand_doublet),
    ],
)

_TABULAR = Program(
    name="tabular",
    substrate=TableContext,
    checks=[
        CheckSpec("general", "non_empty", CHECK_REQUIRED, TableContext, general.non_empty),
        CheckSpec("general", "missing_fraction", CHECK_REQUIRED, TableContext, general.missing_fraction),
        CheckSpec("tabular", "unique_key", CHECK_FAMILY, TableContext, tabular.unique_key, expand=_expand_unique_key),
        CheckSpec("tabular", "required_complete", CHECK_FAMILY, TableContext, tabular.required_complete, expand=_expand_required_complete),
        CheckSpec("tabular", "categoricals", CHECK_FAMILY, TableContext, tabular.categoricals, expand=_expand_categoricals),
        CheckSpec("tabular", "exclusive_flags", CHECK_FAMILY, TableContext, tabular.exclusive_flags, expand=_expand_exclusive_flags),
        CheckSpec("tabular", "type_conformance", CHECK_FAMILY, TableContext, tabular.type_conformance, expand=_expand_type_conformance),
        CheckSpec("numeric-column", "bounds", CHECK_FAMILY, TableContext, numeric_column.bounds, expand=_expand_bounds),
        CheckSpec("numeric-column", "range", CHECK_FAMILY, TableContext, numeric_column.ranges, expand=_expand_ranges),
        CheckSpec("numeric-column", "polarity", CHECK_FAMILY, TableContext, numeric_column.polarity, expand=_expand_polarity),
        CheckSpec("numeric-column", "zero_fraction", CHECK_REQUIRED, TableContext, numeric_column.zero_fraction, selector={"dtype": "numeric"}),
        CheckSpec("numeric-column", "low_variance", CHECK_REQUIRED, TableContext, numeric_column.low_variance, selector={"dtype": "numeric"}),
        CheckSpec("numeric-column", "missing_sentinel", CHECK_FAMILY, TableContext, numeric_column.missing_sentinels, selector={"dtype": "numeric"}, expand=_expand_missing_sentinels),
    ],
)

PROGRAMS: dict[str, Program] = {_SCRNA_QC_TABLE.name: _SCRNA_QC_TABLE, _TABULAR.name: _TABULAR}


def resolve_program(name: str) -> Program:
    if name not in PROGRAMS:
        raise ProgramError(f"unknown program {name!r}; known: {sorted(PROGRAMS)}")
    return PROGRAMS[name]
