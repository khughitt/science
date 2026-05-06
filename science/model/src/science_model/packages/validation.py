"""Validation for research package directories."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from science_model.packages.cells import _CELL_TYPE_MAP
from science_model.packages.schema import ResearchPackageDescriptor


@dataclass
class ValidationResult:
    """Structured validation output, serializable to JSON."""

    package_dir: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "package_dir": self.package_dir,
            "ok": self.ok,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def validate_package(package_dir: Path) -> ValidationResult:
    """Validate a research package directory."""
    result = ValidationResult(package_dir=str(package_dir))
    descriptor_path = package_dir / "datapackage.json"

    if not descriptor_path.is_file():
        result.errors.append(f"Missing datapackage.json in {package_dir}")
        return result

    try:
        raw = json.loads(descriptor_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        result.errors.append(f"Cannot read datapackage.json: {exc}")
        return result

    try:
        pkg = ResearchPackageDescriptor(**raw)
    except Exception as exc:
        result.errors.append(f"Invalid datapackage.json: {exc}")
        return result

    for resource in pkg.resources:
        if not (package_dir / resource.path).is_file():
            result.errors.append(f'Resource "{resource.name}" file missing: {resource.path}')

    for fig in pkg.research.figures:
        if not (package_dir / fig.path).is_file():
            result.errors.append(f'Figure "{fig.name}" file missing: {fig.path}')

    for spec in pkg.research.vegalite_specs:
        if not (package_dir / spec.path).is_file():
            result.errors.append(f'Vega-Lite spec "{spec.name}" file missing: {spec.path}')

    for exc in pkg.research.code_excerpts:
        if not (package_dir / exc.path).is_file():
            result.errors.append(f'Code excerpt "{exc.name}" file missing: {exc.path}')

    cells_path = package_dir / pkg.research.cells
    if not cells_path.is_file():
        result.errors.append(f"Missing cells file: {pkg.research.cells}")
        return result

    try:
        raw_cells = json.loads(cells_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc_inner:
        result.errors.append(f"Cannot read cells file: {exc_inner}")
        return result

    if not isinstance(raw_cells, list):
        result.errors.append("cells.json must be a JSON array")
        return result

    resource_names = {r.name for r in pkg.resources}
    figure_names = {f.name for f in pkg.research.figures}
    vegalite_names = {s.name for s in pkg.research.vegalite_specs}
    excerpt_names = {e.name for e in pkg.research.code_excerpts}

    for i, cell in enumerate(raw_cells):
        if not isinstance(cell, dict):
            result.errors.append(f"Cell {i}: not a dict")
            continue
        cell_type = cell.get("type")
        if cell_type not in _CELL_TYPE_MAP:
            result.errors.append(f"Cell {i}: unknown type '{cell_type}'")
            continue

        if cell_type == "narrative":
            content_path = cell.get("content", "")
            if not (package_dir / content_path).is_file():
                result.errors.append(f"Cell {i}: narrative content file missing: {content_path}")
        elif cell_type == "data-table":
            resource = cell.get("resource", "")
            if resource not in resource_names:
                result.errors.append(f"Cell {i}: references unknown resource '{resource}'")
        elif cell_type == "figure":
            ref = cell.get("ref", "")
            if ref not in figure_names:
                result.errors.append(f"Cell {i}: references unknown figure '{ref}'")
        elif cell_type == "vegalite":
            ref = cell.get("ref", "")
            if ref not in vegalite_names:
                result.errors.append(f"Cell {i}: references unknown vegalite spec '{ref}'")
        elif cell_type == "code-reference":
            excerpt = cell.get("excerpt", "")
            if excerpt not in excerpt_names:
                result.errors.append(f"Cell {i}: references unknown code excerpt '{excerpt}'")

    return result


def check_freshness(package_dir: Path, project_root: Path) -> ValidationResult:
    """Check provenance input freshness by comparing SHA-256 hashes."""
    result = ValidationResult(package_dir=str(package_dir))
    descriptor_path = package_dir / "datapackage.json"

    if not descriptor_path.is_file():
        result.errors.append(f"Missing datapackage.json in {package_dir}")
        return result

    try:
        raw = json.loads(descriptor_path.read_text(encoding="utf-8"))
        pkg = ResearchPackageDescriptor(**raw)
    except Exception as exc:
        result.errors.append(f"Cannot parse datapackage.json: {exc}")
        return result

    for inp in pkg.research.provenance.inputs:
        input_path = project_root / inp.path
        if not input_path.is_file():
            result.warnings.append(f"Input file not found (may have moved): {inp.path}")
            continue
        current_hash = hashlib.sha256(input_path.read_bytes()).hexdigest()
        if current_hash != inp.sha256:
            result.warnings.append(f'Input "{inp.path}" has changed since last workflow run (stale package)')

    return result
