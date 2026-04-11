---
description: Research and summarize a scientific topic with project-context linking.
---

# Research a Topic

Write a structured background synthesis on the topic specified by `$ARGUMENTS`.

## Setup

Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role: `research-assistant`).

Additionally:
1. Read `.ai/templates/background-topic.md` first; if not found, read `${CLAUDE_PLUGIN_ROOT}/templates/background-topic.md`.
2. Check `doc/topics/` for existing coverage; ask before overwriting.
3. Check `doc/papers/` for relevant summaries.

## Research Process

1. Start from LLM knowledge and draft core concepts, active debates, and project relevance.
2. Use web search to verify key references and capture recent changes.
3. Do not read PDFs unless user provides a file path.

## Writing

Follow `.ai/templates/background-topic.md` first, then `${CLAUDE_PLUGIN_ROOT}/templates/background-topic.md`, and fill all sections.
Save to `doc/topics/<topic-slug>.md`.

The output should include:

- Key subtopics and how they connect.
- What is well-established vs uncertain.
- Links to existing hypotheses and open questions.
- Suggested follow-up research tasks.

If loaded aspects contribute additional sections (e.g., Tooling & Implementation from `software-development`), include them after the core sections.

## After Writing

1. Add new references to `papers/references.bib` (create with header if missing).
2. Add newly surfaced questions to `doc/questions/` using `.ai/templates/question.md` first, then `${CLAUDE_PLUGIN_ROOT}/templates/question.md`.
3. Offer to create follow-up tasks via `science-tool tasks add` derived from the synthesis.
4. Commit: `git add -A && git commit -m "doc: research topic <topic>"`

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science-tool feedback add \
  --target "command:research-topic" \
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
