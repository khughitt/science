"""Filesystem equality guards for every registered producer namespace."""

from __future__ import annotations

from pathlib import Path

from science_tool.findings.producers import PRODUCER_NAMESPACES

SRC = Path(__file__).resolve().parents[1] / "src" / "science_tool"

#: Where each namespace's producer modules live, relative to `science_tool/`.
NAMESPACE_DIRS: dict[str, str] = {
    "health_checks": "graph/health_checks",
    "validate_checks": "validate/checks",
    "data_audit": "data_audit.py",
}


def test_every_namespace_declares_where_its_producers_live():
    missing = set(PRODUCER_NAMESPACES) - set(NAMESPACE_DIRS)
    assert not missing, (
        f"namespaces without a declared producer scope: {sorted(missing)}. "
        "A namespace whose scope is undefined cannot be guarded for completeness."
    )


def test_no_namespace_is_declared_without_being_registered():
    extra = set(NAMESPACE_DIRS) - set(PRODUCER_NAMESPACES)
    assert not extra, f"scope declared for unregistered namespaces: {sorted(extra)}"


def _registered_source_modules(namespace: str) -> set[str]:
    from science_tool.findings.catalog import registered_producers

    return {
        producer.source_module
        for producer in registered_producers()
        if producer.namespace == namespace
    }


def test_health_namespace_equals_filesystem() -> None:
    directory = SRC / "graph" / "health_checks"
    discovered = {
        f"graph/health_checks/{path.name}"
        for path in directory.glob("*.py")
        if path.name not in {"__init__.py", "base.py"}
    }
    assert _registered_source_modules("health_checks") == discovered


def test_validation_namespace_equals_filesystem() -> None:
    directory = SRC / "validate" / "checks"
    discovered = {
        f"validate/checks/{path.name}"
        for path in directory.glob("*.py")
        if path.name != "__init__.py"
    }
    discovered.add("validate/runtime.py")
    assert _registered_source_modules("validate_checks") == discovered


def test_data_audit_namespace_equals_filesystem() -> None:
    assert _registered_source_modules("data_audit") == {"data_audit.py"}
