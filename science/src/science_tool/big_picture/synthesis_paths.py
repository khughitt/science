"""Resolve where a hypothesis's synthesis entity lives.

`commands/big-picture.md` says these artifacts are identified "by ``report_kind``, not by
filename" -- but the per-hypothesis output path was still COMPOSED as
``entities/synthesis/<hyp-id>.md``. In a numbered-entity project those are different files.

mm30 and natural-systems both store synthesis as numbered canonical entities
(``0022-epigenetic-commitment.md``) bound to a hypothesis by frontmatter. Composing
``<hyp-id>.md`` would have created 29 NEW files beside the 15 existing ones -- duplicate
synthesis entities for the same hypotheses, with the rollup pointing at one set and the
graph at the other. Both projects built this map by hand before dispatching
(fb-2026-07-11-013, -002).

The scan mirrors ``digests.load_cluster_digests``, which already does exactly this for
``report_kind: cluster-digest``. The pattern existed; it was simply never applied here.
"""

from __future__ import annotations

from pathlib import Path

from science_tool.big_picture.frontmatter import read_frontmatter
from science_tool.big_picture.layout import entity_dir
from science_tool.consolidate import SYNTHESIS_KIND

HYPOTHESIS_SYNTHESIS_REPORT_KIND = "hypothesis-synthesis"


def resolve_synthesis_path(project_root: Path, hypothesis_id: str) -> Path:
    """Return the synthesis file for ``hypothesis_id``.

    An EXISTING ``report_kind: hypothesis-synthesis`` entity whose ``hypothesis:``
    frontmatter names this hypothesis wins, whatever its filename. Only when no such file
    exists do we fall back to ``<hyp-id>.md``.

    Partial coverage is a normal state, not an error: mm30's prior run had covered 15 of
    its 29 hypotheses, so the resolver must answer "no synthesis yet" for the other 14
    without complaint.
    """
    directory = entity_dir(project_root, SYNTHESIS_KIND)
    slug = hypothesis_id.partition(":")[2] or hypothesis_id

    if directory.is_dir():
        for path in sorted(directory.glob("*.md")):
            fm = read_frontmatter(path) or {}
            if fm.get("report_kind") != HYPOTHESIS_SYNTHESIS_REPORT_KIND:
                continue
            if fm.get("hypothesis") == hypothesis_id:
                return path

    return directory / f"{slug}.md"
