from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Sequence, cast

from science_model.audit import AuditFinding

from science_tool.validate.acceptance import (
    AcceptedValidationEntry,
    CurrentAcceptance,
    InvalidAcceptance,
    LegacyAcceptance,
    canonical_acceptance_severity,
    classify_acceptance_entry,
    entry_matches,
    legacy_validation_fields,
)

InstrumentStatus = Literal["ok", "empty", "unwired"]
MigrationVerdict = Literal[
    "migrated",
    "already-current",
    "invalid",
    "stale",
    "ambiguous",
    "duplicate",
    "indeterminate",
]


@dataclass(frozen=True)
class MigrationRow:
    finding: AuditFinding
    finding_id: str


@dataclass(frozen=True)
class EntryMigration:
    entry_index: int
    verdict: MigrationVerdict
    replacement: AcceptedValidationEntry | None
    detail: str


@dataclass(frozen=True)
class AcceptanceMigration:
    entries: tuple[EntryMigration, ...]
    indeterminate_producers: tuple[str, ...]

    @property
    def can_apply(self) -> bool:
        return all(entry.verdict in {"migrated", "already-current"} for entry in self.entries)

    @property
    def needs_write(self) -> bool:
        return self.can_apply and any(entry.verdict == "migrated" for entry in self.entries)

    @property
    def output_entries(self) -> tuple[AcceptedValidationEntry, ...]:
        if not self.can_apply:
            raise ValueError("migration cannot be applied")
        return tuple(cast(AcceptedValidationEntry, entry.replacement) for entry in self.entries)


def classify_migration(
    entries: Sequence[object],
    rows: Sequence[MigrationRow],
    producer_statuses: Mapping[str, InstrumentStatus],
) -> AcceptanceMigration:
    classified_entries = [classify_acceptance_entry(entry) for entry in entries]
    has_legacy_entry = any(isinstance(entry, LegacyAcceptance) for entry in classified_entries)
    indeterminate_producers = (
        tuple(
            sorted(
                producer_id
                for producer_id, status in producer_statuses.items()
                if status == "unwired"
            )
        )
        if has_legacy_entry
        else ()
    )
    migrated_entries: list[EntryMigration] = []

    for index, classified in enumerate(classified_entries):
        if isinstance(classified, CurrentAcceptance):
            migrated_entries.append(
                EntryMigration(
                    entry_index=index,
                    verdict="already-current",
                    replacement=classified.entry,
                    detail="entry is already current",
                )
            )
            continue
        if isinstance(classified, InvalidAcceptance):
            migrated_entries.append(
                EntryMigration(
                    entry_index=index,
                    verdict="invalid",
                    replacement=None,
                    detail=classified.error,
                )
            )
            continue

        if indeterminate_producers:
            migrated_entries.append(
                EntryMigration(
                    entry_index=index,
                    verdict="indeterminate",
                    replacement=None,
                    detail=(
                        "cannot migrate while validation producers are unwired: "
                        + ", ".join(indeterminate_producers)
                    ),
                )
            )
            continue

        legacy = dict(classified.raw)
        matches: list[MigrationRow] = []
        for row in rows:
            fields = legacy_validation_fields(row.finding)
            if entry_matches(
                legacy,
                rule=cast(str | None, fields["rule"]),
                severity=cast(str, fields["severity"]),
                path=cast(str | None, fields["path"]),
                task=cast(str | None, fields["task"]),
                message=cast(str, fields["message"]),
            ):
                matches.append(row)
        if not matches:
            migrated_entries.append(
                EntryMigration(index, "stale", None, "matched no current findings")
            )
            continue
        if len(matches) > 1:
            migrated_entries.append(
                EntryMigration(
                    index,
                    "ambiguous",
                    None,
                    f"matched {len(matches)} current findings",
                )
            )
            continue

        severity = canonical_acceptance_severity(legacy.get("severity"))
        scope = ["warn", "error"] if severity is None else [severity]
        replacement = AcceptedValidationEntry.model_validate(
            {
                "finding_id": matches[0].finding_id,
                "fingerprint_version": 1,
                "severity_scope": scope,
                "reason": legacy["reason"],
            }
        )
        migrated_entries.append(
            EntryMigration(
                index,
                "migrated",
                replacement,
                "matched exactly one current finding",
            )
        )

    indices_by_finding_id: dict[str, list[int]] = {}
    for index, entry in enumerate(migrated_entries):
        if entry.replacement is not None:
            indices_by_finding_id.setdefault(entry.replacement.finding_id, []).append(index)
    for indices in indices_by_finding_id.values():
        if len(indices) < 2:
            continue
        for index in indices:
            entry = migrated_entries[index]
            migrated_entries[index] = EntryMigration(
                entry.entry_index,
                "duplicate",
                entry.replacement,
                "multiple acceptance entries resolve to the same finding_id",
            )

    return AcceptanceMigration(tuple(migrated_entries), indeterminate_producers)
