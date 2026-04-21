"""SourceRef — first-class source-location metadata.

Per spec §Source Location and Error Reporting: the load pipeline must
preserve enough location information to produce actionable error messages.
SourceRef travels alongside entities during load and is embedded in error
messages for collisions and validation failures.
"""

from __future__ import annotations

from pydantic import BaseModel


class SourceRef(BaseModel):
    """A pointer to where an entity record came from."""

    adapter_name: str  # "markdown" | "aggregate" | "datapackage" | "task" | extension-defined
    path: str  # project-relative file path
    line: int | None = None  # line number / entry index where available

    def __str__(self) -> str:
        suffix = f":{self.line}" if self.line is not None else ""
        return f"[{self.adapter_name}] {self.path}{suffix}"
