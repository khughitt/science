"""Shared dataset catalog class and runtime-state semantics."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

DatasetClass = Literal["deposit", "reference", "pointer"]
RuntimeState = Literal["runnable", "unstaged-deposit", "blocked-access", "reference-only", "pointer-only"]

_DATASET_CLASSES: set[str] = {"deposit", "reference", "pointer"}
_GATED_LEVELS = {"registration", "controlled", "commercial"}


def _nonempty_str(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def dataset_class_for(fm: Mapping[str, object]) -> DatasetClass:
    """Return the explicit dataset class, defaulting missing/blank rows to deposit."""
    raw = _nonempty_str(fm.get("dataset_class"))
    if not raw:
        return "deposit"
    if raw not in _DATASET_CLASSES:
        raise ValueError(f"unrecognized dataset_class {raw!r}")
    return raw  # type: ignore[return-value]


def has_runtime_artifact(fm: Mapping[str, object]) -> bool:
    """Whether frontmatter names a staged runtime artifact."""
    return bool(_nonempty_str(fm.get("datapackage")) or _nonempty_str(fm.get("local_path")))


def _access(fm: Mapping[str, object]) -> Mapping[str, object]:
    access = fm.get("access")
    return access if isinstance(access, Mapping) else {}


def _has_exception(access: Mapping[str, object]) -> bool:
    exception = access.get("exception")
    if not isinstance(exception, Mapping):
        return False
    return bool(_nonempty_str(exception.get("mode")))


OrdinalReproClass = Literal[
    "third-party-reproducible",
    "credentialed-reproducible",
    "trust-based-output",
    "insider-only",
]
ReproClass = Literal[
    "third-party-reproducible",
    "credentialed-reproducible",
    "trust-based-output",
    "insider-only",
    "unknown",
]

# Known classes, strongest -> weakest. `unknown` is OFF-lattice.
_REPRO_LATTICE: tuple[str, ...] = (
    "third-party-reproducible",
    "credentialed-reproducible",
    "trust-based-output",
    "insider-only",
)
_LOCAL_RERUNNABLE = {"full-dataset", "analysis-dataset", "synthetic-dataset"}
_CREDENTIALED_OBTAIN = {"registration", "self-service-dua", "approved-researcher"}
_TRE_EXECUTION = {"trusted-environment", "federated-code-to-data"}
_AGGREGATE_EXTRACT = {"aggregate-reviewed", "aggregate-unreviewed"}


def _repro(access: Mapping[str, object]) -> Mapping[str, object]:
    repro = access.get("reproducibility")
    return repro if isinstance(repro, Mapping) else {}


def reproducibility_class_for(fm: Mapping[str, object]) -> tuple[ReproClass, str]:
    """Derive (class, gap_reason) from access.reproducibility controls.

    Returns 'unknown' if any decision-relevant control is unknown or the block is
    absent. gap_reason lists the controls that determined a non-top class.
    Ordered rules; first match wins. insider-only is checked before trust-based-output.
    """
    repro = _repro(_access(fm))
    obtain = _nonempty_str(repro.get("obtainability")) or "unknown"
    execution = _nonempty_str(repro.get("execution")) or "unknown"
    extract = _nonempty_str(repro.get("extractability")) or "unknown"
    gap = f"{obtain} + {execution} + {extract}"

    if "unknown" in (obtain, execution, extract):
        return "unknown", "unassessed: " + gap
    if extract in _LOCAL_RERUNNABLE and obtain == "public":
        return "third-party-reproducible", ""
    if extract in _LOCAL_RERUNNABLE and obtain in _CREDENTIALED_OBTAIN:
        return "credentialed-reproducible", gap
    if obtain == "named-collaboration" or execution == "custodian-run" or extract == "none":
        return "insider-only", gap
    if execution in _TRE_EXECUTION and extract in _AGGREGATE_EXTRACT:
        return "trust-based-output", gap
    return "insider-only", gap  # conservative fail-safe for unmatched fully-known combos


def repro_class_rank(cls: str) -> int:
    """Rank a KNOWN class; higher = more reproducible. Raises on off-lattice 'unknown'."""
    try:
        return len(_REPRO_LATTICE) - _REPRO_LATTICE.index(cls)
    except ValueError as exc:
        raise ValueError(f"{cls!r} is not an ordinal reproducibility class") from exc


def repro_meets_bar(cls: str, bar: str) -> bool:
    """True if KNOWN class `cls` meets or exceeds `bar`. Both must be on the lattice."""
    return repro_class_rank(cls) >= repro_class_rank(bar)


def runtime_state_for(fm: Mapping[str, object]) -> RuntimeState:
    """Derive runtime stageability using the catalog Phase 1 precedence order."""
    dataset_class = dataset_class_for(fm)
    if dataset_class == "reference":
        return "reference-only"
    if dataset_class == "pointer":
        return "pointer-only"
    if has_runtime_artifact(fm):
        return "runnable"

    access = _access(fm)
    verified = access.get("verified") is True
    level = _nonempty_str(access.get("level"))
    if _has_exception(access) or (level in _GATED_LEVELS and not verified):
        return "blocked-access"
    if verified:
        return "unstaged-deposit"
    return "blocked-access"
