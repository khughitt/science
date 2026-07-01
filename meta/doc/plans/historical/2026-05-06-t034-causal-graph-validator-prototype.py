#!/usr/bin/env python3
"""
Prototype validator for t034 v1.2 `causal-graph` extension structural rules.

Per the natural-systems alignment commitment in
meta/doc/plans/historical/2026-05-06-t034-causal-graph-extension-design.md: "the validation
rules in this design must be implemented as enforcing runners — a payload claiming
strengthen-belief without estimator_diagnostics should fail at validate-time, not
pass with a comment."

This prototype implements the structural rules added in v1.1 F6 and confirmed
in v1.2:

- Rule cg-1: graph_object_type ∈ strict enum.
- Rule cg-2: for each edge, epistemic_role ∈ per-graph_object_type permitted set.
- Rule cg-3: promotion roles {identified_causal_effect, mediation_path,
  mr_instrumental_effect} are never authored in-place; recorded by a
  downstream payload instead.
- Rule cg-3-mechanistic: epistemic_role 'mechanistic_hypothesis' is allowed
  in-place only when the payload's primary extension is mechanistic-hypothesis-bundle.

Standalone runner. NOT integrated into meta/validate.sh; this is a study.

Run with:  python meta/doc/plans/historical/2026-05-06-t034-causal-graph-validator-prototype.py

Exits 0 if all 10 test cases match expectations; nonzero otherwise.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Literal

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


@dataclass(frozen=True)
class Issue:
    severity: Literal["error", "warning"]
    path: str
    rule: str
    msg: str

    def __str__(self) -> str:
        return f"[{self.severity:5}] {self.rule:24} {self.path}: {self.msg}"


def _primary(payload: dict) -> str | None:
    exts = payload.get("core", {}).get("extensions", []) or []
    return exts[0] if exts else None


def validate_causal_graph(payload: dict, ext_key: str = "extension/causal-graph") -> list[Issue]:
    issues: list[Issue] = []
    primary = _primary(payload)

    if ext_key not in payload:
        return issues  # extension absent — these rules do not apply

    cg = payload[ext_key] or {}

    got = cg.get("graph_object_type")
    if got is None:
        issues.append(Issue("error", f"{ext_key}.graph_object_type",
                            "rule-cg-1", "graph_object_type is required"))
        return issues
    if got not in GRAPH_OBJECT_TYPES:
        issues.append(Issue("error", f"{ext_key}.graph_object_type",
                            "rule-cg-1",
                            f"{got!r} not in strict enum {sorted(GRAPH_OBJECT_TYPES)}"))
        return issues

    permitted = EDGE_ROLE_BY_GRAPH_TYPE.get(got, set())
    for i, edge in enumerate(cg.get("edges") or []):
        role = edge.get("epistemic_role")
        path = f"{ext_key}.edges[{i}].epistemic_role"

        if role is None:
            issues.append(Issue("error", path, "rule-cg-edge-shape",
                                "edge missing epistemic_role"))
            continue

        if role in PROMOTION_ROLES:
            issues.append(Issue("error", path, "rule-cg-3",
                                f"role {role!r} is promotion-only — recorded by a downstream "
                                f"payload via reference, never in-place"))
            continue

        if role == "mechanistic_hypothesis" and primary != "mechanistic-hypothesis-bundle":
            issues.append(Issue("error", path, "rule-cg-3-mech",
                                f"role 'mechanistic_hypothesis' allowed in-place only when "
                                f"primary extension is 'mechanistic-hypothesis-bundle' "
                                f"(primary={primary!r})"))
            continue

        if role not in permitted and role != "mechanistic_hypothesis":
            issues.append(Issue("error", path, "rule-cg-2",
                                f"role {role!r} not permitted on graph_object_type {got!r}; "
                                f"permitted: {sorted(permitted)}"))

    return issues


# -----------------------------------------------------------------------------
# Test cases — each returns (name, payload, expected_rules_fired)
# -----------------------------------------------------------------------------

def t01_valid_cpdag() -> tuple[str, dict, set[str]]:
    """Valid CPDAG: vaccination CPDAG from a PC run, no rule violations."""
    return ("01-valid-cpdag", {
        "core": {"extensions": ["causal-discovery-run", "causal-graph"]},
        "extension/causal-graph": {
            "graph_object_type": "CPDAG",
            "edges": [
                {"a": "var:vaccination", "b": "var:severe-illness",
                 "epistemic_role": "data_discovered_adjacency", "oriented": False},
                {"a": "var:age", "b": "var:severe-illness",
                 "epistemic_role": "assumed_background_edge", "oriented": True},
            ],
        },
    }, set())


def t02_cpdag_with_mechanistic_edge() -> tuple[str, dict, set[str]]:
    """CPDAG with a mechanistic_hypothesis edge — wrong graph type for that role."""
    return ("02-cpdag-with-mechanistic-edge", {
        "core": {"extensions": ["causal-discovery-run", "causal-graph"]},
        "extension/causal-graph": {
            "graph_object_type": "CPDAG",
            "edges": [
                {"a": "var:a", "b": "var:b",
                 "epistemic_role": "mechanistic_hypothesis", "oriented": True},
            ],
        },
    }, {"rule-cg-3-mech"})


def t03_mhb_with_mechanistic_edge() -> tuple[str, dict, set[str]]:
    """mechanistic-hypothesis-bundle + candidate-graph + mechanistic_hypothesis edge — valid."""
    return ("03-mhb-with-mechanistic-edge", {
        "core": {"extensions": ["mechanistic-hypothesis-bundle", "causal-graph"]},
        "extension/causal-graph": {
            "graph_object_type": "candidate-graph",
            "edges": [
                {"a": "protein:EGFR", "b": "protein:ERK",
                 "epistemic_role": "mechanistic_hypothesis", "oriented": True},
            ],
        },
    }, set())


def t04_discovery_run_with_mechanistic_edge() -> tuple[str, dict, set[str]]:
    """causal-discovery-run + candidate-graph + mechanistic_hypothesis — wrong primary."""
    return ("04-discovery-run-with-mechanistic-edge", {
        "core": {"extensions": ["causal-discovery-run", "causal-graph"]},
        "extension/causal-graph": {
            "graph_object_type": "candidate-graph",
            "edges": [
                {"a": "var:a", "b": "var:b",
                 "epistemic_role": "mechanistic_hypothesis", "oriented": True},
            ],
        },
    }, {"rule-cg-3-mech"})


def t05_cpdag_with_identified_edge() -> tuple[str, dict, set[str]]:
    """CPDAG with identified_causal_effect edge — promotion-only role can never be in-place."""
    return ("05-cpdag-with-identified-edge", {
        "core": {"extensions": ["causal-discovery-run", "causal-graph"]},
        "extension/causal-graph": {
            "graph_object_type": "CPDAG",
            "edges": [
                {"a": "var:x", "b": "var:y",
                 "epistemic_role": "identified_causal_effect", "oriented": True},
            ],
        },
    }, {"rule-cg-3"})


def t06_unknown_graph_object_type() -> tuple[str, dict, set[str]]:
    """graph_object_type='mechanistic' (the v1.1 F2 invalid value) — rejected."""
    return ("06-unknown-got", {
        "core": {"extensions": ["mechanistic-hypothesis-bundle", "causal-graph"]},
        "extension/causal-graph": {
            "graph_object_type": "mechanistic",  # was a leaked v1 value
            "edges": [],
        },
    }, {"rule-cg-1"})


def t07_missing_graph_object_type() -> tuple[str, dict, set[str]]:
    """graph_object_type missing — required field."""
    return ("07-missing-got", {
        "core": {"extensions": ["causal-discovery-run", "causal-graph"]},
        "extension/causal-graph": {"edges": []},
    }, {"rule-cg-1"})


def t08_graph_posterior_empty_edges() -> tuple[str, dict, set[str]]:
    """Adapted Zuber pilot: graph-posterior with edges stored externally — passes structural rules."""
    return ("08-graph-posterior-empty-edges", {
        "core": {"extensions": ["mr-graph-model", "causal-graph", "statistical-uncertainty"],
                 "reason_codes": ["instrument-assumption-risk", "extracted-from-summary-only"]},
        "extension/causal-graph": {
            "graph_object_type": "graph-posterior",
            "edges": [],
        },
    }, set())


def t09_no_causal_graph_extension() -> tuple[str, dict, set[str]]:
    """Adapted Faller pilot: graph-diagnostic doesn't load causal-graph; rules don't apply."""
    return ("09-no-causal-graph-extension", {
        "core": {"extensions": ["graph-diagnostic"]},
        "extension/graph-diagnostic": {
            "diagnostic_kind": "self-compatibility",
            "result": "correlative",
        },
    }, set())


def t10_dugourd_adapted() -> tuple[str, dict, set[str]]:
    """Adapted Dugourd pilot: mechanistic-hypothesis-bundle + candidate-graph passes."""
    return ("10-dugourd-adapted", {
        "core": {"extensions": ["mechanistic-hypothesis-bundle", "causal-graph"],
                 "reason_codes": ["mechanism-hypothesis-only", "prior-network-dependent",
                                  "extracted-from-summary-only"]},
        "extension/causal-graph": {
            "graph_object_type": "candidate-graph",
            "edges": [
                {"a": "protein:EGFR", "b": "protein:ERK",
                 "epistemic_role": "mechanistic_hypothesis", "oriented": True},
                {"a": "metabolite:succinate", "b": "protein:HIF1A",
                 "epistemic_role": "mechanistic_hypothesis", "oriented": True},
            ],
        },
    }, set())


TESTS = [
    t01_valid_cpdag, t02_cpdag_with_mechanistic_edge, t03_mhb_with_mechanistic_edge,
    t04_discovery_run_with_mechanistic_edge, t05_cpdag_with_identified_edge,
    t06_unknown_graph_object_type, t07_missing_graph_object_type,
    t08_graph_posterior_empty_edges, t09_no_causal_graph_extension,
    t10_dugourd_adapted,
]


def main() -> int:
    passed = 0
    failed: list[str] = []

    print(f"t034 v1.2 causal-graph validator prototype — running {len(TESTS)} tests\n")

    for tc in TESTS:
        name, payload, expected_rules = tc()
        issues = validate_causal_graph(payload)
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
