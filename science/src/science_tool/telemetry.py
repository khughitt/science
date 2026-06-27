"""Local-first telemetry event storage and reporting."""

from __future__ import annotations

import json
import os
import re
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from pathlib import Path

from science_tool.registry.config import get_science_config_dir

_SAFE_REF_RE = re.compile(r"^(?:dataset|question|hypothesis|task|paper|topic|theme|kind):[A-Za-z0-9_.:-]+$")
_COMMAND_TOKEN_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_REDACTED_OPTIONS = {
    "--detail",
    "--license",
    "--note",
    "--notes",
    "--out",
    "--output",
    "--path",
    "--project-root",
    "--root",
    "--source",
    "--summary",
    "--title",
    "--url",
}


def get_telemetry_dir() -> Path:
    """Return the local telemetry directory."""
    override = os.environ.get("SCIENCE_TELEMETRY_DIR")
    if override:
        return Path(override)
    return get_science_config_dir() / "telemetry"


def telemetry_enabled() -> bool:
    """Return whether local telemetry writes are enabled."""
    value = os.environ.get("SCIENCE_TELEMETRY_ENABLED", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def redact_argv(argv: Sequence[str]) -> list[str]:
    """Return a conservative, non-sensitive command shape."""
    redacted: list[str] = []
    previous_option: str | None = None
    for index, token in enumerate(argv):
        if token.startswith("--"):
            option, sep, value = token.partition("=")
            redacted.append(option)
            if sep:
                redacted.append(_redact_value(value, option=option, index=index))
                previous_option = None
            else:
                previous_option = option
            continue
        if token.startswith("-") and token != "-":
            redacted.append(token)
            previous_option = token
            continue
        redacted.append(_redact_value(token, option=previous_option, index=index))
        previous_option = None
    return redacted


def new_event(
    *,
    event_type: str,
    command: str | None = None,
    argv: Sequence[str] = (),
    timestamp: str | None = None,
    exit_code: int | None = None,
    error_class: str | None = None,
    error_message_template: str | None = None,
) -> dict[str, object]:
    """Create a telemetry event dictionary."""
    timestamp_value = timestamp or datetime.now().astimezone().isoformat()
    event: dict[str, object] = {
        "schema_version": 1,
        "event_id": f"tel-{_timestamp_slug(timestamp_value)}-{uuid.uuid4().hex[:8]}",
        "timestamp": timestamp_value,
        "surface": "cli",
        "event_type": event_type,
        "source": "science",
        "argv_shape": redact_argv(argv),
    }
    if command:
        event["command"] = command
    if exit_code is not None:
        event["exit_code"] = exit_code
    if error_class:
        event["error_class"] = error_class
    if error_message_template:
        event["error_message_template"] = error_message_template
    return event


def new_validation_summary_event(
    *,
    command: str,
    profile: str,
    strict: bool,
    fail_on: str | None,
    errors: int,
    warnings: int,
    infos: int,
    gated: bool,
    rule_ids: Sequence[str | None],
) -> dict[str, object]:
    """Create an aggregate-only validation summary event."""
    event = new_event(event_type="validation_summary", command=command, argv=())
    event["surface"] = "validation"
    event["profile"] = profile
    event["strict"] = strict
    event["fail_on"] = fail_on
    event["status"] = _validation_status(errors=errors, warnings=warnings, gated=gated)
    event["counts"] = {"error": errors, "warn": warnings, "info": infos}
    event["top_checks"] = _top_checks(rule_ids)
    return event


def append_event(telemetry_dir: Path, event: Mapping[str, object]) -> Path | None:
    """Append an event to the monthly JSONL journal, best effort."""
    try:
        telemetry_dir.mkdir(parents=True, exist_ok=True)
        path = telemetry_dir / f"events-{_event_month(event)}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(event), sort_keys=True, separators=(",", ":")))
            handle.write("\n")
        return path
    except OSError:
        return None


def read_events(telemetry_dir: Path) -> list[dict[str, object]]:
    """Read all valid telemetry events from a directory."""
    if not telemetry_dir.is_dir():
        return []
    events: list[dict[str, object]] = []
    for path in sorted(telemetry_dir.glob("events-*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                events.append(value)
    return events


def summarize_events(events: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Summarize telemetry events for local reporting."""
    event_types: Counter[str] = Counter()
    commands: Counter[str] = Counter()
    error_classes: Counter[str] = Counter()
    exit_codes: Counter[str] = Counter()

    for event in events:
        if event_type := _string_field(event, "event_type"):
            event_types[event_type] += 1
        if command := _string_field(event, "command"):
            commands[command] += 1
        if error_class := _string_field(event, "error_class"):
            error_classes[error_class] += 1
        exit_code = event.get("exit_code")
        if exit_code is not None:
            exit_codes[str(exit_code)] += 1

    return {
        "total_events": len(events),
        "event_types": dict(sorted(event_types.items())),
        "commands": dict(sorted(commands.items())),
        "error_classes": dict(sorted(error_classes.items())),
        "exit_codes": dict(sorted(exit_codes.items())),
    }


def export_events_jsonl(events: Sequence[Mapping[str, object]]) -> str:
    """Render events as deterministic JSONL."""
    sorted_events = sorted(events, key=lambda event: (_string_field(event, "timestamp"), _string_field(event, "event_id")))
    if not sorted_events:
        return ""
    return "\n".join(json.dumps(dict(event), sort_keys=True, separators=(",", ":")) for event in sorted_events) + "\n"


def prune_events(telemetry_dir: Path, before: date) -> int:
    """Remove events before a cutoff date. Returns the number removed."""
    if not telemetry_dir.is_dir():
        return 0

    removed = 0
    for path in sorted(telemetry_dir.glob("events-*.jsonl")):
        kept: list[dict[str, object]] = []
        for event in _read_file_events(path):
            event_date = _event_date(event)
            if event_date is not None and event_date < before:
                removed += 1
                continue
            kept.append(event)
        if kept:
            path.write_text(export_events_jsonl(kept), encoding="utf-8")
        else:
            path.unlink(missing_ok=True)
    return removed


def _redact_value(token: str, *, option: str | None, index: int) -> str:
    if _SAFE_REF_RE.match(token):
        return token
    if token.startswith(("http://", "https://")):
        return "<url:redacted>"
    if "/" in token or token.startswith(("~", ".")):
        return "<path:redacted>"
    if option in _REDACTED_OPTIONS:
        return "<value:redacted>"
    if index < 2 and _COMMAND_TOKEN_RE.match(token):
        return token
    if token in {"true", "false", "json", "table", "text", "public", "private", "all", "open"}:
        return "<value>"
    return "<value>"


def _read_file_events(path: Path) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def _event_date(event: Mapping[str, object]) -> date | None:
    timestamp = _string_field(event, "timestamp")
    if not timestamp:
        return None
    try:
        return date.fromisoformat(timestamp[:10])
    except ValueError:
        return None


def _string_field(event: Mapping[str, object], key: str) -> str:
    value = event.get(key)
    return value if isinstance(value, str) else ""


def _validation_status(*, errors: int, warnings: int, gated: bool) -> str:
    if errors > 0 or gated:
        return "fail"
    if warnings > 0:
        return "warn"
    return "pass"


def _top_checks(rule_ids: Sequence[str | None]) -> list[dict[str, object]]:
    counts = Counter(rule_id for rule_id in rule_ids if rule_id)
    return [
        {"check": rule_id, "count": count}
        for rule_id, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _event_month(event: Mapping[str, object]) -> str:
    timestamp = str(event.get("timestamp") or datetime.now().astimezone().isoformat())
    return timestamp[:7]


def _timestamp_slug(timestamp: str) -> str:
    return (
        timestamp.replace(":", "-")
        .replace("+", "-")
        .replace(".", "-")
        .replace("T", "T")
    )
