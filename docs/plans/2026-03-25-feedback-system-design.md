# Centralized Feedback System — Design Spec

**Date:** 2026-03-25
**Status:** Approved

## Context

The science plugin uses a process reflection step at the end of each command to collect feedback about template friction, missing capture, guidance issues, suggestions, and things that worked well. Currently, feedback is appended to per-project `doc/meta/skill-feedback.md` files as unstructured markdown. A "Last reviewed" date tracks triage progress.

This approach doesn't scale: cross-project deduplication is manual, there's no structured querying, triage is O(n) in feedback volume, and recurrence tracking is prose-based ("3rd occurrence").

## Goal

Replace per-project markdown feedback files with a centralized, structured feedback system integrated into `science-tool`. Entries are stored as individual YAML files in `~/.config/science/feedback/`, queryable via CLI, and triageable by LLM agents.

## Design

### 1. Storage & File Format

**Location:** `~/.config/science/feedback/`

Each entry is a single YAML file named `{id}.yaml`. The ID format is `fb-YYYY-MM-DD-NNN` where NNN is a zero-padded sequence number per day (001, 002, etc.), determined by scanning existing files for that date.

Example file at `~/.config/science/feedback/fb-2026-03-25-001.yaml`:

```yaml
id: fb-2026-03-25-001
created: "2026-03-25"
project: seq-feats
target: "command:interpret-results"
category: suggestion
status: open
summary: "Add User Questions section to interpretation template"
detail: |
  Questions the user raised during interpretation are often the most
  insightful prompts. Record them as part of the interpretation rather
  than losing them to conversation history.
resolution: null
recurrence: 1
related: []
```

#### Entry Schema

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `id` | string | auto | — | `fb-YYYY-MM-DD-NNN` |
| `created` | string | auto | today | ISO date |
| `project` | string | no | auto-detected | Project that generated the feedback |
| `target` | string | yes | — | What the feedback is about (free-form with convention) |
| `category` | enum | no | `suggestion` | `friction`, `gap`, `guidance`, `suggestion`, `positive` |
| `status` | enum | auto | `open` | `open`, `addressed`, `deferred`, `wontfix` |
| `summary` | string | yes | — | One-line description, queryable |
| `detail` | string | no | null | Optional prose narrative |
| `resolution` | string | no | null | Filled when status changes (commit ref, reason) |
| `recurrence` | int | auto | 1 | Incremented when duplicates detected |
| `related` | list | no | [] | IDs of related entries |

#### Category Definitions

| Category | Meaning | Maps to old header |
|---|---|---|
| `friction` | Template/structure that felt forced, empty, or mismatched | Template/structure friction |
| `gap` | Information with no natural place to record it | Missing capture |
| `guidance` | Instructions that were confusing, contradictory, or unhelpful | Guidance issues |
| `suggestion` | Concrete proposal for improvement | Suggested improvement |
| `positive` | Something that worked well and should be preserved | What worked well |

#### Target Conventions

The target field is a free-form string. These conventions are documented but not enforced — new prefixes can emerge naturally:

| Prefix | Examples |
|---|---|
| `command:` | `command:interpret-results`, `command:next-steps` |
| `template:` | `template:interpretation`, `template:discussion` |
| `skill:` | `skill:data-management`, `skill:knowledge-graph` |
| `tool:` | `tool:science-tool`, `tool:graph-build` |
| `workflow:` | `workflow:triage`, `workflow:process-reflection` |

### 2. CLI Commands

New `feedback` command group under `science-tool` with 5 subcommands.

#### `science-tool feedback add`

```bash
science-tool feedback add \
  --target "command:interpret-results" \
  --category suggestion \
  --summary "Add User Questions section to template" \
  --detail "Questions the user raised during interpretation..." \
  --project seq-feats \
  --related fb-2026-03-22-003
```

- `--target` and `--summary` are required; everything else is optional
- `--project` defaults to the current project (the directory name of the nearest ancestor containing `science.yaml`, or the current directory name if none found; walk stops at `$HOME`)
- `--category` defaults to `suggestion`
- Generates the next available ID for today's date
- **Deduplication check:** Before creating, scans open entries with the same target. If either summary is a substring of the other (bidirectional check), in non-interactive mode auto-increments recurrence on the existing entry and adds a `related` link. In interactive mode, prompts: "Similar open entry exists: fb-2026-03-19-002. Increment recurrence instead? [Y/n]"

#### `science-tool feedback list`

```bash
science-tool feedback list                              # all open entries
science-tool feedback list --status open                # explicit status filter
science-tool feedback list --target "command:interpret-results"  # by target
science-tool feedback list --category friction           # by category
science-tool feedback list --project seq-feats           # by project
science-tool feedback list --format table|json            # output format
```

- Default: `--status open`, `--format table`
- `--target` supports `fnmatch` glob patterns (e.g., `command:*`, `template:*`)
- Multiple filters combine with AND
- Table output columns: id, date, project, target, category, summary, recurrence
- Sorted by recurrence (descending), then date

#### `science-tool feedback update`

```bash
science-tool feedback update fb-2026-03-25-001 \
  --status addressed \
  --resolution "commit:86e4f5a — added descriptive signal category"
```

- Updates any mutable field: `status`, `resolution`, `related`, `category`, `summary`, `detail`
- When setting status to `addressed`/`deferred`/`wontfix`, `--resolution` is required

#### `science-tool feedback triage`

```bash
science-tool feedback triage                            # all open, grouped
science-tool feedback triage --target "command:*"       # filter by target (fnmatch glob)
```

- Displays open entries grouped by target, sorted by recurrence within each group
- Shows recurrence count and cross-project spread (e.g., "3 projects, 5 reports")
- Non-interactive: outputs a structured table for LLM agent consumption
- The agent then calls `feedback update` for each item it addresses

#### `science-tool feedback report`

```bash
science-tool feedback report                            # all entries, markdown
science-tool feedback report --project seq-feats        # single project
science-tool feedback report --status addressed         # filter
```

- Generates human-readable markdown output (replacement for the old `doc/meta/skill-feedback.md`)
- Groups by target, shows status badges
- Can be redirected to a file if a project wants a local copy

### 3. Process Reflection Update

The process reflection step at the end of each command currently instructs agents to append a multi-section markdown block to `doc/meta/skill-feedback.md`. This is replaced with:

```markdown
After completing the task above, reflect on the template and workflow.
If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

    science-tool feedback add \
      --target "command:<this-command>" \
      --category <friction|gap|guidance|suggestion|positive> \
      --summary "<one-line summary>" \
      --detail "<optional prose>"

Guidelines:
- One entry per distinct issue (not one big dump)
- If the same issue has occurred before, the tool will detect it and
  increment recurrence automatically
- Skip if everything worked smoothly — no feedback is valid feedback
- For template-specific issues, use --target "template:<name>" instead
```

Commands with process reflection sections to update (16 total):
- `interpret-results`
- `next-steps`
- `discuss`
- `pre-register`
- `plan-pipeline`
- `review-pipeline`
- `research-paper`
- `research-topic`
- `bias-audit`
- `add-hypothesis`
- `compare-hypotheses`
- `critique-approach`
- `find-datasets`
- `search-literature`
- `sketch-model`
- `specify-model`

Note: existing commands have two variants of the process reflection block — a full template version (~35 lines with markdown code block) and a minimal version (~5 lines). Both are replaced with the same new block above.

### 4. Implementation Scope

**In scope:**

1. **New module:** `science-tool/src/science_tool/feedback.py` — YAML read/write, deduplication, filtering, grouping, report rendering
2. **CLI commands:** Added to `cli.py` as a new `@click.group()` — `add`, `list`, `update`, `triage`, `report`
3. **Process reflection update:** Update all 16 commands that have process reflection sections
4. **Tests:** Unit tests for `feedback.py` (CRUD, dedup, filtering, ID generation, report rendering)

**Out of scope:**

- Migration of existing feedback entries (~1300 lines across 3 projects). Old files remain as historical record; the new system starts fresh.
- Fuzzy deduplication (exact substring match is sufficient to start)
- Web UI or interactive TUI
- Integration with the knowledge graph (feedback entries are operational, not epistemic)

**Dependencies:**

- PyYAML (already a dependency)
- Click (already a dependency)
- No new dependencies needed

## Files Created / Modified

| File | Action |
|---|---|
| `science-tool/src/science_tool/feedback.py` | Create |
| `science-tool/src/science_tool/cli.py` | Modify (add feedback command group) |
| `science-tool/tests/test_feedback.py` | Create |
| `commands/interpret-results.md` | Modify (process reflection) |
| `commands/next-steps.md` | Modify (process reflection) |
| `commands/discuss.md` | Modify (process reflection) |
| `commands/pre-register.md` | Modify (process reflection) |
| `commands/plan-pipeline.md` | Modify (process reflection) |
| `commands/review-pipeline.md` | Modify (process reflection) |
| `commands/research-paper.md` | Modify (process reflection) |
| `commands/research-topic.md` | Modify (process reflection) |
| `commands/bias-audit.md` | Modify (process reflection) |
| `commands/add-hypothesis.md` | Modify (process reflection) |
| `commands/compare-hypotheses.md` | Modify (process reflection) |
| `commands/critique-approach.md` | Modify (process reflection) |
| `commands/find-datasets.md` | Modify (process reflection) |
| `commands/search-literature.md` | Modify (process reflection) |
| `commands/sketch-model.md` | Modify (process reflection) |
| `commands/specify-model.md` | Modify (process reflection) |
