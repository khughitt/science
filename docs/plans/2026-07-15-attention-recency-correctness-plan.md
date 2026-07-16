# Attention-ranking recency correctness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the redundant, inert-and-perverse `days_since_last_review`
multiplicative term from the attention weight, and surface an honest
`last_reviewed` (ISO date / never) in its place.

**Architecture:** Recency already flows through the bounded `freshness_multiplier`
(derived from `sci:freshnessState`). The raw-days term is a strictly worse
duplicate, so it is removed. `sci:lastReviewed` is still read — but only as
reviewer-facing context (`AttentionCandidate.last_reviewed: date | None`), parsed
strictly against its canonical `YYYY-MM-DD` producer form, with absence → `None`
and corruption → `ValueError`. Once the term is gone, the `today` parameter it
fed becomes dead across the attention/wander call chain and is removed.

**Tech Stack:** Python ≥3.11, rdflib, Click, Pydantic/dataclasses, pytest.
Package lives under `science/` (`src/science_tool/`).

**Design:** `docs/plans/2026-07-15-attention-recency-correctness-design.md`.

## Global Constraints

- All commands run from the `science/` package dir: `cd science && uv run --frozen pytest`; lint `uv run ruff check`; types `uv run pyright`. (Getting the dir wrong is the most common mistake — never run `uv run` from repo root.)
- Canonical `sci:lastReviewed` lexical form is **exactly `YYYY-MM-DD`** — enforced by a round-trip check `parsed.isoformat() == text`, deliberately narrower than the full `xsd:date` space (rejects compact `20260501` and ISO-week `2026-W18-5`).
- Absence (no triple) → `None`; present-but-invalid → `ValueError` naming the entity id and raw value. Never collapse the two (fail early; corrupt data is not absence).
- No compatibility/legacy layer, no `Unified` prefix, no AI-attribution trailers on commits.
- Use `~/d/` (not `/home/keith/d/` or `/mnt/ssd/...`) for any filepaths written into docs/code.
- Dropbox branch volatility: this work is on branch `attention-recency-correctness`; **verify the branch before every commit** (`git branch --show-current`); never `git stash`; nothing is pushed unless the user asks.
- Every task ends green: `cd science && uv run --frozen pytest && uv run ruff check && uv run pyright`.

The tasks are **strictly sequential** (1 → 2 → 3 → 4): Task 2 wires the helper
Task 1 adds and depends on Task 2's semantic change being in place before Task 3
removes the now-dead `today`.

---

### Task 1: `_last_reviewed_date` strict-parse helper (isolated TDD)

Add the new helper **alongside** the existing `_days_since_last_review` (which
Task 2 removes). This isolates the subtle strict-parse logic behind its own test
gate before the wiring task. Purely additive — the tree stays green.

**Files:**
- Modify: `science/src/science_tool/graph/attention.py` (add helper near `_days_since_last_review`, ~`:660`)
- Test: `science/tests/test_attention_sampling.py` (add helper-contract tests)

**Interfaces:**
- Produces: `_last_reviewed_date(knowledge, entity_id: str, entity_uri: URIRef) -> date | None` — returns the parsed `sci:lastReviewed` date; `None` when the triple is absent; raises `ValueError` (naming `entity_id` and the raw value) when present but not canonical `YYYY-MM-DD`.

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_attention_sampling.py`. The imports `Dataset, Literal,
URIRef` (from rdflib), `XSD`, and `PROJECT_NS`, `SCI_NS` already exist in this
file; add `from science_tool.graph.attention import _last_reviewed_date` and
`import pytest` if not already imported.

```python
def _knowledge_with_last_reviewed(raw: str | None):
    """A one-entity knowledge graph; `raw` is the literal lexical value, or None to omit the triple."""
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    uri = URIRef("https://example.org/hypothesis/h1")
    knowledge.add((uri, SCI_NS.freshnessState, Literal("fresh")))
    if raw is not None:
        # normalize=False is load-bearing: with the default, RDFLib rewrites a
        # parseable non-canonical value (e.g. "2026-W18-5") to its canonical
        # lexical form "2026-05-01", which would mask exactly the case under test.
        knowledge.add((uri, SCI_NS.lastReviewed, Literal(raw, datatype=XSD.date, normalize=False)))
    return knowledge, uri


def test_last_reviewed_date_parses_canonical_form() -> None:
    knowledge, uri = _knowledge_with_last_reviewed("2026-04-01")
    assert _last_reviewed_date(knowledge, "hypothesis:h1", uri) == date(2026, 4, 1)


def test_last_reviewed_date_absent_triple_is_none() -> None:
    knowledge, uri = _knowledge_with_last_reviewed(None)
    assert _last_reviewed_date(knowledge, "hypothesis:h1", uri) is None


@pytest.mark.parametrize("raw", ["2026-05-01garbage", "20260501", "2026-W18-5", "not-a-date"])
def test_last_reviewed_date_rejects_non_canonical(raw: str) -> None:
    knowledge, uri = _knowledge_with_last_reviewed(raw)
    with pytest.raises(ValueError) as excinfo:
        _last_reviewed_date(knowledge, "hypothesis:h1", uri)
    message = str(excinfo.value)
    assert "hypothesis:h1" in message
    assert raw in message
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_attention_sampling.py -k last_reviewed_date -v`
Expected: FAIL — `ImportError: cannot import name '_last_reviewed_date'`.

- [ ] **Step 3: Add the helper**

Insert into `science/src/science_tool/graph/attention.py`, immediately above the
existing `def _days_since_last_review(...)`:

```python
def _last_reviewed_date(knowledge, entity_id: str, entity_uri: URIRef) -> date | None:
    """The entity's sci:lastReviewed date, or None if it was never reviewed.

    Absence (no triple) is None. A PRESENT value must be the canonical xsd:date
    producer form the freshness pass writes (YYYY-MM-DD); anything else is a
    corrupt graph, not an absence, and raises. The round-trip check is
    load-bearing: date.fromisoformat also accepts compact (20260501) and ISO
    week (2026-W18-5) forms, neither of which is the toolkit's canonical form.
    """
    literal = next(knowledge.objects(entity_uri, SCI_NS.lastReviewed), None)
    if literal is None:
        return None
    text = str(literal)
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        parsed = None
    if parsed is None or parsed.isoformat() != text:
        raise ValueError(
            f"{entity_id}: sci:lastReviewed value {text!r} is not a valid ISO date (YYYY-MM-DD)"
        )
    return parsed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_attention_sampling.py -k last_reviewed_date -v`
Expected: PASS (6 cases: canonical, absent, and 4 parametrized rejects).

- [ ] **Step 5: Full green gate**

Run: `cd science && uv run --frozen pytest && uv run ruff check && uv run pyright`
Expected: PASS. (The new helper is unused by production code until Task 2; that is fine — it has test callers, so nothing flags it.)

- [ ] **Step 6: Commit**

```bash
cd ~/d/science/.claude/worktrees/instrument-result
git branch --show-current   # must print: attention-recency-correctness
git add science/src/science_tool/graph/attention.py science/tests/test_attention_sampling.py
git commit -m "feat(attention): add strict _last_reviewed_date helper (canonical YYYY-MM-DD)"
```

---

### Task 2: Delete the recency term; surface honest `last_reviewed` everywhere

The atomic semantic correction. It changes the producer (`attention.py`) and
**all** its consumers (`graph/cli.py`, `wander/context.py`, `wander/skeleton.py`)
together, because they share the `components["days_since_last_review"]` shape —
splitting them would leave the tree red. The `today` parameters stay in place
here (still accepted, now unused); Task 3 removes them.

**Files:**
- Modify: `science/src/science_tool/graph/attention.py` — weight formula (`:161-167`), candidate loop (`:153,183`), `AttentionCandidate` (`:73-84`), `format_attention_candidate` (`:365-386`), delete `NEVER_REVIEWED_DAYS` (`:29`), `_days_since_last_review` + `_parse_date_literal` (`:660-679`).
- Modify: `science/src/science_tool/graph/cli.py` — `attention-sample` table column + `never` transform (`:663-679`); `attention-rank` table column + `never` transform + `try/except ValueError` (`:705-726`).
- Modify: `science/src/science_tool/wander/context.py` — `ContextBundle.last_reviewed` (`:16-31`) + `assemble_bundle` (`:50-64`).
- Modify: `science/src/science_tool/wander/skeleton.py` — skeleton table (`:36-40`), `_bundle_to_dict` JSON (`:116`).
- Test: `science/tests/test_attention_sampling.py`, `science/tests/test_attention_preconditions.py`, `science/tests/test_wander_skeleton.py`, `science/tests/test_wander_stub_smell.py`, `science/tests/test_wander_context.py`.

**Interfaces:**
- Consumes: `_last_reviewed_date(knowledge, entity_id, entity_uri) -> date | None` (Task 1).
- Produces:
  - `AttentionCandidate.last_reviewed: date | None` (new dataclass field).
  - `format_attention_candidate(...)` row dict: key `"days_since_last_review"` **removed**, key `"last_reviewed"` added as `str | None` (ISO date or `None`).
  - `ContextBundle.last_reviewed: date | None` (new dataclass field).
  - CLI/JSON schema: `attention-sample`, `attention-rank`, and Wander JSON now carry `last_reviewed`; both attention tables render a `Last reviewed` column.

- [ ] **Step 1: Write the failing behavioral tests**

Add to `science/tests/test_attention_sampling.py`. These assert the new
contract; they will fail until the implementation lands.

```python
def _uniform_recency_fixture() -> Dataset:
    """Three hypotheses identical in every scoring input, same freshness_state,
    differing only in last_reviewed (recent / old / never)."""
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    for slug, reviewed in [("recent", "2026-04-30"), ("old", "2024-01-01"), ("never", None)]:
        uri = _u(f"hypothesis/{slug}")  # canonical PROJECT_NS URI — non-canonical URIs are skipped by candidate discovery
        knowledge.add((uri, RDF.type, SCI_NS.Hypothesis))
        knowledge.add((uri, SKOS.prefLabel, Literal(slug)))
        knowledge.add((uri, SCI_NS.freshnessState, Literal("fresh")))
        if reviewed is not None:
            knowledge.add((uri, SCI_NS.lastReviewed, Literal(reviewed, datatype=XSD.date)))
    return dataset


def test_recency_no_longer_moves_the_weight() -> None:
    candidates = compute_attention_candidates(_uniform_recency_fixture(), today=date(2026, 5, 1)).rows
    weights = {c.entity_id: c.weight for c in candidates}
    assert weights["hypothesis:recent"] == weights["hypothesis:old"] == weights["hypothesis:never"]


def test_never_reviewed_does_not_dominate_on_recency() -> None:
    # Perverse-repair guard: a never-reviewed entity must NOT outrank an
    # otherwise-identical recently-reviewed one purely on recency.
    candidates = compute_attention_candidates(_uniform_recency_fixture(), today=date(2026, 5, 1)).rows
    weights = {c.entity_id: c.weight for c in candidates}
    assert weights["hypothesis:never"] == weights["hypothesis:recent"]


def test_last_reviewed_surfaced_honestly() -> None:
    candidates = compute_attention_candidates(_uniform_recency_fixture(), today=date(2026, 5, 1)).rows
    by_id = {c.entity_id: c for c in candidates}
    assert by_id["hypothesis:recent"].last_reviewed == date(2026, 4, 30)
    assert by_id["hypothesis:never"].last_reviewed is None
    for c in candidates:
        assert "days_since_last_review" not in c.components
    recent_row = format_attention_candidate(by_id["hypothesis:recent"])
    never_row = format_attention_candidate(by_id["hypothesis:never"])
    assert recent_row["last_reviewed"] == "2026-04-30"
    assert never_row["last_reviewed"] is None
    assert "days_since_last_review" not in recent_row


def test_freshness_still_discriminates_recency() -> None:
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    for slug, state in [("stale", "needs-review"), ("fresh", "fresh")]:
        uri = _u(f"hypothesis/{slug}")
        knowledge.add((uri, RDF.type, SCI_NS.Hypothesis))
        knowledge.add((uri, SKOS.prefLabel, Literal(slug)))
        knowledge.add((uri, SCI_NS.freshnessState, Literal(state)))
    candidates = compute_attention_candidates(dataset, today=date(2026, 5, 1)).rows
    weights = {c.entity_id: c.weight for c in candidates}
    assert weights["hypothesis:stale"] > weights["hypothesis:fresh"]
```

Ensure `format_attention_candidate`, `RDF`, and `SKOS` are imported in the test
module (the fixtures at the top of the file already use `RDF`/`SKOS`; add
`format_attention_candidate` to the existing `from science_tool.graph.attention
import (...)` block).

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_attention_sampling.py -k "recency or last_reviewed_surfaced or freshness_still" -v`
Expected: FAIL — `AttributeError: 'AttentionCandidate' object has no attribute 'last_reviewed'` (and weight-equality failures, since the ~13× term still varies with the old fixture).

- [ ] **Step 3: Change the weight, the candidate, and the helper wiring**

In `science/src/science_tool/graph/attention.py`:

Delete the constant (`:29`): remove the line `NEVER_REVIEWED_DAYS = 365.0`.

Add the field to `AttentionCandidate` (dataclass, `:73-84`) — insert after
`freshness_state`:

```python
    freshness_state: str
    last_reviewed: date | None
    weight: float
```

In the candidate loop, replace the recency read (`:153`):

```python
        last_reviewed = _last_reviewed_date(knowledge, entity_id, entity_uri)
```

Replace the weight expression (`:161-167`) — drop the days factor:

```python
        weight = (
            (1.0 + incoming_bears_on)
            * freshness_multiplier
            * evidence_balance_factor
            * (1.0 + OPEN_QUESTION_DEBT_WEIGHT * open_question_debt)
        ) + epsilon
```

In the `AttentionCandidate(...)` construction (`:173-193`), add the field and
remove the components entry — insert `last_reviewed=last_reviewed,` after
`freshness_state=freshness_state,`, and delete the line
`"days_since_last_review": float(days_since_last_review),` from the `components`
dict.

Delete the now-unused helpers `_days_since_last_review` (`:660-667`) and
`_parse_date_literal` (`:670-679`).

Also delete the line `current_date = today or date.today()` (`:110`) — with the
recency read gone it has no reader, and ruff (F841) fails a green gate on an
unused local. **Keep** the `today` parameter in the signature for now (an unused
*parameter* is not flagged; Task 3 removes the parameter and its plumbing). The
`date` import stays — it is still used by the new field and helper.

- [ ] **Step 4: Update `format_attention_candidate`**

In `science/src/science_tool/graph/attention.py`, in `format_attention_candidate`
(`:365-386`), replace the line
`"days_since_last_review": f"{components['days_since_last_review']:.0f}",` with:

```python
        "last_reviewed": candidate.last_reviewed.isoformat() if candidate.last_reviewed else None,
```

- [ ] **Step 5: Fix the two existing attention assertions this breaks**

In `science/tests/test_attention_sampling.py`, the components-equality assertion
(`:237-247`) pins the old shape. Replace its body so it drops the removed key and
asserts the new field (h1 has `lastReviewed 2026-04-01`, so `last_reviewed` is
that date):

```python
    assert contested.weight > fresh.weight
    assert contested.last_reviewed == date(2026, 4, 1)
    assert contested.components == {
        "incoming_bears_on": 2.0,
        "freshness_multiplier": 3.0,
        "support_count": 1.0,
        "dispute_count": 1.0,
        "evidence_source_count": 2.0,
        "evidence_balance_factor": 2.0,
        "open_question_debt": 0.0,
        "epsilon": 0.05,
    }
```

- [ ] **Step 6: Run attention tests green**

Run: `cd science && uv run --frozen pytest tests/test_attention_sampling.py tests/test_attention_preconditions.py -v`
Expected: PASS. (`import` of the deleted `datetime` may now be unused — Step 11's ruff pass will flag it; remove it from the top-of-file import if so.)

- [ ] **Step 7: Update the CLI — table columns, `never` transform, rank error wrap**

In `science/src/science_tool/graph/cli.py`:

`attention-sample` (`:663-679`): the table branch already builds `table_rows`;
extend its dict comprehension to stringify `last_reviewed`, and swap the column:

```python
    if output_format == "table":
        table_rows = [
            {
                **row,
                "reasons": ", ".join(reason["code"] for reason in row.get("reasons", [])),
                "last_reviewed": row["last_reviewed"] or "never",
            }
            for row in rows
        ]
```

and in that command's `columns=[...]`, replace
`("days_since_last_review", "Days"),` with `("last_reviewed", "Last reviewed"),`.

`attention-rank` (`:705-726`): wrap the query in `try/except ValueError` (it is
currently unwrapped), add a table-only `never` transform, and add the column:

```python
    try:
        rows = unwrap_instrument(
            query_attention_ranked(
                graph_path=graph_path,
                limit=limit,
                today=rank_date,
                kinds=set(kinds) if kinds else None,
                epsilon=epsilon,
            ),
            what="graph attention-rank",
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    table_rows = rows
    if output_format == "table":
        table_rows = [{**row, "last_reviewed": row["last_reviewed"] or "never"} for row in rows]
    emit_query_rows(
        output_format=output_format,
        title="Attention ranking",
        columns=[
            ("id", "ID"),
            ("kind", "Kind"),
            ("freshness_state", "Freshness"),
            ("attention_weight", "Weight"),
            ("last_reviewed", "Last reviewed"),
            ("open_question_debt", "Q-Debt"),
        ],
        rows=table_rows,
    )
```

- [ ] **Step 8: Propagate into Wander context + skeleton**

In `science/src/science_tool/wander/context.py`, add the field to `ContextBundle`
(`:16-31`, after `freshness_state`):

```python
    freshness_state: str
    last_reviewed: date | None
    weight: float
```

and set it in `assemble_bundle` (`:50-64`), after `freshness_state=...`:

```python
        freshness_state=candidate.freshness_state,
        last_reviewed=candidate.last_reviewed,
        weight=candidate.weight,
```

In `science/src/science_tool/wander/skeleton.py`, the skeleton table (`:36-40`):

```python
    lines.append("| ID | Kind | Weight | Last reviewed |")
    lines.append("| --- | --- | --- | --- |")
    for bundle, _ in bundles_with_signals:
        last_reviewed = bundle.last_reviewed.isoformat() if bundle.last_reviewed else "never"
        lines.append(f"| {bundle.entity_id} | {bundle.kind} | {bundle.weight:.4f} | {last_reviewed} |")
```

and `_bundle_to_dict` (`:116`), add a key (place it beside `freshness_state`):

```python
        "freshness_state": bundle.freshness_state,
        "last_reviewed": bundle.last_reviewed.isoformat() if bundle.last_reviewed else None,
```

- [ ] **Step 9: Fix Wander tests that construct `ContextBundle` directly**

In `science/tests/test_wander_skeleton.py`, the `_bundle` helper (`:15-32`) pins
the old components shape. Update its `base` dict: drop `days_since_last_review`
from `components` and add the new field:

```python
        freshness_state="fresh",
        last_reviewed=date(2026, 4, 1),
        weight=1.25,
        components={"incoming_bears_on": 0.0},
```

Then add skeleton assertions in the same file (a new test, or extend an existing
render test):

```python
def test_skeleton_renders_last_reviewed() -> None:
    table_bundle = _bundle("hypothesis:h1")
    never_bundle = _bundle("hypothesis:h2", last_reviewed=None)
    today = date(2026, 5, 9)
    bundles_with_signals = [
        (b, compute_stub_signals(b, today=today)) for b in (table_bundle, never_bundle)
    ]
    text = render_markdown_skeleton(
        walk_id="2026-05-09-1430", walk_date=today, seed=1, n=2,
        bundles_with_signals=bundles_with_signals,
    )
    assert "| Last reviewed |" in text
    assert "2026-04-01" in text
    assert "never" in text

    payload = json.loads(render_json(
        walk_id="2026-05-09-1430", walk_date=today, seed=1, n=2,
        bundles_with_signals=bundles_with_signals,
    ))
    reviewed = {b["entity_id"]: b["last_reviewed"] for b in payload["bundles"]}
    assert reviewed["hypothesis:h1"] == "2026-04-01"
    assert reviewed["hypothesis:h2"] is None
```

In `science/tests/test_wander_stub_smell.py`, every direct `ContextBundle(...)`
construction must gain `last_reviewed=` (a date or `None`) — the stub-smell logic
does not read it, so any value works; use `last_reviewed=None` for minimal churn.

In `science/tests/test_wander_context.py`, add one line to the existing
`test_bundle_includes_candidate_components_neighbors_filesystem` asserting that
`assemble_bundle` propagates the field. Its `_build_dataset` fixture leaves `h1`
unstamped (no `sci:lastReviewed`), so the propagated value is `None` — assert it
**without** importing anything (no `date` needed here; Task 3 removes this file's
`date` import):

```python
    assert bundle.last_reviewed is None
```

- [ ] **Step 10: Add the positive CLI-table rendering test and the corrupt-date surfacing test**

Add both to `science/tests/test_attention_preconditions.py`. This file already
imports `from science_tool.cli import main`, `from click.testing import
CliRunner`, `RDF`/`SKOS`, and defines `_write(tmp_path, dataset) -> Path` (writes
via `save_canonical_graph_dataset`) — reuse all of them; do **not** re-serialize
by hand. The CLI is invoked as `main` with a `"graph"` prefix, e.g.
`CliRunner().invoke(main, ["graph", "attention-rank", "--path", str(graph_path)])`
(see `:178`, `:187`).

```python
def _reviewed_and_never_graph(tmp_path) -> Path:
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    for slug, reviewed in [("stamped", "2026-04-30"), ("never", None)]:
        uri = _u(f"hypothesis/{slug}")  # canonical PROJECT_NS URI (this file defines `_u` at :43)
        knowledge.add((uri, RDF.type, SCI_NS.Hypothesis))
        knowledge.add((uri, SKOS.prefLabel, Literal(slug)))
        knowledge.add((uri, SCI_NS.freshnessState, Literal("fresh")))
        if reviewed is not None:
            knowledge.add((uri, SCI_NS.lastReviewed, Literal(reviewed, datatype=XSD.date)))
    return _write(tmp_path, dataset)


@pytest.mark.parametrize("command", ["attention-sample", "attention-rank"])
def test_attention_tables_render_last_reviewed(tmp_path, command: str) -> None:
    graph_path = _reviewed_and_never_graph(tmp_path)
    args = ["graph", command, "--path", str(graph_path)]
    if command == "attention-sample":
        args += ["--limit", "5", "--seed", "1"]
    # COLUMNS=220 keeps the Rich table wide enough that the "Last reviewed" header
    # and the ISO date are not ellipsis-truncated (Click's default is 80). Matches
    # the existing env={"COLUMNS": ...} idiom already used in this test suite.
    result = CliRunner().invoke(main, args, env={"COLUMNS": "220"})
    assert result.exit_code == 0, result.output
    assert "Last reviewed" in result.output   # column header
    assert "2026-04-30" in result.output       # stamped entity
    assert "never" in result.output            # null rendered as 'never', not '365'
    assert "365" not in result.output


@pytest.mark.parametrize("command", ["attention-sample", "attention-rank"])
def test_corrupt_last_reviewed_is_clean_cli_error(tmp_path, command: str) -> None:
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    uri = _u("hypothesis/h1")
    knowledge.add((uri, RDF.type, SCI_NS.Hypothesis))
    knowledge.add((uri, SKOS.prefLabel, Literal("h1")))
    knowledge.add((uri, SCI_NS.freshnessState, Literal("fresh")))
    knowledge.add((uri, SCI_NS.lastReviewed, Literal("2026-05-01garbage", datatype=XSD.date, normalize=False)))
    graph_path = _write(tmp_path, dataset)

    args = ["graph", command, "--path", str(graph_path)]
    if command == "attention-sample":
        args += ["--limit", "5"]
    result = CliRunner().invoke(main, args, env={"COLUMNS": "220"})
    assert result.exit_code != 0
    assert "hypothesis:h1" in result.output
    assert "2026-05-01garbage" in result.output
```

Add `XSD` to the file's rdflib imports if it is not already present
(`from rdflib.namespace import RDF, SKOS, XSD` — the module currently imports
`RDF, SKOS`).

- [ ] **Step 11: Full green gate**

Run: `cd science && uv run --frozen pytest && uv run ruff check && uv run pyright`
Expected: PASS. Deleting `_parse_date_literal` leaves `datetime` unused in
`attention.py` — change its import line `from datetime import date, datetime` to
`from datetime import date` (keep `date`; it is used by the new field and helper).

- [ ] **Step 12: Commit**

```bash
cd ~/d/science/.claude/worktrees/instrument-result
git branch --show-current   # must print: attention-recency-correctness
git add science/src/science_tool/graph/attention.py science/src/science_tool/graph/cli.py \
        science/src/science_tool/wander/context.py science/src/science_tool/wander/skeleton.py \
        science/tests/test_attention_sampling.py science/tests/test_attention_preconditions.py \
        science/tests/test_wander_skeleton.py science/tests/test_wander_stub_smell.py \
        science/tests/test_wander_context.py
git commit -m "feat(attention): delete recency term; surface honest last_reviewed on every surface"
```

---

### Task 3: Remove the now-dead `today` parameter

With the recency term gone, `current_date = today or date.today()`
(`attention.py:110`) has no reader. Remove `today` everywhere it existed **only**
to feed attention scoring. Keep Wander's `--today` (it dates the walk and drives
stub-smell), dropping only its `today=` argument into attention.

**Files:**
- Modify: `science/src/science_tool/graph/attention.py` — `compute_attention_candidates` (`:87-118`), `query_attention_sample` (`:284-313`), `query_attention_ranked` (`:316-343`).
- Modify: `science/src/science_tool/graph/cli.py` — `attention-sample`/`attention-rank` `--today` options + `sample_date`/`rank_date` plumbing.
- Modify: `science/src/science_tool/wander/sampling.py` — `sample_for_walk` (`:19-45`).
- Modify: `science/src/science_tool/wander/cli.py` — drop `today=` into attention; update `--today` help.
- Test: `science/tests/test_attention_sampling.py`, `science/tests/test_attention_preconditions.py`, `science/tests/test_wander_sampling.py`, `science/tests/test_wander_context.py`, `science/tests/test_wander_cli.py`.

**Interfaces:**
- Produces: `compute_attention_candidates(dataset, *, kinds=None, epsilon=DEFAULT_EPSILON)`, `query_attention_sample(graph_path, *, limit, seed=None, kinds=None, epsilon=DEFAULT_EPSILON, reason_aware=False)`, `query_attention_ranked(graph_path, *, limit=None, kinds=None, epsilon=DEFAULT_EPSILON)`, `sample_for_walk(*, graph_path, n, seed, kinds=None, epsilon=0.05)` — all with `today` **removed**.

- [ ] **Step 1: Write the failing test**

Add to `science/tests/test_attention_preconditions.py`:

```python
def test_compute_attention_candidates_rejects_today_kwarg() -> None:
    # `today` was removed with the recency term; passing it is an error, not a silently-ignored control.
    with pytest.raises(TypeError):
        compute_attention_candidates(_dataset_with_freshness(), today=date(2026, 5, 1))


def test_graph_attention_commands_have_no_today_option() -> None:
    from click.testing import CliRunner

    from science_tool.cli import main

    for command in ("attention-sample", "attention-rank"):
        result = CliRunner().invoke(main, ["graph", command, "--today", "2026-05-01"])
        assert result.exit_code != 0
        assert "no such option" in result.output.lower()
```

(`_dataset_with_freshness` already exists in this file, as do `main` and
`CliRunner` imports at module top.)

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_attention_preconditions.py -k "today" -v`
Expected: FAIL — `compute_attention_candidates` still accepts `today` (no `TypeError`), and `--today` is still a valid option.

- [ ] **Step 3: Remove `today` from the attention functions**

In `science/src/science_tool/graph/attention.py`:

`compute_attention_candidates` — delete the `today: date | None = None,`
parameter. (Its `current_date` local was already removed in Task 2, so only the
parameter remains to drop.)

`query_attention_sample` and `query_attention_ranked` — delete their
`today: date | None = None,` parameters and the `today=today,` argument in each
`compute_attention_candidates(...)` call (`:302`, `:333`).

- [ ] **Step 4: Remove `today` from the CLI**

In `science/src/science_tool/graph/cli.py`, for **both** `graph_attention_sample`
and `graph_attention_rank`: delete the `@click.option("--today", ...)` decorator,
the `today: datetime | None,` function parameter, the `sample_date`/`rank_date`
local, and the `today=...,` argument passed to the query function. Then delete the
import line `from datetime import date, datetime` entirely — after this change
neither `date` nor `datetime` is used anywhere else in `cli.py` (their only uses
were the `today`/`sample_date`/`rank_date` plumbing just removed).

- [ ] **Step 5: Remove `today` from Wander sampling; keep it for the walk**

In `science/src/science_tool/wander/sampling.py`, delete `today: date | None,`
from `sample_for_walk` and the `today=today,` argument in its
`compute_attention_candidates(...)` call (`:42`). Then delete the now-unused
import `from datetime import date` (`:3`) — `date` had no other use in this file.

In `science/src/science_tool/wander/cli.py`: drop only the `today=walk_date`
argument from the `compute_attention_candidates(...)` call (`:84`) — keep
`walk_date`, `walk_id`, and `compute_stub_signals(b, today=walk_date)`. Update the
`--today` option help (`:48-51`) from "Override the date used for sampling and
stub-smell." to `"Override the date used for the walk and stub-smell."`.

- [ ] **Step 6: Strip `today=` from existing test call sites**

Sweep each test file and drop the `today=...` argument from every
`compute_attention_candidates(...)`, `query_attention_sample(...)`,
`query_attention_ranked(...)`, and `sample_for_walk(...)` call — **including the
tests Task 2 added** (`test_recency_no_longer_moves_the_weight`,
`test_never_reviewed_does_not_dominate_on_recency`,
`test_last_reviewed_surfaced_honestly`, `test_freshness_still_discriminates_recency`).
Find them with:

```bash
cd science && rg -n "today=" tests/test_attention_sampling.py tests/test_attention_preconditions.py \
    tests/test_wander_sampling.py tests/test_wander_context.py
```

Files affected: `test_attention_sampling.py`, `test_attention_preconditions.py`,
`test_wander_sampling.py`, `test_wander_context.py`.

Two `today=` call sites must **NOT** be changed:
- any `compute_stub_signals(..., today=...)` — that `today` is stub-smell's own and stays;
- the new `test_compute_attention_candidates_rejects_today_kwarg` (Step 1) —
  it passes `today=` **on purpose** to assert the `TypeError`.

After stripping, two of these files no longer use `date` at all — delete
`from datetime import date` (`:3`) from **`test_wander_sampling.py`** and
**`test_wander_context.py`**. Keep the `date` import in `test_attention_sampling.py`
(used by many non-`today` assertions) and in `test_attention_preconditions.py`
(the `rejects_today_kwarg` test intentionally passes `today=date(2026, 5, 1)`).

- [ ] **Step 7: Assert Wander's `--today` still works**

Add to `science/tests/test_wander_cli.py`. This file imports
`from science_tool.cli import main`, invokes `CliRunner().invoke(main, ["wander",
...])`, and defines `_build_fixture_graph(tmp_path) -> Path` — reuse all three:

```python
def test_wander_today_option_still_accepted(tmp_path: Path) -> None:
    # --today survives the attention `today` removal because it dates the walk and stub-smell.
    graph_path = _build_fixture_graph(tmp_path)
    result = CliRunner().invoke(
        main,
        [
            "wander",
            "--n", "1",
            "--seed", "1",
            "--graph-path", str(graph_path),
            "--format", "json",
            "--today", "2026-05-01",
        ],
    )
    assert result.exit_code == 0, result.output
```

The graph-path option is `--graph-path` (not `--path`), and `--format json`
prints to stdout — without it, `markdown` is the default and would write a
skeleton file into `doc/meta/walks/`. This mirrors `test_wander_writes_markdown
_skeleton` (`:40-57`), minus `--out`.

- [ ] **Step 8: Full green gate**

Run: `cd science && uv run --frozen pytest && uv run ruff check && uv run pyright`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
cd ~/d/science/.claude/worktrees/instrument-result
git branch --show-current   # must print: attention-recency-correctness
git add science/src/science_tool/graph/attention.py science/src/science_tool/graph/cli.py \
        science/src/science_tool/wander/sampling.py science/src/science_tool/wander/cli.py \
        science/tests/test_attention_sampling.py science/tests/test_attention_preconditions.py \
        science/tests/test_wander_sampling.py science/tests/test_wander_context.py \
        science/tests/test_wander_cli.py
git commit -m "refactor(attention): remove dead today parameter across attention + wander"
```

---

### Task 4: Docs — record item 3 as implemented (pre-merge)

Stamp the three documents so the attention-ranking follow-on pair
(fb-2026-07-10-023 + fb-2026-07-11-005) is visibly addressed, not silently
dropped. **This is a feature-branch commit, so the wording is `IMPLEMENTED …
pending merge` — never `SHIPPED`, `CLOSED`, or `RESOLVED`.** Those terminal
words are reserved for the post-merge commit (made by whoever runs
finishing-a-development-branch), exactly as the earlier convergence
reconciliations did it.

**Files:**
- Modify: `docs/plans/2026-07-15-attention-recency-correctness-design.md` (status line).
- Modify: `docs/plans/2026-07-11-instrument-result-convergence-design.md` (top-of-doc banner).
- Modify: `docs/plans/2026-07-11-instrument-result-convergence-plan.md` (top-of-doc banner).

- [ ] **Step 1: Set the feature-design status**

In `docs/plans/2026-07-15-attention-recency-correctness-design.md`, change the
status line to exactly:

```
**Status:** IMPLEMENTED on branch `attention-recency-correctness`; pending merge.
```

Do **not** write `SHIPPED`/`CLOSED` here — that flip happens in the post-merge commit.

- [ ] **Step 2: Add an authoritative top-of-doc banner to the convergence design**

In `docs/plans/2026-07-11-instrument-result-convergence-design.md`, insert
**immediately after the H1 title line** (before any other prose) a banner that
supersedes every later open/live statement about this pair — do not hand-edit the
individual follow-on bullet, which is why a top banner is used:

```markdown
> **UPDATE 2026-07-15 — item 3 IMPLEMENTED (pending merge).** The attention-ranking
> follow-on pair (fb-2026-07-10-023 + fb-2026-07-11-005) is implemented on branch
> `attention-recency-correctness` — see `docs/plans/2026-07-15-attention-recency-correctness-design.md`.
> The redundant `days_since_last_review` term was deleted; fb-2026-07-11-005 was already
> handled by the `_is_closed` terminal drop. **This banner supersedes every statement below
> that describes the attention-ranking pair as open or still-live.**
```

- [ ] **Step 3: Add the same banner to the convergence plan**

First locate the open references so the banner's "supersedes below" claim is
accurate:

```bash
cd ~/d/science/.claude/worktrees/instrument-result
rg -n "2026-07-10-023|2026-07-11-005|[Aa]ttention-ranking" docs/plans/2026-07-11-instrument-result-convergence-plan.md
```

Insert the same `> **UPDATE 2026-07-15 …` banner immediately after that document's
H1 title line.

- [ ] **Step 4: Verify the docs are internally consistent**

```bash
cd ~/d/science/.claude/worktrees/instrument-result
# Banners exist in both convergence docs:
rg -n "UPDATE 2026-07-15 — item 3 IMPLEMENTED" docs/plans/2026-07-11-instrument-result-convergence-design.md docs/plans/2026-07-11-instrument-result-convergence-plan.md
# The feature design's Status line must NOT carry premature terminal wording:
rg -n "^\*\*Status:\*\*.*(SHIPPED|CLOSED|RESOLVED)" docs/plans/2026-07-15-attention-recency-correctness-design.md
# Whitespace/conflict-marker check on the working-tree doc edits (do not stage yet):
git diff --check
```
Expected: both banners found; the Status-line `rg` prints **nothing** (exit 1 is
fine — the status reads `IMPLEMENTED … pending merge`); `git diff --check` prints nothing.

- [ ] **Step 5: Full green gate (docs-only, but keep the invariant)**

Run: `cd science && uv run --frozen pytest && uv run ruff check && uv run pyright`
Expected: PASS (unchanged from Task 3 — this task touches only docs, so confirm nothing regressed).

- [ ] **Step 6: Commit**

```bash
cd ~/d/science/.claude/worktrees/instrument-result
git branch --show-current   # must print: attention-recency-correctness
git add docs/plans/2026-07-15-attention-recency-correctness-design.md \
        docs/plans/2026-07-11-instrument-result-convergence-design.md \
        docs/plans/2026-07-11-instrument-result-convergence-plan.md
git commit -m "docs(attention): record item 3 implemented pending merge (fb-2026-07-10-023 + fb-2026-07-11-005)"
```

**Post-merge (out of this plan's task scope):** when the branch merges to local
main, a follow-up commit flips this design's status to `SHIPPED` and the two
convergence banners to `RESOLVED/CLOSED`. The finishing-a-development-branch skill
owns that step.

---

## Notes for the executor

- **Branch discipline (Dropbox volatility):** run `git branch --show-current` before every commit; it must read `attention-recency-correctness`. Never `git stash`. Nothing is pushed unless the user asks.
- **Package dir:** every `uv run` is from `science/`. Never from the repo root.
- **Atomicity of Task 2:** do not try to land `attention.py` without `cli.py` and the Wander files — they share the `components["days_since_last_review"]` shape and the tree goes red if split. The task is large because the change is genuinely atomic.
- **CLI-invocation idioms:** Tasks 2 & 3 add CLI tests. Both target files invoke the CLI as `from science_tool.cli import main` → `CliRunner().invoke(main, ["graph", ...])` / `["wander", ...]`, and provide graph builders — `_write(tmp_path, dataset)` in `test_attention_preconditions.py`, `_build_fixture_graph(tmp_path)` in `test_wander_cli.py`. Use those; do not invent parallel scaffolding or hand-serialize graphs.
