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
    inventory_parser = subparsers.add_parser("inventory")
    inventory_parser.add_argument("--plans-dir", default="docs/plans")
    inventory_parser.add_argument("--output-dir", default="docs/audits/plans-cleanup")
    inventory_parser.add_argument("--overrides", default="docs/audits/plans-cleanup/overrides.json")
    inventory_parser.add_argument("--generated-at", default=None)
    args = parser.parse_args()
    if args.command == "self-test":
        run_self_test()
        return 0
    if args.command == "inventory":
        repo_root = Path.cwd()
        generated_at = args.generated_at or utc_now_iso()
        write_thread_index(
            repo_root=repo_root,
            plans_dir=repo_root / args.plans_dir,
            output_dir=repo_root / args.output_dir,
            generated_at=generated_at,
            overrides_path=repo_root / args.overrides,
        )
        return 0
    parser.error(f"unhandled command {args.command}")
    return 2


def discover_plan_files(
    plans_dir: Path, repo_root: Path
) -> tuple[list[PlanFile], list[str]]:
    files: list[PlanFile] = []
    non_conforming: list[str] = []
    for path in sorted(plans_dir.glob("*.md")):
        try:
            files.append(parse_plan_file(path, repo_root))
        except ValueError:
            non_conforming.append(path.relative_to(repo_root).as_posix())
    files.sort(key=lambda item: item.path)
    return files, sorted(non_conforming)


def load_overrides(overrides_path: Path) -> dict[str, Any]:
    if not overrides_path.exists():
        return {"schema_version": 1, "splits": {}, "related_threads": {}}
    payload = json.loads(overrides_path.read_text())
    if payload.get("schema_version") != 1:
        raise ValueError("overrides.json schema_version must be 1")
    payload.setdefault("splits", {})
    payload.setdefault("related_threads", {})
    return payload


def apply_splits(
    grouped: dict[str, list[PlanFile]],
    splits: dict[str, Any],
) -> dict[str, list[PlanFile]]:
    result = dict(grouped)
    for original_id, children in sorted(splits.items()):
        if original_id not in result:
            continue  # the original thread's files were already removed
        present = {plan_file.path: plan_file for plan_file in result[original_id]}
        assigned: set[str] = set()
        new_groups: dict[str, list[PlanFile]] = {}
        for child in children:
            child_id = child["thread_id"]
            if child_id in result or child_id in new_groups:
                raise ValueError(f"split child thread_id collides with existing thread: {child_id}")
            unknown_files = sorted(set(child["files"]) - set(present))
            if unknown_files:
                raise ValueError(
                    f"split child {child_id} references files not in {original_id}: {unknown_files}"
                )
            members = [present[path] for path in child["files"]]
            if not members:
                continue
            assigned.update(member.path for member in members)
            new_groups[child_id] = members
        unassigned = sorted(set(present) - assigned)
        if unassigned:
            raise ValueError(f"split of {original_id} leaves files unassigned: {unassigned}")
        del result[original_id]
        result.update(new_groups)
    return result


def build_threads(
    plan_files: list[PlanFile], overrides: dict[str, Any] | None = None
) -> list[ThreadRecord]:
    overrides = overrides or {"splits": {}, "related_threads": {}}
    grouped: dict[str, list[PlanFile]] = {}
    for plan_file in plan_files:
        grouped.setdefault(plan_file.normalized_slug, []).append(plan_file)

    grouped = apply_splits(grouped, overrides.get("splits", {}))
    related = overrides.get("related_threads", {})

    threads: list[ThreadRecord] = []
    for thread_id, files in sorted(grouped.items()):
        dates = sorted(file.file_date for file in files)
        role_files: dict[str, list[str]] = {}
        raw_slugs: dict[str, str] = {}
        stripped_roles: dict[str, str | None] = {}
        for file in sorted(files, key=lambda item: item.path):
            role = file.stripped_role or "primary"
            role_files.setdefault(role, []).append(file.path)
            raw_slugs[file.path] = file.raw_slug
            stripped_roles[file.path] = file.stripped_role
        threads.append(
            ThreadRecord(
                thread_id=thread_id,
                normalized_slug=files[0].normalized_slug,
                earliest_file_date=dates[0],
                latest_file_date=dates[-1],
                files=sorted(file.path for file in files),
                role_files={key: sorted(value) for key, value in sorted(role_files.items())},
                raw_slugs=dict(sorted(raw_slugs.items())),
                stripped_roles=dict(sorted(stripped_roles.items())),
                related_threads=sorted(related.get(thread_id, [])),
            )
        )
    return threads


def write_thread_index(
    *,
    repo_root: Path,
    plans_dir: Path,
    output_dir: Path,
    generated_at: str,
    overrides_path: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_files, non_conforming = discover_plan_files(plans_dir, repo_root)
    overrides = load_overrides(overrides_path)
    threads = build_threads(plan_files, overrides)
    payload = {
        "schema_version": 1,
        "generated_at": generated_at,
        "source_dir": plans_dir.relative_to(repo_root).as_posix(),
        "thread_count": len(threads),
        "file_count": len(plan_files),
        "non_conforming_files": non_conforming,
        "threads": [asdict(thread) for thread in threads],
    }
    output_path = output_dir / "thread-index.json"
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"wrote {output_path.relative_to(repo_root)}")
    print(f"threads: {len(threads)}")
    print(f"files: {len(plan_files)}")
    if non_conforming:
        print(f"WARNING: skipped {len(non_conforming)} non-conforming files:")
        for path in non_conforming:
            print(f"  - {path}")


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
