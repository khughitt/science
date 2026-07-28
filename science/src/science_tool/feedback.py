"""Feedback entry CRUD, filtering, and deduplication for science.

Stores structured feedback as individual YAML files in ~/.config/science/feedback/.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from fnmatch import fnmatch
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

VALID_CATEGORIES = ("friction", "gap", "guidance", "suggestion", "positive")
VALID_STATUSES = ("open", "addressed", "deferred", "wontfix")
VALID_CONCERNS = (
    "tooling",
    "methodology:statistics",
    "methodology:qa",
    "methodology:design",
    "methodology:data-fitness",
    "methodology:reasoning",
)


def _validate_concern_value(value: str) -> str:
    if value not in VALID_CONCERNS:
        allowed = ", ".join(VALID_CONCERNS)
        msg = f"Invalid concern {value!r}; must be one of: {allowed}"
        raise ValueError(msg)
    return value

# Target prefixes that denote the same surface. A slash command (`command:`), its
# plural typo (`commands:`), the CLI form (`cli:`), and the `science:` namespace
# all refer to one tool surface, so they fold to a single normalized prefix.
_TARGET_PREFIX_ALIASES = {"command", "commands", "cli", "science"}
_TARGET_CANONICAL_PREFIX = "command"

_ID_RE = re.compile(r"^fb-(\d{4}-\d{2}-\d{2})-(\d{3})$")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_SUMMARY_STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "in",
    "of",
    "the",
    "to",
    "with",
}


class FeedbackStoreError(ValueError):
    """A feedback ID or path violates the feedback-store boundary."""


def _validate_feedback_id(value: str) -> str:
    if _ID_RE.fullmatch(value) is None:
        raise FeedbackStoreError(
            f"invalid canonical feedback ID {value!r}; expected fb-YYYY-MM-DD-NNN"
        )
    return value


class FeedbackOccurrence(BaseModel):
    """One filing of a feedback lesson.

    Every time the same lesson is reported, a record lands here instead of an
    integer being incremented. Per-filing project/category/detail are preserved
    so recurrence never destroys the cross-project reach it is meant to surface.
    """

    date: str
    project: str = ""
    category: str = "suggestion"
    detail: str | None = None


class FeedbackEntry(BaseModel):
    """A single feedback entry.

    `recurrence` is *derived* — it is `len(occurrences)`, never a stored integer.
    Legacy entries (a bare `recurrence:` and no `occurrences:`) are migrated on
    load by synthesizing that many occurrences from the entry's own fields, so a
    count is never silently dropped.
    """

    id: str
    created: str = Field(default_factory=lambda: date.today().isoformat())
    project: str = ""
    target: str
    category: str = "suggestion"
    status: str = "open"
    summary: str
    detail: str | None = None
    resolution: str | None = None
    related: list[str] = Field(default_factory=list)
    concern: str = "tooling"
    occurrences: list[FeedbackOccurrence] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _check_id(cls, value: str) -> str:
        return _validate_feedback_id(value)

    @field_validator("concern")
    @classmethod
    def _check_concern(cls, value: str) -> str:
        return _validate_concern_value(value)

    @model_validator(mode="before")
    @classmethod
    def _backfill_occurrences(cls, data: object) -> object:
        """Ensure every entry has at least one occurrence.

        Honors a legacy or explicit `recurrence:` by synthesizing that many
        occurrences from the entry's own fields, so migrating an old file never
        reduces its recurrence count.
        """
        if not isinstance(data, dict):
            return data
        if data.get("occurrences"):
            return data
        try:
            count = max(int(data.get("recurrence", 1)), 1)
        except (TypeError, ValueError):
            count = 1
        base = {
            "date": data.get("created") or date.today().isoformat(),
            "project": data.get("project") or "",
            "category": data.get("category") or "suggestion",
            "detail": data.get("detail"),
        }
        data = dict(data)
        data["occurrences"] = [dict(base) for _ in range(count)]
        return data

    @property
    def recurrence(self) -> int:
        """Number of times this lesson has been filed (derived, never stored)."""
        return len(self.occurrences)


@dataclass
class _FeedbackCluster:
    target: str
    concern: str
    category: str
    summary_key: str
    representative_summary: str
    entries: list[FeedbackEntry] = field(default_factory=list)
    projects: set[str] = field(default_factory=set)
    tokens: set[str] = field(default_factory=set)
    total_recurrence: int = 0
    newest_created: str = ""


@dataclass(frozen=True)
class FeedbackTestScaffold:
    """Result of creating or previewing a feedback regression scaffold."""

    path: Path
    suggested_test_target: str
    wrote: bool


def normalize_target(target: str) -> str:
    """Fold prefix and whitespace variance so equivalent spellings match.

    `command:`/`commands:`/`cli:`/`science:` all denote one tool surface and fold
    to a single canonical prefix; internal whitespace is collapsed. This is a
    conservative *exact-match widening* — it merges spellings that genuinely name
    the same surface and nothing more. Deeper spelling divergence (e.g.
    `commons-promote` vs `commons promote`) is left to advisory fuzzy matching.
    """
    collapsed = " ".join(target.split())
    if ":" not in collapsed:
        return collapsed
    prefix, rest = collapsed.split(":", 1)
    prefix = prefix.strip().lower()
    rest = rest.strip()
    if prefix in _TARGET_PREFIX_ALIASES:
        prefix = _TARGET_CANONICAL_PREFIX
    return f"{prefix}:{rest}"


def record_occurrence(
    entry: FeedbackEntry,
    *,
    date: str,
    project: str = "",
    category: str = "suggestion",
    detail: str | None = None,
) -> FeedbackEntry:
    """Append a filing to an entry without discarding any of its fields.

    This replaces the old destructive `recurrence += 1`: the new filing's
    project, category, and detail are retained instead of thrown away.
    """
    entry.occurrences.append(
        FeedbackOccurrence(date=date, project=project, category=category, detail=detail)
    )
    return entry


def save_entry(feedback_dir: Path, entry: FeedbackEntry) -> Path:
    """Write a feedback entry to a YAML file. Returns the file path."""
    entry_id = _validate_feedback_id(entry.id)
    feedback_dir.mkdir(parents=True, exist_ok=True)
    path = _feedback_entry_path(feedback_dir, entry_id)
    resolved_path = _resolve_store_path(feedback_dir, path)
    data = entry.model_dump(mode="json")
    resolved_path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    return path


def load_entry(feedback_dir: Path, entry_id: str) -> FeedbackEntry:
    """Load one canonical feedback ID from the configured store."""
    path = _feedback_entry_path(feedback_dir, _validate_feedback_id(entry_id))
    resolved_path = _resolve_store_path(feedback_dir, path)
    if not resolved_path.exists():
        raise FileNotFoundError(f"Feedback entry not found: {entry_id}")
    return _load_entry_path(feedback_dir, path)


def _feedback_entry_path(feedback_dir: Path, entry_id: str) -> Path:
    return feedback_dir / f"{entry_id}.yaml"


def _resolve_store_path(feedback_dir: Path, path: Path) -> Path:
    resolved_dir = feedback_dir.resolve()
    resolved_path = path.resolve()
    if not resolved_path.is_relative_to(resolved_dir):
        raise FeedbackStoreError(
            f"feedback path resolves outside feedback store {resolved_dir}: {path}"
        )
    if resolved_path.parent != resolved_dir or resolved_path.name != path.name:
        raise FeedbackStoreError(
            f"feedback path does not resolve to its canonical store location: {path}"
        )
    return resolved_path


def _load_entry_path(feedback_dir: Path, path: Path) -> FeedbackEntry:
    resolved_path = _resolve_store_path(feedback_dir, path)
    data = yaml.safe_load(resolved_path.read_text(encoding="utf-8"))
    entry = FeedbackEntry.model_validate(data)
    if path.stem != entry.id:
        raise FeedbackStoreError(
            f"feedback filename {path.name!r} does not match entry id {entry.id!r}"
        )
    return entry


def next_feedback_id(feedback_dir: Path, date_str: str) -> str:
    """Determine the next feedback ID for a given date."""
    max_num = 0
    prefix = f"fb-{date_str}-"

    if feedback_dir.is_dir():
        for path in feedback_dir.glob(f"{prefix}*.yaml"):
            m = _ID_RE.match(path.stem)
            if m and m.group(1) == date_str:
                max_num = max(max_num, int(m.group(2)))

    return f"fb-{date_str}-{max_num + 1:03d}"


def load_all_entries(feedback_dir: Path) -> list[FeedbackEntry]:
    """Load all feedback entries from a directory."""
    if not feedback_dir.is_dir():
        return []
    entries = []
    for path in sorted(feedback_dir.glob("fb-*.yaml")):
        entries.append(_load_entry_path(feedback_dir, path))
    return entries


def list_entries(
    feedback_dir: Path,
    *,
    status: str | None = "open",
    target: str | None = None,
    category: str | None = None,
    project: str | None = None,
    concern: str | None = None,
) -> list[FeedbackEntry]:
    """Filter feedback entries. Default: open entries only. Pass status=None for all."""
    entries = load_all_entries(feedback_dir)

    if status is not None:
        entries = [e for e in entries if e.status == status]
    if target is not None:
        entries = [e for e in entries if fnmatch(e.target, target)]
    if category is not None:
        entries = [e for e in entries if e.category == category]
    if project is not None:
        entries = [e for e in entries if e.project == project]
    if concern is not None:
        entries = [e for e in entries if fnmatch(e.concern, concern)]

    # Sort by recurrence descending, then date descending (most recent first)
    entries.sort(key=lambda e: (e.recurrence, e.created), reverse=True)

    return entries


def update_entry(
    feedback_dir: Path,
    entry_id: str,
    *,
    status: str | None = None,
    resolution: str | None = None,
    category: str | None = None,
    summary: str | None = None,
    detail: str | None = None,
    related: list[str] | None = None,
    concern: str | None = None,
) -> FeedbackEntry:
    """Update fields on an existing entry. Raises FileNotFoundError if not found."""
    entry = load_entry(feedback_dir, entry_id)

    if status is not None:
        if status in ("addressed", "deferred", "wontfix") and resolution is None:
            msg = f"--resolution is required when setting status to '{status}'"
            raise ValueError(msg)
        entry.status = status
    if resolution is not None:
        entry.resolution = resolution
    if category is not None:
        entry.category = category
    if summary is not None:
        entry.summary = summary
    if detail is not None:
        entry.detail = detail
    if related is not None:
        entry.related = related
    if concern is not None:
        entry.concern = _validate_concern_value(concern)

    save_entry(feedback_dir, entry)
    return entry


def find_duplicate(
    feedback_dir: Path,
    *,
    target: str,
    summary: str,
    concern: str = "tooling",
) -> FeedbackEntry | None:
    """Find an existing open entry with an equivalent target, concern, and summary.

    Targets are compared *normalized* (see `normalize_target`), so prefix and
    whitespace spellings of one surface merge. Summary matching stays a
    bidirectional substring check — the conservative signal for a genuine
    duplicate. Entries differing in concern are distinct even when the rest matches.
    """
    normalized = normalize_target(target)
    summary_lower = summary.lower()
    for entry in list_entries(feedback_dir, status="open"):
        if entry.concern != concern or normalize_target(entry.target) != normalized:
            continue
        entry_summary_lower = entry.summary.lower()
        if summary_lower in entry_summary_lower or entry_summary_lower in summary_lower:
            return entry
    return None


def find_similar_open(
    feedback_dir: Path,
    *,
    target: str,
    summary: str,
    concern: str = "tooling",
    threshold: float = 0.5,
    exclude_id: str | None = None,
) -> list[FeedbackEntry]:
    """Return open entries that are *fuzzy* neighbors, never exact duplicates.

    Same normalized target and concern, summary token similarity at or above
    `threshold`, but NOT a bidirectional substring match (those are handled by
    `find_duplicate`). This is advisory only — it surfaces candidates a filer may
    want to relate or merge, and never merges anything automatically.
    """
    normalized = normalize_target(target)
    summary_lower = summary.lower()
    tokens = set(_summary_tokens(summary))
    neighbors: list[FeedbackEntry] = []
    for entry in list_entries(feedback_dir, status="open"):
        if entry.id == exclude_id:
            continue
        if entry.concern != concern or normalize_target(entry.target) != normalized:
            continue
        entry_summary_lower = entry.summary.lower()
        if summary_lower in entry_summary_lower or entry_summary_lower in summary_lower:
            continue
        if _token_similarity(tokens, set(_summary_tokens(entry.summary))) >= threshold:
            neighbors.append(entry)
    return neighbors


def list_regression_candidates(feedback_dir: Path) -> list[dict[str, object]]:
    """List open ``positive`` entries as regression-test candidates.

    A positive is a validated property worth locking in with a test, but the
    category has no consumption path on its own — these entries otherwise go
    nowhere. Each row carries the entry's identity plus the
    ``suggested_next_test_target`` (the existing test file most likely to host
    the regression), so a filer can hand it to ``feedback scaffold-test`` or the
    named surface. Most-validated (highest ``recurrence``) first, then oldest.
    """
    entries = list_entries(feedback_dir, status="open", category="positive")
    entries.sort(key=lambda entry: (-entry.recurrence, entry.created, entry.id))
    return [
        {
            "id": entry.id,
            "created": entry.created,
            "project": entry.project,
            "target": entry.target,
            "summary": entry.summary,
            "recurrence": entry.recurrence,
            "suggested_next_test_target": _suggested_next_test_target(entry.target),
        }
        for entry in entries
    ]


def list_targets(feedback_dir: Path, *, status: str | None = "open") -> list[dict[str, object]]:
    """List distinct feedback targets with their entry counts.

    Lets a filer pick an existing spelling instead of minting a new variant.
    Each row carries the raw `target`, its `normalized` key (so spelling variants
    are visibly grouped), the `count` of entries, and `total_recurrence`.
    """
    entries = list_entries(feedback_dir, status=status)
    rows: dict[str, dict[str, object]] = {}
    for entry in entries:
        row = rows.get(entry.target)
        if row is None:
            row = {
                "target": entry.target,
                "normalized": normalize_target(entry.target),
                "count": 0,
                "total_recurrence": 0,
            }
            rows[entry.target] = row
        row["count"] = int(row["count"]) + 1  # type: ignore[arg-type]
        row["total_recurrence"] = int(row["total_recurrence"]) + entry.recurrence  # type: ignore[arg-type]
    return sorted(
        rows.values(),
        key=lambda r: (-int(r["count"]), str(r["target"])),  # type: ignore[arg-type]
    )


def group_for_triage(
    feedback_dir: Path,
    *,
    target: str | None = None,
    concern: str | None = None,
) -> dict[tuple[str, str], dict]:
    """Group open entries by (concern, target) for triage display.

    Returns: {(concern, target): {concern, target, entries, projects, total_recurrence}}
    Sorted by total_recurrence descending. The grouped value carries explicit
    `concern` and `target` so callers never read the tuple key for display or
    telemetry joins.
    """
    entries = list_entries(feedback_dir, status="open", target=target, concern=concern)

    groups: dict[tuple[str, str], dict] = {}
    for entry in entries:
        key = (entry.concern, entry.target)
        if key not in groups:
            groups[key] = {
                "concern": entry.concern,
                "target": entry.target,
                "entries": [],
                "projects": set(),
                "total_recurrence": 0,
            }
        groups[key]["entries"].append(entry)
        groups[key]["projects"].update(_entry_projects(entry))
        groups[key]["total_recurrence"] += entry.recurrence

    return dict(sorted(groups.items(), key=lambda item: -item[1]["total_recurrence"]))


def cluster_for_triage(
    feedback_dir: Path,
    *,
    target: str | None = None,
    concern: str | None = None,
    since_days: int | None = None,
    today: date | None = None,
) -> list[dict[str, object]]:
    """Cluster open entries by concern, target, category, and near-duplicate summary."""
    entries = list_entries(feedback_dir, status="open", target=target, concern=concern)
    if since_days is not None:
        cutoff = (today or date.today()) - timedelta(days=since_days)
        entries = [entry for entry in entries if date.fromisoformat(entry.created) >= cutoff]

    clusters: list[_FeedbackCluster] = []
    for entry in entries:
        tokens = set(_summary_tokens(entry.summary))
        cluster = _matching_cluster(clusters, entry=entry, tokens=tokens)
        if cluster is None:
            cluster = _FeedbackCluster(
                target=entry.target,
                concern=entry.concern,
                category=entry.category,
                summary_key=_summary_key(entry.summary),
                representative_summary=entry.summary,
                newest_created=entry.created,
            )
            clusters.append(cluster)

        cluster.entries.append(entry)
        cluster.projects.update(_entry_projects(entry))
        cluster.total_recurrence += entry.recurrence
        cluster.newest_created = max(cluster.newest_created, entry.created)
        cluster.tokens |= tokens

    rows = [_cluster_row(cluster) for cluster in clusters]
    def sort_key(row: dict[str, object]) -> tuple[int, int, str, str]:
        total_recurrence = row["total_recurrence"]
        count = row["count"]
        if not isinstance(total_recurrence, int) or not isinstance(count, int):
            raise TypeError("feedback cluster row count fields must be integers")
        return (
            -total_recurrence,
            -count,
            str(row["target"]),
            str(row["summary_key"]),
        )

    rows.sort(key=sort_key)
    return rows


def attach_telemetry_to_triage_rows(
    rows: list[dict[str, object]],
    *,
    events: list[dict[str, object]],
    since_days: int | None,
) -> list[dict[str, object]]:
    """Return triage rows enriched with recent local telemetry summaries."""
    from science_tool.telemetry import summarize_recent_for_feedback_target

    window = since_days if since_days is not None else 14
    enriched: list[dict[str, object]] = []
    for row in rows:
        copied = dict(row)
        copied["telemetry"] = summarize_recent_for_feedback_target(
            events,
            target=str(row.get("target") or ""),
            since_days=window,
        )
        enriched.append(copied)
    return enriched


def scaffold_test_for_feedback(
    feedback_dir: Path,
    entry_id: str,
    *,
    project_root: Path,
    out_path: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> FeedbackTestScaffold:
    """Write a failing pytest scaffold for a feedback entry."""
    entry = load_entry(feedback_dir, entry_id)
    target_path = _scaffold_output_path(project_root, entry_id, out_path)
    suggested_target = _suggested_next_test_target(entry.target)
    if target_path.exists() and not force:
        raise FileExistsError(f"Scaffold already exists: {target_path}")

    if dry_run:
        return FeedbackTestScaffold(path=target_path, suggested_test_target=suggested_target, wrote=False)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(_scaffold_test_text(entry, suggested_target), encoding="utf-8")
    return FeedbackTestScaffold(path=target_path, suggested_test_target=suggested_target, wrote=True)


def _scaffold_output_path(project_root: Path, entry_id: str, out_path: Path | None) -> Path:
    if out_path is not None:
        return out_path if out_path.is_absolute() else project_root / out_path
    return project_root / "science" / "tests" / "scaffolded" / f"test_{_python_safe_name(entry_id)}.py"


def _python_safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_")


def _scaffold_test_text(entry: FeedbackEntry, suggested_target: str) -> str:
    lines = [
        '"""Regression scaffold generated from Science feedback."""',
        "",
        "from __future__ import annotations",
        "",
        "import pytest",
        "",
        "",
        f"def test_{_python_safe_name(entry.id)}() -> None:",
        f'    """Regression scaffold for {entry.id}."""',
        f"    # Target: {entry.target}",
        f"    # Category: {entry.category}",
        f"    # Summary: {entry.summary}",
        f"    # Suggested existing test target: {suggested_target}",
    ]
    if entry.detail:
        lines.append("    # Detail:")
        lines.extend(f"    #   {line}" if line else "    #" for line in entry.detail.splitlines())
    lines.extend(
        [
            "    pytest.fail(",
            f'        "Do not close feedback {entry.id} until this test is replaced "',
            '        "with a real failing regression test and the fix is verified."',
            "    )",
            "",
        ]
    )
    return "\n".join(lines)


def _matching_cluster(
    clusters: list[_FeedbackCluster],
    *,
    entry: FeedbackEntry,
    tokens: set[str],
) -> _FeedbackCluster | None:
    for cluster in clusters:
        if cluster.target != entry.target or cluster.concern != entry.concern or cluster.category != entry.category:
            continue
        if _token_similarity(tokens, cluster.tokens) >= 0.75:
            return cluster
    return None


def _cluster_row(cluster: _FeedbackCluster) -> dict[str, object]:
    entries = sorted(cluster.entries, key=lambda entry: (entry.created, entry.id))
    return {
        "target": cluster.target,
        "concern": cluster.concern,
        "category": cluster.category,
        "summary_key": cluster.summary_key,
        "representative_summary": cluster.representative_summary,
        "entry_ids": [entry.id for entry in entries],
        "count": len(entries),
        "total_recurrence": cluster.total_recurrence,
        "projects": sorted(cluster.projects),
        "suggested_status": _suggested_status(target=cluster.target, category=cluster.category, count=len(entries)),
        "suggested_next_test_target": _suggested_next_test_target(cluster.target),
    }


def _entry_projects(entry: FeedbackEntry) -> set[str]:
    """Every distinct project that filed this lesson, across all occurrences."""
    return {occ.project for occ in entry.occurrences if occ.project}


def _summary_tokens(summary: str) -> list[str]:
    normalized = summary.lower().replace("-", " ")
    tokens: list[str] = []
    for raw in _TOKEN_RE.findall(normalized):
        token = _stem_summary_token(raw)
        if token and token not in _SUMMARY_STOPWORDS:
            tokens.append(token)
    return tokens


def _summary_key(summary: str) -> str:
    return " ".join(_readable_summary_tokens(summary))


def _readable_summary_tokens(summary: str) -> list[str]:
    normalized = summary.lower().replace("-", " ")
    return [token for token in _TOKEN_RE.findall(normalized) if token not in _SUMMARY_STOPWORDS]


def _stem_summary_token(token: str) -> str:
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token


def _token_similarity(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _suggested_status(*, target: str, category: str, count: int) -> str:
    if category == "positive":
        return "positive-reinforce"
    if target.startswith("framework:") or category == "gap":
        return "design-needed"
    if count > 1 or category in {"friction", "guidance", "suggestion"}:
        return "quick-win"
    return "possibly-stale"


def _suggested_next_test_target(target: str) -> str:
    # Normalize first so cli:/commands:/science: spellings route like command: —
    # the same surface equivalence normalize_target establishes for dedup.
    target = normalize_target(target)
    if target == "command:feedback":
        return "science/tests/test_feedback_cli.py"
    if target.startswith("command:"):
        return "science/tests/test_command_docs.py"
    if target.startswith("template:"):
        return "science/tests/validate/test_checks_research_documents.py"
    if target.startswith("framework:"):
        return "docs/plans/"
    return "science/tests/"


def render_report(
    feedback_dir: Path,
    *,
    status: str | None = None,
    project: str | None = None,
    concern: str | None = None,
) -> str:
    """Render a human-readable markdown report grouped by concern then target."""
    entries = list_entries(feedback_dir, status=status, project=project, concern=concern)

    if not entries:
        return "No feedback entries found.\n"

    by_concern: dict[str, dict[str, list[FeedbackEntry]]] = {}
    for entry in entries:
        by_concern.setdefault(entry.concern, {}).setdefault(entry.target, []).append(entry)

    lines = ["# Feedback Report", ""]
    # Alphabetical order is intentional: methodology:* groups sort before
    # tooling, giving the methodology lens top billing. A future reorder must
    # not break the Task-5 test that relies on this.
    for concern_value, by_target in sorted(by_concern.items()):
        lines.append(f"## {concern_value}")
        lines.append("")
        for target, group in sorted(by_target.items()):
            lines.append(f"### {target}")
            lines.append("")
            for entry in group:
                status_badge = f"[{entry.status}]"
                lines.append(f"- **{entry.id}** {status_badge} ({entry.category}) — {entry.summary}")
                if entry.recurrence > 1:
                    lines.append(f"  - Recurrence: {entry.recurrence}")
                if entry.resolution:
                    lines.append(f"  - Resolution: {entry.resolution}")
            lines.append("")

    return "\n".join(lines)


def detect_project(start: Path) -> str:
    """Detect the project name by walking up to find science.yaml.

    Returns the directory name of the nearest ancestor containing science.yaml,
    or the start directory name if none found.
    """
    from science_tool.data_root import nearest_project_root

    resolved = start.resolve()
    root = nearest_project_root(resolved)
    return root.name if root is not None else resolved.name
