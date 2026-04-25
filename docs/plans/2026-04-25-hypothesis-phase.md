# Hypothesis Developmental Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce an optional `phase: candidate | active` frontmatter field on hypotheses, orthogonal to `status:`, with template, validator, and `/science:big-picture` rendering support so candidate hypotheses can be promoted as organizing frames without implying full epistemic standing.

**Architecture:** Three small, mostly-independent surfaces change. (1) `templates/hypothesis.md` gains a `phase: "active"` frontmatter line and an optional "Promotion criteria" body section. (2) `scripts/validate.sh` gains a single rule inside its existing hypothesis loop: if `phase:` is present, value must be `candidate` or `active`. (3) `commands/big-picture.md` gains instructions to partition hypotheses by `phase:` and render a new "Candidate frames" section in the rollup. No Python code changes; the rollup is written by Claude per phase 3 of the big-picture command, so the rendering change is an instructional change to the command file.

**Tech Stack:** Bash (validate.sh), pytest + subprocess (validator tests), Markdown (template + command file). The repo has no central frontmatter schema for hypotheses today — the validator is the only enforcement point — so no Python entity/schema files require changes.

---

## File Structure

Files modified:

- `templates/hypothesis.md` — add `phase: "active"` to frontmatter; insert "Promotion criteria" section between "Falsifiability" and "Supporting Evidence".
- `scripts/validate.sh` — add a phase-value check to the existing hypothesis loop (around line 290-310).
- `commands/big-picture.md` — update Phase 1 (note that bundle includes phase), Phase 3 (add "Candidate frames" body section to rollup, partition the Arc/Research-fronts).
- `science-tool/tests/test_validate_script.py` — add tests for the new phase rule.

No new files. No file splits. No restructuring.

---

## Task 1: Add `phase:` to hypothesis template

**Files:**
- Modify: `templates/hypothesis.md`

This is a documentation-only change. The template is the canonical example new hypotheses copy from. Adding `phase: "active"` here makes the field discoverable without forcing existing hypotheses to migrate (they continue to validate without it).

- [ ] **Step 1: Read the current template**

Run: `cat templates/hypothesis.md`
Expected: see the current frontmatter block (lines 1-11) and body sections starting with `# Hypothesis`.

- [ ] **Step 2: Add `phase: "active"` line to frontmatter**

In `templates/hypothesis.md`, replace the line `status: "proposed"` with:

```yaml
status: "proposed"
phase: "active"  # candidate | active. `candidate` for trial framings being promoted to organize work but not yet committed; `active` (default) for committed frames.
```

- [ ] **Step 3: Add "Promotion criteria" body section between "Falsifiability" and "Supporting Evidence"**

In `templates/hypothesis.md`, find the blank line between the "## Falsifiability" section's closing comment and the "## Supporting Evidence" heading. Insert this section there:

```markdown
## Promotion criteria

<!--
Required prose when `phase: candidate`; omit when `phase: active`.
What evidence or analytic outcome would justify promoting this from
candidate to active? Be concrete. This is a documentation convention,
not a validator-enforced rule.
-->

```

- [ ] **Step 4: Verify the template is well-formed YAML**

Run:
```bash
python3 -c "import yaml; t=open('templates/hypothesis.md').read(); fm=t.split('---',2)[1]; print(yaml.safe_load(fm))"
```
Expected: a Python dict that includes `'phase': 'active'` and `'status': 'proposed'`. No YAML errors.

- [ ] **Step 5: Verify body section ordering**

Run:
```bash
grep -n '^## ' templates/hypothesis.md
```
Expected output (in order):
```
## Organizing Conjecture
## Proposition Bundle
## Current Uncertainty
## Predictions
## Falsifiability
## Promotion criteria
## Supporting Evidence
## Disputing Evidence
## Evidence Needed To Shift Belief
## Related Work
```

- [ ] **Step 6: Commit**

```bash
git add templates/hypothesis.md
git commit -m "feat(templates): add phase field and Promotion criteria section to hypothesis template"
```

---

## Task 2: Write failing test for `phase:` validation

**Files:**
- Modify: `science-tool/tests/test_validate_script.py`

The bash validator is exercised end-to-end via `subprocess.run(["bash", validate.sh])` in this file. We add tests that build a minimal research-profile project, drop a hypothesis file with various `phase:` values into `specs/hypotheses/`, run the validator, and assert on the warning output.

- [ ] **Step 1: Read the bottom of the test file to see existing fixture patterns**

Run: `tail -100 science-tool/tests/test_validate_script.py`
Expected: see existing tests that use `_write_common_files`, `_write_python3_stub`, `_write_science_tool_stub` to set up a tmp_path project, then `subprocess.run` the script.

- [ ] **Step 2: Add helper for writing a hypothesis file**

Append this helper after `_write_science_tool_stub` (anchor on the line immediately before the first `def test_` at line ~101):

```python
def _write_minimal_research_project(root: Path) -> None:
    """Set up a research-profile project with all paths the validator expects."""
    _write_common_files(root, "research")
    _write_python3_stub(root / "bin")
    _write_science_tool_stub(root / "bin")
    (root / "RESEARCH_PLAN.md").write_text("# Research Plan\n\n## Research Direction\n", encoding="utf-8")
    (root / "specs" / "research-question.md").write_text("# Question\n", encoding="utf-8")
    (root / "specs" / "scope-boundaries.md").write_text("# Scope\n", encoding="utf-8")
    (root / "specs" / "hypotheses").mkdir(parents=True)
    (root / "papers" / "pdfs").mkdir(parents=True)
    (root / "papers" / "references.bib").write_text("% bib\n", encoding="utf-8")
    (root / "data" / "raw").mkdir(parents=True)
    (root / "data" / "processed").mkdir(parents=True)
    (root / "models").mkdir(parents=True)
    (root / "results").mkdir(parents=True)
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)
    (root / "code" / "scripts").mkdir(parents=True)
    (root / "code" / "notebooks").mkdir(parents=True)
    (root / "code" / "workflows").mkdir(parents=True)


def _hypothesis_body(phase_line: str) -> str:
    """Compose a hypothesis file body with a configurable phase frontmatter line."""
    fm_lines = [
        "---",
        'id: "hypothesis:h01-test"',
        'type: "hypothesis"',
        'title: "Test"',
        'status: "proposed"',
    ]
    if phase_line:
        fm_lines.append(phase_line)
    fm_lines.extend([
        "source_refs: []",
        "related: []",
        'created: "2026-04-25"',
        'updated: "2026-04-25"',
        "---",
        "",
        "# Hypothesis: Test",
        "",
        "## Falsifiability",
        "",
        "Some falsifiability prose.",
        "",
    ])
    return "\n".join(fm_lines)
```

- [ ] **Step 3: Add the failing tests**

Append these test functions at the end of the file:

```python
def test_validate_accepts_hypothesis_with_phase_active(tmp_path: Path) -> None:
    _write_minimal_research_project(tmp_path)
    (tmp_path / "specs" / "hypotheses" / "h01-test.md").write_text(
        _hypothesis_body('phase: "active"'),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        env=_validate_env(extra_path=tmp_path / "bin"),
        capture_output=True,
        text=True,
        check=False,
    )

    combined = result.stdout + result.stderr
    assert "invalid phase" not in combined.lower(), combined


def test_validate_accepts_hypothesis_with_phase_candidate(tmp_path: Path) -> None:
    _write_minimal_research_project(tmp_path)
    (tmp_path / "specs" / "hypotheses" / "h01-test.md").write_text(
        _hypothesis_body('phase: "candidate"'),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        env=_validate_env(extra_path=tmp_path / "bin"),
        capture_output=True,
        text=True,
        check=False,
    )

    combined = result.stdout + result.stderr
    assert "invalid phase" not in combined.lower(), combined


def test_validate_accepts_hypothesis_without_phase(tmp_path: Path) -> None:
    _write_minimal_research_project(tmp_path)
    (tmp_path / "specs" / "hypotheses" / "h01-test.md").write_text(
        _hypothesis_body(""),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        env=_validate_env(extra_path=tmp_path / "bin"),
        capture_output=True,
        text=True,
        check=False,
    )

    combined = result.stdout + result.stderr
    assert "invalid phase" not in combined.lower(), combined


def test_validate_warns_on_invalid_phase_value(tmp_path: Path) -> None:
    _write_minimal_research_project(tmp_path)
    (tmp_path / "specs" / "hypotheses" / "h01-test.md").write_text(
        _hypothesis_body('phase: "tentative"'),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        env=_validate_env(extra_path=tmp_path / "bin"),
        capture_output=True,
        text=True,
        check=False,
    )

    combined = result.stdout + result.stderr
    assert "invalid phase" in combined.lower() and "tentative" in combined, combined
```

- [ ] **Step 4: Run the new tests to verify they fail**

Run:
```bash
cd science-tool && uv run --frozen pytest tests/test_validate_script.py -k "phase" -v
```
Expected: `test_validate_warns_on_invalid_phase_value` FAILS (the validator does not yet check `phase:`, so no "invalid phase" message appears). The three accept-* tests should PASS already (the absence of a warning is trivially true today). Confirm at least the failing case fails for the right reason ("invalid phase" not in output).

- [ ] **Step 5: Commit the failing test**

```bash
git add science-tool/tests/test_validate_script.py
git commit -m "test(validate): add tests for hypothesis phase frontmatter validation"
```

---

## Task 3: Implement `phase:` validation in validate.sh

**Files:**
- Modify: `scripts/validate.sh:289-311` (the existing hypothesis loop in section "5. Hypothesis completeness")

The hypothesis loop already iterates `specs/hypotheses/h*.md` and checks for `^status:`. We extend it to also check `^phase:` if present.

- [ ] **Step 1: Read the current hypothesis loop**

Run: `sed -n '285,315p' scripts/validate.sh`
Expected: lines covering `# ─── 5. Hypothesis completeness ───` through the closing `fi` at line ~311.

- [ ] **Step 2: Add phase validation inside the loop**

In `scripts/validate.sh`, find the closing `fi` of the existing status check (around line 309 — the line that ends the `if ! grep -q "^\- \*\*Status:\*\*"` block). Immediately after that closing `fi` and before the `done` that ends the for-loop, add:

```bash
        # If phase is present, value must be one of the enumerated values.
        # Absent is fine — defaults to `active` per spec.
        phase_value=$(sed -n "s/^phase:[[:space:]]*['\"]\\{0,1\\}\\([^'\"]*\\)['\"]\\{0,1\\}[[:space:]]*$/\\1/p" "$hyp_file" | head -n 1 || true)
        if [ -n "$phase_value" ] && [ "$phase_value" != "candidate" ] && [ "$phase_value" != "active" ]; then
            warn "${hyp_file} has invalid phase '${phase_value}' (must be 'candidate' or 'active')"
        fi
```

The full context after editing should look like:

```bash
        # Check for status in YAML frontmatter or inline format
        if ! grep -q "^\- \*\*Status:\*\*" "$hyp_file" 2>/dev/null && \
           ! grep -q "^status:" "$hyp_file" 2>/dev/null; then
            warn "${hyp_file} missing Status field"
        fi

        # If phase is present, value must be one of the enumerated values.
        # Absent is fine — defaults to `active` per spec.
        phase_value=$(sed -n "s/^phase:[[:space:]]*['\"]\\{0,1\\}\\([^'\"]*\\)['\"]\\{0,1\\}[[:space:]]*$/\\1/p" "$hyp_file" | head -n 1 || true)
        if [ -n "$phase_value" ] && [ "$phase_value" != "candidate" ] && [ "$phase_value" != "active" ]; then
            warn "${hyp_file} has invalid phase '${phase_value}' (must be 'candidate' or 'active')"
        fi
    done
fi
```

- [ ] **Step 3: Run the targeted tests to verify they pass**

Run:
```bash
cd science-tool && uv run --frozen pytest tests/test_validate_script.py -k "phase" -v
```
Expected: all four `*phase*` tests PASS — the warning fires only when an invalid value is present, never when the value is `active`, `candidate`, or absent.

- [ ] **Step 4: Run the full validate-script test suite to confirm no regressions**

Run:
```bash
cd science-tool && uv run --frozen pytest tests/test_validate_script.py -v
```
Expected: all tests pass.

- [ ] **Step 5: Smoke-test the validator end-to-end against the live repo**

Run from the repo root:
```bash
bash scripts/validate.sh 2>&1 | grep -i "phase" || echo "no phase warnings"
```
Expected: `no phase warnings` (existing hypotheses lack `phase:`, which is allowed).

- [ ] **Step 6: Commit**

```bash
git add scripts/validate.sh
git commit -m "feat(validate): warn on invalid hypothesis phase value"
```

---

## Task 4: Update `/science:big-picture` to render Candidate frames section

**Files:**
- Modify: `commands/big-picture.md`

Per the spec, the rollup gains one new section ("Candidate frames") between "Research fronts" and "Knowledge Gaps". Per-hypothesis files are unchanged in structure or rules — only the rollup's organization changes. The `synthesized_from:` frontmatter list still includes both candidate and active hypotheses; they are distinguished at rollup-write time by reading each hypothesis file's `phase:`.

- [ ] **Step 1: Read the current big-picture command file's Phase 1 hypothesis enumeration and Phase 3 rollup body sections**

Run: `sed -n '40,80p' commands/big-picture.md` then `sed -n '127,170p' commands/big-picture.md`
Expected: see "Enumerate hypotheses from `specs/hypotheses/*.md`" and the body-sections list in Phase 3.

- [ ] **Step 2: Add a phase-aware bundle field to Phase 1**

In `commands/big-picture.md`, find the line `- \`hypothesis_path\`: path to the \`specs/hypotheses/<id>.md\` file.` (around line 47). Immediately after that line, insert:

```markdown
- `phase`: read `phase:` from the hypothesis frontmatter; default to `active` if absent.
```

- [ ] **Step 3: Add the "Candidate frames" body section to the Phase 3 rollup spec**

In `commands/big-picture.md`, find the bullet line for "Research fronts" inside the Phase 3 body-sections list (search for `**Research fronts**`). After the full "Research fronts" bullet (which spans one paragraph ending at the next bullet), and before the "Knowledge Gaps (rollup)" bullet, insert a new bullet:

```markdown
- **Candidate frames** — one paragraph per hypothesis whose bundle has `phase == "candidate"`. Same citation, grounding, and length rules as the per-hypothesis files. If no candidates exist, emit a single line: `No candidate hypotheses.` Do not suppress the section. Active hypotheses are NOT mentioned here — they appear in the Arc and Research-fronts sections only.
```

- [ ] **Step 4: Clarify Arc partitioning**

In `commands/big-picture.md`, find the Phase 3 bullet for "Arc" (it currently reads "**Arc** — one paragraph per hypothesis, plus a framing paragraph on how the hypotheses relate."). Replace that bullet with:

```markdown
- **Arc** — one paragraph per **active** hypothesis (those whose bundle has `phase == "active"` or whose hypothesis file omits `phase:`), plus a framing paragraph on how the active hypotheses relate. Candidate hypotheses are not included here; they appear in the Candidate frames section below.
```

- [ ] **Step 5: Verify the file is well-formed and the new section appears in the expected order**

Run:
```bash
grep -n '\*\*\(TL;DR\|State\|Arc\|Research fronts\|Candidate frames\|Knowledge Gaps\|Emergent threads\)\*\*' commands/big-picture.md
```
Expected output (in this order):
```
... **TL;DR** ...
... **State** ...
... **Arc** ...
... **Research fronts** ...
... **Candidate frames** ...
... **Knowledge Gaps (rollup)** ...
... **Emergent threads** ...
```

- [ ] **Step 6: Commit**

```bash
git add commands/big-picture.md
git commit -m "feat(big-picture): partition rollup by hypothesis phase; add Candidate frames section"
```

---

## Task 5: End-to-end verification against the live repo

**Files:**
- None modified.

This task is verification-only. Confirms (a) no existing hypothesis is broken by the new validation, (b) the template renders, (c) the spec's natural-systems-guide adoption note (an H07 with `phase: candidate`) would render correctly.

- [ ] **Step 1: Run the full repository validator**

Run from `/mnt/ssd/Dropbox/science`:
```bash
bash scripts/validate.sh --verbose 2>&1 | tail -40
```
Expected: no new errors or warnings introduced by these changes. The bottom-line summary should be unchanged from a pre-change run modulo new informational lines.

- [ ] **Step 2: Run the full science-tool test suite**

Run:
```bash
cd science-tool && uv run --frozen pytest -x
```
Expected: all tests pass.

- [ ] **Step 3: Spot-check that an existing hypothesis still validates**

Pick any existing hypothesis under any project and confirm the validator does not emit a `phase` warning for it (since it has no `phase:` field). Example, using a project under the science repo if one exists, or skip this step if no project tree is checked out.

```bash
find . -path '*/specs/hypotheses/h*.md' -not -path '*/.venv/*' | head -3
```

If any are found, none should produce a `phase` warning when the validator runs against their containing project.

- [ ] **Step 4: Spot-check that the template's Promotion criteria section is correctly placed**

Run:
```bash
awk '/^## /{print NR": "$0}' templates/hypothesis.md
```
Expected: Promotion criteria appears between Falsifiability and Supporting Evidence.

- [ ] **Step 5: No commit (verification only)**

If everything passes, this task ends without a commit. If any step fails, return to the relevant earlier task.
