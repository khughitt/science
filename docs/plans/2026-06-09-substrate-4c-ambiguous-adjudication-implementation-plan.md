# Substrate Phase 4c — Ambiguous-Row Adjudication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the aggregate triage's catch-all `AMBIGUOUS` bucket into named dispositions — curie external-refs migrated to a backed authority file, bare method/topic promoted as slug owners, question stubs deferred — and add a v3 conformance gate, so the aggregate files can fully retire (backed-only) without deleting the `AggregateAdapter`.

**Architecture:** A new `CurieRefAdapter` (participation_mode EXTERNAL_REFERENCE) reads a new `external_refs.yaml` authority file and synthesizes lightweight `same_as`-carrying nodes — the exact mirror of 4b's `BibAdapter`. The triage classifier learns two new buckets; the retirement executor gains a `--migrate-curie-refs` action that writes the authority row then drops the aggregate row (idempotent, conflict-loud). Materialization routes the curie through the existing `same_as` → `skos:exactMatch`-to-URIRef path and gates the `prov:Entity` external-ref marking on declared participation mode.

**Tech Stack:** Python 3.12, pydantic, rdflib, click, pytest. Work from `~/d/science/science` (the package root: `pyproject.toml`, `src/`, `tests/`). Design doc: `docs/plans/2026-06-09-substrate-4c-ambiguous-adjudication-design.md` (repo-root `docs/`, one level up).

**Conventions every task must follow:**
- Run tests with `uv run --frozen pytest` from `~/d/science/science`. The suite deselects `snapshot` and `real_projects` markers by default; 2 pre-existing `snapshot` formatter failures and ~174 baseline ruff errors in untouched files are NOT yours.
- Lint touched files only: `uv run --frozen ruff check <files>` and `uv run --frozen ruff format <files>` (120-char line limit). Use `uv`, never `pip`.
- Branch is `substrate-4c-ambiguous-adjudication` (already created, design already committed). Do **not** stage `docs/plans/2026-06-08-epistemic-edges-plan.md` (unrelated, must stay modified-but-unstaged).
- No "Co-Authored-By" trailer in commits.

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `src/science_tool/entities.py` | flip `method`/`topic` builtin policy to `slug` | T1 |
| `src/science_tool/graph/sources.py` | `AggregateRowMeta.primary_external_id` capture; generic EXTERNAL_REFERENCE defer; register `CurieRefAdapter` | T2, T6 |
| `src/science_tool/graph/aggregate_triage.py` | `CURIE_EXTERNAL_REF` + `QUESTION_DEFERRED` buckets; `_bucket` fan-out | T3 |
| `src/science_tool/graph/storage_adapters/curie_ref.py` (new) | read `external_refs.yaml` → external-reference records | T4 |
| `src/science_tool/graph/identity_table.py` | `classify_owner_scope("curie-ref")` | T5 |
| `src/science_tool/graph/materialize.py` | participation-gated `prov:Entity`; curie via `same_as` | T7 |
| `src/science_tool/graph/aggregate_retire.py` | `MIGRATE_EXTERNAL_REF` action: write authority row + drop aggregate row | T8 |
| `src/science_tool/cli.py` | `--migrate-curie-refs` flag | T9 |
| `src/science_tool/validate/checks/aggregate_retired.py` (new) | v3 gate: ERROR on residual aggregate rows | T10 |

**Dependency order (important for subagent execution — do not parallelize across a dependency):**
- T1, T2, T4, T5 are independent leaves. **T3 depends on T2** (`_bucket`/`classify_aggregate_rows` read the `primary_external_id` field T2 adds).
- **T6 depends on T4 + T5** (registers `CurieRefAdapter`; needs the class and its `curie-ref` scope).
- **T7 depends on T4 + T5 + T6** — its materialization fixture loads a project through `CurieRefAdapter`, so the adapter must be registered first.
- **T8 depends on T2 + T3 + T6** — the curie bucket (T3), the captured `primary_external_id` (T2), and the conflict test's load-time defer (T6).
- **T9 depends on T8** (CLI surfaces the migrate action).
- **T10 is independent** (reads the compiled model; its fixture uses only builtin kinds).

Recommended serial order: T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8 → T9 → T10.

---

## Task 1: `method` and `topic` become slug identity kinds

**Files:**
- Modify: `src/science_tool/entities.py:57` (method policy), `:49` (topic policy)
- Test: `tests/test_method_topic_slug_policy.py` (new)

**Context:** `_BUILTIN_MARKDOWN_POLICIES` currently registers `method` and `topic` with the `numeric` strategy (`entities/methods/NNNN-*.md`). MM30's coined ids are slug-shaped (`method:bayesian-inference`) and referenced widely, so they must promote id-preserving. A numeric local part like `0001-foo` also satisfies the slug regex, so flipping to `slug` *broadens* acceptance without invalidating numeric-id projects (design §5). `question` stays `numeric`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_method_topic_slug_policy.py
from __future__ import annotations

from pathlib import Path

from science_tool.entities import (
    generate_entity_id,
    local_part_conforms,
    resolve_path_policy,
)


def test_method_and_topic_use_slug_strategy(tmp_path: Path) -> None:
    assert resolve_path_policy("method", project_root=tmp_path).strategy == "slug"
    assert resolve_path_policy("topic", project_root=tmp_path).strategy == "slug"


def test_slug_local_part_conforms_for_method_and_topic(tmp_path: Path) -> None:
    # The MM30-shaped coined ids: lowercase slug local parts.
    assert local_part_conforms("method", "bayesian-inference", project_root=tmp_path)
    assert local_part_conforms("topic", "proliferation-dominance", project_root=tmp_path)


def test_legacy_numeric_local_part_still_conforms(tmp_path: Path) -> None:
    # Broadening, not invalidating: a numeric-shaped id still satisfies the slug regex.
    assert local_part_conforms("method", "0001-foo", project_root=tmp_path)


def test_generated_method_id_is_slug_derived(tmp_path: Path) -> None:
    # Forward consequence: new method ids are slug-derived, not NNNN-.
    # generate_entity_id(project_root, kind, title, entity_id, slug, today=None).
    new_id = generate_entity_id(tmp_path, "method", "Bayesian Inference", None, None)
    assert new_id.startswith("method:")
    local = new_id.split(":", 1)[1]
    # slug shape: lowercase, hyphen-separated, no leading digits-only sequence prefix.
    assert local == "bayesian-inference"
    assert local_part_conforms("method", local, project_root=tmp_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_method_topic_slug_policy.py -v`
Expected: FAIL — `test_method_and_topic_use_slug_strategy` asserts `"slug"` but gets `"numeric"`.

- [ ] **Step 3: Flip the two policies to slug**

In `src/science_tool/entities.py`, change these two lines inside `_BUILTIN_MARKDOWN_POLICIES`:

```python
    "topic": EntityPathPolicy(Path("entities/topics"), "slug"),    # was "numeric" (4c: slug identity kind)
```

```python
    "method": EntityPathPolicy(Path("entities/methods"), "slug"),  # was "numeric" (4c: slug identity kind)
```

Leave every other policy (including `question` → `numeric`) unchanged.

- [ ] **Step 4: Run the test**

Run: `uv run --frozen pytest tests/test_method_topic_slug_policy.py -v`
Expected: PASS (all 4).

- [ ] **Step 5: Guard against regressions in the wider entity suite**

Run: `uv run --frozen pytest tests/ -k "entit or policy or migrat" -q`
Expected: PASS. If any test pinned `method`/`topic` to `numeric`, it encoded the old policy — update it to expect `slug` (the behavior change is intentional and design-approved). Note any such file in the commit body.

- [ ] **Step 6: Lint + commit**

```bash
cd ~/d/science/science
uv run --frozen ruff check src/science_tool/entities.py tests/test_method_topic_slug_policy.py
uv run --frozen ruff format src/science_tool/entities.py tests/test_method_topic_slug_policy.py
git add src/science_tool/entities.py tests/test_method_topic_slug_policy.py
git commit -m "feat(substrate-4c): method/topic become slug identity kinds"
```

---

## Task 2: Capture `primary_external_id` in `AggregateRowMeta`

**Files:**
- Modify: `src/science_tool/graph/sources.py:144-157` (`AggregateRowMeta`), `:452-465` (capture site)
- Test: `tests/graph/test_aggregate_row_primary_external_id.py` (new)

**Context:** The triage classifier (T3) must see whether an aggregate row carries a `primary_external_id` to bucket it `CURIE_EXTERNAL_REF`. `AggregateRowMeta` is the row-level metadata captured at load time (before non-strict dedup drops a shadowed Entity). It currently carries `path, line, canonical_id, kind, source_path`. Add a `primary_external_id` field captured from the **validated** entity (`entity.primary_external_id` is a typed `ExternalId`, declared on the base `Entity` model at `model/src/science_model/entities.py:248`). Critically, `ExternalId` requires **all** of `source`, `id`, `curie`, `provenance` (`identity.py:17`), and `schema.model_validate(raw)` runs at `sources.py:359` — **before** the aggregate-meta capture at `sources.py:452`. So a half-filled `primary_external_id` never reaches the capture point: it fails `ExternalId` validation and the row is skipped (`entity_schema_validation_failed`). The captured value is therefore the full `{source, id, curie, provenance}` dump or `None`, never a partial mapping (design §3).

- [ ] **Step 1: Write the failing test**

```python
# tests/graph/test_aggregate_row_primary_external_id.py
from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 2\nontologies:\n  - biology\n"


def _write(root: Path, terms: list[dict]) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    src = root / "knowledge" / "sources" / "local"
    src.mkdir(parents=True, exist_ok=True)
    (src / "terms.yaml").write_text(yaml.safe_dump({"terms": terms}), encoding="utf-8")


def _meta_for(sources, cid):
    return next(m for m in sources.aggregate_rows if m.canonical_id == cid)


def test_wellformed_primary_external_id_captured(tmp_path: Path) -> None:
    _write(
        tmp_path,
        [
            {
                "id": "protein:BCMA",
                "title": "BCMA",
                # Full ExternalId shape: source, id, curie, provenance are ALL required.
                "primary_external_id": {
                    "source": "UniProtKB",
                    "id": "Q02223",
                    "curie": "UniProtKB:Q02223",
                    "provenance": "manual",
                },
            }
        ],
    )
    sources = load_project_sources(
        tmp_path, include_commons=False, strict_core_schema=False, strict_identity=False
    )
    meta = _meta_for(sources, "protein:BCMA")
    # Captured from the validated entity; model_dump(exclude_none=True) drops only `version`.
    assert meta.primary_external_id == {
        "source": "UniProtKB",
        "id": "Q02223",
        "curie": "UniProtKB:Q02223",
        "provenance": "manual",
    }


def test_malformed_primary_external_id_row_is_skipped(tmp_path: Path) -> None:
    # A half-filled primary_external_id fails ExternalId schema validation
    # (source/id/curie/provenance all required) at sources.py:359, so the row is
    # SKIPPED before the aggregate-meta capture at :452 — it never appears in
    # aggregate_rows (not even as a None-PEI row). A row with NO primary_external_id
    # validates fine and IS captured with primary_external_id is None. `concept` is a
    # core kind that permits an absent primary_external_id (mirrors real terms.yaml).
    _write(
        tmp_path,
        [
            {"id": "concept:partial", "title": "Partial",
             "primary_external_id": {"source": "UniProtKB"}},  # missing id/curie/provenance -> skipped
            {"id": "concept:plain", "title": "Plain"},  # no primary_external_id -> captured, None
        ],
    )
    sources = load_project_sources(
        tmp_path, include_commons=False, strict_core_schema=False, strict_identity=False
    )
    cids = {m.canonical_id for m in sources.aggregate_rows}
    assert "concept:partial" not in cids  # skipped at ExternalId validation
    assert "concept:plain" in cids  # captured
    assert _meta_for(sources, "concept:plain").primary_external_id is None
    assert sources.skipped_entities  # the malformed row was recorded as a skip
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/graph/test_aggregate_row_primary_external_id.py -v`
Expected: FAIL — `AggregateRowMeta` has no attribute `primary_external_id`.

- [ ] **Step 3: Add the field**

In `src/science_tool/graph/sources.py`, extend the `AggregateRowMeta` dataclass (currently ending at `source_path: str | None`):

```python
    path: str
    line: int
    canonical_id: str
    kind: str
    source_path: str | None
    # 4c: the row's external authority identifier, captured from the VALIDATED
    # entity. `entity.primary_external_id` is a typed ExternalId (or None); a
    # malformed value never reaches capture (it fails ExternalId validation and the
    # row is skipped). So this is the full {source, id, curie, provenance} dump or
    # None — never a half-filled mapping that could masquerade as a backed ref.
    primary_external_id: dict[str, str] | None = None
```

- [ ] **Step 4: Capture it at the aggregate emit point**

In `src/science_tool/graph/sources.py`, inside the `if adapter.name == "aggregate":` block, read the validated entity's `primary_external_id` and pass it to the `AggregateRowMeta(...)` constructor:

```python
                if adapter.name == "aggregate":
                    assert ref.line is not None  # AggregateAdapter always sets the entry index
                    sp_raw = raw.get("source_path")
                    # Capture from the VALIDATED entity, not raw: entity.primary_external_id
                    # is a typed ExternalId (already passed ExternalId validation) or None.
                    # exclude_none drops the optional `version`, leaving the four required keys.
                    pei = entity.primary_external_id
                    aggregate_rows.append(
                        AggregateRowMeta(
                            path=ref.path,
                            line=ref.line,
                            canonical_id=entity.canonical_id,
                            kind=kind,
                            # source_path is unschema'd extra metadata; normalize a
                            # malformed (non-string) value to None so the report can't crash.
                            source_path=sp_raw if isinstance(sp_raw, str) else None,
                            primary_external_id=pei.model_dump(exclude_none=True) if pei is not None else None,
                        )
                    )
```

Note: capturing from `entity.primary_external_id` (not `raw`) is deliberate — by this point the row has passed `schema.model_validate(raw)`, so a malformed `primary_external_id` has already caused the row to be skipped upstream. `entity.primary_external_id` is therefore guaranteed to be a well-formed `ExternalId` or `None`. No `ExternalId` import is needed here (we only call `.model_dump()` on the instance the entity already holds).

- [ ] **Step 5: Run the test**

Run: `uv run --frozen pytest tests/graph/test_aggregate_row_primary_external_id.py -v`
Expected: PASS (both).

- [ ] **Step 6: Lint + commit**

```bash
cd ~/d/science/science
uv run --frozen ruff check src/science_tool/graph/sources.py tests/graph/test_aggregate_row_primary_external_id.py
uv run --frozen ruff format src/science_tool/graph/sources.py tests/graph/test_aggregate_row_primary_external_id.py
git add src/science_tool/graph/sources.py tests/graph/test_aggregate_row_primary_external_id.py
git commit -m "feat(substrate-4c): capture validated primary_external_id in AggregateRowMeta"
```

---

## Task 3: Triage buckets `CURIE_EXTERNAL_REF` and `QUESTION_DEFERRED`

**Files:**
- Modify: `src/science_tool/graph/aggregate_triage.py` (enum, `_bucket`, `classify_aggregate_rows`)
- Test: `tests/graph/test_aggregate_triage_4c_buckets.py` (new)

**Context:** `_bucket(kind, source_path, has_real_owner, self_sourced)` currently ends with a single `return AMBIGUOUS`. 4c replaces that terminal fan-out: curie-bearing rows → `CURIE_EXTERNAL_REF`; bare `question` → `QUESTION_DEFERRED`; bare `method`/`topic` → `COINED`; everything else (no-curie disease/drug, unknown kinds) → residual `AMBIGUOUS`. `_bucket` gains a `has_primary_external_id` parameter; `classify_aggregate_rows` passes `meta.primary_external_id is not None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/graph/test_aggregate_triage_4c_buckets.py
from __future__ import annotations

from science_tool.graph.aggregate_triage import AggregateBucket, _bucket


def _b(kind, *, has_pei=False, self_sourced=True, source_path=None, has_real_owner=False):
    bucket, _evidence = _bucket(kind, source_path, has_real_owner, self_sourced, has_pei)
    return bucket


def test_curie_bearing_row_is_curie_external_ref() -> None:
    assert _b("protein", has_pei=True) is AggregateBucket.CURIE_EXTERNAL_REF
    assert _b("disease", has_pei=True) is AggregateBucket.CURIE_EXTERNAL_REF


def test_no_curie_biomedical_row_is_residual_ambiguous() -> None:
    assert _b("disease", has_pei=False) is AggregateBucket.AMBIGUOUS
    assert _b("drug", has_pei=False) is AggregateBucket.AMBIGUOUS


def test_bare_question_is_deferred() -> None:
    assert _b("question", has_pei=False) is AggregateBucket.QUESTION_DEFERRED


def test_bare_method_and_topic_are_coined() -> None:
    assert _b("method", has_pei=False) is AggregateBucket.COINED
    assert _b("topic", has_pei=False) is AggregateBucket.COINED


def test_shadow_still_wins_over_curie() -> None:
    # An id with a real owner is SHADOW regardless of a curie on the stub.
    assert _b("protein", has_pei=True, has_real_owner=True) is AggregateBucket.SHADOW


def test_existing_coinable_concept_still_coined() -> None:
    assert _b("concept", has_pei=False) is AggregateBucket.COINED
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/graph/test_aggregate_triage_4c_buckets.py -v`
Expected: FAIL — `AggregateBucket` has no `CURIE_EXTERNAL_REF`/`QUESTION_DEFERRED`, and `_bucket` takes 4 args not 5.

- [ ] **Step 3: Add the buckets, vocab set, and rewrite the terminal fan-out**

In `src/science_tool/graph/aggregate_triage.py`:

Add two enum members to `AggregateBucket`:

```python
class AggregateBucket(str, Enum):
    SHADOW = "shadow"
    COINED = "coined"
    DECISION_LOG = "decision-log"
    EXTERNAL_REF = "external-ref"
    CURIE_EXTERNAL_REF = "curie-external-ref"
    CRUFT = "cruft"
    QUESTION_DEFERRED = "question-deferred"
    AMBIGUOUS = "ambiguous"
```

Add a vocabulary-kinds set next to `_COINABLE_KINDS`:

```python
_COINABLE_KINDS = frozenset({"concept", "latent"})
# 4c: bare project vocabulary kinds that promote as slug owners (method/topic
# became slug identity kinds in 4c). `question` is epistemic and is NOT here —
# it routes to QUESTION_DEFERRED for deliberate authoring.
_COINABLE_VOCAB_KINDS = frozenset({"method", "topic"})
```

Replace the `_bucket` signature and its final two lines:

```python
def _bucket(
    kind: str,
    source_path: str | None,
    has_real_owner: bool,
    self_sourced: bool,
    has_primary_external_id: bool,
) -> tuple[AggregateBucket, str]:
    if has_real_owner:
        return AggregateBucket.SHADOW, "a non-aggregate owner of this id exists -> shadow"
    if source_path is not None and source_path.startswith("migration:"):
        return AggregateBucket.CRUFT, f"source_path {source_path!r} is a migration artifact -> cruft"
    if kind == "decision" and source_path == "core/decisions.md":
        return AggregateBucket.DECISION_LOG, "decision sourced from core/decisions.md -> decision-log"
    if kind == "article" or (source_path is not None and source_path.endswith(".bib")):
        return AggregateBucket.EXTERNAL_REF, f"kind={kind} / bibliographic source -> external-ref"
    if self_sourced and (kind in _COINABLE_KINDS or kind == "decision"):
        return AggregateBucket.COINED, f"self-sourced coinable kind={kind} -> coined"
    # 4c terminal fan-out (replaces the old single `return AMBIGUOUS`):
    if has_primary_external_id:
        return AggregateBucket.CURIE_EXTERNAL_REF, f"{kind} carries primary_external_id -> curie external ref"
    if self_sourced and kind == "question":
        return AggregateBucket.QUESTION_DEFERRED, "bare question stub -> requires epistemic authoring (deferred)"
    if self_sourced and kind in _COINABLE_VOCAB_KINDS:
        return AggregateBucket.COINED, f"self-sourced vocabulary kind={kind} -> coined"
    return AggregateBucket.AMBIGUOUS, f"{kind} without primary_external_id -> requires human identity decision"
```

- [ ] **Step 4: Thread `primary_external_id` through `classify_aggregate_rows`**

In the `for decl in agg_rows:` loop of `classify_aggregate_rows`, the join already binds `meta`. Pass the curie presence into `_bucket`:

```python
            self_sourced = source_path in (None, "") or source_path == agg_path
            has_pei = meta is not None and meta.primary_external_id is not None
            bucket, evidence = _bucket(kind, source_path, has_real_owner, self_sourced, has_pei)
```

- [ ] **Step 5: Run the unit test + the existing triage suite**

Run: `uv run --frozen pytest tests/graph/test_aggregate_triage_4c_buckets.py tests/graph/test_aggregate_triage.py -v`
Expected: PASS. (The existing `test_aggregate_triage.py` exercises `classify_aggregate_rows`; the new `_bucket` arg is supplied internally, so those tests still pass.)

- [ ] **Step 6: Lint + commit**

```bash
cd ~/d/science/science
uv run --frozen ruff check src/science_tool/graph/aggregate_triage.py tests/graph/test_aggregate_triage_4c_buckets.py
uv run --frozen ruff format src/science_tool/graph/aggregate_triage.py tests/graph/test_aggregate_triage_4c_buckets.py
git add src/science_tool/graph/aggregate_triage.py tests/graph/test_aggregate_triage_4c_buckets.py
git commit -m "feat(substrate-4c): triage CURIE_EXTERNAL_REF + QUESTION_DEFERRED buckets"
```

---

## Task 4: `CurieRefAdapter`

**Files:**
- Create: `src/science_tool/graph/storage_adapters/curie_ref.py`
- Test: `tests/graph/test_curie_ref_adapter.py` (new)

**Context:** Mirror `BibAdapter` (`bib.py`), but the file is profile-dependent, so the adapter takes `local_profile` and resolves the path via `local_profile_sources_dir`. Both integrity failures (duplicate id, malformed `primary_external_id`) **raise loudly** — `external_refs.yaml` is the durable backing authority once aggregate rows retire (design §4.2). The synthesized record carries the curie in a **list** `same_as` (so `_enrich_raw` normalizes it; a non-list is silently dropped) and sets `file_path` (so provenance is not weak).

- [ ] **Step 1: Write the failing test**

```python
# tests/graph/test_curie_ref_adapter.py
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.graph.identity_table import ParticipationMode
from science_tool.graph.storage_adapters.curie_ref import CurieRefAdapter

_REL = "knowledge/sources/local/external_refs.yaml"


def _write(root: Path, refs: list[dict]) -> None:
    p = root / "knowledge" / "sources" / "local"
    p.mkdir(parents=True, exist_ok=True)
    (p / "external_refs.yaml").write_text(yaml.safe_dump({"references": refs}), encoding="utf-8")


def test_discover_one_ref_per_row_and_load_raw_shape(tmp_path: Path) -> None:
    _write(
        tmp_path,
        [
            {
                "id": "protein:BCMA",
                "type": "protein",
                "title": "BCMA",
                "primary_external_id": {
                    "source": "UniProtKB",
                    "id": "Q02223",
                    "curie": "UniProtKB:Q02223",
                    "provenance": "manual",
                },
                "description": "B-cell maturation antigen.",
            }
        ],
    )
    adapter = CurieRefAdapter(local_profile="local")
    refs = adapter.discover(tmp_path)
    assert len(refs) == 1
    assert refs[0].adapter_name == "curie-ref"
    assert refs[0].path == _REL
    raw = adapter.load_raw(refs[0])
    assert raw["kind"] == "protein"
    assert raw["id"] == "protein:BCMA"
    assert raw["title"] == "BCMA"
    assert raw["same_as"] == ["UniProtKB:Q02223"]  # LIST, not frozenset
    assert raw["file_path"] == _REL
    assert raw["primary_external_id"] == {
        "source": "UniProtKB",
        "id": "Q02223",
        "curie": "UniProtKB:Q02223",
        "provenance": "manual",
    }


def test_participation_mode_is_external_reference() -> None:
    assert CurieRefAdapter(local_profile="local").participation_mode is ParticipationMode.EXTERNAL_REFERENCE


def test_title_defaults_to_id_when_absent(tmp_path: Path) -> None:
    _write(tmp_path, [{"id": "gene:MYC", "type": "gene",
                       "primary_external_id": {"source": "HGNC", "id": "7553", "curie": "HGNC:7553", "provenance": "manual"}}])
    adapter = CurieRefAdapter(local_profile="local")
    raw = adapter.load_raw(adapter.discover(tmp_path)[0])
    assert raw["title"] == "gene:MYC"


def test_duplicate_id_raises(tmp_path: Path) -> None:
    _write(
        tmp_path,
        [
            {"id": "protein:BCMA", "type": "protein",
             "primary_external_id": {"source": "UniProtKB", "id": "Q02223", "curie": "UniProtKB:Q02223", "provenance": "manual"}},
            {"id": "protein:BCMA", "type": "protein",
             "primary_external_id": {"source": "UniProt", "id": "OTHER", "curie": "UniProt:OTHER", "provenance": "manual"}},
        ],
    )
    with pytest.raises(ValueError, match="duplicate"):
        CurieRefAdapter(local_profile="local").discover(tmp_path)


def test_malformed_primary_external_id_raises(tmp_path: Path) -> None:
    # Missing id, curie, provenance — ExternalId requires all four, and external_refs.yaml
    # is the durable authority, so discover() fails loud rather than skipping the row.
    _write(tmp_path, [{"id": "protein:X", "type": "protein", "primary_external_id": {"source": "UniProt"}}])
    with pytest.raises(ValueError, match="primary_external_id"):
        CurieRefAdapter(local_profile="local").discover(tmp_path)


def test_load_raw_before_discover_raises(tmp_path: Path) -> None:
    from science_model.source_ref import SourceRef

    adapter = CurieRefAdapter(local_profile="local")
    with pytest.raises(RuntimeError, match="discover"):
        adapter.load_raw(SourceRef(adapter_name="curie-ref", path=_REL, line=0))


def test_missing_file_yields_no_refs(tmp_path: Path) -> None:
    (tmp_path / "knowledge" / "sources" / "local").mkdir(parents=True)
    assert CurieRefAdapter(local_profile="local").discover(tmp_path) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/graph/test_curie_ref_adapter.py -v`
Expected: FAIL — module `curie_ref` does not exist.

- [ ] **Step 3: Write the adapter**

```python
# src/science_tool/graph/storage_adapters/curie_ref.py
"""CurieRefAdapter — the project ontology cross-reference authority
(`knowledge/sources/<profile>/external_refs.yaml`) as an external-reference
source (design §B2/§B3a/§C3, Phase 4c).

Synthesizes a lightweight `<kind>:<slug>` raw record per row, carrying the curie
in `same_as` so materialization emits a skos:exactMatch to a URIRef external-term
node. These are external references, not owners: the load loop tags their identity
rows ParticipationMode.EXTERNAL_REFERENCE (never renumbered, never a collision).

Unlike a transitional aggregate row (debt the triage tolerates), this file is the
DURABLE backing authority once aggregate rows retire, so both integrity failures
-- a duplicate id, or a malformed primary_external_id -- raise loudly rather than
silently drop a row (which would unresolve citations or lose a curie mapping).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from science_model.source_ref import SourceRef

from science_tool.graph.identity_table import ParticipationMode
from science_tool.graph.storage_adapters.base import StorageAdapter

_FILE_NAME = "external_refs.yaml"
_ROOT_KEY = "references"

# NOTE: do NOT import `local_profile_sources_dir` from `science_tool.graph.sources`
# here — Task 6 registers this adapter *inside* sources.py, so importing from
# sources would create a circular import at module load. Build the path directly
# from the resolved `local_profile`, exactly as AggregateAdapter does
# (`project_root / "knowledge" / "sources" / self._local_profile`). The profile is
# still resolved (passed in by the loader), so nothing is hardcoded except the
# universal `knowledge/sources` structural prefix that AggregateAdapter also fixes.


class CurieRefAdapter(StorageAdapter):
    """Reads `external_refs.yaml` into external-reference curie records."""

    name = "curie-ref"
    participation_mode = ParticipationMode.EXTERNAL_REFERENCE

    def __init__(self, *, local_profile: str) -> None:
        self._local_profile = local_profile
        self._rows: list[dict[str, Any]] = []
        self._rel: str | None = None

    def _path(self, project_root: Path) -> Path:
        # Mirror AggregateAdapter's path construction (no sources.py import; see module note).
        return project_root / "knowledge" / "sources" / self._local_profile / _FILE_NAME

    def discover(self, project_root: Path) -> list[SourceRef]:
        self._rows = []
        path = self._path(project_root)
        self._rel = path.relative_to(project_root).as_posix()
        if not path.is_file():
            return []
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        rows = data.get(_ROOT_KEY) or []
        if not isinstance(rows, list):
            raise ValueError(f"{self._rel}: `{_ROOT_KEY}` must be a list")
        seen: set[str] = set()
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                raise ValueError(f"{self._rel}[{i}]: each reference must be a mapping")
            cid = row.get("id")
            if not isinstance(cid, str) or not cid:
                raise ValueError(f"{self._rel}[{i}]: reference requires a non-empty `id`")
            if cid in seen:
                raise ValueError(f"{self._rel}: duplicate id {cid!r} in external-reference authority")
            seen.add(cid)
            pei = row.get("primary_external_id")
            # Require the full ExternalId shape (source, id, curie, provenance): these
            # rows are validated as ExternalId downstream (sources.py:359) once T6
            # registers the adapter, and external_refs.yaml is the durable backing
            # authority — so a partial mapping must fail loud here, not be skipped later.
            if not (isinstance(pei, dict)
                    and all(isinstance(pei.get(k), str) and pei.get(k) for k in ("source", "id", "curie", "provenance"))):
                raise ValueError(
                    f"{self._rel}[{i}] ({cid}): malformed primary_external_id "
                    "(needs string `source`, `id`, `curie`, `provenance`)"
                )
        self._rows = rows
        return [SourceRef(adapter_name=self.name, path=self._rel, line=i) for i in range(len(rows))]

    def load_raw(self, ref: SourceRef) -> dict[str, Any]:
        if not self._rows:
            raise RuntimeError("CurieRefAdapter.discover() must be called before load_raw()")
        assert ref.line is not None, "CurieRefAdapter SourceRef must carry line (row index)"
        assert self._rel is not None
        row = self._rows[ref.line]
        cid = row["id"]
        kind = row.get("type") or cid.split(":", 1)[0]
        curie = row["primary_external_id"]["curie"]
        raw: dict[str, Any] = {
            "kind": kind,
            "id": cid,
            "title": row.get("title") or cid,
            "same_as": [curie],  # LIST: _enrich_raw normalizes same_as only when isinstance(vals, list)
            "file_path": self._rel,
            "primary_external_id": row["primary_external_id"],
        }
        description = row.get("description")
        if isinstance(description, str) and description:
            raw["summary"] = description
        return raw
```

Note: the record uses `summary` (not `description`) for the prose, matching the base entity field that `_add_entity` materializes (`schema:description`). The synthesized kinds (protein/disease/etc.) resolve through the registry like any other; if a project does not register a kind, the load loop's existing `unknown_entity_kind` skip applies (the same tolerance BibAdapter relies on).

- [ ] **Step 4: Run the test**

Run: `uv run --frozen pytest tests/graph/test_curie_ref_adapter.py -v`
Expected: PASS (all 7).

- [ ] **Step 5: Lint + commit**

```bash
cd ~/d/science/science
uv run --frozen ruff check src/science_tool/graph/storage_adapters/curie_ref.py tests/graph/test_curie_ref_adapter.py
uv run --frozen ruff format src/science_tool/graph/storage_adapters/curie_ref.py tests/graph/test_curie_ref_adapter.py
git add src/science_tool/graph/storage_adapters/curie_ref.py tests/graph/test_curie_ref_adapter.py
git commit -m "feat(substrate-4c): CurieRefAdapter reads external_refs.yaml authority (fail-loud)"
```

---

## Task 5: `classify_owner_scope("curie-ref")`

**Files:**
- Modify: `src/science_tool/graph/identity_table.py` (`classify_owner_scope`)
- Test: `tests/graph/test_classify_owner_scope_curie.py` (new)

**Context:** `classify_owner_scope(adapter, *, project_name) -> (owner_scope, deprecated)` already special-cases `commons-merged`, `bib`, and the deprecated `aggregate`/`datapackage`. Add `curie-ref` as a non-deprecated external-reference authority scope, exactly like `bib`.

- [ ] **Step 1: Write the failing test**

```python
# tests/graph/test_classify_owner_scope_curie.py
from __future__ import annotations

from science_tool.graph.identity_table import classify_owner_scope


def test_curie_ref_is_nondeprecated_authority_scope() -> None:
    assert classify_owner_scope("curie-ref", project_name="demo") == ("curie-ref", False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/graph/test_classify_owner_scope_curie.py -v`
Expected: FAIL — returns `("demo", False)` (the default branch), not `("curie-ref", False)`.

- [ ] **Step 3: Add the branch**

In `src/science_tool/graph/identity_table.py`, add immediately after the `if adapter == "bib":` block:

```python
    if adapter == "curie-ref":
        # External-reference authority scope (design §B3, Phase 4c): curie rows are
        # never owners; this scope labels provenance and is non-deprecated.
        return ("curie-ref", False)
```

- [ ] **Step 4: Run the test**

Run: `uv run --frozen pytest tests/graph/test_classify_owner_scope_curie.py -v`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
cd ~/d/science/science
uv run --frozen ruff check src/science_tool/graph/identity_table.py tests/graph/test_classify_owner_scope_curie.py
uv run --frozen ruff format src/science_tool/graph/identity_table.py tests/graph/test_classify_owner_scope_curie.py
git add src/science_tool/graph/identity_table.py tests/graph/test_classify_owner_scope_curie.py
git commit -m "feat(substrate-4c): classify_owner_scope curie-ref authority scope"
```

---

## Task 6: Loader — generic EXTERNAL_REFERENCE defer + register `CurieRefAdapter`

**Files:**
- Modify: `src/science_tool/graph/sources.py:283-287` (registration), `:432-441` (defer guard), import block
- Test: `tests/graph/test_curie_external_reference_load.py` (new)

**Context:** Two changes in `load_project_sources`. (1) Generalize the 4b bib defer from `isinstance(adapter, BibAdapter)` to `adapter.participation_mode == ParticipationMode.EXTERNAL_REFERENCE` — the branch must say only "this adapter contributes external references and a prior declaration exists → defer," with no adapter-specific knowledge (design §4.3). (2) Register `CurieRefAdapter(local_profile=local_profile)` after `BibAdapter()`. Verify the end-to-end: a curie row synthesizes an EXTERNAL_REFERENCE node, and a curie row whose id is also a transitional aggregate stub defers (no strict-load collision).

- [ ] **Step 1: Write the failing test**

```python
# tests/graph/test_curie_external_reference_load.py
from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.identity_table import ParticipationMode, build_identity_table
from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 2\nontologies:\n  - biology\n"


def _src(root: Path) -> Path:
    p = root / "knowledge" / "sources" / "local"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _base(root: Path) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")


def test_curie_row_synthesizes_external_reference_declaration(tmp_path: Path) -> None:
    _base(tmp_path)
    _src(tmp_path).joinpath("external_refs.yaml").write_text(
        yaml.safe_dump(
            {"references": [
                {"id": "protein:BCMA", "type": "protein", "title": "BCMA",
                 "primary_external_id": {"source": "UniProtKB", "id": "Q02223",
                                         "curie": "UniProtKB:Q02223", "provenance": "manual"}}
            ]}
        ),
        encoding="utf-8",
    )
    sources = load_project_sources(
        tmp_path, include_commons=False, strict_core_schema=False, strict_identity=False
    )
    decl = next(d for d in sources.identity_declarations if d.canonical_id == "protein:BCMA")
    assert decl.participation_mode is ParticipationMode.EXTERNAL_REFERENCE
    assert decl.adapter == "curie-ref"
    ent = next(e for e in sources.entities if e.canonical_id == "protein:BCMA")
    assert "UniProtKB:Q02223" in list(ent.same_as)


def test_curie_defers_to_transitional_aggregate_stub_no_collision(tmp_path: Path) -> None:
    # Same id present as BOTH an aggregate stub (terms.yaml) and a curie authority
    # row. Under STRICT load this must not raise: the curie defers to the stub.
    _base(tmp_path)
    src = _src(tmp_path)
    src.joinpath("terms.yaml").write_text(
        yaml.safe_dump({"terms": [{"id": "protein:BCMA", "title": "BCMA"}]}), encoding="utf-8"
    )
    src.joinpath("external_refs.yaml").write_text(
        yaml.safe_dump(
            {"references": [
                {"id": "protein:BCMA", "type": "protein", "title": "BCMA",
                 "primary_external_id": {"source": "UniProtKB", "id": "Q02223",
                                         "curie": "UniProtKB:Q02223", "provenance": "manual"}}
            ]}
        ),
        encoding="utf-8",
    )
    # strict_identity=True must NOT raise (defer fires).
    sources = load_project_sources(
        tmp_path, include_commons=False, strict_core_schema=False, strict_identity=True
    )
    table = build_identity_table(sources)
    owners = table.owners()[("demo", "protein:BCMA")]
    # Only the aggregate stub is an owner row; the curie row deferred (no second decl).
    assert all(r.adapter == "aggregate" for r in owners)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/graph/test_curie_external_reference_load.py -v`
Expected: FAIL — `CurieRefAdapter` is not registered, so `protein:BCMA` has no declaration / the wrong adapter.

- [ ] **Step 3: Register the adapter**

In `src/science_tool/graph/sources.py`, add the import near the `BibAdapter` import:

```python
from science_tool.graph.storage_adapters.bib import BibAdapter
from science_tool.graph.storage_adapters.curie_ref import CurieRefAdapter
```

Register it in the `adapters` list, right after `BibAdapter()`, and extend the ordering note:

```python
        AggregateAdapter(local_profile=local_profile),
        # NOTE: AggregateAdapter must precede the external-reference adapters
        # (BibAdapter, CurieRefAdapter) — their defer guard relies on aggregate
        # stubs (and markdown owners) being declared first this load.
        BibAdapter(),
        CurieRefAdapter(local_profile=local_profile),
        DatapackageAdapter(),
```

- [ ] **Step 4: Generalize the defer guard**

Replace the `if isinstance(adapter, BibAdapter) and entity.canonical_id in identity_table:` block with a participation-mode guard:

```python
                if (
                    adapter.participation_mode == ParticipationMode.EXTERNAL_REFERENCE
                    and entity.canonical_id in identity_table
                ):
                    # §B3/§C3 external-reference defer (generalized over bib + curie):
                    # an external-reference adapter contributes references, not
                    # owners. If a real owner OR a transitional aggregate stub already
                    # claimed this id this load (all owner-ish adapters precede the
                    # external-reference adapters), it defers — no second declaration,
                    # no duplicate entity, no collision under strict load. The
                    # owner->external-reference flip happens automatically on the next
                    # load once retirement drops the stub. The branch is deliberately
                    # adapter-agnostic; source-specific parsing stays in the adapter.
                    continue
```

`ParticipationMode` is already imported in `sources.py` (used at the legacy-records OWNER declaration). Confirm the import line `from science_tool.graph.identity_table import ( ... ParticipationMode ... )` is present; it is.

- [ ] **Step 5: Run the test + the 4b bib defer regression**

Run: `uv run --frozen pytest tests/graph/test_curie_external_reference_load.py tests/graph/test_bib_external_reference_load.py -v`
Expected: PASS — both the new curie defer and the existing 4b bib defer (now routed through the generalized branch) hold.

- [ ] **Step 6: Lint + commit**

```bash
cd ~/d/science/science
uv run --frozen ruff check src/science_tool/graph/sources.py tests/graph/test_curie_external_reference_load.py
uv run --frozen ruff format src/science_tool/graph/sources.py tests/graph/test_curie_external_reference_load.py
git add src/science_tool/graph/sources.py tests/graph/test_curie_external_reference_load.py
git commit -m "feat(substrate-4c): register CurieRefAdapter + generalize external-reference defer"
```

---

## Task 7: Materialize — participation-gated `prov:Entity` + curie via `same_as`

**Files:**
- Modify: `src/science_tool/graph/materialize.py:100-109` (build set + pass it), `:236-276` (`_add_entity`)
- Test: `tests/graph/test_curie_node_materialization.py` (new)

**Context:** `_add_entity` receives only an `Entity`, so it cannot see participation mode (design §4.4). Build `external_reference_ids` once in `_build_dataset_from_sources` from `sources.identity_declarations` and thread it in; emit `prov:Entity` iff the id is in that set. Converge 4b's `kind == "paper"` prov:Entity onto the same gate (papers are declared EXTERNAL_REFERENCE, so stay marked); keep the paper-specific year/doi/url keyed on `kind == "paper"`. The curie cross-reference itself needs **no new code**: `CurieRefAdapter` put the curie in `same_as`, and the existing `same_as` loop emits `skos:exactMatch` to a URIRef external-term node — provided the curie's prefix is recognized as external (declared in the project's ontology catalogs), which the test fixture supplies.

- [ ] **Step 1: Write the failing test**

```python
# tests/graph/test_curie_node_materialization.py
from __future__ import annotations

from pathlib import Path

import yaml
from rdflib import Literal, URIRef
from rdflib.namespace import PROV, RDF, SKOS

# Mirror tests/graph/test_paper_node_metadata.py (4b): build with
# _build_dataset_from_sources and read the named knowledge graph. NOTE:
# materialize_graph(project_root) takes a path and RETURNS a path (it writes the
# .trig), so it is NOT what these triple assertions want.
from science_tool.graph.materialize import PROJECT_NS, _build_dataset_from_sources, _entity_uri
from science_tool.graph.sources import load_project_sources

# `ontologies: [biology]` registers the `protein` kind (biolink:Protein, name=protein)
# AND declares its curie prefix `UniProtKB`, so (a) the row is not skipped as an
# unknown kind and (b) is_external_reference recognizes the curie -> the same_as
# edge materializes. A literal inline catalog does NOT work: _read_project_config
# coerces `ontologies` entries to strings (sources.py), so only NAMED catalogs load.
_MANIFEST = (
    "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n"
    "ontologies:\n  - biology\n"
)


def _project(root: Path) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    src = root / "knowledge" / "sources" / "local"
    src.mkdir(parents=True, exist_ok=True)
    src.joinpath("external_refs.yaml").write_text(
        yaml.safe_dump(
            {"references": [
                {"id": "protein:BCMA", "type": "protein", "title": "BCMA",
                 "primary_external_id": {"source": "UniProtKB", "id": "Q02223",
                                         "curie": "UniProtKB:Q02223", "provenance": "manual"}}
            ]}
        ),
        encoding="utf-8",
    )


def test_curie_node_is_prov_entity_with_exactmatch_uriref(tmp_path: Path) -> None:
    _project(tmp_path)
    sources = load_project_sources(
        tmp_path, include_commons=False, strict_core_schema=False, strict_identity=False
    )
    ds = _build_dataset_from_sources(sources)
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    bridge = ds.graph(PROJECT_NS["graph/bridge"])  # same_as external-term edges land here
    uri = _entity_uri("protein:BCMA")
    # (a) prov:Entity marking via the participation gate
    assert (uri, RDF.type, PROV.Entity) in knowledge
    # (b) curie cross-reference: skos:exactMatch to a URIRef (NOT a Literal)
    objs = list(bridge.objects(uri, SKOS.exactMatch))
    assert objs, "no skos:exactMatch emitted for the curie"
    assert all(isinstance(o, URIRef) for o in objs)
    assert not any(isinstance(o, Literal) for o in objs)


def test_owned_entity_with_curie_is_not_external_ref_but_still_exactmatches(tmp_path: Path) -> None:
    # An OWNED entity carrying the same-shaped curie must NOT get the external-ref
    # prov:Entity marking, yet its curie still materializes via same_as. Use a
    # `concept` owner: it has a markdown slug policy (entities/concepts), whereas
    # `protein` has no _BUILTIN_MARKDOWN_POLICIES entry so cannot be a markdown owner.
    (tmp_path / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    owners = tmp_path / "entities" / "concepts"
    owners.mkdir(parents=True, exist_ok=True)
    (owners / "bcma-marker.md").write_text(
        "---\nid: concept:bcma-marker\ntype: concept\ntitle: BCMA marker\n"
        "same_as: [UniProtKB:Q02223]\n---\n\nOwned concept that asserts a curie equivalence.\n",
        encoding="utf-8",
    )
    sources = load_project_sources(
        tmp_path, include_commons=False, strict_core_schema=False, strict_identity=False
    )
    ds = _build_dataset_from_sources(sources)
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    bridge = ds.graph(PROJECT_NS["graph/bridge"])
    uri = _entity_uri("concept:bcma-marker")
    assert (uri, RDF.type, PROV.Entity) not in knowledge  # owned -> no external-ref marking
    assert list(bridge.objects(uri, SKOS.exactMatch))  # curie still emitted via same_as
```

> Implementer note: `_build_dataset_from_sources`, `PROJECT_NS`, and `_entity_uri` are imported exactly as `tests/graph/test_paper_node_metadata.py` does. The `same_as` external-term edge is emitted into the **bridge** graph (`_link_same_as_external(... bridge=bridge ...)` at `materialize.py:414`), while `prov:Entity` lands in the **knowledge** graph — assert each on the right named graph.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/graph/test_curie_node_materialization.py -v`
Expected: FAIL — `protein:BCMA` is not marked `prov:Entity` (no participation gate yet).

- [ ] **Step 3: Build `external_reference_ids` and thread it in**

In `src/science_tool/graph/materialize.py`, add the `ParticipationMode` import:

```python
from science_tool.graph.identity_table import ParticipationMode, build_identity_table
```

In `_build_dataset_from_sources`, just after `ext_prefixes = ...` (line ~101), build the set and pass it to `_add_entity`:

```python
    ext_prefixes = _EXTERNAL_PREFIXES | external_prefixes(sources.ontology_catalogs)
    external_reference_ids = {
        d.canonical_id
        for d in sources.identity_declarations
        if d.participation_mode == ParticipationMode.EXTERNAL_REFERENCE
    }

    for entity in sources.entities:
        _add_entity(
            entity=entity,
            knowledge=knowledge,
            provenance=provenance,
            overlay_paths=sources.commons_overlay_paths,
            external_reference_ids=external_reference_ids,
        )
```

- [ ] **Step 4: Gate `prov:Entity` on the set in `_add_entity`**

Change the `_add_entity` signature to accept the set, and replace the paper branch's unconditional `prov:Entity` with the participation gate:

```python
def _add_entity(
    *,
    entity: Entity,
    knowledge,
    provenance,
    overlay_paths: dict[str, str] | None = None,
    external_reference_ids: set[str] | None = None,
) -> None:
```

Replace the existing `if entity.kind == "paper":` block (lines ~261-276) with:

```python
    # Phase 4b/4c: external-reference nodes (bib papers, curie authority rows) are
    # provenance/reference nodes, not project owners. Mark prov:Entity off the
    # DECLARED participation mode, never off kind or curie presence — a future
    # commons-OWNED protein with a curie must keep full owner treatment.
    if external_reference_ids is not None and entity.canonical_id in external_reference_ids:
        knowledge.add((uri, RDF.type, PROV.Entity))
    if entity.kind == "paper":
        # Thin bibliographic surface (year/doi/url), emitted only when present.
        year = getattr(entity, "year", None)
        if year is not None:
            knowledge.add((uri, DCTERMS_NS.date, Literal(str(year))))
        doi = getattr(entity, "doi", "")
        if doi:
            knowledge.add((uri, SCI_NS.doi, Literal(doi)))
        url = getattr(entity, "url", "")
        if url:
            knowledge.add((uri, DCAT_NS.downloadURL, URIRef(url)))
```

The curie's `skos:exactMatch` is emitted by the **existing** `same_as` loop in `_add_relations` (line ~410) — no change there. It fires because `CurieRefAdapter` populated `same_as` and the test manifest declares `UniProt` as an external curie prefix.

- [ ] **Step 5: Run the test + the 4b paper-node regression**

Run: `uv run --frozen pytest tests/graph/test_curie_node_materialization.py tests/graph/test_paper_node_metadata.py -v`
Expected: PASS — curie node marked + exactMatch-to-URIRef; 4b paper nodes still `prov:Entity` + bib surface through the converged gate.

- [ ] **Step 6: Lint + commit**

```bash
cd ~/d/science/science
uv run --frozen ruff check src/science_tool/graph/materialize.py tests/graph/test_curie_node_materialization.py
uv run --frozen ruff format src/science_tool/graph/materialize.py tests/graph/test_curie_node_materialization.py
git add src/science_tool/graph/materialize.py tests/graph/test_curie_node_materialization.py
git commit -m "feat(substrate-4c): participation-gated prov:Entity; curie via same_as exactMatch"
```

---

## Task 8: Retirement — `MIGRATE_EXTERNAL_REF` action

**Files:**
- Modify: `src/science_tool/graph/aggregate_retire.py` (`RetireAction`, `RetirementPlan`, `plan_retirement`, `RetirementReport`, `apply_retirement`)
- Test: `tests/graph/test_aggregate_retire_curie_migration.py` (new)

**Context:** Add a migrate action that **creates** the authority row in `external_refs.yaml` then **drops** the aggregate row (distinct mutation semantics from 4b's delete-when-backed; design §4.5). Idempotent: same id + same curie already present → skip the append, still drop the aggregate row (reconcile); same id + different curie → reject loudly, mutate nothing. The append target path resolves via `local_profile_sources_dir(project_root, local_profile=resolve_local_profile_name(project_root))`, never hardcoded.

- [ ] **Step 1: Write the failing test**

```python
# tests/graph/test_aggregate_retire_curie_migration.py
from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.aggregate_retire import apply_retirement, plan_retirement
from science_tool.graph.aggregate_triage import classify_aggregate_rows
from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\nontologies:\n  - biology\n"


def _project(root: Path, terms: list[dict], external_refs: list[dict] | None = None) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    src = root / "knowledge" / "sources" / "local"
    src.mkdir(parents=True, exist_ok=True)
    (src / "terms.yaml").write_text(yaml.safe_dump({"terms": terms}), encoding="utf-8")
    if external_refs is not None:
        (src / "external_refs.yaml").write_text(
            yaml.safe_dump({"references": external_refs}), encoding="utf-8"
        )


def _run(root: Path):
    sources = load_project_sources(root, include_commons=False, strict_core_schema=False, strict_identity=False)
    rows = classify_aggregate_rows(sources)
    plan = plan_retirement(root, sources, rows, promote_coined=False, delete_cruft=False,
                           delete_shadow=False, migrate_curie_refs=True)
    return apply_retirement(root, plan, dry_run=False)


def _ext_refs(root: Path) -> list[dict]:
    p = root / "knowledge" / "sources" / "local" / "external_refs.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8"))["references"] if p.is_file() else []


def _terms(root: Path) -> list[dict]:
    p = root / "knowledge" / "sources" / "local" / "terms.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8"))["terms"]


def test_migrate_creates_authority_row_and_drops_aggregate_row(tmp_path: Path) -> None:
    _project(
        tmp_path,
        [{"id": "protein:BCMA", "title": "BCMA",
          "primary_external_id": {"source": "UniProtKB", "id": "Q02223",
                                  "curie": "UniProtKB:Q02223", "provenance": "manual"},
          "description": "B-cell maturation antigen."}],
    )
    report = _run(tmp_path)
    assert "protein:BCMA" in report.migrated
    refs = _ext_refs(tmp_path)
    assert len(refs) == 1
    assert refs[0]["id"] == "protein:BCMA"
    assert refs[0]["type"] == "protein"
    # The writer copies the source row's primary_external_id verbatim — full ExternalId shape.
    assert refs[0]["primary_external_id"] == {"source": "UniProtKB", "id": "Q02223",
                                              "curie": "UniProtKB:Q02223", "provenance": "manual"}
    assert refs[0]["description"] == "B-cell maturation antigen."
    assert _terms(tmp_path) == []  # aggregate row dropped


def test_migrate_is_idempotent_on_matching_curie(tmp_path: Path) -> None:
    pei = {"source": "UniProtKB", "id": "Q02223", "curie": "UniProtKB:Q02223", "provenance": "manual"}
    _project(
        tmp_path,
        [{"id": "protein:BCMA", "title": "BCMA", "primary_external_id": pei}],
        external_refs=[{"id": "protein:BCMA", "type": "protein", "title": "BCMA", "primary_external_id": pei}],
    )
    report = _run(tmp_path)
    assert "protein:BCMA" in report.migrated
    assert len(_ext_refs(tmp_path)) == 1  # no duplicate appended
    assert _terms(tmp_path) == []  # aggregate row still dropped (reconciled)


def test_migrate_rejects_conflicting_curie_without_mutation(tmp_path: Path) -> None:
    _project(
        tmp_path,
        [{"id": "protein:BCMA", "title": "BCMA",
          "primary_external_id": {"source": "UniProtKB", "id": "NEW", "curie": "UniProtKB:NEW", "provenance": "manual"}}],
        external_refs=[{"id": "protein:BCMA", "type": "protein", "title": "BCMA",
                        "primary_external_id": {"source": "UniProtKB", "id": "OLD", "curie": "UniProtKB:OLD", "provenance": "manual"}}],
    )
    report = _run(tmp_path)
    assert "protein:BCMA" not in report.migrated
    assert any(cid == "protein:BCMA" and "conflict" in reason for cid, reason in report.rejected)
    assert len(_ext_refs(tmp_path)) == 1  # unchanged
    assert _ext_refs(tmp_path)[0]["primary_external_id"]["curie"] == "UniProtKB:OLD"
    assert len(_terms(tmp_path)) == 1  # aggregate row NOT dropped
```

> Note: the conflict test reads an `external_refs.yaml` that already contains `protein:BCMA`; because `CurieRefAdapter` would also load it, `classify_aggregate_rows` still sees the terms.yaml row as the aggregate owner (the curie row defers via Task 6). The migration's own conflict check (Step 4) is what fires, independent of load-time dedup.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/graph/test_aggregate_retire_curie_migration.py -v`
Expected: FAIL — `plan_retirement` has no `migrate_curie_refs` kwarg; `RetirementReport` has no `migrated`.

- [ ] **Step 3: Extend the action/plan/report dataclasses**

In `src/science_tool/graph/aggregate_retire.py`:

Add the action:

```python
class RetireAction(str, Enum):
    PROMOTE = "promote"
    DELETE = "delete"
    MIGRATE_EXTERNAL_REF = "migrate-external-ref"
```

Add a defaulted `migrate` tuple to `RetirementPlan` (default keeps existing constructors valid):

```python
@dataclass(frozen=True, slots=True)
class RetirementPlan:
    promote: tuple[PlannedRow, ...]
    delete: tuple[PlannedRow, ...]
    reconcile: tuple[PlannedRow, ...]
    rejected: tuple[tuple[AggregateRowTriage, str], ...]
    # 4c: CURIE_EXTERNAL_REF rows to migrate into external_refs.yaml then drop.
    migrate: tuple[PlannedRow, ...] = ()
```

Add a defaulted `migrated` tuple to `RetirementReport` (after `dry_run`, so positional construction stays valid):

```python
@dataclass(frozen=True, slots=True)
class RetirementReport:
    promoted: tuple[str, ...]
    deleted: tuple[str, ...]
    rejected: tuple[tuple[str, str], ...]
    skipped: tuple[tuple[str, str], ...]
    files_rewritten: tuple[str, ...]
    dry_run: bool
    migrated: tuple[str, ...] = ()
```

- [ ] **Step 4: Plan + apply the migrate action**

Add the `migrate_curie_refs` kwarg to `plan_retirement`:

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
    migrate_curie_refs: bool = False,
) -> RetirementPlan:
```

Initialize a `migrate` list next to the others (`migrate: list[PlannedRow] = []`) and, in the per-row loop, add a branch for the curie bucket (place it next to the `EXTERNAL_REF` branch, before the coined/shadow handling):

```python
        if triage.bucket is AggregateBucket.CURIE_EXTERNAL_REF:
            if not migrate_curie_refs:
                continue  # untouched unless explicitly migrating curie refs
            migrate.append(PlannedRow(triage, RetireAction.MIGRATE_EXTERNAL_REF, meta.path, meta.line, None))
            continue
```

Return it: `return RetirementPlan(tuple(promote), tuple(delete), tuple(reconcile), tuple(rejected), tuple(migrate))`.

In `apply_retirement`, add the migrate processing. Add the imports at the top of the module:

```python
from science_tool.graph.sources import resolve_local_profile_name, local_profile_sources_dir
```

> `resolve_local_profile_name`/`local_profile_sources_dir` live in `graph/sources.py`. `aggregate_retire.py` already imports `ProjectSources`/`AggregateRowMeta` from there under `TYPE_CHECKING`; these two are runtime helpers, so import them at module top. If that introduces a circular import (sources.py does not import aggregate_retire at module top, so it should not), fall back to a function-local import inside `apply_retirement`.

Add a `migrated` accumulator and process migrate rows **before** the file-rewrite step. Insert this block after the deletes loop (section 3) and before "4. Rewrite each affected aggregate file once":

```python
    # 3b. Curie external-ref migration: append the authority row, then drop the
    #     aggregate row. Idempotent (same curie -> reconcile-drop); conflict-loud.
    migrated: list[str] = []
    if plan.migrate:
        ext_dir = local_profile_sources_dir(project_root, local_profile=resolve_local_profile_name(project_root))
        ext_path = ext_dir / "external_refs.yaml"
        ext_doc = yaml.safe_load(ext_path.read_text(encoding="utf-8")) if ext_path.is_file() else None
        ext_doc = ext_doc or {}
        ext_rows: list[dict] = ext_doc.get("references") or []
        existing = {r.get("id"): r for r in ext_rows if isinstance(r, dict)}
        dirty = False
        for pr in plan.migrate:
            entry = entries(pr.source_path)[pr.line]
            cid = pr.triage.canonical_id
            pei = entry.get("primary_external_id")
            prior = existing.get(cid)
            if prior is not None:
                if prior.get("primary_external_id") != pei:
                    rejected.append((cid, f"external_refs.yaml conflict: {cid} already mapped to a different curie"))
                    continue
                # Already backed with the SAME mapping: reconcile by dropping the stub.
                migrated.append(cid)
                drop_by_file[pr.source_path].add(pr.line)
                continue
            new_row: dict[str, object] = {"id": cid, "type": pr.triage.kind, "title": entry.get("title") or cid}
            new_row["primary_external_id"] = pei
            description = entry.get("description")
            if isinstance(description, str) and description:
                new_row["description"] = description
            ext_rows.append(new_row)
            existing[cid] = new_row
            dirty = True
            migrated.append(cid)
            drop_by_file[pr.source_path].add(pr.line)
        if dirty and not dry_run:
            ext_doc["references"] = ext_rows
            ext_path.parent.mkdir(parents=True, exist_ok=True)
            ext_path.write_text(yaml.safe_dump(ext_doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
```

Finally, include `migrated` in the returned report:

```python
    return RetirementReport(
        tuple(promoted),
        tuple(deleted),
        tuple(rejected),
        tuple(skipped),
        tuple(files_rewritten),
        dry_run,
        tuple(migrated),
    )
```

- [ ] **Step 5: Run the test**

Run: `uv run --frozen pytest tests/graph/test_aggregate_retire_curie_migration.py -v`
Expected: PASS (all 3). Also run the existing retirement suite to confirm the dataclass additions didn't break positional constructors:

Run: `uv run --frozen pytest tests/graph/ -k "aggregate_retire or retire" -q`
Expected: PASS.

- [ ] **Step 6: Lint + commit**

```bash
cd ~/d/science/science
uv run --frozen ruff check src/science_tool/graph/aggregate_retire.py tests/graph/test_aggregate_retire_curie_migration.py
uv run --frozen ruff format src/science_tool/graph/aggregate_retire.py tests/graph/test_aggregate_retire_curie_migration.py
git add src/science_tool/graph/aggregate_retire.py tests/graph/test_aggregate_retire_curie_migration.py
git commit -m "feat(substrate-4c): MIGRATE_EXTERNAL_REF action (write authority row, drop aggregate row; idempotent/conflict-loud)"
```

---

## Task 9: CLI `--migrate-curie-refs`

**Files:**
- Modify: `src/science_tool/cli.py:293-426` (`entities_triage_aggregate_command`)
- Test: `tests/test_cli_triage_curie.py` (new)

**Context:** Add the flag, wire it into `any_bucket`, the usage-error string, the `plan_retirement` call, and the human/json output. Shares the existing v3 `--apply` gate. `migrate_curie_refs` needs no extra inputs (unlike `--retire-external-refs`, which loads bib keys).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_triage_curie.py
from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.cli import main

_MANIFEST_V2 = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 2\nontologies:\n  - biology\n"
_MANIFEST_V3 = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\nontologies:\n  - biology\n"


def _project(root: Path, manifest: str) -> None:
    (root / "science.yaml").write_text(manifest, encoding="utf-8")
    src = root / "knowledge" / "sources" / "local"
    src.mkdir(parents=True, exist_ok=True)
    (src / "terms.yaml").write_text(
        yaml.safe_dump(
            {"terms": [{"id": "protein:BCMA", "title": "BCMA",
                        "primary_external_id": {"source": "UniProtKB", "id": "Q02223",
                                                "curie": "UniProtKB:Q02223", "provenance": "manual"}}]}
        ),
        encoding="utf-8",
    )


def test_dry_run_lists_curie_migration(tmp_path: Path) -> None:
    _project(tmp_path, _MANIFEST_V3)
    res = CliRunner().invoke(
        main,
        ["entities", "triage-aggregate", "--project-root", str(tmp_path),
         "--migrate-curie-refs", "--format", "json"],
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["dry_run"] is True
    assert "protein:BCMA" in payload["migrated"]
    # Dry-run wrote nothing.
    assert not (tmp_path / "knowledge" / "sources" / "local" / "external_refs.yaml").exists()


def test_apply_refused_on_v2(tmp_path: Path) -> None:
    _project(tmp_path, _MANIFEST_V2)
    res = CliRunner().invoke(
        main,
        ["entities", "triage-aggregate", "--project-root", str(tmp_path),
         "--migrate-curie-refs", "--apply"],
    )
    assert res.exit_code != 0
    assert "layout_version" in res.output


def test_apply_without_bucket_flag_is_usage_error(tmp_path: Path) -> None:
    _project(tmp_path, _MANIFEST_V3)
    res = CliRunner().invoke(
        main, ["entities", "triage-aggregate", "--project-root", str(tmp_path), "--apply"]
    )
    assert res.exit_code != 0
    assert "--migrate-curie-refs" in res.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_cli_triage_curie.py -v`
Expected: FAIL — `--migrate-curie-refs` is not a recognized option.

- [ ] **Step 3: Add the option + param**

In `src/science_tool/cli.py`, add the option after `--retire-external-refs`:

```python
@click.option(
    "--migrate-curie-refs",
    is_flag=True,
    help="Migrate `curie-external-ref` rows into knowledge/sources/<profile>/external_refs.yaml, then drop them.",
)
```

Add the parameter to the function signature (after `retire_external_refs: bool,`):

```python
    migrate_curie_refs: bool,
```

- [ ] **Step 4: Wire it through**

Update `any_bucket` and the usage-error string:

```python
    any_bucket = (
        promote_coined or delete_cruft or delete_shadow
        or promote_decisions or retire_external_refs or migrate_curie_refs
    )
```

```python
            raise click.UsageError(
                "--apply requires at least one of --promote-coined/--delete-cruft/--delete-shadow/"
                "--promote-decisions/--retire-external-refs/--migrate-curie-refs."
            )
```

Pass it to `plan_retirement`:

```python
    plan = plan_retirement(
        project_root,
        sources,
        rows,
        promote_coined=promote_coined,
        delete_cruft=delete_cruft,
        delete_shadow=delete_shadow,
        promote_decisions=promote_decisions,
        retire_external_refs=retire_external_refs,
        bib_keys=bib_keys,
        decision_index=decision_index,
        migrate_curie_refs=migrate_curie_refs,
    )
```

Surface `migrated` in both outputs. In the json block add `"migrated": list(report.migrated),`. In the human block, extend the head line and add a loop:

```python
    head = "PLAN (dry-run)" if report.dry_run else "APPLIED"
    click.echo(
        f"{head}: {len(report.promoted)} promoted, {len(report.migrated)} migrated, "
        f"{len(report.deleted)} deleted, {len(report.rejected)} rejected, {len(report.skipped)} skipped"
    )
    for cid in report.promoted:
        click.echo(f"  promote {cid}")
    for cid in report.migrated:
        click.echo(f"  migrate {cid}")
    for cid in report.deleted:
        click.echo(f"  delete  {cid}")
```

(Leave the existing `delete`/`skip` loops; just add the `migrate` loop.)

- [ ] **Step 5: Run the test**

Run: `uv run --frozen pytest tests/test_cli_triage_curie.py -v`
Expected: PASS (all 3). Also run the existing triage CLI tests:

Run: `uv run --frozen pytest tests/ -k "triage" -q`
Expected: PASS (the 3a/3b/4b CLI tests still hold; head-line text changed but those assert on substrings like `PLAN (dry-run)`/specific cids — confirm none pin the exact head string; if one does, update it).

- [ ] **Step 6: Lint + commit**

```bash
cd ~/d/science/science
uv run --frozen ruff check src/science_tool/cli.py tests/test_cli_triage_curie.py
uv run --frozen ruff format src/science_tool/cli.py tests/test_cli_triage_curie.py
git add src/science_tool/cli.py tests/test_cli_triage_curie.py
git commit -m "feat(substrate-4c): science entities triage-aggregate --migrate-curie-refs"
```

---

## Task 10: v3 end-state conformance gate

**Files:**
- Create: `src/science_tool/validate/checks/aggregate_retired.py`
- Modify: `src/science_tool/validate/checks/__init__.py` or the check-registration module (mirror how `aggregate_stub.py` is registered)
- Test: `tests/validate/test_aggregate_retired_gate.py` (new)

**Context:** The existing `check_lone_aggregate_stub` WARNs unconditionally (visibility). 4c adds the executable end-state assertion: at `layout_version >= 3`, any remaining multi-type aggregate owner row is an ERROR — the project claims to have crossed to v3 but still carries fileless aggregate debt. Below v3, this check is silent (the lone-stub WARN already covers visibility). This is what keeps `AggregateAdapter` deletion deferred yet asserted (design §7): the gate stays red for a project (e.g. MM30 with its deferred questions) until every row is retired.

- [ ] **Step 1: Write the failing test**

```python
# tests/validate/test_aggregate_retired_gate.py
from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.validate.checks.aggregate_retired import check_aggregate_retired_at_v3
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


def _ctx(root: Path, layout_version: int, terms: list[dict]) -> ValidateContext:
    (root / "science.yaml").write_text(
        f"name: demo\nprofile: research\nprofiles: {{local: local}}\nlayout_version: {layout_version}\n",
        encoding="utf-8",
    )
    src = root / "knowledge" / "sources" / "local"
    src.mkdir(parents=True, exist_ok=True)
    (src / "terms.yaml").write_text(yaml.safe_dump({"terms": terms}), encoding="utf-8")
    # Real constructor: ValidateContext.from_project_root(root, *, strict, verbose)
    # (context.py:31) — the dataclass __init__ requires many fields, so use the factory.
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def test_v3_residual_aggregate_row_is_error(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, 3, [{"id": "question:open-thing", "title": "Open Thing"}])
    results = list(check_aggregate_retired_at_v3(ctx))
    assert results, "expected an ERROR for a residual aggregate row at v3"
    assert all(r.severity is Severity.ERROR for r in results)
    assert any("question:open-thing" in (r.message or "") for r in results)


def test_v2_residual_aggregate_row_is_silent(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, 2, [{"id": "question:open-thing", "title": "Open Thing"}])
    assert list(check_aggregate_retired_at_v3(ctx)) == []


def test_v3_no_aggregate_rows_is_clean(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n", encoding="utf-8"
    )
    (tmp_path / "knowledge" / "sources" / "local").mkdir(parents=True)
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
    assert list(check_aggregate_retired_at_v3(ctx)) == []
```

> Step 3/4 note: confirm how `aggregate_stub.py` is registered/discovered (read its test + the check-loader) and mirror it for `aggregate_retired.py`. `ValidateContext.from_project_root(root, *, strict, verbose)` is the real factory (`context.py:31`); the bare dataclass `ValidateContext(...)` requires many fields and must not be used.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/validate/test_aggregate_retired_gate.py -v`
Expected: FAIL — module `aggregate_retired` does not exist.

- [ ] **Step 3: Write the check**

```python
# src/science_tool/validate/checks/aggregate_retired.py
"""Conformance check: aggregate manifests must be retired at layout_version >= 3
(design §B5/§C3, Phase 4c).

`check_lone_aggregate_stub` (order=51) WARNs on lone fileless stubs for visibility
while a project is mid-rollout. This check is the executable END-STATE assertion:
once a project declares layout_version >= 3 it claims the v2->v3 migration is done,
so ANY remaining multi-type aggregate (entities.yaml/terms.yaml) owner row is an
ERROR. Below v3 it is silent (the lone-stub WARN already provides visibility). This
keeps the AggregateAdapter deprecated-owner mode loadable for v2 projects while
asserting that no aggregate rows survive into v3 -- the precondition for eventually
deleting that adapter mode.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import yaml

from science_tool.graph.identity_table import build_identity_table
from science_tool.graph.sources import load_project_sources
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def _layout_version(project_root: Path) -> int | None:
    manifest = yaml.safe_load((project_root / "science.yaml").read_text(encoding="utf-8")) or {}
    v = manifest.get("layout_version")
    return v if isinstance(v, int) else None


@Check(section="aggregate retirement end-state (design §B5/§C3)", order=52)
def check_aggregate_retired_at_v3(ctx: ValidateContext) -> Iterator[Result]:
    version = _layout_version(ctx.project_root)
    if version is None or version < 3:
        return  # below v3 the lone-stub WARN covers visibility; this gate is silent
    sources = load_project_sources(
        ctx.project_root,
        include_commons=False,
        strict_core_schema=False,
        strict_identity=False,
    )
    table = build_identity_table(sources)
    for (_scope, canonical_id), rows in sorted(table.owners().items()):
        for row in rows:
            if row.adapter == "aggregate" and row.deprecated:
                path = Path(row.source_ref.path) if row.source_ref else None
                yield Result(
                    Severity.ERROR,
                    path,
                    None,
                    f"{canonical_id}: aggregate (entities.yaml/terms.yaml) row survives at "
                    f"layout_version {version} -- retire it via `science entities triage-aggregate` "
                    "(promote/migrate/delete) before the v2->v3 migration is considered complete.",
                    "aggregate-not-retired-at-v3",
                    None,
                )
```

- [ ] **Step 4: Register the check**

Mirror how `check_lone_aggregate_stub` is registered. Inspect the check-discovery mechanism (e.g. `src/science_tool/validate/checks/__init__.py` or a `_load_canonical_checks` import list) and add `aggregate_retired` alongside `aggregate_stub`. If checks are auto-discovered by module scan, no edit is needed beyond creating the file — confirm by running the validator's check-enumeration test.

- [ ] **Step 5: Run the test + validator self-test**

Run: `uv run --frozen pytest tests/validate/test_aggregate_retired_gate.py -v`
Expected: PASS (all 3).

Run: `uv run --frozen pytest tests/ -k "validate and check" -q`
Expected: PASS — the new check is discovered and does not perturb existing validate enumeration.

- [ ] **Step 6: Lint + commit**

```bash
cd ~/d/science/science
uv run --frozen ruff check src/science_tool/validate/checks/aggregate_retired.py tests/validate/test_aggregate_retired_gate.py
uv run --frozen ruff format src/science_tool/validate/checks/aggregate_retired.py tests/validate/test_aggregate_retired_gate.py
git add src/science_tool/validate/checks/aggregate_retired.py tests/validate/test_aggregate_retired_gate.py
# include the registration file if you edited one
git commit -m "feat(substrate-4c): v3 conformance gate — aggregate rows must be retired at layout_version>=3"
```

---

## Final verification (after all tasks)

- [ ] **Full suite green**

Run: `uv run --frozen pytest -q` (from `~/d/science/science`)
Expected: all pass except the 2 pre-existing `snapshot` formatter fixtures (deselected by default anyway). Confirm the count climbed from the 4b baseline (4843) by the number of new tests.

- [ ] **Lint clean on all touched files**

Run: `uv run --frozen ruff check src/science_tool/ tests/ | grep substrate-4c` is not how to check — instead lint the specific touched files listed across tasks and confirm zero new errors versus the ~174 baseline in untouched files.

- [ ] **Read-only MM30 smoke (still v2 — must refuse `--apply`)**

From the MM30 project root (`~/d/cancer/cancer-types/multiple-myeloma`), with the branch env:
- `science entities triage-aggregate --format json` → buckets now show `curie-external-ref` (~35) + `question-deferred` (~7) + a smaller `ambiguous` (the no-curie disease/drug) instead of the old 96-row `ambiguous`.
- `science entities triage-aggregate --migrate-curie-refs --apply` → **refused, exit 1, names `layout_version 2`**; MM30 stays git-clean.

Record the observed counts in the holistic-review notes.

---

## Self-Review (completed by plan author)

**1. Spec coverage:**
- §3 bucket split → T3 (CURIE_EXTERNAL_REF, QUESTION_DEFERRED, residual AMBIGUOUS) + T2 (curie capture).
- §4.1 authority file + §4.2 CurieRefAdapter (fail-loud dup/malformed, same_as list, file_path, local_profile path) → T4.
- §4.3 generic defer → T6. §4.2 scope → T5.
- §4.4(a) curie via same_as URIRef + §4.4(b) participation gate → T7.
- §4.5 migrate action (idempotent, conflict-loud, resolved path) → T8; CLI flag → T9.
- §5 method/topic slug (+ creation path) → T1. §6 question deferral → T3 (QUESTION_DEFERRED, no action). §7 v3 gate → T10.
- Non-goals (no adapter deletion, no question promotion, no invented curies, no precedence change) are respected — no task touches them.

**2. Placeholder scan:** No TBD/TODO. Two tasks (T7 graph-access idiom, T10 ValidateContext constructor + check registration) explicitly instruct the implementer to mirror a named existing test/module rather than guess — these are grounding instructions, not placeholders, because the exact local API differs and must be read from source.

**3. Type consistency:** `_bucket` 5-arg signature (T3) matches its `classify_aggregate_rows` call (T3). `AggregateRowMeta.primary_external_id` (T2) is read by T3's `has_pei`. `RetirementPlan.migrate` / `RetirementReport.migrated` (T8) are produced by `plan_retirement(..., migrate_curie_refs=...)` and surfaced by the CLI (T9). `CurieRefAdapter(local_profile=...)` ctor (T4) matches its registration (T6). `external_reference_ids` set (T7) is built from `identity_declarations` whose EXTERNAL_REFERENCE rows are produced by T6.

**Known precondition (not a task):** the curie `skos:exactMatch` edge materializes only when the curie's prefix is a declared external prefix — `_EXTERNAL_PREFIXES` ∪ the prefixes from the project's `ontologies:` catalogs (`materialize.py:101`). MM30 *does* declare `ontologies: [biology, chemistry]`, and the biology catalog declares `UniProtKB`/`MONDO`/etc. for biolink:Protein/Disease/etc. — **but MM30's `terms.yaml` rows write `UniProt:Q02223` (prefix `UniProt`), which does not match the catalog's `UniProtKB`.** So on MM30 the curie node + citations resolve, but the exactMatch edge is absent until the prefix strings align. The migration (T8) copies the curie verbatim, preserving whatever MM30 authored. Resolving the edge is an **MM30-data follow-up** (normalize `UniProt:` → `UniProtKB:` in the curies, or add a `UniProt` alias to the biology catalog) — out of scope for 4c, which only needs the framework path to work when prefixes align (T7's fixture uses the catalog-correct `UniProtKB:`). Flag for the holistic review. The node + backed-authority + citation-resolution goals hold on MM30 regardless of the edge.
