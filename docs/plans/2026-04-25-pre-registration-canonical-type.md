# Pre-registration Canonical Type Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote `pre-registration` from an implicit project-local kind to a Science-canonical type, so files can declare `type: pre-registration` + `id: pre-registration:<slug>` consistently and be validated as such.

**Architecture:** Three small surfaces change, all additive. (1) `templates/pre-registration.md` gains `id:` and `type: "pre-registration"` frontmatter (plus `committed:`/`spec:`/`related:` placeholders) so new pre-regs ship the canonical shape. (2) `scripts/validate.sh` learns to recognize `type: pre-registration`: when present, the `id:` must use the `pre-registration:` prefix, and the existing pre-registration-section sweep (currently keyed on filename glob `doc/meta/pre-registration-*.md`) gains optional warns for the `committed:` / `spec:` body fields. (3) `commands/pre-register.md` is updated to emit `type: pre-registration` + `id: pre-registration:<slug>` when writing files. Downstream projects are NOT migrated.

**Tech Stack:** Bash (validate.sh), pytest + subprocess (validator tests), Markdown (template + command file).

---

## File Structure

Files modified:

- `templates/pre-registration.md` — replace minimal `title:`/`created:` frontmatter with the canonical `id:`/`type: "pre-registration"`/`title:`/`status:`/`committed:`/`spec:`/`related:`/`created:`/`updated:` shape.
- `scripts/validate.sh` — add a new section that walks pre-registration files (any `*.md` under `$DOC_DIR/` whose `type:` is `pre-registration` OR which match the existing `$DOC_DIR/meta/pre-registration-*.md` / `$DOC_DIR/pre-registrations/*.md` globs), verifying the `id:` prefix and optionally warning on missing `committed:` / `spec:`. The existing body-section sweep at `scripts/validate.sh:447-455` is preserved.
- `meta/validate.sh` — mirror the same new section (the two scripts have different sha256 at audit time but are kept in lockstep until managed-artifact-versioning unifies them; locate the equivalent insertion site by content, not line number).
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
source_refs: []
related: []  # hypothesis IDs, inquiry slugs, or task IDs this pre-reg covers
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
---
```

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
        "source_refs: []",
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


def test_validate_warns_when_pre_registration_id_prefix_wrong(tmp_path: Path) -> None:
    _write_minimal_research_project(tmp_path)
    (tmp_path / "doc" / "meta" / "pre-registration-h01-test.md").write_text(
        _pre_registration_body(
            type_value="pre-registration",
            id_value="plan:h01-test",  # wrong prefix
            committed="2026-04-25",
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
    assert "pre-registration:" in combined and "plan:h01-test" in combined, combined


def test_validate_does_not_warn_on_legacy_type_plan_pre_reg(tmp_path: Path) -> None:
    """Legacy shape (type: plan + id: pre-registration:...) must continue to validate
    silently — downstream migration is out of scope for this change."""
    _write_minimal_research_project(tmp_path)
    (tmp_path / "doc" / "meta" / "pre-registration-h01-test.md").write_text(
        _pre_registration_body(
            type_value="plan",
            id_value="pre-registration:h01-test",
            committed="2026-04-25",
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
    assert "id prefix" not in combined.lower(), combined


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
```

- [ ] **Step 3: Run the new tests to confirm three of four fail**

Run:
```bash
cd science-tool && uv run --frozen pytest tests/test_validate_script.py -k "pre_registration" -v
```
Expected: `test_validate_warns_when_pre_registration_id_prefix_wrong` and `test_validate_warns_when_pre_registration_missing_committed` FAIL (the validator does not yet check these). The two accept/no-warn cases should pass trivially.

- [ ] **Step 4: Commit failing tests**

```bash
git add science-tool/tests/test_validate_script.py
git commit -m "test(validate): pre-registration canonical type checks"
```

---

## Task 3: Implement `pre-registration` validation in `scripts/validate.sh` and `meta/validate.sh`

**Files:**
- Modify: `scripts/validate.sh` — extend section 11 (around line 447 where the existing `for f in "$DOC_DIR/meta/pre-registration-"*.md` body-section sweep lives).
- Modify: `meta/validate.sh` — apply the same extension. The two files have different sha256 but the pre-registration loop is identical in shape; locate the loop by content (`for f in "$DOC_DIR/meta/pre-registration-"*.md`) and apply the same change.

The existing loop already iterates `doc/meta/pre-registration-*.md`. We add an inner block that parses `type:` and `id:` from frontmatter (using the same `sed` recipe as the notes section at `scripts/validate.sh:530-543`) and:

- if `type:` is `pre-registration`, require the `id:` to start with `pre-registration:` (error if mismatched);
- if `type:` is `pre-registration`, warn if `committed:` is absent;
- if `type:` is `pre-registration`, warn if `spec:` is absent (`spec:` may be empty string — that's OK, project may not have a paired design doc);
- if `type:` is `plan` (legacy shape used by 3/4 downstream projects), do nothing new — the legacy file continues to validate without warning. This keeps the change purely additive.

Also extend the file glob to include `$DOC_DIR/pre-registrations/*.md` (mm30's canonical placement per audit §3.2; currently invisible to the validator).

- [ ] **Step 1: Read the existing pre-registration loop**

Run: `sed -n '445,460p' scripts/validate.sh`
Expected: the small loop that warns on missing body sections.

- [ ] **Step 2: Extend the loop**

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

    # Parse frontmatter type/id using the same recipe as the notes section.
    pre_type=$(sed -n "s/^type:[[:space:]]*['\"]\\{0,1\\}\\([^'\"]*\\)['\"]\\{0,1\\}[[:space:]]*$/\\1/p" "$f" | head -n 1 || true)
    pre_id=$(sed -n "s/^id:[[:space:]]*['\"]\\{0,1\\}\\([^'\"]*\\)['\"]\\{0,1\\}[[:space:]]*$/\\1/p" "$f" | head -n 1 || true)

    if [ "$pre_type" = "pre-registration" ]; then
        if [ -n "$pre_id" ] && ! printf "%s" "$pre_id" | grep -Eq '^pre-registration:'; then
            error "${f} type is 'pre-registration' but id '${pre_id}' does not use the 'pre-registration:' prefix"
        fi
        if ! grep -Eq '^committed:[[:space:]]' "$f" 2>/dev/null; then
            warn "${f} type 'pre-registration' should declare a 'committed:' date in frontmatter"
        fi
        if ! grep -Eq '^spec:[[:space:]]' "$f" 2>/dev/null; then
            warn "${f} type 'pre-registration' should declare a 'spec:' field (empty string is OK if no paired design doc)"
        fi
    fi
done
```

- [ ] **Step 3: Run targeted tests**

Run:
```bash
cd science-tool && uv run --frozen pytest tests/test_validate_script.py -k "pre_registration" -v
```
Expected: all four pre-registration tests pass.

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
git add scripts/validate.sh
git commit -m "feat(validate): canonical pre-registration type and id-prefix checks"
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

- Files declaring `type: "pre-registration"` (canonical, used today only by cbioportal per `docs/audits/downstream-project-conventions/projects/cbioportal.md` §4) gain enforcement of the `pre-registration:` id prefix and warnings on missing `committed:` / `spec:`.
- Files declaring `type: "plan"` with `id: "pre-registration:..."` (the legacy 3/4 shape — synthesis §5.2; e.g. mm30's `doc/pre-registrations/2026-04-15-t085-...md`, protein-landscape's `doc/meta/pre-registration-q63-heldout-taxa-benchmark.md`, natural-systems' `doc/meta/pre-registration-q54.md`) continue to validate silently. No warning is emitted on the type/id mismatch until at least one downstream project opts in.
- Pre-registration sections embedded inside hypothesis spec bodies (mm30 `specs/hypotheses/h*.md`, protein-landscape `specs/hypotheses/h0[1-4]-*.md`) are not file-level entities and are unaffected.

A separate cycle should later (a) propose a migration sweep for downstream projects to flip `type: plan` → `type: pre-registration`, (b) decide whether to add a deprecation warning for the legacy shape, and (c) coordinate with the §6.3 sanctioned-local-entity-kind work — once that lands, cbioportal's project-local `pre-registration` registration in `knowledge/sources/local/manifest.yaml` becomes redundant and can be removed in favor of the canonical type.

This plan does not need a separate plan file for that migration; a brief synthesis-§3.2 follow-up issue / task at downstream-project-time is sufficient.

---

## Self-Review Checklist

- Goal coverage: the canonical type is registered in the template + validator + command file; tests cover acceptance, id-prefix enforcement, legacy-shape silence, and `committed:` warning.
- Scope discipline: no migrations of downstream projects; no changes to `commands/interpret-results.md` or `science:big-picture` rendering (those depend on `related[]`, which is unchanged).
- Backwards compatibility: legacy `type: plan` + `id: pre-registration:*` files validate without new warnings (Task 2 Step 2 third test).
- Audit evidence: §3.2 (4/4 use pre-registration; 3/4 overload `type: plan`) and §8.3 (mm30's `spec:` linkage pattern) are both reflected in the validator and template change set.
