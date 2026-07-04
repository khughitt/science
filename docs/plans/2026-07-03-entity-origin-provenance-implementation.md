# Entity Origin Provenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `origins` (known-originator claims) + `added_by` (discovery stamp) provenance model to hypothesis/question/topic/theme entities, materialized into the graph as minimal PROV-O, without affecting evidential weight.

**Architecture:** Two optional fields on the base Pydantic `Entity` (so all kinds parse/validate/materialize them uniformly); JSON-schema declaration for the mixin'd kinds (topic/theme); template scaffolding + `VALID_FIELD_NAMES` for the three template-ready kinds (hypothesis/question/theme) and a plain frontmatter line for the mustache topic template; a `sci:Origin` reified node per origin in the `provenance` named graph; health checks for unresolved `paper:` / unknown `cite:` origin refs; `--origin`/`--added-by` CLI flags on entity creation (fed through the existing `extra_frontmatter` seam); command-doc + regenerated codex-skills mirrors.

**Tech Stack:** Python 3.12, Pydantic v2, rdflib, jsonschema (Draft 2020-12), Click, pytest, uv.

## Global Constraints

- **Design spec:** `docs/plans/2026-07-03-entity-origin-provenance.md` (this plan implements it verbatim).
- **Provenance is metadata only; it MUST NOT affect evidential weight.** No belief/scoring code changes.
- **Two packages, run tests from the package dir** (never repo root): model `cd science/model && uv run --frozen pytest`; tool `cd science && uv run --frozen pytest`. Lint/types from `science/`: `uv run ruff check`, `uv run pyright`.
- **No AI-attribution trailers** on commits.
- **Field is `origins` (plural, list).** A scalar `origin: str | None` already exists on `Entity` (dataset external/derived) — do **not** touch or conflate it.
- **Literature `ref` accepts only `paper:<key>` or `cite:<key>`.** Bare/other prefixes rejected at the model layer; the CLI normalizes a bare BibTeX key to `cite:<key>`.
- **No JSON-schema version bumps** — additions are optional/additive; confirm via schema tests.
- **`kind` and `type` must both be set and agree** — `Entity._validate_kind_type_consistency` raises `"kind/type mismatch"`; test fixtures constructing entities directly MUST pass `type=`.
- **Template-ready mapping kinds are `hypothesis`, `question`, `theme`** (they carry a `_template.frontmatter` block and render through `Renderer`). **`topic` is NOT template-ready** — its file is `background-topic.md`, a `{{mustache}}` template with no mapping block; it gets a plain `origins: []` line only.
- Work happens in worktree `.worktrees/entity-origin-provenance`, branch `entity-origin-provenance`. Paths below are repo-relative to that worktree root.

---

## File Structure

- `science/model/src/science_model/entities.py` — new `OriginType`, `OriginRecord`; new `origins`/`added_by` on `Entity`.
- `science/model/src/science_model/frontmatter.py` — parse `origins`/`added_by`.
- `science/model/src/science_model/templates.py` — add `origins` to `VALID_FIELD_NAMES`.
- `science/model/src/science_model/templates/{hypothesis,question,theme}.md` + `templates/{hypothesis,question,theme}.md` — `origins: []` + `{ from: origins, default: [] }` mapping (both dirs, mirrored).
- `science/model/src/science_model/templates/background-topic.md` + `templates/background-topic.md` — plain `origins: []` line (both dirs, mirrored).
- `science/model/src/science_model/schemas/mixin-topic-2.0.json`, `mixin-theme-2.0.json` — declare `origins`/`added_by` (strict).
- `science/src/science_tool/graph/materialize.py` — emit `sci:Origin` nodes + `sci:addedBy`.
- `science/src/science_tool/graph/health.py` — origin-ref health checks.
- `science/src/science_tool/entities.py` — `parse_origin_spec` helper; thread `origins`/`added_by` into creation via `extra_frontmatter`.
- `science/src/science_tool/cli.py` — `--origin`/`--added-by` options on the hypothesis/question create commands.
- `commands/add-hypothesis.md`, `commands/add-question.md`, `commands/research-topic.md` — origin authoring guidance.
- `codex-skills/science-add-hypothesis/SKILL.md`, `science-research-topic/SKILL.md` (+ any others) — regenerated mirrors.
- Tests: `science/model/tests/test_origins.py`, `science/tests/test_graph_origins.py`, `science/tests/test_health_origins.py`, `science/tests/test_origin_cli.py`.

---

## Task 1: OriginType + OriginRecord model and Entity fields

**Files:**
- Modify: `science/model/src/science_model/entities.py` (add classes before `class Entity` at line 227; add fields inside `Entity` after `evidence_refs` at line 247)
- Test: `science/model/tests/test_origins.py` (create)

**Interfaces:**
- Produces: `OriginType(StrEnum)` (`USER`/`ASSISTANT`/`LITERATURE`); `OriginRecord(BaseModel)` fields `type: OriginType`, `ref: str|None`, `date: str|None`, `independent: bool=False`, `note: str|None`, `extra="forbid"`; `Entity.origins: list[OriginRecord]`, `Entity.added_by: str|None`.

- [ ] **Step 1: Write the failing tests**

Create `science/model/tests/test_origins.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_model.entities import OriginRecord, OriginType, ProjectEntity


def test_user_origin_minimal():
    rec = OriginRecord(type="user")
    assert rec.type is OriginType.USER
    assert rec.ref is None and rec.independent is False


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
        OriginRecord.model_validate("smith2019")
    with pytest.raises(ValidationError):
        OriginRecord(type="user", bogus=1)


def test_entity_carries_origins_and_added_by():
    ent = ProjectEntity(
        id="hypothesis:0001-x",
        kind="hypothesis",
        type="hypothesis",  # REQUIRED: _validate_kind_type_consistency
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

In `entities.py`, ensure imports include `re` and `ConfigDict`:

```python
import re
from pydantic import BaseModel, ConfigDict, Field, model_validator
```

Add **before** `class Entity(BaseModel):` (line 227):

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
    independent: bool = False  # THIS record converged independently of the others
    note: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> "OriginRecord":
        if self.type is OriginType.LITERATURE:
            if not self.ref:
                raise ValueError("literature origin requires a ref")
            if not (self.ref.startswith("paper:") or self.ref.startswith("cite:")):
                raise ValueError("literature origin ref must be 'paper:<key>' or 'cite:<key>'")
        if self.date is not None and not _ORIGIN_DATE_RE.match(self.date):
            raise ValueError("origin date must be YYYY-MM-DD")
        return self
```

Add inside `class Entity`, after the `evidence_refs` field (line 247):

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
- Modify: `science/model/src/science_model/frontmatter.py` (the `entity_kwargs` dict, ~lines 375–410, right after the `"source_refs":` line)
- Test: `science/model/tests/test_origins.py` (append)

**Interfaces:**
- Consumes: `Entity.origins`/`added_by` (Task 1); Pydantic coerces list-of-dict → `list[OriginRecord]`.

- [ ] **Step 1: Write the failing test**

Append to `science/model/tests/test_origins.py`:

```python
def test_frontmatter_parses_origins(tmp_path):
    from science_model.frontmatter import parse_entity_file  # confirm real entry-point name

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
    assert ent is not None and ent.added_by == "user"
    assert [o.type.value for o in ent.origins] == ["user", "literature"]
    assert ent.origins[1].ref == "paper:smith2019"
```

**Note to implementer:** confirm the parse entry-point name in `frontmatter.py` (search for the function building `entity_kwargs`). Use the actual name.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_origins.py::test_frontmatter_parses_origins -v`
Expected: FAIL — `origins` empty / `added_by` None.

- [ ] **Step 3: Add the two keys to `entity_kwargs`**

In `frontmatter.py`, after `"source_refs": fm.get("source_refs") or [],`:

```python
        "origins": fm.get("origins") or [],
        "added_by": fm.get("added_by"),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science/model && uv run --frozen pytest tests/test_origins.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/frontmatter.py science/model/tests/test_origins.py
git commit -m "feat(model): parse origins/added_by from entity frontmatter"
```

---

## Task 3: Renderer allowlist + template scaffolding (both dirs)

**Files:**
- Modify: `science/model/src/science_model/templates.py` (`VALID_FIELD_NAMES`, ~line 18)
- Modify (mapping kinds): `science/model/src/science_model/templates/{hypothesis,question,theme}.md` + `templates/{hypothesis,question,theme}.md`
- Modify (mustache topic): `science/model/src/science_model/templates/background-topic.md` + `templates/background-topic.md`
- Test: `science/model/tests/test_origins.py` (append)

**Interfaces:**
- Consumes: `VALID_FIELD_NAMES` gates `_template.frontmatter` `{ from: <field> }` targets; `Renderer.render(kind, fields=...)` honors `default:` when the field is absent from `fields` (proven by the existing `phase: { from: phase, default: "active" }`).
- Produces: rendered hypothesis/question/theme frontmatter contains `origins: []` even when no `origins` value is passed; `background-topic.md` frontmatter contains `origins: []`.

Only `origins` is scaffolded/rendered. `added_by` is set by the CLI (Task 7), not scaffolded, so it needs no `VALID_FIELD_NAMES` entry.

- [ ] **Step 1: Write the failing tests**

Append to `science/model/tests/test_origins.py`:

```python
from pathlib import Path
from science_model.templates import Renderer

_PKG_TEMPLATES = Path("src/science_model/templates")
_ROOT_TEMPLATES = Path(__file__).resolve().parents[3] / "templates"
_MAPPING_KINDS = ["hypothesis", "question", "theme"]
_ALL_KINDS = _MAPPING_KINDS + ["background-topic"]


@pytest.mark.parametrize("kind", _MAPPING_KINDS)
def test_mapping_template_scaffolds_origins(kind):
    text = (_PKG_TEMPLATES / f"{kind}.md").read_text(encoding="utf-8")
    assert "origins: []" in text
    assert "origins: { from: origins, default: [] }" in text


def test_topic_template_scaffolds_origins():
    text = (_PKG_TEMPLATES / "background-topic.md").read_text(encoding="utf-8")
    assert "origins: []" in text  # plain line; topic has no _template mapping


@pytest.mark.parametrize("kind", _ALL_KINDS)
def test_template_dirs_mirrored(kind):
    pkg = (_PKG_TEMPLATES / f"{kind}.md").read_text(encoding="utf-8")
    root = (_ROOT_TEMPLATES / f"{kind}.md").read_text(encoding="utf-8")
    assert pkg == root, f"{kind}.md drifted between packaged and root template dirs"


@pytest.mark.parametrize("kind", _MAPPING_KINDS)
def test_render_defaults_origins_to_empty_list(kind):
    # No `origins` passed → must render `origins: []`, NOT `origins: null`.
    out = Renderer(template_root=_PKG_TEMPLATES).render(
        kind, fields={"title": "X", "slug": "x", "nn": "01"})
    assert "origins: []" in out
    assert "origins: null" not in out
```

**Note to implementer:** run from `science/model/` (so `_PKG_TEMPLATES` is relative to it) and verify `_ROOT_TEMPLATES`/`parents[3]` resolves to `<repo>/templates` — adjust depth if needed. Confirm `Renderer(template_root=...)` and `.render(kind, fields=...)` signatures against Task 3's earlier read of `templates.py` (they match lines 97/103). If the two template dirs already differ for a target file before your change, reconcile them (they must be byte-identical after).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science/model && uv run --frozen pytest tests/test_origins.py -k "template or render" -v`
Expected: FAIL — `origins` not present.

- [ ] **Step 3: Add `origins` to `VALID_FIELD_NAMES`**

In `templates.py`, inside the `VALID_FIELD_NAMES` frozenset literal, add `"origins",`.

- [ ] **Step 4: Edit the three mapping templates (both dirs, identical)**

In each of `hypothesis.md`, `question.md`, `theme.md` (packaged + root = 6 files), add to the YAML frontmatter after `source_refs: []`:

```yaml
# origins: known originators (user | assistant | literature). Provenance only;
# does not affect belief. literature ref must be paper:<key> or cite:<key>.
origins: []
```

and to the `_template.frontmatter:` mapping block after `source_refs: { from: source_refs }`:

```yaml
    origins: { from: origins, default: [] }
```

- [ ] **Step 5: Edit the topic template (both dirs, identical)**

In `background-topic.md` (packaged + root = 2 files), add after `source_refs: []` (there is no `_template` block — plain line only):

```yaml
# origins: known originators (user | assistant | literature). Provenance only.
origins: []
```

- [ ] **Step 6: Verify dirs are byte-identical**

Run: `for k in hypothesis question theme background-topic; do diff science/model/src/science_model/templates/$k.md templates/$k.md && echo "$k OK"; done`
Expected: `hypothesis OK` … `background-topic OK`.

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd science/model && uv run --frozen pytest tests/test_origins.py -k "template or render" -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add science/model/src/science_model/templates.py \
        science/model/src/science_model/templates/hypothesis.md \
        science/model/src/science_model/templates/question.md \
        science/model/src/science_model/templates/theme.md \
        science/model/src/science_model/templates/background-topic.md \
        templates/hypothesis.md templates/question.md templates/theme.md templates/background-topic.md \
        science/model/tests/test_origins.py
git commit -m "feat(model): scaffold origins in hypothesis/question/theme/topic templates"
```

---

## Task 4: JSON-schema declaration for topic + theme mixins (strict)

**Files:**
- Modify: `science/model/src/science_model/schemas/mixin-topic-2.0.json`, `mixin-theme-2.0.json`
- Test: `science/model/tests/test_origins.py` (append)

**Interfaces:**
- Consumes: `EntityValidator().validate(entity_dict)` composes `allOf: [base, mixin]`.
- Produces: topic/theme entities carrying valid `origins`/`added_by` pass; malformed ones (extra keys, literature without a `paper:`/`cite:` ref) fail — matching the Pydantic contract.

Hypothesis/question have **no mixin** → no schema edit here.

- [ ] **Step 1: Write the failing/contract tests**

Append to `science/model/tests/test_origins.py`:

```python
import pytest as _pytest
from science_model.entity_schema.validator import EntityValidator, EntityValidationError


def _topic(**extra):
    base = {
        "id": "topic:immune-set-point",
        "type": "topic",
        "schema_profile": "science-entity-base-1.0+mixin-topic-2.0",  # confirm exact form
        "title": "T", "status": "active",
        "created": "2026-05-10", "updated": "2026-05-10",
        "source_refs": [], "related": [],
    }
    base.update(extra)
    return base


def test_topic_schema_accepts_valid_origins():
    EntityValidator().validate(_topic(
        origins=[{"type": "literature", "ref": "paper:smith2019"}], added_by="user"))


def test_topic_schema_rejects_literature_without_ref():
    with _pytest.raises(EntityValidationError):
        EntityValidator().validate(_topic(origins=[{"type": "literature"}]))


def test_topic_schema_rejects_unknown_origin_key():
    with _pytest.raises(EntityValidationError):
        EntityValidator().validate(_topic(origins=[{"type": "user", "bogus": 1}]))
```

**Note to implementer:** confirm the exact `schema_profile` string (search existing topic fixtures / `entity_schema/profile.py`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science/model && uv run --frozen pytest tests/test_origins.py -k schema -v`
Expected: FAIL (accept-test fails if additionalProperties:false already, reject-tests fail because the shape isn't declared yet).

- [ ] **Step 3: Declare `origins`/`added_by` (strict) in both mixins**

In `mixin-topic-2.0.json` and `mixin-theme-2.0.json`, inside `"properties"`, after `"source_refs"`:

```json
    "origins": {
      "type": "array",
      "science:merge": "append",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["type"],
        "properties": {
          "type": {"enum": ["user", "assistant", "literature"]},
          "ref": {"type": "string"},
          "date": {"type": "string", "format": "date"},
          "independent": {"type": "boolean"},
          "note": {"type": "string"}
        },
        "allOf": [
          {
            "if": {"properties": {"type": {"const": "literature"}}, "required": ["type"]},
            "then": {"required": ["ref"], "properties": {"ref": {"pattern": "^(paper|cite):"}}}
          }
        ]
      }
    },
    "added_by": {"type": "string", "science:merge": "project_only"},
```

(Keep valid JSON — watch trailing commas relative to the next property.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science/model && uv run --frozen pytest tests/test_origins.py -k schema -v`
Expected: PASS.

- [ ] **Step 5: Schema regression suites**

Run: `cd science/model && uv run --frozen pytest tests/test_entity_schema_overlay.py tests/test_entity_schema_merge.py -v`
Expected: PASS (no version bump). If a test asserts an exact property set / version, follow its guidance to bump + update `schema_profile` refs; otherwise leave versions unchanged.

- [ ] **Step 6: Commit**

```bash
git add science/model/src/science_model/schemas/mixin-topic-2.0.json \
        science/model/src/science_model/schemas/mixin-theme-2.0.json \
        science/model/tests/test_origins.py
git commit -m "feat(model): declare strict origins/added_by in topic+theme mixin schemas"
```

---

## Task 5: Graph materialization (sci:Origin nodes + sci:addedBy)

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py` (in `_add_entity`, after the `source_refs` loop ~line 925; add `_cite_bib_uri` near `_annotation_uri` ~line 1663)
- Test: `science/tests/test_graph_origins.py` (create)

**Interfaces:**
- Consumes: `entity.origins`, `entity.added_by`, `entity.canonical_id`; in-scope `provenance` graph, `entity_uri`, `resolver`, `_entity_uri`, `SCI_NS`, `PROJECT_NS`, `PROV`, `RDF`, `XSD`, `Literal`, `quote` (from `urllib.parse`).
- Produces per origin: `<entity> sci:hasOrigin <node>`; `<node> a sci:Origin`; `<node> sci:originKind "<type>"`; user/assistant → `<node> prov:wasAttributedTo sci:agent/<type>` + `sci:agent/<type> a prov:Agent`; literature `paper:` → `<node> prov:wasDerivedFrom <resolved-entity>` (when resolved); literature `cite:` → `<node> prov:wasDerivedFrom sci:cite/<key>` + `sci:cite/<key> a prov:Entity`; optional `prov:generatedAtTime`, `sci:independentOrigination`; `<entity> sci:addedBy "<added_by>"`.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_graph_origins.py`. Reuse the project-materialization fixture used by existing `science/tests/test_graph_*.py` (search for the helper that writes a minimal project and calls `materialize_graph`). Read the real `SCI_NS`/`PROJECT_NS` strings first: `grep -n "SCI_NS =\|PROJECT_NS =" science/src/science_tool/graph/*.py`. Skeleton:

```python
from __future__ import annotations
from rdflib import Graph, URIRef
from rdflib.namespace import PROV, RDF
from science_tool.graph.materialize import materialize_graph

SCI = "..."   # paste the real SCI_NS string


def _hyp(root, origins_block: str, added_by: str | None = None):
    d = root / "entities" / "hypotheses"; d.mkdir(parents=True, exist_ok=True)
    lines = ["---", "id: hypothesis:0001-x", "type: hypothesis", "title: X", "origins:", origins_block]
    if added_by: lines.append(f"added_by: {added_by}")
    lines += ["---", "", "# X", ""]
    (d / "0001-x.md").write_text("\n".join(lines), encoding="utf-8")


def _g(path):
    g = Graph(); g.parse(path, format="trig"); return g


def test_user_origin_agent_attribution(minimal_project):
    _hyp(minimal_project, "  - {type: user, date: '2026-05-10'}", added_by="user")
    g = _g(materialize_graph(minimal_project))
    assert (None, PROV.wasAttributedTo, URIRef(SCI + "agent/user")) in g
    assert (URIRef(SCI + "agent/user"), RDF.type, PROV.Agent) in g
    assert any(str(o) == "user" for o in g.objects(None, URIRef(SCI + "originKind")))
    assert any(str(o) == "user" for o in g.objects(None, URIRef(SCI + "addedBy")))


def test_cite_origin_bib_node(minimal_project):
    _hyp(minimal_project, "  - {type: literature, ref: 'cite:Smith2019'}")
    g = _g(materialize_graph(minimal_project))
    assert (None, PROV.wasDerivedFrom, URIRef(SCI + "cite/Smith2019")) in g
    assert (URIRef(SCI + "cite/Smith2019"), RDF.type, PROV.Entity) in g


def test_independent_and_date_emitted(minimal_project):
    _hyp(minimal_project, "  - {type: user, date: '2019-03-01', independent: true}")
    g = _g(materialize_graph(minimal_project))
    assert any(str(o).startswith("2019-03-01") for o in g.objects(None, PROV.generatedAtTime))
    assert (None, URIRef(SCI + "independentOrigination"), None) in g
```

**Note to implementer:** add a fourth test for `paper:<key>` resolving to a paper-entity URI using an in-project paper fixture. Adapt `minimal_project` to the real fixture name.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_graph_origins.py -v`
Expected: FAIL — no origin triples.

- [ ] **Step 3: Add the bib-URI helper**

In `materialize.py`, near `_annotation_uri`:

```python
def _cite_bib_uri(key: str) -> URIRef:
    """Stable prov:Entity URI for a `cite:<key>` bibliography-only origin."""
    return URIRef(SCI_NS[f"cite/{quote(key.strip(), safe='')}"])
```

- [ ] **Step 4: Emit origins in `_add_entity`**

After the `for raw_target in sorted(entity.source_refs):` loop (before the `evidence_refs` loop):

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

**Note to implementer:** confirm `entity_uri`, `provenance`, `resolver`, `SCI_NS`, `PROJECT_NS`, `quote`, `XSD` are in scope at that point (the surrounding `source_refs`/`same_as` code uses them).

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_graph_origins.py -v`
Expected: PASS. The `sci` prefix is already bound in `io.py` `_SERIALIZER_PREFIXES`, so no new prefix registration is needed — spot-check the emitted `graph.trig` shows `sci:hasOrigin` (not a full URI) once.

- [ ] **Step 6: Commit**

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
- Consumes: `bibliography.load_bib_keys(project_root)` → `set[str]`; the resolver/entity index used by the existing `source_refs` reference check; `entity.origins`.
- Produces: findings at the **same severity** as an unresolved `source_refs` entry for (a) a `paper:<key>` origin that does not resolve, (b) a `cite:<key>` origin whose key is absent from `papers/references.bib`; plus a **soft warn** for `independent: true` on a lone origin.

- [ ] **Step 1: Read the existing pattern**

Read the `source_refs` unresolved-reference check in `health.py` (near `_IDENTITY_REFERENCE_FIELDS`/`_BIBLIOGRAPHY_REFERENCE_FIELDS`, ~lines 1090–1100 and its consuming function). Note the exact Finding constructor + severity. `origins` is a list of **objects**, so it needs bespoke iteration (cannot join the string-ref tuples).

- [ ] **Step 2: Write the failing test**

Create `science/tests/test_health_origins.py`, reusing the health-run fixture from existing `science/tests/test_health*.py`. Adapt the entry-point + finding shape:

```python
from __future__ import annotations
from science_tool.graph.health import run_health_checks  # confirm real name


def test_unknown_cite_key_flagged(health_project):
    _add_hyp(health_project, "  - {type: literature, ref: 'cite:Missing2020'}")
    assert any("Missing2020" in f.message for f in run_health_checks(health_project))


def test_known_cite_key_not_flagged(health_project):
    (health_project / "papers").mkdir(exist_ok=True)
    (health_project / "papers" / "references.bib").write_text("@article{Good2021, title={t}}\n", encoding="utf-8")
    _add_hyp(health_project, "  - {type: literature, ref: 'cite:Good2021'}")
    assert not any("Good2021" in f.message for f in run_health_checks(health_project))


def test_independent_lone_origin_soft_warns(health_project):
    _add_hyp(health_project, "  - {type: user, independent: true}")
    assert any("independent" in f.message.lower() for f in run_health_checks(health_project))
```

**Note to implementer:** write `_add_hyp`/`health_project` by copying the nearest existing health test's helpers; confirm `run_health_checks`, the `Finding` fields, and that the severity matches the `source_refs`-unresolved severity.

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_health_origins.py -v`
Expected: FAIL — no origin findings.

- [ ] **Step 4: Implement the origin health check**

Add a per-entity check mirroring the unresolved-`source_refs` finding severity; compute `bib_keys = load_bib_keys(project_root)` once. Concretize against the real Finding API:

```python
from science_tool.bibliography import load_bib_keys

def _check_origins(entity, *, resolver, entity_index, bib_keys):
    out = []
    for origin in entity.origins:
        if origin.type.value == "literature" and origin.ref:
            if origin.ref.startswith("cite:"):
                key = origin.ref.removeprefix("cite:").strip()
                if key not in bib_keys:
                    out.append(_reference_finding(entity, f"origin cite:{key} not in papers/references.bib"))
            elif origin.ref.startswith("paper:"):
                res = resolver.resolve(origin.ref, allow_cross_kind_fallback=True)
                if res.status != "resolved" or res.canonical_id not in entity_index:
                    out.append(_reference_finding(entity, f"origin {origin.ref} does not resolve"))
    if len(entity.origins) == 1 and entity.origins[0].independent:
        out.append(_soft_finding(entity, "origin independent:true is only meaningful with 2+ origins"))
    return out
```

Wire it into the health run loop, reusing the **same** `_reference_finding` severity as `source_refs`. Replace `_reference_finding`/`_soft_finding`/`Finding` with the real constructors.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_health_origins.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/graph/health.py science/tests/test_health_origins.py
git commit -m "feat(health): flag unresolved paper: / unknown cite: origin refs"
```

---

## Task 7: CLI — `--origin` / `--added-by` on entity creation

**Files:**
- Modify: `science/src/science_tool/entities.py` (add `parse_origin_spec`; thread `origins`/`added_by` into `create_entity` via the existing `extra_frontmatter` seam)
- Modify: `science/src/science_tool/cli.py` (the `hypotheses create` and `questions create` commands)
- Test: `science/tests/test_origin_cli.py` (create)

**Interfaces:**
- Consumes: `OriginRecord` (validation/normalization), `create_entity(..., extra_frontmatter=...)` (existing, line 768) → `build_entity_markdown(..., extra_frontmatter=...)`.
- Produces: `science hypotheses create "T" --origin user --origin literature:smith2019@2019-03-01 --added-by user` writes an entity whose frontmatter has the corresponding `origins` list + `added_by`.
- Compact `--origin` grammar: `TYPE[:REF][@DATE]`. Split off `@DATE` first, then split `TYPE:REF` on the first `:` (so `literature:paper:smith2019` → ref `paper:smith2019`). A bare literature ref is normalized to `cite:<ref>`.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_origin_cli.py`:

```python
from __future__ import annotations
import pytest
from science_tool.entities import parse_origin_spec


def test_parse_user():
    assert parse_origin_spec("user") == {"type": "user"}


def test_parse_user_with_date():
    assert parse_origin_spec("user@2026-05-10") == {"type": "user", "date": "2026-05-10"}


def test_parse_literature_prefixed_ref():
    assert parse_origin_spec("literature:paper:smith2019@2019-03-01") == {
        "type": "literature", "ref": "paper:smith2019", "date": "2019-03-01"}


def test_parse_literature_bare_key_normalized_to_cite():
    assert parse_origin_spec("literature:Smith2019") == {"type": "literature", "ref": "cite:Smith2019"}


def test_parse_rejects_literature_without_ref():
    # Strictness: literature with no ref must raise here, BEFORE any file write.
    with pytest.raises(Exception):
        parse_origin_spec("literature")
```

Add CLI end-to-end tests using the project's Click runner (copy the invocation pattern + scratch-project fixture from an existing `science/tests/` CLI test that exercises `hypotheses create`):

```python
def test_create_writes_origins(cli_runner, scratch_project):
    result = cli_runner.invoke(app, [
        "hypotheses", "create", "Test H",
        "--origin", "user@2026-05-10",
        "--origin", "literature:Smith2019",
        "--added-by", "user",
    ])  # adapt `app`/args to the real CLI entrypoint
    assert result.exit_code == 0, result.output
    created = next((scratch_project / "entities" / "hypotheses").glob("*.md"))
    text = created.read_text(encoding="utf-8")
    assert "added_by: user" in text
    assert "type: user" in text and "ref: cite:Smith2019" in text


def test_create_rejects_malformed_literature_origin(cli_runner, scratch_project):
    # A malformed literature origin (no ref) must fail the command with a clean
    # nonzero exit and write NO entity file.
    result = cli_runner.invoke(app, ["hypotheses", "create", "Bad", "--origin", "literature"])
    assert result.exit_code != 0
    assert not list((scratch_project / "entities" / "hypotheses").glob("*.md"))
```

**Note to implementer:** find the real CLI app object + `hypotheses create` invocation + scratch-project fixture in an existing `science/tests/test_*cli*.py` and mirror them.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_origin_cli.py -v`
Expected: FAIL — `parse_origin_spec` missing; CLI lacks `--origin`.

- [ ] **Step 3: Add `parse_origin_spec` to `entities.py`**

```python
from science_model.entities import OriginRecord  # top of file

def parse_origin_spec(spec: str) -> dict:
    """Parse a compact `TYPE[:REF][@DATE]` origin spec into a validated dict."""
    date = None
    if "@" in spec:
        spec, date = spec.rsplit("@", 1)
    if ":" in spec:
        type_, ref = spec.split(":", 1)
    else:
        type_, ref = spec, None
    if type_ == "literature" and ref and not ref.startswith(("paper:", "cite:")):
        ref = f"cite:{ref}"
    record = {"type": type_}
    if ref:
        record["ref"] = ref
    if date:
        record["date"] = date
    OriginRecord.model_validate(record)  # validate/normalize; raises on bad input
    return record
```

- [ ] **Step 4: Add CLI options + thread into creation**

On the `hypotheses create` and `questions create` Click commands in `cli.py`, add:

```python
@click.option("--origin", "origins", multiple=True,
              help="Origin as TYPE[:REF][@DATE], e.g. user, literature:Smith2019@2019-03-01. Repeatable.")
@click.option("--added-by", "added_by", default=None, help="Discovery stamp (who surfaced this entity).")
```

In each command body, build extra frontmatter and pass it through (merging with any existing `extra_frontmatter`):

```python
    extra = dict(extra_frontmatter or {})
    if origins:
        extra["origins"] = [parse_origin_spec(s) for s in origins]
    if added_by:
        extra["added_by"] = added_by
    # ... pass extra as create_entity(..., extra_frontmatter=extra)
```

Wrap `parse_origin_spec` so a malformed spec fails **cleanly before any write** — catch its `ValidationError` and re-raise as `click.BadParameter` (or the repo's `EntityCommandError`), so `test_create_rejects_malformed_literature_origin` sees a nonzero exit and no file:

```python
    from pydantic import ValidationError
    try:
        parsed = [parse_origin_spec(s) for s in origins]
    except ValidationError as exc:
        raise click.BadParameter(f"invalid --origin: {exc}") from exc
```

**Note to implementer:** confirm how these two commands currently call `create_entity` and that `extra_frontmatter` **overrides** the template's `origins: []` (write the CLI e2e test first — Step 1 — to prove it). If `build_entity_markdown` merges rather than overrides list fields, adjust the merge so an explicit `--origin` wins.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_origin_cli.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/entities.py science/src/science_tool/cli.py science/tests/test_origin_cli.py
git commit -m "feat(cli): --origin/--added-by on hypothesis/question create"
```

---

## Task 8: Command docs + codex mirrors — add-hypothesis / add-question

**Files:**
- Modify: `commands/add-hypothesis.md`, `commands/add-question.md`
- Regenerate + commit: `codex-skills/**` (via `scripts/generate_codex_skills.py`)

**Interfaces:** Consumes the `--origin`/`--added-by` flags (Task 7).

- [ ] **Step 1: Update both command docs**

In `commands/add-hypothesis.md` and `commands/add-question.md`, at the `science hypotheses create` / `science questions create` invocation, document origin capture (replacing any "only edit the body / don't touch frontmatter" implication for these fields):

```markdown
Capture provenance at creation with `--origin` (repeatable) and `--added-by`:

- **user** — you/a collaborator proposed it: `--origin user@<today>`
- **literature** — from a paper: `--origin literature:paper:<key>@<pubdate>` (a bare
  BibTeX key is normalized to `cite:<key>`)
- **assistant** — a novel idea the AI reasoned up with no literature source:
  `--origin assistant`

More than one may apply (e.g. user-proposed but predated in the literature) — pass
`--origin` multiple times; dates establish priority. Set `--added-by user` (this
command is user-driven). Origins are **provenance only** and never change how the
entity's evidence is weighed. For the rare convergent-independent case, add
`independent: true` to the relevant record by editing the created file's frontmatter.
```

- [ ] **Step 2: Regenerate codex-skills mirrors**

Run: `cd science && uv run python ../scripts/generate_codex_skills.py`  *(confirm the exact invocation the repo uses — check `scripts/generate_codex_skills.py` `__main__` and `science/tests/test_codex_skills.py`).*

- [ ] **Step 3: Verify the sync test passes**

Run: `cd science && uv run --frozen pytest tests/test_codex_skills.py -v`
Expected: PASS (regenerated mirrors match `commands/`).

- [ ] **Step 4: Commit**

```bash
git add commands/add-hypothesis.md commands/add-question.md codex-skills
git commit -m "feat(commands): capture origin via --origin/--added-by in add-hypothesis/add-question"
```

---

## Task 9: Command docs + codex mirrors — research-topic

**Files:**
- Modify: `commands/research-topic.md`
- Regenerate + commit: `codex-skills/**`

**Interfaces:** Topic entities are authored directly (mustache `background-topic.md`), so the topic-researcher writes `origins` into frontmatter — no CLI flag needed for topic. Theme has no dedicated creation command; the `background-topic.md`/`theme.md` template comments (Task 3) suffice — do not invent a command.

- [ ] **Step 1: Update `commands/research-topic.md`**

Where the topic entity is authored, add:

```markdown
Set `origins` in the topic frontmatter to reflect where the framing came from —
`{type: literature, ref: paper:<key>}` for each seed review (bare keys → `cite:<key>`),
or `{type: user}` if the user named the topic. Set `added_by: "llm:<model>:research-topic"`.
Provenance only; does not affect belief.
```

- [ ] **Step 2: Acceptance + regenerate**

Run: `grep -c "origins" commands/research-topic.md` → expect ≥ 1.
Run: `cd science && uv run python ../scripts/generate_codex_skills.py`
Run: `cd science && uv run --frozen pytest tests/test_codex_skills.py -v` → PASS.

- [ ] **Step 3: Commit**

```bash
git add commands/research-topic.md codex-skills
git commit -m "feat(commands): record topic origin in research-topic"
```

---

## Task 10: Full validation sweep

- [ ] **Step 1: Model suite** — `cd science/model && uv run --frozen pytest` → PASS.
- [ ] **Step 2: Tool suite** — `cd science && uv run --frozen pytest` → PASS (incl. graph/health/cli/codex origin tests).
- [ ] **Step 3: Lint + types** — `cd science && uv run ruff check && uv run pyright` → clean.
- [ ] **Step 4: Automated CLI→graph end-to-end test** — prove the **create path and the materialization path together** (not only hand-written markdown). Append to `science/tests/test_graph_origins.py`:

```python
def test_cli_created_entity_materializes_origins(cli_runner, scratch_project):
    # scratch_project must have a paper referenced by the cite key in references.bib,
    # or use a user origin to keep the fixture minimal.
    result = cli_runner.invoke(app, [  # adapt app/fixtures to the real CLI test harness
        "hypotheses", "create", "E2E",
        "--origin", "user@2026-07-03", "--added-by", "user",
    ])
    assert result.exit_code == 0, result.output
    out = materialize_graph(scratch_project)
    g = _g(out)
    assert (None, PROV.wasAttributedTo, URIRef(SCI + "agent/user")) in g
    assert any(str(o) == "user" for o in g.objects(None, URIRef(SCI + "addedBy")))
```

Run: `cd science && uv run --frozen pytest tests/test_graph_origins.py::test_cli_created_entity_materializes_origins -v` → PASS.

- [ ] **Step 5: Manual smoke (optional confidence check)** — on a scratch project: `science hypotheses create "Smoke" --origin user@2026-07-03 --origin literature:cite:<key-in-references.bib> --added-by user`; `science graph`; `science health`. Confirm `graph.trig` has the `sci:Origin` nodes + `sci:addedBy`, health is clean, then swap to a missing cite key and confirm health flags it.

- [ ] **Step 6: Final commit (if a fix was needed)**

```bash
git add -A && git commit -m "test: origin-provenance CLI-to-graph end-to-end"
```

---

## Self-Review (completed during authoring)

- **Spec coverage:** model fields (T1), frontmatter (T2), templates + `VALID_FIELD_NAMES` + render-default + both dirs (T3), strict topic/theme mixins, no version bump (T4), PROV-O materialization incl. `paper:`/`cite:` resolution + agents + `added_by` (T5), health (T6), **real** write-path via CLI flags (T7) + command docs + codex regen (T8–T9), migration = none, non-goals untouched. All spec sections map to a task.
- **Review-fix coverage:** F1 topic→`background-topic.md` (not `topic.md`); template-ready set corrected to hypothesis/question/theme (T3). F2 `{from: origins, default: []}` + render test (T3). F3 real CLI authoring via `extra_frontmatter`, not doc-only (T7). F4 `type=` in the entity fixture (T1). F5 strict schema (`additionalProperties:false` + literature `if/then` ref pattern) (T4). F6 codex-skills regeneration + sync test (T8–T9).
- **Placeholder scan:** implementation code is concrete; "Note to implementer" callouts are *lookup* instructions with exact search targets (parse-fn name, `SCI_NS` string + graph fixture, Finding constructor, CLI app/fixture), each backed by a behavior-defining test.
- **Type consistency:** `OriginType`/`OriginRecord` field names (`type`/`ref`/`date`/`independent`/`note`) identical across model, frontmatter, schema, materialize, health, and `parse_origin_spec`. Predicate local-names (`hasOrigin`/`Origin`/`originKind`/`independentOrigination`/`addedBy`/`agent/<type>`/`cite/<key>`) consistent between T5 and the spec.
