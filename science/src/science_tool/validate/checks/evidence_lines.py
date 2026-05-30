"""Structural QA checks for evidence-line entities.

The structural checks operate on frontmatter only — no graph/trig parsing — so they
run even before `graph build` and give fast authoring-time feedback. The belief
authoring checks (`check_belief_authoring`) additionally load the materialized graph
(`knowledge/graph.trig`) to compare authored confidence against the computed ceiling.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path

from rdflib import Literal, RDF, Dataset, URIRef
from rdflib.namespace import PROV

from science_tool.graph.belief import (
    BeliefMagnitude,
    aggregate_belief,
    collect_evidence_units,
    is_decisive_refutation,
    is_proxy_gated,
)
from science_tool.graph.belief_weights import (
    DIAGNOSTIC_ROLES,
    EVIDENCE_ROLE_RANK,
    EVIDENCE_TYPE_RANK,
    STRENGTH_RANK,
    normalize_evidence_type,
)
from science_tool.graph.io import SCHEMA_NS, SCI_NS
from science_tool.graph.store import _evidence_targets_for_uri, _graph_uri
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

    _knowledge, provenance = _load_belief_graphs(ctx)
    if provenance is None:
        return
    for record in provenance.subjects(RDF.type, SCI_NS.DatasetIndependenceCommitment):
        members = [member for member in provenance.objects(record, SCI_NS.independenceMember) if isinstance(member, URIRef)]
        for member in members:
            if _line_independence(provenance, member) == "independent":
                yield Result(
                    severity=Severity.ERROR,
                    path=None,
                    line=None,
                    message=f"{member}: authored independence=independent contradicts committed dataset-derived shared-source dependence",
                    rule="independence.dataset-derived-contradiction",
                    task=None,
                )
    for record in provenance.subjects(RDF.type, SCI_NS.DatasetIndependenceCandidate):
        members = [member for member in provenance.objects(record, SCI_NS.independenceMember) if isinstance(member, URIRef)]
        if len(members) < 2:
            continue
        eligible = [
            member
            for member in members
            if _line_independence(provenance, member) in (None, "independent")
        ]
        if len(eligible) >= 2:
            reason = next((str(value) for value in provenance.objects(record, SCI_NS.independenceReason)), "dataset-derived")
            yield Result(
                severity=Severity.WARN,
                path=None,
                line=None,
                message=f"dataset-derived candidate dependence ({reason}) links {len(eligible)} untagged/authored-independent lines on the same target",
                rule="independence.suspect-circular",
                task=None,
            )


def _line_independence(provenance, line: URIRef) -> str | None:
    for value in provenance.objects(line, SCI_NS.evidenceIndependence):
        return str(value)
    return None


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


# ---------------------------------------------------------------------------
# Check 5: belief authoring (graph-dependent) — compares AUTHORED frontmatter
#   confidence against the COMPUTED belief ceiling. Emits four rules:
#     belief.single-source-ceiling (WARN), belief.refutation-masked (ERROR),
#     belief.inflated (WARN), evidence.proxy-ungated (WARN).
#   The aggregator self-caps, so a computed-vs-computed invariant never fires;
#   these checks surface where authoring overreaches the evidence.
# ---------------------------------------------------------------------------

_MAG_INDEX = {
    m.value: i
    for i, m in enumerate(
        [
            BeliefMagnitude.SPECULATIVE,
            BeliefMagnitude.FRAGILE,
            BeliefMagnitude.SUPPORTED,
            BeliefMagnitude.WELL_SUPPORTED,
        ]
    )
}

# Authored prose/frontmatter phrasings -> ladder rung. Unknown values are skipped (never guessed).
_AUTHORED_MAGNITUDE = {
    "speculative": "speculative",
    "proposed": "speculative",
    "fragile": "fragile",
    "single-source": "fragile",
    "supported": "supported",
    "literature-supported": "supported",
    "partially-supported": "supported",
    "well_supported": "well_supported",
    "well-supported": "well_supported",
    "established": "well_supported",
}


def _load_belief_graphs(ctx: ValidateContext):
    path = ctx.project_root / "knowledge" / "graph.trig"
    if not path.exists():
        return None, None
    ds = Dataset()
    ds.parse(source=str(path), format="trig")
    return ds.graph(_graph_uri("graph/knowledge")), ds.graph(_graph_uri("graph/provenance"))


def _claims(knowledge):
    for ctype in (SCI_NS.Proposition, SCI_NS.Hypothesis):
        for subj, _, _ in knowledge.triples((None, RDF.type, ctype)):
            yield subj


def _authored_magnitude(ctx, provenance, claim_uri):
    """Map a claim's authored confidence (frontmatter) to a ladder rung, or None.

    Resolution: provenance (claim_uri, prov:wasDerivedFrom, source) and
    (source, schema:identifier, "<relative path>"); read belief_state / evidence_stance /
    author_stated_evidence; map the leading token via _AUTHORED_MAGNITUDE; unknown phrasings
    skipped. Overlay sources tolerated — first existing file with a recognized token wins.
    """
    for source in provenance.objects(claim_uri, PROV.wasDerivedFrom):
        rel = next(provenance.objects(source, SCHEMA_NS.identifier), None)
        if rel is None:
            continue
        path = ctx.project_root / str(rel)
        if not path.exists():
            continue
        fm = ctx.frontmatter(path)
        for field in ("belief_state", "evidence_stance", "author_stated_evidence"):
            raw = fm.get(field)
            if not raw:
                continue
            token = str(raw).strip().lower().split()[0].split("(")[0].strip("-_:")
            if token in _AUTHORED_MAGNITUDE:
                return _AUTHORED_MAGNITUDE[token], path
    return None


@Check(section="evidence lines", order=27)
def check_belief_authoring(ctx: ValidateContext) -> Iterator[Result]:
    knowledge, provenance = _load_belief_graphs(ctx)
    if knowledge is None:
        return
    for claim in _claims(knowledge):
        units = collect_evidence_units(
            knowledge, provenance, _evidence_targets_for_uri(knowledge, claim)
        )
        belief = aggregate_belief(units)
        n_support_groups = len({u.independence_group or u.line_uri for u in belief.support_units})
        decisive = any(is_decisive_refutation(u) for u in belief.dispute_units)

        # #6 evidence.proxy-ungated (line-level, both stances — rule 5 is symmetric)
        for u in (*belief.support_units, *belief.dispute_units):
            if is_proxy_gated(u) and u.evidence_role == "direct_test":
                yield Result(
                    severity=Severity.WARN,
                    path=None,
                    line=None,
                    message=(
                        f"{u.line_uri}: indirect/derived proxy as direct_test "
                        f"without a measurement_model"
                    ),
                    rule="evidence.proxy-ungated",
                    task=None,
                )

        authored = _authored_magnitude(ctx, provenance, claim)
        if authored is None:
            continue
        mag, path = authored
        if mag not in _MAG_INDEX:
            continue

        # #5 single-source-ceiling
        if n_support_groups <= 1 and _MAG_INDEX[mag] > _MAG_INDEX["fragile"]:
            yield Result(
                severity=Severity.WARN,
                path=path,
                line=None,
                message=f"authored '{mag}' exceeds single-independence-unit ceiling (fragile)",
                rule="belief.single-source-ceiling",
                task=None,
            )

        # #3 refutation-masked
        if decisive and _MAG_INDEX[mag] >= _MAG_INDEX["supported"]:
            yield Result(
                severity=Severity.ERROR,
                path=path,
                line=None,
                message=f"authored '{mag}' >= supported with an unresolved whole-claim refutation",
                rule="belief.refutation-masked",
                task=None,
            )

        # #4 inflated (general overreach vs computed)
        if _MAG_INDEX[mag] > _MAG_INDEX[belief.magnitude.value]:
            yield Result(
                severity=Severity.WARN,
                path=path,
                line=None,
                message=f"authored '{mag}' exceeds computed '{belief.magnitude.value}'",
                rule="belief.inflated",
                task=None,
            )


# ---------------------------------------------------------------------------
# Check 7: belief.fragile-single-line (WARN) — leave-one-out sensitivity
#   If dropping any single kept independent unit flips the ordinal belief_state
#   (magnitude or contested), the claim's conclusion is not robust.
# ---------------------------------------------------------------------------

@Check(section="evidence lines", order=29)
def check_belief_fragile_single_line(ctx: ValidateContext) -> Iterator[Result]:
    """#7 leave-one-out: if dropping any single kept independent unit flips the ordinal
    belief_state (magnitude or contested), the claim's conclusion is not robust."""
    knowledge, provenance = _load_belief_graphs(ctx)
    if knowledge is None:
        return
    for claim in _claims(knowledge):
        units = collect_evidence_units(knowledge, provenance, _evidence_targets_for_uri(knowledge, claim))
        base = aggregate_belief(units)
        # Include diagnostics: a claim can be contested solely via a diagnostic dispute
        # (e.g. h012/Simeonov), and dropping that line flips contested — exactly the fragility
        # this check exists to surface.
        kept_uris = {u.line_uri for u in (*base.support_units, *base.dispute_units, *base.diagnostics)}
        if len(kept_uris) < 2:
            continue
        # Sort so the reported line is deterministic across processes (set iteration order is
        # PYTHONHASHSEED-dependent); when several lines each flip the state, always report the same.
        for drop in sorted(kept_uris):
            reduced = aggregate_belief([u for u in units if u.line_uri != drop])
            if reduced.magnitude != base.magnitude or reduced.contested != base.contested:
                yield Result(
                    severity=Severity.WARN,
                    path=None,
                    line=None,
                    message=(
                        f"{claim}: belief_state flips ({base.display()} -> "
                        f"{reduced.display()}) when dropping a single line ({drop})"
                    ),
                    rule="belief.fragile-single-line",
                    task=None,
                )
                break


# ---------------------------------------------------------------------------
# Check 8: belief.nonreproducible (ERROR) — golden snapshot comparison
#   Equal inputs (input_hashes + config_version + scalar_enabled) must reproduce
#   the stored belief. Differing inputs are a legitimate change, not flagged.
# ---------------------------------------------------------------------------

_GOLDEN_SCALAR_FIELDS = (
    "massed_support_score", "massed_dispute_score",
    "massed_support_band", "massed_dispute_band", "net_band", "net_robust",
)


@Check(section="evidence lines", order=30)
def check_belief_nonreproducible(ctx: ValidateContext) -> Iterator[Result]:
    """#8 golden: equal inputs (input_hashes + config_version + scalar_enabled) must reproduce
    the stored belief. Differing inputs are legitimate change, not flagged."""
    from science_tool.graph.belief_snapshot import make_snapshots, read_snapshots

    graph_file = ctx.project_root / "knowledge" / "graph.trig"
    snap_file = ctx.project_root / "knowledge" / "belief-snapshots.jsonl"
    if not graph_file.exists() or not snap_file.exists():
        return
    stored = read_snapshots(snap_file)
    for now in make_snapshots(graph_file, as_of="recompute"):
        # All stored rows for this claim whose input set matches the current one, then the
        # LATEST among them (file order == append order). Latest-matching, not latest-per-claim.
        matches = [
            r for r in stored
            if r["claim"] == now["claim"]
            and sorted(r["input_hashes"]) == sorted(now["input_hashes"])
            and r["config_version"] == now["config_version"]
            and r["scalar_enabled"] == now["scalar_enabled"]
        ]
        if not matches:
            continue
        prior = matches[-1]
        diffs = [
            f for f in ("belief_state", "contested", "diagnostic_dispute_count")
            if prior.get(f) != now.get(f)
        ]
        if now["scalar_enabled"]:
            diffs += [f for f in _GOLDEN_SCALAR_FIELDS if prior.get(f) != now.get(f)]
        if diffs:
            yield Result(
                severity=Severity.ERROR,
                path=snap_file,
                line=None,
                message=(
                    f"{now['claim']}: belief not reproducible from identical inputs "
                    f"(differing fields: {', '.join(diffs)})"
                ),
                rule="belief.nonreproducible",
                task=None,
            )


# ---------------------------------------------------------------------------
# Check 6: evidence.unscored-line (WARN)
#   A massable (non-diagnostic) support/dispute line that cannot be scored
#   because one or more of evidence_type, evidence_role, or strength is
#   missing or unrecognized. Diagnostic roles (model_criticism /
#   negative_control) are recognized-but-non-massed and never flagged.
# ---------------------------------------------------------------------------

@Check(section="evidence lines", order=28)
def check_evidence_unscored_line(ctx: ValidateContext) -> Iterator[Result]:
    """A massable (non-diagnostic) support/dispute line that cannot be scored — surfaces an
    authored-metadata gap. Diagnostic roles (model_criticism/negative_control) are
    recognized-but-non-massed and never flagged."""
    for path, fm in _ev_lines(ctx):
        stance = fm.get("stance")
        if stance not in ("supports", "disputes"):
            continue
        role = fm.get("evidence_role") or ""
        if role in DIAGNOSTIC_ROLES:
            continue
        missing: list[str] = []
        if normalize_evidence_type(fm.get("evidence_type")) not in EVIDENCE_TYPE_RANK:
            missing.append("evidence_type")
        if role not in EVIDENCE_ROLE_RANK:
            missing.append("evidence_role")
        if (fm.get("strength") or "") not in STRENGTH_RANK:
            missing.append("strength")
        if missing:
            yield Result(
                severity=Severity.WARN,
                path=path,
                line=None,
                message=f"evidence-line cannot be scored (missing/unrecognized: {', '.join(missing)})",
                rule="evidence.unscored-line",
                task=None,
            )


# ---------------------------------------------------------------------------
# Check 9: evidence.reference-basis-no-identification-strength (WARN, A2/A-D4)
#   A recording-only nudge: if an evidence line rests on a reference (human-
#   curated) dataset but declares no identification_strength, suggest the
#   author set identification_strength: structural. No scoring effect.
# ---------------------------------------------------------------------------

@Check(section="evidence lines", order=32)
def check_reference_basis_no_identification_strength(ctx: ValidateContext) -> Iterator[Result]:
    """#9 authoring nudge (A2/A-D4): lines resting on a reference dataset but declaring no
    identification_strength should consider setting identification_strength: structural."""
    knowledge, provenance = _load_belief_graphs(ctx)
    if knowledge is None:
        return

    reference_uris = {
        str(s)
        for s, _, _ in knowledge.triples((None, SCI_NS.sourceClass, Literal("reference")))
    }
    if not reference_uris:
        return

    for line, _, _ in knowledge.triples((None, RDF.type, SCI_NS.EvidenceLine)):
        derived = {str(o) for _, _, o in provenance.triples((line, PROV.wasDerivedFrom, None))}
        if not (derived & reference_uris):
            continue
        if any(provenance.triples((line, SCI_NS.identificationStrength, None))):
            continue
        yield Result(
            severity=Severity.WARN,
            path=None,
            line=None,
            message=(
                f"{line}: evidence rests on a reference dataset but declares no "
                f"identification_strength; if the curated set IS the basis of the claim, "
                f"set identification_strength: structural (A2/A-D4)"
            ),
            rule="evidence.reference-basis-no-identification-strength",
            task=None,
        )
