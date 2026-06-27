"""Local-first telemetry event storage and reporting."""

from __future__ import annotations

import json
import os
import re
import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime
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
