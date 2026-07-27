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
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from science_model.audit.evidence import Evidence
from science_model.audit.finding import AuditFinding, Severity, thaw_json_value
from science_model.audit.fingerprint import (
    FingerprintError,
    normalize_identity_value,
)
from science_model.audit.subjects import (
    FindingSubject,
    normalize_identifier_namespace,
)

_RULE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z0-9]+(?:-[a-z0-9]+)*)+$")
_SECTION_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

#: Identity qualifiers may only be these, or lists of these (design §3).
_ALLOWED_IDENTITY_TYPES: tuple[type, ...] = (str, bool, int)

Remediation = Literal["none", "producer"]
Visibility = Literal["visible", "hidden"]
SubjectType = Literal["entity", "path", "identifier", "project"]


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
    subject_types: frozenset[SubjectType]
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
            data = dict(data)
            for key in ("severities", "subject_types", "identifier_namespaces"):
                if key in data and data[key] is not None:
                    data[key] = frozenset(data[key])
            if "identifier_namespaces" in data:
                data["identifier_namespaces"] = frozenset(
                    normalize_identifier_namespace(value)
                    for value in data["identifier_namespaces"]
                )
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
        if "identifier" in self.subject_types and not self.identifier_namespaces:
            raise RuleDeclarationError(
                f"{self.id}: identifier subject_types require nonempty "
                "identifier_namespaces"
            )
        if "identifier" not in self.subject_types and self.identifier_namespaces:
            raise RuleDeclarationError(
                f"{self.id}: identifier_namespaces are forbidden when identifier is "
                "not a permitted subject type"
            )
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
            evidence=tuple(evidence or ()),
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
        if subject.type == "identifier":
            if subject.namespace not in self.identifier_namespaces:
                raise RuleDeclarationError(
                    f"{self.id}: namespace {subject.namespace!r} is not in "
                    f"{set(self.identifier_namespaces)}"
                )
        self.validate_qualifiers(qualifiers)
        canonical_qualifiers = self.canonicalize_identity_qualifiers(
            finding.qualifiers
        )
        return AuditFinding(
            rule_id=finding.rule_id,
            subject=finding.subject,
            severity=finding.severity,
            qualifiers=canonical_qualifiers,
            message=finding.message,
            evidence=finding.evidence,
        )

    def validate_qualifiers(self, qualifiers: Mapping[str, object]) -> None:
        """Validate input against the declared schema strictly without coercing it."""
        try:
            thawed = cast(dict[str, object], thaw_json_value(qualifiers))
            self.qualifier_schema.model_validate(thawed, strict=True)
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
        try:
            return {
                key: normalize_identity_value(qualifiers[key])
                for key in self.identity_qualifiers
            }
        except FingerprintError as exc:
            raise RuleDeclarationError(
                f"{self.id}: identity qualifiers invalid: {exc}"
            ) from exc

    def canonicalize_identity_qualifiers(
        self, qualifiers: Mapping[str, object]
    ) -> dict[str, object]:
        """Canonicalize identity-bearing values in the full observed mapping."""
        thawed = cast(dict[str, object], thaw_json_value(qualifiers))
        thawed.update(self.identity_subset(qualifiers))
        return thawed


def _identity_type_permitted(hint: object) -> bool:
    """Permit only scalar identity values or ordered sequences of them."""
    if hint in _ALLOWED_IDENTITY_TYPES:
        return True
    origin = typing.get_origin(hint)
    if origin in (list, tuple):
        arguments = [argument for argument in typing.get_args(hint) if argument is not Ellipsis]
        return bool(arguments) and all(argument in _ALLOWED_IDENTITY_TYPES for argument in arguments)
    return False
