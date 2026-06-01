# science:code
# status: library
# task_ids: [t065]
# science:end
"""L1 epistemic-neighborhood patch prototype (h00 working model, task t065).

A *patch* (RFC §2 / D-006) is one epistemic neighborhood — here the gene→disease
association neighborhood of a single disease, encoded at ladder level **L1**:
belief result + provenance axes + an experimental subjective-logic opinion view,
computed by REUSING the shipped `science_tool.graph.belief` machinery (D-005:
reuse, do not reinvent). The patch is emitted as a TriG **named graph** (D-006).

Real data slice: pan-disease q14 curated panels (elicited/editorial route) +
PubTator gene-disease co-occurrence (discovered/empirical route), extracted into
`fixtures/q14_slice.json`. The cross-project data dependency lives ONLY at
extraction time; this package consumes the JSON with the standard library.

Three things the prototype demonstrates on real numbers:
  1. provenance axes — an EDITORIAL ai-drafted/human-ratified panel assertion is
     structurally lower-status (curation step penalty) than empirical evidence;
  2. publication gravity as **independence-discounted fusion** — universal genes
     (co-occur with every disease) share one `publication-gravity` source group
     and collapse to a single unit instead of inflating the signature;
  3. an honest **uncertainty mass** — a thin editorial-only label carries high
     ignorance until corroborated (the subjective-logic opinion view).
"""
from .model import (
    PUBGRAV_GROUP,
    build_edge_units,
    build_signature_units,
    load_fixture,
    pubgravity_threshold,
)
from .opinion import Opinion, opinion_from_scores
from .patch import build_patch_report, emit_patch_trig

__all__ = [
    "PUBGRAV_GROUP",
    "build_edge_units",
    "build_signature_units",
    "load_fixture",
    "pubgravity_threshold",
    "Opinion",
    "opinion_from_scores",
    "build_patch_report",
    "emit_patch_trig",
]
