"""Read-only drift check for projected entity records.

This module is the pure, side-effect-free analog of
``datasets_register.py::write_derived_dataset_entities``.  Where that
function writes entity records idempotently (skipping writes when on-disk
content already matches), ``check_projection_drift`` compares a
**projection** (the set of records a generator *would* write) against the
**committed** state already on disk, and returns a structured diff
describing any divergence.

The concrete projection — e.g. ``mm30.v8.yml → entities/datasets/`` — is the
responsibility of the *consuming* project.  This module contains only the
generic comparison primitive; it performs no filesystem access and has no
dependency on rdflib or the materialisation pipeline.
"""

from __future__ import annotations


def check_projection_drift(
    expected: dict[str, dict],
    committed: dict[str, dict],
) -> dict[str, dict]:
    """Compare a projected set of entity records against the committed state.

    Both ``expected`` and ``committed`` map ``entity_id`` → ``record`` where
    ``record`` is a plain ``dict`` of field names to values, e.g.::

        {
            "dataset:mmrf": {"origin": "external", "source_class": "observational"},
        }

    Returns an empty dict ``{}`` when every id and every field matches.
    Otherwise returns a dict keyed by the divergent entity ids, where each
    value is one of:

    * ``{"status": "missing_from_committed"}`` — id present in *expected* but
      absent from *committed* (entity was not regenerated / is undergenerated).
    * ``{"status": "unexpected_in_committed"}`` — id present in *committed*
      but absent from *expected* (entity is stale / was not produced by the
      current projection).
    * ``{"fields": {field: {"expected": v_exp, "committed": v_committed}}}`` —
      id present in both but one or more field values differ.  Only drifted
      fields are included; matching fields are omitted.

    The function is **pure and deterministic**: it never mutates its inputs,
    performs no I/O, and returns a dict whose keys are sorted lexicographically
    so that the output is stable for serialisation and comparison.

    Args:
        expected: Mapping of entity id to the record the projection would write.
        committed: Mapping of entity id to the record currently on disk.

    Returns:
        A diff dict (empty when there is no drift).
    """
    raw: dict[str, dict] = {}

    expected_ids = set(expected)
    committed_ids = set(committed)

    # Ids present only in expected (missing from committed)
    for entity_id in expected_ids - committed_ids:
        raw[entity_id] = {"status": "missing_from_committed"}

    # Ids present only in committed (unexpected / stale)
    for entity_id in committed_ids - expected_ids:
        raw[entity_id] = {"status": "unexpected_in_committed"}

    # Ids present in both — check field-level drift
    for entity_id in expected_ids & committed_ids:
        exp_record = expected[entity_id]
        com_record = committed[entity_id]
        all_fields = sorted(set(exp_record) | set(com_record))
        field_diffs: dict[str, dict] = {}
        for field in all_fields:
            v_exp = exp_record.get(field)
            v_com = com_record.get(field)
            if v_exp != v_com:
                field_diffs[field] = {"expected": v_exp, "committed": v_com}
        if field_diffs:
            raw[entity_id] = {"fields": field_diffs}

    # Return with keys sorted for stable, deterministic output
    return dict(sorted(raw.items()))
