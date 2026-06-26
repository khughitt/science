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
