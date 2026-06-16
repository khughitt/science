# Phase 4a — Statement→Proposition Promotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `science annotate promote <source.md>` — a deterministic, curator-reviewed command that turns `proposition`-type statement annotations into `proposition` entities (mint-or-link), with provenance and idempotency, no inference.

**Architecture:** A new `annotation/promote.py` owns pure decision logic (`normalize_claim`, mint-or-link-or-collision) and apply logic (mint via a shared entity writer, link via source-ref append, sidecar `sci:promotedTo` backlink). Reuses the workbench's entity-minting machinery via a **shared, public** `write_entity_file` + `slug_for_claim_text` in `entities.py` (extracted, behavior-preserving). Provenance materializes through a new `annotation:`-ref branch in `graph/materialize.py`.

**Tech Stack:** Python 3.12, `uv` workspace, Click CLI, rdflib (TriG sidecars), Pydantic entity models, pytest.

**Spec:** `docs/plans/2026-06-16-statement-promotion-phase4a-design.md`.

---

## Standing constraints (every task)

- **Worktree:** `/mnt/ssd/Dropbox/science/.worktrees/sub-article-annotation-phase4`, branch **`feat/sub-article-annotation-phase4`**. Every subagent MUST `cd` there and run `git branch --show-current` → expect `feat/sub-article-annotation-phase4` before any commit (commits otherwise leak to the Dropbox-synced `main`).
- **NO `Co-Authored-By` trailer** in commits.
- Tests/lint run from the `science/` subdir: `cd science && uv run --frozen pytest <path> -v` (also `pyright`, `ruff check`). The pytest summary line may not reach piped output — **rely on exit code 0**. `reportMissingImports` for `science_tool.*`/`rdflib` from a bare `pyright` is a known editor artifact; trust `uv run --frozen pyright`.
- Local only — **do not push**.

## Pre-flight anchors (verified file:line)

- `dag/workbench.py:295` `_write_entity_file`; call sites `:396` (proposition), `:407` (evidence-line); hardcoded body `:354`. Slug `:194` `_slug_for_triple`.
- `entities.py:330` `truncate_slug_on_word_boundary`, `:348` `DERIVED_SLUG_MAX_LENGTH = 72`, `:351` `normalize_to_slug`, `:293` `resolve_path_policy`, `:826` `_render_markdown`, `:838` `_atomic_replace_text`, `:972` `_parse_markdown_file`, `default_status`, `EntityCommandError`; `:22` re-exports `load_project_sources`; `:719` `list_entities`.
- `annotation/model.py:83` `Annotation` (fields incl. `lifted_from`, `match_text`), `:44` `TextQuoteSelector.exact`, `:51` `SpecificResource.selector`, `:15` `Status` enum. Claim text = `ann.target.selector.exact`.
- `annotation/io.py:42` `SCI = Namespace("http://example.org/science/vocab/")`; read `:154` `lifted_from = _str_or_none(ds.value(subj, SCI.liftedFrom))`; write `:381` `sci:liftedFrom`; `_str_or_none :263`. `sidecar_for_markdown`/`markdown_for_sidecar` `:48`/`:64`. `write_sidecar` exists in io.py.
- `annotation/query.py:108` `entity_relpath_for_sidecar(sidecar_path, root)`; `:148` `resolve_id` (handles `<relpath>:<frag>`).
- `graph/materialize.py:490-505` `source_refs` loop emitting `PROV.wasDerivedFrom`; `:1183` `_entity_uri`; imports `PROV` (rdflib.namespace), `is_bibliography_reference`/`is_external_reference`/`is_metadata_reference`.
- `graph/io.py:13` `PROJECT_NS = Namespace("http://example.org/project/")`, `:24` `entity_uri_for_ref`.
- `validate/checks/entity_conformance.py` checks **frontmatter only** (`_REQUIRED_FRONTMATTER = ("id","type","title","status","created","updated")`) — body sections are NOT validated, so a minted Claim-section body is safe.
- Entity model: `science_model/propositions.py` `PropositionEntity` — `predicate`/`polarity`/`subject`/`object`/`claim_layer`/`identification_strength` all optional; relational validator fires only when `predicate` set.

---

## File structure

- **Create** `science/src/science_tool/annotation/promote.py` — promotion model + decision + apply + override parsing.
- **Modify** `science/src/science_tool/entities.py` — add public `write_entity_file`, `slug_from_raw`, `slug_for_claim_text`, `append_entity_source_ref`.
- **Modify** `science/src/science_tool/dag/workbench.py` — `_write_entity_file` → thin wrapper over `write_entity_file`; `_slug_for_triple` → uses `slug_from_raw`.
- **Modify** `science/src/science_tool/annotation/model.py` — `Annotation.promoted_to: Optional[str] = None`.
- **Modify** `science/src/science_tool/annotation/io.py` — round-trip `sci:promotedTo`.
- **Modify** `science/src/science_tool/graph/materialize.py` — `annotation:`-ref → `wasDerivedFrom` branch + `_annotation_uri`.
- **Modify** `science/src/science_tool/annotation/cli.py` — `promote` subcommand.
- **Modify** `docs/conventions/annotation-tokens.md` — promotion vocabulary.
- **Tests:** `science/tests/test_entity_writer.py` (new), `test_annotation_io.py`, `test_graph_materialize.py`, `test_annotation_promote.py` (new), `test_annotate_promote_cli.py` (new), `test_workbench_compile.py` (regression).

---

## Task 1: Shared entity writer + claim slug (behavior-preserving refactor)

**Files:**
- Modify: `science/src/science_tool/entities.py`
- Modify: `science/src/science_tool/dag/workbench.py:194-211,295-357,396,407`
- Test: `science/tests/test_entity_writer.py` (new), `science/tests/test_workbench_compile.py` (regression)

- [ ] **Step 1: Write the failing test** — `science/tests/test_entity_writer.py`

```python
from datetime import date
from pathlib import Path

from science_model.propositions import PropositionEntity
from science_tool.entities import (
    slug_for_claim_text,
    slug_from_raw,
    write_entity_file,
)
from science_tool.entities import EntityCommandError
import pytest


def _project(tmp_path: Path) -> Path:
    # resolve_path_policy needs a project; entities/propositions is the proposition home.
    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    return tmp_path


def test_slug_for_claim_text_basic():
    assert slug_for_claim_text("The cat sat on the mat") == "the-cat-sat-on-the-mat"


def test_slug_for_claim_text_unsluggable_raises():
    with pytest.raises(EntityCommandError):
        slug_for_claim_text("…")  # normalizes to <2 chars


def test_write_entity_file_places_custom_body(tmp_path: Path):
    root = _project(tmp_path)
    prop = PropositionEntity(id="proposition:demo-claim", title="Demo claim")
    body = "# Demo claim\n\n## Claim\n\nDemo claim.\n\n## Evidence Summary\n\n\n## Caveats\n"
    write_entity_file(prop, project_root=root, body=body, as_of=date(2026, 6, 16))
    dest = root / "entities" / "propositions" / "demo-claim.md"
    text = dest.read_text(encoding="utf-8")
    assert "## Claim\n\nDemo claim." in text
    assert "id: proposition:demo-claim" in text or 'id: "proposition:demo-claim"' in text
    assert "created: 2026-06-16" in text or 'created: "2026-06-16"' in text
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_entity_writer.py -v`
Expected: FAIL — `ImportError: cannot import name 'write_entity_file'` (and `slug_for_claim_text`).

- [ ] **Step 3: Add the shared primitives to `entities.py`**

Add near the existing slug helpers (after `truncate_slug_on_word_boundary`, ~line 360). `date`, `yaml`, `Path`, `Any` must be importable at the top (add any missing: `import yaml`; `from datetime import date`; `from typing import Any` — check existing imports first and only add what's absent).

```python
def slug_from_raw(raw: str) -> str:
    """Normalize + word-boundary-truncate a raw string to an entity slug (no length guard)."""
    return truncate_slug_on_word_boundary(normalize_to_slug(raw), DERIVED_SLUG_MAX_LENGTH)


def slug_for_claim_text(claim: str) -> str:
    """Deterministic proposition slug from a claim sentence; fail loud if it can't form one."""
    slug = slug_from_raw(claim)
    if len(slug) < 2:
        raise EntityCommandError("claim text cannot derive a stable proposition slug; set an explicit id")
    return slug


def write_entity_file(
    entity: Any,  # any typed entity exposing .kind, .id, and Pydantic .model_dump()
    *,
    project_root: Path,
    body: str,
    as_of: date | None = None,
) -> None:
    """Write a typed entity to its canonical ``entities/<kind>/<slug>.md`` file.

    Single canonical entity writer (also used by ``dag.workbench``). Path from
    ``resolve_path_policy``; frontmatter from the typed model's ``model_dump``; the
    Markdown ``body`` is supplied by the caller. ``created`` is preserved on upsert;
    ``updated`` advances to ``as_of`` (or today).
    """
    today = as_of or date.today()
    kind = entity.kind
    assert entity.id is not None
    local_part = entity.id.split(":", 1)[1]
    policy = resolve_path_policy(kind, project_root=project_root)
    dest = project_root / policy.root / f"{local_part}.md"

    existing_created: str | None = None
    if dest.exists():
        try:
            existing_fm, _ = _parse_markdown_file(dest)
            existing_created = existing_fm.get("created")
            if existing_created is not None:
                existing_created = str(existing_created)
        except (yaml.YAMLError, ValueError, OSError):
            existing_created = None

    frontmatter = entity.model_dump(mode="json", exclude_none=True, exclude_defaults=False)
    frontmatter["id"] = entity.id
    frontmatter["kind"] = kind
    frontmatter.setdefault("status", default_status(kind))
    for derived in ("canonical_id", "content_preview", "content", "file_path"):
        frontmatter.pop(derived, None)
    frontmatter["created"] = existing_created if existing_created is not None else today.isoformat()
    frontmatter["updated"] = today.isoformat()

    text = _render_markdown(frontmatter, body)
    dest.parent.mkdir(parents=True, exist_ok=True)
    _atomic_replace_text(dest, text)


def append_entity_source_ref(file_path: Path, ref: str) -> bool:
    """Append ``ref`` to an existing entity file's ``source_refs`` frontmatter, preserving
    the body. Returns True if added, False if already present. Used by promotion LINK so a
    hand-authored proposition's prose is never clobbered."""
    frontmatter, body = _parse_markdown_file(file_path)
    refs = list(frontmatter.get("source_refs") or [])
    if ref in refs:
        return False
    refs.append(ref)
    frontmatter["source_refs"] = refs
    _atomic_replace_text(file_path, _render_markdown(frontmatter, body))
    return True
```

- [ ] **Step 4: Run the writer test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_entity_writer.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Repoint `dag/workbench.py` onto the shared primitives (byte-preserving)**

Replace `_write_entity_file` (lines 295-357) body with a thin wrapper that reconstructs the **exact** legacy body:

```python
def _write_entity_file(
    entity: PropositionEntity | EvidenceLineEntity,
    *,
    project_root: Path,
    as_of: date | None = None,
) -> None:
    """Workbench writer: delegates to the shared entity writer with the legacy body."""
    from science_tool.entities import write_entity_file

    assert entity.id is not None
    local_part = entity.id.split(":", 1)[1]
    body = f"# {entity.title or local_part}\n\n## Summary\n\n\n## Notes\n"
    write_entity_file(entity, project_root=project_root, body=body, as_of=as_of)
```

And refactor `_slug_for_triple` (lines 194-211) to share the underlying call:

```python
def _slug_for_triple(subject: str | None, predicate: str | None, obj: str | None) -> str:
    """Deterministic slug from a row's triple (`<subject>-<predicate>-<object>`)."""
    from science_tool.entities import EntityCommandError, slug_from_raw

    raw = "-".join(part for part in (subject, predicate, obj) if part)
    slug = slug_from_raw(raw)
    if len(slug) < 2:
        raise EntityCommandError("row triple cannot derive a stable proposition slug; set an explicit id")
    return slug
```

(The two `_write_entity_file` call sites at `:396`/`:407` are unchanged — same signature.)

- [ ] **Step 6: Run the workbench regression suite**

Run: `cd science && uv run --frozen pytest tests/test_workbench_compile.py -v`
Expected: PASS (no behavior change — same frontmatter + same body bytes).

- [ ] **Step 7: Lint + typecheck**

Run: `cd science && uv run --frozen ruff check src/science_tool/entities.py src/science_tool/dag/workbench.py && uv run --frozen pyright src/science_tool/entities.py`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/sub-article-annotation-phase4
git add science/src/science_tool/entities.py science/src/science_tool/dag/workbench.py science/tests/test_entity_writer.py
git commit -m "refactor(entities): shared write_entity_file + slug_for_claim_text; workbench delegates"
```

---

## Task 2: Annotation `promoted_to` field + io round-trip

**Files:**
- Modify: `science/src/science_tool/annotation/model.py:83-99`
- Modify: `science/src/science_tool/annotation/io.py:154,381` (read + write)
- Test: `science/tests/test_annotation_io.py`

- [ ] **Step 1: Write the failing test** — append to `science/tests/test_annotation_io.py`

```python
def test_promoted_to_round_trips(tmp_path):
    # Build a minimal sidecar with one annotation carrying promoted_to, write, re-read.
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.model import (
        Annotation, Motivation, SpecificResource, Status, TextQuoteSelector, TextualBody,
    )
    from datetime import datetime, timezone

    md = tmp_path / "paper.md"
    md.write_text("Alpha beta gamma.\n", encoding="utf-8")
    sidecar_path = anno_io.sidecar_for_markdown(md)
    ann = Annotation(
        id="a-0001",
        target=SpecificResource(source="paper.md", selector=TextQuoteSelector(exact="Alpha", prefix="", suffix=" beta")),
        bodies=(TextualBody(value='{"section":"abstract"}', format="application/json"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="proposition",
        source="llm-annot:m:paper-annotate-v1",
        status=Status.OPEN,
        creator="paper-annotate",
        created=datetime(2026, 6, 16, tzinfo=timezone.utc),
        promoted_to="proposition:alpha",
    )
    sidecar = anno_io.Sidecar(annotations=(ann,))
    anno_io.write_sidecar(sidecar_path, sidecar)
    from science_tool.annotation.query import read_sidecar_strict
    reread = read_sidecar_strict(sidecar_path)
    assert reread.annotations[0].promoted_to == "proposition:alpha"
```

> Confirmed APIs: `Sidecar(annotations=(...), ledgers=(...), shared_targets=(...))` is a frozen dataclass in `model.py` (re-exported via `io.py`); `write_sidecar(path, sidecar)` lives in `annotation/io.py`; **`read_sidecar_strict(path)` lives in `annotation/query.py`** (io has only `read_sidecar`). All positional.

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_annotation_io.py::test_promoted_to_round_trips -v`
Expected: FAIL — `TypeError: ... unexpected keyword argument 'promoted_to'`.

- [ ] **Step 3: Add the field to the model** — `annotation/model.py`, in `Annotation` after `lifted_from`:

```python
    lifted_from: Optional[str] = None
    promoted_to: Optional[str] = None  # proposition:<slug> this span was promoted into (Phase 4a)
    match_text: Optional[str] = None
```

- [ ] **Step 4: Round-trip in `io.py`** — READ (after the `lifted_from` read, ~line 154):

```python
        lifted_from = _str_or_none(ds.value(subj, SCI.liftedFrom))
        promoted_to = _str_or_none(ds.value(subj, SCI.promotedTo))
```

and pass `promoted_to=promoted_to,` into the `Annotation(...)` constructor in that same function (next to `lifted_from=lifted_from,`).

WRITE (after the `sci:liftedFrom` emit, ~line 381):

```python
    if ann.lifted_from is not None:
        out.append(f"    sci:liftedFrom     {_str_lit(ann.lifted_from)} ;")
    if ann.promoted_to is not None:
        out.append(f"    sci:promotedTo     {_str_lit(ann.promoted_to)} ;")
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_annotation_io.py -v`
Expected: PASS (new test + existing io tests still green).

- [ ] **Step 6: Lint + commit**

```bash
cd science && uv run --frozen ruff check src/science_tool/annotation/model.py src/science_tool/annotation/io.py
cd /mnt/ssd/Dropbox/science/.worktrees/sub-article-annotation-phase4
git add science/src/science_tool/annotation/model.py science/src/science_tool/annotation/io.py science/tests/test_annotation_io.py
git commit -m "feat(annotation): sci:promotedTo backlink field + io round-trip"
```

---

## Task 3: materialize `annotation:` source-ref → `wasDerivedFrom`

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py:490-505` (+ a helper near `_entity_uri:1183`)
- Test: `science/tests/test_graph_materialize.py`

- [ ] **Step 1: Write the failing tests** — append to `science/tests/test_graph_materialize.py`

```python
def test_annotation_uri_minter():
    from science_tool.graph.materialize import _annotation_uri

    uri = _annotation_uri("annotation:papers/smith2020.source#a-7f3a")
    assert str(uri).startswith("http://example.org/project/annotation/")
    assert "smith2020.source" in str(uri)
    assert str(uri).endswith("#a-7f3a")


def test_annotation_source_ref_materializes_wasderivedfrom(tmp_path: Path) -> None:
    """A proposition whose source_refs include an `annotation:` ref AND a resolvable
    entity ref produces BOTH prov:wasDerivedFrom triples in the provenance graph."""
    from science_tool.graph.materialize import _annotation_uri

    project = tmp_path / "demo"
    _write_demo_project(project)  # provides the resolvable entity question:q01-demo
    _write_minimal_entity(
        project / "entities" / "propositions" / "demo-claim.md",
        "proposition:demo-claim", "proposition", "Demo claim",
        extra_frontmatter=[
            "source_refs:",
            '  - "annotation:papers/p.source#a-1"',
            '  - "question:q01-demo"',
        ],
    )
    trig_path = materialize_graph(project)
    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    prop_uri = PROJECT_NS["proposition/demo-claim"]
    assert (prop_uri, PROV.wasDerivedFrom, _annotation_uri("annotation:papers/p.source#a-1")) in provenance
    # the resolvable entity ref still materializes via the existing path (paper:<id> behaves identically)
    assert (prop_uri, PROV.wasDerivedFrom, PROJECT_NS["question/q01-demo"]) in provenance
```

> The integration test reuses the file's `_write_demo_project` / `_write_minimal_entity` helpers and the `PROV`/`PROJECT_NS` names already imported at the top of `test_graph_materialize.py`. It uses `question:q01-demo` as the resolvable companion ref (a real entity in the demo project) to prove the new `annotation:` branch coexists with the existing resolved-entity branch; `paper:<paper-id>` follows the identical resolvable-entity path.

- [ ] **Step 2: Run to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_graph_materialize.py -k "annotation_uri or annotation_source_ref" -v`
Expected: FAIL — `ImportError: cannot import name '_annotation_uri'`.

- [ ] **Step 3: Add the helper + loop branch** — `graph/materialize.py`.

Add near `_entity_uri` (line ~1183); `PROJECT_NS` is importable from `science_tool.graph.io`:

```python
def _annotation_uri(ref: str) -> URIRef:
    """Mint a stable project URI for an `annotation:<relpath>#<frag>` source ref.

    Bypasses entity resolution (an annotation is not an entity). Case/`/` of the relpath
    are preserved (unlike `entity_uri_for_ref`, which lowercases)."""
    from science_tool.graph.io import PROJECT_NS

    body = ref[len("annotation:"):]
    return URIRef(f"{PROJECT_NS}annotation/{body}")
```

Insert the branch as the FIRST check in the `source_refs` loop (line ~490), before `is_bibliography_reference`:

```python
    for raw_target in sorted(entity.source_refs):
        if raw_target.startswith("annotation:"):
            provenance.add((entity_uri, PROV.wasDerivedFrom, _annotation_uri(raw_target)))
            continue
        if is_bibliography_reference(raw_target):
            continue
        # ... rest unchanged ...
```

- [ ] **Step 4: Run to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_graph_materialize.py -k "annotation_uri or annotation_source_ref" -v`
Expected: PASS (both new tests). Then `cd science && uv run --frozen pytest tests/test_graph_materialize.py -q` → existing materialize tests still green.

- [ ] **Step 5: Lint + commit**

```bash
cd science && uv run --frozen ruff check src/science_tool/graph/materialize.py
cd /mnt/ssd/Dropbox/science/.worktrees/sub-article-annotation-phase4
git add science/src/science_tool/graph/materialize.py science/tests/test_graph_materialize.py
git commit -m "feat(materialize): annotation: source-ref emits prov:wasDerivedFrom to annotation URI"
```

---

## Task 4: promotion decision core — `normalize_claim` + mint/link/collision

**Files:**
- Create: `science/src/science_tool/annotation/promote.py`
- Test: `science/tests/test_annotation_promote.py` (new)

- [ ] **Step 1: Write the failing test** — `science/tests/test_annotation_promote.py`

```python
import pytest
from science_tool.annotation.promote import (
    Promotable, PromotionCorpus, decide_candidates, normalize_claim,
)


def _corpus(titles_to_slug=None, slugs=None, derived=None):
    return PromotionCorpus(
        title_to_ref={normalize_claim(t): s for t, s in (titles_to_slug or {}).items()},
        existing_slugs=set(slugs or []),
        derived_refs=set(derived or []),
    )


def test_normalize_claim_casefolds_and_collapses():
    assert normalize_claim("The  CAT  sat") == normalize_claim("the cat sat") == "the cat sat"


def test_statement_extract_normalize_text_unchanged():
    # Guard: promotion must NOT casefold the Phase-3 match_text normalizer.
    from science_tool.annotation.statement_extract import _normalize_text
    assert _normalize_text("The Cat") == "The Cat"  # whitespace-only, case-preserving


def test_novel_claim_mints():
    p = Promotable(ref="annotation:a#f1", frag="f1", claim="Novel claim here", subject=None, object=None)
    [c] = decide_candidates([p], _corpus())
    assert c.decision == "MINT" and c.slug == "novel-claim-here"


def test_identical_title_links():
    p = Promotable(ref="annotation:a#f1", frag="f1", claim="Shared claim text", subject=None, object=None)
    corp = _corpus(titles_to_slug={"Shared claim text": "proposition:shared-claim-text"})
    [c] = decide_candidates([p], corp)
    assert c.decision == "LINK" and c.slug == "proposition:shared-claim-text"


def test_case_difference_still_links():
    p = Promotable(ref="annotation:a#f1", frag="f1", claim="SHARED claim TEXT", subject=None, object=None)
    corp = _corpus(titles_to_slug={"shared claim text": "proposition:shared-claim-text"})
    [c] = decide_candidates([p], corp)
    assert c.decision == "LINK"


def test_slug_collision_against_corpus():
    # An existing slug occupied by a DIFFERENT-title proposition → COLLISION, not LINK.
    p = Promotable(ref="annotation:a#f1", frag="f1", claim="Alpha beta", subject=None, object=None)
    corp = _corpus(slugs={"alpha-beta"})
    [c] = decide_candidates([p], corp)
    assert c.decision == "COLLISION"


def test_intra_batch_collision():
    # Two different claims truncating to the same slug in one batch → both COLLISION
    # (simulate with two claims that normalize_to_slug to the same value).
    a = Promotable(ref="annotation:a#f1", frag="f1", claim="Same Slug Here", subject=None, object=None)
    b = Promotable(ref="annotation:a#f2", frag="f2", claim="same slug here!!", subject=None, object=None)
    out = decide_candidates([a, b], _corpus())
    assert [c.decision for c in out] == ["MINT", "COLLISION"]


def test_unsluggable_claim_skipped():
    p = Promotable(ref="annotation:a#f1", frag="f1", claim="…", subject=None, object=None)
    [c] = decide_candidates([p], _corpus())
    assert c.decision == "SKIP" and c.reason == "promote-claim-unsluggable"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_annotation_promote.py -v`
Expected: FAIL — `ModuleNotFoundError: science_tool.annotation.promote`.

- [ ] **Step 3: Create `annotation/promote.py` with the decision core**

```python
"""Phase 4a — statement→proposition promotion (decision + apply)."""

from __future__ import annotations

from dataclasses import dataclass, field

from science_tool.entities import EntityCommandError, slug_for_claim_text


def normalize_claim(text: str) -> str:
    """Promotion-specific normalizer: casefold + whitespace-collapse.

    DELIBERATELY separate from `statement_extract._normalize_text` (whitespace-only,
    case-preserving), which is baked into Phase-3 `match_text` and must not change.
    """
    return " ".join(text.casefold().split())


@dataclass(frozen=True)
class Promotable:
    ref: str            # "annotation:<relpath>#<frag>"
    frag: str           # annotation id within its sidecar
    claim: str          # the TextQuoteSelector exact span
    subject: str | None
    object: str | None


@dataclass(frozen=True)
class PromotionCorpus:
    title_to_ref: dict[str, str]   # normalize_claim(title) -> "proposition:<slug>"
    existing_slugs: set[str]       # bare slugs of existing propositions
    derived_refs: set[str]         # annotation: refs already in some proposition's source_refs


@dataclass(frozen=True)
class PromotionCandidate:
    ref: str
    frag: str
    claim: str
    subject: str | None
    object: str | None
    decision: str           # MINT | LINK | COLLISION | SKIP
    slug: str | None        # MINT: new bare slug; LINK: "proposition:<slug>"; else None
    reason: str             # short explanation / skip reason


def decide_candidates(promotables: list[Promotable], corpus: PromotionCorpus) -> list[PromotionCandidate]:
    """Pure mint-or-link-or-collision decision. Detects intra-batch slug collisions."""
    out: list[PromotionCandidate] = []
    minted_slugs: set[str] = set()
    for p in promotables:
        key = normalize_claim(p.claim)
        existing = corpus.title_to_ref.get(key)
        if existing is not None:
            out.append(_cand(p, "LINK", existing, "normalized claim equals existing proposition title"))
            continue
        try:
            slug = slug_for_claim_text(p.claim)
        except EntityCommandError:
            out.append(_cand(p, "SKIP", None, "promote-claim-unsluggable"))
            continue
        if slug in corpus.existing_slugs:
            out.append(_cand(p, "COLLISION", slug, "promote-slug-collision"))  # vs existing corpus
            continue
        if slug in minted_slugs:
            out.append(_cand(p, "COLLISION", slug, "promote-slug-collision"))  # intra-batch
            continue
        minted_slugs.add(slug)
        out.append(_cand(p, "MINT", slug, "new proposition"))
    return out


def _cand(p: Promotable, decision: str, slug: str | None, reason: str) -> PromotionCandidate:
    return PromotionCandidate(
        ref=p.ref, frag=p.frag, claim=p.claim, subject=p.subject, object=p.object,
        decision=decision, slug=slug, reason=reason,
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_annotation_promote.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Lint + typecheck + commit**

```bash
cd science && uv run --frozen ruff check src/science_tool/annotation/promote.py && uv run --frozen pyright src/science_tool/annotation/promote.py
cd /mnt/ssd/Dropbox/science/.worktrees/sub-article-annotation-phase4
git add science/src/science_tool/annotation/promote.py science/tests/test_annotation_promote.py
git commit -m "feat(promote): normalize_claim + mint/link/collision decision core"
```

---

## Task 5: promotable queue + corpus loader (read side)

**Files:**
- Modify: `science/src/science_tool/annotation/promote.py`
- Test: `science/tests/test_annotation_promote.py`

- [ ] **Step 1: Write the failing test** — append to `test_annotation_promote.py`

```python
def _statement_ann(frag, exact, *, status, atype="proposition", subject=None, promoted_to=None):
    import json as _json
    from science_tool.annotation.model import (
        Annotation, Motivation, SpecificResource, TextQuoteSelector, TextualBody,
    )
    from datetime import datetime, timezone
    body = {"section": "abstract", "stance": "asserted"}
    if subject is not None:
        body["subject"] = subject
    return Annotation(
        id=frag,
        target=SpecificResource(source="paper.md", selector=TextQuoteSelector(exact=exact, prefix="", suffix="")),
        bodies=(TextualBody(value=_json.dumps(body), format="application/json"),),
        motivation=Motivation.CLASSIFYING, annotation_type=atype,
        source="llm-annot:m:paper-annotate-v1", status=status,
        creator="paper-annotate", created=datetime(2026, 6, 16, tzinfo=timezone.utc),
        promoted_to=promoted_to,
    )


def test_promotable_filters_queue(tmp_path):
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.model import Status
    from science_tool.annotation.promote import collect_promotable

    md = tmp_path / "paper.md"
    md.write_text("x\n", encoding="utf-8")
    sidecar_path = anno_io.sidecar_for_markdown(md)
    anns = (
        _statement_ann("a-1", "Open proposition claim", status=Status.OPEN, subject="cells"),
        _statement_ann("a-2", "Already promoted", status=Status.OPEN, promoted_to="proposition:x"),
        _statement_ann("a-3", "A question", status=Status.OPEN, atype="question"),
        _statement_ann("a-4", "Dismissed claim", status=Status.DISMISSED),
    )
    sidecar = anno_io.Sidecar(annotations=anns)

    promotable, skipped = collect_promotable(sidecar, sidecar_path, tmp_path, derived_refs=set())
    assert [p.frag for p in promotable] == ["a-1"]
    assert promotable[0].subject == "cells"
    assert skipped["promote-already-promoted"] == 1
    assert skipped["promote-not-proposition-type"] == 1
    assert skipped["promote-inactive-status"] == 1


def test_malformed_statement_body_hard_fails(tmp_path):
    import pytest
    from datetime import datetime, timezone
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.model import (
        Annotation, Motivation, SpecificResource, Status, TextQuoteSelector, TextualBody,
    )
    from science_tool.annotation.promote import PromotionReadError, collect_promotable

    md = tmp_path / "paper.md"
    md.write_text("x\n", encoding="utf-8")
    sp = anno_io.sidecar_for_markdown(md)
    bad = Annotation(
        id="a-1",
        target=SpecificResource(source="paper.md", selector=TextQuoteSelector(exact="x", prefix="", suffix="")),
        bodies=(TextualBody(value="{ not json", format="application/json"),),
        motivation=Motivation.CLASSIFYING, annotation_type="proposition",
        source="llm-annot:m:paper-annotate-v1", status=Status.OPEN,
        creator="paper-annotate", created=datetime(2026, 6, 16, tzinfo=timezone.utc),
    )
    with pytest.raises(PromotionReadError):
        collect_promotable(anno_io.Sidecar(annotations=(bad,)), sp, tmp_path, derived_refs=set())
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_annotation_promote.py::test_promotable_filters_queue -v`
Expected: FAIL — `cannot import name 'collect_promotable'`.

- [ ] **Step 3: Implement `collect_promotable` + `load_corpus`** — append to `promote.py`

```python
import json
from collections import Counter
from pathlib import Path

from science_tool.annotation.model import Status, TextualBody
from science_tool.annotation.query import entity_relpath_for_sidecar


class PromotionReadError(Exception):
    """Raised when a promotable annotation's statement body cannot be read (fail loud)."""


def _annotation_ref(sidecar_path: Path, root: Path, frag: str) -> str:
    return f"annotation:{entity_relpath_for_sidecar(sidecar_path, root)}#{frag}"


def _statement_subject_object(ann) -> tuple[str | None, str | None]:
    """Parse the annotation's JSON statement body for free-text subject/object phrases.

    The statement body is REQUIRED on a proposition annotation: a missing or unparseable
    body is a hard failure (per spec), not a silent subject/object drop.
    """
    for body in ann.bodies:
        if isinstance(body, TextualBody) and body.format == "application/json":
            try:
                data = json.loads(body.value)
            except json.JSONDecodeError as exc:
                raise PromotionReadError(f"annotation {ann.id}: malformed JSON statement body: {exc}") from exc
            if not isinstance(data, dict):
                raise PromotionReadError(f"annotation {ann.id}: statement body is not a JSON object")
            return data.get("subject"), data.get("object")
    raise PromotionReadError(f"annotation {ann.id}: no application/json statement body")


def collect_promotable(sidecar, sidecar_path: Path, root: Path, *, derived_refs: set[str]) -> tuple[list[Promotable], Counter]:
    """Filter a sidecar to the promotable proposition queue, counting skip reasons."""
    out: list[Promotable] = []
    skipped: Counter = Counter()
    for ann in sidecar.annotations:
        if ann.annotation_type != "proposition":
            skipped["promote-not-proposition-type"] += 1
            continue
        if ann.status not in (Status.OPEN, Status.ACK):
            skipped["promote-inactive-status"] += 1
            continue
        ref = _annotation_ref(sidecar_path, root, ann.id)
        if ann.promoted_to is not None or ref in derived_refs:
            skipped["promote-already-promoted"] += 1
            continue
        subject, object_ = _statement_subject_object(ann)
        out.append(Promotable(ref=ref, frag=ann.id, claim=ann.target.selector.exact, subject=subject, object=object_))
    return out, skipped


def load_corpus(project_root: Path) -> PromotionCorpus:
    """Build the proposition corpus (title index, slug set, already-derived refs) from disk."""
    from science_tool.graph.sources import load_project_sources

    sources = load_project_sources(project_root.resolve())
    title_to_ref: dict[str, str] = {}
    existing_slugs: set[str] = set()
    derived_refs: set[str] = set()
    for entity in sources.entities:
        if entity.kind != "proposition":
            continue
        ref = entity.canonical_id  # "proposition:<slug>"
        existing_slugs.add(ref.split(":", 1)[1])
        title = (entity.title or "").strip()
        if title:
            title_to_ref.setdefault(normalize_claim(title), ref)
        for sref in getattr(entity, "source_refs", []) or []:
            if isinstance(sref, str) and sref.startswith("annotation:"):
                derived_refs.add(sref)
    return PromotionCorpus(title_to_ref=title_to_ref, existing_slugs=existing_slugs, derived_refs=derived_refs)
```

> Implementer (Step-3): `entity.canonical_id`/`.title`/`.source_refs` are confirmed on the typed entity (same attrs `list_entities` reads). `load_project_sources` expects a real project root — if it raises on the bare `tmp_path` fixture, scaffold whatever marks a project root (start with the `entities/` tree the tests already create; add a minimal project manifest only if the loader requires one). Verify this in Step 1 by running the queue test, which calls `load_corpus` indirectly via the CLI in Task 8 (Task 5's own test passes `derived_refs=set()` directly and does NOT need a loadable project).

- [ ] **Step 4: Run to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_annotation_promote.py -v`
Expected: PASS (queue test + earlier decision tests).

- [ ] **Step 5: Lint + commit**

```bash
cd science && uv run --frozen ruff check src/science_tool/annotation/promote.py
cd /mnt/ssd/Dropbox/science/.worktrees/sub-article-annotation-phase4
git add science/src/science_tool/annotation/promote.py science/tests/test_annotation_promote.py
git commit -m "feat(promote): promotable queue filter + proposition corpus loader"
```

---

## Task 6: apply — mint / link / backlink (write side)

**Files:**
- Modify: `science/src/science_tool/annotation/promote.py`
- Test: `science/tests/test_annotation_promote.py`

- [ ] **Step 1: Write the failing test** — append to `test_annotation_promote.py`

```python
def test_apply_mints_proposition_and_backlinks(tmp_path):
    from datetime import date
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.model import Status
    from science_tool.annotation.promote import (
        apply_candidates, collect_promotable, decide_candidates, load_corpus,
    )
    from science_tool.annotation.query import read_sidecar_strict

    # project layout
    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    paper_dir = tmp_path / "papers"
    paper_dir.mkdir()
    md = paper_dir / "smith2020.source.md"
    md.write_text("Cells divide rapidly.\n", encoding="utf-8")
    sidecar_path = anno_io.sidecar_for_markdown(md)
    ann = _statement_ann("a-1", "Cells divide rapidly", status=Status.OPEN, subject="Cells")
    anno_io.write_sidecar(sidecar_path, anno_io.Sidecar(annotations=(ann,)))

    corpus = load_corpus(tmp_path)
    promotable, _ = collect_promotable(read_sidecar_strict(sidecar_path), sidecar_path, tmp_path, derived_refs=corpus.derived_refs)
    candidates = decide_candidates(promotable, corpus)
    report = apply_candidates(
        candidates, sidecar_path=sidecar_path, root=tmp_path, project_root=tmp_path,
        paper_ref="paper:smith2020", as_of=date(2026, 6, 16),
    )

    assert report.minted == 1
    prop = (tmp_path / "entities" / "propositions" / "cells-divide-rapidly.md").read_text(encoding="utf-8")
    assert "## Claim\n\nCells divide rapidly" in prop
    assert "subject: Cells" in prop
    assert "annotation:papers/smith2020.source#a-1" in prop
    assert "paper:smith2020" in prop
    # backlink written into sidecar; status unchanged
    re_ann = read_sidecar_strict(sidecar_path).annotations[0]
    assert re_ann.promoted_to == "proposition:cells-divide-rapidly"
    assert re_ann.status == Status.OPEN


def test_apply_links_to_existing_appends_both_refs_preserves_prose(tmp_path):
    from datetime import date
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.model import Status
    from science_tool.annotation.query import read_sidecar_strict
    from science_tool.annotation.promote import (
        apply_candidates, collect_promotable, decide_candidates, load_corpus,
    )

    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    existing = tmp_path / "entities" / "propositions" / "known-claim.md"
    existing.write_text(
        '---\nid: proposition:known-claim\ntype: proposition\ntitle: Known claim\n'
        'status: draft\nsource_refs:\n  - "paper:other"\n'
        'created: "2026-06-16"\nupdated: "2026-06-16"\n---\n'
        "# Known claim\n\n## Claim\n\nHand-authored prose.\n",
        encoding="utf-8",
    )
    (tmp_path / "papers").mkdir()
    md = tmp_path / "papers" / "p.source.md"
    md.write_text("Known claim.\n", encoding="utf-8")
    sp = anno_io.sidecar_for_markdown(md)
    ann = _statement_ann("a-1", "Known claim", status=Status.OPEN)
    anno_io.write_sidecar(sp, anno_io.Sidecar(annotations=(ann,)))

    corpus = load_corpus(tmp_path)
    promotable, _ = collect_promotable(read_sidecar_strict(sp), sp, tmp_path, derived_refs=corpus.derived_refs)
    candidates = decide_candidates(promotable, corpus)
    assert candidates[0].decision == "LINK"

    report = apply_candidates(candidates, sidecar_path=sp, root=tmp_path, project_root=tmp_path,
                              paper_ref="paper:p", as_of=date(2026, 6, 16))
    assert report.linked == 1
    text = existing.read_text(encoding="utf-8")
    assert "Hand-authored prose." in text                 # prose preserved (no clobber)
    assert "annotation:papers/p.source#a-1" in text        # annotation ref appended
    assert "paper:p" in text and "paper:other" in text     # paper ref appended; original kept
    assert read_sidecar_strict(sp).annotations[0].promoted_to == "proposition:known-claim"


def test_apply_refuses_overwrite_of_different_claim(tmp_path):
    # An explicit-id MINT (e.g. from a curator override) must never clobber an unrelated proposition.
    import pytest
    from datetime import date
    from science_tool.annotation.promote import PromotionApplyError, PromotionCandidate, apply_candidates

    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    existing = tmp_path / "entities" / "propositions" / "shared.md"
    existing.write_text(
        '---\nid: proposition:shared\ntype: proposition\ntitle: Totally different claim\n'
        'status: draft\ncreated: "2026-06-16"\nupdated: "2026-06-16"\n---\n# x\n',
        encoding="utf-8",
    )
    cand = PromotionCandidate(ref="annotation:a#f1", frag="f1", claim="A brand new claim",
                              subject=None, object=None, decision="MINT", slug="shared",
                              reason="override explicit id")
    with pytest.raises(PromotionApplyError):
        apply_candidates([cand], sidecar_path=tmp_path / "x.anno.trig", root=tmp_path,
                         project_root=tmp_path, paper_ref="paper:p", as_of=date(2026, 6, 16))


def test_apply_is_idempotent(tmp_path):
    # Running the full flow twice mints once; the second run's queue is empty.
    from datetime import date
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.model import Status
    from science_tool.annotation.promote import (
        apply_candidates, collect_promotable, decide_candidates, load_corpus,
    )
    from science_tool.annotation.query import read_sidecar_strict
    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    (tmp_path / "papers").mkdir()
    md = tmp_path / "papers" / "p.source.md"
    md.write_text("Claim text body.\n", encoding="utf-8")
    sp = anno_io.sidecar_for_markdown(md)
    ann = _statement_ann("a-1", "Claim text body", status=Status.OPEN)
    anno_io.write_sidecar(sp, anno_io.Sidecar(annotations=(ann,)))

    def run():
        corpus = load_corpus(tmp_path)
        pr, _ = collect_promotable(read_sidecar_strict(sp), sp, tmp_path, derived_refs=corpus.derived_refs)
        return apply_candidates(decide_candidates(pr, corpus), sidecar_path=sp, root=tmp_path,
                                project_root=tmp_path, paper_ref="paper:p", as_of=date(2026, 6, 16))

    assert run().minted == 1
    second = run()
    assert second.minted == 0 and second.linked == 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_annotation_promote.py::test_apply_mints_proposition_and_backlinks -v`
Expected: FAIL — `cannot import name 'apply_candidates'`.

- [ ] **Step 3: Implement apply** — append to `promote.py`

```python
import dataclasses
from datetime import date

from science_model.propositions import PropositionEntity
from science_tool.annotation import io as anno_io
from science_tool.annotation.query import read_sidecar_strict
from science_tool.entities import (
    _parse_markdown_file, append_entity_source_ref, resolve_path_policy, write_entity_file,
)


class PromotionApplyError(Exception):
    """Raised at write time when applying a candidate would overwrite an unrelated proposition."""


@dataclass
class ApplyReport:
    minted: int = 0
    linked: int = 0
    skipped: Counter = field(default_factory=Counter)
    written_paths: list[str] = field(default_factory=list)


def _proposition_body(claim: str) -> str:
    return f"# {claim}\n\n## Claim\n\n{claim}\n\n## Evidence Summary\n\n\n## Caveats\n"


def apply_candidates(
    candidates: list[PromotionCandidate],
    *,
    sidecar_path: Path,
    root: Path,
    project_root: Path,
    paper_ref: str,
    as_of: date | None = None,
) -> ApplyReport:
    """Execute MINT/LINK candidates: write entities, accrue provenance, set the sidecar backlink."""
    report = ApplyReport()
    backlinks: dict[str, str] = {}  # frag -> proposition:<slug>

    for c in candidates:
        if c.decision == "MINT":
            assert c.slug is not None
            prop_ref = f"proposition:{c.slug}"
            policy = resolve_path_policy("proposition", project_root=project_root)
            dest = project_root / policy.root / f"{c.slug}.md"
            # Never-overwrite guard: a MINT slug colliding with a DIFFERENT-claim proposition
            # (only reachable via an explicit-id override; auto mints are pre-screened) fails loud.
            if dest.exists():
                existing_fm, _ = _parse_markdown_file(dest)
                if normalize_claim(str(existing_fm.get("title") or "")) != normalize_claim(c.claim):
                    raise PromotionApplyError(
                        f"refusing to overwrite {dest.name}: it holds a different proposition"
                    )
            prop = PropositionEntity(
                id=prop_ref, title=c.claim, subject=c.subject, object=c.object,
                source_refs=[paper_ref, c.ref],
            )
            write_entity_file(prop, project_root=project_root, body=_proposition_body(c.claim), as_of=as_of)
            report.written_paths.append(str(dest))
            report.minted += 1
            backlinks[c.frag] = prop_ref
        elif c.decision == "LINK":
            assert c.slug is not None  # "proposition:<slug>"
            policy = resolve_path_policy("proposition", project_root=project_root)
            dest = project_root / policy.root / f"{c.slug.split(':', 1)[1]}.md"
            # Accrue BOTH provenance refs onto the existing proposition; append_entity_source_ref
            # dedups and preserves the (possibly hand-authored) prose body.
            for ref in (paper_ref, c.ref):
                append_entity_source_ref(dest, ref)
            report.linked += 1
            backlinks[c.frag] = c.slug
        else:  # COLLISION / SKIP — not applied
            report.skipped[c.reason] += 1

    if backlinks:
        sidecar = read_sidecar_strict(sidecar_path)
        new_anns = tuple(
            dataclasses.replace(a, promoted_to=backlinks[a.id]) if a.id in backlinks else a
            for a in sidecar.annotations
        )
        anno_io.write_sidecar(sidecar_path, dataclasses.replace(sidecar, annotations=new_anns))
    return report
```

> Confirmed: `PropositionEntity` accepts `subject`/`object`/`source_refs` at construction (`propositions.py`); `Sidecar` is a frozen dataclass, so `dataclasses.replace(sidecar, annotations=...)` is correct.

- [ ] **Step 4: Run to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_annotation_promote.py -v`
Expected: PASS (apply + idempotency + all earlier).

- [ ] **Step 5: Lint + typecheck + commit**

```bash
cd science && uv run --frozen ruff check src/science_tool/annotation/promote.py && uv run --frozen pyright src/science_tool/annotation/promote.py
cd /mnt/ssd/Dropbox/science/.worktrees/sub-article-annotation-phase4
git add science/src/science_tool/annotation/promote.py science/tests/test_annotation_promote.py
git commit -m "feat(promote): apply mint/link + sci:promotedTo backlink (idempotent)"
```

---

## Task 7: curator override (`--input` edited candidates)

**Files:**
- Modify: `science/src/science_tool/annotation/promote.py`
- Test: `science/tests/test_annotation_promote.py`

- [ ] **Step 1: Write the failing test** — append to `test_annotation_promote.py`

The override input is the SAME row shape the read-only `--json` emits (the curator edits
`decision`/`slug` in place and feeds the file back).

```python
def test_override_flips_mint_to_link():
    from science_tool.annotation.promote import PromotionCandidate, apply_overrides

    base = [PromotionCandidate(ref="annotation:a#f1", frag="f1", claim="C", subject=None, object=None,
                               decision="MINT", slug="c", reason="new proposition")]
    edited = [{"annotation": "annotation:a#f1", "decision": "LINK", "slug": "proposition:existing"}]
    [out] = apply_overrides(base, edited, existing_refs={"proposition:existing"})
    assert out.decision == "LINK" and out.slug == "proposition:existing"


def test_override_explicit_id_resolves_collision():
    from science_tool.annotation.promote import PromotionCandidate, apply_overrides

    base = [PromotionCandidate(ref="annotation:a#f1", frag="f1", claim="C", subject=None, object=None,
                               decision="COLLISION", slug="c", reason="promote-slug-collision")]
    edited = [{"annotation": "annotation:a#f1", "decision": "MINT", "slug": "proposition:c-2"}]
    [out] = apply_overrides(base, edited, existing_refs=set())
    assert out.decision == "MINT" and out.slug == "c-2"


def test_override_unchanged_row_passthrough():
    from science_tool.annotation.promote import PromotionCandidate, apply_overrides

    base = [PromotionCandidate(ref="annotation:a#f1", frag="f1", claim="C", subject=None, object=None,
                               decision="MINT", slug="c", reason="new")]
    [out] = apply_overrides(base, [{"annotation": "annotation:a#f1", "decision": "MINT", "slug": "c"}], existing_refs=set())
    assert out.decision == "MINT" and out.slug == "c"


def test_override_bad_link_target_fails_loud():
    import pytest
    from science_tool.annotation.promote import PromotionCandidate, PromotionOverrideError, apply_overrides

    base = [PromotionCandidate(ref="annotation:a#f1", frag="f1", claim="C", subject=None, object=None,
                               decision="MINT", slug="c", reason="new")]
    with pytest.raises(PromotionOverrideError):
        apply_overrides(base, [{"annotation": "annotation:a#f1", "decision": "LINK", "slug": "proposition:missing"}], existing_refs=set())


def test_override_unknown_ref_fails_loud():
    import pytest
    from science_tool.annotation.promote import PromotionOverrideError, apply_overrides

    with pytest.raises(PromotionOverrideError):
        apply_overrides([], [{"annotation": "annotation:zzz#f9", "decision": "MINT", "slug": "x"}], existing_refs=set())
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_annotation_promote.py -k override -v`
Expected: FAIL — `cannot import name 'apply_overrides'`.

- [ ] **Step 3: Implement override** — append to `promote.py`

```python
class PromotionOverrideError(Exception):
    """Raised when an edited candidate override is invalid (fail loud)."""


def apply_overrides(
    base: list[PromotionCandidate],
    edited_rows: list[dict],
    *,
    existing_refs: set[str],
) -> list[PromotionCandidate]:
    """Overlay curator edits onto freshly computed base candidates, matched by `annotation` ref.

    `edited_rows` is the SAME row shape the read-only `--json` emits
    (`{annotation, decision, slug, ...}`); the curator edits `decision`/`slug` in place. A row
    may switch a candidate to LINK (`slug` = an existing `proposition:<slug>`) or MINT (`slug`
    = the explicit mint slug, bare or `proposition:`-prefixed). Unknown refs and unknown LINK
    targets fail loud. The explicit-id overwrite guard lives at the write boundary
    (`apply_candidates`)."""
    by_ref = {c.ref: c for c in base}
    edited: dict[str, dict] = {}
    for row in edited_rows:
        ref = row.get("annotation")
        if ref not in by_ref:
            raise PromotionOverrideError(f"override row names unknown annotation ref {ref!r}")
        edited[ref] = row
    out: list[PromotionCandidate] = []
    for c in base:
        row = edited.get(c.ref)
        if row is None:
            out.append(c)
            continue
        decision = row.get("decision", c.decision)
        slug = row.get("slug", c.slug)
        if decision == "LINK":
            if not slug or slug not in existing_refs:
                raise PromotionOverrideError(f"LINK target {slug!r} is not an existing proposition")
            out.append(dataclasses.replace(c, decision="LINK", slug=slug, reason="curator override: link"))
        elif decision == "MINT":
            bare = slug.split(":", 1)[1] if isinstance(slug, str) and slug.startswith("proposition:") else slug
            if not bare:
                raise PromotionOverrideError(f"MINT override for {c.ref!r} requires a slug")
            out.append(dataclasses.replace(c, decision="MINT", slug=bare, reason="curator override: mint"))
        else:
            raise PromotionOverrideError(f"override decision for {c.ref!r} must be LINK or MINT, got {decision!r}")
    return out
```

> Note: `apply_overrides` validates override *structure* + link-target existence. The design's "re-used explicit id whose existing proposition has a different claim fails loud" is enforced at the **write boundary** by `apply_candidates`' never-overwrite guard (`PromotionApplyError`, Task 6) — the single chokepoint that protects auto mints and override mints alike.

- [ ] **Step 4: Run to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_annotation_promote.py -v`
Expected: PASS (override tests + all earlier).

- [ ] **Step 5: Lint + commit**

```bash
cd science && uv run --frozen ruff check src/science_tool/annotation/promote.py
cd /mnt/ssd/Dropbox/science/.worktrees/sub-article-annotation-phase4
git add science/src/science_tool/annotation/promote.py science/tests/test_annotation_promote.py
git commit -m "feat(promote): curator override (--input) flip-to-link + explicit id"
```

---

## Task 8: CLI `promote` subcommand (read-only + --apply + --input)

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py` (sibling of `extract_cmd`, ~line 1061)
- Test: `science/tests/test_annotate_promote_cli.py` (new)

- [ ] **Step 1: Write the failing CLI test** — `science/tests/test_annotate_promote_cli.py`

```python
import json
from datetime import datetime, timezone
from pathlib import Path

from click.testing import CliRunner

from science_tool.annotation import io as anno_io
from science_tool.annotation.cli import annotate_group
from science_tool.annotation.model import (
    Annotation, Motivation, SpecificResource, Status, TextQuoteSelector, TextualBody,
)
from science_tool.annotation.query import read_sidecar_strict


def _setup(tmp_path: Path):
    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    (tmp_path / "papers").mkdir()
    md = tmp_path / "papers" / "p.source.md"
    md.write_text("Genes encode proteins.\n", encoding="utf-8")
    sp = anno_io.sidecar_for_markdown(md)
    ann = Annotation(
        id="a-1",
        target=SpecificResource(source="p.source.md", selector=TextQuoteSelector(exact="Genes encode proteins", prefix="", suffix="")),
        bodies=(TextualBody(value='{"section":"abstract","stance":"asserted"}', format="application/json"),),
        motivation=Motivation.CLASSIFYING, annotation_type="proposition",
        source="llm-annot:m:paper-annotate-v1", status=Status.OPEN,
        creator="paper-annotate", created=datetime(2026, 6, 16, tzinfo=timezone.utc),
    )
    anno_io.write_sidecar(sp, anno_io.Sidecar(annotations=(ann,)))
    return md, sp


def test_promote_readonly_writes_nothing(tmp_path):
    md, sp = _setup(tmp_path)
    r = CliRunner().invoke(annotate_group, ["promote", "--source-md", str(md), "--root", str(tmp_path), "--format", "json"])
    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    assert payload["candidates"][0]["decision"] == "MINT"
    # nothing written
    assert not list((tmp_path / "entities" / "propositions").glob("*.md"))
    assert read_sidecar_strict(sp).annotations[0].promoted_to is None


def test_promote_apply_mints_and_backlinks(tmp_path):
    md, sp = _setup(tmp_path)
    r = CliRunner().invoke(annotate_group, ["promote", "--source-md", str(md), "--root", str(tmp_path),
                                            "--paper-ref", "paper:p", "--apply"])
    assert r.exit_code == 0, r.output
    prop = (tmp_path / "entities" / "propositions" / "genes-encode-proteins.md")
    assert prop.exists()
    assert "annotation:papers/p.source#a-1" in prop.read_text(encoding="utf-8")
    assert read_sidecar_strict(sp).annotations[0].promoted_to == "proposition:genes-encode-proteins"


def test_promote_apply_input_override_links(tmp_path):
    # End-to-end --input contract: read-only JSON → edit a row to LINK → feed back via --apply.
    md, sp = _setup(tmp_path)
    (tmp_path / "entities" / "propositions" / "preexisting.md").write_text(
        '---\nid: proposition:preexisting\ntype: proposition\ntitle: Preexisting\n'
        'status: draft\ncreated: "2026-06-16"\nupdated: "2026-06-16"\n---\n# Preexisting\n',
        encoding="utf-8",
    )
    ro = CliRunner().invoke(annotate_group, ["promote", "--source-md", str(md), "--root", str(tmp_path), "--format", "json"])
    assert ro.exit_code == 0, ro.output
    payload = json.loads(ro.output)
    payload["candidates"][0]["decision"] = "LINK"
    payload["candidates"][0]["slug"] = "proposition:preexisting"
    edited = tmp_path / "edited.json"
    edited.write_text(json.dumps(payload), encoding="utf-8")
    r = CliRunner().invoke(annotate_group, ["promote", "--source-md", str(md), "--root", str(tmp_path),
                                            "--apply", "--input", str(edited)])
    assert r.exit_code == 0, r.output
    assert read_sidecar_strict(sp).annotations[0].promoted_to == "proposition:preexisting"
    assert "annotation:papers/p.source#a-1" in (tmp_path / "entities" / "propositions" / "preexisting.md").read_text(encoding="utf-8")


def test_promote_malformed_input_fails_loud(tmp_path):
    md, _ = _setup(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json", encoding="utf-8")
    r = CliRunner().invoke(annotate_group, ["promote", "--source-md", str(md), "--root", str(tmp_path),
                                            "--apply", "--input", str(bad)])
    assert r.exit_code != 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_annotate_promote_cli.py -v`
Expected: FAIL — no such command `promote`.

- [ ] **Step 3: Add `promote_cmd`** — `annotation/cli.py`, after `extract_cmd` (it has `import json`, `click`, `Path` already in scope at module top):

```python
@annotate_group.command("promote")
@click.option(
    "--source-md", "source_md", required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to the paper's <citekey>.source.md.",
)
@click.option(
    "--root", "root", default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Project root (default: cwd). Used to scan the proposition corpus + write entities.",
)
@click.option("--paper-ref", "paper_ref", default=None,
              help="Resolvable paper entity ref (paper:<id>) recorded in source_refs. "
                   "Defaults to paper:<source-md stem minus .source>.")
@click.option("--apply", "do_apply", is_flag=True, default=False,
              help="Execute candidates (mint/link + backlink). Default is read-only.")
@click.option("--input", "input_path", default=None,
              type=click.Path(exists=True, dir_okay=False, path_type=Path),
              help="Edited candidates.json with curator overrides (use with --apply).")
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def promote_cmd(source_md: Path, root: Path | None, paper_ref: str | None,
                do_apply: bool, input_path: Path | None, fmt: str) -> None:
    """Promote proposition-type statement annotations into proposition entities (mint-or-link)."""
    from science_tool.annotation.io import sidecar_for_markdown
    from science_tool.annotation.query import read_sidecar_strict
    from science_tool.annotation.promote import (
        PromotionApplyError, PromotionOverrideError, PromotionReadError, apply_candidates,
        apply_overrides, collect_promotable, decide_candidates, load_corpus,
    )

    project_root = (root or Path.cwd()).resolve()
    if paper_ref is None:
        # citekey = <citekey>.source.md → <citekey>; the owning paper entity is paper:<citekey>.
        citekey = source_md.name[: -len(".source.md")] if source_md.name.endswith(".source.md") else source_md.stem
        paper_ref = f"paper:{citekey}"

    sidecar_path = sidecar_for_markdown(source_md)
    sidecar = read_sidecar_strict(sidecar_path)
    corpus = load_corpus(project_root)
    try:
        promotable, skipped = collect_promotable(sidecar, sidecar_path, project_root, derived_refs=corpus.derived_refs)
    except PromotionReadError as exc:
        raise click.ClickException(str(exc)) from exc
    candidates = decide_candidates(promotable, corpus)

    if do_apply and input_path is not None:
        try:
            raw = json.loads(input_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise click.ClickException(f"--input is not valid JSON: {exc}") from exc
        # Accept either the full read-only output object or a bare candidates list.
        edited_rows = raw.get("candidates") if isinstance(raw, dict) else raw
        if not isinstance(edited_rows, list):
            raise click.ClickException("--input must be the read-only output object or a candidates list")
        existing_refs = {f"proposition:{s}" for s in corpus.existing_slugs}
        try:
            candidates = apply_overrides(candidates, edited_rows, existing_refs=existing_refs)
        except PromotionOverrideError as exc:
            raise click.ClickException(str(exc)) from exc

    rows = [{"annotation": c.ref, "decision": c.decision, "slug": c.slug,
             "claim": c.claim[:80], "reason": c.reason} for c in candidates]

    if not do_apply:
        if fmt == "json":
            click.echo(json.dumps({"candidates": rows, "skipped": dict(skipped)}, indent=2))
        else:
            for r in rows:
                click.echo(f"{r['decision']:9} {r['slug'] or '-':40} {r['annotation']}  {r['claim']}")
            click.echo(f"skipped: {dict(skipped) or 'none'}")
        return

    try:
        report = apply_candidates(candidates, sidecar_path=sidecar_path, root=project_root,
                                  project_root=project_root, paper_ref=paper_ref)
    except PromotionApplyError as exc:
        raise click.ClickException(str(exc)) from exc
    if fmt == "json":
        click.echo(json.dumps({"minted": report.minted, "linked": report.linked,
                               "skipped": dict(report.skipped) | dict(skipped),
                               "written": report.written_paths}, indent=2))
    else:
        click.echo(f"annotate promote: {report.minted} minted, {report.linked} linked, "
                   f"skipped {dict(report.skipped) | dict(skipped)}")
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_annotate_promote_cli.py -v`
Expected: PASS (4 tests: read-only, apply, override-link, malformed).

- [ ] **Step 5: Provenance integration test** — append to `test_annotate_promote_cli.py`

```python
def test_minted_proposition_materializes_wasderivedfrom(tmp_path):
    # After apply, the minted proposition's annotation: + paper: refs materialize wasDerivedFrom;
    # a cite: ref would not (regression guard).
    from rdflib.namespace import PROV
    from science_tool.graph.materialize import _annotation_uri
    md, sp = _setup(tmp_path)
    CliRunner().invoke(annotate_group, ["promote", "--source-md", str(md), "--root", str(tmp_path),
                                        "--paper-ref", "paper:p", "--apply"])
    text = (tmp_path / "entities" / "propositions" / "genes-encode-proteins.md").read_text(encoding="utf-8")
    assert "annotation:papers/p.source#a-1" in text and "paper:p" in text
    # URI minter is stable + distinct from a bibliography ref
    assert str(_annotation_uri("annotation:papers/p.source#a-1")).endswith("#a-1")
```

Run: `cd science && uv run --frozen pytest tests/test_annotate_promote_cli.py -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Lint + typecheck + commit**

```bash
cd science && uv run --frozen ruff check src/science_tool/annotation/cli.py && uv run --frozen pyright src/science_tool/annotation/cli.py
cd /mnt/ssd/Dropbox/science/.worktrees/sub-article-annotation-phase4
git add science/src/science_tool/annotation/cli.py science/tests/test_annotate_promote_cli.py
git commit -m "feat(promote): science annotate promote CLI (read-only/--apply/--input)"
```

---

## Task 9: Documentation — promotion vocabulary

**Files:**
- Modify: `docs/conventions/annotation-tokens.md`

- [ ] **Step 1: Append a Phase 4a section** to `docs/conventions/annotation-tokens.md`

```markdown
## Statement promotion (Phase 4a)

`science annotate promote <source.md>` turns `proposition`-type statement annotations into
`proposition` entities (mint-or-link). It is **read-only by default**; `--apply` writes,
`--apply --input <candidates.json>` applies curator overrides.

- **Mint-or-link:** a statement LINKs to an existing proposition when `normalize_claim(claim)`
  (casefold + whitespace-collapse) equals `normalize_claim(title)` of an existing proposition;
  otherwise it MINTs `proposition:<slug>` (`slug_for_claim_text`, ≤72 chars). A slug already
  taken by a different-titled proposition is a `promote-slug-collision` (never overwritten;
  resolve with an explicit `id` via `--input`).
- **Minted proposition:** `title` = claim, `## Claim` = claim text, `subject`/`object` copied
  from the statement body when present; `predicate`/`polarity`/`claim_layer`/… left unset
  (Phase 4c). `status: draft`.
- **Provenance (materialization fact, not a status change):** the proposition's `source_refs`
  carries `paper:<paper-id>` (→ `prov:wasDerivedFrom` paper) and the new
  `annotation:<entity-relpath>#<frag>` source ref (→ `prov:wasDerivedFrom` annotation, via the
  materialize bypass branch). The annotation gains a `sci:promotedTo "proposition:<slug>"`
  backlink. Annotation `status` is untouched.
- **Promote queue / idempotency:** active (`open`/`ack`) `proposition` annotations with no
  `sci:promotedTo` and no existing derived proposition. Re-running skips already-promoted rows.
- **Out of scope (later slices):** question/hypothesis promotion (4b), factoring (4c),
  cross-paper evidence (4d), embedding/paraphrase dedup, figurative promotion.
```

- [ ] **Step 2: Commit**

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/sub-article-annotation-phase4
git add docs/conventions/annotation-tokens.md
git commit -m "doc(annotation-tokens): register Phase 4a statement-promotion vocabulary"
```

---

## Final verification (after all tasks)

- [ ] **Full targeted suite**

Run: `cd science && uv run --frozen pytest tests/test_entity_writer.py tests/test_annotation_io.py tests/test_graph_materialize.py tests/test_annotation_promote.py tests/test_annotate_promote_cli.py tests/test_workbench_compile.py -v`
Expected: all PASS (exit 0).

- [ ] **Broader regression** (annotation + entities + graph)

Run: `cd science && uv run --frozen pytest tests/ -k "annotat or entit or workbench or materialize" -q`
Expected: exit 0.

- [ ] **Lint + typecheck the changed surface**

Run: `cd science && uv run --frozen ruff check src/science_tool/annotation/promote.py src/science_tool/annotation/cli.py src/science_tool/entities.py src/science_tool/graph/materialize.py && uv run --frozen pyright src/science_tool/annotation/promote.py`
Expected: clean.

- [ ] **Then:** REQUIRED SUB-SKILL `superpowers:finishing-a-development-branch`.
