---
name: science-health
description: "Run the science health check and triage findings interactively. Use when the user says \"check project health\", \"find issues\", \"what's broken\", or after running migrations."
user-invocable: true
---

# Health Triage

## Science Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load the `science-command-preamble` skill. Use its
   `references/role-prompts/research-assistant.md` role prompt and its aspect definitions.
3. Load the `science-scientific-writing` skill. For research methodology, read the `science-command-preamble` skill's `references/methodology-index.md` and load the relevant generated methodology router skills (e.g. `science-literature`, `science-literature`, `science-epistemics`).
4. Read project context from current entity roots:
   - `entities/questions/` for active research questions.
   - `entities/hypotheses/` for hypotheses.
5. **Load project aspects:** Read `aspects` from `science.yaml` (default: empty list).
   For each declared aspect, resolve the aspect file in this order:
   1. the `science-command-preamble` skill's `references/aspects/<name>/<name>.md` — canonical Science aspects
   2. `.ai/aspects/<name>.md` — project-local aspect override or addition

   If neither path exists (the project declares an aspect that isn't shipped with
   Science and has no project-local definition), do not block: log a single line
   like `aspect "<name>" declared in science.yaml but no definition found —
   proceeding without it` and continue. Suggest the user either (a) drop the
   aspect from `science.yaml`, (b) author it under `.ai/aspects/<name>.md`, or
   (c) align the name with one shipped under the `science-command-preamble` skill's `references/aspects/`.

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
   `references/templates/<name>.md`. If neither exists, warn the
   user and proceed without a template — the command's Writing section provides
   sufficient structure.
8. **Verify the project-local Science CLI:** Execute the top-level CLI
   Compatibility Gate below before the command's first Science invocation. It
   uses the consumer's frozen lock; do not route through a toolkit checkout or
   another environment.

## CLI Compatibility Gate

```bash
SCIENCE_REQUIRED_VERSION=0.3.0
if output=$(uv run --frozen science --version 2>&1); then
  SCIENCE_INSTALLED_VERSION=${output##* }
elif uv run --frozen science --help >/dev/null 2>&1; then
  # The CLI runs but has no --version option, so it predates the baseline.
  # Decided by behavior, never by matching Click's version-dependent wording.
  SCIENCE_INSTALLED_VERSION=
else
  # The CLI cannot run at all: missing/stale lock, Git fetch failure, import
  # error. Report the real diagnosis; never advise moving the Science pin.
  printf '%s\n' "$output" >&2
  exit 1
fi

if ! SCIENCE_INSTALLED_VERSION="$SCIENCE_INSTALLED_VERSION" \
     SCIENCE_REQUIRED_VERSION="$SCIENCE_REQUIRED_VERSION" \
     uv run --no-project python - <<'PY'
import os
import re
import sys

def release(name: str) -> tuple[int, int, int] | None:
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", name)
    return tuple(map(int, match.groups())) if match else None

installed = release(os.environ["SCIENCE_INSTALLED_VERSION"])
required = release(os.environ["SCIENCE_REQUIRED_VERSION"])
sys.exit(0 if installed is not None and required is not None and installed >= required else 1)
PY
then
  display=${SCIENCE_INSTALLED_VERSION:-unknown-or-pre-0.3.0}
  echo "This Science agent command requires science >=$SCIENCE_REQUIRED_VERSION; found $display." >&2
  echo "upgrade with: uv lock --upgrade-package science && uv sync --frozen" >&2
  exit 1
fi
```

After the gate succeeds, run the command through the consumer's project-local
environment as `uv run science <command>`. Missing dependency, missing or stale
lock, and Git fetch failures are surfaced directly and must be fixed in the
consumer project.

A CLI that answers `--help` but rejects `--version` predates the baseline;
malformed successful output and a version below the floor are likewise
compatibility failures, and all three stop with the upgrade command. A CLI that
cannot run at all is an environment failure: its output is printed verbatim and
must be fixed as reported.

The `--help` probe is what separates those two classes. Do not substitute a match
against Click's error text — its wording changed in Click 8.4, and `science`
allows any `click>=8.1`, so a freshly locked consumer can emit either form. The
root `--version` probe is the permanent bootstrap surface; do not replace it with
a preflight subcommand, which an older CLI could not recognize either.

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
- Project concept (`concept`, as an `entities/concepts/*.md` owner)
- Structured explanatory bundle (`mechanism`)
- Existing project kind (`question`, `hypothesis`, `interpretation`, `story`, `theme`)
- Metadata or prose-only note

Use the text after `topic:` only as a clue. Do not create `topic:*` stubs as
the default fix.

For legacy topic-shaped refs, user judgment hints can help route the cluster:
- Date-shaped values (`pivot-2026-03-18`): likely operational markers
- Pure short words (`science-bio`, `protein`): likely domain entities, concepts, or methods
- State-like (`blocked`, `phase3b`, `cycle1`): likely operational

For refs that look like legitimate new entities, read `references/docs/process/entity-creation-cookbook.md`
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
- Semantic triage: create or reuse the typed entity chosen by the cookbook, create a concept entity with `science entity create concept "<title>"` when a durable project-local concept is needed, rewrite as `meta:` or field-scoped `tag:` when the mention is classification metadata, or remove the graph ref and keep prose-only notes out of the graph.
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
  option. See [`../docs/user-guide/evidence-lines.md`](references/docs/user-guide/evidence-lines.md)
  → *Evidence Integrity (Non-Negotiable)*.
