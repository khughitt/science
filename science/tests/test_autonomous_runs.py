from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import PROV, RDF, XSD

from science_model.autonomous_runs import RunRecordError
from science_tool.graph.autonomous_runs import (
    add_run_record_to_graph,
    load_run_records,
    run_node_uri,
)
from science_tool.graph.store import PROJECT_NS, SCI_NS

_RECORD = """---
id: run:2026-07-24-curation-sweep-a3f1
agent: curation-sweep
model: claude-opus-5
tier: belief-neutral
branch: auto/2026-07-24-curation-sweep-a3f1
base_commit: {base}
head_commit: {head}
toolkit_revision: {toolkit}
policy_identity:
  id: core-default
  version: "1"
basis_digest: {digest}
started: 2026-07-24T09:00:00+00:00
ended: 2026-07-24T09:30:00+00:00
budget:
  tokens: 12000
  wall_clock_seconds: 1800.5
disposition: clean
---

Swept stale status lines in conventions/.
"""


def _write_record(root: Path, stem: str = "2026-07-24-curation-sweep-a3f1") -> Path:
    """Write the canonical valid record. Tests that need a variant edit the text after."""
    runs = root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    path = runs / f"{stem}.md"
    path.write_text(
        _RECORD.format(base="a" * 40, head="b" * 40, toolkit="c" * 40, digest="d" * 64),
        encoding="utf-8",
    )
    return path


def test_no_runs_directory_yields_no_records(tmp_path: Path) -> None:
    assert load_run_records(tmp_path) == []


def test_empty_runs_directory_yields_no_records(tmp_path: Path) -> None:
    (tmp_path / "runs").mkdir()
    assert load_run_records(tmp_path) == []


def test_one_record_loads(tmp_path: Path) -> None:
    _write_record(tmp_path)
    records = load_run_records(tmp_path)
    assert [record.id for record in records] == ["run:2026-07-24-curation-sweep-a3f1"]
    assert records[0].agent == "curation-sweep"


def test_records_load_in_filename_order(tmp_path: Path) -> None:
    _write_record(tmp_path)
    second = _write_record(tmp_path, stem="2026-07-25-curation-sweep-b7c2")
    second.write_text(
        second.read_text(encoding="utf-8")
        .replace("2026-07-24-curation-sweep-a3f1", "2026-07-25-curation-sweep-b7c2")
        .replace("2026-07-24T09", "2026-07-25T09"),
        encoding="utf-8",
    )
    assert [record.slug for record in load_run_records(tmp_path)] == [
        "2026-07-24-curation-sweep-a3f1",
        "2026-07-25-curation-sweep-b7c2",
    ]


def test_filename_must_agree_with_the_id(tmp_path: Path) -> None:
    _write_record(tmp_path, stem="2026-07-24-curation-sweep-zzzz")
    with pytest.raises(RunRecordError, match="disagrees with filename"):
        load_run_records(tmp_path)


def test_malformed_record_raises(tmp_path: Path) -> None:
    path = _write_record(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace("disposition: clean", "disposition: passed"),
        encoding="utf-8",
    )
    with pytest.raises(RunRecordError, match="invalid run record"):
        load_run_records(tmp_path)


def test_record_without_frontmatter_raises(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "2026-07-24-curation-sweep-a3f1.md").write_text("just prose\n", encoding="utf-8")
    with pytest.raises(RunRecordError, match="no frontmatter"):
        load_run_records(tmp_path)


def test_nested_directory_raises_rather_than_being_skipped(tmp_path: Path) -> None:
    # A record filed one level down would otherwise be silently unattested.
    _write_record(tmp_path)
    (tmp_path / "runs" / "2026").mkdir()
    with pytest.raises(RunRecordError, match="flat"):
        load_run_records(tmp_path)


def test_runs_as_a_regular_file_raises(tmp_path: Path) -> None:
    # `is_dir()` is False here, so a plain "no runs directory -> []" would report a
    # project with a broken runs path as a project that never ran unattended.
    (tmp_path / "runs").write_text("not a directory\n", encoding="utf-8")
    with pytest.raises(RunRecordError, match="not a directory"):
        load_run_records(tmp_path)


def test_symlinked_runs_directory_raises(tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (tmp_path / "runs").symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(RunRecordError, match="symlink"):
        load_run_records(tmp_path)


def test_symlinked_record_raises(tmp_path: Path) -> None:
    # An out-of-tree file must not be able to become an accepted attestation.
    outside = tmp_path / "outside.md"
    outside.write_text(
        _RECORD.format(base="a" * 40, head="b" * 40, toolkit="c" * 40, digest="d" * 64),
        encoding="utf-8",
    )
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "2026-07-24-curation-sweep-a3f1.md").symlink_to(outside)
    with pytest.raises(RunRecordError, match="symlink"):
        load_run_records(tmp_path)


def test_non_markdown_child_raises(tmp_path: Path) -> None:
    # Including README.md's absence of a run shape: runs/ holds run records only.
    _write_record(tmp_path)
    (tmp_path / "runs" / "notes.txt").write_text("scratch\n", encoding="utf-8")
    with pytest.raises(RunRecordError, match="flat"):
        load_run_records(tmp_path)


def test_duplicate_top_level_key_raises(tmp_path: Path) -> None:
    # yaml.safe_load collapses this to the LAST value, so `extra="forbid"` never sees it.
    # A record that declares two tiers must not be read as declaring one.
    path = _write_record(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "tier: belief-neutral", "tier: report-only\ntier: belief-neutral"
        ),
        encoding="utf-8",
    )
    with pytest.raises(RunRecordError, match="duplicate key"):
        load_run_records(tmp_path)


def test_duplicate_nested_key_raises(tmp_path: Path) -> None:
    path = _write_record(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "  version: \"1\"", "  version: \"1\"\n  version: \"2\""
        ),
        encoding="utf-8",
    )
    with pytest.raises(RunRecordError, match="duplicate key"):
        load_run_records(tmp_path)


def test_yaml_merge_key_raises(tmp_path: Path) -> None:
    path = _write_record(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "disposition: clean", "disposition: clean\n<<: {tier: report-only}"
        ),
        encoding="utf-8",
    )
    with pytest.raises(RunRecordError, match="merge key"):
        load_run_records(tmp_path)


def test_undecodable_record_raises(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "2026-07-24-curation-sweep-a3f1.md").write_bytes(b"---\n\xff\xfe\n---\n")
    with pytest.raises(RunRecordError):
        load_run_records(tmp_path)


def test_unparseable_yaml_raises(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "2026-07-24-curation-sweep-a3f1.md").write_text(
        "---\nid: [unclosed\n---\n\nBody.\n", encoding="utf-8"
    )
    with pytest.raises(RunRecordError):
        load_run_records(tmp_path)


def test_malformed_opening_delimiter_raises(tmp_path: Path) -> None:
    # `text.startswith("---")` accepts this; a line-exact check must not.
    path = _write_record(tmp_path)
    path.write_text(
        "---not-a-delimiter\n" + path.read_text(encoding="utf-8").split("\n", 1)[1],
        encoding="utf-8",
    )
    with pytest.raises(RunRecordError, match="delimiter line"):
        load_run_records(tmp_path)


def test_malformed_closing_delimiter_raises(tmp_path: Path) -> None:
    path = _write_record(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "disposition: clean\n---\n", "disposition: clean\n---not-a-delimiter\n"
        ),
        encoding="utf-8",
    )
    with pytest.raises(RunRecordError, match="unterminated"):
        load_run_records(tmp_path)


def test_triple_dash_inside_a_value_does_not_truncate_the_block(tmp_path: Path) -> None:
    # `text.split("---", 2)` cuts here, silently dropping every field after `model` --
    # including `tier` and `disposition`. A line-exact scan must read the whole block.
    path = _write_record(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "model: claude-opus-5", "model: claude---opus---5"
        ),
        encoding="utf-8",
    )
    record = load_run_records(tmp_path)[0]
    assert record.model == "claude---opus---5"
    assert record.disposition.value == "clean"


def _record(tmp_path: Path):
    _write_record(tmp_path)
    return load_run_records(tmp_path)[0]


def test_node_uri_is_derived_from_the_slug(tmp_path: Path) -> None:
    record = _record(tmp_path)
    assert run_node_uri(record.id) == URIRef(PROJECT_NS["run/2026-07-24-curation-sweep-a3f1"])


def test_node_uri_accepts_the_id_string_directly(tmp_path: Path) -> None:
    record = _record(tmp_path)
    assert run_node_uri("run:2026-07-24-curation-sweep-a3f1") == run_node_uri(record.id)


def test_emission_writes_the_attested_fields(tmp_path: Path) -> None:
    record = _record(tmp_path)
    graph = Graph()
    add_run_record_to_graph(record, graph)
    node = run_node_uri(record.id)
    assert (node, RDF.type, SCI_NS.AutonomousRun) in graph
    assert (node, RDF.type, PROV.Activity) in graph
    assert (node, SCI_NS.runId, Literal(record.id)) in graph
    assert (node, SCI_NS.runAgent, Literal("curation-sweep")) in graph
    assert (node, SCI_NS.runModel, Literal("claude-opus-5")) in graph
    assert (node, SCI_NS.runTier, Literal("belief-neutral")) in graph
    assert (node, SCI_NS.runBranch, Literal("auto/2026-07-24-curation-sweep-a3f1")) in graph
    assert (node, SCI_NS.runBaseCommit, Literal("a" * 40)) in graph
    assert (node, SCI_NS.runHeadCommit, Literal("b" * 40)) in graph
    assert (node, SCI_NS.runToolkitRevision, Literal("c" * 40)) in graph
    assert (node, SCI_NS.runPolicyId, Literal("core-default")) in graph
    assert (node, SCI_NS.runPolicyVersion, Literal("1")) in graph
    assert (node, SCI_NS.runBasisDigest, Literal("d" * 64)) in graph
    assert (node, SCI_NS.runDisposition, Literal("clean")) in graph
    assert (node, SCI_NS.runBudgetTokens, Literal(12000)) in graph
    assert (node, SCI_NS.runBudgetWallClockSeconds, Literal(1800.5)) in graph
    assert (
        node,
        PROV.startedAtTime,
        Literal("2026-07-24T09:00:00+00:00", datatype=XSD.dateTime),
    ) in graph
    assert (
        node,
        PROV.endedAtTime,
        Literal("2026-07-24T09:30:00+00:00", datatype=XSD.dateTime),
    ) in graph


def test_absent_triggered_by_emits_no_triple(tmp_path: Path) -> None:
    record = _record(tmp_path)
    graph = Graph()
    add_run_record_to_graph(record, graph)
    assert (run_node_uri(record.id), SCI_NS.runTriggeredBy, None) not in graph


def test_triggered_by_emits_when_present(tmp_path: Path) -> None:
    path = _write_record(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "disposition: clean",
            "disposition: clean\ntriggered_by: schedule:weekly-curation",
        ),
        encoding="utf-8",
    )
    record = load_run_records(tmp_path)[0]
    graph = Graph()
    add_run_record_to_graph(record, graph)
    node = run_node_uri(record.id)
    assert (node, SCI_NS.runTriggeredBy, Literal("schedule:weekly-curation")) in graph


def test_budget_with_one_measure_emits_only_that_measure(tmp_path: Path) -> None:
    path = _write_record(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace("  wall_clock_seconds: 1800.5\n", ""),
        encoding="utf-8",
    )
    record = load_run_records(tmp_path)[0]
    graph = Graph()
    add_run_record_to_graph(record, graph)
    node = run_node_uri(record.id)
    assert (node, SCI_NS.runBudgetTokens, Literal(12000)) in graph
    assert (node, SCI_NS.runBudgetWallClockSeconds, None) not in graph


def test_emission_is_idempotent(tmp_path: Path) -> None:
    record = _record(tmp_path)
    once, twice = Graph(), Graph()
    add_run_record_to_graph(record, once)
    add_run_record_to_graph(record, twice)
    add_run_record_to_graph(record, twice)
    assert set(once) == set(twice)


def test_yaml_equivalent_duplicate_keys_raise(tmp_path: Path) -> None:
    # `yes:` and `true:` are DIFFERENT raw scalar text but both resolve to `True`, so a
    # duplicate check that compares `key_node.value` misses the pair while `yaml.safe_load`
    # collapses it to `{True: <last>}`. Comparing constructed objects is what catches it.
    path = _write_record(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "tier: belief-neutral", "tier: belief-neutral\nyes: 1\ntrue: 2"
        ),
        encoding="utf-8",
    )
    with pytest.raises(RunRecordError, match="duplicate key"):
        load_run_records(tmp_path)


def test_yaml_equivalent_duplicate_nested_keys_raise(tmp_path: Path) -> None:
    path = _write_record(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "  version: \"1\"", "  version: \"1\"\n  1: a\n  1.0: b"
        ),
        encoding="utf-8",
    )
    with pytest.raises(RunRecordError, match="duplicate key"):
        load_run_records(tmp_path)
