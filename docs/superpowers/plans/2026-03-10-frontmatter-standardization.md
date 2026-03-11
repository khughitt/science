# Frontmatter Standardization Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate 3 templates from inline metadata to standardized YAML frontmatter, standardize discussion.md's frontmatter, remove 2 obsolete templates, update corresponding commands and validate.sh.

**Architecture:** Each template migration has two parts: update the template file, then update the command that uses it to populate the new frontmatter fields. The standardized format matches `templates/background-topic.md` (id, type, title, status, tags, source_refs, related, created, updated). Domain-specific fields that don't map to the common set become additional frontmatter fields (not inline bullets).

**Tech Stack:** Markdown, YAML frontmatter, bash (validate.sh)

**Spec:** Design spec section 3.3 (Standardize Document Frontmatter) from `docs/superpowers/specs/2026-03-10-reasoning-and-coherence-design.md`

**Status: COMPLETE** — All 5 tasks executed and committed, plus deferred inquiry.md migration and one-time migration of 3 existing projects. See commit log below.

---

## Scope

### Templates to migrate (3):
| Template | Used by | Current format | Status |
|---|---|---|---|
| `hypothesis.md` | `add-hypothesis` | Inline bullets (ID, Status, Related, Date) | Done (Task 2) |
| `interpretation.md` | `interpret-results` | Inline bullets (Date, Inquiry, Input) | Done (Task 4) |
| `discussion.md` | `discuss` | YAML but non-standard fields; heading before frontmatter | Done (Task 3) |

### Templates removed (2):
| Template | Reason | Status |
|---|---|---|
| `open-question.md` | Superseded by `question.md` (already has YAML frontmatter). Zero references in codebase. | Done (Task 1) |
| `data-source.md` | Superseded by `dataset.md` (already has YAML frontmatter). Zero references in codebase. | Done (Task 1) |

### Deferred:
| Template | Reason |
|---|---|
| `inquiry.md` | Used programmatically by `science-tool` Python code (`store.py:render_inquiry_doc()`). Migrating the template alone creates an inconsistency — the Python code must also be updated to emit YAML frontmatter. Deferred to a code change. |

### Already standardized (no changes needed):
`background-topic.md`, `search-run.md`, `question.md`, `dataset.md`, `pre-registration.md`, `comparison.md`, `bias-audit.md`, `experiment.md`, `pipeline-step.md`, `paper-summary.md`

---

## Commit Log

| Task | Commit | Description |
|---|---|---|
| Task 1 | `2d18781` | Remove obsolete templates (open-question.md, data-source.md) |
| Task 2 | `86e2319` | Migrate hypothesis template to YAML frontmatter |
| Task 3 | `0aee818` | Standardize discussion template frontmatter |
| Task 4 | `64c652f` | Migrate interpretation template to YAML frontmatter |
| Task 5 | `5bc13d0` | Add frontmatter cross-reference validation to validate.sh |
| Post-plan | `e805993` | Migrate inquiry template + render_inquiry_doc to YAML frontmatter |
| Post-plan | `b383262` | Migrate seq-feats documents (18 files) |
| Post-plan | `24d0760` | Migrate 3d-attention-bias documents (4 files) |
| Post-plan | `17f59ae` | Migrate natural-systems-guide documents (17 files) |

---

## Chunk 1: Template Migrations and validate.sh

### Task 1: Remove obsolete templates

**Files:**
- Delete: `templates/open-question.md`
- Delete: `templates/data-source.md`

- [x] **Step 1: Verify no references exist**
- [x] **Step 2: Delete the files**
- [x] **Step 3: Commit**

---

### Task 2: Migrate hypothesis.md to YAML frontmatter

**Files:**
- Modify: `templates/hypothesis.md`
- Modify: `commands/add-hypothesis.md`
- Modify: `scripts/validate.sh`

- [x] **Step 1: Rewrite the template** — Added standard frontmatter fields (id, type, title, status, tags, source_refs, related, created, updated)
- [x] **Step 2: Update add-hypothesis command** — Replaced "In-document ID" / "Setting Initial Status" with "Frontmatter `id`", "Prose references", and "Populating Frontmatter" subsections
- [x] **Step 3: Update validate.sh hypothesis Status check** — Accepts both YAML `status:` and inline `- **Status:**`
- [x] **Step 4: Commit**

---

### Task 3: Standardize discussion.md frontmatter

**Files:**
- Modify: `templates/discussion.md`
- Modify: `commands/discuss.md`
- Modify: `scripts/validate.sh`

- [x] **Step 1: Rewrite the template** — Added common fields (id, type, tags, source_refs, related, created, updated) alongside domain-specific fields (focus_type, focus_ref, mode). Removed non-standard heading/blockquote before frontmatter.
- [x] **Step 2: Update validate.sh discussion section check** — Removed false-positive `## Alternative Explanations / Confounders` check (never existed in template)
- [x] **Step 3: Update discuss command** — Added frontmatter population guidance
- [x] **Step 4: Commit**

---

### Task 4: Migrate interpretation.md to YAML frontmatter

**Files:**
- Modify: `templates/interpretation.md`
- Modify: `commands/interpret-results.md`

- [x] **Step 1: Rewrite the template** — Added standard frontmatter + domain-specific `input` field. Preserved all existing section content (signal categories, aspect comments, detailed guidance).
- [x] **Step 2: Update interpret-results command** — Added frontmatter population guidance (id, related, source_refs, input, dates)
- [x] **Step 3: Commit**

---

### Task 5: Add frontmatter cross-reference validation to validate.sh

**Files:**
- Modify: `scripts/validate.sh`

- [x] **Step 1: Read validate.sh to find insertion point** — Added as section 16, after Task queue (15) and before Summary
- [x] **Step 2: Add frontmatter cross-reference validation** — Python3 heredoc with env vars (avoids shell quoting issues). Scans `$SPECS_DIR/hypotheses/` and `$DOC_DIR/` for `id:` fields, validates `related:` references against collected IDs. Handles both inline `[...]` and multi-line YAML list formats.
- [x] **Step 3: Commit**

**Implementation note:** The plan originally used `python3 -c "..."` with embedded quotes, but shell quoting of single quotes inside double-quoted Python regex caused syntax errors. Switched to heredoc (`python3 << 'PYEOF'`) with env vars (`XREF_SPECS`, `XREF_DOC`) to pass shell variables cleanly.

---

## Post-Plan: inquiry.md Migration (Done)

Originally deferred because `render_inquiry_doc()` in `store.py` hardcodes the document format. Completed as a coordinated change:

- **Template:** Added YAML frontmatter (id, type, title, status, tags, source_refs, related, created, updated, target) + `## Unknowns` section (was in code but missing from template)
- **Python:** Updated `render_inquiry_doc()` to emit YAML frontmatter instead of inline bullets
- **Tests:** Updated 2 tests in `TestInquiryRender` to assert frontmatter presence
- **Commit:** `e805993`

---

## Post-Plan: Existing Project Migration (Done)

One-time migration of 39 documents across 3 projects using a disposable Python script:

| Project | Hypotheses | Interpretations | Discussions | Inquiries | Total | Commit |
|---|---|---|---|---|---|---|
| `seq-feats` | 4 | 8 | 5 (3 standardized, 2 converted) | 1 | 18 | `b383262` |
| `3d-attention-bias` | 2 | 0 | 0 | 2 | 4 | `24d0760` |
| `natural-systems-guide` | 0 | 11 | 6 (all standardized) | 0 | 17 | `17f59ae` |

Domain-specific inline bullets (Models, Features, Controls, etc.) were preserved below the heading. Standard fields (Date, Status, ID) moved to YAML frontmatter.
