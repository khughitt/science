"""Shared data models for Science research framework."""

from science_model.activity import ActivityItem
from science_model.config import ConfigUpdate, DashboardConfig, LodWeights
from science_model.entities import (
    BayesFactorEvidence,
    ChainAuditEntity,
    ChainAuditInterpretation,
    Entity,
    EntityType,
    EntityUpdate,
    MechanismEntity,
    StructuralChainEntity,
)
from science_model.graph import GraphData, GraphEdge, GraphNode, GraphSummary
from science_model.identity import EntityScope, ExternalId
from science_model.ids import CanonicalId, normalize_alias
from science_model.ontologies.schema import OntologyCatalog, OntologyPredicate, OntologyRegistryEntry, OntologyTermType
from science_model.projects import Project, ProjectDetail
from science_model.reasoning import (
    ClaimLayer,
    DisputeScope,
    EvidenceRole,
    EvidenceStance,
    EvidenceStrength,
    IdentificationStrength,
    IndependenceTag,
    MeasurementModel,
    PropositionMetadata,
    ProxyDirectness,
    RivalModelPacket,
    SupportScope,
)
from science_model.profiles import EntityKind, ProfileManifest, RelationKind
from science_model.provenance import EvidenceIndependence, ProvenanceType
from science_model.relations import build_relation_registry
from science_model.search import Filters, SearchResult
from science_model.sync import SyncSource
from science_model.source_contracts import AuthoredTargetedRelation, BindingSource, ModelSource, ParameterSource
from science_model.packages import (
    ResearchPackageDescriptor,
    ValidationResult,
    check_freshness,
    parse_cells,
    validate_package,
)
from science_model.tasks import Task, TaskCreate, TaskStatus, TaskUpdate
from science_model.entity_schema import (
    EntityValidationError,
    EntityValidator,
    MergePolicy,
    SharedEntity,
)

__all__ = [
    "ActivityItem",
    "BayesFactorEvidence",
    "CanonicalId",
    "ChainAuditEntity",
    "ChainAuditInterpretation",
    "ConfigUpdate",
    "DashboardConfig",
    "ClaimLayer",
    "DisputeScope",
    "Entity",
    "EntityKind",
    "EntityType",
    "EntityValidationError",
    "EntityValidator",
    "EvidenceIndependence",
    "EvidenceRole",
    "EvidenceStance",
    "EvidenceStrength",
    "PropositionMetadata",
    "EntityScope",
    "EntityUpdate",
    "Filters",
    "GraphData",
    "GraphEdge",
    "GraphNode",
    "GraphSummary",
    "IdentificationStrength",
    "IndependenceTag",
    "LodWeights",
    "ProfileManifest",
    "Project",
    "ProvenanceType",
    "ProjectDetail",
    "MeasurementModel",
    "MechanismEntity",
    "MergePolicy",
    "ModelSource",
    "ParameterSource",
    "BindingSource",
    "AuthoredTargetedRelation",
    "ProxyDirectness",
    "RelationKind",
    "RivalModelPacket",
    "ResearchPackageDescriptor",
    "SearchResult",
    "SharedEntity",
    "SupportScope",
    "SyncSource",
    "StructuralChainEntity",
    "ExternalId",
    "Task",
    "TaskCreate",
    "TaskStatus",
    "TaskUpdate",
    "ValidationResult",
    "build_relation_registry",
    "check_freshness",
    "normalize_alias",
    "OntologyCatalog",
    "OntologyPredicate",
    "OntologyRegistryEntry",
    "OntologyTermType",
    "parse_cells",
    "validate_package",
]
