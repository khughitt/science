"""Generate Python validation sidecar skeletons from legacy bash sidecars."""

from __future__ import annotations

from dataclasses import dataclass
import json
import keyword
from pathlib import Path
import re
import shlex


class PortValidateSidecarError(Exception):
    """Legacy sidecar could not be converted to a Python skeleton."""


@dataclass(frozen=True)
class HookRegistration:
    hook_name: str
    bash_function: str
    python_function: str
    bash_body: str


_FUNCTION_START_RE = re.compile(r"^\s*(?:function\s+)?(?P<fn>[A-Za-z_][A-Za-z0-9_]*)\s*(?:\(\s*\))?\s*\{\s*$")
_VALID_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_INVALID_IDENTIFIER_CHAR_RE = re.compile(r"\W+")


def port_validate_sidecar(project_root: Path, *, force: bool = False) -> Path:
    """Write a validate_local.py skeleton and return the written path."""
    root = project_root.resolve()
    legacy_path = root / "validate.local.sh"
    target_path = root / "validate_local.py"
    draft_path = root / "validate_local.py.draft"

    if not legacy_path.is_file():
        raise PortValidateSidecarError(f"validate.local.sh not found at {legacy_path}")
    if target_path.exists() and not force:
        raise PortValidateSidecarError("validate_local.py already exists; pass --force to overwrite it")
    if draft_path.exists() and not force:
        raise PortValidateSidecarError("validate_local.py.draft already exists; remove it or pass --force")

    text = legacy_path.read_text(encoding="utf-8")
    registrations = extract_registrations(text)
    if not registrations:
        raise PortValidateSidecarError("no register_validation_hook calls found in validate.local.sh")

    output_path = target_path if force else draft_path
    output_path.write_text(render_validate_local(registrations), encoding="utf-8")
    return output_path


def extract_registrations(text: str) -> list[HookRegistration]:
    """Extract legacy hook registrations and their bash function bodies."""
    function_bodies = _extract_function_bodies(text)
    seen_python_names: set[str] = set()
    registrations: list[HookRegistration] = []
    for hook_name, bash_function in _iter_registration_tokens(text):
        python_function = _unique_name(_sanitize_identifier(bash_function), seen_python_names)
        registrations.append(
            HookRegistration(
                hook_name=hook_name,
                bash_function=bash_function,
                python_function=python_function,
                bash_body=function_bodies.get(bash_function, ""),
            )
        )
    return registrations


def _iter_registration_tokens(text: str) -> list[tuple[str, str]]:
    registrations: list[tuple[str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("register_validation_hook"):
            continue
        try:
            tokens = shlex.split(stripped, comments=True, posix=True)
        except ValueError:
            continue
        if len(tokens) < 3 or tokens[0] != "register_validation_hook":
            continue
        registrations.append((tokens[1], tokens[2]))
    return registrations


def render_validate_local(registrations: list[HookRegistration]) -> str:
    """Render a valid Python sidecar skeleton."""
    blocks = [
        '"""Draft Python validation sidecar generated from validate.local.sh."""',
        "",
        "from __future__ import annotations",
        "",
        "from science_tool.validate import Result, Severity, hook",
        "",
        "",
    ]
    for registration in registrations:
        blocks.append(_render_hook(registration))
        blocks.append("")
        blocks.append("")
    return "\n".join(blocks).rstrip() + "\n"


def _extract_function_bodies(text: str) -> dict[str, str]:
    lines = text.splitlines()
    bodies: dict[str, str] = {}
    index = 0
    while index < len(lines):
        match = _FUNCTION_START_RE.match(lines[index])
        if match is None:
            index += 1
            continue

        start = index
        index += 1
        while index < len(lines) and not re.match(r"^\s*}\s*$", lines[index]):
            index += 1
        if index < len(lines):
            index += 1
        bodies[match.group("fn")] = "\n".join(lines[start:index])
    return bodies


def _render_hook(registration: HookRegistration) -> str:
    body = registration.bash_body or f"# Bash function body for {registration.bash_function!r} was not found."
    indented_body = "\n".join(f"    {line}" if line else "" for line in _triple_quote_safe(body).splitlines())
    return "\n".join(
        [
            f"@hook({json.dumps(registration.hook_name)})",
            f"def {registration.python_function}(ctx):",
            '    """TODO: port legacy bash validation hook.',
            "",
            f"    Original bash function: {registration.bash_function}",
            "",
            "    ```bash",
            indented_body,
            "    ```",
            '    """',
            "    _ = ctx, Result, Severity",
            "    return []",
        ]
    )


def _sanitize_identifier(name: str) -> str:
    sanitized = _INVALID_IDENTIFIER_CHAR_RE.sub("_", name).strip("_")
    if not sanitized:
        sanitized = "validation_hook"
    if sanitized[0].isdigit():
        sanitized = f"hook_{sanitized}"
    if keyword.iskeyword(sanitized):
        sanitized = f"{sanitized}_"
    if not _VALID_IDENTIFIER_RE.match(sanitized):
        raise AssertionError(f"invalid sanitized identifier: {sanitized}")
    return sanitized


def _unique_name(name: str, seen: set[str]) -> str:
    candidate = name
    suffix = 2
    while candidate in seen:
        candidate = f"{name}_{suffix}"
        suffix += 1
    seen.add(candidate)
    return candidate


def _triple_quote_safe(text: str) -> str:
    return text.replace('"""', r"\"\"\"")
