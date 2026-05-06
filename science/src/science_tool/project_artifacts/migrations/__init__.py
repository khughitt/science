"""Migration framework: step protocol, runner, transaction snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from science_tool.project_artifacts.migrations.bash import BashStepAdapter
from science_tool.project_artifacts.migrations.python import PythonStepAdapter
from science_tool.project_artifacts.migrations.transaction import (
    ManifestSnapshot,
    TempCommitSnapshot,
)
from science_tool.project_artifacts.registry_schema import (
    BashImpl,
    MigrationStep,
    PythonImpl,
)

__all__ = [
    "BashStepAdapter",
    "ManifestSnapshot",
    "MigrationResult",
    "PythonStepAdapter",
    "StepResult",
    "TempCommitSnapshot",
    "run_migration",
]


def adapter_for(step: MigrationStep) -> BashStepAdapter | PythonStepAdapter:
    if isinstance(step.impl, PythonImpl):
        return PythonStepAdapter(step)
    if isinstance(step.impl, BashImpl):
        return BashStepAdapter(step)
    raise TypeError(f"unknown impl type for step {step.id!r}: {type(step.impl).__name__}")


@dataclass(frozen=True)
class StepResult:
    step_id: str
    action: Literal["skipped", "applied", "failed"]
    detail: str = ""


@dataclass
class MigrationResult:
    all_succeeded: bool
    steps: list[StepResult] = field(default_factory=list)


def run_migration(
    steps: list[MigrationStep],
    project_root: Path,
    snapshot: TempCommitSnapshot | ManifestSnapshot,
    *,
    auto_apply: bool,
) -> MigrationResult:
    """Walk *steps* in order. On any failure, restore the snapshot."""
    results: list[StepResult] = []
    for step in steps:
        adapter = adapter_for(step)
        # Pre-check: if the step is already satisfied, skip it.
        if adapter.check(project_root):
            results.append(StepResult(step.id, "skipped", "already satisfied"))
            continue
        # Confirmation: in non-interactive contexts (auto_apply=True) skip the prompt;
        # interactive prompting is the CLI verb's responsibility (Task 23 wires it).
        if not auto_apply and not step.idempotent:
            # Caller MUST set auto_apply=True or accept the step is non-idempotent
            # and risk re-running it. Runner does not prompt directly.
            results.append(StepResult(step.id, "failed", "non-idempotent step requires explicit confirmation"))
            snapshot.restore()
            return MigrationResult(False, results)
        # Apply.
        try:
            adapter.apply(project_root)
        except Exception as exc:  # noqa: BLE001
            results.append(StepResult(step.id, "failed", str(exc)))
            snapshot.restore()
            return MigrationResult(False, results)
        # Post-check.
        if not adapter.check(project_root):
            results.append(StepResult(step.id, "failed", "post-check did not report satisfied"))
            snapshot.restore()
            return MigrationResult(False, results)
        results.append(StepResult(step.id, "applied"))
    return MigrationResult(True, results)
