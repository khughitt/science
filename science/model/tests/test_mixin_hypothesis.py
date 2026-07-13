"""`mixin-hypothesis-1.0` — the first project-authored kind on the shared schema system.

The authority for every disposition below is `docs/plans/2026-07-12-hypothesis-field-adjudication.md`
(Task 2). This file is its EXECUTABLE form: the schema is checked against the adjudication, not
against a hand-kept list in prose.
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

import pytest

from science_model.entity_schema import (
    EntityValidationError,
    EntityValidator,
    default_profile_for_kind,
)

PROFILE = default_profile_for_kind("hypothesis")
V = EntityValidator()
MIXIN = json.loads(
    (files("science_model.schemas") / "mixin-hypothesis-1.0.json").read_text(encoding="utf-8")
)


def _h(**over: Any) -> dict[str, Any]:
    base = {
        "id": "hypothesis:0001-x",
        "kind": "hypothesis",
        "title": "T",
        "created": "2026-07-12",
        "updated": "2026-07-12",
        "status": "active",
    }
    base.update(over)
    return base


# ---------------------------------------------------------------------------------------------
# TASK 2's ADJUDICATION, AS DATA.
#
# Task 2 has FOUR dispositions, and rename is not delete. Collapsing them loses the one fact the
# migration needs: a RENAMED key has a TARGET that must exist and must receive its value; a DELETED
# key has none. Both end up `false` in the mixin -- but for opposite reasons, and only one of them
# obliges the migration to write something.
# ---------------------------------------------------------------------------------------------

# §2, §3, §4, §6-keep -- an accepted toolkit contract owns the semantics.
CORE = {
    "id", "kind", "title", "status", "created", "updated",       # §2 structural
    "related", "source_refs",                                    # §2 resolution/graph edges
    "origins", "added_by", "lens_views", "ontology_terms",       # §3 real readers
    "datasets", "review_state", "aliases", "profile",
    "composition_rule", "description", "rival_model_packet",
    "required_capabilities", "capability_scope",                 # §4 capability side-channel
}

# NEW core -- 0 authored today; core BEFORE any reader ships (design rev 8/9).
NEW_CORE = {"verdict", "closure_basis", "superseded_by", "resynthesized_into", "archive_ref"}

# §5 PROJECT-EXTENSION -- real fields, owned by ONE project. Must be UNDECLARED in core: admission
# is Task 6b's to grant, and `false` here would make the extension unsatisfiable.
PROJECT_EXTENSION = {
    "confidence_label", "confidence_mechanistic_label", "identification",   # mm30
    "external_hypothesis_id",                                              # evolution
}

# §6 RENAME / MIGRATE -- the VALUE survives; only its home changes. The migration MUST write the
# target. `false` on the source key, so the old spelling can never come back.
RENAMED_TO_FIELD = {
    "phase": "status",                                    # design rev 7 -- `phase` IS the lifecycle
    "author_stated_evidence": "source_stated_evidence",   # -> extension-evolution.provenance (§6)
    "promoted_from": "origins",                           # its values are literally source paths
}

# ...and one whose target is not a FIELD at all. `confidence` becomes author-written
# `expert_judgment` evidence-line ENTITIES (§5b). Two scalars do not specify a target proposition,
# stance, source, strength or independence -- so the migration must REFUSE to synthesize them, and
# there is no key here for it to write. Kept distinct from a delete precisely because the value is
# not garbage; it is under-specified, and only the author can finish it.
RENAMED_TO_ENTITY = {
    "confidence": "evidence-line (expert_judgment) -- AUTHOR-WRITTEN, never migrated"
}

# §7 DERIVED / DELETE -- no target. The value does not survive, and nothing is owed to it.
DELETED = {
    "belief_state",          # derived: belief.py's _claims() already covers Hypothesis (Task 2b)
    "evidence_stance",       # §5b: collapses durable origin with time-varying coverage
    "tags",                  # already ruled legacy by the toolkit's OWN health check
    "priority", "role", "domain", "promotion_criteria",   # no owned semantics (§7)
}

RENAMED = set(RENAMED_TO_FIELD) | set(RENAMED_TO_ENTITY)
FORBIDDEN = RENAMED | DELETED      # everything `false` in the mixin, for two different reasons

# Every field a PROJECT EXTENSION declares (Task 6b). Note it is not the same set as
# PROJECT_EXTENSION: `source_stated_evidence` is authored by nobody yet -- it is the rename TARGET
# of `author_stated_evidence`, and it must be declared before the migration can write it.
PROJECT_EXTENSION_TARGETS = PROJECT_EXTENSION | {"source_stated_evidence"}

# The corpus, MEASURED (Task 1) -- written out, NOT computed as the union of the three sets above.
# A derived AUTHORED_KEYS would make the partition test a tautology that passes no matter which
# disposition a key was filed under, or whether the corpus authors it at all. This literal is the
# only thing in the file that the schema is not free to define.
AUTHORED_KEYS = {
    "added_by", "aliases", "author_stated_evidence", "belief_state", "capability_scope",
    "composition_rule", "confidence", "confidence_label", "confidence_mechanistic_label",
    "created", "datasets", "description", "domain", "evidence_stance", "external_hypothesis_id",
    "id", "identification", "kind", "lens_views", "ontology_terms", "origins", "phase",
    "priority", "profile", "promoted_from", "promotion_criteria", "related",
    "required_capabilities", "review_state", "rival_model_packet", "role", "source_refs",
    "status", "tags", "title", "updated",
}
assert len(AUTHORED_KEYS) == 36


_LIST_KEYS = {"related", "source_refs", "origins", "lens_views", "ontology_terms", "datasets",
              "aliases", "tags", "required_capabilities", "resynthesized_into", "same_as"}
_TYPED_KEYS: dict[str, Any] = {
    "created": "2026-07-12", "updated": "2026-07-12",   # `format: date` from base 2.0
    "superseded_by": "hypothesis:0002-y",               # `pattern: ^hypothesis:`
    "verdict": "supported",                             # an ENUM -- "x" is not in it
    # Constrained by THIS task. Every contract added to the mixin is a new way for `"x"` to be
    # wrong, so every contract added owes a sample here.
    "composition_rule": "conjunctive",                  # an ENUM
    "capability_scope": "methodological",               # an ENUM
    "review_state": {"last_reviewed": "2026-07-12"},    # an OBJECT, closed
    "rival_model_packet": {"packet_id": "p"},           # an OBJECT, `packet_id` required
}


def _sample(key: str) -> Any:
    """A SCHEMA-VALID value for each key. The admission tests must fail ONLY on admission.

    Every key with a value constraint needs its own sample. A bare "x" for `created` (a date), for
    `superseded_by` (a pattern) or for `verdict` (an enum) makes an admission test go red for a
    reason that has nothing to do with whether the property is DECLARED -- and it goes red looking
    exactly like a schema defect while actually being a fixture defect. That misdirection is the
    whole cost: the test would be pointing at the wrong file.
    """
    if key in _LIST_KEYS:
        return []
    return _TYPED_KEYS.get(key, "x")


def test_lifecycle_vocabulary_is_the_ruled_one() -> None:
    for good in ("draft", "active"):
        V.validate_as(_h(status=good), PROFILE)
    for verdict_word in ("proposed", "under-investigation", "supported", "weakened"):
        with pytest.raises(EntityValidationError):
            V.validate_as(_h(status=verdict_word), PROFILE)


def test_verdict_excludes_the_unassessed_spellings() -> None:
    V.validate_as(_h(verdict="refuted"), PROFILE)
    for bad in ("proposed", "under-investigation"):
        # D1: absence already means "not yet assessed". Admitting these makes three
        # spellings of one state and re-collapses the axis.
        with pytest.raises(EntityValidationError):
            V.validate_as(_h(verdict=bad), PROFILE)


def test_the_axes_are_orthogonal() -> None:
    # The cell the collapsed field could not express.
    V.validate_as(
        _h(status="superseded", verdict="supported", superseded_by="hypothesis:0002-y"), PROFILE
    )
    V.validate_as(_h(status="draft", verdict="weakened"), PROFILE)


def test_complete_REQUIRES_a_verdict() -> None:
    # RULED (design rev 6): prohibited outright, NOT dischargeable by closure_basis.
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(status="complete"), PROFILE)
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(status="complete", closure_basis="ran out of time"), PROFILE)
    V.validate_as(_h(status="complete", verdict="supported"), PROFILE)


def test_retired_always_requires_a_closure_basis() -> None:
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(status="retired"), PROFILE)
    V.validate_as(_h(status="retired", closure_basis="no samples left"), PROFILE)


def test_superseded_requires_lineage_or_a_basis() -> None:
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(status="superseded"), PROFILE)
    V.validate_as(_h(status="superseded", superseded_by="hypothesis:0002-y"), PROFILE)
    # `resynthesized_into` is a LIST (archive.py:38, materialize.py:155) -- not a string.
    V.validate_as(_h(status="superseded", resynthesized_into=["hypothesis:0002-y"]), PROFILE)
    V.validate_as(_h(status="superseded", closure_basis="folded into h5"), PROFILE)


def test_archived_requires_a_basis() -> None:
    # The `archived` half of the terminal contract -- the one with no other test in this file.
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(status="archived"), PROFILE)
    V.validate_as(_h(status="archived", archive_ref="archive/2026/h1.md"), PROFILE)
    V.validate_as(_h(status="archived", closure_basis="folded into the h5 reframing"), PROFILE)


def test_phase_and_disposition_are_FORBIDDEN() -> None:
    for gone in ({"phase": "candidate"}, {"disposition": "closed"}, {"disposition_basis": "x"}):
        with pytest.raises(EntityValidationError):
            V.validate_as(_h(**gone), PROFILE)


def test_an_arbitrary_unknown_key_is_REJECTED() -> None:
    # THE original defect is that `Entity` is extra="ignore" and silently DROPS anything
    # undeclared. A test using `phase` would prove nothing about unknown keys -- `phase` is
    # explicitly `false` in the schema. This is the test that actually pins it.
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(role_typo="oops"), PROFILE)


@pytest.mark.parametrize("derived", ["schema_profile", "version"])
def test_DERIVED_fields_cannot_be_AUTHORED_on_a_project_kind(derived: str) -> None:
    # "`schema_profile` is derived; `version` is a commons concept" is only DOCUMENTATION until
    # something rejects the authored spelling. Base 2.0 keeps both as optional generic properties
    # (commons records on base 1.0 still author them), so the base cannot be where this is said --
    # `mixin-hypothesis` must set BOTH to `false`.
    #
    # Otherwise the failure is silent and self-inflicted: an author writes
    # `schema_profile: science-entity-base/1.0+hypothesis/1.0`, the schema accepts it, and the
    # entity is now validated against a profile it chose for itself. A derived field an author can
    # set is not derived -- it is a second, unversioned source of truth. That is the exact shape of
    # the `status`/`phase` collapse this whole arc exists to undo.
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(**{derived: "1.0.0"}), PROFILE)


def test_the_mixin_says_so_STRUCTURALLY_not_just_behaviorally() -> None:
    # Pin the mechanism, so a later refactor cannot make the two tests above pass by accident
    # (e.g. via `unevaluatedProperties: false` alone) and then regress when the base changes.
    assert MIXIN["properties"]["schema_profile"] is False
    assert MIXIN["properties"]["version"] is False


def test_no_ADMITTED_field_has_a_VACUOUS_contract() -> None:
    # The structural guard for the whole class of defect. `{}` admits 42; an array with no `items`
    # admits [42]; an object with neither `properties` nor `$ref` admits {"anything": 1}. Each of
    # those LOOKS like a declaration and is the absence of one -- and a reviewer scanning the mixin
    # reads them as "declared". Five core fields shipped that way in the first draft.
    #
    # This does not check that the contract is RIGHT (that is
    # `test_the_schema_is_at_least_as_strict_as_the_projection`, Task 8). It checks that a contract
    # EXISTS -- which is the part a human eye slides straight over.
    def _resolve(spec: dict[str, Any]) -> dict[str, Any]:
        # Follow `$ref` into `$defs` -- otherwise the guard is itself vacuous for every field
        # whose contract is a `$def`, which is five of the six it most needs to check.
        ref = spec.get("$ref")
        if not ref:
            return spec
        assert ref.startswith("#/$defs/"), f"unexpected ref {ref}"
        target = MIXIN["$defs"].get(ref.removeprefix("#/$defs/"))
        assert target, f"{ref} does not resolve"
        return target

    for name, spec in MIXIN["properties"].items():
        if spec is False:
            continue  # forbidden -- an absent contract is the POINT
        assert spec != {}, f"{name}: `{{}}` is not a contract; it admits 42"
        resolved = _resolve(spec)
        if resolved.get("type") == "array":
            item = resolved.get("items")
            assert item, f"{name}: an array with no `items` admits [42]"
            assert _resolve(item) != {}, f"{name}: `items: {{}}` admits [42]"
        if resolved.get("type") == "object":
            assert (
                "properties" in resolved
                or "additionalProperties" in resolved
                or "propertyNames" in resolved
            ), f"{name}: an object with no constrained keys admits anything"


def test_every_authored_key_has_EXACTLY_ONE_disposition() -> None:
    # The 36 keys the corpus actually authors (`science entity field-inventory --kind hypothesis`,
    # Task 1) partition into Task 2's FOUR dispositions -- no key in two, no key in none. A key that
    # falls through the partition is a key the schema has not decided about, and it will be decided
    # by accident at migration time.
    groups = [CORE, PROJECT_EXTENSION, RENAMED, DELETED]
    assert set().union(*groups) == AUTHORED_KEYS
    for i, a in enumerate(groups):
        for b in groups[i + 1:]:
            assert not (a & b), f"{sorted(a & b)} has two dispositions"


def test_every_RENAMED_key_has_a_TARGET_and_the_target_is_ADMITTED_SOMEWHERE() -> None:
    # Rename is not delete, and this is the assertion that makes the difference load-bearing: a
    # renamed key's VALUE must have somewhere to land. `source_stated_evidence` lives in
    # extension-evolution.provenance (Task 6b), so it is legitimately not in the core mixin -- but
    # it must not be nowhere. A rename whose target nobody declared is a delete with better manners.
    for source, target in RENAMED_TO_FIELD.items():
        assert MIXIN["properties"][source] is False, f"{source} must be un-resurrectable"
        assert target in CORE or target in PROJECT_EXTENSION_TARGETS, (
            f"{source} -> {target}: the target is declared nowhere"
        )
    # And the one whose target is an ENTITY, not a field: nothing to write, and the migration must
    # REFUSE rather than synthesize it (§5b). Assert only that the key itself is gone for good.
    for source in RENAMED_TO_ENTITY:
        assert MIXIN["properties"][source] is False


def test_CORE_keys_are_admitted() -> None:
    # Each core key, one at a time -- a single kitchen-sink payload would let one key's rejection
    # hide behind another's.
    for key in CORE - {"id", "kind", "title", "status"}:  # the four are already in _h()
        V.validate_as(_h(**{key: _sample(key)}), PROFILE)


def test_the_NEW_core_fields_are_admitted_AS_A_SET() -> None:
    # `verdict` and `closure_basis` get their own conditional tests above, and that is exactly how
    # `archive_ref` and `resynthesized_into` could quietly vanish from the schema while the suite
    # stayed green. They are core BEFORE any reader ships (rev 8/9); nothing else asserts they exist.
    for key in NEW_CORE:
        assert key in MIXIN["properties"], f"{key} is core and undeclared"
        V.validate_as(_h(**{key: _sample(key)}), PROFILE)


def test_PROJECT_EXTENSION_keys_are_ABSENT_FROM_CORE_but_not_FORBIDDEN_BY_IT() -> None:
    # Two assertions, and BOTH matter.
    for key in PROJECT_EXTENSION:
        # (a) core alone rejects it -- else the mixin swallowed a one-project field into the
        #     shared vocabulary of all 22 projects, which is the rev-2 defect.
        with pytest.raises(EntityValidationError):
            V.validate_as(_h(**{key: _sample(key)}), PROFILE)
        # (b) core does NOT declare it `false` -- else Task 6b is UNSATISFIABLE. `allOf` intersects,
        #     so `false` in the mixin ∧ `{type: string}` in mm30's extension is a contradiction:
        #     every mm30 hypothesis would fail, with no hint pointing at the mixin. Admission for
        #     these keys is Task 6b's to grant; the mixin must be SILENT, not hostile.
        assert key not in MIXIN["properties"]


def test_FORBIDDEN_keys_are_rejected_and_UNRESURRECTABLE() -> None:
    for key in FORBIDDEN:
        with pytest.raises(EntityValidationError):
            V.validate_as(_h(**{key: _sample(key)}), PROFILE)
        # `false`, not merely undeclared: a field D5 DELETED must not come back through a project
        # extension. This is the line that makes `tags` (which base 2.0 still declares!) actually
        # illegal -- `unevaluatedProperties` cannot reject what the base declared.
        assert MIXIN["properties"][key] is False


def test_a_field_the_BASE_declares_is_still_rejected_when_the_mixin_says_false() -> None:
    # The trap this test exists for: `unevaluatedProperties: false` does NOT reject base-declared
    # keys -- they ARE evaluated. Without the mixin's explicit `false`, base 2.0 would silently
    # re-admit `tags`, the field the toolkit's own health check exists to remove.
    assert "tags" in json.loads(
        (files("science_model.schemas") / "science-entity-base-2.0.json").read_text(
            encoding="utf-8"
        )
    )["properties"]
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(tags=["legacy"]), PROFILE)


# ---- the inherited surface: base 2.0's properties, decided EXPLICITLY ----


@pytest.mark.parametrize("key", ["schema_profile", "version", "sources", "licenses", "contributors"])
def test_the_INHERITED_prohibitions_are_structural(key: str) -> None:
    # `unevaluatedProperties: false` cannot reject what the BASE declares -- these five are declared
    # there, so only the mixin's `false` makes them illegal on a hypothesis. Without this test the
    # audit that produced them lives in prose, and prose does not fail a build.
    assert MIXIN["properties"][key] is False
    with pytest.raises(EntityValidationError):
        V.validate_as(_h(**{key: "x"}), PROFILE)


def test_the_INHERITED_admissions_actually_validate() -> None:
    # The other half of the same audit, and the half that is easy to get wrong by omission: `same_as`
    # and `dataset_usage` are live owned semantics for ANY project kind (Entity:317 -> sameAs edges
    # at materialize.py:889; Entity:444 has its own graph module). Zero hypotheses author them today,
    # so forbidding them would have looked free -- and would have deleted a capability.
    V.validate_as(_h(same_as=["hypothesis:0002-y"]), PROFILE)
    V.validate_as(_h(dataset_usage=[{"ref": "dataset:x", "role": "analyzed"}]), PROFILE)


def test_the_single_rival_packet_SURVIVES_the_projection() -> None:
    # The whole point of Step 3c, and the property `extra="ignore"` silently violated: the model
    # ACCEPTED this packet all along and `model_dump()` dropped all four keys. Acceptance was never
    # the property worth asserting -- SURVIVAL is.
    from science_model.entities import HypothesisEntity

    packet = {
        "packet_id": "platonic-vs-multimanifold",
        "rival_id": "platonic-representation-hypothesis",
        "rival_name": "PRH",
        "rival_claim": "representations converge",
        "discriminator_status": "pre-registered via question:0018",
    }

    V.validate_as(_h(rival_model_packet=packet), PROFILE)          # the SCHEMA admits it...

    dumped = HypothesisEntity.model_validate(
        {
            "project": "p", "file_path": "h.md", "content_preview": "", "ontology_terms": [],
            "related": [], "source_refs": [], **_h(rival_model_packet=packet),
        }
    ).model_dump(mode="json")["rival_model_packet"]

    for key, value in packet.items():                              # ...and the MODEL keeps it.
        assert dumped[key] == value, f"{key} validated and then evaporated"


def test_a_LIST_form_packet_serializes_BYTE_IDENTICALLY() -> None:
    # The collateral-churn guard. `_model_to_json` is an inclusive `model_dump`, so four plain
    # optionals would add four `null` keys to the serialized literal of every EXISTING packet --
    # one of which is on a PROPOSITION, an entity this migration must not touch at all.
    from science_model.reasoning import RivalModelPacket

    packet = RivalModelPacket(packet_id="p", alternative_models=["m"], shared_observables=["o"])
    serialized = json.dumps(packet.model_dump(mode="json"))

    assert "rival_id" not in serialized
    assert "discriminator_status" not in serialized
