"""A frontmatter field that materializes NOTHING is an error (fb-2026-07-11-017).

The graph's source of truth for a supersession/amendment edge is a `relations:` entry with
the corresponding predicate (`profiles/core.py` RelationKind descriptors; `consolidation.py`
for supersession). A TOP-LEVEL `supersedes:`/`amends:` key looks authoritative but produces
ZERO triples, silently -- and big-picture then derives a wrong `provenance_coverage` from the
missing chains. A pure no-op field is worse than a wrong one: nothing surfaces at all.

Severity is an unconditional ERROR, NOT routed through `kind_severity`: this rule judges
whether authored information has ANY effect, not whether a kind's status/verdict vocabulary
is certified.

The REMEDIATION is kind-aware for a second, independent reason: naming the `relations:` form
is only useful where that form is admissible. `sci:supersedes` declares 18 source kinds and
`sci:amends` 6, so for most kinds the prescribed replacement is itself rejected by
materialize -- see `_remediation`.
"""

from __future__ import annotations

from collections.abc import Iterator

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.entity_scan import iter_entity_markdown
from science_tool.kind_descriptors import kind_can_author_relation
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

#: Top-level frontmatter key -> the relation name (and thus predicate) that DOES materialize.
#: The key materializes nothing on every kind; whether the relation is authorable in its
#: place is a separate, per-kind question -- see `_remediation`.
_NON_MATERIALIZING: dict[str, str] = {
    "supersedes": "sci:supersedes",
    "amends": "sci:amends",
}

SECTION, RULES = declare_validation_rules(
    section_id="materialization",
    section_title="materialization",
    section_order=158,
    rule_ids=("materialization.non-materializing-field",),
    severities=frozenset({"error", "warn", "info"}),
)


def _remediation(key: str, predicate: str, kind: object) -> str:
    """The actionable half of the message, for this key on this kind.

    The relations: form is prescribed ONLY where the kind may actually author it. The
    `supersedes` RelationKind admits 18 source kinds and `amends` 6, so for most kinds the
    old blanket prescription named a form materialize rejects with
    `RelationRejection("illegal-kind-pair")` -- an ERROR whose only exit was deleting the
    authored lineage. A check that judges whether authored information has any effect must
    not, in the same breath, direct the author at a form that also has none.

    A non-string `kind` cannot be tested for admissibility, so it keeps the schematic
    prescription: "this kind cannot author the edge" is a claim, and it is not one we can
    support for a kind we failed to read.
    """
    relation_name = key  # the frontmatter key and the RelationKind share a name
    if isinstance(kind, str) and not kind_can_author_relation(relation_name, kind):
        return (
            f"kind '{kind}' cannot author '{predicate}' either (it is not a declared source "
            f"endpoint for that relation), so there is no supported spelling for this lineage: "
            f"remove the key, or widen the relation's endpoints if the lineage is real."
        )
    return f"Author it as a relations: entry with 'predicate: {predicate}' and a 'target: <target-id>' instead."


@Check(section=SECTION, order=23, producer_id="validate.materialization", rules=tuple(RULES.values()))
def check_non_materializing_fields(ctx: ValidateContext) -> Iterator[CheckObservation]:
    entities_root = ctx.project_root / "entities"
    if not entities_root.is_dir():
        return

    for path in iter_entity_markdown(entities_root):
        fm = ctx.frontmatter(path)
        kind = fm.get("kind")
        entity_id = fm.get("id") or path.name
        for key, predicate in _NON_MATERIALIZING.items():
            if key not in fm:  # PRESENCE, not value -- null/[] are still findings
                continue
            yield validation_observation(
                severity=Severity.ERROR,
                path=path,
                line=None,
                message=f"{entity_id}: top-level '{key}:' materializes no triples and is silently ignored by the graph. {_remediation(key, predicate, kind)}",
                rule=RULES["materialization.non-materializing-field"],
                task=None,
                qualifiers={"key": ["frontmatter-field", key]},
            )
