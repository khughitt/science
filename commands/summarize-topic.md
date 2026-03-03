---
description: Write a structured background document on a scientific topic. Use when the user wants to research, summarize, or write about a topic for their research project.
---

# Summarize a Topic

> Compatibility alias: this command remains supported. Prefer `/science:research-topic` for the capability-first interface.

Write a structured background document on the topic specified by `$ARGUMENTS`.

## Before Writing

1. Read the `research-methodology` skill for source hierarchy and evaluation guidelines.
2. Read the `scientific-writing` skill for writing conventions.
3. Read `templates/background-topic.md` for the required document structure.
4. Check `specs/research-question.md` to understand the project context.
5. Check `doc/background/` — has this topic already been covered? If so, tell the user and ask if they want an update or a new document on a subtopic.
6. Check `papers/summaries/` for already-summarized relevant papers.

## Research Process

Follow the source hierarchy from the research-methodology skill:

1. **Start from LLM knowledge.** Write an initial draft covering key concepts, current state of knowledge, controversies, and relevance to this project.
2. **Supplement with web search.** Search for:
   - Recent developments (last 1-2 years)
   - Key facts to cross-check (author claims, specific results, methodological details)
   - Seminal papers you want to verify exist and cite correctly
3. **Do NOT read PDFs** unless the user has explicitly provided a file path.

## Writing

Follow the `templates/background-topic.md` structure. Fill every section.

Save to `doc/background/NN-topic-name.md` where NN is the next sequential number.

## After Writing

1. Add BibTeX entries for any new references to `papers/references.bib`. If the file doesn't exist yet, create it with a header comment:
   ```bibtex
   % references.bib — BibTeX database for this Science project
   % Use keys in the format: FirstAuthorLastNameYear (e.g., Smith2024)
   ```
2. Check if any findings are relevant to existing hypotheses in `specs/hypotheses/` — if so, note the connection.
3. If new questions emerge, add them to `doc/08-open-questions.md`.
4. If the topic connects to existing open questions, note that connection in the background doc.
5. Commit: `git add -A && git commit -m "doc: add background on <topic>"`
