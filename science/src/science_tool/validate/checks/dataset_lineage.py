"""Dataset sub-cohort lineage checks: parent_dataset referential integrity + acyclicity.

A dataset's ``parent_dataset`` field declares it is a sub-cohort of a larger dataset
(e.g. ``dataset:ukb-ppp`` ⊂ ``dataset:uk-biobank``). This check enforces:

1. The reference must resolve — either locally or in the commons.
2. The lineage chain must be acyclic.
3. A ``member_of`` collection member must not itself be used as a lineage parent
   (``member_of`` is a row-level membership relation, not a sub-cohort relation).

Non-local parents are resolved against the commons via the shared helper from
``reference_collections``. When the commons is unavailable, the check emits INFO
(never a false ERROR) to match the ``reference-collection.commons-unavailable``
precedent.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from science_tool.validate._helpers import dataset_frontmatters
from science_tool.validate.checks import Check
from science_tool.validate.checks.reference_collections import _commons_has_dataset
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def _result(severity: Severity, path: str | None, message: str, rule: str) -> Result:
    return Result(severity, Path(path) if path else None, None, message, rule, None)


def _err(path: str | None, message: str, rule: str) -> Result:
    return _result(Severity.ERROR, path, message, rule)


def evaluate_dataset_lineage(
    datasets: list[dict[str, Any]],
    *,
    commons_cache: dict[str, bool | None] | None = None,
) -> Iterator[Result]:
    """Pure core: ``datasets`` are raw frontmatter dicts (each with ``_path``).

    ``commons_cache`` is injectable for unit tests so they never hit the real
    commons. Keys map a dataset id to: True (present), False (commons available
    but id absent), None (commons unavailable/unconfigured).
    """
    if commons_cache is None:
        commons_cache = {}

    by_id = {d.get("id"): d for d in datasets if isinstance(d.get("id"), str)}

    # Collect ids of datasets that are member_of collection members — these must
    # not be used as sub-cohort parents because they represent individual rows,
    # not cohorts.
    member_of_ids: set[str] = {
        d["id"]
        for d in datasets
        if isinstance(d.get("derivation"), dict) and d["derivation"].get("kind") == "member_of"
        and isinstance(d.get("id"), str)
    }

    # --- Pass 1: per-dataset referential integrity checks ---
    for d in datasets:
        parent = d.get("parent_dataset")
        if not parent:
            continue
        path = d.get("_path")
        ident = d.get("id", "?")

        if not isinstance(parent, str) or not parent.startswith("dataset:"):
            yield _err(
                path,
                f"{ident}: parent_dataset must be a 'dataset:' reference, got {parent!r}",
                "dataset.lineage.ref",
            )
            continue

        # A member_of row must not be used as a sub-cohort parent.
        if parent in member_of_ids:
            yield _err(
                path,
                f"{ident}: parent_dataset {parent!r} is a member_of collection member, "
                f"not a sub-cohort parent",
                "dataset.lineage.member-parent",
            )

        if parent in by_id:
            continue  # resolved locally — no further lookup needed

        # Not local — check the commons (cache-first for unit-test determinism).
        present = _commons_has_dataset(parent, commons_cache)
        if present is False:
            yield _err(
                path,
                f"{ident}: parent_dataset {parent!r} does not resolve to a dataset entity "
                f"(not in project or commons)",
                "dataset.lineage.unresolved",
            )
        elif present is None:
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: parent_dataset {parent!r} is non-local and the commons is "
                f"unavailable; cannot verify",
                "dataset.lineage.commons-unavailable",
            )
        # present is True → resolved in commons, no defect

    # --- Pass 2: cycle detection over the parent_dataset chain ---
    for start in by_id:
        seen: set[str] = set()
        cur = start
        while cur in by_id and by_id[cur].get("parent_dataset"):
            cur = by_id[cur]["parent_dataset"]
            if cur in seen or cur == start:
                yield _err(
                    by_id[start].get("_path"),
                    f"{start}: parent_dataset chain forms a cycle",
                    "dataset.lineage.cycle",
                )
                break
            seen.add(cur)


@Check(section="dataset lineage", order=53)
def check_dataset_lineage(ctx: ValidateContext) -> Iterator[Result]:
    yield from evaluate_dataset_lineage(dataset_frontmatters(ctx))
