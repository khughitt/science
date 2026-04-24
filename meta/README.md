# science-meta

Applying the Science toolkit to itself.

## Why this exists

The Science toolkit (`../science-tool/`, aspects, skills, commands, templates)
has grown organically through dogfooding on external research projects. It is
now mature enough to be a **research object in its own right**: how well does
its data model capture scientific practice? Are the causal-inference and
hypothesis-testing aspects correctly scoped? Does the research-agent's loop
produce defensible output? This project is the formal answer to those
questions.

## Two layers

### Software (primary)

Direct development of the toolkit: the research agent, knowledge graph,
causal-inference tooling, aspects, skills, and commands. This is where most
work has been and will continue to be. Tool code lives at `../science-tool/`
and siblings — this project tracks the **design intent, hypotheses, and
decisions** behind it.

### Research

An evidence-driven re-examination of the data / knowledge model, informed by
the scientific-process, knowledge-representation, and research-agent
literatures. Outputs land in:

- `doc/background/topics/` — topic syntheses
- `doc/background/papers/` — paper summaries
- `specs/hypotheses/` — falsifiable claims about design choices
- `doc/interpretations/` — what the evidence says about current model

## Workstreams (initial sketch)

1. **Tool development** — feature work, bugfixes, refactors. Bulk of commits.
2. **Knowledge model audit** — does the current ontology cover what scientists
   actually do? Where are the gaps?
3. **Research-agent evaluation** — when does the agent help, when does it
   mislead? What are the failure modes?
4. **Literature grounding** — pull in relevant prior art on causal-inference
   tooling, scientific-workflow systems, knowledge-graph research assistants.

## Getting started

```bash
cd meta
bash validate.sh --verbose
uv run --project ../science-tool science-tool --help
```

Use `/science:status` from inside `meta/` for orientation.
