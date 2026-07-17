# Identity Arbitration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace encounter-order identity selection with collect → close → arbitrate → compose, so external references cannot shadow commons owners or overlays, contribution precedence is deterministic and schema-driven, and dataset overlays use the versioned dataset/2.0 status policy.

**Architecture:** Source adapters and commons closure produce an unordered union of validated whole-entity and overlay-attachment contributions. A new pure arbitration module owns identity grouping, deterministic ordering, role × merge-policy composition, diagnostic errors, and the final projections consumed by ProjectSources. The dataset-status instance is fixed independently through a side-by-side mixin-dataset-2.0 schema and an explicit science-commons profile migration; read_merge_policy keeps its existing shared-interface contract.

**Tech Stack:** Python 3.12, Pydantic v2, JSON Schema draft 2020-12, pytest, Hypothesis-free exhaustive permutations, uv, Git worktrees.

**Design reference:** docs/plans/2026-07-16-identity-arbitration-design.md

## Global Constraints

- Work in ~/d/science/.worktrees/commons-overlay-bib-shadow on branch fix/commons-overlay-bib-shadow.
- Preserve the two uncommitted fb-2026-07-16-005 regression tests in science/tests/test_graph_commons_sources.py. The uncommitted production changes in graph/sources.py and graph/commons_sources.py are superseded; rework them in place and do not commit the side channel, five-field allowlist, or truthiness helper.
- Collection never selects, evicts, absorbs, or defers a contribution. Arbitration is the only selection/composition authority.
- Identity grouping uses (owner_scope, canonical_id). Contribution ordering uses ContributionKey and never adjudicates a scalar conflict.
- External references remain EXTERNAL_REFERENCE rows. They materialize a minimal node only when no owner exists.
- A genuine duplicate owner is always an arbitration error. Diagnostic loads may return the error and omit the contested representative; they may not silently choose a winner.
- read_merge_policy and read_overlay_merge_policy retain their current public return contracts. A fixes only the dataset-status crash instance through dataset/2.0.
- mixin-dataset-1.0 remains byte-for-byte unchanged. Pinned dataset/1.0 profiles retain REPLACE semantics for status.
- The science-commons migration is a separate commit in an isolated sibling-repo worktree because the main science-commons checkout is dirty.
- Merge order is toolkit-first and non-negotiable: `mixin-dataset-2.0.json` ships only on this toolkit branch, so merging the commons migration (`fix/dataset-mixin-2`, migration `5c36831`, whose `MERGE-NOTES.md` records the same rule) before the toolkit lands makes all 41 migrated datasets reference a schema resource that consumers on a pre-2.0 toolkit pin cannot resolve, breaking their loads (exit 1, `schema resource 'mixin-dataset-2.0.json' not found`). Commons-first is prohibited; the ordered gate is Task 9.
- Run toolkit commands from the nested science/ or science/model/ package, never the repository root.
- Use ~/d/ paths in documentation and commands. Do not add compatibility layers, a Unified prefix, or AI-attribution trailers.

---

## File Map

- Create science/src/science_tool/graph/identity_arbitration.py: contribution types, ContributionKey, is_unset, arbitration errors/result, and the pure arbitration function.
- Create science/tests/graph/test_identity_arbitration.py: constructor guards, merge matrix, deterministic conflict attribution, external-only nodes, and permutation invariance.
- Modify science/src/science_tool/graph/sources.py: collect validated contributions; invoke close and arbitrate; project ArbitrationResult into ProjectSources.
- Modify science/src/science_tool/graph/commons_sources.py: close references/overlays to a fixed point and return contributions plus owner policy declarations; never merge or select.
- Modify science/src/science_tool/graph/storage_adapters/base.py and datapackage.py: remove should_defer and deferred_dataset_datapackage.
- Modify science/src/science_tool/commons/overlay.py: expose a pure frontmatter composition helper used by arbitration while retaining merge_entity for CLI callers.
- Modify science/src/science_tool/graph/errors.py: add contributor-attributed arbitration failure.
- Modify focused loader/commons/equivalence tests named below.
- Create science/model/src/science_model/schemas/mixin-dataset-2.0.json and science/model/tests/test_mixin_dataset_2_0.py.
- Modify science/model/src/science_model/entity_schema/profile.py, science/model/tests/test_project_profiles.py, science/src/science_tool/commons/promote.py, and focused promotion tests to make dataset/2.0 the default without altering 1.0.
- Modify datasets/*/entity.md in the isolated science-commons migration worktree, changing only the dataset mixin component from 1.0 to 2.0.

---

### Task 1: Ship the versioned dataset/2.0 schema contract

**Files:**

- Create: science/model/src/science_model/schemas/mixin-dataset-2.0.json
- Create: science/model/tests/test_mixin_dataset_2_0.py
- Modify: science/model/src/science_model/entity_schema/profile.py
- Modify: science/model/tests/test_project_profiles.py
- Modify: science/src/science_tool/commons/promote.py
- Modify: science/tests/test_commons_promote_active_profile.py
- Modify: science/tests/test_commons_promote_dataset_plan.py

**Interfaces:**

- Produces default_profile_for_kind("dataset") == science-entity-base/1.0+dataset/2.0.
- Produces mixin schema id https://schemas.science/mixin-dataset-2.0.json with status declared as PROJECT_ONLY.
- Preserves read_merge_policy(parse_profile("science-entity-base/1.0+dataset/1.0"))["status"] == MergePolicy.REPLACE.

- [ ] **Step 1: Write the failing versioning tests**

Create science/model/tests/test_mixin_dataset_2_0.py:

~~~python
from __future__ import annotations

from science_model.entity_schema import MergePolicy, default_profile_for_kind, parse_profile, read_merge_policy


_V1 = parse_profile("science-entity-base/1.0+dataset/1.0")
_V2 = parse_profile("science-entity-base/1.0+dataset/2.0")


def test_dataset_2_declares_status_project_only() -> None:
    assert read_merge_policy(_V2)["status"] is MergePolicy.PROJECT_ONLY


def test_dataset_1_keeps_its_pinned_status_semantics() -> None:
    assert read_merge_policy(_V1)["status"] is MergePolicy.REPLACE


def test_dataset_default_moves_atomically_to_2_0() -> None:
    assert default_profile_for_kind("dataset").render() == "science-entity-base/1.0+dataset/2.0"
~~~

In science/model/tests/test_project_profiles.py, change only the dataset default assertion to dataset/2.0. Keep explicit dataset/1.0 controls such as _BASE2_DATASET pinned to 1.0.

- [ ] **Step 2: Run the tests and confirm the missing schema/default failures**

Run:

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow/science/model
uv run --frozen pytest tests/test_mixin_dataset_2_0.py tests/test_project_profiles.py -q
~~~

Expected: FAIL because mixin-dataset-2.0.json does not exist and the default still renders dataset/1.0.

- [ ] **Step 3: Add dataset/2.0 without mutating dataset/1.0**

Copy the complete content of mixin-dataset-1.0.json into mixin-dataset-2.0.json, change only its $id/title version markers, and add this property beside the other dataset properties:

~~~json
"status": {"type": "string", "science:merge": "project_only"}
~~~

In science/model/src/science_model/entity_schema/profile.py:

~~~python
_DEFAULT_MIXIN_VERSION: dict[str, str] = {
    "dataset": "2.0",
    "paper": "2.0",
    "topic": "2.0",
    "theme": "2.0",
    "hypothesis": "1.0",
}
~~~

In science/src/science_tool/commons/promote.py, update only PROMOTE_KIND_DATASET:

~~~python
mixin_schema_id="https://schemas.science/mixin-dataset-2.0.json",
default_profile=default_profile_for_kind("dataset"),
~~~

Update focused promotion expectations that exercise the default profile to dataset/2.0. Do not mechanically replace explicit 1.0 fixtures; those are compatibility controls unless the test calls default_profile_for_kind or PROMOTE_KIND_DATASET.

- [ ] **Step 4: Run the focused model and promotion tests**

Run:

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow/science/model
uv run --frozen pytest tests/test_mixin_dataset_2_0.py tests/test_project_profiles.py tests/test_entity_schema_loader.py tests/test_entity_schema_mixin_dataset.py -q
~~~

Expected: PASS, including the explicit 1.0 semantic control.

Run:

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow/science
uv run --frozen pytest tests/test_commons_promote_active_profile.py tests/test_commons_promote_dataset_plan.py tests/test_commons_promote_kind_config.py -q
~~~

Expected: PASS; generated/default dataset profiles use 2.0.

- [ ] **Step 5: Commit the schema version**

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow
git add science/model/src/science_model/schemas/mixin-dataset-2.0.json science/model/src/science_model/entity_schema/profile.py science/model/tests/test_mixin_dataset_2_0.py science/model/tests/test_project_profiles.py science/src/science_tool/commons/promote.py science/tests/test_commons_promote_active_profile.py science/tests/test_commons_promote_dataset_plan.py science/tests/test_commons_promote_kind_config.py
git commit -m "feat(schema): add dataset mixin 2.0 status policy"
~~~

---

### Task 2: Define the contribution and ordering types

**Files:**

- Create: science/src/science_tool/graph/identity_arbitration.py
- Create: science/tests/graph/test_identity_arbitration.py
- Modify: science/src/science_tool/graph/errors.py

**Interfaces:**

- Produces EntityContribution(declaration: IdentityDeclaration, candidate: Entity).
- Produces AttachmentContribution(declaration: IdentityDeclaration, record: OverlayRecord).
- Produces SourceContribution = EntityContribution | AttachmentContribution.
- Produces ContributionKey.from_declaration(declaration) and ContributionKey.ordering.
- Produces is_unset(value: object) -> bool.
- Produces ContributionConflictError carrying canonical_id, field, and sorted SourceRefs.

- [ ] **Step 1: Write constructor, ordering, and unset tests**

Create science/tests/graph/test_identity_arbitration.py with small helpers that construct IdentityDeclaration, Entity, and OverlayRecord, then add:

~~~python
def test_entity_contribution_rejects_borrower_payload() -> None:
    with pytest.raises(ValueError, match="borrower contributes an attachment"):
        EntityContribution(_declaration(ParticipationMode.BORROWER), _paper("paper:x"))


def test_attachment_contribution_rejects_non_borrower_payload() -> None:
    with pytest.raises(ValueError, match="only a borrower"):
        AttachmentContribution(_declaration(ParticipationMode.OWNER), _overlay("paper:x"))


@pytest.mark.parametrize("value", [None, "", "   ", [], {}, set(), ()])
def test_is_unset_accepts_only_absence_shapes(value: object) -> None:
    assert is_unset(value)


@pytest.mark.parametrize("value", [False, 0, 0.0, "x", [0], {"x": 0}])
def test_is_unset_preserves_defended_falsey_values(value: object) -> None:
    assert not is_unset(value)


def test_contribution_key_uses_role_authority_path_and_position() -> None:
    rows = [
        _declaration(ParticipationMode.EXTERNAL_REFERENCE, adapter="bib", path="papers/references.bib", line=2),
        _declaration(ParticipationMode.BORROWER, adapter="overlay", path="overlays/papers/x.md"),
        _declaration(ParticipationMode.OWNER, adapter="markdown", path="entities/papers/x.md"),
    ]
    assert [row.participation_mode for row in sorted(rows, key=lambda row: ContributionKey.from_declaration(row).ordering)] == [
        ParticipationMode.OWNER,
        ParticipationMode.BORROWER,
        ParticipationMode.EXTERNAL_REFERENCE,
    ]
~~~

- [ ] **Step 2: Run the focused tests and confirm import failures**

Run:

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow/science
uv run --frozen pytest tests/graph/test_identity_arbitration.py -q
~~~

Expected: FAIL because identity_arbitration.py and its public types do not exist.

- [ ] **Step 3: Implement the types and fail-early guards**

In science/src/science_tool/graph/identity_arbitration.py, define:

~~~python
from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from science_model.entities import Entity
from science_tool.commons.overlay import OverlayRecord
from science_tool.graph.identity_table import IdentityDeclaration, ParticipationMode

_ROLE_RANK = {
    ParticipationMode.OWNER: 0,
    ParticipationMode.BORROWER: 1,
    ParticipationMode.EXTERNAL_REFERENCE: 2,
}


@dataclass(frozen=True)
class EntityContribution:
    declaration: IdentityDeclaration
    candidate: Entity

    def __post_init__(self) -> None:
        if self.declaration.participation_mode is ParticipationMode.BORROWER:
            raise ValueError("a borrower contributes an attachment, not an entity")
        if self.declaration.canonical_id != self.candidate.canonical_id:
            raise ValueError("identity declaration and entity candidate disagree on canonical_id")


@dataclass(frozen=True)
class AttachmentContribution:
    declaration: IdentityDeclaration
    record: OverlayRecord

    def __post_init__(self) -> None:
        if self.declaration.participation_mode is not ParticipationMode.BORROWER:
            raise ValueError("only a borrower contributes an attachment")
        if self.declaration.canonical_id != self.record.canonical_id:
            raise ValueError("identity declaration and overlay attachment disagree on canonical_id")


SourceContribution: TypeAlias = EntityContribution | AttachmentContribution


@dataclass(frozen=True)
class ContributionKey:
    role: ParticipationMode
    authority: str
    path: str
    position: int

    @classmethod
    def from_declaration(cls, declaration: IdentityDeclaration) -> "ContributionKey":
        ref = declaration.source_ref
        return cls(
            role=declaration.participation_mode,
            authority=f"{declaration.owner_scope}:{declaration.adapter}",
            path="" if ref is None else ref.path,
            position=-1 if ref is None or ref.line is None else ref.line,
        )

    @property
    def ordering(self) -> tuple[int, str, str, int]:
        return (_ROLE_RANK[self.role], self.authority, self.path, self.position)


def is_unset(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, frozenset, dict)):
        return len(value) == 0
    return False
~~~

In science/src/science_tool/graph/errors.py, add ContributionConflictError. Its message must include the canonical id, field, and each sorted SourceRef; do not accept a preformatted string that could omit provenance.

- [ ] **Step 4: Run the type tests**

Run:

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow/science
uv run --frozen pytest tests/graph/test_identity_arbitration.py -q
uv run --frozen ruff check src/science_tool/graph/identity_arbitration.py src/science_tool/graph/errors.py tests/graph/test_identity_arbitration.py
~~~

Expected: PASS.

- [ ] **Step 5: Commit the contribution vocabulary**

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow
git add science/src/science_tool/graph/identity_arbitration.py science/src/science_tool/graph/errors.py science/tests/graph/test_identity_arbitration.py
git commit -m "feat(graph): define identity contribution contract"
~~~

---

### Task 3: Implement pure set arbitration and the total role matrix

**Files:**

- Modify: science/src/science_tool/graph/identity_arbitration.py
- Modify: science/src/science_tool/commons/overlay.py
- Modify: science/tests/graph/test_identity_arbitration.py
- Modify: science/tests/test_commons_overlay.py

**Interfaces:**

- Produces ArbitrationContext(project_scope, field_policies).
- Produces ArbitrationResult with entities, identity_declarations, entity_source_adapters, dataset_datapackages, overlay_paths, field_sources, and errors.
- Produces arbitrate_contributions(contributions, *, context) -> ArbitrationResult.
- Produces compose_frontmatter(canonical, overlay, merge_policy) in commons/overlay.py; merge_entity delegates to it so CLI behavior and graph arbitration share one borrower-policy implementation.

- [ ] **Step 1: Add failing matrix tests**

Extend science/tests/graph/test_identity_arbitration.py with controls for:

~~~python
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
        _owner_talk("talk:x", duration_minutes=0),
        _external_talk("talk:x", duration_minutes=30),
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
    assert "overlays/papers/x.md" in error.contributors[0]


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
    assert result.identity_declarations[0].participation_mode is ParticipationMode.EXTERNAL_REFERENCE


def test_real_owner_and_deprecated_datapackage_record_attachment_output() -> None:
    result = _arbitrate(
        _owner("dataset:x", adapter="markdown", deprecated=False),
        _owner("dataset:x", adapter="datapackage", deprecated=True, path="data/x/datapackage.yaml"),
    )
    assert result.entity_source_adapters == {"dataset:x": "markdown"}
    assert result.dataset_datapackages == {"dataset:x": "data/x/datapackage.yaml"}


def test_genuine_duplicate_owner_is_error_and_has_no_representative() -> None:
    result = _arbitrate(
        _owner("paper:x", path="entities/papers/a.md"),
        _owner("paper:x", path="entities/papers/b.md"),
    )
    assert result.entities == ()
    assert result.errors[0].code == "duplicate-owner"
~~~

External whole-entity candidates offer only permitted metadata: structural identity/provenance fields are never submitted as updates; a defended REPLACE field is not offered; an unset REPLACE field, APPEND field, or otherwise explicitly admitted field is offered. This is how a full bib candidate can support a commons node without “attempting” to replace its title or id. Borrower frontmatter is explicit project input, so a defended REPLACE field is an attributed error.

- [ ] **Step 2: Add the failing permutation test**

Use three contributions so all six encounter orders are exercised:

~~~python
from itertools import permutations


def test_every_permutation_has_identical_entities_provenance_and_errors() -> None:
    contributions = (
        _owner("paper:x", doi=None, related=["topic:owner"]),
        _borrower("paper:x", status="active", related=["topic:project"]),
        _external("paper:x", doi="10.1/x", related=["topic:bib"]),
    )
    snapshots = {
        _snapshot(_arbitrate(*ordering, policy={
            "doi": MergePolicy.REPLACE,
            "status": MergePolicy.PROJECT_ONLY,
            "related": MergePolicy.APPEND,
        }))
        for ordering in permutations(contributions)
    }
    assert len(snapshots) == 1
~~~

The snapshot must include serialized entities, sorted identity rows, entity_source_adapters, overlay_paths, field_sources, and serialized errors. Do not snapshot only entity values.

- [ ] **Step 3: Run the arbitration tests and confirm behavioral failures**

Run:

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow/science
uv run --frozen pytest tests/graph/test_identity_arbitration.py -q
~~~

Expected: FAIL because ArbitrationContext, ArbitrationResult, and arbitrate_contributions are not implemented.

- [ ] **Step 4: Implement the pure result and deterministic issue ledger**

Add these public shapes to identity_arbitration.py:

~~~python
@dataclass(frozen=True)
class ArbitrationContext:
    project_scope: str
    field_policies: Mapping[tuple[str, str], Mapping[str, MergePolicy]]


@dataclass(frozen=True, order=True)
class ArbitrationError:
    code: str
    canonical_id: str
    owner_scope: str
    field: str
    contributors: tuple[str, ...]


@dataclass(frozen=True)
class ArbitrationResult:
    entities: tuple[Entity, ...]
    identity_declarations: tuple[IdentityDeclaration, ...]
    entity_source_adapters: dict[str, str]
    dataset_datapackages: dict[str, str]
    overlay_paths: dict[str, str]
    field_sources: dict[str, dict[str, tuple[ContributionKey, ...]]]
    errors: tuple[ArbitrationError, ...]


def arbitrate_contributions(
    contributions: Iterable[SourceContribution],
    *,
    context: ArbitrationContext,
) -> ArbitrationResult:
    ordered = tuple(sorted(contributions, key=_contribution_ordering))
    return _arbitrate_ordered(ordered, context=context)
~~~

Implement the body with these exact phases:

1. Sort contributions once by ContributionKey.ordering.
2. Preserve every declaration, sorted by the same key.
3. Group owner rows by (owner_scope, canonical_id). A group with two non-deprecated owners emits duplicate-owner and suppresses that canonical id from entities; it never chooses one.
4. A non-deprecated owner beats a deprecated datapackage owner in the same scope; retain both declarations and emit dataset_datapackages from the datapackage SourceRef.
5. Across valid owner scopes, preserve all owner rows. For the one in-memory representative, use the project_scope owner when present, otherwise commons, otherwise the only remaining owner. This is the existing B3a materialization rule; the rows retain cross-scope ambiguity for the resolver.
6. Attach a borrower only to the owner in its declared owner_scope. Missing owner emits missing-owner.
7. Compose fields from the owner policy at field_policies[(owner_scope, canonical_id)]. Fail early if an attachment exists but no policy exists.
8. If no owner exists and at least one external EntityContribution exists, materialize the first ContributionKey candidate as the minimal node and merge only non-conflicting supporting metadata.
9. Sort entities by canonical_id and errors by their dataclass order before returning.

Implement _contribution_ordering as ContributionKey.from_declaration(contribution.declaration).ordering. Implement _arbitrate_ordered as the nine-phase algorithm above; it is private so arbitrate_contributions remains the only public arbitration entry point.

Use model_copy(update=field_updates) for the representative so Pydantic type/private authored-alias state is preserved. Never mutate a candidate or attachment.

- [ ] **Step 5: Extract pure borrower frontmatter composition**

In commons/overlay.py, extract the field loop into:

~~~python
def compose_frontmatter(
    canonical: Mapping[str, Any],
    overlay: Mapping[str, Any],
    merge_policy: Mapping[str, MergePolicy],
    *,
    canonical_id: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Compose validated canonical and overlay frontmatter without I/O."""
~~~

Apply the role matrix:

- APPEND: owner values first, then deterministic borrower values, deduplicated.
- PROJECT_ONLY: borrower wins.
- REPLACE: borrower may fill only when owner is_unset; otherwise raise ContributionConflictError naming the overlay SourceRef at the arbitration layer.
- FORBIDDEN: any defended borrower value is an error.
- Skip id, overlay_of, pin_version, and pin_effective_version.

Keep merge_entity as the CLI-facing wrapper: it reads bodies, calls compose_frontmatter, and returns MergedEntity. Do not change read_merge_policy or the overlay-policy default lookup in this task beyond replacing the formerly “unreachable” branch with the explicit matrix.

- [ ] **Step 6: Run matrix, overlay, and permutation tests**

Run:

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow/science
uv run --frozen pytest tests/graph/test_identity_arbitration.py tests/test_commons_overlay.py -q
uv run --frozen ruff check src/science_tool/graph/identity_arbitration.py src/science_tool/commons/overlay.py tests/graph/test_identity_arbitration.py tests/test_commons_overlay.py
~~~

Expected: PASS.

- [ ] **Step 7: Commit pure arbitration**

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow
git add science/src/science_tool/graph/identity_arbitration.py science/src/science_tool/graph/errors.py science/src/science_tool/commons/overlay.py science/tests/graph/test_identity_arbitration.py science/tests/test_commons_overlay.py
git commit -m "feat(graph): arbitrate identity contributions deterministically"
~~~

---

### Task 4: Make adapter collection exhaustive and selection-free

**Files:**

- Modify: science/src/science_tool/graph/sources.py
- Modify: science/src/science_tool/graph/storage_adapters/base.py
- Modify: science/src/science_tool/graph/storage_adapters/datapackage.py
- Modify: science/tests/graph/test_source_load_equivalence.py
- Modify: science/tests/graph/test_bib_external_reference_load.py
- Modify: science/tests/graph/test_curie_external_reference_load.py
- Modify: science/tests/test_load_project_sources_unified.py

**Interfaces:**

- Consumes EntityContribution, ArbitrationContext, and arbitrate_contributions from Task 3.
- Produces every successfully validated adapter/legacy entity as an EntityContribution before any identity decision.
- Removes StorageAdapter.should_defer and StorageAdapter.deferred_dataset_datapackage.
- Preserves strict_identity=False as a diagnostic projection: arbitration errors are observable and contested ids are omitted, never arbitrarily selected.

- [ ] **Step 1: Change the frozen source-load expectations first**

In science/tests/graph/test_source_load_equivalence.py:

- Add the deprecated datapackage owner row for dataset:ds2 to EXPECTED_STRICT while keeping markdown as the materialized entity_source_adapters value and the datapackage path in dataset_datapackages.
- Add the bib EXTERNAL_REFERENCE row for paper:Smith2024 to EXPECTED_NONSTRICT while keeping markdown as the materialized owner.
- Rename the two “unchanged” tests to state the post-arbitration contract.

In science/tests/test_load_project_sources_unified.py, change test_datapackage_defers_to_markdown_owner to assert two declarations: the real markdown owner and deprecated datapackage owner. Keep build_identity_table(sources).collisions() as one non-genuine transitional collision, not an empty list.

In bib/curie external-reference tests, assert that owner-first and external-first fixture variants retain both declarations and one representative.

- [ ] **Step 2: Run focused tests and confirm the old deferral behavior fails them**

Run:

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow/science
uv run --frozen pytest tests/graph/test_source_load_equivalence.py tests/graph/test_bib_external_reference_load.py tests/graph/test_curie_external_reference_load.py tests/test_load_project_sources_unified.py -q
~~~

Expected: FAIL because should_defer still deletes datapackage/bib/curie declarations.

- [ ] **Step 3: Remove adapter-time deferral**

Delete StorageAdapter.should_defer and StorageAdapter.deferred_dataset_datapackage from graph/storage_adapters/base.py. Delete both overrides from datapackage.py.

In sources.py, replace identity_table, external_reference_ids, immediate entities, and immediate entity_source_adapters mutation with:

~~~python
contributions: list[SourceContribution] = []
field_policies: dict[tuple[str, str], dict[str, MergePolicy]] = {}
~~~

For every validated adapter entity and every legacy/structured entity, always create an IdentityDeclaration and append EntityContribution. Do not consult earlier contributions. Register a project-owner policy only for a kind supported by default_profile_for_kind:

~~~python
declaration = IdentityDeclaration(
    canonical_id=entity.canonical_id,
    participation_mode=adapter.participation_mode,
    owner_scope=owner_scope,
    adapter=adapter.name,
    source_ref=ref,
    deprecated=deprecated,
)
contributions.append(EntityContribution(declaration=declaration, candidate=entity))
if declaration.participation_mode is ParticipationMode.OWNER:
    try:
        profile = default_profile_for_kind(entity.kind)
    except ProfileParseError:
        pass
    else:
        field_policies[(owner_scope, entity.canonical_id)] = read_merge_policy(profile)
~~~

The explicit ProfileParseError branch is not a fallback policy. It means no overlay/external composition contract exists for that project-only kind; arbitration must fail if an attachment later requires one.

- [ ] **Step 4: Arbitrate local contributions before ProjectSources projection**

Until Task 5 adds commons closure, call arbitrate_contributions on the local contribution set. Build nested entity relations from result.entities, not encounter-order candidates. Project result fields into ProjectSources.

If result.errors is nonempty and strict_identity is true, raise the existing EntityIdentityCollisionError for duplicate-owner and ContributionConflictError for field errors. If strict_identity is false, return all declarations, omit contested representatives, and leave the errors visible to the existing identity audit through the declarations.

Do not delete the strict_identity parameter; it is a consumer-facing diagnostic mode. The semantic change is that arbitration always detects the error, while strictness controls raising versus diagnostic projection.

- [ ] **Step 5: Run loader, identity-audit, and phase-split tests**

Run:

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow/science
uv run --frozen pytest tests/graph/test_source_load_equivalence.py tests/graph/test_bib_external_reference_load.py tests/graph/test_curie_external_reference_load.py tests/test_load_project_sources_unified.py tests/test_identity_audit_entrypoints.py tests/graph/test_phase_split_contracts.py tests/test_graph_build_strict.py -q
~~~

Expected: PASS. Genuine duplicate strict builds fail; diagnostic loads still produce the declarations needed by the identity audit.

- [ ] **Step 6: Prove no deferral API remains**

Run:

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow
rg -n "should_defer|deferred_dataset_datapackage" science/src science/tests
# The side channel is a DERIVATION pattern, not a name: nothing in the loader or the closure may
# consult a set of external-reference ids to decide identity. The one surviving set is
# `reference_only_ids` in graph/materialize.py, derived FROM arbitration's declarations
# (external-reference and not owner) purely to type owner-free nodes -- an output projection,
# never an input. It is named for what it contains, not for the declaration it filters.
rg -n "reference_only_ids|external_reference_ids" science/src/science_tool/graph/sources.py science/src/science_tool/graph/commons_sources.py
~~~

Expected: no production matches. Test prose may mention former behavior only when explicitly describing the regression.

- [ ] **Step 7: Commit exhaustive collection**

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow
git add science/src/science_tool/graph/sources.py science/src/science_tool/graph/storage_adapters/base.py science/src/science_tool/graph/storage_adapters/datapackage.py science/tests/graph/test_source_load_equivalence.py science/tests/graph/test_bib_external_reference_load.py science/tests/graph/test_curie_external_reference_load.py science/tests/test_load_project_sources_unified.py
git commit -m "refactor(graph): collect every identity contribution before selection"
~~~

---

### Task 5: Close commons references and overlays as contributions

**Files:**

- Modify: science/src/science_tool/graph/commons_sources.py
- Modify: science/src/science_tool/graph/sources.py
- Modify: science/tests/test_graph_commons_sources.py
- Modify: science/tests/test_substrate_two_scope_e2e.py

**Interfaces:**

- Replaces _load_commons_referenced_entities with collect_commons_contributions returning CommonsClosure(contributions, field_policies, overlay_paths).
- Commons owners are EntityContribution values; overlays are AttachmentContribution values.
- validate_overlay_pin runs during Close for every resolved overlay, even when a project owner or external reference uses the same canonical id.
- Close discovers transitive references from canonical candidates and overlay frontmatter until pending is empty.

- [ ] **Step 1: Preserve and strengthen the two existing fb-005 regressions**

Keep the uncommitted test_bib_entry_does_not_shadow_paper_overlay and test_bib_entry_does_not_suppress_overlay_pin_check in science/tests/test_graph_commons_sources.py.

Add assertions to the first test:

~~~python
rows = [row for row in sources.identity_declarations if row.canonical_id == "paper:Adams2025"]
assert {(row.participation_mode, row.adapter) for row in rows} == {
    (ParticipationMode.OWNER, "commons-merged"),
    (ParticipationMode.BORROWER, "overlay"),
    (ParticipationMode.EXTERNAL_REFERENCE, "bib"),
}
assert len([entity for entity in sources.entities if entity.canonical_id == "paper:Adams2025"]) == 1
~~~

Retain the existing public adapter name "commons-merged" in the declaration and assertion. classify_owner_scope already maps it to owner_scope "commons"; do not add a second adapter alias.

Add a fixed-point test where an overlay field references a second commons id and assert both owner contributions are collected. This prevents Close from traversing only the canonical candidate while ignoring the borrower.

- [ ] **Step 2: Run the regressions against the old loader**

Run:

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow/science
uv run --frozen pytest tests/test_graph_commons_sources.py -q -k "bib_entry or fixed_point"
~~~

Expected: FAIL under the pre-arbitration loader; the old branch either suppresses commons or merges before contributions exist.

- [ ] **Step 3: Define the closure result and canonical materializer**

In graph/commons_sources.py:

~~~python
@dataclass(frozen=True)
class CommonsClosure:
    contributions: tuple[SourceContribution, ...]
    field_policies: dict[tuple[str, str], dict[str, MergePolicy]]
    overlay_paths: dict[str, str]


def collect_commons_contributions(
    *,
    project_root: Path,
    project_slug: str,
    seed_entities: Iterable[Entity],
    project_relations: list[SourceRelation],
    project_bindings: list[BindingSource],
    registry: EntityRegistry,
    active_kinds: frozenset[str],
    ontology_catalogs: list[OntologyCatalog],
) -> CommonsClosure:
    collector = _CommonsClosureCollector(
        project_root=project_root,
        project_slug=project_slug,
        registry=registry,
        active_kinds=active_kinds,
        ontology_catalogs=ontology_catalogs,
    )
    return collector.collect(
        seed_entities=seed_entities,
        project_relations=project_relations,
        project_bindings=project_bindings,
    )
~~~

Implement the private _CommonsClosureCollector with constructor arguments and collect inputs exactly matching the wrapper above; collect performs the nine fixed-point steps in Step 4 and returns CommonsClosure. Replace the MergedEntity-based _materialize_commons_entity with _materialize_commons_candidate(record: CommonsEntityRecord, *, registry, project_slug, active_kinds, ontology_catalogs) -> Entity. It validates the canonical frontmatter into Entity without applying the overlay. Preserve the current description→summary, journal→venue, shared scope/profile, source path, enrichment, and schema.model_validate behavior.

- [ ] **Step 4: Implement fixed-point Close**

The loop must:

1. Scan all overlays once and fail on OverlayValidationError.
2. Seed pending from references parsed out of every seed Entity, structured relation, binding, and overlay frontmatter.
3. Pop ids in sorted order.
4. Query CommonsQuery. An overlay whose canonical cannot resolve is an OverlayValidationError; a plain unknown reference remains unresolved downstream.
5. Read the canonical profile policy and call validate_overlay_pin before creating contributions.
6. Add one commons owner EntityContribution and, when present, one overlay AttachmentContribution.
7. Add policy under ("commons", canonical_id).
8. Add references parsed from both the canonical candidate and the overlay frontmatter to pending.
9. Terminate only when pending is empty; use seen ids only for I/O deduplication, never to suppress a declaration discovered from another authority.

Do not pass identity_table, locally_owned, external_reference_ids, or selected entities into this function. Those are arbitration concepts.

- [ ] **Step 5: Wire Close before final arbitration**

In sources.py:

- Collect local candidates and structured relations/bindings.
- If include_commons, call collect_commons_contributions with all local EntityContribution candidates as seeds.
- Extend contributions and field_policies with the closure result.
- Call arbitrate_contributions exactly once over the complete set.
- Rebuild entity-nested relations from the final result.entities so a non-representative candidate cannot leak edges.
- Project result.overlay_paths to ProjectSources.commons_overlay_paths.
- Delete _absorb_external_reference_metadata, _EXTERNAL_REFERENCE_SUPPORTING_FIELDS, identity-table eviction, and the side-channel logic from the dirty production diff.

- [ ] **Step 6: Run commons, two-scope, and overlay tests**

Run:

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow/science
uv run --frozen pytest tests/test_graph_commons_sources.py tests/test_substrate_two_scope_e2e.py tests/test_commons_overlay.py tests/graph/test_bib_external_reference_load.py tests/graph/test_curie_external_reference_load.py -q
~~~

Expected: PASS. The stale-pin test raises OverlayValidationError; the live-pin test has one node and all three declarations.

- [ ] **Step 7: Run the shadow-code absence check**

Run:

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow
rg -n "_EXTERNAL_REFERENCE_SUPPORTING_FIELDS|_absorb_external_reference_metadata|identity_table: dict\\[str, SourceRef\\]" science/src/science_tool/graph
# Scoped to the loader/closure: materialize.py legitimately projects `reference_only_ids` OUT of
# arbitration's declarations (see Task 5 Step 7).
rg -n "reference_only_ids|external_reference_ids" science/src/science_tool/graph/sources.py science/src/science_tool/graph/commons_sources.py
~~~

Expected: no matches.

- [ ] **Step 8: Commit fixed-point closure**

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow
git add science/src/science_tool/graph/commons_sources.py science/src/science_tool/graph/sources.py science/tests/test_graph_commons_sources.py science/tests/test_substrate_two_scope_e2e.py science/tests/test_commons_overlay.py
git commit -m "fix(graph): close commons overlays before identity arbitration"
~~~

---

### Task 6: Certify dataset overlay status and version pinning end to end

**Files:**

- Modify: science/tests/test_graph_commons_sources.py
- Modify: science/tests/test_commons_overlay.py
- Modify: science/model/tests/test_mixin_dataset_2_0.py

**Interfaces:**

- Consumes dataset/2.0 from Task 1 and arbitration from Tasks 3–5.
- Produces an end-to-end proof that a dataset/2.0 commons owner accepts project status through PROJECT_ONLY.
- Produces a negative compatibility proof that dataset/1.0 still treats status as REPLACE and rejects a borrower replacing a defended value.

- [ ] **Step 1: Add the dataset/2.0 graph regression**

Create a commons dataset fixture with:

~~~yaml
schema_profile: science-entity-base/1.0+dataset/2.0
id: dataset:status-demo
kind: dataset
status: canonical
origin: external
tier: use-now
dataset_class: pointer
access:
  level: public
  verified: true
~~~

Create its project overlay with status: active. Load ProjectSources and assert:

~~~python
entity = next(entity for entity in sources.entities if entity.canonical_id == "dataset:status-demo")
assert entity.status == "active"
~~~

- [ ] **Step 2: Add the pinned-1.0 negative control**

Use the same canonical/overlay shape with schema_profile dataset/1.0 and a defended canonical status. Assert the arbitration result carries contribution-conflict for status and names the overlay path. This is the versioning atomicity test: do not weaken it to “1.0 validates.”

- [ ] **Step 3: Run the status slice**

Run:

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow/science
uv run --frozen pytest tests/test_graph_commons_sources.py tests/test_commons_overlay.py -q -k "dataset and status"
~~~

Expected: PASS; 2.0 merges and 1.0 refuses replacement.

- [ ] **Step 4: Commit the acceptance slice**

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow
git add science/tests/test_graph_commons_sources.py science/tests/test_commons_overlay.py science/model/tests/test_mixin_dataset_2_0.py
git commit -m "test(graph): certify versioned dataset overlay status"
~~~

---

### Task 7: Migrate science-commons dataset profiles in an isolated worktree

**Files:**

- Modify in sibling worktree: ~/d/science-commons/.worktrees/dataset-mixin-2/datasets/*/entity.md

**Interfaces:**

- Consumes the toolkit schema/default support committed in Task 1.
- Produces every live science-commons dataset profile with dataset/2.0 while preserving base and bio extension components.
- Produces a separate science-commons commit; it is not added to the science repository commit.

- [ ] **Step 1: Create the sibling worktree without touching its dirty main checkout**

Run:

~~~bash
git -C ~/d/science-commons worktree add ~/d/science-commons/.worktrees/dataset-mixin-2 -b fix/dataset-mixin-2
~~~

Expected: a clean worktree on a new branch. The dirty files in the main science-commons checkout remain unchanged.

- [ ] **Step 2: Record the migration denominator**

Run:

~~~bash
rg -l "schema_profile:.*\\+dataset/1\\.0" ~/d/science-commons/.worktrees/dataset-mixin-2/datasets
~~~

Expected: 41 dataset entity.md paths. Save the count in the commit message body or execution notes; a different count requires inspection before editing.

- [ ] **Step 3: Apply the one-component migration**

Run:

~~~bash
perl -pi -e 's/\\+dataset\\/1\\.0/\\+dataset\\/2.0/' ~/d/science-commons/.worktrees/dataset-mixin-2/datasets/*/entity.md
~~~

This intentionally preserves science-entity-base/1.0 and every +bio.* extension. Do not edit paper/topic/theme profiles.

- [ ] **Step 4: Verify the migration is total and narrow**

Run:

~~~bash
rg -n "schema_profile:.*\\+dataset/1\\.0" ~/d/science-commons/.worktrees/dataset-mixin-2/datasets
~~~

Expected: no matches.

Run:

~~~bash
rg -n "schema_profile:.*\\+dataset/2\\.0" ~/d/science-commons/.worktrees/dataset-mixin-2/datasets
~~~

Expected: the same 41 records.

Run:

~~~bash
git -C ~/d/science-commons/.worktrees/dataset-mixin-2 diff --check
git -C ~/d/science-commons/.worktrees/dataset-mixin-2 diff --stat
~~~

Expected: only datasets/*/entity.md files; one profile-component replacement per file.

- [ ] **Step 4a: Build the migrated worktree's registry**

`registry.sqlite` is gitignored, so a fresh worktree has none. Every consumer that resolves
through the registry — the Task 8 meta canaries, and the toolkit tests that honour
`SCIENCE_COMMONS_ROOT` — fails until it exists. `science commons validate` does NOT need it (it
scans files), so validating first and treating that pass as readiness is misleading.

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow/science
SCIENCE_COMMONS_ROOT=~/d/science-commons/.worktrees/dataset-mixin-2 uv run --frozen science commons index rebuild
~~~

Expected: `indexed 369 entities`. The file is ignored, so the worktree stays clean and this adds
nothing to the migration commit.

- [ ] **Step 5: Validate the migrated store with the feature toolkit**

Run:

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow/science
SCIENCE_COMMONS_ROOT=~/d/science-commons/.worktrees/dataset-mixin-2 uv run --frozen science commons validate
~~~

Expected: `checked 369 entities` with zero errors. If the inventory has intentionally changed before execution, reconcile the new authoritative inventory count before accepting a different denominator.

- [ ] **Step 6: Commit the commons migration separately**

~~~bash
git -C ~/d/science-commons/.worktrees/dataset-mixin-2 add datasets
git -C ~/d/science-commons/.worktrees/dataset-mixin-2 commit -m "chore(schema): migrate datasets to mixin 2.0"
~~~

---

### Task 8: Run federation canaries, graph-output assertions, and full verification

**Files:**

- Modify only if failures expose A-owned defects: focused files from Tasks 1–6.
- Do not fix stale consumer pins, Persi2025 authority scope, or wang2025-mri-gwas in this plan; record those as surfaced pre-existing defects.

**Interfaces:**

- Certifies the design’s meta graph counts, toolkit package health, model package health, and commons compatibility.
- Produces the final evidence required before claiming A complete.

- [ ] **Step 1: Run the complete model package**

Run:

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow/science/model
uv run --frozen pytest
~~~

Expected: PASS.

- [ ] **Step 2: Run the complete toolkit package**

Run:

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow/science
SCIENCE_COMMONS_ROOT=~/d/science-commons/.worktrees/dataset-mixin-2 uv run --frozen pytest
~~~

Expected: PASS. Default marker exclusions remain in effect.

- [ ] **Step 3: Run lint and types**

Run:

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow/science
uv run --frozen ruff check
uv run --frozen pyright
~~~

Expected: both PASS.

- [ ] **Step 4: Build and validate meta against the migrated commons worktree**

Run:

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow/meta
SCIENCE_COMMONS_ROOT=~/d/science-commons/.worktrees/dataset-mixin-2 uv run --frozen science validate --verbose
SCIENCE_COMMONS_ROOT=~/d/science-commons/.worktrees/dataset-mixin-2 uv run --frozen science graph build --local-only
~~~

Expected: both commands complete without an A-owned load/overlay error.

- [ ] **Step 5: Assert the metadata graph denominators**

The acceptance is a RELATION between the pre-arc graph and the new one, not a count. A bare
count cannot tell "composition added metadata" from "composition replaced one set of triples
with a different set of the same size", which is the very confusion this step exists to rule
out. The corpus canary is recorded second, because it dates the moment it is written.

Build the pre-arc graph once for comparison:

~~~bash
git -C ~/d/science worktree add -f --detach /tmp/prearc c94be64c
cd /tmp/prearc/meta && uv run --frozen science graph build --local-only
~~~

Then compare the two graphs:

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow/meta
uv run --frozen python - <<'PY'
from rdflib import Dataset, URIRef
DOI = URIRef("http://example.org/science/vocab/doi")
DATE = URIRef("http://purl.org/dc/terms/date")

def triples(path):
    d = Dataset(); d.parse(path, format="trig")
    return {(s, p, o) for p in (DOI, DATE) for s, _, o, _ in d.quads((None, p, None, None))}

pre, now = triples("/tmp/prearc/meta/knowledge/graph.trig"), triples("knowledge/graph.trig")
assert pre <= now, f"pre-arc metadata LOST: {sorted(pre - now)[:5]}"
counts = (sum(1 for s, p, o in now if p == DOI), sum(1 for s, p, o in now if p == DATE))
print(counts, f"+{len(now - pre)} added")
PY
~~~

Expected, in order of authority:

1. Every pre-arc DOI/date triple survives, values included (`pre <= now`). A lost or changed
   triple is a regression regardless of the totals.
2. Additions are bib metadata filling owner vacancies. Spot-check one against
   `papers/references.bib`: the owner authored no DOI, and the bib entry supplies it.
3. The corpus canary at 2026-07-17 is `(72, 95)` with 112 additions. This number is a fact about
   meta's CONTENT, not about the toolkit -- it moves whenever papers or bib entries are added, so
   a mismatch calls for re-checking 1 and 2, never for editing the code to reproduce it.

Together these prove owner-unset composition preserved existing metadata AND filled vacancies,
without a field-name allowlist.

Note: the plan originally asserted `(23, 18)`. That number matched neither the pre-arc graph
(`25, 30`) nor the result, and being lower than pre-arc it would have accepted a state that
LOST metadata -- the opposite of what the step set out to prove.

- [ ] **Step 6: Check the branch diff for forbidden remnants and unrelated edits**

Run:

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow
git diff --check
git status --short
rg -n "_EXTERNAL_REFERENCE_SUPPORTING_FIELDS|_absorb_external_reference_metadata|should_defer|deferred_dataset_datapackage" science/src
# The loader and closure must never consult external-reference ids to decide identity. Such a set
# survives only in graph/materialize.py, as the post-arbitration `reference_only_ids` projection.
rg -n "reference_only_ids|external_reference_ids" science/src/science_tool/graph/sources.py science/src/science_tool/graph/commons_sources.py
~~~

Expected: diff check clean; status contains only intended A files; forbidden-remnant search has no matches.

- [ ] **Step 7: Commit any verification-driven A fixes**

If and only if Steps 1–6 required an A-scoped correction, commit the focused files:

~~~bash
cd ~/d/science/.worktrees/commons-overlay-bib-shadow
git add science/src science/model/src science/tests science/model/tests
git commit -m "fix(graph): close identity arbitration verification gaps"
~~~

If no files changed, do not create an empty commit.

- [ ] **Step 8: Request code review before branch integration**

Invoke superpowers:requesting-code-review with:

- Design: docs/plans/2026-07-16-identity-arbitration-design.md
- Plan: docs/plans/2026-07-16-identity-arbitration-implementation-plan.md
- Science commit range: c94be64c..HEAD
- Commons migration branch: fix/dataset-mixin-2
- Verification evidence from Steps 1–6

The review must explicitly inspect permutation invariance, diagnostic duplicate-owner behavior, the absence of the side channel/five-field list, and the unchanged dataset/1.0 semantics.

---

### Task 9: Integrate toolkit-first, then repin, then merge commons

**Why an ordered gate.** `mixin-dataset-2.0.json` exists only on this toolkit branch. The 41
migrated `science-commons` datasets on `fix/dataset-mixin-2` reference it by name. A consumer
resolves that schema resource from the toolkit revision its `uv.lock` pins, so any consumer still
pinned to a pre-2.0 toolkit cannot resolve `mixin-dataset-2.0.json` and fails to load every
migrated dataset (exit 1, `schema resource 'mixin-dataset-2.0.json' not found`). The only safe
sequence therefore lands the toolkit first, repins consumers onto it, proves the federation on
those pins, and merges commons last. This mirrors an expand → migrate → contract rollout: the new
schema version must be resolvable everywhere before any data references it.

**Files:**

- No toolkit source changes. This task is release sequencing plus the commons merge notes.
- Add the ordering constraint to the `science-commons` merge notes for `fix/dataset-mixin-2` so a
  future operator merging that branch sees the toolkit-first requirement at the merge point, not
  only here.

- [ ] **Step 1: Merge the toolkit branch, including `mixin-dataset-2.0`**

Land `fix/commons-overlay-bib-shadow` on toolkit `main`. `mixin-dataset-1.0.json` is retained, so
consumers not yet repinned keep resolving their pinned 1.0 profiles unchanged.

- [ ] **Step 2: Repin managed consumers that read current commons**

Bump the toolkit pin in every managed consumer that resolves commons datasets (`meta`,
`mechanisms/evolution`, `cancer-types/multiple-myeloma`, and any other consumer on a commons pin)
to the merged toolkit revision, and `uv sync --frozen` each. Until a consumer is repinned it MUST
NOT read the migrated commons.

- [ ] **Step 3: Run the federation canaries against the repinned consumers**

~~~bash
# For each repinned consumer, against the MIGRATED commons:
SCIENCE_COMMONS_ROOT=~/d/science-commons uv run --frozen science validate --verbose
SCIENCE_COMMONS_ROOT=~/d/science-commons uv run --frozen science graph build --local-only
~~~

Expected: no `schema resource 'mixin-dataset-2.0.json' not found`, and the Task 8 Step 5
denominator relation still holds (`pre <= now`, canary `(72, 95)`). A consumer that genuinely
stands alone may instead build with `science graph build --no-commons`; that path never reads the
migrated schema and is not a substitute for repinning a consumer that does consume commons.

- [ ] **Step 4: Merge the commons migration last**

Only after Steps 1–3 are green, merge `science-commons` `fix/dataset-mixin-2` (migration
`5c36831`; branch tip `b77959a` adds `MERGE-NOTES.md` recording this dependency). Commons-first is
prohibited (see Global Constraints). Delete `MERGE-NOTES.md` as part of the merge once the toolkit
is landed and consumers are repinned.
