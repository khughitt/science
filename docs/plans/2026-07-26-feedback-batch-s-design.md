# Feedback Batch S — the silent-reader cluster

Four filings, one doctrine: **an instrument that cannot see its input must not
report a clean result.** Each entry is a reader that resolves the wrong
location, or no location, and returns empty — which every downstream consumer
reads as a legitimate negative.

Successor to `2026-07-26-feedback-batch-r-design.md`.

| id | target | one-line defect |
|---|---|---|
| `fb-2026-07-19-001` | `cli:inquiry` | causal checks read one of two authoring routes; empty edge set yields two green checks |
| `fb-2026-07-19-003` | `command:critique-approach` | Step 2 computes identifiability over an empty exported model |
| `fb-2026-07-25-008` | `cli:project` | `resolve-refs` / `topic-coverage` return empty outside a project root |
| `fb-2026-07-26-020` | `commands:specs-path` | five commands read a `specs/` path the migrator moved and the scaffolder still writes |

## Excluded from this batch

**`fb-2026-07-26-005`** is not worked here. Its remaining half is
`budget/invocation.py::hint_for` returning a bare relative filename — fleet-wide,
not health-specific — and closing it needs the unbuilt XDG state tier. Owner
decision D2 routed it to the context-budget program, and `context-budget-slice3`
is live in another worktree. Two sessions editing one fleet-wide surface is the
failure this exclusion avoids. It stays open, correctly parked.

## D1 — `scic:causes` has two authoring routes and no reader reads both

This is the root of `-001`, and it is larger than the filing states.

A causal edge can reach the graph two ways:

1. **Entity relation** — a `relations:` entry with `graph_layer: graph/causal`,
   which materializes into the `graph/causal` named graph. This is what
   `constants.py:432` declares (`{"predicate": "scic:causes", "layer":
   "graph/causal"}`) and what `export.py:376` enforces.
2. **Inquiry flow edge** — a `flow_edges` entry with `predicate: causes` on an
   authored `inquiry:` block. `inquiry_compile._FLOW_PREDICATE` maps it to
   `SCIC_NS.causes` and writes it into the named graph `inquiry/<slug>`, per
   that module's own docstring.

post-acute-infection authored route 2 (52 flow edges). The readers split:

| reader | reads | after `fc9e0201` |
|---|---|---|
| `export_pgmpy._get_causal_edges_for_inquiry` | `for graph in (inquiry_graph, causal_graph)` | **both routes** |
| `graph/store/inquiry.py:716` — `science inquiry validate` | `graph/causal` only | **route 1 only** |
| `graph/store/validation.py:91` — project-wide validate | `graph/causal` only | **route 1 only** |

`fc9e0201` fixed the exporter and stopped. Its commit message states the
principle it was applying — "so there is one supported resolution path" — but
applied it only within `export_pgmpy.py`. The two validators kept their own.

**Why this is invisible in the test suite.** `test_causal.py::_causal_relation`
hardcodes `"graph_layer": "graph/causal"`, so every causal-check test authors
route 1. The tests exercise the reader's own convention and pass. This is the
second time in one file: `fc9e0201` recorded that the prior regression test
"hardcodes `normalize_slug=True` (writing the reader's convention)". A fixture
that writes what the reader expects cannot falsify the reader.

**Ruling.** Extract the union — inquiry graph ∪ `graph/causal`, member-filtered
— into one function in `graph/store/inquiry.py` beside `resolve_inquiry`, and
route the exporter and both validators through it. Not three call sites that
agree today; one function that cannot disagree.

## D2 — zero resolved causal edges: fail only when edges were declared

*(owner decision, AskUserQuestion)*

Today an empty edge set produces `causal_acyclicity: pass` ("Causal edges are
acyclic") and `confounders_declared: pass` ("No common causes found"). Both are
vacuously true over the empty set. A check that passes when it saw nothing is
the estimator-doctrine failure: it cannot fail.

Two facts must be distinguished, and one status cannot carry both:

- **declared** — `scic:causes` triples in `inquiry/<slug>`, plus triples in
  `graph/causal` with at least one endpoint among the inquiry's members. This
  is what the author wrote for this inquiry.
- **resolved** — of those, the ones with *both* endpoints among the members.
  This is what the check can actually compute over.

| declared | resolved | verdict |
|---|---|---|
| 0 | 0 | `skip` — "no causal edges authored for this inquiry" |
| N > 0 | 0 | `fail` — "N causal edge(s) declared but none resolve to inquiry members" |
| N > 0 | M > 0 | check normally |

The `declared > 0, resolved == 0` row is precisely the post-acute-infection
incident, and it is currently the row that reports `pass`. The rejected
alternative — fail on any empty edge set — cannot state *why* the set is empty
and fires on sketch-stage inquiries that have authored nothing yet.

This also catches a defect nobody filed: an edge with one endpoint outside the
boundary/flow member set is dropped by the member filter today, silently.

## D3 — `critique-approach` Step 2 must assert a non-empty model

`-003` is `-001` seen one layer up: with pgmpy absent the identifiability checks
skip, and a reader who runs `uv add pgmpy` then gets *green* checks computed
over `DiscreteBayesianNetwork([])`. Green-over-empty is worse than the skip it
replaces.

Once D1 and D2 land, `science inquiry validate` fails loudly in that state, so
the command doc's job is to route on that signal rather than re-derive it: Step 2
asserts the exported model is non-empty before reading any identifiability
result, and falls back to explicit hand-derived d-separation when it is not.
The graph-backed / pre-DAG binary becomes a trichotomy — graph-backed and
populated, graph-backed but vacuous, pre-DAG.

## D4 — `science project` must fail when no project root resolves

`--project-root` defaults to `"."`. Run from `meta/entities/questions/`,
`resolve-refs` reports nine valid id-exact references as `unresolved` and
`topic-coverage` returns `{"n_topics": 0, "note": "no topics"}`. Both are
well-formed negative answers to a question that was never asked.

Precedent exists and is followed rather than reinvented:
`validate/context.py:55` already raises `science.yaml not found at
{manifest_path}`. Both commands validate the resolved root the same way and
raise before doing any work. No upward search — an implicit walk-up would make
the answer depend on invocation directory in a way the caller cannot see, and
`--project-root` already exists for callers who mean a different root.

## D5 — one spec-path resolver, and fix the scaffolder that regenerates the stale one

*(owner decision, AskUserQuestion)*

`-020` is a doctrine contradiction, not five stale strings. `entity
migrate-specs` canonicalizes specs to `entities/specs/NNNN-slug.md`. Yet
`create-project.md:352-353` instructs the scaffolder to write
`specs/research-question.md` and `specs/scope-boundaries.md` — and line 363,
eleven lines later, says "do not place typed entity owners under `doc/` or
`specs/`." The scaffolder contradicts both the migrator and the paragraph below
it, so every new project is created into the layout the migrator moves away
from, and the five readers follow the scaffolder.

Batch R already wrote the resolution logic for one caller
(`explore_ideas_seed._canonical_spec`: match a slug against the filename tail
and the frontmatter `id`/`aliases`, canonical layout winning). Promote it to a
shared helper, expose it as a CLI the command docs can call, point the readers
at it, and change the scaffolder to write the canonical layout. The resolver
reports which layout it found and errors when neither exists — so an unmigrated
project gets an answer, and a project with neither gets a failure rather than an
empty read.

## Sequencing

S1 (D1+D2) → S2 (D3, depends on S1's signal) → S3 (D4) → S4 (D5). S3 and S4 are
independent of the causal work.
