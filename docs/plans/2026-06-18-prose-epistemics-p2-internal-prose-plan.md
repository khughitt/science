# P2 Internal Prose Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the framework-only P2 internal-prose path: ingest offline Markdown decomposition JSON, mint/link `prose-source` entities, check regenerable locators, and promote validated candidate units into existing propositions/questions/hypotheses.

**Architecture:** P2 is artifact-led. A new decomposition parser validates offline JSON into typed records; a store persists immutable artifact generations plus a small index under `data/prose-decompositions/<slug>/`; `InternalProseAdapter` resolves Markdown heading/quote locators without using `.anno.trig`; prose-specific CLI commands ingest, check, and promote from the persisted artifact. Existing paper extraction/promotion behavior remains unchanged.

**Tech Stack:** Python 3, Click, Pydantic model package, dataclasses, JSON files, pytest.

---

## Scope And Decisions

This plan implements the approved design:

- Design: `~/d/science/docs/plans/2026-06-18-prose-epistemics-p2-internal-prose-design.md`
- Parent umbrella: `~/d/science/docs/plans/2026-06-17-prose-epistemics-umbrella-design.md`
- P2 only. No live LLM calls. No natural-systems content campaign. No YAML/model-record decomposition. No `.anno.trig` rewrite.

Concrete implementation choices locked by this plan:

- `prose-source` is a core, template-backed, operational kind with slug strategy and home `entities/prose-sources`.
- Artifact storage lives at `data/prose-decompositions/<slug>/`.
- Immutable submitted artifact generations live at `data/prose-decompositions/<slug>/generations/<artifact_id>.json`.
- Cross-generation state lives in `data/prose-decompositions/<slug>/index.json`.
- Artifact/unit provenance is recorded in promoted entities as `annotation:data/prose-decompositions/<slug>/generations/<artifact_id>.json#<unit_id>` so graph materialization can reuse the existing `annotation:` provenance URI path.
- New CLI commands are prose-specific:
  - `science-tool annotate ingest-prose-decomposition <artifact.json>`
  - `science-tool annotate check-prose-decomposition --source prose-source:<slug>`
  - `science-tool annotate promote-prose-decomposition --source prose-source:<slug> --unit <unit_id>`
- `InternalProseAdapter` is not added to `TEXT_SOURCE_ADAPTERS` in P2. The existing registry remains path-keyed and paper command behavior must stay unchanged.

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `science/model/src/science_model/entities.py` | Core `EntityType` enum and non-epistemic validation list | Modify |
| `science/model/src/science_model/profiles/core.py` | `prose-source` kind descriptor | Modify |
| `science/model/src/science_model/templates/prose-source.md` | Template for auto-created source entities | Create |
| `science/model/tests/test_kind_reconciliation.py` | Model kind reconciliation gate | Existing tests should pass after kind change |
| `science/tests/test_kind_reconciliation_registry.py` | Tool registry reconciliation gate | Modify expected core-kind delta |
| `science/tests/test_entities.py` | Entity create/template behavior for `prose-source` | Modify |
| `science/src/science_tool/annotation/prose_decomposition.py` | Decomposition schema parser, fingerprinting, artifact store | Create |
| `science/tests/test_prose_decomposition.py` | Parser, fingerprint, store tests | Create |
| `science/src/science_tool/annotation/internal_prose_adapter.py` | Markdown heading parser, locator resolution, `InternalProseAdapter` | Create |
| `science/tests/test_internal_prose_adapter.py` | Markdown locator resolution tests | Create |
| `science/src/science_tool/annotation/prose_source_entity.py` | Auto mint/link and conservative metadata update for `prose-source` | Create |
| `science/tests/test_prose_source_entity.py` | Source entity resolver tests | Create |
| `science/src/science_tool/annotation/prose_promote.py` | Convert validated prose units into promotion candidates and apply | Create |
| `science/tests/test_prose_promote.py` | Prose promotion core tests | Create |
| `science/src/science_tool/annotation/cli.py` | Add ingest/check/promote prose commands | Modify |
| `science/tests/test_annotate_prose_decomposition_cli.py` | CLI integration tests | Create |

## Test Command Notes

Run commands from the repository root `~/d/science`.

Use this prefix for focused Python tests:

```bash
PYTHONPATH=science/src:science/model/src science/.venv/bin/pytest -q
```

If the local environment uses `uv`, this equivalent command is acceptable:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen pytest -q
```

---

## Task 1: Add `prose-source` Core Kind

**Files:**
- Modify: `science/model/src/science_model/entities.py`
- Modify: `science/model/src/science_model/profiles/core.py`
- Create: `science/model/src/science_model/templates/prose-source.md`
- Modify: `science/tests/test_kind_reconciliation_registry.py`
- Modify: `science/tests/test_entities.py`

- [ ] **Step 1: Write the failing kind/template tests**

Append these tests to `science/tests/test_entities.py`:

```python
def test_create_prose_source_entity(tmp_path):
    import yaml

    from science_tool.entities import create_entity

    result = create_entity(
        project_root=tmp_path,
        kind="prose-source",
        title="Example Prose Source",
        slug="example-prose-source",
        no_hints=True,
    )

    path = tmp_path / "entities" / "prose-sources" / "example-prose-source.md"
    assert result.entity_id == "prose-source:example-prose-source"
    assert result.path == path
    text = path.read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(text.split("---", 2)[1])
    assert frontmatter["id"] == "prose-source:example-prose-source"
    assert frontmatter["type"] == "prose-source"
    assert frontmatter["status"] == "active"
```

Modify `INTENDED_ADDITIONS` in `science/tests/test_kind_reconciliation_registry.py` only after the implementation step. The initial failure should show the new kind is missing.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=science/src:science/model/src science/.venv/bin/pytest -q \
  science/tests/test_entities.py::test_create_prose_source_entity \
  science/model/tests/test_kind_reconciliation.py \
  science/tests/test_kind_reconciliation_registry.py
```

Expected: FAIL because `prose-source` has no path policy/template and is not in `EntityType`.

- [ ] **Step 3: Add the model enum and non-epistemic classification**

Modify `science/model/src/science_model/entities.py`:

```python
class EntityType(StrEnum):
    # keep existing order; add near PAPER / BOOK / TALK source kinds
    PAPER = "paper"
    PROSE_SOURCE = "prose-source"
    BOOK = "book"
```

In `Entity._validate_review_state_kind`, add `"prose-source"` to the `non_epistemic` set:

```python
non_epistemic = {
    "task",
    "dataset",
    "workflow-run",
    "data-package",
    "paper",
    "prose-source",
    "book",
    "experiment",
    "code-file",
}
```

- [ ] **Step 4: Add the core kind descriptor**

Modify `science/model/src/science_model/profiles/core.py`, directly after the `paper` kind:

```python
        EntityKind(
            name="prose-source",
            canonical_prefix="prose-source",
            layer="layer/core",
            description="Authored internal Markdown prose used as an operational evidence source.",
            entity_class=EntityClass.OPERATIONAL,
            category=KindCategory.AUTHORED_CORE,
            template_ready=True,
            home="entities/prose-sources",
            strategy="slug",
            default_status="active",
            statuses=["active", "retired"],
        ),
```

- [ ] **Step 5: Create the `prose-source` template**

Create `science/model/src/science_model/templates/prose-source.md`:

```markdown
---
id: "prose-source:{{slug}}"
type: "prose-source"
title: "{{title}}"
status: "active"
source_path: ""
content_hash: ""
latest_decomposition_artifact: ""
source_refs: []
related: []
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
_template:
  frontmatter:
    id: { from: entity_id }
    type: { default: "prose-source" }
    title: { from: title }
    status: { from: status }
    source_path: { default: "" }
    content_hash: { default: "" }
    latest_decomposition_artifact: { default: "" }
    source_refs: { from: source_refs }
    related: { from: related }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: source, name: "Source", required: true }
    - { key: notes, name: "Notes", required: true }
---

# {{title}}

## Source

## Notes
```

- [ ] **Step 6: Update the registry delta test**

Modify `INTENDED_ADDITIONS` in `science/tests/test_kind_reconciliation_registry.py`:

```python
INTENDED_ADDITIONS = frozenset(
    {
        "dataset",
        "variable",
        "assumption",
        "transformation",
        "article",
        "spec",
        "research-package",
        "validation-report",
        "curation-sweep",
        "concept",
        "construct",
        "outcome",
        "pre-registration",
        "research-question",
        "topic",
        "discussion",
        "inquiry",
        "plan",
        "report",
        "synthesis",
        "search",
        "patch-definition",
        "decision",
        "claim-registry",
        "prose-source",
        "unknown",
    }
)
```

- [ ] **Step 7: Run focused tests**

Run:

```bash
PYTHONPATH=science/src:science/model/src science/.venv/bin/pytest -q \
  science/tests/test_entities.py::test_create_prose_source_entity \
  science/model/tests/test_kind_reconciliation.py \
  science/tests/test_kind_reconciliation_registry.py
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add \
  science/model/src/science_model/entities.py \
  science/model/src/science_model/profiles/core.py \
  science/model/src/science_model/templates/prose-source.md \
  science/tests/test_kind_reconciliation_registry.py \
  science/tests/test_entities.py
git commit -m "feat(prose-source): add core source entity kind"
```

---

## Task 2: Decomposition Parser And Fingerprints

**Files:**
- Create: `science/src/science_tool/annotation/prose_decomposition.py`
- Create: `science/tests/test_prose_decomposition.py`

- [ ] **Step 1: Write parser and fingerprint tests**

Create `science/tests/test_prose_decomposition.py`:

```python
import json
from pathlib import Path

import pytest

from science_tool.annotation.prose_decomposition import (
    DecompositionError,
    artifact_unit_ref,
    parse_submitted_decomposition,
)


def _artifact(tmp_path: Path, *, unit_id: str = "u001", heading=None, quote=None) -> dict:
    source = tmp_path / "docs" / "example.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("# Section\n\nBasalt flows record the cooling history.\n", encoding="utf-8")
    return {
        "schema_version": 1,
        "source": {
            "kind": "prose-source",
            "slug": "example",
            "path": str(source),
            "title": "Example",
            "content_hash": "sha256:" + "0" * 64,
        },
        "artifact": {
            "id": "decomp-1",
            "generated_at": "2026-06-18T12:00:00Z",
            "producer": "offline-agent",
        },
        "units": [
            {
                "unit_id": unit_id,
                "disposition": "candidate",
                "locator": {"regime": "markdown-heading-path", "value": heading or ["Section"]},
                "payload": {
                    "type": "proposition",
                    "exact": quote or "Basalt flows record the cooling history.",
                    "prefix": "",
                    "suffix": "",
                    "stance": "asserted",
                },
            },
            {
                "unit_id": "s001",
                "disposition": "skip",
                "reason": {"code": "not_a_claim", "detail": "Heading only."},
                "locator": {
                    "regime": "markdown-heading-path-with-quote",
                    "value": ["Section"],
                    "quote": {"exact": "Basalt flows", "prefix": "", "suffix": ""},
                },
            },
        ],
    }


def test_parse_valid_decomposition(tmp_path):
    artifact = parse_submitted_decomposition(json.dumps(_artifact(tmp_path)), project_root=tmp_path)
    assert artifact.schema_version == 1
    assert artifact.source_ref == "prose-source:example"
    assert artifact.units[0].unit_id == "u001"
    assert artifact.units[0].candidate is not None
    assert artifact.units[1].reason_code == "not_a_claim"


def test_candidate_locator_quote_is_rejected(tmp_path):
    raw = _artifact(tmp_path)
    raw["units"][0]["locator"]["quote"] = {"exact": "duplicate", "prefix": "", "suffix": ""}
    with pytest.raises(DecompositionError, match="candidate unit must not carry locator.quote"):
        parse_submitted_decomposition(json.dumps(raw), project_root=tmp_path)


def test_unknown_skip_reason_fails(tmp_path):
    raw = _artifact(tmp_path)
    raw["units"][1]["reason"]["code"] = "mystery"
    with pytest.raises(DecompositionError, match="unknown skip reason"):
        parse_submitted_decomposition(json.dumps(raw), project_root=tmp_path)


def test_candidate_payload_must_be_statement_candidate(tmp_path):
    raw = _artifact(tmp_path)
    raw["units"][0]["payload"] = {
        "type": "metaphor",
        "exact": "Basalt flows",
        "prefix": "",
        "suffix": "",
        "source_domain": "geology",
        "target_domain": "history",
    }
    with pytest.raises(DecompositionError, match="StatementCandidate"):
        parse_submitted_decomposition(json.dumps(raw), project_root=tmp_path)


def test_duplicate_unit_id_fails(tmp_path):
    raw = _artifact(tmp_path)
    raw["units"][1]["unit_id"] = "u001"
    with pytest.raises(DecompositionError, match="duplicate unit_id"):
        parse_submitted_decomposition(json.dumps(raw), project_root=tmp_path)


def test_fingerprint_ignores_artifact_local_unit_id(tmp_path):
    first = parse_submitted_decomposition(json.dumps(_artifact(tmp_path, unit_id="u001")), project_root=tmp_path)
    second = parse_submitted_decomposition(json.dumps(_artifact(tmp_path, unit_id="u777")), project_root=tmp_path)
    assert first.units[0].fingerprint == second.units[0].fingerprint


def test_artifact_unit_ref_uses_annotation_namespace(tmp_path):
    artifact = parse_submitted_decomposition(json.dumps(_artifact(tmp_path)), project_root=tmp_path)
    assert artifact_unit_ref(artifact, artifact.units[0]) == (
        "annotation:data/prose-decompositions/example/generations/decomp-1.json#u001"
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=science/src:science/model/src science/.venv/bin/pytest -q science/tests/test_prose_decomposition.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.annotation.prose_decomposition'`.

- [ ] **Step 3: Create the parser module**

Create `science/src/science_tool/annotation/prose_decomposition.py` with these public names and behavior:

```python
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Literal

from science_tool.annotation.statement_extract import CandidateError, StatementCandidate, parse_candidates

SUPPORTED_SCHEMA_VERSION = 1
SOURCE_KIND = "prose-source"
SKIP_REASON_CODES = frozenset(
    {
        "meta_commentary",
        "not_a_claim",
        "duplicate_or_restatement",
        "citation_or_reference_only",
        "out_of_scope",
        "unresolved_or_malformed",
    }
)
LOCATOR_REGIMES = frozenset({"markdown-heading-path", "markdown-heading-path-with-quote"})


class DecompositionError(ValueError):
    """Raised when a prose decomposition artifact is structurally invalid."""


@dataclass(frozen=True)
class Quote:
    exact: str
    prefix: str = ""
    suffix: str = ""


@dataclass(frozen=True)
class MarkdownLocator:
    regime: str
    heading_path: tuple[str, ...]
    quote: Quote | None = None


@dataclass(frozen=True)
class DecompositionSource:
    kind: str
    slug: str
    path: Path
    title: str
    content_hash: str


@dataclass(frozen=True)
class DecompositionArtifactMeta:
    artifact_id: str
    generated_at: str
    producer: str


@dataclass(frozen=True)
class DecompositionUnit:
    unit_id: str
    disposition: Literal["candidate", "skip"]
    locator: MarkdownLocator
    fingerprint: str
    candidate: StatementCandidate | None = None
    reason_code: str | None = None
    reason_detail: str = ""


@dataclass(frozen=True)
class DecompositionArtifact:
    schema_version: int
    source: DecompositionSource
    artifact: DecompositionArtifactMeta
    units: tuple[DecompositionUnit, ...]

    @property
    def source_ref(self) -> str:
        return f"{self.source.kind}:{self.source.slug}"
```

Implement these functions in the same module:

```python
def parse_submitted_decomposition(raw: str, *, project_root: Path) -> DecompositionArtifact:
    data = _json_object(raw)
    schema_version = data.get("schema_version")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise DecompositionError(f"unsupported schema_version {schema_version!r}")
    source = _parse_source(data.get("source"), project_root=project_root)
    artifact = _parse_artifact(data.get("artifact"))
    raw_units = data.get("units")
    if not isinstance(raw_units, list):
        raise DecompositionError("units must be a list")
    seen_ids: set[str] = set()
    units: list[DecompositionUnit] = []
    for index, item in enumerate(raw_units):
        unit = _parse_unit(item, index=index, source_ref=f"{source.kind}:{source.slug}")
        if unit.unit_id in seen_ids:
            raise DecompositionError(f"duplicate unit_id {unit.unit_id!r}")
        seen_ids.add(unit.unit_id)
        units.append(unit)
    return DecompositionArtifact(
        schema_version=schema_version,
        source=source,
        artifact=artifact,
        units=tuple(units),
    )


def artifact_storage_root(project_root: Path, slug: str) -> Path:
    return project_root / "data" / "prose-decompositions" / slug


def artifact_generation_relpath(artifact: DecompositionArtifact) -> Path:
    return Path("data") / "prose-decompositions" / artifact.source.slug / "generations" / f"{artifact.artifact.artifact_id}.json"


def artifact_unit_ref(artifact: DecompositionArtifact, unit: DecompositionUnit) -> str:
    return f"annotation:{artifact_generation_relpath(artifact).as_posix()}#{unit.unit_id}"


def compute_source_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
```

Use private helpers with these exact validation rules:

- JSON must be an object.
- `source.kind` must equal `prose-source`.
- `source.slug`, `source.path`, and `source.content_hash` must be non-empty strings.
- `source.path` may begin with `~/d/`; convert it to an absolute path by replacing `~/d/science` with `project_root`.
- Candidate unit payload is validated by `parse_candidates(json.dumps({"candidates": [payload]}))` and the parsed result must be a `StatementCandidate`, not a `FigurativeCandidate`.
- Candidate units reject `locator.quote`.
- Skip units require `reason.code` in `SKIP_REASON_CODES`.
- Unit dispositions other than `candidate` or `skip` fail.
- Fingerprint input is a JSON object with `source_ref`, `locator_regime`, `heading_path`, and normalized quote fields.

Normalization helpers:

```python
_SPACE_RE = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    return _SPACE_RE.sub(" ", value.strip()).casefold()


def source_span_fingerprint(
    *,
    source_ref: str,
    locator: MarkdownLocator,
    quote: Quote,
) -> str:
    payload = {
        "source_ref": source_ref,
        "locator_regime": locator.regime,
        "heading_path": [normalize_text(part) for part in locator.heading_path],
        "quote": {
            "exact": normalize_text(quote.exact),
            "prefix": normalize_text(quote.prefix),
            "suffix": normalize_text(quote.suffix),
        },
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run parser tests**

Run:

```bash
PYTHONPATH=science/src:science/model/src science/.venv/bin/pytest -q science/tests/test_prose_decomposition.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/prose_decomposition.py science/tests/test_prose_decomposition.py
git commit -m "feat(prose): parse decomposition artifacts"
```

---

## Task 3: Markdown Locator Resolution And `InternalProseAdapter`

**Files:**
- Create: `science/src/science_tool/annotation/internal_prose_adapter.py`
- Create: `science/tests/test_internal_prose_adapter.py`

- [ ] **Step 1: Write locator tests**

Create `science/tests/test_internal_prose_adapter.py`:

```python
from pathlib import Path

from science_tool.annotation.internal_prose_adapter import (
    InternalProseAdapter,
    LocatorStatus,
    resolve_markdown_locator,
)
from science_tool.annotation.prose_decomposition import MarkdownLocator, Quote


def test_resolve_unique_heading_path_with_candidate_quote(tmp_path):
    md = tmp_path / "source.md"
    md.write_text("# A\n\nIntro.\n\n## B\n\nThe claim is here.\n", encoding="utf-8")
    locator = MarkdownLocator(regime="markdown-heading-path", heading_path=("A", "B"))
    result = resolve_markdown_locator(md, locator, Quote(exact="The claim is here."))
    assert result.status is LocatorStatus.RESOLVED
    assert result.text == "The claim is here."


def test_ambiguous_heading_path_is_reported(tmp_path):
    md = tmp_path / "source.md"
    md.write_text("# A\n\n## Repeat\n\nOne.\n\n# B\n\n## Repeat\n\nTwo.\n", encoding="utf-8")
    locator = MarkdownLocator(regime="markdown-heading-path", heading_path=("Repeat",))
    result = resolve_markdown_locator(md, locator, Quote(exact="One."))
    assert result.status is LocatorStatus.AMBIGUOUS
    assert "multiple sections" in result.message


def test_quote_missing_is_reported(tmp_path):
    md = tmp_path / "source.md"
    md.write_text("# A\n\nDifferent text.\n", encoding="utf-8")
    locator = MarkdownLocator(regime="markdown-heading-path", heading_path=("A",))
    result = resolve_markdown_locator(md, locator, Quote(exact="The claim is here."))
    assert result.status is LocatorStatus.UNRESOLVED
    assert "quote not found" in result.message


def test_internal_prose_adapter_shape(tmp_path):
    md = tmp_path / "notes.md"
    md.write_text("# Notes\n", encoding="utf-8")
    adapter = InternalProseAdapter()
    assert adapter.name == "internal-prose"
    assert adapter.handles(md) is True
    assert adapter.source_ref(md) == "prose-source:notes"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=science/src:science/model/src science/.venv/bin/pytest -q science/tests/test_internal_prose_adapter.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.annotation.internal_prose_adapter'`.

- [ ] **Step 3: Create the adapter module**

Create `science/src/science_tool/annotation/internal_prose_adapter.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from science_tool.annotation.prose_decomposition import MarkdownLocator, Quote
from science_tool.annotation.text_source_adapter import LocatorRegime, TextSourceAdapter
from science_tool.entities import normalize_to_slug


class LocatorStatus(Enum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class LocatorResolution:
    status: LocatorStatus
    text: str = ""
    message: str = ""
```

Implement `InternalProseAdapter`:

```python
class InternalProseAdapter(TextSourceAdapter):
    name = "internal-prose"
    locator_regime = LocatorRegime.REGENERABLE
    can_fetch = False
    can_seed = False

    def handles(self, source_md: Path) -> bool:
        return source_md.suffix.lower() == ".md" and not source_md.name.endswith(".source.md")

    def source_ref(self, source_md: Path) -> str:
        return f"prose-source:{normalize_to_slug(source_md.stem)}"

    def source_ref_from_slug(self, slug: str) -> str:
        return f"prose-source:{slug}"

    def resolve_unit(self, source_md: Path, locator: MarkdownLocator, quote: Quote) -> LocatorResolution:
        return resolve_markdown_locator(source_md, locator, quote)
```

Implement the Markdown section resolver:

- Parse ATX headings that start with `#`.
- Keep heading levels and section start/end byte offsets.
- A heading path matches when its normalized heading sequence is a suffix of the active heading stack. This lets `["Repeat"]` intentionally be ambiguous if repeated.
- A section-only `markdown-heading-path` match with multiple sections returns `AMBIGUOUS`.
- A quote match searches within the matched section body and returns `RESOLVED` only when exactly one section contains the quote.

Use this normalization inside the module:

```python
def _norm(value: str) -> str:
    return " ".join(value.strip().casefold().split())
```

- [ ] **Step 4: Run locator tests**

Run:

```bash
PYTHONPATH=science/src:science/model/src science/.venv/bin/pytest -q science/tests/test_internal_prose_adapter.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/internal_prose_adapter.py science/tests/test_internal_prose_adapter.py
git commit -m "feat(prose): resolve markdown locators"
```

---

## Task 4: Prose-Source Entity Resolver

**Files:**
- Create: `science/src/science_tool/annotation/prose_source_entity.py`
- Create: `science/tests/test_prose_source_entity.py`

- [ ] **Step 1: Write resolver tests**

Create `science/tests/test_prose_source_entity.py`:

```python
from pathlib import Path

import yaml

from science_tool.annotation.prose_source_entity import resolve_or_create_prose_source


def test_resolver_creates_missing_prose_source(tmp_path):
    source = tmp_path / "docs" / "example.md"
    source.parent.mkdir()
    source.write_text("# Example\n", encoding="utf-8")

    result = resolve_or_create_prose_source(
        project_root=tmp_path,
        slug="example",
        title="Example",
        source_path=source,
        content_hash="sha256:" + "1" * 64,
        artifact_id="decomp-1",
    )

    path = tmp_path / "entities" / "prose-sources" / "example.md"
    assert result.entity_id == "prose-source:example"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(text.split("---", 2)[1])
    assert frontmatter["source_path"]
    assert frontmatter["content_hash"] == "sha256:" + "1" * 64
    assert frontmatter["latest_decomposition_artifact"] == "decomp-1"


def test_resolver_preserves_authored_notes(tmp_path):
    path = tmp_path / "entities" / "prose-sources"
    path.mkdir(parents=True)
    existing = path / "example.md"
    existing.write_text(
        "---\n"
        "id: prose-source:example\n"
        "type: prose-source\n"
        "title: Example\n"
        "status: active\n"
        "source_path: old.md\n"
        "content_hash: sha256:old\n"
        "latest_decomposition_artifact: old\n"
        "source_refs: []\n"
        "related: []\n"
        "created: '2026-06-18'\n"
        "updated: '2026-06-18'\n"
        "---\n"
        "# Example\n\n## Source\n\n## Notes\n\nCurated note.\n",
        encoding="utf-8",
    )
    source = tmp_path / "docs" / "example.md"
    source.parent.mkdir()
    source.write_text("# Example\n", encoding="utf-8")

    resolve_or_create_prose_source(
        project_root=tmp_path,
        slug="example",
        title="Example Changed",
        source_path=source,
        content_hash="sha256:" + "2" * 64,
        artifact_id="decomp-2",
    )

    text = existing.read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(text.split("---", 2)[1])
    assert "Curated note." in text
    assert frontmatter["title"] == "Example"
    assert frontmatter["content_hash"] == "sha256:" + "2" * 64
    assert frontmatter["latest_decomposition_artifact"] == "decomp-2"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=science/src:science/model/src science/.venv/bin/pytest -q science/tests/test_prose_source_entity.py
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create resolver implementation**

Create `science/src/science_tool/annotation/prose_source_entity.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from science_tool.entities import (
    EntityCommandError,
    _atomic_replace_text,
    _parse_markdown_file,
    _render_markdown,
    create_entity,
    find_entity,
)


@dataclass(frozen=True)
class ProseSourceResolution:
    entity_id: str
    path: Path
    created: bool
```

Implement:

```python
def resolve_or_create_prose_source(
    *,
    project_root: Path,
    slug: str,
    title: str,
    source_path: Path,
    content_hash: str,
    artifact_id: str,
    today: date | None = None,
) -> ProseSourceResolution:
    ref = f"prose-source:{slug}"
    created = False
    try:
        location = find_entity(project_root, ref)
        path = location.path
    except EntityCommandError:
        result = create_entity(
            project_root=project_root,
            kind="prose-source",
            title=title,
            slug=slug,
            today=today,
            no_hints=True,
        )
        path = result.path
        created = True

    frontmatter, body = _parse_markdown_file(path)
    frontmatter["source_path"] = _display_path(project_root, source_path)
    frontmatter["content_hash"] = content_hash
    frontmatter["latest_decomposition_artifact"] = artifact_id
    frontmatter["updated"] = (today or date.today()).isoformat()
    _atomic_replace_text(path, _render_markdown(frontmatter, body))
    return ProseSourceResolution(entity_id=ref, path=path, created=created)
```

Add `_display_path(project_root, source_path)` that returns `~/d/science/...` when the path is inside `project_root`, and otherwise returns `str(source_path)`.

- [ ] **Step 4: Run resolver tests**

Run:

```bash
PYTHONPATH=science/src:science/model/src science/.venv/bin/pytest -q science/tests/test_prose_source_entity.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/prose_source_entity.py science/tests/test_prose_source_entity.py
git commit -m "feat(prose): resolve prose source entities"
```

---

## Task 5: Artifact Store And Stale Index

**Files:**
- Modify: `science/src/science_tool/annotation/prose_decomposition.py`
- Modify: `science/tests/test_prose_decomposition.py`

- [ ] **Step 1: Add store tests**

Append to `science/tests/test_prose_decomposition.py`:

```python
from science_tool.annotation.prose_decomposition import ProseDecompositionStore


def test_store_persists_generation_and_index(tmp_path):
    artifact = parse_submitted_decomposition(json.dumps(_artifact(tmp_path)), project_root=tmp_path)
    store = ProseDecompositionStore(tmp_path)
    report = store.persist(artifact)
    assert report.artifact_id == "decomp-1"
    assert report.stale_fingerprints == []
    assert (tmp_path / "data" / "prose-decompositions" / "example" / "generations" / "decomp-1.json").exists()
    assert (tmp_path / "data" / "prose-decompositions" / "example" / "index.json").exists()


def test_store_marks_missing_fingerprint_stale(tmp_path):
    first = parse_submitted_decomposition(json.dumps(_artifact(tmp_path)), project_root=tmp_path)
    raw_second = _artifact(tmp_path, quote="A different claim.")
    raw_second["artifact"]["id"] = "decomp-2"
    second = parse_submitted_decomposition(json.dumps(raw_second), project_root=tmp_path)
    store = ProseDecompositionStore(tmp_path)
    store.persist(first)
    report = store.persist(second)
    assert len(report.stale_fingerprints) == 1


def test_store_preserves_promoted_link_across_unit_renumber(tmp_path):
    first = parse_submitted_decomposition(json.dumps(_artifact(tmp_path, unit_id="u001")), project_root=tmp_path)
    second_raw = _artifact(tmp_path, unit_id="u777")
    second_raw["artifact"]["id"] = "decomp-2"
    second = parse_submitted_decomposition(json.dumps(second_raw), project_root=tmp_path)
    store = ProseDecompositionStore(tmp_path)
    store.persist(first)
    store.record_promotion(source_slug="example", fingerprint=first.units[0].fingerprint, promoted_to="proposition:x")
    store.persist(second)
    state = store.load_index("example")
    assert state["units"][first.units[0].fingerprint]["promoted_to"] == "proposition:x"
    assert state["units"][first.units[0].fingerprint]["latest_unit_id"] == "u777"
    assert state["units"][first.units[0].fingerprint]["stale"] is False


def test_store_load_latest_reparses_generation(tmp_path):
    artifact = parse_submitted_decomposition(json.dumps(_artifact(tmp_path)), project_root=tmp_path)
    store = ProseDecompositionStore(tmp_path)
    store.persist(artifact)
    latest = store.load_latest("example")
    assert latest.artifact.artifact_id == "decomp-1"
    assert latest.units[0].unit_id == "u001"
```

- [ ] **Step 2: Run store tests to verify they fail**

Run:

```bash
PYTHONPATH=science/src:science/model/src science/.venv/bin/pytest -q \
  science/tests/test_prose_decomposition.py::test_store_persists_generation_and_index \
  science/tests/test_prose_decomposition.py::test_store_marks_missing_fingerprint_stale \
  science/tests/test_prose_decomposition.py::test_store_preserves_promoted_link_across_unit_renumber \
  science/tests/test_prose_decomposition.py::test_store_load_latest_reparses_generation
```

Expected: FAIL because `ProseDecompositionStore` is not defined.

- [ ] **Step 3: Add store implementation**

In `science/src/science_tool/annotation/prose_decomposition.py`, add:

```python
@dataclass(frozen=True)
class StorePersistReport:
    source_slug: str
    artifact_id: str
    stale_fingerprints: list[str]


class ProseDecompositionStore:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()

    def source_dir(self, slug: str) -> Path:
        return artifact_storage_root(self.project_root, slug)

    def generation_path(self, artifact: DecompositionArtifact) -> Path:
        return self.project_root / artifact_generation_relpath(artifact)

    def index_path(self, slug: str) -> Path:
        return self.source_dir(slug) / "index.json"

    def load_index(self, slug: str) -> dict[str, Any]:
        path = self.index_path(slug)
        if not path.exists():
            return {
                "schema_version": 1,
                "source_ref": f"prose-source:{slug}",
                "latest_artifact_id": "",
                "artifacts": [],
                "units": {},
            }
        return json.loads(path.read_text(encoding="utf-8"))
```

Implement `persist()`:

- Write the submitted raw artifact as canonical JSON under `generations/<artifact_id>.json`.
- Preserve old unit rows in `index.json`.
- Mark a previous row stale when its fingerprint is absent from the new artifact.
- Mark current fingerprints stale `False`.
- Carry existing `promoted_to` forward when the fingerprint is unchanged.
- Store `latest_unit_id`, `latest_artifact_id`, `latest_disposition`, and `artifact_unit_ref`.

Implement `record_promotion(source_slug, fingerprint, promoted_to)`:

- Load index.
- Fail with `DecompositionError` if fingerprint is absent.
- Set `units[fingerprint]["promoted_to"] = promoted_to`.
- Rewrite `index.json` atomically.

Implement `load_latest(slug) -> DecompositionArtifact`:

- Load `index.json`.
- Read `latest_artifact_id`.
- Read `generations/<latest_artifact_id>.json`.
- Re-parse the stored generation with `parse_submitted_decomposition(..., project_root=self.project_root)`.
- Fail with `DecompositionError` if the index or generation is missing.

Use a helper:

```python
def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
```

- [ ] **Step 4: Run store tests**

Run:

```bash
PYTHONPATH=science/src:science/model/src science/.venv/bin/pytest -q science/tests/test_prose_decomposition.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/prose_decomposition.py science/tests/test_prose_decomposition.py
git commit -m "feat(prose): persist decomposition artifacts"
```

---

## Task 6: Ingest CLI

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py`
- Create: `science/tests/test_annotate_prose_decomposition_cli.py`

- [ ] **Step 1: Write ingest CLI tests**

Create `science/tests/test_annotate_prose_decomposition_cli.py`:

```python
import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.annotation.cli import annotate_group
from science_tool.annotation.prose_decomposition import compute_source_hash


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "docs" / "example.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("# Section\n\nBasalt flows record the cooling history.\n", encoding="utf-8")
    return source


def _artifact_file(tmp_path: Path, *, artifact_id="decomp-1", content_hash=None) -> Path:
    source = _source(tmp_path)
    payload = {
        "schema_version": 1,
        "source": {
            "kind": "prose-source",
            "slug": "example",
            "path": str(source),
            "title": "Example",
            "content_hash": content_hash or compute_source_hash(source),
        },
        "artifact": {"id": artifact_id, "generated_at": "2026-06-18T12:00:00Z", "producer": "offline-agent"},
        "units": [
            {
                "unit_id": "u001",
                "disposition": "candidate",
                "locator": {"regime": "markdown-heading-path", "value": ["Section"]},
                "payload": {
                    "type": "proposition",
                    "exact": "Basalt flows record the cooling history.",
                    "prefix": "",
                    "suffix": "",
                    "stance": "asserted",
                },
            }
        ],
    }
    path = tmp_path / f"{artifact_id}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_ingest_creates_source_entity_and_artifact(tmp_path):
    path = _artifact_file(tmp_path)
    result = CliRunner().invoke(
        annotate_group,
        ["ingest-prose-decomposition", str(path), "--root", str(tmp_path), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["source_ref"] == "prose-source:example"
    assert payload["artifact_id"] == "decomp-1"
    assert (tmp_path / "entities" / "prose-sources" / "example.md").exists()
    assert (tmp_path / "data" / "prose-decompositions" / "example" / "index.json").exists()


def test_ingest_hash_mismatch_fails_without_allow_changed(tmp_path):
    path = _artifact_file(tmp_path, content_hash="sha256:" + "0" * 64)
    result = CliRunner().invoke(
        annotate_group,
        ["ingest-prose-decomposition", str(path), "--root", str(tmp_path)],
    )
    assert result.exit_code != 0
    assert "content hash mismatch" in result.output


def test_ingest_hash_mismatch_can_be_allowed(tmp_path):
    path = _artifact_file(tmp_path, content_hash="sha256:" + "0" * 64)
    result = CliRunner().invoke(
        annotate_group,
        ["ingest-prose-decomposition", str(path), "--root", str(tmp_path), "--allow-changed"],
    )
    assert result.exit_code == 0, result.output
```

- [ ] **Step 2: Run CLI tests to verify they fail**

Run:

```bash
PYTHONPATH=science/src:science/model/src science/.venv/bin/pytest -q \
  science/tests/test_annotate_prose_decomposition_cli.py::test_ingest_creates_source_entity_and_artifact \
  science/tests/test_annotate_prose_decomposition_cli.py::test_ingest_hash_mismatch_fails_without_allow_changed \
  science/tests/test_annotate_prose_decomposition_cli.py::test_ingest_hash_mismatch_can_be_allowed
```

Expected: FAIL because the Click command does not exist.

- [ ] **Step 3: Add `ingest-prose-decomposition` command**

In `science/src/science_tool/annotation/cli.py`, add:

```python
@annotate_group.command("ingest-prose-decomposition")
@click.argument("artifact_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option("--allow-changed", is_flag=True, default=False)
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def ingest_prose_decomposition_cmd(
    artifact_path: Path,
    root: Path | None,
    allow_changed: bool,
    fmt: str,
) -> None:
    """Ingest an offline internal-prose decomposition JSON artifact."""
```

Command body:

- `project_root = (root or Path.cwd()).resolve()`
- Parse with `parse_submitted_decomposition(artifact_path.read_text(...), project_root=project_root)`.
- Compute `compute_source_hash(artifact.source.path)`.
- If hash differs and `allow_changed` is false, raise `click.ClickException("content hash mismatch: ...")`.
- Call `resolve_or_create_prose_source(...)`.
- Call `ProseDecompositionStore(project_root).persist(artifact)`.
- Emit JSON fields `source_ref`, `artifact_id`, `stale`, and `source_entity_created`.

Catch `DecompositionError` and `EntityCommandError` and re-raise as `click.ClickException`.

- [ ] **Step 4: Run ingest CLI tests**

Run:

```bash
PYTHONPATH=science/src:science/model/src science/.venv/bin/pytest -q \
  science/tests/test_annotate_prose_decomposition_cli.py::test_ingest_creates_source_entity_and_artifact \
  science/tests/test_annotate_prose_decomposition_cli.py::test_ingest_hash_mismatch_fails_without_allow_changed \
  science/tests/test_annotate_prose_decomposition_cli.py::test_ingest_hash_mismatch_can_be_allowed
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/cli.py science/tests/test_annotate_prose_decomposition_cli.py
git commit -m "feat(prose): ingest decomposition artifacts"
```

---

## Task 7: Check CLI

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py`
- Modify: `science/tests/test_annotate_prose_decomposition_cli.py`

- [ ] **Step 1: Add check CLI tests**

Append to `science/tests/test_annotate_prose_decomposition_cli.py`:

```python
def test_check_reports_candidate(tmp_path):
    ingest = CliRunner().invoke(
        annotate_group,
        ["ingest-prose-decomposition", str(_artifact_file(tmp_path)), "--root", str(tmp_path)],
    )
    assert ingest.exit_code == 0, ingest.output
    result = CliRunner().invoke(
        annotate_group,
        ["check-prose-decomposition", "--source", "prose-source:example", "--root", str(tmp_path), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["source_ref"] == "prose-source:example"
    assert payload["units"][0]["unit_id"] == "u001"
    assert payload["units"][0]["status"] == "candidate"
    assert payload["units"][0]["locator_status"] == "resolved"


def test_check_reports_ambiguous_heading_path(tmp_path):
    source = _source(tmp_path)
    source.write_text("# A\n\n## Repeat\n\nOne.\n\n# B\n\n## Repeat\n\nTwo.\n", encoding="utf-8")
    path = _artifact_file(tmp_path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["source"]["content_hash"] = compute_source_hash(source)
    raw["units"][0]["locator"]["value"] = ["Repeat"]
    path.write_text(json.dumps(raw), encoding="utf-8")
    ingest = CliRunner().invoke(
        annotate_group,
        ["ingest-prose-decomposition", str(path), "--root", str(tmp_path)],
    )
    assert ingest.exit_code == 0, ingest.output
    result = CliRunner().invoke(
        annotate_group,
        ["check-prose-decomposition", "--source", "prose-source:example", "--root", str(tmp_path), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["units"][0]["locator_status"] == "ambiguous"
```

- [ ] **Step 2: Run check tests to verify they fail**

Run:

```bash
PYTHONPATH=science/src:science/model/src science/.venv/bin/pytest -q \
  science/tests/test_annotate_prose_decomposition_cli.py::test_check_reports_candidate \
  science/tests/test_annotate_prose_decomposition_cli.py::test_check_reports_ambiguous_heading_path
```

Expected: FAIL because the command does not exist.

- [ ] **Step 3: Add `check-prose-decomposition` command**

In `science/src/science_tool/annotation/cli.py`, add:

```python
@annotate_group.command("check-prose-decomposition")
@click.option("--source", "source_ref", required=True)
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def check_prose_decomposition_cmd(source_ref: str, root: Path | None, fmt: str) -> None:
    """Check the latest internal-prose decomposition artifact."""
```

Command body:

- Validate `source_ref.startswith("prose-source:")`.
- Load index from `ProseDecompositionStore`.
- Load the latest artifact with `ProseDecompositionStore.load_latest(slug)`.
- For each unit, choose quote:
  - candidate: `Quote(unit.candidate.exact, unit.candidate.prefix, unit.candidate.suffix)`
  - skip: `unit.locator.quote`
- Resolve with `InternalProseAdapter().resolve_unit(...)`.
- Emit JSON rows with `unit_id`, `disposition`, `status`, `fingerprint`, `locator_status`, `message`, `promoted_to`, and `stale`.

- [ ] **Step 4: Run check tests**

Run:

```bash
PYTHONPATH=science/src:science/model/src science/.venv/bin/pytest -q \
  science/tests/test_annotate_prose_decomposition_cli.py::test_check_reports_candidate \
  science/tests/test_annotate_prose_decomposition_cli.py::test_check_reports_ambiguous_heading_path
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/cli.py science/src/science_tool/annotation/prose_decomposition.py science/tests/test_annotate_prose_decomposition_cli.py
git commit -m "feat(prose): check decomposition locators"
```

---

## Task 8: Prose Promotion Core And CLI

**Files:**
- Create: `science/src/science_tool/annotation/prose_promote.py`
- Modify: `science/src/science_tool/annotation/cli.py`
- Create: `science/tests/test_prose_promote.py`
- Modify: `science/tests/test_annotate_prose_decomposition_cli.py`

- [ ] **Step 1: Write promotion core test**

Create `science/tests/test_prose_promote.py`:

```python
import json
from pathlib import Path

import pytest

from science_tool.annotation.prose_decomposition import ProseDecompositionStore, parse_submitted_decomposition
from science_tool.annotation.prose_promote import ProsePromotionError, promote_prose_unit


def _project(tmp_path: Path, *, units: list[dict] | None = None, artifact_id: str = "decomp-1") -> tuple[ProseDecompositionStore, str]:
    (tmp_path / "entities" / "propositions").mkdir(parents=True, exist_ok=True)
    source = tmp_path / "docs" / "example.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("# Section\n\nBasalt flows record the cooling history.\n", encoding="utf-8")
    default_units = [
        {
            "unit_id": "u001",
            "disposition": "candidate",
            "locator": {"regime": "markdown-heading-path", "value": ["Section"]},
            "payload": {
                "type": "proposition",
                "exact": "Basalt flows record the cooling history.",
                "prefix": "",
                "suffix": "",
                "stance": "asserted",
            },
        }
    ]
    raw = {
        "schema_version": 1,
        "source": {
            "kind": "prose-source",
            "slug": "example",
            "path": str(source),
            "title": "Example",
            "content_hash": "sha256:" + "0" * 64,
        },
        "artifact": {"id": artifact_id, "generated_at": "2026-06-18T12:00:00Z", "producer": "offline-agent"},
        "units": units or default_units,
    }
    artifact = parse_submitted_decomposition(json.dumps(raw), project_root=tmp_path)
    store = ProseDecompositionStore(tmp_path)
    store.persist(artifact)
    return store, artifact.units[0].fingerprint


def test_promote_prose_unit_mints_proposition_and_records_state(tmp_path):
    store, fingerprint = _project(tmp_path)
    report = promote_prose_unit(
        project_root=tmp_path,
        source_ref="prose-source:example",
        unit_id="u001",
        apply=True,
    )
    assert report.minted == 1
    prop = tmp_path / "entities" / "propositions" / "basalt-flows-record-the-cooling-history.md"
    assert prop.exists()
    text = prop.read_text(encoding="utf-8")
    assert "prose-source:example" in text
    assert "annotation:data/prose-decompositions/example/generations/decomp-1.json#u001" in text
    assert store.load_index("example")["units"][fingerprint]["promoted_to"].startswith("proposition:")


def test_promote_prose_unit_links_existing_proposition_and_appends_two_refs(tmp_path):
    _project(tmp_path)
    existing = tmp_path / "entities" / "propositions" / "existing.md"
    existing.write_text(
        "---\n"
        "id: proposition:existing\n"
        "type: proposition\n"
        "title: Basalt flows record the cooling history.\n"
        "status: draft\n"
        "source_refs: []\n"
        "related: []\n"
        "created: '2026-06-18'\n"
        "updated: '2026-06-18'\n"
        "---\n"
        "# Existing\n",
        encoding="utf-8",
    )

    report = promote_prose_unit(
        project_root=tmp_path,
        source_ref="prose-source:example",
        unit_id="u001",
        apply=True,
    )

    text = existing.read_text(encoding="utf-8")
    assert report.linked == 1
    assert "prose-source:example" in text
    assert "annotation:data/prose-decompositions/example/generations/decomp-1.json#u001" in text
    assert not (tmp_path / "entities" / "propositions" / "basalt-flows-record-the-cooling-history.md").exists()


def test_promote_prose_unit_rejects_skip_unit(tmp_path):
    skip_units = [
        {
            "unit_id": "s001",
            "disposition": "skip",
            "reason": {"code": "not_a_claim", "detail": "Heading only."},
            "locator": {
                "regime": "markdown-heading-path-with-quote",
                "value": ["Section"],
                "quote": {"exact": "Basalt flows", "prefix": "", "suffix": ""},
            },
        }
    ]
    _project(tmp_path, units=skip_units)

    with pytest.raises(ProsePromotionError, match="non-candidate"):
        promote_prose_unit(
            project_root=tmp_path,
            source_ref="prose-source:example",
            unit_id="s001",
            apply=True,
        )


def test_promote_prose_unit_rejects_missing_or_stale_previous_unit(tmp_path):
    first_units = [
        {
            "unit_id": "u001",
            "disposition": "candidate",
            "locator": {"regime": "markdown-heading-path", "value": ["Section"]},
            "payload": {
                "type": "proposition",
                "exact": "Basalt flows record the cooling history.",
                "prefix": "",
                "suffix": "",
                "stance": "asserted",
            },
        }
    ]
    second_units = [
        {
            "unit_id": "u777",
            "disposition": "candidate",
            "locator": {"regime": "markdown-heading-path", "value": ["Section"]},
            "payload": {
                "type": "proposition",
                "exact": "A different claim.",
                "prefix": "",
                "suffix": "",
                "stance": "asserted",
            },
        }
    ]
    _project(tmp_path, units=first_units, artifact_id="decomp-1")
    _project(tmp_path, units=second_units, artifact_id="decomp-2")

    with pytest.raises(ProsePromotionError, match="not in latest artifact|stale"):
        promote_prose_unit(
            project_root=tmp_path,
            source_ref="prose-source:example",
            unit_id="u001",
            apply=True,
        )


def test_promote_prose_unit_rejects_already_promoted_unit(tmp_path):
    store, fingerprint = _project(tmp_path)
    store.record_promotion(source_slug="example", fingerprint=fingerprint, promoted_to="proposition:existing")

    with pytest.raises(ProsePromotionError, match="already promoted"):
        promote_prose_unit(
            project_root=tmp_path,
            source_ref="prose-source:example",
            unit_id="u001",
            apply=True,
        )


def test_promote_prose_unit_rejects_candidate_type_not_in_targets(tmp_path, monkeypatch):
    _project(tmp_path)
    import science_tool.annotation.prose_promote as prose_promote

    real_build_targets = prose_promote.build_targets

    def targets_without_proposition():
        targets = real_build_targets()
        targets.pop("proposition")
        return targets

    monkeypatch.setattr(prose_promote, "build_targets", targets_without_proposition)

    with pytest.raises(ProsePromotionError, match="not a promotable target"):
        promote_prose_unit(
            project_root=tmp_path,
            source_ref="prose-source:example",
            unit_id="u001",
            apply=True,
        )
```

- [ ] **Step 2: Run core test to verify it fails**

Run:

```bash
PYTHONPATH=science/src:science/model/src science/.venv/bin/pytest -q science/tests/test_prose_promote.py
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create promotion implementation**

Create `science/src/science_tool/annotation/prose_promote.py` with:

```python
from __future__ import annotations

from pathlib import Path

from science_tool.annotation.internal_prose_adapter import InternalProseAdapter, LocatorStatus
from science_tool.annotation.prose_decomposition import (
    DecompositionError,
    ProseDecompositionStore,
    Quote,
    artifact_unit_ref,
)
from science_tool.annotation.promote import (
    ApplyReport,
    Promotable,
    build_targets,
    decide_all,
    load_corpora,
)
from science_tool.entities import append_entity_source_ref, find_entity


class ProsePromotionError(ValueError):
    """Raised when a prose unit cannot be promoted."""
```

Implement `promote_prose_unit(project_root, source_ref, unit_id, apply)`:

- Load latest artifact and index.
- Find unit by `unit_id`.
- Reject missing, non-candidate, stale, and already-promoted units.
- Resolve locator with `InternalProseAdapter`; reject unresolved or ambiguous.
- Convert to the existing promotion decision shape:

```python
from science_tool.annotation.promote import Promotable

promotable = Promotable(
    ref=artifact_unit_ref(artifact, unit),
    frag=unit.unit_id,
    claim=unit.candidate.exact,
    subject=unit.candidate.subject,
    object=unit.candidate.object,
    kind=unit.candidate.type,
)
```

- Build targets with `targets = build_targets()`.
- Before calling `decide_all`, reject `unit.candidate.type` when it is not a key in `targets` with `ProsePromotionError(f"candidate type {unit.candidate.type!r} is not a promotable target")`. This keeps bad future candidate types from surfacing as `KeyError`.
- Use `load_corpora` and `decide_all([promotable], corpora, targets)`.
- In read-only mode, return the candidate decision without writing.
- In apply mode:
  - For `MINT`, call `targets[c.kind].mint(c, [source_ref, c.ref], project_root, None)`.
  - For `LINK`, resolve the existing entity file with `dest = find_entity(project_root, c.slug).path`. In a LINK candidate, `c.slug` is the full ref string `"<kind>:<local_part>"`, not a bare slug.
  - For `LINK`, append both provenance refs by calling `append_entity_source_ref(dest, source_ref)` and `append_entity_source_ref(dest, c.ref)`. The function accepts one ref per call and takes a file path, not `project_root`.
  - Record promotion in `ProseDecompositionStore.record_promotion(...)`.
  - Return `ApplyReport`.

Do not call `annotation.promote.apply_candidates`, because that function writes back to `.anno.trig`.

- [ ] **Step 4: Run core promotion test**

Run:

```bash
PYTHONPATH=science/src:science/model/src science/.venv/bin/pytest -q science/tests/test_prose_promote.py
```

Expected: PASS.

- [ ] **Step 5: Add CLI tests**

Append to `science/tests/test_annotate_prose_decomposition_cli.py`:

```python
def test_promote_prose_decomposition_apply_mints(tmp_path):
    ingest = CliRunner().invoke(
        annotate_group,
        ["ingest-prose-decomposition", str(_artifact_file(tmp_path)), "--root", str(tmp_path)],
    )
    assert ingest.exit_code == 0, ingest.output
    result = CliRunner().invoke(
        annotate_group,
        [
            "promote-prose-decomposition",
            "--source", "prose-source:example",
            "--unit", "u001",
            "--root", str(tmp_path),
            "--apply",
            "--format", "json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["minted"] == 1
    assert (tmp_path / "entities" / "propositions" / "basalt-flows-record-the-cooling-history.md").exists()


def test_promote_prose_decomposition_rejects_unresolved_locator(tmp_path):
    path = _artifact_file(tmp_path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["units"][0]["payload"]["exact"] = "Not present."
    path.write_text(json.dumps(raw), encoding="utf-8")
    ingest = CliRunner().invoke(
        annotate_group,
        ["ingest-prose-decomposition", str(path), "--root", str(tmp_path)],
    )
    assert ingest.exit_code == 0, ingest.output
    result = CliRunner().invoke(
        annotate_group,
        [
            "promote-prose-decomposition",
            "--source", "prose-source:example",
            "--unit", "u001",
            "--root", str(tmp_path),
            "--apply",
        ],
    )
    assert result.exit_code != 0
    assert "locator" in result.output
```

- [ ] **Step 6: Add `promote-prose-decomposition` command**

In `science/src/science_tool/annotation/cli.py`, add:

```python
@annotate_group.command("promote-prose-decomposition")
@click.option("--source", "source_ref", required=True)
@click.option("--unit", "unit_id", required=True)
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option("--apply", "do_apply", is_flag=True, default=False)
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def promote_prose_decomposition_cmd(
    source_ref: str,
    unit_id: str,
    root: Path | None,
    do_apply: bool,
    fmt: str,
) -> None:
    """Promote one validated internal-prose decomposition candidate."""
```

Command body:

- Validate `source_ref.startswith("prose-source:")`.
- Call `promote_prose_unit(project_root=..., source_ref=source_ref, unit_id=unit_id, apply=do_apply)`.
- Emit JSON with `minted`, `linked`, `skipped`, and `written`.
- Catch `ProsePromotionError` and `DecompositionError` as `click.ClickException`.

- [ ] **Step 7: Run prose promotion CLI tests**

Run:

```bash
PYTHONPATH=science/src:science/model/src science/.venv/bin/pytest -q \
  science/tests/test_prose_promote.py \
  science/tests/test_annotate_prose_decomposition_cli.py::test_promote_prose_decomposition_apply_mints \
  science/tests/test_annotate_prose_decomposition_cli.py::test_promote_prose_decomposition_rejects_unresolved_locator
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add \
  science/src/science_tool/annotation/prose_promote.py \
  science/src/science_tool/annotation/cli.py \
  science/tests/test_prose_promote.py \
  science/tests/test_annotate_prose_decomposition_cli.py
git commit -m "feat(prose): promote decomposition candidates"
```

---

## Task 9: Regression Net And Documentation Reconciliation

**Files:**
- Modify: `docs/plans/2026-06-18-prose-epistemics-p2-internal-prose-design.md` only if implementation discovers a deliberate design-plan reconciliation.

- [ ] **Step 1: Run the focused P2 and P1 regression suite**

Run:

```bash
PYTHONPATH=science/src:science/model/src science/.venv/bin/pytest -q \
  science/tests/test_text_source_adapter.py \
  science/tests/test_annotate_extract_cli.py \
  science/tests/test_annotate_promote_cli.py \
  science/tests/test_prose_decomposition.py \
  science/tests/test_internal_prose_adapter.py \
  science/tests/test_prose_source_entity.py \
  science/tests/test_prose_promote.py \
  science/tests/test_annotate_prose_decomposition_cli.py \
  science/model/tests/test_kind_reconciliation.py \
  science/tests/test_kind_reconciliation_registry.py
```

Expected: PASS.

- [ ] **Step 2: Run formatting/lint checks on touched Python files**

Run:

```bash
uv run --frozen ruff check \
  science/src/science_tool/annotation/prose_decomposition.py \
  science/src/science_tool/annotation/internal_prose_adapter.py \
  science/src/science_tool/annotation/prose_source_entity.py \
  science/src/science_tool/annotation/prose_promote.py \
  science/src/science_tool/annotation/cli.py \
  science/tests/test_prose_decomposition.py \
  science/tests/test_internal_prose_adapter.py \
  science/tests/test_prose_source_entity.py \
  science/tests/test_prose_promote.py \
  science/tests/test_annotate_prose_decomposition_cli.py
```

Expected: PASS.

- [ ] **Step 3: Confirm paper command behavior remains unchanged**

Run:

```bash
PYTHONPATH=science/src:science/model/src science/.venv/bin/pytest -q \
  science/tests/test_annotate_extract_cli.py \
  science/tests/test_annotate_promote_cli.py
```

Expected: PASS, including `test_promote_unhandled_source_fails_loud`.

- [ ] **Step 4: Commit any docs-only reconciliation if needed**

If the implementation required a deliberate design-plan reconciliation, edit `docs/plans/2026-06-18-prose-epistemics-p2-internal-prose-design.md` and add a short note naming the final behavior.

Commit command:

```bash
git add docs/plans/2026-06-18-prose-epistemics-p2-internal-prose-design.md
git commit -m "docs(prose-epistemics): reconcile P2 implementation details"
```

Skip this commit if no design reconciliation was needed.

---

## Self-Review Checklist

Before executing this plan, verify:

- Task 1 makes `prose-source:<slug>` resolvable through the normal entity/materialization path.
- Task 2 rejects raw agent output that does not validate as schema version 1.
- Task 2 uses `StatementCandidate` fields as the only authoritative candidate quote.
- Task 5 compares source-span fingerprints, not artifact-local `unit_id`, across generations.
- Task 6 validates before writing and uses idempotent source entity resolution before artifact persistence.
- Task 7 treats ambiguous heading paths as unresolved findings.
- Task 8 records both `prose-source:<slug>` and `annotation:data/prose-decompositions/...#unit` in promoted entity `source_refs`.
- Task 8 does not call `.anno.trig` sidecar code.
- P1 paper extraction/promotion tests still pass.
