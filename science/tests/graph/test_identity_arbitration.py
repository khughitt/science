"""Contribution vocabulary and arbitration: guards, ordering, the role matrix, invariance."""
from __future__ import annotations

import json
from itertools import permutations
from pathlib import Path

import pytest
from science_model.entities import Entity
from science_model.entity_schema import MergePolicy
from science_model.source_ref import SourceRef

from science_tool.commons.overlay import OverlayRecord
from science_tool.graph.errors import ContributionConflictError
from science_tool.graph.identity_arbitration import (
    ArbitrationCode,
    ArbitrationContext,
    ArbitrationResult,
    AttachmentContribution,
    ContributionKey,
    EntityContribution,
    arbitrate_contributions,
)
from science_tool.graph.identity_table import IdentityDeclaration, ParticipationMode
from science_tool.unset import is_unset


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


def _ref_less(mode: ParticipationMode, *, adapter: str = "markdown") -> IdentityDeclaration:
    return IdentityDeclaration(
        canonical_id="paper:x",
        participation_mode=mode,
        owner_scope="proj",
        adapter=adapter,
        source_ref=None,
    )


def test_an_entity_contribution_requires_provenance() -> None:
    """A contribution with no `source_ref` is a claim nobody can be held to.

    `_refs_of` dropped such rows, so a duplicate-owner error between two of them carried
    `contributors=()` -- an error naming nobody -- and the strict boundary indexed that empty
    tuple and raised IndexError in place of the identity collision. Refusing at construction is
    the one spot the guard cannot be forgotten; every later consumer then gets to assume it.
    """
    with pytest.raises(ValueError, match="source_ref"):
        EntityContribution(_ref_less(ParticipationMode.OWNER), _paper())


def test_an_attachment_contribution_requires_provenance() -> None:
    with pytest.raises(ValueError, match="source_ref"):
        AttachmentContribution(_ref_less(ParticipationMode.BORROWER, adapter="overlay"), _overlay())


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


def test_contribution_conflict_error_separates_line_zero_from_no_line() -> None:
    """Line 0 is a valid index, not absence.

    Keyed as `ref.line or -1`, a 0-line and a None-line ref with the same path collide, and
    Python's stable sort then renders the conflict in whatever order the adapters happened to
    run. Same defect as reading absence off truthiness -- absence is a shape.
    """
    refs = [
        SourceRef(adapter_name="markdown", path="a.md", line=None),
        SourceRef(adapter_name="markdown", path="a.md", line=0),
    ]

    forward = str(ContributionConflictError(canonical_id="p:x", field="t", refs=refs))
    reverse = str(
        ContributionConflictError(canonical_id="p:x", field="t", refs=list(reversed(refs)))
    )

    assert forward == reverse
    # None sorts before 0: absent location is less specific than a located line 0.
    assert forward.index("a.md\n") < forward.index("a.md:0")


# --------------------------------------------------------------------------------------
# Arbitration: the role matrix, the issue ledger, and permutation invariance.
# --------------------------------------------------------------------------------------


def _entity(canonical_id: str, **fields: object) -> Entity:
    kind = canonical_id.split(":", 1)[0]
    base: dict[str, object] = {
        "id": canonical_id,
        "canonical_id": canonical_id,
        "kind": kind,
        "title": "",
        "project": "proj",
        "ontology_terms": [],
        "related": [],
        "source_refs": [],
        "content_preview": "",
        "file_path": f"entities/{kind}s/x.md",
    }
    base.update(fields)
    return Entity(**base)  # type: ignore[arg-type]


def _owner(
    canonical_id: str,
    *,
    adapter: str = "markdown",
    owner_scope: str = "proj",
    path: str | None = None,
    deprecated: bool = False,
    **fields: object,
) -> EntityContribution:
    kind = canonical_id.split(":", 1)[0]
    declaration = IdentityDeclaration(
        canonical_id=canonical_id,
        participation_mode=ParticipationMode.OWNER,
        owner_scope=owner_scope,
        adapter=adapter,
        source_ref=SourceRef(
            adapter_name=adapter, path=path or f"entities/{kind}s/x.md", line=None
        ),
        deprecated=deprecated,
    )
    return EntityContribution(declaration, _entity(canonical_id, **fields))


def _borrower(
    canonical_id: str,
    *,
    owner_scope: str = "proj",
    path: str | None = None,
    **fields: object,
) -> AttachmentContribution:
    kind = canonical_id.split(":", 1)[0]
    overlay_path = path or f"overlays/{kind}s/x.md"
    declaration = IdentityDeclaration(
        canonical_id=canonical_id,
        participation_mode=ParticipationMode.BORROWER,
        owner_scope=owner_scope,
        adapter="overlay",
        source_ref=SourceRef(adapter_name="overlay", path=overlay_path, line=None),
    )
    record = OverlayRecord(
        canonical_id=canonical_id,
        type=kind,
        slug="x",
        project="proj",
        project_root=Path("/proj"),
        overlay_path=Path("/proj") / overlay_path,
        frontmatter=dict(fields),
        body="",
        pin_version=None,
        pin_effective_version=None,
    )
    return AttachmentContribution(declaration, record)


def _external(
    canonical_id: str,
    *,
    adapter: str = "bib",
    path: str = "papers/references.bib",
    line: int | None = 1,
    **fields: object,
) -> EntityContribution:
    declaration = IdentityDeclaration(
        canonical_id=canonical_id,
        participation_mode=ParticipationMode.EXTERNAL_REFERENCE,
        owner_scope=adapter,
        adapter=adapter,
        source_ref=SourceRef(adapter_name=adapter, path=path, line=line),
    )
    return EntityContribution(declaration, _entity(canonical_id, **fields))


def _arbitrate(
    *contributions: EntityContribution | AttachmentContribution,
    policy: dict[str, MergePolicy] | None = None,
    project_scope: str = "proj",
) -> ArbitrationResult:
    field_policies = {
        (c.declaration.owner_scope, c.declaration.canonical_id): dict(policy or {})
        for c in contributions
    }
    return arbitrate_contributions(
        contributions,
        context=ArbitrationContext(
            project_scope=project_scope, field_policies=field_policies
        ),
    )


def test_owner_unset_allows_one_external_value() -> None:
    result = _arbitrate(
        _owner("paper:x", doi=None),
        _external("paper:x", doi="10.1/x"),
        policy={"doi": MergePolicy.REPLACE},
    )
    assert result.entities[0].doi == "10.1/x"


def test_owner_false_is_never_replaced() -> None:
    result = _arbitrate(
        _owner("paper:x", pre_registered=False),
        _external("paper:x", pre_registered=True),
        policy={"pre_registered": MergePolicy.REPLACE},
    )
    assert result.entities[0].pre_registered is False


def test_owner_zero_is_never_replaced() -> None:
    result = _arbitrate(
        _owner("talk:x", duration_minutes=0),
        _external("talk:x", duration_minutes=30),
        policy={"duration_minutes": MergePolicy.REPLACE},
    )
    assert result.entities[0].duration_minutes == 0


def test_borrower_replace_against_defended_owner_is_attributed() -> None:
    result = _arbitrate(
        _owner("paper:x", title="Canonical"),
        _borrower("paper:x", title="Project rewrite"),
        policy={"title": MergePolicy.REPLACE},
    )
    [error] = result.errors
    assert error.code == "contribution-conflict"
    assert error.field == "title"
    assert [ref.path for ref in error.contributors] == ["overlays/papers/x.md"]
    # The owner keeps its value: a rejected contribution changes nothing.
    assert result.entities[0].title == "Canonical"


def test_external_replace_against_defended_owner_is_silently_not_offered() -> None:
    """An external reference SUPPORTS a node; it does not contest one.

    A bib entry carries a title for every paper it names. Treating that as an attempted
    overwrite would make every citation of an owned paper an error, so a defended REPLACE
    field is simply not offered -- unlike a borrower's, which is explicit project input.
    """
    result = _arbitrate(
        _owner("paper:x", title="Canonical"),
        _external("paper:x", title="Bib title"),
        policy={"title": MergePolicy.REPLACE},
    )
    assert result.entities[0].title == "Canonical"
    assert result.errors == ()


def test_project_only_borrower_wins() -> None:
    result = _arbitrate(
        _owner("dataset:x", status="canonical"),
        _borrower("dataset:x", status="active"),
        policy={"status": MergePolicy.PROJECT_ONLY},
    )
    assert result.entities[0].status == "active"


def test_append_is_owner_first_then_contribution_key_order() -> None:
    result = _arbitrate(
        _owner("paper:x", related=["topic:owner"]),
        _borrower("paper:x", related=["topic:b"]),
        _external("paper:x", related=["topic:e"]),
        policy={"related": MergePolicy.APPEND},
    )
    assert result.entities[0].related == ["topic:owner", "topic:b", "topic:e"]


def test_external_only_materializes_without_becoming_owner() -> None:
    result = _arbitrate(_external("paper:x", title="Citation"))
    assert [entity.canonical_id for entity in result.entities] == ["paper:x"]
    assert (
        result.identity_declarations[0].participation_mode
        is ParticipationMode.EXTERNAL_REFERENCE
    )
    assert result.errors == ()


def test_real_owner_and_deprecated_datapackage_record_attachment_output() -> None:
    result = _arbitrate(
        _owner("dataset:x", adapter="markdown", deprecated=False),
        _owner(
            "dataset:x",
            adapter="datapackage",
            deprecated=True,
            path="data/x/datapackage.yaml",
        ),
    )
    assert result.entity_source_adapters == {"dataset:x": "markdown"}
    assert result.dataset_datapackages == {"dataset:x": "data/x/datapackage.yaml"}
    # Both rows survive: the deprecated owner is rollout debt a later phase must find.
    assert len(result.identity_declarations) == 2
    assert result.errors == ()


def test_genuine_duplicate_owner_is_error_and_has_no_representative() -> None:
    result = _arbitrate(
        _owner("paper:x", path="entities/papers/a.md"),
        _owner("paper:x", path="entities/papers/b.md"),
    )
    assert result.entities == ()
    assert result.errors[0].code == "duplicate-owner"


def test_borrower_without_an_owner_in_its_scope_is_attributed() -> None:
    result = _arbitrate(_borrower("paper:x", status="active"))
    assert result.entities == ()
    assert result.errors[0].code == "missing-owner"


def test_attachment_without_a_policy_fails_early() -> None:
    """A borrower composed under no policy would silently contribute nothing."""
    owner = _owner("paper:x", title="Canonical")
    borrower = _borrower("paper:x", status="active")
    context = ArbitrationContext(project_scope="proj", field_policies={})
    with pytest.raises(KeyError, match="paper:x"):
        arbitrate_contributions((owner, borrower), context=context)


def test_aggregate_file_may_own_many_entities_at_one_location() -> None:
    """Same path, same adapter, no line -- distinct entities.

    ContributionKey is unique per entity, not globally: an aggregate file legitimately owns
    many entities from one location, and rejecting that as ambiguous would break real projects.
    """
    result = _arbitrate(
        _owner("paper:a", adapter="aggregate", path="entities/papers/all.md"),
        _owner("paper:b", adapter="aggregate", path="entities/papers/all.md"),
    )
    assert [entity.canonical_id for entity in result.entities] == ["paper:a", "paper:b"]
    assert result.errors == ()


def test_two_differing_contributions_at_one_key_are_rejected() -> None:
    """Same entity, same role, same file, same line, different content.

    Nothing downstream can tell these apart, so a stable sort would resolve them by whichever
    adapter ran first. That is the silent instrument this arc exists to remove.
    """
    first = _owner("paper:x", title="One")
    second = _owner("paper:x", title="Two")
    with pytest.raises(ValueError, match="indistinguishable"):
        _arbitrate(first, second)


def test_identical_contributions_at_one_key_are_deduplicated() -> None:
    result = _arbitrate(_owner("paper:x", title="One"), _owner("paper:x", title="One"))
    assert len(result.identity_declarations) == 1
    assert result.entities[0].title == "One"
    assert result.errors == ()


def _snapshot(result: ArbitrationResult) -> str:
    return json.dumps(
        {
            "entities": [entity.model_dump(mode="json") for entity in result.entities],
            "declarations": [
                [
                    row.canonical_id,
                    row.participation_mode.value,
                    row.owner_scope,
                    row.adapter,
                    str(row.source_ref),
                    row.deprecated,
                ]
                for row in result.identity_declarations
            ],
            "entity_source_adapters": result.entity_source_adapters,
            "dataset_datapackages": result.dataset_datapackages,
            "overlay_paths": result.overlay_paths,
            "field_sources": {
                cid: {field: [list(key.ordering) for key in keys] for field, keys in fields.items()}
                for cid, fields in result.field_sources.items()
            },
            "errors": [
                [error.code, error.canonical_id, error.owner_scope, error.field, [str(ref) for ref in error.contributors]]
                for error in result.errors
            ],
        },
        sort_keys=True,
        default=str,
    )


def test_every_permutation_has_identical_entities_provenance_and_errors() -> None:
    contributions = (
        _owner("paper:x", doi=None, related=["topic:owner"]),
        _borrower("paper:x", status="active", related=["topic:project"]),
        _external("paper:x", doi="10.1/x", related=["topic:bib"]),
    )
    snapshots = {
        _snapshot(
            _arbitrate(
                *ordering,
                policy={
                    "doi": MergePolicy.REPLACE,
                    "status": MergePolicy.PROJECT_ONLY,
                    "related": MergePolicy.APPEND,
                },
            )
        )
        for ordering in permutations(contributions)
    }
    assert len(snapshots) == 1


def test_every_permutation_agrees_on_errors_too() -> None:
    """Invariance must hold on the failing path, not only the succeeding one."""
    contributions = (
        _owner("paper:x", title="Canonical", path="entities/papers/a.md"),
        _owner("paper:x", title="Other", path="entities/papers/b.md"),
        _borrower("paper:x", title="Rewrite"),
    )
    snapshots = {
        _snapshot(_arbitrate(*ordering, policy={"title": MergePolicy.REPLACE}))
        for ordering in permutations(contributions)
    }
    assert len(snapshots) == 1


def test_permutation_invariance_holds_between_peers_of_one_role() -> None:
    """Two contributions of the SAME role must resolve identically in every arrival order.

    The three-contribution fixture above (one owner, one borrower, one external) cannot see this:
    with one contribution per role, no two ever compete, and the result sorts normalize the
    output -- so it passes even against an arbitration that never sorts at all. Ordering only
    becomes observable when peers contend.

    APPEND is what proves the sort is live, because sequence is the value. The two DOIs prove the
    opposite property: peers disagreeing on a scalar is a CONFLICT, not a race the lower key wins.
    """
    contributions = (
        _owner("paper:x", doi=None, related=["topic:owner"]),
        _external("paper:x", line=2, doi="10.1/second", related=["topic:second"]),
        _external("paper:x", line=1, doi="10.1/first", related=["topic:first"]),
    )
    results = [
        _arbitrate(
            *ordering,
            policy={"doi": MergePolicy.REPLACE, "related": MergePolicy.APPEND},
        )
        for ordering in permutations(contributions)
    ]

    assert len({_snapshot(result) for result in results}) == 1
    # APPEND follows key order in every encounter order: this is what the sort buys.
    assert results[0].entities[0].related == ["topic:owner", "topic:first", "topic:second"]
    # The vacancy STAYS vacant: no source position confers authority over a scalar.
    assert results[0].entities[0].doi is None
    [error] = results[0].errors
    assert error.code == "contribution-conflict"
    assert error.field == "doi"
    assert [ref.path for ref in error.contributors] == ["papers/references.bib"] * 2


def test_peers_agreeing_on_a_scalar_collapse_to_one_value() -> None:
    """Agreement is not conflict. Two sources saying the same thing fill the vacancy."""
    result = _arbitrate(
        _owner("paper:x", doi=None),
        _external("paper:x", line=1, doi="10.1/x"),
        _external("paper:x", line=2, doi="10.1/x"),
        policy={"doi": MergePolicy.REPLACE},
    )
    assert result.entities[0].doi == "10.1/x"
    assert result.errors == ()


def test_two_borrowers_disagreeing_on_a_vacancy_leave_it_vacant() -> None:
    """The fold-per-borrower defect: the first fills, the second is faulted for disagreeing with
    a value the first had no authority to install. Proposals are gathered before any decision."""
    result = _arbitrate(
        _owner("paper:x", doi=None),
        _borrower("paper:x", path="overlays/papers/a.md", doi="10.1/a"),
        _borrower("paper:x", path="overlays/papers/b.md", doi="10.1/b"),
        policy={"doi": MergePolicy.REPLACE},
    )
    assert result.entities[0].doi is None
    [error] = result.errors
    assert error.code == "contribution-conflict"
    assert [ref.path for ref in error.contributors] == [
        "overlays/papers/a.md",
        "overlays/papers/b.md",
    ]


def test_external_only_node_leaves_a_contested_scalar_vacant() -> None:
    result = _arbitrate(
        _external("paper:x", line=1, doi="10.1/first", title="First"),
        _external("paper:x", line=2, doi="10.1/second", title="First"),
    )
    assert result.entities[0].doi is None
    assert result.entities[0].title == "First"
    [error] = result.errors
    assert error.code == "contribution-conflict"
    assert error.field == "doi"


def test_field_provenance_credits_only_what_the_owner_authored() -> None:
    """`model_dump()` yields ~67 fields for an entity that authored a dozen.

    Crediting the owner for all of them reports it as the source of values it never supplied --
    and in the vacancy case names it a source of the very DOI it did not have.
    """
    result = _arbitrate(
        _owner("paper:x", doi=None, title="Canonical"),
        _external("paper:x", doi="10.1/x"),
        policy={"doi": MergePolicy.REPLACE},
    )
    sources = result.field_sources["paper:x"]

    owner_key = ContributionKey(
        role=ParticipationMode.OWNER,
        authority="proj:markdown",
        path="entities/papers/x.md",
        position=-1,
    )
    assert sources["title"] == (owner_key,)
    # The owner supplied no doi, so it is not a source of one.
    assert owner_key not in sources["doi"]
    assert [key.role for key in sources["doi"]] == [ParticipationMode.EXTERNAL_REFERENCE]
    # Defaulted, unauthored fields are credited to nobody.
    assert "commits_to" not in sources
    assert "lens_views" not in sources
    # TRUTHY defaults, which `is_unset` alone cannot exclude. Without these the test certifies
    # only the `is_unset` half of `_authored_fields`: dropping `model_fields_set` entirely
    # leaves every empty-default assertion above green, while the owner silently starts being
    # credited as the source of a `scope` and a `profile` it never wrote.
    assert "scope" not in sources
    assert "profile" not in sources


def test_cross_scope_peers_are_ambiguous_not_silently_chosen() -> None:
    """Neither scope is ours nor commons. "The only remaining owner" is a cardinality
    precondition, not licence to let the lexically lower adapter supply the entity."""
    result = _arbitrate(
        _owner("paper:x", owner_scope="alpha", title="Alpha"),
        _owner("paper:x", owner_scope="beta", title="Beta"),
        project_scope="unrelated",
    )
    assert result.entities == ()
    [error] = result.errors
    assert error.code == "ambiguous-representative"
    # Both rows survive for the resolver.
    assert len(result.identity_declarations) == 2


def test_cross_scope_peer_resolves_when_this_project_owns_it() -> None:
    result = _arbitrate(
        _owner("paper:x", owner_scope="proj", title="Ours"),
        _owner("paper:x", owner_scope="beta", title="Beta"),
        project_scope="proj",
    )
    assert result.entities[0].title == "Ours"
    assert result.errors == ()


def test_cross_scope_peer_resolves_to_commons_when_we_do_not_own_it() -> None:
    result = _arbitrate(
        _owner("paper:x", owner_scope="commons", title="Canonical"),
        _owner("paper:x", owner_scope="beta", title="Beta"),
        project_scope="unrelated",
    )
    assert result.entities[0].title == "Canonical"
    assert result.errors == ()


def test_composed_value_is_coerced_to_the_model_type() -> None:
    """A contributed value must enter the graph as the entity model's type, not as YAML wrote it.

    Overlay frontmatter is validated against the OVERLAY schema, which types a date as a
    string. The entity model types it as a `date`. Composition is the boundary between those
    two vocabularies, so it is the place the value must be coerced -- installing the raw string
    hands every downstream consumer a `str` where it declared a `date`, and the failure lands
    far away (freshness comparing `str > date`) with nothing pointing back at the overlay.
    """
    from datetime import date

    result = arbitrate_contributions(
        [
            _owner("paper:x"),
            _borrower("paper:x", updated="2026-07-10"),
        ],
        context=ArbitrationContext(
            project_scope="proj",
            field_policies={("proj", "paper:x"): {"updated": MergePolicy.PROJECT_ONLY}},
        ),
    )

    assert result.errors == ()
    assert result.entities[0].updated == date(2026, 7, 10)


def test_composed_value_that_the_model_rejects_is_not_installed_silently() -> None:
    """Coercion is validation, not casting: a value the model cannot accept must fail loudly."""
    with pytest.raises(ValueError):
        arbitrate_contributions(
            [
                _owner("paper:x"),
                _borrower("paper:x", updated="not-a-date"),
            ],
            context=ArbitrationContext(
                project_scope="proj",
                field_policies={("proj", "paper:x"): {"updated": MergePolicy.PROJECT_ONLY}},
            ),
        )


def test_composition_preserves_private_alias_provenance_and_the_authored_field_set() -> None:
    """Coercion must not rebuild the entity -- only the composed values may change.

    `_authored_aliases` is carried from load and, as the model itself states, must never be
    inferred: it is what distinguishes an authored alias from a derived convenience when the two
    coincide. `model_fields_set` is the same kind of fact -- what the SOURCE authored, which
    `_authored_fields` reads to decide who gets credited for a value.

    Reconstructing the entity from `model_dump()` silently drops the first and inflates the
    second to every field the dump names. Both losses are invisible here and land far away:
    `build_alias_map` would reclassify an authored alias as derived, so a colliding mappings
    entry silently wins where it should raise.
    """
    from datetime import date

    owner = _owner("paper:x", aliases=["Smith24"])
    owner.candidate._authored_aliases = frozenset({"Smith24"})
    authored_before = set(owner.candidate.model_fields_set)

    result = arbitrate_contributions(
        [owner, _borrower("paper:x", updated="2026-07-10")],
        context=ArbitrationContext(
            project_scope="proj",
            field_policies={("proj", "paper:x"): {"updated": MergePolicy.PROJECT_ONLY}},
        ),
    )

    entity = result.entities[0]
    assert entity.updated == date(2026, 7, 10)
    assert entity._authored_aliases == frozenset({"Smith24"})
    # Exactly the composed field joins the authored set -- nothing else the dump would name.
    assert entity.model_fields_set == authored_before | {"updated"}


_XREF_A = {"source": "doi", "id": "10.1/x", "curie": "doi:10.1/x", "provenance": "bib"}
_XREF_B = {"source": "pmid", "id": "999", "curie": "doi:10.1/x", "provenance": "bib"}
_XREF_C = {"source": "pmid", "id": "999", "curie": "pmid:999", "provenance": "bib"}


def _round_tripped(entity: Entity) -> Entity:
    """The entity the model would build from this entity's own serialized form.

    Private state is carried from load and deliberately never serialized, so a dump cannot
    express it; carrying it across keeps the comparison about the values the model DECLARES
    rather than about what a dump happens to preserve.
    """
    rebuilt = type(entity).model_validate(entity.model_dump())
    rebuilt._authored_aliases = entity._authored_aliases
    return rebuilt


def test_every_returned_representative_equals_its_own_round_trip() -> None:
    """The general invariant: a representative is what its model says it is.

    Equality, not "validation does not raise". A de-typed nested value -- a dict sitting where
    the model declares an `ExternalId` -- validates happily, because the dict is exactly what the
    model would accept as INPUT for that field. It is only unequal to what the model BUILDS from
    it. Round-trip-does-not-raise is blind to the whole class; round-trip-equals is not.
    """
    result = arbitrate_contributions(
        [
            _owner("paper:owned"),
            _borrower("paper:owned", updated="2026-07-10"),
            _external("paper:contested", title="One"),
            _external("paper:contested", title="Two", path="knowledge/refs.yaml", line=2),
            _external("paper:agreed", title="Same"),
            _external("paper:agreed", title="Same", path="knowledge/refs.yaml", line=3),
            _external("paper:nested-invariant", xrefs=[_XREF_A]),
            _external(
                "paper:nested-invariant", xrefs=[_XREF_C], path="knowledge/refs.yaml", line=4
            ),
        ],
        context=ArbitrationContext(
            project_scope="proj",
            field_policies={("proj", "paper:owned"): {"updated": MergePolicy.PROJECT_ONLY}},
        ),
    )

    assert result.entities
    for entity in result.entities:
        assert entity == _round_tripped(entity)


def test_external_only_title_conflict_yields_no_representative() -> None:
    """A contested required field means the graph cannot honestly say what the node is.

    The vacancy rule is right -- letting the first bib line's title stand would make file order
    the authority. But `title` is required, so the vacancy is unrepresentable, and the choice is
    between an invalid entity and no entity. No entity is correct: the conflict is in the ledger
    naming both sources, which is the actionable fact. Materializing `PaperEntity(title=None)`
    would instead hand every consumer a node that violates its own contract.
    """
    result = arbitrate_contributions(
        [
            _external("paper:contested", title="One"),
            _external("paper:contested", title="Two", path="knowledge/refs.yaml", line=2),
        ],
        context=ArbitrationContext(project_scope="proj", field_policies={}),
    )

    assert [e.canonical_id for e in result.entities] == []
    conflicts = [e for e in result.errors if e.code is ArbitrationCode.CONTRIBUTION_CONFLICT]
    assert len(conflicts) == 1
    assert conflicts[0].field == "title"
    # The ledger still names BOTH sources: the node is absent, but why is not.
    assert len(conflicts[0].contributors) == 2


def test_external_only_composition_preserves_nested_model_values() -> None:
    """A proposal must carry the candidate's VALUES, not its serialized shape.

    Reading proposals from `model_dump()` turns a nested `ExternalId` into a plain dict, and the
    external-only path installs with `model_copy`, which does not coerce it back. The entity then
    ships with `xrefs` elements that are dicts where the model declares `ExternalId` -- and it
    ships quietly, because a dict dumps identically to the model it impersonates.
    """
    from science_model.identity import ExternalId

    result = arbitrate_contributions(
        [
            _external("paper:nested", xrefs=[_XREF_A]),
            _external("paper:nested", xrefs=[_XREF_C], path="knowledge/refs.yaml", line=2),
        ],
        context=ArbitrationContext(project_scope="proj", field_policies={}),
    )

    # The union differs from either candidate's own list, so the composed value is genuinely
    # installed rather than left as the first candidate's untouched object.
    entity = result.entities[0]
    assert [type(xref) for xref in entity.xrefs] == [ExternalId, ExternalId]
    assert {xref.curie for xref in entity.xrefs} == {"doi:10.1/x", "pmid:999"}


def test_external_only_model_level_rejection_fails_loudly() -> None:
    """A whole-entity invariant names no field, so no vacancy can explain it.

    Two externals each carrying a valid xref can compose into a list the model rejects as a
    whole (duplicate CURIEs). That failure arrives with an empty `loc`, and a guard that reads
    only located errors sees an empty set -- i.e. "nothing wrong" -- and returns the invalid
    entity with nothing in the ledger. Unexplained means loud.
    """
    with pytest.raises(ValueError, match="does not explain"):
        arbitrate_contributions(
            [
                _external("paper:dupe", xrefs=[_XREF_A]),
                _external("paper:dupe", xrefs=[_XREF_B], path="knowledge/refs.yaml", line=2),
            ],
            context=ArbitrationContext(project_scope="proj", field_policies={}),
        )


def test_a_duplicated_owner_is_not_also_reported_as_a_missing_owner() -> None:
    """A borrower whose scope has TWO owners is not a borrower with none.

    The ledger is what an audit reader acts on, so a contradiction in it is a defect even
    though it over-reports rather than under-reports: "this scope owns nothing" is simply false
    when the scope owns the id twice, and it points the reader at authoring an owner that
    already exists -- twice. The duplicate-owner row is the actionable fact.
    """
    result = arbitrate_contributions(
        [
            _owner("paper:x", path="a.md"),
            _owner("paper:x", path="b.md"),
            _borrower("paper:x", relevance="r"),
        ],
        context=ArbitrationContext(project_scope="proj", field_policies={}),
    )

    assert [e.code for e in result.errors] == [ArbitrationCode.DUPLICATE_OWNER]


def test_a_borrower_whose_scope_has_no_owner_at_all_is_still_reported() -> None:
    """The MISSING_OWNER row must survive for the case it actually describes."""
    result = arbitrate_contributions(
        [
            _owner("paper:x", path="a.md"),
            _owner("paper:x", path="b.md"),
            _borrower("paper:x", owner_scope="other", relevance="r"),
        ],
        context=ArbitrationContext(project_scope="proj", field_policies={}),
    )

    assert sorted({e.code for e in result.errors}) == [
        ArbitrationCode.DUPLICATE_OWNER,
        ArbitrationCode.MISSING_OWNER,
    ]
    missing = next(e for e in result.errors if e.code is ArbitrationCode.MISSING_OWNER)
    assert missing.owner_scope == "other"
