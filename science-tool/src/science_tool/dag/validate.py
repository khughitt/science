"""Comprehensive validation for the DAG YAML + .dot layer.

Composes existing Phase 1 shape + ref checks with cross-file topology,
acyclicity, posterior-sanity, and JSON-schema-conformance checks.
``--strict`` adds migration-completeness gates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

import yaml

from science_tool.dag.paths import DagPaths
from science_tool.dag.refs import RefResolutionError, validate_ref_entry
from science_tool.dag.schema import EdgesYamlFile, SchemaError

Severity = Literal["error", "strict_error"]


@dataclass(frozen=True)
class ValidationFinding:
    """One check-failure entry."""

    dag: str
    edge_id: int | None
    rule: str
    severity: Severity
    message: str
    location: str | None

    def to_json(self) -> dict:  # type: ignore[type-arg]
        return {
            "dag": self.dag,
            "edge_id": self.edge_id,
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "location": self.location,
        }


@dataclass(frozen=True)
class ValidationReport:
    """Result of a ``validate_project()`` invocation."""

    today: date
    strict: bool
    findings: tuple[ValidationFinding, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not any(self._blocks(f) for f in self.findings)

    def _blocks(self, f: ValidationFinding) -> bool:
        return f.severity == "error" or (self.strict and f.severity == "strict_error")

    def to_json(self) -> dict:  # type: ignore[type-arg]
        return {
            "today": self.today.isoformat(),
            "strict": self.strict,
            "ok": self.ok,
            "findings": [f.to_json() for f in self.findings],
        }


def _discover_edge_yaml_files(paths: DagPaths) -> list[Path]:
    """Return the list of <slug>.edges.yaml files to validate."""
    if paths.dags is not None:
        return [paths.dag_dir / f"{slug}.edges.yaml" for slug in paths.dags]
    return sorted(paths.dag_dir.glob("*.edges.yaml"))


def _check_shape_and_refs(
    yaml_path: Path, project_root: Path
) -> tuple[list[ValidationFinding], EdgesYamlFile | None]:
    """Run Pydantic shape validation and per-entry ref resolution.

    Returns (findings, parsed_model_or_None). If shape validation fails the
    model is None and ref checks are skipped.
    """
    findings: list[ValidationFinding] = []
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    try:
        model = EdgesYamlFile.model_validate(raw)
    except (SchemaError, ValueError) as exc:
        findings.append(
            ValidationFinding(
                dag=raw.get("dag", yaml_path.stem) if isinstance(raw, dict) else yaml_path.stem,
                edge_id=None,
                rule="shape",
                severity="error",
                message=str(exc),
                location=yaml_path.name,
            )
        )
        return findings, None

    for edge in model.edges:
        for ref_list_name in ("data_support", "lit_support", "eliminated_by"):
            entries = getattr(edge, ref_list_name, None) or []
            for entry in entries:
                try:
                    validate_ref_entry(entry, project_root)
                except RefResolutionError as exc:
                    findings.append(
                        ValidationFinding(
                            dag=model.dag,
                            edge_id=edge.id,
                            rule="refs",
                            severity="error",
                            message=str(exc),
                            location=yaml_path.name,
                        )
                    )
    return findings, model


def validate_project(
    paths: DagPaths,
    *,
    strict: bool = False,
    today: date | None = None,
) -> ValidationReport:
    """Validate every DAG YAML under ``paths.dag_dir``.

    Always-on checks (block exit 0): shape + refs.
    Subsequent tasks will add: posterior sanity, topology, acyclicity,
    jsonschema conformance. Strict-only checks come last.
    """
    if today is None:
        today = date.today()
    project_root = paths.dag_dir.parent.parent  # dag_dir := <root>/doc/figures/dags
    findings: list[ValidationFinding] = []

    for yaml_path in _discover_edge_yaml_files(paths):
        if not yaml_path.exists():
            findings.append(
                ValidationFinding(
                    dag=yaml_path.stem.removesuffix(".edges"),
                    edge_id=None,
                    rule="shape",
                    severity="error",
                    message=f"edges.yaml file not found: {yaml_path}",
                    location=yaml_path.name,
                )
            )
            continue

        f, _model = _check_shape_and_refs(yaml_path, project_root)
        findings.extend(f)

    return ValidationReport(today=today, strict=strict, findings=tuple(findings))
