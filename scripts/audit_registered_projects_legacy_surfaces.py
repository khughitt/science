#!/usr/bin/env python3
"""Inventory legacy Science surfaces across registered downstream projects."""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click

SCRIPT_DIR = Path(__file__).resolve().parent
SCIENCE_REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(SCIENCE_REPO_ROOT / "science" / "src") not in sys.path:
    sys.path.insert(0, str(SCIENCE_REPO_ROOT / "science" / "src"))

from audit_downstream_project_inventory import (  # noqa: E402
    LEGACY_SCAN_EXCLUDED_DIRS,
    LegacySurfaceScan,
    scan_legacy_surfaces,
)
from science_tool.registry.config import get_default_config_path, load_global_config  # noqa: E402

DEFAULT_MARKDOWN_OUTPUT = SCIENCE_REPO_ROOT / "docs" / "audits" / "legacy-support-scrub-inventory-2026-07-04.md"
DEFAULT_JSON_OUTPUT = DEFAULT_MARKDOWN_OUTPUT.with_suffix(".json")


@dataclass(frozen=True)
class RegisteredLegacyReport:
    generated_at_utc: str
    config_path: str
    summary: dict[str, int]
    projects: tuple[LegacySurfaceScan, ...]
    surface_totals: dict[str, int]
    skipped_registered_projects: tuple[dict[str, str], ...]
    unregistered_science_yaml: tuple[dict[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "legacy-surfaces-v1",
            "generated_at_utc": self.generated_at_utc,
            "config_path": _display_path(self.config_path),
            "summary": self.summary,
            "surface_totals": self.surface_totals,
            "projects": [_project_to_display_dict(project) for project in self.projects],
            "skipped_registered_projects": [
                {
                    "path": _display_path(entry["path"]),
                    "reason": entry["reason"],
                }
                for entry in self.skipped_registered_projects
            ],
            "unregistered_science_yaml": [
                {
                    "path": _display_path(entry["path"]),
                    "science_yaml": _display_path(entry["science_yaml"]),
                }
                for entry in self.unregistered_science_yaml
            ],
        }


def _safe_resolve(path: Path) -> Path:
    try:
        return path.expanduser().resolve()
    except (OSError, RuntimeError):
        return path.expanduser().absolute()


def _display_path(path: str | Path) -> str:
    raw = Path(path).expanduser()
    text = raw.as_posix()
    home = Path.home().as_posix()
    if text == home:
        return "~"
    if text.startswith(home + "/"):
        return "~/" + text[len(home) + 1 :]
    synced_root = (Path.home() / "d").resolve().as_posix()
    if text == synced_root:
        return "~/d"
    if text.startswith(synced_root + "/"):
        return "~/d/" + text[len(synced_root) + 1 :]
    home_d = (Path.home() / "d").as_posix()
    if text == home_d:
        return "~/d"
    if text.startswith(home_d + "/"):
        return "~/d/" + text[len(home_d) + 1 :]
    return text


def _is_fixture_project(path: Path) -> bool:
    parts = set(path.parts)
    return "tests" in parts or "fixtures" in parts


def _project_to_display_dict(project: LegacySurfaceScan) -> dict[str, Any]:
    data = project.to_dict()
    data["project_root"] = _display_path(data["project_root"])
    return data


def _registered_project_paths(config_path: Path) -> tuple[list[Path], int]:
    cfg = load_global_config(config_path)
    unique: dict[Path, Path] = {}
    duplicates = 0
    for project in cfg.projects:
        raw = Path(project.path)
        resolved = _safe_resolve(raw)
        if resolved in unique:
            duplicates += 1
            continue
        unique[resolved] = raw
    return sorted(unique.keys()), duplicates


def _default_search_roots(registered_paths: Iterable[Path]) -> list[Path]:
    roots = {path.parent for path in registered_paths}
    return sorted(roots)


def _iter_science_yaml(search_root: Path) -> Iterable[Path]:
    search_root = _safe_resolve(search_root)
    if not search_root.exists():
        return
    for root, dirnames, filenames in _walk_search_root(search_root):
        if "science.yaml" in filenames:
            yield root / "science.yaml"


def _walk_search_root(search_root: Path) -> Iterable[tuple[Path, list[str], list[str]]]:
    for root, dirnames, filenames in os.walk(search_root):
        dirnames[:] = sorted(dirname for dirname in dirnames if dirname not in LEGACY_SCAN_EXCLUDED_DIRS)
        yield Path(root), dirnames, sorted(filenames)


def find_unregistered_science_yaml(
    *,
    search_roots: Iterable[Path],
    registered_paths: Iterable[Path],
) -> tuple[dict[str, str], ...]:
    registered = {_safe_resolve(path) for path in registered_paths}
    findings: list[dict[str, str]] = []
    seen: set[Path] = set()
    for root in search_roots:
        for science_yaml in _iter_science_yaml(root):
            project_root = _safe_resolve(science_yaml.parent)
            if project_root in registered or project_root in seen:
                continue
            if _is_fixture_project(project_root):
                continue
            seen.add(project_root)
            findings.append(
                {
                    "path": str(project_root),
                    "science_yaml": str(science_yaml),
                }
            )
    return tuple(sorted(findings, key=lambda entry: entry["path"]))


def scan_registered_projects(
    *,
    config_path: Path | None = None,
    search_roots: Iterable[Path] | None = None,
) -> RegisteredLegacyReport:
    config_path = _safe_resolve(config_path or get_default_config_path())
    cfg = load_global_config(config_path)
    registered_paths, duplicates = _registered_project_paths(config_path)

    projects: list[LegacySurfaceScan] = []
    skipped_registered_projects: list[dict[str, str]] = []
    for project_root in registered_paths:
        if not project_root.is_dir() or not (project_root / "science.yaml").is_file():
            skipped_registered_projects.append(
                {
                    "path": str(project_root),
                    "reason": ("missing directory" if not project_root.is_dir() else "missing science.yaml"),
                }
            )
            continue
        projects.append(scan_legacy_surfaces(project_root))

    totals: Counter[str] = Counter()
    for project in projects:
        totals.update(project.counts_by_surface())

    roots = list(search_roots) if search_roots is not None else _default_search_roots(registered_paths)
    unregistered = find_unregistered_science_yaml(
        search_roots=roots,
        registered_paths=registered_paths,
    )

    summary = {
        "registered_entries": len(cfg.projects),
        "unique_registered_paths": len(registered_paths),
        "duplicate_registered_entries": duplicates,
        "scanned_projects": len(projects),
        "skipped_registered_projects": len(skipped_registered_projects),
        "unregistered_science_yaml": len(unregistered),
        "total_findings": sum(totals.values()),
    }
    return RegisteredLegacyReport(
        generated_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        config_path=str(config_path),
        summary=summary,
        projects=tuple(projects),
        surface_totals=dict(sorted(totals.items())),
        skipped_registered_projects=tuple(sorted(skipped_registered_projects, key=lambda entry: entry["path"])),
        unregistered_science_yaml=unregistered,
    )


def render_markdown(report: RegisteredLegacyReport) -> str:
    out: list[str] = [
        "# Legacy Support Scrub Inventory",
        "",
        f"Generated at: `{report.generated_at_utc}`",
        f"Config path: `{_display_path(report.config_path)}`",
        "",
        "## Summary",
        "",
        "| metric | count |",
        "| --- | ---: |",
    ]
    for key, value in report.summary.items():
        out.append(f"| `{key}` | {value} |")
    out.extend(["", "## Surface Totals", ""])
    if report.surface_totals:
        out.extend(["| surface | findings |", "| --- | ---: |"])
        for surface, count in report.surface_totals.items():
            out.append(f"| `{surface}` | {count} |")
    else:
        out.append("_No legacy surface findings._")
    out.extend(["", "## Projects", ""])
    out.extend(["| project | findings | surfaces |", "| --- | ---: | --- |"])
    for project in sorted(report.projects, key=lambda item: item.project_root):
        counts = project.counts_by_surface()
        surfaces = ", ".join(f"`{surface}`={count}" for surface, count in counts.items())
        out.append(f"| `{_display_path(project.project_root)}` | {sum(counts.values())} | {surfaces} |")

    out.extend(["", "## Findings", ""])
    if any(project.findings for project in report.projects):
        out.extend(["| project | surface | path | detail |", "| --- | --- | --- | --- |"])
        for project in sorted(report.projects, key=lambda item: item.project_root):
            for finding in project.findings:
                out.append(
                    f"| `{_display_path(project.project_root)}` | `{finding.surface}` | `{finding.path}` | {finding.detail} |"
                )
    else:
        out.append("_No per-project findings._")

    out.extend(["", "## Skipped Registered Projects", ""])
    if report.skipped_registered_projects:
        out.extend(["| project root | reason |", "| --- | --- |"])
        for entry in report.skipped_registered_projects:
            out.append(f"| `{_display_path(entry['path'])}` | {entry['reason']} |")
    else:
        out.append("_No registered projects skipped._")

    out.extend(["", "## Coverage Sweep", ""])
    if report.unregistered_science_yaml:
        out.extend(["| project root | science.yaml |", "| --- | --- |"])
        for entry in report.unregistered_science_yaml:
            out.append(f"| `{_display_path(entry['path'])}` | `{_display_path(entry['science_yaml'])}` |")
    else:
        out.append("_No unregistered `science.yaml` files found in search roots._")
    out.append("")
    return "\n".join(out)


@click.command()
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="Science global config path. Defaults to ~/.config/science/config.yaml.",
)
@click.option(
    "--search-root",
    "search_roots",
    type=click.Path(path_type=Path, file_okay=False),
    multiple=True,
    help="Root to sweep for unregistered science.yaml files. Repeatable.",
)
@click.option(
    "--output",
    "markdown_output",
    type=click.Path(path_type=Path, dir_okay=False),
    default=DEFAULT_MARKDOWN_OUTPUT,
    show_default=True,
    help="Markdown report path.",
)
@click.option(
    "--json-output",
    type=click.Path(path_type=Path, dir_okay=False),
    default=DEFAULT_JSON_OUTPUT,
    show_default=True,
    help="JSON report path.",
)
def main(
    config_path: Path | None,
    search_roots: tuple[Path, ...],
    markdown_output: Path,
    json_output: Path,
) -> None:
    report = scan_registered_projects(
        config_path=config_path,
        search_roots=search_roots or None,
    )
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(render_markdown(report), encoding="utf-8")
    json_output.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    click.echo(f"Wrote {markdown_output}")
    click.echo(f"Wrote {json_output}")


if __name__ == "__main__":
    main()
