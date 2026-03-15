"""Shared data models for Science research framework."""

from science_model.activity import ActivityItem
from science_model.config import ConfigUpdate, DashboardConfig, LodWeights
from science_model.entities import Entity, EntityType, EntityUpdate
from science_model.graph import GraphData, GraphEdge, GraphNode, GraphSummary
from science_model.ids import CanonicalId, normalize_alias
from science_model.projects import Project, ProjectDetail
from science_model.profiles import EntityKind, ProfileManifest, RelationKind
from science_model.relations import build_relation_registry
from science_model.search import Filters, SearchResult
from science_model.source_contracts import AuthoredTargetedRelation, BindingSource, ModelSource, ParameterSource
from science_model.tasks import Task, TaskCreate, TaskStatus, TaskUpdate

__all__ = [
    "ActivityItem",
    "CanonicalId",
    "ConfigUpdate",
    "DashboardConfig",
    "Entity",
    "EntityKind",
    "EntityType",
    "EntityUpdate",
    "Filters",
    "GraphData",
    "GraphEdge",
    "GraphNode",
    "GraphSummary",
    "LodWeights",
    "ProfileManifest",
    "Project",
    "ProjectDetail",
    "ModelSource",
    "ParameterSource",
    "BindingSource",
    "AuthoredTargetedRelation",
    "RelationKind",
    "SearchResult",
    "Task",
    "TaskCreate",
    "TaskStatus",
    "TaskUpdate",
    "build_relation_registry",
    "normalize_alias",
]
