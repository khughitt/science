from __future__ import annotations

from science_model.contracts.inventory_v1 import (
    InventoryAlias,
    InventoryEntity,
    InventoryPayload,
    InventorySourceLocation,
    InventoryWarning,
    compute_audit_hash,
    compute_content_hash,
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
