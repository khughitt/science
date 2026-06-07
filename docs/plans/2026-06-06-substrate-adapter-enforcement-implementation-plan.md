# Adapter Participation-Mode Enforcement (Substrate Phase 1.2) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the framework **owner root** (`entities/`) hold owner declarations *only*: a markdown file under `entities/` that carries `overlay_of:` frontmatter is a **conformance violation** (WARN during the v2→v3 transition, ERROR at `layout_version >= 3`), because such a file would otherwise be silently minted as a spurious `OWNER` by `MarkdownAdapter` while an overlay is, by design, a *borrow* attachment read only by `OverlayAdapter` under `doc/<type>/`.

**Architecture:** Add one canonical validation check, `check_overlay_of_in_owner_root`, to the already-registered `validate/checks/entity_conformance.py` module (the home of the other `entities/` layout-conformance checks). It does a tolerant frontmatter scan of `entities/**/*.md` and yields a `Result` for any file declaring `overlay_of`. No loader changes, no identity-table changes, no new module registration — the `@Check` decorator wires it in on import.

This implements the **owner-root facet** of §C3 — and only that facet. It keeps a borrow declaration from hiding in `entities/`, the one owner root where `MarkdownAdapter` would otherwise mint it as a spurious owner. It is deliberately *partial*: `load_project_sources` still configures `MarkdownAdapter` to also scan `doc/datasets`, `doc/workflows`, and `doc/workflow-runs` (`sources.py:254`); those transitional roots are the dataset/workflow dual-SSOT case deferred to 1.5/§B4 and are **not** covered here. `OverlayAdapter` is already the sole *class* that parses overlays (`commons/overlay.py:71`), so "sole borrower reader" is largely a pre-existing property; this check does not by itself collapse OverlayAdapter's four call sites or narrow MarkdownAdapter's scan roots — it only guarantees the `entities/` owner root contains owner declarations exclusively.

**Tech Stack:** Python 3, pytest. Library at `~/d/science/science/` (`src/science_tool/`, `tests/`). Run tests with `cd ~/d/science/science && uv run --frozen pytest`.

**Scope (this plan only):** the single `check_overlay_of_in_owner_root` validation check, its direct-function unit tests, and a registration test. **Out of scope** (later sub-plans / phases): scoped-ref resolution & `ambiguous_reference` (1.3); rerouting the migrator through the compiled model + retiring the masking hack (1.4); migrating orphan datapackages and the dataset dual-SSOT `doc/datasets/` handling (1.5 / §B4 — explicitly NOT touched here, even though `MarkdownAdapter` also scans `doc/datasets`); any identity-table-level "two readers" / "owns-and-borrows" audit row (not reachable under the current commons-only overlay loader, so deliberately omitted to avoid dead code).

**Design source:** `~/d/science/docs/plans/2026-06-06-knowledge-meta-model-and-substrate-design.md` — §B2 (one canonical declaration surface; overlays are attachments; `overlay_of` under an owner root is a conformance error), §C3 (adapter participation-mode table: `MarkdownAdapter` owner-only, `OverlayAdapter` sole borrower reader).

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/science_tool/validate/checks/entity_conformance.py` | Add `check_overlay_of_in_owner_root` (`@Check(... order=42)`); reuse existing `_result`, `_severity`, `_rel`, `yaml` | **Modify** (append a check function; helpers already present) |
| `tests/validate/test_checks_entity_conformance.py` | Direct-function tests (flagged / not-flagged / transition severity) + a registration test | **Modify** (append; reuse existing `_ctx`/`_write` helpers) |

### Reference facts (verified against `main` @ `e2b3a757`)

- The check framework: `@Check(section: str, order: int)` decorator in `validate/checks/__init__.py:64-72` appends a `CheckEntry(section, order, fn)` to the module-global `CANONICAL_CHECKS` on import and re-sorts by `order`. A check is `Callable[[ValidateContext], Iterable[Result]]`.
- `entity_conformance` is **already** in `CANONICAL_CHECK_MODULES` (`__init__.py:47`), so a new `@Check`-decorated function added to that file auto-registers — **no `CANONICAL_CHECK_MODULES` edit needed.**
- **`order=42` is free.** The maximum `order` currently in use across all checks is `41` (`entity_conformance.check_entity_stray_files`, `__init__.py`-loaded). Verify before committing: `grep -rhoE "order=[0-9]+" src/science_tool/validate/checks/*.py | sort -t= -k2 -n | tail -1` should print `order=41`.
- `entity_conformance.py` already imports `yaml` (line 13) and defines the helpers this check reuses:
  - `_result(severity: Severity, path: Path | None, message: str) -> Result` (line 31-32) — sets `rule="entity-conformance"`.
  - `_severity(ctx: ValidateContext) -> Severity` (line 133-135) — `Severity.ERROR` if `ctx.manifest.get("layout_version")` is an int `>= 3`, else `Severity.WARN`. **Reuse this** so the rule warns during the v2→v3 transition and hardens to ERROR in the substrate target state, exactly like the sibling checks.
  - `_rel(ctx, path) -> Path` (line 48-49) — `path.relative_to(ctx.project_root)`.
- `ValidateContext` accessors used here (seen in `entity_conformance.py`): `ctx.project_root: Path`, `ctx.read_text_cached(path) -> str`, `ctx.frontmatter(path) -> dict` (may raise `yaml.YAMLError`), `ctx.manifest: dict`.
- Test idiom (verified in `tests/validate/test_checks_entity_conformance.py:21-37`):
  - `_ctx(tmp_path)` writes `science.yaml` with `layout_version: 3` and returns `ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)`.
  - `_write(root, rel, fm: dict)` writes `"---\n" + yaml.safe_dump(fm) + "---\n"` to `root/rel`.
  - Tests call the check directly: `list(check_xxx(ctx))`, asserting on `r.severity` (`Severity.ERROR`/`WARN`), `r.path`, `r.message`.
- **Blast radius is zero today.** No markdown file under any `entities/` directory in the science repo or its fixtures declares `overlay_of`; legitimate overlays live only under `doc/{datasets,papers,topics,themes}/` (read by `OverlayAdapter`, `commons/overlay.py:71`). The check guards against a future mistake; it will not spuriously fire on existing data. (At `layout_version >= 3` it *would* fire on any genuinely misplaced overlay in a downstream project such as MM30 — which is the intended behavior.)

---

## Task 1: The `check_overlay_of_in_owner_root` check + behavior tests

**Files:**
- Modify: `src/science_tool/validate/checks/entity_conformance.py`
- Test: `tests/validate/test_checks_entity_conformance.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/validate/test_checks_entity_conformance.py`. First add the import to the existing `from science_tool.validate.checks.entity_conformance import (...)` block:

```python
    check_overlay_of_in_owner_root,
```

Also confirm `ValidateContext` is already imported in this file (it is, at module top). Then append:

```python
def test_overlay_of_in_owner_root_flagged_as_error_at_v3(tmp_path: Path) -> None:
    # an overlay file mistakenly placed under the owner root entities/
    _write(
        tmp_path,
        "entities/topics/0001-x.md",
        {"id": "topic:0001-x", "type": "topic", "overlay_of": "topic:0001-x"},
    )
    ctx = _ctx(tmp_path)  # _ctx writes layout_version: 3 -> ERROR
    results = list(check_overlay_of_in_owner_root(ctx))
    assert any(
        r.severity is Severity.ERROR
        and "overlay_of" in r.message
        and "entities/topics/0001-x.md" in str(r.path)
        for r in results
    )


def test_overlay_under_doc_is_not_flagged(tmp_path: Path) -> None:
    # the legitimate location for an overlay; the owner-root check must ignore it
    _write(tmp_path, "doc/topics/bayesian.md", {"overlay_of": "topic:bayesian"})
    ctx = _ctx(tmp_path)
    assert list(check_overlay_of_in_owner_root(ctx)) == []


def test_clean_owner_entity_is_not_flagged(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "entities/topics/0001-x.md",
        {
            "id": "topic:0001-x",
            "type": "topic",
            "title": "X",
            "status": "active",
            "created": "2026-01-01",
            "updated": "2026-01-01",
        },
    )
    ctx = _ctx(tmp_path)
    assert list(check_overlay_of_in_owner_root(ctx)) == []


def test_overlay_of_in_owner_root_warns_during_transition(tmp_path: Path) -> None:
    # layout_version 2 -> WARN, consistent with the sibling entity-conformance checks
    (tmp_path / "science.yaml").write_text(
        "name: t\nlayout_version: 2\nprofile: research\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    _write(
        tmp_path,
        "entities/topics/0001-x.md",
        {"id": "topic:0001-x", "type": "topic", "overlay_of": "topic:0001-x"},
    )
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
    results = list(check_overlay_of_in_owner_root(ctx))
    assert results
    assert all(r.severity is Severity.WARN for r in results)


def test_overlay_of_under_entities_templates_is_ignored(tmp_path: Path) -> None:
    # template scaffolds under entities/**/templates/ are not entities and must be
    # skipped (mirrors the templates guard in check_entity_location_coherence)
    _write(
        tmp_path,
        "entities/questions/templates/example.md",
        {"id": "question:example", "type": "question", "overlay_of": "question:example"},
    )
    ctx = _ctx(tmp_path)
    assert list(check_overlay_of_in_owner_root(ctx)) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_entity_conformance.py -q`
Expected: FAIL — `ImportError: cannot import name 'check_overlay_of_in_owner_root'`.

- [ ] **Step 3: Implement the check**

Append to `src/science_tool/validate/checks/entity_conformance.py` (after `check_entity_stray_files`, the last check). It reuses `_result`, `_severity`, `_rel`, and the already-imported `yaml`:

```python
@Check(section="overlay_of in owner root...", order=42)
def check_overlay_of_in_owner_root(ctx: ValidateContext) -> Iterator[Result]:
    """An overlay (`overlay_of:` frontmatter) is a borrow attachment and belongs
    under doc/<type>/, never under the framework owner root entities/. A file with
    overlay_of in entities/ would be silently minted as a spurious OWNER by
    MarkdownAdapter (design §B2/§C3: the owner root holds owner declarations only;
    OverlayAdapter is the sole borrower reader). Flag it as a conformance
    violation — WARN during the v2->v3 transition, ERROR at layout_version >= 3."""
    root = ctx.project_root / "entities"
    if not root.is_dir():
        return
    for path in sorted(root.rglob("*.md")):
        if "templates" in path.relative_to(ctx.project_root).parts:
            continue
        text = ctx.read_text_cached(path)
        if not text.startswith("---\n"):
            continue  # no frontmatter -> cannot declare overlay_of
        try:
            data = ctx.frontmatter(path)
        except yaml.YAMLError:
            continue  # invalid YAML is reported by check_entity_frontmatter_completeness
        if "overlay_of" in data:
            yield _result(
                _severity(ctx),
                _rel(ctx, path),
                f"{path.name}: overlay_of in owner root entities/ "
                "(overlays belong under doc/<type>/; entities/ holds owner declarations only)",
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_entity_conformance.py -q`
Expected: PASS (all prior conformance tests + the 5 new behavior tests).

- [ ] **Step 5: ruff + Commit**

Run `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/validate/checks/entity_conformance.py tests/validate/test_checks_entity_conformance.py && uv run --frozen ruff format --check src/science_tool/validate/checks/entity_conformance.py tests/validate/test_checks_entity_conformance.py` (fix with `ruff format` if needed), then:

```bash
cd ~/d/science && git add science/src/science_tool/validate/checks/entity_conformance.py science/tests/validate/test_checks_entity_conformance.py
git commit -m "feat(substrate): conformance check — overlay_of in owner root entities/"
```
Do NOT include any "Co-Authored-By" trailer.

---

## Task 2: Registration test (the check is reachable through the canonical loader)

Proves the check reaches `CANONICAL_CHECKS` via the real loader (`_load_canonical_checks()`, which imports every module named in `CANONICAL_CHECK_MODULES`) — not merely via a manual import. The test snapshots and restores the process-global `CANONICAL_CHECKS` in a `finally` block (the snapshot/restore idiom in `tests/validate/test_checks_tasks.py:198-212`), because `runner.run()` reads `CANONICAL_CHECKS` directly (`runner.py:157`), so leaving it mutated would silently strip checks from later in-process tests. It also restores the original `sys.modules["science_tool.validate.checks.entity_conformance"]` entry, because the wiring proof temporarily removes that cached module to force a loader import.

**Files:**
- Test: `tests/validate/test_checks_entity_conformance.py` (append)

- [ ] **Step 1: Write the test**

Append to `tests/validate/test_checks_entity_conformance.py`:

```python
def test_overlay_of_check_registered_via_canonical_loader() -> None:
    import sys

    from science_tool.validate.checks import (
        CANONICAL_CHECKS,
        _load_canonical_checks,
        clear_checks_for_tests,
    )

    original_entries = list(CANONICAL_CHECKS)  # snapshot process-global registry
    module_name = "science_tool.validate.checks.entity_conformance"
    original_module = sys.modules.get(module_name)
    try:
        clear_checks_for_tests()
        # Drop the cached module so _load_canonical_checks() must re-import it
        # from the CANONICAL_CHECK_MODULES tuple. If entity_conformance were ever
        # dropped from that tuple, the module's @Check decorators would not re-run
        # and this assertion would fail — that is what makes this a true wiring test.
        sys.modules.pop(module_name, None)
        _load_canonical_checks()
        entries = [e for e in CANONICAL_CHECKS if e.fn.__name__ == "check_overlay_of_in_owner_root"]
        assert len(entries) == 1
        assert entries[0].order == 42
    finally:
        CANONICAL_CHECKS[:] = original_entries  # restore for later in-process tests
        if original_module is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = original_module
```

> Why this proves wiring: `import_module` returns the *cached* module without
> re-running its decorators, so popping `entity_conformance` from `sys.modules`
> first forces `_load_canonical_checks()` to genuinely re-import it through the
> `CANONICAL_CHECK_MODULES` tuple. The decorators re-run only for that re-imported
> module, so after the call `CANONICAL_CHECKS` holds exactly `entity_conformance`'s
> checks — and the assertion confirms our check is among them at `order=42`. The
> `finally` restores the full original registry and original module-cache entry,
> so no sibling test runs with a stripped registry or a swapped module object.

- [ ] **Step 2: Confirm the assertion is meaningful (red), then green**

Since Task 1 already ships the check, observe red by temporarily changing `42` to `999` in the assertion and running the test (expect `assert 42 == 999` FAIL); then revert to `42`.

Run: `cd ~/d/science/science && uv run --frozen pytest "tests/validate/test_checks_entity_conformance.py::test_overlay_of_check_registered_via_canonical_loader" -q`
Expected (with `42`): PASS.

- [ ] **Step 3: Confirm no registry pollution across the suite**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/ -q`
Expected: all PASS. The `finally` restore keeps the global registry intact, so sibling tests that rely on the full `CANONICAL_CHECKS` (e.g. `runner.run()` paths) are unaffected. If anything fails *only when run together*, the restore is not executing — fix the `try/finally` rather than relocating the test.

- [ ] **Step 4: ruff + Commit**

Run `cd ~/d/science/science && uv run --frozen ruff check tests/validate/test_checks_entity_conformance.py && uv run --frozen ruff format --check tests/validate/test_checks_entity_conformance.py` (fix if needed), then:

```bash
cd ~/d/science && git add science/tests/validate/
git commit -m "test(substrate): overlay_of owner-root check reachable via canonical loader"
```
No "Co-Authored-By" trailer.

---

## Task 3: Full-suite green + ruff

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `cd ~/d/science/science && uv run --frozen pytest -q`
Expected: all PASS. The only new behavior is an additive validation check that fires only on `overlay_of` under `entities/` (zero such files exist today), so no existing test should change. If a fixture project happens to validate at `layout_version >= 3` AND has an `overlay_of` file under `entities/`, that is a real latent violation the check correctly surfaces — fix the fixture (move the overlay under `doc/`) rather than weakening the check, and report it.

- [ ] **Step 2: Lint/format (changed files)**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/validate/checks/entity_conformance.py tests/validate/test_checks_entity_conformance.py && uv run --frozen ruff format --check src/science_tool/validate/checks/entity_conformance.py tests/validate/test_checks_entity_conformance.py`
Expected: clean. (The repo as a whole carries pre-existing ruff debt unrelated to this change — do NOT attempt a repo-wide reformat; only the files this plan touches must be clean.)

- [ ] **Step 3: Commit any lint fixes**

Only if Step 2 required changes:
```bash
cd ~/d/science && git add science/src/science_tool/validate/checks/entity_conformance.py science/tests/validate/test_checks_entity_conformance.py
git commit -m "chore(substrate): ruff clean for overlay_of owner-root check"
```

---

## Self-Review

**1. Spec coverage (this plan's scope only):**
- §B2 "an `overlay_of` file under an owner root (`entities/`) is a conformance error" → Task 1 check. ✓ (the headline rule, fully covered)
- §C3 `MarkdownAdapter` owner-only → enforced **for the `entities/` owner root only**: a borrow declaration can no longer hide there and be minted as a spurious owner. NOT covered: MarkdownAdapter's transitional `doc/datasets`, `doc/workflows`, `doc/workflow-runs` scan roots (`sources.py:254`) — deferred to 1.5/§B4. Partial-by-design. ◐
- §C3 `OverlayAdapter` sole borrower reader → `OverlayAdapter` (`commons/overlay.py:71`) is already the sole *class* parsing overlays; this check does not change that, nor does it collapse its four call sites. It only keeps the `entities/` owner root clear of overlays. Pre-existing property, reinforced — not newly established here. ◐
- Transition discipline: reuses `_severity(ctx)` so the rule is WARN pre-v3 and ERROR at the substrate target, matching sibling checks. ✓
- Explicitly deferred (named in Scope): scoped-ref resolution (1.3), migrator rerouting (1.4), dataset `doc/datasets/` dual-SSOT + orphan datapackages (1.5/§B4), identity-table "two readers"/"owns-and-borrows" audit rows (omitted — unreachable under the current commons-only overlay loader, so they would be dead code). ✓

**2. Placeholder scan:** No TBD/TODO. Every code step shows complete code; every test step shows assertions and exact commands. Task 2 Step 2 explains how to confirm the registration assertion is meaningful given Task 1 already ships the check (flip `42`→`999` to see red, then revert). ✓

**3. Type/name consistency:** `check_overlay_of_in_owner_root` is spelled identically in the implementation, the import, the behavior tests, and the registration test. It reuses the real helpers `_result`, `_severity`, `_rel` and the `yaml`/`Iterator`/`Result`/`Check`/`ValidateContext`/`Severity` names already imported in `entity_conformance.py`. `order=42` is consistent between the decorator and the registration assertion, and verified free. ✓

---

## Where this sits (Phase 1 roadmap — NOT part of this plan)

Phase 1.1 (merged, `e2b3a757`) built the compiled `IdentityTable` and non-strict reporting. **This is Phase 1.2**: the owner-root conformance guard, the first of the adapter-enforcement facets, implemented as one additive validation check with zero current blast radius. Remaining Phase-1 sub-plans (each its own full plan):

- **1.3 — Scoped-ref resolution (§B3a):** `ambiguous_reference` error + scoped form (`commons:topic:x`); bare-ref search chain that never shadows owner ambiguity. Depends on 1.1.
- **1.4 — Migrator on the compiled model (§C4):** replace the alias-collision proxy + in-memory simulation/masking with `build_identity_table`-based detection (load `strict_identity=False`, block apply on any `identity_collision`); renumber only non-transitional project owners. Retires the masking hack. Depends on 1.1–1.3.
- **1.5 — Migrate orphan datapackages (§B4):** migrate a datapackage with no entity-file owner to a real owner file; the `doc/datasets/` dual-SSOT handling deliberately untouched here. Depends on 1.1.

Phases 2–4 (dataset reconciliation, `entities.yaml` retirement, external-reference resolver) follow Phase 1 and are out of scope here.
