---
description: Research and summarize a scientific topic with project-context linking. Capability-first command surface; compatible with existing summarize-topic behavior.
---

# Research a Topic

Write a structured background synthesis on the topic specified by `$ARGUMENTS`.

## Compatibility Note

This command is the capability-first surface for topic-level synthesis.
`/science:summarize-topic` remains supported for backward compatibility and should follow the same behavior.

## Before Writing

1. Read `prompts/roles/research-assistant.md` if present; otherwise read `${CLAUDE_PLUGIN_ROOT}/references/role-prompts/research-assistant.md`.
2. Read the `research-methodology` skill.
3. Read the `scientific-writing` skill.
4. Read `templates/background-topic.md`.
5. Read `specs/research-question.md` for project context.
6. Check `doc/background/` for existing coverage; if present, ask whether to update or create a subtopic document.
7. Check `papers/summaries/` for existing relevant summaries.
8. If present, read `references/notes-organization.md`.
9. If present, read `templates/notes/topic-note.md` for compact note updates.
10. First-use compatibility: if `notes/topics/` is missing, create `notes/topics/` and `notes/index.md` before writing note outputs.

## Research Process

1. Start from LLM knowledge and draft core concepts, active debates, and project relevance.
2. Use web search to verify key references and capture recent changes.
3. Do not read PDFs unless user provides a file path.

## Writing

Follow `templates/background-topic.md` and fill all sections.
Save to `doc/background/NN-topic-name.md` with next sequential number.

The output should include:

- Key subtopics and how they connect.
- What is well-established vs uncertain.
- Links to existing hypotheses and open questions.
- Suggested follow-up research tasks.

## After Writing

1. Add new references to `papers/references.bib` (create with header if missing).
2. Update `doc/08-open-questions.md` with newly surfaced questions.
3. Update `RESEARCH_PLAN.md` with follow-up tasks derived from the synthesis.
4. Create or update `notes/topics/<topic-slug>.md` using `templates/notes/topic-note.md`.
5. Populate note metadata when available:
   - `ontology_terms` with relevant ontology CURIEs.
   - `datasets` with known associated dataset accessions.
6. Commit: `git add -A && git commit -m "doc: research topic <topic>"`
