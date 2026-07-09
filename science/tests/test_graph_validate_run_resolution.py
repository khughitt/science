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


def test_verdict_is_identical_with_and_without_data_files_on_disk(
    tmp_path, empirical_line_with_run_trig
):
    """THE load-bearing test: obligations derive from DECLARED facts, never a disk probe.

    Validate must return the same rows whether or not the run's data files exist.
    """
    ds = _dataset_from_trig(empirical_line_with_run_trig)
    before, _ = validate_graph_dataset(ds)

    data = tmp_path / "results" / "w1" / "r1"
    data.mkdir(parents=True)
    (data / "out.csv").write_text("x,y\n1,2\n", encoding="utf-8")
    after_present, _ = validate_graph_dataset(_dataset_from_trig(empirical_line_with_run_trig))

    (data / "out.csv").unlink()
    after_absent, _ = validate_graph_dataset(_dataset_from_trig(empirical_line_with_run_trig))

    assert before == after_present == after_absent


def test_run_resolution_ignores_datasets_outside_the_dataset_qa_substrate(tmp_path, local_fingerprint):
    """Substrate parity: `empirical_run_resolution` and the dataset-QA ceiling must
    rest on the SAME per-line dataset set — `dependence_datasets_by_line`, restricted
    to dependence-role usage.

    A `cited`-role dataset_usage is NOT part of that substrate (dataset-QA would
    never cap a line for a merely-cited dataset's QA failure). This test names a
    FINGERPRINTED run only on the cited-only dataset, and a dependence-role dataset
    with no provenance at all. If `_runs_for_line` ever stopped going through
    `dependence_datasets_by_line` — e.g. by walking every `dataset_usage` entry
    regardless of role — the cited dataset's run would wrongly rescue resolution
    and this test would flip from warn to pass.
    """
    import yaml
    from rdflib import Dataset

    from science_tool.graph.dataset_independence import dependence_datasets_by_line
    from science_tool.graph.io import PROJECT_NS, SCI_NS
    from science_tool.graph.materialize import materialize_graph
    from science_tool.graph.store.validation import _knowledge_and_provenance

    root = tmp_path
    (root / "science.yaml").write_text(
        "name: run-resolution-parity\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )

    props = root / "entities" / "propositions"
    props.mkdir(parents=True)
    (props / "p1.md").write_text(
        "---\nid: proposition:p1\nkind: proposition\ntitle: P1\n---\n\nClaim.\n",
        encoding="utf-8",
    )

    fingerprint_yaml = yaml.safe_dump(
        {"fingerprint": local_fingerprint().model_dump(mode="json", exclude_none=True)},
        sort_keys=False,
    )
    runs = root / "entities" / "workflow-runs"
    runs.mkdir(parents=True)
    (runs / "r1.md").write_text(
        f"---\nid: workflow-run:r1\nkind: workflow-run\ntitle: R1\n{fingerprint_yaml}---\n",
        encoding="utf-8",
    )

    datasets = root / "entities" / "datasets"
    datasets.mkdir(parents=True)
    # Dependence-role dataset with NO provenance of its own.
    (datasets / "ds-dep.md").write_text(
        "---\nid: dataset:ds-dep\nkind: dataset\ntitle: DS-DEP\n---\n",
        encoding="utf-8",
    )
    # Cited-only dataset whose derivation names the FINGERPRINTED run.
    (datasets / "ds-cited.md").write_text(
        "---\n"
        "id: dataset:ds-cited\n"
        "kind: dataset\n"
        "title: DS-CITED\n"
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
        "  - ref: dataset:ds-dep\n"
        "    role: analyzed\n"
        "    overlap: full\n"
        "  - ref: dataset:ds-cited\n"
        "    role: cited\n"
        "    overlap: full\n"
        "created: '2026-05-01'\n"
        "updated: '2026-05-01'\n"
        "---\n",
        encoding="utf-8",
    )

    trig_path = materialize_graph(root)
    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")

    line_uri = PROJECT_NS["evidence-line/e1"]
    dep_uri = PROJECT_NS["dataset/ds-dep"]
    cited_uri = PROJECT_NS["dataset/ds-cited"]
    run_uri = PROJECT_NS["workflow-run/r1"]

    knowledge, provenance = _knowledge_and_provenance(dataset)
    # The run really is fingerprinted and really is reachable from ds-cited — this
    # is not a no-op fixture.
    assert (run_uri, SCI_NS.fingerprintPolicy, None) in knowledge
    assert (cited_uri, SCI_NS.workflowRun, run_uri) in knowledge

    # This IS the substrate the dataset-QA ceiling (graph/dataset_qa.py) consumes.
    by_line = dependence_datasets_by_line(knowledge, provenance)
    assert by_line[line_uri] == {dep_uri}

    rows, has_failures = validate_graph_dataset(dataset)
    row = _row(rows, "empirical_run_resolution")
    # The cited-only run must NOT rescue resolution: only ds-dep (no provenance)
    # is on the substrate, so the line stays unresolved.
    assert row["status"] == "warn"
    assert "no-provenance" in row["details"]
    assert not has_failures
