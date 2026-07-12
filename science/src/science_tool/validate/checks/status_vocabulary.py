"""Check that an entity's `status` is in its kind's declared vocabulary.

`entities.edit_entity` validates status on CLI WRITES (`_STATUS_VALUES[kind]`), but
hand-authored frontmatter is never re-checked -- and nothing in `science validate` looked
at status at all. So an out-of-vocabulary status could sit in a committed file and no
surface would say a word.

That is how natural-systems' `hypothesis:0009` came to carry `status: retired`. `retired`
is not in the hypothesis vocabulary (proposed | under-investigation | partially-supported |
supported | weakened | refuted | archived) -- it is a TASK status. The author needed a
workflow word, `status` was the only field available, and the workflow word overwrote the
epistemic verdict. The hypothesis had in fact been WEAKENED (a non-significant confirmatory
null, z = -0.889), not refuted, and not retired (fb-2026-07-11-005).

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


def _severity(ctx: ValidateContext) -> Severity:
    """ERROR on v3 projects, WARN on older layouts.

    Enforcement here is RETROACTIVE: a project may already hold entities whose status was
    never in the vocabulary, and turning on a hard error would fail its whole corpus at
    once. This graded rollout is the codebase's existing answer to that (see
    `entity_conformance._severity`), so use it rather than inventing a second policy.
    """
    version = ctx.manifest.get("layout_version")
    return Severity.ERROR if isinstance(version, int) and version >= 3 else Severity.WARN


def _result(severity: Severity, path: Path, message: str) -> Result:
    return Result(severity, path, None, message, "status-vocabulary", None)


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
                _severity(ctx),
                path,
                f"status {status!r} is not in the declared vocabulary for kind {kind!r} "
                f"({', '.join(sorted(allowed))}).",
            )
