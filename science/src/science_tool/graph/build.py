"""CLI-facing local-graph build service.

Owns the register-then-materialize policy for `science graph build`: resolve
the project root, register the project with the local Science registry (iff
`science.yaml` exists), and materialize `knowledge/graph.trig`.

Deliberately narrow contract — composite-graph refresh, `--local-only`
semantics, and non-blocking ontology suggestions stay in the `graph build`
command (`science_tool.graph.cli`), not here. `materialize_graph` itself
(`science_tool.graph.materialize`) has non-CLI callers (annotation archiving,
source snapshots, freshness propagation, the inquiry store, `graph/__init__`)
and must never gain a registry side-effect, so registration lives only in
this wrapper.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from science_tool.data_root import project_config_path
from science_tool.graph.materialize import materialize_graph
from science_tool.project_config import ProjectConfig


@dataclass
class LocalGraphBuild:
    """Result of `build_project_graph`: the materialized local graph path plus config."""

    local_path: Path
    config: ProjectConfig | None


def build_project_graph(project_root: Path) -> LocalGraphBuild:
    """Register the project (if configured) and materialize `knowledge/graph.trig`.

    Lets `materialize_graph`'s `ValueError` propagate; callers keep their own
    error handling around it.
    """
    from science_tool.project_config import load_project_config
    from science_tool.registry.config import ensure_registered

    _project_root = Path.cwd() if str(project_root) == "." else project_root
    _science_yaml = project_config_path(_project_root)
    _cfg: ProjectConfig | None = None
    if _science_yaml.is_file():
        _cfg = load_project_config(_project_root)
        ensure_registered(
            _project_root,
            _cfg.name,
            project_id=_cfg.id,
            role=str(_cfg.role),
            parent=None,
        )

    local_path = materialize_graph(_project_root)
    return LocalGraphBuild(local_path=local_path, config=_cfg)
