"""DAG rendering and audit pipeline for science."""

from science_tool.dag.audit import AuditReport, ProposedMutation, run_audit
from science_tool.dag.number import number_all, number_one
from science_tool.dag.paths import DagPaths, load_dag_paths
from science_tool.dag.proposition_edges import (
    edges_from_propositions,
    load_proposition_edges,
    proposition_to_edge,
)
from science_tool.dag.refs import RefResolutionError, validate_ref_entry
from science_tool.dag.render import render_all, render_one
from science_tool.dag.schema import RefEntry, SchemaError
from science_tool.dag.validate import (
    ValidationFinding,
    ValidationReport,
    validate_project,
)
from science_tool.dag.workbench import (
    CompileResult,
    EvidenceStub,
    WorkbenchFile,
    WorkbenchRow,
    compile_workbench,
)
from science_tool.dag.workbench_apply import (
    PlannedWorkbenchEdit,
    WorkbenchApplyError,
    WorkbenchApplyPlan,
    WorkbenchApplyResult,
    apply_workbench,
    apply_workbench_plan,
    build_workbench_apply_plan,
)

__all__ = [
    "AuditReport",
    "ProposedMutation",
    "run_audit",
    "DagPaths",
    "load_dag_paths",
    "number_all",
    "number_one",
    "RefResolutionError",
    "validate_ref_entry",
    "render_all",
    "render_one",
    "edges_from_propositions",
    "load_proposition_edges",
    "proposition_to_edge",
    "RefEntry",
    "SchemaError",
    "ValidationFinding",
    "ValidationReport",
    "validate_project",
    "CompileResult",
    "EvidenceStub",
    "WorkbenchFile",
    "WorkbenchRow",
    "compile_workbench",
    "PlannedWorkbenchEdit",
    "WorkbenchApplyError",
    "WorkbenchApplyPlan",
    "WorkbenchApplyResult",
    "apply_workbench",
    "apply_workbench_plan",
    "build_workbench_apply_plan",
]
