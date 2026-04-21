"""Click commands for verdict parsing and rollups."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Any, cast

import click
from rich.console import Console
from rich.table import Table

from science_tool.verdict.models import ParseResult
from science_tool.verdict.parser import parse_file
from science_tool.verdict.registry import IndexedClaimRegistry, load_registry
from science_tool.verdict.rollup import Scope, group_by, tally_polarities, walk_interpretations
from science_tool.verdict.tokens import Token


_MAX_ANCESTOR_REGISTRY_LEVELS = 5


@click.group("verdict")
def verdict_group() -> None:
    """Parse and roll up verdict interpretation frontmatter."""


@verdict_group.command("parse")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--registry",
    "registry_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to a claim registry YAML file.",
)
def parse_cmd(file: Path, registry_path: Path | None) -> None:
    """Emit JSON for one parsed verdict interpretation."""
    registry = _load_registry_for_parse(file, registry_path)
    result = _parse_single_file(file, registry=registry)
    _handle_warnings(result.validation_warnings, result.unresolved_claim_ids, strict=False)
    _emit_json(_normalize(result))


@verdict_group.command("rollup")
@click.option(
    "--scope",
    type=click.Choice(["all", "claim"]),
    default=None,
    help="Rollup scope.",
)
@click.option(
    "--by-claim",
    is_flag=True,
    help="Alias for --scope claim.",
)
@click.option(
    "--root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path.cwd,
    show_default=True,
    help="Directory containing verdict interpretation markdown files.",
)
@click.option(
    "--registry",
    "registry_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to a claim registry YAML file.",
)
@click.option(
    "--output",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--strict",
    is_flag=True,
    help="Treat unresolved claim IDs as errors.",
)
def rollup_cmd(
    scope: str | None,
    by_claim: bool,
    root: Path,
    registry_path: Path | None,
    output_format: str,
    strict: bool,
) -> None:
    """Roll up parsed verdict interpretations by scope."""
    resolved_scope = _resolve_scope(scope, by_claim)
    registry = _load_registry_for_rollup(root, registry_path)
    if resolved_scope == "claim" and registry is None:
        raise click.ClickException("Claim-scope rollup requires a claim registry")

    results = _walk_results(root, registry=registry)
    unresolved_claim_ids = _unresolved_claim_ids(results)
    warnings = [warning for result in results for warning in result.validation_warnings]
    _handle_warnings(warnings, unresolved_claim_ids, strict=strict)

    groups = group_by(results, scope=resolved_scope, registry=registry)
    payload = _rollup_payload(resolved_scope, results, groups)
    if output_format == "json":
        _emit_json(payload)
        return

    _emit_rollup_table(payload["groups"])


def _load_registry_for_parse(file: Path, registry_path: Path | None) -> IndexedClaimRegistry | None:
    path = registry_path or _discover_ancestor_registry(file)
    if path is None:
        return None
    return _load_registry(path)


def _load_registry_for_rollup(root: Path, registry_path: Path | None) -> IndexedClaimRegistry | None:
    path = registry_path
    if path is None:
        candidate = root / "specs" / "claim-registry.yaml"
        path = candidate if candidate.is_file() else None
    if path is None:
        return None
    return _load_registry(path)


def _load_registry(path: Path) -> IndexedClaimRegistry:
    try:
        return load_registry(path)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


def _discover_ancestor_registry(path: Path) -> Path | None:
    current = path.parent
    for _ in range(_MAX_ANCESTOR_REGISTRY_LEVELS + 1):
        candidate = current / "specs" / "claim-registry.yaml"
        if candidate.is_file():
            return candidate
        if current.parent == current:
            return None
        current = current.parent
    return None


def _parse_single_file(path: Path, *, registry: IndexedClaimRegistry | None) -> ParseResult:
    try:
        return parse_file(path, registry=registry)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


def _walk_results(root: Path, *, registry: IndexedClaimRegistry | None) -> list[ParseResult]:
    try:
        return list(walk_interpretations(root, registry=registry))
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


def _resolve_scope(scope: str | None, by_claim: bool) -> Scope:
    if by_claim and scope == "all":
        raise click.ClickException("--by-claim cannot be combined with --scope all")
    if by_claim:
        return "claim"
    return cast(Scope, scope or "all")


def _handle_warnings(warnings: list[str], unresolved_claim_ids: list[str], *, strict: bool) -> None:
    if strict and unresolved_claim_ids:
        raise click.ClickException(f"Unresolved claim IDs: {', '.join(unresolved_claim_ids)}")

    for warning in warnings:
        click.echo(f"Warning: {warning}", err=True)


def _unresolved_claim_ids(results: list[ParseResult]) -> list[str]:
    unresolved: list[str] = []
    seen: set[str] = set()
    for result in results:
        for claim_id in result.unresolved_claim_ids:
            if claim_id in seen:
                continue
            seen.add(claim_id)
            unresolved.append(claim_id)
    return unresolved


def _rollup_payload(scope: Scope, results: list[ParseResult], groups: dict[str, list[ParseResult]]) -> dict[str, Any]:
    return {
        "scope": scope,
        "n_documents": len(results),
        "groups": {
            group_id: {
                "n": len(results),
                "tally": _token_tally(tally_polarities(results)),
                "documents": [result.interpretation_id for result in results],
            }
            for group_id, results in groups.items()
        },
    }


def _token_tally(tally: dict[Token, int]) -> dict[str, int]:
    return {token.value: tally.get(token, 0) for token in Token}


def _emit_json(payload: Any) -> None:
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _emit_rollup_table(groups: dict[str, Any]) -> None:
    table = Table()
    table.add_column("Group")
    table.add_column("n", justify="right")
    for token in Token:
        table.add_column(token.value, justify="right")

    for group_id, group_payload in groups.items():
        tally = group_payload["tally"]
        table.add_row(
            group_id,
            str(group_payload["n"]),
            *(str(tally[token.value]) for token in Token),
        )

    console = Console(file=click.get_text_stream("stdout"), force_terminal=False, color_system=None)
    console.print(table)


def _normalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return _normalize(asdict(value))
    if isinstance(value, dict):
        return {_normalize(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_normalize(item) for item in value]
    return value
