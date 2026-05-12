from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_model.contracts.inventory_v1 import (
    InventoryAlias,
    InventoryEntity,
    InventoryFindingCandidate,
    InventoryPayload,
    InventoryProjectMetadata,
    InventoryReference,
    InventorySourceLocation,
    InventoryWarning,
    compute_audit_hash,
    compute_content_hash,
    finalize_inventory_payload,
)


def test_inventory_payload_hashes_ignore_generated_at() -> None:
    entity = InventoryEntity(
        id="finding:landscape-topology",
        kind="finding",
        local_id="landscape-topology",
        title="Landscape topology",
        status="active",
        activity="active",
        source=InventorySourceLocation(
            adapter="markdown",
            path="doc/findings/landscape-topology.md",
            address="frontmatter",
        ),
    )
    alias = InventoryAlias(alias="f001", canonical_id="finding:landscape-topology")
    warning = InventoryWarning(
        code="deprecated-prose-reference",
        severity="warning",
        message="Markdown prose references deprecated ID h4.",
        path="doc/summary.md",
    )

    first = InventoryPayload(
        generated_at="2026-05-12T10:00:00Z",
        project_id="multiple-myeloma",
        entities=[entity],
        aliases=[alias],
        warnings=[warning],
        watch_paths=["doc", "knowledge", "results", "tasks"],
    )
    second = first.model_copy(update={"generated_at": "2026-05-12T10:01:00Z"})

    assert compute_content_hash(first) == compute_content_hash(second)
    assert compute_audit_hash(first) == compute_audit_hash(second)


def test_inventory_payload_sorts_stable_collections_for_hashing() -> None:
    left = InventoryPayload(
        generated_at="2026-05-12T10:00:00Z",
        project_id="natural-systems",
        entities=[
            InventoryEntity(
                id="question:q02",
                kind="question",
                local_id="q02",
                title="Second",
                source=InventorySourceLocation(adapter="markdown", path="doc/q02.md"),
            ),
            InventoryEntity(
                id="question:q01",
                kind="question",
                local_id="q01",
                title="First",
                source=InventorySourceLocation(adapter="markdown", path="doc/q01.md"),
            ),
        ],
    )
    right = left.model_copy(update={"entities": list(reversed(left.entities))})

    assert compute_content_hash(left) == compute_content_hash(right)


def test_inventory_models_reject_compatible_type_coercion() -> None:
    source_location_data: dict[str, object] = {
        "adapter": "markdown",
        "path": "doc/source.md",
        "line": "3",
    }
    alias_data: dict[str, object] = {
        "alias": 123,
        "canonical_id": "finding:landscape-topology",
    }

    with pytest.raises(ValidationError, match="line"):
        InventorySourceLocation.model_validate(source_location_data)

    with pytest.raises(ValidationError, match="alias"):
        InventoryAlias.model_validate(alias_data)


def test_inventory_payload_normalizes_nested_entity_collections_for_hashing() -> None:
    source = InventorySourceLocation(adapter="markdown", path="doc/finding.md")
    left = InventoryPayload(
        generated_at="2026-05-12T10:00:00Z",
        project_id="natural-systems",
        entities=[
            InventoryEntity(
                id="finding:f01",
                kind="finding",
                local_id="f01",
                source=source,
                aliases=["f001", "finding-one"],
                source_refs=["paper:beta", "paper:alpha"],
                targets=["question:q02", "question:q01"],
                deprecated_ids=["old:f02", "old:f01"],
                related=[
                    InventoryReference(relation="supports", target_id="hypothesis:h02"),
                    InventoryReference(relation="supports", target_id="hypothesis:h01"),
                ],
            )
        ],
    )
    right = left.model_copy(
        update={
            "entities": [
                left.entities[0].model_copy(
                    update={
                        "aliases": list(reversed(left.entities[0].aliases)),
                        "source_refs": list(reversed(left.entities[0].source_refs)),
                        "targets": list(reversed(left.entities[0].targets)),
                        "deprecated_ids": list(reversed(left.entities[0].deprecated_ids)),
                        "related": list(reversed(left.entities[0].related)),
                    }
                )
            ]
        }
    )

    assert compute_content_hash(left) == compute_content_hash(right)


def test_inventory_payload_normalizes_project_metadata_collections_for_hashing() -> None:
    left = InventoryPayload(
        generated_at="2026-05-12T10:00:00Z",
        project_id="natural-systems",
        project=InventoryProjectMetadata(
            id="natural-systems",
            name="Natural systems",
            aspects=["ecology", "hydrology"],
            tags=["field", "model"],
        ),
    )
    project = left.project
    assert project is not None
    right = left.model_copy(
        update={
            "project": project.model_copy(
                update={
                    "aspects": list(reversed(project.aspects)),
                    "tags": list(reversed(project.tags)),
                }
            )
        }
    )

    assert compute_content_hash(left) == compute_content_hash(right)


def test_inventory_audit_hash_normalizes_project_metadata_collections() -> None:
    left = InventoryPayload(
        generated_at="2026-05-12T10:00:00Z",
        project_id="natural-systems",
        project=InventoryProjectMetadata(
            id="natural-systems",
            name="Natural systems",
            aspects=["ecology", "hydrology"],
            tags=["field", "model"],
        ),
    )
    project = left.project
    assert project is not None
    right = left.model_copy(
        update={
            "project": project.model_copy(
                update={
                    "aspects": list(reversed(project.aspects)),
                    "tags": list(reversed(project.tags)),
                }
            )
        }
    )

    assert compute_audit_hash(left) == compute_audit_hash(right)


def test_inventory_payload_normalizes_finding_candidate_targets_for_hashing() -> None:
    source = InventorySourceLocation(adapter="markdown", path="doc/candidate.md")
    left = InventoryPayload(
        generated_at="2026-05-12T10:00:00Z",
        project_id="natural-systems",
        finding_candidates=[
            InventoryFindingCandidate(
                candidate_id="candidate:one",
                title="Candidate one",
                targets=["question:q02", "question:q01"],
                source=source,
                reason="Referenced in synthesis.",
            )
        ],
    )
    right = left.model_copy(
        update={
            "finding_candidates": [
                left.finding_candidates[0].model_copy(
                    update={"targets": list(reversed(left.finding_candidates[0].targets))}
                )
            ]
        }
    )

    assert compute_content_hash(left) == compute_content_hash(right)


def test_inventory_entity_rejects_inconsistent_canonical_id_parts() -> None:
    with pytest.raises(ValidationError, match="must match"):
        InventoryEntity(
            id="finding:wrong-id",
            kind="finding",
            local_id="landscape-topology",
            source=InventorySourceLocation(adapter="markdown", path="doc/finding.md"),
        )


def test_inventory_entity_rejects_non_json_data_values() -> None:
    with pytest.raises(ValidationError, match="JSON"):
        InventoryEntity(
            id="finding:f01",
            kind="finding",
            local_id="f01",
            source=InventorySourceLocation(adapter="markdown", path="doc/finding.md"),
            data={"bad": object()},
        )


def test_inventory_entity_accepts_json_data_values_for_hashing() -> None:
    entity = InventoryEntity(
        id="finding:f01",
        kind="finding",
        local_id="f01",
        source=InventorySourceLocation(adapter="markdown", path="doc/finding.md"),
        data={
            "name": "Landscape topology",
            "rank": 3,
            "score": 0.75,
            "active": True,
            "optional": None,
            "tags": ["alpha", "beta"],
            "metrics": {"effect": 1.2, "count": 4},
        },
    )
    payload = InventoryPayload(
        generated_at="2026-05-12T10:00:00Z",
        project_id="natural-systems",
        entities=[entity],
    )

    assert compute_content_hash(payload)


def test_inventory_payload_top_level_sorts_have_deterministic_tie_breakers() -> None:
    left = InventoryPayload(
        generated_at="2026-05-12T10:00:00Z",
        project_id="natural-systems",
        aliases=[
            InventoryAlias(alias="f001", canonical_id="finding:beta"),
            InventoryAlias(alias="f001", canonical_id="finding:alpha"),
        ],
    )
    right = left.model_copy(update={"aliases": list(reversed(left.aliases))})

    assert compute_content_hash(left) == compute_content_hash(right)


def test_finalize_inventory_payload_populates_stable_hashes() -> None:
    payload = InventoryPayload(
        generated_at="2026-05-12T10:00:00Z",
        project_id="natural-systems",
        warnings=[
            InventoryWarning(
                code="deprecated-prose-reference",
                severity="warning",
                message="Markdown prose references deprecated ID h4.",
                path="doc/summary.md",
            )
        ],
    )

    finalized = finalize_inventory_payload(payload)
    finalized_again = finalize_inventory_payload(finalized)

    assert finalized.content_hash == compute_content_hash(payload)
    assert finalized.audit_hash == compute_audit_hash(payload)
    assert finalized.content_hash is not None
    assert finalized.audit_hash is not None
    assert finalized_again.content_hash == finalized.content_hash
    assert finalized_again.audit_hash == finalized.audit_hash
