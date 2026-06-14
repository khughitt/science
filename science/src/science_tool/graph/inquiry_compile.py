"""Compile authored inquiry profiles into legacy-equivalent sci:Inquiry views.

A PatchDefinition with patch_type == "inquiry" authors an `inquiry:` block.
This module renders that block into a dedicated named graph whose identifier
equals the inquiry URI `PROJECT_NS["inquiry/<slug>"]` — the layout the existing
inquiry readers (`graph/store/inquiry.py`, `causal/export_pgmpy.py`) require.
Pure: mutates the provided Dataset in memory, never writes files.
"""

from __future__ import annotations

import hashlib

from rdflib import Dataset, Graph, Literal as RDFLiteral, URIRef
from rdflib.namespace import PROV, RDF, SKOS

from science_model.patch_definition import InquiryProfile, PatchDefinitionEntity
from science_tool.graph.io import DCTERMS_NS, PROJECT_NS, SCI_NS, SCIC_NS, entity_uri_for_ref

_PROFILE_TO_INQUIRY_TYPE = {"investigation": "general", "causal": "causal"}
_FLOW_PREDICATE = {"feedsInto": SCI_NS.feedsInto, "produces": SCI_NS.produces, "causes": SCIC_NS.causes}
_BOUNDARY_ROLE = {"BoundaryIn": SCI_NS.BoundaryIn, "BoundaryOut": SCI_NS.BoundaryOut}


def inquiry_slug(definition: PatchDefinitionEntity) -> str:
    """The inquiry/patch slug — the local part of the patch-definition id."""
    return definition.canonical_id.split(":", 1)[-1]


def inquiry_uri(definition: PatchDefinitionEntity) -> URIRef:
    return URIRef(PROJECT_NS[f"inquiry/{inquiry_slug(definition)}"])


def _node_uri(definition: PatchDefinitionEntity, kind: str, ref: str) -> URIRef:
    """Deterministic URI for an inquiry-internal minted node (assumption / transformation)."""
    local = ref.split(":", 1)[-1].lower()
    return URIRef(PROJECT_NS[f"inquiry/{inquiry_slug(definition)}/{kind}/{local}"])


def inquiry_existing_refs(definition: PatchDefinitionEntity) -> list[str]:
    """Refs the inquiry block contributes that MUST resolve to existing entities.

    Boundary nodes, flow-edge endpoints, flow-edge backing claims (propositions),
    treatment, outcome. The deriver hard-errors any of these that do not resolve
    (design §3) and records them as members with derivationReason "inquiry".
    """
    prof = definition.inquiry
    if prof is None:
        return []
    refs: list[str] = []
    for b in prof.boundary_roles:
        refs.append(b.ref)
    for e in prof.flow_edges:
        refs.append(e.subject)
        refs.append(e.object)
        refs.extend(e.claim_refs)
    if prof.treatment:
        refs.append(prof.treatment)
    if prof.outcome:
        refs.append(prof.outcome)
    return sorted(dict.fromkeys(refs))


def inquiry_minted_uris(definition: PatchDefinitionEntity) -> list[URIRef]:
    """Compiler-minted assumption/transformation node URIs (always typed by the emitter)."""
    prof = definition.inquiry
    if prof is None:
        return []
    uris = [_node_uri(definition, "assumption", a.ref) for a in prof.assumptions]
    uris += [_node_uri(definition, "transformation", t.ref) for t in prof.transformations]
    return sorted(set(uris), key=str)


def emit_inquiry_views(dataset: Dataset, patch_definitions: list[PatchDefinitionEntity]) -> None:
    for definition in sorted(patch_definitions, key=lambda d: d.canonical_id):
        if definition.patch_type != "inquiry" or definition.inquiry is None:
            continue
        _emit_one(dataset, definition, definition.inquiry)


def _emit_one(dataset: Dataset, definition: PatchDefinitionEntity, prof: InquiryProfile) -> None:
    iu = inquiry_uri(definition)
    g: Graph = dataset.graph(iu)
    provenance: Graph = dataset.graph(PROJECT_NS["graph/provenance"])
    focal = entity_uri_for_ref(definition.focal)

    g.add((iu, RDF.type, SCI_NS.Inquiry))
    g.add((iu, SKOS.prefLabel, RDFLiteral(definition.title or inquiry_slug(definition))))
    g.add((iu, SCI_NS.inquiryStatus, RDFLiteral(prof.status)))
    g.add((iu, SCI_NS.inquiryType, RDFLiteral(_PROFILE_TO_INQUIRY_TYPE[prof.profile])))
    g.add((iu, SCI_NS.target, focal))
    g.add((iu, SCI_NS.focalEntity, focal))
    if definition.created:
        g.add((iu, DCTERMS_NS.created, RDFLiteral(definition.created)))

    for b in prof.boundary_roles:
        g.add((entity_uri_for_ref(b.ref), SCI_NS.boundaryRole, _BOUNDARY_ROLE[b.role]))

    for e in prof.flow_edges:
        s = entity_uri_for_ref(e.subject)
        pred = _FLOW_PREDICATE[e.predicate]
        o = entity_uri_for_ref(e.object)
        g.add((s, pred, o))
        if e.claim_refs:
            _emit_edge_claims(g, iu, s, pred, o, e.claim_refs)

    if prof.treatment:
        g.add((iu, SCI_NS.treatment, entity_uri_for_ref(prof.treatment)))
    if prof.outcome:
        g.add((iu, SCI_NS.outcome, entity_uri_for_ref(prof.outcome)))

    for a in prof.assumptions:
        node = _node_uri(definition, "assumption", a.ref)
        g.add((node, RDF.type, SCI_NS.Assumption))
        g.add((node, SKOS.prefLabel, RDFLiteral(a.statement)))
        if a.derived_from:
            provenance.add((node, PROV.wasDerivedFrom, entity_uri_for_ref(a.derived_from)))

    for t in prof.transformations:
        node = _node_uri(definition, "transformation", t.ref)
        g.add((node, RDF.type, SCI_NS.Transformation))
        if t.tool:
            g.add((node, SCI_NS.tool, RDFLiteral(t.tool)))
        if t.validated_by:
            g.add((node, SCI_NS.validatedBy, entity_uri_for_ref(t.validated_by)))
        for p in t.params:
            g.add((node, SCI_NS.paramValue, RDFLiteral(p.value)))
            if p.source:
                g.add((node, SCI_NS.paramSource, RDFLiteral(p.source)))
            if p.ref:
                g.add((node, SCI_NS.paramRef, RDFLiteral(p.ref)))
            if p.note:
                g.add((node, SCI_NS.paramNote, RDFLiteral(p.note)))

    for unknown in prof.unknowns:
        # `Unknown` is an additive marker on the referenced node, not its primary
        # kind: if the ref names an existing entity it stays double-typed, and
        # `_member_kind` still resolves the real kind (concrete sci: types sort
        # before `Unknown`).
        g.add((entity_uri_for_ref(unknown), RDF.type, SCI_NS.Unknown))


def _emit_edge_claims(
    g: Graph, inquiry: URIRef, subject: URIRef, predicate: URIRef, obj: URIRef, claim_refs: list[str]
) -> None:
    """Reify the edge as an rdf:Statement and attach backing claims.

    Matches the shape `graph/store/identity.py::_edge_claims` reads. Full
    subject/predicate/object cross-validation against the proposition (as the
    interactive mutator did) is deferred — see plan §11.
    """
    key = f"{inquiry}\x00{subject}\x00{predicate}\x00{obj}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    statement = URIRef(PROJECT_NS[f"inquiry-edge/{digest}"])
    g.add((statement, RDF.type, RDF.Statement))
    g.add((statement, RDF.subject, subject))
    g.add((statement, RDF.predicate, predicate))
    g.add((statement, RDF.object, obj))
    for claim in dict.fromkeys(claim_refs):
        g.add((statement, SCI_NS.backedByClaim, entity_uri_for_ref(claim)))
