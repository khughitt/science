"""Update verb: refresh installed managed artifact to current canonical."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from science_tool.project_artifacts.migrations import run_migration
from science_tool.project_artifacts.migrations.transaction import (
    ManifestSnapshot,
    TempCommitSnapshot,
)
from science_tool.project_artifacts.paths import canonical_path
from science_tool.project_artifacts.registry_schema import (
    Artifact,
    MigrationKind,
    Pin,
    TransactionKind,
)
from science_tool.project_artifacts.status import Status, classify_full
from science_tool.project_artifacts.worktree import (
    dirty_paths,
    in_git_repo,
    is_clean,
    paths_intersect,
)


class UpdateError(Exception):
    """Raised when update refuses or fails."""


@dataclass(frozen=True)
class UpdateResult:
    name: str
    from_version: str | None
    to_version: str
    backup: Path
    committed: bool
    migrated_steps: list[str]


def update_artifact(
    artifact: Artifact,
    project_root: Path,
    *,
    pins: list[Pin] | None = None,
    allow_dirty: bool = False,
    no_commit: bool = False,
    force: bool = False,
    yes: bool = False,
    auto_apply: bool = False,
) -> UpdateResult:
    """Refresh *artifact* in *project_root* per spec Data flow 'update'."""
    target = project_root / artifact.install_target
    classified = classify_full(target, artifact, pins or [])

    # 1. Worktree check.
    if in_git_repo(project_root):
        if not is_clean(project_root) and not allow_dirty:
            dirty_list = sorted(str(p) for p in dirty_paths(project_root))
            raise UpdateError(
                f"refusing to update {artifact.name}: dirty worktree.\n"
                f"  dirty paths: {', '.join(dirty_list)}\n"
                f"  re-run with --allow-dirty (will refuse on path conflict) or commit/stash first"
            )
        if not is_clean(project_root) and allow_dirty:
            touched = [str(target.relative_to(project_root))]
            for m in artifact.migrations:
                for step in m.steps:
                    touched.extend(step.touched_paths)
            conflicts = paths_intersect(touched, dirty_paths(project_root))
            if conflicts:
                raise UpdateError(
                    f"refusing to update {artifact.name}: --allow-dirty path conflict\n"
                    f"  conflicting paths: {', '.join(sorted(str(p) for p in conflicts))}"
                )

    # 2. Locally-modified check.
    if classified.status is Status.LOCALLY_MODIFIED and not (force and yes):
        raise UpdateError(
            f"installed {artifact.name} is locally modified; "
            f"re-run with --force --yes to overwrite (writes .pre-update.bak)"
        )

    # 3. Take snapshot — only meaningful with migration steps; for byte-replace
    #    the .pre-update.bak alone is sufficient. We still take one for symmetry.
    snapshot: TempCommitSnapshot | ManifestSnapshot
    if in_git_repo(project_root) and artifact.mutation_policy.transaction_kind is TransactionKind.TEMP_COMMIT:
        snapshot = TempCommitSnapshot(project_root)
    else:
        touched_rel = [str(target.relative_to(project_root))]
        snapshot = ManifestSnapshot(project_root, [Path(t) for t in touched_rel])
    snapshot.take()

    try:
        # 4. Run any project_action migrations targeting the version we're upgrading TO.
        migrated_step_ids: list[str] = []
        for entry in artifact.migrations:
            if entry.to_version != artifact.version:
                continue
            if entry.kind is MigrationKind.PROJECT_ACTION and entry.steps:
                mig_result = run_migration(entry.steps, project_root, snapshot, auto_apply=auto_apply)
                if not mig_result.all_succeeded:
                    failure = next((s for s in mig_result.steps if s.action == "failed"), None)
                    raise UpdateError(
                        f"migration step {failure.step_id if failure else '?'!r} failed: "
                        f"{failure.detail if failure else '(unknown)'}"
                    )
                migrated_step_ids.extend(s.step_id for s in mig_result.steps if s.action == "applied")

        # 5. Byte-replace + write .pre-update.bak.
        backup = target.with_suffix(target.suffix + ".pre-update.bak")
        if target.exists():
            shutil.copy(target, backup)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(canonical_path(artifact.name), target)
        target.chmod(int(artifact.mode, 8))

        # 6. Commit.
        committed = False
        from_version = classified.detail.split()[-1] if classified.status is Status.STALE else None
        commit_lines = [
            f"chore(artifacts): refresh {artifact.name} to {artifact.version}",
            "",
            f"From: {from_version or 'unknown'}",
            f"To:   {artifact.version}",
        ]
        if migrated_step_ids:
            commit_lines.append("")
            commit_lines.append(f"Migrated steps: {', '.join(migrated_step_ids)}")
        commit_message = "\n".join(commit_lines) + "\n"

        if no_commit or not artifact.mutation_policy.commit_default:
            snapshot.discard(commit_message=None)
        else:
            if in_git_repo(project_root):
                snapshot.discard(commit_message=commit_message)
                committed = True
            else:
                snapshot.discard(commit_message=None)

        return UpdateResult(
            name=artifact.name,
            from_version=from_version,
            to_version=artifact.version,
            backup=backup,
            committed=committed,
            migrated_steps=migrated_step_ids,
        )
    except Exception:
        snapshot.restore()
        # On migration failure, ensure no leftover backup is visible.
        backup = target.with_suffix(target.suffix + ".pre-update.bak")
        if backup.exists():
            backup.unlink()
        raise
