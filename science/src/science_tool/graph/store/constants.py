from __future__ import annotations

from pathlib import Path

from rdflib import Namespace, URIRef
from rdflib.namespace import PROV, RDF, SKOS, XSD
from science_model.profiles import CORE_PROFILE
from science_model.profiles.schema import RelationKind

from science_tool.graph.io import (
    BIOLINK_NS,
    CITO_NS,
    DCTERMS_NS,
    PROJECT_NS,
    REVISION_URI,
    SCHEMA_NS,
    SCI_NS,
    SCIC_NS,
)

DEFAULT_GRAPH_PATH = Path("knowledge/graph.trig")

VALID_INQUIRY_TYPES: tuple[str, ...] = ("general", "causal")

GRAPH_LAYERS: tuple[str, ...] = (
    "graph/knowledge",
    "graph/bridge",
    "graph/causal",
    "graph/provenance",
    "graph/datasets",
)
GRAPH_EXPORT_SCHEMA_VERSION = "1"
GRAPH_EXPORT_VISIBLE_LAYERS: tuple[str, ...] = (
    "graph/knowledge",
    "graph/bridge",
    "graph/causal",
    "graph/datasets",
)
GRAPH_EXPORT_EDGE_METADATA_PREDICATES: frozenset[URIRef] = frozenset(
    {
        RDF.type,
        RDF.subject,
        RDF.predicate,
        RDF.object,
        SKOS.prefLabel,
        SKOS.note,
        PROV.wasDerivedFrom,
        DCTERMS_NS.created,
        SCHEMA_NS.name,
        SCHEMA_NS.dateModified,
        SCHEMA_NS.text,
        SCHEMA_NS.description,
        SCHEMA_NS.identifier,
        SCHEMA_NS.sha256,
        SCI_NS.inquiryStatus,
        SCI_NS.inquiryType,
        SCI_NS.target,
        SCI_NS.boundaryRole,
        SCI_NS.treatment,
        SCI_NS.outcome,
        SCI_NS.tool,
        SCI_NS.paramValue,
        SCI_NS.paramSource,
        SCI_NS.paramNote,
        SCI_NS.paramRef,
        SCI_NS.backedByClaim,
        SCI_NS.validatedBy,
        SCI_NS.projectStatus,
        SCI_NS.scope,
        SCI_NS.sourceClass,
        SCI_NS.hasDatasetUsage,
        SCI_NS.dataset,
        SCI_NS.usageRole,
        SCI_NS.usageOverlap,
        SCI_NS.usageSource,
        SCI_NS.confidence,
        SCI_NS.evidenceType,
        SCI_NS.evidenceStrength,
        SCI_NS.evidenceCaveats,
        SCI_NS.evidenceMethod,
        SCI_NS.evidenceIndependence,
        SCI_NS.compositionalStatus,
        SCI_NS.compositionalMethod,
        SCI_NS.compositionalNote,
        SCI_NS.platformPattern,
        SCI_NS.datasetEffects,
        SCI_NS.evidenceLine,
        SCI_NS.statisticalSupport,
        SCI_NS.mechanisticSupport,
        SCI_NS.replicationScope,
        SCI_NS.claimStatus,
        SCI_NS.preRegisteredIn,
        SCI_NS.interactionTerm,
        SCI_NS.bridgeBetween,
        SCI_NS.falsifies,
        SCI_NS.supersedesClaim,
        CITO_NS.supports,
        CITO_NS.disputes,
        CITO_NS.discusses,
    }
)

CURIE_PREFIXES: dict[str, Namespace] = {
    "sci": SCI_NS,
    "scic": SCIC_NS,
    "schema": SCHEMA_NS,
    "prov": Namespace(str(PROV)),
    "skos": Namespace(str(SKOS)),
    "rdf": Namespace(str(RDF)),
    "biolink": BIOLINK_NS,
    "cito": CITO_NS,
    "dcterms": DCTERMS_NS,
}
# Graph-store helpers only recognize actively authored project entity prefixes.
# Legacy `topic:` refs are still handled by the unified loaders/materializer,
# but are intentionally omitted here so direct graph-store authoring does not
# continue expanding topic usage.
PROJECT_ENTITY_PREFIXES: set[str] = {
    "proposition",
    "observation",
    "concept",
    "hypothesis",
    "dataset",
    "question",
    "inquiry",
    "task",
    "data-package",
    "workflow-run",
    "finding",
    "interpretation",
    "story",
    "mechanism",
    "paper",
    "article",
    "falsification",
    "pre-registration",
    "chain",
    "chain-audit",
}
PROJECT_ENTITY_PREFIX_KINDS: dict[str, str] = {
    **{prefix: prefix for prefix in PROJECT_ENTITY_PREFIXES},
    "chain": "structural-chain",
}

# Lookup of `predicate URI -> relation kind`,
# derived once from CORE_PROFILE so add_edge can warn on direction mistakes
# without scanning the profile on every call.
_RELATION_KIND_BY_PREDICATE: dict[URIRef, RelationKind] = {
    URIRef(SCI_NS[rk.predicate.split(":", 1)[1]] if rk.predicate.startswith("sci:") else rk.predicate): rk
    for rk in CORE_PROFILE.relation_kinds
    if rk.predicate.startswith("sci:")
}

STRUCTURED_PROPOSITION_PREDICATES: frozenset[URIRef] = frozenset(
    {
        SCI_NS.relatedTo,
        SCIC_NS.causes,
        SCIC_NS.confounds,
        CITO_NS.supports,
        CITO_NS.disputes,
        CITO_NS.discusses,
    }
)

# Predicates that require explicit epistemic tracking via add_evidence_edge
EVIDENCE_STANCE_PREDICATES: frozenset[URIRef] = frozenset(
    {
        CITO_NS.supports,
        CITO_NS.disputes,
    }
)

INITIAL_GRAPH_TEMPLATE = """@prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:   <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:    <http://www.w3.org/2001/XMLSchema#> .
@prefix skos:   <http://www.w3.org/2004/02/skos/core#> .
@prefix prov:   <http://www.w3.org/ns/prov#> .
@prefix schema: <https://schema.org/> .
@prefix sci:    <http://example.org/science/vocab/> .
@prefix scic:   <http://example.org/science/vocab/causal/> .
@prefix :       <http://example.org/project/> .

<http://example.org/project/graph/knowledge> {
}

<http://example.org/project/graph/bridge> {
}

<http://example.org/project/graph/causal> {
}

<http://example.org/project/graph/provenance> {
}

<http://example.org/project/graph/datasets> {
}
"""

PREDICATE_REGISTRY: list[dict[str, str]] = [
    {"predicate": "skos:related", "description": "General association between concepts", "layer": "graph/knowledge"},
    {"predicate": "skos:broader", "description": "Broader concept hierarchy", "layer": "graph/knowledge"},
    {"predicate": "skos:narrower", "description": "Narrower concept hierarchy", "layer": "graph/knowledge"},
    {"predicate": "cito:supports", "description": "Evidence edge: supports proposition", "layer": "graph/knowledge"},
    {"predicate": "cito:disputes", "description": "Evidence edge: disputes proposition", "layer": "graph/knowledge"},
    {"predicate": "cito:discusses", "description": "Structural link to hypothesis/topic", "layer": "graph/knowledge"},
    {"predicate": "cito:extends", "description": "Work extends prior research", "layer": "graph/knowledge"},
    {"predicate": "cito:usesMethodIn", "description": "Uses method from another work", "layer": "graph/knowledge"},
    {"predicate": "cito:citesAsDataSource", "description": "Cites as data source", "layer": "graph/knowledge"},
    {"predicate": "sci:evaluates", "description": "Benchmark evaluates model/method", "layer": "graph/knowledge"},
    {"predicate": "sci:hasModality", "description": "Model/method operates on modality", "layer": "graph/knowledge"},
    {"predicate": "sci:detectedBy", "description": "Feature detected by method/tool", "layer": "graph/knowledge"},
    {"predicate": "sci:storedIn", "description": "Data stored in database/repository", "layer": "graph/knowledge"},
    {"predicate": "sci:measuredBy", "description": "Variable measured by dataset", "layer": "graph/datasets"},
    {"predicate": "sci:projectStatus", "description": "Project status of entity", "layer": "graph/knowledge"},
    {
        "predicate": "sci:sourceClass",
        "description": "Dataset epistemic source class (observational | derived | reference)",
        "layer": "graph/knowledge",
    },
    {
        "predicate": "sci:hasDatasetUsage",
        "description": "Links a consumer entity to a reified dataset usage record",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:dataset",
        "description": "Dataset referenced by a reified dataset usage record",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:usageRole",
        "description": "Role of a dataset in a reified usage record",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:usageOverlap",
        "description": "Overlap of a dataset usage record: full, partial, or unknown",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:usageSource",
        "description": "Projection source for a reified dataset usage record",
        "layer": "graph/provenance",
    },
    {"predicate": "sci:confidence", "description": "Confidence score (0.0-1.0)", "layer": "graph/provenance"},
    {
        "predicate": "sci:evidenceType",
        "description": "Evidence classification for propositions",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:compositionalStatus",
        "description": "Compositional robustness status for proposition-backed claims",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:compositionalMethod",
        "description": "Normalization or per-cell method used for compositional checks",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:compositionalNote",
        "description": "Free-text note about compositional robustness results",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:platformPattern",
        "description": "Summary label for cross-platform heterogeneity",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:datasetEffects",
        "description": "Per-dataset effect summary encoded as JSON",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:evidenceLine",
        "description": "Structured evidence-line provenance encoded as JSON",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:statisticalSupport",
        "description": "Explicit statistical support classification for a proposition",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:mechanisticSupport",
        "description": "Explicit mechanistic support classification for a proposition",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:replicationScope",
        "description": "Explicit replication scope classification for a proposition",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:claimStatus",
        "description": "Explicit current lifecycle status for a proposition-backed claim",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:claimLayer",
        "description": "Authored claim layer for a proposition",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:identificationStrength",
        "description": "Normalized causal leverage or identification strength",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:proxyDirectness",
        "description": "How directly a claim or evidence line refers to the target construct",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:supportsScope",
        "description": "Authored review-radius hint for how widely a claim update should propagate",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:independenceGroup",
        "description": "Authored independence grouping for evidence lines or proposition bundles",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:evidenceRole",
        "description": "Role of a proposition or evidence line in support / criticism",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:measurementModel",
        "description": "JSON-encoded measurement/proxy model for a proposition",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:rivalModelPacket",
        "description": "JSON-encoded rival-model packet for a proposition",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:preRegisteredIn",
        "description": "Link from a claim to an existing pre-registration record or slug",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:interactionTerm",
        "description": "Structured interaction/effect-modification term encoded as JSON",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:bridgeBetween",
        "description": "Claim explicitly bridges multiple hypotheses",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:falsifies",
        "description": "Falsification record linked to a proposition",
        "layer": "graph/knowledge",
    },
    {
        "predicate": "sci:sourceOfPrediction",
        "description": "Origin of the prediction that was later falsified",
        "layer": "graph/knowledge",
    },
    {"predicate": "sci:predicted", "description": "Predicted claim before falsification", "layer": "graph/knowledge"},
    {
        "predicate": "sci:observed",
        "description": "Observed result contradicting the prediction",
        "layer": "graph/knowledge",
    },
    {"predicate": "sci:decision", "description": "Decision taken after falsification", "layer": "graph/knowledge"},
    {
        "predicate": "sci:supersedesClaim",
        "description": "Claim superseded by a falsification decision",
        "layer": "graph/knowledge",
    },
    {"predicate": "sci:epistemicStatus", "description": "Epistemic status of proposition", "layer": "graph/provenance"},
    # Project Model compositional predicates
    {"predicate": "sci:addresses", "description": "Question addresses proposition", "layer": "graph/knowledge"},
    {
        "predicate": "sci:groundedBy",
        "description": "Finding grounded by data-package or workflow-run",
        "layer": "graph/knowledge",
    },
    {"predicate": "sci:synthesizes", "description": "Story synthesizes interpretation", "layer": "graph/knowledge"},
    {
        "predicate": "sci:organizedBy",
        "description": "Story organized by question or hypothesis",
        "layer": "graph/knowledge",
    },
    {"predicate": "sci:comprises", "description": "Paper comprises stories", "layer": "graph/knowledge"},
    {"predicate": "sci:grounds", "description": "Workflow-run grounds observation", "layer": "graph/provenance"},
    {"predicate": "sci:dataSource", "description": "Observation data source reference", "layer": "graph/knowledge"},
    {
        "predicate": "sci:evidenceStrength",
        "description": "Evidence edge strength annotation",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:evidenceCaveats",
        "description": "Evidence edge caveats annotation",
        "layer": "graph/provenance",
    },
    {"predicate": "sci:evidenceMethod", "description": "Evidence edge method annotation", "layer": "graph/provenance"},
    {"predicate": "sci:maturity", "description": "Maturity of open question", "layer": "graph/knowledge"},
    {"predicate": "scic:causes", "description": "Causal relationship", "layer": "graph/causal"},
    {"predicate": "scic:confounds", "description": "Confounding relationship", "layer": "graph/causal"},
    {"predicate": "prov:wasDerivedFrom", "description": "Provenance source", "layer": "graph/provenance"},
    # Inquiry predicates
    {"predicate": "sci:target", "description": "Inquiry targets hypothesis/question", "layer": "inquiry"},
    {"predicate": "sci:boundaryRole", "description": "Boundary classification within inquiry", "layer": "inquiry"},
    {"predicate": "sci:inquiryStatus", "description": "Inquiry lifecycle status", "layer": "inquiry"},
    {"predicate": "sci:feedsInto", "description": "Data/information flow", "layer": "inquiry"},
    {"predicate": "sci:assumes", "description": "Dependency on assumption", "layer": "inquiry"},
    {"predicate": "sci:produces", "description": "Transformation yields output", "layer": "inquiry"},
    {"predicate": "sci:paramValue", "description": "Parameter value", "layer": "inquiry"},
    {"predicate": "sci:paramSource", "description": "Parameter source type", "layer": "inquiry"},
    {"predicate": "sci:paramRef", "description": "Parameter reference", "layer": "inquiry"},
    {"predicate": "sci:paramNote", "description": "Parameter rationale", "layer": "inquiry"},
    {"predicate": "sci:observability", "description": "Variable observability status", "layer": "graph/knowledge"},
    {"predicate": "sci:backedByClaim", "description": "Inquiry edge backed by proposition", "layer": "inquiry"},
    {"predicate": "sci:validatedBy", "description": "Step validated by criterion", "layer": "inquiry"},
    {"predicate": "sci:inquiryType", "description": "Inquiry type (general, causal)", "layer": "inquiry"},
    {
        "predicate": "sci:treatment",
        "description": "Treatment/intervention variable in causal inquiry",
        "layer": "inquiry",
    },
    {"predicate": "sci:outcome", "description": "Outcome variable in causal inquiry", "layer": "inquiry"},
    # Model-parameter structure predicates (natural-systems-guide)
    {"predicate": "sci:hasParameter", "description": "Model uses canonical parameter", "layer": "graph/knowledge"},
    {"predicate": "sci:approximates", "description": "Model approximates another model", "layer": "graph/knowledge"},
    {"predicate": "sci:limitOf", "description": "Model is a limit case of another", "layer": "graph/knowledge"},
    {"predicate": "sci:dualOf", "description": "Models are dual formulations", "layer": "graph/knowledge"},
    {"predicate": "sci:coarseGrainOf", "description": "Model is coarse-grained version", "layer": "graph/knowledge"},
    {"predicate": "sci:coupledWith", "description": "Models coupled in multi-physics", "layer": "graph/knowledge"},
    {
        "predicate": "sci:analogousTo",
        "description": "Structure-preserving cross-domain analogy",
        "layer": "graph/knowledge",
    },
    {
        "predicate": "sci:competesWithParam",
        "description": "Parameters have competing effects",
        "layer": "graph/knowledge",
    },
    {
        "predicate": "sci:controlsOnset",
        "description": "Parameter controls bifurcation/onset",
        "layer": "graph/knowledge",
    },
]
