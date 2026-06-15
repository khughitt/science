"""Single source of truth for per-kind metadata (the kind descriptor manifest).

Every per-kind structure in the tool layer (path policies, default statuses,
status vocabularies, shortform aliases) derives from ``CORE_KINDS``. This module
is the kind SSOT and lives in ``science_model`` so the tool can depend on it.

Keystone scope: ``CORE_KINDS`` enumerates the file-authored core kinds only (the
kinds with a built-in path policy: markdown-authored kinds plus the two singletons).
Non-markdown ``EntityType`` members and the ``model_class`` / ``entity_class`` /
``template`` descriptor fields are deferred to later increments (design §6).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from science_model.profiles.schema import EntityFilenameStrategy  # noqa: F401  (canonical def moved to profiles.schema in Spec 2; re-exported so kinds.py stays the SSOT import site)


@dataclass(frozen=True)
class KindDescriptor:
    name: str  # canonical kind, e.g. "hypothesis"
    path: Path | None = None  # file home: a dir, or a file for singletons
    strategy: EntityFilenameStrategy | None = None  # filename strategy; None for non-file-authored kinds
    statuses: frozenset[str] | None = None  # controlled status vocab; None = open set
    default_status: str | None = None
    shortform: str | None = None  # single-letter alias, e.g. "h" -> hypothesis


CORE_KINDS: tuple[KindDescriptor, ...] = (
    KindDescriptor(
        name="question",
        path=Path("entities/questions"),
        strategy="numeric",
        statuses=frozenset({"active", "partially-answered", "answered", "deferred", "retired"}),
        default_status="active",
        shortform="q",
    ),
    KindDescriptor(
        name="hypothesis",
        path=Path("entities/hypotheses"),
        strategy="numeric",
        statuses=frozenset(
            {"proposed", "under-investigation", "partially-supported", "supported", "weakened", "refuted"}
        ),
        default_status="proposed",
        shortform="h",
    ),
    KindDescriptor(
        name="patch-definition",
        path=Path("entities/patches"),
        strategy="slug",
        statuses=frozenset({"active", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="proposition",
        path=Path("entities/propositions"),
        strategy="slug",
        statuses=frozenset({"draft", "active", "supported", "contested", "weakened", "retired", "superseded"}),
        default_status="draft",
        shortform="p",
    ),
    KindDescriptor(
        name="interpretation",
        path=Path("entities/interpretations"),
        strategy="numeric",
        statuses=frozenset({"active", "complete", "superseded"}),
        default_status="active",
        shortform="i",
    ),
    KindDescriptor(
        name="discussion",
        path=Path("entities/discussions"),
        strategy="numeric",
        statuses=frozenset({"active", "complete", "superseded"}),
        default_status="active",
        shortform="d",
    ),
    KindDescriptor(
        name="finding",
        path=Path("entities/findings"),
        strategy="numeric",
        statuses=frozenset({"active", "superseded", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="inquiry",
        path=Path("entities/inquiries"),
        strategy="numeric",
        statuses=frozenset({"active", "complete", "superseded"}),
        default_status="active",
    ),
    KindDescriptor(
        name="theme",
        path=Path("entities/themes"),
        strategy="numeric",
        statuses=frozenset({"draft", "active", "superseded", "retired"}),
        default_status="active",
        shortform="t",
    ),
    KindDescriptor(
        name="topic",
        path=Path("entities/topics"),
        strategy="slug",  # was "numeric" (4c: slug identity kind)
        statuses=frozenset({"active", "superseded", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="evidence-line",
        path=Path("entities/evidence-lines"),
        strategy="slug",
        statuses=frozenset({"draft", "active", "retired"}),
        default_status="draft",
    ),
    KindDescriptor(
        name="observation",
        path=Path("entities/observations"),
        strategy="slug",  # was "numeric": observations carry descriptive slug ids (e.g. observation:swan-stage-shift); enables id-preserving single-type aggregate retirement (§B5)
        statuses=frozenset({"active", "superseded", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="mechanism",
        path=Path("entities/mechanisms"),
        strategy="numeric",
        statuses=frozenset({"active", "superseded", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="synthesis",
        path=Path("entities/synthesis"),
        strategy="numeric",
        statuses=frozenset({"active", "superseded", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="report",
        path=Path("entities/reports"),
        strategy="numeric",
        statuses=frozenset({"active", "superseded", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="plan",
        path=Path("entities/plans"),
        strategy="numeric",
        statuses=frozenset({"active", "complete", "superseded", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="search",
        path=Path("entities/searches"),
        strategy="numeric",
        statuses=frozenset({"active", "complete", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="method",
        path=Path("entities/methods"),
        strategy="slug",  # was "numeric" (4c: slug identity kind)
        statuses=frozenset({"active", "superseded", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="pre-registration",
        path=Path("entities/pre-registrations"),
        strategy="numeric",
        statuses=frozenset({"active", "amended", "superseded", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="concept",
        path=Path("entities/concepts"),
        strategy="slug",
        statuses=frozenset({"active", "deprecated"}),
        default_status="active",
    ),
    KindDescriptor(
        name="construct",
        path=Path("entities/constructs"),
        strategy="slug",
        statuses=frozenset({"active", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="decision",
        path=Path("entities/decision"),
        strategy="verbatim",
        statuses=frozenset({"active", "superseded", "abandoned"}),
        default_status="active",
    ),
    KindDescriptor(
        name="paper",
        path=Path("entities/papers"),
        strategy="citekey",
        statuses=frozenset({"active", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="book",
        path=Path("entities/books"),
        strategy="citekey",
        statuses=frozenset({"active", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="talk",
        path=Path("entities/talks"),
        strategy="citekey",
        statuses=frozenset({"active", "retired"}),
        default_status="active",
    ),
    KindDescriptor(
        name="outcome",
        path=Path("entities/outcomes"),
        strategy="slug",
        statuses=frozenset({"active", "retired"}),
        default_status="active",
    ),
    # Singletons: `path` is the file path itself, not a directory. No per-instance
    # status vocabulary or default status.
    KindDescriptor(
        name="research-question",
        path=Path("entities/research-question.md"),
        strategy="singleton",
    ),
    KindDescriptor(
        name="claim-registry",
        path=Path("entities/claim-registry.yaml"),
        strategy="singleton",
    ),
)

CORE_KINDS_BY_NAME: dict[str, KindDescriptor] = {k.name: k for k in CORE_KINDS}
