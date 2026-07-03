# Entity Origin Provenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `origins` (known-originator claims) + `added_by` (discovery stamp) provenance model to hypothesis/question/topic/theme entities, materialized into the graph as minimal PROV-O, without affecting evidential weight.

**Architecture:** Two optional fields on the base Pydantic `Entity` (so all kinds parse/validate/materialize them uniformly); JSON-schema declaration only for the mixin'd kinds (topic/theme); template scaffolding + `VALID_FIELD_NAMES` for the four v1 kinds; a `sci:Origin` reified node per origin in the `provenance` named graph; health checks for unresolved `paper:` and unknown `cite:` origin refs; minimal `add-*` prompt wiring.

**Tech Stack:** Python 3.12, Pydantic v2, rdflib, jsonschema (Draft 2020-12), pytest, uv.

## Global Constraints

- **Design spec:** `docs/plans/2026-07-03-entity-origin-provenance.md` (this plan implements it verbatim).
- **Provenance is metadata only; it MUST NOT affect evidential weight.** No belief/scoring code changes in this plan.
- **Two packages, run tests from the package dir** (never repo root): model work `cd science/model && uv run --frozen pytest`; tool work `cd science && uv run --frozen pytest`. Lint/types from `science/`: `uv run ruff check`, `uv run pyright`.
- **No AI-attribution trailers** on commits.
- **Field is `origins` (plural, list).** A scalar `origin: str | None` already exists on `Entity` (dataset external/derived) — do **not** touch or conflate it.
- **Literature `ref` accepts only `paper:<key>` or `cite:<key>`.** Bare/other prefixes are rejected at the model layer.
- **No JSON-schema version bumps** — additions are optional/additive; confirm via schema tests.
- Work happens in the worktree `.worktrees/entity-origin-provenance` on branch `entity-origin-provenance`. All paths below are repo-relative to that worktree root.

---

## File Structure

- `science/model/src/science_model/entities.py` — **new** `OriginType`, `OriginRecord`; **new** `origins`/`added_by` fields on `Entity`.
- `science/model/src/science_model/frontmatter.py` — parse `origins`/`added_by` from frontmatter into the Entity kwargs.
- `science/model/src/science_model/templates.py` — add `origins` to `VALID_FIELD_NAMES`.
- `science/model/src/science_model/templates/{hypothesis,question,topic,theme}.md` **and** `templates/{hypothesis,question,topic,theme}.md` — scaffold `origins: []` (both dirs, mirrored).
- `science/model/src/science_model/schemas/mixin-topic-2.0.json`, `mixin-theme-2.0.json` — declare `origins`/`added_by`.
- `science/src/science_tool/graph/materialize.py` — emit `sci:Origin` nodes + `sci:addedBy` in `_add_entity`.
- `science/src/science_tool/graph/health.py` — origin-ref health checks.
- `commands/add-hypothesis.md`, `commands/add-question.md`, `commands/research-topic.md` — origin elicitation.
- Tests: `science/model/tests/test_origins.py`, `science/tests/test_graph_origins.py`, `science/tests/test_health_origins.py`.

---

## Task 1: OriginType + OriginRecord model and Entity fields

**Files:**
- Modify: `science/model/src/science_model/entities.py` (add classes before `class Entity` at line 227; add fields inside `Entity` after `source_refs`/`evidence_refs` at lines 246–247)
- Test: `science/model/tests/test_origins.py` (create)

**Interfaces:**
- Produces:
  - `class OriginType(StrEnum)` with members `USER="user"`, `ASSISTANT="assistant"`, `LITERATURE="literature"`.
  - `class OriginRecord(BaseModel)` with fields `type: OriginType`, `ref: str | None = None`, `date: str | None = None`, `independent: bool = False`, `note: str | None = None`; `model_config = ConfigDict(extra="forbid")`.
  - `Entity.origins: list[OriginRecord]` (default empty), `Entity.added_by: str | None`.

- [ ] **Step 1: Write the failing tests**

Create `science/model/tests/test_origins.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_model.entities import OriginRecord, OriginType


def test_user_origin_minimal():
    rec = OriginRecord(type="user")
    assert rec.type is OriginType.USER
    assert rec.ref is None
    assert rec.independent is False


def test_literature_origin_requires_ref():
    with pytest.raises(ValidationError, match="literature origin requires a ref"):
        OriginRecord(type="literature")


def test_literature_ref_must_be_paper_or_cite():
    with pytest.raises(ValidationError, match="paper:<key>' or 'cite:<key>'"):
        OriginRecord(type="literature", ref="smith2019")
    assert OriginRecord(type="literature", ref="paper:smith2019").ref == "paper:smith2019"
    assert OriginRecord(type="literature", ref="cite:Smith2019").ref == "cite:Smith2019"


def test_date_format_validated():
    OriginRecord(type="user", date="2026-05-10")
    with pytest.raises(ValidationError, match="YYYY-MM-DD"):
        OriginRecord(type="user", date="May 2026")


def test_bare_string_and_unknown_keys_rejected():
    with pytest.raises(ValidationError):
        OriginRecord.model_validate("smith2019")  # bare string, not an object
    with pytest.raises(ValidationError):
        OriginRecord(type="user", bogus=1)  # extra=forbid


def test_assistant_ref_is_free_form():
    rec = OriginRecord(type="assistant", ref="llm:opus:explore-ideas-v1")
    assert rec.ref == "llm:opus:explore-ideas-v1"
```

Create `science/model/tests/test_origins_entity.py`? No — keep entity-field coverage here too. Append:

```python
def test_entity_carries_origins_and_added_by():
    from science_model.entities import ProjectEntity

    ent = ProjectEntity(
        id="hypothesis:0001-x",
        kind="hypothesis",
        title="X",
        project="p",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="entities/hypotheses/0001-x.md",
        origins=[{"type": "user", "date": "2026-05-10"},
                 {"type": "literature", "ref": "paper:smith2019", "independent": True}],
        added_by="user",
    )
    assert ent.added_by == "user"
    assert [o.type.value for o in ent.origins] == ["user", "literature"]
    assert ent.origins[1].independent is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science/model && uv run --frozen pytest tests/test_origins.py -v`
Expected: FAIL — `ImportError: cannot import name 'OriginRecord'`.

- [ ] **Step 3: Implement the model**

In `science/model/src/science_model/entities.py`:

Ensure imports at top include `re` and `ConfigDict`:

```python
import re
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, model_validator
```

(`StrEnum` and `model_validator` are already imported; add `re` and `ConfigDict` if missing.)

Add immediately **before** `class Entity(BaseModel):` (line 227):

```python
_ORIGIN_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class OriginType(StrEnum):
    """Where an epistemic entity's idea came from (an originator claim)."""

    USER = "user"
    ASSISTANT = "assistant"
    LITERATURE = "literature"


class OriginRecord(BaseModel):
    """One known originator of an entity.

    Provenance metadata only; MUST NOT affect evidential weight. Records a known
    originator *claim*, not a guarantee of metaphysical first origin.
    """

    model_config = ConfigDict(extra="forbid")

    type: OriginType
    ref: str | None = None
    date: str | None = None
    # True means THIS record converged on the idea independently of the others.
    independent: bool = False
    note: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> "OriginRecord":
        if self.type is OriginType.LITERATURE:
            if not self.ref:
                raise ValueError("literature origin requires a ref")
            if not (self.ref.startswith("paper:") or self.ref.startswith("cite:")):
                raise ValueError(
                    "literature origin ref must be 'paper:<key>' or 'cite:<key>'"
                )
        if self.date is not None and not _ORIGIN_DATE_RE.match(self.date):
            raise ValueError("origin date must be YYYY-MM-DD")
        return self
```

Add inside `class Entity`, immediately after the `evidence_refs` field (line 247):

```python
    # Provenance: known originators (metadata only; MUST NOT affect belief).
    origins: list[OriginRecord] = Field(default_factory=list)
    # Discovery stamp: who/what surfaced this entity into the project.
    added_by: str | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science/model && uv run --frozen pytest tests/test_origins.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/entities.py science/model/tests/test_origins.py
git commit -m "feat(model): OriginType/OriginRecord + origins/added_by on Entity"
```

---

## Task 2: Frontmatter parsing

**Files:**
- Modify: `science/model/src/science_model/frontmatter.py` (the `entity_kwargs` dict, ~lines 375–410)
- Test: `science/model/tests/test_origins.py` (append)

**Interfaces:**
- Consumes: `Entity.origins`, `Entity.added_by` (Task 1). Pydantic coerces list-of-dict → `list[OriginRecord]` automatically.
- Produces: parsed entities carry `origins`/`added_by` from markdown frontmatter.

- [ ] **Step 1: Write the failing test**

Append to `science/model/tests/test_origins.py`:

```python
def test_frontmatter_parses_origins(tmp_path):
    from science_model.frontmatter import parse_entity_file

    p = tmp_path / "0001-x.md"
    p.write_text(
        "---\n"
        "id: hypothesis:0001-x\n"
        "type: hypothesis\n"
        "title: X\n"
        "origins:\n"
        "  - {type: user, date: '2026-05-10'}\n"
        "  - {type: literature, ref: 'paper:smith2019', independent: true}\n"
        "added_by: user\n"
        "---\n\n# X\n",
        encoding="utf-8",
    )
    ent = parse_entity_file(p, project_slug="p")
    assert ent is not None
    assert ent.added_by == "user"
    assert [o.type.value for o in ent.origins] == ["user", "literature"]
    assert ent.origins[1].ref == "paper:smith2019"
```

**Note to implementer:** confirm the real parse entry point name in `frontmatter.py` (search for the function that builds `entity_kwargs`; it may be `parse_entity_file` / `load_entity` / `entity_from_path`). Use the actual name in the test import.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_origins.py::test_frontmatter_parses_origins -v`
Expected: FAIL — `origins` empty / `added_by` is None (keys not read).

- [ ] **Step 3: Add the two keys to `entity_kwargs`**

In `frontmatter.py`, in the `entity_kwargs = {...}` dict (right after the `"source_refs": fm.get("source_refs") or [],` line):

```python
        "origins": fm.get("origins") or [],
        "added_by": fm.get("added_by"),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/model && uv run --frozen pytest tests/test_origins.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/frontmatter.py science/model/tests/test_origins.py
git commit -m "feat(model): parse origins/added_by from entity frontmatter"
```

---

## Task 3: Renderer allowlist + template scaffolding (both dirs)

**Files:**
- Modify: `science/model/src/science_model/templates.py` (`VALID_FIELD_NAMES`, ~line 18)
- Modify: `science/model/src/science_model/templates/hypothesis.md`, `question.md`, `topic.md`, `theme.md`
- Modify: `templates/hypothesis.md`, `question.md`, `topic.md`, `theme.md` (root copies)
- Test: `science/model/tests/test_origins.py` (append)

**Interfaces:**
- Consumes: `VALID_FIELD_NAMES` gates `_template.frontmatter` `{ from: <field> }` targets.
- Produces: rendered hypothesis/question/topic/theme frontmatter contains `origins: []`.

Only `origins` is scaffolded (a visible list). `added_by` is set by write paths (Task 7), not scaffolded, so it does **not** need a `VALID_FIELD_NAMES` entry.

- [ ] **Step 1: Write the failing tests**

Append to `science/model/tests/test_origins.py`:

```python
from pathlib import Path

_PKG_TEMPLATES = Path("src/science_model/templates")
_ROOT_TEMPLATES = Path(__file__).resolve().parents[3] / "templates"
_ORIGIN_KINDS = ["hypothesis", "question", "topic", "theme"]


@pytest.mark.parametrize("kind", _ORIGIN_KINDS)
def test_template_scaffolds_origins(kind):
    text = (_PKG_TEMPLATES / f"{kind}.md").read_text(encoding="utf-8")
    assert "origins: []" in text
    assert "origins: { from: origins }" in text


@pytest.mark.parametrize("kind", _ORIGIN_KINDS)
def test_template_dirs_mirrored(kind):
    pkg = (_PKG_TEMPLATES / f"{kind}.md").read_text(encoding="utf-8")
    root = (_ROOT_TEMPLATES / f"{kind}.md").read_text(encoding="utf-8")
    assert pkg == root, f"{kind}.md drifted between packaged and root template dirs"
```

**Note to implementer:** run these from `science/model/` (cwd), so `_PKG_TEMPLATES` is relative to `science/model/`. Verify `_ROOT_TEMPLATES` resolves to `<repo>/templates` — adjust `parents[N]` if the depth differs. If the two dirs are *already* not byte-identical for these kinds pre-change, reconcile them as part of this task (they must be mirrored after).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science/model && uv run --frozen pytest tests/test_origins.py -k template -v`
Expected: FAIL — `origins: []` not present.

- [ ] **Step 3: Add `origins` to `VALID_FIELD_NAMES`**

In `templates.py`, inside the `VALID_FIELD_NAMES` frozenset literal, add:

```python
        "origins",
```

- [ ] **Step 4: Edit all eight template files identically**

In each of the eight files, in the YAML frontmatter block, add after the `source_refs: []` line:

```yaml
origins: []
```

and in the `_template.frontmatter:` mapping block, add after the `source_refs: { from: source_refs }` line:

```yaml
    origins: { from: origins }
```

Also add an explanatory comment above the `origins: []` line (keep both dirs identical):

```yaml
# origins: known originators (user | assistant | literature). Provenance only;
# does not affect belief. literature ref must be paper:<key> or cite:<key>.
origins: []
```

- [ ] **Step 5: Verify dirs are byte-identical**

Run: `for k in hypothesis question topic theme; do diff science/model/src/science_model/templates/$k.md templates/$k.md && echo "$k OK"; done`
Expected: `hypothesis OK` … `theme OK` (no diff output).

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd science/model && uv run --frozen pytest tests/test_origins.py -k template -v`
Expected: PASS (8 tests).

- [ ] **Step 7: Commit**

```bash
git add science/model/src/science_model/templates.py \
        science/model/src/science_model/templates/hypothesis.md \
        science/model/src/science_model/templates/question.md \
        science/model/src/science_model/templates/topic.md \
        science/model/src/science_model/templates/theme.md \
        templates/hypothesis.md templates/question.md templates/topic.md templates/theme.md \
        science/model/tests/test_origins.py
git commit -m "feat(model): scaffold origins in hypothesis/question/topic/theme templates"
```

---

## Task 4: JSON-schema declaration for topic + theme mixins

**Files:**
- Modify: `science/model/src/science_model/schemas/mixin-topic-2.0.json`
- Modify: `science/model/src/science_model/schemas/mixin-theme-2.0.json`
- Test: `science/model/tests/test_origins.py` (append)

**Interfaces:**
- Consumes: `EntityValidator().validate(entity_dict)` composes `allOf: [base, mixin]`.
- Produces: topic/theme entities carrying `origins`/`added_by` pass schema validation.

Hypothesis/question have **no mixin** — they are not validated by `EntityValidator`, so they get no schema edit here.

- [ ] **Step 1: Write the failing test**

Append to `science/model/tests/test_origins.py`:

```python
from science_model.entity_schema.validator import EntityValidator


def _topic(**extra):
    base = {
        "id": "topic:immune-set-point",
        "type": "topic",
        "schema_profile": "science-entity-base-1.0+mixin-topic-2.0",
        "title": "T",
        "status": "active",
        "created": "2026-05-10",
        "updated": "2026-05-10",
        "source_refs": [],
        "related": [],
    }
    base.update(extra)
    return base


def test_topic_schema_accepts_origins():
    EntityValidator().validate(_topic(
        origins=[{"type": "literature", "ref": "paper:smith2019"}],
        added_by="user",
    ))
```

**Note to implementer:** confirm the exact `schema_profile` string form the loader expects (search existing topic fixtures / `entity_schema/profile.py`). Use that exact form in the test.

- [ ] **Step 2: Run test to verify it fails or passes-permissively**

Run: `cd science/model && uv run --frozen pytest tests/test_origins.py::test_topic_schema_accepts_origins -v`
Expected: If the mixin sets `additionalProperties: false`, FAIL (`Additional properties are not allowed ('origins'…)`). If not, it passes trivially — still add the declaration in Step 3 so the shape is enforced.

- [ ] **Step 3: Declare `origins`/`added_by` in both mixins**

In `mixin-topic-2.0.json` and `mixin-theme-2.0.json`, inside `"properties": { … }`, add after the `"source_refs"` entry:

```json
    "origins": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["type"],
        "properties": {
          "type": {"enum": ["user", "assistant", "literature"]},
          "ref": {"type": "string"},
          "date": {"type": "string", "format": "date"},
          "independent": {"type": "boolean"},
          "note": {"type": "string"}
        }
      },
      "science:merge": "append"
    },
    "added_by": {"type": "string", "science:merge": "project_only"},
```

(Watch trailing commas — `origins`/`added_by` must not be the last property unless you drop the trailing comma. Keep valid JSON.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science/model && uv run --frozen pytest tests/test_origins.py -k schema -v`
Expected: PASS.

- [ ] **Step 5: Run the schema regression suites**

Run: `cd science/model && uv run --frozen pytest tests/test_entity_schema_overlay.py tests/test_entity_schema_merge.py -v`
Expected: PASS (no version-bump required). If a test asserts an exact property set or a version, bump the mixin per its guidance and update `schema_profile` references — otherwise leave versions unchanged.

- [ ] **Step 6: Commit**

```bash
git add science/model/src/science_model/schemas/mixin-topic-2.0.json \
        science/model/src/science_model/schemas/mixin-theme-2.0.json \
        science/model/tests/test_origins.py
git commit -m "feat(model): declare origins/added_by in topic+theme mixin schemas"
```

---

## Task 5: Graph materialization (sci:Origin nodes + sci:addedBy)

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py` (in `_add_entity`, after the `source_refs` loop that ends ~line 925; add a URI helper near `_annotation_uri`, ~line 1663)
- Test: `science/tests/test_graph_origins.py` (create)

**Interfaces:**
- Consumes: `entity.origins` (`list[OriginRecord]`), `entity.added_by`; existing `provenance` graph, `entity_uri` (local var in `_add_entity`), `_entity_uri`, `resolver`, `SCI_NS`, `PROJECT_NS`, `PROV`, `RDF`, `XSD`, `Literal`, `quote`.
- Produces graph triples per origin:
  - `<entity> sci:hasOrigin <origin_node>`; `<origin_node> a sci:Origin`; `<origin_node> sci:originKind "<type>"`.
  - user/assistant: `<origin_node> prov:wasAttributedTo sci:agent/<type>`; `sci:agent/<type> a prov:Agent`.
  - literature `paper:<key>`: `<origin_node> prov:wasDerivedFrom <resolved-paper-entity-uri>` (only when resolved).
  - literature `cite:<key>`: `<origin_node> prov:wasDerivedFrom sci:cite/<key>`; `sci:cite/<key> a prov:Entity`.
  - optional `prov:generatedAtTime "<date>"^^xsd:date`; optional `sci:independentOrigination true`.
  - `<entity> sci:addedBy "<added_by>"` when set.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_graph_origins.py`. Use whatever project-materialization fixture the existing graph tests use (search `test_graph_*` for the helper that writes a minimal project and calls `materialize_graph`). Skeleton:

```python
from __future__ import annotations

from rdflib import Graph
from rdflib.namespace import PROV, RDF

# Reuse the repo's materialization helper; adapt import to the real one.
from science_tool.graph.materialize import materialize_graph


def _write_hypothesis(root, origins_yaml: str, added_by: str | None = None):
    d = root / "entities" / "hypotheses"
    d.mkdir(parents=True, exist_ok=True)
    fm = ["---", "id: hypothesis:0001-x", "type: hypothesis", "title: X",
          "origins:", origins_yaml]
    if added_by:
        fm.append(f"added_by: {added_by}")
    fm += ["---", "", "# X", ""]
    (d / "0001-x.md").write_text("\n".join(fm), encoding="utf-8")


def _load_trig(graph_path):
    g = Graph()
    g.parse(graph_path, format="trig")
    return g


def test_user_origin_emits_agent_attribution(minimal_project):  # fixture from existing tests
    _write_hypothesis(minimal_project, "  - {type: user, date: '2026-05-10'}", added_by="user")
    out = materialize_graph(minimal_project)
    g = _load_trig(out)
    SCI = "https://schemas.science/ns#"  # confirm actual SCI_NS string
    origins = list(g.objects(predicate=g.namespace_manager.store  # replace with URIRef(SCI+"hasOrigin")
                             ))
    # Assertions (write with real URIRefs):
    # - some origin node typed sci:Origin
    # - that node prov:wasAttributedTo sci:agent/user
    # - sci:agent/user rdf:type prov:Agent
    # - entity sci:addedBy Literal("user")
    assert any(str(o).endswith("agent/user") for o in g.objects(None, PROV.wasAttributedTo))


def test_literature_cite_origin_emits_bib_node(minimal_project):
    _write_hypothesis(minimal_project, "  - {type: literature, ref: 'cite:Smith2019'}")
    g = _load_trig(materialize_graph(minimal_project))
    assert any(str(o).endswith("cite/Smith2019") for o in g.objects(None, PROV.wasDerivedFrom))
    bib = [s for s in g.subjects(RDF.type, PROV.Entity) if str(s).endswith("cite/Smith2019")]
    assert bib, "cite: origin must materialize a prov:Entity bib node"
```

**Note to implementer:** the exact `SCI_NS` string and the materialize fixture name must be read from the codebase first (`grep -n "SCI_NS =" science/src/science_tool/graph/*.py`; find the fixture in an existing `science/tests/test_graph_*.py`). Rewrite the assertions with real `URIRef`s. Add a third test for `paper:<key>` resolving to a paper-entity URI using an in-project paper fixture, and a fourth asserting `sci:independentOrigination` + `prov:generatedAtTime` appear for a dated independent origin.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_graph_origins.py -v`
Expected: FAIL — no `sci:hasOrigin`/agent/bib triples emitted.

- [ ] **Step 3: Add a bib-URI helper**

In `materialize.py`, near `_annotation_uri` (~line 1663):

```python
def _cite_bib_uri(key: str) -> URIRef:
    """Stable prov:Entity URI for a `cite:<key>` bibliography-only origin."""
    return URIRef(SCI_NS[f"cite/{quote(key.strip(), safe='')}"])
```

- [ ] **Step 4: Emit origins in `_add_entity`**

In `_add_entity`, immediately after the `for raw_target in sorted(entity.source_refs):` loop completes (before the `evidence_refs` loop), add:

```python
    for i, origin in enumerate(entity.origins):
        origin_node = URIRef(PROJECT_NS[f"origin/{quote(entity.canonical_id, safe='')}/{i}"])
        provenance.add((entity_uri, SCI_NS.hasOrigin, origin_node))
        provenance.add((origin_node, RDF.type, SCI_NS.Origin))
        provenance.add((origin_node, SCI_NS.originKind, Literal(origin.type.value)))
        if origin.date:
            provenance.add((origin_node, PROV.generatedAtTime, Literal(origin.date, datatype=XSD.date)))
        if origin.independent:
            provenance.add((origin_node, SCI_NS.independentOrigination, Literal(True)))
        if origin.type.value in ("user", "assistant"):
            agent_uri = URIRef(SCI_NS[f"agent/{origin.type.value}"])
            provenance.add((origin_node, PROV.wasAttributedTo, agent_uri))
            provenance.add((agent_uri, RDF.type, PROV.Agent))
        elif origin.type.value == "literature" and origin.ref:
            if origin.ref.startswith("cite:"):
                bib_uri = _cite_bib_uri(origin.ref.removeprefix("cite:"))
                provenance.add((origin_node, PROV.wasDerivedFrom, bib_uri))
                provenance.add((bib_uri, RDF.type, PROV.Entity))
            else:  # paper:<key>
                resolution = resolver.resolve(origin.ref, allow_cross_kind_fallback=True)
                if resolution.status == "resolved" and resolution.canonical_id is not None:
                    provenance.add((origin_node, PROV.wasDerivedFrom, _entity_uri(resolution.canonical_id)))
                # unresolved paper: ref → no edge; Task 6 health flags it.
    if entity.added_by:
        provenance.add((entity_uri, SCI_NS.addedBy, Literal(entity.added_by)))
```

**Note to implementer:** confirm `entity_uri`, `provenance`, `resolver`, `SCI_NS`, `PROJECT_NS`, `quote`, `XSD` are all in scope at that point in `_add_entity` (they are used by the surrounding code). `quote` is imported from `urllib.parse` at the top of the file.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_graph_origins.py -v`
Expected: PASS.

- [ ] **Step 6: Confirm `sci` prefix serialization**

The serializer already binds the `sci` prefix (`io.py` `_SERIALIZER_PREFIXES`), so `sci:hasOrigin`/`sci:Origin`/`sci:agent/*`/`sci:cite/*`/`sci:addedBy` need no new registration. Verify by inspecting the emitted `graph.trig`:

Run: `cd science && uv run --frozen pytest tests/test_graph_origins.py -v && echo OK`
Expected: PASS. (If any new prefix were needed it would surface as a full-URI serialization, not a failure — spot-check the trig once.)

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/graph/materialize.py science/tests/test_graph_origins.py
git commit -m "feat(graph): materialize origins as sci:Origin PROV-O nodes + sci:addedBy"
```

---

## Task 6: Health checks for origin refs

**Files:**
- Modify: `science/src/science_tool/graph/health.py`
- Test: `science/tests/test_health_origins.py` (create)

**Interfaces:**
- Consumes: `bibliography.load_bib_keys(project_root)` → `set[str]` (valid BibTeX keys from `papers/references.bib`); the entity resolver / entity index used by existing `source_refs` reference checks; `entity.origins`.
- Produces: health findings, at the **same severity** as an unresolved `source_refs` entry, for:
  - a `paper:<key>` origin ref that does not resolve to a known entity;
  - a `cite:<key>` origin ref whose key is absent from `papers/references.bib`;
  - (soft warn) `independent: true` on an entity with exactly one origin.

- [ ] **Step 1: Read the existing pattern**

Read the `source_refs` unresolved-reference check in `health.py` (near `_IDENTITY_REFERENCE_FIELDS` / `_BIBLIOGRAPHY_REFERENCE_FIELDS`, ~lines 1090–1100 and the function that consumes them). Note the exact Finding/severity constructor and how findings are collected — the new check mirrors that severity. `origins` is a list of **objects**, so it needs its own iteration (it cannot be added to the string-ref tuples).

- [ ] **Step 2: Write the failing test**

Create `science/tests/test_health_origins.py`. Reuse the health-run fixture from existing `science/tests/test_health*.py`. Skeleton (adapt to the real health entry point + finding shape):

```python
from __future__ import annotations

# Adapt these imports to the real health API used by existing health tests.
from science_tool.graph.health import run_health_checks  # confirm actual name


def test_unknown_cite_key_flagged(health_project):
    # health_project: a fixture project with an empty papers/references.bib
    _add_hypothesis_with_origin(health_project, "  - {type: literature, ref: 'cite:Missing2020'}")
    findings = run_health_checks(health_project)
    assert any("Missing2020" in f.message for f in findings)


def test_known_cite_key_not_flagged(health_project):
    (health_project / "papers").mkdir(exist_ok=True)
    (health_project / "papers" / "references.bib").write_text(
        "@article{Good2021, title={t}}\n", encoding="utf-8")
    _add_hypothesis_with_origin(health_project, "  - {type: literature, ref: 'cite:Good2021'}")
    findings = run_health_checks(health_project)
    assert not any("Good2021" in f.message for f in findings)


def test_independent_lone_origin_soft_warns(health_project):
    _add_hypothesis_with_origin(health_project, "  - {type: user, independent: true}")
    findings = run_health_checks(health_project)
    assert any("independent" in f.message.lower() for f in findings)
```

**Note to implementer:** write `_add_hypothesis_with_origin` and `health_project` by copying the nearest existing health test's fixture/helpers. Confirm `run_health_checks`, the `Finding` fields (`message`, severity), and how to assert severity equals the `source_refs`-unresolved severity.

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_health_origins.py -v`
Expected: FAIL — no origin findings produced.

- [ ] **Step 4: Implement the origin health check**

Add a check function in `health.py` mirroring the existing unresolved-`source_refs` finding severity. Pseudocode to make concrete against the real Finding API:

```python
from science_tool.bibliography import load_bib_keys

def _check_origins(entity, *, resolver, entity_index, bib_keys) -> list[Finding]:
    findings: list[Finding] = []
    for origin in entity.origins:
        if origin.type.value == "literature" and origin.ref:
            if origin.ref.startswith("cite:"):
                key = origin.ref.removeprefix("cite:").strip()
                if key not in bib_keys:
                    findings.append(_reference_finding(
                        entity, f"origin cite:{key} not found in papers/references.bib"))
            elif origin.ref.startswith("paper:"):
                res = resolver.resolve(origin.ref, allow_cross_kind_fallback=True)
                if res.status != "resolved" or res.canonical_id not in entity_index:
                    findings.append(_reference_finding(
                        entity, f"origin {origin.ref} does not resolve to a known entity"))
    if len(entity.origins) == 1 and entity.origins[0].independent:
        findings.append(_soft_finding(
            entity, "origin independent:true is only meaningful with 2+ origins"))
    return findings
```

Wire it into the health run loop where per-entity checks are aggregated, compute `bib_keys = load_bib_keys(project_root)` once, and use the **same** `_reference_finding` severity the `source_refs` check uses (`_soft_finding` = a warning-level finding). Replace `_reference_finding`/`_soft_finding`/`Finding` with the real constructors.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_health_origins.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/graph/health.py science/tests/test_health_origins.py
git commit -m "feat(health): flag unresolved paper: / unknown cite: origin refs"
```

---

## Task 7: Write-path wiring — `add-hypothesis` / `add-question`

**Files:**
- Modify: `commands/add-hypothesis.md`
- Modify: `commands/add-question.md`
- (No pytest — these are agent command instructions. Acceptance is a content check.)

**Interfaces:**
- Consumes: `origins`/`added_by` frontmatter fields (Tasks 1–3).
- Produces: new hypotheses/questions authored via these commands carry an `origins` entry and `added_by`.

- [ ] **Step 1: Read the current command flow**

Read `commands/add-hypothesis.md` and find where the entity frontmatter is authored/written.

- [ ] **Step 2: Insert the origin elicitation step**

Add a short step immediately before the entity file is written, in both commands. Exact prose to insert (adjust variable names to the command's style):

```markdown
### Record origin (provenance)

Ask the user where this <hypothesis|question> came from:

- **user** — you (or a collaborator) proposed it. → `origins: [{type: user, date: <today>}]`
- **literature** — it comes from a paper. Ask for a reference. If they give a
  `paper:<key>` reference, store it as-is; if they give a bare BibTeX key,
  normalize it to `cite:<key>`. → `origins: [{type: literature, ref: <normalized>, date: <pub-date-if-known>}]`
- **assistant** — a novel idea you (the AI) reasoned up with no literature source.
  → `origins: [{type: assistant, ref: "llm:<model>:add-<kind>"}]`

More than one may apply (e.g. user-proposed but predated in the literature) — add
one record per origin, set `independent: true` on a record that converged
independently, and use `date` to establish priority.

Set `added_by: user` (this command is user-driven). Origins are **provenance
only** and never change how the entity's evidence is weighed.
```

- [ ] **Step 3: Acceptance check**

Run: `grep -l "Record origin (provenance)" commands/add-hypothesis.md commands/add-question.md`
Expected: both files listed.

- [ ] **Step 4: Commit**

```bash
git add commands/add-hypothesis.md commands/add-question.md
git commit -m "feat(commands): elicit + normalize origin in add-hypothesis/add-question"
```

---

## Task 8: Write-path wiring — topic authoring (research-topic)

**Files:**
- Modify: `commands/research-topic.md`
- (No pytest — content check.)

**Interfaces:** same as Task 7, for `topic` entities. (Theme authoring has no dedicated creation command; document the field in the theme template comment from Task 3, which is sufficient for v1 — do not invent a new command.)

- [ ] **Step 1: Read `commands/research-topic.md`** and find where the topic entity is written.

- [ ] **Step 2: Insert a minimal origin note**

Add, where the topic frontmatter is authored:

```markdown
When writing the topic entity, set `origins` to reflect where the framing came
from — `{type: literature, ref: paper:<key>}` for each seed review the topic is
built from (bare keys normalized to `cite:<key>`), or `{type: user}` if the user
named the topic. Set `added_by: "llm:<model>:research-topic"`. Provenance only;
does not affect belief.
```

- [ ] **Step 3: Acceptance check**

Run: `grep -c "origins" commands/research-topic.md`
Expected: ≥ 1.

- [ ] **Step 4: Commit**

```bash
git add commands/research-topic.md
git commit -m "feat(commands): record topic origin in research-topic"
```

---

## Task 9: Full validation sweep

**Files:** none (verification only).

- [ ] **Step 1: Model suite**

Run: `cd science/model && uv run --frozen pytest`
Expected: PASS (0 failures), including the new `test_origins.py` and the schema regression tests.

- [ ] **Step 2: Tool suite**

Run: `cd science && uv run --frozen pytest`
Expected: PASS (0 failures), including `test_graph_origins.py` and `test_health_origins.py`.

- [ ] **Step 3: Lint + types**

Run: `cd science && uv run ruff check && uv run pyright`
Expected: clean (no new findings in touched files).

- [ ] **Step 4: End-to-end smoke**

On a scratch project: author a hypothesis with two origins (one `user`, one `cite:<key>` with the key present in `papers/references.bib`) + `added_by`, run `science graph` (materialize) and `science health`. Confirm: `graph.trig` contains the `sci:Origin` nodes and `sci:addedBy`; health is clean; then change the cite key to a missing one and confirm health flags it.

- [ ] **Step 5: Final commit (if any smoke-fix needed)**

```bash
git add -A && git commit -m "test: origin-provenance end-to-end verification"
```

---

## Self-Review (completed during authoring)

- **Spec coverage:** model fields (T1), frontmatter (T2), templates + `VALID_FIELD_NAMES` + both dirs (T3), topic/theme mixins with no version bump (T4), PROV-O materialization incl. `paper:`/`cite:` resolution + agents + `added_by` (T5), health for unresolved `paper:` / unknown `cite:` + lone-`independent` warn (T6), `add-*`/research-topic write paths (T7–T8), migration = none (optional fields), non-goals untouched (no belief code). All spec sections map to a task.
- **Placeholder scan:** implementation code is concrete; the three "Note to implementer" callouts (exact parse-fn name, `SCI_NS` string + materialize fixture, real Finding constructor) are *lookup* instructions with the exact search commands, not deferred logic — each task's test defines behavior precisely.
- **Type consistency:** `OriginType`/`OriginRecord` field names (`type`/`ref`/`date`/`independent`/`note`) are identical across model, frontmatter, schema JSON, materialize, and health. `origins`/`added_by` names consistent throughout. Predicate local-names (`hasOrigin`, `Origin`, `originKind`, `independentOrigination`, `addedBy`, `agent/<type>`, `cite/<key>`) consistent between T5 and the spec.
