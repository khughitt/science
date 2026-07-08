"""Controlled vocabulary for the `capability_scope` marker.

An entity carries `capability_scope` to positively declare that it sits OUTSIDE
the molecular assay/modality capability gate: its empty provided/required
capabilities are intentional and complete, not a pending annotation. See
docs/plans/2026-07-07-capability-scope-marker-design.md.

Type II values are terminal ("measures nothing"); Type I values are transitional
("measures something non-molecular") and are the forward pointers to a future
outcome/clinical axis.
"""

from __future__ import annotations

CAPABILITY_SCOPE_VALUES: dict[str, str] = {
    # Type II — terminal not-applicable (no measurement axis at all)
    "reference-substrate": (
        "External curated catalog, annotation track, LD panel, gene-set "
        "collection, or corpus/panel metadata registry; enables analysis, "
        "measures nothing itself."
    ),
    "derived-product": (
        "A project-produced result artifact with no independent measurement "
        "capability (NOT merely anything downstream of assays)."
    ),
    "methodological": (
        "Question answered by an algorithm / statistic / pipeline-design / "
        "census / vocabulary-curation decision over already-derived artifacts; "
        "consumes no assay matrix."
    ),
    "model-system": (
        "In-vivo / functional model or analogy pointer with no catalogued assay."
    ),
    # Type I — transitional (non-molecular measurement; future outcome axis)
    "clinical-outcome": (
        "Clinical labs, survival, treatment response / MRD endpoints, symptom / "
        "QoL, frailty, drug-dosing."
    ),
    "epidemiological": "Population incidence / prevalence / burden / exposure.",
    "behavioral-instrument": (
        "Questionnaire / self-report / neurocognitive-task / wearable / EMA."
    ),
}

TYPE_II_SCOPES: frozenset[str] = frozenset(
    {"reference-substrate", "derived-product", "methodological", "model-system"}
)
TYPE_I_SCOPES: frozenset[str] = frozenset(
    {"clinical-outcome", "epidemiological", "behavioral-instrument"}
)
VALID_SCOPES: frozenset[str] = frozenset(CAPABILITY_SCOPE_VALUES)


def is_valid_scope(value: object) -> bool:
    """True iff `value` is one of the controlled capability_scope strings."""
    return isinstance(value, str) and value in VALID_SCOPES
