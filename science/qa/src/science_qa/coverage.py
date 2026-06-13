from __future__ import annotations

from dataclasses import dataclass, field

STATUS_RAN = "ran"
STATUS_EMPTY = "empty"
STATUS_BLOCKED = "blocked"
STATUS_NA = "not-applicable"

_IN_DENOMINATOR = {STATUS_RAN, STATUS_EMPTY, STATUS_BLOCKED}


@dataclass
class CoverageEntry:
    check_id: str
    aspect: str
    status: str
    columns: list[str]
    flag_count: int


@dataclass
class Coverage:
    entries: list[CoverageEntry] = field(default_factory=list)
    unconfigured_families: list[str] = field(default_factory=list)

    def executable_denominator(self) -> int:
        return sum(1 for e in self.entries if e.status in _IN_DENOMINATOR)

    def narrow_signal(self) -> list[str]:
        flagged = [e.check_id for e in self.entries if e.status in {STATUS_EMPTY, STATUS_BLOCKED}]
        return sorted(flagged + list(self.unconfigured_families))

    def to_dict(self) -> dict:
        # total-order key: families repeat a check_id, so disambiguate by resolved columns
        ordered = sorted(self.entries, key=lambda e: (e.check_id, tuple(e.columns)))
        counts = {s: sum(1 for e in self.entries if e.status == s)
                  for s in (STATUS_RAN, STATUS_EMPTY, STATUS_BLOCKED, STATUS_NA)}
        return {
            "executable_denominator": self.executable_denominator(),
            **counts,
            "unconfigured_families": sorted(self.unconfigured_families),
            "narrow_signal": self.narrow_signal(),
            "entries": [
                {"check_id": e.check_id, "aspect": e.aspect, "status": e.status,
                 "columns": list(e.columns), "flag_count": e.flag_count}
                for e in ordered
            ],
        }
