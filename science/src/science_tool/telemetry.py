"""Local-first telemetry event storage and reporting."""

from __future__ import annotations

import json
import os
import re
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
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


@dataclass(frozen=True)
class TelemetryFeedbackContext:
    """Feedback defaults derived from a redacted telemetry event."""

    event: Mapping[str, object]
    target: str
    category: str
    detail: str


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


def summarize_recent_for_feedback_target(
    events: Sequence[Mapping[str, object]],
    *,
    target: str,
    today: date | None = None,
    since_days: int = 14,
) -> dict[str, object]:
    """Summarize recent telemetry relevant to a feedback target."""
    cutoff = (today or date.today()) - timedelta(days=since_days)
    matching = [
        event
        for event in events
        if (event_date := _event_date(event)) is not None
        and event_date >= cutoff
        and _feedback_target_matches_event(target, event)
    ]
    return _summarize_feedback_events(matching)


def feedback_context_from_recent_event(
    events: Sequence[Mapping[str, object]],
    *,
    index: int = 1,
    today: date | None = None,
    since_days: int = 14,
) -> TelemetryFeedbackContext:
    """Return feedback defaults for a recent eligible telemetry event."""
    if index < 1:
        raise ValueError("--from-recent uses a 1-based index")

    cutoff = (today or date.today()) - timedelta(days=since_days)
    eligible = [
        event
        for event in events
        if (event_date := _event_date(event)) is not None and event_date >= cutoff and _is_feedback_source_event(event)
    ]
    eligible.sort(key=lambda event: (_string_field(event, "timestamp"), _string_field(event, "event_id")), reverse=True)
    if not eligible:
        raise ValueError("No eligible recent telemetry events found")
    if index > len(eligible):
        raise ValueError(f"--from-recent index {index} is out of range for {len(eligible)} eligible telemetry events")

    event = eligible[index - 1]
    command = _string_field(event, "command")
    command_token = command.split(maxsplit=1)[0] if command else "unknown"
    return TelemetryFeedbackContext(
        event=event,
        target=f"command:{command_token}",
        category=_feedback_category_for_event(event),
        detail=_feedback_detail_for_event(event),
    )


def format_feedback_telemetry(summary: Mapping[str, object]) -> str:
    """Format feedback telemetry context for compact table output."""
    recent_events = _int_value(summary.get("recent_events"))
    if recent_events == 0:
        return "no recent telemetry"

    validation = summary.get("validation")
    if isinstance(validation, Mapping) and (validation_runs := _int_value(validation.get("runs"))) > 0:
        statuses = validation.get("statuses")
        status_counts = statuses if isinstance(statuses, Mapping) else {}
        parts = [f"validate: {validation_runs} runs"]
        for status in ("fail", "warn", "pass"):
            count = _int_value(status_counts.get(status))
            if count:
                parts.append(f"{count} {status}")
        return ", ".join(parts)

    command_errors = summary.get("command_errors")
    if isinstance(command_errors, Mapping) and command_errors:
        total_errors = sum(int(value) for value in command_errors.values() if isinstance(value, int))
        return f"{recent_events} events, {total_errors} errors"
    return f"{recent_events} events"


def _is_feedback_source_event(event: Mapping[str, object]) -> bool:
    event_type = _string_field(event, "event_type")
    if event_type == "command_error":
        return True
    if event_type == "command_finish":
        exit_code = event.get("exit_code")
        return isinstance(exit_code, int) and exit_code != 0
    if event_type == "validation_summary":
        return _string_field(event, "status") in {"warn", "fail"}
    return False


def _feedback_category_for_event(event: Mapping[str, object]) -> str:
    if _string_field(event, "event_type") == "validation_summary":
        return "gap"
    return "friction"


def _feedback_detail_for_event(event: Mapping[str, object]) -> str:
    lines = ["Telemetry context:"]
    _append_detail_line(lines, "event", _string_field(event, "event_id"))
    _append_detail_line(lines, "timestamp", _string_field(event, "timestamp"))
    _append_detail_line(lines, "command", _string_field(event, "command"))
    argv_shape = event.get("argv_shape")
    if isinstance(argv_shape, Sequence) and not isinstance(argv_shape, (str, bytes)):
        rendered_argv = " ".join(str(token) for token in argv_shape)
        _append_detail_line(lines, "argv", rendered_argv)
    if isinstance(event.get("exit_code"), int):
        _append_detail_line(lines, "exit_code", str(event["exit_code"]))
    _append_detail_line(lines, "error_class", _string_field(event, "error_class"))
    _append_detail_line(lines, "validation_status", _string_field(event, "status"))
    counts = event.get("counts")
    if isinstance(counts, Mapping):
        rendered_counts = ", ".join(
            f"{key}={_int_value(counts.get(key))}"
            for key in ("error", "warn", "info")
            if key in counts
        )
        _append_detail_line(lines, "validation_counts", rendered_counts)
    rendered_checks = _render_top_checks(event.get("top_checks"))
    _append_detail_line(lines, "top_checks", rendered_checks)
    return "\n".join(lines)


def _append_detail_line(lines: list[str], label: str, value: str) -> None:
    if value:
        lines.append(f"- {label}: {value}")


def _render_top_checks(value: object) -> str:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ""
    rendered: list[str] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        check = item.get("check")
        count = item.get("count")
        if isinstance(check, str) and isinstance(count, int):
            rendered.append(f"{check}={count}")
    return ", ".join(rendered)


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


def _feedback_target_matches_event(target: str, event: Mapping[str, object]) -> bool:
    if not target.startswith("command:"):
        return True
    command_target = target.removeprefix("command:")
    command = _string_field(event, "command")
    if not command:
        return False
    first_token = command.split(maxsplit=1)[0]
    return command == command_target or first_token == command_target


def _summarize_feedback_events(events: Sequence[Mapping[str, object]]) -> dict[str, object]:
    commands: Counter[str] = Counter()
    command_errors: Counter[str] = Counter()
    validation_statuses: Counter[str] = Counter()
    validation_top_checks: Counter[str] = Counter()
    validation_runs = 0

    for event in events:
        event_type = _string_field(event, "event_type")
        if event_type in {"command_finish", "command_error"}:
            if command := _string_field(event, "command"):
                commands[command] += 1
        if event_type == "command_error":
            if error_class := _string_field(event, "error_class"):
                command_errors[error_class] += 1
        if event_type == "validation_summary":
            validation_runs += 1
            if status := _string_field(event, "status"):
                validation_statuses[status] += 1
            top_checks = event.get("top_checks")
            if isinstance(top_checks, Sequence) and not isinstance(top_checks, (str, bytes)):
                for item in top_checks:
                    if not isinstance(item, Mapping):
                        continue
                    check = item.get("check")
                    count = item.get("count")
                    if isinstance(check, str) and isinstance(count, int):
                        validation_top_checks[check] += count

    return {
        "recent_events": len(events),
        "command_errors": dict(sorted(command_errors.items())),
        "commands": dict(sorted(commands.items())),
        "validation": {
            "runs": validation_runs,
            "statuses": dict(sorted(validation_statuses.items())),
            "top_checks": dict(sorted(validation_top_checks.items())),
        },
    }


def _string_field(event: Mapping[str, object], key: str) -> str:
    value = event.get(key)
    return value if isinstance(value, str) else ""


def _int_value(value: object) -> int:
    return value if isinstance(value, int) else 0


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
