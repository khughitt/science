#!/usr/bin/env python3
"""
Prototype validator for t034 v1.4 cross-payload reason-code propagation.

Third validator slice. Sister to:
- meta/doc/plans/historical/2026-05-06-t034-causal-graph-validator-prototype.py (slice 1: structural)
- meta/doc/plans/historical/2026-05-06-t034-mr-graph-model-validator-prototype.py (slice 2: role-permission)

This slice closes the natural-systems alignment commitment for t034: it implements
`effective_codes` computation across a payload graph (declared ∪ auto-injected ∪
propagated upstream blocking codes minus retired codes), then enforces the
consumer-side `causal-effect-estimate.strengthen-belief` rule against that state.

v1.4 contract reminder:
    effective_codes(p) = declared(p) ∪ auto_injected(p) ∪ propagated_blocking(upstream(p))
                       \\ retired_by(p)

Where:
- declared(p)       = p.core.reason_codes (author-written, post-v1.3 must EXCLUDE auto-injected;
                      v1.4 hard-errors on hand-writing per P1.4-b)
- auto_injected(p)  = ∪ over loaded extensions of AUTO_INJECTION[ext]
- propagated_blocking(upstream(p)) = ∪ over p.core.input_artifact_refs of
                                     {c ∈ effective_codes(upstream) : c is blocking}
- retired_by(p)     = codes p resolves on its content. v1.4 retirement table:
                      (1) causal-identification with identification_status ∈
                          {identified, partially-identified} retires identification-missing;
                      (2) mr-analysis with pleiotropy_handling != unhandled retires
                          pleiotropy-untested;
                      (3) [P1.4-a] mr-analysis with pleiotropy_handling != unhandled
                          AND upstream mr_graph_payload_ref.instrument_validity_assumptions
                          containing 'relevance' retires instrument-assumption-risk
                          (first retirement reading upstream payload state).

The consumer-side rule under test (the load-bearing case the slice-2 findings called
out as the smallest non-trivial slice-3 test):

    causal-effect-estimate.validation_role: strengthen-belief is permitted iff
    (a) identification_payload_ref.identification_status ∈ {identified, partially-identified}
    (b) effective_codes (post-retirement) excludes identification-missing AND
        instrument-assumption-risk
    (c) estimator_diagnostics is present

**v1.4 patch:**
- _retired_by signature changed: now takes (store, payload) so the iar retirement
  can resolve mr_graph_payload_ref and read its instrument_validity_assumptions.
- test_strengthen_mr_two_stage_iar_finding renamed to test_strengthen_mr_two_stage_iar_retired
  and its assertion flipped: under v1.4, the two-stage MR pattern with valid pleiotropy
  handling and upstream relevance now correctly retires iar, so cee-strengthen-b does
  NOT fire and the consumer rule passes. Fixture updated to populate
  instrument_validity_assumptions and mr_graph_payload_ref so the upstream-state
  check can resolve.

Standalone runner. NOT integrated into meta/validate.sh; this is a study.
The production validator at meta/src/t034_validator/ already implements v1.4.

Run with:  python meta/doc/plans/historical/2026-05-06-t034-effective-codes-validator-prototype.py
Exits 0 if all tests match expectations; nonzero otherwise.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Literal

# v1.3 auto-injection table (P1.3-c)
AUTO_INJECTION: dict[str, set[str]] = {
    "causal-discovery-run": {"identification-missing"},
    "mr-graph-model": {"instrument-assumption-risk"},
    "mr-analysis": {"instrument-assumption-risk"},
    "mechanistic-hypothesis-bundle": {"mechanism-hypothesis-only", "prior-network-dependent"},
}

# Blocking flags from the t034 v1.3 reason-code rollup table.
BLOCKING_CODES: set[str] = {
    "llm-prior-unvalidated",
    "identification-missing",
    "pleiotropy-untested",
    "multiplicity-uncorrected",
    "self-incompatible",
    "mechanism-hypothesis-only",
    "estimand-mismatch",
}


@dataclass(frozen=True)
class Issue:
    severity: Literal["error", "warning"]
    payload_id: str
    path: str
    rule: str
    msg: str

    def __str__(self) -> str:
        return f"[{self.severity:5}] {self.rule:8} {self.payload_id}:{self.path}: {self.msg}"


@dataclass
class Store:
    """Toy payload registry. Real validator backs onto the t022 / t025 stores."""
    payloads: dict[str, dict] = field(default_factory=dict)

    def get(self, pid: str) -> dict | None:
        return self.payloads.get(pid)

    def add(self, pid: str, payload: dict) -> None:
        if pid in self.payloads:
            raise ValueError(f"duplicate payload id {pid!r}")
        self.payloads[pid] = payload


def _loaded_extensions(payload: dict) -> set[str]:
    return set(payload.get("core", {}).get("extensions") or [])


def _auto_injected(payload: dict) -> set[str]:
    out: set[str] = set()
    for ext in _loaded_extensions(payload):
        out |= AUTO_INJECTION.get(ext, set())
    return out


def _retired_by(store: "Store", payload: dict) -> set[str]:
    """Codes this payload resolves. Reads local payload state and (for the v1.4
    P1.4-a iar rule) upstream state via mr_graph_payload_ref."""
    retired: set[str] = set()
    exts = _loaded_extensions(payload)

    # causal-identification with identification_status ∈ {identified, partially-identified}
    # retires propagated identification-missing.
    if "causal-identification" in exts:
        ci = payload.get("extension/causal-identification") or {}
        if ci.get("identification_status") in {"identified", "partially-identified"}:
            retired.add("identification-missing")

    # mr-analysis with pleiotropy_handling != unhandled retires propagated
    # pleiotropy-untested.
    if "mr-analysis" in exts:
        ma = payload.get("extension/mr-analysis") or {}
        if ma.get("pleiotropy_handling") not in {None, "unhandled"}:
            retired.add("pleiotropy-untested")
            # v1.4 P1.4-a: iar retirement also requires upstream relevance.
            mr_ref = ma.get("mr_graph_payload_ref")
            if mr_ref:
                upstream = store.get(mr_ref)
                if upstream is not None:
                    upstream_ext = upstream.get("extension/mr-graph-model") or {}
                    iva = set(upstream_ext.get("instrument_validity_assumptions") or [])
                    if "relevance" in iva:
                        retired.add("instrument-assumption-risk")

    return retired


def effective_codes(store: Store, pid: str, _seen: set[str] | None = None) -> set[str]:
    """Compute effective_codes for a payload, recursing through input_artifact_refs.

    Cycle detection via _seen. A cycle in input_artifact_refs is itself an error
    in the payload graph; here we just halt recursion at the cycle boundary
    rather than diverging.
    """
    seen = set(_seen or set())
    if pid in seen:
        return set()
    seen.add(pid)

    payload = store.get(pid)
    if payload is None:
        return set()

    declared = set(payload.get("core", {}).get("reason_codes") or [])
    auto = _auto_injected(payload)

    propagated: set[str] = set()
    for upstream_ref in payload.get("core", {}).get("input_artifact_refs") or []:
        upstream_eff = effective_codes(store, upstream_ref, seen)
        propagated |= {c for c in upstream_eff if c in BLOCKING_CODES}

    retired = _retired_by(store, payload)

    return (declared | auto | propagated) - retired


def detect_cycle(store: Store, pid: str, _seen: set[str] | None = None) -> str | None:
    """Return the offending payload id if input_artifact_refs has a cycle starting at pid."""
    seen = set(_seen or set())
    if pid in seen:
        return pid
    seen.add(pid)
    payload = store.get(pid)
    if payload is None:
        return None
    for ref in payload.get("core", {}).get("input_artifact_refs") or []:
        cyc = detect_cycle(store, ref, seen)
        if cyc is not None:
            return cyc
    return None


def validate_v13_authoring(payload_id: str, payload: dict) -> list[Issue]:
    """v1.3 P1.3-c: declared codes must NOT contain auto-injected codes for loaded extensions."""
    declared = set(payload.get("core", {}).get("reason_codes") or [])
    auto = _auto_injected(payload)
    overlap = declared & auto
    if not overlap:
        return []
    return [Issue("error", payload_id, "core.reason_codes", "v1.3-auto-inject",
                  f"author wrote auto-injected codes by hand: {sorted(overlap)}; "
                  f"per v1.3 P1.3-c, the validator's contribution-merger adds these")]


def validate_strengthen_cee(store: Store, pid: str) -> list[Issue]:
    """The load-bearing consumer rule.

    causal-effect-estimate.validation_role: strengthen-belief is permitted iff
    (a) identification_payload_ref.identification_status ∈ {identified, partially-identified}
    (b) effective_codes excludes identification-missing AND instrument-assumption-risk
    (c) estimator_diagnostics is present
    """
    issues: list[Issue] = []
    payload = store.get(pid)
    if payload is None:
        return issues

    if "causal-effect-estimate" not in _loaded_extensions(payload):
        return issues  # rule does not apply

    core = payload.get("core", {}) or {}
    if core.get("validation_role") != "strengthen-belief":
        return issues  # rule's guard condition not triggered

    cee = payload.get("extension/causal-effect-estimate") or {}

    # (a) identification status check
    id_ref = cee.get("identification_payload_ref")
    id_payload = store.get(id_ref) if id_ref else None
    if id_payload is None:
        issues.append(Issue("error", pid, "extension/causal-effect-estimate.identification_payload_ref",
                            "cee-strengthen-a",
                            f"identification_payload_ref {id_ref!r} does not resolve in store"))
    else:
        ci = id_payload.get("extension/causal-identification") or {}
        status = ci.get("identification_status")
        if status not in {"identified", "partially-identified"}:
            issues.append(Issue("error", pid, "extension/causal-effect-estimate.identification_payload_ref",
                                "cee-strengthen-a",
                                f"upstream identification_status={status!r} not in "
                                f"{{identified, partially-identified}}"))

    # (b) effective codes check
    eff = effective_codes(store, pid)
    forbidden_in_eff = {"identification-missing", "instrument-assumption-risk"} & eff
    if forbidden_in_eff:
        issues.append(Issue("error", pid, "core.reason_codes (effective)",
                            "cee-strengthen-b",
                            f"effective_codes contains forbidden codes for strengthen-belief: "
                            f"{sorted(forbidden_in_eff)} (effective_codes={sorted(eff)})"))

    # (c) estimator_diagnostics presence
    if not cee.get("estimator_diagnostics"):
        issues.append(Issue("error", pid, "extension/causal-effect-estimate.estimator_diagnostics",
                            "cee-strengthen-c",
                            "strengthen-belief requires estimator_diagnostics to be present"))

    return issues


# -----------------------------------------------------------------------------
# Test scenarios
# -----------------------------------------------------------------------------

def _payload(extensions, *, validation_role: str = "record-only", reason_codes=None,
             input_artifact_refs=None, exts: dict | None = None) -> dict:
    p = {
        "core": {
            "extensions": list(extensions),
            "validation_role": validation_role,
            "reason_codes": list(reason_codes or []),
            "input_artifact_refs": list(input_artifact_refs or []),
        },
    }
    for k, v in (exts or {}).items():
        p[f"extension/{k.replace('_', '-')}"] = v
    return p


# ---- effective_codes computation tests --------------------------------------

def test_effective_simple_auto_inject():
    """Loading mr-graph-model auto-injects instrument-assumption-risk."""
    store = Store()
    store.add("p1", _payload(["mr-graph-model", "causal-graph", "statistical-uncertainty"]))
    eff = effective_codes(store, "p1")
    assert eff == {"instrument-assumption-risk"}, eff


def test_effective_propagation_blocking_only():
    """Upstream causal-discovery-run propagates blocking identification-missing,
    but not non-blocking causal-sufficiency-assumption."""
    store = Store()
    store.add("disc1", _payload(["causal-discovery-run", "causal-graph"],
                                reason_codes=["causal-sufficiency-assumption"]))
    store.add("id1", _payload(["causal-identification"],
                              input_artifact_refs=["disc1"],
                              exts={"causal_identification": {"identification_status": "pending"}}))
    eff = effective_codes(store, "id1")
    assert "identification-missing" in eff, eff
    assert "causal-sufficiency-assumption" not in eff, eff


def test_effective_retirement_id_resolved():
    """causal-identification with identified status retires propagated identification-missing."""
    store = Store()
    store.add("disc1", _payload(["causal-discovery-run", "causal-graph"]))
    store.add("id1", _payload(["causal-identification"],
                              input_artifact_refs=["disc1"],
                              exts={"causal_identification": {"identification_status": "identified"}}))
    eff = effective_codes(store, "id1")
    assert "identification-missing" not in eff, eff


def test_effective_retirement_pleiotropy():
    """mr-analysis with pleiotropy_handling=mr-egger-intercept retires propagated pleiotropy-untested."""
    store = Store()
    # stage (a): mr-graph-model with pleiotropy_model=none-assumed → declares pleiotropy-untested
    store.add("mra1", _payload(["mr-graph-model", "causal-graph", "statistical-uncertainty"],
                               reason_codes=["pleiotropy-untested"]))
    # stage (b): causal-effect-estimate + mr-analysis retires it
    store.add("cee1", _payload(
        ["causal-effect-estimate", "mr-analysis", "statistical-uncertainty"],
        input_artifact_refs=["mra1"],
        exts={"mr_analysis": {"pleiotropy_handling": "mr-egger-intercept"}}))
    eff = effective_codes(store, "cee1")
    assert "pleiotropy-untested" not in eff, eff


def test_effective_cycle_halts():
    """A cycle in input_artifact_refs halts recursion rather than diverging."""
    store = Store()
    store.add("a", _payload(["causal-discovery-run", "causal-graph"], input_artifact_refs=["b"]))
    store.add("b", _payload(["causal-identification"], input_artifact_refs=["a"]))
    eff = effective_codes(store, "a")
    assert isinstance(eff, set), eff
    assert detect_cycle(store, "a") is not None


# ---- v1.3 authoring tests --------------------------------------------------

def test_v13_authoring_clean():
    p = _payload(["mr-graph-model", "causal-graph", "statistical-uncertainty"],
                 reason_codes=["reverse-causation-assumed"])
    issues = validate_v13_authoring("p1", p)
    assert issues == [], issues


def test_v13_authoring_violation():
    """Author wrote instrument-assumption-risk by hand — v1.3 says don't."""
    p = _payload(["mr-graph-model", "causal-graph", "statistical-uncertainty"],
                 reason_codes=["instrument-assumption-risk", "reverse-causation-assumed"])
    issues = validate_v13_authoring("p1", p)
    assert len(issues) == 1 and issues[0].rule == "v1.3-auto-inject", issues


# ---- consumer-rule (causal-effect-estimate strengthen-belief) tests ---------

def test_strengthen_clean():
    """Identified upstream + no forbidden codes + diagnostics → strengthen permitted."""
    store = Store()
    store.add("disc1", _payload(["causal-discovery-run", "causal-graph"]))
    store.add("id1", _payload(["causal-identification"],
                              input_artifact_refs=["disc1"],
                              exts={"causal_identification": {"identification_status": "identified"}}))
    store.add("cee1", _payload(
        ["causal-effect-estimate", "statistical-uncertainty"],
        validation_role="strengthen-belief",
        input_artifact_refs=["id1"],
        exts={"causal_effect_estimate": {
            "identification_payload_ref": "id1",
            "estimator_diagnostics": {"converged": True},
        }}))
    issues = validate_strengthen_cee(store, "cee1")
    assert issues == [], issues


def test_strengthen_blocked_by_propagated_identification_missing():
    """Upstream identification was pending → identification-missing propagates → strengthen rejected."""
    store = Store()
    store.add("disc1", _payload(["causal-discovery-run", "causal-graph"]))
    store.add("id1", _payload(["causal-identification"],
                              input_artifact_refs=["disc1"],
                              exts={"causal_identification": {"identification_status": "pending"}}))
    store.add("cee1", _payload(
        ["causal-effect-estimate", "statistical-uncertainty"],
        validation_role="strengthen-belief",
        input_artifact_refs=["id1"],
        exts={"causal_effect_estimate": {
            "identification_payload_ref": "id1",
            "estimator_diagnostics": {"converged": True},
        }}))
    issues = validate_strengthen_cee(store, "cee1")
    rules = {i.rule for i in issues}
    assert rules == {"cee-strengthen-a", "cee-strengthen-b"}, (rules, issues)


def test_strengthen_blocked_by_local_iar_via_mr_analysis():
    """Co-loading mr-analysis auto-injects instrument-assumption-risk locally → strengthen rejected."""
    store = Store()
    store.add("disc1", _payload(["causal-discovery-run", "causal-graph"]))
    store.add("id1", _payload(["causal-identification"],
                              input_artifact_refs=["disc1"],
                              exts={"causal_identification": {"identification_status": "identified"}}))
    store.add("cee1", _payload(
        ["causal-effect-estimate", "mr-analysis", "statistical-uncertainty"],
        validation_role="strengthen-belief",
        input_artifact_refs=["id1"],
        # mr-analysis present → instrument-assumption-risk auto-injected on cee1
        exts={"causal_effect_estimate": {
            "identification_payload_ref": "id1",
            "estimator_diagnostics": {"converged": True},
        },
           "mr_analysis": {"pleiotropy_handling": "unhandled"}}))
    issues = validate_strengthen_cee(store, "cee1")
    rules = {i.rule for i in issues}
    assert rules == {"cee-strengthen-b"}, (rules, issues)


def test_strengthen_missing_diagnostics():
    store = Store()
    store.add("disc1", _payload(["causal-discovery-run", "causal-graph"]))
    store.add("id1", _payload(["causal-identification"],
                              input_artifact_refs=["disc1"],
                              exts={"causal_identification": {"identification_status": "identified"}}))
    store.add("cee1", _payload(
        ["causal-effect-estimate", "statistical-uncertainty"],
        validation_role="strengthen-belief",
        input_artifact_refs=["id1"],
        exts={"causal_effect_estimate": {"identification_payload_ref": "id1"}}))
    issues = validate_strengthen_cee(store, "cee1")
    rules = {i.rule for i in issues}
    assert rules == {"cee-strengthen-c"}, (rules, issues)


def test_strengthen_unresolved_id_ref():
    store = Store()
    store.add("cee1", _payload(
        ["causal-effect-estimate", "statistical-uncertainty"],
        validation_role="strengthen-belief",
        exts={"causal_effect_estimate": {
            "identification_payload_ref": "id-does-not-exist",
            "estimator_diagnostics": {"converged": True},
        }}))
    issues = validate_strengthen_cee(store, "cee1")
    rules = {i.rule for i in issues}
    assert rules == {"cee-strengthen-a"}, (rules, issues)


def test_strengthen_role_not_triggered():
    """validation_role: record-only — rule does not fire even if other conditions fail."""
    store = Store()
    store.add("cee1", _payload(
        ["causal-effect-estimate", "statistical-uncertainty"],
        validation_role="record-only",
        exts={"causal_effect_estimate": {"identification_payload_ref": "missing"}}))
    issues = validate_strengthen_cee(store, "cee1")
    assert issues == [], issues


def test_strengthen_mr_two_stage_iar_retired():
    """End-to-end two-stage MR (T34-6): stage (a) declares pleiotropy-untested; stage (b)
    retires both pleiotropy-untested AND instrument-assumption-risk via valid
    pleiotropy_handling plus upstream relevance.

    Pre-v1.4, this test asserted the misfire (cee-strengthen-b fired on locally-auto-injected
    iar) — the slice-3 finding labeled this as the test_strengthen_mr_two_stage_iar_finding
    case. v1.4 P1.4-a adopted the iar retirement rule explicitly: when mr-analysis has
    valid pleiotropy_handling AND upstream mr_graph_payload_ref.instrument_validity_assumptions
    contains 'relevance', iar is retired locally. This flipped fixture exercises the rule:
    the consumer rule now passes, demonstrating that T34-6 stage (b) validates at
    strengthen-belief under v1.4."""
    store = Store()
    # stage (a) — must populate instrument_validity_assumptions for the iar retirement
    # to fire on the downstream stage (b).
    store.add("mra1", _payload(["mr-graph-model", "causal-graph", "statistical-uncertainty"],
                               validation_role="prioritize-attention",
                               reason_codes=["pleiotropy-untested"],
                               exts={"mr_graph_model": {
                                   "instrument_validity_assumptions": ["relevance", "exclusion"],
                               }}))
    # an identification payload referencing the MR graph
    store.add("id1", _payload(["causal-identification"],
                              input_artifact_refs=["mra1"],
                              exts={"causal_identification": {"identification_status": "identified"}}))
    # stage (b): cee + mr-analysis retires pleiotropy-untested via mr-egger-intercept,
    # and (v1.4) retires instrument-assumption-risk via mr_graph_payload_ref pointing to
    # an upstream graph whose instrument_validity_assumptions includes relevance.
    store.add("cee1", _payload(
        ["causal-effect-estimate", "mr-analysis", "statistical-uncertainty"],
        validation_role="strengthen-belief",
        input_artifact_refs=["id1"],
        exts={"causal_effect_estimate": {
            "identification_payload_ref": "id1",
            "estimator_diagnostics": {"converged": True},
        },
           "mr_analysis": {
               "mr_graph_payload_ref": "mra1",
               "pleiotropy_handling": "mr-egger-intercept",
           }}))
    issues = validate_strengthen_cee(store, "cee1")
    rules = {i.rule for i in issues}
    assert rules == set(), (rules, issues)


TESTS = [
    test_effective_simple_auto_inject,
    test_effective_propagation_blocking_only,
    test_effective_retirement_id_resolved,
    test_effective_retirement_pleiotropy,
    test_effective_cycle_halts,
    test_v13_authoring_clean,
    test_v13_authoring_violation,
    test_strengthen_clean,
    test_strengthen_blocked_by_propagated_identification_missing,
    test_strengthen_blocked_by_local_iar_via_mr_analysis,
    test_strengthen_missing_diagnostics,
    test_strengthen_unresolved_id_ref,
    test_strengthen_role_not_triggered,
    test_strengthen_mr_two_stage_iar_retired,
]


def main() -> int:
    passed = 0
    failed: list[tuple[str, BaseException]] = []
    print(f"t034 v1.4 effective-codes / propagation validator prototype — running {len(TESTS)} tests\n")
    for tc in TESTS:
        name = tc.__name__
        try:
            tc()
            print(f"PASS {name}")
            passed += 1
        except AssertionError as exc:
            print(f"FAIL {name}: {exc}")
            failed.append((name, exc))
        except Exception as exc:
            print(f"ERROR {name}: {type(exc).__name__}: {exc}")
            failed.append((name, exc))

    print(f"\n---\n{passed}/{len(TESTS)} passed")
    if failed:
        print("FAILED: " + ", ".join(n for n, _ in failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
