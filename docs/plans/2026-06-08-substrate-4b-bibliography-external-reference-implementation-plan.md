# Substrate Phase 4b — Bibliography External-Reference Resolver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `papers/references.bib` the local identity authority for `paper:<citekey>` so the aggregate manifest's bibliographic deprecated-owner rows retire without breaking citations — the first real consumer of `ParticipationMode.EXTERNAL_REFERENCE`.

**Architecture:** A `BibAdapter` synthesizes in-memory lightweight `paper:<citekey>` `Entity` objects from the bib (never authored to disk) and tags their identity rows `external-reference`. That single move makes citations resolve (normal entity presence), keeps a metadata-bearing graph node per cited paper, and keeps the migrator/conformance from ever owning/renumbering them. The retirement executor gains a `--retire-external-refs` action that drops aggregate `paper`/`article` rows whose citekey the bib backs, and rejects un-backed ones.

**Tech Stack:** Python 3.13, pydantic v2 (`PaperEntity`), rdflib, click, pytest, `uv`. Work from `~/d/science/science`. Design doc: `~/d/science/docs/plans/2026-06-08-substrate-4b-bibliography-external-reference-design.md`.

---

## Orientation (read before Task 1)

**Where things live (verified file:line):**
- `bibliography.py` — `papers/references.bib` helpers: `load_bib_keys` (regex-only key set, `:35`), `_BIBTEX_ENTRY_RE` (`:13`), `_entry_span` (balanced-brace whole-entry matcher, `:101`). You will ADD `BibEntry` + `load_bib_entries` here.
- `graph/storage_adapters/base.py` — `StorageAdapter` ABC (`name: str` at `:26`). You will ADD a `participation_mode` class attribute.
- `graph/storage_adapters/aggregate.py` — the closest adapter template (`discover`/`load_raw`, `SourceRef(adapter_name=…, path=…, line=…)`). You will CREATE a sibling `bib.py`.
- `graph/identity_table.py` — `ParticipationMode` enum (OWNER/BORROWER/EXTERNAL_REFERENCE, `:19`), `IdentityDeclaration` (`:27`), `IdentityTable.owners()` (OWNER-only, `:65`), `classify_owner_scope(adapter, *, project_name)` (`:97`), `build_identity_table` (`:119`). You will ADD a `"bib"` case to `classify_owner_scope`.
- `graph/sources.py` — `load_project_sources`: adapters list (`:267–291`), the load loop, the `classify_owner_scope` call (`:413`), the `DatapackageAdapter` defer template (`:414`), and the `IdentityDeclaration(... participation_mode=ParticipationMode.OWNER ...)` emit (`:429–437`). You will register `BibAdapter`, replace the hardcoded OWNER, and add a bib defer.
- `graph/materialize.py` — `_add_entity` (`:236`, emits `skos:prefLabel`=title already), `_build_dataset_from_sources` (`:78`), `_entity_uri` (`:1059`), `SCI_NS`, `PROJECT_NS`; `DCTERMS_NS`/`DCAT_NS` imported from `graph.io` (`:64`). You will ADD a `kind == "paper"` metadata branch.
- `graph/aggregate_retire.py` — `plan_retirement` (`:99`), the bucket dispatch loop (`:122–160`), `RetireAction` (`:31`), `apply_retirement` (`:230`). You will ADD an `external-ref` branch + `retire_external_refs`/`bib_keys` params.
- `graph/aggregate_triage.py` — the classifier; `EXTERNAL_REF` bucket = `kind == "article"` OR source ends `.bib` (`:56`). **No change needed** — it already buckets these rows.
- `cli.py` — `entities triage-aggregate` (`:293–417`): flags, `any_bucket` (`:325`), v3 gate (`:362–372`), `plan_retirement`/`apply_retirement` call (`:380–390`). You will ADD `--retire-external-refs`.
- `model/src/science_model/entities.py` — `PaperEntity(ProjectEntity)` (`:542`) already carries `bibkey`/`year: int|None`/`doi: str`/`url: str`; registry maps `"paper"` → `PaperEntity` (`graph/entity_registry.py:118`). **No schema change needed.**

**Tooling:**
- Single test: `uv run --frozen pytest tests/path/test_x.py::test_y -v`
- Full suite (project default deselects `snapshot`/`real_projects`): `uv run --frozen pytest`
- Lint (run on touched files before each commit): `uv run --frozen ruff check <files> && uv run --frozen ruff format <files>` (120-char limit).
- Use `uv`, never `pip`. Two pre-existing `snapshot`-marked formatter-fixture failures and ~174 baseline ruff errors in untouched files are NOT yours — ignore them; only ensure files you touch are clean.

**Test fixture idiom** (from `tests/graph/test_aggregate_retire_terms.py`): a `science.yaml` manifest `name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n`, aggregate rows under `knowledge/sources/local/{entities,terms}.yaml`, loaded with `load_project_sources(root, include_commons=False, strict_core_schema=False, strict_identity=False)`.

**TDD discipline:** every task writes the failing test FIRST, runs it to confirm the expected failure, implements the minimal change, reruns to green, then commits. Do not batch.

---

## Task 1: `load_bib_entries` — balanced-entry reader with brace-depth field parsing

Adds the bib reader the BibAdapter (Task 3) and the retirement gate (Task 7) both consume. The key invariant: a returned key ⟺ a node-producing entry — so retirement only drops an aggregate row when a replacement external-reference node provably exists. Two things break a naive reader, both handled here:
- **Brace balance** — only `_entry_span`-balanced entries are admitted (`load_bib_keys` would wrongly return keys from truncated entries).
- **Schema-loadability** — the synthesized `PaperEntity` must validate, or `load_project_sources` skips it (`sources.py:355`) and no node is produced. The only constrained field is `year` (`PaperEntity.year` is `ge=1800, le=2200`, `model/src/science_model/entities.py:547`). So `load_bib_entries` **clamps `year` to `None` when it is not a 4-digit integer in `[1800, 2200]`** — the parsed metadata can never make the synthesized entity fail validation, keeping key ⟺ node true by construction. (All other parsed fields are unconstrained strings.)

**Files:**
- Modify: `src/science_tool/bibliography.py` (add after `load_bib_author_surnames`, before the `BibAddResult` dataclass at `:84`)
- Test: `tests/test_bibliography_entries.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_bibliography_entries.py
from __future__ import annotations

from pathlib import Path

from science_tool.bibliography import BibEntry, load_bib_entries


def _write_bib(root: Path, text: str) -> None:
    (root / "papers").mkdir(parents=True, exist_ok=True)
    (root / "papers" / "references.bib").write_text(text, encoding="utf-8")


def test_load_bib_entries_parses_fields_and_gates_on_balance(tmp_path: Path) -> None:
    _write_bib(
        tmp_path,
        "@article{Smith2024,\n"
        "  title = {The {DNA} story},\n"   # nested braces must NOT truncate
        "  year = {2024},\n"
        "  doi = {10.1/x},\n"
        "}\n\n"
        "@article{Broken2020,\n"
        "  title = {Truncated without a close brace\n",  # unbalanced -> excluded
    )
    entries = load_bib_entries(tmp_path)
    assert isinstance(entries["Smith2024"], BibEntry)
    assert entries["Smith2024"].title == "The {DNA} story"
    assert entries["Smith2024"].year == 2024
    assert entries["Smith2024"].doi == "10.1/x"
    assert entries["Smith2024"].url is None  # absent field -> None
    assert "Broken2020" not in entries  # unbalanced entry contributes no key


def test_load_bib_entries_quoted_and_bare_forms(tmp_path: Path) -> None:
    _write_bib(
        tmp_path,
        '@article{Jones2019,\n  title = "Quoted Title",\n  year = 2019,\n}\n',
    )
    assert load_bib_entries(tmp_path)["Jones2019"].title == "Quoted Title"
    assert load_bib_entries(tmp_path)["Jones2019"].year == 2019


def test_load_bib_entries_out_of_range_year_clamped_to_none(tmp_path: Path) -> None:
    # PaperEntity.year is ge=1800/le=2200. A balanced entry with an out-of-range
    # year must STILL be admitted (it is node-producing) but with year=None, so the
    # synthesized PaperEntity validates and the "backed" invariant holds.
    _write_bib(tmp_path, "@article{Old1600,\n  title = {Ancient},\n  year = {1600},\n}\n")
    entries = load_bib_entries(tmp_path)
    assert "Old1600" in entries  # still backed (node-producing)
    assert entries["Old1600"].year is None  # clamped, cannot break validation


def test_load_bib_entries_absent_file_is_empty(tmp_path: Path) -> None:
    assert load_bib_entries(tmp_path) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_bibliography_entries.py -v`
Expected: FAIL with `ImportError: cannot import name 'BibEntry'`.

- [ ] **Step 3: Write minimal implementation**

Add to `src/science_tool/bibliography.py` (the `@dataclass` and `re` are already imported at the top of the file):

```python
@dataclass(frozen=True)
class BibEntry:
    """One balanced bibliography entry — the subset Phase 4b materializes."""

    key: str
    title: str | None = None
    year: int | None = None
    doi: str | None = None
    url: str | None = None


def _field_value(entry_text: str, field: str) -> str | None:
    """Extract a BibTeX field value from a single entry block, brace-aware.

    Handles the brace form ``field = {The {DNA} story}`` (matched by depth so
    nested braces do not truncate), the quoted form ``field = "..."``, and the
    bare form ``field = 2024``. Returns None when the field is absent.
    """
    match = re.search(r"\b" + re.escape(field) + r"\s*=\s*", entry_text, re.IGNORECASE)
    if not match:
        return None
    i = match.end()
    if i >= len(entry_text):
        return None
    if entry_text[i] == "{":
        depth = 0
        for j in range(i, len(entry_text)):
            if entry_text[j] == "{":
                depth += 1
            elif entry_text[j] == "}":
                depth -= 1
                if depth == 0:
                    return entry_text[i + 1 : j].strip()
        return None  # unbalanced field value
    if entry_text[i] == '"':
        close = entry_text.find('"', i + 1)
        return entry_text[i + 1 : close].strip() if close != -1 else None
    bare = re.match(r"([^,\n}]*)", entry_text[i:])
    value = bare.group(1).strip() if bare else ""
    return value or None


def load_bib_entries(project_root: Path) -> dict[str, "BibEntry"]:
    """Parse ``papers/references.bib`` into balanced entries keyed by citekey.

    Only entries whose braces balance (via ``_entry_span``) are admitted, so the
    returned key set is exactly the set of entries that produce a real
    external-reference node — the invariant the retirement backed/un-backed test
    relies on. A truncated entry contributes no key. Missing fields are None.
    """
    bib_path = project_root / "papers" / "references.bib"
    if not bib_path.is_file():
        return {}
    text = bib_path.read_text(encoding="utf-8")
    entries: dict[str, BibEntry] = {}
    for match in _BIBTEX_ENTRY_RE.finditer(text):
        key = match.group(1)
        span = _entry_span(text, key)
        if span is None:
            continue  # unbalanced/truncated — cannot be "backed", excluded
        block = text[span[0] : span[1]]
        year_raw = _field_value(block, "year")
        # Clamp to None unless it is a valid PaperEntity.year (ge=1800, le=2200).
        # This guarantees the synthesized PaperEntity validates, so a returned key
        # always yields a node (the retirement "backed" invariant).
        year = int(year_raw) if year_raw is not None and year_raw.isdigit() and 1800 <= int(year_raw) <= 2200 else None
        entries[key] = BibEntry(
            key=key,
            title=_field_value(block, "title"),
            year=year,
            doi=_field_value(block, "doi"),
            url=_field_value(block, "url"),
        )
    return entries
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_bibliography_entries.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
uv run --frozen ruff check src/science_tool/bibliography.py tests/test_bibliography_entries.py
uv run --frozen ruff format src/science_tool/bibliography.py tests/test_bibliography_entries.py
git add src/science_tool/bibliography.py tests/test_bibliography_entries.py
git commit -m "feat(substrate-4b): load_bib_entries balanced-entry reader (title/year/doi/url)"
```

---

## Task 2: `participation_mode` attribute on `StorageAdapter`

Lets the load loop read a per-adapter participation mode instead of hardcoding OWNER. Default OWNER keeps every existing adapter behavior-identical.

**Files:**
- Modify: `src/science_tool/graph/storage_adapters/base.py`
- Test: `tests/graph/test_storage_adapter_participation.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/graph/test_storage_adapter_participation.py
from __future__ import annotations

from science_tool.graph.identity_table import ParticipationMode
from science_tool.graph.storage_adapters.base import StorageAdapter


def test_storage_adapter_default_participation_mode_is_owner() -> None:
    assert StorageAdapter.participation_mode is ParticipationMode.OWNER
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/graph/test_storage_adapter_participation.py -v`
Expected: FAIL with `AttributeError: type object 'StorageAdapter' has no attribute 'participation_mode'`.

- [ ] **Step 3: Write minimal implementation**

In `src/science_tool/graph/storage_adapters/base.py`, add the import and the class attribute:

```python
from science_tool.graph.identity_table import ParticipationMode
```

and inside `class StorageAdapter(ABC):`, directly under `name: str  # ...`:

```python
    # Default participation: an adapter declares owner rows. Subclasses that
    # contribute borrower/external-reference rows override this (design §B3/§C3).
    participation_mode: ParticipationMode = ParticipationMode.OWNER
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/graph/test_storage_adapter_participation.py -v`
Expected: 1 passed. (If an `ImportError`/circular-import surfaces, `identity_table` imports only `science_model.source_ref`, so importing it from `base` is acyclic — rerun; the error would be elsewhere.)

- [ ] **Step 5: Commit**

```bash
uv run --frozen ruff check src/science_tool/graph/storage_adapters/base.py tests/graph/test_storage_adapter_participation.py
uv run --frozen ruff format src/science_tool/graph/storage_adapters/base.py tests/graph/test_storage_adapter_participation.py
git add src/science_tool/graph/storage_adapters/base.py tests/graph/test_storage_adapter_participation.py
git commit -m "feat(substrate-4b): StorageAdapter.participation_mode (default OWNER)"
```

---

## Task 3: `BibAdapter` — synthesize `paper:<citekey>` records from the bib

A read-only adapter that turns each balanced bib entry into a `kind: paper` raw record. Declares `participation_mode = EXTERNAL_REFERENCE` (consumed in Task 5).

**Files:**
- Create: `src/science_tool/graph/storage_adapters/bib.py`
- Test: `tests/graph/test_bib_adapter.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/graph/test_bib_adapter.py
from __future__ import annotations

from pathlib import Path

from science_tool.graph.identity_table import ParticipationMode
from science_tool.graph.storage_adapters.bib import BibAdapter


def _write_bib(root: Path, text: str) -> None:
    (root / "papers").mkdir(parents=True, exist_ok=True)
    (root / "papers" / "references.bib").write_text(text, encoding="utf-8")


def test_bib_adapter_declares_external_reference() -> None:
    assert BibAdapter.participation_mode is ParticipationMode.EXTERNAL_REFERENCE
    assert BibAdapter.name == "bib"


def test_bib_adapter_discovers_and_loads(tmp_path: Path) -> None:
    _write_bib(
        tmp_path,
        "@article{Smith2024,\n  title = {Cells},\n  year = {2024},\n  doi = {10.1/x},\n}\n",
    )
    adapter = BibAdapter()
    refs = adapter.discover(tmp_path)
    assert [r.line for r in refs] == [0]
    assert refs[0].path == "papers/references.bib"
    raw = adapter.load_raw(refs[0])
    assert raw["kind"] == "paper"
    assert raw["id"] == "paper:Smith2024"
    assert raw["title"] == "Cells"
    assert raw["bibkey"] == "Smith2024"
    assert raw["year"] == 2024
    assert raw["doi"] == "10.1/x"


def test_bib_adapter_title_falls_back_to_key(tmp_path: Path) -> None:
    _write_bib(tmp_path, "@misc{NoTitle2000,\n  year = {2000},\n}\n")
    adapter = BibAdapter()
    raw = adapter.load_raw(adapter.discover(tmp_path)[0])
    assert raw["title"] == "NoTitle2000"


def test_bib_adapter_absent_bib_is_empty(tmp_path: Path) -> None:
    assert BibAdapter().discover(tmp_path) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/graph/test_bib_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.graph.storage_adapters.bib'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/science_tool/graph/storage_adapters/bib.py
"""BibAdapter — the project bibliography (`papers/references.bib`) as an
external-reference authority (design §B2/§B3a/§C3, Phase 4b).

Synthesizes a lightweight `paper:<citekey>` raw record per balanced bib entry.
These are external references, not owners: the load loop tags their identity rows
ParticipationMode.EXTERNAL_REFERENCE (never renumbered, never a collision) and the
materializer emits a minimal metadata node so citation edges resolve. No `dump`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from science_model.source_ref import SourceRef

from science_tool.bibliography import BibEntry, load_bib_entries
from science_tool.graph.identity_table import ParticipationMode
from science_tool.graph.storage_adapters.base import StorageAdapter

_BIB_REL = "papers/references.bib"


class BibAdapter(StorageAdapter):
    """Reads `papers/references.bib` into external-reference paper records."""

    name = "bib"
    participation_mode = ParticipationMode.EXTERNAL_REFERENCE

    def __init__(self) -> None:
        self._entries: dict[str, BibEntry] = {}
        self._keys_by_line: list[str] = []

    def discover(self, project_root: Path) -> list[SourceRef]:
        self._entries = load_bib_entries(project_root)
        self._keys_by_line = list(self._entries)  # insertion order = bib file order
        return [SourceRef(adapter_name=self.name, path=_BIB_REL, line=i) for i in range(len(self._keys_by_line))]

    def load_raw(self, ref: SourceRef) -> dict[str, Any]:
        assert ref.line is not None, "BibAdapter SourceRef must carry line (entry index)"
        entry = self._entries[self._keys_by_line[ref.line]]
        raw: dict[str, Any] = {
            "kind": "paper",
            "id": f"paper:{entry.key}",
            "title": entry.title or entry.key,
            "bibkey": entry.key,
            "file_path": _BIB_REL,
        }
        if entry.year is not None:
            raw["year"] = entry.year
        if entry.doi:
            raw["doi"] = entry.doi
        if entry.url:
            raw["url"] = entry.url
        return raw
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/graph/test_bib_adapter.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
uv run --frozen ruff check src/science_tool/graph/storage_adapters/bib.py tests/graph/test_bib_adapter.py
uv run --frozen ruff format src/science_tool/graph/storage_adapters/bib.py tests/graph/test_bib_adapter.py
git add src/science_tool/graph/storage_adapters/bib.py tests/graph/test_bib_adapter.py
git commit -m "feat(substrate-4b): BibAdapter synthesizes paper:<citekey> external-reference records"
```

---

## Task 4: `classify_owner_scope` — `bib` scope

External-reference rows carry an `owner_scope` naming the authority (`"bib"`), non-deprecated.

**Files:**
- Modify: `src/science_tool/graph/identity_table.py:97-112`
- Test: `tests/graph/test_identity_table.py` (append) — or create `tests/graph/test_classify_owner_scope_bib.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/graph/test_classify_owner_scope_bib.py
from __future__ import annotations

from science_tool.graph.identity_table import classify_owner_scope


def test_classify_owner_scope_bib_is_non_deprecated_authority() -> None:
    assert classify_owner_scope("bib", project_name="demo") == ("bib", False)


def test_classify_owner_scope_markdown_unchanged() -> None:
    assert classify_owner_scope("markdown", project_name="demo") == ("demo", False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/graph/test_classify_owner_scope_bib.py -v`
Expected: FAIL — `test_..._bib_...` asserts `("bib", False)` but the current function returns `("demo", False)` (the default branch).

- [ ] **Step 3: Write minimal implementation**

In `src/science_tool/graph/identity_table.py`, inside `classify_owner_scope`, add the `bib` case right after the `commons-merged` check (`:105-106`):

```python
    if adapter == "commons-merged":
        return (_COMMONS_SCOPE, False)
    if adapter == "bib":
        # External-reference authority scope (design §B3): bib rows are never
        # owners, so this scope only labels provenance; it is non-deprecated.
        return ("bib", False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/graph/test_classify_owner_scope_bib.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
uv run --frozen ruff check src/science_tool/graph/identity_table.py tests/graph/test_classify_owner_scope_bib.py
uv run --frozen ruff format src/science_tool/graph/identity_table.py tests/graph/test_classify_owner_scope_bib.py
git add src/science_tool/graph/identity_table.py tests/graph/test_classify_owner_scope_bib.py
git commit -m "feat(substrate-4b): classify_owner_scope recognizes the bib authority scope"
```

---

## Task 5: Wire `BibAdapter` into the load loop — activate external references

The integration that lights up the feature: register the adapter (after AggregateAdapter), emit each adapter's own participation mode, and add the defer guard so a transitional aggregate-stub + bib pair never collides under strict load.

**Files:**
- Modify: `src/science_tool/graph/sources.py` (adapters list `:267-291`; the emit + defer near `:413-437`)
- Test: `tests/graph/test_bib_external_reference_load.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/graph/test_bib_external_reference_load.py
from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.identity_table import ParticipationMode, build_identity_table
from science_tool.graph.reference_resolution import ReferenceResolver
from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n"


def _write(root: Path, *, bib: str | None = None, entities: list[dict] | None = None) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    if bib is not None:
        (root / "papers").mkdir(parents=True, exist_ok=True)
        (root / "papers" / "references.bib").write_text(bib, encoding="utf-8")
    if entities is not None:
        src = root / "knowledge" / "sources" / "local"
        src.mkdir(parents=True, exist_ok=True)
        (src / "entities.yaml").write_text(yaml.safe_dump({"entities": entities}), encoding="utf-8")


def _load(root: Path, *, strict_identity: bool = False, include_commons: bool = False):
    return load_project_sources(
        root, include_commons=include_commons, strict_core_schema=False, strict_identity=strict_identity
    )


def test_bib_paper_is_external_reference_and_resolves(tmp_path: Path) -> None:
    _write(tmp_path, bib="@article{Smith2024,\n  title = {Cells},\n  year = {2024},\n}\n")
    sources = _load(tmp_path)
    table = build_identity_table(sources)
    rows = [r for r in table.rows if r.canonical_id == "paper:Smith2024"]
    assert rows, "bib paper produced no identity row"
    assert all(r.participation_mode is ParticipationMode.EXTERNAL_REFERENCE for r in rows)
    assert ("bib", "paper:Smith2024") not in table.owners()  # external ref is not an owner
    resolver = ReferenceResolver.from_entities(sources.entities, identity_table=table)
    assert resolver.resolve("paper:Smith2024").status == "resolved"


def test_bib_defers_to_aggregate_stub_under_strict_load(tmp_path: Path) -> None:
    # entities.yaml owns paper:Smith2024 (aggregate, deprecated) AND the bib has it.
    # Strict load must NOT raise; the bib defers, leaving a single (aggregate) owner.
    _write(
        tmp_path,
        bib="@article{Smith2024,\n  title = {Cells},\n}\n",
        entities=[{"canonical_id": "article:Smith2024", "kind": "article", "title": "S"}],
    )
    sources = _load(tmp_path, strict_identity=True)  # would raise if bib emitted a 2nd declaration
    rows = [r for r in build_identity_table(sources).rows if r.canonical_id == "paper:Smith2024"]
    assert rows and all(r.participation_mode is ParticipationMode.OWNER for r in rows)
    assert all(r.adapter == "aggregate" for r in rows)  # the aggregate stub won; bib deferred


def test_bib_entry_with_out_of_range_year_still_loads_as_entity(tmp_path: Path) -> None:
    # A balanced entry with an out-of-range year (clamped to None by load_bib_entries)
    # must still produce a loadable PaperEntity — proving the "backed -> node" invariant
    # survives schema validation, not just brace balance.
    _write(tmp_path, bib="@article{Old1600,\n  title = {Ancient},\n  year = {1600},\n}\n")
    sources = _load(tmp_path)
    ent = next((e for e in sources.entities if e.canonical_id == "paper:Old1600"), None)
    assert ent is not None, "out-of-range-year bib entry failed to synthesize a node"
    assert ent.kind == "paper"


def test_bib_paper_loads_under_default_commons_path(tmp_path: Path) -> None:
    # SMOKE TEST ONLY: the default include_commons=True load path works (no crash, the
    # bib paper is an external reference). This fixture references no commons ids and
    # declares no commons owner, so the commons resolver is a no-op — it does NOT
    # exercise the stated bib-vs-commons-owner precedence. That precedence (local bib
    # wins materialization; commons owner row still recorded) is verified in the final
    # holistic review against a project with a real commons paper owner.
    _write(tmp_path, bib="@article{Smith2024,\n  title = {Cells},\n}\n")
    sources = _load(tmp_path, include_commons=True)
    table = build_identity_table(sources)
    rows = [r for r in table.rows if r.canonical_id == "paper:Smith2024"]
    assert rows and all(r.participation_mode is ParticipationMode.EXTERNAL_REFERENCE for r in rows)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/graph/test_bib_external_reference_load.py -v`
Expected: FAIL — `test_bib_paper_is_external_reference_and_resolves` finds no `paper:Smith2024` row (BibAdapter not registered).

- [ ] **Step 3: Write minimal implementation**

In `src/science_tool/graph/sources.py`:

(a) Import `BibAdapter` near the other adapter imports (top of file, beside `from science_tool.graph.storage_adapters... import ...`):

```python
from science_tool.graph.storage_adapters.bib import BibAdapter
```

(b) Register it in the `adapters` list (`:267-291`), **after** `AggregateAdapter(local_profile=local_profile)`:

```python
        AggregateAdapter(local_profile=local_profile),
        BibAdapter(),
        DatapackageAdapter(),
```

(c) Replace the hardcoded participation mode in the `IdentityDeclaration(...)` emit (`:431`):

```python
                identity_declarations.append(
                    IdentityDeclaration(
                        canonical_id=entity.canonical_id,
                        participation_mode=adapter.participation_mode,
                        owner_scope=owner_scope,
                        adapter=adapter.name,
                        source_ref=ref,
                        deprecated=deprecated,
                    )
                )
```

(d) Add the bib defer guard immediately after the `DatapackageAdapter` defer block (right after `:413` `owner_scope, deprecated = classify_owner_scope(...)`, alongside the existing `if isinstance(adapter, DatapackageAdapter) ...` at `:414`):

```python
                if isinstance(adapter, BibAdapter) and entity.canonical_id in identity_table:
                    # Already declared this load (a real owner OR an aggregate stub):
                    # the bib is an authority, not a competing declaration, so it
                    # DEFERS (mirrors the §B4 datapackage defer). No second row, no
                    # duplicate entity, no collision under strict load. The owner ->
                    # external-reference flip happens automatically on the next load
                    # once 4b retirement drops the aggregate stub.
                    continue
```

- [ ] **Step 4: Run the new test, then the full suite**

Run: `uv run --frozen pytest tests/graph/test_bib_external_reference_load.py -v`
Expected: 4 passed.

Run: `uv run --frozen pytest`
Expected: all pass. **Watch for a regression** in any fixture that ships a `papers/references.bib`: those projects now load extra `paper:` entities. If a previously-passing test asserts an exact entity/row count or a "no such entity" condition for a paper id, that is a real interaction of this task — inspect whether the fixture intends a bib; do not silence it by reverting the wiring. (Most fixtures have no `papers/references.bib`, so `discover` returns `[]` and they are unaffected.)

- [ ] **Step 5: Commit**

```bash
uv run --frozen ruff check src/science_tool/graph/sources.py tests/graph/test_bib_external_reference_load.py
uv run --frozen ruff format src/science_tool/graph/sources.py tests/graph/test_bib_external_reference_load.py
git add src/science_tool/graph/sources.py tests/graph/test_bib_external_reference_load.py
git commit -m "feat(substrate-4b): wire BibAdapter into load loop (external-ref rows + defer)"
```

---

## Task 6: Minimal paper metadata node in materialization

`_add_entity` already emits `skos:prefLabel`=title for every entity (so a paper node and its title exist). This task adds the cheap bib metadata (`year`/`doi`/`url`) so citation edges land on an inspectable, metadata-bearing node. The branch keys on `kind == "paper"` (it cannot see participation mode) and emits only present fields — additive and harmless on the rare owned/commons paper entity.

**Files:**
- Modify: `src/science_tool/graph/materialize.py` (in `_add_entity`, after the dataset `license` branch at `:259-260`, before `source_uri = _source_uri(...)` at `:262`)
- Test: `tests/graph/test_paper_node_metadata.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/graph/test_paper_node_metadata.py
from __future__ import annotations

from pathlib import Path

from rdflib import Literal
from rdflib import URIRef
from rdflib.namespace import PROV, RDF, SKOS

from science_tool.graph.io import DCAT_NS, DCTERMS_NS
from science_tool.graph.materialize import PROJECT_NS, SCI_NS, _build_dataset_from_sources, _entity_uri
from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n"


def _write(root: Path, bib: str) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    (root / "papers").mkdir(parents=True, exist_ok=True)
    (root / "papers" / "references.bib").write_text(bib, encoding="utf-8")


def test_paper_node_carries_bib_metadata(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "@article{Smith2024,\n  title = {Cells},\n  year = {2024},\n  doi = {10.1/x},\n  url = {https://ex/x},\n}\n",
    )
    sources = load_project_sources(
        tmp_path, include_commons=False, strict_core_schema=False, strict_identity=False
    )
    ds = _build_dataset_from_sources(sources)
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    uri = _entity_uri("paper:Smith2024")
    assert (uri, SKOS.prefLabel, Literal("Cells")) in knowledge          # title (pre-existing path)
    assert (uri, RDF.type, PROV.Entity) in knowledge                     # NEW: reference/provenance typing
    assert (uri, DCTERMS_NS.date, Literal("2024")) in knowledge          # NEW: year
    assert (uri, SCI_NS.doi, Literal("10.1/x")) in knowledge             # NEW: doi
    assert (uri, DCAT_NS.downloadURL, URIRef("https://ex/x")) in knowledge  # NEW: url (design surface)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/graph/test_paper_node_metadata.py -v`
Expected: FAIL — the `prefLabel`/title assertion passes, but the `prov:Entity` type and the `DCTERMS_NS.date` / `SCI_NS.doi` / `DCAT_NS.downloadURL` triples are absent.

- [ ] **Step 3: Write minimal implementation**

In `src/science_tool/graph/materialize.py`, inside `_add_entity`, after the dataset `license` block (`:259-260`) and before `source_uri = _source_uri(entity.file_path)` (`:262`):

```python
    if entity.kind == "paper":
        # Phase 4b: a paper is a bibliographic external reference. The node already
        # carries its kind-class rdf:type and skos:prefLabel=title from the shared
        # path above; mark it additionally as prov:Entity (a reference/provenance
        # node, per the design) and add the thin bib surface (year/doi/url, only
        # when present) so citation/evidence edges land on an inspectable node.
        knowledge.add((uri, RDF.type, PROV.Entity))
        year = getattr(entity, "year", None)
        if year:
            knowledge.add((uri, DCTERMS_NS.date, Literal(str(year))))
        doi = getattr(entity, "doi", "") or ""
        if doi:
            knowledge.add((uri, SCI_NS.doi, Literal(doi)))
        url = getattr(entity, "url", "") or ""
        if url:
            knowledge.add((uri, DCAT_NS.downloadURL, URIRef(url)))
```

(All namespaces used are already imported in `materialize.py`: `DCTERMS_NS`/`DCAT_NS` at `:64`, `PROV`/`RDF`/`SKOS` at `:12`, `URIRef`/`Literal` at `:11`; `SCI_NS` and `knowledge` are in scope.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/graph/test_paper_node_metadata.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
uv run --frozen ruff check src/science_tool/graph/materialize.py tests/graph/test_paper_node_metadata.py
uv run --frozen ruff format src/science_tool/graph/materialize.py tests/graph/test_paper_node_metadata.py
git add src/science_tool/graph/materialize.py tests/graph/test_paper_node_metadata.py
git commit -m "feat(substrate-4b): emit minimal bib metadata (year/doi/url) on paper nodes"
```

---

## Task 7: External-ref retirement action in `plan_retirement`

Adds the bucket action: an `external-ref` row whose citekey the bib backs is dropped; an un-backed one is rejected/retained. The planner takes the backed key set as an explicit parameter (the CLI computes it in Task 8) so this is unit-testable without an on-disk bib.

**Files:**
- Modify: `src/science_tool/graph/aggregate_retire.py` (`plan_retirement` signature `:99-109`; the dispatch loop `:122-160`)
- Test: `tests/graph/test_aggregate_retire_external_ref.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/graph/test_aggregate_retire_external_ref.py
from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.aggregate_retire import apply_retirement, plan_retirement
from science_tool.graph.aggregate_triage import classify_aggregate_rows
from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n"
_ENT_REL = "knowledge/sources/local/entities.yaml"


def _write(root: Path, entities: list[dict]) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    src = root / "knowledge" / "sources" / "local"
    src.mkdir(parents=True, exist_ok=True)
    (src / "entities.yaml").write_text(yaml.safe_dump({"entities": entities}), encoding="utf-8")


def _plan_apply(root: Path, **flags):
    sources = load_project_sources(
        root, include_commons=False, strict_core_schema=False, strict_identity=False
    )
    plan = plan_retirement(
        root,
        sources,
        classify_aggregate_rows(sources),
        promote_coined=False,
        delete_cruft=False,
        delete_shadow=False,
        **flags,
    )
    return apply_retirement(root, plan, dry_run=False)


def test_external_ref_backed_by_bib_is_dropped(tmp_path: Path) -> None:
    # kind=article -> EXTERNAL_REF bucket; canonical_id canonicalizes article:->paper:.
    _write(tmp_path, [{"canonical_id": "article:Smith2024", "kind": "article", "title": "S"}])
    report = _plan_apply(tmp_path, retire_external_refs=True, bib_keys=frozenset({"Smith2024"}))
    assert "paper:Smith2024" in report.deleted
    assert yaml.safe_load((tmp_path / _ENT_REL).read_text())["entities"] == []


def test_external_ref_unbacked_is_rejected_and_retained(tmp_path: Path) -> None:
    _write(tmp_path, [{"canonical_id": "article:Jones2099", "kind": "article", "title": "J"}])
    report = _plan_apply(tmp_path, retire_external_refs=True, bib_keys=frozenset())
    assert ("paper:Jones2099", "missing bibliography authority") in report.rejected
    remaining = yaml.safe_load((tmp_path / _ENT_REL).read_text())["entities"]
    assert [r["canonical_id"] for r in remaining] == ["article:Jones2099"]  # untouched


def test_external_ref_untouched_without_flag(tmp_path: Path) -> None:
    _write(tmp_path, [{"canonical_id": "article:Smith2024", "kind": "article", "title": "S"}])
    report = _plan_apply(tmp_path, retire_external_refs=False, bib_keys=frozenset({"Smith2024"}))
    assert "paper:Smith2024" not in report.deleted
    assert len(yaml.safe_load((tmp_path / _ENT_REL).read_text())["entities"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/graph/test_aggregate_retire_external_ref.py -v`
Expected: FAIL with `TypeError: plan_retirement() got an unexpected keyword argument 'retire_external_refs'`.

- [ ] **Step 3: Write minimal implementation**

In `src/science_tool/graph/aggregate_retire.py`:

(a) Extend the `plan_retirement` signature (`:99-109`) with two keyword-only params (after `delete_shadow`):

```python
def plan_retirement(
    project_root: Path,
    sources: "ProjectSources",
    rows: list[AggregateRowTriage],
    *,
    promote_coined: bool,
    delete_cruft: bool,
    delete_shadow: bool,
    retire_external_refs: bool = False,
    bib_keys: frozenset[str] = frozenset(),
    promote_decisions: bool = False,
    decision_index: DecisionLogIndex | None = None,
) -> RetirementPlan:
```

(b) In the dispatch loop, add the external-ref branch immediately AFTER the `if meta.kind == "decision":` block (which ends with its own `continue` at `:143`) and BEFORE the shadow/reconcile block (`:145`):

```python
        if triage.bucket is AggregateBucket.EXTERNAL_REF:
            if not retire_external_refs:
                continue  # untouched unless explicitly retiring external refs
            citekey = meta.canonical_id.split(":", 1)[1] if ":" in meta.canonical_id else meta.canonical_id
            if citekey in bib_keys:
                # Backed: a replacement external-reference node provably exists, so
                # the aggregate deprecated-owner row is redundant -> drop it.
                delete.append(PlannedRow(triage, RetireAction.DELETE, meta.path, meta.line, None))
            else:
                rejected.append((triage, "missing bibliography authority"))
            continue
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/graph/test_aggregate_retire_external_ref.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
uv run --frozen ruff check src/science_tool/graph/aggregate_retire.py tests/graph/test_aggregate_retire_external_ref.py
uv run --frozen ruff format src/science_tool/graph/aggregate_retire.py tests/graph/test_aggregate_retire_external_ref.py
git add src/science_tool/graph/aggregate_retire.py tests/graph/test_aggregate_retire_external_ref.py
git commit -m "feat(substrate-4b): plan_retirement external-ref action (bib-backed drop / un-backed reject)"
```

---

## Task 8: CLI `--retire-external-refs` flag

Surfaces the new action on `science entities triage-aggregate`, computing the backed key set from the project bib, gated by the same v3 `--apply` rule as the other buckets.

**Files:**
- Modify: `src/science_tool/cli.py:293-390`
- Test: `tests/test_cli_triage_external_ref.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_triage_external_ref.py
from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.cli import cli

_ENT_REL = "knowledge/sources/local/entities.yaml"


def _write(root: Path, *, layout: int, bib_key: str | None) -> None:
    root.joinpath("science.yaml").write_text(
        f"name: demo\nprofile: research\nprofiles: {{local: local}}\nlayout_version: {layout}\n",
        encoding="utf-8",
    )
    src = root / "knowledge" / "sources" / "local"
    src.mkdir(parents=True, exist_ok=True)
    src.joinpath("entities.yaml").write_text(
        yaml.safe_dump({"entities": [{"canonical_id": "article:Smith2024", "kind": "article", "title": "S"}]}),
        encoding="utf-8",
    )
    if bib_key is not None:
        (root / "papers").mkdir(parents=True, exist_ok=True)
        (root / "papers" / "references.bib").write_text(f"@article{{{bib_key},\n  title = {{S}},\n}}\n", encoding="utf-8")


def test_cli_retire_external_refs_apply_v3_drops_backed_row(tmp_path: Path) -> None:
    _write(tmp_path, layout=3, bib_key="Smith2024")
    result = CliRunner().invoke(
        cli,
        ["entities", "triage-aggregate", "--project-root", str(tmp_path), "--retire-external-refs", "--apply"],
    )
    assert result.exit_code == 0, result.output
    assert yaml.safe_load((tmp_path / _ENT_REL).read_text())["entities"] == []


def test_cli_retire_external_refs_apply_refused_on_v2(tmp_path: Path) -> None:
    _write(tmp_path, layout=2, bib_key="Smith2024")
    result = CliRunner().invoke(
        cli,
        ["entities", "triage-aggregate", "--project-root", str(tmp_path), "--retire-external-refs", "--apply"],
    )
    assert result.exit_code != 0
    assert "layout_version 2" in result.output
    assert len(yaml.safe_load((tmp_path / _ENT_REL).read_text())["entities"]) == 1  # untouched
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_cli_triage_external_ref.py -v`
Expected: FAIL — `--retire-external-refs` is not a known option (Click error, non-zero exit on the v3 test).

- [ ] **Step 3: Write minimal implementation**

In `src/science_tool/cli.py`, `entities_triage_aggregate_command` (`:293-390`):

(a) Add the option after `--promote-decisions` (`:304`):

```python
@click.option(
    "--retire-external-refs",
    is_flag=True,
    help="Drop `external-ref` (paper/article) rows backed by papers/references.bib.",
)
```

(b) Add the parameter to the function signature (after `promote_decisions: bool,`):

```python
    retire_external_refs: bool,
```

(c) Import the bib reader with the other local imports (`:318-321`):

```python
    from science_tool.bibliography import load_bib_entries
```

(d) Include it in `any_bucket` (`:325`) and the usage error (`:330-332`):

```python
    any_bucket = promote_coined or delete_cruft or delete_shadow or promote_decisions or retire_external_refs
```
```python
            raise click.UsageError(
                "--apply requires at least one of --promote-coined/--delete-cruft/--delete-shadow/"
                "--promote-decisions/--retire-external-refs."
            )
```

(e) Compute the backed key set and pass both params to `plan_retirement` (`:380-389`):

```python
    bib_keys = frozenset(load_bib_entries(project_root)) if retire_external_refs else frozenset()
    plan = plan_retirement(
        project_root,
        sources,
        rows,
        promote_coined=promote_coined,
        delete_cruft=delete_cruft,
        delete_shadow=delete_shadow,
        retire_external_refs=retire_external_refs,
        bib_keys=bib_keys,
        promote_decisions=promote_decisions,
        decision_index=decision_index,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_cli_triage_external_ref.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
uv run --frozen ruff check src/science_tool/cli.py tests/test_cli_triage_external_ref.py
uv run --frozen ruff format src/science_tool/cli.py tests/test_cli_triage_external_ref.py
git add src/science_tool/cli.py tests/test_cli_triage_external_ref.py
git commit -m "feat(substrate-4b): science entities triage-aggregate --retire-external-refs"
```

---

## Final verification (after all tasks)

- [ ] **Full suite green:** `uv run --frozen pytest` — all pass (the 2 pre-existing `snapshot` formatter-fixture failures stay deselected; do not attribute them to 4b).
- [ ] **Lint clean on touched files:** `uv run --frozen ruff check` + `ruff format --check` on the 8 source files + 7 test files (no NEW errors beyond the ~174 pre-existing baseline in untouched files).
- [ ] **MM30 v2 smoke** (read-only; MM30 stays git-clean — never `--apply` on v2). From the MM30 repo root:
  - `uv run --frozen science entities triage-aggregate --retire-external-refs --project-root .` (dry-run) lists the bib-backed `external-ref` rows as `delete` and the `doi:`/unbalanced/un-backed ones as `skip … missing bibliography authority`.
  - `uv run --frozen science entities triage-aggregate --retire-external-refs --apply --project-root .` is **refused exit 1** naming `layout_version 2`.
  - Loading MM30 now synthesizes external references for bib keys with no aggregate stub / markdown owner, so previously-unresolved bib-backed citations resolve; `git status --porcelain` is empty.
- [ ] **Holistic review** per subagent-driven-development: confirm (1) the bib defer truly prevents a strict-load collision on a stub+bib pair, (2) "backed" ⟺ a node provably exists — `load_bib_entries` admits only brace-balanced entries AND clamps `year` so the synthesized `PaperEntity` always validates (no balanced-but-unloadable key can trigger a drop), (3) no existing fixture with a `papers/references.bib` silently changed behavior in Task 5, (4) the stated commons precedence (local bib paper wins materialization; commons owner row still recorded) holds under the default `include_commons=True` load.

---

## Self-review (completed during planning)

**Spec coverage** — every design component maps to a task: Component 1 (bib reader) → T1; participation-mode seam → T2 + T5(c); Component 2 (BibAdapter) → T3; Component 3 (loop wiring + defer + scope) → T4 + T5; Component 4 (paper node) → T6; Component 5 (retirement action) → T7; Component 6 (CLI) → T8. Error-handling cases (absent bib, unbalanced entry, doi rows, transitional coexistence) are exercised by T1/T3/T5/T7 tests.

**Type consistency** — `BibEntry(key,title,year,doi,url)` (T1) is consumed unchanged by `BibAdapter.load_raw` (T3); `load_bib_entries` returns `dict[str, BibEntry]` and its `.keys()`/`frozenset(...)` feed `plan_retirement(bib_keys=frozenset[str])` (T7/T8); `participation_mode` is `ParticipationMode` on base (T2), overridden to `EXTERNAL_REFERENCE` on `BibAdapter` (T3), read as `adapter.participation_mode` in the loop (T5); `RetireAction.DELETE` reused for the external-ref drop (T7) lands in `RetirementReport.deleted` (existing shape). `PaperEntity.year/doi/url` (model) are the fields `_add_entity` reads (T6).

**No placeholders** — every code step shows complete code; every run step shows the exact command + expected result.
