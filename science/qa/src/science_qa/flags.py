from __future__ import annotations

from dataclasses import dataclass

SEVERITY_STRUCTURAL = "structural"
SEVERITY_DISTRIBUTION = "distribution"


def build_flag_id(source: str, check: str, subject: str, side: str | None) -> str:
    """Namespaced, collision-resistant flag id: {source}/{check}/{subject}/{side}.

    `side` is `min`/`max` for two-sided checks; `None` collapses to `-`.
    """
    return f"{source}/{check}/{subject}/{side or '-'}"


@dataclass(frozen=True)
class Flag:
    source: str            # "generic" or a pack name, e.g. "scrna"
    check: str             # "range", "unique_key", "threshold", ...
    subject: str           # variable name, or a "+"-joined tuple for table-level checks
    side: str | None       # "min" | "max" | None
    severity: str          # SEVERITY_STRUCTURAL | SEVERITY_DISTRIBUTION
    value: str             # observed value, stringified for deterministic output
    threshold: str         # threshold/expectation, stringified
    message: str

    @property
    def flag_id(self) -> str:
        return build_flag_id(self.source, self.check, self.subject, self.side)

    def to_dict(self) -> dict[str, str]:
        return {
            "flag_id": self.flag_id,
            "source": self.source,
            "check": self.check,
            "subject": self.subject,
            "side": self.side or "-",
            "severity": self.severity,
            "value": self.value,
            "threshold": self.threshold,
            "message": self.message,
        }
