from __future__ import annotations

import hashlib
import importlib
import importlib.resources
import json
import re
import subprocess
from collections import deque
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, NotRequired, TypedDict, cast

import click
from rdflib import Dataset, Graph, Literal, Namespace, URIRef
from rdflib.namespace import PROV, RDF, SKOS, XSD
from science_model.profiles import CORE_PROFILE
from science_model.profiles.schema import RelationKind
from science_model.reasoning import MeasurementModel, RivalModelPacket
from science_model.relations import relation_allows_kinds

from science_tool.graph.export_types import (
    GraphExportEdge,
    GraphExportLayer,
    GraphExportNode,
    GraphExportOverlays,
    GraphExportPayload,
    GraphExportScope,
    build_graph_export_edge_id,
    build_graph_export_node_id,
)
from science_tool.graph.io import (
    BIOLINK_NS,
    CITO_NS,
    DCTERMS_NS,
    PROJECT_NS,
    REVISION_URI,
    SCHEMA_NS,
    SCI_NS,
    SCIC_NS,
    build_input_manifest as _build_input_manifest,
    project_root_from_graph_path as _project_root_from_graph_path,
    read_revision_manifest as _read_revision_manifest,
    save_canonical_graph_dataset,
)
from science_tool.graph.belief import aggregate_belief, collect_evidence_units
from science_tool.graph.sources import is_metadata_reference

from .constants import (DEFAULT_GRAPH_PATH, VALID_INQUIRY_TYPES, GRAPH_LAYERS, GRAPH_EXPORT_SCHEMA_VERSION, GRAPH_EXPORT_VISIBLE_LAYERS, GRAPH_EXPORT_EDGE_METADATA_PREDICATES, CURIE_PREFIXES, PROJECT_ENTITY_PREFIXES, PROJECT_ENTITY_PREFIX_KINDS, _RELATION_KIND_BY_PREDICATE, STRUCTURED_PROPOSITION_PREDICATES, EVIDENCE_STANCE_PREDICATES, INITIAL_GRAPH_TEMPLATE, PREDICATE_REGISTRY, BIOLINK_NS, CITO_NS, DCTERMS_NS, PROJECT_NS, REVISION_URI, SCHEMA_NS, SCI_NS, SCIC_NS)
from .types import (InquiryEdge, InquiryInfo, ClaimSummaryData, NeighborhoodSummaryData, QuestionSummaryData, PropositionEvidenceLine, PropositionPhase1Metadata, PropositionEvidenceSemantics, PropositionInteractionTerm, FalsificationRecord, EvidenceClaimBundle, EvidenceEdgeOverlay, EvidenceOverlayData, InquirySummaryData, ProjectSummaryData, EvidenceSignalSummary)
from .graphutil import _has_cycle


from .identity import (_entity_kind_from_uri, canonical_id_from_entity_uri, _slug, _graph_uri, _derive_relation_claim_text, _relation_claim_label, _edge_claims, _edge_statement_uri, _resolve_term, _resolve_center_entity, _about_tokens, shorten_uri, _short_name)
from .notebooks import (_uv_lock, _NOTEBOOKS_PYPROJECT, _copy_viz_notebook)
from .dataset import (init_graph_file, read_graph_stats, _load_dataset, _save_dataset, save_graph_dataset)
from .evidence_signals import (_linked_claims_for_hypothesis, _source_strings, _load_proposition_phase1_metadata, _load_proposition_evidence_semantics, _load_proposition_pre_registrations, _load_proposition_interaction_terms, _load_proposition_bridge_hypotheses, _load_proposition_falsifications, _json_literal, _evidence_targets_for_uri, _collect_evidence_signals, _apply_phase1_metadata_to_bundle, _apply_evidence_semantics_to_bundle, _evidence_type_strings, _collect_evidence_types)
from .mutations import (add_concept, add_article, add_proposition, add_observation, add_evidence_edge, add_finding, add_interpretation, add_discussion, add_falsification, add_mechanism, add_story, add_paper_entity, add_hypothesis, add_question, add_edge, add_inquiry, add_inquiry_node, add_inquiry_edge, add_assumption, add_transformation, add_data_package, set_boundary_role, set_param_metadata, migrate_addresses_direction, _warn_on_relation_direction_mismatch, _attach_edge_claims)
from .export import export_graph_payload
from .inquiry import (list_inquiries, get_inquiry, set_treatment_outcome, render_inquiry_doc, validate_inquiry)
from .snapshot import (import_snapshot, stamp_revision)
from .validation import (query_predicates, validate_graph, diff_graph_inputs)
from .queries import (query_neighborhood, query_claims, query_evidence)
from .summary import (query_dashboard_summary, query_neighborhood_summary, query_question_summary, query_inquiry_summary, query_project_summary, query_coverage, query_gaps, query_uncertainty, _claim_summary_data)


def build_graph_dot(
    graph_path: Path,
    graph_layer: str,
    center: str | None,
    hops: int,
    limit: int,
) -> str:
    if center:
        rows = query_neighborhood(
            graph_path=graph_path,
            center=center,
            hops=hops,
            graph_layer=graph_layer,
            limit=limit,
        )
    else:
        dataset = _load_dataset(graph_path)
        layer = dataset.graph(_graph_uri(graph_layer))
        rows = []
        for subj, pred, obj in layer:
            if isinstance(subj, URIRef) and isinstance(obj, URIRef):
                rows.append(
                    {
                        "subject": str(subj),
                        "predicate": str(pred),
                        "object": str(obj),
                    }
                )
            if len(rows) >= limit:
                break

    lines = ["digraph G {", "  rankdir=LR;"]
    nodes: set[str] = set()
    for row in rows:
        subj = row["subject"]
        obj = row["object"]
        pred = row["predicate"]
        nodes.add(subj)
        nodes.add(obj)
        lines.append(f'  "{_short_name(subj)}" -> "{_short_name(obj)}" [label="{_short_name(pred)}"];')
    for node in sorted(nodes):
        lines.append(f'  "{_short_name(node)}";')
    lines.append("}")
    return "\n".join(lines) + "\n"


