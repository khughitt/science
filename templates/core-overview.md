<!--
core/overview.md — curated project orientation, loaded at session start.

Length cap: ~150 lines including this comment. If you exceed it, something
belongs in doc/ instead. The point of this file is to be the smallest thing
a fresh collaborator (human or agent) can read to be useful in five minutes.

Keep it durable. Avoid:
- duplicating science.yaml or README.md (those are loaded separately)
- pasting recent /science:status output (that's regenerated each session)
- play-by-play history (use git log + doc/meta/ for that)

Include only the judgment calls and context that machine-readable manifests
cannot capture.
-->

# Project Overview

## What this project is

<!-- One paragraph. Plain language. Resist jargon. -->

## Why it exists

<!-- The motivating problem and why this project's angle on it is the right one.
Two paragraphs max. -->

## Current state

<!-- Where the project is right now in 5-10 bullet points:
- what's working
- what's in flight
- what's blocked
- what was just decided

Update this section when the answer to "what should I work on next?" changes
materially. Stale entries here are worse than no entries. -->

## Open fronts

<!-- The 2-4 active workstreams or research threads, each in 2-3 lines:
- what the thread is going after
- what would count as progress
- what would count as a stop / pivot signal

These should match the active.md priorities. If they don't, one of them is
out of date. -->

## Domain context an outsider would miss

<!-- 3-7 bullets of "things every collaborator on this project ends up
needing to know but that aren't written down anywhere obvious." Examples:
- non-obvious data quirks ("GSE12345 has duplicated sample IDs across batches")
- terminology ("we use 'cohort' to mean X, not Y")
- conventions ("we report median not mean unless noted")
- ecological context ("upstream tool A and downstream consumer B both depend
  on the column-name contract in data/processed/")

This is the section that pays for itself fastest. Add to it whenever you
catch yourself explaining the same thing twice. -->

## Pointers

- Research question: `specs/research-question.md`
- Active tasks: `tasks/active.md`
- Recent next-steps: `doc/meta/next-steps-*.md` (most recent)
- Decisions log: `core/decisions.md`
- Knowledge graph: `knowledge/graph.trig`
