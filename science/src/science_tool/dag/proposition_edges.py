"""Source DAG edges from compiled relational propositions (Task 5f).

The DAG is a VIEW over compiled ``PropositionEntity`` records: each proposition
is one edge ``(subject -> object)`` carrying the orthogonal *authored* channel
fields the channel-driven renderer (``style_for_edge``, design §6) consumes:

  - ``polarity``                 → hue channel
  - ``claim_layer``              → feeds ``derived_edge_status`` (structural band)
  - ``identification``           → line-style + arrowhead channel

This is the epistemic source-of-truth replacement for ``*.edges.yaml``
(retired, see ``schema.load_legacy_edges_yaml``).  ``edge_status`` is **never**
carried here — it is DERIVED at render time via ``derived_edge_status``.

Belief-derived channel fields (``belief_magnitude``, ``refuted``,
``has_grounding_evidence``) are NOT authored on a proposition; they are produced
by the belief engine over the materialized graph.  They default safely in
``style_for_edge``'s channel mode (an ungrounded proposition derives the
``unknown`` band), so a proposition alone yields a valid channel-mode edge.
Enriching edges with materialized belief at render time is a follow-on; this
module owns only the authored-axis projection.
"""

from __future__ import annotations

from pathlib import Path

from science_model.propositions import PropositionEntity


def proposition_to_edge(prop: PropositionEntity) -> dict:  # type: ignore[type-arg]
    """Project one ``PropositionEntity`` to a channel-mode edge dict.

    The returned dict carries ``source``/``target`` (the DOT node names taken
    from ``subject``/``object``) plus the authored orthogonal channel fields.
    The presence of ``polarity``/``claim_layer`` switches ``style_for_edge``
    into channel-driven mode, so ``edge_status`` is DERIVED (never authored).
    """
    if prop.subject is None or prop.object is None:
        raise ValueError(
            f"proposition {prop.id!r} has no subject/object; cannot source a DAG edge from it"
        )

    polarity = prop.polarity.value if prop.polarity is not None else "unsigned"
    claim_layer = prop.claim_layer.value if prop.claim_layer is not None else "causal_effect"
    identification = (
        prop.identification_strength.value
        if prop.identification_strength is not None
        else "observational"
    )

    edge: dict = {  # type: ignore[type-arg]
        "source": prop.subject,
        "target": prop.object,
        # Channel fields (authored axes only). Their presence forces channel
        # mode in style_for_edge; edge_status is intentionally absent.
        "polarity": polarity,
        "claim_layer": claim_layer,
        "identification": identification,
        # Belief-derived channels default to the ungrounded floor (no graph
        # belief wired in here); style_for_edge derives "unknown" from these.
        "belief_magnitude": "speculative",
        "refuted": False,
        "has_grounding_evidence": False,
        # Label seed: the legacy relation label (or predicate) so the rendered
        # edge keeps a human-readable caption.
        "original_label": prop.legacy_relation_label
        or (prop.predicate.value if prop.predicate is not None else ""),
    }
    return edge


def edges_from_propositions(propositions: list[PropositionEntity]) -> list[dict]:  # type: ignore[type-arg]
    """Project a list of compiled propositions to channel-mode edge dicts.

    Propositions with no ``subject``/``object`` (claim-only, non-relational)
    cannot be drawn as edges and are skipped.
    """
    edges: list[dict] = []  # type: ignore[type-arg]
    for prop in propositions:
        if prop.subject is None or prop.object is None:
            continue
        edges.append(proposition_to_edge(prop))
    return edges


def load_proposition_edges(project_root: Path) -> list[dict]:  # type: ignore[type-arg]
    """Load compiled ``PropositionEntity`` records and project them to edges.

    Reads the project's entity index (the canonical ``entities/propositions/``
    store written by ``compile_workbench``) and returns channel-mode edge dicts.
    """
    from science_tool.entities import load_local_entity_index

    index = load_local_entity_index(project_root)
    propositions = [e for e in index.values() if isinstance(e, PropositionEntity)]
    return edges_from_propositions(propositions)
