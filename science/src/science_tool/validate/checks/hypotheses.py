"""Port of validate.sh "Checking hypotheses..." and review horizon blocks.

Checks hypothesis files under both ``entities/hypotheses/`` (new layout)
and the legacy ``$SPECS_DIR/hypotheses/`` root for Falsifiability and Status,
then scans ``$DOC_DIR`` and ``$SPECS_DIR`` markdown
frontmatter for non-positive review horizons.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml
from science_model.entity_schema.resolution import check_resolution

from science_tool.entity_scan import iter_entity_markdown
from science_tool.graph.identity_table import build_identity_table
from science_tool.graph.reference_resolution import ReferenceResolver
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_STATUS_RE = re.compile(r"^status:")
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def _result(severity: Severity, path: str | None, message: str) -> Result:
    return Result(severity, Path(path) if path is not None else None, None, message, "hypotheses", None)


@Check(section="hypotheses...", order=5)
def check_hypotheses(ctx: ValidateContext) -> Iterator[Result]:
    roots = (ctx.project_root / "entities" / "hypotheses",)
    for target in roots:
        if not target.is_dir():
            continue
        for path in sorted(target.glob("*.md")):  # *.md covers legacy h-prefixed and new numeric names
            if path.is_file():
                yield from _check_hypothesis(ctx, path)

    yield from _check_review_horizon_days(ctx)


def _check_hypothesis(ctx: ValidateContext, path: Path) -> Iterator[Result]:
    relative = path.relative_to(ctx.project_root).as_posix()
    text = ctx.read_text_cached(path)
    lines = text.splitlines()

    yield _result(Severity.INFO, relative, f"Checking {relative}...")

    if not _has_falsifiability_heading(lines):
        yield _result(Severity.ERROR, relative, f"{relative} missing ## Falsifiability section")
    elif _is_falsifiability_empty(lines):
        yield _result(Severity.WARN, relative, f"{relative} has empty Falsifiability section")

    try:
        frontmatter = ctx.frontmatter(path)
    except yaml.YAMLError:
        frontmatter = {}
    if not _has_status(frontmatter, lines):
        yield _result(Severity.WARN, relative, f"{relative} missing Status field")



def _has_falsifiability_heading(lines: list[str]) -> bool:
    return any(line == "## Falsifiability" for line in _non_fenced_lines(lines))


def _is_falsifiability_empty(lines: list[str]) -> bool:
    in_section = False
    in_html_comment = False
    for line in _non_fenced_lines(lines):
        if not in_section:
            if line == "## Falsifiability":
                in_section = True
            continue

        if line.startswith("## "):
            return True
        stripped = line.strip()

        if in_html_comment:
            if "-->" in stripped:
                in_html_comment = False
            continue
        if stripped.startswith("<!--"):
            if "-->" not in stripped:
                in_html_comment = True
            continue
        if stripped == "" or stripped.startswith("#"):
            continue
        return False

    return True


def _non_fenced_lines(lines: list[str]) -> Iterator[str]:
    fence_char: str | None = None
    for line in lines:
        match = _FENCE_RE.match(line)
        if match is not None:
            marker = match.group(1)
            char = marker[0]
            if fence_char is None:
                fence_char = char
                continue
            if char == fence_char:
                fence_char = None
                continue
        if fence_char is not None:
            continue
        yield line


def _has_status(frontmatter: dict[str, Any], lines: list[str]) -> bool:
    return "status" in frontmatter or any(line.startswith("- **Status:**") or _STATUS_RE.match(line) for line in lines)




def _check_review_horizon_days(ctx: ValidateContext) -> Iterator[Result]:
    # review_state lives only on epistemic entities, which the Plan 3 cutover
    # relocated to entities/. Scan there (the legacy doc/specs roots are gone).
    for root in (ctx.project_root / "entities",):
        if not root.is_dir():
            continue
        for path in iter_entity_markdown(root):
            if not path.is_file():
                continue
            try:
                frontmatter = ctx.frontmatter(path)
            except yaml.YAMLError:
                continue

            horizon = _review_horizon_days(frontmatter)
            if horizon is None or horizon > 0:
                continue

            relative = path.relative_to(ctx.project_root).as_posix()
            yield _result(
                Severity.WARN,
                relative,
                f"{relative}: review_state.review_horizon_days must be positive (got {horizon:g})",
            )


RULE_DANGLING_LINEAGE = "hypothesis.dangling-lineage"
_LINEAGE_KIND = "hypothesis"


@Check(section="hypotheses...", order=6)
def check_dangling_lineage(ctx: ValidateContext) -> Iterator[Result]:
    """A closed hypothesis's successor must resolve to a real, live, OTHER entity.

    The schema validates one record in isolation, so it can only see that `superseded_by:` is
    PRESENT. Whether it resolves is a cross-record fact, and this is where it is asked.

    ☠️ The resolver is built HERE, and NOT inside `load_project_sources`. That was tried, and it is
    wrong: `ReferenceResolver.from_entities` raises `AliasCollisionError` on a corpus with a
    duplicated alias, so constructing it in the loader turns a REPORTABLE fault into an UNLOADABLE
    project -- for every consumer of the loader, including the ones that never look at a hypothesis.
    `annotation/proposition_archive.py` exists precisely to REPORT and unblock those collisions, and
    calls `load_project_sources` on a colliding corpus on purpose; the loader-side pass breaks it
    (three tests). Resolution is ANALYSIS over a loaded corpus. The loader loads. Every other
    `from_entities` call site in the tree builds its own resolver for the same reason.

    Same three arguments as `materialize.py` -- same entities, same manual aliases, same identity
    table -- because a validator that resolves a reference differently from the materializer is a
    second authority for one fact.

    WARN, hard-coded, until the `hypothesis` kind is certified (Task 12's ratchet flips it per kind).
    """
    sources = ctx.project_sources()
    resolver = ReferenceResolver.from_entities(
        sources.entities,
        manual_aliases=sources.manual_aliases,
        archive_alias_tokens=sources.archive_alias_tokens,
        identity_table=build_identity_table(sources),
    )
    path_by_id = {
        str(document.frontmatter.get("id")): document.path
        for document in sources.markdown_documents
        if document.frontmatter.get("id")
    }

    live_hypotheses = _live_lineage_targets(sources)
    for entity in sources.entities:
        for violation in check_resolution(
            entity.model_dump(mode="json"), targets=resolver, live_hypotheses=live_hypotheses
        ):
            path = path_by_id.get(violation.entity_id)
            yield Result(
                Severity.WARN,
                Path(path) if path else None,
                None,
                violation.message,
                RULE_DANGLING_LINEAGE,
                None,
            )


def _live_lineage_targets(sources) -> set[str]:
    """The ids a successor may name: LOCAL, LIVE **hypotheses**. Not every loaded entity.

    ☠️ This was `{e.canonical_id for e in sources.entities}` -- every entity, every kind -- and that
    is a hole, because the schema constrains only the AUTHORED spelling. `superseded_by` is
    `pattern: "^hypothesis:"`, but an ALIAS may point anywhere: put `aliases: [hypothesis:looks-valid]`
    on `dataset:0002` and `superseded_by: hypothesis:looks-valid` resolves to a DATASET, is found in
    the all-entities set, and reports CLEAN. A hypothesis superseded by a dataset.

    Keyed on `canonical_id`, NOT `id`: the resolver ANSWERS in canonical ids, so a set keyed on the
    authored `id` would fail to contain its own resolver's answers for every entity whose canonical
    id differs from the one on disk.

    `kind == "hypothesis"` is also what makes these LOCAL, and by CONTRACT rather than by luck:
    `sources.entities` is local markdown plus the commons overlay, and commons can own only
    `dataset` / `paper` / `topic` / `theme` -- `_TYPE_DIR_TO_TYPE` (commons/adapter.py:25) derives
    the kind from the directory, and there is no `hypotheses/` one. A commons entity therefore can
    never be a hypothesis, so no separate locality filter is needed; adding one would be dead code.
    """
    return {
        entity.canonical_id for entity in sources.entities if entity.kind == _LINEAGE_KIND
    }


def _review_horizon_days(frontmatter: dict[str, Any]) -> float | None:
    review_state = frontmatter.get("review_state")
    if not isinstance(review_state, dict):
        return None

    value = review_state.get("review_horizon_days")
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None
