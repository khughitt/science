from pathlib import Path

from rdflib import Dataset, Literal, RDF, URIRef

from science_tool.graph.belief_policy import DEFAULT_BELIEF_POLICY
from science_tool.graph.belief_snapshot import (
    append_snapshots, read_snapshots, snapshot_records,
)
from science_tool.graph.io import CITO_NS, SCI_NS
from science_tool.graph.store import _graph_uri

PROP = URIRef("https://example.org/prop/p1")
LINE = URIRef("https://example.org/el/yang")


def _graphs():
    ds = Dataset()
    k = ds.graph(_graph_uri("graph/knowledge"))
    p = ds.graph(_graph_uri("graph/provenance"))
    k.add((PROP, RDF.type, SCI_NS.Proposition))
    k.add((LINE, RDF.type, SCI_NS.EvidenceLine))
    k.add((LINE, CITO_NS.supports, PROP))
    p.add((LINE, SCI_NS.evidenceStrength, Literal("strong")))
    p.add((LINE, SCI_NS.evidenceRole, Literal("direct_test")))
    p.add((LINE, SCI_NS.evidenceType, Literal("empirical_data_evidence")))
    return k, p


def test_snapshot_row_carries_policy_identity():
    k, p = _graphs()
    row = snapshot_records(k, p, scalar_enabled=False, as_of="2026-06-16")[0]
    assert row["policy_id"] == "core-default"
    assert row["policy_version"] == "1"


def test_policy_version_bump_is_not_deduped(tmp_path: Path):
    base = {
        "as_of": "2026-06-16", "claim": "c", "input_hashes": ["sha256:x"],
        "config_version": "belief-logodds-v3", "scalar_enabled": False,
        "policy_id": "core-default", "policy_version": "1",
    }
    bumped = {**base, "policy_version": "2"}
    out = tmp_path / "knowledge" / "belief-snapshots.jsonl"
    assert append_snapshots(out, [base]) == 1
    assert append_snapshots(out, [base]) == 0      # idempotent
    assert append_snapshots(out, [bumped]) == 1    # version bump -> distinct _key -> new row
    assert {r["policy_version"] for r in read_snapshots(out)} == {"1", "2"}


def test_read_snapshots_normalizes_pre_policy_rows(tmp_path: Path):
    # A pre-Slice-A artifact row has no policy fields; it was produced by the core-default
    # policy, so read normalizes it to that identity (no KeyError downstream in _key/matcher).
    import json

    out = tmp_path / "knowledge" / "belief-snapshots.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    legacy = {
        "as_of": "2026-05-24", "claim": "prop:p1", "belief_state": "fragile",
        "contested": False, "scalar_enabled": False,
        "input_hashes": ["sha256:abc"], "config_version": "belief-logodds-v3",
    }
    out.write_text(json.dumps(legacy) + "\n", encoding="utf-8")
    row = read_snapshots(out)[0]
    assert row["policy_id"] == "core-default"
    assert row["policy_version"] == "1"
    # And append remains idempotent against the normalized legacy row.
    normalized = {**legacy, "policy_id": "core-default", "policy_version": "1"}
    assert append_snapshots(out, [normalized]) == 0


def test_patch_trig_emits_policy_identity(tmp_path: Path):
    from science_tool.model.patch import PatchEdge, PatchNode, emit_patch_trig

    sci = "http://example.org/science/vocab/"
    patch_iri = URIRef("http://example.org/project/patch/demo")
    focal = PatchNode(URIRef("http://example.org/world/disease/D1"), "Demo", URIRef(sci + "Disease"))
    edge = PatchEdge(
        iri=URIRef("http://example.org/project/patch/demo/assoc/G1"),
        subject=PatchNode(URIRef("http://example.org/world/gene/G1"), "G1", URIRef(sci + "Gene")),
        edge_type=URIRef(sci + "GeneDiseaseAssociation"),
        belief_magnitude="supported",
    )
    out = emit_patch_trig(patch_iri, focal, "L1", [edge], tmp_path / "patch.trig")
    ds = Dataset()
    ds.parse(str(out), format="trig")
    g = ds.graph(patch_iri)
    ids = [str(o) for o in g.objects(edge.iri, URIRef(sci + "beliefPolicyId"))]
    vers = [str(o) for o in g.objects(edge.iri, URIRef(sci + "beliefPolicyVersion"))]
    assert ids == [DEFAULT_BELIEF_POLICY.policy_id]
    assert vers == [DEFAULT_BELIEF_POLICY.version]


def test_snapshot_persists_qa_dataset_capped_and_legacy_normalizes(tmp_path):
    from science_tool.graph.belief_snapshot import _with_policy_defaults, _key

    legacy = _with_policy_defaults({"as_of": "x", "claim": "c", "input_hashes": [],
        "config_version": "v", "scalar_enabled": False, "policy_id": "core-default",
        "policy_version": "1"})
    assert legacy["qa_dataset_capped"] is False
    with_flag = dict(legacy)
    with_flag["qa_dataset_capped"] = True
    assert _key(legacy) == _key(with_flag)   # derived flag, not identity
