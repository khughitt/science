"""The hypothesis SCHEMA and the hypothesis PROJECTION, reconciled field by field.

D3 rules that `mixin-hypothesis-1.0.json` is THE authority for shape and invariants and that
`HypothesisEntity` is a PROJECTION of it. That sentence has an executable meaning, and this file is
it. Three properties, and the last two are the ones a naive test cannot see:

1. Every field the schema ADMITS is REPRESENTABLE on the model  (else: validates on disk, silently
   dropped on load -- `Entity` is `extra="ignore"`).
2. The schema is AT LEAST AS STRICT as the model  (else: the model is the real authority and the
   schema is decoration).
3. Every value the schema admits SURVIVES the round trip  (else: it validates, the model *accepts*
   it, and `model_dump()` loses it -- acceptance and preservation are different properties).

☠️ SCOPE: this file reconciles the PACKAGE-DEFAULT profile -- core base + core mixin. It cannot see a
PROJECT EXTENSION, and it must not try: `entity_extensions` is a `science_tool` concept, and
`science_model` may not import its own consumer. So the third property is only half-proved here.

Its other half -- *a field declared by a project extension survives the projection* -- is D3.3, and it
is proved where the composition actually happens: `science/tests/test_schema_first_load.py`. Do not
read the battery below as covering it. `Entity` was `extra="ignore"` while every test in this file
passed, and mm30's `identification`, evolution's `source_stated_evidence`, and mm30's
`confidence_mechanistic_label` were being discarded at `model_validate` the whole time.
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

import pytest
from pydantic import ValidationError

from science_model.entities import HypothesisEntity
from science_model.entity_schema import (
    EntityValidationError,
    EntityValidator,
    default_profile_for_kind,
)
from science_model.profiles.core import CORE_PROFILE

MIXIN = json.loads(
    (files("science_model.schemas") / "mixin-hypothesis-1.0.json").read_text(encoding="utf-8")
)
BASE_2 = json.loads(
    (files("science_model.schemas") / "science-entity-base-2.0.json").read_text(encoding="utf-8")
)["properties"]
_PROFILE = default_profile_for_kind("hypothesis")
_V = EntityValidator()

# Admitted by the COMPOSED profile = what the base declares (minus what the mixin forbids) plus what
# the mixin declares. Deriving this from the mixin ALONE is how `description` hid for four drafts:
# it is CORE, authored by 3 files, declared in base 2.0 -- and on no model.
_ADMITTED = (
    {n for n in BASE_2 if MIXIN["properties"].get(n) is not False}
    | {n for n, s in MIXIN["properties"].items() if s is not False}
)

# Admitted by the schema, absent from the model, and CORRECT -- for exactly one reason: these two
# are the P1 capability subsystem, whose readers re-parse RAW frontmatter and never go through the
# model at all. The value is not dropped; it is read by another path. Absorbing them is P1, and P1
# DELETES this exception -- it must never grow a third member without a reader named beside it.
_NOT_ON_THE_MODEL = {"required_capabilities", "capability_scope"}

# The fields BOTH authorities describe. Derived from `_ADMITTED`, so the base surface
# (`created`, `updated`, `title`, `description`, `ontology_terms`, `same_as`, `dataset_usage`) is
# reconciled too. `false` properties are excluded by `_ADMITTED`: the schema rejects them outright,
# so "at least as strict" holds trivially and there is nothing to compare.
_SHARED_FIELDS = _ADMITTED & set(HypothesisEntity.model_fields)

# Model-only required fields. NOT frontmatter -- the loader stamps them -- so they never appear in a
# schema payload, and every direct model construction here goes through `_model_payload` rather than
# hand-listing them (and forgetting three).
_MODEL_ONLY: dict[str, Any] = {
    "project": "p",
    "file_path": "h.md",
    "content_preview": "",
    "ontology_terms": [],
    "related": [],
    "source_refs": [],
}

_LEGAL_ORIGIN = {"type": "literature", "ref": "paper:Smith2024"}
_LEGAL_LENS = {"lens": "mechanism", "rationale": "r"}

# Every value here is one the MODEL has an opinion about; the point is to make the schema hold the
# same opinions. It must equal `_SHARED_FIELDS` exactly -- see
# `test_the_BATTERY_is_EXACTLY_the_shared_surface`, which checks both directions.
_BATTERY: dict[str, list[Any]] = {
    "origins": [
        [42],
        42,
        [{}],
        [{"type": "nope"}],
        [{"type": "literature"}],
        [{"type": "literature", "ref": "topic:x"}],  # ref must be paper:/cite:
        [dict(_LEGAL_ORIGIN, bogus=1)],  # additionalProperties: false
        [dict(_LEGAL_ORIGIN, date="2026-02-31")],  # must be a real calendar date
        [_LEGAL_ORIGIN],  # the control: passes BOTH
    ],
    "review_state": [
        42,
        "x",
        {"review_horizon_days": 0},
        {"review_horizon_days": "x"},
        {"last_reviewed": "nope"},
        {"bogus": 1},
        {"last_reviewed": "2026-07-13", "review_horizon_days": 90},
    ],
    # The RESERVED rules are the point: `Entity._validate_composition_rule` rejects both, so a schema
    # that enumerated all four of `CompositionRule` would admit values the model refuses.
    "composition_rule": [42, "nope", "evidence_union", "faceted_support", "conjunctive"],
    # The single-rival form must SURVIVE, not merely validate -- this entry is what
    # `test_every_value_the_schema_ADMITS_SURVIVES_the_projection` runs on.
    "rival_model_packet": [
        42,
        {},
        {"packet_id": ""},
        {"packet_id": "p", "alternative_models": [42]},
        {"packet_id": "p", "bogus": 1},
        {
            "packet_id": "p",
            "rival_id": "platonic",
            "rival_name": "PRH",
            "rival_claim": "representations converge",
            "discriminator_status": "pre-registered",
        },
        {"packet_id": "p"},
    ],
    "datasets": [[42], 42, ["dataset:x"]],
    "lens_views": [
        [42],
        [{"lens": "nope", "rationale": "r"}],
        [{"lens": "mechanism"}],
        [{"lens": "mechanism", "rationale": " "}],
        [dict(_LEGAL_LENS, bogus=1)],
        [_LEGAL_LENS],
    ],
    # The BASE surface. Omitting it is how `description` stayed unreconciled: it is declared by base
    # 2.0, never by the mixin, so a battery derived from mixin properties could not see it.
    "title": [42, "T"],
    "description": [42, "a description"],
    "created": [42, "x", "2026-13-01", "2026-07-13"],
    "updated": [42, "x", "2026-07-13"],
    "ontology_terms": [42, [42], ["GO:0008150"]],
    "same_as": [42, [42], ["hypothesis:0002-y"]],
    "dataset_usage": [
        42,
        [{"ref": "x", "role": "analyzed"}],  # ref must be `^dataset:`
        [{"ref": "dataset:x", "role": "nope"}],  # role is an enum
        [{"ref": "dataset:x"}],  # role is required
        [{"ref": "dataset:x", "role": "analyzed"}],
    ],
    # The rest of the mixin surface.
    "related": [42, [42], ["hypothesis:0002-y"]],
    "source_refs": [42, [42], ["papers/x.md"]],
    "aliases": [42, [42], ["alias"]],
    "added_by": [42, "science:explore-ideas"],
    # `run:` prefix + non-empty-after-strip remainder, enforced identically by
    # `Entity._validate_autonomous_run` and the mixin's `pattern`. "bogus" (no prefix) and
    # "run:" (empty remainder) probe that neither authority is looser than the other.
    "autonomous_run": [42, "bogus", "run:", "run:2026-07-24-curation-sweep-a3f1"],
    "profile": [42, "core"],
    "id": [42, "topic:x", "hypothesis:0001-x"],
    "kind": [42, "dataset", "hypothesis"],
    "status": [42, "nope", "active"],
    "verdict": [42, "nope", "refuted"],
    "closure_basis": [42, "", "the assay was discontinued"],
    "superseded_by": [42, "topic:x", "hypothesis:0002-y"],
    "resynthesized_into": [42, [42], ["topic:x"], [], ["hypothesis:0002-y"]],
    # `relations` is admitted by the mixin (D4 leg 1) and inherited from `Entity` -- so the DERIVED
    # set gains it automatically and this hand-written battery does not. That asymmetry is the whole
    # reason `test_the_BATTERY_is_EXACTLY_the_shared_surface` exists.
    "relations": [
        42,
        [42],
        [{}],
        [{"predicate": "sci:supersedes"}],  # `target` is required
        [{"target": "hypothesis:0002-y"}],  # `predicate` is required
        [{"predicate": " ", "target": "hypothesis:0002-y"}],  # non-empty
        [
            {
                "predicate": "sci:supersedes",
                "target": "hypothesis:0002-y",
                "tarrget": "typo",
            }
        ],  # additionalProperties: false
        [{"predicate": "sci:supersedes", "target": "hypothesis:0002-y"}],  # control
        [
            {
                "predicate": "sci:supersedes",
                "target": "hypothesis:0002-y",
                "graph_layer": "graph/knowledge",
            }
        ],  # control, explicit layer
    ],
}


def _payload(**over: Any) -> dict[str, Any]:
    return {
        "id": "hypothesis:0001-x",
        "kind": "hypothesis",
        "title": "T",
        "created": "2026-07-13",
        "updated": "2026-07-13",
        "status": "active",
        **over,
    }


def _model_payload(**over: Any) -> dict[str, Any]:
    return _MODEL_ONLY | _payload(**over)


def _schema_accepts(field: str, value: Any) -> bool:
    try:
        _V.validate_as(_payload(**{field: value}), _PROFILE)
        return True
    except EntityValidationError:
        return False


def _model_accepts(field: str, value: Any) -> bool:
    try:
        HypothesisEntity.model_validate(_model_payload(**{field: value}))
        return True
    except ValidationError:
        return False


def _survives(authored: Any, dumped: Any) -> bool:
    """Every authored path is still present, with its value, after the round trip.

    NOT `dumped == authored`: a dump legitimately carries defaults the author never wrote. The claim
    is one-directional -- nothing the author WROTE may vanish.
    """
    if isinstance(authored, dict):
        return all(k in dumped and _survives(v, dumped[k]) for k, v in authored.items())
    if isinstance(authored, list):
        return len(authored) == len(dumped) and all(map(_survives, authored, dumped))
    return authored == dumped


def _model_preserves(field: str, value: Any) -> bool:
    dumped = HypothesisEntity.model_validate(_model_payload(**{field: value})).model_dump(
        mode="json"  # dates -> ISO strings, enums -> values, so it compares to AUTHORED yaml
    )
    return field in dumped and _survives(value, dumped[field])


def _kind():
    return next(k for k in CORE_PROFILE.entity_kinds if k.name == "hypothesis")


def test_descriptor_declares_the_lifecycle_not_the_verdict() -> None:
    assert sorted(_kind().statuses) == sorted(
        ["draft", "active", "complete", "superseded", "retired", "archived"]
    )
    assert _kind().default_status == "active"


def test_verdict_and_closure_basis_are_first_class_fields() -> None:
    h = HypothesisEntity.model_validate(_model_payload(verdict="refuted"))
    assert h.verdict == "refuted"


def test_disposition_is_gone() -> None:
    assert "disposition" not in HypothesisEntity.model_fields
    assert "disposition_basis" not in HypothesisEntity.model_fields


def test_the_projection_does_NOT_reimplement_the_schema_invariants() -> None:
    # D3: JSON Schema is THE authority; Pydantic is a PROJECTION. Re-asserting `complete requires a
    # verdict` as a model_validator recreates the second authority D3 exists to abolish, and
    # guarantees the two eventually disagree. The projection must be able to REPRESENT anything the
    # schema admits, and must not independently police it.
    HypothesisEntity.model_validate(_model_payload(status="complete"))  # SCHEMA rejects; model must not
    assert not _schema_accepts("status", "complete")  # ...and the schema DOES. Both halves, or neither.


def test_every_field_the_schema_ADMITS_is_REPRESENTABLE_in_the_projection() -> None:
    # A field the schema admits but the projection cannot hold is a field that validates on disk and
    # is SILENTLY DROPPED on load (`Entity` is `extra="ignore"`) -- which is `phase`'s entire
    # history, and the reason this arc exists. `description` was the third instance, and it survived
    # every earlier draft because no test looked at the fields the BASE contributes.
    missing = _ADMITTED - set(HypothesisEntity.model_fields) - _NOT_ON_THE_MODEL
    assert not missing, f"schema admits {sorted(missing)}; the projection would silently drop them"


@pytest.mark.parametrize("field", sorted(_SHARED_FIELDS))
def test_the_schema_is_at_least_as_strict_as_the_projection(field: str) -> None:
    """D3 point 4, half two — and the one that actually bites.

    **No payload the schema accepts may be rejected by the model.** If one is, the model is the real
    authority for that field and the schema is decoration.

    The first draft of `mixin-hypothesis` failed this on FIVE fields at once (`origins`,
    `review_state`, `composition_rule`, `rival_model_packet`, `datasets`) because each was declared
    `{}` or as a bare array -- and the old reconciliation test, which compared three field NAMES and
    the status enum, could not see any of it. Names are not contracts.

    The converse is NOT asserted: the schema may be STRICTER (it forbids unknown nested keys the
    model would ignore, and it enforces `complete -> verdict`, which the model deliberately does
    not). Strictness beyond the projection is the design working as intended.
    """
    for value in _BATTERY[field]:
        schema_ok = _schema_accepts(field, value)
        model_ok = _model_accepts(field, value)
        assert not (schema_ok and not model_ok), (
            f"{field}={value!r}: the SCHEMA admits it and the MODEL rejects it. "
            f"The schema is not authoritative for this field."
        )

    # Anti-tautology: a battery the schema accepts in full is a battery that proves nothing. If this
    # fires, the field's contract is vacuous (or the battery is) -- exactly the state the five `{}`
    # declarations were in, where every test still passed.
    assert any(not _schema_accepts(field, v) for v in _BATTERY[field]), (
        f"{field}: the schema rejected NOTHING in the battery -- its contract admits anything"
    )


@pytest.mark.parametrize("field", sorted(_SHARED_FIELDS))
def test_every_value_the_schema_ADMITS_SURVIVES_the_projection(field: str) -> None:
    """D3 point 4, half three — the half that "the model accepted it" cannot see.

    Acceptance and preservation are DIFFERENT properties, and `extra="ignore"` is exactly the gap
    between them: the model accepts the object, and `model_dump()` loses the keys it did not
    declare. `rival_model_packet` sat in that gap -- schema admits the four single-rival keys,
    Pydantic accepts the object, four authored values gone. Every test in the earlier draft passed.

    A field that validates on disk and evaporates on load is not a contract; it is a **trap**, and it
    is precisely `phase`'s failure mode reappearing one nesting level down. So the claim is not "the
    model tolerated it" but "the author's value is still there afterwards."
    """
    for value in _BATTERY[field]:
        if not _schema_accepts(field, value):
            continue  # the schema already refused it; nothing is owed
        assert _model_preserves(field, value), (
            f"{field}={value!r}: the SCHEMA admits it, the MODEL accepts it, and `model_dump()` "
            f"DROPS it. The value validates and then evaporates."
        )


def test_the_lens_vocabulary_is_not_a_SECOND_authority() -> None:
    # The mixin hard-codes the lens enum because JSON Schema cannot call Python. That duplication is
    # only safe while THIS test exists: add a lens to `LENS_SLUGS` without regenerating the mixin and
    # every hypothesis authoring it fails validation with no hint why.
    from science_model.lenses import LENS_SLUGS

    assert sorted(MIXIN["$defs"]["lens_view"]["properties"]["lens"]["enum"]) == sorted(LENS_SLUGS)


def test_the_status_vocabulary_is_not_a_SECOND_authority() -> None:
    assert sorted(MIXIN["properties"]["status"]["enum"]) == sorted(_kind().statuses)


def test_the_composition_rule_vocabulary_is_not_a_SECOND_authority() -> None:
    # The IMPLEMENTED rules, not every name `CompositionRule` declares. `evidence_union` and
    # `faceted_support` are RESERVED and rejected by `Entity._validate_composition_rule` -- so a
    # schema enumerating all four would admit two values the model refuses, which is the exact
    # schema-is-not-authoritative defect this test exists to prevent, committed BY this test.
    from science_model.reasoning import WEAKEST_LINK_COMPOSITION_RULES

    assert sorted(MIXIN["properties"]["composition_rule"]["enum"]) == sorted(
        r.value for r in WEAKEST_LINK_COMPOSITION_RULES
    )


def test_the_BATTERY_is_EXACTLY_the_shared_surface() -> None:
    # EQUALITY, not coverage. `_SHARED_FIELDS` is derived; the battery is hand-written -- so the
    # battery is the half that falls behind, and it falls behind in BOTH directions:
    #
    #   missing  -> a field is declared by both authorities and reconciled by neither, while every
    #               test still passes. (`description` and the whole base surface lived here.)
    #   spurious -> a battery entry for a field nobody declares. It never runs, and it reads like
    #               coverage that does not exist -- which is worse than no entry at all.
    assert set(_BATTERY) == _SHARED_FIELDS, (
        f"unreconciled: {sorted(_SHARED_FIELDS - set(_BATTERY))}; "
        f"stale: {sorted(set(_BATTERY) - _SHARED_FIELDS)}"
    )
