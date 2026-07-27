# AuditFinding Convergence — Plan 1: The Contract

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the audit-finding contract — payload, subject union, frozen fingerprint, record, storage, rule registry, report wire types, and trusted ingestion — converting no existing producer.

**Architecture:** New Pydantic models in `science-model` under `science_model/audit/`, with the registry, storage, ingestion, and CLI in `science_tool/findings/`. Nothing in this plan touches an existing health check, `count_issues`, or any renderer, so the suite stays green throughout. The uniform-channel ratchet is *declared* here and *enforced* in Plan 2, which is the atomic convergence landing.

**Tech Stack:** Python 3.12+, Pydantic v2, Click, pytest. `science-model` has no dependency on `science_tool`; the dependency runs one way only.

**Design:** [`2026-07-27-finding-convergence-design.md`](2026-07-27-finding-convergence-design.md), revision 6. Section references below (§1, §3, …) are to that document.

## Global Constraints

- **`science_model/audit/` imports nothing from `science_tool`.** The model package is consumed by the tool package, never the reverse.
- **Run tests from the package directory.** `cd science && uv run --frozen pytest` for tool tests; `cd science/model && uv run --frozen pytest` for model tests. Running `uv run` from the repo root is the most common orientation mistake and does not work — there is no root `pyproject.toml`.
- **Never run the full suite in this plan's tasks.** It is ~10k tests and ~2-3 min, over the 120s default timeout. Run the scoped selection each task names.
- **Lint and types from `science/`:** `uv run ruff check` and `uv run pyright`. Pyright is configured once by `pyrightconfig.json` at the repo root and covers all three source trees; test directories are not type-checked.
- **Fingerprint domain prefix is exactly `science.finding.v1\n`** (§3). Occurrence keys use `science.occurrence.v1\n`, reviews `science.review.v1\n`, acceptance keys `science.acceptance.v1\n`.
- **Digests are 64 lowercase hex characters.** The acceptance key alone is truncated to 32 (§10).
- **All new Pydantic models set `model_config = ConfigDict(extra="forbid", frozen=True)`** unless a task says otherwise. `Entity` uses `extra="ignore"`, which is why a hand-written `phase:` could never reach the graph; audit records must not repeat that.
- **Conventional commits.** No AI-attribution trailer or footer on any commit.
- **No "legacy" or "compatibility" shims**, and no `Unified` prefix on any component name.

## File Structure

**`science/model/src/science_model/audit/`** — new package, the wire and storage contract.

| File | Responsibility |
|---|---|
| `__init__.py` | Public re-exports only. |
| `subjects.py` | The four subject variants and their normalization (§2). |
| `evidence.py` | `LocationEvidence` / `TextEvidence` and bounds (§1). |
| `fingerprint.py` | Canonical encoding, normalization, and the v1 digest (§3). |
| `finding.py` | The `AuditFinding` payload (§1). |
| `rules.py` | `FindingRule`, `FindingSection`, declaration-time validation (§6). |
| `record.py` | `AuditFindingRecord`, `Occurrence`, `Transition`, `Review` (§4). |
| `report.py` | `ReportedFinding`, `AcceptedFinding`, `AuditReport` (§11). |

**`science/src/science_tool/findings/`** — new package, the tool-side machinery.

| File | Responsibility |
|---|---|
| `__init__.py` | Empty; the package is import-side-effect free. |
| `producers.py` | Producer registration and the derived frozen registry (§6). |
| `storage.py` | Case-file path mapping, atomic write, loader with filename binding (§5). |
| `ingest.py` | Report validation, project lock, upsert, idempotency (§8). |
| `cli.py` | `science findings ingest` / `list` (§8). |

**Tests** live in `science/model/tests/` and `science/tests/` respectively, matching each package's existing layout.

---

### Task 1: Subject union

**Files:**
- Create: `science/model/src/science_model/audit/__init__.py`
- Create: `science/model/src/science_model/audit/subjects.py`
- Test: `science/model/tests/test_audit_subjects.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `EntitySubject`, `PathSubject`, `IdentifierSubject`, `ProjectSubject`, `FindingSubject` (the union), `SubjectError`, and `normalize_project_path(raw: str) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# science/model/tests/test_audit_subjects.py
import pytest
from pydantic import ValidationError

from science_model.audit.subjects import (
    EntitySubject,
    IdentifierSubject,
    PathSubject,
    ProjectSubject,
    normalize_project_path,
)


def test_entity_subject_requires_prefixed_ref():
    assert EntitySubject(ref="dataset:gtex-v8").ref == "dataset:gtex-v8"
    with pytest.raises(ValidationError):
        EntitySubject(ref="gtex-v8")


def test_path_subject_normalizes_separators_and_strips_trailing_slash():
    assert PathSubject(path="entities/papers/").path == "entities/papers"
    assert PathSubject(path="./science.yaml").path == "science.yaml"


def test_path_subject_refuses_absolute_and_any_traversal_segment():
    for bad in (
        "/etc/passwd",
        "../outside.md",
        "entities/../../escape.md",
        # Refused, NOT collapsed to "b": a traversal segment is rejected outright, so
        # no path that mentions `..` is ever accepted on the strength of where it
        # happens to land.
        "a/../b",
        "a/b/..",
    ):
        with pytest.raises(ValidationError):
            PathSubject(path=bad)


def test_path_subject_pointer_forbids_positional_segments():
    PathSubject(path="science.yaml", pointer="health.accepted_validation")
    with pytest.raises(ValidationError):
        PathSubject(path="science.yaml", pointer="health.accepted_validation[3]")


def test_identifier_subject_lowercases_namespace_and_requires_value():
    subject = IdentifierSubject(namespace="Managed-Artifact", value="validate.sh")
    assert subject.namespace == "managed-artifact"
    with pytest.raises(ValidationError):
        IdentifierSubject(namespace="managed-artifact", value="")


def test_project_subject_carries_no_other_field():
    assert ProjectSubject().type == "project"
    with pytest.raises(ValidationError):
        ProjectSubject(ref="anything")


def test_normalize_project_path_is_idempotent():
    once = normalize_project_path("entities//papers/./x.md")
    assert once == "entities/papers/x.md"
    assert normalize_project_path(once) == once
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_audit_subjects.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_model.audit'`

- [ ] **Step 3: Write minimal implementation**

```python
# science/model/src/science_model/audit/__init__.py
"""Audit-finding contract: the shared payload deterministic checks and agentic
lenses both emit, and the project-state case it is stored as.

Deliberately NOT an entity kind. `EntityKind.FINDING` is a live epistemic kind
meaning "propositions grounded by observations"; an audit finding is a case about
repository or corpus hygiene and never reaches the knowledge graph, belief, or
attention. See docs/plans/2026-07-27-finding-convergence-design.md §5.
"""
```

```python
# science/model/src/science_model/audit/subjects.py
"""The four finding subjects (design §2).

One REQUIRED, discriminated primary subject. There is deliberately no
entity-then-path fallback: an invalid entity subject fails rather than silently
degrading to a path, which would change a case's identity unnoticed.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

_ENTITY_REF_RE = re.compile(r"^[a-z][a-z0-9-]*:[A-Za-z0-9._-]+$")
_POSITIONAL_RE = re.compile(r"\[\d+\]")
_NAMESPACE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

MAX_POINTER_LENGTH = 200


class SubjectError(ValueError):
    """A subject could not be normalized or is not permitted."""


def normalize_project_path(raw: str) -> str:
    """Project-relative POSIX form.

    A `..` segment is REFUSED, never collapsed. `a/../b` does not become `b`: the
    design forbids traversal segments, and normalizing one away would accept a path
    on the strength of where it happens to land rather than on what it says. `.` and
    duplicate separators are collapsed, because neither is traversal.
    """
    candidate = raw.replace("\\", "/")
    if candidate.startswith("/"):
        raise SubjectError(f"path must be project-relative, got {raw!r}")
    segments = [s for s in candidate.split("/") if s not in ("", ".")]
    if any(segment == ".." for segment in segments):
        raise SubjectError(
            f"path contains a `..` segment and is refused, not normalized: {raw!r}"
        )
    if not segments:
        raise SubjectError(f"path names no file, got {raw!r}")
    return "/".join(segments)


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EntitySubject(_Base):
    type: Literal["entity"] = "entity"
    ref: str

    @field_validator("ref")
    @classmethod
    def _canonical_ref(cls, value: str) -> str:
        if not _ENTITY_REF_RE.match(value):
            raise SubjectError(f"entity ref must be `<prefix>:<slug>`, got {value!r}")
        return value


class PathSubject(_Base):
    type: Literal["path"] = "path"
    path: str
    pointer: str | None = None

    @field_validator("path")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return normalize_project_path(value)

    @field_validator("pointer")
    @classmethod
    def _stable_pointer(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            raise SubjectError("pointer must not be blank; omit it instead")
        if len(value) > MAX_POINTER_LENGTH:
            raise SubjectError(f"pointer exceeds {MAX_POINTER_LENGTH} characters")
        if _POSITIONAL_RE.search(value):
            raise SubjectError(
                f"pointer {value!r} contains a positional segment; identity must not "
                "depend on list position (design §2)"
            )
        return value


class IdentifierSubject(_Base):
    type: Literal["identifier"] = "identifier"
    namespace: str
    value: str

    @field_validator("namespace")
    @classmethod
    def _lower_namespace(cls, value: str) -> str:
        lowered = value.lower()
        if not _NAMESPACE_RE.match(lowered):
            raise SubjectError(f"namespace must be kebab-case, got {value!r}")
        return lowered

    @field_validator("value")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value.strip():
            raise SubjectError("identifier value must not be blank")
        return value


class ProjectSubject(_Base):
    type: Literal["project"] = "project"


FindingSubject = Annotated[
    Union[EntitySubject, PathSubject, IdentifierSubject, ProjectSubject],
    Field(discriminator="type"),
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science/model && uv run --frozen pytest tests/test_audit_subjects.py -v`
Expected: PASS, 7 tests

Then: `cd science && uv run ruff check && uv run pyright`
Expected: no findings

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/audit/ science/model/tests/test_audit_subjects.py
git commit -m "feat(audit): the four finding subjects, discriminated with no fallback"
```

---

### Task 2: Evidence union

**Files:**
- Create: `science/model/src/science_model/audit/evidence.py`
- Test: `science/model/tests/test_audit_evidence.py`

**Interfaces:**
- Consumes: `normalize_project_path`, `SubjectError` from Task 1.
- Produces: `LocationEvidence`, `TextEvidence`, `Span`, `Evidence` (union), `MAX_EVIDENCE_ENTRIES = 100`, `MAX_TEXT_LENGTH = 4000`, `MAX_LABEL_LENGTH = 200`.

Note the deliberate difference from Task 1: `LocationEvidence.pointer` **permits** positional segments, because evidence is not identity-bearing (§1).

- [ ] **Step 1: Write the failing test**

```python
# science/model/tests/test_audit_evidence.py
import pytest
from pydantic import ValidationError

from science_model.audit.evidence import LocationEvidence, Span, TextEvidence


def test_location_evidence_normalizes_path_and_refuses_traversal():
    assert LocationEvidence(path="./src/x.py").path == "src/x.py"
    with pytest.raises(ValidationError):
        LocationEvidence(path="../outside.py")


def test_location_pointer_permits_positional_segments():
    # Unlike PathSubject.pointer: evidence is not identity-bearing.
    assert LocationEvidence(path="science.yaml", pointer="health.x[3]").pointer


def test_line_is_one_based():
    assert LocationEvidence(path="a.py", line=1).line == 1
    with pytest.raises(ValidationError):
        LocationEvidence(path="a.py", line=0)


def test_line_and_span_are_mutually_exclusive():
    with pytest.raises(ValidationError):
        LocationEvidence(path="a.py", line=3, span=Span(start_line=3, end_line=4))


def test_span_ends_are_inclusive_and_ordered():
    Span(start_line=3, end_line=3)
    with pytest.raises(ValidationError):
        Span(start_line=5, end_line=4)
    with pytest.raises(ValidationError):
        Span(start_line=0, end_line=1)


def test_span_columns_are_paired():
    Span(start_line=1, end_line=1, start_col=2, end_col=4)
    with pytest.raises(ValidationError):
        Span(start_line=1, end_line=1, start_col=2)
    with pytest.raises(ValidationError):
        Span(start_line=1, end_line=1, start_col=4, end_col=2)


def test_text_evidence_bounds():
    TextEvidence(text="x" * 4000)
    with pytest.raises(ValidationError):
        TextEvidence(text="x" * 4001)
    with pytest.raises(ValidationError):
        TextEvidence(text="ok", label="y" * 201)


def test_unknown_fields_are_refused_not_ignored():
    with pytest.raises(ValidationError):
        LocationEvidence(path="a.py", lien=3)
    with pytest.raises(ValidationError):
        TextEvidence(text="ok", labl="x")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_audit_evidence.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_model.audit.evidence'`

- [ ] **Step 3: Write minimal implementation**

```python
# science/model/src/science_model/audit/evidence.py
"""Supporting evidence on a finding (design §1).

A discriminated union, not a free-form list: ingestion validates every evidence
path, which is impossible against a list that cannot tell a path from prose.

`extra="forbid"` on both variants is deliberate. `Entity` uses `extra="ignore"`,
which is why a hand-written `phase:` could be written and never reach the graph.
A silently dropped field on an audit record would cost the same diagnosis.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from science_model.audit.subjects import normalize_project_path

MAX_EVIDENCE_ENTRIES = 100
MAX_TEXT_LENGTH = 4000
MAX_LABEL_LENGTH = 200
MAX_POINTER_LENGTH = 200


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Span(_Base):
    """A 1-based, END-INCLUSIVE region. Columns are optional as a PAIR."""

    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    start_col: int | None = Field(default=None, ge=1)
    end_col: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _ordered(self) -> "Span":
        if self.end_line < self.start_line:
            raise ValueError("end_line must be >= start_line")
        if (self.start_col is None) != (self.end_col is None):
            raise ValueError(
                "start_col and end_col are optional as a pair; supplying one without "
                "the other is ambiguous"
            )
        if (
            self.start_col is not None
            and self.end_col is not None
            and self.start_line == self.end_line
            and self.end_col < self.start_col
        ):
            raise ValueError("on a single line, end_col must be >= start_col")
        return self


class LocationEvidence(_Base):
    type: Literal["location"] = "location"
    path: str
    pointer: str | None = None
    line: int | None = Field(default=None, ge=1)
    span: Span | None = None

    @field_validator("path")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return normalize_project_path(value)

    @field_validator("pointer")
    @classmethod
    def _bounded_pointer(cls, value: str | None) -> str | None:
        # Positional segments ARE permitted here: evidence is not identity-bearing.
        if value is not None and len(value) > MAX_POINTER_LENGTH:
            raise ValueError(f"pointer exceeds {MAX_POINTER_LENGTH} characters")
        return value

    @model_validator(mode="after")
    def _line_xor_span(self) -> "LocationEvidence":
        if self.line is not None and self.span is not None:
            raise ValueError(
                "line and span are mutually exclusive; supplying both is rejected "
                "rather than resolved by precedence"
            )
        return self


class TextEvidence(_Base):
    type: Literal["text"] = "text"
    label: str | None = Field(default=None, max_length=MAX_LABEL_LENGTH)
    text: str = Field(max_length=MAX_TEXT_LENGTH)


Evidence = Annotated[Union[LocationEvidence, TextEvidence], Field(discriminator="type")]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science/model && uv run --frozen pytest tests/test_audit_evidence.py -v`
Expected: PASS, 8 tests

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/audit/evidence.py science/model/tests/test_audit_evidence.py
git commit -m "feat(audit): freeze the evidence wire types, forbidding unknown fields"
```

---

### Task 3: Fingerprint v1

**Files:**
- Create: `science/model/src/science_model/audit/fingerprint.py`
- Test: `science/model/tests/test_audit_fingerprint.py`

**Interfaces:**
- Consumes: `FindingSubject` from Task 1.
- Produces: `FINDING_DOMAIN = "science.finding.v1"`, `FINGERPRINT_VERSION = 1`, `canonical_json(value: object) -> bytes`, `finding_fingerprint(*, rule_id: str, subject: FindingSubject, identity_qualifiers: Mapping[str, object]) -> str`, `rule_slug(rule_id: str) -> str`, `FingerprintError`.

The golden vectors in Step 1 are the frozen API (§3). Changing normalization must break this test.

- [ ] **Step 1: Write the failing test**

```python
# science/model/tests/test_audit_fingerprint.py
import pytest

from science_model.audit.fingerprint import (
    FingerprintError,
    canonical_json,
    finding_fingerprint,
    rule_slug,
)
from science_model.audit.subjects import (
    EntitySubject,
    IdentifierSubject,
    PathSubject,
    ProjectSubject,
)

# Golden vectors. These bytes are an API: they are persisted in case filenames and in
# consumers' science.yaml. Changing normalization MUST break this test.
#
# Each entry pins BOTH the canonical byte string AND the digest. The digests were
# produced by coreutils `sha256sum`, NOT by this implementation — see Step 4 for the
# exact command. An implementation checked against its own output is its own oracle
# and can only ever confirm that it is self-consistent.
GOLDEN = (
    (
        "entity",
        "dataset.cached-field-drift",
        EntitySubject(ref="dataset:gtex-v8"),
        {"field": "year"},
        '{"qualifiers":{"field":"year"},"rule_id":"dataset.cached-field-drift",'
        '"subject":{"ref":"dataset:gtex-v8","type":"entity"}}',
        "4c88cbe7b7951a0f68c084ab403a662440ab8432958501e2dc873a9a0469cf9f",
    ),
    (
        "path-with-pointer",
        "tags.lingering",
        PathSubject(path="doc/x.md", pointer="frontmatter.tags"),
        {},
        '{"qualifiers":{},"rule_id":"tags.lingering","subject":{"path":"doc/x.md",'
        '"pointer":"frontmatter.tags","type":"path"}}',
        "e21c72e84b7f48fdca1ae72fafb38d92b1611d7f20e87223d0e3bfc03f1abc3f",
    ),
    (
        "project-two-qualifiers",
        "layered-claim.coverage-incomplete",
        ProjectSubject(),
        {"coverage": "proposition_claim_layer", "threshold": 1},
        '{"qualifiers":{"coverage":"proposition_claim_layer","threshold":1},'
        '"rule_id":"layered-claim.coverage-incomplete","subject":{"type":"project"}}',
        "c0e10a4a0c9647f84c922addd40c7356ef6e78a2639b417d063d7d6926f9bd17",
    ),
)


def test_canonical_json_sorts_keys_and_omits_whitespace():
    assert canonical_json({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def test_canonical_json_omits_absent_fields_rather_than_nulling_them():
    assert canonical_json({"a": 1, "b": None}) == b'{"a":1}'


def test_canonical_json_preserves_array_order():
    assert canonical_json({"a": ["z", "y"]}) == b'{"a":["z","y"]}'


def test_fingerprint_is_64_lowercase_hex():
    digest = finding_fingerprint(
        rule_id="refs.unresolved",
        subject=IdentifierSubject(namespace="reference", value="dataset:missing"),
        identity_qualifiers={},
    )
    assert len(digest) == 64
    assert digest == digest.lower()
    assert all(c in "0123456789abcdef" for c in digest)


def test_fingerprint_is_stable_across_qualifier_insertion_order():
    a = finding_fingerprint(
        rule_id="r", subject=ProjectSubject(), identity_qualifiers={"x": 1, "y": 2}
    )
    b = finding_fingerprint(
        rule_id="r", subject=ProjectSubject(), identity_qualifiers={"y": 2, "x": 1}
    )
    assert a == b


def test_fingerprint_differs_by_subject_variant_for_the_same_string():
    path = finding_fingerprint(
        rule_id="r", subject=PathSubject(path="a.md"), identity_qualifiers={}
    )
    ident = finding_fingerprint(
        rule_id="r",
        subject=IdentifierSubject(namespace="reference", value="a.md"),
        identity_qualifiers={},
    )
    assert path != ident


def test_fingerprint_rejects_float_null_and_nested_qualifiers():
    for bad in ({"x": 1.5}, {"x": None}, {"x": {"nested": 1}}):
        with pytest.raises(FingerprintError):
            finding_fingerprint(
                rule_id="r", subject=ProjectSubject(), identity_qualifiers=bad
            )


def test_fingerprint_accepts_str_bool_int_and_arrays_of_those():
    finding_fingerprint(
        rule_id="r",
        subject=ProjectSubject(),
        identity_qualifiers={"s": "a", "b": True, "i": 3, "l": ["a", "b"]},
    )


def test_rule_slug_is_frozen():
    assert rule_slug("dataset.cached-field-drift") == "dataset-cached-field-drift"
    assert rule_slug("prose_lints.hit") == "prose-lints-hit"
    assert rule_slug("a..__b") == "a-b"
    assert rule_slug("-x-") == "x"
    assert len(rule_slug("a" * 100)) == 60


@pytest.mark.parametrize(
    ("name", "rule_id", "subject", "quals", "expected_bytes", "expected_digest"), GOLDEN
)
def test_canonical_bytes_are_frozen(
    name, rule_id, subject, quals, expected_bytes, expected_digest
):
    """Pin the ENCODING independently of the hash, so a break says which one moved."""
    payload = {
        "rule_id": rule_id,
        "subject": subject.model_dump(mode="json", exclude_none=True),
        "qualifiers": quals,
    }
    assert canonical_json(payload).decode("utf-8") == expected_bytes, (
        f"golden vector {name!r}: canonical encoding changed. Fingerprint v1 is frozen "
        "(design §3); a deliberate change requires a v2 domain prefix, not an edit."
    )


@pytest.mark.parametrize(
    ("name", "rule_id", "subject", "quals", "expected_bytes", "expected_digest"), GOLDEN
)
def test_golden_digests_match_an_independent_oracle(
    name, rule_id, subject, quals, expected_bytes, expected_digest
):
    """The expected digests came from coreutils `sha256sum`, not from this code."""
    actual = finding_fingerprint(
        rule_id=rule_id, subject=subject, identity_qualifiers=quals
    )
    assert actual == expected_digest, (
        f"golden vector {name!r}: digest changed. Fingerprint v1 is frozen (design §3)."
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_audit_fingerprint.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_model.audit.fingerprint'`

- [ ] **Step 3: Write minimal implementation**

```python
# science/model/src/science_model/audit/fingerprint.py
"""Fingerprint v1 — frozen (design §3).

The digest is an API. It is persisted in case filenames and in consumers'
`science.yaml` acceptance entries, so its observable bytes cannot change without a
new domain prefix. A future v2 normalization produces DISJOINT identities by
construction rather than silently colliding with v1.

Identity inputs, and only these: rule id, subject, and the rule-declared identity
qualifier subset. Excluded: date, model, lens, run id, producer, prose, message,
severity, evidence, line numbers, and list positions.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping
from typing import Any

from science_model.audit.subjects import FindingSubject

FINDING_DOMAIN = "science.finding.v1"
FINGERPRINT_VERSION = 1

MAX_SLUG_LENGTH = 60

_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


class FingerprintError(ValueError):
    """A value cannot participate in an identity."""


def _normalize_scalar(value: Any) -> Any:
    """Permit str / bool / int and arrays of those. Nothing else.

    Floats are refused so no identity depends on float formatting; nulls are refused
    because §3 omits absent fields rather than encoding them; nested objects are
    refused so no identity depends on a nested key order.
    """
    if isinstance(value, bool):  # before int — bool is a subclass of int
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, (list, tuple)):
        return [_normalize_scalar(item) for item in value]
    raise FingerprintError(
        f"identity qualifier value of type {type(value).__name__} is not permitted; "
        "use str, bool, int, or an array of those (design §3)"
    )


def _prune(value: object) -> object:
    """Drop ``None`` members at EVERY level, never encode them as null (§3)."""
    if isinstance(value, Mapping):
        return {k: _prune(v) for k, v in value.items() if v is not None}
    if isinstance(value, (list, tuple)):
        return [_prune(item) for item in value]
    return value


def canonical_json(value: object) -> bytes:
    """UTF-8 JSON, keys sorted by code point, no insignificant whitespace.

    Pruning is RECURSIVE. A shallow prune would encode a nested absent field as null
    while `model_dump(exclude_none=True)` omitted it, so the same logical value would
    have two encodings depending on which path produced it.
    """
    return json.dumps(
        _prune(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def finding_fingerprint(
    *,
    rule_id: str,
    subject: FindingSubject,
    identity_qualifiers: Mapping[str, object],
) -> str:
    """The v1 digest: 64 lowercase hex characters."""
    payload = {
        "rule_id": unicodedata.normalize("NFC", rule_id),
        "subject": subject.model_dump(mode="json", exclude_none=True),
        "qualifiers": {
            key: _normalize_scalar(val) for key, val in sorted(identity_qualifiers.items())
        },
    }
    digest = hashlib.sha256(f"{FINDING_DOMAIN}\n".encode("utf-8") + canonical_json(payload))
    return digest.hexdigest()


def rule_slug(rule_id: str) -> str:
    """Frozen transformation used in case filenames (design §3).

    Lowercase; `.`/`_`/any character outside [a-z0-9-] becomes `-`; runs of `-`
    collapse; leading and trailing `-` are stripped; truncated to 60 characters.
    """
    collapsed = _SLUG_STRIP_RE.sub("-", rule_id.lower()).strip("-")
    return collapsed[:MAX_SLUG_LENGTH].rstrip("-")
```

- [ ] **Step 4: Run tests to verify they pass against the independent oracle**

Run: `cd science/model && uv run --frozen pytest tests/test_audit_fingerprint.py -v`
Expected: PASS, 15 tests (9 unparametrized + 2 × 3 golden vectors)

**Do not paste implementation output into the test.** The three digests in `GOLDEN`
were produced by coreutils `sha256sum` over the pinned byte strings — a different
implementation of SHA-256 than Python's `hashlib`. That independence is what lets the
test detect a *wrong* implementation rather than merely a *changed* one.

To re-derive them yourself, or to add a fourth vector, run the byte string through
`sha256sum` with the domain prefix and no trailing newline:

```bash
printf 'science.finding.v1\n%s' \
  '{"qualifiers":{"field":"year"},"rule_id":"dataset.cached-field-drift","subject":{"ref":"dataset:gtex-v8","type":"entity"}}' \
  | sha256sum
# 4c88cbe7b7951a0f68c084ab403a662440ab8432958501e2dc873a9a0469cf9f  -
```

If `test_canonical_bytes_are_frozen` fails but `test_golden_digests_match_an_independent_oracle`
also fails, the encoding moved. If only the digest test fails, the hashing step moved.
Splitting them is what makes the failure diagnostic instead of merely red.

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/audit/fingerprint.py science/model/tests/test_audit_fingerprint.py
git commit -m "feat(audit): freeze fingerprint v1 with golden vectors"
```

---

### Task 4: `AuditFinding` payload

**Files:**
- Create: `science/model/src/science_model/audit/finding.py`
- Test: `science/model/tests/test_audit_finding.py`

**Interfaces:**
- Consumes: `FindingSubject` (Task 1), `Evidence` / `MAX_EVIDENCE_ENTRIES` (Task 2).
- Produces: `AuditFinding`, `Severity` (`Literal["error", "warn", "info"]`), `normalize_severity(raw: str) -> str`, `QualifierMap` (the frozen-mapping annotation reused by `record.py`).

`rule_id` is a **string** on the wire (§1); producer-side factories take a `FindingRule` object and derive it (Task 5).

- [ ] **Step 1: Write the failing test**

```python
# science/model/tests/test_audit_finding.py
import pytest
from pydantic import ValidationError

from science_model.audit.evidence import LocationEvidence, TextEvidence
from science_model.audit.finding import AuditFinding, normalize_severity
from science_model.audit.subjects import EntitySubject


def _finding(**overrides):
    base = dict(
        rule_id="dataset.cached-field-drift",
        subject=EntitySubject(ref="dataset:gtex-v8"),
        severity="warn",
        qualifiers={"field": "year"},
        message="cached year 2019 differs from source 2020",
        evidence=[],
    )
    return AuditFinding(**{**base, **overrides})


def test_rule_id_is_a_string_on_the_wire():
    assert _finding().model_dump(mode="json")["rule_id"] == "dataset.cached-field-drift"


def test_severity_normalizes_warning_to_warn():
    assert normalize_severity("warning") == "warn"
    assert normalize_severity("warn") == "warn"
    assert _finding(severity="warning").severity == "warn"


def test_unknown_severity_is_refused():
    with pytest.raises(ValidationError):
        _finding(severity="critical")


def test_evidence_collection_bound_is_enforced():
    ok = [TextEvidence(text=str(i)) for i in range(100)]
    _finding(evidence=ok)
    with pytest.raises(ValidationError):
        _finding(evidence=ok + [TextEvidence(text="101")])


def test_evidence_round_trips_as_a_discriminated_union():
    finding = _finding(
        evidence=[LocationEvidence(path="a.py", line=3), TextEvidence(text="note")]
    )
    reloaded = AuditFinding.model_validate(finding.model_dump(mode="json"))
    assert reloaded == finding


def test_unknown_field_is_refused():
    with pytest.raises(ValidationError):
        _finding(rule="dataset.cached-field-drift")


def test_qualifiers_cannot_be_mutated_in_place():
    # `frozen=True` is SHALLOW. Qualifiers bear identity, so an in-place edit would
    # change what the finding IS while every derived id kept saying otherwise.
    finding = _finding()
    with pytest.raises(TypeError):
        finding.qualifiers["field"] = "month"      # type: ignore[index]
    with pytest.raises(TypeError):
        del finding.qualifiers["field"]            # type: ignore[attr-defined]
    assert finding.qualifiers == {"field": "year"}


def test_a_qualifier_mapping_is_copied_not_aliased():
    # A proxy over a dict the caller still holds is not immutable.
    source = {"field": "year"}
    finding = _finding(qualifiers=source)
    source["field"] = "month"
    assert finding.qualifiers["field"] == "year"


def test_an_omitted_qualifier_mapping_is_frozen_too():
    # Pydantic does not validate defaults unless told to; without `validate_default`
    # this one would be a plain mutable dict.
    finding = _finding(qualifiers={})
    bare = AuditFinding(
        rule_id="dataset.cached-field-drift",
        subject=EntitySubject(ref="dataset:gtex-v8"),
        severity="warn",
        message="m",
    )
    assert bare.qualifiers == finding.qualifiers == {}
    with pytest.raises(TypeError):
        bare.qualifiers["sneak"] = 1              # type: ignore[index]


def test_qualifiers_serialize_as_a_plain_dict():
    dumped = _finding().model_dump(mode="json")["qualifiers"]
    assert type(dumped) is dict
    assert dumped == {"field": "year"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_audit_finding.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_model.audit.finding'`

- [ ] **Step 3: Write minimal implementation**

```python
# science/model/src/science_model/audit/finding.py
"""The shared emitted payload (design §1).

What a producer SAYS on one observation. Not what is stored: the stored case is
`AuditFindingRecord`, which carries identity plus append-only history, and deliberately
does not keep a canonical payload.

`message` and `evidence` are excluded from identity so that rewording a diagnostic
does not fork a case.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, PlainSerializer, field_validator

from science_model.audit.evidence import MAX_EVIDENCE_ENTRIES, Evidence
from science_model.audit.subjects import FindingSubject

Severity = Literal["error", "warn", "info"]

_SEVERITY_ALIASES = {"warning": "warn", "warn": "warn", "error": "error", "info": "info"}


def _freeze_qualifiers(value: Mapping[str, object]) -> Mapping[str, object]:
    """A read-only view over a PRIVATE copy.

    Pydantic's `frozen=True` is shallow: it blocks `finding.qualifiers = {...}` and
    does nothing about `finding.qualifiers["field"] = "other"`. Qualifiers bear
    IDENTITY, so an in-place edit would silently change what a case is while the
    stored `finding_id` kept saying otherwise. The proxy wraps `dict(value)` rather
    than `value` itself, so no caller retains a writable handle on the underlying
    mapping -- a proxy over a dict someone else still holds is not immutable.
    """
    return MappingProxyType(dict(value))


#: Annotated once, used for every qualifier mapping in this package. The serializer
#: converts back to a plain dict so `model_dump()` output is ordinary JSON-ready data
#: and re-validation (`with_occurrence`) round-trips.
QualifierMap = Annotated[
    Mapping[str, object],
    AfterValidator(_freeze_qualifiers),
    PlainSerializer(dict, return_type=dict, when_used="always"),
]


def normalize_severity(raw: str) -> str:
    """`warning` and `warn` are one severity, matching `_severity_matches`."""
    try:
        return _SEVERITY_ALIASES[raw]
    except KeyError:
        raise ValueError(f"unknown severity {raw!r}") from None


class AuditFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str
    subject: FindingSubject
    severity: Severity
    #: `validate_default=True` is required: pydantic does NOT validate defaults, so
    #: without it an omitted `qualifiers` would be a plain, mutable `{}`.
    qualifiers: QualifierMap = Field(default_factory=dict, validate_default=True)
    message: str
    evidence: list[Evidence] = Field(default_factory=list, max_length=MAX_EVIDENCE_ENTRIES)

    @field_validator("severity", mode="before")
    @classmethod
    def _normalize(cls, value: object) -> object:
        return normalize_severity(value) if isinstance(value, str) else value
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science/model && uv run --frozen pytest tests/test_audit_finding.py -v`
Expected: PASS, 10 tests

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/audit/finding.py science/model/tests/test_audit_finding.py
git commit -m "feat(audit): the AuditFinding payload, with rule_id as its wire form"
```

---

### Task 5: Rule and section declarations

**Files:**
- Create: `science/model/src/science_model/audit/rules.py`
- Test: `science/model/tests/test_audit_rules.py`

**Interfaces:**
- Consumes: `Severity` (Task 4), `FingerprintError` (Task 3).
- Produces: `FindingRule`, `FindingSection`, `RuleDeclarationError`, and `FindingRule.build(...) -> AuditFinding` — the producer-side factory that makes emitting an undeclared rule impossible.

- [ ] **Step 1: Write the failing test**

```python
# science/model/tests/test_audit_rules.py
import pytest
from pydantic import BaseModel, ConfigDict

from science_model.audit.rules import (
    FindingRule,
    FindingSection,
    RuleDeclarationError,
)
from science_model.audit.subjects import EntitySubject, ProjectSubject


class FieldQualifier(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str


def _rule(**overrides) -> FindingRule:
    base = dict(
        id="dataset.cached-field-drift",
        severities={"warn"},
        subject_types={"entity"},
        identifier_namespaces=set(),
        qualifier_schema=FieldQualifier,
        identity_qualifiers=("field",),
        remediation="producer",
        title="Cached dataset field drifted from source",
        section="datasets",
        display_order=340,
        default_visibility="visible",
    )
    return FindingRule(**{**base, **overrides})


def test_build_produces_a_finding_carrying_the_rule_id():
    finding = _rule().build(
        subject=EntitySubject(ref="dataset:gtex-v8"),
        severity="warn",
        qualifiers={"field": "year"},
        message="drifted",
    )
    assert finding.rule_id == "dataset.cached-field-drift"


def test_build_refuses_a_severity_outside_the_declared_set():
    with pytest.raises(RuleDeclarationError):
        _rule().build(
            subject=EntitySubject(ref="dataset:x"),
            severity="error",
            qualifiers={"field": "year"},
            message="m",
        )


def test_build_refuses_a_subject_type_outside_the_declared_set():
    with pytest.raises(RuleDeclarationError):
        _rule().build(
            subject=ProjectSubject(), severity="warn", qualifiers={"field": "y"}, message="m"
        )


def test_build_validates_qualifiers_against_the_declared_schema():
    with pytest.raises(RuleDeclarationError):
        _rule().build(
            subject=EntitySubject(ref="dataset:x"),
            severity="warn",
            qualifiers={"feild": "typo"},
            message="m",
        )


def test_identity_qualifiers_must_exist_in_the_schema():
    with pytest.raises(RuleDeclarationError):
        _rule(identity_qualifiers=("nonexistent",))


def test_identity_qualifier_types_are_constrained_at_declaration():
    class FloatQualifier(BaseModel):
        model_config = ConfigDict(extra="forbid")
        ratio: float

    with pytest.raises(RuleDeclarationError):
        _rule(qualifier_schema=FloatQualifier, identity_qualifiers=("ratio",))


def test_rule_declaring_producer_remediation_needs_a_handler_name():
    with pytest.raises(RuleDeclarationError):
        _rule(remediation="producer", remediator=None)


def test_there_is_no_opt_out_flag_for_the_remediator_check():
    # A field that disables the check would be a bypass of the check.
    assert "requires_remediator" not in FindingRule.model_fields


def test_a_remediator_without_producer_remediation_is_refused():
    with pytest.raises(RuleDeclarationError):
        _rule(remediation="none", remediator="fix_it")


def test_unordered_identity_qualifier_collections_are_refused():
    class SetQualifier(BaseModel):
        model_config = ConfigDict(extra="forbid")
        tags: frozenset[str]

    # frozenset is unordered; §3 encodes arrays in declaration order.
    with pytest.raises(RuleDeclarationError):
        _rule(qualifier_schema=SetQualifier, identity_qualifiers=("tags",))


def test_ordered_identity_qualifier_collections_are_permitted():
    class ListQualifier(BaseModel):
        model_config = ConfigDict(extra="forbid")
        tags: list[str]

    _rule(qualifier_schema=ListQualifier, identity_qualifiers=("tags",))


def test_section_order_is_declared_not_derived_from_the_name():
    section = FindingSection(id="datasets", title="Datasets", section_order=300)
    assert section.section_order == 300
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_audit_rules.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_model.audit.rules'`

- [ ] **Step 3: Write minimal implementation**

```python
# science/model/src/science_model/audit/rules.py
"""Rule and section declarations (design §6).

Declared BESIDE the producer that emits them; the frozen registry is DERIVED from
these declarations (see `science_tool.findings.producers`). There is no
hand-maintained central table, so no repeated rule-id string can drift — the defect
that let `dataset_access_invalid` be emitted while `DATASET_ANOMALY_CODES` declared
eleven codes.

`build()` is why a producer cannot emit an undeclared rule: the only supported way
to construct a `AuditFinding` in production code is through a declaration object.
"""

from __future__ import annotations

import re
import typing
from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

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
    """A display grouping with an EXPLICIT order.

    Sorting on `id` would alphabetize and discard the display order that
    `HEALTH_CHECKS`'s hand-ordered tuple encodes today.
    """

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
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    id: str
    severities: frozenset[Severity]
    subject_types: frozenset[str]
    identifier_namespaces: frozenset[str] = frozenset()
    qualifier_schema: type[BaseModel]
    identity_qualifiers: tuple[str, ...] = ()
    remediation: Remediation = "none"
    remediator: str | None = None

    # presentation metadata — so renderers stop hardcoding sections, order, visibility
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
        severity: str,
        qualifiers: Mapping[str, object],
        message: str,
        evidence: list[object] | None = None,
    ) -> AuditFinding:
        """Construct a `AuditFinding` that cannot violate this rule."""
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
        try:
            # `dict(...)`: qualifier mappings are frozen views (`QualifierMap`), and a
            # model validator takes a concrete dict, not any Mapping.
            self.qualifier_schema.model_validate(dict(qualifiers))
        except ValidationError as exc:
            raise RuleDeclarationError(f"{self.id}: qualifiers invalid: {exc}") from exc
        return finding

    def identity_subset(self, qualifiers: Mapping[str, object]) -> dict[str, object]:
        """The identity-bearing qualifier subset consumed by the fingerprint."""
        return {k: qualifiers[k] for k in self.identity_qualifiers if k in qualifiers}


def _identity_type_permitted(hint: object) -> bool:
    """Only str / bool / int, and ORDERED sequences of those.

    `set` and `frozenset` are deliberately absent: they are unordered, and §3 encodes
    arrays in declaration order. An unordered collection would make the canonical
    encoding depend on iteration order, which is exactly the kind of instability the
    frozen fingerprint exists to exclude.
    """
    if hint in _ALLOWED_IDENTITY_TYPES:
        return True
    origin = typing.get_origin(hint)
    if origin in (list, tuple):
        args = [a for a in typing.get_args(hint) if a is not Ellipsis]
        return bool(args) and all(a in _ALLOWED_IDENTITY_TYPES for a in args)
    return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science/model && uv run --frozen pytest tests/test_audit_rules.py -v`
Expected: PASS, 12 tests

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/audit/rules.py science/model/tests/test_audit_rules.py
git commit -m "feat(audit): rule and section declarations with a build() that cannot emit an undeclared rule"
```

---

### Task 6: `AuditFindingRecord`, occurrences, transitions, reviews

**Files:**
- Create: `science/model/src/science_model/audit/record.py`
- Test: `science/model/tests/test_audit_record.py`

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: `AuditFindingRecord` (frozen, with `with_occurrence` / `with_review` / `with_transition` / `current_severity` / `confirmation_count`), `Occurrence`, `Transition`, `Review`, `CaseStatus`, `RecordError`, `occurrence_key(...)`, `review_id(...)`, `PERMITTED_TRANSITIONS`, `DOC_KIND = "audit-case"`.

- [ ] **Step 1: Write the failing test**

```python
# science/model/tests/test_audit_record.py
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from science_model.audit.record import (
    AuditFindingRecord,
    Occurrence,
    Review,
    Transition,
    occurrence_key,
    review_id,
)
from science_model.audit.subjects import EntitySubject

NOW = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
FID = "a" * 64


def _occurrence(**overrides) -> Occurrence:
    producer = overrides.pop("producer_id", "dataset_anomalies")
    ingestion = overrides.pop("ingestion_ref", "run:2026-07-27-curation-sweep-a3f1")
    base = dict(
        idempotency_key=occurrence_key(
            producer_id=producer, ingestion_ref=ingestion, finding_id=FID
        ),
        producer_id=producer,
        ingestion_ref=ingestion,
        observed_at=NOW,
        severity="warn",
        message="drifted",
        qualifiers={"field": "year", "note": "non-identity"},
        evidence=(),
    )
    return Occurrence(**{**base, **overrides})


def _review(**overrides) -> Review:
    kind = overrides.pop("reviewer_kind", "human")
    ref = overrides.pop("reviewer_ref", "keith")
    lens = overrides.pop("lens", None)
    run = overrides.pop("run_ref", "run:x")
    base = dict(
        review_id=review_id(
            reviewer_kind=kind, reviewer_ref=ref, lens=lens, run_ref=run, finding_id=FID
        ),
        reviewer_kind=kind,
        reviewer_ref=ref,
        lens=lens,
        run_ref=run,
        at=NOW,
        outcome="confirms",
        note="checked",
    )
    return Review(**{**base, **overrides})


def _record(**overrides) -> AuditFindingRecord:
    base = dict(
        finding_id=FID,
        fingerprint_version=1,
        rule_id="dataset.cached-field-drift",
        subject=EntitySubject(ref="dataset:gtex-v8"),
        identity_qualifiers={"field": "year"},
        occurrences=[_occurrence()],
        reviews=[],
        transitions=[
            Transition(
                from_status=None, to_status="proposed", actor="ingest", at=NOW, reason="detected"
            )
        ],
        status="proposed",
    )
    return AuditFindingRecord(**{**base, **overrides})


def test_genesis_transition_is_required():
    with pytest.raises(ValidationError):
        _record(transitions=[])


def test_first_transition_must_come_from_none():
    with pytest.raises(ValidationError):
        _record(
            transitions=[
                Transition(
                    from_status="proposed", to_status="confirmed", actor="k", at=NOW, reason="r"
                )
            ]
        )


def test_status_is_derived_and_must_agree_with_the_log():
    with pytest.raises(ValidationError):
        _record(status="confirmed")


def test_transition_outside_the_graph_is_rejected():
    genesis = Transition(
        from_status=None, to_status="proposed", actor="ingest", at=NOW, reason="detected"
    )
    illegal = Transition(
        from_status="proposed", to_status="promoted", actor="k", at=NOW, reason="r",
        task_ref="task:1",
    )
    with pytest.raises(ValidationError):
        _record(transitions=[genesis, illegal], status="promoted")


def test_promoted_task_present_iff_status_is_promoted():
    genesis = Transition(
        from_status=None, to_status="proposed", actor="ingest", at=NOW, reason="detected"
    )
    confirm = Transition(
        from_status="proposed", to_status="confirmed", actor="k", at=NOW, reason="r"
    )
    promote = Transition(
        from_status="confirmed", to_status="promoted", actor="k", at=NOW, reason="r",
        task_ref="task:0042",
    )
    ok = _record(
        transitions=[genesis, confirm, promote], status="promoted", promoted_task="task:0042"
    )
    assert ok.promoted_task == "task:0042"
    with pytest.raises(ValidationError):
        _record(transitions=[genesis, confirm, promote], status="promoted")
    with pytest.raises(ValidationError):
        _record(promoted_task="task:0042")


def test_transition_to_promoted_requires_a_task_ref():
    genesis = Transition(
        from_status=None, to_status="proposed", actor="ingest", at=NOW, reason="detected"
    )
    with pytest.raises(ValidationError):
        Transition(
            from_status="confirmed", to_status="promoted", actor="k", at=NOW, reason="r"
        )
    with pytest.raises(ValidationError):
        Transition(
            from_status="proposed", to_status="confirmed", actor="k", at=NOW, reason="r",
            task_ref="task:1",
        )
    assert genesis.task_ref is None


def test_occurrence_carries_the_complete_qualifier_object():
    occ = _occurrence()
    assert set(occ.qualifiers) == {"field", "note"}


def test_occurrence_acceptance_key_is_optional():
    assert _occurrence().acceptance_key is None
    assert _occurrence(acceptance_key="b" * 32).acceptance_key == "b" * 32


def test_occurrence_key_is_stable_and_distinguishes_producers():
    a = occurrence_key(producer_id="p1", ingestion_ref="r1", finding_id=FID)
    assert a == occurrence_key(producer_id="p1", ingestion_ref="r1", finding_id=FID)
    assert a != occurrence_key(producer_id="p2", ingestion_ref="r1", finding_id=FID)


def test_review_id_includes_lens_so_two_lenses_do_not_collide():
    grounding = review_id(
        reviewer_kind="agent", reviewer_ref="curation-sweep", lens="grounding",
        run_ref="run:x", finding_id=FID,
    )
    coverage = review_id(
        reviewer_kind="agent", reviewer_ref="curation-sweep", lens="coverage",
        run_ref="run:x", finding_id=FID,
    )
    assert grounding != coverage
    assert grounding == review_id(
        reviewer_kind="agent", reviewer_ref="curation-sweep", lens="grounding",
        run_ref="run:x", finding_id=FID,
    )


def test_agent_review_requires_lens_and_model():
    Review(
        review_id="c" * 64, reviewer_kind="agent", reviewer_ref="curation-sweep",
        lens="grounding", model="claude-opus-5", run_ref="run:x", at=NOW,
        outcome="confirms", note="checked",
    )
    with pytest.raises(ValidationError):
        Review(
            review_id="c" * 64, reviewer_kind="agent", reviewer_ref="curation-sweep",
            model="claude-opus-5", run_ref="run:x", at=NOW, outcome="confirms", note="n",
        )
    with pytest.raises(ValidationError):
        Review(
            review_id="c" * 64, reviewer_kind="agent", reviewer_ref="curation-sweep",
            lens="grounding", run_ref="run:x", at=NOW, outcome="confirms", note="n",
        )


def test_human_review_needs_neither_lens_nor_model():
    Review(
        review_id="d" * 64, reviewer_kind="human", reviewer_ref="keith", run_ref="run:x",
        at=NOW, outcome="refutes", note="not real",
    )


def test_confirmation_count_is_derived_from_distinct_confirming_reviews():
    record = _record(
        reviews=[
            _review(reviewer_ref="keith", outcome="confirms"),
            _review(reviewer_ref="other", outcome="refutes"),
        ]
    )
    assert record.confirmation_count() == 1


def test_idempotency_key_is_required_and_must_match_its_own_fields():
    with pytest.raises(ValidationError):
        Occurrence(
            producer_id="p", ingestion_ref="r", observed_at=NOW, severity="warn",
            message="m",
        )
    with pytest.raises(ValidationError):
        _record(occurrences=[_occurrence(idempotency_key="0" * 64)])


def test_duplicate_occurrence_keys_are_rejected():
    occ = _occurrence()
    with pytest.raises(ValidationError):
        _record(occurrences=[occ, occ])


def test_review_id_must_match_its_own_fields():
    with pytest.raises(ValidationError):
        _record(reviews=[_review().model_copy(update={"review_id": "0" * 64})])


def test_promoted_task_must_equal_the_promotion_transitions_task_ref():
    genesis = Transition(
        from_status=None, to_status="proposed", actor="ingest", at=NOW, reason="detected"
    )
    confirm = Transition(
        from_status="proposed", to_status="confirmed", actor="k", at=NOW, reason="r"
    )
    promote = Transition(
        from_status="confirmed", to_status="promoted", actor="k", at=NOW, reason="r",
        task_ref="task:0042",
    )
    with pytest.raises(ValidationError):
        _record(
            transitions=[genesis, confirm, promote], status="promoted",
            promoted_task="task:9999",
        )


def test_the_record_is_frozen():
    record = _record()
    with pytest.raises(ValidationError):
        record.status = "confirmed"


def test_appending_goes_through_validation():
    record = _record()
    grown = record.with_occurrence(_occurrence(ingestion_ref="ing:2"))
    assert len(grown.occurrences) == 2
    # A bad append is refused rather than silently stored, which model_copy would allow.
    with pytest.raises(ValidationError):
        record.with_occurrence(_occurrence(idempotency_key="0" * 64))


def test_current_severity_uses_each_producers_most_recent_ingestion():
    from datetime import timedelta

    later = NOW + timedelta(hours=1)
    record = _record(
        occurrences=[
            _occurrence(ingestion_ref="ing:1", severity="error"),
            _occurrence(ingestion_ref="ing:2", severity="warn", observed_at=later),
        ]
    )
    # The newer look from the same producer supersedes the older one.
    assert record.current_severity() == "warn"


def test_current_severity_takes_the_max_across_producers():
    record = _record(
        occurrences=[
            _occurrence(producer_id="a", severity="warn"),
            _occurrence(producer_id="b", severity="error"),
        ]
    )
    assert record.current_severity() == "error"


def test_identity_qualifiers_cannot_be_mutated_in_place():
    # `finding_id` is a digest OVER this mapping. If the mapping can change, the
    # digest silently stops describing the case it names.
    #
    # The two exception types are not a typo: `mappingproxy` refuses SUBSCRIPT
    # mutation with `TypeError` and simply does not HAVE the mutating dict methods,
    # so `.clear()` is an `AttributeError`. Both are asserted because both are ways
    # a caller reaches for.
    record = _record()
    with pytest.raises(TypeError):
        record.identity_qualifiers["field"] = "month"   # type: ignore[index]
    with pytest.raises(AttributeError):
        record.identity_qualifiers.clear()              # type: ignore[attr-defined]


def test_occurrence_qualifiers_cannot_be_mutated_in_place():
    occurrence = _record().occurrences[0]
    with pytest.raises(TypeError):
        occurrence.qualifiers["field"] = "month"        # type: ignore[index]


def test_a_record_round_trips_through_a_plain_dict_dump():
    # The frozen mappings serialize as ordinary dicts, so re-validation -- which is
    # how `with_occurrence` appends -- works on the dumped form.
    record = _record()
    assert AuditFindingRecord.model_validate(record.model_dump(mode="json")) == record
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_audit_record.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_model.audit.record'`

- [ ] **Step 3: Write minimal implementation**

```python
# science/model/src/science_model/audit/record.py
"""The canonical stored case (design §4).

`AuditFindingRecord` carries IMMUTABLE identity plus APPEND-ONLY history. It deliberately
does NOT store a canonical payload: whoever ingested first would otherwise own the
message, severity, and evidence forever, and later observations would be discarded.

`status` is DERIVED from the last transition and validated against the stored value.
Disagreement is a load error, not a repair.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from science_model.audit.evidence import MAX_EVIDENCE_ENTRIES, Evidence
from science_model.audit.finding import QualifierMap, Severity
from science_model.audit.subjects import FindingSubject

DOC_KIND = "audit-case"

OCCURRENCE_DOMAIN = "science.occurrence.v1"
REVIEW_DOMAIN = "science.review.v1"

CaseStatus = Literal["proposed", "confirmed", "dismissed", "promoted"]
ReviewerKind = Literal["human", "agent", "deterministic"]
ReviewOutcome = Literal["confirms", "refutes", "abstains"]

#: The transition graph is CLOSED. Any pair absent here is rejected.
PERMITTED_TRANSITIONS: frozenset[tuple[CaseStatus | None, CaseStatus]] = frozenset(
    {
        (None, "proposed"),
        ("proposed", "confirmed"),
        ("proposed", "dismissed"),
        ("confirmed", "dismissed"),
        ("confirmed", "promoted"),
        ("dismissed", "proposed"),
        ("promoted", "dismissed"),
    }
)


class RecordError(ValueError):
    """A stored case is malformed."""


def occurrence_key(*, producer_id: str, ingestion_ref: str, finding_id: str) -> str:
    payload = f"{OCCURRENCE_DOMAIN}\n{producer_id}\0{ingestion_ref}\0{finding_id}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def review_id(
    *,
    reviewer_kind: str,
    reviewer_ref: str,
    lens: str | None,
    run_ref: str,
    finding_id: str,
) -> str:
    """Lens is PART OF review identity: two lenses in one run are two reviews."""
    payload = (
        f"{REVIEW_DOMAIN}\n{reviewer_kind}\0{reviewer_ref}\0{lens or ''}\0"
        f"{run_ref}\0{finding_id}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Occurrence(_Base):
    """One COMPLETE observation. Nothing a producer said is discarded."""

    #: REQUIRED, and validated against `occurrence_key(...)` by the owning record.
    #: Optional would mean a stored key nobody ever checks.
    idempotency_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    producer_id: str = Field(min_length=1)
    ingestion_ref: str = Field(min_length=1)
    observed_at: datetime
    severity: Severity
    message: str
    #: Frozen like every qualifier mapping here: a stored observation is history, and
    #: history that can be edited in place is not history.
    qualifiers: QualifierMap = Field(default_factory=dict, validate_default=True)
    evidence: tuple[Evidence, ...] = Field(default=(), max_length=MAX_EVIDENCE_ENTRIES)
    #: Present when the observation arrived on the report's `accepted` channel.
    acceptance_key: str | None = None

    def content_signature(self) -> str:
        """What must match for an identical idempotency key to be a genuine retry."""
        return hashlib.sha256(
            canonical_occurrence_content(self).encode("utf-8")
        ).hexdigest()


def canonical_occurrence_content(occurrence: Occurrence) -> str:
    from science_model.audit.fingerprint import canonical_json

    return canonical_json(
        {
            "severity": occurrence.severity,
            "message": occurrence.message,
            "qualifiers": {k: v for k, v in sorted(occurrence.qualifiers.items())},
            "evidence": [e.model_dump(mode="json", exclude_none=True) for e in occurrence.evidence],
            "acceptance_key": occurrence.acceptance_key,
        }
    ).decode("utf-8")


class Transition(_Base):
    from_status: CaseStatus | None
    to_status: CaseStatus
    actor: str
    at: datetime
    reason: str = Field(min_length=1)
    task_ref: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> "Transition":
        if (self.from_status, self.to_status) not in PERMITTED_TRANSITIONS:
            raise RecordError(
                f"transition {self.from_status!r} -> {self.to_status!r} is not permitted"
            )
        if self.to_status == "promoted" and not self.task_ref:
            raise RecordError("a transition to 'promoted' requires task_ref")
        if self.to_status != "promoted" and self.task_ref is not None:
            raise RecordError("task_ref is forbidden except on a transition to 'promoted'")
        return self


class Review(_Base):
    review_id: str
    reviewer_kind: ReviewerKind
    reviewer_ref: str
    lens: str | None = None
    model: str | None = None
    run_ref: str
    at: datetime
    outcome: ReviewOutcome
    note: str = Field(min_length=1)

    @model_validator(mode="after")
    def _agent_provenance(self) -> "Review":
        if self.reviewer_kind == "agent":
            if not self.lens:
                raise RecordError("an agent review requires a lens (design §4)")
            if not self.model:
                raise RecordError(
                    "an agent review requires model provenance, so the correlation "
                    "caution stays measurable (design §4)"
                )
        return self


#: Ordering for "the most severe observation", highest first.
_SEVERITY_RANK: dict[str, int] = {"error": 3, "warn": 2, "info": 1}


class AuditFindingRecord(BaseModel):
    """FROZEN, with immutable history collections.

    Every derived value stored here is RECOMPUTED and checked on construction:
    occurrence keys, review ids, the status implied by the transition log, and the
    promoted task. A stored derived value nobody validates is a value that can lie.

    Appending goes through `with_occurrence` / `with_review` / `with_transition`,
    which rebuild through the constructor. `model_copy(update=...)` is deliberately
    NOT the append path: it bypasses every validator above.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    fingerprint_version: int
    rule_id: str
    subject: FindingSubject
    #: The identity-bearing subset. `finding_id` is a digest OVER this mapping, so a
    #: mutable one would let a caller change the identity without changing the digest.
    identity_qualifiers: QualifierMap = Field(default_factory=dict, validate_default=True)

    occurrences: tuple[Occurrence, ...] = Field(min_length=1)
    reviews: tuple[Review, ...] = ()
    transitions: tuple[Transition, ...] = Field(min_length=1)

    status: CaseStatus
    promoted_task: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> "AuditFindingRecord":
        self._validate_transitions()
        self._validate_occurrences()
        self._validate_reviews()
        return self

    def _validate_transitions(self) -> None:
        if self.transitions[0].from_status is not None:
            raise RecordError(
                "the first transition must be the genesis `None -> proposed`; the log "
                "is never empty and status needs no special case"
            )
        expected: CaseStatus | None = None
        promotion_task: str | None = None
        for transition in self.transitions:
            if transition.from_status != expected:
                raise RecordError(
                    f"transition log is discontinuous: expected from_status "
                    f"{expected!r}, got {transition.from_status!r}"
                )
            expected = transition.to_status
            if transition.to_status == "promoted":
                promotion_task = transition.task_ref
        if self.status != expected:
            raise RecordError(
                f"status {self.status!r} disagrees with the transition log, which ends "
                f"at {expected!r}; this is a load error, not something to repair"
            )
        if (self.status == "promoted") != (self.promoted_task is not None):
            raise RecordError(
                "promoted_task is present if and only if status is 'promoted'"
            )
        if self.status == "promoted" and self.promoted_task != promotion_task:
            raise RecordError(
                f"promoted_task {self.promoted_task!r} does not match the task_ref "
                f"{promotion_task!r} recorded on the promotion transition"
            )

    def _validate_occurrences(self) -> None:
        seen: set[str] = set()
        for occurrence in self.occurrences:
            expected = occurrence_key(
                producer_id=occurrence.producer_id,
                ingestion_ref=occurrence.ingestion_ref,
                finding_id=self.finding_id,
            )
            if occurrence.idempotency_key != expected:
                raise RecordError(
                    f"occurrence idempotency_key {occurrence.idempotency_key!r} is not "
                    f"the key derived from its own fields ({expected!r})"
                )
            if occurrence.idempotency_key in seen:
                raise RecordError(
                    f"duplicate occurrence idempotency_key {occurrence.idempotency_key!r}"
                )
            seen.add(occurrence.idempotency_key)

    def _validate_reviews(self) -> None:
        seen: set[str] = set()
        for review in self.reviews:
            expected = review_id(
                reviewer_kind=review.reviewer_kind,
                reviewer_ref=review.reviewer_ref,
                lens=review.lens,
                run_ref=review.run_ref,
                finding_id=self.finding_id,
            )
            if review.review_id != expected:
                raise RecordError(
                    f"review_id {review.review_id!r} is not the id derived from its own "
                    f"fields ({expected!r})"
                )
            if review.review_id in seen:
                raise RecordError(f"duplicate review_id {review.review_id!r}")
            seen.add(review.review_id)

    def with_occurrence(self, occurrence: Occurrence) -> "AuditFindingRecord":
        """Append through the constructor, so every validator above runs."""
        return AuditFindingRecord.model_validate(
            {
                **self.model_dump(mode="python"),
                "occurrences": (*self.occurrences, occurrence),
            }
        )

    def with_review(self, review: Review) -> "AuditFindingRecord":
        return AuditFindingRecord.model_validate(
            {**self.model_dump(mode="python"), "reviews": (*self.reviews, review)}
        )

    def with_transition(
        self, transition: Transition, *, promoted_task: str | None = None
    ) -> "AuditFindingRecord":
        return AuditFindingRecord.model_validate(
            {
                **self.model_dump(mode="python"),
                "transitions": (*self.transitions, transition),
                "status": transition.to_status,
                "promoted_task": promoted_task,
            }
        )

    def current_severity(self) -> Severity:
        """Max severity over occurrences from EACH producer's MOST RECENT ingestion.

        A defined function of the log (design §4), not a field anyone writes. An older
        run that saw `error` does not keep a case at `error` after every producer's
        latest look says `warn`.
        """
        latest: dict[str, tuple[datetime, str]] = {}
        for occurrence in self.occurrences:
            seen = latest.get(occurrence.producer_id)
            if seen is None or occurrence.observed_at > seen[0]:
                latest[occurrence.producer_id] = (
                    occurrence.observed_at,
                    occurrence.severity,
                )
            elif occurrence.observed_at == seen[0]:
                if _SEVERITY_RANK[occurrence.severity] > _SEVERITY_RANK[seen[1]]:
                    latest[occurrence.producer_id] = (seen[0], occurrence.severity)
        return max(
            (severity for _at, severity in latest.values()),
            key=lambda s: _SEVERITY_RANK[s],
        )

    def confirmation_count(self) -> int:
        """Distinct confirming reviews. NEVER a confidence, NEVER aggregated."""
        return len({r.review_id for r in self.reviews if r.outcome == "confirms"})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science/model && uv run --frozen pytest tests/test_audit_record.py -v`
Expected: PASS, 24 tests

Then: `cd science/model && uv run --frozen pytest tests/test_audit_*.py -q`
Expected: PASS, all audit model tests

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/audit/record.py science/model/tests/test_audit_record.py
git commit -m "feat(audit): AuditFindingRecord with a genesis transition and a closed lifecycle graph"
```

---

### Task 7: Report wire types

**Files:**
- Create: `science/model/src/science_model/audit/report.py`
- Modify: `science/model/src/science_model/audit/__init__.py` (add re-exports)
- Test: `science/model/tests/test_audit_report.py`

**Interfaces:**
- Consumes: `AuditFinding` (Task 4).
- Produces: `AuditReport`, `ReportedFinding`, `AcceptedFinding`, `ProducerMetrics`, `UnwiredProducer`, `ReportTotals`, `ReportMeta`, `REPORT_SCHEMA_VERSION = 2`, `MAX_REPORT_FINDINGS = 5000`.

- [ ] **Step 1: Write the failing test**

```python
# science/model/tests/test_audit_report.py
import pytest
from pydantic import ValidationError

from science_model.audit.finding import AuditFinding
from science_model.audit.report import (
    REPORT_SCHEMA_VERSION,
    AuditReport,
    ReportedFinding,
)
from science_model.audit.subjects import EntitySubject


def _finding(ref="dataset:a", rule="dataset.stale-review") -> AuditFinding:
    return AuditFinding(
        rule_id=rule, subject=EntitySubject(ref=ref), severity="warn",
        qualifiers={}, message="m", evidence=[],
    )


def _report(**overrides) -> AuditReport:
    base = dict(
        schema_version=REPORT_SCHEMA_VERSION,
        fingerprint_version=1,
        ingestion_ref="run:2026-07-27-curation-sweep-a3f1",
        generated_at="2026-07-27T12:00:00+00:00",
        findings=[ReportedFinding(producer_id="dataset_anomalies", finding=_finding())],
        accepted=[],
        metrics={},
        unwired=[],
        totals={"findings_total": 1, "findings_by_severity": {"warn": 1},
                "accepted_total": 0, "unwired_total": 0},
        meta={"producers_run": ["dataset_anomalies"], "total_duration_seconds": 0.5,
              "timings": []},
    )
    return AuditReport(**{**base, **overrides})


def test_a_finding_is_enveloped_with_its_producer():
    assert _report().findings[0].producer_id == "dataset_anomalies"


def test_bare_finding_without_producer_is_refused():
    with pytest.raises(ValidationError):
        _report(findings=[_finding()])


def test_ingestion_ref_and_generated_at_are_required():
    with pytest.raises(ValidationError):
        _report(ingestion_ref=None)
    with pytest.raises(ValidationError):
        _report(generated_at=None)


def test_unknown_schema_version_is_refused():
    with pytest.raises(ValidationError):
        _report(schema_version=99)


def test_the_report_does_not_try_to_dedup_by_identity():
    # Identity is a fingerprint over the rule's DECLARED identity qualifiers, which
    # this module cannot compute -- it does not know the registry. Enforcing the
    # one-per-(producer, finding_id) rule here would have to key on the whole payload,
    # which passes two observations with identical identity and different prose.
    # Ingestion enforces it instead; see test_findings_ingest.py.
    dup = ReportedFinding(producer_id="p", finding=_finding())
    report = _report(findings=[dup, dup], totals={
        "findings_total": 2, "findings_by_severity": {"warn": 2},
        "accepted_total": 0, "unwired_total": 0,
    })
    assert len(report.findings) == 2


def test_two_producers_may_emit_the_same_finding():
    finding = _finding()
    report = _report(
        findings=[
            ReportedFinding(producer_id="p1", finding=finding),
            ReportedFinding(producer_id="p2", finding=finding),
        ],
        totals={"findings_total": 2, "findings_by_severity": {"warn": 2},
                "accepted_total": 0, "unwired_total": 0},
    )
    assert len(report.findings) == 2


def test_accepted_findings_carry_provenance_and_an_acceptance_key():
    from science_model.audit.report import AcceptedFinding

    report = _report(
        accepted=[
            AcceptedFinding(
                producer_id="p", finding=_finding(), acceptance_key="b" * 32,
                reason="known and accepted",
            )
        ],
        totals={"findings_total": 1, "findings_by_severity": {"warn": 1},
                "accepted_total": 1, "unwired_total": 0},
    )
    assert report.accepted[0].acceptance_key == "b" * 32


def test_totals_must_agree_with_the_channels():
    with pytest.raises(ValidationError):
        _report(totals={"findings_total": 7, "findings_by_severity": {"warn": 7},
                        "accepted_total": 0, "unwired_total": 0})


def test_findings_by_severity_must_agree_with_the_unsuppressed_channel():
    # The scalar total is right; the breakdown is not. A check on the total alone
    # would pass this.
    with pytest.raises(ValidationError, match="findings_by_severity"):
        _report(totals={"findings_total": 1, "findings_by_severity": {"error": 1},
                        "accepted_total": 0, "unwired_total": 0})
    with pytest.raises(ValidationError, match="findings_by_severity"):
        _report(totals={"findings_total": 1,
                        "findings_by_severity": {"warn": 1, "error": 0},
                        "accepted_total": 0, "unwired_total": 0})


def test_generated_at_must_be_iso_8601():
    with pytest.raises(ValidationError, match="ISO-8601"):
        _report(generated_at="last Tuesday")
    with pytest.raises(ValidationError, match="ISO-8601"):
        _report(generated_at="2026-13-45T99:00:00")


def test_the_finding_ceiling_applies_across_both_channels():
    from science_model.audit.report import MAX_REPORT_FINDINGS, AcceptedFinding

    half = MAX_REPORT_FINDINGS // 2
    findings = [
        ReportedFinding(producer_id="p", finding=_finding(ref=f"dataset:{i}"))
        for i in range(half + 1)
    ]
    accepted = [
        AcceptedFinding(
            producer_id="p", finding=_finding(ref=f"dataset:acc-{i}"),
            acceptance_key="b" * 32, reason="known",
        )
        for i in range(half + 1)
    ]
    with pytest.raises(ValidationError, match="ceiling"):
        _report(
            findings=findings, accepted=accepted,
            totals={"findings_total": len(findings),
                    "findings_by_severity": {"warn": len(findings)},
                    "accepted_total": len(accepted), "unwired_total": 0},
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_audit_report.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_model.audit.report'`

- [ ] **Step 3: Write minimal implementation**

```python
# science/model/src/science_model/audit/report.py
"""The public audit output contract (design §11).

Findings are ENVELOPED with their producer. A bare `AuditFinding` cannot populate an
occurrence's required `producer_id`, and rule ownership cannot supply it either —
several producers must be able to emit one rule, which is the premise of
cross-producer dedup.

`ingestion_ref` and `generated_at` are report-level and TRUSTED: supplied by the
supervisor or the ingesting command, never by a finding.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from science_model.audit.finding import AuditFinding

REPORT_SCHEMA_VERSION = 2

#: The ceiling applies to `findings + accepted` TOGETHER. Both channels are ingested
#: (design §8), so a bound on one alone is a bound on nothing: 5000 accepted
#: observations cost exactly what 5000 unsuppressed ones cost.
MAX_REPORT_FINDINGS = 5000


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReportedFinding(_Base):
    producer_id: str = Field(min_length=1)
    finding: AuditFinding


class AcceptedFinding(_Base):
    producer_id: str = Field(min_length=1)
    finding: AuditFinding
    acceptance_key: str = Field(pattern=r"^[0-9a-f]{32}$")
    reason: str = Field(min_length=1)


class UnwiredProducer(_Base):
    producer_id: str
    code: str = Field(min_length=1)
    reason: str | None = None


class ProducerMetrics(BaseModel):
    """Validated against the schema the producer declared at registration (§6).

    `extra="allow"` here and strict validation there: this type is the transport,
    the producer's declared schema is the contract. `science_tool.findings.producers`
    performs that validation; `science_model` cannot, because it does not know the
    registry.
    """

    model_config = ConfigDict(extra="allow")


class ReportTotals(_Base):
    findings_total: int = Field(ge=0)
    findings_by_severity: dict[str, int] = Field(default_factory=dict)
    accepted_total: int = Field(ge=0)
    unwired_total: int = Field(ge=0)


class ReportMeta(_Base):
    producers_run: list[str] = Field(default_factory=list)
    total_duration_seconds: float
    timings: list[dict[str, object]] = Field(default_factory=list)


class AuditReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[2]
    fingerprint_version: int
    ingestion_ref: str = Field(min_length=1)
    #: ISO-8601, and validated as such HERE. Ingestion turns this into the
    #: `observed_at` of every occurrence it writes; a bare `min_length=1` would push a
    #: raw `ValueError` from `datetime.fromisoformat` out of the write path, where it
    #: is neither an `IngestError` nor a validation failure the caller can report.
    generated_at: str = Field(min_length=1)
    findings: list[ReportedFinding] = Field(max_length=MAX_REPORT_FINDINGS)
    accepted: list[AcceptedFinding] = Field(
        default_factory=list, max_length=MAX_REPORT_FINDINGS
    )
    metrics: dict[str, ProducerMetrics] = Field(default_factory=dict)
    unwired: list[UnwiredProducer] = Field(default_factory=list)
    totals: ReportTotals
    meta: ReportMeta

    @field_validator("generated_at")
    @classmethod
    def _iso_8601(cls, value: str) -> str:
        try:
            datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(
                f"generated_at must be ISO-8601, got {value!r}: {exc}"
            ) from exc
        return value

    @model_validator(mode="after")
    def _validate(self) -> "AuditReport":
        # NOTE: the "at most one finding per (producer_id, finding_id)" rule is NOT
        # enforced here. It cannot be: `finding_id` is a fingerprint over the rule's
        # DECLARED identity qualifiers, and this module does not know the registry.
        # Keying on the whole serialized payload instead would pass two observations
        # with identical identity and different prose -- precisely the collision the
        # rule exists to prevent. Ingestion enforces it after computing fingerprints
        # (`science_tool.findings.ingest._plan`).
        if len(self.findings) + len(self.accepted) > MAX_REPORT_FINDINGS:
            raise ValueError(
                f"{len(self.findings)} findings + {len(self.accepted)} accepted exceeds "
                f"the {MAX_REPORT_FINDINGS} ceiling; both channels are ingested, so the "
                "bound is on their sum"
            )
        if self.totals.findings_total != len(self.findings):
            raise ValueError(
                f"totals.findings_total {self.totals.findings_total} != "
                f"{len(self.findings)} findings"
            )
        if self.totals.accepted_total != len(self.accepted):
            raise ValueError("totals.accepted_total disagrees with the accepted channel")
        if self.totals.unwired_total != len(self.unwired):
            raise ValueError("totals.unwired_total disagrees with the unwired channel")
        # `findings_by_severity` counts the UNSUPPRESSED channel only -- it is the
        # severity breakdown of what is being shown. Checking the scalar total while
        # leaving the breakdown unchecked is how a summary comes to disagree with the
        # rows underneath it. Equality is exact: a `{"warn": 0}` entry for a severity
        # nothing emitted is a disagreement, not a harmless zero.
        actual = Counter(item.finding.severity for item in self.findings)
        if dict(self.totals.findings_by_severity) != dict(actual):
            raise ValueError(
                f"totals.findings_by_severity {dict(self.totals.findings_by_severity)} "
                f"disagrees with the findings channel {dict(actual)}"
            )
        return self
```

Add to `science/model/src/science_model/audit/__init__.py`:

```python
from science_model.audit.evidence import Evidence, LocationEvidence, Span, TextEvidence
from science_model.audit.finding import AuditFinding, Severity, normalize_severity
from science_model.audit.fingerprint import (
    FINGERPRINT_VERSION,
    finding_fingerprint,
    rule_slug,
)
from science_model.audit.record import (
    DOC_KIND,
    CaseStatus,
    AuditFindingRecord,
    Occurrence,
    Review,
    Transition,
    occurrence_key,
    review_id,
)
from science_model.audit.report import (
    REPORT_SCHEMA_VERSION,
    AcceptedFinding,
    AuditReport,
    ReportedFinding,
)
from science_model.audit.rules import FindingRule, FindingSection, RuleDeclarationError
from science_model.audit.subjects import (
    EntitySubject,
    FindingSubject,
    IdentifierSubject,
    PathSubject,
    ProjectSubject,
)

__all__ = [
    "DOC_KIND",
    "FINGERPRINT_VERSION",
    "REPORT_SCHEMA_VERSION",
    "AcceptedFinding",
    "AuditReport",
    "CaseStatus",
    "EntitySubject",
    "Evidence",
    "AuditFinding",
    "AuditFindingRecord",
    "FindingRule",
    "FindingSection",
    "FindingSubject",
    "IdentifierSubject",
    "LocationEvidence",
    "Occurrence",
    "PathSubject",
    "ProjectSubject",
    "ReportedFinding",
    "Review",
    "RuleDeclarationError",
    "Severity",
    "Span",
    "TextEvidence",
    "Transition",
    "finding_fingerprint",
    "normalize_severity",
    "occurrence_key",
    "review_id",
    "rule_slug",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science/model && uv run --frozen pytest tests/test_audit_report.py -v`
Expected: PASS, 11 tests

Then: `cd science/model && uv run --frozen pytest -q` (the model suite is small and fast)
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/audit/
git add science/model/tests/test_audit_report.py
git commit -m "feat(audit): the report contract, with findings enveloped by producer"
```

---

### Task 8: Producer registration and the derived registry

**Files:**
- Create: `science/src/science_tool/findings/__init__.py`
- Create: `science/src/science_tool/findings/producers.py`
- Test: `science/tests/test_findings_registry.py`

**Interfaces:**
- Consumes: `FindingRule`, `FindingSection`, `RuleDeclarationError`, `ProducerMetrics` from `science_model.audit`.
- Produces: `FindingProducer`, `PRODUCER_NAMESPACES`, `build_registry(producers) -> FindingRegistry`, `FindingRegistry` (with `.rule(rule_id)`, `.section(section_id)`, `.sort_key(rule_id)`, `.validate_metrics(producer_id, metrics)`), `RegistryError`.

Registration is **generic** — not `HealthCheck`-shaped — so health checks, validation modules, `data_audit`, and later Pi lenses all participate without making health the ontology owner.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_findings_registry.py
import pytest
from pydantic import BaseModel, ConfigDict
from science_model.audit import FindingRule, FindingSection

from science_tool.findings.producers import (
    FindingProducer,
    RegistryError,
    build_registry,
)


class Q(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str


class M(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scanned: int


SECTION = FindingSection(id="datasets", title="Datasets", section_order=300)


def _rule(rule_id="dataset.stale-review", order=100) -> FindingRule:
    return FindingRule(
        id=rule_id, severities={"warn"}, subject_types={"entity"},
        qualifier_schema=Q, identity_qualifiers=("field",),
        title="t", section="datasets", display_order=order,
    )


def _producer(pid="dataset_anomalies", rules=None, metrics_schema=M) -> FindingProducer:
    return FindingProducer(
        producer_id=pid, namespace="health_checks", rules=tuple(rules or [_rule()]),
        sections=(SECTION,), metrics_schema=metrics_schema, remediators=frozenset(),
    )


def test_registry_resolves_a_declared_rule():
    registry = build_registry([_producer()])
    assert registry.rule("dataset.stale-review").title == "t"


def test_duplicate_rule_id_across_producers_fails():
    with pytest.raises(RegistryError, match="duplicate rule id"):
        build_registry([_producer(pid="a"), _producer(pid="b")])


def test_duplicate_producer_id_fails():
    with pytest.raises(RegistryError, match="duplicate producer id"):
        build_registry([_producer(), _producer(rules=[_rule("dataset.other")])])


def test_unknown_rule_lookup_fails_rather_than_returning_none():
    registry = build_registry([_producer()])
    with pytest.raises(RegistryError, match="undeclared rule"):
        registry.rule("dataset.never-declared")


def test_colliding_display_order_within_a_section_fails():
    with pytest.raises(RegistryError, match="display_order"):
        build_registry([
            _producer(rules=[_rule("dataset.a", 10), _rule("dataset.b", 10)])
        ])


def test_colliding_section_order_fails():
    other = FindingSection(id="tasks", title="Tasks", section_order=300)
    producer = FindingProducer(
        producer_id="p", namespace="health_checks", rules=(_rule(),),
        sections=(SECTION, other), metrics_schema=M, remediators=frozenset(),
    )
    with pytest.raises(RegistryError, match="section_order"):
        build_registry([producer])


def test_rule_naming_an_undeclared_section_fails():
    with pytest.raises(RegistryError, match="undeclared section"):
        build_registry([
            _producer(rules=[_rule("dataset.a")]).model_copy(update={"sections": ()})
        ])


def test_producer_remediation_without_a_registered_handler_fails():
    rule = FindingRule(
        id="dataset.fixable", severities={"warn"}, subject_types={"entity"},
        qualifier_schema=Q, identity_qualifiers=("field",), remediation="producer",
        remediator="fix_dataset", title="t", section="datasets", display_order=200,
    )
    with pytest.raises(RegistryError, match="remediator"):
        build_registry([_producer(rules=[rule])])


def test_sort_key_orders_by_section_then_display_order_not_by_name():
    alpha = FindingSection(id="zzz-last-alphabetically", title="Z", section_order=100)
    beta = FindingSection(id="aaa-first-alphabetically", title="A", section_order=200)
    producer = FindingProducer(
        producer_id="p", namespace="health_checks",
        rules=(
            FindingRule(id="z.rule", severities={"warn"}, subject_types={"project"},
                        qualifier_schema=Q, title="t", section=alpha.id, display_order=1),
            FindingRule(id="a.rule", severities={"warn"}, subject_types={"project"},
                        qualifier_schema=Q, title="t", section=beta.id, display_order=1),
        ),
        sections=(alpha, beta), metrics_schema=M, remediators=frozenset(),
    )
    registry = build_registry([producer])
    assert registry.sort_key("z.rule") < registry.sort_key("a.rule")


def test_metrics_are_validated_against_the_declared_schema():
    registry = build_registry([_producer()])
    registry.validate_metrics("dataset_anomalies", {"scanned": 3})
    with pytest.raises(RegistryError, match="metrics"):
        registry.validate_metrics("dataset_anomalies", {"scaned": 3})


def test_the_registry_mappings_are_not_mutable():
    registry = build_registry([_producer()])
    with pytest.raises(TypeError):
        registry.rules_by_id["injected"] = _rule("dataset.injected")
    with pytest.raises(TypeError):
        registry.sections_by_id["injected"] = SECTION
    with pytest.raises(TypeError):
        registry.producers_by_id["injected"] = _producer()


def test_project_config_cannot_add_or_override_a_rule(tmp_path):
    # The registry reads nothing from the filesystem, environment, or project config.
    # This test is the assertion that it has no such input at all.
    import inspect

    import science_tool.findings.producers as module

    source = inspect.getsource(module)
    for forbidden in ("yaml", "project_config", "os.environ", "science.yaml"):
        assert forbidden not in source, (
            f"{forbidden!r} appears in producers.py; the registry must not be "
            "project-overridable (design §6)"
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_findings_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.findings'`

- [ ] **Step 3: Write minimal implementation**

```python
# science/src/science_tool/findings/__init__.py
"""Audit-finding machinery: registry, storage, ingestion, CLI.

Import-side-effect free by design; nothing here registers anything on import.
"""
```

```python
# science/src/science_tool/findings/producers.py
"""Producer registration and the DERIVED frozen registry (design §6).

Rules are declared beside the producer that emits them; this module derives one
immutable lookup authority from those declarations. There is no hand-maintained
central table, so no repeated rule-id string can drift -- the defect that let
`dataset_access_invalid` be emitted while `DATASET_ANOMALY_CODES` declared eleven.

NOT project-overridable by construction: nothing here reads project configuration,
the environment, or any file. A project needing different audit rules is a design
conversation, not a config key.

Registration is GENERIC -- deliberately not `HealthCheck`-shaped -- so health
checks, validation modules, `data_audit`, and later Pi lenses all participate
without making health the ontology owner.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, ValidationError
from science_model.audit import FindingRule, FindingSection

#: Every namespace contributing producers to the derived registry. Each one MUST have
#: a filesystem-derived completeness guard (design §6); see
#: tests/test_findings_producer_namespaces.py.
PRODUCER_NAMESPACES: tuple[str, ...] = (
    "health_checks",
    "validate_checks",
    "data_audit",
)


class RegistryError(ValueError):
    """The derived registry is inconsistent, or a lookup names something undeclared."""


class FindingProducer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    producer_id: str
    namespace: str
    rules: tuple[FindingRule, ...]
    sections: tuple[FindingSection, ...] = ()
    metrics_schema: type[BaseModel] | None = None
    remediators: frozenset[str] = frozenset()


@dataclass(frozen=True)
class FindingRegistry:
    """The one immutable lookup authority.

    A frozen dataclass over `MappingProxyType`, not a Pydantic model over `dict`: a
    "frozen" model whose fields are plain dicts is mutable through those dicts, so
    `registry.rules_by_id[...] = ...` would silently work. The same idiom guards
    `autonomy/policy.py`'s allowlists.
    """

    rules_by_id: Mapping[str, FindingRule]
    sections_by_id: Mapping[str, FindingSection]
    producers_by_id: Mapping[str, FindingProducer]

    def rule(self, rule_id: str) -> FindingRule:
        try:
            return self.rules_by_id[rule_id]
        except KeyError:
            raise RegistryError(
                f"undeclared rule {rule_id!r}; a producer may only emit findings built "
                "from a declared FindingRule (design §6)"
            ) from None

    def section(self, section_id: str) -> FindingSection:
        try:
            return self.sections_by_id[section_id]
        except KeyError:
            raise RegistryError(f"undeclared section {section_id!r}") from None

    def sort_key(self, rule_id: str) -> tuple[int, int]:
        rule = self.rule(rule_id)
        return (self.section(rule.section).section_order, rule.display_order)

    def validate_metrics(self, producer_id: str, metrics: dict[str, object]) -> None:
        producer = self.producers_by_id.get(producer_id)
        if producer is None:
            raise RegistryError(f"unregistered producer {producer_id!r}")
        if producer.metrics_schema is None:
            if metrics:
                raise RegistryError(
                    f"{producer_id!r} declared no metrics schema but emitted metrics"
                )
            return
        try:
            producer.metrics_schema.model_validate(metrics)
        except ValidationError as exc:
            raise RegistryError(f"{producer_id!r} metrics invalid: {exc}") from exc


def build_registry(producers: list[FindingProducer]) -> FindingRegistry:
    """Derive the frozen registry, failing early on every §6 condition."""
    rules_by_id: dict[str, FindingRule] = {}
    sections_by_id: dict[str, FindingSection] = {}
    producers_by_id: dict[str, FindingProducer] = {}
    order_claims: dict[tuple[str, int], str] = {}
    section_order_claims: dict[int, str] = {}

    for producer in producers:
        if producer.producer_id in producers_by_id:
            raise RegistryError(f"duplicate producer id {producer.producer_id!r}")
        if producer.namespace not in PRODUCER_NAMESPACES:
            raise RegistryError(
                f"{producer.producer_id!r} declares namespace {producer.namespace!r}, "
                f"which is not in PRODUCER_NAMESPACES"
            )
        producers_by_id[producer.producer_id] = producer

        for section in producer.sections:
            existing = sections_by_id.get(section.id)
            if existing is not None and existing != section:
                raise RegistryError(f"conflicting declarations for section {section.id!r}")
            claimed = section_order_claims.get(section.section_order)
            if claimed is not None and claimed != section.id:
                raise RegistryError(
                    f"section_order {section.section_order} claimed by both "
                    f"{claimed!r} and {section.id!r}"
                )
            section_order_claims[section.section_order] = section.id
            sections_by_id[section.id] = section

        for rule in producer.rules:
            if rule.id in rules_by_id:
                raise RegistryError(f"duplicate rule id {rule.id!r}")
            rules_by_id[rule.id] = rule
            if rule.remediation == "producer":
                if not rule.remediator or rule.remediator not in producer.remediators:
                    raise RegistryError(
                        f"{rule.id!r} declares remediation='producer' but its remediator "
                        f"{rule.remediator!r} is not registered by "
                        f"{producer.producer_id!r}"
                    )

    for rule in rules_by_id.values():
        if rule.section not in sections_by_id:
            raise RegistryError(f"{rule.id!r} names undeclared section {rule.section!r}")
        claim = (rule.section, rule.display_order)
        claimed_by = order_claims.get(claim)
        if claimed_by is not None:
            raise RegistryError(
                f"display_order {rule.display_order} in section {rule.section!r} is "
                f"claimed by both {claimed_by!r} and {rule.id!r}"
            )
        order_claims[claim] = rule.id

    return FindingRegistry(
        rules_by_id=MappingProxyType(dict(rules_by_id)),
        sections_by_id=MappingProxyType(dict(sections_by_id)),
        producers_by_id=MappingProxyType(dict(producers_by_id)),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_findings_registry.py -v`
Expected: PASS, 12 tests

Then: `cd science && uv run ruff check && uv run pyright`
Expected: no findings

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/findings/ science/tests/test_findings_registry.py
git commit -m "feat(findings): derive the frozen rule registry from producer declarations"
```

---

### Task 9: Case storage

**Files:**
- Create: `science/src/science_tool/findings/paths.py`
- Create: `science/src/science_tool/findings/storage.py`
- Modify: `science/src/science_tool/graph/io.py:428-431` (add the exclude glob)
- Test: `science/tests/test_findings_paths.py`
- Test: `science/tests/test_findings_storage.py`

**Interfaces:**
- Consumes: `AuditFindingRecord`, `DOC_KIND`, `rule_slug`, `finding_fingerprint` from `science_model.audit`.
- Produces (paths): `PathSafetyError`, `resolve_inside(project_root, rel_path) -> Path`, `mkdir_inside(project_root, rel_dir) -> Path`, `project_relative(project_root, path) -> str`, `read_inside_bounded(project_root, path, max_bytes) -> str`, `open_read_bounded(path, max_bytes) -> str`, `open_write_nofollow(path) -> int`.
- Produces (storage): `CASES_DIRNAME = "doc/audits/cases"`, `MAX_CASE_BYTES`, `case_path(...)`, `write_case(project_root, record)`, `load_case(project_root, path)`, `load_cases(project_root)`, `CaseStorageError`.

Three reasons `paths.py` exists rather than inlining the checks:

1. **Checking only the final component is not symlink refusal.** A link at `doc/` or
   `doc/audits/` redirects the whole operation while `path.is_symlink()` on the leaf
   returns `False`. `resolve_inside` walks **every** component from the project root.
2. **Validating after mutating is not validating.** `Path.mkdir(parents=True)` follows
   links, so a linked `doc/audits` gets a real `cases/` created in its target — outside
   the project — before any check runs. `mkdir_inside` creates one component at a time
   through directory descriptors opened `O_DIRECTORY | O_NOFOLLOW`, so it stops *at* the
   link having created nothing beyond it.
3. **`stat()`-then-`read()` is a race.** `open_read_bounded` opens once with
   `O_NOFOLLOW`, then `fstat`s *that descriptor* and reads from it, so the file it
   sized is the file it read.

`load_case` takes the **project root**, not just a path, for the same reason: given a
bare path it would have to open it directly, which is precisely what following a link
looks like.

Unlike `write_run_record`, which is write-once (`O_EXCL`), a case is **upserted** — occurrences accumulate — so the write is temp-file-plus-rename rather than exclusive-create.

- [ ] **Step 1a: Write the failing path-safety test**

```python
# science/tests/test_findings_paths.py
from pathlib import Path

import pytest

from science_tool.findings.paths import (
    PathSafetyError,
    mkdir_inside,
    open_read_bounded,
    project_relative,
    read_inside_bounded,
    resolve_inside,
)


def test_resolve_inside_returns_the_path_when_every_component_is_real(tmp_path):
    (tmp_path / "doc" / "audits" / "cases").mkdir(parents=True)
    target = tmp_path / "doc" / "audits" / "cases" / "x.md"
    target.write_text("hi", encoding="utf-8")
    assert resolve_inside(tmp_path, "doc/audits/cases/x.md") == target


def test_resolve_inside_refuses_a_symlinked_INTERMEDIATE_component(tmp_path):
    # The leaf is a real file; `doc/audits` is the link. A check that only looked at
    # the final component would pass this.
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "cases").mkdir(parents=True)
    (elsewhere / "cases" / "x.md").write_text("hi", encoding="utf-8")
    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "audits").symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(PathSafetyError, match="symlink"):
        resolve_inside(tmp_path, "doc/audits/cases/x.md")


def test_resolve_inside_refuses_a_symlinked_leaf(tmp_path):
    (tmp_path / "real.md").write_text("hi", encoding="utf-8")
    (tmp_path / "link.md").symlink_to(tmp_path / "real.md")
    with pytest.raises(PathSafetyError, match="symlink"):
        resolve_inside(tmp_path, "link.md")


def test_resolve_inside_refuses_absolute_and_traversal(tmp_path):
    for bad in ("/etc/passwd", "../outside.md", "a/../b"):
        with pytest.raises(PathSafetyError):
            resolve_inside(tmp_path, bad)


def test_resolve_inside_tolerates_a_not_yet_existing_leaf(tmp_path):
    (tmp_path / "doc" / "audits" / "cases").mkdir(parents=True)
    assert resolve_inside(tmp_path, "doc/audits/cases/new.md").name == "new.md"


def test_open_read_bounded_reads_a_small_file(tmp_path):
    path = tmp_path / "a.json"
    path.write_text("{}", encoding="utf-8")
    assert open_read_bounded(path, 1024) == "{}"


def test_open_read_bounded_refuses_an_oversize_file(tmp_path):
    path = tmp_path / "a.json"
    path.write_text("x" * 100, encoding="utf-8")
    with pytest.raises(PathSafetyError, match="exceeds"):
        open_read_bounded(path, 10)


def test_open_read_bounded_refuses_a_symlink(tmp_path):
    real = tmp_path / "real.json"
    real.write_text("{}", encoding="utf-8")
    link = tmp_path / "link.json"
    link.symlink_to(real)
    with pytest.raises(PathSafetyError, match="symlink"):
        open_read_bounded(link, 1024)


def test_mkdir_inside_creates_the_whole_chain(tmp_path):
    created = mkdir_inside(tmp_path, "doc/audits/cases")
    assert created == tmp_path / "doc" / "audits" / "cases"
    assert created.is_dir()
    # Idempotent: an existing chain is not an error.
    assert mkdir_inside(tmp_path, "doc/audits/cases") == created


def test_mkdir_inside_refuses_a_symlinked_component_AND_CREATES_NOTHING_BEYOND_IT(
    tmp_path,
):
    # This is the ordering bug in its pure form. `doc/audits` is a link to a directory
    # that does NOT contain `cases/`. `Path.mkdir(parents=True)` would follow the link
    # and create `cases/` in the target -- outside the project -- and only then would a
    # validation step refuse the path, with the directory already made.
    target = tmp_path / "elsewhere"
    target.mkdir()
    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "audits").symlink_to(target, target_is_directory=True)

    with pytest.raises(PathSafetyError, match="symlink or not a directory"):
        mkdir_inside(tmp_path, "doc/audits/cases")

    assert list(target.iterdir()) == [], "a directory was created in the link target"


def test_mkdir_inside_refuses_a_component_that_is_a_regular_file(tmp_path):
    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "audits").write_text("not a directory", encoding="utf-8")
    with pytest.raises(PathSafetyError, match="symlink or not a directory"):
        mkdir_inside(tmp_path, "doc/audits/cases")


def test_project_relative_returns_the_relative_spelling(tmp_path):
    assert project_relative(tmp_path, tmp_path / "doc" / "x.md") == "doc/x.md"
    assert project_relative(tmp_path, Path("doc/x.md")) == "doc/x.md"


def test_project_relative_refuses_a_path_outside_the_project(tmp_path):
    outside = tmp_path.parent / "not-in-here.json"
    with pytest.raises(PathSafetyError, match="outside the project root"):
        project_relative(tmp_path, outside)
    with pytest.raises(PathSafetyError, match=r"\.\."):
        project_relative(tmp_path, tmp_path / ".." / "escape.json")


def test_read_inside_bounded_refuses_a_symlinked_PARENT(tmp_path):
    # The leaf is a real file inside the link target, so a leaf-only `O_NOFOLLOW`
    # check reads it happily.
    target = tmp_path / "elsewhere"
    target.mkdir()
    (target / "report.json").write_text("{}", encoding="utf-8")
    (tmp_path / "runs").symlink_to(target, target_is_directory=True)
    with pytest.raises(PathSafetyError, match="symlink"):
        read_inside_bounded(tmp_path, tmp_path / "runs" / "report.json", 1024)


def test_read_inside_bounded_reads_a_real_file(tmp_path):
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / "report.json").write_text("{}", encoding="utf-8")
    assert read_inside_bounded(tmp_path, tmp_path / "runs" / "report.json", 1024) == "{}"
```

- [ ] **Step 1b: Write the failing storage test**

```python
# science/tests/test_findings_storage.py
from datetime import UTC, datetime

import pytest
from science_model.audit import (
    AuditFindingRecord,
    EntitySubject,
    Occurrence,
    Transition,
    finding_fingerprint,
    occurrence_key,
)

from science_tool.findings.storage import (
    CASES_DIRNAME,
    CaseStorageError,
    case_path,
    load_case,
    load_cases,
    write_case,
)

NOW = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
SUBJECT = EntitySubject(ref="dataset:gtex-v8")
RULE = "dataset.cached-field-drift"
QUALS = {"field": "year"}


def _occurrence(finding_id: str, *, ingestion_ref: str = "ing:1") -> Occurrence:
    return Occurrence(
        idempotency_key=occurrence_key(
            producer_id="dataset_anomalies",
            ingestion_ref=ingestion_ref,
            finding_id=finding_id,
        ),
        producer_id="dataset_anomalies",
        ingestion_ref=ingestion_ref,
        observed_at=NOW,
        severity="warn",
        message="drifted",
        qualifiers={"field": "year"},
        evidence=(),
    )


def _record(quals: dict | None = None) -> AuditFindingRecord:
    quals = QUALS if quals is None else quals
    finding_id = finding_fingerprint(
        rule_id=RULE, subject=SUBJECT, identity_qualifiers=quals
    )
    return AuditFindingRecord(
        finding_id=finding_id,
        fingerprint_version=1,
        rule_id=RULE,
        subject=SUBJECT,
        identity_qualifiers=quals,
        occurrences=(_occurrence(finding_id),),
        transitions=(
            Transition(from_status=None, to_status="proposed", actor="ingest", at=NOW,
                       reason="detected"),
        ),
        status="proposed",
    )


def test_case_path_carries_the_rule_slug_and_the_full_digest(tmp_path):
    record = _record()
    path = case_path(tmp_path, record)
    assert path.parent == tmp_path / CASES_DIRNAME
    assert path.name == f"dataset-cached-field-drift--{record.finding_id}.md"


def test_write_then_load_round_trips(tmp_path):
    record = _record()
    path = write_case(tmp_path, record)
    assert load_case(tmp_path, path) == record


def test_write_is_an_upsert_not_a_write_once(tmp_path):
    record = _record()
    write_case(tmp_path, record)
    grown = record.with_occurrence(_occurrence(record.finding_id, ingestion_ref="ing:2"))
    write_case(tmp_path, grown)
    assert len(load_case(tmp_path, case_path(tmp_path, record)).occurrences) == 2


def test_frontmatter_carries_doc_kind_and_never_an_entity_kind(tmp_path):
    text = write_case(tmp_path, _record()).read_text(encoding="utf-8")
    assert "doc_kind: audit-case" in text
    assert "\nkind:" not in text
    assert "\nid:" not in text


def test_load_refuses_a_filename_whose_digest_disagrees(tmp_path):
    record = _record()
    path = write_case(tmp_path, record)
    moved = path.with_name(f"dataset-cached-field-drift--{'0' * 64}.md")
    path.rename(moved)
    with pytest.raises(CaseStorageError, match="filename digest"):
        load_case(tmp_path, moved)


def test_load_refuses_a_filename_whose_slug_disagrees(tmp_path):
    record = _record()
    path = write_case(tmp_path, record)
    moved = path.with_name(f"some-other-rule--{record.finding_id}.md")
    path.rename(moved)
    with pytest.raises(CaseStorageError, match="filename slug"):
        load_case(tmp_path, moved)


def test_load_refuses_a_record_whose_finding_id_is_not_its_own_fingerprint(tmp_path):
    record = _record()
    path = write_case(tmp_path, record)
    text = path.read_text(encoding="utf-8")
    # Edit only the identity qualifier, leaving finding_id alone: the recomputed
    # fingerprint no longer matches what the file claims.
    tampered = text.replace("field: year", "field: month")
    assert tampered != text
    path.write_text(tampered, encoding="utf-8")
    with pytest.raises(CaseStorageError, match="recomputed fingerprint"):
        load_case(tmp_path, path)


def test_write_refuses_a_symlinked_cases_directory(tmp_path):
    real = tmp_path / "elsewhere"
    real.mkdir()
    link_parent = tmp_path / "doc" / "audits"
    link_parent.mkdir(parents=True)
    (link_parent / "cases").symlink_to(real, target_is_directory=True)
    with pytest.raises(CaseStorageError, match="symlink"):
        write_case(tmp_path, _record())


def test_write_refuses_a_symlinked_PARENT_of_the_cases_directory(tmp_path):
    # `doc/audits` is the link, `cases/` under it is real. Checking only the final
    # directory would miss this entirely.
    real = tmp_path / "elsewhere"
    (real / "cases").mkdir(parents=True)
    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "audits").symlink_to(real, target_is_directory=True)
    with pytest.raises(CaseStorageError, match="symlink"):
        write_case(tmp_path, _record())


def test_write_creates_nothing_inside_a_symlinked_parents_target(tmp_path):
    # The link target does NOT yet contain `cases/`. A `mkdir(parents=True)` that runs
    # before validation would create it there, outside the project, and the later
    # refusal would arrive after the damage. Nothing must appear in the target.
    real = tmp_path / "elsewhere"
    real.mkdir()
    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "audits").symlink_to(real, target_is_directory=True)
    with pytest.raises(CaseStorageError, match="symlink|not a directory"):
        write_case(tmp_path, _record())
    assert list(real.iterdir()) == []


def test_load_refuses_a_case_reached_through_a_symlinked_parent(tmp_path):
    write_case(tmp_path, _record())
    real_cases = tmp_path / "doc" / "audits" / "cases"
    moved = tmp_path / "moved-cases"
    real_cases.rename(moved)
    real_cases.symlink_to(moved, target_is_directory=True)
    with pytest.raises(CaseStorageError, match="symlink"):
        load_cases(tmp_path)


def test_load_cases_returns_every_case_sorted_by_finding_id(tmp_path):
    write_case(tmp_path, _record())
    # Built through the constructor, not model_copy: the finding_id, the occurrence
    # keys, and the identity qualifiers must agree, and only construction checks that.
    write_case(tmp_path, _record(quals={"field": "url"}))
    loaded = load_cases(tmp_path)
    assert [r.finding_id for r in loaded] == sorted(r.finding_id for r in loaded)
    assert len(loaded) == 2


def test_load_cases_on_a_project_with_no_cases_returns_empty(tmp_path):
    assert load_cases(tmp_path) == []


def test_load_cases_refuses_a_DANGLING_cases_symlink(tmp_path):
    # `Path.exists()` follows links, so this reads as absent and would report "no
    # findings" for a store that was redirected somewhere that no longer exists.
    # Absence must mean nothing is there under any name.
    (tmp_path / "doc" / "audits").mkdir(parents=True)
    (tmp_path / "doc" / "audits" / "cases").symlink_to(
        tmp_path / "gone", target_is_directory=True
    )
    with pytest.raises(CaseStorageError, match="symlink"):
        load_cases(tmp_path)


def test_load_cases_refuses_a_cases_path_that_is_not_a_directory(tmp_path):
    (tmp_path / "doc" / "audits").mkdir(parents=True)
    (tmp_path / "doc" / "audits" / "cases").write_text("nope", encoding="utf-8")
    with pytest.raises(CaseStorageError, match="not a directory"):
        load_cases(tmp_path)


def test_load_case_refuses_a_case_reached_through_a_symlinked_parent(tmp_path):
    # `load_case` takes the project root precisely so it walks components. Given only
    # a path, it would open whatever the link pointed at.
    write_case(tmp_path, _record())
    real_cases = tmp_path / "doc" / "audits" / "cases"
    moved = tmp_path / "moved-cases"
    real_cases.rename(moved)
    real_cases.symlink_to(moved, target_is_directory=True)
    with pytest.raises(CaseStorageError, match="symlink"):
        load_case(tmp_path, case_path(tmp_path, _record()))


def test_load_case_refuses_a_path_outside_the_project(tmp_path):
    outside = tmp_path.parent / "stray.md"
    outside.write_text("---\ndoc_kind: audit-case\n---\n", encoding="utf-8")
    with pytest.raises(CaseStorageError, match="outside the project root"):
        load_case(tmp_path, outside)


def test_load_case_refuses_a_file_with_no_frontmatter(tmp_path):
    path = write_case(tmp_path, _record())
    path.write_text("just a body, no frontmatter\n", encoding="utf-8")
    with pytest.raises(CaseStorageError, match="frontmatter"):
        load_case(tmp_path, path)
```

- [ ] **Step 2: Run both tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_findings_paths.py tests/test_findings_storage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.findings.paths'`

- [ ] **Step 3: Write minimal implementation**

```python
# science/src/science_tool/findings/paths.py
"""One hardened path primitive, used for every filesystem touch in this package.

Three failures this exists to prevent:

1. **Partial symlink checks.** `path.is_symlink()` on a leaf says nothing about
   `doc/` or `doc/audits/`. A link at any component redirects the whole operation
   while the leaf check passes, so `resolve_inside` walks EVERY component.
2. **Mutating before validating.** `Path.mkdir(parents=True)` FOLLOWS links: if
   `doc/audits` is a link, it happily creates `cases/` in the target, outside the
   project, and only then does a later check refuse the path. The damage is already
   done. `mkdir_inside` therefore creates one component at a time through directory
   descriptors opened `O_DIRECTORY | O_NOFOLLOW`, so it stops AT the link having
   created nothing beyond it.
3. **stat-then-read races.** Sizing a path and then opening it are two lookups of a
   name that can change in between. `open_read_bounded` opens ONCE with `O_NOFOLLOW`
   and `fstat`s that descriptor, so the file it sized is the file it read.
"""

from __future__ import annotations

import os
from pathlib import Path


class PathSafetyError(ValueError):
    """A path is absolute, escapes the project, or passes through a symlink."""


def _segments(rel_path: str) -> list[str]:
    """The validated components of a project-relative path.

    `..` is REFUSED, never collapsed: collapsing `a/../b` lexically answers a question
    about the filesystem (what is `a`?) with string arithmetic.
    """
    candidate = rel_path.replace("\\", "/")
    if candidate.startswith("/"):
        raise PathSafetyError(f"path must be project-relative, got {rel_path!r}")
    parts = [s for s in candidate.split("/") if s not in ("", ".")]
    if any(segment == ".." for segment in parts):
        raise PathSafetyError(f"path contains a `..` segment: {rel_path!r}")
    if not parts:
        raise PathSafetyError(f"path names no file, got {rel_path!r}")
    return parts


def resolve_inside(project_root: Path, rel_path: str) -> Path:
    """Return `project_root / rel_path`, refusing a symlink at ANY component.

    The leaf need not exist -- callers create case files. Every component that DOES
    exist, including the leaf, must be a real entry rather than a link.
    """
    root = project_root.resolve()
    current = root
    for segment in _segments(rel_path):
        current = current / segment
        if current.is_symlink():
            raise PathSafetyError(
                f"{current} is a symlink; every component of {rel_path!r} must be a "
                "real entry inside the project"
            )
    return current


def mkdir_inside(project_root: Path, rel_dir: str) -> Path:
    """Create every component of `rel_dir`, never traversing or creating a link.

    Each component is created relative to a descriptor for its parent and then
    REOPENED `O_DIRECTORY | O_NOFOLLOW`. `mkdir` does not follow a final symlink, so a
    linked component raises `FileExistsError`, and the reopen then fails with `ELOOP`
    -- refusing BEFORE any deeper component is created. `Path.mkdir(parents=True)`
    followed by a check cannot offer this: by the time the check runs, directories
    have already been created wherever the link pointed.
    """
    segments = _segments(rel_dir)
    root = project_root.resolve()
    current = root
    parent_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for segment in segments:
            current = current / segment
            try:
                os.mkdir(segment, mode=0o755, dir_fd=parent_fd)
            except FileExistsError:
                pass  # may be a real directory -- the reopen below decides
            except OSError as exc:
                raise PathSafetyError(f"could not create {current}: {exc}") from exc
            try:
                child_fd = os.open(
                    segment,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=parent_fd,
                )
            except OSError as exc:
                raise PathSafetyError(
                    f"{current} is a symlink or not a directory; every component of "
                    f"{rel_dir!r} must be a real directory inside the project ({exc})"
                ) from exc
            os.close(parent_fd)
            parent_fd = child_fd
    finally:
        os.close(parent_fd)
    return current


def project_relative(project_root: Path, path: Path) -> str:
    """The project-relative spelling of an absolute-or-relative `path`, or refuse.

    Used for caller-supplied paths -- the report file, a case file handed back by
    `case_path` -- so they go through the same component walk as everything else.
    `path` is NOT resolved: resolving would follow the very links this refuses, and a
    symlinked report would silently be read as its target.

    Both spellings of the root are accepted because the caller may name the project
    with an unresolved prefix (`/tmp/...` where `/tmp` is a link) while the walk
    starts from the resolved one. Which spelling matched changes nothing: the
    authoritative refusal is `resolve_inside`, below.
    """
    candidate = path if path.is_absolute() else (project_root / path)
    if ".." in candidate.parts:
        raise PathSafetyError(f"path contains a `..` segment: {path}")
    normalized = Path(os.path.normpath(candidate))
    for base in (project_root.resolve(), Path(os.path.normpath(project_root))):
        try:
            return normalized.relative_to(base).as_posix()
        except ValueError:
            continue
    raise PathSafetyError(f"{path} is outside the project root {project_root}")


def read_inside_bounded(project_root: Path, path: Path, max_bytes: int) -> str:
    """Read a caller-supplied path after the full inside-the-project component walk."""
    return open_read_bounded(
        resolve_inside(project_root, project_relative(project_root, path)), max_bytes
    )


def open_read_bounded(path: Path, max_bytes: int) -> str:
    """Read at most `max_bytes`, refusing symlinks, with no stat/read race."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        # ELOOP is what O_NOFOLLOW raises on a symlinked final component.
        raise PathSafetyError(
            f"could not open {path} without following a symlink: {exc}"
        ) from exc
    try:
        size = os.fstat(descriptor).st_size
        if size > max_bytes:
            raise PathSafetyError(f"{path} is {size} bytes, which exceeds {max_bytes}")
        data = os.read(descriptor, max_bytes + 1)
    finally:
        os.close(descriptor)
    if len(data) > max_bytes:
        raise PathSafetyError(f"{path} exceeds {max_bytes} bytes")
    return data.decode("utf-8")


def open_write_nofollow(path: Path) -> int:
    """Open for writing, refusing to follow a symlink at the final component."""
    try:
        return os.open(
            path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644
        )
    except OSError as exc:
        raise PathSafetyError(f"could not write {path} without following a link: {exc}") from exc
```

```python
# science/src/science_tool/findings/storage.py
"""Canonical case files under `doc/audits/cases/` (design §5).

NOT `entities/` and NOT any directory named `findings/`: `EntityKind.FINDING` is a
live epistemic kind, and `_infer_kind_from_path` keys on `path.parent.name` with no
root anchoring, so a `findings/` directory anywhere would infer that kind. `cases`
is absent from `_DIR_TO_KIND`.

Unlike `write_run_record`, which is write-once via `O_EXCL`, a case is UPSERTED:
occurrences accumulate. The write is therefore temp-file-plus-rename, with symlink
refusal on the directory and on the target.

Loaders validate the filename against the contents. A case whose slug, digest, or
stored `finding_id` disagrees with the fingerprint recomputed from its own immutable
fields is a LOAD ERROR -- never a silent repair or rename.
"""

from __future__ import annotations

import os
from pathlib import Path

from science_model.audit import DOC_KIND, AuditFindingRecord, finding_fingerprint, rule_slug
from science_model.frontmatter import render_frontmatter, split_frontmatter

from science_tool.findings.paths import (
    PathSafetyError,
    mkdir_inside,
    open_write_nofollow,
    read_inside_bounded,
    resolve_inside,
)

CASES_DIRNAME = "doc/audits/cases"

#: A case is frontmatter plus one comment line. Anything approaching this is a file
#: someone else's tooling wrote into `cases/`, and reading it unbounded is the same
#: mistake as reading an unbounded report.
MAX_CASE_BYTES = 4 * 1024 * 1024

_BODY = (
    "<!-- Project-state case about repository or corpus hygiene. Not a KG entity: "
    "carries no `kind:`/`id:`, never materializes into the knowledge graph, never "
    "affects belief or attention. See "
    "docs/plans/2026-07-27-finding-convergence-design.md -->\n"
)


class CaseStorageError(ValueError):
    """A case file could not be written, read, or trusted."""


def cases_dir(project_root: Path) -> Path:
    return project_root / CASES_DIRNAME


def case_filename(record: AuditFindingRecord) -> str:
    return f"{rule_slug(record.rule_id)}--{record.finding_id}.md"


def case_path(project_root: Path, record: AuditFindingRecord) -> Path:
    return cases_dir(project_root) / case_filename(record)


def write_case(project_root: Path, record: AuditFindingRecord) -> Path:
    relative = f"{CASES_DIRNAME}/{case_filename(record)}"
    try:
        # `mkdir_inside`, NOT `mkdir(parents=True)` then a check: the latter follows a
        # linked component and creates directories in its target before anything has
        # been validated. Validation that runs after the mutation it was meant to
        # prevent is not validation.
        mkdir_inside(project_root, CASES_DIRNAME)
        path = resolve_inside(project_root, relative)
    except PathSafetyError as exc:
        raise CaseStorageError(str(exc)) from exc
    except OSError as exc:
        raise CaseStorageError(
            f"could not create {cases_dir(project_root)}: {exc}"
        ) from exc

    payload = {"doc_kind": DOC_KIND, **record.model_dump(mode="json", exclude_none=True)}
    text = render_frontmatter(payload, _BODY)
    temp = path.with_name(f".{path.name}.tmp")
    try:
        descriptor = open_write_nofollow(temp)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temp, path)
    except PathSafetyError as exc:
        temp.unlink(missing_ok=True)
        raise CaseStorageError(str(exc)) from exc
    except OSError as exc:
        temp.unlink(missing_ok=True)
        raise CaseStorageError(f"could not write case to {path}: {exc}") from exc
    return path


def load_case(project_root: Path, path: Path) -> AuditFindingRecord:
    """Read one case. Takes the project root so it uses the SAME component walk as
    every other filesystem touch here -- `parse_frontmatter(path)` would open the path
    directly, following any link on the way to it."""
    try:
        text = read_inside_bounded(project_root, path, MAX_CASE_BYTES)
    except PathSafetyError as exc:
        raise CaseStorageError(str(exc)) from exc
    except OSError as exc:
        raise CaseStorageError(f"could not read {path}: {exc}") from exc
    frontmatter, _body = split_frontmatter(text)
    if not frontmatter:
        raise CaseStorageError(f"{path} has no parsable frontmatter")
    if frontmatter.get("doc_kind") != DOC_KIND:
        raise CaseStorageError(
            f"{path} is not a {DOC_KIND}; got doc_kind={frontmatter.get('doc_kind')!r}"
        )
    fields = {k: v for k, v in frontmatter.items() if k != "doc_kind"}
    try:
        record = AuditFindingRecord.model_validate(fields)
    except Exception as exc:  # pydantic ValidationError or RecordError
        raise CaseStorageError(f"{path} is not a valid case: {exc}") from exc

    expected_slug = rule_slug(record.rule_id)
    stem = path.stem
    if "--" not in stem:
        raise CaseStorageError(f"{path.name} is not `<rule-slug>--<digest>.md`")
    slug, _, digest = stem.rpartition("--")
    if slug != expected_slug:
        raise CaseStorageError(
            f"{path.name}: filename slug {slug!r} != {expected_slug!r} for rule "
            f"{record.rule_id!r}"
        )
    if digest != record.finding_id:
        raise CaseStorageError(
            f"{path.name}: filename digest does not match finding_id "
            f"{record.finding_id!r}"
        )
    recomputed = finding_fingerprint(
        rule_id=record.rule_id,
        subject=record.subject,
        identity_qualifiers=record.identity_qualifiers,
    )
    if recomputed != record.finding_id:
        raise CaseStorageError(
            f"{path.name}: recomputed fingerprint {recomputed!r} != stored finding_id "
            f"{record.finding_id!r}; a case never acquires a new identity by being edited"
        )
    return record


def load_cases(project_root: Path) -> list[AuditFindingRecord]:
    directory = cases_dir(project_root)
    # `lstat`, not `exists()`: `exists()` follows links, so a DANGLING `cases` symlink
    # reads as absent and the caller is told "no findings" about a store that was
    # redirected out from under it. Absence must mean nothing is there under ANY name.
    try:
        os.lstat(directory)
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise CaseStorageError(f"could not stat {directory}: {exc}") from exc

    # Something is there. It must be a real directory reached without a link -- a
    # redirected or replaced case store is an unavailable instrument, not an empty one.
    try:
        resolved = resolve_inside(project_root, CASES_DIRNAME)
    except PathSafetyError as exc:
        raise CaseStorageError(str(exc)) from exc
    if not resolved.is_dir():
        raise CaseStorageError(
            f"{resolved} exists but is not a directory; refusing to report zero cases "
            "from a path that cannot hold any"
        )
    records = [
        load_case(project_root, path) for path in sorted(resolved.glob("*.md"))
    ]
    return sorted(records, key=lambda r: r.finding_id)
```

Then modify `science/src/science_tool/graph/io.py`. The current tuple is:

```python
DEFAULT_REVISION_MANIFEST_EXCLUDES: tuple[str, ...] = (
    "doc/curations/*.md",
    "doc/meta/*-next-steps.md",
)
```

Change it to:

```python
DEFAULT_REVISION_MANIFEST_EXCLUDES: tuple[str, ...] = (
    "doc/curations/*.md",
    "doc/meta/*-next-steps.md",
    # Audit cases have the same property as curation ledgers, at higher volume: they
    # contribute NO triples but would be hashed into the manifest, so every ingestion
    # would flip the graph to stale. Shipped as a default so no project rediscovers
    # the knob (design §5).
    "doc/audits/cases/*.md",
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_findings_paths.py tests/test_findings_storage.py -v`
Expected: PASS — 15 path tests, 18 storage tests

Then the manifest-exclude guard, to confirm the new glob broke nothing:
Run: `cd science && uv run --frozen pytest tests/test_graph_io_revision_manifest.py tests/test_graph_io.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/findings/paths.py science/src/science_tool/findings/storage.py
git add science/tests/test_findings_paths.py science/tests/test_findings_storage.py
git add science/src/science_tool/graph/io.py
git commit -m "feat(findings): hardened path handling and case storage bound to its filename"
```

---

### Task 10: Trusted ingestion

**Files:**
- Create: `science/src/science_tool/findings/ingest.py`
- Test: `science/tests/test_findings_ingest.py`

**Interfaces:**
- Consumes: Tasks 6–9.
- Produces: `ingest_report(project_root, report, registry, *, actor="ingest") -> IngestOutcome`, `IngestOutcome` (`records_written`, `occurrences_appended`, `occurrences_skipped`), `IngestError`, `MAX_REPORT_BYTES = 8 * 1024 * 1024`, `load_report(project_root, path) -> AuditReport`.

Not a multi-file transaction, and it does not claim to be: full prevalidation, then atomic per-record writes under a project-scoped lock, with **idempotent retry** as the documented recovery from partial I/O failure (§8).

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_findings_ingest.py
import json
from collections import Counter

import pytest
from pydantic import BaseModel, ConfigDict
from science_model.audit import (
    AuditFinding,
    AuditReport,
    EntitySubject,
    FindingRule,
    FindingSection,
    ReportedFinding,
)

from science_tool.findings.ingest import IngestError, ingest_report, load_report
from science_tool.findings.producers import FindingProducer, build_registry
from science_tool.findings.storage import load_cases


class Q(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str = ""
    #: Declared on the schema but deliberately absent from `RULE.identity_qualifiers`.
    #: This is the non-identity qualifier the collision and survival tests turn on; a
    #: qualifier the schema rejects would fail validation before identity ever matters.
    note: str = ""


SECTION = FindingSection(id="datasets", title="Datasets", section_order=300)
RULE = FindingRule(
    id="dataset.stale-review", severities={"warn"}, subject_types={"entity"},
    qualifier_schema=Q, identity_qualifiers=("field",), title="t",
    section="datasets", display_order=100,
)
REGISTRY = build_registry([
    FindingProducer(
        producer_id="dataset_anomalies", namespace="health_checks", rules=(RULE,),
        sections=(SECTION,), metrics_schema=None, remediators=frozenset(),
    )
])


def _finding(**overrides) -> AuditFinding:
    base = dict(
        rule_id="dataset.stale-review", subject=EntitySubject(ref="dataset:a"),
        severity="warn", qualifiers={"field": "year"}, message="stale", evidence=[],
    )
    return AuditFinding(**{**base, **overrides})


def _report(findings=None, accepted=None, **overrides) -> AuditReport:
    findings = findings if findings is not None else [
        ReportedFinding(producer_id="dataset_anomalies", finding=_finding())
    ]
    accepted = accepted or []
    # `findings_by_severity` is DERIVED here, not hardcoded: `AuditReport` now checks
    # the breakdown against the channel, so a helper that always says `warn` would make
    # every non-warn test fail at construction instead of where it means to.
    base = dict(
        schema_version=2, fingerprint_version=1, ingestion_ref="ing:1",
        generated_at="2026-07-27T12:00:00+00:00", findings=findings, accepted=accepted,
        metrics={}, unwired=[],
        totals={"findings_total": len(findings),
                "findings_by_severity": dict(
                    Counter(item.finding.severity for item in findings)
                ),
                "accepted_total": len(accepted), "unwired_total": 0},
        meta={"producers_run": ["dataset_anomalies"], "total_duration_seconds": 0.1,
              "timings": []},
    )
    return AuditReport(**{**base, **overrides})


def test_ingest_writes_a_case_with_a_genesis_transition(tmp_path):
    outcome = ingest_report(tmp_path, _report(), REGISTRY)
    assert outcome.records_written == 1
    record = load_cases(tmp_path)[0]
    assert record.status == "proposed"
    assert record.transitions[0].from_status is None
    assert len(record.occurrences) == 1


def test_reingesting_an_identical_report_appends_nothing(tmp_path):
    ingest_report(tmp_path, _report(), REGISTRY)
    second = ingest_report(tmp_path, _report(), REGISTRY)
    assert second.occurrences_appended == 0
    assert second.occurrences_skipped == 1
    assert len(load_cases(tmp_path)[0].occurrences) == 1


def test_a_later_ingestion_ref_appends_a_second_occurrence(tmp_path):
    ingest_report(tmp_path, _report(), REGISTRY)
    ingest_report(tmp_path, _report(ingestion_ref="ing:2"), REGISTRY)
    assert len(load_cases(tmp_path)[0].occurrences) == 2


def test_same_key_with_different_content_is_an_error_not_a_retry(tmp_path):
    ingest_report(tmp_path, _report(), REGISTRY)
    conflicting = _report(findings=[
        ReportedFinding(
            producer_id="dataset_anomalies", finding=_finding(message="DIFFERENT")
        )
    ])
    with pytest.raises(IngestError, match="idempotency"):
        ingest_report(tmp_path, conflicting, REGISTRY)


def test_two_producers_upsert_one_record_with_two_occurrences(tmp_path):
    registry = build_registry([
        FindingProducer(
            producer_id="dataset_anomalies", namespace="health_checks", rules=(RULE,),
            sections=(SECTION,), metrics_schema=None, remediators=frozenset(),
        ),
        FindingProducer(
            producer_id="curation_lens", namespace="health_checks", rules=(),
            sections=(), metrics_schema=None, remediators=frozenset(),
        ),
    ])
    report = _report(findings=[
        ReportedFinding(producer_id="dataset_anomalies", finding=_finding()),
        ReportedFinding(producer_id="curation_lens", finding=_finding()),
    ])
    ingest_report(tmp_path, report, registry)
    records = load_cases(tmp_path)
    assert len(records) == 1
    assert {o.producer_id for o in records[0].occurrences} == {
        "dataset_anomalies", "curation_lens"
    }


def test_no_arrival_order_dependence(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    first = _report(findings=[
        ReportedFinding(producer_id="dataset_anomalies", finding=_finding())
    ])
    second = _report(ingestion_ref="ing:2", findings=[
        ReportedFinding(
            producer_id="dataset_anomalies", finding=_finding(message="later")
        )
    ])
    ingest_report(a, first, REGISTRY)
    ingest_report(a, second, REGISTRY)
    ingest_report(b, second, REGISTRY)
    ingest_report(b, first, REGISTRY)
    ra, rb = load_cases(a)[0], load_cases(b)[0]
    assert ra.finding_id == rb.finding_id
    assert sorted(o.idempotency_key for o in ra.occurrences) == sorted(
        o.idempotency_key for o in rb.occurrences
    )


def test_non_identity_qualifiers_survive_on_the_occurrence(tmp_path):
    report = _report(findings=[
        ReportedFinding(
            producer_id="dataset_anomalies",
            finding=_finding(qualifiers={"field": "year", "note": "extra"}),
        )
    ])
    ingest_report(tmp_path, report, REGISTRY)
    record = load_cases(tmp_path)[0]
    assert set(record.occurrences[0].qualifiers) == {"field", "note"}
    assert set(record.identity_qualifiers) == {"field"}


def test_accepted_observations_are_ingested_and_leave_status_alone(tmp_path):
    from science_model.audit import AcceptedFinding

    report = _report(
        findings=[],
        accepted=[
            AcceptedFinding(
                producer_id="dataset_anomalies", finding=_finding(),
                acceptance_key="b" * 32, reason="known",
            )
        ],
    )
    ingest_report(tmp_path, report, REGISTRY)
    record = load_cases(tmp_path)[0]
    assert record.status == "proposed"
    assert record.occurrences[0].acceptance_key == "b" * 32


def test_the_same_observation_accepted_and_unsuppressed_conflicts(tmp_path):
    from science_model.audit import AcceptedFinding

    ingest_report(tmp_path, _report(), REGISTRY)
    with pytest.raises(IngestError, match="idempotency"):
        ingest_report(
            tmp_path,
            _report(findings=[], accepted=[
                AcceptedFinding(
                    producer_id="dataset_anomalies", finding=_finding(),
                    acceptance_key="b" * 32, reason="known",
                )
            ]),
            REGISTRY,
        )


def test_an_undeclared_rule_is_refused(tmp_path):
    report = _report(findings=[
        ReportedFinding(
            producer_id="dataset_anomalies",
            finding=_finding(rule_id="dataset.never-declared"),
        )
    ])
    with pytest.raises(IngestError, match="undeclared rule"):
        ingest_report(tmp_path, report, REGISTRY)


def test_an_unregistered_producer_is_refused(tmp_path):
    report = _report(findings=[
        ReportedFinding(producer_id="who", finding=_finding())
    ])
    with pytest.raises(IngestError, match="unregistered producer"):
        ingest_report(tmp_path, report, REGISTRY)


def test_a_severity_outside_the_rule_is_refused(tmp_path):
    report = _report(findings=[
        ReportedFinding(
            producer_id="dataset_anomalies", finding=_finding(severity="error")
        )
    ])
    with pytest.raises(IngestError, match="severity"):
        ingest_report(tmp_path, report, REGISTRY)


def test_a_validation_failure_writes_nothing(tmp_path):
    # The first finding is valid, the second names an undeclared rule. Prevalidation
    # must reject the whole report before the first one reaches disk.
    valid = ReportedFinding(producer_id="dataset_anomalies", finding=_finding())
    invalid = ReportedFinding(
        producer_id="dataset_anomalies",
        finding=_finding(
            subject=EntitySubject(ref="dataset:b"), rule_id="dataset.never-declared"
        ),
    )
    with pytest.raises(IngestError):
        ingest_report(tmp_path, _report(findings=[valid, invalid]), REGISTRY)
    assert load_cases(tmp_path) == []


def test_partial_failure_is_repaired_by_rerunning_the_same_report(tmp_path):
    # Simulate a crash after the first of two records is written, by writing the
    # first record alone and then re-ingesting the whole report.
    first_only = _report(findings=[
        ReportedFinding(producer_id="dataset_anomalies", finding=_finding())
    ])
    ingest_report(tmp_path, first_only, REGISTRY)
    both = _report(findings=[
        ReportedFinding(producer_id="dataset_anomalies", finding=_finding()),
        ReportedFinding(
            producer_id="dataset_anomalies",
            finding=_finding(subject=EntitySubject(ref="dataset:b")),
        ),
    ])
    outcome = ingest_report(tmp_path, both, REGISTRY)
    assert outcome.occurrences_skipped == 1
    assert len(load_cases(tmp_path)) == 2
    for record in load_cases(tmp_path):
        assert len(record.occurrences) == 1


def test_load_report_refuses_an_unknown_schema_version(tmp_path):
    path = tmp_path / "report.json"
    path.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
    with pytest.raises(IngestError, match="schema_version"):
        load_report(tmp_path, path)


def test_load_report_refuses_an_oversize_report(tmp_path):
    from science_tool.findings.ingest import MAX_REPORT_BYTES

    path = tmp_path / "report.json"
    path.write_text("x" * (MAX_REPORT_BYTES + 1), encoding="utf-8")
    with pytest.raises(IngestError, match="exceeds"):
        load_report(tmp_path, path)


def test_load_report_refuses_a_symlinked_report(tmp_path):
    real = tmp_path / "real.json"
    real.write_text("{}", encoding="utf-8")
    link = tmp_path / "link.json"
    link.symlink_to(real)
    with pytest.raises(IngestError, match="symlink"):
        load_report(tmp_path, link)


def test_load_report_refuses_a_report_under_a_symlinked_PARENT(tmp_path):
    # The report file itself is real; `runs/` is the link. An `O_NOFOLLOW` on the
    # final component alone reads this without complaint.
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "report.json").write_text("{}", encoding="utf-8")
    (tmp_path / "runs").symlink_to(outside, target_is_directory=True)
    with pytest.raises(IngestError, match="symlink"):
        load_report(tmp_path, tmp_path / "runs" / "report.json")


def test_load_report_refuses_a_report_outside_the_project(tmp_path):
    # §8 gives the actor ONE supervisor-supplied report path, on a surface the
    # `report-only` tier already allows -- which is inside the project.
    project = tmp_path / "project"
    project.mkdir()
    stray = tmp_path / "stray.json"
    stray.write_text("{}", encoding="utf-8")
    with pytest.raises(IngestError, match="outside the project root"):
        load_report(project, stray)


def test_a_dangling_case_symlink_is_refused_rather_than_overwritten(tmp_path):
    # `Path.exists()` is False for a dangling link, so an existence check would treat
    # this as "no case yet" and write straight through the link.
    from science_tool.findings.storage import case_path

    ingest_report(tmp_path, _report(), REGISTRY)
    records = load_cases(tmp_path)
    path = case_path(tmp_path, records[0])
    path.unlink()
    path.symlink_to(tmp_path / "gone.md")
    with pytest.raises(IngestError, match="symlink"):
        ingest_report(tmp_path, _report(ingestion_ref="ing:2"), REGISTRY)


def test_evidence_path_escaping_the_project_is_refused_at_the_model(tmp_path):
    from pydantic import ValidationError
    from science_model.audit import LocationEvidence

    with pytest.raises(ValidationError):
        LocationEvidence(path="../../etc/passwd")


def test_one_producer_emitting_two_findings_with_one_identity_is_refused(tmp_path):
    # Same rule, same subject, same identity qualifiers -- different prose. The model
    # cannot catch this (it does not know which qualifiers bear identity); ingestion
    # must, or the collision surfaces later as an idempotency conflict.
    report = _report(findings=[
        ReportedFinding(
            producer_id="dataset_anomalies", finding=_finding(message="first")
        ),
        ReportedFinding(
            producer_id="dataset_anomalies", finding=_finding(message="second")
        ),
    ])
    with pytest.raises(IngestError, match="two findings with identity"):
        ingest_report(tmp_path, report, REGISTRY)
    assert load_cases(tmp_path) == []


def test_a_non_identity_qualifier_difference_still_collides(tmp_path):
    # The two payloads differ ONLY in `note`, which `RULE` does not list among its
    # identity qualifiers, so they share a fingerprint and collide. A version of this
    # test where both payloads carry the same qualifiers proves nothing about
    # non-identity qualifiers -- it is just the previous test again.
    report = _report(findings=[
        ReportedFinding(
            producer_id="dataset_anomalies",
            finding=_finding(qualifiers={"field": "year", "note": "first look"}),
        ),
        ReportedFinding(
            producer_id="dataset_anomalies",
            finding=_finding(qualifiers={"field": "year", "note": "second look"}),
        ),
    ])
    with pytest.raises(IngestError, match="two findings with identity"):
        ingest_report(tmp_path, report, REGISTRY)


def test_a_subject_path_through_a_symlink_is_refused(tmp_path):
    from science_model.audit import PathSubject

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "x.md").write_text("hi", encoding="utf-8")
    (tmp_path / "doc").symlink_to(outside, target_is_directory=True)

    path_rule = FindingRule(
        id="tags.lingering", severities={"warn"}, subject_types={"path"},
        qualifier_schema=Q, title="t", section="datasets", display_order=110,
    )
    registry = build_registry([
        FindingProducer(
            producer_id="dataset_anomalies", namespace="health_checks",
            rules=(RULE, path_rule), sections=(SECTION,), metrics_schema=None,
            remediators=frozenset(),
        )
    ])
    report = _report(findings=[
        ReportedFinding(
            producer_id="dataset_anomalies",
            finding=AuditFinding(
                rule_id="tags.lingering", subject=PathSubject(path="doc/x.md"),
                severity="warn", qualifiers={}, message="m", evidence=[],
            ),
        )
    ])
    with pytest.raises(IngestError, match="symlink"):
        ingest_report(tmp_path, report, registry)


def test_an_evidence_path_through_a_symlink_is_refused(tmp_path):
    from science_model.audit import LocationEvidence

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "x.md").write_text("hi", encoding="utf-8")
    (tmp_path / "doc").symlink_to(outside, target_is_directory=True)

    report = _report(findings=[
        ReportedFinding(
            producer_id="dataset_anomalies",
            finding=_finding(evidence=[LocationEvidence(path="doc/x.md", line=1)]),
        )
    ])
    with pytest.raises(IngestError, match="symlink"):
        ingest_report(tmp_path, report, REGISTRY)


def test_a_symlinked_lock_file_is_refused(tmp_path):
    cases = tmp_path / "doc" / "audits" / "cases"
    cases.mkdir(parents=True)
    outside = tmp_path / "outside.lock"
    outside.write_text("", encoding="utf-8")
    (cases / ".ingest.lock").symlink_to(outside)
    with pytest.raises(IngestError, match="symlink|link"):
        ingest_report(tmp_path, _report(), REGISTRY)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_findings_ingest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.findings.ingest'`

- [ ] **Step 3: Write minimal implementation**

```python
# science/src/science_tool/findings/ingest.py
"""Trusted ingestion: the write boundary (design §8).

An untrusted actor writes ONE gated report path. Ingestion validates it, computes
identities, and upserts canonical cases. `entity_kind_for_path` already returns
`None` for `doc/audits/cases/...` and the path gate already reads `None` as denied,
so "Layer 1 works unchanged" is literal -- nothing in `autonomy/policy.py` is edited.

This is NOT a multi-file transaction and does not claim to be. Full prevalidation,
then atomic per-record writes under a project-scoped lock. A crash after three
renames leaves three committed cases, which is acceptable ONLY because recovery is
idempotent: re-running the same report re-applies it, and every already-written
occurrence is a no-op by idempotency key. Retry is the documented recovery.
"""

from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from pydantic import BaseModel, ConfigDict, ValidationError
from science_model.audit import (
    REPORT_SCHEMA_VERSION,
    AuditReport,
    AuditFinding,
    AuditFindingRecord,
    Occurrence,
    Transition,
    finding_fingerprint,
    occurrence_key,
)
from science_model.audit.record import canonical_occurrence_content

from science_tool.findings.paths import (
    PathSafetyError,
    mkdir_inside,
    open_write_nofollow,
    read_inside_bounded,
    resolve_inside,
)
from science_tool.findings.producers import FindingRegistry, RegistryError
from science_tool.findings.storage import (
    CASES_DIRNAME,
    CaseStorageError,
    case_path,
    cases_dir,
    load_case,
    write_case,
)

MAX_REPORT_BYTES = 8 * 1024 * 1024
SUPPORTED_FINGERPRINT_VERSIONS = frozenset({1})


class IngestError(ValueError):
    """A report was refused, or an occurrence conflicts with a stored one."""


class IngestOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    records_written: int
    occurrences_appended: int
    occurrences_skipped: int


def load_report(project_root: Path, path: Path) -> AuditReport:
    """Read the actor's one gated report path.

    Takes the project root because the report must LIVE inside it: §8 gives the actor
    exactly one supervisor-supplied report path, on a surface `report-only` already
    allows. `read_inside_bounded` therefore walks every component -- a link at any of
    them is refused, not merely one on the file itself -- and reads once from a single
    `O_NOFOLLOW` descriptor it also sized, so `stat()`-then-`read()` cannot race.
    """
    try:
        text = read_inside_bounded(project_root, path, MAX_REPORT_BYTES)
    except PathSafetyError as exc:
        raise IngestError(str(exc)) from exc
    except OSError as exc:
        raise IngestError(f"could not read {path}: {exc}") from exc
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise IngestError(f"could not parse {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise IngestError(f"{path} is not a JSON object")
    if raw.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise IngestError(
            f"{path} declares schema_version {raw.get('schema_version')!r}; this "
            f"toolkit implements {REPORT_SCHEMA_VERSION} and refuses to coerce"
        )
    try:
        return AuditReport.model_validate(raw)
    except ValidationError as exc:
        raise IngestError(f"{path} is not a valid audit report: {exc}") from exc


@contextmanager
def _project_lock(project_root: Path) -> Iterator[None]:
    """Serialize ingestion per project; concurrent runs queue rather than interleave.

    The lock file is opened with `O_NOFOLLOW` like every other write here. A plain
    `open(..., "w")` would happily follow a planted link and write outside the project.
    """
    directory = cases_dir(project_root)
    try:
        mkdir_inside(project_root, CASES_DIRNAME)
        lock_path = resolve_inside(project_root, f"{CASES_DIRNAME}/.ingest.lock")
    except PathSafetyError as exc:
        raise IngestError(str(exc)) from exc
    except OSError as exc:
        raise IngestError(f"could not create {directory}: {exc}") from exc

    try:
        descriptor = open_write_nofollow(lock_path)
    except PathSafetyError as exc:
        raise IngestError(str(exc)) from exc
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


class _Planned(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    finding_id: str
    finding: AuditFinding
    producer_id: str
    acceptance_key: str | None
    identity_qualifiers: dict[str, object]


def _plan(
    project_root: Path, report: AuditReport, registry: FindingRegistry
) -> list[_Planned]:
    """Validate everything and compute every identity BEFORE writing anything."""
    if report.fingerprint_version not in SUPPORTED_FINGERPRINT_VERSIONS:
        raise IngestError(
            f"report declares fingerprint_version {report.fingerprint_version}; this "
            f"toolkit implements {sorted(SUPPORTED_FINGERPRINT_VERSIONS)}"
        )

    for producer_id, metrics in report.metrics.items():
        try:
            registry.validate_metrics(producer_id, metrics.model_dump())
        except RegistryError as exc:
            raise IngestError(str(exc)) from exc

    planned: list[_Planned] = []
    channels: list[tuple[str, AuditFinding, str | None]] = [
        (r.producer_id, r.finding, None) for r in report.findings
    ] + [(a.producer_id, a.finding, a.acceptance_key) for a in report.accepted]

    for producer_id, finding, acceptance_key in channels:
        if producer_id not in registry.producers_by_id:
            raise IngestError(f"unregistered producer {producer_id!r}")
        try:
            rule = registry.rule(finding.rule_id)
        except RegistryError as exc:
            raise IngestError(str(exc)) from exc
        if finding.severity not in rule.severities:
            raise IngestError(
                f"{finding.rule_id}: severity {finding.severity!r} is not in "
                f"{sorted(rule.severities)}"
            )
        if finding.subject.type not in rule.subject_types:
            raise IngestError(
                f"{finding.rule_id}: subject type {finding.subject.type!r} is not in "
                f"{sorted(rule.subject_types)}"
            )
        if finding.subject.type == "identifier" and rule.identifier_namespaces:
            if finding.subject.namespace not in rule.identifier_namespaces:
                raise IngestError(
                    f"{finding.rule_id}: namespace {finding.subject.namespace!r} is not "
                    f"in {sorted(rule.identifier_namespaces)}"
                )
        try:
            # `dict(...)`: `finding.qualifiers` is a frozen view (`QualifierMap`).
            rule.qualifier_schema.model_validate(dict(finding.qualifiers))
        except ValidationError as exc:
            raise IngestError(f"{finding.rule_id}: qualifiers invalid: {exc}") from exc

        _assert_paths_are_safe(project_root, finding)

        identity = rule.identity_subset(finding.qualifiers)
        planned.append(
            _Planned(
                finding_id=finding_fingerprint(
                    rule_id=finding.rule_id,
                    subject=finding.subject,
                    identity_qualifiers=identity,
                ),
                finding=finding,
                producer_id=producer_id,
                acceptance_key=acceptance_key,
                identity_qualifiers=identity,
            )
        )

    # The at-most-one-per-(producer, finding_id) rule of §1, enforced HERE because it
    # needs the fingerprint, which needs the registry. `AuditReport` cannot do it:
    # keying on the whole payload would pass two observations with identical identity
    # and different prose, which is exactly the collision this rule prevents.
    seen: set[tuple[str, str]] = set()
    for item in planned:
        key = (item.producer_id, item.finding_id)
        if key in seen:
            raise IngestError(
                f"{item.producer_id!r} emitted two findings with identity "
                f"{item.finding_id}: aggregate their evidence into one finding, or "
                f"declare an identity qualifier on {item.finding.rule_id!r} that tells "
                "them apart (design §1)"
            )
        seen.add(key)
    return planned


def _assert_paths_are_safe(project_root: Path, finding: AuditFinding) -> None:
    """Every path the finding names must resolve inside the project without a link.

    The model normalizes path SYNTAX; only the filesystem can answer whether a
    component is a symlink, so the check lives here.
    """
    candidates: list[str] = []
    if finding.subject.type == "path":
        candidates.append(finding.subject.path)
    candidates.extend(
        item.path for item in finding.evidence if item.type == "location"
    )
    for candidate in candidates:
        try:
            resolve_inside(project_root, candidate)
        except PathSafetyError as exc:
            raise IngestError(f"{finding.rule_id}: {exc}") from exc


def ingest_report(
    project_root: Path,
    report: AuditReport,
    registry: FindingRegistry,
    *,
    actor: str = "ingest",
) -> IngestOutcome:
    planned = _plan(project_root, report, registry)
    observed_at = datetime.fromisoformat(report.generated_at)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)

    written = appended = skipped = 0
    with _project_lock(project_root):
        for item in planned:
            occurrence = Occurrence(
                idempotency_key=occurrence_key(
                    producer_id=item.producer_id,
                    ingestion_ref=report.ingestion_ref,
                    finding_id=item.finding_id,
                ),
                producer_id=item.producer_id,
                ingestion_ref=report.ingestion_ref,
                observed_at=observed_at,
                severity=item.finding.severity,
                message=item.finding.message,
                qualifiers=dict(item.finding.qualifiers),
                evidence=tuple(item.finding.evidence),
                acceptance_key=item.acceptance_key,
            )
            probe = AuditFindingRecord(
                finding_id=item.finding_id,
                fingerprint_version=report.fingerprint_version,
                rule_id=item.finding.rule_id,
                subject=item.finding.subject,
                identity_qualifiers=item.identity_qualifiers,
                occurrences=(occurrence,),
                transitions=(
                    Transition(
                        from_status=None,
                        to_status="proposed",
                        actor=actor,
                        at=observed_at,
                        reason=f"detected by {item.producer_id}",
                    ),
                ),
                status="proposed",
            )
            path = case_path(project_root, probe)
            # `lexists`, not `exists()`: a case path that is a DANGLING link is present
            # under its own name, and treating it as absent would overwrite whatever
            # the link points at. `load_case` below refuses it explicitly instead.
            if not os.path.lexists(path):
                write_case(project_root, probe)
                written += 1
                appended += 1
                continue

            try:
                existing = load_case(project_root, path)
            except CaseStorageError as exc:
                raise IngestError(str(exc)) from exc

            stored = {o.idempotency_key: o for o in existing.occurrences}
            prior = stored.get(occurrence.idempotency_key)
            if prior is not None:
                if canonical_occurrence_content(prior) != canonical_occurrence_content(
                    occurrence
                ):
                    raise IngestError(
                        f"idempotency conflict on {item.finding_id}: key "
                        f"{occurrence.idempotency_key} already exists with different "
                        "observation content; identical keys must mean identical "
                        "observations"
                    )
                skipped += 1
                continue

            # `with_occurrence`, not `model_copy(update=...)`: the latter bypasses every
            # validator, so a malformed append would reach disk unchecked.
            write_case(project_root, existing.with_occurrence(occurrence))
            appended += 1

    return IngestOutcome(
        records_written=written,
        occurrences_appended=appended,
        occurrences_skipped=skipped,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_findings_ingest.py -v`
Expected: PASS, 26 tests

Then: `cd science && uv run ruff check && uv run pyright`
Expected: no findings

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/findings/ingest.py science/tests/test_findings_ingest.py
git commit -m "feat(findings): trusted ingestion with idempotent retry as the recovery path"
```

---

### Task 11: CLI surface

**Files:**
- Create: `science/src/science_tool/findings/cli.py`
- Modify: `science/src/science_tool/cli.py` (register the group)
- Test: `science/tests/test_findings_cli.py`

**Interfaces:**
- Consumes: Tasks 8–10.
- Produces: `findings_group` with `ingest` and `list` subcommands.

`science health` gains **no** persist flag. Ingestion is a separate explicit command; a diagnostic run never writes cases as a side effect (§8).

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_findings_cli.py
import json

from click.testing import CliRunner

from science_tool.findings.cli import findings_group


def _report_json() -> dict:
    return {
        "schema_version": 2,
        "fingerprint_version": 1,
        "ingestion_ref": "ing:1",
        "generated_at": "2026-07-27T12:00:00+00:00",
        "findings": [],
        "accepted": [],
        "metrics": {},
        "unwired": [],
        "totals": {"findings_total": 0, "findings_by_severity": {},
                   "accepted_total": 0, "unwired_total": 0},
        "meta": {"producers_run": [], "total_duration_seconds": 0.0, "timings": []},
    }


def test_ingest_reports_what_it_did(tmp_path):
    report = tmp_path / "report.json"
    report.write_text(json.dumps(_report_json()), encoding="utf-8")
    result = CliRunner().invoke(
        findings_group,
        ["ingest", str(report), "--project-root", str(tmp_path), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["records_written"] == 0


def test_ingest_exits_nonzero_on_a_refused_report(tmp_path):
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
    result = CliRunner().invoke(
        findings_group, ["ingest", str(report), "--project-root", str(tmp_path)]
    )
    assert result.exit_code == 2
    assert "schema_version" in result.output


def test_list_on_a_project_with_no_cases_is_empty_and_exits_zero(tmp_path):
    result = CliRunner().invoke(
        findings_group, ["list", "--project-root", str(tmp_path), "--format", "json"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_findings_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.findings.cli'`

- [ ] **Step 3: Write minimal implementation**

```python
# science/src/science_tool/findings/cli.py
"""`science findings` -- the trusted side of the audit write boundary.

`ingest` is a SEPARATE EXPLICIT COMMAND. `science health` stays purely read-only and
gains no persist flag: a diagnostic run never writes cases as a side effect (§8).
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from science_tool.output import OUTPUT_FORMATS, emit


@click.group("findings")
def findings_group() -> None:
    """Ingest and inspect audit findings."""


def _registry():
    """The derived registry. Plan 2 populates it from real producers."""
    from science_tool.findings.producers import build_registry

    return build_registry([])


@findings_group.command("ingest")
@click.argument("report_path", type=click.Path(path_type=Path, exists=True))
@click.option(
    "--project-root", type=click.Path(path_type=Path), default=Path("."), show_default=True
)
@click.option(
    "--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table",
    show_default=True,
)
def ingest_command(report_path: Path, project_root: Path, output_format: str) -> None:
    """Validate a report and upsert its findings into `doc/audits/cases/`.

    Exit codes: 0 ingested, 2 refused. Nothing is written on a validation failure.
    """
    from science_tool.findings.ingest import IngestError, ingest_report, load_report

    try:
        report = load_report(project_root, report_path)
        outcome = ingest_report(project_root, report, _registry())
    except IngestError as exc:
        message = f"refused: {exc}"
        emit(
            output_format=output_format,
            payload={"ingested": False, "error": message},
            render_text=lambda: click.echo(message),
        )
        sys.exit(2)

    emit(
        output_format=output_format,
        payload=outcome.model_dump(mode="json"),
        render_text=lambda: click.echo(
            f"{outcome.records_written} new case(s), "
            f"{outcome.occurrences_appended} occurrence(s) appended, "
            f"{outcome.occurrences_skipped} skipped as already recorded"
        ),
    )
    sys.exit(0)


@findings_group.command("list")
@click.option(
    "--project-root", type=click.Path(path_type=Path), default=Path("."), show_default=True
)
@click.option("--status", default=None, help="Filter to one lifecycle status.")
@click.option(
    "--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table",
    show_default=True,
)
def list_command(project_root: Path, status: str | None, output_format: str) -> None:
    """List stored cases. Read-only."""
    from science_tool.findings.storage import CaseStorageError, load_cases

    try:
        records = load_cases(project_root)
    except CaseStorageError as exc:
        click.echo(f"could not load cases: {exc}")
        sys.exit(2)

    if status is not None:
        records = [r for r in records if r.status == status]

    payload = [
        {
            "finding_id": r.finding_id,
            "rule_id": r.rule_id,
            "status": r.status,
            "occurrences": len(r.occurrences),
            "confirmations": r.confirmation_count(),
        }
        for r in records
    ]

    def _render_text() -> None:
        for row in payload:
            click.echo(
                f"{row['status']:<10} {row['rule_id']:<40} "
                f"{row['occurrences']}occ {row['confirmations']}conf "
                f"{row['finding_id'][:12]}"
            )

    emit(output_format=output_format, payload=payload, render_text=_render_text)
    sys.exit(0)
```

Then register the group in `science/src/science_tool/cli.py`. The root group is named
`main` (`@click.group(cls=TelemetryGroup)` at `cli.py:170`, `def main(...)` at `:184`),
and registrations are a run of `main.add_command(...)` calls beginning at `cli.py:194`.
Add the import beside the other group imports and one line to that run, keeping it in
the existing alphabetical-ish order:

```python
from science_tool.findings.cli import findings_group

main.add_command(findings_group)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_findings_cli.py -v`
Expected: PASS, 3 tests

Then confirm the group is reachable and that CLI-registration guards still hold:
Run: `cd science && uv run --frozen python -m science_tool.cli findings --help`
Expected: usage text listing `ingest` and `list`

Run: `cd science && uv run --frozen pytest tests/test_cli_is_registration_only.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/findings/cli.py science/src/science_tool/cli.py science/tests/test_findings_cli.py
git commit -m "feat(findings): science findings ingest/list, leaving health read-only"
```

---

### Task 12: Namespace-completeness and isolation guards

**Files:**
- Create: `science/tests/test_findings_producer_namespaces.py`
- Create: `science/tests/test_findings_isolation.py`

**Interfaces:**
- Consumes: `PRODUCER_NAMESPACES` (Task 8), `CASES_DIRNAME` (Task 9), `entity_kind_for_path` and `evaluate` from `science_tool.autonomy`.
- Produces: nothing; these are guards.

Every namespace contributing to the derived registry needs a **filesystem-derived** completeness guard — never a list, per `test_check_registry_is_complete.py`'s own rule about itself. In this plan no namespace has producers yet, so the guard asserts the *mapping* is total and will fail the moment Plan 2 adds a producer without wiring its namespace.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_findings_producer_namespaces.py
"""Scope declarations for the producer namespaces.

**This file is NOT design test 29** (producer-namespace completeness), and does not
pretend to be. Test 29 requires comparing filesystem-discovered producers against
registered ones. Plan 1 registers ZERO producers, so that comparison would be
`set() == set()` — a guard that passes because there is nothing to check. A green
vacuous assertion is worse than an absent one: it reads as coverage it does not have,
which is the failure mode this repo has already been bitten by.

**Test 29 is therefore deferred to Plan 2**, where the first real producers exist and
the comparison can fail.

What this file does guard now is the precondition test 29 will need: every registered
namespace declares WHERE its producers live. A namespace whose scope nobody defined
cannot be walked, so Plan 2 could not write test 29 for it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.findings.producers import PRODUCER_NAMESPACES

SRC = Path(__file__).resolve().parents[1] / "src" / "science_tool"

#: Where each namespace's producer modules live, relative to `science_tool/`.
NAMESPACE_DIRS: dict[str, str] = {
    "health_checks": "graph/health_checks",
    "validate_checks": "validate/checks",
    "data_audit": "data_audit.py",
}


def test_every_namespace_declares_where_its_producers_live():
    missing = set(PRODUCER_NAMESPACES) - set(NAMESPACE_DIRS)
    assert not missing, (
        f"namespaces without a declared producer scope: {sorted(missing)}. "
        "A namespace whose scope is undefined cannot be guarded for completeness."
    )


def test_no_namespace_is_declared_without_being_registered():
    extra = set(NAMESPACE_DIRS) - set(PRODUCER_NAMESPACES)
    assert not extra, f"scope declared for unregistered namespaces: {sorted(extra)}"


@pytest.mark.parametrize("namespace", sorted(NAMESPACE_DIRS))
def test_each_declared_scope_exists_on_disk(namespace: str):
    target = SRC / NAMESPACE_DIRS[namespace]
    assert target.exists(), f"{namespace}: declared scope {target} does not exist"


def test_phase_boundary_ratchet_no_producers_are_registered_yet():
    """A PHASE-BOUNDARY RATCHET, not a placeholder.

    It states a fact that is true in Plan 1 and false the instant Plan 2 registers its
    first producer: at that moment the tree goes red, and the only correct way to make
    it green is to write design test 29 -- the real discovery-versus-registration
    comparison -- IN THE SAME COMMIT that registers the producer.

    Deleting it is not the correct response. Replacing it is. A commit that removes
    this and adds no equality guard has moved the codebase from "cannot check
    completeness" to "does not check completeness" while turning the tree green, which
    is the exact substitution this ratchet exists to make impossible.
    """
    from science_tool.findings.cli import _registry

    assert not _registry().producers_by_id, (
        "producers are now registered, so design test 29 (producer-namespace "
        "completeness) can and must be written: compare the modules discovered under "
        "each NAMESPACE_DIRS entry against the registered producers, and REPLACE this "
        "ratchet with that comparison in this same commit."
    )
```

```python
# science/tests/test_findings_isolation.py
"""Cases are project-state, not knowledge, and not writable by an autonomous actor.

Both properties hold with NO change to `autonomy/policy.py` or to the graph writer;
these guards assert that, so a later edit cannot quietly break either.
"""

from __future__ import annotations

from science_model.autonomous_runs import RunTier

from science_tool.autonomy.changes import (
    ChangeSet,
    ChangeType,
    PathChange,
    entity_kind_for_path,
)
from science_tool.autonomy.path_gate import evaluate
from science_tool.findings.storage import CASES_DIRNAME
from science_tool.graph.io import DEFAULT_REVISION_MANIFEST_EXCLUDES


def test_a_case_path_is_unclassified_and_therefore_denied():
    rel = f"{CASES_DIRNAME}/dataset-stale-review--{'a' * 64}.md"
    assert entity_kind_for_path(rel) is None


def test_the_path_gate_denies_an_actor_writing_a_case():
    rel = f"{CASES_DIRNAME}/dataset-stale-review--{'a' * 64}.md"
    change_set = ChangeSet(
        base_commit="a" * 40,
        head_commit="b" * 40,
        changes=(
            PathChange(
                path=rel,
                change_type=ChangeType.ADDED,
                entity_kind=None,
                fields=(),
            ),
        ),
    )
    verdict = evaluate(change_set, tier=RunTier.BELIEF_NEUTRAL, report_path=None)
    assert not verdict.allowed
    assert any(d.path == rel for d in verdict.denials)


def test_cases_are_excluded_from_the_revision_manifest():
    assert f"{CASES_DIRNAME}/*.md" in DEFAULT_REVISION_MANIFEST_EXCLUDES


def test_a_case_directory_is_not_an_entity_home():
    # `cases` must not be in the directory->kind map, or a case would infer
    # `kind: finding` -- a live epistemic kind (design §5).
    from science_model.frontmatter import _DIR_TO_KIND

    assert "cases" not in _DIR_TO_KIND
    assert "audits" not in _DIR_TO_KIND


```

Both `ChangeSet` and `PathChange` live in `science_tool/autonomy/changes.py` (`:44` and
`:27`), both are `frozen=True, extra="forbid"`, and `ChangeSet.changes` is a
**tuple**, not a list. `change_type` is a `ChangeType` StrEnum (`MODIFIED` / `ADDED` /
`DELETED`), not a bare string. Do **not** modify `evaluate`, `PathChange`, or
`ChangeSet` — the whole point of this guard is that the existing gate denies these
paths untouched.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_findings_producer_namespaces.py tests/test_findings_isolation.py -v`
Expected: FAIL — `ModuleNotFoundError` on `science_tool.findings.storage` if Task 9 has not landed; otherwise the namespace tests pass and the isolation tests pass.

- [ ] **Step 3: No implementation needed**

These are guards over behaviour that already exists. If any of them fails, that is a real
finding — either the gate no longer denies unclassified paths, or `cases` has entered
`_DIR_TO_KIND`, or the manifest exclude was dropped. Investigate rather than adjusting the
assertion.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_findings_producer_namespaces.py tests/test_findings_isolation.py -v`
Expected: PASS

Then the whole findings surface plus the autonomy gate suite it asserts against:
Run: `cd science && uv run --frozen pytest tests/test_findings_*.py -q`
Expected: PASS

Run: `cd science && uv run --frozen pytest -k autonomy -q`
Expected: PASS, unchanged from before this plan

- [ ] **Step 5: Commit**

```bash
git add science/tests/test_findings_producer_namespaces.py science/tests/test_findings_isolation.py
git commit -m "test(findings): guard namespace completeness, gate denial, and graph isolation"
```

---

### Task 13: Full-suite verification and plan handoff

**Files:**
- Modify: `docs/plans/2026-07-27-finding-convergence-design.md` (status line only)

**Interfaces:**
- Consumes: everything.
- Produces: a green tree ready for Plan 2.

- [ ] **Step 1: Run the model suite**

Run: `cd science/model && uv run --frozen pytest -q`
Expected: PASS

- [ ] **Step 2: Run the full tool suite with an explicit long timeout**

Run: `cd science && uv run --frozen pytest -q` with a **600000 ms** timeout on the Bash call. The suite is ~10k tests and takes ~2-3 minutes, over the 120s default.

Expected: PASS, with no new failures relative to `main`. If anything fails, it is a real regression from this plan — Plan 1 converts no producer and changes exactly one existing line (`DEFAULT_REVISION_MANIFEST_EXCLUDES`), so the likely culprit is a manifest-exclude snapshot.

- [ ] **Step 3: Lint and type-check**

Run: `cd science && uv run ruff check && uv run pyright`
Run: `cd science/model && uv run ruff check`
Expected: no findings from any of the three

- [ ] **Step 4: Record that Plan 1 landed**

Edit the design document's status block, changing:

The current line begins:

```
> **Status:** design, revision 6 — **approved for implementation planning**. **Spec 1 of
```

Replace the `design, revision 6 — **approved for implementation planning**.` clause with:

```
> **Status:** revision 6. **Plan 1 (the contract) is implemented**; Plan 2 (the
> atomic convergence) and Plan 3 (acceptance migration) are outstanding. **Spec 1 of
```

Leave the rest of that block, from `**Spec 1 of` onward, untouched.

- [ ] **Step 5: Commit**

```bash
git add docs/plans/2026-07-27-finding-convergence-design.md
git commit -m "docs(plans): record that the finding contract landed"
```

---

## Self-Review

**Spec coverage.** Walking the design section by section:

| Design section | Task | Note |
|---|---|---|
| §1 `AuditFinding` payload | 4 | `rule_id` as wire form, severity normalization |
| §1 evidence union | 2 | types frozen, `extra="forbid"`, bounds |
| §1 one finding per (producer, finding) | 10 | enforced in `_plan`, after fingerprints exist; Task 7 asserts the report deliberately does *not* try |
| §2 subject union | 1 | four variants, no fallback |
| §3 fingerprint v1 | 3 | normalization, canonical encoding, digest, slug, golden vectors |
| §4 `AuditFindingRecord` | 6 | identity + occurrences + transitions + reviews |
| §4 genesis + closed graph | 6 | `PERMITTED_TRANSITIONS` |
| §4 review record | 6 | lens in identity, agent `model` required |
| §5 storage, filename binding | 9 | plus the manifest exclude |
| §6 rule declarations | 5 | `build()`, identity-type constraints |
| §6 derived registry, 7 failures | 8 | all seven conditions |
| §6 namespace scope declarations | 12 | precondition for test 29; **test 29 itself deferred to Plan 2** |
| §7 remediation | 5, 8 | capability declared; handler must be registered |
| §8 ingestion | 10 | lock, prevalidation, atomic writes, idempotency |
| §8 accepted channel ingested | 10 | `acceptance_key` on occurrence |
| §11 output contract | 7 | envelope, provenance, totals |
| §11 ordering | 8 | `sort_key` on `(section_order, display_order)` |

**Deferred to Plan 2, by design:** §9's migration ledger, §11's renderer rewrite and `totals` derivation from real producers, the uniform-channel ratchet enforcement, and removing `_drain_instrument_results`' passthrough. **Deferred to Plan 3:** all of §10.

**Design tests not yet coverable — deferred to Plan 2.** Tests **1** (uniform-channel ratchet), **5** (renderer clean-refusal), **26** (count ledger), **27** (presentation order vs today's `HEALTH_CHECKS`), **28** (metrics are not findings), **29** (producer-namespace completeness), and **30** (twelve dataset rules) all require converted producers. They belong to Plan 2 and are listed there, not silently dropped.

Test **23** (graph isolation) is *not* in that set — it is covered here, in Task 12.

Test **29** is the one deferral that needed a decision rather than a schedule: with zero registered producers, a discovery-versus-registration comparison is `set() == set()`, which passes vacuously. Task 12 ships the *precondition* (every namespace declares its scope) plus a **phase-boundary ratchet** — `test_phase_boundary_ratchet_no_producers_are_registered_yet` — which asserts a fact that stops being true the instant Plan 2 registers its first producer.

The ratchet is not a placeholder, and Plan 2 must **replace** it with the real equality guard *in the same commit that registers the producer* — not delete it. A commit that removes the ratchet and adds no comparison has moved the tree from "cannot check completeness" to "does not check completeness" while going green, which is precisely the substitution it exists to prevent. This obligation is carried in the test's own docstring, where the person deleting it will read it.

**Type consistency check.** `finding_fingerprint(rule_id=, subject=, identity_qualifiers=)` is called with those exact keywords in Tasks 3, 9, and 10. `occurrence_key(producer_id=, ingestion_ref=, finding_id=)` matches between Tasks 6 and 10. `rule.identity_subset(qualifiers)` defined in Task 5 is consumed in Task 10. `registry.rule()` raising `RegistryError` in Task 8 is caught and re-raised as `IngestError` in Task 10. `CASES_DIRNAME` is `"doc/audits/cases"` in Task 9 and asserted with that value in Task 12.

**Signatures, all resolved against the tree — no grep-and-adjust steps remain.**

| Thing | Resolved form |
|---|---|
| `PathChange` | `science_tool/autonomy/changes.py:27`, frozen; `PathChange(path=..., change_type=ChangeType.ADDED, entity_kind=None, fields=())` |
| `ChangeSet` | **`changes.py:44`, not `extract.py`**; `ChangeSet(base_commit=..., head_commit=..., changes=(...))`, `changes` is a tuple |
| CLI registration | root group is `main` (`cli.py:170,184`); `main.add_command(findings_group)`, joining the run at `cli.py:194` |
| Manifest test | `science/tests/test_graph_io_revision_manifest.py` |

**Filesystem-safety invariants, stated once here so a reviewer can check them in one place.** Every filesystem touch in this package goes through `paths.py` — there is no `Path.open`, `read_text`, `mkdir`, or `parse_frontmatter(path)` anywhere in `science_tool/findings/`:

| Primitive | Guarantee |
|---|---|
| `resolve_inside` | walks *every* component from the project root; a symlink at any of them is refused |
| `mkdir_inside` | creates one component at a time through `O_DIRECTORY \| O_NOFOLLOW` descriptors, so it **stops at a link having created nothing beyond it** |
| `project_relative` | a caller-supplied path is refused unless it is inside the project, with no `..` |
| `read_inside_bounded` | `project_relative` → `resolve_inside` → `open_read_bounded`, in that order |
| `open_read_bounded` | opens once with `O_NOFOLLOW` and `fstat`s *that* descriptor, so no stat/read race |
| `open_write_nofollow` | refuses a symlinked final component |

Three orderings this gets right, each of which the obvious code gets wrong:

1. **Create, then validate, is not validation.** `mkdir(parents=True)` followed by a check has already created directories in a link's target by the time the check refuses. `mkdir_inside` refuses first. Asserted by `test_write_creates_nothing_inside_a_symlinked_parents_target`, which checks the *target is still empty* — not merely that an error was raised.
2. **`exists()` is not presence.** It follows links, so a dangling `cases` symlink reads as absent and `load_cases` would report zero findings for a store that was redirected. `load_cases` uses `lstat`; ingestion uses `os.path.lexists` before deciding a case is new.
3. **A leaf check is not a path check.** `load_report` and `load_case` both take the **project root**, because given only a path they would have to open it directly — which is what following a link looks like.

**Immutability invariants.** Pydantic's `frozen=True` is shallow: it blocks attribute assignment and nothing else. `AuditFinding.qualifiers`, `Occurrence.qualifiers`, and `AuditFindingRecord.identity_qualifiers` are therefore `QualifierMap` — a `MappingProxyType` over a private copy — so identity cannot be edited in place while `finding_id` keeps claiming otherwise. `validate_default=True` is required on all three and is not decoration: verified against pydantic 2.12.5, an omitted field without it is a plain mutable `dict`.

**Report-boundary invariants.** `generated_at` is validated as ISO-8601 at the model, so `datetime.fromisoformat` in the write path cannot leak a raw `ValueError`; the `MAX_REPORT_FINDINGS` ceiling applies to `findings + accepted` **together**, because §8 ingests both; and `findings_by_severity` must equal the actual breakdown of the unsuppressed channel exactly. Checking the scalar total while leaving the breakdown unchecked is how a summary comes to disagree with the rows beneath it.
