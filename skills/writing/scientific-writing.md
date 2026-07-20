---
name: scientific-writing
description: Scientific writing conventions for research documents. This skill should be used whenever writing or editing research documents, background sections, paper summaries, hypothesis descriptions, overview documents, or any content in the doc/ directory. Also use when the user asks to write, draft, revise, or edit any scientific or technical prose, or when creating content that will be part of a research project's documentation.
archetype: practice-guide
provenance: internal
---

# Scientific Writing

Answers: how do I write project prose that is correctly hedged, sourced, and
connected to the research framework?

## When to apply

Before writing or editing any document in `doc/` or `specs/`, any entity
description, or any prose that will become part of the project's durable
record.

The default epistemic posture is skeptical:
- write hypotheses as organizing conjectures
- write propositions as uncertain unless the evidence base is unusually strong
- describe evidence as supporting, disputing, or leaving a proposition unresolved

## Workflow steps

1. **Check the project first.** Before writing any document, check:
1. `specs/research-question.md` — What is this project about?
2. `entities/hypotheses/` — What hypotheses are we tracking?
3. `entities/questions/` — What questions are we trying to answer?
4. `doc/background/papers/` — What have we already reviewed?
5. `doc/background/topics/` — What topics have we already covered?

This prevents duplication and ensures new work connects to the existing knowledge base.
2. **Read the template.**
All research documents must follow their corresponding framework template unless the project defines a specific override in `.ai/templates/`. Read the relevant template before writing. The template sections are not optional — fill every section, even if briefly.
3. **Draft, hedging to the evidence.** Apply the judgment rules below.
4. **Mark what you could not source.** When a claim cannot carry an in-line citation, mark it with one of the four annotation tokens defined in `docs/conventions/annotation-tokens.md`: `[UNVERIFIED]`, `[MISSING_CITATION]`, `[SPECULATION]`, `[INACCESSIBLE]`. That document is the normative owner of the vocabulary and the validator behavior; do not restate the definitions here.
5. **Connect the document to the framework.**
- Reference relevant **hypotheses** by ID: `(see Hypothesis H01)`
- Reference important **propositions** when they are the real unit being updated
- Note implications for **open questions** in `entities/questions/`
- Suggest updates to **next steps** when findings change priorities
- Flag any findings that affect the **causal model** in `models/`

Avoid writing as if one result has proved a hypothesis or validated an edge unless that standard is genuinely met.

## Judgment rules

- **Precise.** Choose words carefully. "The model predicts" is different from "the model suggests."
- **Evidence-based.** Every substantive claim should reference evidence or be explicitly marked as conjecture.
- **Appropriately hedged.** Use "suggests," "indicates," "is consistent with," or "supports" for uncertain findings. Use stronger language only when the evidence base is genuinely strong and replicated.
- **Active voice preferred.** "Smith et al. demonstrated" over "It was demonstrated by Smith et al."
- **Concise.** Cut unnecessary words. Avoid throat-clearing introductions.

## Hedging Guide

| Confidence Level | Language |
|---|---|
| Strong evidence, replicated | "X strongly supports / provides strong evidence for" |
| Good evidence, limited scope | "X supports / indicates" |
| Suggestive evidence | "X suggests / points toward / is consistent with" |
| Preliminary / weak | "X may indicate / could suggest / tentatively supports" |
| Speculation | "One possibility is / It is conceivable that / We hypothesize" |

## Quality criteria

All documents follow framework templates unless the project defines an override in `.ai/templates/`. General structural principles:

- **Lead with the point.** First paragraph should state the main takeaway.
- **Sections are self-contained.** A reader should be able to read any section in isolation and get value.
- **Cross-reference liberally.** Link to other project documents, for example `(see Background: Topic A)`.
- **End with implications.** What does this mean for the project? What should we do next?
- Use ATX-style headers (`#`, `##`, `###`)
- One sentence per line in source (for better diffs)
- Use fenced code blocks with language tags for any code or data
- Tables for structured comparisons
- Bullet lists only when items are genuinely parallel; prefer prose otherwise
- **Background topics** (`doc/background/topics/`): 500-1500 words. Comprehensive but focused.
- **Paper summaries** (`doc/background/papers/`): 300-800 words. Capture what matters for this project.
- **Hypothesis descriptions** (`entities/hypotheses/`): 300-1000 words. Thorough enough to be actionable.
- **Open questions** (`entities/questions/`): 50-200 words per question. Concise and specific.
- **Overview** (`doc/01-overview.md`): 500-1000 words. The "elevator pitch" for the whole project.

## Common pitfalls

- Hedging language that outruns the evidence → match the hedge to the tier in the table, not to how confident the sentence sounds.
- Writing a document with no connection to a hypothesis or question → check the project before drafting, not after.
- Restating the annotation-token definitions locally → point at `docs/conventions/annotation-tokens.md`; a second copy drifts.
- Passive throat-clearing openings → lead with the point in the first paragraph.

## Outputs

A document conforming to its framework template, with every substantive claim
either cited or annotated, hedging matched to evidence strength, and explicit
links to the hypotheses, questions, or propositions it bears on.

## Success test

Did the agent carry out the cross-cutting practice according to its workflow, judgment rules, and quality criteria?

## Companion Skills

- [`../research/citation-discipline.md`](../research/citation-discipline.md) - citation format, bibliography keys, and source-pointer conformance.
- [`../research/literature-evaluation.md`](../research/literature-evaluation.md) - selecting and assessing the sources this prose cites.
- [`../statistics/SKILL.md`](../statistics/SKILL.md) - statistical reporting language for pre-registrations, analyses, and verdicts.
- [`../INDEX.md`](../INDEX.md) — the skill index.

For the project's reasoning model, see `docs/user-guide/epistemic-model.md`.
