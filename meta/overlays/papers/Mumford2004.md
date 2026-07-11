---
id: paper:Mumford2004
overlay_of: paper:Mumford2004
pin_version: "1.0.0"
status: active
created: "2026-07-10"
updated: "2026-07-10"
source_refs:
- cite:Mumford2004
related:
- hypothesis:0007-working-model
- hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
---
# Laws in Nature

- **Authors:** Stephen Mumford
- **Year:** 2004
- **Publisher:** Routledge (Routledge Studies in Twentieth-Century Philosophy, #18)
- **ISBN:** 978-0-415-40782-3 (pbk); 978-0-415-31128-1 (hbk)
- **BibTeX key:** Mumford2004
- **Source:** PDF (publisher preview — front matter + Chapter 1 only, ~34 pp; remaining chapters [INACCESSIBLE])

> **Partial-preview caveat.** This summary is based on the publisher preview PDF,
> which contains the full preface, acknowledgements, table of contents, and Chapter 1
> ("Laws in science and philosophy," pp. 1–18). Parts II and III (Chapters 2–12,
> pp. 19–205) are not included in the preview and their content beyond the chapter
> outlines is [INACCESSIBLE]. All chapter-level claims below are drawn from the
> overview Mumford himself provides in §1.6 and in the preface, not from reading
> those chapters directly.

## Key Contribution

Mumford argues for **realist lawlessness**: the position that there are genuine
necessary connections (modal properties, causal powers) in nature, but no
distinct metaphysical entities called "laws of nature" that govern them [@Mumford2004].
His central thesis is that the very concept of a natural law is explanatorily
redundant and metaphysically incoherent once one accepts that properties are
intrinsically modal (power-bearing). If properties already carry their own
necessity, laws have nothing left to do — and can only be added back as a
solution to a problem (Humean inertness of the world) that was misconceived in
the first place.

The book's slogan: "The world is more of a jigsaw than a mosaic: its pieces can
form only one picture, and laws are no part of it."

## Methods

This is a work of analytic metaphysics. Mumford proceeds by:

1. **Critical survey** of existing positions — Humean lawlessness (regularity/best-systems
   theories; David Lewis, van Fraassen, Russell, Ayer) and nomological realism
   (Dretske-Tooley-Armstrong necessitation relation; Ellis's scientific essentialism).
2. **The Central Dilemma** (Chapter 9): presents nomological realism with two
   exhaustive horns —
   - *External laws* (laws distinct from properties): cannot govern categorical
     properties; leads to quidditism and disconnection from what they are supposed
     to determine. [INACCESSIBLE — detail beyond §1.6 summary]
   - *Internal laws* (laws absorbed into properties): collapse into the dispositional
     structure of properties and become redundant. [INACCESSIBLE — detail beyond §1.6 summary]
3. **Positive account** (Chapter 10): modal properties / powers as de re necessities
   that replace every function once assigned to laws, following Shoemaker's (1980)
   cluster-of-relations view of properties. [INACCESSIBLE — detail beyond §1.6 summary]

No empirical data or computational methods are employed; argument is
purely conceptual.

## Relevance

**Direct relevance to Science toolkit design:**

1. **Patchwork / federated model (H07).** The Science working model
   (`hypothesis:0007-working-model`) explicitly describes knowledge as a
   "federated patchwork of epistemic neighborhoods." Mumford's realist lawlessness
   — and its Cartwright-adjacent rejection of universal covering laws in favour of
   locally-real powers — supplies one philosophical grounding for why a
   *patchwork* representation is not a deficiency but a feature: domains do not
   share a common law-like structure; their patches connect through shared
   properties, not through universal laws.

2. **Causal edges vs. laws vs. regularities.** The Science graph distinguishes
   association edges from causal edges. Mumford's taxonomy maps directly:
   regularity/pattern = association; modal property/power = genuinely causal edge.
   His argument that laws are redundant once powers are admitted supports the
   toolkit's decision to represent causal claims as *property-of-entity* relations
   rather than free-standing rules.

3. **Causal-estimand guardrails (H04).** The problem Mumford diagnoses for
   nomological realism — how does a law determine its instances, and by what
   mechanism? — is structurally parallel to the guardrail problem: how does an
   evidence artifact bearing on one estimand license an update to a causal
   proposition with a different target? Both problems arise from missing
   specification of the *mechanism of determination*. Mumford's Central Dilemma
   suggests that unless the mechanism is grounded in the intrinsic properties of
   the entities involved (not in an external rule/law), the governance claim is
   empty — analogous to a causal-claim update that lacks estimand metadata.

4. **Cartwright cross-link.** Mumford explicitly positions his work relative to
   Cartwright's *The Dappled World* (1999) and her nomological-machines argument.
   Any future intake of Cartwright should cross-reference this work.

5. **Natural-systems relevance (for commons promotion).** The book's central
   metaphor — holism ("jigsaw") over atomism ("mosaic") — and its powers-based
   ontology are directly relevant to how biological natural systems (e.g.,
   pan-disease) should model mechanistic causal structure: cellular properties
   *have* causal powers (receptor activation, gene expression); those powers are
   not governed by biology's "laws" as external rules but as de re necessities of
   the molecular components. This is a candidate for promotion to commons once
   cross-project synthesis is possible.

## Project Framework Mapping

| Mumford Concept | Science Concept | Notes |
|---|---|---|
| Realist lawlessness | Patchwork / federated epistemic model | Both deny universal covering structure; assert local necessity |
| Modal property / power | Causal edge (directed, mechanism-specified) | A causal edge in the graph should encode an intrinsic power, not just a regularity |
| Regularity / best-system axiom | Association edge (undirected, non-causal) | Pattern without grounding in powers |
| Central Dilemma (external vs. internal laws) | Estimand-mechanism gap | Guardrail question: how does the evidence determine the proposition? |
| Natural kinds of laws | Evidence type vocabulary | "Laws are not a natural kind" parallels the need for explicit evidence-type tags |
| Harmless/harmful metaphor | Misleading edge label | Law-as-metaphor → causal-as-metaphor if not grounded; label discipline matters |

## Model / Tool Availability

No software artifact. This is a philosophical monograph.

## Follow-up

- Read Cartwright (1999) *The Dappled World* — Mumford's closest relative and
  direct foil; differences in scientific vs. metaphysical argumentation.
- Read Molnar (2003) *Powers* — the dispositionalist realism that directly
  influenced Mumford; referenced as "a major contribution against Humeanism."
- Read Ellis (2001) *Scientific Essentialism* — the essentialist nomological
  realism Mumford critiques most extensively.
- Question reserved: whether the toolkit's causal-edge semantics should
  explicitly adopt a powers-based ontology over a regularity-based one.
- Cross-reference with natural-systems project when it models mechanistic biology
  — this book's ontology maps onto molecular/cellular powers models.
