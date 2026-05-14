from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_model.contracts.inventory_v2 import (
    InventoryOverlay,
    InventorySourceLocation,
)


def _source() -> InventorySourceLocation:
    return InventorySourceLocation(
        adapter="commons-overlay", path="doc/papers/Adams2025.md"
    )


def test_inventory_overlay_accepts_minimal_fields() -> None:
    overlay = InventoryOverlay(
        overlay_of="paper:Adams2025",
        project_id="proj-alpha",
        source=_source(),
    )
    assert overlay.overlay_of == "paper:Adams2025"
    assert overlay.pin_version is None
    assert overlay.project_only_fields == {}
    assert overlay.append_fields == {}
    assert overlay.body_sections == []


def test_inventory_overlay_carries_split_fields_and_body() -> None:
    overlay = InventoryOverlay(
        overlay_of="paper:Adams2025",
        project_id="proj-alpha",
        source=_source(),
        pin_version="1.2.0",
        project_only_fields={"relevance": "H2", "hypothesis_links": ["H2", "H4"]},
        append_fields={"tags": ["overlay-added"]},
        body_sections=["## Project-Specific Notes\nText."],
    )
    assert overlay.pin_version == "1.2.0"
    assert overlay.project_only_fields["hypothesis_links"] == ["H2", "H4"]
    assert overlay.append_fields["tags"] == ["overlay-added"]
    assert overlay.body_sections == ["## Project-Specific Notes\nText."]


def test_inventory_overlay_rejects_overlay_of_without_separator() -> None:
    with pytest.raises(ValidationError, match="canonical"):
        InventoryOverlay(
            overlay_of="Adams2025", project_id="proj-alpha", source=_source()
        )


def test_inventory_overlay_rejects_overlay_of_empty_kind() -> None:
    with pytest.raises(ValidationError, match="canonical"):
        InventoryOverlay(
            overlay_of=":Adams2025", project_id="proj-alpha", source=_source()
        )


def test_inventory_overlay_rejects_overlay_of_empty_local_id() -> None:
    with pytest.raises(ValidationError, match="canonical"):
        InventoryOverlay(
            overlay_of="paper:", project_id="proj-alpha", source=_source()
        )


def test_inventory_overlay_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        InventoryOverlay(
            overlay_of="paper:Adams2025",
            project_id="proj-alpha",
            source=_source(),
            mystery="value",
        )


def test_inventory_overlay_rejects_non_json_field_values() -> None:
    with pytest.raises(ValidationError, match="JSON"):
        InventoryOverlay(
            overlay_of="paper:Adams2025",
            project_id="proj-alpha",
            source=_source(),
            project_only_fields={"bad": object()},
        )
    with pytest.raises(ValidationError, match="JSON"):
        InventoryOverlay(
            overlay_of="paper:Adams2025",
            project_id="proj-alpha",
            source=_source(),
            append_fields={"bad": object()},
        )


def test_inventory_payload_v2_defaults_schema_version_and_overlays() -> None:
    from science_model.contracts.inventory_v2 import InventoryPayload

    payload = InventoryPayload(
        generated_at="2026-05-14T10:00:00Z", project_id="commons"
    )
    assert payload.schema_version == "2"
    assert payload.overlays == []
    assert payload.entities == []


def test_inventory_payload_v2_rejects_schema_version_1() -> None:
    from science_model.contracts.inventory_v2 import InventoryPayload

    with pytest.raises(ValidationError):
        InventoryPayload(
            generated_at="2026-05-14T10:00:00Z",
            project_id="commons",
            schema_version="1",
        )


def test_inventory_payload_v2_rejects_unknown_fields() -> None:
    from science_model.contracts.inventory_v2 import InventoryPayload

    with pytest.raises(ValidationError):
        InventoryPayload(
            generated_at="2026-05-14T10:00:00Z",
            project_id="commons",
            mystery="value",
        )


def test_inventory_payload_v2_carries_overlays() -> None:
    from science_model.contracts.inventory_v2 import InventoryPayload

    payload = InventoryPayload(
        generated_at="2026-05-14T10:00:00Z",
        project_id="proj-alpha",
        overlays=[
            InventoryOverlay(
                overlay_of="paper:Adams2025",
                project_id="proj-alpha",
                source=_source(),
            )
        ],
    )
    assert payload.overlays[0].overlay_of == "paper:Adams2025"


def test_v2_hashes_ignore_generated_at() -> None:
    from science_model.contracts.inventory_v2 import (
        InventoryPayload,
        compute_audit_hash,
        compute_content_hash,
    )

    first = InventoryPayload(
        generated_at="2026-05-14T10:00:00Z",
        project_id="commons",
        overlays=[
            InventoryOverlay(
                overlay_of="paper:Adams2025",
                project_id="proj-alpha",
                source=_source(),
            )
        ],
    )
    second = first.model_copy(update={"generated_at": "2026-05-14T11:00:00Z"})
    assert compute_content_hash(first) == compute_content_hash(second)
    assert compute_audit_hash(first) == compute_audit_hash(second)


def test_v2_content_hash_is_stable_under_overlay_reordering() -> None:
    from science_model.contracts.inventory_v2 import (
        InventoryPayload,
        compute_content_hash,
    )

    left = InventoryPayload(
        generated_at="2026-05-14T10:00:00Z",
        project_id="proj-alpha",
        overlays=[
            InventoryOverlay(
                overlay_of="paper:Beta2025",
                project_id="proj-alpha",
                source=_source(),
            ),
            InventoryOverlay(
                overlay_of="paper:Alpha2025",
                project_id="proj-alpha",
                source=_source(),
            ),
        ],
    )
    right = left.model_copy(update={"overlays": list(reversed(left.overlays))})
    assert compute_content_hash(left) == compute_content_hash(right)


def test_v2_content_hash_changes_when_overlay_field_changes() -> None:
    from science_model.contracts.inventory_v2 import (
        InventoryPayload,
        compute_content_hash,
    )

    base = InventoryPayload(
        generated_at="2026-05-14T10:00:00Z",
        project_id="proj-alpha",
        overlays=[
            InventoryOverlay(
                overlay_of="paper:Adams2025",
                project_id="proj-alpha",
                source=_source(),
                project_only_fields={"relevance": "H2"},
            )
        ],
    )
    changed = base.model_copy(
        update={
            "overlays": [
                base.overlays[0].model_copy(
                    update={"project_only_fields": {"relevance": "H9"}}
                )
            ]
        }
    )
    assert compute_content_hash(base) != compute_content_hash(changed)


def test_v2_audit_hash_ignores_overlays() -> None:
    from science_model.contracts.inventory_v2 import (
        InventoryPayload,
        compute_audit_hash,
    )

    base = InventoryPayload(
        generated_at="2026-05-14T10:00:00Z",
        project_id="proj-alpha",
        overlays=[
            InventoryOverlay(
                overlay_of="paper:Adams2025",
                project_id="proj-alpha",
                source=_source(),
                project_only_fields={"relevance": "H2"},
            )
        ],
    )
    no_overlays = base.model_copy(update={"overlays": []})
    assert compute_audit_hash(base) == compute_audit_hash(no_overlays)


def test_v2_finalize_populates_stable_hashes() -> None:
    from science_model.contracts.inventory_v2 import (
        InventoryPayload,
        compute_audit_hash,
        compute_content_hash,
        finalize_inventory_payload,
    )

    payload = InventoryPayload(
        generated_at="2026-05-14T10:00:00Z", project_id="commons"
    )
    finalized = finalize_inventory_payload(payload)
    assert finalized.content_hash == compute_content_hash(payload)
    assert finalized.audit_hash == compute_audit_hash(payload)
    assert finalize_inventory_payload(finalized).content_hash == finalized.content_hash
