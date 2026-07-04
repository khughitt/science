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
from science_tool.dag.retired_edge_migration import (
    RetiredEdgeMigrationPlan,
    RetiredEdgeMigrationRow,
    build_retired_edge_migration_plan,
    migration_plan_to_workbench_yaml,
    render_migration_plan_table,
)
from science_tool.dag.schema import (
    EdgeRecord,
    EdgeStatus,
    EdgesYamlFile,
    Identification,
    PosteriorBlock,
    RefEntry,
    SchemaError,
    load_legacy_edges_yaml,
)
from science_tool.dag.staleness import (
    CandidateTask,
    DriftedEdge,
    StalenessReport,
    UnderReviewedEdge,
    UnpropagatedTask,
    UnresolvedRef,
    check_staleness,
)
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
    "RetiredEdgeMigrationPlan",
    "RetiredEdgeMigrationRow",
    "build_retired_edge_migration_plan",
    "migration_plan_to_workbench_yaml",
    "render_migration_plan_table",
    "EdgeRecord",
    "EdgeStatus",
    "EdgesYamlFile",
    "load_legacy_edges_yaml",
    "edges_from_propositions",
    "load_proposition_edges",
    "proposition_to_edge",
    "Identification",
    "PosteriorBlock",
    "RefEntry",
    "SchemaError",
    "CandidateTask",
    "DriftedEdge",
    "StalenessReport",
    "UnderReviewedEdge",
    "UnpropagatedTask",
    "UnresolvedRef",
    "check_staleness",
    "ValidationFinding",
    "ValidationReport",
    "validate_project",
    "CompileResult",
    "EvidenceStub",
    "WorkbenchFile",
    "WorkbenchRow",
    "compile_workbench",
]
