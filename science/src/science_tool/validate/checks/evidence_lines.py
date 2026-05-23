"""Structural QA checks for evidence-line entities.

Checks operate on frontmatter only — no graph/trig parsing — so they run
even before `graph build` and give fast authoring-time feedback.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path

from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

# Observability keys that, if shared between two "independent" lines on the
# same target, make them suspect.
_OBSERVABILITY_KEYS = ("shared_dataset", "shared_lab", "shared_platform", "shared_cohort")


def _ev_lines(ctx: ValidateContext) -> list[tuple[Path, dict]]:
    """Return (path, frontmatter) pairs for every evidence-line file."""
    ev_dir = ctx.doc_dir / "evidence-lines"
    if not ev_dir.is_dir():
        return []
    return [(path, ctx.frontmatter(path)) for path in sorted(ev_dir.glob("*.md"))]


# ---------------------------------------------------------------------------
# Check 1: evidence.unstanced (WARN)
#   (a) Missing stance or empty/missing target on an evidence-line file.
#   (b) Proposition source_refs with no matching evidence-line coverage.
# ---------------------------------------------------------------------------

@Check(section="evidence lines", order=23)
def check_evidence_lines_unstanced(ctx: ValidateContext) -> Iterator[Result]:
    lines = _ev_lines(ctx)

    # Sub-case (a): missing stance or missing/empty target.
    for path, fm in lines:
        if not fm.get("stance"):
            yield Result(
                severity=Severity.WARN,
                path=path,
                line=None,
                message=f"{path.name}: missing required field 'stance'",
                rule="evidence.unstanced",
                task=None,
            )
        if not fm.get("target"):
            yield Result(
                severity=Severity.WARN,
                path=path,
                line=None,
                message=f"{path.name}: missing or empty required field 'target'",
                rule="evidence.unstanced",
                task=None,
            )

    # Sub-case (b): uncounted proposition source_refs.
    # Build an index: (target_id, source_ref) -> bool for all existing lines.
    covered: set[tuple[str, str]] = set()
    for _path, fm in lines:
        target = fm.get("target", "")
        source = fm.get("source", "")
        if target and source:
            covered.add((str(target), str(source)))

    prop_dir = ctx.doc_dir / "propositions"
    if prop_dir.is_dir():
        for prop_path in sorted(prop_dir.glob("*.md")):
            pfm = ctx.frontmatter(prop_path)
            prop_id = pfm.get("id", "")
            source_refs = pfm.get("source_refs") or []
            if not isinstance(source_refs, list):
                source_refs = [source_refs]
            for ref in source_refs:
                ref = str(ref)
                prefix = ref.split(":")[0] if ":" in ref else ""
                # Skip bibliography-style refs (cite:...).
                if prefix == "cite":
                    continue
                if (str(prop_id), ref) not in covered:
                    yield Result(
                        severity=Severity.WARN,
                        path=prop_path,
                        line=None,
                        message=(
                            f"{prop_path.name}: source '{ref}' on proposition '{prop_id}' "
                            f"has no matching evidence-line (target={prop_id!r}, source={ref!r})"
                        ),
                        rule="evidence.unstanced",
                        task=None,
                    )


# ---------------------------------------------------------------------------
# Check 2: independence.ungrouped-collapse (ERROR)
#   Lines with independence in {shared-source, circular} but no group.
# ---------------------------------------------------------------------------

@Check(section="evidence lines", order=24)
def check_independence_ungrouped_collapse(ctx: ValidateContext) -> Iterator[Result]:
    _NEEDS_GROUP = {"shared-source", "circular"}
    for path, fm in _ev_lines(ctx):
        independence = fm.get("independence", "")
        if independence in _NEEDS_GROUP:
            group = fm.get("independence_group", "")
            if not group:
                yield Result(
                    severity=Severity.ERROR,
                    path=path,
                    line=None,
                    message=(
                        f"{path.name}: independence='{independence}' requires "
                        f"'independence_group' to be set (collapse-to is undefined without it)"
                    ),
                    rule="independence.ungrouped-collapse",
                    task=None,
                )


# ---------------------------------------------------------------------------
# Check 3: independence.suspect-circular (WARN)
#   Two "independent" lines on the SAME target that share an independence_group
#   OR share a non-empty observability key value.
# ---------------------------------------------------------------------------

@Check(section="evidence lines", order=25)
def check_independence_suspect_circular(ctx: ValidateContext) -> Iterator[Result]:
    lines = _ev_lines(ctx)

    # Collect only lines tagged as independent, grouped by target.
    by_target: dict[str, list[tuple[Path, dict]]] = defaultdict(list)
    for path, fm in lines:
        if fm.get("independence") == "independent" and fm.get("target"):
            by_target[str(fm["target"])].append((path, fm))

    for _target, group in by_target.items():
        # Check every pair within the same target.
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                path_a, fm_a = group[i]
                path_b, fm_b = group[j]
                shared_key, shared_val = _first_shared_signal(fm_a, fm_b)
                if shared_key is not None:
                    yield Result(
                        severity=Severity.WARN,
                        path=path_a,
                        line=None,
                        message=(
                            f"{path_a.name} and {path_b.name} are both tagged "
                            f"independence=independent on the same target but share "
                            f"{shared_key}={shared_val!r}"
                        ),
                        rule="independence.suspect-circular",
                        task=None,
                    )


def _first_shared_signal(
    fm_a: dict, fm_b: dict
) -> tuple[str, str] | tuple[None, None]:
    """Return (key, value) for the first signal shared between two frontmatters."""
    # Check independence_group first.
    grp_a = fm_a.get("independence_group", "")
    grp_b = fm_b.get("independence_group", "")
    if grp_a and grp_b and grp_a == grp_b:
        return "independence_group", str(grp_a)
    # Check observability keys.
    for key in _OBSERVABILITY_KEYS:
        val_a = fm_a.get(key, "")
        val_b = fm_b.get(key, "")
        if val_a and val_b and val_a == val_b:
            return key, str(val_a)
    return None, None


# ---------------------------------------------------------------------------
# Check 4: evidence.strength-implausible (WARN)
#   strength=strong + evidence_role=background_constraint is contradictory.
# ---------------------------------------------------------------------------

@Check(section="evidence lines", order=26)
def check_evidence_strength_implausible(ctx: ValidateContext) -> Iterator[Result]:
    for path, fm in _ev_lines(ctx):
        if fm.get("strength") == "strong" and fm.get("evidence_role") == "background_constraint":
            yield Result(
                severity=Severity.WARN,
                path=path,
                line=None,
                message=(
                    f"{path.name}: strength='strong' combined with "
                    f"evidence_role='background_constraint' is implausible — "
                    f"'strong' requires a direct test, not background framing"
                ),
                rule="evidence.strength-implausible",
                task=None,
            )
