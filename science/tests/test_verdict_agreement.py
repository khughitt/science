"""`verdict.*` — does an AUTHORED adjudication agree with the COMPOSED evidence?

**The subsystem had no tests.** Every claim it rests on — polarity, admissibility, core-member
scope, the non-ordinal matrix, the rules firing independently — was asserted in prose and gated by
nothing. And the artifact diff cannot stand in for them: **no corpus hypothesis carries a verdict
until Task 9**, so that diff is *empty by construction* and would go green over a
`check_verdict_agreement` that returned `[]` on every input. A suite that cannot distinguish a
working check from a check that does nothing is not a suite.

These build a real project, materialize a real graph, and run the real check.

**Every "not a basis" test is paired with a MATCHED CONTROL** differing in exactly the property
under test. Without the control, a check that always yielded both rules would pass every one of
them.

**No suppression.** Evidence that fails polarity, admissibility, or scope fails it for
`_qualifying_basis` AND for the composition — so the verdict has no basis *and* disagrees with the
belief the corpus actually composes to. Both are true, and both are said. Folding one into the
other would silently re-grade whichever lost: the rules carry different severities and different
gate tiers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml
from rdflib import Dataset, URIRef

from science_tool.graph.io import SCI_NS
from science_tool.graph.materialize import materialize_graph
from science_tool.graph.store import PROJECT_NS
from science_tool.validate.checks.verdict_agreement import check_verdict_agreement
from science_tool.validate.context import ValidateContext
from science_tool.validate.gates import cumulative_rules
from science_tool.validate.result import Severity

HYPOTHESIS = "hypothesis:0001-x"
CORE = "proposition:core"
RIVAL = "proposition:rival"


# ---------------------------------------------------------------------------------------------
# fixtures — a real project, a real graph
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Unit:
    """One evidence line.

    `stance="disputes"` is DECISIVE by default (independent + strong + direct_test + whole_claim) --
    the only shape `is_decisive_refutation` accepts. That is deliberate: for `refuted`, a
    NON-decisive dispute is a qualifying BASIS but not a refutation, so a non-decisive default would
    have made the polarity control below assert two things at once.

    `admissible=False` makes it an authored assertion with no `confidence` -- excluded by the belief
    policy's confidence gate (`_authored_assertion_counts`), so it never reaches `support_units`.
    A REAL policy exclusion, not a synthetic one.
    """

    stance: str = "supports"
    on: str = "hypothesis"          # "hypothesis" | "core" | "rival"
    admissible: bool = True


def _frontmatter(**fields: object) -> str:
    return f"---\n{yaml.safe_dump(fields, sort_keys=False)}---\n\n# t\n"


def _write(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _target_ref(on: str) -> str:
    return {"hypothesis": HYPOTHESIS, "core": CORE, "rival": RIVAL}[on]


def _write_unit(root: Path, index: int, unit: Unit) -> None:
    fields: dict[str, object] = {
        "id": f"evidence-line:e{index}",
        "kind": "evidence-line",
        "title": f"e{index}",
        "created": "2026-07-13",
        "updated": "2026-07-13",
        "stance": unit.stance,
        "target": _target_ref(unit.on),
        "evidence_role": "direct_test",
        "strength": "strong",
        "independence": "independent",
        "independence_group": f"g{index}",
    }
    if unit.stance == "disputes":
        fields["dispute_scope"] = "whole_claim"
    if unit.admissible:
        fields["evidence_type"] = "empirical_data_evidence"
    else:
        # An authored assertion with NO confidence: the policy's gate rejects it outright.
        fields["evidence_type"] = "expert_judgment"
    _write(root, f"entities/evidence-lines/e{index}.md", _frontmatter(**fields))


def build(
    root: Path,
    *,
    verdict: str | None = None,
    units: tuple[Unit, ...] = (),
    members: tuple[str, ...] = (),
    falsified_member: str | None = None,
) -> Path:
    """Write a project, materialize it, and return the PROJECT ROOT.

    `members` names the roles of the proposition members to create.
    """
    _write(root, "science.yaml", yaml.safe_dump({"name": "demo", "id": "demo"}))

    hypothesis: dict[str, object] = {
        "id": HYPOTHESIS,
        "kind": "hypothesis",
        "title": "x",
        "created": "2026-07-13",
        "updated": "2026-07-13",
        "status": "complete" if verdict else "active",
    }
    if verdict:
        hypothesis["verdict"] = verdict
    _write(root, "entities/hypotheses/0001-x.md", _frontmatter(**hypothesis))

    # A member reaches its frame through the PROPOSITION's `discusses` (reverse cito:discusses).
    # A bare string is core; an object carries the explicit role. A hypothesis has no
    # `propositions:` field -- only a mechanism does -- so this is the ONLY authoring path.
    for role in members:
        ref = _target_ref(role)
        discusses: list[object] = (
            [HYPOTHESIS] if role == "core" else [{"frame": HYPOTHESIS, "role": "rival"}]
        )
        _write(
            root,
            f"entities/propositions/{role}.md",
            _frontmatter(
                id=ref, kind="proposition", title=role,
                created="2026-07-13", updated="2026-07-13", discusses=discusses,
            ),
        )

    for index, unit in enumerate(units):
        _write_unit(root, index, unit)

    if falsified_member is not None:
        _write(
            root,
            "entities/falsifications/f1.md",
            _frontmatter(
                id="falsification:f1", kind="falsification", title="f1",
                created="2026-07-13", updated="2026-07-13",
                falsifies=_target_ref(falsified_member),
                predicted="p", observed="o", decision="reject",
            ),
        )

    assert materialize_graph(root).is_file()
    return root


def trig(root: Path) -> Path:
    # The path the CHECK hardcodes (`_load_belief_graphs`). Asserting against it here is asserting
    # the contract the check actually depends on, not a path this test invented.
    return root / "knowledge" / "graph.trig"


def results(root: Path) -> list:
    ctx = ValidateContext.from_project_root(root, strict=False, verbose=False)
    return list(check_verdict_agreement(ctx))


def rules(root: Path) -> set[str]:
    return {result.rule for result in results(root)}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return tmp_path


# ---------------------------------------------------------------------------------------------
# the surface itself: without the triple, EVERY test below would pass vacuously
# ---------------------------------------------------------------------------------------------


def test_a_verdict_REACHES_the_graph(project: Path) -> None:
    # The check reads `sci:verdict`. Without the emission it reads None, `continue`s, and yields
    # nothing -- forever, silently, for every input. This is the gate on the whole suite.
    root = build(project, verdict="supported")
    dataset = Dataset()
    dataset.parse(source=str(trig(root)), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    uri = URIRef(PROJECT_NS["hypothesis/0001-x"])
    assert str(next(knowledge.objects(uri, SCI_NS.verdict))) == "supported"


def test_an_ABSENT_verdict_is_not_a_finding(project: Path) -> None:
    # Absence == "not yet assessed". The common case, and it must be silent.
    assert results(build(project, verdict=None, units=(Unit(),))) == []


# ---------------------------------------------------------------------------------------------
# a basis is not merely an EDGE — three ways to have one and still have nothing
# ---------------------------------------------------------------------------------------------


def test_an_edge_of_the_WRONG_POLARITY_is_not_a_basis(project: Path) -> None:
    # A `supports` line is not a basis for `refuted`. `if not units` -- the drafted body -- passes.
    # `disagrees-with-computed` fires too (matrix, `refuted` row: no decisive refutation and no
    # linked falsification -- a lone `supports` unit is neither).
    root = build(project, verdict="refuted", units=(Unit(stance="supports"),))
    assert rules(root) == {"verdict.missing-basis", "verdict.disagrees-with-computed"}


def test_a_REFUTING_edge_IS_a_basis_for_refuted(project: Path) -> None:
    # The POLARITY control: identical but for the stance. Silence here is what proves the test above
    # is about polarity, and not about `refuted` being unsatisfiable.
    assert results(build(project, verdict="refuted", units=(Unit(stance="disputes"),))) == []


def test_an_INADMISSIBLE_unit_is_not_a_basis(project: Path) -> None:
    # Excluded by the belief policy => it does not compose => it cannot adjudicate. And because it
    # does not compose, the composed belief does not support `supported` either.
    root = build(project, verdict="supported", units=(Unit(admissible=False),))
    assert rules(root) == {"verdict.missing-basis", "verdict.disagrees-with-computed"}


def test_an_ADMISSIBLE_unit_IS_a_basis(project: Path) -> None:
    # The ADMISSIBILITY control: same stance, same scope -- admitted by the policy.
    assert results(build(project, verdict="supported", units=(Unit(admissible=True),))) == []


def test_evidence_on_a_RIVAL_member_is_not_a_basis(project: Path) -> None:
    # Scope: the hypothesis or its CORE members. A rival adjudicates nothing about THIS hypothesis
    # -- and `belief_for_entity` already excludes rivals from the conjunction, so a check that
    # counted them would contradict the composition it claims to read.
    root = build(project, verdict="supported", units=(Unit(on="rival"),), members=("rival",))
    assert rules(root) == {"verdict.missing-basis", "verdict.disagrees-with-computed"}


def test_evidence_on_a_CORE_member_IS_a_basis(project: Path) -> None:
    # The SCOPE control. Without it, the test above passes for a payload that has no basis at all.
    root = build(project, verdict="supported", units=(Unit(on="core"),), members=("core",))
    assert results(root) == []


def test_a_FALSIFICATION_on_a_core_member_IS_a_basis_for_refuted(project: Path) -> None:
    # The SECOND limb of the basis contract -- the "explicitly linked negative adjudication" the
    # `refuted` row calls for -- and the one the plan's own test list never exercised. Note there is
    # no evidence line at all here: the falsification alone discharges both rules.
    #
    # A falsification ON THE HYPOTHESIS cannot exist and is not looked for: `FalsificationEntity`
    # requires `falsifies`, and materialization hard-raises unless it resolves to a proposition.
    root = build(project, verdict="refuted", members=("core",), falsified_member="core")
    assert results(root) == []


def test_a_FALSIFICATION_is_NOT_a_basis_for_supported(project: Path) -> None:
    # The POLARITY control for the falsification limb: a negative adjudication cannot ground a
    # positive verdict. Without this, the limb above would admit a falsification for ANY verdict.
    root = build(project, verdict="supported", members=("core",), falsified_member="core")
    assert "verdict.missing-basis" in rules(root)


# ---------------------------------------------------------------------------------------------
# the rules are INDEPENDENT — one may not mask another
# ---------------------------------------------------------------------------------------------


def test_the_three_rules_fire_INDEPENDENTLY(project: Path) -> None:
    # A `supported` verdict, no qualifying basis, AND an unresolved decisive refutation.
    #
    # ALL THREE fire. The emitter has no `continue` between the rules, so each is evaluated on its
    # own facts:
    #   - no qualifying basis at all                          -> missing-basis           (WARN)
    #   - `supported` over a decisive refutation              -> refutation-masked       (ERROR)
    #   - and the composed belief plainly is not `supported`  -> disagrees-with-computed (WARN)
    #
    # Expecting only two would reject a correct implementation, and the only way to make a two-rule
    # oracle true is to SUPPRESS the third -- the masking this suite forbids. Skipping the hard
    # invariant for exactly the files with the weakest evidentiary footing would suppress it where
    # it matters most.
    root = build(project, verdict="supported", units=(Unit(stance="disputes"),))

    assert rules(root) == {
        "verdict.missing-basis",
        "verdict.refutation-masked",
        "verdict.disagrees-with-computed",
    }
    assert {r.rule: r.severity for r in results(root)} == {
        "verdict.missing-basis": Severity.WARN,            # >=11 of 15 cannot satisfy it -- never ERROR
        "verdict.refutation-masked": Severity.ERROR,       # the one hard invariant
        "verdict.disagrees-with-computed": Severity.WARN,  # explanatory, never a ceiling
    }


def test_a_refutation_DIRECTLY_on_the_hypothesis_is_caught_despite_bundle_members(
    project: Path,
) -> None:
    # THE trap. With core members, `belief_for_entity` takes the bundle branch and NEVER calls
    # `collect_evidence_units([hypothesis_uri])` -- so a decisive refutation attached to the
    # hypothesis ITSELF is invisible to the composition. Bundle dispatch would hide the very thing
    # `refutation-masked` exists to catch, and the suite would be green.
    root = build(
        project,
        verdict="supported",
        units=(Unit(stance="disputes", on="hypothesis"),),
        members=("core",),
    )
    assert "verdict.refutation-masked" in rules(root)


# ---------------------------------------------------------------------------------------------
# the matrix is NOT a ladder
# ---------------------------------------------------------------------------------------------


def test_partially_supported_with_a_refuted_CORE_member_is_NOT_a_disagreement(
    project: Path,
) -> None:
    # On an ordinal reading this is a contradiction. It is not: a decisively refuted constituent is
    # exactly what `partially-supported` ASSERTS. Ordinalizing the verdict produces this false
    # positive, which is why the check reports a MATRIX and never compares rungs.
    root = build(
        project,
        verdict="partially-supported",
        units=(Unit(stance="disputes", on="core"),),
        members=("core",),
    )
    assert "verdict.disagrees-with-computed" not in rules(root)


def test_partially_supported_with_NOTHING_partial_IS_a_disagreement(project: Path) -> None:
    # The other side -- without it, the test above is satisfied by a check that never fires at all.
    root = build(project, verdict="partially-supported", units=(Unit(stance="supports"),))
    assert "verdict.disagrees-with-computed" in rules(root)


def test_refuted_from_ONE_decisive_test_is_NOT_ceilinged(project: Path) -> None:
    # A single-source ceiling applied to `refuted` would flag the STRONGEST POSSIBLE refutation as
    # unfounded. One decisive independent test legitimately establishes a refutation. This is the
    # deleted `belief.single-source-ceiling` NOT coming back through the side door.
    assert results(build(project, verdict="refuted", units=(Unit(stance="disputes"),))) == []


def test_weakened_is_never_inferred_from_ONE_snapshot(project: Path) -> None:
    # `weakened` asserts a CHANGE. With no prior belief snapshot there is no trajectory to read, so
    # the check may report only "no dispute exists" -- never "no weakening occurred".
    assert results(build(project, verdict="weakened", units=(Unit(stance="disputes"),))) == []


def test_weakened_with_NO_dispute_at_all_IS_a_disagreement(project: Path) -> None:
    # The control: the one thing a single snapshot CAN say about `weakened` is that nothing disputes
    # the hypothesis at all. Without this, the test above passes for a check that never fires.
    root = build(project, verdict="weakened", units=(Unit(stance="supports"),))
    assert "verdict.disagrees-with-computed" in rules(root)


# ---------------------------------------------------------------------------------------------
# severity and the gate ladder
# ---------------------------------------------------------------------------------------------


def test_missing_basis_is_WARN_and_UNGATED(project: Path) -> None:
    # >= 11 of the 15 migrating verdicts CANNOT satisfy this rule. An ERROR here would be an
    # uncertified instrument failing real builds -- the original incident, verbatim.
    #
    # FILTER for the rule under test. `supported` + no basis emits `disagrees-with-computed` too, so
    # asserting over the whole result list would test the OTHER rule's existence as a side effect
    # and fail on a correct emitter.
    root = build(project, verdict="supported")
    missing = [r for r in results(root) if r.rule == "verdict.missing-basis"]

    assert [r.severity for r in missing] == [Severity.WARN]
    assert "verdict.missing-basis" not in cumulative_rules("hygiene")


def test_refutation_masked_IS_gated_at_hygiene() -> None:
    # The one hard invariant, inheriting the gated ERROR `belief.refutation-masked` held before
    # Task 2b removed it.
    assert "verdict.refutation-masked" in cumulative_rules("hygiene")


def test_disagrees_with_computed_is_NEVER_gated() -> None:
    # A disagreement is information, not a fault. Gating it would make the check a ceiling on the
    # authored verdict -- which is exactly what rev 8 point 4 forbids.
    assert "verdict.disagrees-with-computed" not in cumulative_rules("hygiene")
