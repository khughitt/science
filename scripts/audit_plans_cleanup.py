#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# ///
"""Audit helper for cleaning root docs/plans planning documents.

The script is intentionally read-mostly. It writes only audit artifacts under
docs/audits/plans-cleanup/ unless a later human-approved cleanup task moves or
deletes files with normal git commands.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DATE_PREFIX_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})-(?P<slug>.+)$")
# Ordered longest-match-first: normalize_slug returns the first suffix that
# matches, so any compound suffix (for example "implementation-plan") must
# precede its shorter form ("implementation"). Adding a new suffix that shares a
# tail with an existing one means inserting it ahead of the shorter entry.
ROLE_SUFFIXES = (
    "implementation-plan",
    "implementation",
    "manifest",
    "findings",
    "addendum",
    "design",
    "pilot",
    "spec",
    "plan",
)
VALID_STATUSES = {
    "delete_obvious",
    "superseded_delete",
    "implemented_needs_durable_docs",
    "keep_historical",
    "incomplete",
    "unclear",
}
VALID_RECOMMENDED_ACTIONS = {
    "delete",
    "create migration checkpoint",
    "keep for triage",
    "move to historical",
    "keep active",
}
VALID_ACTIONS = {
    "deleted",
    "moved_to_historical",
    "migration_checkpoint_created",
    "deferred",
}
TERMINAL_ACTIONS = {"deleted", "moved_to_historical"}


@dataclass(frozen=True)
class PlanFile:
    path: str
    file_date: str
    raw_slug: str
    normalized_slug: str
    stripped_role: str | None


@dataclass
class ThreadRecord:
    thread_id: str
    normalized_slug: str
    earliest_file_date: str
    latest_file_date: str
    files: list[str]
    role_files: dict[str, list[str]] = field(default_factory=dict)
    raw_slugs: dict[str, str] = field(default_factory=dict)
    stripped_roles: dict[str, str | None] = field(default_factory=dict)
    related_threads: list[str] = field(default_factory=list)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_plan_file(path: Path, root: Path) -> PlanFile:
    rel = path.relative_to(root).as_posix()
    stem = path.stem
    match = DATE_PREFIX_RE.match(stem)
    if not match:
        raise ValueError(f"plan filename lacks YYYY-MM-DD prefix: {rel}")
    raw_slug = match.group("slug")
    normalized_slug, stripped_role = normalize_slug(raw_slug)
    return PlanFile(
        path=rel,
        file_date=match.group("date"),
        raw_slug=raw_slug,
        normalized_slug=normalized_slug,
        stripped_role=stripped_role,
    )


def normalize_slug(raw_slug: str) -> tuple[str, str | None]:
    # Strips at most one terminal role suffix. A slug that ends in two role words
    # (for example "foo-design-plan") keeps the inner role ("foo-design"); this is
    # intentional so genuine topics ending in a role word are not over-stripped.
    for role in ROLE_SUFFIXES:
        suffix = f"-{role}"
        if raw_slug.endswith(suffix):
            return raw_slug[: -len(suffix)], role
    return raw_slug, None


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("self-test")
    args = parser.parse_args()
    if args.command == "self-test":
        run_self_test()
        return 0
    parser.error(f"unhandled command {args.command}")
    return 2


def run_self_test() -> None:
    cases = {
        "dataset-verify-access-design": ("dataset-verify-access", "design"),
        "dataset-verify-access-implementation-plan": (
            "dataset-verify-access",
            "implementation-plan",
        ),
        "schema-adoption-campaign-manifest": (
            "schema-adoption-campaign",
            "manifest",
        ),
        "unified-entity-model": ("unified-entity-model", None),
        "test-plan-design": ("test-plan", "design"),
    }
    for raw_slug, expected in cases.items():
        actual = normalize_slug(raw_slug)
        if actual != expected:
            raise AssertionError(f"{raw_slug}: expected {expected}, got {actual}")
    print(f"self-test passed ({len(cases)} cases)")


if __name__ == "__main__":
    raise SystemExit(main())
