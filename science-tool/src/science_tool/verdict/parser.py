"""Markdown verdict frontmatter parser."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any
import re

import yaml

from science_tool.verdict.models import Claim, Context, ParseResult, VerdictBlock
from science_tool.verdict.registry import IndexedClaimRegistry
from science_tool.verdict.rules import aggregate_composite, rule_disagrees_with_body
from science_tool.verdict.tokens import Token, parse_body_verdict


_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)


class NoVerdictBlockError(ValueError):
    """Raised when markdown frontmatter exists but lacks a `verdict:` block."""


def parse_file(path: Path | str, *, registry: IndexedClaimRegistry | None = None) -> ParseResult:
    """Hydrate a parse result from markdown frontmatter and body verdict prose."""
    file_path = Path(path)
    frontmatter, body = _split_frontmatter(file_path, file_path.read_text(encoding="utf-8"))
    try:
        meta = yaml.safe_load(frontmatter) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"{file_path}: malformed frontmatter") from exc
    if not isinstance(meta, Mapping):
        raise ValueError(f"{file_path}: frontmatter must be a mapping")

    if "verdict" not in meta:
        raise NoVerdictBlockError(f"{file_path}: frontmatter has no 'verdict:' block")

    raw_verdict = meta["verdict"]
    if not isinstance(raw_verdict, Mapping):
        raise ValueError(f"{file_path}: verdict block must be a mapping")

    verdict = _hydrate_verdict(raw_verdict)
    interpretation_id = str(meta.get("id") or f"unknown:{file_path.stem}")

    warnings: list[str] = []
    body_verdict = parse_body_verdict(body)
    if body_verdict is None:
        composite_token = verdict.composite
        composite_clause = ""
        warnings.append(f"{file_path}: missing body verdict; using frontmatter composite")
    else:
        composite_token, composite_clause = body_verdict

    if verdict.rule == "reframed" and verdict.reframing_target is None:
        warnings.append(f"{file_path}: reframed verdict is missing reframing_target")
    if verdict.rule == "non-adjudicating" and verdict.closure_terminal is None:
        warnings.append(f"{file_path}: non-adjudicating verdict is missing closure_terminal")

    unresolved_claim_ids: list[str] = []
    if registry is not None:
        unresolved_claim_ids = [claim.id for claim in verdict.claims if registry.resolve(claim.id) is None]
        if unresolved_claim_ids:
            unresolved = ", ".join(unresolved_claim_ids)
            warnings.append(f"{file_path}: unresolved claim IDs: {unresolved}")

    rule_derived_composite = aggregate_composite(verdict.rule, verdict.claims)
    disagrees = rule_disagrees_with_body(rule_derived_composite, composite_token)

    return ParseResult(
        interpretation_id=interpretation_id,
        composite_token=composite_token,
        composite_clause=composite_clause,
        rule=verdict.rule,
        rule_derived_composite=rule_derived_composite,
        rule_disagrees_with_body=disagrees,
        closure_terminal=verdict.closure_terminal,
        reframing_target=verdict.reframing_target,
        reframing_reason=verdict.reframing_reason,
        claims=verdict.claims,
        unresolved_claim_ids=unresolved_claim_ids,
        validation_warnings=warnings,
    )


def _split_frontmatter(path: Path, content: str) -> tuple[str, str]:
    match = _FRONTMATTER_RE.match(content)
    if match is None:
        raise ValueError(f"{path}: missing frontmatter")
    return match.group(1), match.group(2)


def _hydrate_verdict(raw: Mapping[str, Any]) -> VerdictBlock:
    composite = Token.from_str(_required_str(raw, "composite", "verdict block"))
    rule = _required_str(raw, "rule", "verdict block")
    claims = _hydrate_claims(raw.get("claims", []))
    return VerdictBlock(
        composite=composite,
        rule=rule,
        claims=claims,
        closure_terminal=_optional_str(raw, "closure_terminal", "verdict block"),
        reframing_target=_optional_str(raw, "reframing_target", "verdict block"),
        reframing_reason=_optional_str(raw, "reframing_reason", "verdict block"),
    )


def _hydrate_claims(raw_claims: Any) -> list[Claim]:
    if raw_claims is None:
        return []
    if not isinstance(raw_claims, list):
        raise ValueError("Malformed verdict block: claims must be a list")
    return [_hydrate_claim(raw_claim) for raw_claim in raw_claims]


def _hydrate_claim(raw: Any) -> Claim:
    if not isinstance(raw, Mapping):
        raise ValueError("Malformed verdict block: each claim must be a mapping")
    claim_id = _required_str(raw, "id", "claim")
    polarity = Token.from_str(_required_str(raw, "polarity", "claim"))
    return Claim(
        id=claim_id,
        polarity=polarity,
        strength=_optional_str(raw, "strength", "claim"),
        weight=_optional_float(raw, "weight", 1.0),
        evidence_summary=_optional_str(raw, "evidence_summary", "claim") or "",
        contexts=_hydrate_contexts(raw.get("contexts", [])),
        members=_string_list(raw.get("members", []), "members", "claim"),
    )


def _hydrate_contexts(raw_contexts: Any) -> list[Context]:
    if raw_contexts is None:
        return []
    if not isinstance(raw_contexts, list):
        raise ValueError("Malformed verdict block: contexts must be a list")

    contexts: list[Context] = []
    for raw_context in raw_contexts:
        if not isinstance(raw_context, Mapping):
            raise ValueError("Malformed verdict block: each context must be a mapping")
        contexts.append(
            Context(
                context=_required_str(raw_context, "context", "context"),
                polarity=Token.from_str(_required_str(raw_context, "polarity", "context")),
                strength=_optional_str(raw_context, "strength", "context"),
            )
        )
    return contexts


def _required_str(raw: Mapping[str, Any], field_name: str, block_name: str) -> str:
    value = raw.get(field_name)
    if not isinstance(value, str):
        raise ValueError(f"Malformed verdict block: {block_name} {field_name!r} is required")
    return value


def _optional_str(raw: Mapping[str, Any], field_name: str, block_name: str) -> str | None:
    value = raw.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Malformed verdict block: {block_name} {field_name!r} must be a string")
    return value


def _optional_float(raw: Mapping[str, Any], field_name: str, default: float) -> float:
    value = raw.get(field_name, default)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"Malformed verdict block: claim {field_name!r} must be numeric")
    return float(value)


def _string_list(value: Any, field_name: str, block_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"Malformed verdict block: {block_name} {field_name!r} must be a list of strings")
    return value
