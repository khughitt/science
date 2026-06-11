"""Structural QA checks for proposition entities.

These checks operate on frontmatter only — no graph/trig parsing — so they run
even before ``graph build`` and give fast authoring-time feedback.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_model.reasoning import SIGN_MEANINGFUL_PREDICATES, Polarity
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
