"""Parser for the co-located `# science:code … # science:end` block."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml

_START = "science:code"
_END = "science:end"


@dataclass(frozen=True)
class CodeMetadata:
    """Three-state result of parsing a code file's metadata block.

    - absent: `present is False` (no block at all) — a ghost in Plan B.
    - invalid: `present is True` and `fields is None` with `error` set
      (unterminated, non-mapping, or malformed YAML) — a malformed block in Plan B.
    - valid: `present is True` and `fields` is the parsed mapping.
    """

    present: bool
    fields: dict[str, Any] | None
    error: str | None

    @property
    def valid(self) -> bool:
        return self.present and self.fields is not None and self.error is None


def _strip_comment(line: str) -> str:
    body = line.lstrip().lstrip("#")
    return body[1:] if body.startswith(" ") else body


def parse_code_metadata(text: str) -> CodeMetadata:
    """Parse the `# science:code … # science:end` block into a CodeMetadata.

    Delimiters are matched only after stripping the `#` comment prefix and must
    equal `science:code` / `science:end` exactly, so a sentinel inside a string
    or code (e.g. `print("science:code")`) never triggers parsing, and an
    earlier `science:end` cannot terminate before a real start. The body is
    parsed as YAML (after stripping a leading run of `#` and one space per line)
    so values get proper types (lists, bools). Works for any `#`-comment
    language in scope (Python, R, shell, Snakemake); non-`#` languages are out
    of scope while app_roots is unscanned.
    """
    started = False
    terminated = False
    body_lines: list[str] = []
    for raw_line in text.splitlines():
        marker = _strip_comment(raw_line).strip()
        if not started:
            if marker == _START:
                started = True
            continue
        if marker == _END:
            terminated = True
            break
        body_lines.append(_strip_comment(raw_line))
    if not started:
        return CodeMetadata(present=False, fields=None, error=None)
    if not terminated:
        return CodeMetadata(present=True, fields=None, error="unterminated science:code block (missing science:end)")
    try:
        loaded = yaml.safe_load("\n".join(body_lines)) if body_lines else {}
    except yaml.YAMLError as exc:
        return CodeMetadata(present=True, fields=None, error=f"invalid YAML in science:code block: {exc}")
    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        return CodeMetadata(present=True, fields=None, error="science:code block must be a mapping of fields")
    return CodeMetadata(present=True, fields={str(k): v for k, v in loaded.items()}, error=None)
