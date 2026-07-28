"""Dataset-anomalies health check: dataset lineage, access, and package invariants."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import yaml as _yaml
from pydantic import BaseModel, ConfigDict
from science_model.audit import EntitySubject, FindingRule, FindingSection, LocationEvidence
from science_model.audit.subjects import SubjectError

from science_tool.datasets.semantics import dataset_class_for, runtime_state_for
from science_tool.findings.producers import FindingProducer
from science_tool.graph.health_checks.base import HealthCheck, HealthContext, composed_result
from science_tool.instruments import InstrumentResult

DATASET_RULE_CODES: tuple[str, ...] = (
    "dataset_access_invalid",
    "dataset_consumed_but_unverified",
    "dataset_stale_review",
    "dataset_missing_source_url",
    "dataset_cached_field_drift",
    "dataset_invariant_violation",
    "dataset_derived_missing_workflow_run",
    "dataset_derived_asymmetric_edge",
    "dataset_derived_input_chain_broken",
    "dataset_origin_block_mismatch",
    "dataset_verified_but_unstageable",
    "dataset_research_package_asymmetric",
)


class DatasetAnomalyQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    invariant: str
    counterpart: str


SECTION = FindingSection(
    id="dataset-anomalies",
    title="Dataset anomalies",
    section_order=212,
)
RULES = {
    code: FindingRule(
        id=f"dataset.{code.removeprefix('dataset_').replace('_', '-')}",
        severities=frozenset({"error", "warn"}),
        subject_types=frozenset({"entity"}),
        qualifier_schema=DatasetAnomalyQualifiers,
        identity_qualifiers=("field", "invariant", "counterpart"),
        title=code.removeprefix("dataset_").replace("_", " ").title(),
        section=SECTION.id,
        display_order=index,
    )
    for index, code in enumerate(DATASET_RULE_CODES, start=1)
}
PRODUCER = FindingProducer(
    producer_id="dataset_anomalies",
    namespace="health_checks",
    source_module="graph/health_checks/dataset_anomalies.py",
    rules=tuple(RULES.values()),
    sections=(SECTION,),
)

_FIELDS = {
    "dataset_access_invalid": "access",
    "dataset_consumed_but_unverified": "consumed_by",
    "dataset_stale_review": "access.last_reviewed",
    "dataset_missing_source_url": "access.source_url",
    "dataset_cached_field_drift": "datapackage",
    "dataset_derived_missing_workflow_run": "derivation.workflow_run",
    "dataset_derived_asymmetric_edge": "derivation.workflow_run",
    "dataset_derived_input_chain_broken": "derivation.inputs",
    "dataset_origin_block_mismatch": "origin",
    "dataset_verified_but_unstageable": "datapackage",
    "dataset_research_package_asymmetric": "consumed_by",
    "dataset_invariant_violation": "dataset",
}
_INVARIANTS = {
    "dataset_origin_block_mismatch": "origin-block",
    "dataset_invariant_violation": "dataset-lineage",
    "dataset_derived_asymmetric_edge": "workflow-run-symmetry",
    "dataset_derived_input_chain_broken": "input-chain",
    "dataset_research_package_asymmetric": "research-package-symmetry",
}


def _passes_gate(
    entity_id: str,
    datasets_by_id: dict[str, dict],  # raw-frontmatter dict per id
    *,
    in_progress: frozenset[str],
    memo: dict[str, tuple[bool, str]],
) -> tuple[bool, str]:
    """Recursively check whether `entity_id` transitively passes the gate.

    Cycle detection uses `in_progress` (DFS path stack — IMMUTABLE per recursion frame).
    Memoization uses `memo` (already-computed pass/fail per entity_id).
    Sibling branches sharing an upstream both succeed because the upstream's result is
    memoized after the first descent — no false-positive cycle detection.
    """
    if entity_id in in_progress:
        return False, f"cycle through {entity_id}"
    if entity_id in memo:
        return memo[entity_id]
    fm = datasets_by_id.get(entity_id)
    if fm is None:
        memo[entity_id] = (False, f"missing entity {entity_id}")
        return memo[entity_id]
    origin = fm.get("origin", "external")
    if origin == "external":
        access = fm.get("access") or {}
        if not isinstance(access, dict):
            memo[entity_id] = (False, f"external {entity_id} access must be a mapping")
            return memo[entity_id]
        verified = bool(access.get("verified", False))
        exception_mode = (access.get("exception") or {}).get("mode", "")
        if verified or exception_mode:
            memo[entity_id] = (True, "")
        else:
            memo[entity_id] = (False, f"external {entity_id} unverified and no exception")
        return memo[entity_id]
    if origin == "derived":
        derivation = fm.get("derivation") or {}
        next_in_progress = in_progress | {entity_id}
        for inp in list(derivation.get("inputs") or []):
            ok, msg = _passes_gate(str(inp), datasets_by_id, in_progress=next_in_progress, memo=memo)
            if not ok:
                memo[entity_id] = (False, f"{entity_id} -> {msg}")
                return memo[entity_id]
        memo[entity_id] = (True, "")
        return memo[entity_id]
    memo[entity_id] = (False, f"{entity_id} has no origin")
    return memo[entity_id]


def _load_research_packages(project_root: Path) -> dict[str, list[str]]:
    """Map research-package:<slug> -> displays list."""
    from science_model.frontmatter import parse_frontmatter

    rps: dict[str, list[str]] = {}
    rp_root = project_root / "research" / "packages"
    if not rp_root.exists():
        return rps
    for md in rp_root.rglob("research-package.md"):
        result = parse_frontmatter(md)
        if not result:
            continue
        fm, _ = result
        if fm.get("kind") == "research-package" and fm.get("id"):
            rps[str(fm["id"])] = list(fm.get("displays") or [])
    return rps


def _load_runtime_pkg(project_root: Path, datapackage_path: str) -> dict | None:
    p = project_root / datapackage_path
    if not p.exists():
        return None
    try:
        return _yaml.safe_load(p.read_text(encoding="utf-8"))
    except _yaml.YAMLError:
        return None


def check_dataset_anomalies(project_root: Path) -> InstrumentResult[dict]:
    """Run dataset-related health checks and return found anomalies.

    Each anomaly dict has: code, severity, entity_id, file_path, message.

    Uses raw frontmatter dicts (not the Pydantic model) so that invariant
    violations — which cause model_validator to raise — can still be flagged.

    ``unwired`` when there is no ``entities/datasets/`` directory: every check below
    is anchored on a dataset entity, and the research-package symmetry check would
    otherwise flag every display as a missing dataset on the strength of a directory
    it never opened.
    """
    from science_model.frontmatter import parse_frontmatter

    datasets_dir = project_root / "entities" / "datasets"
    if not datasets_dir.is_dir():
        # NOT unwired: entities/datasets/ is optional, so its absence means the project
        # catalogues no datasets -- and a project with no datasets genuinely has no
        # dataset anomalies. Making this unwired would print a "COULD NOT RUN" row on
        # every project that has not catalogued anything, which is precisely the
        # skip-warning spam fb-2026-07-10-021 already complains about.
        return InstrumentResult.empty(
            code="no_datasets_dir",
            reason="entities/datasets/ does not exist; this project catalogues no datasets",
        )

    issues: list[dict] = []
    workflow_runs = _load_workflow_runs(project_root)

    # Build datasets_by_id for transitive gate walk (task 6.5)
    datasets_by_id: dict[str, dict] = {}
    for md in datasets_dir.rglob("*.md"):
        result = parse_frontmatter(md)
        if not result:
            continue
        fm, _ = result
        if fm.get("kind") == "dataset" and fm.get("id"):
            datasets_by_id[str(fm["id"])] = fm
    gate_memo: dict[str, tuple[bool, str]] = {}

    # Load research packages for symmetry check (task 6.7)
    research_packages = _load_research_packages(project_root)

    for md in datasets_dir.rglob("*.md"):
        result = parse_frontmatter(md)
        if not result:
            continue
        fm, _ = result
        if fm.get("kind") != "dataset":
            continue
        entity_id = str(fm.get("id", md.stem))
        origin = fm.get("origin", "external")  # legacy default

        # Invariant #7: external must not carry derivation:
        if origin == "external" and "derivation" in fm:
            issues.append(
                {
                    "code": "dataset_origin_block_mismatch",
                    "severity": "error",
                    "entity_id": entity_id,
                    "file_path": str(md),
                    "message": "origin: external entity carries a derivation: block (invariant #7)",
                }
            )

        # Invariant #8: derived must not carry access:, accessions:, or local_path:
        if origin == "derived":
            forbidden = []
            if "access" in fm:
                forbidden.append("access")
            if fm.get("accessions"):
                forbidden.append("accessions")
            if fm.get("local_path"):
                forbidden.append("local_path")
            if forbidden:
                issues.append(
                    {
                        "code": "dataset_origin_block_mismatch",
                        "severity": "error",
                        "entity_id": entity_id,
                        "file_path": str(md),
                        "message": f"origin: derived entity carries forbidden field(s): {', '.join(forbidden)} (invariant #8)",
                    }
                )

        # External-access anomalies
        if origin == "external":
            access = fm.get("access") or {}
            if not isinstance(access, dict):
                issues.append(
                    {
                        "code": "dataset_access_invalid",
                        "severity": "error",
                        "entity_id": entity_id,
                        "file_path": str(md),
                        "message": "origin: external entity access must be a mapping",
                    }
                )
                continue
            verified = bool(access.get("verified", False))
            exception_mode = (access.get("exception") or {}).get("mode", "")
            consumed_by = list(fm.get("consumed_by") or [])

            # Consumed but unverified (with no exception)
            if consumed_by and not verified and not exception_mode:
                issues.append(
                    {
                        "code": "dataset_consumed_but_unverified",
                        "severity": "error",
                        "entity_id": entity_id,
                        "file_path": str(md),
                        "message": f"consumed by {consumed_by} but access.verified is false and no exception is set",
                    }
                )

            # Stale review (verified + last_reviewed > 365 days ago)
            last_reviewed = access.get("last_reviewed", "")
            if verified and last_reviewed:
                from datetime import date

                try:
                    reviewed = date.fromisoformat(last_reviewed)
                    if (date.today() - reviewed).days > 365:
                        issues.append(
                            {
                                "code": "dataset_stale_review",
                                "severity": "warning",
                                "entity_id": entity_id,
                                "file_path": str(md),
                                "message": f"last_reviewed {last_reviewed} is older than 12 months",
                            }
                        )
                except ValueError:
                    pass

            # Missing source_url on verified entity
            if verified and not access.get("source_url"):
                issues.append(
                    {
                        "code": "dataset_missing_source_url",
                        "severity": "warning",
                        "entity_id": entity_id,
                        "file_path": str(md),
                        "message": "access.verified is true but source_url is empty",
                    }
                )

            # Task 6.6: verified but unstageable
            datapackage = fm.get("datapackage", "")
            local_path = fm.get("local_path", "")
            stageable_path = datapackage or local_path
            try:
                dataset_class = dataset_class_for(fm)
                runtime_state = runtime_state_for(fm)
            except ValueError:
                dataset_class = "deposit"
                runtime_state = "blocked-access"
            # evaluate-next / track are not-yet-staged triage tiers, where a
            # verified dataset means "confirmed reachable", not "staged" — so
            # absence of datapackage/local_path is expected, not an anomaly.
            not_yet_staged = (fm.get("tier") or "").strip() in ("evaluate-next", "track")
            if (
                dataset_class == "deposit"
                and runtime_state == "unstaged-deposit"
                and (verified or exception_mode)
                and not stageable_path
                and not not_yet_staged
            ):
                issues.append(
                    {
                        "code": "dataset_verified_but_unstageable",
                        "severity": "warning",
                        "entity_id": entity_id,
                        "file_path": str(md),
                        "message": (
                            "access is verified but runtime files are not staged; add "
                            "datapackage:/local_path: or move the dataset out of use-now"
                        ),
                    }
                )
            elif dataset_class == "deposit" and stageable_path:
                full = project_root / stageable_path
                if not full.exists():
                    issues.append(
                        {
                            "code": "dataset_verified_but_unstageable",
                            "severity": "warning",
                            "entity_id": entity_id,
                            "file_path": str(md),
                            "message": f"runtime path {stageable_path} does not exist on disk",
                        }
                    )

        # Derived workflow-run checks (invariant #9)
        if origin == "derived":
            derivation = fm.get("derivation") or {}
            wf_run_id = str(derivation.get("workflow_run", ""))
            if wf_run_id:
                run_fm = workflow_runs.get(wf_run_id)
                if run_fm is None:
                    issues.append(
                        {
                            "code": "dataset_derived_missing_workflow_run",
                            "severity": "error",
                            "entity_id": entity_id,
                            "counterpart": wf_run_id,
                            "file_path": str(md),
                            "message": f"derivation.workflow_run {wf_run_id} does not resolve to a workflow-run entity",
                        }
                    )
                else:
                    produces = list(run_fm.get("produces") or [])
                    if entity_id not in produces:
                        issues.append(
                            {
                                "code": "dataset_derived_asymmetric_edge",
                                "severity": "error",
                                "entity_id": entity_id,
                                "counterpart": wf_run_id,
                                "file_path": str(md),
                                "message": f"workflow-run {wf_run_id} does not list {entity_id} in produces:",
                            }
                        )

            # Task 6.5: transitive input chain (cycle-safe)
            for inp in list(derivation.get("inputs") or []):
                ok, msg = _passes_gate(str(inp), datasets_by_id, in_progress=frozenset({entity_id}), memo=gate_memo)
                if not ok:
                    issues.append(
                        {
                            "code": "dataset_derived_input_chain_broken",
                            "severity": "error",
                            "entity_id": entity_id,
                            "counterpart": str(inp),
                            "file_path": str(md),
                            "message": f"input chain broken: {msg}",
                        }
                    )
                    break  # one error per entity is enough

        # Task 6.7: research-package symmetry (forward: dataset.consumed_by -> rp.displays)
        consumed_by_list = list(fm.get("consumed_by") or [])
        for cons in consumed_by_list:
            if str(cons).startswith("research-package:"):
                rp_displays = research_packages.get(str(cons))
                if rp_displays is None:
                    issues.append(
                        {
                            "code": "dataset_research_package_asymmetric",
                            "severity": "error",
                            "entity_id": entity_id,
                            "counterpart": str(cons),
                            "file_path": str(md),
                            "message": f"consumed_by lists {cons} but it doesn't resolve to a research-package",
                        }
                    )
                elif entity_id not in rp_displays:
                    issues.append(
                        {
                            "code": "dataset_research_package_asymmetric",
                            "severity": "error",
                            "entity_id": entity_id,
                            "counterpart": str(cons),
                            "file_path": str(md),
                            "message": f"consumed_by lists {cons} but its displays: doesn't include {entity_id}",
                        }
                    )

        # Task 6.10: cached-field drift (datapackage YAML vs entity frontmatter)
        datapackage_path = fm.get("datapackage", "")
        if datapackage_path:
            rt = _load_runtime_pkg(project_root, datapackage_path)
            if rt is not None:
                fm_license = fm.get("license", "")
                rt_license = rt.get("license", "")
                if fm_license and rt_license and fm_license != rt_license:
                    issues.append(
                        {
                            "code": "dataset_cached_field_drift",
                            "severity": "warning",
                            "entity_id": entity_id,
                            "field": "license",
                            "file_path": str(md),
                            "message": f"license drift: entity={fm_license!r} runtime={rt_license!r}",
                        }
                    )
                fm_ot = sorted(list(fm.get("ontology_terms") or []))
                rt_ot = sorted(list(rt.get("ontology_terms") or []))
                if fm_ot and rt_ot and fm_ot != rt_ot:
                    issues.append(
                        {
                            "code": "dataset_cached_field_drift",
                            "severity": "warning",
                            "entity_id": entity_id,
                            "field": "ontology_terms",
                            "file_path": str(md),
                            "message": f"ontology_terms drift: entity={fm_ot} runtime={rt_ot}",
                        }
                    )
                fm_uc = fm.get("update_cadence", "")
                rt_uc = rt.get("update_cadence", "")
                if fm_uc and rt_uc and fm_uc != rt_uc:
                    issues.append(
                        {
                            "code": "dataset_cached_field_drift",
                            "severity": "warning",
                            "entity_id": entity_id,
                            "field": "update_cadence",
                            "file_path": str(md),
                            "message": f"update_cadence drift: entity={fm_uc!r} runtime={rt_uc!r}",
                        }
                    )

    # Task 6.9: umbrella + lineage invariants (cross-entity, done after per-entity loop)
    # #1: an umbrella entity (has siblings:) must not appear in any other entity's consumed_by
    umbrella_ids = {ds_id for ds_id, fm in datasets_by_id.items() if fm.get("siblings")}
    for ds_id, fm in datasets_by_id.items():
        for cons in list(fm.get("consumed_by") or []):
            if str(cons) in umbrella_ids:
                issues.append(
                    {
                        "code": "dataset_invariant_violation",
                        "severity": "warning",
                        "entity_id": ds_id,
                        "invariant": "umbrella-consumption",
                        "counterpart": str(cons),
                        "file_path": "",
                        "message": f"umbrella {cons} appears in {ds_id}.consumed_by (invariant #1)",
                    }
                )

    # #5: lineage symmetry: parent_dataset ↔ siblings
    for ds_id, fm in datasets_by_id.items():
        for sib_id in list(fm.get("siblings") or []):
            sib_id_str = str(sib_id)
            child_fm = datasets_by_id.get(sib_id_str)
            if child_fm is not None and str(child_fm.get("parent_dataset", "")) != ds_id:
                issues.append(
                    {
                        "code": "dataset_invariant_violation",
                        "severity": "warning",
                        "entity_id": ds_id,
                        "invariant": "lineage-symmetry",
                        "counterpart": sib_id_str,
                        "file_path": "",
                        "message": f"lineage drift: {ds_id} lists sibling {sib_id_str} but {sib_id_str}.parent_dataset != {ds_id}",
                    }
                )

    # Task 6.7: reverse check (rp.displays -> dataset.consumed_by)
    # Re-use already-built datasets_by_id to avoid a third rglob pass.
    ds_consumed_by: dict[str, list[str]] = {
        ds_id: list(fm.get("consumed_by") or []) for ds_id, fm in datasets_by_id.items()
    }
    for rp_id, displays in research_packages.items():
        for ds_id in displays:
            ds_id = str(ds_id)
            cb = ds_consumed_by.get(ds_id)
            if cb is None:
                issues.append(
                    {
                        "code": "dataset_research_package_asymmetric",
                        "severity": "error",
                        "entity_id": ds_id,
                        "counterpart": rp_id,
                        "file_path": "",
                        "message": f"research-package.displays lists {ds_id} but no such dataset entity",
                    }
                )
            elif rp_id not in cb:
                issues.append(
                    {
                        "code": "dataset_research_package_asymmetric",
                        "severity": "error",
                        "entity_id": ds_id,
                        "counterpart": rp_id,
                        "file_path": "",
                        "message": f"{rp_id} displays {ds_id} but the dataset's consumed_by doesn't include the research-package",
                    }
                )

    return InstrumentResult.from_rows(issues)


def _dataset_subject(row: dict):
    entity_id = str(row["entity_id"])
    if not entity_id.startswith("dataset:"):
        entity_id = f"dataset:{entity_id.removeprefix('research-package:')}"
    try:
        return EntitySubject(ref=entity_id)
    except SubjectError as exc:
        raise ValueError(f"dataset anomaly has no valid dataset identity: {row!r}") from exc


def run_check(context: HealthContext):
    observed = check_dataset_anomalies(context.project_root)
    findings = [
        RULES[str(row["code"])].build(
            subject=_dataset_subject(row),
            severity="warn" if row["severity"] == "warning" else "error",
            qualifiers={
                "field": str(row.get("field", _FIELDS[str(row["code"])])),
                "invariant": str(
                    row.get("invariant", _INVARIANTS.get(str(row["code"]), ""))
                ),
                "counterpart": str(row.get("counterpart", "")),
            },
            message=str(row["message"]),
            evidence=(
                [LocationEvidence(path=str(row["file_path"]))]
                if row["file_path"]
                else []
            ),
        )
        for row in observed.rows
    ]
    return composed_result(cast("InstrumentResult[object]", observed), findings)


def _load_workflow_runs(project_root: Path) -> dict[str, dict]:
    """Map workflow-run:<slug> -> raw frontmatter dict."""
    from science_model.frontmatter import parse_frontmatter

    runs: dict[str, dict] = {}
    runs_dir = project_root / "entities" / "workflow-runs"
    if not runs_dir.exists():
        return runs
    for md in runs_dir.rglob("*.md"):
        result = parse_frontmatter(md)
        if not result:
            continue
        fm, _ = result
        if fm.get("kind") == "workflow-run" and fm.get("id"):
            runs[str(fm["id"])] = fm
    return runs


CHECK = HealthCheck(
    name="dataset_anomalies",
    description="Run dataset lineage, access, and package invariant checks.",
    requires_sources=False,
    run=run_check,
    producer=PRODUCER,
)
