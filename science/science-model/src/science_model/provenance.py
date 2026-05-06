"""Provenance types for data field annotations.

Canonical vocabulary for declaring how a data field was produced.
Projects use these types in their own field-provenance registries
to enable independence checking when data fields are compared or
composed into metrics.

The framework provides the vocabulary; projects decide where to
store the declarations (e.g., a TypeScript registry, a YAML manifest).
"""

from __future__ import annotations

from enum import Enum


class ProvenanceType(str, Enum):
    """How a data field was produced."""

    def __str__(self) -> str:
        return self.value

    MATHEMATICAL = "mathematical"
    """Derivable from the equation or formal definition.
    Examples: primitives, symmetries, field count, wiring topology.
    Comparing two mathematical fields is expected and informative
    (structural self-similarity), not a confound.
    """

    EMPIRICAL = "empirical"
    """Measured from external data sources.
    Examples: formulation breadth (beta), citation counts, dataset metrics.
    Generally independent of other field types unless the measurement
    procedure uses the same data.
    """

    EDITORIAL = "editorial"
    """Assigned by human or AI judgment.
    Examples: behavioral classes, metaClass, chapter assignment, theme labels.
    Risk: when the same annotator assigns multiple editorial fields,
    correlations may reflect annotator consistency rather than structural
    alignment.
    """

    DERIVED = "derived"
    """Computed from other fields via an explicit transform.
    Examples: enriched similarity matrix, IDF weights, community labels.
    Inherits the provenance of its inputs. A derived field containing
    editorial inputs carries editorial provenance for that fraction.
    Not a fallback for unknown provenance — use only when the derivation
    chain is known and the basis fields are identified.
    """


class EvidenceIndependence(str, Enum):
    """Independence status of an evidence edge.

    Declares whether the evidence source is independent of the claim
    it supports or disputes. Independence is defined epistemically:
    does the evidence tell us something we couldn't already infer
    from the claim's own construction?

    Shared mathematical provenance is NOT a confound — comparing two
    mathematically-derived representations is the intended use of
    structural analysis. The concern is with editorial provenance
    (annotator consistency) and self-referential composites (circularity).
    """

    def __str__(self) -> str:
        return self.value

    INDEPENDENT = "independent"
    """No circularity and no shared editorial/empirical provenance.
    The evidence source and validation target are epistemically independent.
    Shared mathematical provenance is acceptable under this level.
    Example: CKA(RawPrimitive, Chapter) — mathematical vs. editorial.
    """

    SHARED_SOURCE = "shared-source"
    """Both sides trace to editorial (or empirical) provenance from the
    same annotation source, but neither side directly contains the other.
    The evidence may reflect annotator consistency rather than a genuine
    structural relationship.
    Example: CKA(Chapter, MetaClass) — both editorial, same annotator.
    """

    CIRCULAR = "circular"
    """A composite metric contains a component that overlaps the
    validation target's basis fields. The evidence is partially
    self-referential and uninformative about the relationship being tested.
    Example: CKA(Enriched, Behavioral) where enriched contains 25% behavioral.
    """
