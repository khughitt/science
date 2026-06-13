# science/qa/src/science_qa/extensions.py
from __future__ import annotations

import importlib

from science_qa.aspects import CheckSpec


class ProjectLocalError(Exception):
    """Raised when a project_local reference cannot be imported or is not a CheckSpec."""


def load_project_local(refs: list[str], *, reserved_check_ids: set[str] | None = None) -> list[CheckSpec]:
    """Resolve 'module.path:attr' references to CheckSpec instances (append-only extension).

    Each attr must be a CheckSpec, or a list of CheckSpecs. Fail early on a malformed ref,
    an import error, a missing attribute, a wrong type, a non-project-local namespace,
    a check_id collision, or a project-local `requires` clause.
    """
    specs: list[CheckSpec] = []
    seen = set(reserved_check_ids or set())
    for ref in refs:
        module_path, sep, attr = ref.partition(":")
        if not sep or not attr:
            raise ProjectLocalError(f"project_local ref must be 'module:attr': {ref!r}")
        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            raise ProjectLocalError(f"cannot import project_local module {module_path!r}: {exc}") from exc
        if not hasattr(module, attr):
            raise ProjectLocalError(f"project_local module {module_path!r} has no attribute {attr!r}")
        obj = getattr(module, attr)
        for candidate in (obj if isinstance(obj, list) else [obj]):
            if not isinstance(candidate, CheckSpec):
                raise ProjectLocalError(f"project_local {ref!r} resolved to {type(candidate).__name__}, not a CheckSpec")
            if candidate.aspect != "project-local":
                raise ProjectLocalError(f"project_local {ref!r} must use the project-local aspect")
            if candidate.check_id in seen:
                raise ProjectLocalError(f"project_local check_id {candidate.check_id!r} collides with an existing check")
            if candidate.requires:
                raise ProjectLocalError(
                    f"project_local {candidate.check_id!r} declares requires={candidate.requires!r}; "
                    "missing-input ownership is not implemented for project-local checks"
                )
            seen.add(candidate.check_id)
            specs.append(candidate)
    return specs
