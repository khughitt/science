from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from science_model.audit import AuditReport

from science_tool.findings.catalog import registered_producers
from science_tool.findings.producers import build_registry


SRC = Path(__file__).resolve().parents[1] / "src" / "science_tool"


def _source_modules(namespace: str) -> list[str]:
    return [
        producer.source_module
        for producer in registered_producers()
        if producer.namespace == namespace
    ]


def test_every_registered_health_module_has_one_catalog_producer() -> None:
    modules = _source_modules("health_checks")
    expected = {
        f"graph/health_checks/{path.name}"
        for path in (SRC / "graph" / "health_checks").glob("*.py")
        if path.name not in {"__init__.py", "base.py"}
    }
    assert set(modules) == expected
    assert len(modules) == len(set(modules))


def test_every_registered_validation_module_contributes_a_producer() -> None:
    modules = _source_modules("validate_checks")
    expected = {
        f"validate/checks/{path.name}"
        for path in (SRC / "validate" / "checks").glob("*.py")
        if path.name != "__init__.py"
    }
    expected.add("validate/runtime.py")
    assert set(modules) == expected


def test_data_audit_file_contributes_its_one_producer() -> None:
    assert _source_modules("data_audit") == ["data_audit.py"]


def _called_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_every_namespace_execution_crosses_validate_producer_result() -> None:
    execution_surfaces = (
        SRC / "validate" / "runner.py",
        SRC / "graph" / "health.py",
        SRC / "data_cli.py",
    )
    assert {
        path.relative_to(SRC).as_posix()
        for path in execution_surfaces
        if "validate_producer_result" in _called_names(path)
    } == {
        "validate/runner.py",
        "graph/health.py",
        "data_cli.py",
    }


def _audit_report(
    *,
    caveats: list[dict[str, object]] | None = None,
    unwired: list[dict[str, object]] | None = None,
) -> AuditReport:
    return AuditReport.model_validate(
        {
            "schema_version": 2,
            "fingerprint_version": 1,
            "ingestion_ref": "health:test",
            "generated_at": "2026-07-28T12:00:00+00:00",
            "findings": [],
            "accepted": [],
            "metrics": {},
            "caveats": caveats or [],
            "unwired": unwired or [],
            "totals": {
                "findings_total": 0,
                "findings_by_severity": {},
                "accepted_total": 0,
                "unwired_total": len(unwired or []),
            },
            "meta": {
                "producers_run": ["wired"] if not unwired else [],
                "total_duration_seconds": 0.0,
                "timings": [],
            },
        }
    )


@dataclass
class _Console:
    values: list[str]

    def print(self, value: object = "") -> None:
        self.values.append(str(value))


@dataclass
class _Sink:
    values: list[str] = field(default_factory=list)

    @property
    def console(self) -> _Console:
        return _Console(self.values)

    def echo(self, value: object = "") -> None:
        self.values.append(str(value))


def _render(report: AuditReport) -> str:
    from science_tool.graph import health_cli

    renderer: Any = getattr(health_cli, "render_health_report", None)
    assert renderer is not None, "health must expose its AuditReport v2 renderer"
    sink = _Sink()
    registry = build_registry([], active_kinds=frozenset())
    renderer(report, registry=registry, sink=sink)
    return "\n".join(sink.values)


def test_renderer_never_calls_an_unwired_report_clean() -> None:
    rendered = _render(
        _audit_report(
            unwired=[
                {
                    "producer_id": "missing",
                    "code": "not-configured",
                    "reason": "required input is absent",
                }
            ]
        )
    )
    assert "Project is not clean: one or more diagnostics could not run." in rendered
    assert "Project is clean." not in rendered


def test_renderer_shows_a_wired_caveat_without_reclassifying_true_zero() -> None:
    rendered = _render(
        _audit_report(
            caveats=[
                {
                    "producer_id": "wired",
                    "code": "partial",
                    "reason": "one optional source was skipped",
                }
            ]
        )
    )
    assert "one optional source was skipped" in rendered
    assert "Project is clean." in rendered


def test_health_report_has_only_the_audit_report_v2_fields() -> None:
    assert set(AuditReport.model_fields) == {
        "schema_version",
        "fingerprint_version",
        "ingestion_ref",
        "generated_at",
        "findings",
        "accepted",
        "metrics",
        "caveats",
        "unwired",
        "totals",
        "meta",
    }


def test_retired_archive_lag_is_not_reintroduced() -> None:
    producers = registered_producers()
    producer_ids = {producer.producer_id for producer in producers}
    rule_ids = {
        rule.id
        for producer in producers
        for rule in producer.expanded_rules(frozenset())
    }
    assert "archive_lag" not in producer_ids
    assert "tasks.archive-lag" not in rule_ids
