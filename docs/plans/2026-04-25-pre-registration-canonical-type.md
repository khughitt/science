# Pre-registration Canonical Type Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote `pre-registration` from an implicit project-local kind to a Science-canonical type, so files can declare `type: pre-registration` + `id: pre-registration:<slug>` consistently and be validated as such.

**Architecture:** Three small surfaces change, all additive. (1) `templates/pre-registration.md` gains `id:` and `type: "pre-registration"` frontmatter (plus `committed:`/`spec:`/`related:` placeholders) so new pre-regs ship the canonical shape. (2) `scripts/validate.sh` extends the existing pre-registration-section sweep (currently keyed on filename glob `doc/meta/pre-registration-*.md`) with optional warns for the `committed:` / `spec:` body fields, and broadens the glob to include `doc/pre-registrations/*.md`. **Id-prefix conformance is deliberately NOT added here** — Plan #7 Task 6 ships a generic per-type id-prefix table that includes a `pre-registration` row, and that is the single canonical home for id-prefix checks. Adding the same check here would produce duplicate warnings once Plan #7 lands. (3) `commands/pre-register.md` is updated to emit `type: pre-registration` + `id: pre-registration:<slug>` when writing files. Downstream projects are NOT migrated.

**Tech Stack:** Bash (validate.sh), pytest + subprocess (validator tests), Markdown (template + command file).

---

## File Structure

Files modified:

- `templates/pre-registration.md` — replace minimal `title:`/`created:` frontmatter with the canonical `id:`/`type: "pre-registration"`/`title:`/`status:`/`committed:`/`spec:`/`related:`/`created:`/`updated:` shape.
- `scripts/validate.sh` — extend the existing pre-registration body-section sweep (located by content; `for f in "$DOC_DIR/meta/pre-registration-"*.md`) so it (a) also iterates `$DOC_DIR/pre-registrations/*.md` and (b) when `type: pre-registration`, warns on missing `committed:` / `spec:` frontmatter fields. **Does not** add an id-prefix check — that lives in Plan #7 Task 6's PREFIX_RULES table.
- `meta/validate.sh` — mirror the same change (the two scripts have different sha256 at audit time but are kept in lockstep until managed-artifact-versioning unifies them; locate the equivalent insertion site by content, not line number).
- `commands/pre-register.md` — update the "Naming" and "After Writing" sections so the agent writes the new frontmatter, and accept `doc/pre-registrations/<slug>.md` placement (per audit §3.2 mm30 canonical) as well as the existing `doc/meta/pre-registration-<slug>.md`.
- `science-tool/tests/test_validate_script.py` — add tests for the new validator behavior.
- `README.md` — if the canonical-types or commands list calls out per-type id prefixes, append `pre-registration` to it; otherwise no change. (Verify in Task 5.)
- `docs/project-organization-profiles.md` — same: if the canonical-layout text enumerates entity types, append `pre-registration`; otherwise no change. (Verify in Task 5.)

No new files. No file splits. No restructuring. No migrations of downstream `*.md` files (those projects are read-only — see Migration Notes).

---

## Task 1: Update `templates/pre-registration.md` to canonical frontmatter

**Files:**
- Modify: `templates/pre-registration.md`

The current template ships only `title:` and `created:` (verified at `templates/pre-registration.md:1-4`). All four downstream projects have already converged on richer frontmatter — mm30 carries `id: pre-registration:<slug>, type: plan, status: committed, committed: <date>, spec: <doc/specs/...>, related[]` per `docs/audits/downstream-project-conventions/projects/mm30.md` §4. The right canonical shape is the same fields with `type: "pre-registration"` instead of `type: plan`.

- [ ] **Step 1: Read the current template**

Run: `cat templates/pre-registration.md | head -10`
Expected: see the two-line frontmatter (`title:` + `created:`).

- [ ] **Step 2: Replace the frontmatter block**

In `templates/pre-registration.md`, replace the first four lines (the existing `---`/`title`/`created`/`---` block) with:

```yaml
---
id: "pre-registration:{{slug}}"
type: "pre-registration"
title: "{{Short Title}}"
status: "committed"
committed: "{{YYYY-MM-DD}}"
spec: ""  # optional path to design/spec doc, e.g. doc/specs/2026-04-25-<slug>-design.md
related: []  # hypothesis IDs, inquiry slugs, or task IDs this pre-reg covers
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
---
```

`source_refs:` is intentionally **omitted** — the audit synthesis (§3.2) does not list it as part of the canonical pre-registration shape, and adding it would invent structure beyond audit evidence. Projects that need source-ref tracking on pre-regs may add the field as a project-local extension.

The body sections are unchanged.

- [ ] **Step 3: Verify the template is well-formed YAML**

Run:
```bash
python3 -c "import yaml; t=open('templates/pre-registration.md').read(); fm=t.split('---',2)[1]; print(yaml.safe_load(fm))"
```
Expected: a Python dict that includes `'type': 'pre-registration'` and `'id': 'pre-registration:{{slug}}'`. No YAML errors.

- [ ] **Step 4: Commit**

```bash
git add templates/pre-registration.md
git commit -m "feat(templates): pre-registration uses canonical type and id shape"
```

---

## Task 2: Add failing tests for `pre-registration` validation

**Files:**
- Modify: `science-tool/tests/test_validate_script.py`

The existing test file already has `_write_minimal_research_project` and `_write_common_files` helpers (verified at `science-tool/tests/test_validate_script.py:1-110`). The new tests drop pre-registration files at `doc/meta/pre-registration-<slug>.md` (the location the validator already inspects) and assert on validator output.

- [ ] **Step 1: Append a helper that writes a pre-registration file**

Append after the existing `_hypothesis_body` helper (or near the end of the helper section, before the first `def test_`):

```python
def _pre_registration_body(*, type_value: str, id_value: str, committed: str | None = None, spec: str | None = None) -> str:
    fm_lines = ["---", f'id: "{id_value}"', f'type: "{type_value}"', 'title: "Test Pre-Reg"', 'status: "committed"']
    if committed is not None:
        fm_lines.append(f'committed: "{committed}"')
    if spec is not None:
        fm_lines.append(f'spec: "{spec}"')
    fm_lines.extend([
        "related: []",
        'created: "2026-04-25"',
        'updated: "2026-04-25"',
        "---",
        "",
        "# Pre-registration: Test",
        "",
        "## Hypotheses Under Test\n\nh01.\n",
        "## Expected Outcomes\n\nSomething.\n",
        "## Decision Criteria\n\nThreshold X.\n",
        "## Null Result Plan\n\nFallback Y.\n",
    ])
    return "\n".join(fm_lines)
```

- [ ] **Step 2: Append failing tests**

Append the following tests at the end of the file:

```python
def test_validate_accepts_canonical_pre_registration(tmp_path: Path) -> None:
    _write_minimal_research_project(tmp_path)
    (tmp_path / "doc" / "meta" / "pre-registration-h01-test.md").write_text(
        _pre_registration_body(
            type_value="pre-registration",
            id_value="pre-registration:h01-test",
            committed="2026-04-25",
            spec="doc/specs/2026-04-25-h01-test-design.md",
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        env=_validate_env(extra_path=tmp_path / "bin"),
        capture_output=True, text=True, check=False,
    )
    combined = result.stdout + result.stderr
    assert "pre-registration" not in combined.lower() or "missing" not in combined.lower(), combined
    assert "id prefix" not in combined.lower(), combined


# NOTE: id-prefix conformance for type: pre-registration is intentionally NOT
# tested here. Plan #7 Task 6's generic PREFIX_RULES table is the single
# canonical home for that check; the corresponding test lives in Plan #7's
# test set. Adding it here too would produce duplicate warnings once Plan #7
# lands.


def test_validate_does_not_warn_on_legacy_type_plan_pre_reg(tmp_path: Path) -> None:
    """Legacy shape (type: plan + id: pre-registration:...) must not fire any of
    the Plan-#2-introduced warnings (committed/spec) — those are gated on
    type == pre-registration. (Plan #7 Task 6's id-prefix table will warn
    separately on the type/id mismatch once it ships; that is out of scope
    for this test.)"""
    _write_minimal_research_project(tmp_path)
    (tmp_path / "doc" / "meta" / "pre-registration-h01-test.md").write_text(
        _pre_registration_body(
            type_value="plan",
            id_value="pre-registration:h01-test",
            committed=None,
            spec=None,
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        env=_validate_env(extra_path=tmp_path / "bin"),
        capture_output=True, text=True, check=False,
    )
    combined = result.stdout + result.stderr
    assert "should declare a 'committed:'" not in combined, combined
    assert "should declare a 'spec:'" not in combined, combined


def test_validate_warns_when_pre_registration_missing_committed(tmp_path: Path) -> None:
    _write_minimal_research_project(tmp_path)
    (tmp_path / "doc" / "meta" / "pre-registration-h01-test.md").write_text(
        _pre_registration_body(
            type_value="pre-registration",
            id_value="pre-registration:h01-test",
            committed=None,  # missing
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        env=_validate_env(extra_path=tmp_path / "bin"),
        capture_output=True, text=True, check=False,
    )
    combined = result.stdout + result.stderr
    assert "committed" in combined.lower(), combined
    assert result.returncode == 0, combined  # warning, not error


def test_validate_warns_when_pre_registration_missing_spec(tmp_path: Path) -> None:
    _write_minimal_research_project(tmp_path)
    (tmp_path / "doc" / "meta" / "pre-registration-h01-test.md").write_text(
        _pre_registration_body(
            type_value="pre-registration",
            id_value="pre-registration:h01-test",
            committed="2026-04-25",
            spec=None,  # missing
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        env=_validate_env(extra_path=tmp_path / "bin"),
        capture_output=True, text=True, check=False,
    )
    combined = result.stdout + result.stderr
    assert "spec" in combined.lower(), combined
    assert result.returncode == 0, combined  # warning, not error
```

- [ ] **Step 3: Run the new tests to confirm two of four fail**

Run:
```bash
cd science-tool && uv run --frozen pytest tests/test_validate_script.py -k "pre_registration" -v
```
Expected: `test_validate_warns_when_pre_registration_missing_committed` and `test_validate_warns_when_pre_registration_missing_spec` FAIL (the validator does not yet check these). The two no-warn / legacy-silence cases pass trivially.

- [ ] **Step 4: Commit failing tests**

```bash
git add science-tool/tests/test_validate_script.py
git commit -m "test(validate): pre-registration canonical type checks"
```

---

## Task 3: Implement `pre-registration` validation in `scripts/validate.sh` and `meta/validate.sh`

**Files:**
- Modify: `scripts/validate.sh` — extend the existing `for f in "$DOC_DIR/meta/pre-registration-"*.md` body-section sweep (located by content; ~line 456 at audit time).
- Modify: `meta/validate.sh` — apply the same extension (~line 448 at audit time; locate by content, `for f in "$DOC_DIR/meta/pre-registration-"*.md`).

The existing loop already iterates `doc/meta/pre-registration-*.md`. We extend it so it (a) also iterates `$DOC_DIR/pre-registrations/*.md` (mm30's canonical placement per audit §3.2; currently invisible to the validator), and (b) when `type: pre-registration`, warns on missing `committed:` / `spec:` body fields. Frontmatter parsing reuses the same `sed` recipe used elsewhere in the script.

Concretely:

- if `type:` is `pre-registration`, warn if `committed:` is absent;
- if `type:` is `pre-registration`, warn if `spec:` is absent (`spec:` may be empty string — that's OK, project may not have a paired design doc);
- if `type:` is anything else (legacy `type: plan` in mm30 + protein-landscape; `type: plan` with `id: plan:pre-registration-<slug>` in natural-systems; project-local `type: pre-registration` already in cbioportal — only 2/4 use `type: plan` + `id: pre-registration:*`), do nothing new — the legacy/local file continues to validate without these warnings. This keeps the change purely additive.

**Id-prefix conformance is intentionally NOT added in this loop** — Plan #7 Task 6 ships a generic per-type id-prefix table (`PREFIX_RULES`) that includes a `pre-registration:` row. Adding it here too would produce duplicate warnings on the same condition once Plan #7 lands.

- [ ] **Step 1: Read the existing pre-registration loop in both files**

```bash
sed -n '445,460p' scripts/validate.sh
sed -n '445,460p' meta/validate.sh   # locate by content; line offset may differ
```
Expected: the small loop that warns on missing body sections, in both files.

- [ ] **Step 2a: Extend the loop in `scripts/validate.sh`**

Replace the existing block:

```bash
# --- Pre-registration documents ---
for f in "$DOC_DIR/meta/pre-registration-"*.md; do
    [ -f "$f" ] || continue
    for section in "Hypotheses Under Test" "Expected Outcomes" "Decision Criteria" "Null Result Plan"; do
        if ! grep -q "## $section" "$f"; then
            warn "Pre-registration $f missing section: $section"
        fi
    done
done
```

with:

```bash
# --- Pre-registration documents ---
# Inspect both placements observed across downstream projects (audit §3.2):
#   doc/meta/pre-registration-<slug>.md  (natural-systems, protein-landscape, cbioportal)
#   doc/pre-registrations/<slug>.md      (mm30 canonical)
for f in "$DOC_DIR/meta/pre-registration-"*.md "$DOC_DIR/pre-registrations/"*.md; do
    [ -f "$f" ] || continue

    for section in "Hypotheses Under Test" "Expected Outcomes" "Decision Criteria" "Null Result Plan"; do
        if ! grep -q "## $section" "$f"; then
            warn "Pre-registration $f missing section: $section"
        fi
    done

    # Parse frontmatter type using the same recipe as the notes section.
    # Note: id-prefix conformance is handled by Plan #7 Task 6's PREFIX_RULES
    # table, not here, to avoid duplicate warnings on the same condition.
    pre_type=$(sed -n "s/^type:[[:space:]]*['\"]\\{0,1\\}\\([^'\"]*\\)['\"]\\{0,1\\}[[:space:]]*$/\\1/p" "$f" | head -n 1 || true)

    if [ "$pre_type" = "pre-registration" ]; then
        if ! grep -Eq '^committed:[[:space:]]' "$f" 2>/dev/null; then
            warn "${f} type 'pre-registration' should declare a 'committed:' date in frontmatter"
        fi
        if ! grep -Eq '^spec:[[:space:]]' "$f" 2>/dev/null; then
            warn "${f} type 'pre-registration' should declare a 'spec:' field (empty string is OK if no paired design doc)"
        fi
    fi
done
```

- [ ] **Step 2b: Apply the same replacement in `meta/validate.sh`**

Locate the same `for f in "$DOC_DIR/meta/pre-registration-"*.md` loop in `meta/validate.sh` (line offset differs from `scripts/validate.sh`; use content search). Apply the identical replacement block. Both validators must contain the same logic until managed-artifact-versioning unifies them.

Verify the change is in place:

```bash
grep -n 'pre-registrations' scripts/validate.sh meta/validate.sh
grep -n 'committed:' scripts/validate.sh meta/validate.sh | grep -v '^#'
```

Expected: both files show the new `$DOC_DIR/pre-registrations/` glob entry and the warn-on-missing-`committed:` / `spec:` logic.

- [ ] **Step 3: Run targeted tests**

Run:
```bash
cd science-tool && uv run --frozen pytest tests/test_validate_script.py -k "pre_registration" -v
```
Expected: all four pre-registration tests (canonical-acceptance, legacy-silence, missing-committed warn, missing-spec warn) pass.

- [ ] **Step 4: Run full validator test suite for regressions**

Run:
```bash
cd science-tool && uv run --frozen pytest tests/test_validate_script.py -v
```
Expected: all tests pass.

- [ ] **Step 5: Smoke-test against the live `meta/` project**

Run from `/mnt/ssd/Dropbox/science/meta`:
```bash
bash validate.sh 2>&1 | grep -i "pre-registration" || echo "no pre-registration warnings"
```
Expected: `no pre-registration warnings` (meta has no pre-registration files yet).

- [ ] **Step 6: Commit**

```bash
git add scripts/validate.sh meta/validate.sh
git commit -m "feat(validate): canonical pre-registration committed/spec checks (warn severity)"
```

---

## Task 4: Update `commands/pre-register.md` to emit canonical frontmatter

**Files:**
- Modify: `commands/pre-register.md`

The current command file (verified at `commands/pre-register.md:83-94`) tells the agent to fill in the template's body but does not specify the frontmatter shape — there's no instruction to set `type:` or `id:`. With Task 1's template change the new shape is implicit, but the command should explicitly call it out so the agent fills in `id`, `committed`, and `spec` correctly.

- [ ] **Step 1: Read the current "Writing" and "Naming" sections**

Run: `sed -n '80,100p' commands/pre-register.md`
Expected: see the existing "Writing" / "Naming" / "After Writing" prose.

- [ ] **Step 2: Replace the "Naming" section**

In `commands/pre-register.md`, replace the existing "Naming" subsection with:

```markdown
### Naming and Frontmatter

Use the hypothesis ID, inquiry slug, or task ID as the basis:
- **Filename:** `doc/meta/pre-registration-<slug>.md` (default), or `doc/pre-registrations/<slug>.md` if the project has adopted that placement.
- **Frontmatter** must use the canonical pre-registration shape:
  - `id: "pre-registration:<slug>"`
  - `type: "pre-registration"`
  - `status: "committed"` once the user has signed off on the criteria
  - `committed: "<YYYY-MM-DD>"` — the date the criteria are locked
  - `spec: "<path-to-design-doc>"` — optional; empty string if no paired design doc exists
  - `related: [...]` — hypothesis IDs, inquiry slugs, and/or task IDs this pre-reg covers
- The `related` field is what `interpret-results` searches on, so it must be populated.
```

- [ ] **Step 3: Update the "After Writing" section's first bullet**

In the "After Writing" section, replace:

```markdown
1. Save to `doc/meta/pre-registration-<slug>.md`.
```

with:

```markdown
1. Save to `doc/meta/pre-registration-<slug>.md` (or `doc/pre-registrations/<slug>.md` if the project uses that placement). The frontmatter must declare `type: "pre-registration"` and `id: "pre-registration:<slug>"` per the template.
```

- [ ] **Step 4: Commit**

```bash
git add commands/pre-register.md
git commit -m "feat(pre-register): emit canonical pre-registration type and id"
```

---

## Task 5: Verify documentation enumerations and end-to-end check

**Files:**
- Read-then-decide: `README.md`, `docs/project-organization-profiles.md`. Modify only if these documents enumerate canonical types / id prefixes.

Both files were spot-checked: neither currently lists Science's canonical types as an explicit enumeration (no "the canonical types are: hypothesis, plan, ..." block). If a future grep confirms an enumeration was added, append `pre-registration`.

- [ ] **Step 1: Search for any canonical-types enumeration**

Run:
```bash
grep -nE 'canonical types?|type:[[:space:]]*"?(hypothesis|plan|question|paper|topic|interpretation|report|search|meta)"?' README.md docs/project-organization-profiles.md
```
Expected: a small number of context-only matches (e.g. example frontmatter blocks), no flat enumeration. If a flat enumeration appears, edit it to include `pre-registration` and re-run validation.

- [ ] **Step 2: Update if needed**

If Step 1 found an enumeration, append `pre-registration` in alphabetical order. Otherwise skip.

- [ ] **Step 3: Run full repo validators**

Run from `/mnt/ssd/Dropbox/science`:
```bash
cd meta && bash validate.sh --verbose 2>&1 | tail -20
```
Expected: no new errors or warnings introduced by these changes.

- [ ] **Step 4: Run full science-tool test suite**

Run:
```bash
cd science-tool && uv run --frozen pytest -x
```
Expected: all tests pass.

- [ ] **Step 5: No commit unless Step 2 modified files**

If documentation was edited:
```bash
git add README.md docs/project-organization-profiles.md
git commit -m "docs: list pre-registration as a canonical type"
```

Otherwise this task ends without a commit.

---

## Migration Notes

**Downstream migration is out of scope for this plan.** The four audited projects (`mm30`, `cbioportal`, `protein-landscape`, `natural-systems`) live in separate repositories and are read-only from this change's perspective.

The validator change in Task 3 is purely additive:

- Files declaring `type: "pre-registration"` (canonical, used today only by cbioportal per `docs/audits/downstream-project-conventions/projects/cbioportal.md` §4) gain warnings on missing `committed:` / `spec:` body fields. Id-prefix conformance lands separately via Plan #7 Task 6.
- Files declaring `type: "plan"` with `id: "pre-registration:..."` (the 2/4 legacy shape used by mm30 and protein-landscape — e.g. mm30's `doc/pre-registrations/2026-04-15-t085-...md` and protein-landscape's `doc/meta/pre-registration-q63-heldout-taxa-benchmark.md`) do not fire any Plan-#2 warning — the new checks are gated on `type == pre-registration`. natural-systems uses a third shape (`type: "plan"` with `id: "plan:pre-registration-<slug>"`) which is similarly untouched by Plan #2. cbioportal already registers `type: pre-registration` as a project-local kind and converges on the canonical shape with no migration. (Plan #7 Task 6 will warn on the legacy type/id mismatches via its generic prefix table once it ships; that is the deliberate single home for that signal.)
- Pre-registration sections embedded inside hypothesis spec bodies (mm30 `specs/hypotheses/h*.md`, protein-landscape `specs/hypotheses/h0[1-4]-*.md`) are not file-level entities and are unaffected.

A separate cycle should later (a) propose a migration sweep for downstream projects to flip `type: plan` → `type: pre-registration`, (b) decide whether to add a deprecation warning for the legacy shape, and (c) coordinate with the §6.3 sanctioned-local-entity-kind work — once that lands, cbioportal's project-local `pre-registration` registration in `knowledge/sources/local/manifest.yaml` becomes redundant and can be removed in favor of the canonical type.

This plan does not need a separate plan file for that migration; a brief synthesis-§3.2 follow-up issue / task at downstream-project-time is sufficient.

---

## Self-Review Checklist

- Goal coverage: the canonical type is registered in the template + validator + command file; tests cover acceptance, legacy-shape silence, missing-`committed:`, and missing-`spec:`. Id-prefix conformance is owned by Plan #7 Task 6's PREFIX_RULES table — deliberately out of scope here to avoid duplicate warnings.
- Scope discipline: no migrations of downstream projects; no changes to `commands/interpret-results.md` or `science:big-picture` rendering (those depend on `related[]`, which is unchanged).
- Backwards compatibility: legacy `type: plan` + `id: pre-registration:*` files do not fire any Plan-#2-introduced warning (committed/spec are gated on `type == pre-registration`). Plan #7 Task 6 will warn separately on the type/id mismatch when it ships; that is expected.
- Audit evidence: §3.2 (4/4 use pre-registration; 3/4 overload `type: plan`, of which only 2/4 use `id: pre-registration:*` — natural-systems uses `id: plan:pre-registration-<slug>`) and §8.3 (mm30's `spec:` linkage pattern) are both reflected in the validator and template change set.
