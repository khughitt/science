---
name: science-health
description: "Run the science-tool health check and triage findings interactively. Use when the user says \"check project health\", \"find issues\", \"what's broken\", or after running migrations. Also use when the user explicitly asks for `science-health` or references `/science:health`."
---

# Health Triage

Converted from Claude command `/science:health`.

## Science Codex Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load role prompt: `.ai/prompts/<role>.md` if present, else `references/role-prompts/<role>.md`.
3. Load the `research-methodology` and `scientific-writing` skills.
4. Read `specs/research-question.md` for project context when it exists.
5. **Load project aspects:** Read `aspects` from `science.yaml` (default: empty list).
   For each declared aspect, resolve the aspect file in this order:
   1. `aspects/<name>/<name>.md` — canonical Science aspects
   2. `.ai/aspects/<name>.md` — project-local aspect override or addition

   If neither path exists (the project declares an aspect that isn't shipped with
   Science and has no project-local definition), do not block: log a single line
   like `aspect "<name>" declared in science.yaml but no definition found —
   proceeding without it` and continue. Suggest the user either (a) drop the
   aspect from `science.yaml`, (b) author it under `.ai/aspects/<name>.md`, or
   (c) align the name with one shipped under `aspects/`.

   When executing command steps, incorporate the additional sections, guidance,
   and signal categories from loaded aspects. Aspect-contributed sections are
   whole sections inserted at the placement indicated in each aspect file.
6. **Check for missing aspects:** Scan for structural signals that suggest aspects
   the project could benefit from but hasn't declared:

   | Signal | Suggests |
   |---|---|
   | Files in `specs/hypotheses/` | `hypothesis-testing` |
   | Files in `models/` (`.dot`, `.json` DAG files) | `causal-modeling` |
   | Workflow files, notebooks, or benchmark scripts in `code/` | `computational-analysis` |
   | Package manifests (`pyproject.toml`, `package.json`, `Cargo.toml`) at project root with project source code (not just tool dependencies) | `software-development` |

   If a signal is detected and the corresponding aspect is not in the `aspects` list,
   briefly note it to the user before proceeding:
   > "This project has [signal] but the `[aspect]` aspect isn't enabled.
   > This would add [brief description of what the aspect contributes].
   > Want me to add it to `science.yaml`?"

   If the user agrees, add the aspect to `science.yaml` and load the aspect file
   before continuing. If they decline, proceed without it.

   Only check once per command invocation — do not re-prompt for the same aspect
   if the user has previously declined it in this session.
7. **Resolve templates:** When a command says "Read `.ai/templates/<name>.md`",
   check the project's `.ai/templates/` directory first. If not found, read from
   `templates/<name>.md`. If neither exists, warn the
   user and proceed without a template — the command's Writing section provides
   sufficient structure.
8. **Resolve science-tool invocation:** When a command says to run `science-tool`,
   prefer the project-local install path: `uv run science-tool <command>`.
   This assumes the root `pyproject.toml` includes `science-tool` as a dev
   dependency installed via `uv add --dev --editable "$SCIENCE_TOOL_PATH"`.
   If that fails (no root `pyproject.toml` or science-tool not in dependencies),
   fall back to:
   `uv run --with <science-plugin-root>/science-tool science-tool <command>`

Aggregate project health diagnostics and walk the user through cluster-level cleanup.

the user input optionally specifies the project root (default: current directory).

## Procedure

### 1. Run the health command

```bash
uv run science-tool health --project-root <root> --format=json
```

Parse the JSON output. Fields:
- `unresolved_refs`: list of `{target, mention_count, sources, looks_like}`
- `lingering_tags_lines`: list of `{file, values}`
- `layered_claims`: object with:
  - `proposition_claim_layer_coverage`
  - `causal_leaning_identification_coverage`
  - `rival_model_packets_missing_discriminating_predictions`
  - `migration_issues`

### 2. Cluster issues

Group `unresolved_refs` by `looks_like` heuristic:
- **looks_like=task**: refs like `topic:t143`, `topic:t146` — likely mis-prefixed task IDs
- **looks_like=hypothesis**: refs like `topic:h01` — likely mis-prefixed hypothesis IDs
- **looks_like=semantic-triage**: refs like `topic:genomics`, `topic:phase3b` — these need semantic reclassification, not default topic stubs
- **looks_like=unknown**: anything else

For the `semantic-triage` cluster, sub-cluster by user judgment hint:
- Date-shaped values (`pivot-2026-03-18`): likely operational markers
- Pure short words (`genomics`, `protein`): likely domain entities, methods, or concepts
- State-like (`blocked`, `phase3b`, `cycle1`): likely operational

### 3. Present findings

Show a structured summary:

```
Health Report for <project>
================================
Unresolved References (N total):
  - 5 look like task IDs (would be better as task: refs)
  - 12 need semantic triage (domain entity / method / concept / mechanism candidate)
  - 8 look like operational markers (consider meta: prefix)

Lingering tags: lines: M files

Total issues: X
```

Include the layered-claim section explicitly:

- authored `claim_layer` coverage across propositions
- authored `identification_strength` coverage across causal-leaning propositions
- unsupported mechanistic narratives still lacking lower-layer support
- proxy-mediated propositions still lacking `measurement_model`
- rival-model packets missing discriminating predictions

If the project is using `independence_group` on only one visible support line for a high-impact proposition, mention that as a fragility note even if it is still being surfaced manually rather than by a dedicated metric.

### 4. Propose batch actions

For each cluster, propose ONE action covering the whole cluster, not per-ref decisions. Examples:

**Task-id cluster:**
> "5 refs look like task IDs being mis-prefixed: topic:t143, topic:t146, topic:t147, topic:t149, topic:t150. Rewrite all as task: refs?"

**Semantic triage cluster:**
> "12 refs need semantic reclassification: topic:genomics, topic:protein, topic:embeddings, ... Triage these into domain entities, methods, concepts, mechanism candidates, or meta: refs?"

**Operational markers cluster:**
> "8 refs look like operational markers (phase, cycle, milestone): topic:phase3b, topic:cycle1, ... Rewrite as meta: refs (preserved as metadata, excluded from KG)?"

**Lingering tags cluster:**
> "M files still have `tags:` lines (residual from old templates). Run `science-tool graph migrate-tags --apply` to clean them up?"

### 5. Apply chosen actions

For each cluster the user approves, use the appropriate CLI to apply:
- Rewriting refs: edit frontmatter or task markdown directly (find files via the `sources` field of each ref)
- Reclassifying semantic refs: rewrite to domain/entity refs, `method:`, `concept:`, `mechanism:`, or `meta:` as appropriate
- Migrating tags: `science-tool graph migrate-tags --apply` (default meta:)
- Migrating tags as topics: `science-tool graph migrate-tags --apply --as-topic` only for audited legacy projects

### 6. Verify

Re-run `science-tool health` after applying actions to confirm the issue counts dropped. Show the user the delta.

### 7. Commit

```bash
git add <changed files>
git commit -m "chore(health): triage <N> issues — <brief description per cluster>"
```

## Tips

- ALWAYS propose at the cluster level, never per-ref. The user shouldn't make 47 decisions.
- ALWAYS get confirmation before applying changes.
- For ambiguous clusters, ask the user to classify before proposing actions.
- The `looks_like` heuristic is just a hint — let the user override it if they disagree.
