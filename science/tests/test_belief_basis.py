from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys

import pytest
from pydantic import ValidationError
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF

from science_tool.graph.belief import EVIDENCE_LINE_CLASS, EvidenceUnit
from science_tool.graph.belief_basis import (
    BASIS_SNAPSHOT_SCHEMA_VERSION,
    NO_TYPED_ENTITIES,
    EntityBasis,
    SnapshotIntegrityError,
    basis_digest,
    build_snapshot,
    capture_basis,
    compare_bases,
    load_snapshot,
    unit_key,
)
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS


def _u(stance: str = "supports", **kw) -> EvidenceUnit:
    base = dict(
        line_uri="x", stance=stance, strength="strong", independence="independent",
        independence_group="g", evidence_role="direct_test",
        evidence_type="empirical_data_evidence", dispute_scope=None,
        proxy_directness=None, has_measurement_model=False, source=None,
        observability_keys=(),
    )
    base.update(kw)
    return EvidenceUnit(**base)


def _distinct(value: object) -> object:
    """Return a value of compatible shape that differs from `value`."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, float):
        return value + 1.0
    if isinstance(value, tuple):
        return (*value, "perturbed")
    if isinstance(value, str):
        return value + "-perturbed"
    return "perturbed"  # None, and anything else


def test_identical_units_share_a_key():
    assert unit_key(_u()) == unit_key(_u())


def test_differing_strength_changes_the_key():
    assert unit_key(_u(strength="strong")) != unit_key(_u(strength="weak"))


def test_every_field_value_affects_the_key():
    """Fail-closed: every field's VALUE must reach the key, not just its name.

    Checking that field names appear in the key would pass an implementation
    serializing {name: None} for every field. Perturbing each value in turn
    catches that, and stays valid if unit_key later returns a hash instead
    of a JSON string.
    """
    base = _u()
    for field in dataclasses.fields(EvidenceUnit):
        mutated = dataclasses.replace(base, **{field.name: _distinct(getattr(base, field.name))})
        assert unit_key(mutated) != unit_key(base), f"{field.name} does not affect the key"


def test_unserializable_value_raises_rather_than_coercing():
    """No `default=` fallback: an unrepresentable value must fail loudly at capture.

    A `default=str` would stringify this and could collapse two distinct objects
    into one key, silently weakening the basis.
    """
    unit = dataclasses.replace(_u(), source=object())
    with pytest.raises(TypeError):
        unit_key(unit)


CLAIM = URIRef(PROJECT_NS["proposition/p"])
LINE = URIRef(PROJECT_NS["evidence-line/e"])


def _graphs_with_one_supporting_line() -> tuple[Graph, Graph]:
    knowledge, provenance = Graph(), Graph()
    knowledge.add((CLAIM, RDF.type, SCI_NS.Proposition))
    knowledge.add((LINE, RDF.type, EVIDENCE_LINE_CLASS))
    knowledge.add((LINE, CITO_NS.supports, CLAIM))
    provenance.add((LINE, SCI_NS.evidenceStrength, Literal("strong")))
    return knowledge, provenance


def test_capture_records_one_unit_for_the_claim():
    knowledge, provenance = _graphs_with_one_supporting_line()
    result = capture_basis(knowledge, provenance)
    assert result.status == "ok"
    claim = next(r for r in result.rows if r.entity_id == "proposition:p")
    assert len(claim.unit_keys) == 1
    assert claim.target_uris == (str(CLAIM),)


def test_capture_records_policy_identity():
    knowledge, provenance = _graphs_with_one_supporting_line()
    claim = next(r for r in capture_basis(knowledge, provenance).rows if r.entity_id == "proposition:p")
    assert claim.policy_id == "core-default"
    assert claim.policy_version


def test_empty_graph_is_unwired_not_empty():
    """No typed entities means belief was never assessed — that is not 'no changes'."""
    result = capture_basis(Graph(), Graph())
    assert result.status == "unwired"
    assert result.code == NO_TYPED_ENTITIES


def test_layer_uris_are_not_entities():
    knowledge, provenance = Graph(), Graph()
    knowledge.add((URIRef(PROJECT_NS["graph/knowledge"]), RDF.type, SCI_NS.Layer))
    assert capture_basis(knowledge, provenance).status == "unwired"


#: Captures one hypothesis whose evidence-target closure holds two propositions of
#: OPPOSING polarity, both linked by the SAME evidence line. Prints the surviving
#: unit's inherited target_polarity and the whole-capture digest.
#:
#: This must run in a fresh interpreter: `collect_evidence_units` iterated a
#: `frozenset` of URIRef (a str subclass), so the target that claimed the shared
#: line — and therefore the polarity baked into the unit key — depended on the
#: process-wide string hash seed. Capturing twice in ONE process shares one seed
#: and cannot detect that; baseline and comparison captures are separate processes
#: by construction, so the seed is exactly what differs in production.
_CROSS_PROCESS_PROBE = '''
import json

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF

from science_tool.graph.belief import EVIDENCE_LINE_CLASS, collect_evidence_units
from science_tool.graph.belief_basis import basis_digest, capture_basis
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS
from science_tool.graph.store import _evidence_targets_for_uri

HYP = URIRef(PROJECT_NS["hypothesis/h"])
CLAIM_A = URIRef(PROJECT_NS["proposition/a"])
CLAIM_Z = URIRef(PROJECT_NS["proposition/z"])
LINE = URIRef(PROJECT_NS["evidence-line/e"])

knowledge, provenance = Graph(), Graph()
knowledge.add((HYP, RDF.type, SCI_NS.Hypothesis))
knowledge.add((LINE, RDF.type, EVIDENCE_LINE_CLASS))
for claim, polarity in ((CLAIM_A, "affirms"), (CLAIM_Z, "negates")):
    knowledge.add((claim, RDF.type, SCI_NS.Proposition))
    knowledge.add((claim, CITO_NS.discusses, HYP))
    knowledge.add((LINE, CITO_NS.supports, claim))
    provenance.add((claim, SCI_NS.polarity, Literal(polarity)))

units = collect_evidence_units(knowledge, provenance, _evidence_targets_for_uri(knowledge, HYP))
result = capture_basis(knowledge, provenance)
print(json.dumps({"polarity": [u.target_polarity for u in units], "digest": basis_digest(result.rows)}))
'''

#: Seeds 0 and 1 already disagree without the fix; the rest are margin against a
#: future interpreter whose table layout happens to agree on one pair.
_HASH_SEEDS = ("0", "1", "2", "3", "4", "5")


def _probe_across_hash_seeds(tmp_path) -> list[dict[str, object]]:
    script = tmp_path / "cross_process_probe.py"
    script.write_text(_CROSS_PROCESS_PROBE)
    outputs: list[dict[str, object]] = []
    for seed in _HASH_SEEDS:
        completed = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "PYTHONHASHSEED": seed},
        )
        outputs.append(json.loads(completed.stdout))
    return outputs


def test_capture_is_reproducible_across_processes(tmp_path):
    """The digest must not depend on the interpreter's string hash seed.

    A baseline captured at run start and a comparison captured at run end are
    different processes. If the digest moves with the seed, `--compare` reports a
    belief movement on a run that changed nothing, and the guard gets switched off.
    """
    digests = {probe["digest"] for probe in _probe_across_hash_seeds(tmp_path)}
    assert len(digests) == 1, f"basis digest varies with PYTHONHASHSEED: {sorted(digests)}"


def test_shared_line_inherits_the_lowest_target_polarity(tmp_path):
    """Pins WHICH target claims a shared line, so the reproducibility above is not accidental.

    Targets are visited in sorted URI order, so `proposition/a` claims the line
    before `proposition/z` and the unit carries "affirms" in every process.
    """
    polarities = {tuple(probe["polarity"]) for probe in _probe_across_hash_seeds(tmp_path)}
    assert polarities == {("affirms",)}


def _basis(entity_id: str, unit_keys: tuple[str, ...] = ()) -> EntityBasis:
    return EntityBasis(
        entity_id=entity_id,
        uri=str(PROJECT_NS[entity_id.replace(":", "/")]),
        target_uris=(),
        unit_keys=unit_keys,
        policy_id="core-default",
        policy_version="1",
    )


def test_digest_is_order_independent():
    a, b = _basis("proposition:a"), _basis("proposition:b")
    assert basis_digest([a, b]) == basis_digest([b, a])


def test_digest_changes_when_a_unit_changes():
    before = basis_digest([_basis("proposition:a", ("k1",))])
    after = basis_digest([_basis("proposition:a", ("k2",))])
    assert before != after


def test_empty_capture_has_its_own_digest():
    """The empty basis must be distinguishable, not merely reproducible."""
    assert basis_digest([]) != basis_digest([_basis("proposition:a")])


def test_snapshot_round_trips():
    snapshot = build_snapshot([_basis("proposition:a", ("k1",))])
    reloaded = load_snapshot(snapshot.model_dump(mode="json"))
    assert reloaded.rows == snapshot.rows
    assert reloaded.digest == snapshot.digest


def test_tampered_rows_are_rejected():
    """A substituted baseline must not be able to produce a clean comparison."""
    payload = build_snapshot([_basis("proposition:a", ("k1",))]).model_dump(mode="json")
    payload["rows"][0]["unit_keys"] = ["k2"]
    with pytest.raises(SnapshotIntegrityError, match="digest mismatch"):
        load_snapshot(payload)


def test_unknown_schema_version_is_rejected():
    payload = build_snapshot([_basis("proposition:a")]).model_dump(mode="json")
    payload["schema_version"] = BASIS_SNAPSHOT_SCHEMA_VERSION + 1
    with pytest.raises(SnapshotIntegrityError, match="schema_version"):
        load_snapshot(payload)


def test_unknown_basis_field_is_rejected_not_dropped():
    """A newer snapshot must fail loudly rather than be truncated into a clean compare."""
    payload = build_snapshot([_basis("proposition:a")]).model_dump(mode="json")
    payload["rows"][0]["future_field"] = "value"
    with pytest.raises(ValidationError):  # extra="forbid"
        load_snapshot(payload)


@pytest.mark.parametrize("payload", [[], "snapshot", None, 42])
def test_wrong_shaped_payload_raises_validation_error(payload: object):
    """A top-level array or scalar must raise ValidationError, not TypeError.

    A TypeError from `**payload` unpacking would escape the CLI's handler and be
    reported as exit 1 — a belief movement — instead of unwired.
    """
    with pytest.raises(ValidationError):
        load_snapshot(payload)


def test_identical_captures_have_no_delta():
    before = [_basis("proposition:a", ("k1",))]
    assert compare_bases(before, list(before)) == []


def test_changed_units_are_reported():
    deltas = compare_bases([_basis("proposition:a", ("k1",))], [_basis("proposition:a", ("k2",))])
    assert [d.entity_id for d in deltas] == ["proposition:a"]
    assert deltas[0].changed == ("units",)


def test_new_entity_is_not_a_delta():
    """A bot filing a new question is permitted; it has no before-value to move."""
    assert compare_bases([], [_basis("question:0042")]) == []


def test_removed_entity_is_a_delta():
    deltas = compare_bases([_basis("proposition:a")], [])
    assert deltas[0].changed == ("removed",)


def test_policy_swap_is_a_delta_even_with_identical_units():
    before = [_basis("proposition:a", ("k1",))]
    after = [
        EntityBasis(
            entity_id="proposition:a", uri=str(PROJECT_NS["proposition/a"]),
            target_uris=(), unit_keys=("k1",),
            policy_id="other-policy", policy_version="1",
        )
    ]
    assert compare_bases(before, after)[0].changed == ("policy",)


def test_changed_targets_are_reported():
    """The targets branch needs its own load-bearing test.

    Every other comparison test leaves target_uris empty on both sides, so
    deleting the targets branch outright would not fail any of them.
    """
    before = [_basis("proposition:a", ("k1",))]
    after = [
        EntityBasis(
            entity_id="proposition:a", uri=str(PROJECT_NS["proposition/a"]),
            target_uris=(str(PROJECT_NS["proposition/a"]),), unit_keys=("k1",),
            policy_id="core-default", policy_version="1",
        )
    ]
    assert compare_bases(before, after)[0].changed == ("targets",)
