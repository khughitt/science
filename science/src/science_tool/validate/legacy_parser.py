from __future__ import annotations

from pathlib import Path
import re

from science_tool.validate.result import Result, Severity

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_RESULT_RE = re.compile(r"^(WARN|ERROR): (.*)$")


def parse(stdout: str, project_root: Path | None = None) -> tuple[list[Result], list[str]]:
    results: list[Result] = []
    log_lines: list[str] = []

    for raw_line in stdout.splitlines():
        line = _ANSI_RE.sub("", raw_line)
        match = _RESULT_RE.match(line)
        if match is None:
            log_lines.append(line)
            continue

        severity = Severity.WARN if match.group(1) == "WARN" else Severity.ERROR
        path, message = _extract_path(match.group(2), project_root)
        results.append(Result(severity, path, None, message, None, None))

    return results, log_lines


def _extract_path(message: str, project_root: Path | None) -> tuple[Path | None, str]:
    if project_root is None or ": " not in message:
        return None, message

    token, rest = message.split(": ", 1)
    candidate = Path(token)
    if _is_valid_project_relative_path(candidate, project_root):
        return candidate, rest
    return None, message


def _is_valid_project_relative_path(path: Path, project_root: Path) -> bool:
    if path.is_absolute() or path == Path() or ".." in path.parts:
        return False
    try:
        resolved_root = project_root.resolve(strict=True)
        resolved_path = (resolved_root / path).resolve(strict=True)
        resolved_path.relative_to(resolved_root)
    except (OSError, ValueError):
        return False
    return True
