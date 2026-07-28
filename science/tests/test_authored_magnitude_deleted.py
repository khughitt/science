"""Provenance must never set an epistemic magnitude (D5 Task 2b).

`_authored_magnitude` walked ("belief_state", "evidence_stance", "author_stated_evidence") and
returned on the FIRST recognized token. The corpus makes that ordering load-bearing in the worst
way -- all 13 files that author any of these carry ALL THREE:

    belief_state:           speculative                      -> rung 0  (the floor)
    evidence_stance:        literature-supported             -> rung 2
    author_stated_evidence: established (barcoded mouse)     -> rung 3  (the ceiling)

So the chain is ordered most-cautious -> most-boastful, and peeling fields off in the obvious
order walks the corpus UP the ladder:

    delete belief_state              -> every file jumps to `supported`      (ERROR possible)
    delete belief_state + stance     -> every file jumps to `well_supported` (ERROR likely)

The careful fix is worse than the careless one. The chain is therefore DELETED, not narrowed:
`evidence_stance` and `author_stated_evidence` are PROVENANCE -- they say where a claim came from,
not how strong the evidence is -- and provenance must never set an epistemic magnitude.

This is behavior-neutral on the real corpus: all 13 files resolve to `speculative` (rung 0) today,
and every rule the magnitude fed requires rung > 1, so none of them can currently fire on any real
file. These tests pin that the provenance fields cannot resurrect them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_AUTHORING_RULES = {"belief.single-source-ceiling", "belief.refutation-masked", "belief.inflated"}


def _write(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _manifest(root: Path) -> None:
    _write(root, "science.yaml", "name: test\nknowledge_profiles:\n  local: local\n")


def _proposition(extra: str) -> str:
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


def _support_line() -> str:
    return (
        "---\n"
        "id: evidence-line:sup\n"
        "kind: evidence-line\n"
        'title: "sup"\n'
        "project: test\n"
        "ontology_terms: []\n"
        "related: []\n"
        "source_refs: []\n"
        "created: 2026-05-01\n"
        "updated: 2026-05-01\n"
        "stance: supports\n"
        "target: proposition:p\n"
        "evidence_role: direct_test\n"
        "strength: strong\n"
        "independence: independent\n"
        "independence_group: g1\n"
        "---\n"
    )


def _authoring_rules(tmp_path: Path) -> set[str]:
    from science_tool.graph.materialize import materialize_graph
    from science_tool.validate import ValidateContext
    from science_tool.validate.checks.evidence_lines import check_belief_authoring

    materialize_graph(tmp_path)
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
    return {result.rule_id for result in check_belief_authoring(ctx)} & _AUTHORING_RULES


@pytest.mark.parametrize(
    "field,value",
    [
        # `literature-supported` says WHERE the claim came from. It is coverage/provenance, not
        # epistemic magnitude. Under the old chain it mapped to rung 2 and fired the ceiling rule.
        ("evidence_stance", "literature-supported"),
        # The leading token is what the old parser took: "established ..." -> rung 3, the ceiling.
        ("author_stated_evidence", "established (barcoded mouse experiment)"),
        ("author_stated_evidence", "established at single-cell scale (Lee2026)"),
    ],
)
def test_provenance_never_sets_an_epistemic_magnitude(tmp_path: Path, field: str, value: str) -> None:
    _manifest(tmp_path)
    _write(tmp_path, "entities/propositions/p.md", _proposition(f"{field}: {value}\n"))
    _write(tmp_path, "entities/evidence-lines/sup.md", _support_line())

    assert _authoring_rules(tmp_path) == set()


def test_the_real_corpus_shape_produces_no_authoring_findings(tmp_path: Path) -> None:
    """All 13 real files carry all three fields at once. Under the old chain `belief_state` won and
    everything was silent; the danger was only ever what happened when it was removed."""
    _manifest(tmp_path)
    _write(
        tmp_path,
        "entities/propositions/p.md",
        _proposition(
            "belief_state: speculative\n"
            "evidence_stance: literature-supported\n"
            "author_stated_evidence: established (barcoded mouse experiment)\n"
        ),
    )
    _write(tmp_path, "entities/evidence-lines/sup.md", _support_line())

    assert _authoring_rules(tmp_path) == set()


def test_the_magnitude_chain_is_gone_entirely(tmp_path: Path) -> None:
    """Not narrowed to one field -- deleted. A single-field read would still be an authored belief,
    which is the second-source-of-truth defect D5 abolishes (design rev 8)."""
    from science_tool.validate.checks import evidence_lines

    assert not hasattr(evidence_lines, "_authored_magnitude")
    assert not hasattr(evidence_lines, "_AUTHORED_MAGNITUDE")
