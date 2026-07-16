"""Contribution vocabulary: constructor guards, ordering, and the unset predicate."""
from __future__ import annotations

from pathlib import Path

import pytest
from science_model.entities import Entity
from science_model.source_ref import SourceRef

from science_tool.commons.overlay import OverlayRecord
from science_tool.graph.errors import ContributionConflictError
from science_tool.graph.identity_arbitration import (
    AttachmentContribution,
    ContributionKey,
    EntityContribution,
    is_unset,
)
from science_tool.graph.identity_table import IdentityDeclaration, ParticipationMode


def _declaration(
    mode: ParticipationMode,
    *,
    canonical_id: str = "paper:x",
    owner_scope: str = "proj",
    adapter: str = "markdown",
    path: str = "entities/papers/x.md",
    line: int | None = None,
) -> IdentityDeclaration:
    return IdentityDeclaration(
        canonical_id=canonical_id,
        participation_mode=mode,
        owner_scope=owner_scope,
        adapter=adapter,
        source_ref=SourceRef(adapter_name=adapter, path=path, line=line),
    )


def _paper(canonical_id: str = "paper:x") -> Entity:
    return Entity(
        id=canonical_id,
        canonical_id=canonical_id,
        kind="paper",
        title="X",
        project="proj",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="entities/papers/x.md",
    )


def _overlay(canonical_id: str = "paper:x") -> OverlayRecord:
    return OverlayRecord(
        canonical_id=canonical_id,
        type="paper",
        slug="x",
        project="proj",
        project_root=Path("/proj"),
        overlay_path=Path("/proj/overlays/papers/x.md"),
        frontmatter={},
        body="",
        pin_version=None,
        pin_effective_version=None,
    )


def test_entity_contribution_rejects_borrower_payload() -> None:
    with pytest.raises(ValueError, match="borrower contributes an attachment"):
        EntityContribution(_declaration(ParticipationMode.BORROWER), _paper())


def test_attachment_contribution_rejects_non_borrower_payload() -> None:
    with pytest.raises(ValueError, match="only a borrower"):
        AttachmentContribution(_declaration(ParticipationMode.OWNER), _overlay())


def test_entity_contribution_rejects_identity_disagreement() -> None:
    """The declaration and its payload must name the same entity.

    A contribution filed under one id carrying another's record would arbitrate the
    wrong subject silently -- the payload is what composes, the declaration is what
    routes, and nothing downstream re-checks that they agree.
    """
    with pytest.raises(ValueError, match="disagree on canonical_id"):
        EntityContribution(_declaration(ParticipationMode.OWNER), _paper("paper:other"))


def test_attachment_contribution_rejects_identity_disagreement() -> None:
    with pytest.raises(ValueError, match="disagree on canonical_id"):
        AttachmentContribution(
            _declaration(ParticipationMode.BORROWER), _overlay("paper:other")
        )


@pytest.mark.parametrize("value", [None, "", "   ", [], {}, set(), ()])
def test_is_unset_accepts_only_absence_shapes(value: object) -> None:
    assert is_unset(value)


@pytest.mark.parametrize("value", [False, 0, 0.0, "x", [0], {"x": 0}])
def test_is_unset_preserves_defended_falsey_values(value: object) -> None:
    """`False`, `0`, and `0.0` are VALUES an owner authored, not absence.

    This is the defect the superseded helper carried: `if getattr(owner, field, None):`
    treats an authored `False` as missing and lets a borrower overwrite it. Absence is a
    shape, not a truthiness.
    """
    assert not is_unset(value)


def test_contribution_key_uses_role_authority_path_and_position() -> None:
    rows = [
        _declaration(
            ParticipationMode.EXTERNAL_REFERENCE,
            adapter="bib",
            path="papers/references.bib",
            line=2,
        ),
        _declaration(
            ParticipationMode.BORROWER, adapter="overlay", path="overlays/papers/x.md"
        ),
        _declaration(
            ParticipationMode.OWNER, adapter="markdown", path="entities/papers/x.md"
        ),
    ]

    ordered = sorted(rows, key=lambda row: ContributionKey.from_declaration(row).ordering)

    assert [row.participation_mode for row in ordered] == [
        ParticipationMode.OWNER,
        ParticipationMode.BORROWER,
        ParticipationMode.EXTERNAL_REFERENCE,
    ]


def test_contribution_key_is_total_over_every_participation_mode() -> None:
    """Every mode must rank. A mode added later without a rank would raise KeyError
    at ordering time -- deep inside a sort, on real data, not here."""
    for mode in ParticipationMode:
        key = ContributionKey.from_declaration(_declaration(mode))
        assert isinstance(key.ordering[0], int)


def test_contribution_key_orders_same_role_by_authority_then_path_then_position() -> None:
    """Ordering must be total within a role, or arbitration is input-order dependent."""
    rows = [
        _declaration(ParticipationMode.OWNER, adapter="markdown", path="b.md", line=1),
        _declaration(ParticipationMode.OWNER, adapter="markdown", path="a.md", line=2),
        _declaration(ParticipationMode.OWNER, adapter="markdown", path="a.md", line=1),
        _declaration(ParticipationMode.OWNER, adapter="aggregate", path="z.md", line=9),
    ]

    ordered = [
        (key.authority, key.path, key.position)
        for key in sorted(
            (ContributionKey.from_declaration(row) for row in rows),
            key=lambda key: key.ordering,
        )
    ]

    assert ordered == [
        ("proj:aggregate", "z.md", 9),
        ("proj:markdown", "a.md", 1),
        ("proj:markdown", "a.md", 2),
        ("proj:markdown", "b.md", 1),
    ]


def test_contribution_key_tolerates_a_declaration_without_a_source_ref() -> None:
    key = ContributionKey.from_declaration(
        IdentityDeclaration(
            canonical_id="paper:x",
            participation_mode=ParticipationMode.OWNER,
            owner_scope="proj",
            adapter="markdown",
            source_ref=None,
        )
    )

    assert key.path == ""
    assert key.position == -1


def test_contribution_conflict_error_reports_every_source() -> None:
    """The message must carry the provenance a human needs to resolve the conflict.

    A conflict naming only the field and id sends the reader hunting for which files
    disagree -- the arbitration already knows, so it must say.
    """
    error = ContributionConflictError(
        canonical_id="paper:x",
        field="title",
        refs=[
            SourceRef(adapter_name="markdown", path="b.md", line=3),
            SourceRef(adapter_name="markdown", path="a.md", line=1),
        ],
    )

    message = str(error)
    assert "paper:x" in message
    assert "title" in message
    assert "a.md" in message
    assert "b.md" in message
    assert error.canonical_id == "paper:x"
    assert error.field == "title"


def test_contribution_conflict_error_sorts_its_sources() -> None:
    """Sorted, so the same conflict reads identically on every run."""
    refs = [
        SourceRef(adapter_name="markdown", path="b.md", line=3),
        SourceRef(adapter_name="markdown", path="a.md", line=1),
    ]

    forward = str(ContributionConflictError(canonical_id="p:x", field="t", refs=refs))
    reverse = str(
        ContributionConflictError(canonical_id="p:x", field="t", refs=list(reversed(refs)))
    )

    assert forward == reverse
    assert forward.index("a.md") < forward.index("b.md")
