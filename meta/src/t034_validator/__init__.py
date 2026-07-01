# science:code
# status: library
# task_ids: [t034]
# science:end
"""t034 evidence-payload validator (production fold-in of the slice prototypes).

Bundles the three slice-prototype rule sets into a single runner against the
v1.4 contract:

- slice 1 (causal-graph structural): graph_object_type enum, edge-role
  per-graph-type permission, promotion-only roles never authored in-place,
  mechanistic_hypothesis allowed in-place only under mechanistic-hypothesis-bundle.
- slice 2 (mr-graph-model role-permission and conditional-required fields):
  validation_role permission, co-required extensions, always-required and
  summary-gated optional fields, biconditional reason-code rules for
  pleiotropy_model and direction_constraint.
- slice 3 (effective_codes / propagation / consumer rules): declared ∪
  auto-injected ∪ propagated_blocking − retired; v1.3 P1.3-c hard-error on
  hand-written auto-injected codes; CEE-strengthen-belief consumer rule.

v1.4 retirement table is implemented in `_retired_by`:
- causal-identification with identified / partially-identified retires
  identification-missing
- mr-analysis with pleiotropy_handling != unhandled retires pleiotropy-untested
- mr-analysis with pleiotropy_handling != unhandled AND upstream
  instrument_validity_assumptions including 'relevance' retires
  instrument-assumption-risk (P1.4-a — first retirement that reads upstream state)

The durable authoring contract is meta/evidence/t034-causal-graph-contract.md.
The historical prototypes in doc/plans/historical/ were extracted into
meta/tests/test_t034_validator.py. This package is what runs at validate-time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GRAPH_OBJECT_TYPES: set[str] = {
    "DAG", "CPDAG", "PAG", "ADMG",
    "equivalence-class-feature", "candidate-graph", "graph-posterior",
}

EDGE_ROLE_BY_GRAPH_TYPE: dict[str, set[str]] = {
    "DAG": {"assumed_background_edge", "llm_prior_edge"},
    "CPDAG": {"assumed_background_edge", "llm_ancestral_constraint",
              "data_discovered_adjacency", "equivalence_class_feature"},
    "PAG": {"data_discovered_adjacency", "equivalence_class_feature",
            "latent_variable_hypothesis"},
    "ADMG": {"data_discovered_adjacency", "equivalence_class_feature",
             "latent_variable_hypothesis"},
    "equivalence-class-feature": set(),
    "candidate-graph": {"assumed_background_edge", "llm_prior_edge",
                        "llm_ancestral_constraint", "data_discovered_adjacency",
                        "latent_variable_hypothesis", "mechanistic_hypothesis"},
    "graph-posterior": {"llm_prior_edge"},
}

PROMOTION_ROLES: set[str] = {
    "identified_causal_effect", "mediation_path", "mr_instrumental_effect",
}

# v1.3 P1.3-c auto-injection table.
AUTO_INJECTION: dict[str, set[str]] = {
    "causal-discovery-run": {"identification-missing"},
    "mr-graph-model": {"instrument-assumption-risk"},
    "mr-analysis": {"instrument-assumption-risk"},
    "mechanistic-hypothesis-bundle": {"mechanism-hypothesis-only", "prior-network-dependent"},
}

# Blocking codes from the t034 v1.3 reason-code rollup table. Only blocking
# codes propagate via input_artifact_refs.
BLOCKING_CODES: set[str] = {
    "llm-prior-unvalidated",
    "identification-missing",
    "pleiotropy-untested",
    "multiplicity-uncorrected",
    "self-incompatible",
    "mechanism-hypothesis-only",
    "estimand-mismatch",
}

# mr-graph-model slice constants
MR_EXT = "extension/mr-graph-model"
MR_PERMITTED_ROLES: set[str] = {"prioritize-attention", "record-only"}
MR_FORBIDDEN_ROLES: set[str] = {"strengthen-belief", "gate-update", "quality-record-only"}
MR_CO_REQUIRED_EXTENSIONS: set[str] = {"causal-graph", "statistical-uncertainty"}
MR_GRAPH_OBJECT_TYPES: set[str] = {"CPDAG", "DAG", "graph-posterior"}
MR_ALWAYS_REQUIRED_FIELDS: tuple[str, ...] = (
    "exposure_set", "outcome_set", "instrument_validity_assumptions",
    "pleiotropy_model", "direction_constraint", "graph_object_type",
)
MR_CONDITIONALLY_REQUIRED_FIELDS: tuple[str, ...] = (
    "instrument_set", "summary_statistic_provenance",
)
PLEIOTROPY_BLOCKING_VALUES: set[str] = {"none-assumed", "not-modelled"}


# ---------------------------------------------------------------------------
# Issue / Store
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Issue:
    severity: Literal["error", "warning"]
    payload_id: str
    path: str
    rule: str
    msg: str

    def __str__(self) -> str:
        return f"[{self.severity:5}] {self.rule:20} {self.payload_id}:{self.path}: {self.msg}"


@dataclass
class Store:
    payloads: dict[str, dict] = field(default_factory=dict)

    def get(self, pid: str) -> dict | None:
        return self.payloads.get(pid)

    def add(self, pid: str, payload: dict) -> None:
        if pid in self.payloads:
            raise ValueError(f"duplicate payload id {pid!r}")
        self.payloads[pid] = payload


# ---------------------------------------------------------------------------
# Effective-codes machinery (slice 3 + v1.4 P1.4-a)
# ---------------------------------------------------------------------------

def _loaded_extensions(payload: dict) -> set[str]:
    return set(payload.get("core", {}).get("extensions") or [])


def _auto_injected(payload: dict) -> set[str]:
    out: set[str] = set()
    for ext in _loaded_extensions(payload):
        out |= AUTO_INJECTION.get(ext, set())
    return out


def _retired_by(store: Store, payload: dict) -> set[str]:
    """Codes this payload retires from effective_codes. Reads local payload state
    and (for the P1.4-a iar rule) upstream state via mr_graph_payload_ref.
    """
    retired: set[str] = set()
    exts = _loaded_extensions(payload)

    if "causal-identification" in exts:
        ci = payload.get("extension/causal-identification") or {}
        if ci.get("identification_status") in {"identified", "partially-identified"}:
            retired.add("identification-missing")

    if "mr-analysis" in exts:
        ma = payload.get("extension/mr-analysis") or {}
        ph = ma.get("pleiotropy_handling")
        if ph not in {None, "unhandled"}:
            retired.add("pleiotropy-untested")
            # P1.4-a: iar retirement also requires upstream relevance.
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
    """Compute effective_codes for payload `pid`.

    Formula: declared ∪ auto_injected ∪ propagated_blocking(upstream) − retired.

    `propagated_blocking` walks `core.input_artifact_refs` recursively, filtering
    upstream effective_codes to BLOCKING_CODES. Cycles in input_artifact_refs are
    halted at the cycle boundary; use `detect_cycle` to surface them as errors.
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
    """Return the offending payload id if input_artifact_refs has a cycle from pid."""
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


# ---------------------------------------------------------------------------
# v1.3 P1.3-c authoring rule (hard-error per v1.4 P1.4-b)
# ---------------------------------------------------------------------------

def validate_v13_authoring(pid: str, payload: dict) -> list[Issue]:
    declared = set(payload.get("core", {}).get("reason_codes") or [])
    auto = _auto_injected(payload)
    overlap = declared & auto
    if not overlap:
        return []
    return [Issue("error", pid, "core.reason_codes", "v1.3-auto-inject",
                  f"author hand-wrote auto-injected code(s) {sorted(overlap)}; "
                  f"per t034 v1.3 P1.3-c the validator's contribution-merger "
                  f"adds these — v1.4 hard-errors on hand-writing")]


# ---------------------------------------------------------------------------
# Slice 1 — causal-graph structural rules
# ---------------------------------------------------------------------------

def _primary(payload: dict) -> str | None:
    exts = payload.get("core", {}).get("extensions") or []
    return exts[0] if exts else None


def validate_causal_graph(pid: str, payload: dict) -> list[Issue]:
    """Slice 1 — causal-graph structural rules. Applies if the payload loads
    the causal-graph extension."""
    issues: list[Issue] = []
    ext_key = "extension/causal-graph"
    if ext_key not in payload:
        return issues

    primary = _primary(payload)
    cg = payload[ext_key] or {}

    got = cg.get("graph_object_type")
    if got is None:
        issues.append(Issue("error", pid, f"{ext_key}.graph_object_type",
                            "rule-cg-1", "graph_object_type is required"))
        return issues
    if got not in GRAPH_OBJECT_TYPES:
        issues.append(Issue("error", pid, f"{ext_key}.graph_object_type",
                            "rule-cg-1",
                            f"{got!r} not in strict enum {sorted(GRAPH_OBJECT_TYPES)}"))
        return issues

    permitted = EDGE_ROLE_BY_GRAPH_TYPE.get(got, set())
    for i, edge in enumerate(cg.get("edges") or []):
        role = edge.get("epistemic_role")
        path = f"{ext_key}.edges[{i}].epistemic_role"

        if role is None:
            issues.append(Issue("error", pid, path, "rule-cg-edge-shape",
                                "edge missing epistemic_role"))
            continue

        if role in PROMOTION_ROLES:
            issues.append(Issue("error", pid, path, "rule-cg-3",
                                f"role {role!r} is promotion-only — recorded by a downstream "
                                f"payload via reference, never in-place"))
            continue

        if role == "mechanistic_hypothesis" and primary != "mechanistic-hypothesis-bundle":
            issues.append(Issue("error", pid, path, "rule-cg-3-mech",
                                f"role 'mechanistic_hypothesis' allowed in-place only when "
                                f"primary extension is 'mechanistic-hypothesis-bundle' "
                                f"(primary={primary!r})"))
            continue

        if role not in permitted and role != "mechanistic_hypothesis":
            issues.append(Issue("error", pid, path, "rule-cg-2",
                                f"role {role!r} not permitted on graph_object_type {got!r}; "
                                f"permitted: {sorted(permitted)}"))

    return issues


# ---------------------------------------------------------------------------
# Slice 2 — mr-graph-model role-permission + biconditional codes
# ---------------------------------------------------------------------------

def _is_nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, tuple, set, dict, str)):
        return len(value) > 0
    return True


def validate_mr_graph_model(pid: str, payload: dict) -> list[Issue]:
    """Slice 2 — mr-graph-model rules (mr-1..mr-5, mr-7..mr-9). The retired mr-6
    is replaced by validate_v13_authoring (run separately).

    Effective codes for biconditional checks: declared ∪ auto-injected (no
    upstream propagation needed since mr-* codes are local-state assertions).
    """
    issues: list[Issue] = []
    if MR_EXT not in payload:
        return issues

    core = payload.get("core", {}) or {}
    ext = payload[MR_EXT] or {}
    extensions = set(core.get("extensions") or [])

    # local effective codes for biconditional rules (no upstream propagation here)
    eff_codes = set(core.get("reason_codes") or []) | (
        AUTO_INJECTION.get("mr-graph-model", set()) if MR_EXT in payload else set()
    )
    summary_only = "extracted-from-summary-only" in eff_codes

    # mr-3: co-required extensions
    missing_co = MR_CO_REQUIRED_EXTENSIONS - extensions
    if missing_co:
        issues.append(Issue("error", pid, "core.extensions", "mr-3",
                            f"mr-graph-model requires co-loaded extensions "
                            f"{sorted(MR_CO_REQUIRED_EXTENSIONS)}; missing: {sorted(missing_co)}"))

    # mr-2: validation_role permission
    role = core.get("validation_role")
    if role is None:
        issues.append(Issue("error", pid, "core.validation_role", "mr-2",
                            "validation_role is required"))
    elif role in MR_FORBIDDEN_ROLES:
        issues.append(Issue("error", pid, "core.validation_role", "mr-2",
                            f"validation_role {role!r} forbidden on mr-graph-model "
                            f"(stage (a) graph posterior cannot strengthen belief; "
                            f"permitted: {sorted(MR_PERMITTED_ROLES)})"))
    elif role not in MR_PERMITTED_ROLES:
        issues.append(Issue("error", pid, "core.validation_role", "mr-2",
                            f"validation_role {role!r} not in permitted set "
                            f"{sorted(MR_PERMITTED_ROLES)}"))

    # mr-4: always-required fields
    for f in MR_ALWAYS_REQUIRED_FIELDS:
        if not _is_nonempty(ext.get(f)):
            issues.append(Issue("error", pid, f"{MR_EXT}.{f}", "mr-4",
                                f"required field {f!r} is missing or empty"))

    # mr-5: conditionally-required fields
    for f in MR_CONDITIONALLY_REQUIRED_FIELDS:
        if not _is_nonempty(ext.get(f)) and not summary_only:
            issues.append(Issue("error", pid, f"{MR_EXT}.{f}", "mr-5",
                                f"field {f!r} required unless extracted-from-summary-only "
                                f"in effective_codes"))

    # mr-1: graph_object_type narrower enum
    got = ext.get("graph_object_type")
    if got is not None and got not in MR_GRAPH_OBJECT_TYPES:
        issues.append(Issue("error", pid, f"{MR_EXT}.graph_object_type", "mr-1",
                            f"{got!r} not in mr-graph-model permitted set "
                            f"{sorted(MR_GRAPH_OBJECT_TYPES)}"))

    # mr-7: pleiotropy-untested ↔ pleiotropy_model ∈ blocking
    pmodel = ext.get("pleiotropy_model")
    has_untested = "pleiotropy-untested" in eff_codes
    if pmodel in PLEIOTROPY_BLOCKING_VALUES and not has_untested:
        issues.append(Issue("error", pid, "core.reason_codes", "mr-7",
                            f"pleiotropy_model={pmodel!r} requires reason code "
                            f"'pleiotropy-untested' (blocking) to be declared"))
    if pmodel not in PLEIOTROPY_BLOCKING_VALUES and has_untested:
        issues.append(Issue("error", pid, "core.reason_codes", "mr-7",
                            f"reason code 'pleiotropy-untested' declared but "
                            f"pleiotropy_model={pmodel!r} is not in "
                            f"{sorted(PLEIOTROPY_BLOCKING_VALUES)}"))

    # mr-8: pleiotropy-unspecified ↔ pleiotropy_model = unspecified
    has_unspec = "pleiotropy-unspecified" in eff_codes
    if pmodel == "unspecified" and not has_unspec:
        issues.append(Issue("error", pid, "core.reason_codes", "mr-8",
                            "pleiotropy_model='unspecified' requires reason code "
                            "'pleiotropy-unspecified' to be declared"))
    if pmodel != "unspecified" and has_unspec:
        issues.append(Issue("error", pid, "core.reason_codes", "mr-8",
                            f"reason code 'pleiotropy-unspecified' declared but "
                            f"pleiotropy_model={pmodel!r} is not 'unspecified'"))

    # mr-9: reverse-causation-assumed ↔ direction-constraint and not direction-inherent
    dc = ext.get("direction_constraint")
    iva = set(ext.get("instrument_validity_assumptions") or [])
    has_rca = "reverse-causation-assumed" in eff_codes
    should_rca = (dc == "exposures-to-outcomes-only"
                  and "direction-inherent-from-iv-class" not in iva)
    if should_rca and not has_rca:
        issues.append(Issue("error", pid, "core.reason_codes", "mr-9",
                            "direction_constraint='exposures-to-outcomes-only' without "
                            "'direction-inherent-from-iv-class' in instrument_validity_assumptions "
                            "requires reason code 'reverse-causation-assumed'"))
    if has_rca and not should_rca:
        issues.append(Issue("error", pid, "core.reason_codes", "mr-9",
                            "reason code 'reverse-causation-assumed' declared but "
                            "either direction_constraint != 'exposures-to-outcomes-only' "
                            "or 'direction-inherent-from-iv-class' is in instrument_validity_assumptions"))

    return issues


# ---------------------------------------------------------------------------
# Slice 3 — CEE-strengthen consumer rule
# ---------------------------------------------------------------------------

def validate_strengthen_cee(store: Store, pid: str) -> list[Issue]:
    """causal-effect-estimate.validation_role: strengthen-belief is permitted iff
    (a) identification_payload_ref.identification_status ∈ {identified, partially-identified}
    (b) effective_codes (post-retirement) excludes identification-missing AND
        instrument-assumption-risk
    (c) estimator_diagnostics is present.
    """
    issues: list[Issue] = []
    payload = store.get(pid)
    if payload is None:
        return issues
    # Dispatch on section presence rather than core.extensions membership so a
    # payload with the section but a misconfigured list still gets validated.
    # The section/list mismatch itself is reported separately by
    # validate_section_list_consistency.
    if "extension/causal-effect-estimate" not in payload:
        return issues

    core = payload.get("core", {}) or {}
    if core.get("validation_role") != "strengthen-belief":
        return issues

    cee = payload.get("extension/causal-effect-estimate") or {}

    # (a)
    id_ref = cee.get("identification_payload_ref")
    id_payload = store.get(id_ref) if id_ref else None
    if id_payload is None:
        issues.append(Issue("error", pid,
                            "extension/causal-effect-estimate.identification_payload_ref",
                            "cee-strengthen-a",
                            f"identification_payload_ref {id_ref!r} does not resolve in store"))
    else:
        ci = id_payload.get("extension/causal-identification") or {}
        status = ci.get("identification_status")
        if status not in {"identified", "partially-identified"}:
            issues.append(Issue("error", pid,
                                "extension/causal-effect-estimate.identification_payload_ref",
                                "cee-strengthen-a",
                                f"upstream identification_status={status!r} not in "
                                f"{{identified, partially-identified}}"))

    # (b) effective_codes (post-retirement per v1.4)
    eff = effective_codes(store, pid)
    forbidden_in_eff = {"identification-missing", "instrument-assumption-risk"} & eff
    if forbidden_in_eff:
        issues.append(Issue("error", pid, "core.reason_codes (effective)",
                            "cee-strengthen-b",
                            f"effective_codes contains forbidden codes for strengthen-belief: "
                            f"{sorted(forbidden_in_eff)} (effective_codes={sorted(eff)})"))

    # (c)
    if not cee.get("estimator_diagnostics"):
        issues.append(Issue("error", pid,
                            "extension/causal-effect-estimate.estimator_diagnostics",
                            "cee-strengthen-c",
                            "strengthen-belief requires estimator_diagnostics to be present"))

    return issues


# ---------------------------------------------------------------------------
# Core shape rules — section/list consistency and ref resolution
# ---------------------------------------------------------------------------

def validate_section_list_consistency(pid: str, payload: dict) -> list[Issue]:
    """Errors on mismatch between core.extensions and extension/* sections.

    Both directions are errors:
    - A name in core.extensions without a matching extension/<name>: section
      means the dispatcher would skip rules that the author intended to load.
    - An extension/<name>: section without the name in core.extensions means
      the dispatcher (when keyed off the list) would silently skip the section's
      rules — the failure mode this rule was added to catch.
    """
    issues: list[Issue] = []
    core = payload.get("core") or {}
    listed = list(core.get("extensions") or [])
    sectioned = [k[len("extension/"):] for k in payload.keys()
                 if isinstance(k, str) and k.startswith("extension/")]

    listed_set = set(listed)
    sectioned_set = set(sectioned)

    listed_no_section = listed_set - sectioned_set
    if listed_no_section:
        issues.append(Issue("error", pid, "core.extensions", "core-extensions-shape",
                            f"core.extensions lists {sorted(listed_no_section)} but no "
                            f"matching extension/<name> section is present"))

    section_not_listed = sectioned_set - listed_set
    if section_not_listed:
        issues.append(Issue("error", pid, "extension/*", "core-extensions-shape",
                            f"extension/<name> section(s) {sorted(section_not_listed)} "
                            f"present but not declared in core.extensions"))

    return issues


def validate_input_refs(store: Store, pid: str, payload: dict) -> list[Issue]:
    """Errors on every entry in core.input_artifact_refs that doesn't resolve.

    An unresolved upstream ref would otherwise silently drop the propagation
    chain (effective_codes returns set() for missing payloads), letting a typo
    mask blocking codes that should reach this payload.
    """
    issues: list[Issue] = []
    core = payload.get("core") or {}
    refs = core.get("input_artifact_refs") or []
    for i, ref in enumerate(refs):
        if store.get(ref) is None:
            issues.append(Issue("error", pid,
                                f"core.input_artifact_refs[{i}]", "core-input-refs",
                                f"input_artifact_refs entry {ref!r} does not resolve in store"))
    return issues


# ---------------------------------------------------------------------------
# Top-level dispatch
# ---------------------------------------------------------------------------

def validate_payload(store: Store, pid: str) -> list[Issue]:
    """Run all applicable rules on payload `pid`."""
    payload = store.get(pid)
    if payload is None:
        return [Issue("error", pid, "<store>", "missing-payload",
                      "payload not found in store")]

    issues: list[Issue] = []
    issues.extend(validate_section_list_consistency(pid, payload))
    issues.extend(validate_input_refs(store, pid, payload))
    issues.extend(validate_v13_authoring(pid, payload))
    issues.extend(validate_causal_graph(pid, payload))
    issues.extend(validate_mr_graph_model(pid, payload))
    issues.extend(validate_strengthen_cee(store, pid))

    cyc = detect_cycle(store, pid)
    if cyc is not None:
        issues.append(Issue("error", pid, "core.input_artifact_refs", "cycle",
                            f"input_artifact_refs cycle detected at {cyc!r}"))

    return issues
