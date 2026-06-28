# Plans Cleanup First Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a resumable audit workflow for `docs/plans/`, run the first March/April-focused review batch, and perform only verified obvious cleanup actions.

**Architecture:** Add one standalone audit script at the repo root to generate deterministic thread inventory and validate append-only review/action logs. Keep all generated audit state under `docs/audits/plans-cleanup/`. Use subagents only for read-only thread review; the main agent reconciles findings and performs deletions or historical moves.

**Tech Stack:** Python 3.11 standard library, PEP 723 `uv run` script execution, JSON/JSONL audit artifacts, git for versioned cleanup actions.

---

## File Structure

- Create `scripts/audit_plans_cleanup.py`: standalone audit helper with `self-test`, `inventory`, `batch`, `validate`, and `pending` subcommands.
- Create `docs/audits/plans-cleanup/thread-index.json`: generated thread inventory for root `docs/plans/`.
- Create `docs/audits/plans-cleanup/overrides.json`: hand-authored thread splits and related-thread links reapplied by `inventory` on every regeneration.
- Create `docs/audits/plans-cleanup/reviews.jsonl`: append-only review log keyed by `thread_id`.
- Create `docs/audits/plans-cleanup/actions.jsonl`: append-only main-agent action log.
- Create `docs/audits/plans-cleanup/batches/`: generated batch assignment Markdown files for subagent review.
- Create `docs/plans/historical/` only when a reviewed `keep_historical` action is performed.

## Task 1: Create The Audit Script Skeleton And Self-Test Harness

**Files:**
- Create: `scripts/audit_plans_cleanup.py`

- [ ] **Step 1: Create the script with CLI skeleton**

Create `scripts/audit_plans_cleanup.py` with this structure:

```python
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
```

- [ ] **Step 2: Run the self-test**

Run:

```bash
rtk uv run scripts/audit_plans_cleanup.py self-test
```

Expected output:

```text
self-test passed (5 cases)
```

- [ ] **Step 3: Commit the skeleton**

```bash
rtk git add scripts/audit_plans_cleanup.py
rtk git commit -m "chore: add plans cleanup audit helper skeleton"
```

## Task 2: Implement Deterministic Thread Inventory

**Files:**
- Modify: `scripts/audit_plans_cleanup.py`
- Create: `docs/audits/plans-cleanup/thread-index.json`

- [ ] **Step 1: Extend the CLI arguments**

Add these arguments:

```python
    inventory_parser = subparsers.add_parser("inventory")
    inventory_parser.add_argument("--plans-dir", default="docs/plans")
    inventory_parser.add_argument("--output-dir", default="docs/audits/plans-cleanup")
    inventory_parser.add_argument("--overrides", default="docs/audits/plans-cleanup/overrides.json")
    inventory_parser.add_argument("--generated-at", default=None)
```

Insert this branch in `main()` immediately after the `self-test` branch:

```python
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
```

- [ ] **Step 2: Add inventory functions**

Add these functions:

```python
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
```

- [ ] **Step 3: Run the deterministic inventory command**

Run:

```bash
rtk uv run scripts/audit_plans_cleanup.py inventory --generated-at 2026-06-27T00:00:00+00:00
```

Expected output includes:

```text
wrote docs/audits/plans-cleanup/thread-index.json
threads:
files:
```

The exact counts depend on the current repository state. Confirm the output has
one line beginning with `threads:` and one line beginning with `files:`.

- [ ] **Step 4: Inspect known grouping cases**

Run:

```bash
rtk proxy python -m json.tool docs/audits/plans-cleanup/thread-index.json > /tmp/plans-thread-index.pretty.json
rtk rg -n '"thread_id": "dataset-verify-access"|"thread_id": "schema-adoption-campaign"|"thread_id": "unified-entity-model"' /tmp/plans-thread-index.pretty.json
```

Expected: all three thread ids are present. `dataset-verify-access` includes both design and implementation-plan role files if both source files exist.

- [ ] **Step 5: Create the starter overrides file and commit inventory support**

The inventory works without `overrides.json` (a missing file is treated as
empty), but create a committed starter so the file is discoverable and ready for
the first reconciliation split:

```bash
rtk proxy tee docs/audits/plans-cleanup/overrides.json >/dev/null <<'JSON'
{
  "schema_version": 1,
  "splits": {},
  "related_threads": {}
}
JSON
```

```bash
rtk git add scripts/audit_plans_cleanup.py docs/audits/plans-cleanup/thread-index.json docs/audits/plans-cleanup/overrides.json
rtk git commit -m "chore: inventory plans cleanup threads"
```

## Task 3: Add Batch Generation And Log Validation

**Files:**
- Modify: `scripts/audit_plans_cleanup.py`
- Create: `docs/audits/plans-cleanup/batches/march-april-001.md`
- Create: `docs/audits/plans-cleanup/reviews.jsonl`
- Create: `docs/audits/plans-cleanup/actions.jsonl`
- Create: `docs/audits/plans-cleanup/pending.md`

- [ ] **Step 1: Add batch and validate CLI arguments**

Update the imports:

```python
from tempfile import TemporaryDirectory
```

Add these parser definitions:

```python
    batch_parser = subparsers.add_parser("batch")
    batch_parser.add_argument("--index", default="docs/audits/plans-cleanup/thread-index.json")
    batch_parser.add_argument("--output", required=True)
    batch_parser.add_argument("--latest-before", required=True)
    batch_parser.add_argument("--limit", type=int, default=12)
    batch_parser.add_argument("--skip-reviewed", default="docs/audits/plans-cleanup/reviews.jsonl")

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--index", default="docs/audits/plans-cleanup/thread-index.json")
    validate_parser.add_argument("--reviews", default="docs/audits/plans-cleanup/reviews.jsonl")
    validate_parser.add_argument("--actions", default="docs/audits/plans-cleanup/actions.jsonl")
    validate_parser.add_argument("--overrides", default="docs/audits/plans-cleanup/overrides.json")

    pending_parser = subparsers.add_parser("pending")
    pending_parser.add_argument("--index", default="docs/audits/plans-cleanup/thread-index.json")
    pending_parser.add_argument("--reviews", default="docs/audits/plans-cleanup/reviews.jsonl")
    pending_parser.add_argument("--actions", default="docs/audits/plans-cleanup/actions.jsonl")
    pending_parser.add_argument("--output", default="docs/audits/plans-cleanup/pending.md")
```

Insert these branches in `main()` immediately after the `inventory` branch:

```python
    if args.command == "batch":
        repo_root = Path.cwd()
        write_batch_file(
            repo_root=repo_root,
            index_path=repo_root / args.index,
            output_path=repo_root / args.output,
            latest_before=args.latest_before,
            limit=args.limit,
            reviews_path=repo_root / args.skip_reviewed,
        )
        return 0
    if args.command == "validate":
        repo_root = Path.cwd()
        validate_logs(
            index_path=repo_root / args.index,
            reviews_path=repo_root / args.reviews,
            actions_path=repo_root / args.actions,
            overrides_path=repo_root / args.overrides,
        )
        return 0
    if args.command == "pending":
        repo_root = Path.cwd()
        write_pending_report(
            repo_root=repo_root,
            index_path=repo_root / args.index,
            reviews_path=repo_root / args.reviews,
            actions_path=repo_root / args.actions,
            output_path=repo_root / args.output,
        )
        return 0
```

- [ ] **Step 2: Add JSONL helpers and validators**

Add these helpers:

```python
REQUIRED_REVIEW_KEYS = {
    "thread_id",
    "files",
    "topic",
    "status",
    "superseded_by",
    "supersedes",
    "related_threads",
    "evidence",
    "remaining_gaps",
    "durable_doc_candidate",
    "recommended_action",
    "review_notes",
}
PENDING_REVIEW_STATUSES = {
    "implemented_needs_durable_docs",
    "incomplete",
    "unclear",
}
PENDING_ACTIONS = {"deferred", "migration_checkpoint_created"}
COHERENT_ACTIONS = {
    "delete_obvious": {"delete"},
    "superseded_delete": {"delete"},
    "implemented_needs_durable_docs": {"create migration checkpoint"},
    "keep_historical": {"move to historical"},
    "incomplete": {"keep for triage", "keep active"},
    "unclear": {"keep for triage", "keep active"},
}
ACTIONS_ALLOWED_BY_STATUS = {
    "delete_obvious": {"deleted", "deferred"},
    "superseded_delete": {"deleted", "deferred"},
    "implemented_needs_durable_docs": {
        "migration_checkpoint_created",
        "deferred",
    },
    "keep_historical": {"moved_to_historical", "deferred"},
    "incomplete": {"deferred"},
    "unclear": {"deferred"},
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"{path}:{line_number}: expected object")
        records.append(record)
    return records


def load_index(index_path: Path) -> dict[str, Any]:
    payload = json.loads(index_path.read_text())
    if payload.get("schema_version") != 1:
        raise ValueError("thread-index.json schema_version must be 1")
    return payload


def reviewed_thread_ids(reviews_path: Path) -> set[str]:
    return {str(record["thread_id"]) for record in read_jsonl(reviews_path) if "thread_id" in record}


def validate_logs(
    *,
    index_path: Path,
    reviews_path: Path,
    actions_path: Path,
    overrides_path: Path | None = None,
) -> None:
    payload = load_index(index_path)
    known_threads = {thread["thread_id"] for thread in payload["threads"]}
    reviews = read_jsonl(reviews_path)
    actions = read_jsonl(actions_path)
    latest_reviews = latest_records_by_thread(reviews)
    terminal_actioned_threads = {
        str(record["thread_id"])
        for record in actions
        if record.get("action") in TERMINAL_ACTIONS and "thread_id" in record
    }
    split_origin_threads: set[str] = set()
    if overrides_path is not None:
        split_origin_threads = set(load_overrides(overrides_path).get("splits", {}))
    allowed_threads = known_threads | terminal_actioned_threads | split_origin_threads
    for record in reviews:
        missing = REQUIRED_REVIEW_KEYS - set(record)
        if missing:
            raise ValueError(f"review {record.get('thread_id', 'missing-thread-id')} missing {sorted(missing)}")
        if record["thread_id"] not in allowed_threads:
            raise ValueError(f"review references unrecognized thread_id {record['thread_id']}")
        if record["status"] not in VALID_STATUSES:
            raise ValueError(f"review {record['thread_id']} has invalid status {record['status']}")
        if record["recommended_action"] not in VALID_RECOMMENDED_ACTIONS:
            raise ValueError(
                f"review {record['thread_id']} has invalid recommended_action {record['recommended_action']}"
            )
        if record["recommended_action"] not in COHERENT_ACTIONS[record["status"]]:
            raise ValueError(
                f"review {record['thread_id']} status {record['status']} is incoherent "
                f"with recommended_action {record['recommended_action']}"
            )
        if record["status"] == "superseded_delete" and not record["superseded_by"]:
            raise ValueError(f"review {record['thread_id']} superseded_delete lacks superseded_by")
    for record in actions:
        if "thread_id" not in record or "action" not in record:
            raise ValueError(f"action record missing thread_id/action: {record}")
        if record["action"] not in VALID_ACTIONS:
            raise ValueError(f"action {record['thread_id']} has invalid action {record['action']}")
        if record["thread_id"] not in allowed_threads:
            raise ValueError(f"action references unrecognized thread_id {record['thread_id']}")
        latest_review = latest_reviews.get(record["thread_id"])
        if latest_review is None:
            raise ValueError(f"action {record['thread_id']} lacks a review record")
        allowed_actions = ACTIONS_ALLOWED_BY_STATUS[latest_review["status"]]
        if record["action"] not in allowed_actions:
            raise ValueError(
                f"action {record['thread_id']} action {record['action']} is not allowed "
                f"for latest review status {latest_review['status']}"
            )
        action_files = record.get("files")
        if not isinstance(action_files, list):
            raise ValueError(f"action {record['thread_id']} files must be a list")
        review_files = set(latest_review["files"])
        extra_files = sorted(str(path) for path in action_files if path not in review_files)
        if extra_files:
            raise ValueError(
                f"action {record['thread_id']} references files outside latest review: {extra_files}"
            )
    print("audit logs valid")
```

- [ ] **Step 3: Add batch writer**

Add:

```python
def write_batch_file(
    *,
    repo_root: Path,
    index_path: Path,
    output_path: Path,
    latest_before: str,
    limit: int,
    reviews_path: Path,
) -> None:
    payload = load_index(index_path)
    already_reviewed = reviewed_thread_ids(reviews_path)
    candidates = [
        thread
        for thread in payload["threads"]
        if thread["latest_file_date"] < latest_before
        and thread["thread_id"] not in already_reviewed
    ]
    candidates = sorted(
        candidates,
        key=lambda thread: (thread["latest_file_date"], thread["thread_id"]),
    )[:limit]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Plans Cleanup Review Batch",
        "",
        f"- Source index: `{index_path.relative_to(repo_root).as_posix()}`",
        f"- Latest file date before: `{latest_before}`",
        f"- Thread count: `{len(candidates)}`",
        "",
        "## Review Contract",
        "",
        "Review each thread read-only. Verify implementation reality from code and durable docs.",
        "Return one JSON object per thread with the Review Record fields from the audit design.",
        "",
    ]
    for thread in candidates:
        lines.extend(
            [
                f"## {thread['thread_id']}",
                "",
                f"- latest_file_date: `{thread['latest_file_date']}`",
                f"- earliest_file_date: `{thread['earliest_file_date']}`",
                "- files:",
                *[f"  - `{path}`" for path in thread["files"]],
                "",
            ]
        )
    output_path.write_text("\n".join(lines) + "\n")
    print(f"wrote {output_path.relative_to(repo_root)}")
    print(f"threads: {len(candidates)}")
```

- [ ] **Step 4: Add pending report writer**

Add:

```python
def latest_records_by_thread(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        thread_id = record.get("thread_id")
        if isinstance(thread_id, str):
            latest[thread_id] = record
    return latest


def records_by_thread(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        thread_id = record.get("thread_id")
        if isinstance(thread_id, str):
            grouped.setdefault(thread_id, []).append(record)
    return grouped


def write_pending_report(
    *,
    repo_root: Path,
    index_path: Path,
    reviews_path: Path,
    actions_path: Path,
    output_path: Path,
) -> None:
    payload = load_index(index_path)
    current_threads = {thread["thread_id"]: thread for thread in payload["threads"]}
    latest_reviews = latest_records_by_thread(read_jsonl(reviews_path))
    actions_by_thread = records_by_thread(read_jsonl(actions_path))
    pending: list[tuple[str, dict[str, Any], dict[str, Any] | None, list[dict[str, Any]]]] = []
    for thread_id, review in sorted(latest_reviews.items()):
        thread_actions = actions_by_thread.get(thread_id, [])
        pending_actions = [
            action for action in thread_actions if action.get("action") in PENDING_ACTIONS
        ]
        has_terminal_action = any(
            action.get("action") in TERMINAL_ACTIONS for action in thread_actions
        )
        if has_terminal_action:
            continue
        if review["status"] in PENDING_REVIEW_STATUSES or pending_actions:
            pending.append((thread_id, review, current_threads.get(thread_id), thread_actions))

    lines = [
        "# Plans Cleanup Pending Triage",
        "",
        f"- Source index: `{index_path.relative_to(repo_root).as_posix()}`",
        f"- Pending thread count: `{len(pending)}`",
        "",
    ]
    for thread_id, review, current_thread, thread_actions in pending:
        action_names = ", ".join(action["action"] for action in thread_actions) or "none"
        lines.extend(
            [
                f"## {thread_id}",
                "",
                f"- status: `{review['status']}`",
                f"- recommended_action: `{review['recommended_action']}`",
                f"- actions: `{action_names}`",
                "- files:",
            ]
        )
        files = current_thread["files"] if current_thread else review["files"]
        lines.extend(f"  - `{path}`" for path in files)
        pending_actions = [
            action for action in thread_actions if action.get("action") in PENDING_ACTIONS
        ]
        if pending_actions:
            lines.append("- pending_actions:")
            for action in pending_actions:
                lines.append(f"  - `{action['action']}`: {action.get('reason', 'no reason recorded')}")
                for path in action.get("files", []):
                    lines.append(f"    - `{path}`")
        if review.get("remaining_gaps"):
            lines.append("- remaining_gaps:")
            lines.extend(f"  - {gap}" for gap in review["remaining_gaps"])
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n")
    print(f"wrote {output_path.relative_to(repo_root)}")
    print(f"pending: {len(pending)}")
```

- [ ] **Step 5: Extend self-test coverage**

Replace `run_self_test()` with:

```python
def run_self_test() -> None:
    test_normalize_slug()
    test_apply_overrides_splits_thread()
    test_batch_selection_uses_latest_before()
    test_validate_allows_deferred_then_terminal_removed_thread()
    test_validate_rejects_incoherent_action()
    test_validate_rejects_action_disallowed_by_latest_status()
    test_validate_rejects_action_files_outside_review()
    test_pending_report_terminal_action_resolves_prior_pending()
    print("self-test passed (8 groups)")


def test_normalize_slug() -> None:
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


def test_apply_overrides_splits_thread() -> None:
    files = [
        PlanFile(
            path="docs/plans/2026-03-01-shared-slug-design.md",
            file_date="2026-03-01",
            raw_slug="shared-slug-design",
            normalized_slug="shared-slug",
            stripped_role="design",
        ),
        PlanFile(
            path="docs/plans/2026-06-01-shared-slug-design.md",
            file_date="2026-06-01",
            raw_slug="shared-slug-design",
            normalized_slug="shared-slug",
            stripped_role="design",
        ),
    ]
    overrides = {
        "splits": {
            "shared-slug": [
                {"thread_id": "shared-slug-march", "files": [files[0].path]},
                {"thread_id": "shared-slug-june", "files": [files[1].path]},
            ]
        },
        "related_threads": {"shared-slug-march": ["shared-slug-june"]},
    }
    threads = {thread.thread_id: thread for thread in build_threads(files, overrides)}
    if set(threads) != {"shared-slug-march", "shared-slug-june"}:
        raise AssertionError(f"unexpected thread ids: {sorted(threads)}")
    if threads["shared-slug-march"].latest_file_date != "2026-03-01":
        raise AssertionError("march child has wrong latest_file_date")
    if threads["shared-slug-march"].related_threads != ["shared-slug-june"]:
        raise AssertionError("related_threads not applied")
    try:
        build_threads(
            files,
            {"splits": {"shared-slug": [{"thread_id": "only-march", "files": [files[0].path]}]}},
        )
    except ValueError:
        pass
    else:
        raise AssertionError("expected unassigned-file split to fail")
    try:
        build_threads(
            files,
            {
                "splits": {
                    "shared-slug": [
                        {
                            "thread_id": "unknown-file",
                            "files": ["docs/plans/2026-03-01-missing.md"],
                        },
                        {"thread_id": "known-file", "files": [files[1].path]},
                    ]
                }
            },
        )
    except ValueError:
        pass
    else:
        raise AssertionError("expected unknown-file split to fail")


def test_batch_selection_uses_latest_before() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        index_path = root / "thread-index.json"
        reviews_path = root / "reviews.jsonl"
        output_path = root / "batch.md"
        index_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "threads": [
                        {
                            "thread_id": "april-thread",
                            "earliest_file_date": "2026-04-01",
                            "latest_file_date": "2026-04-30",
                            "files": ["docs/plans/2026-04-01-april-thread.md"],
                        },
                        {
                            "thread_id": "may-thread",
                            "earliest_file_date": "2026-05-01",
                            "latest_file_date": "2026-05-01",
                            "files": ["docs/plans/2026-05-01-may-thread.md"],
                        },
                    ],
                }
            )
            + "\n"
        )
        reviews_path.write_text("")
        write_batch_file(
            repo_root=root,
            index_path=index_path,
            output_path=output_path,
            latest_before="2026-05-01",
            limit=12,
            reviews_path=reviews_path,
        )
        text = output_path.read_text()
        if "april-thread" not in text:
            raise AssertionError("April thread should be selected")
        if "may-thread" in text:
            raise AssertionError("May thread should be excluded")


def test_validate_allows_deferred_then_terminal_removed_thread() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        index_path = root / "thread-index.json"
        reviews_path = root / "reviews.jsonl"
        actions_path = root / "actions.jsonl"
        index_path.write_text(json.dumps({"schema_version": 1, "threads": []}) + "\n")
        reviews_path.write_text(
            json.dumps(
                {
                    "thread_id": "removed-thread",
                    "files": ["docs/plans/2026-03-01-removed-thread.md"],
                    "topic": "Removed thread",
                    "status": "delete_obvious",
                    "superseded_by": [],
                    "supersedes": [],
                    "related_threads": [],
                    "evidence": ["Verified as completed."],
                    "remaining_gaps": [],
                    "durable_doc_candidate": None,
                    "recommended_action": "delete",
                    "review_notes": "Terminal action test.",
                }
            )
            + "\n"
        )
        actions_path.write_text(
            json.dumps(
                {
                    "thread_id": "removed-thread",
                    "action": "deferred",
                    "files": ["docs/plans/2026-03-01-removed-thread.md"],
                    "reason": "first-pass triage deferred",
                    "commit": None,
                }
            )
            + "\n"
            + json.dumps(
                {
                    "thread_id": "removed-thread",
                    "action": "deleted",
                    "files": ["docs/plans/2026-03-01-removed-thread.md"],
                    "reason": "self-test terminal action",
                    "commit": None,
                }
            )
            + "\n"
        )
        validate_logs(
            index_path=index_path,
            reviews_path=reviews_path,
            actions_path=actions_path,
        )


def test_validate_rejects_incoherent_action() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        index_path = root / "thread-index.json"
        reviews_path = root / "reviews.jsonl"
        actions_path = root / "actions.jsonl"
        index_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "threads": [
                        {
                            "thread_id": "incoherent-thread",
                            "earliest_file_date": "2026-03-01",
                            "latest_file_date": "2026-03-01",
                            "files": ["docs/plans/2026-03-01-incoherent-thread.md"],
                        }
                    ],
                }
            )
            + "\n"
        )
        reviews_path.write_text(
            json.dumps(
                {
                    "thread_id": "incoherent-thread",
                    "files": ["docs/plans/2026-03-01-incoherent-thread.md"],
                    "topic": "Incoherent",
                    "status": "delete_obvious",
                    "superseded_by": [],
                    "supersedes": [],
                    "related_threads": [],
                    "evidence": ["Verified complete."],
                    "remaining_gaps": [],
                    "durable_doc_candidate": None,
                    "recommended_action": "keep active",
                    "review_notes": "Coherence test.",
                }
            )
            + "\n"
        )
        actions_path.write_text("")
        try:
            validate_logs(
                index_path=index_path,
                reviews_path=reviews_path,
                actions_path=actions_path,
            )
        except ValueError:
            return
        raise AssertionError("expected incoherent recommended_action to fail")


def test_validate_rejects_action_disallowed_by_latest_status() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        index_path = root / "thread-index.json"
        reviews_path = root / "reviews.jsonl"
        actions_path = root / "actions.jsonl"
        file_path = "docs/plans/2026-03-01-incomplete-thread.md"
        index_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "threads": [
                        {
                            "thread_id": "incomplete-thread",
                            "earliest_file_date": "2026-03-01",
                            "latest_file_date": "2026-03-01",
                            "files": [file_path],
                        }
                    ],
                }
            )
            + "\n"
        )
        reviews_path.write_text(
            json.dumps(
                {
                    "thread_id": "incomplete-thread",
                    "files": [file_path],
                    "topic": "Incomplete",
                    "status": "incomplete",
                    "superseded_by": [],
                    "supersedes": [],
                    "related_threads": [],
                    "evidence": ["Still missing implementation."],
                    "remaining_gaps": ["Complete the implementation."],
                    "durable_doc_candidate": None,
                    "recommended_action": "keep for triage",
                    "review_notes": "Action coherence test.",
                }
            )
            + "\n"
        )
        actions_path.write_text(
            json.dumps(
                {
                    "thread_id": "incomplete-thread",
                    "action": "deleted",
                    "files": [file_path],
                    "reason": "should fail",
                    "commit": None,
                }
            )
            + "\n"
        )
        try:
            validate_logs(
                index_path=index_path,
                reviews_path=reviews_path,
                actions_path=actions_path,
            )
        except ValueError:
            return
        raise AssertionError("expected deleted action for incomplete review to fail")


def test_validate_rejects_action_files_outside_review() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        index_path = root / "thread-index.json"
        reviews_path = root / "reviews.jsonl"
        actions_path = root / "actions.jsonl"
        reviewed_file = "docs/plans/2026-03-01-delete-thread.md"
        extra_file = "docs/plans/2026-03-01-other-thread.md"
        index_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "threads": [
                        {
                            "thread_id": "delete-thread",
                            "earliest_file_date": "2026-03-01",
                            "latest_file_date": "2026-03-01",
                            "files": [reviewed_file],
                        }
                    ],
                }
            )
            + "\n"
        )
        reviews_path.write_text(
            json.dumps(
                {
                    "thread_id": "delete-thread",
                    "files": [reviewed_file],
                    "topic": "Delete",
                    "status": "delete_obvious",
                    "superseded_by": [],
                    "supersedes": [],
                    "related_threads": [],
                    "evidence": ["Verified complete."],
                    "remaining_gaps": [],
                    "durable_doc_candidate": None,
                    "recommended_action": "delete",
                    "review_notes": "File subset test.",
                }
            )
            + "\n"
        )
        actions_path.write_text(
            json.dumps(
                {
                    "thread_id": "delete-thread",
                    "action": "deleted",
                    "files": [reviewed_file, extra_file],
                    "reason": "should fail",
                    "commit": None,
                }
            )
            + "\n"
        )
        try:
            validate_logs(
                index_path=index_path,
                reviews_path=reviews_path,
                actions_path=actions_path,
            )
        except ValueError:
            return
        raise AssertionError("expected action with files outside review to fail")


def test_pending_report_terminal_action_resolves_prior_pending() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        index_path = root / "thread-index.json"
        reviews_path = root / "reviews.jsonl"
        actions_path = root / "actions.jsonl"
        output_path = root / "pending.md"
        file_path = "docs/plans/2026-03-01-resolved-thread.md"
        index_path.write_text(json.dumps({"schema_version": 1, "threads": []}) + "\n")
        reviews_path.write_text(
            json.dumps(
                {
                    "thread_id": "resolved-thread",
                    "files": [file_path],
                    "topic": "Resolved",
                    "status": "delete_obvious",
                    "superseded_by": [],
                    "supersedes": [],
                    "related_threads": [],
                    "evidence": ["Verified complete."],
                    "remaining_gaps": [],
                    "durable_doc_candidate": None,
                    "recommended_action": "delete",
                    "review_notes": "Pending resolution test.",
                }
            )
            + "\n"
        )
        actions_path.write_text(
            json.dumps(
                {
                    "thread_id": "resolved-thread",
                    "action": "deferred",
                    "files": [file_path],
                    "reason": "first pass deferred",
                    "commit": None,
                }
            )
            + "\n"
            + json.dumps(
                {
                    "thread_id": "resolved-thread",
                    "action": "deleted",
                    "files": [file_path],
                    "reason": "resolved",
                    "commit": None,
                }
            )
            + "\n"
        )
        write_pending_report(
            repo_root=root,
            index_path=index_path,
            reviews_path=reviews_path,
            actions_path=actions_path,
            output_path=output_path,
        )
        text = output_path.read_text()
        if "resolved-thread" in text:
            raise AssertionError("terminal action should remove thread from pending report")
```

- [ ] **Step 6: Initialize append-only logs**

Run:

```bash
rtk proxy touch docs/audits/plans-cleanup/reviews.jsonl docs/audits/plans-cleanup/actions.jsonl
```

- [ ] **Step 7: Run the expanded self-test**

Run:

```bash
rtk uv run scripts/audit_plans_cleanup.py self-test
```

Expected output includes:

```text
self-test passed (8 groups)
```

- [ ] **Step 8: Generate the first March/April batch**

Run:

```bash
rtk uv run scripts/audit_plans_cleanup.py batch --latest-before 2026-05-01 --limit 12 --output docs/audits/plans-cleanup/batches/march-april-001.md
```

Expected output:

```text
wrote docs/audits/plans-cleanup/batches/march-april-001.md
threads: 12
```

- [ ] **Step 9: Validate empty logs against the inventory**

Run:

```bash
rtk uv run scripts/audit_plans_cleanup.py validate
```

Expected output:

```text
audit logs valid
```

- [ ] **Step 10: Generate the initial pending report**

Run:

```bash
rtk uv run scripts/audit_plans_cleanup.py pending
```

Expected output:

```text
wrote docs/audits/plans-cleanup/pending.md
pending: 0
```

- [ ] **Step 11: Commit batch tooling and generated first batch**

```bash
rtk git add scripts/audit_plans_cleanup.py docs/audits/plans-cleanup/thread-index.json docs/audits/plans-cleanup/reviews.jsonl docs/audits/plans-cleanup/actions.jsonl docs/audits/plans-cleanup/pending.md docs/audits/plans-cleanup/batches/march-april-001.md
rtk git commit -m "chore: prepare first plans cleanup audit batch"
```

## Task 4: Run Read-Only Subagent Review For The First Batch

**Files:**
- Read: `docs/audits/plans-cleanup/batches/march-april-001.md`
- Modify: `docs/audits/plans-cleanup/reviews.jsonl`

- [ ] **Step 1: Dispatch subagents**

Dispatch one or more read-only subagents. Give each subagent this prompt followed by the assigned thread sections from `march-april-001.md`:

```text
You are reviewing a batch of root Science planning-doc threads for cleanup.

Rules:
- Read only. Do not edit files, delete files, move files, or run mutating git commands.
- Review implementation reality from code, durable docs, tests, and git history where useful.
- Do not trust status text inside old plans without verification.
- Return one JSON object per thread, with exactly these keys:
  thread_id, files, topic, status, superseded_by, supersedes, related_threads,
  evidence, remaining_gaps, durable_doc_candidate, recommended_action, review_notes.
- Allowed status values:
  delete_obvious, superseded_delete, implemented_needs_durable_docs,
  keep_historical, incomplete, unclear.
- Use superseded_by for superseded_delete.
- recommended_action must be one of:
  delete, create migration checkpoint, keep for triage, move to historical, keep active.
- Evidence must include concrete file paths, durable docs, command summaries, or git references.
- If a thread appears over-merged, flag it in review_notes, list the split-worthy
  file groups in related_threads, and avoid recommending a thread-wide delete.
```

- [ ] **Step 2: Append returned records to `reviews.jsonl`**

For each returned JSON object, append one compact JSON line. Example shape:

```json
{"thread_id":"example-thread","files":["docs/plans/2026-03-01-example-design.md"],"topic":"Example topic","status":"unclear","superseded_by":[],"supersedes":[],"related_threads":[],"evidence":["Inspected docs/plans/2026-03-01-example-design.md; no durable doc or code path found."],"remaining_gaps":["Needs main-agent follow-up to find implementation evidence."],"durable_doc_candidate":null,"recommended_action":"keep for triage","review_notes":"Low confidence; no cleanup action recommended."}
```

- [ ] **Step 3: Validate the appended reviews**

Run:

```bash
rtk uv run scripts/audit_plans_cleanup.py validate
```

Expected output:

```text
audit logs valid
```

- [ ] **Step 4: Refresh the pending triage report**

Run:

```bash
rtk uv run scripts/audit_plans_cleanup.py pending
```

Expected output includes:

```text
wrote docs/audits/plans-cleanup/pending.md
pending:
```

The exact pending count depends on review statuses.

- [ ] **Step 5: Commit review records**

```bash
rtk git add docs/audits/plans-cleanup/reviews.jsonl docs/audits/plans-cleanup/pending.md
rtk git commit -m "docs: record first plans cleanup audit reviews"
```

## Task 5: Reconcile Reviews And Perform Obvious Cleanup Actions

**Files:**
- Read: `docs/audits/plans-cleanup/thread-index.json`
- Read: `docs/audits/plans-cleanup/reviews.jsonl`
- Modify: `docs/audits/plans-cleanup/overrides.json` (only when splitting an over-merged thread).
- Modify: `docs/audits/plans-cleanup/actions.jsonl`
- Delete: verified `docs/plans/*.md` files with `delete_obvious` or `superseded_delete`.
- Move: verified `keep_historical` files to `docs/plans/historical/`.

- [ ] **Step 1: Read the first-batch reviews**

Run:

```bash
rtk proxy tail -n 12 docs/audits/plans-cleanup/reviews.jsonl
```

Expected: one valid JSON object per reviewed first-batch thread.

- [ ] **Step 2: Reconcile statuses manually**

For each reviewed thread:

- If `status` is `delete_obvious`, confirm the evidence proves completion and no durable-doc migration is needed.
- If `status` is `superseded_delete`, confirm `superseded_by` names concrete replacement code, docs, or thread ids.
- If `status` is `keep_historical`, confirm historical value and move all files for that thread to `docs/plans/historical/`.
- If `status` is `implemented_needs_durable_docs`, do not delete files; create a migration checkpoint action only.
- If `status` is `incomplete` or `unclear`, do not delete or move files.
- If `review_notes` flags an over-merged thread, record a split in
  `docs/audits/plans-cleanup/overrides.json` (map the original `thread_id` to its
  child threads with their exact files), regenerate the inventory so the children
  become first-class threads, append fresh reviews for each child, then act
  file-by-file. Leave any unrelated child group in place with a `deferred` action
  record until it is reviewed.

- [ ] **Step 3: Perform only verified deletes and historical moves**

Use normal file operations, then inspect the git diff. For each historical move, set `path` to one exact file path from the reviewed thread:

```bash
rtk mkdir -p docs/plans/historical
path=docs/plans/2026-03-01-knowledge-graph-design.md
target=docs/plans/historical/2026-03-01-knowledge-graph-design.md
rtk git mv "$path" "$target"
```

For each verified delete, set `path` to one exact file path from the reviewed thread:

```bash
path=docs/plans/2026-03-02-agent-capabilities-design.md
rtk git rm "$path"
```

The two `path=` examples above are examples of command shape only. Replace them with reviewed file paths before running the commands. Do not delete or move files whose evidence is ambiguous.

- [ ] **Step 4: Append action records**

Append one JSON line per reconciled action to `docs/audits/plans-cleanup/actions.jsonl`. Use this shape:

```json
{"thread_id":"example-thread","action":"deferred","files":["docs/plans/2026-03-01-example-design.md"],"reason":"status unclear after first review","commit":null}
```

Allowed `action` values for this pass:

- `deleted`
- `moved_to_historical`
- `migration_checkpoint_created`
- `deferred`

- [ ] **Step 5: Validate logs**

Run:

```bash
rtk uv run scripts/audit_plans_cleanup.py validate
```

Expected output:

```text
audit logs valid
```

- [ ] **Step 6: Refresh the pending triage report**

Run:

```bash
rtk uv run scripts/audit_plans_cleanup.py pending
```

Expected output includes:

```text
wrote docs/audits/plans-cleanup/pending.md
pending:
```

- [ ] **Step 7: Inspect cleanup diff**

Run:

```bash
rtk git diff --stat
rtk git diff -- docs/audits/plans-cleanup/actions.jsonl docs/plans docs/plans/historical
```

Expected: only reviewed first-batch files are deleted or moved, `actions.jsonl`
records every action, and `pending.md` reflects deferred or incomplete threads.

- [ ] **Step 8: Commit the first cleanup actions**

```bash
rtk git add -A docs/audits/plans-cleanup/actions.jsonl docs/audits/plans-cleanup/pending.md docs/plans
rtk git commit -m "docs: clean up first reviewed plans batch"
```

## Task 6: Regenerate Inventory And Prepare The Next Batch

**Files:**
- Modify: `docs/audits/plans-cleanup/thread-index.json`
- Modify: `docs/audits/plans-cleanup/pending.md`
- Create: `docs/audits/plans-cleanup/batches/march-april-002.md`

- [ ] **Step 1: Regenerate inventory after cleanup**

Run:

```bash
rtk uv run scripts/audit_plans_cleanup.py inventory --generated-at 2026-06-27T00:00:00+00:00
```

Expected output includes a reduced active file count if any files were deleted or moved to `docs/plans/historical/`.

Any `overrides.json` splits or related-thread links are reapplied here, so manual
reconciliation survives regeneration and split children remain in the index for
the next batch.

- [ ] **Step 2: Generate the next March/April batch**

Run:

```bash
rtk uv run scripts/audit_plans_cleanup.py batch --latest-before 2026-05-01 --limit 12 --output docs/audits/plans-cleanup/batches/march-april-002.md
```

Expected: reviewed thread ids from `reviews.jsonl` are skipped.

- [ ] **Step 3: Validate audit state**

Run:

```bash
rtk uv run scripts/audit_plans_cleanup.py validate
```

Expected output:

```text
audit logs valid
```

- [ ] **Step 4: Refresh pending triage after regeneration**

Run:

```bash
rtk uv run scripts/audit_plans_cleanup.py pending
```

Expected output includes:

```text
wrote docs/audits/plans-cleanup/pending.md
pending:
```

- [ ] **Step 5: Commit refreshed inventory and next batch**

```bash
rtk git add docs/audits/plans-cleanup/thread-index.json docs/audits/plans-cleanup/pending.md docs/audits/plans-cleanup/batches/march-april-002.md
rtk git commit -m "docs: prepare next plans cleanup audit batch"
```

## Verification Checklist

- [ ] `rtk uv run scripts/audit_plans_cleanup.py self-test` passes.
- [ ] `rtk uv run scripts/audit_plans_cleanup.py validate` passes.
- [ ] `docs/audits/plans-cleanup/thread-index.json` exists and excludes `docs/plans/historical/`.
- [ ] `docs/audits/plans-cleanup/reviews.jsonl` has one complete JSON object per reviewed thread.
- [ ] `docs/audits/plans-cleanup/actions.jsonl` records each delete, historical move, migration checkpoint, or deferral.
- [ ] `docs/audits/plans-cleanup/pending.md` lists deferred, incomplete, unclear, `implemented_needs_durable_docs`, and migration-checkpoint threads that do not have a later terminal action.
- [ ] No plan files are deleted unless their latest review status is `delete_obvious` or `superseded_delete`.
- [ ] No plan files are moved to `docs/plans/historical/` unless their latest review status is `keep_historical`.
- [ ] `docs/audits/plans-cleanup/overrides.json` splits are reapplied idempotently by `inventory`, and split children appear in `thread-index.json`.
- [ ] `thread-index.json` records any non-date-prefixed files under `non_conforming_files` instead of failing the inventory.
- [ ] `validate` rejects a review whose `recommended_action` is incoherent with its `status`.
- [ ] Worktree is clean after the final commit.
