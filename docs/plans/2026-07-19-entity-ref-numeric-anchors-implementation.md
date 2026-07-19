# Entity-ref citations as numeric-anchor anchors — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `numeric-anchor` recognize resolvable, provenance-bearing typed entity-ref citations (`interpretation:0011-…`, short `plan:0023`, `dataset:gtex`) as paragraph-local anchors, without masking — so genuinely-grounded numbers stop flagging while topical citations, fabricated refs, ambiguous prefixes, and embedded substrings still flag.

**Architecture:** Three contained changes in `src/science_tool/numeric_provenance.py` (a provenance-kind allowlist driving one guarded `_BODY_REF_RE` branch; short numeric-prefix resolution on `ResolutionIndex`), plus a one-kind correction to `refs._LOCAL_ENTITY_KINDS` and a detector-version bump. Design: [`2026-07-19-entity-ref-numeric-anchors-design.md`](2026-07-19-entity-ref-numeric-anchors-design.md) (rev 5).

**Tech Stack:** Python 3.13, `re`, pydantic-free dataclasses; pytest; run from `science/` with `uv run --frozen`.

## Global Constraints

- Run all commands from `~/d/science/.worktrees/entity-ref-anchors/science` with `uv run --frozen`.
- Gates before each commit: `uv run --frozen pytest <touched test files>`; the final task runs the full `uv run --frozen pytest`, `uv run ruff check`, `uv run pyright`.
- **Three anti-masking gates** hold for every entity-ref anchor: (1) kind in `_ANCHOR_ENTITY_KINDS` (extraction); (2) exact-id or **unique digit-lead prefix** resolution against the real index; (3) two-sided token boundaries. A topical kind, fabricated ref, ambiguous prefix, non-numeric prefix, or embedded substring must leave the number `Unanchored`.
- Do **not** touch `additional_anchor_patterns`/`anchor_patterns`, Part B (`numeric-verification`), or the graph.
- No AI-attribution trailer/footer on commits.
- Additive extraction for existing forms (`task:`, `[@]`, `cite:`, `[[wiki]]`) — their behavior is unchanged; only `dataset` moves under the guard.
- Commit after each task.

---

### Task 1: Correct the entity index — add `plan`

**Files:**
- Modify: `src/science_tool/refs.py:85` (`_LOCAL_ENTITY_KINDS`)
- Test: `tests/test_refs.py`

**Interfaces:**
- Consumes: `check_refs(root, *, include_body=True)` → `list[RefIssue]` with `.ref_type` / `.ref_value`; body typed-refs surface as `ref_type="body-entity-ref"` via exact `ref in entity_index` matching.
- Produces: `plan` is now an indexed local kind, so `plan:*` ids populate `_load_entity_index` and body `plan:` refs are validated.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_refs.py`:

```python
def test_plan_body_entity_ref_validated_after_index_fix() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "entities" / "plans").mkdir(parents=True, exist_ok=True)
        (root / "entities" / "plans" / "0084-reading.md").write_text(
            "---\nid: plan:0084-reading\nkind: plan\ntitle: Reading\n---\n\nbody\n"
        )
        # Bare refs: the refs body scan strips inline code, so backtick-wrapping
        # would hide them (unlike numeric-anchor's local-candidate scan).
        (root / "doc" / "background" / "topics" / "test.md").write_text(
            "# Test\nGood ref plan:0084-reading; bad ref plan:9999-ghost.\n"
        )
        issues = check_refs(root, include_body=True)
        plan_refs = [i for i in issues if i.ref_type == "body-entity-ref" and i.ref_value.startswith("plan:")]
        assert [i.ref_value for i in plan_refs] == ["plan:9999-ghost"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/test_refs.py::test_plan_body_entity_ref_validated_after_index_fix -v`
Expected: FAIL — with `plan` unindexed, `_TYPED_ENTITY_REF_RE` never matches `plan:*`, so `plan_refs == []` and the `== ["plan:9999-ghost"]` assertion fails.

- [ ] **Step 3: Add `plan` to `_LOCAL_ENTITY_KINDS`**

In `src/science_tool/refs.py`, insert `"plan",` into the `_LOCAL_ENTITY_KINDS` frozenset (alphabetical neighborhood, after `"paper",`):

```python
        "paper",
        "plan",
        "pre-registration",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/test_refs.py::test_plan_body_entity_ref_validated_after_index_fix -v`
Expected: PASS

- [ ] **Step 5: Guard against index-driven regressions**

Run: `uv run --frozen pytest tests/test_refs.py -q`
Expected: PASS. If any pre-existing test asserted an exact set of body-entity-ref issues that now includes newly-validated `plan:` refs, that is an intended delta — update that test's expectation and note it in the commit body. Do not weaken the new test.

- [ ] **Step 6: Commit**

```bash
git add src/science_tool/refs.py tests/test_refs.py
git commit -m "fix(refs): index the plan kind in _LOCAL_ENTITY_KINDS

plan is a core entity kind but was missing from the hardcoded local-kind
snapshot, so plan: ids were never indexed and plan: body refs never
validated. Needed for numeric-anchor to resolve plan: citations."
```

---

### Task 2: Short numeric-prefix resolution with ambiguity handling

**Files:**
- Modify: `src/science_tool/numeric_provenance.py` — `ResolutionIndex` (add field), `resolve()` (typed-ref branch), `build_resolution_index()`
- Test: `tests/test_numeric_provenance.py`

**Interfaces:**
- Consumes: `refs._load_entity_index(root)` → canonical `<kind>:<slug>` ids.
- Produces: `ResolutionIndex.entity_prefix_owners: dict[str, int]` (no default) — maps `<kind>:<digit-lead>` to the count of canonical ids `<kind>:<digits>-<rest>` sharing that lead. `resolve()` returns True for a `_TYPED_REF_RE` ref that is an exact id **or** a prefix owned by **exactly one** entity (`owners == 1`). Matches the approved design's owner-count representation and validator.py's `_index_by_prefix` precedent (resolve only when the prefix has a single owner).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_numeric_provenance.py`:

```python
def _interp(tmp_path: Path, slug: str) -> None:
    d = tmp_path / "entities" / "interpretations"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slug}.md").write_text(
        f"---\nid: interpretation:{slug}\nkind: interpretation\n---\n\nbody\n"
    )


def test_resolve_full_id_and_unique_numeric_prefix(tmp_path):
    _project(tmp_path)
    _interp(tmp_path, "0007-altview")
    idx = build_resolution_index(tmp_path)
    assert idx.resolve("interpretation:0007-altview") is True   # exact full id
    assert idx.resolve("interpretation:0007") is True           # unique numeric prefix
    assert idx.resolve("interpretation:9999") is False          # fabricated


def test_resolve_ambiguous_numeric_prefix_fails(tmp_path):
    _project(tmp_path)
    _interp(tmp_path, "0013-alpha")
    _interp(tmp_path, "0013-beta")
    idx = build_resolution_index(tmp_path)
    assert idx.resolve("interpretation:0013-alpha") is True     # exact still resolves
    assert idx.resolve("interpretation:0013") is False          # 2 owners -> ambiguous, fail-closed


def test_resolve_non_numeric_prefix_is_not_expanded(tmp_path):
    _project(tmp_path)
    d = tmp_path / "entities" / "datasets"
    (d / "cptac.md").write_text(
        "---\nid: dataset:cptac-gbm-2021-proteogenomics\nkind: dataset\n---\n\nbody\n"
    )
    idx = build_resolution_index(tmp_path)
    assert idx.resolve("dataset:cptac-gbm-2021-proteogenomics") is True  # exact
    assert idx.resolve("dataset:cptac") is False                # non-numeric lead: never a short form
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --frozen pytest tests/test_numeric_provenance.py -k "unique_numeric_prefix or ambiguous_numeric_prefix or non_numeric_prefix" -v`
Expected: FAIL — `ResolutionIndex` has no `entity_prefix_owners`, and `resolve()` returns False for the prefix forms.

- [ ] **Step 3: Add the field to `ResolutionIndex` (no default)**

In `src/science_tool/numeric_provenance.py`, add a **non-defaulted** field to the frozen dataclass (after `data_root`). No default is deliberate: every construction must compute the map, so an index can never be silently built without prefix ownership (fail early > defensive). The sole constructor is `build_resolution_index` (verified — no other call site), so a required field is safe.

```python
    data_root: Path
    entity_prefix_owners: dict[str, int]
```

- [ ] **Step 4: Extend `resolve()`'s typed-ref branch**

Replace the existing two lines:

```python
        if _TYPED_REF_RE.match(ref):
            return ref in self.entity_ids
```

with:

```python
        if _TYPED_REF_RE.match(ref):
            # Exact canonical id, or a digit-lead short prefix owned by exactly
            # one entity (`interpretation:0013` -> the sole `interpretation:0013-…`).
            # Non-numeric leads never enter the map; ambiguous (multi-owner)
            # prefixes have owners > 1 — neither resolves, so a citation cannot
            # silently anchor to a guessed entity.
            return ref in self.entity_ids or self.entity_prefix_owners.get(ref) == 1
```

- [ ] **Step 5: Populate the owner map in `build_resolution_index`**

Replace the `return ResolutionIndex(...)` block body so `entity_ids` is captured and the owner map computed:

```python
    entity_ids = frozenset(refs._load_entity_index(root))
    entity_prefix_owners: dict[str, int] = {}
    for eid in entity_ids:
        kind, _, ident = eid.partition(":")
        lead = ident.split("-", 1)[0]
        if lead.isdigit() and lead != ident:
            key = f"{kind}:{lead}"
            entity_prefix_owners[key] = entity_prefix_owners.get(key, 0) + 1
    return ResolutionIndex(
        project_root=root,
        task_numbers=frozenset(task_numbers),
        entity_ids=entity_ids,
        bib_keys=frozenset(load_bib_keys(root)),
        doi_corpus=frozenset(d.strip().lower() for d in refs._load_doi_corpus(root)),
        pmid_corpus=frozenset(refs._load_pmid_corpus(root)),
        data_root=resolve_data_root(root),
        entity_prefix_owners=entity_prefix_owners,
    )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run --frozen pytest tests/test_numeric_provenance.py -k "unique_numeric_prefix or ambiguous_numeric_prefix or non_numeric_prefix or resolution_index_resolves" -v`
Expected: PASS (including the pre-existing `test_resolution_index_resolves_real_refs_and_rejects_fakes`).

- [ ] **Step 7: Commit**

```bash
git add src/science_tool/numeric_provenance.py tests/test_numeric_provenance.py
git commit -m "feat(numeric-anchor): resolve unique digit-lead entity-ref prefixes

Short citations like interpretation:0013 resolve to the sole owning
entity; ambiguous (multi-owner) prefixes and non-numeric leads never
resolve, so a citation cannot silently anchor to a guessed entity."
```

---

### Task 3: Provenance-kind allowlist + guarded extraction branch

**Files:**
- Modify: `src/science_tool/numeric_provenance.py` — add `_ANCHOR_ENTITY_KINDS`, rebuild `_BODY_REF_RE` (add guarded branch, remove the dedicated `dataset:` branch), update `local_candidates_for_paragraph` docstring
- Test: `tests/test_numeric_provenance.py`

**Interfaces:**
- Consumes: `ResolutionIndex.resolve` (Task 2) via `local_candidates_for_paragraph`.
- Produces: `_ANCHOR_ENTITY_KINDS: frozenset[str]`; `_BODY_REF_RE` matches allowlisted `<kind>:<id>` (full or short, incl. dotted ids like `paper:Volker2023.source` and `paper:good.-id`) with two-sided boundary guards, an **id-scoped no-`..` lookahead**, and an **atomic** id-body match, and no longer has a standalone `dataset:` alternative. The id body is `[0-9A-Za-z](?:[0-9A-Za-z._-]*[0-9A-Za-z])?` inside an atomic group `(?>…)`: alnum start/terminal (a trailing sentence period stays outside), arbitrary internal `._-`. The malformed-id restriction is the preceding `(?![A-Za-z0-9._-]*\.\.)` lookahead — a `..` anywhere in the id run makes the whole alternative fail (no truncated `paper:bad` survives), mirroring `_VERBATIM_RE`'s no-`..` rule. This grammar is a **deliberate strict subset** of `_VERBATIM_RE` (which additionally permits a *trailing* separator like `paper:foo.`): the required alnum terminal is intentional so a sentence period is never captured — see the design's terminal-subset rationale. Atomicity forbids backtracking to a shorter id, so `interpretation:0007.foo@host` fails entirely instead of truncating to a resolvable `interpretation:0007`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_numeric_provenance.py`:

```python
def _refs(para, idx):
    return {c.reference for c in local_candidates_for_paragraph(para, idx)}

def _resolved_refs(para, idx):
    return {c.reference for c in local_candidates_for_paragraph(para, idx) if c.resolution_status == "resolved"}


def test_provenance_entity_ref_extracts_and_resolves(tmp_path):
    _project(tmp_path)
    _interp(tmp_path, "0007-altview")
    idx = build_resolution_index(tmp_path)
    assert "interpretation:0007-altview" in _resolved_refs(
        "value 7.94 (`interpretation:0007-altview`)", idx)          # full id
    assert "interpretation:0007" in _resolved_refs(
        "value 7.94 per `interpretation:0007`.", idx)                # short prefix
    assert "dataset:xyz" in _resolved_refs("value 7.94 in `dataset:xyz`", idx)


def test_dotted_verbatim_paper_id_extracts(tmp_path):
    _project(tmp_path)
    d = tmp_path / "entities" / "papers"
    d.mkdir(parents=True, exist_ok=True)
    # id: is read from frontmatter, not the filename; keep the file name plain.
    (d / "volker2023-source.md").write_text(
        "---\nid: paper:Volker2023.source\nkind: paper\n---\n\nbody\n"
    )
    idx = build_resolution_index(tmp_path)
    assert "paper:Volker2023.source" in _resolved_refs(
        "value 7.94 (`paper:Volker2023.source`)", idx)


def test_dotted_id_not_truncated_before_continuation(tmp_path):
    # Atomic id-body guard: a dotted id followed by @host / /path / :extra must
    # not backtrack to a resolvable shorter id (paper:Volker2023).
    _project(tmp_path)
    d = tmp_path / "entities" / "papers"
    d.mkdir(parents=True, exist_ok=True)
    (d / "volker2023.md").write_text(
        "---\nid: paper:Volker2023\nkind: paper\n---\n\nbody\n"
    )
    idx = build_resolution_index(tmp_path)
    assert "paper:Volker2023" in _resolved_refs("value 7.94 (`paper:Volker2023`)", idx)  # bare id resolves
    for para in (
        "value 7.94 paper:Volker2023.source@host here",
        "value 7.94 paper:Volker2023.source/path here",
        "value 7.94 paper:Volker2023.source:extra here",
    ):
        assert "paper:Volker2023" not in _resolved_refs(para, idx)


def _paper(tmp_path: Path, entity_id: str, fname: str) -> None:
    d = tmp_path / "entities" / "papers"
    d.mkdir(parents=True, exist_ok=True)
    (d / fname).write_text(f"---\nid: {entity_id}\nkind: paper\n---\n\nbody\n")


def test_double_dot_id_masks_no_shorter_ref(tmp_path):
    # No-`..` rule (mirrors _VERBATIM_RE): a malformed id with consecutive dots
    # must extract NOTHING — not even a shorter, resolvable prefix. `paper:bad`
    # is a REAL entity here, so a truncating grammar would mask the number; the
    # no-`..` lookahead must prevent any candidate at that position.
    _project(tmp_path)
    _paper(tmp_path, "paper:bad", "bad.md")
    idx = build_resolution_index(tmp_path)
    assert idx.resolve("paper:bad") is True                       # the short id really exists…
    assert _refs("value 7.94 (`paper:bad..id`)", idx) == set()    # …yet `..` yields no candidate
    assert _resolved_refs("value 7.94 (`paper:bad..id`)", idx) == set()


def test_internal_dot_hyphen_id_extracts_whole(tmp_path):
    # `paper:good.-id` is a legal _VERBATIM_RE form (only `..` is banned);
    # the grammar must extract it whole, not truncate to `paper:good`.
    _project(tmp_path)
    _paper(tmp_path, "paper:good.-id", "good.md")
    idx = build_resolution_index(tmp_path)
    assert "paper:good.-id" in _resolved_refs("value 7.94 (`paper:good.-id`)", idx)


def test_topical_kinds_are_not_extracted(tmp_path):
    _project(tmp_path)
    idx = build_resolution_index(tmp_path)
    # hypothesis / question are not provenance-bearing: no candidate at all
    assert _refs("value 7.94 supports `hypothesis:0001-molecular-truth`.", idx) == set()
    assert _refs("value 7.94 for `question:0016-tissue`.", idx) == set()


def test_embedded_tokens_do_not_yield_resolvable_ref(tmp_path):
    _project(tmp_path)
    _interp(tmp_path, "0007-altview")
    idx = build_resolution_index(tmp_path)
    for para in (
        "see x_interpretation:0007 here",
        "see x-interpretation:0007 here",
        "path/interpretation:0007-altview.md",
        "interpretation:0007@host",
        "interpretation:0007/panel",
    ):
        assert "interpretation:0007" not in _resolved_refs(para, idx)
        assert "interpretation:0007-altview" not in _resolved_refs(para, idx)


def test_dataset_under_guard_boundaries(tmp_path):
    _project(tmp_path)
    idx = build_resolution_index(tmp_path)
    assert "dataset:xyz" not in _resolved_refs("path/dataset:xyz here", idx)   # embedded path
    assert "dataset:xyz" in _resolved_refs("computed from `dataset:xyz`.", idx)  # trailing period ok
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --frozen pytest tests/test_numeric_provenance.py -k "provenance_entity_ref or dotted_verbatim or dotted_id_not_truncated or double_dot_id or internal_dot_hyphen or topical_kinds or embedded_tokens or dataset_under_guard" -v`
Expected: FAIL — the positive/extraction tests (`provenance_entity_ref`, `dotted_verbatim`, `internal_dot_hyphen`) fail because entity-ref kinds are not yet extracted, and `dataset_under_guard` fails because the old `dataset:` branch masks `path/dataset:xyz` and drops the trailing period. (The negative guards — `dotted_id_not_truncated`, `double_dot_id_masks_no_shorter_ref`, `topical_kinds`, `embedded_tokens` — may pass trivially pre-change since nothing is extracted; they lock the post-change contract.)

- [ ] **Step 3: Add `_ANCHOR_ENTITY_KINDS` and rebuild `_BODY_REF_RE`**

In `src/science_tool/numeric_provenance.py`, replace the `_BODY_REF_RE = re.compile(...)` block with:

```python
# Provenance-bearing entity kinds whose typed citations may anchor a numeric
# claim. Deliberately EXCLUDES topical/framing kinds (hypothesis, question,
# topic, theme, concept, discussion, …): existence-checking proves identity,
# not that the number is sourced there. `task:`/`[@]`/`cite:` remain anchors
# through their own alternatives below.
_ANCHOR_ENTITY_KINDS = frozenset({
    # result / evidence artifacts produced by project work
    "interpretation", "report", "synthesis", "observation", "finding",
    "evidence-line", "validation-report", "experiment", "workflow-run",
    "data-package",
    # external sources
    "dataset", "paper", "book", "source",
    # registered / planned parameters
    "pre-registration", "plan",
})

# Longest-first so hyphenated kinds (validation-report) win over any prefix.
_ANCHOR_KIND_ALT = "|".join(sorted(_ANCHOR_ENTITY_KINDS, key=len, reverse=True))

_BODY_REF_RE = re.compile(
    r"(?:(?<![A-Za-z])task:t\d{2,}"
    r"|\[@[A-Za-z][A-Za-z0-9_:.-]*\]"
    r"|(?<![A-Za-z])cite:[A-Za-z][A-Za-z0-9_:.-]*"
    # Provenance-bearing typed entity-ref (incl. dataset). Three guards:
    #  (1) left lookbehind — rejects an id embedded in a larger token
    #      (x_interpretation, path/…, a:…);
    #  (2) id-scoped no-`..` lookahead — a malformed id whose char-run contains
    #      consecutive dots matches NOTHING here (not even a truncated prefix),
    #      mirroring _VERBATIM_RE's sole no-`..` prohibition;
    #  (3) atomic id body `(?>…)` over the FULL _VERBATIM_RE id charset
    #      (`[0-9A-Za-z](?:[0-9A-Za-z._-]*[0-9A-Za-z])?` — alnum start, alnum
    #      terminal so a trailing sentence period stays outside, arbitrary
    #      internal `._-` incl. `.-`), locked so it cannot backtrack to a
    #      shorter id: `interpretation:0007.foo@host` fails outright rather
    #      than truncating to a resolvable `interpretation:0007`;
    #  followed by a right lookahead rejecting @host / /path / :extra.
    r"|(?<![A-Za-z0-9_.:/@-])(?:" + _ANCHOR_KIND_ALT + r"):"
    r"(?![A-Za-z0-9._-]*\.\.)"
    r"(?>[0-9A-Za-z](?:[0-9A-Za-z._-]*[0-9A-Za-z])?)"
    r"(?![A-Za-z0-9_:/@-])"
    r"|\[\[[^\]\n]+\]\])"
)
```

Python 3.13's `re` supports atomic groups `(?>…)`; do not substitute a
non-atomic group and do not narrow the charset to single-separator runs —
atomicity is the load-bearing anti-truncation guard, and the no-`..`
lookahead (not the charset) is what enforces the malformed-id rule while
still accepting valid `_VERBATIM_RE` forms like `paper:good.-id`.

- [ ] **Step 4: Update the `local_candidates_for_paragraph` docstring**

Change its docstring line listing recognized refs to:

```python
    """Extract resolvable body references scoped to a single paragraph.

    Matches `task:tNNN`, `[@key]`, `cite:key`, and provenance-bearing typed
    entity-refs (`_ANCHOR_ENTITY_KINDS`, e.g. `interpretation:0011-…`,
    `dataset:slug`), full-id or unique digit-lead prefix. A `[[wiki]]` link is
    topical (like `related`) — treated as evidence, not a candidate.
    """
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --frozen pytest tests/test_numeric_provenance.py -k "provenance_entity_ref or dotted_verbatim or dotted_id_not_truncated or double_dot_id or internal_dot_hyphen or topical_kinds or embedded_tokens or dataset_under_guard" -v`
Expected: PASS

- [ ] **Step 6: Confirm existing extraction tests stay green**

Run: `uv run --frozen pytest tests/test_numeric_provenance.py -q`
Expected: PASS — `test_body_ref_requires_word_boundary`, `test_wiki_link_is_topical_not_a_candidate`, `test_generic_anchor_pattern_is_evidence_not_candidate`, `test_local_body_ref_resolves_only_when_it_exists`, and the dataset resolution tests all still pass.

- [ ] **Step 7: Commit**

```bash
git add src/science_tool/numeric_provenance.py tests/test_numeric_provenance.py
git commit -m "feat(numeric-anchor): anchor provenance-bearing entity-ref citations

Add _ANCHOR_ENTITY_KINDS allowlist and a boundary-guarded _BODY_REF_RE
branch that recognizes result/source/plan citations (full id or unique
numeric prefix). Fold dataset under the guard (removing its unguarded
alternative). Topical kinds (hypothesis, question, …) are never
extracted, so they cannot anchor a number."
```

---

### Task 4: End-to-end assessment behavior

**Files:**
- Test: `tests/test_numeric_provenance.py` (uses the existing `_assess` helper at the bottom of the file)

**Interfaces:**
- Consumes: `assess_numeric_claims` via the file's `_assess(tmp_path, body, frontmatter="")` helper, which builds the index from `_project(tmp_path)`. Extend the tests to first create the cited entities.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_numeric_provenance.py`:

```python
def _hypothesis(tmp_path: Path, slug: str) -> None:
    d = tmp_path / "entities" / "hypotheses"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slug}.md").write_text(
        f"---\nid: hypothesis:{slug}\nkind: hypothesis\n---\n\nbody\n"
    )


def test_number_anchored_by_provenance_entity_ref(tmp_path):
    _project(tmp_path)
    _interp(tmp_path, "0007-altview")
    idx = build_resolution_index(tmp_path)
    path = _doc(tmp_path, "The window retained 7399 genes (`interpretation:0007`).",
                frontmatter="kind: interpretation")
    out = assess_numeric_claims(build_document_context(path), idx, _CFG)
    kinds = {type(a).__name__ for a in out if a.claim.value == "7399"}
    assert kinds == {"Anchored"}


def test_number_not_anchored_by_topical_hypothesis_ref(tmp_path):
    # The hypothesis is REAL and resolvable in the index — proving the claim
    # stays Unanchored because `hypothesis` is a topical (non-provenance) KIND,
    # not merely because the ref is fabricated.
    _project(tmp_path)
    _hypothesis(tmp_path, "0001-molecular-truth")
    idx = build_resolution_index(tmp_path)
    assert idx.resolve("hypothesis:0001-molecular-truth") is True  # it exists…
    path = _doc(tmp_path, "The ARI z was 221 (`hypothesis:0001-molecular-truth`).",
                frontmatter="kind: interpretation")
    out = assess_numeric_claims(build_document_context(path), idx, _CFG)
    kinds = {type(a).__name__ for a in out if a.claim.value == "221"}
    assert kinds == {"Unanchored"}   # …yet a topical citation must not clear the claim
```

Note: `_CFG` and `_assess` already exist near the bottom of the test file; if `_CFG` is defined after these tests, place these tests below its definition. Build the index explicitly (as above) so the freshly-written entity files are picked up. `hypothesis` is already in `refs._LOCAL_ENTITY_KINDS`, so the created hypothesis is indexed and `resolve()` returns True for it — the negative therefore isolates the KIND allowlist, exactly as the approved design requires.

- [ ] **Step 2: Run tests to verify they fail (pre-Task-3 baseline) / pass (post-Task-3)**

Run: `uv run --frozen pytest tests/test_numeric_provenance.py -k "anchored_by_provenance or not_anchored_by_topical" -v`
Expected: PASS (Tasks 2–3 already implement the behavior; these tests lock the user-facing contract at the `assess_numeric_claims` level). If either fails, fix the implementation in Task 2/3 — do not weaken the assertion.

- [ ] **Step 3: Commit**

```bash
git add tests/test_numeric_provenance.py
git commit -m "test(numeric-anchor): lock end-to-end entity-ref anchoring contract

A number cited with a resolvable interpretation ref is Anchored; a number
cited only with a topical hypothesis ref stays Unanchored."
```

---

### Task 5: Detector-version bump

**Files:**
- Modify: `src/science_tool/annotation/sources/lint.py:34` (`DETECTOR_VERSIONS`)
- Test: `tests/test_annotation_lint_source_numeric.py:12-13`

**Interfaces:**
- Produces: `DETECTOR_VERSIONS["numeric-anchor"] == "v2026-07-19"`, so re-keyed findings/audit ledgers are not mistaken for output audited under the old behavior.

- [ ] **Step 1: Update the contract test first (it will fail)**

In `tests/test_annotation_lint_source_numeric.py`, change lines 12–13:

```python
    assert DETECTOR_VERSIONS["numeric-anchor"] == "v2026-07-19"
    assert lint_source_name("numeric-anchor") == "lint:numeric-anchor-v2026-07-19"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_annotation_lint_source_numeric.py::test_numeric_anchor_detector_version_bumped -v`
Expected: FAIL — value is still `v2026-07-18b`.

- [ ] **Step 3: Bump the version**

In `src/science_tool/annotation/sources/lint.py`:

```python
    "numeric-anchor":   "v2026-07-19",
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --frozen pytest tests/test_annotation_lint_source_numeric.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/annotation/sources/lint.py tests/test_annotation_lint_source_numeric.py
git commit -m "chore(numeric-anchor): bump detector version to v2026-07-19

Entity-ref anchoring changes numeric-anchor output; re-key so audit
ledgers do not treat re-scanned prose as previously audited."
```

---

### Task 6: Document the behavior

**Files:**
- Modify: `docs/conventions/prose-lints.md` (numeric-anchor "local scope" bullet + Existence-checking note)

- [ ] **Step 1: Update the local-scope bullet**

In the `## numeric-anchor` section, replace the *local scope* bullet:

```markdown
  - *local scope* — a resolvable `task:tNNN`, `[@citekey]`, `cite:key`, or
    `dataset:slug` reference in the **same paragraph** — covers only that
    paragraph.
```

with:

```markdown
  - *local scope* — a resolvable reference in the **same paragraph** covers
    only that paragraph: `task:tNNN`, `[@citekey]`, `cite:key`, or a
    **provenance-bearing typed entity-ref** (interpretation, report, synthesis,
    observation, finding, evidence-line, validation-report, experiment,
    workflow-run, data-package, dataset, paper, book, source, pre-registration,
    plan), cited full-id or as a unique numeric prefix (`interpretation:0013`).
    Topical/framing kinds (hypothesis, question, topic, theme, concept,
    discussion, …) are **not** anchors — citing one next to a number is
    adjacency, not provenance. An ambiguous numeric prefix (two owners) or a
    non-numeric prefix does not resolve.
```

- [ ] **Step 2: Add a sentence to the Existence-checking note**

Append to the `### Existence-checking` paragraph:

```markdown
The same existence check governs entity-ref anchors: a typed entity-ref
resolves only against the project's frontmatter `id:` index (exact id or a
unique digit-lead prefix), so a fabricated `interpretation:9999` or an
ambiguous prefix leaves the claim flagged.
```

- [ ] **Step 3: Commit**

```bash
git add docs/conventions/prose-lints.md
git commit -m "docs(prose-lints): document entity-ref anchoring for numeric-anchor"
```

---

### Task 7: Full gates + pan-disease acceptance

**Files:** none (verification only)

- [ ] **Step 1: Full suite + lint + types**

Run (from `science/`):
```bash
uv run --frozen pytest -q
uv run ruff check
uv run pyright
```
Expected: all green. Investigate any failure before proceeding; a refs-integrity delta from Task 1 must be an intended, explained change.

All pan-disease steps capture **pinned (before)** and **overlay (after)**
JSON and compare **normalized finding identities**, not just aggregate counts
— a wrong finding vanishing while an expected one persists preserves the count
and would slip past a count-only check. Every capture command tolerates its
expected nonzero exit (`|| true`) so a check that flags findings does not abort
the script before the after-scan runs. `pinned` = current `--frozen` science
(0.5.0); `overlay` = the worktree via `--with-editable`.

- [ ] **Step 2: pan-disease numeric-anchor before/after (identity diff, not count)**

`science prose lint --format json` emits `{counts, hits, coverage}`; each hit
carries `file, line, col, check, match`. Filter to the numeric-anchor check and
compare normalized identities `(file, line, col, match)`. Non-strict `prose
lint` exits 0, so no `|| true` is needed (it is included only to guard against a
transient nonzero exit, never to mask a schema error — the `jq -e` assertions
below are the real gate).

From the pan-disease checkout (use `~/d/`, not an absolute Dropbox path):
```bash
cd ~/d/health/comparisons/pan-disease
uv run --frozen \
  science prose lint --check numeric-anchor --format json > /tmp/na-before.json
uv run --with-editable ~/d/science/.worktrees/entity-ref-anchors/science \
  science prose lint --check numeric-anchor --format json > /tmp/na-after.json

_ids() { jq -S '[.hits[] | select(.check=="numeric-anchor") | {file,line,col,match}]' "$1"; }
_ids /tmp/na-before.json > /tmp/na-before.ids
_ids /tmp/na-after.json  > /tmp/na-after.ids
echo "before=$(jq length /tmp/na-before.ids)  after=$(jq length /tmp/na-after.ids)"
echo "=== CLEARED (before − after) ==="
jq -S -n --slurpfile a /tmp/na-before.ids --slurpfile b /tmp/na-after.ids '$a[0] - $b[0]'
echo "=== APPEARED (after − before) — MUST be empty ==="
jq -S -n --slurpfile a /tmp/na-before.ids --slurpfile b /tmp/na-after.ids '$b[0] - $a[0]'
# Hard gate: fail loudly if any new finding appeared.
jq -e -n --slurpfile a /tmp/na-before.ids --slurpfile b /tmp/na-after.ids \
  '(($b[0] - $a[0]) | length) == 0' >/dev/null \
  && echo "OK: no new findings" || { echo "BLOCKED: new numeric-anchor finding(s) appeared"; exit 1; }
```
Expected: before ≈ 196. The **CLEARED** set is ~13 entity-ref-grounded numbers (interpretation/plan/pre-registration citations, incl. pre-reg 0012's `interpretation:0010/0011` values). The **APPEARED** set MUST be empty — the `jq -e` gate exits 1 otherwise, blocking the merge until explained. Record both sets verbatim; every cleared item must trace to a resolvable provenance entity-ref in its paragraph.

- [ ] **Step 3: pan-disease refs-integrity before/after (validate cannot see body refs)**

`science validate` calls `check_refs()` **without** `include_body=True`, so newly-recognized `plan:` body refs are invisible to it. Diff the body-ref scan directly (it exits 1 when broken refs exist — tolerate that):

```bash
cd ~/d/health/comparisons/pan-disease
uv run --frozen \
  science refs check --include-body --format json > /tmp/refs-before.json || true
uv run --with-editable ~/d/science/.worktrees/entity-ref-anchors/science \
  science refs check --include-body --format json > /tmp/refs-after.json || true
diff <(jq -S '.broken' /tmp/refs-before.json) <(jq -S '.broken' /tmp/refs-after.json) || true
```
Expected delta, entirely from the Task 1 `plan` index addition: `plan:` body refs that were unindexed (and thus silently skipped) before now either **resolve** (full-id `plan:NNNN-slug` citations drop out of `broken`) or **surface as broken** where a short `plan:NNNN` prefix fails refs' exact-match body scan (refs has no prefix resolution — that lives only in numeric-anchor). Record the exact broken-ref delta; changes must be confined to `plan:` refs. Any non-`plan:` movement blocks the merge.

- [ ] **Step 4: pan-disease full-validation before/after (JSON must be identical)**

`validate --format json`'s payload (`_json_payload`) **drops INFO-severity
results** — and non-strict `numeric-anchor` is INFO — so the numeric-anchor
delta does **not** surface here at all; Step 2 already proved it precisely. The
correct expectation for validate is therefore **identical** before/after JSON.
Validation is expected to pass (pan-disease is green post-t107), so run it
**without** `|| true` — a nonzero exit is a real failure to investigate, not
something to swallow.

```bash
cd ~/d/health/comparisons/pan-disease
uv run --frozen \
  science validate --format json > /tmp/validate-before.json
uv run --with-editable ~/d/science/.worktrees/entity-ref-anchors/science \
  science validate --format json > /tmp/validate-after.json
diff <(jq -S . /tmp/validate-before.json) <(jq -S . /tmp/validate-after.json) \
  && echo "OK: validation JSON unchanged" || { echo "BLOCKED: validation payload changed"; exit 1; }
```
Expected: **no diff** — status stays `PASSED` and, because INFO results are excluded, the numeric-anchor reduction is intentionally invisible here (that is Step 2's job). Any diff means an ERROR/WARN-level check moved and blocks the merge. Retain both full JSON payloads for the record.

- [ ] **Step 5: Finish the branch**

Use superpowers:finishing-a-development-branch. Merge target: science `main`.

---

## Self-review notes

- **Spec coverage:** allowlist (T3) · prefix+ambiguity, count-map contract (T2) · non-numeric-prefix guard (T2) · dotted ids + no-`..` + atomic anti-truncation (T3) · boundary guards incl. dataset fold (T3) · plan index + refs contract (T1) · detector bump (T5) · docs (T6) · numeric-anchor + refs-body + validation deltas (T7). All design sections map to a task.
- **Type consistency:** `entity_prefix_owners: dict[str, int]` (no default — the sole constructor `build_resolution_index` always computes it; verified no other `ResolutionIndex(...)` call site and nothing hashes the instance, so the dict field is safe under `frozen=True`, which still blocks attribute reassignment); `resolve()` reads it via `.get(ref) == 1`, matching validator.py's single-owner precedent. `_ANCHOR_ENTITY_KINDS`/`_ANCHOR_KIND_ALT` module constants; `resolve()` signature unchanged.
- **No placeholders:** every code step carries complete code; the `_interp`/`_hypothesis`/`_refs`/`_resolved_refs` test helpers are defined in T2/T3/T4 before use.
- **Anti-masking invariant (design rev 5):** (1) kind allowlist at extraction; (2) exact-id or single-owner digit-lead prefix at resolution; (3) two-sided boundary guards + an id-scoped no-`..` lookahead + an atomic id-body (full `_VERBATIM_RE` charset) that forbids backtrack-truncation. Topical kinds, fabricated refs, ambiguous/non-numeric prefixes, `..`-malformed ids (which yield *no* candidate, not a truncated one), and embedded substrings all leave the number `Unanchored`. Grammar verified against Python 3.13 `re` over 24 cases incl. every reviewer truncation vector.
- **Delta rigor (T7):** every pan-disease acceptance step diffs normalized finding *identities* (file, line, literal) pinned-vs-overlay, not aggregate counts, and asserts the "appeared" set is empty — a count-preserving swap cannot pass. Captures tolerate expected nonzero exits.
