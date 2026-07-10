"""Resolve DAG-related directory paths from the project's science.yaml configuration."""

from dataclasses import dataclass
from pathlib import Path

import yaml

from science_tool.data_root import project_config_path


@dataclass(frozen=True)
class DagPaths:
    """Resolved paths for the DAG rendering and audit pipeline."""

    dag_dir: Path
    tasks_dir: Path
    dags: tuple[str, ...] | None  # None = auto-discover all <slug>.dot files
    project_root: Path | None = None


def load_dag_paths(project_root: Path) -> DagPaths:
    """Load DAG path configuration from science.yaml.

    Falls back to defaults when the ``dag:`` block is absent. A project with
    no ``dag:`` block and no ``*.dot`` files is a valid empty state:
    auto-discover yields zero slugs and audit/validate return clean results.
    """
    cfg: dict = yaml.safe_load(project_config_path(project_root).read_text()) or {}
    block: dict | None = cfg.get("dag")

    if block is None:
        return DagPaths(
            dag_dir=project_root / "doc/figures/dags",
            tasks_dir=project_root / "tasks",
            dags=None,
            project_root=project_root,
        )

    return DagPaths(
        dag_dir=project_root / block.get("dag_dir", "doc/figures/dags"),
        tasks_dir=project_root / block.get("tasks_dir", "tasks"),
        dags=tuple(block["dags"]) if block.get("dags") else None,
        project_root=project_root,
    )
