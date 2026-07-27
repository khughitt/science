---
name: science-review
description: "Scrutinize one or more epistemic entities (hypothesis, proposition, interpretation, report) for claim-vs-operationalization drift, leaky or overstated language, eroded falsifiability, and unincorporated open questions, then record an artifact-guarded review. Use when an entity looks settled but is heavily caveated or carries open-question debt, or on a periodic sweep of the attention ranking."
user-invocable: true
---

# Entity Review

## Science Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load the `science-command-preamble` skill. Use its
   `references/role-prompts/research-assistant.md` role prompt and its aspect definitions.
3. Load the `science-scientific-writing` skill. For research methodology, read the `science-command-preamble` skill's `references/methodology-index.md` and load the relevant generated methodology router skills (e.g. `literature-evaluation`, `literature-citation-discipline`, `epistemics-proposition-graph-reasoning`).
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

Review load-bearing (epistemic) entities for drift between what they claim and what their
evidence and operationalization actually support. Targets failure mode A
(scope/operationalization drift) and the residue of B/C that static checks cannot
adjudicate. Current behavior and residual backlog are checkpointed in
`references/docs/audits/plans-cleanup/2026-07-01-final-root-plan-checkpoint.md`; the
historical design is
`references/docs/plans/historical/2026-06-04-epistemic-drift-detection-design.md`. See also
`science-meta:question:15-claim-operationalization-drift`.

Use the user input to scope the review to specific epistemic entities. If no scope is given,
pull the top of the attention ranking. If the user input names an operational entity such as
`dataset:*`, `paper:*`, `workflow:*`, `workflow-run:*`, `task:*`, `plan:*`, or
`pre-registration:*`, do not stamp it with `entity review`; follow it only as evidence or
manifest context for the epistemic claim under review.

## Setup

Load the `scientific-writing` skill. For research methodology, read the `science-command-preamble` skill's `references/methodology-index.md` and load the leaves relevant to the task (e.g. `literature-evaluation`, `literature-citation-discipline`, `epistemics-proposition-graph-reasoning`).

## Selecting targets

If the user input names epistemic entities, review exactly those. Otherwise pull the
deterministic attention ranking (rows carry `open_question_debt` and reason codes):

```
science graph attention-rank --limit 15 --format json
```

Prefer the conjunction that names the blind spot — settled-looking but overdue and
indebted. Rank by, in order: `open_question_debt` desc, then `needs-review`/`stale`
freshness, then `status: supported` / high-confidence with an old `last_reviewed`.
Independent entities may be reviewed in parallel (one sub-agent per entity, mirroring
`big-picture`'s per-hypothesis fan-out). Do not parallelize entities that cite each other.

## Per-kind rubric

For every epistemic kind, check: does the stated scope exceed what is actually
operationalized/measured? Is the language leaky or overstated relative to the evidence?
Are there open questions (debt statuses: `active` / `partially-answered` / `deferred`)
related to this entity, or sharing a theme, that have never been folded into its claims?

- **hypothesis:** scope vs operationalization (enumerate what the pipeline/code actually
  measures and compare to the prose claim); falsifiability still crisp and testable;
  confidence rating justified by *current* evidence, not legacy; high-risk or edge cases
  the framing silently excludes.
- **proposition:** claim layer and identification strategy still accurate; evidence stance
  (supports/disputes balance) current; not over-generalized beyond its tested contexts.
- **interpretation:** conclusions still match the cited evidence and effect sizes; no
  drift between the headline reading and the underlying numbers.
- **report:** headline claims still match the entities they summarize; no inherited
  overstatement from a since-narrowed source entity.

**Decisions are out of scope for now.** `decision` is not a registered entity kind;
decisions live as `##` sections in `core/decisions.md` without their own `review_state`.
Do not run `entity review` on a decision. If a review surfaces a stale or code-contradicted
decision, record it as a finding/task and flag it for the future decision-review path.

**Operational entities are context, not review targets.** `dataset`, `paper`, `workflow`,
`workflow-run`, `research-package`, `task`, `plan`, and `pre-registration` are operational
in the core registry. Inspect them for manifests, evidence, provenance, and contradiction
checks, but record the review on the epistemic entity whose claim depends on them.

## Recording the review (artifact-required)

A review MUST emit a concrete artifact before the timestamp is set — never a bare bump:

1. **Finding / overstatement:** edit the entity to qualify or narrow the claim, or open a
   task (`science tasks add ...`) capturing the data-dependent follow-up.
2. **Prose-vs-code contradiction (mode B):** correct the prose and cite the authoritative
   manifest (e.g. a code constant such as `constants.py::EVENTS`).
3. **Unincorporated question (mode C):** fold it into the claim, or explicitly link/defer
   it with a reason.
4. **No change warranted:** record the *reasoning* for why no change is needed.

Then stamp the review with the artifact as the note:

```
science entity review <kind>:<id> --note "<finding | diff summary | task id | reasoned no-change>"
```

The command refuses an empty `--note` — that guard is what keeps this review honest.
