"""Rule and section declarations (design §6).

Declared beside the producer that emits them; the frozen registry is derived from
these declarations. There is no hand-maintained central table, so no repeated rule-id
string can drift.

`build()` is why a producer cannot emit an undeclared rule: the only supported way
to construct an `AuditFinding` in production code is through a declaration object.
"""

from __future__ import annotations

import re
import typing
from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from science_model.audit.evidence import Evidence
from science_model.audit.finding import AuditFinding, Severity
from science_model.audit.subjects import FindingSubject

_RULE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z0-9]+(?:-[a-z0-9]+)*)+$")
_SECTION_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

#: Identity qualifiers may only be these, or lists of these (design §3).
_ALLOWED_IDENTITY_TYPES: tuple[type, ...] = (str, bool, int)

Remediation = Literal["none", "producer"]
Visibility = Literal["visible", "hidden"]


class RuleDeclarationError(ValueError):
    """A rule declaration is malformed, or a finding violates the rule it names."""


class FindingSection(BaseModel):
    """A display grouping with an explicit order."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    title: str
    section_order: int

    @model_validator(mode="after")
    def _valid_id(self) -> "FindingSection":
        if not _SECTION_ID_RE.match(self.id):
            raise RuleDeclarationError(f"section id must be kebab-case, got {self.id!r}")
        return self


class FindingRule(BaseModel):
    """A declaration that constrains the findings a producer can emit."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    id: str
    severities: frozenset[Severity]
    subject_types: frozenset[str]
    identifier_namespaces: frozenset[str] = frozenset()
    qualifier_schema: type[BaseModel]
    identity_qualifiers: tuple[str, ...] = ()
    remediation: Remediation = "none"
    remediator: str | None = None

    title: str
    section: str
    display_order: int
    default_visibility: Visibility = "visible"

    @model_validator(mode="before")
    @classmethod
    def _freeze_sets(cls, data: object) -> object:
        if isinstance(data, dict):
            for key in ("severities", "subject_types", "identifier_namespaces"):
                if key in data and data[key] is not None:
                    data[key] = frozenset(data[key])
        return data

    @model_validator(mode="after")
    def _validate_declaration(self) -> "FindingRule":
        if not _RULE_ID_RE.match(self.id):
            raise RuleDeclarationError(
                f"rule id must be dotted kebab-case, got {self.id!r}"
            )
        if not self.severities:
            raise RuleDeclarationError(f"{self.id}: severities must not be empty")
        if not self.subject_types:
            raise RuleDeclarationError(f"{self.id}: subject_types must not be empty")
        if self.qualifier_schema.model_config.get("extra") != "forbid":
            raise RuleDeclarationError(
                f"{self.id}: qualifier schema {self.qualifier_schema.__name__} must set "
                "model_config extra='forbid'"
            )

        hints = typing.get_type_hints(self.qualifier_schema)
        for name in self.identity_qualifiers:
            if name not in hints:
                raise RuleDeclarationError(
                    f"{self.id}: identity qualifier {name!r} is not a field of "
                    f"{self.qualifier_schema.__name__}"
                )
            if not _identity_type_permitted(hints[name]):
                raise RuleDeclarationError(
                    f"{self.id}: identity qualifier {name!r} has type {hints[name]!r}; "
                    "only str, bool, int, and lists of those may bear identity (§3)"
                )
        if self.remediation == "producer" and not self.remediator:
            raise RuleDeclarationError(
                f"{self.id}: remediation='producer' requires a remediator name. There "
                "is deliberately no opt-out flag: a switch that turns this check off "
                "is a bypass of the check."
            )
        if self.remediation == "none" and self.remediator:
            raise RuleDeclarationError(
                f"{self.id}: names a remediator but declares remediation='none'"
            )
        return self

    def build(
        self,
        *,
        subject: FindingSubject,
        severity: Severity,
        qualifiers: Mapping[str, object],
        message: str,
        evidence: list[Evidence] | None = None,
    ) -> AuditFinding:
        """Construct an `AuditFinding` that cannot violate this rule."""
        finding = AuditFinding(
            rule_id=self.id,
            subject=subject,
            severity=severity,
            qualifiers=qualifiers,
            message=message,
            evidence=evidence or [],
        )
        if finding.severity not in self.severities:
            raise RuleDeclarationError(
                f"{self.id}: severity {finding.severity!r} is not in {set(self.severities)}"
            )
        if subject.type not in self.subject_types:
            raise RuleDeclarationError(
                f"{self.id}: subject type {subject.type!r} is not in "
                f"{set(self.subject_types)}"
            )
        if subject.type == "identifier" and self.identifier_namespaces:
            if subject.namespace not in self.identifier_namespaces:
                raise RuleDeclarationError(
                    f"{self.id}: namespace {subject.namespace!r} is not in "
                    f"{set(self.identifier_namespaces)}"
                )
        self.validate_qualifiers(qualifiers)
        self.identity_subset(qualifiers)
        return finding

    def validate_qualifiers(self, qualifiers: Mapping[str, object]) -> None:
        """Validate input against the declared schema strictly without coercing it."""
        try:
            self.qualifier_schema.model_validate(dict(qualifiers), strict=True)
        except ValidationError as exc:
            raise RuleDeclarationError(f"{self.id}: qualifiers invalid: {exc}") from exc

    def identity_subset(self, qualifiers: Mapping[str, object]) -> dict[str, object]:
        """Return the explicitly supplied identity-bearing qualifier subset."""
        missing = [key for key in self.identity_qualifiers if key not in qualifiers]
        if missing:
            raise RuleDeclarationError(
                f"{self.id}: identity qualifier(s) {missing} are declared but absent "
                "from the emitted qualifiers. An identity qualifier must be stated "
                "explicitly, even when the schema would default it: an omitted key and "
                "an explicit default produce different fingerprints."
            )
        return {key: qualifiers[key] for key in self.identity_qualifiers}


def _identity_type_permitted(hint: object) -> bool:
    """Permit only scalar identity values or ordered sequences of them."""
    if hint in _ALLOWED_IDENTITY_TYPES:
        return True
    origin = typing.get_origin(hint)
    if origin in (list, tuple):
        arguments = [argument for argument in typing.get_args(hint) if argument is not Ellipsis]
        return bool(arguments) and all(argument in _ALLOWED_IDENTITY_TYPES for argument in arguments)
    return False
