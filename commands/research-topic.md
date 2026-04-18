---
description: Research and summarize a scientific topic with project-context linking.
---

# Research a Topic

Write a structured background synthesis on the topic specified by `$ARGUMENTS`.

## Dispatch Strategy

This command runs in two roles. Determine which you are before proceeding.

### If you are the orchestrator

(You received the `/research-topic` slash command directly from the user.)

1. **Pre-dispatch check:** Look at `doc/topics/` for existing coverage of the topic. If a file likely overlaps, ask the user whether to overwrite, skip, or produce a supplementary synthesis. Pass their decision into the subagent prompt.
2. **Dispatch** the `topic-researcher` subagent via the Agent tool:
   - `subagent_type: topic-researcher`
   - `description`: a short identifier for the topic
   - `prompt`: the full `$ARGUMENTS` plus the overwrite decision, plus any scope narrowing the user has hinted at
3. Do **not** perform the Setup / Research Process / Writing / After Writing steps below yourself — those are the subagent's job and dispatching preserves the cost savings this command exists for.
4. When the subagent reports back, continue at **Orchestrator Post-Dispatch** below.

### If you are the `topic-researcher` subagent

Skip the Dispatch Strategy section and execute Setup → Research Process → Writing → After Writing. Then report back per the response contract in your agent definition.

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
3. Commit: `git add -A && git commit -m "doc: research topic <topic>"`

Note: "Offer to create follow-up tasks via `science-tool tasks add`" is intentionally deferred to the orchestrator — it is a user-interactive step and the subagent cannot prompt the user directly.

## Orchestrator Post-Dispatch

After the subagent returns its report:

1. Review the scope the subagent settled on. If it narrowed too aggressively (or not enough), flag that to the user before moving on.
2. Review suggested follow-up research tasks in the subagent's report. Offer to create them via `science-tool tasks add`, grouping related items where sensible and including the rationale the subagent provided.
3. If the subagent flagged contradictions or open questions that overlap existing hypotheses in `specs/hypotheses/`, make small follow-up edits as a separate commit.
4. Read the written synthesis only if you need its content for downstream reasoning. Otherwise, trust the report.

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
