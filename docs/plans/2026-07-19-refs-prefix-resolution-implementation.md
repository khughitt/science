# refs body-entity-ref prefix resolution — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Teach `science refs check --include-body` to resolve a short digit-lead body entity-ref (e.g. `plan:0019`) against the canonical `id:` index — exact id or unique digit-lead prefix — and reuse the same rule that t108 already uses for numeric-anchor.

**Architecture:** Extract the "unique digit-lead prefix" contract into two pure helpers in `refs.py` (the single source of truth), wire them into the body-prose scan with a distinct ambiguity diagnostic, then refactor `numeric_provenance.py` to reuse them so the two checks share one implementation.

**Tech Stack:** Python 3.13, `uv`, pytest, ruff, pyright. Package root is `science/` inside the worktree.

## Global Constraints

- Work in the worktree: `~/d/science/.worktrees/refs-prefix-resolution`. The package lives in its `science/` subdir; run all `uv`/pytest/ruff/pyright from there.
- Resolution semantics are **digit-lead prefix only**, identical to t108: `ref in entity_ids or prefix_owners.get(ref) == 1`. Non-numeric leads and ambiguous multi-owner prefixes never resolve (fail-closed).
- Helper params take a read-only `AbstractSet[str]` (`from collections.abc import Set as AbstractSet`) — never `set[str]`/`Iterable[str]` — so a `frozenset` caller type-checks and duplicate inputs cannot over-count owners.
- No AI-attribution trailers/footers on commits.
- Use `~/d/` in any doc/code path references, never `/home/keith/...` or `/mnt/ssd/...`.
- Changed-files gate: `ruff check` and `pyright` must be clean on the files this branch touches. The repo carries pre-existing findings in untouched files (observed during t108) — those are out of scope.
- `science validate` behavior must be unchanged (it calls `check_refs()` without `include_body`).

---

### Task 1: Pure prefix-resolution helpers in `refs.py`

**Files:**
- Modify: `science/src/science_tool/refs.py` (add import near line 8–12; add two functions after `_resolve_entity_index`, before `_scan_body_typed_refs` at line 354)
- Test: `science/tests/test_refs.py` (new `TestEntityPrefixResolution` class)

**Interfaces:**
- Produces:
  - `build_entity_prefix_owners(entity_ids: AbstractSet[str]) -> dict[str, int]`
  - `resolve_local_entity_ref(ref: str, entity_ids: AbstractSet[str], prefix_owners: dict[str, int]) -> bool`

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_refs.py`:

```python
class TestEntityPrefixResolution:
    def test_build_counts_unique_digit_lead_owner(self):
        from science_tool.refs import build_entity_prefix_owners

        owners = build_entity_prefix_owners({"plan:0019-t071-panel", "plan:0020-other"})
        assert owners == {"plan:0019": 1, "plan:0020": 1}

    def test_build_counts_multiple_owners_for_same_prefix(self):
        from science_tool.refs import build_entity_prefix_owners

        owners = build_entity_prefix_owners({"plan:0019-a", "plan:0019-b"})
        assert owners == {"plan:0019": 2}

    def test_build_excludes_non_digit_and_bare_numeric_leads(self):
        from science_tool.refs import build_entity_prefix_owners

        # non-numeric lead (dataset:gtex-v8 -> lead "gtex") excluded;
        # bare-numeric id (plan:0019, lead == ident) does not self-count.
        owners = build_entity_prefix_owners({"dataset:gtex-v8", "plan:0019"})
        assert owners == {}

    def test_resolve_exact_id(self):
        from science_tool.refs import resolve_local_entity_ref

        ids = {"plan:0019-t071-panel"}
        assert resolve_local_entity_ref("plan:0019-t071-panel", ids, {}) is True

    def test_resolve_unique_digit_lead_prefix(self):
        from science_tool.refs import resolve_local_entity_ref

        ids = {"plan:0019-t071-panel"}
        owners = {"plan:0019": 1}
        assert resolve_local_entity_ref("plan:0019", ids, owners) is True

    def test_resolve_rejects_ambiguous_prefix(self):
        from science_tool.refs import resolve_local_entity_ref

        ids = {"plan:0019-a", "plan:0019-b"}
        owners = {"plan:0019": 2}
        assert resolve_local_entity_ref("plan:0019", ids, owners) is False

    def test_resolve_rejects_absent_ref(self):
        from science_tool.refs import resolve_local_entity_ref

        assert resolve_local_entity_ref("plan:9999", {"plan:0019-a"}, {}) is False

    def test_build_accepts_frozenset(self):
        # ResolutionIndex.entity_ids is a frozenset — the param type must accept it.
        from science_tool.refs import build_entity_prefix_owners

        owners = build_entity_prefix_owners(frozenset({"interpretation:0011-x"}))
        assert owners == {"interpretation:0011": 1}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/.worktrees/refs-prefix-resolution/science && uv run --frozen pytest tests/test_refs.py::TestEntityPrefixResolution -v`
Expected: FAIL — `ImportError: cannot import name 'build_entity_prefix_owners'`.

- [ ] **Step 3: Add the import**

In `science/src/science_tool/refs.py`, add after `from pathlib import Path` (line 12):

```python
from collections.abc import Set as AbstractSet
```

- [ ] **Step 4: Add the two helpers**

In `science/src/science_tool/refs.py`, insert immediately before `def _scan_body_typed_refs(` (currently line 354):

```python
def build_entity_prefix_owners(entity_ids: AbstractSet[str]) -> dict[str, int]:
    """Count owners of each `<kind>:<digit-lead>` short prefix.

    For a canonical id `<kind>:<ident>`, the lead is the segment before the
    first `-`. A lead that is all-digits and is not the whole ident (so a
    bare-numeric id does not count itself) registers one owner under
    `<kind>:<lead>`. A short ref resolves only when its owner count is exactly
    one (see `resolve_local_entity_ref`), so this map is the fail-closed
    ambiguity guard. Takes a read-only set so duplicate values cannot inflate
    a count.
    """
    owners: dict[str, int] = {}
    for eid in entity_ids:
        kind, _, ident = eid.partition(":")
        lead = ident.split("-", 1)[0]
        if lead.isdigit() and lead != ident:
            key = f"{kind}:{lead}"
            owners[key] = owners.get(key, 0) + 1
    return owners


def resolve_local_entity_ref(
    ref: str, entity_ids: AbstractSet[str], prefix_owners: dict[str, int]
) -> bool:
    """True if `ref` is an exact canonical id or a unique digit-lead prefix.

    Non-numeric leads never enter `prefix_owners`, and ambiguous multi-owner
    prefixes have a count > 1, so neither resolves — a citation can never
    silently anchor to a guessed entity.
    """
    return ref in entity_ids or prefix_owners.get(ref) == 1
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd ~/d/science/.worktrees/refs-prefix-resolution/science && uv run --frozen pytest tests/test_refs.py::TestEntityPrefixResolution -v`
Expected: PASS (8 passed).

- [ ] **Step 6: Lint & type-check the changed files**

Run: `cd ~/d/science/.worktrees/refs-prefix-resolution/science && uv run --frozen ruff check src/science_tool/refs.py tests/test_refs.py && uv run --frozen pyright src/science_tool/refs.py`
Expected: no new findings in these files.

- [ ] **Step 7: Commit**

```bash
cd ~/d/science/.worktrees/refs-prefix-resolution
git add science/src/science_tool/refs.py science/tests/test_refs.py
git commit -m "feat(refs): add shared entity-ref prefix-resolution helpers"
```

---

### Task 2: Wire prefix resolution + ambiguity diagnostic into the body scan

**Files:**
- Modify: `science/src/science_tool/refs.py` — `_scan_body_typed_refs` (354–390), `check_refs` (build at 564, call site 781–790)
- Modify: `docs/conventions/refs-check.md` (worktree-root docs, NOT under `science/`; "Default behavior" section, lines 9–14)
- Test: `science/tests/test_refs.py` (extend `TestBodyTypedRefScan`)

**Interfaces:**
- Consumes: `build_entity_prefix_owners`, `resolve_local_entity_ref` (Task 1)
- Produces: `_scan_body_typed_refs(file_path, rel_path, lines, frontmatter_lines, entity_index, prefix_owners)` — new trailing `prefix_owners: dict[str, int]` param

- [ ] **Step 1: Write the failing tests**

Add to `TestBodyTypedRefScan` in `science/tests/test_refs.py` (the class's `_project` helper creates `question:q01-foo` and `task:t050`; extend it to add a plan and an ambiguous pair):

```python
    def test_short_digit_lead_prefix_resolves(self, tmp_path):
        from science_tool.refs import check_refs

        root = self._project(tmp_path)
        (root / "doc" / "plan19.md").write_text(
            "---\nid: plan:0019-t071-panel\nkind: plan\n---\nBody.\n"
        )
        (root / "doc" / "report.md").write_text(
            "---\nkind: report\n---\nSee plan:0019 for the design.\n"
        )
        issues = check_refs(root, include_body=True)
        assert [i for i in issues if i.ref_type == "body-entity-ref"] == []

    def test_ambiguous_short_prefix_gets_ambiguity_diagnostic(self, tmp_path):
        from science_tool.refs import check_refs

        root = self._project(tmp_path)
        (root / "doc" / "plan19a.md").write_text(
            "---\nid: plan:0019-alpha\nkind: plan\n---\nBody.\n"
        )
        (root / "doc" / "plan19b.md").write_text(
            "---\nid: plan:0019-beta\nkind: plan\n---\nBody.\n"
        )
        (root / "doc" / "report.md").write_text(
            "---\nkind: report\n---\nSee plan:0019 for the design.\n"
        )
        issues = check_refs(root, include_body=True)
        body = [i for i in issues if i.ref_type == "body-entity-ref"]
        assert len(body) == 1
        assert body[0].ref_value == "plan:0019"
        assert "ambiguous short entity ref" in body[0].message
        assert "2" in body[0].message

    def test_non_numeric_short_prefix_still_flagged(self, tmp_path):
        from science_tool.refs import check_refs

        root = self._project(tmp_path)
        (root / "doc" / "gtex.md").write_text(
            "---\nid: dataset:gtex-v8\nkind: dataset\n---\nBody.\n"
        )
        (root / "doc" / "report.md").write_text(
            "---\nkind: report\n---\nSee dataset:gtex for the source.\n"
        )
        issues = check_refs(root, include_body=True)
        body = [i for i in issues if i.ref_type == "body-entity-ref"]
        assert len(body) == 1
        assert body[0].ref_value == "dataset:gtex"
        assert "ambiguous" not in body[0].message

    def test_not_found_message_is_source_neutral(self, tmp_path):
        from science_tool.refs import check_refs

        root = self._project(tmp_path)
        (root / "doc" / "report.md").write_text(
            "---\nkind: report\n---\nSee task:t999 for the gap.\n"
        )
        issues = check_refs(root, include_body=True)
        body = [i for i in issues if i.ref_type == "body-entity-ref"]
        assert len(body) == 1
        assert "frontmatter" not in body[0].message
        assert "not found in project entity id index" in body[0].message
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/.worktrees/refs-prefix-resolution/science && uv run --frozen pytest tests/test_refs.py::TestBodyTypedRefScan -v`
Expected: **three** new tests FAIL and **one** already passes:
- FAIL `test_short_digit_lead_prefix_resolves` — current exact-match still flags `plan:0019`.
- FAIL `test_ambiguous_short_prefix_gets_ambiguity_diagnostic` — no ambiguity message exists yet.
- FAIL `test_not_found_message_is_source_neutral` — current message still says "frontmatter `id:` index".
- PASS `test_non_numeric_short_prefix_still_flagged` — `dataset:gtex` is already flagged under current behavior, and the old not-found message contains no "ambiguous"; this test is a regression guard confirming the exact-only path for non-numeric leads is preserved by the change.

- [ ] **Step 3: Update `_scan_body_typed_refs` signature and resolution logic**

In `science/src/science_tool/refs.py`, change the signature (line 354–360) to add the trailing param:

```python
def _scan_body_typed_refs(
    file_path: Path,
    rel_path: str,
    lines: list[str],
    frontmatter_lines: set[int],
    entity_index: set[str],
    prefix_owners: dict[str, int],
) -> list[RefIssue]:
```

Then replace the resolution/append block (currently lines 379–389, from `if ref in entity_index:` through the `issues.append(...)` call) with:

```python
            if resolve_local_entity_ref(ref, entity_index, prefix_owners):
                continue
            owners = prefix_owners.get(ref, 0)
            if owners > 1:
                message = (
                    f"{ref} — ambiguous short entity ref: matches {owners} "
                    "entities by prefix; cite the full id"
                )
            else:
                message = f"{ref} — typed entity ref not found in project entity id index"
            issues.append(
                RefIssue(
                    file=rel_path,
                    line=line_num,
                    ref_type="body-entity-ref",
                    ref_value=ref,
                    message=message,
                )
            )
```

- [ ] **Step 4: Build `prefix_owners` in `check_refs` and thread it through**

In `science/src/science_tool/refs.py`, after line 564 (`entity_index = _resolve_entity_index(...) if include_body else set()`) add:

```python
    prefix_owners = build_entity_prefix_owners(entity_index) if include_body else {}
```

Then update the call site (currently 781–790) to pass it:

```python
        if include_body:
            issues.extend(
                _scan_body_typed_refs(
                    file_path,
                    rel_path,
                    lines,
                    frontmatter_lines,
                    entity_index,
                    prefix_owners,
                )
            )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd ~/d/science/.worktrees/refs-prefix-resolution/science && uv run --frozen pytest tests/test_refs.py::TestBodyTypedRefScan -v`
Expected: PASS (all existing + 4 new).

- [ ] **Step 6: Run the whole refs test module (catch regressions in the message change)**

Run: `cd ~/d/science/.worktrees/refs-prefix-resolution/science && uv run --frozen pytest tests/test_refs.py -q`
Expected: PASS. If any test asserted the old `"frontmatter \`id:\` index"` string, update it to the neutralized wording (a pre-scan showed only a docstring at `tests/test_refs.py:1536`, which needs no change, but confirm).

- [ ] **Step 7: Update `docs/conventions/refs-check.md`**

In the worktree-root file `docs/conventions/refs-check.md`, replace the "Default behavior" paragraph (lines 9–14) with:

```markdown
Scans `paths.doc_dir` (default `doc/`), `paths.entities_dir` (default
`entities/`), and root `README.md`. The body-prose typed-ref scan
(opt-in via `--include-body`) validates each `<kind>:<slug>` ref against the
project's configured entity ID index — the frontmatter `id:` sweep by
default, or `knowledge/graph.trig` when `entity_index_source:
knowledge_graph` is set (see `entity_index_source` below). A body ref
resolves by **exact canonical id or unique digit-lead prefix** — so
`plan:0019` resolves to the sole `plan:0019-…` entity, while a prefix owned
by two or more entities is reported as an ambiguous short ref (cite the full
id), and a non-numeric short prefix (`dataset:gtex`) resolves by exact id
only.
```

- [ ] **Step 8: Lint & type-check the changed files**

Run: `cd ~/d/science/.worktrees/refs-prefix-resolution/science && uv run --frozen ruff check src/science_tool/refs.py tests/test_refs.py && uv run --frozen pyright src/science_tool/refs.py`
Expected: no new findings.

- [ ] **Step 9: Commit**

```bash
cd ~/d/science/.worktrees/refs-prefix-resolution
git add science/src/science_tool/refs.py science/tests/test_refs.py docs/conventions/refs-check.md
git commit -m "feat(refs): resolve short digit-lead body entity-refs; distinct ambiguity diagnostic"
```

---

### Task 3: Refactor `numeric_provenance.py` to reuse the shared helpers

**Files:**
- Modify: `science/src/science_tool/numeric_provenance.py` — `build_resolution_index` (653–659), `ResolutionIndex.resolve` (218–224)
- Test: `science/tests/test_numeric_provenance.py` (existing t108 tests are the regression guard; no new tests required)

**Interfaces:**
- Consumes: `refs.build_entity_prefix_owners`, `refs.resolve_local_entity_ref` (Task 1)
- Produces: no signature changes — `ResolutionIndex` keeps its `entity_prefix_owners: dict[str, int]` field and frozen shape.

- [ ] **Step 1: Confirm the regression baseline is green**

Run: `cd ~/d/science/.worktrees/refs-prefix-resolution/science && uv run --frozen pytest tests/test_numeric_provenance.py -q`
Expected: PASS (baseline before refactor).

- [ ] **Step 2: Replace the inline owner-count loop in `build_resolution_index`**

In `science/src/science_tool/numeric_provenance.py`, replace the loop (currently lines 653–659):

```python
    entity_prefix_owners: dict[str, int] = {}
    for eid in entity_ids:
        kind, _, ident = eid.partition(":")
        lead = ident.split("-", 1)[0]
        if lead.isdigit() and lead != ident:
            key = f"{kind}:{lead}"
            entity_prefix_owners[key] = entity_prefix_owners.get(key, 0) + 1
```

with (the function already does `from science_tool import refs` at its top, line 646):

```python
    entity_prefix_owners = refs.build_entity_prefix_owners(entity_ids)
```

- [ ] **Step 3: Replace the inline resolve expression in `ResolutionIndex.resolve`**

In `science/src/science_tool/numeric_provenance.py`, replace the `_TYPED_REF_RE` branch (currently lines 218–224):

```python
        if _TYPED_REF_RE.match(ref):
            # Exact canonical id, or a digit-lead short prefix owned by exactly
            # one entity (`interpretation:0013` -> the sole `interpretation:0013-…`).
            # Non-numeric leads never enter the map; ambiguous (multi-owner)
            # prefixes have owners > 1 — neither resolves, so a citation cannot
            # silently anchor to a guessed entity.
            return ref in self.entity_ids or self.entity_prefix_owners.get(ref) == 1
```

with (add the function-local import — `resolve()` does not otherwise have `refs` in scope; refs imports nothing from numeric_provenance, so this is cycle-proof):

```python
        if _TYPED_REF_RE.match(ref):
            # Exact canonical id, or a digit-lead short prefix owned by exactly
            # one entity (`interpretation:0013` -> the sole `interpretation:0013-…`).
            # Non-numeric leads never enter the map; ambiguous (multi-owner)
            # prefixes have owners > 1 — neither resolves, so a citation cannot
            # silently anchor to a guessed entity. Shared with refs body-scan.
            from science_tool import refs

            return refs.resolve_local_entity_ref(
                ref, self.entity_ids, self.entity_prefix_owners
            )
```

- [ ] **Step 4: Run the regression suite to verify identical behavior**

Run: `cd ~/d/science/.worktrees/refs-prefix-resolution/science && uv run --frozen pytest tests/test_numeric_provenance.py -q`
Expected: PASS — same result set as Step 1.

- [ ] **Step 5: Lint & type-check the changed file**

Run: `cd ~/d/science/.worktrees/refs-prefix-resolution/science && uv run --frozen ruff check src/science_tool/numeric_provenance.py && uv run --frozen pyright src/science_tool/numeric_provenance.py`
Expected: no new findings.

- [ ] **Step 6: Commit**

```bash
cd ~/d/science/.worktrees/refs-prefix-resolution
git add science/src/science_tool/numeric_provenance.py
git commit -m "refactor(numeric-anchor): reuse shared refs prefix-resolution helpers"
```

---

### Task 4: Full-suite + static gates + pan-disease overlay acceptance

**Files:** none (verification only; capture evidence).

- [ ] **Step 1: Full science test suite**

Run: `cd ~/d/science/.worktrees/refs-prefix-resolution/science && uv run --frozen pytest -q`
Expected: green (no failures introduced).

- [ ] **Step 2: Static gates on all changed files**

Run:
```bash
cd ~/d/science/.worktrees/refs-prefix-resolution/science
uv run --frozen ruff check src/science_tool/refs.py src/science_tool/numeric_provenance.py tests/test_refs.py tests/test_numeric_provenance.py
uv run --frozen pyright src/science_tool/refs.py src/science_tool/numeric_provenance.py
```
Expected: clean on these files (pre-existing findings in untouched files are out of scope).

- [ ] **Step 3: pan-disease overlay — short digit-lead prefixes clear, no new breakage**

From the pan-disease project root, overlay the worktree's science and compare `refs check --include-body` against the current pinned behavior:

```bash
cd ~/d/health/comparisons/pan-disease
# Current pin (short digit-lead prefixes flagged):
uv run --frozen science refs check --include-body --format json \
  > /tmp/refs-before.json 2>/dev/null; echo "before exit: $?"
# Worktree overlay (prefix resolution active):
uv run --with-editable ~/d/science/.worktrees/refs-prefix-resolution/science \
  science refs check --include-body --format json \
  > /tmp/refs-after.json 2>/dev/null; echo "after exit: $?"
```

Then confirm each cleared ref is backed by **exactly one canonical owner** (a genuine unique digit-lead prefix) and nothing regressed. The shape regex alone is insufficient — a fabricated `interpretation:9999` also matches `<kind>:<digits>`; it simply never *clears* (0 owners → still broken in both runs). The authoritative proof is the owner count, so run the check **under the overlay env** and rebuild the same index + owner map the overlay's scan used:

```bash
uv run --with-editable ~/d/science/.worktrees/refs-prefix-resolution/science \
  python3 - <<'PY'
import json
from pathlib import Path
from science_tool import refs
before = json.load(open("/tmp/refs-before.json"))
after = json.load(open("/tmp/refs-after.json"))
def keyset(d):
    items = d if isinstance(d, list) else d.get("issues", d.get("broken", []))
    return {(i.get("file"), i.get("value") or i.get("ref_value"), i.get("line")) for i in items}
cleared = keyset(before) - keyset(after)
appeared = keyset(after) - keyset(before)
print("cleared:", len(cleared), " appeared:", len(appeared))
for c in sorted(cleared): print("  -", c)
for c in sorted(appeared): print("  +", c)
# Rebuild the exact index + owner map the overlay refs scan used.
root = Path(".")
idx = refs._resolve_entity_index(root, refs._load_refs_config(root))
owners = refs.build_entity_prefix_owners(idx)
assert not appeared, "REGRESSION: new broken refs appeared under overlay"
assert cleared, "NO-OP: nothing cleared — prefix resolution is not active"
# Every clear must be a `<kind>:<digits>` prefix with exactly ONE canonical
# owner. This rejects fabricated refs (owners.get -> None), ambiguous prefixes
# (> 1), and suffixed full ids (never a key in the owner map) in one check.
notunique = [v for _, v, _ in cleared if owners.get(v) != 1]
assert not notunique, f"clears not backed by a unique canonical owner: {notunique}"
print("OK: every clear is a unique digit-lead prefix; no regressions")
PY
```

Expected: `cleared` is non-empty and every entry is a `<kind>:<digits>` prefix with owner count 1 (e.g. `plan:0019`, plus any pre-existing `interpretation:NNNN` / `pre-registration:NNNN` body short-refs that now resolve); `appeared` is empty. Inspect `/tmp/refs-before.json` first and adjust the `keyset` extractor if the JSON shape differs — the `assert cleared` guards against a mis-parsed empty keyset silently passing.

- [ ] **Step 4: `science validate` unchanged under the overlay**

```bash
cd ~/d/health/comparisons/pan-disease
uv run --frozen science validate --format json > /tmp/validate-before.json 2>/dev/null
uv run --with-editable ~/d/science/.worktrees/refs-prefix-resolution/science \
  science validate --format json > /tmp/validate-after.json 2>/dev/null
# One script loads BOTH payloads and asserts structural equality. A parse
# failure (empty/invalid JSON from either run) raises -> nonzero exit, so a
# double-empty render cannot false-pass the way a `diff` of two empty renders
# would.
python3 - <<'PY'
import json, sys
before = json.load(open("/tmp/validate-before.json"))  # raises on empty/invalid
after = json.load(open("/tmp/validate-after.json"))
if before == after:
    print("VALIDATE IDENTICAL")
else:
    print("VALIDATE DIFF — investigate", file=sys.stderr)
    sys.exit(1)
PY
```
Expected: `VALIDATE IDENTICAL` (this change never reaches `validate`); a difference or an unparseable payload exits nonzero and fails the step.

- [ ] **Step 5: Record acceptance evidence**

Note the cleared-count and the `VALIDATE IDENTICAL` result in the final review / progress ledger. No commit (verification only).

---

## Notes for the executor

- The pan-disease overlay in Task 4 reads the **worktree** package via `--with-editable ~/d/science/.worktrees/refs-prefix-resolution/science` — not the main `~/d/science` checkout. Do not bump the pan-disease pin here; that is a separate follow-up once this branch merges.
- Every commit body must be free of AI-attribution trailers.
- If `refs check --format json` or `validate --format json` emits a non-list top-level shape, inspect the file and adjust the extractor before asserting — do not silently pass on an empty keyset.
