"""Belief QA checks comparing AUTHORED frontmatter confidence vs the COMPUTED ceiling.

Each test scaffolds a real project, materializes `knowledge/graph.trig`, builds a
ValidateContext, runs `check_belief_authoring`, and asserts which `Result.rule`s fire.
The aggregator self-caps, so these checks compare authored frontmatter against the
computed belief — the resolution path (claim -> prov:wasDerivedFrom -> schema:identifier
-> file -> frontmatter) is exercised end-to-end here.
"""

from __future__ import annotations

from pathlib import Path


def _write(root: Path, rel: str, body: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _manifest(root: Path) -> None:
    _write(root, "science.yaml", "name: test\nknowledge_profiles:\n  local: local\n")


def _prop(belief_state: str | None = None) -> str:
    extra = f"belief_state: {belief_state}\n" if belief_state is not None else ""
    return (
        "---\n"
        "id: proposition:p\n"
        "kind: proposition\n"
        'title: "Proposition P"\n'
        "project: test\n"
        "ontology_terms: []\n"
        "related: []\n"
        "source_refs: []\n"
        "created: 2026-05-01\n"
        "updated: 2026-05-01\n"
        f"{extra}"
        "---\n"
    )


def _evidence_line(
    *,
    eid: str,
    stance: str,
    extra: str = "",
) -> str:
    return (
        "---\n"
        f"id: evidence-line:{eid}\n"
        "kind: evidence-line\n"
        f'title: "{eid}"\n'
        "project: test\n"
        "ontology_terms: []\n"
        "related: []\n"
        "source_refs: []\n"
        "created: 2026-05-01\n"
        "updated: 2026-05-01\n"
        f"stance: {stance}\n"
        "target: proposition:p\n"
        f"{extra}"
        "---\n"
    )


def _run_check(tmp_path: Path):
    from science_tool.graph.materialize import materialize_graph
    from science_tool.validate import ValidateContext
    from science_tool.validate.checks.evidence_lines import check_belief_authoring

    materialize_graph(tmp_path)
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
    return list(check_belief_authoring(ctx))


def _rules(results) -> set[str]:
    return {r.rule for r in results}


# ---------------------------------------------------------------------------
# belief.single-source-ceiling (WARN)
#   authored magnitude > fragile but only ONE independence unit of support.
# ---------------------------------------------------------------------------

def test_single_source_ceiling_fires_with_one_support(tmp_path: Path) -> None:
    _manifest(tmp_path)
    _write(tmp_path, "entities/propositions/p.md", _prop(belief_state="supported"))
    _write(
        tmp_path,
        "entities/evidence-lines/sup.md",
        _evidence_line(
            eid="sup",
            stance="supports",
            extra="evidence_role: direct_test\nstrength: strong\nindependence: independent\nindependence_group: g1\n",
        ),
    )

    rules = _rules(_run_check(tmp_path))
    assert "belief.single-source-ceiling" in rules


def test_single_source_ceiling_silent_with_two_independent_supports(tmp_path: Path) -> None:
    _manifest(tmp_path)
    _write(tmp_path, "entities/propositions/p.md", _prop(belief_state="supported"))
    _write(
        tmp_path,
        "entities/evidence-lines/sup1.md",
        _evidence_line(
            eid="sup1",
            stance="supports",
            extra="evidence_role: direct_test\nstrength: strong\nindependence: independent\nindependence_group: g1\n",
        ),
    )
    _write(
        tmp_path,
        "entities/evidence-lines/sup2.md",
        _evidence_line(
            eid="sup2",
            stance="supports",
            extra="evidence_role: direct_test\nstrength: strong\nindependence: independent\nindependence_group: g2\n",
        ),
    )

    rules = _rules(_run_check(tmp_path))
    assert "belief.single-source-ceiling" not in rules


# ---------------------------------------------------------------------------
# belief.refutation-masked (ERROR)
#   authored magnitude >= supported with an UNRESOLVED independent strong
#   direct_test whole_claim dispute present.
# ---------------------------------------------------------------------------

def test_refutation_masked_fires_with_decisive_dispute(tmp_path: Path) -> None:
    _manifest(tmp_path)
    _write(tmp_path, "entities/propositions/p.md", _prop(belief_state="supported"))
    # Two independent supports so the masked-refutation arm is the live signal.
    _write(
        tmp_path,
        "entities/evidence-lines/sup1.md",
        _evidence_line(
            eid="sup1",
            stance="supports",
            extra="evidence_role: direct_test\nstrength: strong\nindependence: independent\nindependence_group: g1\n",
        ),
    )
    _write(
        tmp_path,
        "entities/evidence-lines/sup2.md",
        _evidence_line(
            eid="sup2",
            stance="supports",
            extra="evidence_role: direct_test\nstrength: strong\nindependence: independent\nindependence_group: g2\n",
        ),
    )
    # Decisive refutation: independent + strong + direct_test + whole_claim (default scope).
    _write(
        tmp_path,
        "entities/evidence-lines/dis.md",
        _evidence_line(
            eid="dis",
            stance="disputes",
            extra="evidence_role: direct_test\nstrength: strong\nindependence: independent\nindependence_group: g3\ndispute_scope: whole_claim\n",
        ),
    )

    rules = _rules(_run_check(tmp_path))
    assert "belief.refutation-masked" in rules


def test_refutation_masked_silent_for_scoped_diagnostic_dispute(tmp_path: Path) -> None:
    _manifest(tmp_path)
    _write(tmp_path, "entities/propositions/p.md", _prop(belief_state="supported"))
    _write(
        tmp_path,
        "entities/evidence-lines/sup1.md",
        _evidence_line(
            eid="sup1",
            stance="supports",
            extra="evidence_role: direct_test\nstrength: strong\nindependence: independent\nindependence_group: g1\n",
        ),
    )
    _write(
        tmp_path,
        "entities/evidence-lines/sup2.md",
        _evidence_line(
            eid="sup2",
            stance="supports",
            extra="evidence_role: direct_test\nstrength: strong\nindependence: independent\nindependence_group: g2\n",
        ),
    )
    # Same independent/strong dispute but authored as model_criticism + generalization:
    # diagnostic and scoped, never decisive.
    _write(
        tmp_path,
        "entities/evidence-lines/dis.md",
        _evidence_line(
            eid="dis",
            stance="disputes",
            extra="evidence_role: model_criticism\nstrength: strong\nindependence: independent\nindependence_group: g3\ndispute_scope: generalization\n",
        ),
    )

    rules = _rules(_run_check(tmp_path))
    assert "belief.refutation-masked" not in rules


# ---------------------------------------------------------------------------
# belief.inflated (WARN)
#   authored magnitude strictly above the computed magnitude.
# ---------------------------------------------------------------------------

def test_inflated_fires_when_authored_exceeds_computed(tmp_path: Path) -> None:
    _manifest(tmp_path)
    # Authored well_supported, but only ONE clean support -> computed fragile.
    _write(tmp_path, "entities/propositions/p.md", _prop(belief_state="well_supported"))
    _write(
        tmp_path,
        "entities/evidence-lines/sup.md",
        _evidence_line(
            eid="sup",
            stance="supports",
            extra="evidence_role: direct_test\nstrength: strong\nindependence: independent\nindependence_group: g1\n",
        ),
    )

    rules = _rules(_run_check(tmp_path))
    assert "belief.inflated" in rules


# ---------------------------------------------------------------------------
# evidence.proxy-ungated (WARN)
#   a counted support line with proxy_directness in {indirect, derived},
#   NO measurement_model, and evidence_role == direct_test. Line-level: fires
#   even when the proposition declares no authored magnitude.
# ---------------------------------------------------------------------------

def test_proxy_ungated_fires_for_indirect_direct_test_without_measurement_model(tmp_path: Path) -> None:
    _manifest(tmp_path)
    _write(tmp_path, "entities/propositions/p.md", _prop(belief_state=None))
    _write(
        tmp_path,
        "entities/evidence-lines/sup.md",
        _evidence_line(
            eid="sup",
            stance="supports",
            extra="evidence_role: direct_test\nstrength: strong\nindependence: independent\nindependence_group: g1\nproxy_directness: indirect\n",
        ),
    )

    rules = _rules(_run_check(tmp_path))
    assert "evidence.proxy-ungated" in rules
