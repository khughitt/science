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
from pydantic import BaseModel, Field

VALID_CATEGORIES = ("friction", "gap", "guidance", "suggestion", "positive")
VALID_STATUSES = ("open", "addressed", "deferred", "wontfix")

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


class FeedbackEntry(BaseModel):
    """A single feedback entry."""

    id: str
    created: str = Field(default_factory=lambda: date.today().isoformat())
    project: str = ""
    target: str
    category: str = "suggestion"
    status: str = "open"
    summary: str
    detail: str | None = None
    resolution: str | None = None
    recurrence: int = 1
    related: list[str] = Field(default_factory=list)


@dataclass
class _FeedbackCluster:
    target: str
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


def save_entry(feedback_dir: Path, entry: FeedbackEntry) -> Path:
    """Write a feedback entry to a YAML file. Returns the file path."""
    feedback_dir.mkdir(parents=True, exist_ok=True)
    path = feedback_dir / f"{entry.id}.yaml"
    data = entry.model_dump(mode="json")
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")
    return path


def load_entry(path: Path) -> FeedbackEntry:
    """Load a feedback entry from a YAML file."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return FeedbackEntry.model_validate(data)


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
        entries.append(load_entry(path))
    return entries


def list_entries(
    feedback_dir: Path,
    *,
    status: str | None = "open",
    target: str | None = None,
    category: str | None = None,
    project: str | None = None,
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
) -> FeedbackEntry:
    """Update fields on an existing entry. Raises FileNotFoundError if not found."""
    path = feedback_dir / f"{entry_id}.yaml"
    if not path.exists():
        msg = f"Feedback entry not found: {entry_id}"
        raise FileNotFoundError(msg)

    entry = load_entry(path)

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

    save_entry(feedback_dir, entry)
    return entry


def find_duplicate(
    feedback_dir: Path,
    *,
    target: str,
    summary: str,
) -> FeedbackEntry | None:
    """Find an existing open entry with the same target and similar summary.

    Uses bidirectional substring matching: returns a match if either summary
    is a substring of the other.
    """
    entries = list_entries(feedback_dir, status="open", target=target)
    summary_lower = summary.lower()
    for entry in entries:
        entry_summary_lower = entry.summary.lower()
        if summary_lower in entry_summary_lower or entry_summary_lower in summary_lower:
            return entry
    return None


def group_for_triage(
    feedback_dir: Path,
    *,
    target: str | None = None,
) -> dict[str, dict]:
    """Group open entries by target for triage display.

    Returns: {target: {entries: [...], projects: set, total_recurrence: int}}
    Sorted by total_recurrence descending.
    """
    entries = list_entries(feedback_dir, status="open", target=target)

    groups: dict[str, dict] = {}
    for entry in entries:
        if entry.target not in groups:
            groups[entry.target] = {
                "entries": [],
                "projects": set(),
                "total_recurrence": 0,
            }
        groups[entry.target]["entries"].append(entry)
        if entry.project:
            groups[entry.target]["projects"].add(entry.project)
        groups[entry.target]["total_recurrence"] += entry.recurrence

    # Sort groups by total recurrence descending
    return dict(sorted(groups.items(), key=lambda item: -item[1]["total_recurrence"]))


def cluster_for_triage(
    feedback_dir: Path,
    *,
    target: str | None = None,
    since_days: int | None = None,
    today: date | None = None,
) -> list[dict[str, object]]:
    """Cluster open entries by target, category, and near-duplicate summary."""
    entries = list_entries(feedback_dir, status="open", target=target)
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
                category=entry.category,
                summary_key=_summary_key(entry.summary),
                representative_summary=entry.summary,
                newest_created=entry.created,
            )
            clusters.append(cluster)

        cluster.entries.append(entry)
        if entry.project:
            cluster.projects.add(entry.project)
        cluster.total_recurrence += entry.recurrence
        cluster.newest_created = max(cluster.newest_created, entry.created)
        cluster.tokens |= tokens

    rows = [_cluster_row(cluster) for cluster in clusters]
    rows.sort(
        key=lambda row: (
            -int(row["total_recurrence"]),
            -int(row["count"]),
            str(row["target"]),
            str(row["summary_key"]),
        )
    )
    return rows


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
    entry_path = feedback_dir / f"{entry_id}.yaml"
    if not entry_path.exists():
        raise FileNotFoundError(f"Feedback entry not found: {entry_id}")

    entry = load_entry(entry_path)
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
        if cluster.target != entry.target or cluster.category != entry.category:
            continue
        if _token_similarity(tokens, cluster.tokens) >= 0.75:
            return cluster
    return None


def _cluster_row(cluster: _FeedbackCluster) -> dict[str, object]:
    entries = sorted(cluster.entries, key=lambda entry: (entry.created, entry.id))
    return {
        "target": cluster.target,
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
) -> str:
    """Render a human-readable markdown report of feedback entries."""
    entries = list_entries(feedback_dir, status=status, project=project)

    if not entries:
        return "No feedback entries found.\n"

    # Group by target
    by_target: dict[str, list[FeedbackEntry]] = {}
    for entry in entries:
        by_target.setdefault(entry.target, []).append(entry)

    lines = ["# Feedback Report", ""]
    for target, group in sorted(by_target.items()):
        lines.append(f"## {target}")
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
    or the start directory name if none found. Walk stops at $HOME.
    """
    home = Path.home()
    current = start.resolve()

    while current != current.parent:
        if (current / "science.yaml").exists():
            return current.name
        if current == home:
            break
        current = current.parent

    return start.resolve().name
