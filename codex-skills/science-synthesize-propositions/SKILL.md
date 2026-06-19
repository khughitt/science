---
name: science-synthesize-propositions
description: "Propose the reasoning fields (predicate, polarity, claim_layer, refined subject/object) of a paper's promoted propositions, via the proposition-synthesize subagent."
---

# /synthesize-propositions

Converted from Claude command `/science:synthesize-propositions`.

## Science Codex Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load role prompt: `.ai/prompts/<role>.md` if present, else `references/role-prompts/<role>.md`.
3. Load the `science-research-methodology` and `science-scientific-writing` Codex skills. If native skill loading is unavailable, use `codex-skills/INDEX.md` to map canonical Science skill names to generated skill files and source paths.
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
8. **Resolve science CLI invocation:** When a command says to run `science`,
   prefer the project-local install path: `uv run science <command>`.
   This assumes the root `pyproject.toml` includes `science` as a dev
   dependency installed via `uv add --dev --editable "$SCIENCE_TOOL_PATH"`
   (the distribution is `science`; the entry point it installs is `science`).
   If that fails (no root `pyproject.toml` or science not in dependencies),
   fall back to:
   `uv run --with <science-plugin-root>/science science <command>`

Propose the *reasoning fields* — `predicate`, `polarity`, `claim_layer`, and refined
`subject` / `object` — of the promoted propositions for one paper, via the
`proposition-synthesize` subagent. The agent only proposes; the curator reviews and applies.

## Usage

`/synthesize-propositions <pmid|doi|citekey>`

## Workflow

1. **Resolve the paper** to its `<citekey>.source.md` path and the project `--root`. The paper's
   statements must already have been promoted into proposition entities
   (`science annotate promote`); this command fills the reasoning fields those propositions left
   unset, it does not promote.

2. **Dispatch the `proposition-synthesize` subagent** with `--source-md <path>`, `--root <root>`,
   and `--model <model-id>`. The subagent runs the **read-only scaffold**
   (`science annotate synthesize <path> --root <root> --format json`), reads each proposition's
   `current` fields + verbatim `statements` (+ non-authoritative `relation_hints`), and emits an
   **untrusted** candidates file — exactly one patch per proposition it can factor.

3. **Surface the report** the subagent returns (which propositions it factored, which fields it
   set, what it left untouched).

4. **Hand to the curator.** The flow is: read-only scaffold → agent emits candidates → curator
   reviews → curator applies. After reviewing the candidates file, the curator — not this command,
   not the agent — runs:

   ```bash
   uv run science annotate synthesize <path> --apply --input <candidates-file>
   ```

   `--apply` is a **curator action**.

## Notes

- The `proposition-synthesize-v1` source version (`llm-synth:<model>:proposition-synthesize-v1`)
  means a prompt/vocab/schema change later (a `v2` bump) re-establishes the source identity stamped
  into `PropositionEntity.reasoning_source` on apply.
- By default apply fills only **unset** fields; an already-set field is replaced only when the
  patch lists it in its `override` set. `reasoning_source` is never overrideable.
- For bulk runs, dispatch one subagent per paper (they are independent; the deterministic command
  serializes its own writes).
