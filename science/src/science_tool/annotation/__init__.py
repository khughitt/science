# science/src/science_tool/annotation/__init__.py
"""Phase-3 annotation system: data model + sidecar I/O.

See docs/plans/historical/2026-05-10-annotation-system-spec.md.
"""

from science_tool.annotation.model import (
    Annotation,
    AuditLedger,
    Body,
    IriBody,
    Motivation,
    PriorState,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)

__all__ = [
    "Annotation",
    "AuditLedger",
    "Body",
    "IriBody",
    "Motivation",
    "PriorState",
    "Sidecar",
    "SpecificResource",
    "Status",
    "TextQuoteSelector",
    "TextualBody",
]
