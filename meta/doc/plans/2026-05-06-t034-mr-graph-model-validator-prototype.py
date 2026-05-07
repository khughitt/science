#!/usr/bin/env python3
"""
Prototype validator for t034 v1.2 `mr-graph-model` extension role-permission and
conditional-required-field rules.

Second prototype slice. Sister to `2026-05-06-t034-causal-graph-validator-prototype.py`.
Where that prototype targeted *structural* rules on the `causal-graph` extension
(graph_object_type enum, edge-role compatibility, promotion-only roles), this one
targets the load-bearing half of the natural-systems alignment commitment:
role-permission rules (validation_role × extension state × effective_codes), plus
the conditional-required-field machinery added in v1.2 (P-pilot-1).

Rules implemented:

- mr-1: graph_object_type ∈ {CPDAG, DAG, graph-posterior} (mr-graph-model's slice
        of the t034 enum — narrower than the causal-graph enum).
- mr-2: validation_role ∈ {prioritize-attention, record-only}; strengthen-belief,
        gate-update, quality-record-only forbidden directly on this payload.
- mr-3: co-required extensions {causal-graph, statistical-uncertainty} present.
- mr-4: required fields always-required: exposure_set, outcome_set,
        instrument_validity_assumptions, pleiotropy_model, direction_constraint,
        graph_object_type.
- mr-5: required fields conditionally-required: instrument_set,
        summary_statistic_provenance — required UNLESS
        extracted-from-summary-only ∈ effective_codes.
- mr-6 (semantic): instrument-assumption-risk MUST be in core.reason_codes
        whenever this extension is loaded.
- mr-7 (semantic): pleiotropy-untested ↔ pleiotropy_model ∈
        {none-assumed, not-modelled}.
- mr-8 (semantic): pleiotropy-unspecified ↔ pleiotropy_model = unspecified.
- mr-9 (semantic): reverse-causation-assumed ↔ direction_constraint =
        exposures-to-outcomes-only AND direction-inherent-from-iv-class NOT in
        instrument_validity_assumptions.

mr-2 is the rule the natural-systems "asserted vs verified" thread cares about —
a payload that *says* strengthen-belief on a stage-(a) MR posterior must be
rejected at validate-time, not flagged in prose.

Effective codes: for this stage-(a) primary, we treat core.reason_codes as the
effective set. Cross-payload reason-code propagation is out of scope here (it's
the third prototype slice).

Standalone runner. NOT integrated into meta/validate.sh; this is a study.

Run with:  python meta/doc/plans/2026-05-06-t034-mr-graph-model-validator-prototype.py
Exits 0 if all tests match expectations; nonzero otherwise.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Literal

EXT_KEY = "extension/mr-graph-model"

PERMITTED_ROLES: set[str] = {"prioritize-attention", "record-only"}
FORBIDDEN_ROLES: set[str] = {"strengthen-belief", "gate-update", "quality-record-only"}

CO_REQUIRED_EXTENSIONS: set[str] = {"causal-graph", "statistical-uncertainty"}

GRAPH_OBJECT_TYPES_FOR_MR: set[str] = {"CPDAG", "DAG", "graph-posterior"}

ALWAYS_REQUIRED_FIELDS: tuple[str, ...] = (
    "exposure_set", "outcome_set", "instrument_validity_assumptions",
    "pleiotropy_model", "direction_constraint", "graph_object_type",
)

CONDITIONALLY_REQUIRED_FIELDS: tuple[str, ...] = (
    "instrument_set", "summary_statistic_provenance",
)

PLEIOTROPY_BLOCKING_VALUES: set[str] = {"none-assumed", "not-modelled"}


@dataclass(frozen=True)
class Issue:
    severity: Literal["error", "warning"]
    path: str
    rule: str
    msg: str

    def __str__(self) -> str:
        return f"[{self.severity:5}] {self.rule:6} {self.path}: {self.msg}"


def _effective_codes(payload: dict) -> set[str]:
    """Stage-(a) effective codes = core.reason_codes (no upstream propagation here)."""
    return set(payload.get("core", {}).get("reason_codes") or [])


def _is_nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, tuple, set, dict, str)):
        return len(value) > 0
    return True


def validate_mr_graph_model(payload: dict) -> list[Issue]:
    issues: list[Issue] = []

    if EXT_KEY not in payload:
        return issues  # extension absent — these rules do not apply

    core = payload.get("core", {}) or {}
    ext = payload[EXT_KEY] or {}
    extensions = set(core.get("extensions") or [])
    eff_codes = _effective_codes(payload)
    summary_only = "extracted-from-summary-only" in eff_codes

    # mr-3: co-required extensions
    missing_co = CO_REQUIRED_EXTENSIONS - extensions
    if missing_co:
        issues.append(Issue("error", "core.extensions", "mr-3",
                            f"mr-graph-model requires co-loaded extensions {sorted(CO_REQUIRED_EXTENSIONS)}; "
                            f"missing: {sorted(missing_co)}"))

    # mr-2: validation_role permission
    role = core.get("validation_role")
    if role is None:
        issues.append(Issue("error", "core.validation_role", "mr-2",
                            "validation_role is required"))
    elif role in FORBIDDEN_ROLES:
        issues.append(Issue("error", "core.validation_role", "mr-2",
                            f"validation_role {role!r} forbidden on mr-graph-model "
                            f"(stage (a) graph posterior cannot strengthen belief; "
                            f"permitted: {sorted(PERMITTED_ROLES)})"))
    elif role not in PERMITTED_ROLES:
        issues.append(Issue("error", "core.validation_role", "mr-2",
                            f"validation_role {role!r} not in permitted set "
                            f"{sorted(PERMITTED_ROLES)}"))

    # mr-4: always-required fields
    for f in ALWAYS_REQUIRED_FIELDS:
        if not _is_nonempty(ext.get(f)):
            issues.append(Issue("error", f"{EXT_KEY}.{f}", "mr-4",
                                f"required field {f!r} is missing or empty"))

    # mr-5: conditionally-required fields
    for f in CONDITIONALLY_REQUIRED_FIELDS:
        if not _is_nonempty(ext.get(f)):
            if not summary_only:
                issues.append(Issue("error", f"{EXT_KEY}.{f}", "mr-5",
                                    f"field {f!r} required unless extracted-from-summary-only "
                                    f"in effective_codes"))

    # mr-1: graph_object_type narrower enum
    got = ext.get("graph_object_type")
    if got is not None and got not in GRAPH_OBJECT_TYPES_FOR_MR:
        issues.append(Issue("error", f"{EXT_KEY}.graph_object_type", "mr-1",
                            f"{got!r} not in mr-graph-model permitted set "
                            f"{sorted(GRAPH_OBJECT_TYPES_FOR_MR)}"))

    # mr-6 (semantic): instrument-assumption-risk must be declared
    if "instrument-assumption-risk" not in eff_codes:
        issues.append(Issue("error", "core.reason_codes", "mr-6",
                            "instrument-assumption-risk must be declared whenever "
                            "mr-graph-model extension is loaded"))

    # mr-7 (semantic): pleiotropy-untested ↔ pleiotropy_model ∈ blocking
    pmodel = ext.get("pleiotropy_model")
    has_untested = "pleiotropy-untested" in eff_codes
    if pmodel in PLEIOTROPY_BLOCKING_VALUES and not has_untested:
        issues.append(Issue("error", "core.reason_codes", "mr-7",
                            f"pleiotropy_model={pmodel!r} requires reason code "
                            f"'pleiotropy-untested' (blocking) to be declared"))
    if pmodel not in PLEIOTROPY_BLOCKING_VALUES and has_untested:
        issues.append(Issue("error", "core.reason_codes", "mr-7",
                            f"reason code 'pleiotropy-untested' declared but "
                            f"pleiotropy_model={pmodel!r} is not in {sorted(PLEIOTROPY_BLOCKING_VALUES)}"))

    # mr-8 (semantic): pleiotropy-unspecified ↔ pleiotropy_model = unspecified
    has_unspec = "pleiotropy-unspecified" in eff_codes
    if pmodel == "unspecified" and not has_unspec:
        issues.append(Issue("error", "core.reason_codes", "mr-8",
                            "pleiotropy_model='unspecified' requires reason code "
                            "'pleiotropy-unspecified' to be declared"))
    if pmodel != "unspecified" and has_unspec:
        issues.append(Issue("error", "core.reason_codes", "mr-8",
                            f"reason code 'pleiotropy-unspecified' declared but "
                            f"pleiotropy_model={pmodel!r} is not 'unspecified'"))

    # mr-9 (semantic): reverse-causation-assumed ↔ direction-constraint and not direction-inherent
    dc = ext.get("direction_constraint")
    iva = set(ext.get("instrument_validity_assumptions") or [])
    has_rca = "reverse-causation-assumed" in eff_codes
    should_rca = (dc == "exposures-to-outcomes-only"
                  and "direction-inherent-from-iv-class" not in iva)
    if should_rca and not has_rca:
        issues.append(Issue("error", "core.reason_codes", "mr-9",
                            "direction_constraint='exposures-to-outcomes-only' without "
                            "'direction-inherent-from-iv-class' in instrument_validity_assumptions "
                            "requires reason code 'reverse-causation-assumed'"))
    if has_rca and not should_rca:
        issues.append(Issue("error", "core.reason_codes", "mr-9",
                            "reason code 'reverse-causation-assumed' declared but "
                            "either direction_constraint != 'exposures-to-outcomes-only' "
                            "or 'direction-inherent-from-iv-class' is in instrument_validity_assumptions"))

    return issues


# -----------------------------------------------------------------------------
# Test cases — each returns (name, payload, expected_rules_fired)
# -----------------------------------------------------------------------------

def _base_payload(**core_overrides) -> dict:
    """Helper: build a minimal valid mr-graph-model payload, then apply overrides."""
    p = {
        "core": {
            "extensions": ["mr-graph-model", "causal-graph", "statistical-uncertainty"],
            "validation_role": "prioritize-attention",
            "reason_codes": ["instrument-assumption-risk"],
        },
        "extension/mr-graph-model": {
            "exposure_set": ["var:exposure-1"],
            "outcome_set": ["var:outcome-1"],
            "instrument_set": ["snp:rs1"],
            "instrument_validity_assumptions": ["relevance", "exclusion"],
            "pleiotropy_model": "mr-egger",
            "direction_constraint": "bidirectional-search",
            "graph_object_type": "graph-posterior",
            "summary_statistic_provenance": "dataset:gwas-1",
        },
    }
    p["core"].update(core_overrides)
    return p


def t01_minimal_valid() -> tuple[str, dict, set[str]]:
    return ("01-minimal-valid", _base_payload(), set())


def t02_strengthen_forbidden() -> tuple[str, dict, set[str]]:
    """The natural-systems load-bearing case: strengthen-belief on stage-(a) MR posterior."""
    p = _base_payload(validation_role="strengthen-belief")
    return ("02-strengthen-forbidden", p, {"mr-2"})


def t03_gate_update_forbidden() -> tuple[str, dict, set[str]]:
    p = _base_payload(validation_role="gate-update")
    return ("03-gate-update-forbidden", p, {"mr-2"})


def t04_quality_record_forbidden() -> tuple[str, dict, set[str]]:
    """quality-record-only is a t034 graph-diagnostic role, not for mr-graph-model."""
    p = _base_payload(validation_role="quality-record-only")
    return ("04-quality-record-forbidden", p, {"mr-2"})


def t05_record_only_permitted() -> tuple[str, dict, set[str]]:
    p = _base_payload(validation_role="record-only")
    return ("05-record-only-permitted", p, set())


def t06_missing_co_required_ext() -> tuple[str, dict, set[str]]:
    p = _base_payload()
    p["core"]["extensions"] = ["mr-graph-model", "causal-graph"]  # no statistical-uncertainty
    return ("06-missing-co-required-ext", p, {"mr-3"})


def t07_missing_instrument_set_no_summary_gate() -> tuple[str, dict, set[str]]:
    """instrument_set missing without extracted-from-summary-only — required."""
    p = _base_payload()
    del p["extension/mr-graph-model"]["instrument_set"]
    return ("07-missing-instrument-set-no-summary-gate", p, {"mr-5"})


def t08_missing_instrument_set_with_summary_gate() -> tuple[str, dict, set[str]]:
    """instrument_set missing WITH extracted-from-summary-only — relaxed; passes."""
    p = _base_payload()
    del p["extension/mr-graph-model"]["instrument_set"]
    p["core"]["reason_codes"] = ["instrument-assumption-risk", "extracted-from-summary-only"]
    return ("08-missing-instrument-set-with-summary-gate", p, set())


def t09_missing_provenance_with_summary_gate() -> tuple[str, dict, set[str]]:
    """summary_statistic_provenance missing WITH extracted-from-summary-only — relaxed."""
    p = _base_payload()
    del p["extension/mr-graph-model"]["summary_statistic_provenance"]
    p["core"]["reason_codes"] = ["instrument-assumption-risk", "extracted-from-summary-only"]
    return ("09-missing-provenance-with-summary-gate", p, set())


def t10_missing_provenance_no_summary_gate() -> tuple[str, dict, set[str]]:
    p = _base_payload()
    del p["extension/mr-graph-model"]["summary_statistic_provenance"]
    return ("10-missing-provenance-no-summary-gate", p, {"mr-5"})


def t11_always_required_missing() -> tuple[str, dict, set[str]]:
    """exposure_set is always required — even with summary gate."""
    p = _base_payload()
    del p["extension/mr-graph-model"]["exposure_set"]
    p["core"]["reason_codes"] = ["instrument-assumption-risk", "extracted-from-summary-only"]
    return ("11-always-required-missing-with-gate", p, {"mr-4"})


def t12_pleiotropy_blocking_code_missing() -> tuple[str, dict, set[str]]:
    """pleiotropy_model=none-assumed without pleiotropy-untested — must declare."""
    p = _base_payload()
    p["extension/mr-graph-model"]["pleiotropy_model"] = "none-assumed"
    return ("12-pleiotropy-blocking-code-missing", p, {"mr-7"})


def t13_pleiotropy_blocking_code_correct() -> tuple[str, dict, set[str]]:
    p = _base_payload()
    p["extension/mr-graph-model"]["pleiotropy_model"] = "not-modelled"
    p["core"]["reason_codes"] = ["instrument-assumption-risk", "pleiotropy-untested"]
    return ("13-pleiotropy-blocking-code-correct", p, set())


def t14_pleiotropy_untested_overdeclared() -> tuple[str, dict, set[str]]:
    """pleiotropy-untested declared but pleiotropy_model=mr-egger (handled) — false alarm."""
    p = _base_payload()
    p["core"]["reason_codes"] = ["instrument-assumption-risk", "pleiotropy-untested"]
    return ("14-pleiotropy-untested-overdeclared", p, {"mr-7"})


def t15_pleiotropy_unspecified_correct() -> tuple[str, dict, set[str]]:
    """Adapted Zuber pilot: pleiotropy_model=unspecified + pleiotropy-unspecified code."""
    p = _base_payload()
    p["extension/mr-graph-model"]["pleiotropy_model"] = "unspecified"
    p["core"]["reason_codes"] = ["instrument-assumption-risk", "pleiotropy-unspecified",
                                 "extracted-from-summary-only"]
    return ("15-pleiotropy-unspecified-correct", p, set())


def t16_pleiotropy_unspecified_code_missing() -> tuple[str, dict, set[str]]:
    p = _base_payload()
    p["extension/mr-graph-model"]["pleiotropy_model"] = "unspecified"
    return ("16-pleiotropy-unspecified-code-missing", p, {"mr-8"})


def t17_pleiotropy_unspecified_overdeclared() -> tuple[str, dict, set[str]]:
    p = _base_payload()
    p["core"]["reason_codes"] = ["instrument-assumption-risk", "pleiotropy-unspecified"]
    return ("17-pleiotropy-unspecified-overdeclared", p, {"mr-8"})


def t18_reverse_causation_required() -> tuple[str, dict, set[str]]:
    """direction_constraint=exposures-to-outcomes-only without direction-inherent → require code."""
    p = _base_payload()
    p["extension/mr-graph-model"]["direction_constraint"] = "exposures-to-outcomes-only"
    return ("18-reverse-causation-required", p, {"mr-9"})


def t19_reverse_causation_carve_out() -> tuple[str, dict, set[str]]:
    """direction-inherent-from-iv-class present → reverse-causation-assumed NOT required."""
    p = _base_payload()
    p["extension/mr-graph-model"]["direction_constraint"] = "exposures-to-outcomes-only"
    p["extension/mr-graph-model"]["instrument_validity_assumptions"] = [
        "relevance", "exclusion", "direction-inherent-from-iv-class",
    ]
    return ("19-reverse-causation-carve-out", p, set())


def t20_reverse_causation_overdeclared() -> tuple[str, dict, set[str]]:
    """reverse-causation-assumed declared with bidirectional-search — false alarm."""
    p = _base_payload()
    p["core"]["reason_codes"] = ["instrument-assumption-risk", "reverse-causation-assumed"]
    return ("20-reverse-causation-overdeclared", p, {"mr-9"})


def t21_instrument_assumption_risk_missing() -> tuple[str, dict, set[str]]:
    p = _base_payload()
    p["core"]["reason_codes"] = []
    return ("21-instrument-assumption-risk-missing", p, {"mr-6"})


def t22_graph_object_type_out_of_slice() -> tuple[str, dict, set[str]]:
    """ADMG is in t034's broad enum but not in mr-graph-model's narrower slice."""
    p = _base_payload()
    p["extension/mr-graph-model"]["graph_object_type"] = "ADMG"
    return ("22-graph-object-type-out-of-slice", p, {"mr-1"})


def t23_no_extension_loaded() -> tuple[str, dict, set[str]]:
    """Payload doesn't load mr-graph-model — rules don't apply."""
    return ("23-no-extension-loaded", {
        "core": {"extensions": ["causal-discovery-run", "causal-graph"],
                 "validation_role": "prioritize-attention",
                 "reason_codes": []},
    }, set())


def t24_zuber_pilot_adapted() -> tuple[str, dict, set[str]]:
    """Adapted Zuber2025: full paper-summary extraction with all v1.2 relaxations engaged."""
    return ("24-zuber-pilot-adapted", {
        "core": {
            "extensions": ["mr-graph-model", "causal-graph", "statistical-uncertainty"],
            "validation_role": "prioritize-attention",
            "reason_codes": [
                "instrument-assumption-risk",
                "pleiotropy-unspecified",
                "extracted-from-summary-only",
            ],
        },
        "extension/mr-graph-model": {
            "exposure_set": ["var:lipid-traits"],
            "outcome_set": ["var:cardiovascular-outcomes"],
            "instrument_validity_assumptions": ["relevance", "direction-inherent-from-iv-class"],
            "pleiotropy_model": "unspecified",
            "direction_constraint": "exposures-to-outcomes-only",
            "graph_object_type": "graph-posterior",
            # instrument_set, summary_statistic_provenance: omitted, gated by extracted-from-summary-only
        },
    }, set())


def t25_zuber_pilot_strengthen_attempt() -> tuple[str, dict, set[str]]:
    """Adapted Zuber pilot but with strengthen-belief — must reject."""
    _, p, _ = t24_zuber_pilot_adapted()
    p["core"]["validation_role"] = "strengthen-belief"
    return ("25-zuber-pilot-strengthen-attempt", p, {"mr-2"})


TESTS = [
    t01_minimal_valid, t02_strengthen_forbidden, t03_gate_update_forbidden,
    t04_quality_record_forbidden, t05_record_only_permitted,
    t06_missing_co_required_ext,
    t07_missing_instrument_set_no_summary_gate, t08_missing_instrument_set_with_summary_gate,
    t09_missing_provenance_with_summary_gate, t10_missing_provenance_no_summary_gate,
    t11_always_required_missing,
    t12_pleiotropy_blocking_code_missing, t13_pleiotropy_blocking_code_correct,
    t14_pleiotropy_untested_overdeclared,
    t15_pleiotropy_unspecified_correct, t16_pleiotropy_unspecified_code_missing,
    t17_pleiotropy_unspecified_overdeclared,
    t18_reverse_causation_required, t19_reverse_causation_carve_out,
    t20_reverse_causation_overdeclared,
    t21_instrument_assumption_risk_missing,
    t22_graph_object_type_out_of_slice, t23_no_extension_loaded,
    t24_zuber_pilot_adapted, t25_zuber_pilot_strengthen_attempt,
]


def main() -> int:
    passed = 0
    failed: list[str] = []

    print(f"t034 v1.2 mr-graph-model validator prototype — running {len(TESTS)} tests\n")

    for tc in TESTS:
        name, payload, expected_rules = tc()
        issues = validate_mr_graph_model(payload)
        actual_rules = {i.rule for i in issues if i.severity == "error"}

        if actual_rules == expected_rules:
            passed += 1
            status = "PASS"
        else:
            failed.append(name)
            status = "FAIL"

        print(f"{status} {name}")
        if expected_rules:
            print(f"  expected error rules: {sorted(expected_rules)}")
        if actual_rules:
            print(f"  actual   error rules: {sorted(actual_rules)}")
        for issue in issues:
            print(f"    {issue}")
        if not issues:
            print(f"    (no issues)")
        print()

    print(f"---\n{passed}/{len(TESTS)} passed")
    if failed:
        print(f"FAILED: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
