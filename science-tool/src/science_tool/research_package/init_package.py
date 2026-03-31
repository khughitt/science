"""Scaffold a new research package directory."""

from __future__ import annotations

import json
import re
from pathlib import Path


def _read_workflow_config(workflow_dir: Path) -> dict:
    """Read config.yaml from a workflow directory using simple regex parsing."""
    config_path = workflow_dir / "config.yaml"
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

    return result


def init_research_package(
    name: str,
    title: str,
    output_dir: Path,
    *,
    workflow_dir: Path | None = None,
) -> Path:
    """Scaffold a research package directory with empty structure."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "data").mkdir(exist_ok=True)
    (output_dir / "figures").mkdir(exist_ok=True)
    (output_dir / "prose").mkdir(exist_ok=True)
    (output_dir / "excerpts").mkdir(exist_ok=True)

    config: dict = {}
    if workflow_dir:
        config = _read_workflow_config(workflow_dir)

    provenance = {
        "workflow": str(workflow_dir / "Snakefile") if workflow_dir else "",
        "config": str(workflow_dir / "config.yaml") if workflow_dir else "",
        "last_run": "",
        "git_commit": "",
        "repository": config.get("repository", ""),
        "inputs": [{"path": p, "sha256": ""} for p in config.get("inputs", [])],
        "scripts": config.get("scripts", []),
    }

    descriptor = {
        "name": name,
        "title": title,
        "profile": "science-research-package",
        "version": "1.0.0",
        "resources": [],
        "research": {
            "cells": "cells.json",
            "figures": [],
            "vegalite_specs": [],
            "code_excerpts": [],
            "provenance": provenance,
        },
    }

    (output_dir / "datapackage.json").write_text(
        json.dumps(descriptor, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / "cells.json").write_text("[]\n", encoding="utf-8")

    return output_dir
