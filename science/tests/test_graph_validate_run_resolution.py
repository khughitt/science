from __future__ import annotations

from science_tool.graph.store.validation import validate_graph_dataset


def _dataset_from_trig(trig: str):
    from rdflib import Dataset

    ds = Dataset()
    ds.parse(data=trig, format="trig")
    return ds


def _row(rows, name):
    return next(r for r in rows if r["check"] == name)


def test_row_is_always_present_even_with_no_evidence_lines():
    rows, _ = validate_graph_dataset(_dataset_from_trig("@prefix ex: <http://e/> . ex:a ex:b ex:c ."))
    assert _row(rows, "empirical_run_resolution")["status"] == "pass"


def test_unresolved_empirical_line_warns_in_p2(empirical_line_without_run_trig):
    rows, has_failures = validate_graph_dataset(_dataset_from_trig(empirical_line_without_run_trig))
    row = _row(rows, "empirical_run_resolution")
    assert row["status"] == "warn"
    assert not has_failures  # P2 is warn-only; P4 flips this


def test_resolved_empirical_line_passes(empirical_line_with_run_trig):
    rows, has_failures = validate_graph_dataset(_dataset_from_trig(empirical_line_with_run_trig))
    assert _row(rows, "empirical_run_resolution")["status"] == "pass"
    assert not has_failures


def test_member_of_cycle_fails(member_of_cycle_trig):
    rows, has_failures = validate_graph_dataset(_dataset_from_trig(member_of_cycle_trig))
    row = _row(rows, "empirical_run_resolution")
    assert row["status"] == "fail"
    assert "dataset.member-of-cycle" in row["details"]
    assert has_failures


def test_derivation_run_without_fingerprint_still_warns(empirical_line_with_unfingerprinted_run_trig):
    """The contract must fail CLOSED: naming a run is not bearing a fingerprint."""
    rows, _ = validate_graph_dataset(_dataset_from_trig(empirical_line_with_unfingerprinted_run_trig))
    row = _row(rows, "empirical_run_resolution")
    assert row["status"] == "warn"
    assert "run-unfingerprinted" in row["details"]


def test_run_refs_to_unfingerprinted_run_still_warns(line_with_unfingerprinted_run_ref_trig):
    """run_refs must not be a back door around the fingerprint requirement."""
    rows, _ = validate_graph_dataset(_dataset_from_trig(line_with_unfingerprinted_run_ref_trig))
    row = _row(rows, "empirical_run_resolution")
    assert row["status"] == "warn"
    assert "run-unfingerprinted" in row["details"]


def test_run_refs_to_fingerprinted_run_resolves_a_code_only_dataset(
    line_with_produced_by_dataset_and_fingerprinted_run_ref_trig,
):
    """The rescue case: sound dataset provenance that cannot itself name a run."""
    rows, _ = validate_graph_dataset(
        _dataset_from_trig(line_with_produced_by_dataset_and_fingerprinted_run_ref_trig)
    )
    assert _row(rows, "empirical_run_resolution")["status"] == "pass"


def test_real_materialized_unfingerprinted_run_does_not_resolve(tmp_path):
    """Real `graph build` output (not a hand-built fixture): an empirical line resting
    on a dataset whose derivation names a real, but unfingerprinted, `workflow-run`
    must warn — proving the contract fails closed against actual materializer output,
    not just against fixtures a test author might build with the wrong shape.
    """
    from rdflib import Dataset

    from science_tool.graph.io import PROJECT_NS, SCI_NS
    from science_tool.graph.materialize import materialize_graph

    root = tmp_path
    (root / "science.yaml").write_text(
        "name: run-resolution-e2e\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )

    props = root / "entities" / "propositions"
    props.mkdir(parents=True)
    (props / "p1.md").write_text(
        "---\nid: proposition:p1\nkind: proposition\ntitle: P1\n---\n\nClaim.\n",
        encoding="utf-8",
    )

    # Named, real workflow-run entity — deliberately without a `fingerprint:` block.
    runs = root / "entities" / "workflow-runs"
    runs.mkdir(parents=True)
    (runs / "r1.md").write_text(
        "---\nid: workflow-run:r1\nkind: workflow-run\ntitle: R1\n---\n",
        encoding="utf-8",
    )

    datasets = root / "entities" / "datasets"
    datasets.mkdir(parents=True)
    (datasets / "ds1.md").write_text(
        "---\n"
        "id: dataset:ds1\n"
        "kind: dataset\n"
        "title: DS1\n"
        "origin: derived\n"
        "derivation:\n"
        "  workflow: workflow:wf\n"
        "  workflow_run: workflow-run:r1\n"
        "  git_commit: abc\n"
        "  config_snapshot: config.yaml\n"
        "  produced_at: '2026-04-19T00:00:00Z'\n"
        "---\n",
        encoding="utf-8",
    )

    lines = root / "entities" / "evidence-lines"
    lines.mkdir(parents=True)
    (lines / "e1.md").write_text(
        "---\n"
        "id: evidence-line:e1\n"
        "kind: evidence-line\n"
        "title: E1\n"
        "status: active\n"
        "stance: supports\n"
        "target: proposition:p1\n"
        "strength: moderate\n"
        "evidence_type: empirical_data_evidence\n"
        "dataset_usage:\n"
        "  - ref: dataset:ds1\n"
        "    role: analyzed\n"
        "    overlap: full\n"
        "created: '2026-05-01'\n"
        "updated: '2026-05-01'\n"
        "---\n",
        encoding="utf-8",
    )

    trig_path = materialize_graph(root)
    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")

    run_uri = PROJECT_NS["workflow-run/r1"]
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    # The dataset's derivation really does name the run — this is not a no-op fixture.
    dataset_uri = PROJECT_NS["dataset/ds1"]
    assert (dataset_uri, SCI_NS.workflowRun, run_uri) in knowledge

    rows, has_failures = validate_graph_dataset(dataset)
    row = _row(rows, "empirical_run_resolution")
    assert row["status"] == "warn"
    assert "run-unfingerprinted" in row["details"]
    assert not has_failures
    assert (run_uri, SCI_NS.fingerprintPolicy, None) not in knowledge
