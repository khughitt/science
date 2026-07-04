---
name: science-health
description: "Run the science health check and triage findings interactively. Use when the user says \"check project health\", \"find issues\", \"what's broken\", or after running migrations."
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
3. Load the `science-research-methodology` and `science-scientific-writing` Codex skills. If native skill loading is unavailable, use `codex-skills/INDEX.md` to map canonical Science skill names to generated skill files and source paths.
4. Read project context from layout-v3 entity roots first:
   - `entities/questions/` for active research questions.
   - `entities/hypotheses/` for hypotheses.
   - Read legacy specs/research-question.md only if it exists.
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
   | Files in `entities/hypotheses/` | `hypothesis-testing` |
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
8. **Resolve science CLI invocation:** When a command says to run `science`,
   prefer the project-local install path: `uv run science <command>`.
   This assumes the root `pyproject.toml` includes `science` as a dev
   dependency installed via `uv add --dev --editable "$SCIENCE_TOOL_PATH"`
   (the distribution is `science`; the entry point it installs is `science`).
   If you are operating from a git worktree and `uv run --frozen science ...`
   fails because a relative editable `tool.uv.sources` path resolves to a
   nonexistent checkout, use the main checkout's synced environment while
   keeping the worktree as the current directory:
   `$MAIN/.venv/bin/science <command>`. For wrappers or rules that shell out to
   nested `uv run --frozen ...`, export `UV_PROJECT=$MAIN` so dependencies
   resolve from the main checkout while cwd-relative project files still come
   from the worktree.
   If that fails (no root `pyproject.toml` or science not in dependencies),
   fall back to:
   `uv run --with <science-plugin-root>/science science <command>`

Aggregate project health diagnostics and walk the user through cluster-level cleanup.

the user input optionally specifies the project root (default: current directory).

## Procedure

### 1. Run the health command

```bash
uv run science health --project-root <root> --format=json
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
- **looks_like=question**: refs like `topic:q05` — likely mis-prefixed question IDs
- **looks_like=semantic-triage**: refs like `topic:genomics`, `topic:phase3b` — legacy topic refs that need semantic triage
- **looks_like=unknown**: anything else

For the `semantic-triage` cluster, sub-cluster by intended semantics:
- Catalog-backed entity (`gene`, `protein`, `disease`, `pathway`, etc.)
- Analytical method (`method`)
- Project concept (`concept`, as a lightweight `terms.yaml` row or a full `entities/concepts/*.md` owner)
- Structured explanatory bundle (`mechanism`)
- Existing project kind (`question`, `hypothesis`, `interpretation`, `story`, `theme`)
- Metadata or prose-only note

Use the text after `topic:` only as a clue. Do not create `topic:*` stubs as
the default fix.

For legacy topic-shaped refs, user judgment hints can help route the cluster:
- Date-shaped values (`pivot-2026-03-18`): likely operational markers
- Pure short words (`genomics`, `protein`): likely domain entities, concepts, or methods
- State-like (`blocked`, `phase3b`, `cycle1`): likely operational

For refs that look like legitimate new entities, read `docs/process/entity-creation-cookbook.md`
before proposing action. Apply its identity policy triage explicitly: check the
external-id requirement, decide whether the item belongs in a shared registry kind
or a project-local kind, and use the prose-only fallback when the mention should
remain prose rather than become a graph entity.

### 3. Present findings

Show a structured summary:

```
Health Report for <project>
================================
Unresolved References (N total):
  - 5 look like task IDs (would be better as task: refs)
  - 12 legacy topic-shaped refs need semantic triage
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

**Semantic-triage cluster:**
> "12 refs are legacy topic-shaped refs: topic:genomics, topic:protein, topic:embeddings, ... Triage them into catalog-backed entities, methods, concepts in terms.yaml, mechanisms, metadata, or prose-only notes?"

**Operational markers cluster:**
> "8 refs look like operational markers (phase, cycle, milestone): topic:phase3b, topic:cycle1, ... Rewrite as meta: refs (preserved as metadata, excluded from KG)?"

**Lingering tags cluster:**
> "M files still have `tags:` lines (residual from old templates). Remove the `tags:` lines, or replace each with the intended `meta:` or field-scoped `tag:` ref, by hand?"

### 5. Apply chosen actions

For each cluster the user approves, use the appropriate CLI to apply:
- Rewriting refs: edit frontmatter or task markdown directly (find files via the `sources` field of each ref)
- Semantic triage: create or reuse the typed entity chosen by the cookbook, add a lightweight term with `science terms add`, create a full concept entity with `science entity create concept "<title>"`, rewrite as `meta:` or field-scoped `tag:` when the mention is classification metadata, or remove the graph ref and keep prose-only notes out of the graph.
- Cleaning up lingering tags: remove the `tags:` lines from the frontmatter, or replace each with the intended `meta:` or field-scoped `tag:` ref, by hand

### 6. Verify

Re-run `science health` after applying actions to confirm the issue counts dropped. Show the user the delta.

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
- **Never clear a belief/evidence check by overstating evidence.** For `belief.fragile-single-line`
  and similar belief/validation warnings, do NOT relabel weak/indirect lines as `strong`/`direct_test`,
  split genuinely-dependent lines (same cohort/instrument/source) into separate `independence_group`s,
  or otherwise misrepresent stance/strength/independence to force a check green. The only valid moves
  are: add *genuine* independent evidence, correct an *actual* mislabeling, or accept the residual flag
  and record why. A check may legitimately stay yellow — never present "overstate to clear it" as an
  option. See [`../docs/user-guide/evidence-lines.md`](../docs/user-guide/evidence-lines.md)
  → *Evidence Integrity (Non-Negotiable)*.
