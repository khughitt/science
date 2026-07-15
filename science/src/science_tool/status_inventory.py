"""Plan the hypothesis lifecycle/verdict migration. Writes nothing.

The mapping is design §10 rev 7, and it **inverts what every earlier revision assumed**. `phase`
is the lifecycle; `status` was only ever the verdict. `proposed` and `under-investigation` are not
states — they are the collapsed field's way of saying *"the evidence has not spoken"*, which is
exactly what an **absent verdict** already says (D1).

Why the inversion was invisible for so long: every revision reasoned about *vocabularies*, and the
D4 audit counted values one field at a time. The contradiction lived only in the **joint**
distribution — 60 of 147 files carry `status: proposed` AND `phase: active` at once, so the two
"deterministic" rules (`proposed → draft`, `active → active`) disagree on the largest cohort.
Mapping `proposed` to `draft` would have mis-migrated **88 of 147 files**.

AMBIGUITY IS ESCAPED BY AN ARTIFACT, NEVER BY SHAPE. A file whose `status` is terminal has lost its
lifecycle, its verdict AND its closure reason simultaneously, and no rule recovers them. An author
supplies all three in an adjudication file, keyed by entity id. Re-reading the *file* cannot help:
the author's edit is indistinguishable from the corruption, so the classifier would refuse it
forever — which is precisely the loop rev 1 of the plan shipped.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml
from science_model.frontmatter import split_frontmatter

from science_tool.entity_scan import iter_entity_markdown

# The four adjudication words. `status` carried these and nothing else that was ever a verdict.
_VERDICTS = frozenset({"supported", "weakened", "partially-supported", "refuted"})

# "The evidence has not spoken" == an ABSENT verdict. These are not lifecycle states.
_NO_VERDICT = frozenset({"proposed", "under-investigation"})

# An absent `phase` defaults to `active`: the template ships `phase: "active"`, `hypotheses_cli.py`
# defaults to it, and `commands/big-picture.md` says so explicitly.
_PHASE_TO_STATUS: dict[str | None, str] = {"candidate": "draft", "active": "active", None: "active"}

# A few authors wrote a lifecycle word into the collapsed `status`. It carries no verdict.
_LIFECYCLE_WORDS = frozenset({"active", "draft"})


@dataclass(frozen=True, slots=True)
class Adjudicated:
    """An author's explicit decision for a file that no rule can migrate."""

    status: str
    verdict: str | None = None
    closure_basis: str | None = None


@dataclass(frozen=True, slots=True)
class InventoryRow:
    path: Path
    entity_id: str
    status: str | None
    phase: str | None
    target_status: str | None
    target_verdict: str | None
    target_closure_basis: str | None
    ambiguity: str | None


@dataclass(frozen=True, slots=True)
class StatusInventory:
    rows: list[InventoryRow]

    @property
    def deterministic(self) -> list[InventoryRow]:
        return [row for row in self.rows if row.ambiguity is None]

    @property
    def ambiguous(self) -> list[InventoryRow]:
        return [row for row in self.rows if row.ambiguity is not None]


# THE canonical interface. The inventory, the CLI and the Task 11 migration all read this one path
# -- an adjudication an author writes must be found by every consumer, or it is not an escape hatch,
# it is a second corpus.
ADJUDICATION_PATH = Path(".science/hypothesis-lifecycle.adjudication.yaml")


def adjudication_for(project_root: Path) -> dict[str, Adjudicated]:
    """The project's canonical adjudication artifact. Absent is normal — most projects need none."""
    path = project_root / ADJUDICATION_PATH
    return load_adjudication(path) if path.is_file() else {}


def load_adjudication(path: Path) -> dict[str, Adjudicated]:
    """Read an adjudication file: ``{entity_id: {status, verdict?, closure_basis?}}``.

    A path that does not exist is an ERROR, not an empty result: silently ignoring a mistyped
    adjudication would refuse the very files the artifact was written to discharge, and report the
    refusal as if the author had never spoken. Use `adjudication_for` for the may-be-absent case.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        entity_id: Adjudicated(
            status=spec["status"],
            verdict=spec.get("verdict"),
            closure_basis=spec.get("closure_basis"),
        )
        for entity_id, spec in raw.items()
    }


def _classify(path: Path, entity_id: str, status: str | None, phase: str | None) -> InventoryRow:
    def row(**kwargs) -> InventoryRow:
        return InventoryRow(
            path=path,
            entity_id=entity_id,
            status=status,
            phase=phase,
            target_closure_basis=None,
            **kwargs,
        )

    if status is None:
        return row(
            target_status=None,
            target_verdict=None,
            ambiguity="no `status`: nothing to derive a verdict from",
        )
    if phase is not None and phase not in _PHASE_TO_STATUS:
        return row(
            target_status=None,
            target_verdict=None,
            ambiguity=f"unknown phase {phase!r} (expected candidate|active)",
        )

    lifecycle = _PHASE_TO_STATUS[phase]

    if status in _NO_VERDICT:
        return row(target_status=lifecycle, target_verdict=None, ambiguity=None)
    if status in _VERDICTS:
        return row(target_status=lifecycle, target_verdict=status, ambiguity=None)
    if status in _LIFECYCLE_WORDS and status == lifecycle:
        # The author wrote a lifecycle word into `status`, and `phase` independently agrees.
        # No verdict was ever recorded here.
        return row(target_status=lifecycle, target_verdict=None, ambiguity=None)

    # `retired` / `archived` / anything else. A terminal word in the collapsed field destroyed the
    # lifecycle, the verdict AND the closure reason at the same moment. Nothing is left to recover,
    # and inventing any of the three would be the exact fabrication this design exists to prevent.
    return row(
        target_status=None,
        target_verdict=None,
        ambiguity=(
            f"status {status!r} is terminal or unknown: the prior verdict and the closure reason "
            f"are unrecoverable. Adjudicate {entity_id} explicitly."
        ),
    )


def inventory(
    project_root: Path, *, adjudication: Mapping[str, Adjudicated] | None = None
) -> StatusInventory:
    """Classify every authored hypothesis into its target lifecycle + verdict.

    `adjudication` overrides the classifier for files it cannot decide. An entry for an id that
    does not exist raises `KeyError` — a typo must not silently adjudicate nothing and leave the
    file refused.
    """
    adjudication = dict(adjudication or {})
    rows: list[InventoryRow] = []
    seen: set[str] = set()

    for path in iter_entity_markdown(project_root / "entities"):
        frontmatter, _body = split_frontmatter(path.read_text(encoding="utf-8"))
        if frontmatter.get("kind") != "hypothesis":
            continue

        entity_id = str(frontmatter.get("id") or "")
        seen.add(entity_id)
        status = frontmatter.get("status")
        phase = frontmatter.get("phase")

        decision = adjudication.get(entity_id)
        if decision is not None:
            rows.append(
                InventoryRow(
                    path=path,
                    entity_id=entity_id,
                    status=str(status) if status is not None else None,
                    phase=str(phase) if phase is not None else None,
                    target_status=decision.status,
                    target_verdict=decision.verdict,
                    target_closure_basis=decision.closure_basis,
                    ambiguity=None,
                )
            )
            continue

        rows.append(
            _classify(
                path,
                entity_id,
                str(status) if status is not None else None,
                str(phase) if phase is not None else None,
            )
        )

    unknown = sorted(set(adjudication) - seen)
    if unknown:
        raise KeyError(
            f"adjudication names {len(unknown)} hypothesis id(s) that do not exist in "
            f"{project_root}: {', '.join(unknown)}"
        )

    return StatusInventory(rows=rows)
