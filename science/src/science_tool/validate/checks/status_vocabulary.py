"""Check that an entity's `status` is in its kind's declared vocabulary.

`entities.edit_entity` validates status on CLI WRITES (`_STATUS_VALUES[kind]`), but
hand-authored frontmatter is never re-checked -- and nothing in `science validate` looked
at status at all. So an out-of-vocabulary status could sit in a committed file and no
surface would say a word.

That is how natural-systems' `hypothesis:0009` came to carry `status: retired` -- and the history
has to be kept straight, because this check now fires the OTHER WAY. Back then the hypothesis
vocabulary was the VERDICT (proposed | under-investigation | partially-supported | supported |
weakened | refuted | archived), so `retired` -- a lifecycle word -- was illegal, and the author who
needed one had nowhere to put it. D5 gave `status` the lifecycle and moved the conclusion to
`verdict`, so today `retired` is LEGAL on a hypothesis and `weakened` is what this check flags.

(The author ruled 0009's true record `complete` + `refuted`: the decisive test RAN, so the work was
concluded rather than abandoned, and it rejected the organizing conjecture. Do not infer `weakened`
from the non-significant null -- five drafts of the design did, and all five were wrong.
fb-2026-07-11-005.)

The vocabulary is derived from the Kind Descriptors via `valid_statuses` -- the SAME
source `edit_entity` uses. There is deliberately NO table here: a per-kind list in this file
would be a second definition of the vocabulary, and the two would drift.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.entities import valid_statuses
from science_tool.entity_scan import iter_entity_markdown
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def _result(path: Path, message: str) -> Result:
    """Always WARN.

    This check first shipped grading severity by `layout_version >= 3`, copying
    `entity_conformance`. That was the wrong axis and it failed immediately: layout
    version says whether a project's LAYOUT is modern, not whether a KIND's status
    vocabulary is trustworthy. All five projects were v3, so the gate graded nothing, and
    472 entities errored the moment the check landed -- ~3 in 4 of them because the
    vocabulary was wrong, not the entity (`report` had no terminal state; `plan` had no
    `draft`; `pre-registration` had no `committed`, the very state our own template and
    command prescribe).

    The doctrine we already hold covers this: an UNCERTIFIED instrument cannot refute.
    A vocabulary that has never been reconciled against what the toolkit scaffolds and
    what projects author is an uncertified instrument, and it may not fail anyone's
    build. So this check advises, and only advises, until each kind's vocabulary is
    certified and its projects migrated -- at which point severity ratchets up PER KIND
    (see docs/plans/2026-07-12-status-vocabulary-certification-design.md), which is the
    axis that actually carries the meaning.
    """
    return Result(Severity.WARN, path, None, message, "status-vocabulary", None)


@Check(section="entity status vocabulary", order=20)
def check_status_vocabulary(ctx: ValidateContext) -> Iterator[Result]:
    entities_root = ctx.project_root / "entities"
    if not entities_root.is_dir():
        return

    for path in iter_entity_markdown(entities_root):
        fm = ctx.frontmatter(path)
        status = fm.get("status")
        kind = fm.get("kind")
        if not isinstance(status, str) or not status or not isinstance(kind, str) or not kind:
            continue

        try:
            allowed = valid_statuses(kind, project_root=ctx.project_root)
        except KeyError:
            # An unregistered kind is already reported as `unknown_entity_kind` by the
            # source loader. Two checks reporting one defect is worse than one, and
            # crashing validate over an entity another check owns is worse still.
            continue

        # `None` means the kind declares an OPEN status set. That is a deliberate
        # declaration, not a gap -- any status is legal and this check must stay silent.
        if allowed is None:
            continue

        if status not in allowed:
            yield _result(
                path,
                f"status {status!r} is not in the declared vocabulary for kind {kind!r} "
                f"({', '.join(sorted(allowed))}).",
            )
