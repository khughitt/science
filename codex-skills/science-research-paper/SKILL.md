---
name: science-research-paper
description: "Research and summarize a single scientific paper. Also use when the user explicitly asks for `science-research-paper` or references `/science:research-paper`."
---

# Research a Paper

Converted from Claude command `/science:research-paper`.

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
   For each aspect, read `aspects/<name>/<name>.md`.
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

Research and summarize the paper specified by the user input.
The input may be a paper title, author name(s), DOI, URL, or a file path to a PDF.

## Setup

Follow the Science Codex Command Preamble before executing this skill. Use the `research-assistant` role prompt.

Additionally:
1. Read `.ai/templates/paper-summary.md` first; if not found, read `templates/paper-summary.md`.
2. Check `doc/papers/` for existing summary; ask before overwriting.

## Source Strategy

Follow the source hierarchy strictly:

### If given a paper title, authors, or DOI:

1. Start from LLM knowledge.
2. Cross-check key facts via web search:
   - Author list and affiliations
   - Publication year and venue
   - Specific quantitative results that matter to project decisions
   - Method details relevant to reproducibility
3. Mark uncertain details as `[UNVERIFIED]`.

### If given a PDF file path:

1. Read: Abstract, Introduction, Methods, Results, Discussion/Conclusion.
2. Skip: References, supplemental materials, acknowledgments unless needed.
3. Extract required template fields.
4. Cross-check key metadata when possible.

### If given a URL:

1. Fetch metadata/abstract from the URL.
2. Supplement with LLM context.
3. Cross-check key facts.
4. **If the URL returns a paywall, 403, or redirect loop:** fall back to DOI resolution → PubMed/preprint search (bioRxiv, arXiv, SSRN) → press coverage → GitHub README/repo. Do not abandon the paper — most paywalled papers have accessible metadata through alternative channels. Note the fallback source in the `Source:` frontmatter field.

### If the paper cannot be found:

1. State that the paper could not be identified reliably.
2. Ask for full title, first author, year, venue, or DOI.
3. Ask for a PDF path if available.
4. Do not fabricate a summary.

## Writing

Follow `.ai/templates/paper-summary.md` first, then `templates/paper-summary.md`, and fill every section.

- Include frontmatter `Source:` describing provenance (`LLM knowledge`, `web search`, `PDF`, or combination).
- Generate BibTeX key as `FirstAuthorLastNameYear` (with suffix if needed).
- Save to `doc/papers/<citekey>.md`.

## After Writing

1. Add/update the BibTeX entry in `papers/references.bib` (create file with header if missing).
2. Link relevance to existing hypotheses in `specs/hypotheses/`.
3. Add new questions to `doc/questions/` using `.ai/templates/question.md` first, then `templates/question.md` when appropriate.
4. Note approach implications in `doc/04-approach.md` when relevant.
5. Commit: `git add -A && git commit -m "papers: research <citekey> - <short title>"`

## Batch Processing

When processing multiple papers in a single session (2+ papers with a shared thematic connection), after all individual summaries are written:

1. Produce a brief cross-paper synthesis document at `doc/papers/synthesis-YYYY-MM-DD-<theme>.md`.
2. Contents: shared themes, tensions between papers, and combined implications for the project.
3. Cross-reference the individual paper summaries by their `id` fields.

This only applies when papers share a thematic connection. Unrelated papers processed in the same session do not need synthesis.

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science-tool feedback add \
  --target "command:research-paper" \
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
