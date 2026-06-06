# v2→v3 Migration Robustness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `science entities migrate` (v2→v3) and entity conformance robust to the real-world conventions of all 19 registered Science projects, so every audited project except seq-feats migrates cleanly with zero project-side edits, and the two hard-crashes (natural-systems, protein-landscape) are eliminated.

**Architecture:** Seven localized seams in the migrator/conformance layer. The keystone (Unit A) replaces the position-blind "any non-conforming token blocks `--apply`" rule with **graph-audit-equivalent validation over a simulated post-move `ProjectSources`**: inject the planned moves + id-rewrites as markdown overrides (so moved entities are discovered at their new `entities/` paths) and augment `manual_aliases` with the plan's `id_map` (so disk-resident non-markdown sources resolve old→new), then run the existing `audit_project_sources` and block only on its `fail` rows. Prose-body leftovers from `rewrite_references` become non-blocking warnings. The other units (graceful manifest loading, date-key fallback, exact-root discovery, mappings handling, date-scoped aliases, placeholder guard) each collapse one false-positive class.

**Tech Stack:** Python 3.12/3.13, pydantic v2, pytest. Code lives in `~/d/science/science/src/science_tool/`; tests in `~/d/science/science/tests/`. Branch: `feat/migration-robustness` in the `~/d/science` repo.

**Design spec:** `~/d/science/docs/plans/2026-06-06-migration-robustness-design.md`
**Readiness audit:** `~/d/science/docs/audits/2026-06-06-layout-v3-migration-readiness-audit.md`

**Shell convention:** all commands below are run through the `rtk` token-proxy per repo convention (`rtk uv …`, `rtk git …`, `rtk rg …`). The Claude Code hook auto-rewrites bare commands transparently, but the snippets show `rtk` explicitly so workers without the hook stay compliant.

**Test command (run from the library subdir):**
```bash
cd ~/d/science/science && rtk uv run --frozen pytest <path>::<test> -v
```

**Task order matches the design's remediation order:** B (unblock crashes) → D (clears most "undated") → A (keystone) → C/E/F/G → companions → integration.

---

## Task 1: Unit B — Graceful local-kind loading (G7)

A malformed/vestigial local entity kind must be skipped with a warning instead of aborting the whole migration. `load_local_entity_policies` keeps its exact dict signature and caching (callers untouched); only the failure mode changes from raise → skip+warn. A new `local_kind_warnings` exposes the `(kind, reason)` pairs, and a new conformance check surfaces them.

**Files:**
- Modify: `science/src/science_tool/entities.py:112-155` (refactor `load_local_entity_policies`)
- Modify: `science/tests/test_entities_local_policies.py` (rewrite 4 "must raise" tests to skip+warn; add `local_kind_warnings` coverage)
- Modify: `science/src/science_tool/validate/checks/entity_conformance.py` (new surfacing check)
- Test: `science/tests/test_entities_local_policies.py`, `science/tests/test_entity_conformance.py` (or wherever conformance checks are tested — see Step 9)

- [ ] **Step 1: Rewrite the four "must raise" tests to assert skip+warn**

In `science/tests/test_entities_local_policies.py`, add `local_kind_warnings` to the import from `science_tool.entities` (line 8-17 block). Then replace the four tests (`test_name_must_equal_canonical_prefix`, `test_home_override_must_be_relative_under_entities`, `test_home_override_may_not_collide_with_core_directory`, `test_strategy_override_must_be_known`) with skip+warn versions:

```python
def test_name_not_equal_canonical_prefix_is_skipped_with_warning(tmp_path: Path) -> None:
    manifest = _LOCAL_MANIFEST.replace("canonical_prefix: design", "canonical_prefix: dsgn")
    _write(tmp_path, "science.yaml", "name: t\nknowledge_profiles:\n  local: local\n")
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", manifest)
    policies = load_local_entity_policies(tmp_path)
    assert "design" not in policies  # malformed kind dropped, not crashed
    assert "gadget" in policies  # the valid sibling kind still loads
    warned = {kind for kind, _ in local_kind_warnings(tmp_path)}
    assert "design" in warned


@pytest.mark.parametrize(
    "bad_home",
    ["/abs/entities/design", "../outside/design", "doc/design", "entities/../escape", "entities"],
)
def test_home_override_invalid_is_skipped_with_warning(tmp_path: Path, bad_home: str) -> None:
    manifest = _LOCAL_MANIFEST.replace("    home: entities/gizmos\n", f"    home: {bad_home}\n")
    _write(tmp_path, "science.yaml", "name: t\nknowledge_profiles:\n  local: local\n")
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", manifest)
    policies = load_local_entity_policies(tmp_path)
    assert "gadget" not in policies  # the kind with the bad home is dropped
    assert "design" in policies  # the valid sibling kind still loads
    assert "gadget" in {kind for kind, _ in local_kind_warnings(tmp_path)}


def test_home_override_core_collision_is_skipped_with_warning(tmp_path: Path) -> None:
    manifest = _LOCAL_MANIFEST.replace("    home: entities/gizmos\n", "    home: entities/hypotheses\n")
    _write(tmp_path, "science.yaml", "name: t\nknowledge_profiles:\n  local: local\n")
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", manifest)
    policies = load_local_entity_policies(tmp_path)
    assert "gadget" not in policies
    assert "gadget" in {kind for kind, _ in local_kind_warnings(tmp_path)}


@pytest.mark.parametrize("bad_strategy", ["banana", "singleton"])
def test_strategy_override_unknown_is_skipped_with_warning(tmp_path: Path, bad_strategy: str) -> None:
    manifest = _LOCAL_MANIFEST.replace(
        "    home: entities/gizmos\n", f"    home: entities/gizmos\n    strategy: {bad_strategy}\n"
    )
    _write(tmp_path, "science.yaml", "name: t\nknowledge_profiles:\n  local: local\n")
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", manifest)
    policies = load_local_entity_policies(tmp_path)
    assert "gadget" not in policies
    assert "gadget" in {kind for kind, _ in local_kind_warnings(tmp_path)}
```

Also add a clean-path assertion that a valid manifest yields no warnings:

```python
def test_valid_manifest_has_no_local_kind_warnings(tmp_path: Path) -> None:
    root = _project_with_local_kinds(tmp_path)
    assert local_kind_warnings(root) == []
```

Remove the now-obsolete `test_name_must_equal_canonical_prefix`, `test_home_override_must_be_relative_under_entities`, `test_home_override_may_not_collide_with_core_directory`, `test_strategy_override_must_be_known`. Keep `test_local_kind_may_not_shadow_core` (shadowing a core kind is a silent skip, not a warning — unchanged behavior).

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `cd ~/d/science/science && rtk uv run --frozen pytest tests/test_entities_local_policies.py -v`
Expected: FAIL — `ImportError: cannot import name 'local_kind_warnings'` (it does not exist yet).

- [ ] **Step 3: Refactor `load_local_entity_policies` into a skip+warn core**

In `science/src/science_tool/entities.py`, replace the body of `load_local_entity_policies` (lines 112-155) with a shared core plus two thin public accessors. The validation predicates are byte-for-byte the same; only `raise` becomes `warnings.append(...); continue`:

```python
def _load_local_policies_and_warnings(
    project_root: Path,
) -> tuple[dict[str, EntityPathPolicy], list[tuple[str, str]]]:
    """Load local markdown-kind policies, skipping (not raising on) malformed
    kinds. Returns (policies, warnings) where warnings is a list of
    (kind_name, reason) for every kind dropped during validation. Cached on the
    manifest mtime exactly as the prior single-dict implementation was."""
    profile_name = resolve_local_profile_name(project_root)
    manifest_path = local_profile_sources_dir(project_root, local_profile=profile_name) / "manifest.yaml"
    if not manifest_path.is_file():
        return {}, []
    cache_key = (str(manifest_path), manifest_path.stat().st_mtime_ns)
    cached = _LOCAL_POLICY_CACHE.get(cache_key)
    if cached is not None:
        return cached
    manifest = load_profile_manifest(manifest_path)
    policies: dict[str, EntityPathPolicy] = {}
    warnings: list[tuple[str, str]] = []
    if manifest is not None:
        for ek in manifest.entity_kinds:
            if ek.name != ek.canonical_prefix:
                warnings.append(
                    (ek.name, f"canonical_prefix {ek.canonical_prefix!r} != name {ek.name!r}; skipped")
                )
                continue
            if ek.name in _BUILTIN_MARKDOWN_POLICIES:
                continue  # a local kind may not shadow a core kind (silent, core wins)
            if ek.strategy is not None and ek.strategy not in _VALID_STRATEGIES:
                warnings.append(
                    (ek.name, f"strategy {ek.strategy!r} not one of {sorted(_VALID_STRATEGIES)}; skipped")
                )
                continue
            try:
                root = _resolve_local_home(ek.name, ek.home)
            except EntityCommandError as exc:
                warnings.append((ek.name, f"{exc}; skipped"))
                continue
            if root.name in _CORE_HOME_DIR_NAMES:
                warnings.append(
                    (ek.name, f"home {root!r} collides with core entity directory {root.name!r}; skipped")
                )
                continue
            strategy = cast(EntityFilenameStrategy, ek.strategy or "numeric")
            policies[ek.name] = EntityPathPolicy(root, strategy)
    result = (policies, warnings)
    _LOCAL_POLICY_CACHE[cache_key] = result
    return result


def load_local_entity_policies(project_root: Path) -> dict[str, EntityPathPolicy]:
    """Path policies for the project's registered local markdown kinds.

    Malformed kinds (bad canonical_prefix/home/strategy, or a home colliding with
    a core directory) are skipped; see `local_kind_warnings` for the reasons. This
    preserves the dict signature every caller relies on (notably `entity_policies`,
    which splats `{**load_local_entity_policies(...), **builtins}`)."""
    return _load_local_policies_and_warnings(project_root)[0]


def local_kind_warnings(project_root: Path) -> list[tuple[str, str]]:
    """The (kind_name, reason) pairs for local kinds skipped during policy load."""
    return _load_local_policies_and_warnings(project_root)[1]
```

The `_LOCAL_POLICY_CACHE` now stores a `tuple[dict, list]` instead of a bare dict. Update its type annotation if one is declared at the top of the module (search for `_LOCAL_POLICY_CACHE`); the cache is keyed and read only through `_load_local_policies_and_warnings`, so no other call site changes.

- [ ] **Step 4: Run the policy tests to verify they pass**

Run: `cd ~/d/science/science && rtk uv run --frozen pytest tests/test_entities_local_policies.py -v`
Expected: PASS (all skip+warn tests + the existing unchanged tests).

- [ ] **Step 5: Verify no regression in dependent callers**

Run: `cd ~/d/science/science && rtk uv run --frozen pytest tests/test_entity_layout_migration.py -v`
Expected: PASS (the migrator imports `load_local_entity_policies`; its dict contract is unchanged).

- [ ] **Step 6: Commit**

```bash
cd ~/d/science && rtk git add science/src/science_tool/entities.py science/tests/test_entities_local_policies.py
rtk git commit -m "feat(migrate): skip+warn on malformed local entity kinds (Unit B, G7)"
```

- [ ] **Step 7: Write the failing conformance-surfacing test**

First locate the conformance test module:
```bash
cd ~/d/science/science && rtk rg -l "check_entity_location_coherence|entity_conformance" tests/
```
Add to that module (call it `tests/test_entity_conformance.py` below — use the real path the `rtk rg` command returns):

```python
def test_local_kind_warning_is_surfaced_as_validate_warning(tmp_path: Path) -> None:
    # A manifest with one malformed local kind must produce a WARN result from the
    # conformance layer, not crash validation.
    manifest = (
        "name: t-local\nimports: [core]\nstrictness: typed-extension\n"
        "entity_kinds:\n"
        "  - name: gadget\n    canonical_prefix: WRONG\n    layer: layer/local\n    description: x\n"
        "relation_kinds: []\n"
    )
    (tmp_path / "science.yaml").write_text("name: t\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    p = tmp_path / "knowledge/sources/local/manifest.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(manifest, encoding="utf-8")

    from science_tool.validate.checks.entity_conformance import check_local_kind_manifest
    ctx = _make_ctx(tmp_path)  # use the module's existing ValidateContext fixture/factory
    results = list(check_local_kind_manifest(ctx))
    assert any("gadget" in r.message for r in results)
    assert all(r.severity is Severity.WARN for r in results)
```

If the test module has no `_make_ctx`/`ValidateContext` factory, follow the construction pattern used by the existing conformance tests in that file (they already build a `ValidateContext` for `check_entity_location_coherence`). Reuse it verbatim.

- [ ] **Step 8: Run it to verify it fails**

Run: `cd ~/d/science/science && rtk uv run --frozen pytest tests/test_entity_conformance.py::test_local_kind_warning_is_surfaced_as_validate_warning -v`
Expected: FAIL — `ImportError`/`AttributeError`: `check_local_kind_manifest` does not exist.

- [ ] **Step 9: Add the surfacing check**

In `science/src/science_tool/validate/checks/entity_conformance.py`, add `local_kind_warnings` to the existing `from science_tool.entities import ...` line, then add a new check near the other `@Check` definitions (use `order=36`, just before `check_entity_location_coherence` at order 37):

```python
@Check(section="local entity kind manifest...", order=36)
def check_local_kind_manifest(ctx: ValidateContext) -> Iterator[Result]:
    """Surface local entity kinds skipped during policy loading (bad
    canonical_prefix/home/strategy, or home colliding with a core directory) as
    warnings, so a vestigial kind is visible without aborting validation."""
    for kind, reason in local_kind_warnings(ctx.project_root):
        yield _result(Severity.WARN, None, f"local kind {kind!r} skipped during load: {reason}")
```

`_result`, `Severity`, `Check`, `Iterator`, `ValidateContext`, and `Result` are already imported in this module.

- [ ] **Step 10: Run the conformance test to verify it passes**

Run: `cd ~/d/science/science && rtk uv run --frozen pytest tests/test_entity_conformance.py -v`
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
cd ~/d/science && rtk git add science/src/science_tool/validate/checks/entity_conformance.py science/tests/test_entity_conformance.py
rtk git commit -m "feat(validate): surface skipped local kinds as warnings (Unit B)"
```

---

## Task 2: Unit D — Date-fallback extension (G9)

Recognize author-supplied dates stored under `generated_at:` (big-picture synthesis output) and `committed:` (pre-registrations), normalizing each to a real `YYYY-MM-DD` date before use. The `_UNDATED_SENTINEL` still blocks (a truly date-less file remains a blocker — decision 3).

**Files:**
- Modify: `science/src/science_tool/entity_layout_migration.py:144-164` (`_fallback_created` + a new `_leading_date` helper)
- Test: `science/tests/test_entity_layout_migration.py`

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_entity_layout_migration.py` (import `_fallback_created` and `LegacyEntity` from `science_tool.entity_layout_migration` — extend the existing import block):

```python
def _legacy(rel_path: str, frontmatter: dict) -> "LegacyEntity":
    from science_tool.entity_layout_migration import LegacyEntity
    return LegacyEntity(rel_path=rel_path, kind="report", old_id=None, frontmatter=frontmatter, body="")


def test_fallback_created_reads_generated_at_timestamp() -> None:
    # big-picture synthesis files carry an ISO timestamp under generated_at:.
    e = _legacy("doc/reports/synthesis.md", {"generated_at": "2026-04-28T12:00:00Z"})
    assert _fallback_created(e) == "2026-04-28"


def test_fallback_created_reads_committed_date() -> None:
    e = _legacy("doc/pre-registrations/foo.md", {"committed": "2026-03-15"})
    assert _fallback_created(e) == "2026-03-15"


def test_fallback_created_prefers_created_over_other_keys() -> None:
    e = _legacy("doc/reports/x.md", {"created": "2026-01-01", "generated_at": "2026-04-28T00:00:00Z"})
    assert _fallback_created(e) == "2026-01-01"


def test_fallback_created_unparseable_date_key_falls_through_to_sentinel() -> None:
    from science_tool.entity_layout_migration import _UNDATED_SENTINEL
    e = _legacy("doc/reports/x.md", {"generated_at": "not-a-date"})
    assert _fallback_created(e) == _UNDATED_SENTINEL


def test_fallback_created_filename_prefix_still_wins_over_nothing() -> None:
    e = _legacy("doc/reports/2026-05-30-triage.md", {})
    assert _fallback_created(e) == "2026-05-30"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd ~/d/science/science && rtk uv run --frozen pytest tests/test_entity_layout_migration.py -k fallback_created -v`
Expected: FAIL — `generated_at`/`committed` are ignored today, so those return the sentinel.

- [ ] **Step 3: Add `_leading_date` and extend the fallback chain**

In `science/src/science_tool/entity_layout_migration.py`, add `import datetime` to the imports (top of file, after `import re`). Add a helper near `_DATE_PREFIX_DATE_RE` (line 150):

```python
_LEADING_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def _leading_date(value: object) -> str | None:
    """Extract and validate a leading YYYY-MM-DD from a date or ISO-timestamp.

    `created:` is modeled as a date, but `generated_at:` is an ISO *timestamp*
    (2026-04-28T12:00:00Z). Take the leading date component and confirm it is a
    real calendar date; return None (fall through) when there is none."""
    if not value:
        return None
    m = _LEADING_DATE_RE.match(str(value))
    if m is None:
        return None
    try:
        datetime.date.fromisoformat(m.group(1))
    except ValueError:
        return None
    return m.group(1)
```

Replace the body of `_fallback_created` (lines 153-164) with the extended chain:

```python
def _fallback_created(entity: "LegacyEntity") -> str:
    """created fallback: frontmatter created -> generated_at -> committed ->
    filename YYYY-MM-DD prefix -> sentinel. Each frontmatter source is normalized
    to a real date via `_leading_date`; a value with no parseable leading date is
    skipped rather than copied raw.

    (synthesize_frontmatter still prefers a body **Date:** header over this fallback.)
    """
    for key in ("created", "generated_at", "committed"):
        candidate = _leading_date(entity.frontmatter.get(key))
        if candidate:
            return candidate
    m = _DATE_PREFIX_DATE_RE.match(Path(entity.rel_path).stem)
    if m:
        return m.group(1)
    return _UNDATED_SENTINEL
```

- [ ] **Step 4: Run the fallback tests to verify they pass**

Run: `cd ~/d/science/science && rtk uv run --frozen pytest tests/test_entity_layout_migration.py -k fallback_created -v`
Expected: PASS.

- [ ] **Step 5: Run the full migration test module (regression)**

Run: `cd ~/d/science/science && rtk uv run --frozen pytest tests/test_entity_layout_migration.py -v`
Expected: PASS (the undated-blocking test still blocks a genuinely date-less file).

- [ ] **Step 6: Commit**

```bash
cd ~/d/science && rtk git add science/src/science_tool/entity_layout_migration.py science/tests/test_entity_layout_migration.py
rtk git commit -m "feat(migrate): read generated_at/committed date keys for created fallback (Unit D, G9)"
```

---

## Task 3: Unit A — Position-aware blocking via simulated post-move audit (G1–G6)

The keystone. `--apply` blocking is decided by running the existing `audit_project_sources` over a **simulated post-move `ProjectSources`** (built in-memory, no disk mutation), not by treating every non-conforming `rewrite_references` token as a blocker. Prose-body leftovers become non-blocking `unresolved_warnings`.

**Files:**
- Modify: `science/src/science_tool/entity_layout_migration.py` (new `_strip_code_spans`, `_is_placeholder_token` stub, `_simulated_postmove_audit_failures`, `_audit_failures_to_report`; rewrite the blocking/warning section of `migrate_layout`, lines 666-696)
- Modify: `science/tests/test_entity_layout_migration.py` (new Unit A tests; update `test_migrate_version_not_bumped_when_audit_fails` to expect pre-mutation blocking)
- Test: `science/tests/test_entity_layout_migration.py`

> **Helper for fixtures:** the existing module already defines `_write` and a `_git_init` helper (used by `test_migrate_undated_entity_blocks_apply_and_is_reported`). Reuse both. Minimal loadable fixtures use `science.yaml` containing `name: t\nlayout_version: 2\n` — `load_project_sources` tolerates a missing `knowledge_profiles` block on these (proven by the existing apply-path tests). When a fixture needs local kinds, add `knowledge_profiles:\n  local: local\n` plus `knowledge/sources/local/manifest.yaml`.

- [ ] **Step 1: Write the failing warning-vs-block tests**

Add to `science/tests/test_entity_layout_migration.py`. These assert the new report keys (`unresolved_warnings` non-blocking; `unresolved_references` blocking) and the pre-mutation blocking of structural dangling refs:

```python
def test_code_fenced_and_inline_example_ids_warn_not_block(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\n")
    _write(
        tmp_path, "specs/hypotheses/h01-a.md",
        '---\nid: "hypothesis:h01-a"\ntype: hypothesis\ncreated: "2026-01-01"\n'
        'title: A\nstatus: proposed\nupdated: "2026-01-01"\n---\n'
        "See `hypothesis:hNN` and:\n```markdown\nhypothesis:disease-label-misalignment\n```\n",
    )
    _git_init(tmp_path)
    dry = migrate_layout(tmp_path, apply=False)
    # Code-fence / inline-code example ids do not appear in either bucket.
    flat_warn = [t for toks in dry["unresolved_warnings"].values() for t in toks]
    assert "hypothesis:disease-label-misalignment" not in flat_warn
    assert "hypothesis:hNN" not in flat_warn
    assert dry["unresolved_references"] == {}  # nothing structural dangling
    # apply must succeed (clean project, only example ids in prose).
    migrate_layout(tmp_path, apply=True)
    assert (tmp_path / "entities/hypotheses/0001-a.md").exists()


def test_cross_project_prose_pointer_warns_not_blocks(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\n")
    _write(
        tmp_path, "specs/hypotheses/h01-a.md",
        '---\nid: "hypothesis:h01-a"\ntype: hypothesis\ncreated: "2026-01-01"\n'
        'title: A\nstatus: proposed\nupdated: "2026-01-01"\n---\n'
        "Builds on hypothesis:h00-working-model from the parent project.\n",
    )
    _git_init(tmp_path)
    dry = migrate_layout(tmp_path, apply=False)
    flat_warn = [t for toks in dry["unresolved_warnings"].values() for t in toks]
    assert "hypothesis:h00-working-model" in flat_warn  # reported...
    assert dry["unresolved_references"] == {}  # ...but not blocking
    migrate_layout(tmp_path, apply=True)  # does not raise


def test_wikilink_to_existing_paper_warns_not_blocks(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\n")
    _write(tmp_path, "doc/background/papers/Adams2025.md",
           '---\nid: "paper:Adams2025"\ntype: paper\ncreated: "2026-01-01"\n'
           'title: Adams\nstatus: active\nupdated: "2026-01-01"\n---\nbody\n')
    _write(tmp_path, "doc/reports/2026-01-02-note.md",
           '---\nid: "report:2026-01-02-note"\ntype: report\ncreated: "2026-01-02"\n'
           'title: Note\nstatus: active\nupdated: "2026-01-02"\n---\nSee [[Adams2025]].\n')
    _git_init(tmp_path)
    dry = migrate_layout(tmp_path, apply=False)
    flat_warn = [t for toks in dry["unresolved_warnings"].values() for t in toks]
    assert "[[Adams2025]]" in flat_warn
    assert dry["unresolved_references"] == {}


def test_dangling_structural_related_ref_blocks_pre_mutation(tmp_path: Path) -> None:
    # A conformant-but-dangling ref in a `related:` list (the case rewrite_references
    # leftovers cannot see) must block --apply BEFORE any git mv.
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\n")
    _write(tmp_path, "specs/hypotheses/h01-alpha.md",
           '---\nid: "hypothesis:h01-alpha"\ntype: hypothesis\ncreated: "2026-01-01"\n'
           'title: Alpha\nstatus: proposed\nupdated: "2026-01-01"\n---\nbody\n')
    _write(tmp_path, "doc/questions/q01-myq.md",
           '---\nid: "question:q01-myq"\ntype: question\ncreated: "2026-01-02"\n'
           'title: My Q\nstatus: active\nupdated: "2026-01-02"\n'
           'related: ["hypothesis:9999-nope"]\n---\nBody.\n')
    _git_init(tmp_path)
    dry = migrate_layout(tmp_path, apply=False)
    assert dry["unresolved_references"]  # structural blocker present in dry-run
    with _pytest.raises(ValueError, match="structural"):
        migrate_layout(tmp_path, apply=True)
    assert not (tmp_path / "entities").exists()  # no mutation occurred
    assert (tmp_path / "doc/questions/q01-myq.md").exists()


def test_dangling_ref_in_non_related_audited_field_blocks(tmp_path: Path) -> None:
    # Proves the blocking surface tracks the WHOLE graph audit, not just `related:`.
    # A proposition `commits_to:` (audited) pointing at a dangling id must block.
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\n")
    _write(tmp_path, "specs/propositions/p01-claim.md",
           '---\nid: "proposition:p01-claim"\ntype: proposition\ncreated: "2026-01-01"\n'
           'title: Claim\nstatus: draft\nupdated: "2026-01-01"\n'
           'commits_to: ["hypothesis:9999-nope"]\n---\nbody\n')
    _git_init(tmp_path)
    dry = migrate_layout(tmp_path, apply=False)
    assert dry["unresolved_references"]
    with _pytest.raises(ValueError, match="structural"):
        migrate_layout(tmp_path, apply=True)


def test_accepted_external_and_bibliography_refs_do_not_block(tmp_path: Path) -> None:
    # cite:* in source_refs, external go:/path refs, and meta:* are accepted by the
    # graph audit without resolution — they must NOT block.
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\n")
    _write(tmp_path, "specs/hypotheses/h01-a.md",
           '---\nid: "hypothesis:h01-a"\ntype: hypothesis\ncreated: "2026-01-01"\n'
           'title: A\nstatus: proposed\nupdated: "2026-01-01"\n'
           'source_refs: ["cite:Adams2025"]\nrelated: ["meta:big-picture-2026"]\n'
           'evidence_refs: ["go:0008150", "./data/x.parquet"]\n---\nbody\n')
    _git_init(tmp_path)
    dry = migrate_layout(tmp_path, apply=False)
    assert dry["unresolved_references"] == {}
    migrate_layout(tmp_path, apply=True)  # does not raise
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd ~/d/science/science && rtk uv run --frozen pytest tests/test_entity_layout_migration.py -k "warn_not_block or warns_not or structural or audited_field or external_and_bibliography" -v`
Expected: FAIL — `KeyError: 'unresolved_warnings'` (key does not exist) and the structural-block tests raise the old "working tree" post-mutation error or do not block at all.

- [ ] **Step 3: Add the code-span stripper, placeholder-token stub, and the simulated-audit helpers**

In `science/src/science_tool/entity_layout_migration.py`, add near the reference-rewriting layer (after `_WIKILINK_RE`, ~line 527):

```python
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def _strip_code_spans(text: str) -> str:
    """Remove fenced code blocks and inline-code spans so example ids inside
    documentation do not generate reference warnings."""
    text = _FENCE_RE.sub("", text)
    return _INLINE_CODE_RE.sub("", text)


def _is_placeholder_token(token: str) -> bool:
    """Stub — Unit G replaces this with the real placeholder filter. Returns
    False so every prose token is kept as a warning until Unit G lands."""
    return False
```

Add the simulated-post-move audit helper after the orchestrator helpers (`_render`, ~line 603), before `migrate_layout`:

```python
def _simulated_postmove_audit_failures(
    project_root: Path,
    plan: MigrationPlan,
    rewritten: dict[str, str],
    singleton_text: dict[str, str],
    inplace_text: dict[str, str],
) -> list[dict]:
    """Graph-audit-equivalent validation over a simulated post-move source set.

    Reproduces the post-mutation backstop (migrate_layout step 4) BEFORE any disk
    mutation, with no disk writes:

    - markdown_overrides inject every post-move markdown file at its NEW path, so
      the MarkdownAdapter discovers moved entities under entities/<kind>/ (their
      legacy doc/specs homes are never scanned) carrying their rewritten, new-id
      content. (`MarkdownAdapter.discover` adds any `.md` rel-path in virtual_files
      even when absent from disk; `load_raw` reads the override content.)
    - manual_aliases is augmented with plan.id_map (old_id/stem/shortform ->
      new_id) so disk-resident sources the override channel cannot reach — tasks,
      datapackages, relations/bindings on disk — still resolve old ids to their
      new identity exactly as they would after the in-place rewrite on --apply.

    Returns the audit's `fail` rows. Inherits the audit's full field surface and
    its acceptance exceptions (cite:* in source_refs/evidence_refs, external
    URLs/paths/go:/mesh:/doi:, meta:*) with zero re-implementation.
    """
    from science_tool.graph.migrate import audit_project_sources
    from science_tool.graph.sources import load_project_sources

    merged = {**rewritten, **singleton_text, **inplace_text}
    overrides = {rel: text for rel, text in merged.items() if rel.endswith(".md")}
    sources = load_project_sources(project_root, markdown_overrides=overrides)
    sources = sources.model_copy(
        update={"manual_aliases": {**sources.manual_aliases, **plan.id_map}}
    )
    rows, failed = audit_project_sources(sources)
    return [r for r in rows if r.get("status") == "fail"] if failed else []


def _audit_failures_to_report(rows: list[dict]) -> dict[str, list[str]]:
    """Shape audit fail rows into {source -> sorted unique targets} for the
    report's `unresolved_references` (preserving its dict-of-lists contract)."""
    out: dict[str, list[str]] = {}
    for row in rows:
        out.setdefault(str(row.get("source", "?")), []).append(str(row.get("target", "?")))
    return {source: sorted(set(targets)) for source, targets in out.items()}
```

- [ ] **Step 4: Rewrite the blocking/warning section of `migrate_layout`**

Replace lines 666-696 (the `all_unresolved` loop, `report` dict, and the three pre-mutation guards) with the split model. Keep the full-text rewrite that produces the actual `--apply` output; compute warnings from a code-stripped pass; compute blocking from the simulated audit:

```python
    # Full-text rewrite (produces the content --apply will write) + a separate
    # code-stripped pass that feeds the non-blocking prose-warning bucket.
    unresolved_warnings: dict[str, list[str]] = {}
    for bucket in (rewritten, singleton_text, inplace_text):
        for rel, text in list(bucket.items()):
            out, _ = rewrite_references(
                text, plan.id_map, policed_kinds=policed_kinds, project_root=project_root
            )
            bucket[rel] = out
            _, warn_tokens = rewrite_references(
                _strip_code_spans(text), plan.id_map, policed_kinds=policed_kinds, project_root=project_root
            )
            warn_tokens = [t for t in warn_tokens if not _is_placeholder_token(t)]
            if warn_tokens:
                unresolved_warnings[rel] = warn_tokens

    # Blocking is graph-audit-equivalent validation over the simulated post-move
    # source set — the SAME check the post-mutation backstop runs, moved earlier.
    structural_failures = _simulated_postmove_audit_failures(
        project_root, plan, rewritten, singleton_text, inplace_text
    )

    report = {
        "moves": [vars(m) for m in plan.moves],
        "singletons": [vars(s) for s in plan.singletons],
        "id_map": plan.id_map,
        "collisions": plan.collisions,
        "unresolved_references": _audit_failures_to_report(structural_failures),
        "unresolved_warnings": unresolved_warnings,
        "local_kind_warnings": local_kind_warnings(project_root),
        "undated_entities": undated_entities,
        "applied": apply,
    }

    if not apply:
        return report

    # Pre-mutation guards — raise cleanly with no tree modification.
    if plan.collisions:
        raise ValueError(f"collisions block --apply: {plan.collisions}")
    if structural_failures:
        raise ValueError(
            f"unresolved structural references block --apply "
            f"(simulated post-move graph audit): {structural_failures[:10]}"
        )
    if undated_entities:
        raise ValueError(
            f"undated entities block --apply (add a **Date:** header or frontmatter "
            f"created: to each, then re-run): {undated_entities}"
        )
```

Add `local_kind_warnings` to the existing `from science_tool.entities import (...)` block at the top of the file (lines 16-28).

> **Note:** the post-mutation audit at lines 698-722 is unchanged — it remains the backstop. Because the pre-mutation guard now runs the identical audit on the simulated tree, the post-mutation audit should never fire on a project that passed the dry-run; it stays as a defense-in-depth check.

- [ ] **Step 5: Update the now-superseded post-mutation test**

`test_migrate_version_not_bumped_when_audit_fails` (around line 418) asserts the dangling `hypothesis:9999-nope` is caught *post*-mutation (`match="working tree"`). Under Unit A it is caught *pre*-mutation. Update its tail to:

```python
    with _pytest.raises(ValueError, match="structural"):
        migrate_layout(tmp_path, apply=True)

    # Caught pre-mutation: no files moved, version untouched.
    assert (tmp_path / "specs/hypotheses/h01-alpha.md").exists()
    assert not (tmp_path / "entities").exists()
    manifest = yaml.safe_load((tmp_path / "science.yaml").read_text())
    assert manifest.get("layout_version") == 2
```

Also scan the rest of the module for any test asserting on `unresolved_references` containing prose tokens (e.g. the wikilink/shortform tests around lines 360-384) — those tokens now live in `unresolved_warnings`. Update each such assertion to read from `unresolved_warnings` where the token is a prose/body reference, and keep `unresolved_references` assertions only for genuinely structural dangling refs. Run the module first (next step) to enumerate exactly which break.

- [ ] **Step 6: Run the Unit A tests + full module**

Run: `cd ~/d/science/science && rtk uv run --frozen pytest tests/test_entity_layout_migration.py -v`
Expected: PASS. If any pre-existing test fails because a prose token moved from `unresolved_references` to `unresolved_warnings`, update that assertion per Step 5 (the migration behavior is correct; the test's expectation was the position-blind one).

- [ ] **Step 7: Commit**

```bash
cd ~/d/science && rtk git add science/src/science_tool/entity_layout_migration.py science/tests/test_entity_layout_migration.py
rtk git commit -m "feat(migrate): block on simulated post-move audit; prose refs warn (Unit A, G1-G6)"
```

---

## Task 4: Unit C — Entity-discovery tightening + entity-signal gate (G8)

Stop sweeping frontmatter-less files under nested non-root dirs into the entity set, and stop treating direct-child prose docs at a real root (no `id:`) as entities. Discovery by explicit `type:`/`kind:`/known-id-prefix is unchanged; only the directory-name fallback is tightened to exact-relative-path matching **and** an entity-signal requirement.

**Files:**
- Modify: `science/src/science_tool/entity_layout_migration.py` (`_DIR_TO_KIND` → exact-path maps; `_infer_kind`/`_project_dir_to_kind`; new `_discover_with_skips`; `skipped_untyped` report key)
- Test: `science/tests/test_entity_layout_migration.py`

- [ ] **Step 1: Write the failing discovery tests**

```python
def test_nested_nonroot_papers_dir_not_swept_without_signal(tmp_path: Path) -> None:
    # A frontmatter-less file under a NESTED dir whose bare name is `papers` must
    # not be discovered as a paper (exact-root keying, not bare parent name).
    _write(tmp_path, "doc/background/papers/loose-note.md", "# Loose note\n\nProse.\n")
    found = {e.rel_path for e in discover_legacy_entities(tmp_path)}
    assert "doc/background/papers/loose-note.md" not in found


def test_prose_doc_at_real_root_without_id_is_skipped_untyped(tmp_path: Path) -> None:
    # Direct child of specs/hypotheses with no id:/type: is prose, not a hypothesis.
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\n")
    _write(tmp_path, "specs/hypotheses/cohort-adjudication-h01.md", "# Cohort adjudication\n\nProse.\n")
    _write(tmp_path, "specs/hypotheses/h01-real.md",
           '---\nid: "hypothesis:h01-real"\ntype: hypothesis\ncreated: "2026-01-01"\n'
           'title: Real\nstatus: proposed\nupdated: "2026-01-01"\n---\nbody\n')
    _git_init(tmp_path)
    found = {e.rel_path for e in discover_legacy_entities(tmp_path)}
    assert "specs/hypotheses/cohort-adjudication-h01.md" not in found  # prose excluded
    assert "specs/hypotheses/h01-real.md" in found  # real entity discovered
    dry = migrate_layout(tmp_path, apply=False)
    assert "specs/hypotheses/cohort-adjudication-h01.md" in dry["skipped_untyped"]
    assert dry["undated_entities"] == []  # the prose doc is NOT an undated blocker


def test_explicit_id_in_nested_dir_still_discovered(tmp_path: Path) -> None:
    # A file with an explicit id of a known kind is still discovered regardless of
    # directory (id-prefix inference runs before the dir fallback).
    _write(tmp_path, "doc/background/papers/Adams2025.md",
           '---\nid: "paper:Adams2025"\ntype: paper\n---\nbody\n')
    found = {e.rel_path: e for e in discover_legacy_entities(tmp_path)}
    assert found["doc/background/papers/Adams2025.md"].kind == "paper"


def test_frontmatterless_file_at_exact_root_with_id_is_discovered(tmp_path: Path) -> None:
    # id: present (signal) but no type:/kind: — discovered via dir fallback + signal.
    _write(tmp_path, "doc/questions/q05-y.md", '---\nid: "question:q05-y"\n---\nbody\n')
    found = {e.rel_path for e in discover_legacy_entities(tmp_path)}
    assert "doc/questions/q05-y.md" in found
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd ~/d/science/science && rtk uv run --frozen pytest tests/test_entity_layout_migration.py -k "nested_nonroot or skipped_untyped or explicit_id_in_nested or exact_root_with_id" -v`
Expected: FAIL — today `doc/background/papers/loose-note.md` is swept in (bare `papers` parent), `skipped_untyped` is not a report key, and the prose doc is discovered as an undated entity.

- [ ] **Step 3: Replace the bare-name dir map with exact-relative-path maps**

In `science/src/science_tool/entity_layout_migration.py`, replace `_DIR_TO_KIND` (lines 138-142) with an explicit **legacy-root** map (pre-v3 source locations) plus a **destination** map (the `entities/<dir>` homes, for re-runs on partly-migrated trees), both keyed on full relative parent paths:

```python
# Pre-v3 legacy source roots -> kind, keyed on the FULL relative parent path so a
# nested dir whose bare name happens to match (doc/background/papers) is NOT swept.
# One entry per numeric/citekey core kind, derived from the pre-v3 layout.
_LEGACY_ROOT_TO_KIND: dict[str, str] = {
    "doc/papers": "paper",
    "doc/questions": "question",
    "doc/topics": "topic",
    "doc/interpretations": "interpretation",
    "doc/reports": "report",
    "doc/methods": "method",
    "doc/plans": "plan",
    "doc/pre-registrations": "pre-registration",
    "doc/discussions": "discussion",
    "doc/themes": "theme",
    "doc/searches": "search",
    "doc/evidence-lines": "evidence-line",
    "doc/findings": "finding",
    "doc/inquiries": "inquiry",
    "doc/observations": "observation",
    "doc/mechanisms": "mechanism",
    "specs/hypotheses": "hypothesis",
    "specs/propositions": "proposition",
}

# Destination roots (entities/<dir>) -> kind, for re-running on a partly-migrated
# tree. Derived from the policy table (SSOT) so every numeric/citekey kind's home
# is covered; singletons (no per-kind dir) are excluded.
_DEST_ROOT_TO_KIND: dict[str, str] = {
    resolve_path_policy(kind).root.as_posix(): kind
    for kind in markdown_entity_kinds()
    if resolve_path_policy(kind).strategy != "singleton"
}
```

> **Verify the legacy-root list:** run `cd ~/d/science/science && rtk uv run --frozen python -c "from science_tool.entities import markdown_entity_kinds, resolve_path_policy; [print(k, resolve_path_policy(k).root) for k in sorted(markdown_entity_kinds()) if resolve_path_policy(k).strategy != 'singleton']"` and confirm every non-singleton kind has a `_LEGACY_ROOT_TO_KIND` entry whose value matches. Add any missing kind (the destination map is auto-derived; the legacy map is hand-written and must stay complete).

- [ ] **Step 4: Rewrite `_project_dir_to_kind` to return full-path keys**

Replace `_project_dir_to_kind` (lines 123-129) so it returns a **full relative parent path → kind** map (legacy ∪ destination ∪ local homes):

```python
def _project_dir_to_kind(project_root: Path) -> dict[str, str]:
    """Full relative parent-path -> kind for the directory-name discovery fallback.

    Unions: pre-v3 legacy source roots, entities/<dir> destination roots (re-run
    safety), and each local kind's declared home. Keyed on the FULL relative path
    (not the bare segment) so nested dirs that merely share a name are not matched."""
    mapping = {**_LEGACY_ROOT_TO_KIND, **_DEST_ROOT_TO_KIND}
    for kind, policy in load_local_entity_policies(project_root).items():
        if policy.strategy != "singleton":
            mapping[policy.root.as_posix()] = kind
    return mapping
```

- [ ] **Step 5: Make `_infer_kind` key on the full parent path and signal the dir-fallback path**

Rewrite `_infer_kind` (lines 99-120) to (a) match the full relative parent path against the map, and (b) report whether the kind came from the dir fallback (which then requires an entity signal). Return a `(kind, needs_signal)` tuple:

```python
def _has_entity_signal(frontmatter: dict | None) -> bool:
    """True iff the frontmatter carries an entity signal: id/type/kind."""
    if not frontmatter:
        return False
    return any(frontmatter.get(k) for k in ("id", "type", "kind"))


def _infer_kind(
    rel_path: str,
    frontmatter: dict | None,
    *,
    known_kinds: set[str],
    dir_to_kind: dict[str, str],
) -> tuple[str | None, bool]:
    """Return (kind, needs_signal). needs_signal is True only for the directory
    fallback path; explicit type/kind/known-id-prefix and the by-path override
    are authoritative and need no extra signal."""
    if frontmatter is not None:
        value = frontmatter.get("type") or frontmatter.get("kind")
        if isinstance(value, str) and value:
            return value, False  # explicit type wins
        raw_id = frontmatter.get("id")
        if isinstance(raw_id, str) and ":" in raw_id:
            prefix = raw_id.split(":", 1)[0]
            if prefix in known_kinds:
                return prefix, False  # id-prefix beats directory name for foreign-dir files
    if rel_path in _PATH_KIND_OVERRIDES:
        return _PATH_KIND_OVERRIDES[rel_path], False  # synthesis singleton by path
    parent = Path(rel_path).parent.as_posix()
    dir_kind = dir_to_kind.get(parent)
    if dir_kind is not None:
        return dir_kind, True  # dir fallback: requires an entity signal (decision 4)
    return None, False
```

- [ ] **Step 6: Add `_discover_with_skips` and route discovery through it**

Refactor `discover_legacy_entities` (lines 62-86) to delegate to a new `_discover_with_skips` that also collects `skipped_untyped`. The public `discover_legacy_entities` keeps its `list[LegacyEntity]` signature so `plan_migration` is untouched:

```python
def _discover_with_skips(project_root: Path) -> tuple[list["LegacyEntity"], list[str]]:
    results: list[LegacyEntity] = []
    skipped_untyped: list[str] = []
    known = set(markdown_entity_kinds(project_root=project_root))
    dir_to_kind = _project_dir_to_kind(project_root)
    for root_name in _LEGACY_SCAN_ROOTS:
        root = project_root / root_name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            rel = path.relative_to(project_root).as_posix()
            if "templates" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            frontmatter, body = _split_frontmatter(text)
            kind, needs_signal = _infer_kind(rel, frontmatter, known_kinds=known, dir_to_kind=dir_to_kind)
            if kind is None:
                continue
            if needs_signal and not _has_entity_signal(frontmatter):
                skipped_untyped.append(rel)  # prose doc at a real root, no id/type — not an entity
                continue
            if not is_markdown_entity_kind(kind, project_root=project_root):
                continue
            old_id = None
            if frontmatter is not None:
                raw_id = frontmatter.get("id")
                old_id = raw_id if isinstance(raw_id, str) else None
            results.append(
                LegacyEntity(rel_path=rel, kind=kind, old_id=old_id, frontmatter=frontmatter or {}, body=body)
            )
    return results, sorted(skipped_untyped)


def discover_legacy_entities(project_root: Path) -> list["LegacyEntity"]:
    return _discover_with_skips(project_root)[0]
```

- [ ] **Step 7: Surface `skipped_untyped` in the migrate_layout report**

In `migrate_layout`, change the discovery call (line 607) and add the report key. Replace:
```python
    legacy_entities = list(discover_legacy_entities(project_root))
```
with:
```python
    legacy_entities, skipped_untyped = _discover_with_skips(project_root)
```
and add `"skipped_untyped": skipped_untyped,` to the `report` dict (next to `unresolved_warnings`).

- [ ] **Step 8: Run the discovery tests + full module**

Run: `cd ~/d/science/science && rtk uv run --frozen pytest tests/test_entity_layout_migration.py -v`
Expected: PASS. The existing `test_discovers_specs_and_doc_legacy_locations` still passes (`doc/background/papers/Adams2025.md` carries explicit `id:`/`type:` → discovered via id-prefix, not the dir fallback). `test_frontmatterless_file_under_unknown_parent_dir_is_skipped` still passes (no map entry → `kind is None`).

- [ ] **Step 9: Commit**

```bash
cd ~/d/science && rtk git add science/src/science_tool/entity_layout_migration.py science/tests/test_entity_layout_migration.py
rtk git commit -m "feat(migrate): exact-root discovery + entity-signal gate (Unit C, G8)"
```

---

## Task 5: Unit E — Knowledge-source `mappings.yaml` handling (G10)

`mappings.yaml` alias *source* keys are definitions, never references — they must not generate prose-ref warnings. Alias *targets* are structural and **must** resolve, but the graph audit does **not** validate them: `audit_project_sources` only feeds `manual_aliases` into the resolver (`graph/migrate.py:146`), and `ReferenceResolver.resolve()` treats any alias-map *key* as resolved without proving its target exists (`graph/reference_resolution.py:63`). A dangling alias target therefore passes the Unit A simulated audit silently. So this unit does two things: (1) exempt `mappings.yaml` from the free-text warning scan; (2) add **explicit alias-target validation** that resolves each target *through* the simulated post-move alias map (so a valid target by old id still passes via the injected `id_map`) and emits a structural blocker for a dangling target.

> Verified empirically: `aliases: {hypothesis:legacy-name: hypothesis:9999-nope}` yields `audit_project_sources(...) -> failed=False`; the explicit `_dangling_alias_targets` check below flags it, while a target that resolves (directly, or by old id via `id_map`) is not flagged.

`mappings.yaml` lives at `knowledge/sources/<local-profile>/mappings.yaml` with a top-level `aliases:` block (`commons/aliases.py:10-23`) — tests must use that real schema, not a bare top-level key.

**Files:**
- Modify: `science/src/science_tool/entity_layout_migration.py` (`migrate_layout` warning loop; new `_dangling_alias_targets`; extend `_simulated_postmove_audit_failures`)
- Test: `science/tests/test_entity_layout_migration.py`

- [ ] **Step 1: Write the failing tests (real `aliases:` schema)**

```python
def test_mappings_yaml_alias_source_key_is_not_a_warning(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\nknowledge_profiles:\n  local: local\n")
    _write(tmp_path, "specs/hypotheses/h01-a.md",
           '---\nid: "hypothesis:h01-a"\ntype: hypothesis\ncreated: "2026-01-01"\n'
           'title: A\nstatus: proposed\nupdated: "2026-01-01"\n---\nbody\n')
    # Real mappings.yaml schema: a top-level `aliases:` block whose SOURCE key
    # looks like a ref token must not be flagged as a warning.
    _write(tmp_path, "knowledge/sources/local/mappings.yaml",
           "aliases:\n  hypothesis:legacy-name: hypothesis:h01-a\n")
    _git_init(tmp_path)
    dry = migrate_layout(tmp_path, apply=False)
    flat_warn = [t for toks in dry["unresolved_warnings"].values() for t in toks]
    assert "hypothesis:legacy-name" not in flat_warn  # source key is a definition
    assert dry["unresolved_references"] == {}  # the target (h01-a) resolves → no blocker
    migrate_layout(tmp_path, apply=True)  # clean project applies


def test_mappings_yaml_dangling_alias_target_blocks(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", "name: t\nlayout_version: 2\nknowledge_profiles:\n  local: local\n")
    _write(tmp_path, "specs/hypotheses/h01-a.md",
           '---\nid: "hypothesis:h01-a"\ntype: hypothesis\ncreated: "2026-01-01"\n'
           'title: A\nstatus: proposed\nupdated: "2026-01-01"\n---\nbody\n')
    # Alias TARGET points at a nonexistent entity — the audit would not catch it,
    # so the explicit alias-target check must block --apply.
    _write(tmp_path, "knowledge/sources/local/mappings.yaml",
           "aliases:\n  hypothesis:legacy-name: hypothesis:9999-nope\n")
    _git_init(tmp_path)
    dry = migrate_layout(tmp_path, apply=False)
    assert dry["unresolved_references"]  # dangling target surfaced as a structural blocker
    with _pytest.raises(ValueError, match="structural"):
        migrate_layout(tmp_path, apply=True)
    assert not (tmp_path / "entities").exists()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd ~/d/science/science && rtk uv run --frozen pytest tests/test_entity_layout_migration.py -k "mappings_yaml" -v`
Expected: FAIL — the free-text scan flags the source key, and the dangling target does **not** block (the audit misses it).

- [ ] **Step 3: Exempt `mappings.yaml` from the warning scan**

In `migrate_layout`'s warning loop (added in Task 3, Step 4), skip the warning computation for `mappings.yaml` while still rewriting its content. Change the loop body to:

```python
    for bucket in (rewritten, singleton_text, inplace_text):
        for rel, text in list(bucket.items()):
            out, _ = rewrite_references(
                text, plan.id_map, policed_kinds=policed_kinds, project_root=project_root
            )
            bucket[rel] = out
            if rel.endswith("mappings.yaml"):
                continue  # Unit E: alias source keys are definitions, not refs;
                          # alias TARGETS are validated separately (see _dangling_alias_targets)
            _, warn_tokens = rewrite_references(
                _strip_code_spans(text), plan.id_map, policed_kinds=policed_kinds, project_root=project_root
            )
            warn_tokens = [t for t in warn_tokens if not _is_placeholder_token(t)]
            if warn_tokens:
                unresolved_warnings[rel] = warn_tokens
```

- [ ] **Step 4: Add `_dangling_alias_targets` and call it from the simulated-audit helper**

Add the helper near `_simulated_postmove_audit_failures` (Task 3) in `entity_layout_migration.py`:

```python
def _dangling_alias_targets(sources) -> list[dict]:
    """Alias targets the graph audit silently accepts but that resolve to no
    entity. `audit_project_sources` passes manual_aliases into the resolver but
    never proves each target exists; this closes that gap. Targets are resolved
    THROUGH the simulated alias map, so a valid target referenced by its OLD id
    (rewritten to a new identity via the injected id_map) is accepted. External
    (URL/path/go:/mesh:/doi:) and meta:* targets are exempt, matching the audit's
    own acceptance exceptions."""
    from science_tool.graph.reference_resolution import ReferenceResolver
    from science_tool.graph.sources import is_external_reference, is_metadata_reference

    resolver = ReferenceResolver.from_entities(sources.entities, manual_aliases=sources.manual_aliases)
    fails: list[dict] = []
    for alias, target in sources.manual_aliases.items():
        if is_external_reference(target) or is_metadata_reference(target):
            continue
        if resolver.resolve(target).status != "resolved":
            fails.append(
                {"check": "dangling_alias_target", "status": "fail",
                 "source": alias, "field": "aliases", "target": target}
            )
    return fails
```

Then extend `_simulated_postmove_audit_failures` (Task 3) so it appends these rows. Change its tail from:

```python
    rows, failed = audit_project_sources(sources)
    return [r for r in rows if r.get("status") == "fail"] if failed else []
```
to:
```python
    rows, failed = audit_project_sources(sources)
    audit_fails = [r for r in rows if r.get("status") == "fail"] if failed else []
    return audit_fails + _dangling_alias_targets(sources)
```

`sources` here is the simulated post-move `ProjectSources` whose `manual_aliases` is `real_mappings ∪ plan.id_map`; the injected `id_map` entries always target real moved-entity new ids, so they never false-positive.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd ~/d/science/science && rtk uv run --frozen pytest tests/test_entity_layout_migration.py -k "mappings_yaml" -v`
Expected: PASS — source key not warned; dangling target blocks; valid target applies.

- [ ] **Step 6: Commit**

```bash
cd ~/d/science && rtk git add science/src/science_tool/entity_layout_migration.py science/tests/test_entity_layout_migration.py
rtk git commit -m "feat(migrate): exempt mappings sources + block dangling alias targets (Unit E, G10)"
```

---

## Task 6: Unit F — Date-dir-scoped alias generation (G-novel collisions)

Multiple files sharing a bare-kind-word stem under distinct date-prefixed parent dirs (pan-disease's four `doc/probes/2026-05-*/interpretation.md`) currently collide on the back-compat alias `interpretation:interpretation`. Scope the generated alias with the date-prefixed parent directory so each gets a distinct alias.

**Files:**
- Modify: `science/src/science_tool/entity_layout_migration.py` (`_add_move`, the stem-alias block at lines 446-467)
- Test: `science/tests/test_entity_layout_migration.py`

- [ ] **Step 1: Write the failing test**

```python
def test_date_dir_scoped_alias_avoids_bare_kind_word_collision(tmp_path: Path) -> None:
    # Two files named interpretation.md under distinct date dirs must NOT collide
    # on the alias interpretation:interpretation.
    for day in ("2026-05-14", "2026-05-20"):
        _write(tmp_path, f"doc/probes/{day}/interpretation.md",
               f'---\ntype: interpretation\ncreated: "{day}"\ntitle: Probe {day}\n'
               f'status: active\n---\nbody\n')
    plan = plan_migration(tmp_path)
    alias_collisions = [c for c in plan.collisions if c.get("kind") == "alias"]
    assert alias_collisions == []  # date-scoping made the two aliases distinct
    assert "interpretation:2026-05-14-interpretation" in plan.id_map
    assert "interpretation:2026-05-20-interpretation" in plan.id_map
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd ~/d/science/science && rtk uv run --frozen pytest tests/test_entity_layout_migration.py::test_date_dir_scoped_alias_avoids_bare_kind_word_collision -v`
Expected: FAIL — both files produce alias `interpretation:interpretation`, recorded as an `alias` collision.

- [ ] **Step 3: Scope the stem alias by date-dir when the stem is a bare kind word**

In `_add_move` (lines 446-467), compute the alias local part with date-dir scoping when the bare stem equals the kind word (the ambiguous "bare kind word" case from the design). Replace the `stem_alias = f"{kind}:{Path(entity.rel_path).stem}"` line (line 446) with:

```python
    stem = Path(entity.rel_path).stem
    if stem == kind:
        # Bare kind-word stem (interpretation.md under doc/probes/<date>/): the
        # plain alias `interpretation:interpretation` collides across sibling
        # date dirs. Scope it by the date-prefixed parent dir so each is distinct.
        parent_name = Path(entity.rel_path).parent.name
        date_m = _DATE_PREFIX_DATE_RE.match(parent_name)
        alias_local = f"{date_m.group(1)}-{stem}" if date_m else stem
    else:
        alias_local = stem
    stem_alias = f"{kind}:{alias_local}"
```

The rest of the stem-alias block (the `if stem_alias in plan.id_map:` ambiguity handling, lines 447-467) is unchanged — it now sees distinct keys for the date-dir case and records no collision.

- [ ] **Step 4: Run the test + full module**

Run: `cd ~/d/science/science && rtk uv run --frozen pytest tests/test_entity_layout_migration.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && rtk git add science/src/science_tool/entity_layout_migration.py science/tests/test_entity_layout_migration.py
rtk git commit -m "feat(migrate): date-dir-scoped aliases for bare-kind-word stems (Unit F)"
```

---

## Task 7: Unit G — Placeholder guard for warnings

Keep the prose-warnings signal-rich by dropping tokens that are obviously not real ids: wildcards/glob (`*`, `…`), angle-bracket placeholders (`<id>`), bare `hNN`/`qNN`-style schema placeholders, and numeric line-range notations (`report:198-210`). Purely cosmetic — these are already non-blocking under Unit A. Replaces the Task 3 stub of `_is_placeholder_token`.

**Files:**
- Modify: `science/src/science_tool/entity_layout_migration.py` (`_is_placeholder_token` body)
- Test: `science/tests/test_entity_layout_migration.py`

- [ ] **Step 1: Write the failing tests**

The module already imports `pytest as _pytest` (top of file). Reuse it:

```python
@_pytest.mark.parametrize(
    "token",
    [
        "hypothesis:hNN",
        "question:qNN",
        "hypothesis:<id>",
        "report:198-210",
        "topic:*",
        "topic:…",
    ],
)
def test_placeholder_tokens_are_filtered_from_warnings(token: str) -> None:
    from science_tool.entity_layout_migration import _is_placeholder_token
    assert _is_placeholder_token(token) is True


@_pytest.mark.parametrize("token", ["hypothesis:h00-working-model", "paper:Adams2025", "question:0001-aging"])
def test_real_tokens_are_not_filtered(token: str) -> None:
    from science_tool.entity_layout_migration import _is_placeholder_token
    assert _is_placeholder_token(token) is False
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd ~/d/science/science && rtk uv run --frozen pytest tests/test_entity_layout_migration.py -k "placeholder_tokens or real_tokens" -v`
Expected: FAIL — the stub returns `False` for everything, so the placeholder cases fail.

- [ ] **Step 3: Implement the placeholder filter**

Replace the `_is_placeholder_token` stub (added in Task 3) with the real body. Add the module-level regex near the other ref regexes (~line 527):

```python
_PLACEHOLDER_LOCAL_RE = re.compile(r"^(?:[A-Za-z]NN|\d+-\d+|<.*>|[*…])$")


def _is_placeholder_token(token: str) -> bool:
    """True for tokens that are obviously not real ids: schema placeholders
    (hNN/qNN), angle-bracket placeholders (<id>), numeric line ranges
    (report:198-210), and wildcards (*, …). Used to keep prose warnings
    signal-rich; these are already non-blocking under Unit A."""
    if ":" not in token:
        return token in {"*", "…"} or token.startswith("<")
    _, local = token.split(":", 1)
    return _PLACEHOLDER_LOCAL_RE.match(local) is not None
```

- [ ] **Step 4: Run the tests + full module**

Run: `cd ~/d/science/science && rtk uv run --frozen pytest tests/test_entity_layout_migration.py -v`
Expected: PASS. Also re-run the Task 3 `test_code_fenced_and_inline_example_ids_warn_not_block` — `hypothesis:hNN` is now filtered from warnings too (it was already absent via code-span stripping; this is belt-and-suspenders).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && rtk git add science/src/science_tool/entity_layout_migration.py science/tests/test_entity_layout_migration.py
rtk git commit -m "feat(migrate): filter placeholder tokens from ref warnings (Unit G)"
```

---

## Task 8: Companion project-side manifest fixes (natural-systems, protein-landscape)

These are edits in **other project repos** (not the `~/d/science` branch). With Unit B, both projects already stop *crashing* (the bad kind is skipped+warned); these fixes make the warning go away and let the affected kinds actually migrate. Resolve each project root from `~/.config/science/config.yaml`.

**Files (in their respective project repos):**
- Modify: natural-systems `knowledge/sources/<local-profile>/manifest.yaml`
- Modify: protein-landscape `knowledge/sources/<local-profile>/manifest.yaml`

- [ ] **Step 1: Locate the two project roots and their local manifests**

```bash
rtk rg -n -A2 "natural-systems|protein-landscape" ~/.config/science/config.yaml
```
For each, the local manifest is `<root>/knowledge/sources/<local-profile>/manifest.yaml` where `<local-profile>` is the `knowledge_profiles.local` value in `<root>/science.yaml` (default `local`).

- [ ] **Step 2: Fix natural-systems `meta` kind**

In natural-systems' local manifest, change the `meta` kind's `canonical_prefix` from `doc` to `meta` so `name == canonical_prefix`:

```yaml
  - name: meta
    canonical_prefix: meta   # was: doc
    ...
```

Verify: `cd <natural-systems-root> && rtk uv run --frozen --project ~/d/science/science python -c "from pathlib import Path; from science_tool.entities import local_kind_warnings; print(local_kind_warnings(Path('.')))"` — expect `[]` for the `meta` kind.

- [ ] **Step 3: Remove protein-landscape's vestigial kinds**

In protein-landscape's local manifest, delete the `methods` and `paper-synthesis` entity-kind entries (0 entities each; `methods` home collides with the core `method` directory). Confirm no entities exist under their homes first:

```bash
cd <protein-landscape-root> && ls entities/methods entities/paper-synthesis 2>/dev/null
```
Expect "No such file or directory" (or empty) before deleting the kinds.

- [ ] **Step 4: Dry-run both projects to confirm clean readiness**

```bash
cd <natural-systems-root> && rtk uv run --frozen --project ~/d/science/science science entities migrate --project-root . > /tmp/migration-audit/natural-systems.json
cd <protein-landscape-root> && rtk uv run --frozen --project ~/d/science/science science entities migrate --project-root . > /tmp/migration-audit/protein-landscape.json
```
Expect: no crash; `collisions: []`, `unresolved_references: {}`, `undated_entities: []` in each (warnings may be populated).

- [ ] **Step 5: Commit each project repo separately**

```bash
cd <natural-systems-root> && rtk git add knowledge/sources && rtk git commit -m "fix(manifest): meta kind canonical_prefix doc->meta for v3 migration"
cd <protein-landscape-root> && rtk git add knowledge/sources && rtk git commit -m "fix(manifest): drop vestigial methods/paper-synthesis kinds for v3 migration"
```

---

## Task 9: Integration gate — re-run the 19-project dry-run

Re-run the readiness audit's dry-run across all 19 registered projects and confirm the design's success criteria. This is the acceptance gate, not a unit test.

**Files:**
- Read: `~/.config/science/config.yaml` (project enumeration)
- Read: `~/d/science/docs/audits/2026-06-06-layout-v3-migration-readiness-audit.md` (prior results to diff against)

- [ ] **Step 1: Run the full test suite once more**

```bash
cd ~/d/science/science && rtk uv run --frozen pytest tests/test_entity_layout_migration.py tests/test_entities_local_policies.py tests/test_entity_conformance.py -v
```
Expected: all PASS.

- [ ] **Step 2: Re-run the dry-run across all 19 projects**

For each project root in `~/.config/science/config.yaml`, run the migrator dry-run and capture JSON. This may be dispatched as parallel sub-agents (one per project) writing to `/tmp/migration-audit/<name>.json`, mirroring the original audit. Per project:

```bash
cd <project-root> && rtk uv run --frozen --project ~/d/science/science science entities migrate --project-root . > /tmp/migration-audit/<name>.json 2>/tmp/migration-audit/<name>.err
```

- [ ] **Step 3: Assert the success criteria**

For each report, check:
- **No crashes:** natural-systems and protein-landscape produce JSON (not a non-zero exit / `EntityCommandError`).
- **Ready (all but seq-feats):** `collisions == []`, `unresolved_references == {}`, `undated_entities == []`.
- **Warnings populated but non-blocking:** `unresolved_warnings` / `local_kind_warnings` / `skipped_untyped` may be non-empty; they do not affect readiness.
- **seq-feats** remains blocked on its genuine content debt (competing id variants) — this is expected, not a regression.

- [ ] **Step 4: Regression guard — the 5 clean leaf projects lose no real entities**

For cancer-ovarian, cancer-head-and-neck, cancer-prostate, cancer-breast, and health-immunity: confirm every entity that appeared in `moves` before still appears now, and that **none** of their real entities landed in `skipped_untyped` (the entity-signal gate must drop nothing real). Compare the `moves` count against the pre-change audit numbers in the readiness-audit doc.

- [ ] **Step 5: Update the readiness audit doc with the post-change results**

Append a "Post-implementation re-run (YYYY-MM-DD)" section to `~/d/science/docs/audits/2026-06-06-layout-v3-migration-readiness-audit.md` recording the new readiness table (expected: 18 ready / 1 blocked on content), and commit:

```bash
cd ~/d/science && rtk git add docs/audits/2026-06-06-layout-v3-migration-readiness-audit.md
rtk git commit -m "doc(audit): record post-robustness 19-project re-run results"
```

- [ ] **Step 6: Final review handoff**

After all tasks pass, dispatch the final whole-implementation code review (per subagent-driven-development), then use superpowers:finishing-a-development-branch to complete `feat/migration-robustness`.

---

## Self-Review Notes

- **Spec coverage:** Unit A → Task 3; Unit B → Task 1; Unit C → Task 4; Unit D → Task 2; Unit E → Task 5; Unit F → Task 6; Unit G → Task 7; companion manifest fixes → Task 8; integration gate → Task 9. All seven units + companions + integration are covered.
- **Keystone fidelity:** Task 3 implements blocking as `audit_project_sources` over a simulated post-move `ProjectSources` (markdown_overrides inject moved entities at new paths; `manual_aliases` augmented with `plan.id_map` for disk-resident non-markdown sources). This inherits the entire audited field surface and acceptance exceptions with no field enumeration — matching the thrice-reviewed design and the post-mutation backstop by construction.
- **Alias-target gap (review fix):** the graph audit does not validate `manual_aliases` targets (`graph/migrate.py:146` + `reference_resolution.py:63` — any alias-map key resolves without proving its target exists). Task 5 closes this with an explicit `_dangling_alias_targets` check that resolves each target through the simulated alias map (valid old-id targets resolve via the injected `id_map`; external/`meta:*` exempt) and feeds the structural blocker set. Verified empirically before writing the task.
- **API stability:** `load_local_entity_policies` (Task 1) and `discover_legacy_entities` (Task 4) keep their existing signatures; new behavior is exposed through sibling functions (`local_kind_warnings`, `_discover_with_skips`), so no caller breaks.
- **Type consistency:** `_is_placeholder_token` is introduced as a stub in Task 3 and given its real body in Task 7 (same signature). `_simulated_postmove_audit_failures` returns `list[dict]`; `_audit_failures_to_report` adapts it to the report's `dict[str, list[str]]` contract.
