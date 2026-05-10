from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from itertools import combinations

from science_tool.wander.context import ContextBundle
from science_tool.wander.stub_smell import StubSignals

BundleWithSignals = tuple[ContextBundle, StubSignals]


def render_markdown_skeleton(
    *,
    walk_id: str,
    walk_date: date,
    seed: int | None,
    n: int,
    bundles_with_signals: list[BundleWithSignals],
) -> str:
    sampled_ids = [b.entity_id for b, _ in bundles_with_signals]
    lines: list[str] = []
    lines.append("---")
    lines.append(f"date: {walk_date.isoformat()}")
    lines.append(f"walk_id: {walk_id}")
    lines.append(f"seed: {seed if seed is not None else 'null'}")
    lines.append(f"n: {n}")
    lines.append(f"sampled: [{', '.join(sampled_ids)}]")
    lines.append("---")
    lines.append("")
    lines.append(f"# Wander · {walk_date.isoformat()} ({walk_id})")
    lines.append("")
    lines.append("## Sample")
    lines.append("")
    lines.append("| ID | Kind | Weight | Last reviewed (days) |")
    lines.append("| --- | --- | --- | --- |")
    for bundle, _ in bundles_with_signals:
        days = bundle.components.get("days_since_last_review", "")
        lines.append(f"| {bundle.entity_id} | {bundle.kind} | {bundle.weight:.4f} | {days} |")
    lines.append("")
    lines.append("## Per-entity review")
    lines.append("")
    for bundle, signals in bundles_with_signals:
        lines.extend(_render_entity_block(bundle, signals))
        lines.append("")
    lines.append("## Pairwise connections")
    lines.append("")
    for left, right in combinations(bundles_with_signals, 2):
        lines.append(f"### {left[0].entity_id} ↔ {right[0].entity_id}")
        lines.append("")
        lines.append("_(agent: fill in — or note 'no obvious connection')_")
        lines.append("")
    lines.append("## Prune candidates")
    lines.append("")
    lines.append("_(agent: list flagged stubs from the per-entity review, or 'none')_")
    lines.append("")
    lines.append("## Spawned tasks")
    lines.append("")
    lines.append("_(populated only when --apply was passed)_")
    lines.append("")
    return "\n".join(lines)


def _render_entity_block(bundle: ContextBundle, signals: StubSignals) -> list[str]:
    out: list[str] = []
    out.append(f"### {bundle.entity_id} — {bundle.label}")
    out.append("")
    out.append("**Context:**")
    out.append(f"- kind: `{bundle.kind}`")
    out.append(f"- weight: {bundle.weight:.4f}")
    out.append(f"- freshness: `{bundle.freshness_state}`")
    if bundle.source_path:
        out.append(f"- source: `{bundle.source_path}`")
    if bundle.created_date:
        out.append(f"- created: {bundle.created_date.isoformat()}")
    if bundle.mtime:
        out.append(f"- mtime: {bundle.mtime.isoformat()}")
    if bundle.content_length is not None:
        out.append(f"- length: {bundle.content_length} chars")
    out.append(
        f"- bears_on (in/out): {len(bundle.neighbors.bears_on_incoming)}/{len(bundle.neighbors.bears_on_outgoing)}"
    )
    out.append(f"- active references: {', '.join(r.entity_id for r in bundle.active_references) or 'none'}")
    out.append("")
    out.append("**Stub-smell signals:**")
    out.append(f"- older_than_60_days: {signals.older_than_60_days}")
    out.append(f"- no_incoming_bears_on: {signals.no_incoming_bears_on}")
    out.append(f"- no_active_references: {signals.no_active_references}")
    out.append(f"- short_or_unchanged: {signals.short_or_unchanged}")
    out.append(f"- **is_stub_candidate: {signals.is_stub_candidate}**")
    out.append("")
    out.append("**Gaps:** _(agent: fill in — text/code/epistemic; or 'none surfaced')_")
    out.append("")
    return out


def render_json(
    *,
    walk_id: str,
    walk_date: date,
    seed: int | None,
    n: int,
    bundles_with_signals: list[BundleWithSignals],
) -> str:
    payload = {
        "walk_id": walk_id,
        "date": walk_date.isoformat(),
        "seed": seed,
        "n": n,
        "bundles": [_bundle_to_dict(b, s) for b, s in bundles_with_signals],
    }
    return json.dumps(payload, indent=2, sort_keys=True, default=str)


def _bundle_to_dict(bundle: ContextBundle, signals: StubSignals) -> dict:
    return {
        "entity_id": bundle.entity_id,
        "uri": bundle.uri,
        "kind": bundle.kind,
        "label": bundle.label,
        "freshness_state": bundle.freshness_state,
        "weight": bundle.weight,
        "components": dict(bundle.components),
        "source_path": bundle.source_path,
        "mtime": bundle.mtime.isoformat() if bundle.mtime else None,
        "content_length": bundle.content_length,
        "created_date": bundle.created_date.isoformat() if bundle.created_date else None,
        "neighbors": {
            "bears_on_incoming": list(bundle.neighbors.bears_on_incoming),
            "bears_on_outgoing": list(bundle.neighbors.bears_on_outgoing),
            "other_incoming": [asdict(e) for e in bundle.neighbors.other_incoming],
            "other_outgoing": [asdict(e) for e in bundle.neighbors.other_outgoing],
        },
        "active_references": [asdict(r) for r in bundle.active_references],
        "stub_signals": {
            "older_than_60_days": signals.older_than_60_days,
            "no_incoming_bears_on": signals.no_incoming_bears_on,
            "no_active_references": signals.no_active_references,
            "short_or_unchanged": signals.short_or_unchanged,
            "is_stub_candidate": signals.is_stub_candidate,
        },
    }
