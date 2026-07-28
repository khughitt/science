"""Structural QA checks for proposition entities.

These checks operate on frontmatter only — no graph/trig parsing — so they run
even before ``graph build`` and give fast authoring-time feedback.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import cast

from science_model.reasoning import (
    MEMBERSHIP_ROLE_VALUES,
    SIGN_MEANINGFUL_PREDICATES,
    ClaimLayer,
    IdentificationStrength,
    MembershipRole,
    Polarity,
)

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.entities import resolve_path_policy
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

# String values of polarity entries that are valid for sign-meaningful predicates.
_SIGNED_POLARITY_VALUES = frozenset({Polarity.POSITIVE.value, Polarity.NEGATIVE.value, Polarity.UNSIGNED.value})

# String values of predicate entries that are sign-meaningful (derived from the model).
_SIGN_MEANINGFUL_VALUES = frozenset(p.value for p in SIGN_MEANINGFUL_PREDICATES)

# Allowed string values for claim_layer and identification_strength (derived from enums).
_CLAIM_LAYER_VALUES = frozenset(v.value for v in ClaimLayer)
_IDENTIFICATION_STRENGTH_VALUES = frozenset(v.value for v in IdentificationStrength)


SECTION, RULES = declare_validation_rules(
    section_id="propositions",
    section_title="propositions",
    section_order=150,
    rule_ids=(
        "proposition.claim-layer.canonical",
        "proposition.identification.canonical",
        "proposition.membership.duplicate",
        "proposition.membership.frame",
        "proposition.membership.role",
        "proposition.membership.shape",
        "proposition.polarity.aptitude",
        "relation.role.cross-surface-conflict",
        "relation.role.non-discusses",
        "relation.role.non-membership",
        "relation.role.unresolved-frame",
    ),
    severities=frozenset({"error", "warn", "info"}),
)


def _propositions(ctx: ValidateContext) -> list[tuple[Path, dict]]:
    """Return (path, frontmatter) pairs for every proposition file."""
    prop_dir = ctx.project_root / resolve_path_policy("proposition").root
    result: list[tuple[Path, dict]] = []
    if prop_dir.is_dir():
        for path in sorted(prop_dir.glob("*.md")):
            result.append((path, ctx.frontmatter(path)))
    return result


@Check(
    section=SECTION,
    order=10,
    producer_id="validate.propositions.polarity-predicate-aptitude",
    rules=tuple(RULES.values()),
)
def check_polarity_predicate_aptitude(ctx: ValidateContext) -> Iterator[CheckObservation]:
    """Corpus-level enforcement of the sign rule (design §2.2).

    For each proposition with a ``predicate`` field set:
    - sign-meaningful predicate (affects/regulates/associates_with):
      ``polarity`` must be one of {positive, negative, unsigned}; missing or
      ``not_applicable`` → ERROR.
    - sign-less predicate (any other value):
      ``polarity`` must be exactly ``not_applicable``; any other value → ERROR.
    """
    for path, fm in _propositions(ctx):
        predicate = fm.get("predicate")
        if not predicate:
            continue
        predicate_str = str(predicate)
        polarity = fm.get("polarity")
        polarity_str = str(polarity) if polarity is not None else None

        if predicate_str in _SIGN_MEANINGFUL_VALUES:
            # Sign-meaningful: polarity must be positive, negative, or unsigned.
            if polarity_str not in _SIGNED_POLARITY_VALUES:
                yield validation_observation(
                    severity=Severity.ERROR,
                    path=path,
                    line=None,
                    message=f"{path.name}: predicate '{predicate_str}' is sign-meaningful but polarity is {polarity_str!r} — must be one of {sorted(_SIGNED_POLARITY_VALUES)}",
                    rule=RULES["proposition.polarity.aptitude"],
                    task=None,
                    qualifiers={"key": []},
                )
        else:
            # Sign-less: polarity must be not_applicable.
            if polarity_str != Polarity.NOT_APPLICABLE.value:
                yield validation_observation(
                    severity=Severity.ERROR,
                    path=path,
                    line=None,
                    message=f"{path.name}: predicate '{predicate_str}' is sign-less but polarity is {polarity_str!r} — must be 'not_applicable'",
                    rule=RULES["proposition.polarity.aptitude"],
                    task=None,
                    qualifiers={"key": []},
                )


@Check(section=SECTION, order=20, producer_id="validate.propositions.canonical-enum-binding", rules=())
def check_canonical_enum_binding(ctx: ValidateContext) -> Iterator[CheckObservation]:
    """Reject non-canonical claim_layer / identification_strength values (anti-drift).

    Allowed values are derived from the ``ClaimLayer`` and ``IdentificationStrength``
    enums so this check tracks the model automatically.  Absent fields are accepted
    (unspecified ≠ invalid).
    """
    for path, fm in _propositions(ctx):
        claim_layer = fm.get("claim_layer")
        if claim_layer is not None:
            claim_layer_str = str(claim_layer)
            if claim_layer_str not in _CLAIM_LAYER_VALUES:
                yield validation_observation(
                    severity=Severity.ERROR,
                    path=path,
                    line=None,
                    message=f"{path.name}: claim_layer '{claim_layer_str}' is not a canonical ClaimLayer value — must be one of {sorted(_CLAIM_LAYER_VALUES)}",
                    rule=RULES["proposition.claim-layer.canonical"],
                    task=None,
                    qualifiers={"key": []},
                )

        identification_strength = fm.get("identification_strength")
        if identification_strength is not None:
            id_str = str(identification_strength)
            if id_str not in _IDENTIFICATION_STRENGTH_VALUES:
                yield validation_observation(
                    severity=Severity.ERROR,
                    path=path,
                    line=None,
                    message=f"{path.name}: identification_strength '{id_str}' is not a canonical IdentificationStrength value — must be one of {sorted(_IDENTIFICATION_STRENGTH_VALUES)}",
                    rule=RULES["proposition.identification.canonical"],
                    task=None,
                    qualifiers={"key": []},
                )


@Check(section=SECTION, order=30, producer_id="validate.propositions.discusses-membership", rules=())
def check_discusses_membership(ctx: ValidateContext) -> Iterator[CheckObservation]:
    """Structural QA for `discusses` membership entries (spec §5 rules 0, 1, 3, 4).

    Rule 2's "frame must be a bundle kind" is enforced at graph-build time
    (materialize), not here, since kind resolution needs the entity index.
    """
    for path, fm in _propositions(ctx):
        raw_discusses = fm.get("discusses")
        if raw_discusses is None:
            continue
        if not isinstance(raw_discusses, list):
            yield validation_observation(
                severity=Severity.ERROR,
                path=path,
                line=None,
                message=f"{path.name}: discusses must be a list of strings or {{frame, role}} objects",
                rule=RULES["proposition.membership.shape"],
                task=None,
                qualifiers={"key": []},
            )
            continue
        discusses = raw_discusses
        roles_by_frame: dict[str, set[str]] = {}
        missing_frame_reported = False
        invalid_roles_reported: set[str] = set()
        invalid_shapes_reported: set[str] = set()
        for entry in discusses:
            if isinstance(entry, str):
                frame, role = entry, "core"  # bare string => core
            elif isinstance(entry, dict):
                frame = entry.get("frame")
                role = entry.get("role", "core")
                if not frame:
                    if not missing_frame_reported:
                        missing_frame_reported = True
                        yield validation_observation(
                            severity=Severity.ERROR,
                            path=path,
                            line=None,
                            message=f"{path.name}: discusses entry missing required 'frame'",
                            rule=RULES["proposition.membership.frame"],
                            task=None,
                            qualifiers={"key": ["required-field", "frame"]},
                        )
                    continue
                if str(role) not in MEMBERSHIP_ROLE_VALUES:
                    role_key = str(role)
                    if role_key not in invalid_roles_reported:
                        invalid_roles_reported.add(role_key)
                        yield validation_observation(
                            severity=Severity.ERROR,
                            path=path,
                            line=None,
                            message=f"{path.name}: discusses role '{role}' is not a canonical MembershipRole — must be one of {sorted(MEMBERSHIP_ROLE_VALUES)}",
                            rule=RULES["proposition.membership.role"],
                            task=None,
                            qualifiers={"key": ["role", role_key]},
                        )
                    continue
            else:
                shape_key = type(entry).__name__
                if shape_key not in invalid_shapes_reported:
                    invalid_shapes_reported.add(shape_key)
                    yield validation_observation(
                        severity=Severity.ERROR,
                        path=path,
                        line=None,
                        message=f"{path.name}: discusses entry must be a string or a {{frame, role}} object",
                        rule=RULES["proposition.membership.shape"],
                        task=None,
                        qualifiers={"key": ["entry-type", shape_key]},
                    )
                continue
            roles_by_frame.setdefault(str(frame), set()).add(str(role))

        for frame, roles in sorted(roles_by_frame.items()):
            if len(roles) > 1:
                yield validation_observation(
                    severity=Severity.ERROR,
                    path=path,
                    line=None,
                    message=f"{path.name}: frame '{frame}' is listed with conflicting membership roles {sorted(roles)} — a proposition has exactly one role per bundle",
                    rule=RULES["proposition.membership.duplicate"],
                    task=None,
                    qualifiers={"key": ["frame", frame]},
                )


# Live-bundle kind prefixes that make a cito:discusses edge a membership (design §4).
_LIVE_BUNDLE_PREFIXES = frozenset({"hypothesis", "mechanism"})

# The cito:discusses predicate expressed both as a CURIE and as the resolved absolute IRI.
# Validation classifies predicates by comparing against both forms so that an edge authored
# as the full IRI ("http://purl.org/spar/cito/discusses") is treated the same way as one
# authored as the CURIE ("cito:discusses") — matching the resolution materialize.py performs
# via _resolve_relation_term / CITO_NS.  Importing _resolve_relation_term directly would
# create a circular dependency (propositions → materialize → sources → propositions), so we
# compare against both the CURIE string and the resolved IRI string instead.
_CITO_DISCUSSES_CURIE = "cito:discusses"
_CITO_DISCUSSES_IRI = "http://purl.org/spar/cito/discusses"


def _is_cito_discusses(predicate: str) -> bool:
    """Return True when `predicate` refers to cito:discusses in any authored form."""
    return predicate == _CITO_DISCUSSES_CURIE or predicate == _CITO_DISCUSSES_IRI


@Check(section=SECTION, order=40, producer_id="validate.propositions.relations-store-membership-roles", rules=())
def check_relations_store_membership_roles(ctx: ValidateContext) -> Iterator[CheckObservation]:
    """Validate authored `role` fields in relations.yaml (design §4, three rules).

    Rule 1: role set on a non-cito:discusses predicate → error.
    Rule 2: role set on a cito:discusses edge that is NOT a proposition→live-bundle
            membership (subject not a proposition, or object not a bundle) → error.
    Rule 3: the same (proposition, frame) pair carries conflicting roles across
            frontmatter `discusses:` and relations.yaml `role:` → error.
            A role-less relations.yaml cito:discusses edge to a proposition→live-bundle
            pair contributes an implicit 'core' role to this comparison (because
            materialize.py uses ``role=relation.role or MembershipRole.CORE`` and writes
            to the same deterministic membership node IRI).
    """
    try:
        sources = ctx.project_sources(strict_identity=False)
    except Exception:
        # If loading fails for unrelated reasons, skip this check gracefully —
        # other checks (e.g. cross_references) will surface the load failure.
        return

    # Build a map of (proposition_cid, frame_cid) → role from relations.yaml.
    # Explicit-role edges: also emit rule-1 and rule-2 errors.
    # Role-less cito:discusses edges to proposition→live-bundle pairs: contribute
    # implicit 'core' to the conflict map (Rule 3 only; no rule-1/rule-2 errors).
    relation_roles: dict[tuple[str, str], str] = {}

    for relation in sources.relations:
        if relation.role is None:
            # Still need to check role-less cito:discusses → proposition→live-bundle
            # edges for Rule 3 (implicit core).  All other role-less edges are irrelevant.
            if not _is_cito_discusses(relation.predicate):
                continue
            subject_prefix = relation.subject.split(":", 1)[0]
            object_prefix = relation.object.split(":", 1)[0]
            if subject_prefix == "proposition" and object_prefix in _LIVE_BUNDLE_PREFIXES:
                # Implicit core: record for cross-surface conflict check only.
                # Do NOT overwrite an explicit role already recorded for this pair.
                key = (relation.subject, relation.object)
                relation_roles.setdefault(key, "core")
            continue

        # Rule 1: role is only meaningful on cito:discusses.
        if not _is_cito_discusses(relation.predicate):
            yield validation_observation(
                severity=Severity.ERROR,
                path=Path(relation.source_path),
                line=None,
                message=f"relations.yaml: role '{relation.role.value}' set on '{relation.predicate}' relation ({relation.subject} → {relation.object}); role is only valid on cito:discusses membership edges (design §4)",
                rule=RULES["relation.role.non-discusses"],
                task=None,
                qualifiers={
                    "key": [
                        relation.subject,
                        relation.predicate,
                        relation.object,
                        relation.role.value,
                    ]
                },
            )
            continue

        # Rule 2: role on cito:discusses requires proposition subject and live-bundle object.
        subject_prefix = relation.subject.split(":", 1)[0]
        object_prefix = relation.object.split(":", 1)[0]
        subject_is_proposition = subject_prefix == "proposition"
        object_is_live_bundle = object_prefix in _LIVE_BUNDLE_PREFIXES

        if not subject_is_proposition or not object_is_live_bundle:
            yield validation_observation(
                severity=Severity.ERROR,
                path=Path(relation.source_path),
                line=None,
                message=f"relations.yaml: role '{relation.role.value}' set on {relation.subject} cito:discusses {relation.object}, but this is not a proposition→live-bundle membership edge (subject must be a proposition and object a hypothesis/mechanism); membership roles are only valid on membership edges (design §4)",
                rule=RULES["relation.role.non-membership"],
                task=None,
                qualifiers={
                    "key": [
                        relation.subject,
                        relation.object,
                        relation.role.value,
                    ]
                },
            )
            continue

        # Valid explicit membership role — record it for cross-surface conflict check (Rule 3).
        # Explicit role overwrites any implicit-core entry for the same pair.
        relation_roles[(relation.subject, relation.object)] = relation.role.value

    if not relation_roles:
        return

    # Rule 3: cross-surface conflict — same (proposition, frame) pair with conflicting roles
    # across frontmatter `discusses:` and relations.yaml `role:`.
    #
    # Key-space alignment: both sides must be canonicalized before keying so that a
    # short-slug or alias ref in either surface matches a canonical-id ref in the other.
    # We use build_alias_map (the same resolver used by the materialize path) to
    # canonicalize BOTH the frontmatter frame_refs AND the relation subject/object
    # strings.  If a ref cannot be canonicalized, we emit an ERROR (never silently skip).
    from science_model import normalize_alias

    from science_tool.graph.sources import build_alias_map

    alias_map = build_alias_map(
        sources.entities,
        manual_aliases=sources.manual_aliases,
        archive_alias_tokens=sources.archive_alias_tokens,
    )

    # Re-key relation_roles by canonicalized (subject_cid, object_cid) pairs.
    canonical_relation_roles: dict[tuple[str, str], str] = {}
    for (raw_subject, raw_object), rel_role in relation_roles.items():
        subj_cid = normalize_alias(raw_subject, alias_map)
        obj_cid = normalize_alias(raw_object, alias_map)
        canonical_relation_roles[(subj_cid, obj_cid)] = rel_role

    for entity in sources.entities:
        iter_memberships = getattr(entity, "iter_memberships", None)
        if not callable(iter_memberships):
            continue
        for frame_ref, role in cast(Iterable[tuple[str, MembershipRole]], iter_memberships()):
            # Canonicalize the frontmatter frame_ref via the alias map.
            # normalize_alias returns the raw string unchanged when the ref is not found in
            # the alias map (neither raw nor lowercased).  A known canonical_id is always
            # registered as its own alias, so the only case where resolution fails is a
            # genuinely unknown ref.
            frame_cid = normalize_alias(frame_ref, alias_map)
            unresolved = frame_ref not in alias_map and frame_ref.lower() not in alias_map
            if unresolved:
                # Since a discusses frame MUST resolve (the materialize path fails loud on
                # the same condition), surface this as an error rather than silently
                # skipping — a silent skip here would hide cross-surface conflicts for any
                # author using an alias or mis-typed ref.
                yield validation_observation(
                    severity=Severity.ERROR,
                    path=Path(entity.file_path),
                    line=None,
                    message=f"{entity.canonical_id}: discusses frame ref '{frame_ref}' cannot be resolved to a known entity; cannot check cross-surface role conflict (design §4 rule 3)",
                    rule=RULES["relation.role.unresolved-frame"],
                    task=None,
                    qualifiers={
                        "key": [entity.canonical_id, "frame", frame_ref]
                    },
                )
                continue
            pair = (entity.canonical_id, frame_cid)
            if pair not in canonical_relation_roles:
                continue
            relations_role = canonical_relation_roles[pair]
            if role.value != relations_role:
                yield validation_observation(
                    severity=Severity.ERROR,
                    path=Path(entity.file_path),
                    line=None,
                    message=f"{entity.canonical_id}: conflicting membership roles for frame '{frame_cid}' — frontmatter says '{role.value}' but relations.yaml says '{relations_role}' (design §4 rule 3)",
                    rule=RULES["relation.role.cross-surface-conflict"],
                    task=None,
                    qualifiers={"key": [entity.canonical_id, "frame", frame_cid]},
                )
