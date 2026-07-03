# Big Picture

This is the concise conceptual map of Science: its stance, its substrate, its
epistemic model, and its data model, each linking down to the detailed chapter
that owns the depth. Read it after the [Introduction](introduction.md) to get
oriented, then follow the `→ full detail` pointers when you need more.

This chapter is not the same as [Big-Picture Synthesis](big-picture-synthesis.md).
"Big Picture" is a conceptual map *of Science*; "Big-Picture Synthesis" is a
generated per-project report produced by `/science:big-picture` from a project's
own authored sources.

## Stance

Science is skeptical and data-driven by default. The creed:

- Open data is preferred over closed data; open literature over closed
  literature.
- Believe nothing until we have re-analyzed the data ourselves.
- Support from multiple independent datasets outweighs single-dataset support.
- Literature claims are *hints*, not facts. Belief updates from our own
  analyses, not from what a paper concluded.
- Uncertainty, contestation, and fragility stay visible. Fail early, prefer
  explicit over defensive, and never bury a weak result to make a dashboard look
  green.

The point is not to turn every claim green; it is to keep current support,
dispute, fragility, and missing evidence honest and inspectable.

→ full detail: [Introduction](introduction.md), [Epistemic Model](epistemic-model.md)

## The Substrate

Authored project files are the source of truth. That is mostly Markdown entity
files with YAML frontmatter, but also the bibliography, source records, sidecar
annotations, lightweight terms, and manifests. The knowledge graph, dashboard
summaries, belief snapshots, and health reports are all *derived views* over
those files. When a derived view is wrong, fix the source and rebuild the graph
— never hand-patch generated TriG under `knowledge/`.

The working model is a heterogeneous **patchwork** of small epistemic
neighborhoods, each a local cluster around one research concern (a question,
hypothesis, proposition, inquiry, dataset, or analysis result) rather than one
undifferentiated project graph. Beyond a single project, a **commons** holds
reusable canonical owners — shared datasets and reference graphs — and projects
recognize peers and synchronize shared knowledge without flattening away local
context.

→ full detail: [Science Model](science-model.md), [Cross-Project Work](cross-project-work.md)

## Epistemic Model & Key Players

Belief flows along a spine of typed players:

```text
question → hypothesis → proposition → observation / evidence-line →
belief → snapshot
```

- **question** frames what the project wants to learn.
- **hypothesis** organizes one or more propositions into a working conjecture;
  it is not supported just because it was written down.
- **proposition** is the primary truth-apt, belief-bearing assertion.
- **observation** is a concrete empirical finding or recorded datum.
- **evidence-line** is a durable line of support or dispute, tagged with
  provenance, role, strength, and independence, that bears on a proposition.
- **belief** is the derived reading of a proposition given its eligible
  evidence.
- **snapshot** persists that derived belief so state is comparable over time.

Evidence *supports* or *disputes* a proposition; it never *proves* it. That
spine is a teaching order, not a required one — real work starts from a paper, a
dataset, a failed analysis, or a health warning and loops through the same
players in whatever order the science demands.

Belief aggregation is an explicit, versioned policy (currently `core-default`
version 1), not an ad-hoc label. Evidence lines are reduced by independence
group and quality, clean support sets the ordinal magnitude, and decisive
refutations can cap stronger support down to `fragile`. An optional log-odds
scalar is a derived projection over that ordinal result. Two ceilings keep
weak inputs from overclaiming: authored assertions (`expert_judgment`) pass a
confidence gate but cannot by themselves exceed `fragile`, and empirical support
resting on a structurally QA-failed dataset is capped unless QA-clean support
stands on its own.

→ full detail: [Epistemic Model](epistemic-model.md), [Evidence Lines](evidence-lines.md)

## The Data Model

An `Entity` is a typed `kind:id` record — for example `hypothesis:h01-example`
or `dataset:gtex-v8` — stored as Markdown with YAML frontmatter, where the
frontmatter carries machine-readable identity and the body carries human
context. Relations connect entities: a question is addressed by a proposition,
an evidence line supports or disputes a proposition, a workflow run produces a
dataset. Per-kind facts (category, entity class, path policy, status vocabulary)
live in the built-in kind descriptors, which are the single source of truth that
tooling derives from. Entities fall into three classes: **epistemic** (uncertain
knowledge), **operational** (work products, sources, datasets, machinery), and
**reference** (concepts, variables, outcomes, and other referenced objects).

Datasets are described as a Frictionless Data Package. The runtime surface is
`datapackage.yaml` (a JSON `datapackage.json` is also accepted), and each
tabular resource can carry a typed Data Resource schema that is the source of
truth for its shape and QA inputs. Structural QA verdicts over those resources
feed back into belief through the dataset-QA ceiling.

→ full detail: [Entities](entities.md)
