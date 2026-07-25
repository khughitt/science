"""A frontmatter field that materializes NOTHING is an error (fb-2026-07-11-017).

The graph's source of truth for a supersession/amendment edge is a `relations:` entry with
the corresponding predicate (`profiles/core.py` RelationKind descriptors; `consolidation.py`
for supersession). A TOP-LEVEL `supersedes:`/`amends:` key looks authoritative but produces
ZERO triples, silently -- and big-picture then derives a wrong `provenance_coverage` from the
missing chains. A pure no-op field is worse than a wrong one: nothing surfaces at all.

Severity is an unconditional ERROR, NOT routed through `kind_severity`: this rule judges
whether authored information has ANY effect, not whether a kind's status/verdict vocabulary
is certified.

Kind-awareness is a small explicit legit-reader set, not a schema derivation. `workflow-run`
carries a real top-level `supersedes` field ONLY because `qa_audit/runs.py:47` reads it for
the QA-audit chain -- a behavioral fact no kind descriptor declares, so it cannot be derived
from the D5 schema, and deriving from the schema would falsely flag it. Note `entities.py`
lists `supersedes` in `_REMOVABLE_FRONTMATTER_REF_KEYS`, but that is generic entity-deletion
reference cleanup with no supersession semantics and no emitted edge; it does not legitimize
the key as lineage authoring on other kinds.

The REMEDIATION is kind-aware for a second, independent reason: naming the `relations:` form
is only useful where that form is admissible. `sci:supersedes` declares 9 source kinds and
`sci:amends` 6, so for most kinds the prescribed replacement is itself rejected by
materialize -- see `_remediation`.
"""

from __future__ import annotations

from collections.abc import Iterator

from science_tool.entity_scan import iter_entity_markdown
from science_tool.kind_descriptors import kind_can_author_relation
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

#: Top-level frontmatter key -> the relation name (and thus predicate) that DOES materialize.
#: The key materializes nothing on every kind; whether the relation is authorable in its
#: place is a separate, per-kind question -- see `_remediation`.
_NON_MATERIALIZING: dict[str, str] = {
    "supersedes": "sci:supersedes",
    "amends": "sci:amends",
}

#: ``(kind, key)`` pairs where a top-level key IS a real field with a live domain consumer,
#: so it must NOT be flagged. Behavioral fact (a reader), not a schema declaration -- which
#: is exactly why it can't be derived from the kind descriptor.
_LEGIT_TOP_LEVEL: frozenset[tuple[str, str]] = frozenset(
    {
        ("workflow-run", "supersedes"),  # read by qa_audit/runs.py:47 for the QA-audit chain
    }
)


def _remediation(key: str, predicate: str, kind: object) -> str:
    """The actionable half of the message, for this key on this kind.

    The relations: form is prescribed ONLY where the kind may actually author it. The
    `supersedes` RelationKind admits 9 source kinds and `amends` 6, so for most kinds the
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
    return (
        f"Author it as a relations: entry with 'predicate: {predicate}' and a "
        f"'target: <target-id>' instead."
    )


@Check(section="non-materializing frontmatter fields", order=23)
def check_non_materializing_fields(ctx: ValidateContext) -> Iterator[Result]:
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
            # A non-string `kind` (list/mapping from malformed YAML) is UNHASHABLE: building
            # `(kind, key)` for the frozenset lookup would raise, and the runner
            # (runner.py:124) would convert THIS check into a single `validate.check-error`,
            # silently skipping every entity after the malformed one. A non-string kind also
            # cannot be a legit reader, so the key must still be flagged.
            if isinstance(kind, str) and (kind, key) in _LEGIT_TOP_LEVEL:
                continue
            yield Result(
                Severity.ERROR,
                path,
                None,
                (
                    f"{entity_id}: top-level '{key}:' materializes no triples and is "
                    f"silently ignored by the graph. {_remediation(key, predicate, kind)}"
                ),
                "non-materializing-field",
                None,
            )
