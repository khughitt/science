# PubTator3 Relation Seeder (Phase 2b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `science annotate pubtator` so the same `seed_pubtator` run that seeds entity mentions also converts each PubTator3 document-level relation into an `oa:TextQuoteSelector` annotation with a JSON `TextualBody`, anchored to the minimal evidence span where its subject and object concepts co-occur.

**Architecture:** All new code lands in the existing `science/src/science_tool/annotation/pubtator_seed.py`. Relations are parsed from the document-level `record["PubTator3"][0]["relations"]`, each role's concept resolved through the **existing** `concept_iri_for`, and targeted to the smallest covering span of the closest same-passage subject×object mention pair (reusing the 2a passage bridge + offset math). One `merge_planned` call merges entities + relations; `SeedReport` is restructured to keep the two counts separate.

**Tech Stack:** Python 3.11, `httpx` (injected client + `MockTransport` in tests), `uv` workspace, pytest. Reuses `merge_planned` / `read_sidecar` / `write_sidecar` / `verify_path` and the W3C annotation model (`TextualBody`, `Motivation.LINKING`, `PlannedAnnotation`).

**Design doc:** `docs/plans/2026-06-15-pubtator-seeder-phase2b-design.md`.

**Conventions for every task:**
- Work in the worktree: `cd ~/d/science/.worktrees/sub-article-annotation-phase2b`. Verify branch with `git branch --show-current` → must print `feat/sub-article-annotation-phase2b` before committing.
- All `pytest` / `pyright` / `ruff` commands run from the `science/` subdirectory via `uv run --frozen …`.
- No `Co-Authored-By` trailer in commits.
- Phase 2a is shipped; this plan only **adds** relation handling and **restructures** `SeedReport` (an explicit rename, no compatibility aliases).

---

### Task 1: Restructure `SeedReport` (entity / relation split) + migrate callers

This is a pure rename refactor done first, so entity behavior stays green before relations are added. The new report keeps entity and relation counts structurally separate (design decision #10).

**Files:**
- Modify: `science/src/science_tool/annotation/pubtator_seed.py` (the `SeedReport` dataclass ~lines 371-375 and the `seed_pubtator` return ~lines 404-447)
- Modify: `science/src/science_tool/annotation/cli.py:1034-1037` (report printing)
- Test: `science/tests/test_pubtator_seed.py` (migrate 6 assertions: lines 397, 399-400, 415-416, 442-443)

- [ ] **Step 1: Update the existing orchestrator tests to the new field names (they will fail to import/attribute first)**

In `science/tests/test_pubtator_seed.py`, replace the entity-side assertions:

```python
# test_seed_pubtator_end_to_end:
    assert report.entity_written == 6
    # Skips: 1 tmVar (unnormalized) + 1 TP53 (non-persisted INTRO body).
    assert report.entity_skipped.get("unnormalized-concept") == 1
    assert report.entity_skipped.get("non-persisted-passage") == 1

# test_seed_pubtator_idempotent_rerun:
    assert first.entity_written == 6
    assert second.entity_written == 0  # 4-tuple skip -> fully idempotent

# test_seed_pubtator_no_bioc_record_is_noop:
    assert report.entity_written == 0
    assert report.note is not None
```

- [ ] **Step 2: Run the tests to confirm they fail on the old field names**

Run: `cd science && uv run --frozen pytest tests/test_pubtator_seed.py -q`
Expected: FAIL — `AttributeError: 'SeedReport' object has no attribute 'entity_written'`.

- [ ] **Step 3: Restructure `SeedReport` and `seed_pubtator`**

In `pubtator_seed.py`, replace the `SeedReport` dataclass:

```python
@dataclass(frozen=True)
class SeedReport:
    entity_written: int
    entity_skipped: dict[str, int]
    relation_written: int
    relation_skipped: dict[str, int]
    note: str | None = None
```

Then update every `return SeedReport(...)` in `seed_pubtator`. The early-exit/no-op returns become:

```python
    if not resolved.pmid:
        return SeedReport(0, {}, 0, {}, note="no PMID; PubTator3 is PubMed-only")
    ...
    if not record:
        return SeedReport(0, {}, 0, {}, note=f"no PubTator3 record ({err or 'no record'})")
    ...
    if parsed is None:
        return SeedReport(0, {}, 0, {}, note="PubTator3 record had no usable passages")
```

And the final return (entities only for now; relations wired in Task 6):

```python
    sidecar_path = sidecar_for_markdown(source_md)
    sidecar = read_sidecar(sidecar_path) if sidecar_path.exists() else Sidecar()
    new_sidecar, written = merge_planned(sidecar, planned, actor=actor, now=now)
    if written:
        atomic_write_text(sidecar_path, serialize_sidecar(new_sidecar))

    return SeedReport(
        entity_written=len(written),
        entity_skipped=dict(skipped),
        relation_written=0,
        relation_skipped={},
        note=None,
    )
```

(The `skipped: Counter[str]` accumulator and entity planning loop above are unchanged in this task.)

- [ ] **Step 4: Migrate the CLI report printing**

In `science/src/science_tool/annotation/cli.py`, replace lines 1034-1037 with:

```python
    if report.note:
        click.echo(report.note)
    all_skips = {
        **{f"entity:{k}": v for k, v in report.entity_skipped.items()},
        **{f"relation:{k}": v for k, v in report.relation_skipped.items()},
    }
    skips = ", ".join(f"{k}={v}" for k, v in sorted(all_skips.items()))
    click.echo(
        f"Wrote {report.entity_written} entity + {report.relation_written} relation "
        f"annotation(s)" + (f"; skipped {skips}" if skips else "")
    )
```

- [ ] **Step 5: Run the full annotation test suite to confirm green**

Run: `cd science && uv run --frozen pytest tests/test_pubtator_seed.py tests/test_cli_annotate_pubtator.py -q`
Expected: PASS (the CLI test asserts on stdout; confirm it still matches — see Task 6 if its substring needs updating; for now it checks a count that may differ — if it fails on the "Wrote" substring, update that test in this step to expect `Wrote 2 entity + 0 relation annotation(s)`).

- [ ] **Step 6: Type-check and lint**

Run: `cd science && uv run --frozen pyright src/science_tool/annotation/pubtator_seed.py src/science_tool/annotation/cli.py && uv run --frozen ruff check src/science_tool/annotation/pubtator_seed.py`
Expected: no new errors in `pubtator_seed.py` (cli.py has pre-existing unrelated warnings — confirm none are new on lines you touched).

- [ ] **Step 7: Commit**

```bash
cd ~/d/science/.worktrees/sub-article-annotation-phase2b
git add science/src/science_tool/annotation/pubtator_seed.py science/src/science_tool/annotation/cli.py science/tests/test_pubtator_seed.py science/tests/test_cli_annotate_pubtator.py
git commit -m "refactor(pubtator-seed): split SeedReport into entity/relation counts"
```

---

### Task 2: Parse document-level relations (`BiocRelation` + `parse_bioc_relations`)

**Files:**
- Modify: `science/src/science_tool/annotation/pubtator_seed.py` (add after `parse_bioc_entity_annotations`, ~line 133)
- Test: `science/tests/test_pubtator_relations.py` (new)

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_pubtator_relations.py`:

```python
from science_tool.annotation.pubtator_seed import BiocRelation, parse_bioc_relations

# Real-shape relation record (pinned from live PubTator3, PMID 28483577, 2026-06-15).
REL_RECORD = {
    "PubTator3": [
        {
            "relations": [
                {
                    "id": "R1",
                    "infons": {
                        "score": "0.5056",
                        "role1": {"identifier": "MESH:D000068298", "type": "Chemical"},
                        "role2": {"identifier": "MESH:D000068759", "type": "Chemical"},
                        "type": "Cotreatment",
                    },
                },
                {
                    "id": "R2",
                    "infons": {
                        "score": "0.9988",
                        "role1": {"identifier": "MESH:D000068298", "type": "Chemical"},
                        "role2": {"identifier": "MESH:D007249", "type": "Disease"},
                        "type": "Negative_Correlation",
                    },
                },
            ]
        }
    ]
}


def test_parse_bioc_relations_real_shape():
    rels, dropped = parse_bioc_relations(REL_RECORD)
    assert dropped == {}
    assert rels == [
        BiocRelation("Chemical", "MESH:D000068298", "Chemical", "MESH:D000068759", "Cotreatment", 0.5056),
        BiocRelation("Chemical", "MESH:D000068298", "Disease", "MESH:D007249", "Negative_Correlation", 0.9988),
    ]


def test_parse_bioc_relations_counts_malformed():
    rec = {
        "PubTator3": [
            {
                "relations": [
                    {"infons": {"role1": {"identifier": "X", "type": "Gene"}, "type": "Association"}},  # no role2
                    {"infons": {"role1": {"identifier": "X", "type": "Gene"},
                                "role2": {"identifier": "Y", "type": "Gene"}}},  # no type
                    "not-a-dict",
                ]
            }
        ]
    }
    rels, dropped = parse_bioc_relations(rec)
    assert rels == []
    assert dropped == {"malformed-bioc-relation": 3}


def test_parse_bioc_relations_non_numeric_score_is_none():
    rec = {
        "PubTator3": [
            {
                "relations": [
                    {"infons": {"role1": {"identifier": "1", "type": "Gene"},
                                "role2": {"identifier": "2", "type": "Gene"},
                                "type": "Association", "score": "n/a"}}
                ]
            }
        ]
    }
    rels, _ = parse_bioc_relations(rec)
    assert rels[0].score is None


def test_parse_bioc_relations_non_finite_score_is_none():
    rec = {
        "PubTator3": [
            {
                "relations": [
                    {"infons": {"role1": {"identifier": "1", "type": "Gene"},
                                "role2": {"identifier": "2", "type": "Gene"},
                                "type": "Association", "score": "NaN"}},
                    {"infons": {"role1": {"identifier": "1", "type": "Gene"},
                                "role2": {"identifier": "2", "type": "Gene"},
                                "type": "Association", "score": "Infinity"}},
                ]
            }
        ]
    }
    rels, _ = parse_bioc_relations(rec)
    assert [r.score for r in rels] == [None, None]


def test_parse_bioc_relations_no_relations_key():
    assert parse_bioc_relations({"PubTator3": [{"passages": []}]}) == ([], {})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/test_pubtator_relations.py -q`
Expected: FAIL — `ImportError: cannot import name 'BiocRelation'`.

- [ ] **Step 3: Implement `BiocRelation` + `parse_bioc_relations`**

Add `import math` to the top of `pubtator_seed.py` (with the other stdlib imports, before `import re`). Then add after `parse_bioc_entity_annotations` (~line 133):

```python
@dataclass(frozen=True)
class BiocRelation:
    """One PubTator document-level relation: subject/object concept (type+id),
    predicate type, and optional model confidence."""

    subject_type: str
    subject_id: str
    object_type: str
    object_id: str
    rel_type: str
    score: float | None


def _parse_score(raw: Any) -> float | None:
    """PubTator stores `infons.score` as a stringified float; invalid -> None.

    JSON permits only finite numbers for a portable `application/json` body, so NaN
    and infinities are treated like a missing confidence.
    """
    if isinstance(raw, (int, float)):
        value = float(raw)
        return value if math.isfinite(value) else None
    if isinstance(raw, str):
        try:
            value = float(raw)
        except ValueError:
            return None
        return value if math.isfinite(value) else None
    return None


def parse_bioc_relations(
    record: dict[str, Any],
) -> tuple[list[BiocRelation], dict[str, int]]:
    """Flatten the document-level `relations` into ordered rows + a drop-count map.

    Returns `(relations, dropped)`. A relation missing/invalid `role1`/`role2`/`type`
    (or non-dict) is counted under "malformed-bioc-relation" (nothing silent); the
    orchestrator folds this into the report's relation skips.
    """
    dropped: Counter[str] = Counter()
    docs = record.get("PubTator3") or record.get("documents")
    if not isinstance(docs, list) or not docs:
        return [], {}
    doc = docs[0]
    if not isinstance(doc, dict):
        return [], {}
    raw_rels = doc.get("relations")
    if not isinstance(raw_rels, list):
        return [], {}

    relations: list[BiocRelation] = []
    for rel in raw_rels:
        if not isinstance(rel, dict):
            dropped["malformed-bioc-relation"] += 1
            continue
        infons = rel.get("infons")
        infons = infons if isinstance(infons, dict) else {}
        role1, role2 = infons.get("role1"), infons.get("role2")
        rtype = infons.get("type")
        if not isinstance(role1, dict) or not isinstance(role2, dict) or not isinstance(rtype, str) or not rtype:
            dropped["malformed-bioc-relation"] += 1
            continue
        s_type, s_id = role1.get("type"), role1.get("identifier")
        o_type, o_id = role2.get("type"), role2.get("identifier")
        if not (isinstance(s_type, str) and isinstance(s_id, str) and isinstance(o_type, str) and isinstance(o_id, str)):
            dropped["malformed-bioc-relation"] += 1
            continue
        relations.append(
            BiocRelation(
                subject_type=s_type,
                subject_id=s_id,
                object_type=o_type,
                object_id=o_id,
                rel_type=rtype,
                score=_parse_score(infons.get("score")),
            )
        )
    return relations, dict(dropped)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run --frozen pytest tests/test_pubtator_relations.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/.worktrees/sub-article-annotation-phase2b
git add science/src/science_tool/annotation/pubtator_seed.py science/tests/test_pubtator_relations.py
git commit -m "feat(pubtator-seed): parse document-level BioC relations"
```

---

### Task 3: Predicate map (`RELATION_PREDICATES` + `predicate_for`)

**Files:**
- Modify: `science/src/science_tool/annotation/pubtator_seed.py` (add after `concept_iri_for`, ~line 216)
- Test: `science/tests/test_pubtator_relations.py`

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_pubtator_relations.py`:

```python
import pytest

from science_tool.annotation.pubtator_seed import predicate_for


@pytest.mark.parametrize(
    "rel_type,curie,source",
    [
        ("Association", "biolink:associated_with", "biolink"),
        ("Positive_Correlation", "biolink:positively_correlated_with", "biolink"),
        ("Negative_Correlation", "biolink:negatively_correlated_with", "biolink"),
        ("Bind", "biolink:directly_physically_interacts_with", "biolink"),
        ("Drug_Interaction", "biolink:interacts_with", "biolink"),
        ("Cotreatment", "sci:cotreatment", "sci"),
        ("Comparison", "sci:comparison", "sci"),
        ("Conversion", "sci:conversion", "sci"),
    ],
)
def test_predicate_for_known_types(rel_type, curie, source):
    assert predicate_for(rel_type) == (curie, source, None)


def test_predicate_for_is_case_insensitive():
    assert predicate_for("negative_correlation") == ("biolink:negatively_correlated_with", "biolink", None)
    assert predicate_for("COTREATMENT") == ("sci:cotreatment", "sci", None)


def test_predicate_for_unexpected_type_sanitized():
    # Unknown type -> sci:pubtator_<slug>, raw type preserved, never dropped.
    assert predicate_for("Some New/Weird Type!") == (
        "sci:pubtator_some_new_weird_type_",
        "sci",
        "Some New/Weird Type!",
    )
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/test_pubtator_relations.py -k predicate -q`
Expected: FAIL — `ImportError: cannot import name 'predicate_for'`.

- [ ] **Step 3: Implement the map + sanitizer**

In `pubtator_seed.py`, add after `concept_iri_for` (~line 216):

```python
# --- Relation type -> predicate CURIE ----------------------------------------

# PubTator3 uses the fixed BioRED 8-type relation set. Clean Biolink predicate where
# one exists, else a `sci:` project predicate. Keys are matched case-insensitively
# (lowercased). See docs/conventions/annotation-tokens.md.
RELATION_PREDICATES: dict[str, tuple[str, str]] = {
    "association": ("biolink:associated_with", "biolink"),
    "positive_correlation": ("biolink:positively_correlated_with", "biolink"),
    "negative_correlation": ("biolink:negatively_correlated_with", "biolink"),
    "bind": ("biolink:directly_physically_interacts_with", "biolink"),
    "drug_interaction": ("biolink:interacts_with", "biolink"),
    "cotreatment": ("sci:cotreatment", "sci"),
    "comparison": ("sci:comparison", "sci"),
    "conversion": ("sci:conversion", "sci"),
}

_PRED_SLUG_BAD = re.compile(r"[^a-z0-9_]")


def predicate_for(rel_type: str) -> tuple[str, str, str | None]:
    """Map a PubTator relation type to (predicate_curie, predicate_source, raw_or_None).

    Known BioRED types return (curie, "biolink"|"sci", None). An unexpected type is
    NOT dropped: it returns ("sci:pubtator_<slug>", "sci", <verbatim raw type>) where
    <slug> lowercases the raw type and replaces every non-[a-z0-9_] char with "_", so
    the data is preserved without pretending it is a curated project predicate.
    """
    mapped = RELATION_PREDICATES.get(rel_type.strip().lower())
    if mapped is not None:
        return mapped[0], mapped[1], None
    slug = _PRED_SLUG_BAD.sub("_", rel_type.strip().lower())
    return f"sci:pubtator_{slug}", "sci", rel_type
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run --frozen pytest tests/test_pubtator_relations.py -k predicate -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/.worktrees/sub-article-annotation-phase2b
git add science/src/science_tool/annotation/pubtator_seed.py science/tests/test_pubtator_relations.py
git commit -m "feat(pubtator-seed): BioRED relation-type -> predicate map"
```

---

### Task 4: Deterministic relation body JSON (`relation_body_json`)

**Files:**
- Modify: `science/src/science_tool/annotation/pubtator_seed.py` (add after `predicate_for`)
- Test: `science/tests/test_pubtator_relations.py`

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_pubtator_relations.py`:

```python
import json

from science_tool.annotation.pubtator_seed import relation_body_json


def test_relation_body_json_deterministic_and_sorted():
    body = relation_body_json(
        subject_iri="https://identifiers.org/ncbigene:672",
        object_iri="https://identifiers.org/mesh:D001943",
        predicate="biolink:associated_with",
        predicate_source="biolink",
        raw_predicate_type=None,
        score=0.97,
    )
    # Compact separators, sorted keys, byte-stable.
    assert body == (
        '{"object":"https://identifiers.org/mesh:D001943",'
        '"predicate":"biolink:associated_with",'
        '"predicate_source":"biolink",'
        '"score":0.97,'
        '"subject":"https://identifiers.org/ncbigene:672"}'
    )
    assert json.loads(body)["score"] == 0.97


def test_relation_body_json_omits_optional_fields():
    body = relation_body_json(
        subject_iri="a", object_iri="b",
        predicate="sci:cotreatment", predicate_source="sci",
        raw_predicate_type=None, score=None,
    )
    obj = json.loads(body)
    assert "score" not in obj
    assert "raw_predicate_type" not in obj


def test_relation_body_json_includes_raw_predicate_type_when_present():
    body = relation_body_json(
        subject_iri="a", object_iri="b",
        predicate="sci:pubtator_weird", predicate_source="sci",
        raw_predicate_type="Weird", score=None,
    )
    assert json.loads(body)["raw_predicate_type"] == "Weird"


def test_relation_body_json_omits_non_finite_score():
    body = relation_body_json(
        subject_iri="a", object_iri="b",
        predicate="sci:cotreatment", predicate_source="sci",
        raw_predicate_type=None, score=float("nan"),
    )
    obj = json.loads(body)
    assert "score" not in obj
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/test_pubtator_relations.py -k body_json -q`
Expected: FAIL — `ImportError: cannot import name 'relation_body_json'`.

- [ ] **Step 3: Implement**

Add `import json` to the top of `pubtator_seed.py` (with the other stdlib imports, before `import math` / `import re` if Task 2 already added `math`). Then add after `predicate_for`:

```python
def relation_body_json(
    *,
    subject_iri: str,
    object_iri: str,
    predicate: str,
    predicate_source: str,
    raw_predicate_type: str | None,
    score: float | None,
) -> str:
    """Build the deterministic JSON for a relation's TextualBody.

    Always carries subject / predicate / object / predicate_source. `raw_predicate_type`
    is included only for unmapped types; `score` only when PubTator supplied a numeric
    confidence. Serialized with sorted keys + compact separators so re-runs are
    byte-stable (stable content_hash, no sidecar churn).
    """
    obj: dict[str, Any] = {
        "subject": subject_iri,
        "predicate": predicate,
        "object": object_iri,
        "predicate_source": predicate_source,
    }
    if raw_predicate_type is not None:
        obj["raw_predicate_type"] = raw_predicate_type
    if score is not None and math.isfinite(score):
        obj["score"] = score
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run --frozen pytest tests/test_pubtator_relations.py -k body_json -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/.worktrees/sub-article-annotation-phase2b
git add science/src/science_tool/annotation/pubtator_seed.py science/tests/test_pubtator_relations.py
git commit -m "feat(pubtator-seed): deterministic relation body JSON"
```

---

### Task 5: Relation targeting (`ResolvedMention`, `resolve_persisted_mentions`, `plan_relation`)

This is the heart: resolve every persisted+normalizable mention to an absolute file index grouped by concept IRI, then anchor each relation to the smallest covering span of the closest same-passage subject×object pair.

**Files:**
- Modify: `science/src/science_tool/annotation/pubtator_seed.py` (add after `plan_mention`, ~line 366)
- Test: `science/tests/test_pubtator_relations.py`

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_pubtator_relations.py`:

```python
from science_tool.annotation.model import Motivation, TextualBody
from science_tool.annotation.pubtator_seed import (
    PairedPassage,
    ResolvedMention,
    plan_relation,
)

# A single passage spanning file indices [0, 40); bioc offset 0.
_PASSAGE = PairedPassage(bioc_offset=0, bioc_len=40, file_char_base=0)
_TEXT = "BRCA1 raises risk of breast cancer a lot."
#         0....5         ........21...........  (BRCA1 @0:5, breast cancer @21:13)

GENE = "https://identifiers.org/ncbigene:672"
DIS = "https://identifiers.org/mesh:D001943"


def _mentions():
    return {
        GENE: [ResolvedMention(iri=GENE, file_idx=0, length=5, passage=_PASSAGE)],
        DIS: [ResolvedMention(iri=DIS, file_idx=21, length=13, passage=_PASSAGE)],
    }


def _rel(subj=("Gene", "672"), obj=("Disease", "MESH:D001943"), rtype="Association", score=0.9):
    return BiocRelation(subj[0], subj[1], obj[0], obj[1], rtype, score)


def test_plan_relation_minimal_covering_span():
    planned, reason = plan_relation(
        _TEXT, _rel(), _mentions(), release="2025-01", source_md_name="x.source.md"
    )
    assert reason is None
    assert planned is not None
    # Covering span = BRCA1 start (0) .. breast cancer end (34).
    assert planned.target.selector.exact == _TEXT[0:34]
    assert planned.annotation_type == "relation"
    assert planned.motivation == Motivation.LINKING
    assert isinstance(planned.body, TextualBody)
    assert planned.body.format == "application/json"
    body = json.loads(planned.body.value)
    assert body["subject"] == GENE and body["object"] == DIS
    assert body["predicate"] == "biolink:associated_with"
    # match_text = predicate|subj|obj|span_start:span_length
    assert planned.match_text == f"biolink:associated_with|{GENE}|{DIS}|0:34"
    assert planned.source_name == "pubtator3:2025-01:seeder-v1"


def test_plan_relation_picks_closest_pair():
    # Two gene mentions; the nearer one to the disease wins the minimal span.
    mentions = {
        GENE: [
            ResolvedMention(iri=GENE, file_idx=0, length=5, passage=_PASSAGE),
            ResolvedMention(iri=GENE, file_idx=15, length=5, passage=_PASSAGE),
        ],
        DIS: [ResolvedMention(iri=DIS, file_idx=21, length=13, passage=_PASSAGE)],
    }
    planned, _ = plan_relation(_TEXT, _rel(), mentions, release="r", source_md_name="x")
    # Closest gene (file_idx 15) .. disease end (34): span [15, 34).
    assert planned.target.selector.exact == _TEXT[15:34]
    assert planned.match_text.endswith("|15:19")


def test_plan_relation_tie_breaks_by_earliest_span_start():
    text = "AAAAAxxBBBBByyCCCCC"
    left = "https://identifiers.org/ncbigene:672"
    right = "https://identifiers.org/ncbigene:7157"
    mentions = {
        left: [
            ResolvedMention(iri=left, file_idx=0, length=5, passage=_PASSAGE),
            ResolvedMention(iri=left, file_idx=7, length=5, passage=_PASSAGE),
        ],
        right: [
            ResolvedMention(iri=right, file_idx=7, length=5, passage=_PASSAGE),
            ResolvedMention(iri=right, file_idx=14, length=5, passage=_PASSAGE),
        ],
    }
    rel = BiocRelation("Gene", "672", "Gene", "7157", "Association", None)
    planned, reason = plan_relation(text, rel, mentions, release="r", source_md_name="x")
    assert reason is None
    assert planned is not None
    # Candidate spans [0, 12) and [7, 19) are both length 12; earliest start wins.
    assert planned.target.selector.exact == text[0:12]
    assert planned.match_text.endswith("|0:12")


def test_plan_relation_unnormalized_concept_skips():
    planned, reason = plan_relation(
        _TEXT, _rel(obj=("Disease", "OMIM:99999")), _mentions(),
        release="r", source_md_name="x",
    )
    assert planned is None and reason == "relation-unnormalized-concept"


def test_plan_relation_no_persisted_mentions_skips():
    # Object concept resolves but has no persisted mention.
    planned, reason = plan_relation(
        _TEXT, _rel(obj=("Gene", "7157")), _mentions(), release="r", source_md_name="x"
    )
    assert planned is None and reason == "relation-no-persisted-mentions"


def test_plan_relation_cross_passage_skips():
    other = PairedPassage(bioc_offset=100, bioc_len=20, file_char_base=100)
    mentions = {
        GENE: [ResolvedMention(iri=GENE, file_idx=0, length=5, passage=_PASSAGE)],
        DIS: [ResolvedMention(iri=DIS, file_idx=100, length=13, passage=other)],
    }
    planned, reason = plan_relation(_TEXT + " " * 80 + "breast cancer", _rel(), mentions, release="r", source_md_name="x")
    assert planned is None and reason == "relation-cross-passage"


def test_resolve_persisted_mentions_groups_by_iri():
    from science_tool.annotation.pubtator_seed import resolve_persisted_mentions

    file_text = "BRCA1 and breast cancer"  # BRCA1 @0:5, breast cancer @10:13
    paired = [PairedPassage(bioc_offset=0, bioc_len=23, file_char_base=0)]
    mentions = [
        BiocMention(pubtator_type="Gene", identifier="672", text="BRCA1", offset=0, length=5),
        BiocMention(pubtator_type="Disease", identifier="MESH:D001943", text="breast cancer", offset=10, length=13),
        BiocMention(pubtator_type="Gene", identifier="7157", text="TP53", offset=500, length=4),  # non-persisted
    ]
    grouped = resolve_persisted_mentions(file_text, paired, mentions)
    assert set(grouped) == {GENE, DIS}  # TP53 (non-persisted) excluded
    assert grouped[GENE][0].file_idx == 0
```

Add the `BiocMention` import to the existing import block at the top of the test file:
`from science_tool.annotation.pubtator_seed import (..., BiocMention, ...)`.

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/test_pubtator_relations.py -k "plan_relation or resolve_persisted" -q`
Expected: FAIL — `ImportError: cannot import name 'ResolvedMention'`.

- [ ] **Step 3: Implement**

In `pubtator_seed.py`, add after `plan_mention` (~line 366):

```python
# --- Relation -> PlannedAnnotation conversion ---------------------------------


@dataclass(frozen=True)
class ResolvedMention:
    """A persisted, normalizable entity mention located at an absolute file index."""

    iri: str
    file_idx: int
    length: int
    passage: PairedPassage


def resolve_persisted_mentions(
    file_text: str,
    paired: list[PairedPassage],
    mentions: list[BiocMention],
) -> dict[str, list[ResolvedMention]]:
    """Group persisted + normalizable mentions by concept IRI, with absolute file index.

    A mention is included only if it (a) falls inside a persisted passage and (b) has a
    normalizable concept IRI. The slice-verify guard mirrors plan_mention: a mapped slice
    that does not equal the mention text is a hard SourceTextError (never a mis-placed
    anchor). Used by plan_relation to find subject/object evidence spans.
    """
    grouped: dict[str, list[ResolvedMention]] = {}
    for m in mentions:
        pp = _containing(paired, m.offset, m.length)
        if pp is None:
            continue
        iri = concept_iri_for(m.pubtator_type, m.identifier)
        if iri is None:
            continue
        file_idx = pp.file_char_base + (m.offset - pp.bioc_offset)
        exact = file_text[file_idx : file_idx + m.length]
        if exact != m.text:
            raise SourceTextError(
                f"offset slice {exact!r} != BioC mention text {m.text!r} "
                f"at file index {file_idx} (offset drift); aborting"
            )
        grouped.setdefault(iri, []).append(
            ResolvedMention(iri=iri, file_idx=file_idx, length=m.length, passage=pp)
        )
    return grouped


def plan_relation(
    file_text: str,
    relation: BiocRelation,
    mentions_by_iri: dict[str, list[ResolvedMention]],
    *,
    release: str,
    source_md_name: str,
) -> tuple[PlannedAnnotation | None, str | None]:
    """Convert a BiocRelation to a PlannedAnnotation, or (None, skip_reason).

    Skip reasons: "relation-unnormalized-concept" (a role id does not normalize),
    "relation-no-persisted-mentions" (a role concept has no persisted mention),
    "relation-cross-passage" (both persisted but never co-occur in one passage).
    Target = the smallest covering span of the closest same-passage subject x object
    mention pair; prefix/suffix clamped to that passage.
    """
    subject_iri = concept_iri_for(relation.subject_type, relation.subject_id)
    object_iri = concept_iri_for(relation.object_type, relation.object_id)
    if subject_iri is None or object_iri is None:
        return None, "relation-unnormalized-concept"

    subj_mentions = mentions_by_iri.get(subject_iri, [])
    obj_mentions = mentions_by_iri.get(object_iri, [])
    if not subj_mentions or not obj_mentions:
        return None, "relation-no-persisted-mentions"

    best: tuple[int, int, int] | None = None  # (span_len, span_start, span_end)
    best_passage: PairedPassage | None = None
    for s in subj_mentions:
        for o in obj_mentions:
            if s.passage != o.passage:
                continue
            span_start = min(s.file_idx, o.file_idx)
            span_end = max(s.file_idx + s.length, o.file_idx + o.length)
            cand = (span_end - span_start, span_start, span_end)
            if best is None or cand < best:
                best = cand
                best_passage = s.passage
    if best is None:
        return None, "relation-cross-passage"
    assert best_passage is not None

    _, span_start, span_end = best
    exact = file_text[span_start:span_end]
    passage_start = best_passage.file_char_base
    passage_end = best_passage.file_char_base + best_passage.bioc_len
    prefix_start = max(passage_start, span_start - _CONTEXT)
    suffix_end = min(passage_end, span_end + _CONTEXT)
    selector = TextQuoteSelector(
        exact=exact,
        prefix=file_text[prefix_start:span_start],
        suffix=file_text[span_end:suffix_end],
    )

    predicate, predicate_source, raw_predicate_type = predicate_for(relation.rel_type)
    body = relation_body_json(
        subject_iri=subject_iri,
        object_iri=object_iri,
        predicate=predicate,
        predicate_source=predicate_source,
        raw_predicate_type=raw_predicate_type,
        score=relation.score,
    )
    span_length = span_end - span_start
    match_text = f"{predicate}|{subject_iri}|{object_iri}|{span_start}:{span_length}"
    planned = PlannedAnnotation(
        target=SpecificResource(source=source_md_name, selector=selector),
        annotation_type="relation",
        motivation=Motivation.LINKING,
        body=TextualBody(value=body, format="application/json"),
        match_text=match_text,
        source_name=f"pubtator3:{release}:seeder-v1",
    )
    return planned, None
```

Add `TextualBody` to the existing model import block at the top of `pubtator_seed.py`:
```python
from science_tool.annotation.model import (
    IriBody,
    Motivation,
    Sidecar,
    SpecificResource,
    TextQuoteSelector,
    TextualBody,
)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run --frozen pytest tests/test_pubtator_relations.py -q`
Expected: PASS (all relation tests).

- [ ] **Step 5: Type-check and lint**

Run: `cd science && uv run --frozen pyright src/science_tool/annotation/pubtator_seed.py && uv run --frozen ruff check src/science_tool/annotation/pubtator_seed.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
cd ~/d/science/.worktrees/sub-article-annotation-phase2b
git add science/src/science_tool/annotation/pubtator_seed.py science/tests/test_pubtator_relations.py
git commit -m "feat(pubtator-seed): minimal-covering-span relation targeting"
```

---

### Task 6: Wire relations into `seed_pubtator` + end-to-end

**Files:**
- Modify: `science/src/science_tool/annotation/pubtator_seed.py` (`seed_pubtator`, the entity-planning section ~lines 427-447)
- Test: `science/tests/test_pubtator_seed.py` (extend `BIOC_FIXTURE`, add relation assertions)

- [ ] **Step 1: Add relations to `BIOC_FIXTURE` and write the failing end-to-end assertions**

In `science/tests/test_pubtator_seed.py`, add a `"relations"` key to the document in `BIOC_FIXTURE` (sibling of `"passages"`, inside the `"PubTator3"[0]` dict):

```python
            "relations": [
                {
                    "id": "R1",
                    "infons": {
                        "role1": {"identifier": "672", "type": "Gene"},
                        "role2": {"identifier": "MESH:D001943", "type": "Disease"},
                        "type": "Association",
                        "score": "0.95",
                    },
                },
                {
                    "id": "R2",
                    "infons": {
                        "role1": {"identifier": "672", "type": "Gene"},
                        "role2": {"identifier": "MESH:D013629", "type": "Chemical"},
                        "type": "Negative_Correlation",
                    },
                },
            ],
```

R1 (BRCA1 gene 672 ↔ breast cancer disease D001943) both live in the **title** passage → one relation written. R2 (BRCA1 in title ↔ Tamoxifen chemical in abstract) is persisted on both sides but in **different** passages → `relation-cross-passage` skip.

Then extend the orchestrator assertions:

```python
# in test_seed_pubtator_end_to_end, after the entity assertions:
    assert report.relation_written == 1            # BRCA1 -- breast cancer (title passage)
    assert report.relation_skipped.get("relation-cross-passage") == 1  # BRCA1 -- Tamoxifen

    sidecar = read_sidecar(sidecar_for_markdown(source_md))
    assert len(sidecar.annotations) == 7           # 6 entity + 1 relation
    rels = [a for a in sidecar.annotations if a.annotation_type == "relation"]
    assert len(rels) == 1
    assert rels[0].motivation == Motivation.LINKING
```

Update the existing `len(sidecar.annotations) == 6` line in that test to the `== 7` above (replace, do not duplicate). And in `test_seed_pubtator_idempotent_rerun` add:

```python
    assert first.relation_written == 1
    assert second.relation_written == 0  # relations are idempotent too
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/test_pubtator_seed.py -q`
Expected: FAIL — `report.relation_written == 1` fails (still 0; relations not wired).

- [ ] **Step 3: Wire relations into `seed_pubtator`**

In `pubtator_seed.py`, replace the entity-planning + merge tail of `seed_pubtator` (from the `planned = []` entity loop through the final `return`) with:

```python
    entity_skipped: Counter[str] = Counter(skipped)  # carries parse_drops from above
    planned: list[PlannedAnnotation] = []
    for m in mentions:
        p, reason = plan_mention(
            file_text, paired, m, release=release, source_md_name=source_md.name
        )
        if p is not None:
            planned.append(p)
        elif reason is not None:
            entity_skipped[reason] += 1

    # Relations: same record, same paired passages, same normalized-mention index.
    relations, rel_drops = parse_bioc_relations(record)
    relation_skipped: Counter[str] = Counter(rel_drops)  # malformed-bioc-relation, not silent
    mentions_by_iri = resolve_persisted_mentions(file_text, paired, mentions)
    rel_planned: list[PlannedAnnotation] = []
    for r in relations:
        p, reason = plan_relation(
            file_text, r, mentions_by_iri, release=release, source_md_name=source_md.name
        )
        if p is not None:
            rel_planned.append(p)
        elif reason is not None:
            relation_skipped[reason] += 1

    sidecar_path = sidecar_for_markdown(source_md)
    sidecar = read_sidecar(sidecar_path) if sidecar_path.exists() else Sidecar()
    new_sidecar, written = merge_planned(sidecar, planned + rel_planned, actor=actor, now=now)
    if written:
        atomic_write_text(sidecar_path, serialize_sidecar(new_sidecar))

    # Partition the written rows by annotation_type to report entity vs relation counts.
    rel_written = sum(1 for a in written if a.annotation_type == "relation")
    return SeedReport(
        entity_written=len(written) - rel_written,
        entity_skipped=dict(entity_skipped),
        relation_written=rel_written,
        relation_skipped=dict(relation_skipped),
        note=None,
    )
```

Note: this replaces the earlier `skipped`-based tail from Task 1. The `skipped: Counter[str]` declared near the top of `seed_pubtator` (which `.update(parse_drops)` populated) is now consumed via `Counter(skipped)` into `entity_skipped` — verify the parse-drop folding still happens before this block (the `skipped.update(parse_drops)` line stays where it is). Confirm `written` elements expose `.annotation_type` (they are `Annotation` instances — they do).

- [ ] **Step 4: Run the end-to-end + verifier + idempotency tests**

Run: `cd science && uv run --frozen pytest tests/test_pubtator_seed.py -q`
Expected: PASS — including `test_seeded_selectors_resolve_via_verifier` (every relation selector re-resolves: `.broken == 0`, `.fuzzy == 0`).

- [ ] **Step 5: Update the CLI end-to-end test for the combined summary**

Run: `cd science && uv run --frozen pytest tests/test_cli_annotate_pubtator.py -q`
Expected: if it asserts on the old `Wrote N annotation(s)` substring, update that assertion to match the new combined line, e.g.:
```python
    assert "entity" in result.output and "relation" in result.output
```
(Match whatever counts the CLI fixture produces; assert on the stable `entity`/`relation` words rather than exact numbers if the fixture has no relations.)

- [ ] **Step 6: Full suite + type-check + lint**

Run: `cd science && uv run --frozen pytest tests/test_pubtator_seed.py tests/test_pubtator_relations.py tests/test_cli_annotate_pubtator.py -q && uv run --frozen pyright src/science_tool/annotation/pubtator_seed.py && uv run --frozen ruff check src/science_tool/annotation/pubtator_seed.py`
Expected: all PASS, pyright/ruff clean.

- [ ] **Step 7: Commit**

```bash
cd ~/d/science/.worktrees/sub-article-annotation-phase2b
git add science/src/science_tool/annotation/pubtator_seed.py science/tests/test_pubtator_seed.py science/tests/test_cli_annotate_pubtator.py
git commit -m "feat(pubtator-seed): seed relations alongside entities in one run"
```

---

### Task 7: Register relation vocabulary in the conventions doc

**Files:**
- Modify: `docs/conventions/annotation-tokens.md`

- [ ] **Step 1: Append the relation-seeding section**

After the existing "PubTator3 entity-mention seeding (Phase 2a)" section, add:

````markdown
### PubTator3 relation seeding (Phase 2b)

`science annotate pubtator <pmid|doi>` also seeds **document-level relations** from the
same BioC record, alongside entity mentions, under the same
`pubtator3:<release>:seeder-v1` source.

- **`annotation_type`:** `relation`. **Motivation:** `oa:linking`.
- **Target:** the smallest covering span of the closest subject×object entity-mention
  pair within a single persisted passage (PubTator supplies no relation offset).
- **Body:** one `TextualBody` with `format = "application/json"`, carrying a
  deterministic JSON object (`json.dumps(sort_keys=True, separators=(",", ":"))`):
  - always `subject`, `predicate`, `object`, `predicate_source` (`"biolink"` | `"sci"`)
  - `raw_predicate_type` only when the PubTator relation type is unmapped
  - `score` only when PubTator supplied a numeric confidence (excluded from identity)

#### Relation-type → predicate map (BioRED 8-type set)

| PubTator `infons.type` | predicate | source |
|---|---|---|
| `Association` | `biolink:associated_with` | biolink |
| `Positive_Correlation` | `biolink:positively_correlated_with` | biolink |
| `Negative_Correlation` | `biolink:negatively_correlated_with` | biolink |
| `Bind` | `biolink:directly_physically_interacts_with` | biolink |
| `Drug_Interaction` | `biolink:interacts_with` | biolink |
| `Cotreatment` | `sci:cotreatment` | sci |
| `Comparison` | `sci:comparison` | sci |
| `Conversion` | `sci:conversion` | sci |

`Drug_Interaction` maps to the broad `biolink:interacts_with`; promotion (Phase 4) may
specialize it. Any unexpected/future type maps to `sci:pubtator_<slug>` (lowercased,
non-`[a-z0-9_]` → `_`) with the verbatim type preserved in `raw_predicate_type` —
never dropped, never presented as a curated predicate.
````

- [ ] **Step 2: Commit**

```bash
cd ~/d/science/.worktrees/sub-article-annotation-phase2b
git add docs/conventions/annotation-tokens.md
git commit -m "doc(annotation-tokens): register relation type + predicate map (Phase 2b)"
```

---

### Final verification (after all tasks)

- [ ] **Run the full project test suite**

Run: `cd science && uv run --frozen pytest -q`
Expected: all pass (Phase 2a's 98 feature tests + the new relation tests). Report the exact pass/skip counts.

- [ ] **Confirm branch + clean tree**

Run: `cd ~/d/science/.worktrees/sub-article-annotation-phase2b && git branch --show-current && git status --short`
Expected: `feat/sub-article-annotation-phase2b`, clean tree.

Then proceed to **superpowers:finishing-a-development-branch**.

---

## Self-Review

**Spec coverage** (design doc → task):
- Targeting (minimal covering span, same-passage, explicit earliest-start tie-break) → Task 5 ✓
- Three skip reasons (unnormalized / no-persisted / cross-passage) → Task 5 ✓ (+ end-to-end cross-passage in Task 6)
- `concept_iri_for` reuse for roles → Task 5 (`plan_relation`, `resolve_persisted_mentions`) ✓
- Predicate map (8 types + case-insensitive + `sci:pubtator_<slug>` + `raw_predicate_type`) → Task 3 ✓
- Body (deterministic strict JSON, optional finite score, LINKING, `relation` type, no model change) → Task 4 + Task 5 ✓
- `score` optional, finite-only, and excluded from `match_text` → Task 2 (finite parse) + Task 4 (omit non-finite) + Task 5 (`match_text` has no score) ✓
- `match_text = predicate|subj|obj|start:length` → Task 5 ✓
- Source `pubtator3:<release>:seeder-v1`, additive/idempotent → Task 5 + Task 6 (idempotency assertions) ✓
- `SeedReport` entity/relation split + caller migration → Task 1 ✓
- `parse_bioc_relations` + malformed counting → Task 2 ✓
- Verifier round-trip → Task 6 (reuses existing `test_seeded_selectors_resolve_via_verifier`) ✓
- Conventions registration → Task 7 ✓

**Placeholder scan:** none — every code step shows complete code; every run step gives an exact command + expected result.

**Type consistency:** `BiocRelation` (6 fields) used identically in Tasks 2/5/6. `ResolvedMention` (iri/file_idx/length/passage) defined in Task 5, used by `resolve_persisted_mentions` + `plan_relation`. `predicate_for → (curie, source, raw|None)` consumed by `relation_body_json` (Task 4) and `plan_relation` (Task 5) with matching arity. `relation_body_json` keyword-only signature matches its call in `plan_relation`. `SeedReport` field names (`entity_written`/`entity_skipped`/`relation_written`/`relation_skipped`/`note`) consistent across Tasks 1/6 and the CLI (Task 1) + tests (Tasks 1/6).
