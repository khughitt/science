"""Atomic, kind-agnostic id reservation for numeric entity kinds.

Generalizes questions.reserve_question. The reservation unit is the NUMBER:
a per-number sentinel (".NNNN.reserving") is created with O_CREAT|O_EXCL, so
two concurrent agents can never claim the NNNN even when their slugs
differ. After grabbing the sentinel the reserver re-confirms no committed
"NNNN-slug.md" already backs the number (closing the window where a reserver
holding a stale next_n re-claims a number whose sentinel was just released);
the sentinel is removed once the committed "NNNN-slug.md" backs the number
(the .md then satisfies future scans). Crash-leaked sentinels only cause
skipped numbers (gaps), never collisions — non-contiguous ids are fine.

Sentinels are hidden dotfiles; directory scanners that enumerate non-``.md``
files in an entity kind's directory must skip names starting with ``"."`` to
avoid false stray-file reports.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from science_tool.entities import (
    LOCAL_PART_WIDTH,
    EntityCommandError,
    derive_slug,
    resolve_path_policy,
    validate_slug,
)

_NUMERIC_SCAN_RE = re.compile(r"^(?:[A-Za-z])?(\d+)")          # committed NNNN-slug.md (tolerates legacy hNN)
_SENTINEL_RE = re.compile(r"^\.(\d+)\.reserving$")            # in-flight number claim


def _number_is_committed(directory: Path, number: int) -> bool:
    """True iff a committed ``.md`` already backs ``number``."""
    for entry in directory.iterdir():
        if entry.suffix != ".md":
            continue
        match = _NUMERIC_SCAN_RE.match(entry.stem)
        if match is not None and int(match.group(1)) == number:
            return True
    return False


@dataclass(frozen=True)
class Reservation:
    entity_id: str
    path: Path


def _max_number(directory: Path) -> int:
    """Highest number backed by either a committed .md OR an in-flight sentinel,
    so concurrent reservers see each other's claims and never reuse a number."""
    max_n = 0
    if directory.is_dir():
        for entry in directory.iterdir():
            if entry.suffix == ".md":
                match = _NUMERIC_SCAN_RE.match(entry.stem)
            else:
                match = _SENTINEL_RE.match(entry.name)
            if match is not None:
                max_n = max(max_n, int(match.group(1)))
    return max_n


def reserve_number_in_dir(
    directory: Path,
    slug_value: str,
    *,
    stub: str = "",
    label: str = "entity",
    max_attempts: int = 100,
) -> tuple[int, str, Path]:
    """Atomically claim the next number in ``directory`` and commit its .md.

    Returns ``(number, local_part, path)``. The number — not the slugged
    filename — is the lock unit (see the module docstring). This is the
    shared core behind both :func:`reserve_entity` and question reservation.
    """
    directory.mkdir(parents=True, exist_ok=True)
    for _ in range(max_attempts):
        next_n = _max_number(directory) + 1
        # Atomically claim the NUMBER (slug-independent) — the only correct lock unit.
        sentinel = directory / f".{next_n:0{LOCAL_PART_WIDTH}d}.reserving"
        try:
            os.close(os.open(sentinel, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644))
        except FileExistsError:
            continue  # another reserver owns this number; recompute (will now see the sentinel)
        # Re-confirm under the held sentinel: a competitor that committed and
        # released this number between our stale scan and our claim must win.
        if _number_is_committed(directory, next_n):
            sentinel.unlink(missing_ok=True)
            continue
        local_part = f"{next_n:0{LOCAL_PART_WIDTH}d}-{slug_value}"
        path = directory / f"{local_part}.md"
        try:
            with open(path, "x", encoding="utf-8") as handle:  # "x" == O_CREAT|O_EXCL belt-and-suspenders
                handle.write(stub)
        finally:
            sentinel.unlink(missing_ok=True)  # committed .md now backs the number
        return next_n, local_part, path

    raise EntityCommandError(f"could not reserve a {label} number after {max_attempts} attempts")


def reserve_entity(
    project_root: Path,
    kind: str,
    title: str,
    *,
    slug: str | None = None,
    stub: str = "",
    max_attempts: int = 100,
) -> Reservation:
    policy = resolve_path_policy(kind)
    if policy.strategy != "numeric":
        raise EntityCommandError(f"reserve_entity supports numeric kinds only; {kind} is {policy.strategy}")
    directory = project_root / policy.root
    slug_value = validate_slug(slug) if slug is not None else derive_slug(title)
    _, local_part, path = reserve_number_in_dir(
        directory, slug_value, stub=stub, label=kind, max_attempts=max_attempts
    )
    return Reservation(entity_id=f"{kind}:{local_part}", path=path)
