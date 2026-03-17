---
name: scientific-writing
description: Scientific writing conventions for research documents. This skill should be used whenever writing or editing research documents, background sections, paper summaries, hypothesis descriptions, overview documents, or any content in the doc/ directory. Also use when the user asks to write, draft, revise, or edit any scientific or technical prose, or when creating content that will be part of a research project's documentation.
---

# Scientific Writing

This skill defines writing conventions for documents within a Science project. Read this before writing or editing any document in `doc/` or `specs/`.

The default epistemic posture is skeptical:
- write hypotheses as organizing conjectures
- write claims as uncertain unless the evidence base is unusually strong
- describe evidence as supporting, disputing, or leaving a claim unresolved

## Voice and Tone

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

## Document Structure

All documents follow templates from the `templates/` directory. General structural principles:

- **Lead with the point.** First paragraph should state the main takeaway.
- **Sections are self-contained.** A reader should be able to read any section in isolation and get value.
- **Cross-reference liberally.** Link to other project documents: `(see [Background: Topic A](background/01-topic-a.md))`.
- **End with implications.** What does this mean for the project? What should we do next?

## Citation Format

- Inline: `[@AuthorYear]` using BibTeX keys from `papers/references.bib`
- Multiple: `[@Smith2020; @Jones2021]`
- With page: `[@Smith2020, p. 42]`
- Narrative: `Smith et al. [@Smith2020] found that...`

Every BibTeX key used in a document must have a corresponding entry in `papers/references.bib`. If you create a new citation, add the BibTeX entry.

## Connecting to the Project

When writing any document, actively connect the content to the project's research framework:

- Reference relevant **hypotheses** by ID: `(see Hypothesis H01)`
- Reference important **claims** or `relation_claim`s when they are the real unit being updated
- Note implications for **open questions** in `doc/questions/`
- Suggest updates to **next steps** when findings change priorities
- Flag any findings that affect the **causal model** in `models/`

Avoid writing as if one result has proved a hypothesis or validated an edge unless that standard is genuinely met.

For the project’s reasoning model, see `docs/claim-and-evidence-model.md`.

## Formatting Conventions

- Use ATX-style headers (`#`, `##`, `###`)
- One sentence per line in source (for better diffs)
- Use fenced code blocks with language tags for any code or data
- Tables for structured comparisons
- Bullet lists only when items are genuinely parallel; prefer prose otherwise

## Length Guidelines

- **Background topics** (`doc/topics/`): 500-1500 words. Comprehensive but focused.
- **Paper summaries** (`doc/papers/`): 300-800 words. Capture what matters for this project.
- **Hypothesis descriptions** (`specs/hypotheses/`): 300-1000 words. Thorough enough to be actionable.
- **Open questions** (`doc/questions/`): 50-200 words per question. Concise and specific.
- **Overview** (`doc/01-overview.md`): 500-1000 words. The "elevator pitch" for the whole project.
