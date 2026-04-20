"""Assemble a research package from workflow results."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from science_model.packages.validation import validate_package


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_commit() -> str:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _read_workflow_config(config_path: Path) -> dict:
    """Parse workflow config.yaml via regex."""
    result: dict = {}
    if not config_path.is_file():
        return result
    text = config_path.read_text(encoding="utf-8")

    for key in ("title", "lens", "section", "workflow_name", "repository"):
        match = re.search(rf"^{key}:\s*[\"']?(.+?)[\"']?\s*$", text, re.MULTILINE)
        if match:
            result[key] = match.group(1).strip()

    scripts_match = re.search(r"^scripts:\s*\n((?:\s+- .+\n?)+)", text, re.MULTILINE)
    if scripts_match:
        result["scripts"] = [s.strip() for s in re.findall(r"\s+- (.+)", scripts_match.group(1))]

    inputs_match = re.search(r"^provenance_inputs:\s*\n((?:\s+- .+\n?)+)", text, re.MULTILINE)
    if inputs_match:
        result["inputs"] = [s.strip() for s in re.findall(r"\s+- (.+)", inputs_match.group(1))]

    prose_match = re.search(r"^prose_dir:\s*(.+)$", text, re.MULTILINE)
    if prose_match:
        result["prose_dir"] = prose_match.group(1).strip()

    cells_match = re.search(r"^cells_file:\s*(.+)$", text, re.MULTILINE)
    if cells_match:
        result["cells_file"] = cells_match.group(1).strip()

    excerpts_match = re.search(r"^code_excerpts:\s*\n((?:\s+- .+\n?|\s+\w+:.+\n?)+)", text, re.MULTILINE)
    if excerpts_match:
        excerpt_blocks = re.findall(
            r"- name:\s*(.+)\n\s+source:\s*(.+)\n\s+lines:\s*\[(\d+),\s*(\d+)\]",
            excerpts_match.group(1),
        )
        result["code_excerpts"] = [
            {"name": n.strip(), "source": s.strip(), "lines": [int(a), int(b)]} for n, s, a, b in excerpt_blocks
        ]

    return result


def build_research_package(
    results_dir: Path,
    config_path: Path,
    output_dir: Path,
) -> list[str]:
    """Assemble a research package from workflow results. Returns error list."""
    config = _read_workflow_config(config_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    data_dir = output_dir / "data"
    data_dir.mkdir(exist_ok=True)
    figures_dir = output_dir / "figures"
    figures_dir.mkdir(exist_ok=True)
    prose_dir_out = output_dir / "prose"
    prose_dir_out.mkdir(exist_ok=True)
    excerpts_dir = output_dir / "excerpts"
    excerpts_dir.mkdir(exist_ok=True)

    # Copy CSVs
    resources = []
    for csv_file in sorted(results_dir.glob("*.csv")):
        dest = data_dir / csv_file.name
        shutil.copy2(csv_file, dest)
        resources.append({"name": csv_file.stem, "path": f"data/{csv_file.name}"})

    # Copy figures
    figures = []
    vegalite_specs = []
    results_figures = results_dir / "figures"
    if results_figures.is_dir():
        for fig_file in sorted(results_figures.iterdir()):
            dest = figures_dir / fig_file.name
            shutil.copy2(fig_file, dest)
            if fig_file.suffix == ".png":
                figures.append(
                    {
                        "name": fig_file.stem,
                        "path": f"figures/{fig_file.name}",
                        "caption": fig_file.stem.replace("-", " ").replace("_", " "),
                    }
                )
            elif fig_file.name.endswith(".vl.json"):
                vegalite_specs.append(
                    {
                        "name": fig_file.stem.removesuffix(".vl"),
                        "path": f"figures/{fig_file.name}",
                    }
                )

    # Copy prose
    prose_src = Path(config.get("prose_dir", "prose"))
    if prose_src.is_dir():
        for md_file in sorted(prose_src.glob("*.md")):
            shutil.copy2(md_file, prose_dir_out / md_file.name)

    # Extract code excerpts
    commit = _git_commit()
    repository = config.get("repository", "")
    code_excerpts = []
    for exc_config in config.get("code_excerpts", []):
        src_path = Path(exc_config["source"])
        if not src_path.is_file():
            continue
        lines = src_path.read_text(encoding="utf-8").splitlines()
        start, end = exc_config["lines"]
        excerpt_text = "\n".join(lines[start - 1 : end])
        exc_dest = excerpts_dir / src_path.name
        exc_dest.write_text(excerpt_text, encoding="utf-8")

        permalink = ""
        if repository and commit:
            permalink = f"{repository}/blob/{commit}/{exc_config['source']}#L{start}-L{end}"

        code_excerpts.append(
            {
                "name": exc_config.get("name", src_path.stem),
                "path": f"excerpts/{src_path.name}",
                "source": exc_config["source"],
                "lines": exc_config["lines"],
                "github_permalink": permalink,
            }
        )

    # Copy cells.json
    cells_src = Path(config.get("cells_file", "cells.json"))
    if cells_src.is_file():
        shutil.copy2(cells_src, output_dir / "cells.json")

    # Compute input hashes
    input_hashes = []
    for inp_path_str in config.get("inputs", []):
        inp_path = Path(inp_path_str)
        if inp_path.is_file():
            input_hashes.append({"path": inp_path_str, "sha256": _sha256_file(inp_path)})
        else:
            input_hashes.append({"path": inp_path_str, "sha256": ""})

    # Assemble descriptor
    lens = config.get("lens", "")
    section = config.get("section", "")
    descriptor = {
        "name": f"{lens}-{section}" if lens and section else config.get("workflow_name", "package"),
        "title": config.get("title", "Research Package"),
        "profile": "science-research-package",
        "version": "1.0.0",
        "resources": resources,
        "research": {
            "target_route": f"/guide/{lens}/{section}" if lens and section else None,
            "cells": "cells.json",
            "figures": figures,
            "vegalite_specs": vegalite_specs,
            "code_excerpts": code_excerpts,
            "provenance": {
                "workflow": config.get("workflow_name", ""),
                "config": str(config_path),
                "last_run": datetime.now(timezone.utc).isoformat(),
                "git_commit": commit,
                "repository": repository,
                "inputs": input_hashes,
                "scripts": config.get("scripts", []),
            },
        },
    }

    (output_dir / "datapackage.json").write_text(
        json.dumps(descriptor, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    result = validate_package(output_dir)
    return result.errors
