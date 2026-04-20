"""Resolve DAG-related directory paths from the project's science.yaml configuration."""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class DagPaths:
    """Resolved paths for the DAG rendering and audit pipeline."""

    dag_dir: Path
    tasks_dir: Path
    dags: tuple[str, ...] | None  # None = auto-discover all <slug>.edges.yaml


def load_dag_paths(project_root: Path) -> DagPaths:
    """Load DAG path configuration from science.yaml.

    Falls back to research-profile defaults when the ``dag:`` block is absent.
    Raises ``FileNotFoundError`` for non-research profiles that lack the block.
    """
    cfg: dict = yaml.safe_load((project_root / "science.yaml").read_text()) or {}
    profile = cfg.get("profile", "research")
    block: dict | None = cfg.get("dag")

    if block is None and profile == "research":
        return DagPaths(
            dag_dir=project_root / "doc/figures/dags",
            tasks_dir=project_root / "tasks",
            dags=None,
        )

    if block is None:
        raise FileNotFoundError(f"'dag:' block required in science.yaml for profile={profile!r}")

    return DagPaths(
        dag_dir=project_root / block.get("dag_dir", "doc/figures/dags"),
        tasks_dir=project_root / block.get("tasks_dir", "tasks"),
        dags=tuple(block["dags"]) if block.get("dags") else None,
    )
