"""Structural classification of a code file (harvested from MM30's classify_script).

Classification is *derived* from path + content + a precomputed workflow-reference
flag; it is deliberately independent of the *declared* lifecycle `status`
(umbrella decision 7). The orphan check (validate/checks/code_files.py) layers the
status-based exemption on top. `effective_decision_bearing` is fail-closed: an
executable with no explicit `decision_bearing` is treated as decision-bearing,
matching MM30 and umbrella §6.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_EXECUTABLE_SUFFIXES = {".R", ".r", ".sh"}
_WORKFLOW_SUFFIXES = {".smk"}
_PYTHON_ENTRY_POINTS = (
    'if __name__ == "__main__"',
    "if __name__ == '__main__'",
    "@click.command",
    "argparse.ArgumentParser",
    "snakemake",
)


@dataclass(frozen=True)
class CodeClassification:
    classification: str
    executable: bool
    workflow_referenced: bool
    effective_decision_bearing: bool


def is_executable(rel_path: str, text: str) -> bool:
    """True for a file that is run as a program. Workflow definitions are not
    executables (they are the workflow, not invoked by it)."""
    path = Path(rel_path)
    if path.suffix in _WORKFLOW_SUFFIXES or path.name == "Snakefile":
        return False
    if path.suffix in _EXECUTABLE_SUFFIXES:
        return True
    return any(marker in text for marker in _PYTHON_ENTRY_POINTS)


def classify_code_file(
    rel_path: str,
    text: str,
    *,
    declared_decision_bearing: bool | None,
    workflow_referenced: bool,
) -> CodeClassification:
    path = Path(rel_path)
    executable = is_executable(rel_path, text)
    if path.suffix in _WORKFLOW_SUFFIXES or path.name == "Snakefile":
        classification = "workflow-definition"
    elif path.name == "__init__.py":
        classification = "package-marker"
    elif "/tests/" in f"/{rel_path}" or path.name.startswith("test_"):
        classification = "test"
    elif executable and workflow_referenced:
        classification = "workflow-owned-executable"
    elif executable:
        classification = "orphaned-executable"
    else:
        classification = "library"

    if declared_decision_bearing is not None:
        effective_decision_bearing = declared_decision_bearing
    else:
        effective_decision_bearing = classification == "orphaned-executable"

    return CodeClassification(
        classification=classification,
        executable=executable,
        workflow_referenced=workflow_referenced,
        effective_decision_bearing=effective_decision_bearing,
    )
