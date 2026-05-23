from __future__ import annotations

import importlib.resources
import subprocess
from pathlib import Path


def _uv_lock(directory: Path) -> None:
    """Run ``uv lock`` in *directory*, silently skipping on failure."""
    try:
        subprocess.run(["uv", "lock"], cwd=directory, check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass


_NOTEBOOKS_PYPROJECT = """\
[project]
name = "notebooks"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "marimo",
    "altair>=5",
    "click",
    "polars",
    "rdflib>=7",
]
"""


def _copy_viz_notebook(notebooks_dir: Path) -> None:
    """Copy the bundled viz.py marimo notebook into the notebooks directory."""
    dest = notebooks_dir / "viz.py"
    if dest.exists():
        return
    notebooks_dir.mkdir(parents=True, exist_ok=True)
    template = importlib.resources.files("science_tool.graph").joinpath("viz_template.py")
    with importlib.resources.as_file(template) as src:
        import_root = Path(__file__).resolve().parents[3]
        content = src.read_text(encoding="utf-8").replace("__SCIENCE_TOOL_IMPORT_ROOT__", import_root.as_posix())
        dest.write_text(content, encoding="utf-8")

    pyproject = notebooks_dir / "pyproject.toml"
    if not pyproject.exists():
        pyproject.write_text(_NOTEBOOKS_PYPROJECT, encoding="utf-8")
        _uv_lock(notebooks_dir)
