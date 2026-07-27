---
name: science-add-hypothesis
description: "Develop and refine a research hypothesis interactively. Use when the user wants to add a hypothesis, formalize a conjecture, or organize uncertain propositions around one research direction."
user-invocable: true
---

# Add a Hypothesis

## Science Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load the `science-command-preamble` skill. Use its
   `references/role-prompts/research-assistant.md` role prompt and its aspect definitions.
3. Load the `science-scientific-writing` skill. For research methodology, read the `science-command-preamble` skill's `references/methodology-index.md` and load the emitted methodology router skills that own the relevant leaf guidance (for example, load the `science-literature` skill for `literature-evaluation` and `literature-citation-discipline` guidance, and load the `science-epistemics` skill for `epistemics-proposition-graph-reasoning` guidance).
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

Develop a structured hypothesis from the user's input in the user input.

In this project, a hypothesis is an organizing conjecture, not a settled fact. Treat it as a bundle of uncertain propositions that may later gain or lose support.

## Setup


Additionally:
1. Read `references/docs/user-guide/epistemic-model.md`.
2. Read existing hypotheses in `entities/hypotheses/` to avoid duplication.
3. Check `entities/questions/` — the new hypothesis may address an existing open question.
4. Read `.ai/templates/hypothesis.md` first; if not found, read `references/templates/hypothesis.md`. Use hypothesis templates only after creation, as body-writing references.

## Interactive Refinement

Have a natural conversation with the user to develop the hypothesis. The questions below are guidelines — use judgment based on how much context the user has already provided.

### 1. Clarify the Conjecture
- What is the overall research idea?
- What are the main propositions inside it?
- Which propositions are causal, mechanistic, predictive, or descriptive?

Try to separate:
- the high-level hypothesis
- the concrete proposition units that would actually be tested

### 2. Define the Proposition Bundle

For each important proposition, identify:
- subject, predicate, and object when it is naturally relational
- whether it is best treated as `empirical_regularity`, `causal_effect`, `mechanistic_narrative`, or `structural_claim`
- what would count as supporting evidence
- what would count as disputing evidence
- whether the proposition is currently speculative, fragile, or already somewhat supported

If a proposition relies on an indirect proxy, note that early and record the likely `measurement_model` rather than treating the proxy as direct evidence.

### 3. Test for Falsifiability
- What evidence would materially lower confidence in this hypothesis?
- What observation or result would force revision of one of its key propositions?
- If the user cannot name a disconfirming result, the hypothesis needs to be sharper.

### 4. Identify Predictions And Evidence Needs
- If the hypothesis is useful, what downstream predictions follow?
- What empirical-data evidence, simulation evidence, or literature evidence would shift belief?
- What would be the most discriminating test?

If the hypothesis has genuinely competing structural readings, note the likely rival-model packet:
- shared observables
- discriminating predictions
- an optional `current_working_model` only if one already exists

### 5. Check Connections
- Does this relate to existing hypotheses, questions, or inquiries?
- Does it imply candidate propositions for the graph?
- Does it suggest a future inquiry or experiment?

## Writing

Create first, then draft. After the conversation, create the hypothesis with
`science hypotheses create`. `science hypotheses create` owns ID sequencing,
frontmatter, file placement, and prospective validation. The tool assigns the
next sequential `hNN` ID, places the file under `entities/hypotheses/`, and
writes canonical frontmatter (`id`, `kind`, `title`, `status`, `related`,
`source_refs`, `created`, `updated`). It also runs prospective validation
against the project's audit rules — unresolved references emit warnings,
structural problems block.

```bash
uv run science hypotheses create "<short title>" \
  --related <question:qNN-...> \
  --related <hypothesis:hMM-...> \
  --source-ref <paper-or-package-ref> \
  --origin user@<today> \
  --added-by user
```

The command prints the chosen ID (e.g. `hypothesis:h03-short-title`) and the file path. Do NOT pre-write the file or hand-pick the ID — let the tool sequence and validate. If the user wants a specific slug, pass `--slug <slug>`; if they need a literal ID, pass `--id hypothesis:<local-part>`.

Capture provenance at creation with `--origin` (repeatable) and `--added-by`:

- **user** — you/a collaborator proposed it: `--origin user@<today>`
- **literature** — from a paper: `--origin literature:paper:<key>@<pubdate>` (a
  bare BibTeX key is normalized to `cite:<key>`)
- **assistant** — a novel idea the AI reasoned up with no literature source:
  `--origin assistant`

More than one may apply (e.g. user-proposed but predated in the literature) —
pass `--origin` multiple times; dates establish priority. Set `--added-by user`
(this command is user-driven). Origins are **provenance only** — they never
affect how the hypothesis's evidence is weighed. For the rare
convergent-independent case, add `independent: true` to the relevant origin by
editing the created file's frontmatter — this is the one narrow exception to
"preserve the frontmatter `science` produced" below, because the `--origin
TYPE[:REF][@DATE]` CLI grammar has no way to express `independent`; every
other origin field is set via the CLI flags at creation.

After the file is created, open it and fill in the body using `.ai/templates/hypothesis.md` first, then `references/templates/hypothesis.md` as the writing reference. Preserve the frontmatter `science` produced; only edit the body. Use `science entity edit <ref>` (or `science entity edit <ref>`) for later metadata changes — both run prospective validation and update `updated` automatically.

Write the hypothesis as:
- one organizing conjecture
- a small set of explicit propositions
- a skeptical assessment of current uncertainty

Do not frame a single paper or result as proving the hypothesis.

### Naming Conventions

- **Filename:** lowercase `h` prefix: `h01-short-title.md`, `h02-short-title.md`, etc. (assigned by `science hypotheses create`).
- **Frontmatter `id`:** matches the filename stem: `"hypothesis:h01-short-title"`.
- **Prose references:** uppercase `H` prefix: `H01`, `H02`, etc.

### Body And Optional Frontmatter

`science hypotheses create` defaults `status` to `proposed`. The supported life-cycle values are `proposed`, `under-investigation`, `partially-supported`, `supported`, `weakened`, and `refuted`. Use `--status under-investigation` only if active testing is already underway. Avoid `supported`, `weakened`, or `refuted` as the default outcome of authoring a new hypothesis — those are evidence-based exit states.

`status` defaults to `active` (a committed frame). For a trial framing you are promoting to organize work but have not yet committed to, pass `--status draft`: this sets `status: draft` in the frontmatter *and* includes the otherwise-optional `## Promotion criteria` section, where you state what evidence or analytic outcome would justify promoting it to `active`.

`status` is the **lifecycle** (`draft | active | complete | superseded | retired | archived`) — what is being *done* with the hypothesis. What the *evidence says* is a separate field, `verdict` (`partially-supported | supported | weakened | refuted`), and it stays **absent until the evidence speaks**. Never infer one from the other: a refuted hypothesis you are still writing up is `status: active`, and a hypothesis retired for pragmatic reasons has no verdict at all.

Use optional layered-claim fields only when they reduce ambiguity, by editing the file body and frontmatter after creation:
- `claim_layer`
- `identification_strength`
- `measurement_model`
- `supports_scope` as a review hint, not as a graph override
- `rival_model_packet`

## After Writing

1. If the hypothesis addresses an open question, link it via `science entity edit <question-ref> --related hypothesis:h<NN>-<short-title>`. (Or update the question body in place if it needs prose changes.)
2. If the hypothesis naturally decomposes into graph-native propositions, note the likely propositions the user may want to formalize later.
3. Suggest 2-3 papers that may be relevant to testing this hypothesis.
Source-check titles and authors via web search before presenting them.
4. If the hypothesis is ready to be formalized in the graph, suggest `science-specify-model` skill.
5. If the user wants to design a test before running it, suggest `science-pre-register` skill.
6. Commit: `git add -A && git commit -m "hypothesis: add H<NN> - <short title>"`

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science feedback add \
  --target "command:add-hypothesis" \
  --category <friction|gap|guidance|suggestion|positive> \
  --summary "<one-line summary>" \
  --detail "<optional prose>"
```

Guidelines:
- One entry per distinct issue (not one big dump)
- If the same issue has occurred before, the tool will detect it and
  increment recurrence automatically
- Skip if everything worked smoothly — no feedback is valid feedback
- For template-specific issues, use `--target "template:<name>"` instead
