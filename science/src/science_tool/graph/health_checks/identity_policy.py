"""Identity-policy health check: entity identity policy and relation endpoint disambiguation."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import TypedDict, cast

from pydantic import BaseModel, ConfigDict
from science_model.audit import EntitySubject, FindingRule, FindingSection, LocationEvidence, PathSubject
from science_model.audit.subjects import SubjectError
from science_model.entities import Entity

from science_tool.findings.producers import FindingProducer
from science_tool.graph.health_checks.base import (
    IDENTITY_REFERENCE_FIELDS,
    NO_ENTITIES_REASON,
    PROJECT_SOURCES_EMPTY,
    HealthCheck,
    HealthContext,
    composed_result,
    context_sources,
)
from science_tool.graph.sources import ProjectSources, load_project_sources
from science_tool.instruments import InstrumentResult


class IdentityPolicyFinding(TypedDict):
    check: str
    entity_id: str
    source_file: str
    message: str


class IdentityPolicyQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check: str


SECTION = FindingSection(id="identity-policy", title="Identity policy", section_order=200)
RULE = FindingRule(
    id="identity.policy-violation",
    severities=frozenset({"warn"}),
    subject_types=frozenset({"entity", "path"}),
    qualifier_schema=IdentityPolicyQualifiers,
    identity_qualifiers=("check",),
    title="Identity policy violation",
    section=SECTION.id,
    display_order=1,
)
PRODUCER = FindingProducer(
    producer_id="identity_policy",
    namespace="health_checks",
    source_module="graph/health_checks/identity_policy.py",
    rules=(RULE,),
    sections=(SECTION,),
)


def _subject(row: IdentityPolicyFinding):
    if row["check"] == "relation_endpoint_disambiguation":
        role = row["message"].split(" ", 1)[0]
        return PathSubject(
            path=row["source_file"],
            pointer=f"relation/{row['entity_id']}/{role}",
        )
    try:
        return EntitySubject(ref=row["entity_id"])
    except (SubjectError, ValueError):
        return PathSubject(path=row["source_file"])


_LOCAL_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_IDENTITY_REQUIRED_KINDS = frozenset(
    {
        "gene",
        "protein",
        "disease",
        "drug",
        "chemical",
        "cell_type",
        "phenotype",
        "anatomy",
        "pathway",
        "process",
        "function",
    }
)
_TAXON_REQUIRED_KINDS = frozenset({"gene", "protein"})


def _coerce_external_curie(raw: object) -> str | None:
    curie = getattr(raw, "curie", None)
    if isinstance(curie, str) and curie.strip():
        return curie.strip()
    if isinstance(raw, str):
        text = raw.strip()
        return text or None
    if isinstance(raw, dict):
        curie = raw.get("curie")
        if isinstance(curie, str) and curie.strip():
            return curie.strip()
        source = raw.get("source")
        identifier = raw.get("id")
        if isinstance(source, str) and isinstance(identifier, str) and source.strip() and identifier.strip():
            return f"{source.strip()}:{identifier.strip()}"
    return None


def collect_identity_policy_findings(
    project_root: Path, *, sources: ProjectSources | None = None
) -> InstrumentResult[IdentityPolicyFinding]:
    """Return identity-policy issues surfaced from loaded entities and relations.

    ``unwired`` when the load produced no entities — no identity was inspected.
    """
    if sources is None:
        sources = load_project_sources(project_root.resolve())
    if not sources.entities:
        return InstrumentResult.unwired(code=PROJECT_SOURCES_EMPTY, reason=NO_ENTITIES_REASON)
    findings: list[IdentityPolicyFinding] = []

    primary_claims: dict[str, list[tuple[str, str]]] = defaultdict(list)
    deprecated_to_canonical: dict[str, str] = {}
    for entity in sources.entities:
        canonical_id = entity.canonical_id
        source_file = entity.file_path
        primary = _coerce_external_curie(getattr(entity, "primary_external_id", None))
        if primary is not None:
            primary_claims[primary].append((canonical_id, source_file))
        for deprecated_id in [str(item) for item in getattr(entity, "deprecated_ids", []) if isinstance(item, str)]:
            deprecated_to_canonical[deprecated_id] = canonical_id

    for curie, claims in primary_claims.items():
        if len(claims) < 2:
            continue
        for canonical_id, source_file in sorted(claims, key=lambda row: row[0])[1:]:
            findings.append(
                IdentityPolicyFinding(
                    check="primary_external_id_collision",
                    entity_id=canonical_id,
                    source_file=source_file,
                    message=f"{curie} is already claimed by another entity",
                )
            )

    for entity in sources.entities:
        _collect_entity_identity_findings(
            entity=entity,
            findings=findings,
            deprecated_to_canonical=deprecated_to_canonical,
        )

    for relation in sources.relations:
        relation_stub = f"{relation.subject} {relation.predicate} {relation.object}".strip()
        for role, ref in (("subject", relation.subject), ("object", relation.object)):
            if ":" not in ref:
                findings.append(
                    IdentityPolicyFinding(
                        check="relation_endpoint_disambiguation",
                        entity_id=relation_stub,
                        source_file=relation.source_path,
                        message=f"{role} {ref!r} is missing a kind prefix",
                    )
                )

    findings.sort(key=lambda row: (row["check"], row["entity_id"], row["source_file"]))
    return InstrumentResult.from_rows(findings)


def _collect_entity_identity_findings(
    *,
    entity: Entity,
    findings: list[IdentityPolicyFinding],
    deprecated_to_canonical: dict[str, str],
) -> None:
    canonical_id = entity.canonical_id
    source_file = entity.file_path
    kind = entity.kind
    primary = _coerce_external_curie(getattr(entity, "primary_external_id", None))
    provisional = bool(getattr(entity, "provisional", False))
    taxon = getattr(entity, "taxon", None)

    if kind in _IDENTITY_REQUIRED_KINDS and primary is None and not provisional:
        findings.append(
            IdentityPolicyFinding(
                check="missing_primary_external_id",
                entity_id=canonical_id,
                source_file=source_file,
                message=f"{kind} entities should carry a primary external id",
            )
        )

    if kind in _TAXON_REQUIRED_KINDS and not taxon and not provisional:
        findings.append(
            IdentityPolicyFinding(
                check="missing_taxon",
                entity_id=canonical_id,
                source_file=source_file,
                message=f"{kind} entities should carry taxon metadata",
            )
        )

    if kind in {"concept", "method", "mechanism"}:
        local_id = canonical_id.split(":", 1)[1] if ":" in canonical_id else canonical_id
        if not _LOCAL_ID_RE.fullmatch(local_id):
            findings.append(
                IdentityPolicyFinding(
                    check="invalid_local_id_syntax",
                    entity_id=canonical_id,
                    source_file=source_file,
                    message="local ids must use lowercase kebab-case",
                )
            )

    for deprecated_id in [str(item) for item in getattr(entity, "deprecated_ids", []) if isinstance(item, str)]:
        deprecated_to_canonical[deprecated_id] = canonical_id

    for field_name in IDENTITY_REFERENCE_FIELDS:
        refs = getattr(entity, field_name, None)
        if not isinstance(refs, list):
            continue
        for ref in [str(item) for item in refs if isinstance(item, str)]:
            target = deprecated_to_canonical.get(ref)
            if target is None:
                continue
            findings.append(
                IdentityPolicyFinding(
                    check="deprecated_id_inbound_ref",
                    entity_id=canonical_id,
                    source_file=source_file,
                    message=f"{field_name} references deprecated id {ref} from {target}",
                )
            )


def run_check(context: HealthContext):
    observed = collect_identity_policy_findings(
        context.project_root,
        sources=context_sources(context),
    )
    findings = [
        RULE.build(
            subject=_subject(row),
            severity="warn",
            qualifiers={"check": row["check"]},
            message=row["message"],
            evidence=[LocationEvidence(path=row["source_file"])],
        )
        for row in observed.rows
    ]
    return composed_result(cast("InstrumentResult[object]", observed), findings)


CHECK = HealthCheck(
    name="identity_policy",
    description="Validate entity identity policy and relation endpoint disambiguation.",
    requires_sources=True,
    run=run_check,
    producer=PRODUCER,
)
