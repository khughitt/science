"""Structural QA checks for proposition entities.

These checks operate on frontmatter only — no graph/trig parsing — so they run
even before ``graph build`` and give fast authoring-time feedback.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_model.reasoning import (
    MEMBERSHIP_ROLE_VALUES,
    SIGN_MEANINGFUL_PREDICATES,
    ClaimLayer,
    IdentificationStrength,
    Polarity,
)
from science_tool.entities import resolve_path_policy
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

# String values of polarity entries that are valid for sign-meaningful predicates.
_SIGNED_POLARITY_VALUES = frozenset(
    {Polarity.POSITIVE.value, Polarity.NEGATIVE.value, Polarity.UNSIGNED.value}
)

# String values of predicate entries that are sign-meaningful (derived from the model).
_SIGN_MEANINGFUL_VALUES = frozenset(p.value for p in SIGN_MEANINGFUL_PREDICATES)

# Allowed string values for claim_layer and identification_strength (derived from enums).
_CLAIM_LAYER_VALUES = frozenset(v.value for v in ClaimLayer)
_IDENTIFICATION_STRENGTH_VALUES = frozenset(v.value for v in IdentificationStrength)


def _propositions(ctx: ValidateContext) -> list[tuple[Path, dict]]:
    """Return (path, frontmatter) pairs for every proposition file."""
    prop_dir = ctx.project_root / resolve_path_policy("proposition").root
    result: list[tuple[Path, dict]] = []
    if prop_dir.is_dir():
        for path in sorted(prop_dir.glob("*.md")):
            result.append((path, ctx.frontmatter(path)))
    return result


@Check(section="propositions", order=10)
def check_polarity_predicate_aptitude(ctx: ValidateContext) -> Iterator[Result]:
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
                yield Result(
                    severity=Severity.ERROR,
                    path=path,
                    line=None,
                    message=(
                        f"{path.name}: predicate '{predicate_str}' is sign-meaningful but "
                        f"polarity is {polarity_str!r} — must be one of "
                        f"{sorted(_SIGNED_POLARITY_VALUES)}"
                    ),
                    rule="proposition.polarity.aptitude",
                    task=None,
                )
        else:
            # Sign-less: polarity must be not_applicable.
            if polarity_str != Polarity.NOT_APPLICABLE.value:
                yield Result(
                    severity=Severity.ERROR,
                    path=path,
                    line=None,
                    message=(
                        f"{path.name}: predicate '{predicate_str}' is sign-less but "
                        f"polarity is {polarity_str!r} — must be 'not_applicable'"
                    ),
                    rule="proposition.polarity.aptitude",
                    task=None,
                )


@Check(section="propositions", order=20)
def check_canonical_enum_binding(ctx: ValidateContext) -> Iterator[Result]:
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
                yield Result(
                    severity=Severity.ERROR,
                    path=path,
                    line=None,
                    message=(
                        f"{path.name}: claim_layer '{claim_layer_str}' is not a canonical "
                        f"ClaimLayer value — must be one of {sorted(_CLAIM_LAYER_VALUES)}"
                    ),
                    rule="proposition.claim_layer.canonical",
                    task=None,
                )

        identification_strength = fm.get("identification_strength")
        if identification_strength is not None:
            id_str = str(identification_strength)
            if id_str not in _IDENTIFICATION_STRENGTH_VALUES:
                yield Result(
                    severity=Severity.ERROR,
                    path=path,
                    line=None,
                    message=(
                        f"{path.name}: identification_strength '{id_str}' is not a canonical "
                        f"IdentificationStrength value — must be one of "
                        f"{sorted(_IDENTIFICATION_STRENGTH_VALUES)}"
                    ),
                    rule="proposition.identification.canonical",
                    task=None,
                )


@Check(section="propositions", order=30)
def check_discusses_membership(ctx: ValidateContext) -> Iterator[Result]:
    """Structural QA for `discusses` membership entries (spec §5 rules 0, 1, 3, 4).

    Rule 2's "frame must be a bundle kind" is enforced at graph-build time
    (materialize), not here, since kind resolution needs the entity index.
    """
    for path, fm in _propositions(ctx):
        raw_discusses = fm.get("discusses")
        if raw_discusses is None:
            continue
        if not isinstance(raw_discusses, list):
            yield Result(
                severity=Severity.ERROR,
                path=path,
                line=None,
                message=f"{path.name}: discusses must be a list of strings or {{frame, role}} objects",
                rule="proposition.membership.shape",
                task=None,
            )
            continue
        discusses = raw_discusses
        roles_by_frame: dict[str, set[str]] = {}
        for entry in discusses:
            if isinstance(entry, str):
                frame, role = entry, "core"  # bare string => core
            elif isinstance(entry, dict):
                frame = entry.get("frame")
                role = entry.get("role", "core")
                if not frame:
                    yield Result(
                        severity=Severity.ERROR,
                        path=path,
                        line=None,
                        message=f"{path.name}: discusses entry missing required 'frame'",
                        rule="proposition.membership.frame",
                        task=None,
                    )
                    continue
                if str(role) not in MEMBERSHIP_ROLE_VALUES:
                    yield Result(
                        severity=Severity.ERROR,
                        path=path,
                        line=None,
                        message=(
                            f"{path.name}: discusses role '{role}' is not a canonical "
                            f"MembershipRole — must be one of {sorted(MEMBERSHIP_ROLE_VALUES)}"
                        ),
                        rule="proposition.membership.role",
                        task=None,
                    )
                    continue
            else:
                yield Result(
                    severity=Severity.ERROR,
                    path=path,
                    line=None,
                    message=f"{path.name}: discusses entry must be a string or a {{frame, role}} object",
                    rule="proposition.membership.shape",
                    task=None,
                )
                continue
            roles_by_frame.setdefault(str(frame), set()).add(str(role))

        for frame, roles in sorted(roles_by_frame.items()):
            if len(roles) > 1:
                yield Result(
                    severity=Severity.ERROR,
                    path=path,
                    line=None,
                    message=(
                        f"{path.name}: frame '{frame}' is listed with conflicting membership "
                        f"roles {sorted(roles)} — a proposition has exactly one role per bundle"
                    ),
                    rule="proposition.membership.duplicate",
                    task=None,
                )


# Live-bundle kind prefixes that make a cito:discusses edge a membership (design §4).
_LIVE_BUNDLE_PREFIXES = frozenset({"hypothesis", "mechanism"})


@Check(section="propositions", order=40)
def check_relations_store_membership_roles(ctx: ValidateContext) -> Iterator[Result]:
    """Validate authored `role` fields in relations.yaml (design §4, three rules).

    Rule 1: role set on a non-cito:discusses predicate → error.
    Rule 2: role set on a cito:discusses edge that is NOT a proposition→live-bundle
            membership (subject not a proposition, or object not a bundle) → error.
    Rule 3: the same (proposition, frame) pair carries conflicting roles across
            frontmatter `discusses:` and relations.yaml `role:` → error.
    """
    from science_tool.graph.sources import load_project_sources, SourceRelation

    try:
        sources = load_project_sources(ctx.project_root, strict_identity=False)
    except Exception:
        # If loading fails for unrelated reasons, skip this check gracefully —
        # other checks (e.g. cross_references) will surface the load failure.
        return

    # Build a map of (proposition_cid, frame_cid) → role from relations.yaml.
    # Also emit rule-1 and rule-2 errors for each relation.
    relation_roles: dict[tuple[str, str], str] = {}

    for relation in sources.relations:
        if relation.role is None:
            continue

        # Rule 1: role is only meaningful on cito:discusses.
        if relation.predicate != "cito:discusses":
            yield Result(
                severity=Severity.ERROR,
                path=Path(relation.source_path),
                line=None,
                message=(
                    f"relations.yaml: role '{relation.role.value}' set on "
                    f"'{relation.predicate}' relation ({relation.subject} → {relation.object}); "
                    "role is only valid on cito:discusses membership edges (design §4)"
                ),
                rule="relation.role.non-discusses",
                task=None,
            )
            continue

        # Rule 2: role on cito:discusses requires proposition subject and live-bundle object.
        subject_prefix = relation.subject.split(":", 1)[0]
        object_prefix = relation.object.split(":", 1)[0]
        subject_is_proposition = subject_prefix == "proposition"
        object_is_live_bundle = object_prefix in _LIVE_BUNDLE_PREFIXES

        if not subject_is_proposition or not object_is_live_bundle:
            yield Result(
                severity=Severity.ERROR,
                path=Path(relation.source_path),
                line=None,
                message=(
                    f"relations.yaml: role '{relation.role.value}' set on "
                    f"{relation.subject} cito:discusses {relation.object}, "
                    "but this is not a proposition→live-bundle membership edge "
                    "(subject must be a proposition and object a hypothesis/mechanism); "
                    "membership roles are only valid on membership edges (design §4)"
                ),
                rule="relation.role.non-membership",
                task=None,
            )
            continue

        # Valid membership role — record it for cross-surface conflict check (Rule 3).
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
    from science_tool.graph.sources import build_alias_map
    from science_model import normalize_alias

    alias_map = build_alias_map(sources.entities, manual_aliases=sources.manual_aliases)

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
        for frame_ref, role in iter_memberships():
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
                yield Result(
                    severity=Severity.ERROR,
                    path=Path(entity.file_path),
                    line=None,
                    message=(
                        f"{entity.canonical_id}: discusses frame ref '{frame_ref}' cannot be "
                        "resolved to a known entity; cannot check cross-surface role conflict "
                        "(design §4 rule 3)"
                    ),
                    rule="relation.role.unresolved-frame",
                    task=None,
                )
                continue
            pair = (entity.canonical_id, frame_cid)
            if pair not in canonical_relation_roles:
                continue
            relations_role = canonical_relation_roles[pair]
            if role.value != relations_role:
                yield Result(
                    severity=Severity.ERROR,
                    path=Path(entity.file_path),
                    line=None,
                    message=(
                        f"{entity.canonical_id}: conflicting membership roles for frame "
                        f"'{frame_cid}' — frontmatter says '{role.value}' but "
                        f"relations.yaml says '{relations_role}' (design §4 rule 3)"
                    ),
                    rule="relation.role.cross-surface-conflict",
                    task=None,
                )
