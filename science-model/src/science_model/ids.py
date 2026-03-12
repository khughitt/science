"""Canonical identifier helpers for Science knowledge graph entities."""

from __future__ import annotations

from pydantic import BaseModel


class CanonicalId(BaseModel):
    """Canonical typed identifier shared across docs, tasks, and RDF."""

    kind: str
    slug: str

    @classmethod
    def parse(cls, raw: str) -> "CanonicalId":
        """Parse a `kind:slug` identifier into structured parts."""
        kind, slug = raw.split(":", 1)
        return cls(kind=kind, slug=slug)

    def __str__(self) -> str:
        return f"{self.kind}:{self.slug}"


def normalize_alias(raw: str, aliases: dict[str, str]) -> str:
    """Resolve a legacy alias to its canonical identifier when possible."""
    resolved = aliases.get(raw) or aliases.get(raw.lower())
    if resolved is not None:
        return resolved
    return raw if ":" in raw else raw.lower()
