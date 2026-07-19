# Entity-ref citations as numeric-anchor anchors — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `numeric-anchor` recognize resolvable, provenance-bearing typed entity-ref citations (`interpretation:0011-…`, short `plan:0023`, `dataset:gtex`) as paragraph-local anchors, without masking — so genuinely-grounded numbers stop flagging while topical citations, fabricated refs, ambiguous prefixes, and embedded substrings still flag.

**Architecture:** Three contained changes in `src/science_tool/numeric_provenance.py` (a provenance-kind allowlist driving one guarded `_BODY_REF_RE` branch; short numeric-prefix resolution on `ResolutionIndex`), plus a one-kind correction to `refs._LOCAL_ENTITY_KINDS` and a detector-version bump. Design: [`2026-07-19-entity-ref-numeric-anchors-design.md`](2026-07-19-entity-ref-numeric-anchors-design.md) (rev 4, approved).

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
- Produces: `ResolutionIndex.unique_entity_prefixes: frozenset[str]` — `<kind>:<digit-lead>` for every canonical id `<kind>:<digits>-<rest>` owned by **exactly one** entity. `resolve()` returns True for a `_TYPED_REF_RE` ref that is an exact id **or** a unique digit-lead prefix.

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
Expected: FAIL — `ResolutionIndex` has no `unique_entity_prefixes`, and `resolve()` returns False for the prefix forms.

- [ ] **Step 3: Add the field to `ResolutionIndex`**

In `src/science_tool/numeric_provenance.py`, add a field to the frozen dataclass (after `data_root`):

```python
    data_root: Path
    unique_entity_prefixes: frozenset[str] = frozenset()
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
            # Exact canonical id, or a unique digit-lead short prefix
            # (`interpretation:0013` -> the sole `interpretation:0013-…`).
            # Non-numeric leads and ambiguous (multi-owner) prefixes never
            # resolve — a citation must not silently anchor to a guessed entity.
            return ref in self.entity_ids or ref in self.unique_entity_prefixes
```

- [ ] **Step 5: Populate the prefix set in `build_resolution_index`**

Replace the `return ResolutionIndex(...)` block body so `entity_ids` is captured and the prefix set computed:

```python
    entity_ids = frozenset(refs._load_entity_index(root))
    prefix_owner_counts: dict[str, int] = {}
    for eid in entity_ids:
        kind, _, ident = eid.partition(":")
        lead = ident.split("-", 1)[0]
        if lead.isdigit() and lead != ident:
            prefix_owner_counts[f"{kind}:{lead}"] = prefix_owner_counts.get(f"{kind}:{lead}", 0) + 1
    return ResolutionIndex(
        project_root=root,
        task_numbers=frozenset(task_numbers),
        entity_ids=entity_ids,
        bib_keys=frozenset(load_bib_keys(root)),
        doi_corpus=frozenset(d.strip().lower() for d in refs._load_doi_corpus(root)),
        pmid_corpus=frozenset(refs._load_pmid_corpus(root)),
        data_root=resolve_data_root(root),
        unique_entity_prefixes=frozenset(p for p, c in prefix_owner_counts.items() if c == 1),
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
- Produces: `_ANCHOR_ENTITY_KINDS: frozenset[str]`; `_BODY_REF_RE` matches allowlisted `<kind>:<id>` (full or short, incl. dotted ids) with two-sided boundary guards, and no longer has a standalone `dataset:` alternative.

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

Run: `uv run --frozen pytest tests/test_numeric_provenance.py -k "provenance_entity_ref or dotted_verbatim or topical_kinds or embedded_tokens or dataset_under_guard" -v`
Expected: FAIL — entity-ref kinds are not extracted; the old `dataset:` branch still masks `path/dataset:xyz` and drops the trailing period.

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
    # Provenance-bearing typed entity-ref (incl. dataset). Two-sided token
    # guards: the left lookbehind rejects an id embedded in a larger token
    # (x_interpretation, path/…, a:…); the id requires an alnum terminal so a
    # trailing sentence period stays outside; the right lookahead rejects
    # @host / /path / :extra continuations.
    r"|(?<![A-Za-z0-9_.:/@-])(?:" + _ANCHOR_KIND_ALT + r"):"
    r"[0-9A-Za-z](?:[0-9A-Za-z._-]*[0-9A-Za-z])?(?![A-Za-z0-9_:/@-])"
    r"|\[\[[^\]\n]+\]\])"
)
```

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

Run: `uv run --frozen pytest tests/test_numeric_provenance.py -k "provenance_entity_ref or dotted_verbatim or topical_kinds or embedded_tokens or dataset_under_guard" -v`
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
    _project(tmp_path)
    idx = build_resolution_index(tmp_path)
    path = _doc(tmp_path, "The ARI z was 221 (`hypothesis:0001-molecular-truth`).",
                frontmatter="kind: interpretation")
    out = assess_numeric_claims(build_document_context(path), idx, _CFG)
    kinds = {type(a).__name__ for a in out if a.claim.value == "221"}
    assert kinds == {"Unanchored"}   # topical citation must not clear the claim
```

Note: `_CFG` and `_assess` already exist near the bottom of the test file; if `_CFG` is defined after these tests, place these two tests below its definition. Build the index explicitly (as above) so the freshly-written entity files are picked up.

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

- [ ] **Step 2: pan-disease acceptance (overlay, no pin bump)**

From the pan-disease checkout:
```bash
cd /mnt/ssd/Dropbox/health/comparisons/pan-disease
uv run --with-editable ~/d/science/.worktrees/entity-ref-anchors/science \
  science prose lint --check numeric-anchor --format json > /tmp/after.json
```
Compare against the pre-change baseline (196). Expected: ~13 fewer findings (interpretation/plan/pre-registration citations clear, including pre-reg 0012's `interpretation:0010/0011` values); hypothesis/question/discussion-adjacent numbers remain flagged. Record the exact delta.

- [ ] **Step 3: pan-disease refs delta (record, do not assume unchanged)**

```bash
uv run --with-editable ~/d/science/.worktrees/entity-ref-anchors/science \
  science validate 2>&1 | tail -3
```
Expected: PASSED. If the `plan` index addition surfaces new `plan:` body-entity-ref warnings under the project's ref checks, record them as the expected refs delta (short `plan:` prefixes fail refs' exact-match body scan) — this is intended, not a regression.

- [ ] **Step 4: Finish the branch**

Use superpowers:finishing-a-development-branch. Merge target: science `main`.

---

## Self-review notes

- **Spec coverage:** allowlist (T3) · prefix+ambiguity (T2) · non-numeric-prefix guard (T2) · dotted ids (T3) · boundary guards incl. dataset fold (T3) · plan index + refs contract (T1) · detector bump (T5) · docs (T6) · acceptance/deltas (T7). All design sections map to a task.
- **Type consistency:** `unique_entity_prefixes: frozenset[str]` (defaulted, keeps `ResolutionIndex` hashable and existing single constructor valid); `_ANCHOR_ENTITY_KINDS`/`_ANCHOR_KIND_ALT` module constants; `resolve()` signature unchanged.
- **No placeholders:** every code step carries complete code; the `_interp`/`_refs`/`_resolved_refs` test helpers are defined in T2/T3 before use.
