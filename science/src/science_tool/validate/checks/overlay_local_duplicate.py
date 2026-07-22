"""Conformance check: an id held BOTH as a local owner and as an overlay.

A project that carries ``entities/<type>/<slug>.md`` (a local owner) AND
``overlays/<type>/<slug>.md`` (an overlay of the same id) has a genuine
duplicate. The overlay is the correct form — it defers to the commons canonical
and carries only project-specific content — and the local owner shadows it.

This is what fb-2026-07-11-019 reported: a paper already consumed from commons
via an overlay was re-intaked as a fresh local entity because the dedup pass
looked at ``entities/`` + ``references.bib`` but never at ``overlays/``. The
duplicate went unnoticed until ``commons promote`` failed with a late "overlay
target collision". ``science validate`` should flag it early.

Unlike `commons_owner_collision`, this needs no commons store: holding both
files for one id is a purely LOCAL fact, and the remedy is unambiguous — delete
the local owner, keep the overlay (converting the local owner into a *second*
overlay would only collide). `commons_owner_collision` defers to this check when
an overlay is present so the two never disagree on the fix.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.entity_scan import iter_entity_markdown
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

RULE = "commons.overlay-local-duplicate"


def _ids_under(ctx: ValidateContext, subdir: str) -> dict[str, str]:
    """Map canonical id -> project-relative path for every markdown under `subdir`.

    First path wins for a repeated id (a same-id duplicate WITHIN one root is
    `identity_collision`'s concern, not this check's).
    """
    root = ctx.project_root / subdir
    if not root.is_dir():
        return {}
    ids: dict[str, str] = {}
    for path in iter_entity_markdown(root):
        canonical_id = ctx.frontmatter(path).get("id")
        if not isinstance(canonical_id, str) or ":" not in canonical_id:
            continue
        rel = path.relative_to(ctx.project_root).as_posix()
        ids.setdefault(canonical_id, rel)
    return ids


@Check(section="overlay/local duplicate (id held as both a local owner and an overlay)", order=1)
def check_overlay_local_duplicate(ctx: ValidateContext) -> Iterator[Result]:
    overlay_ids = _ids_under(ctx, "overlays")
    if not overlay_ids:
        return
    local_ids = _ids_under(ctx, "entities")
    for canonical_id, local_path in sorted(local_ids.items()):
        overlay_path = overlay_ids.get(canonical_id)
        if overlay_path is None:
            continue
        yield Result(
            Severity.ERROR,
            Path(local_path),
            None,
            (
                f"{canonical_id}: held both as a local owner ({local_path}) and as an "
                f"overlay ({overlay_path}). This is always a duplicate — the overlay is "
                f"the correct form. Delete the local entity {local_path}; keeping it "
                f"shadows the overlay, and converting it to a second overlay would collide."
            ),
            RULE,
            None,
        )
