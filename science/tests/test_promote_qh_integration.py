import json
from datetime import datetime, timezone
from pathlib import Path

from click.testing import CliRunner
from rdflib import Dataset, Namespace

from science_tool.annotation import io as anno_io
from science_tool.annotation.cli import annotate_group
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.query import read_sidecar_strict
from science_tool.graph.materialize import _annotation_uri, materialize_graph

PROJECT_NS = Namespace("http://example.org/project/")
PROV = Namespace("http://www.w3.org/ns/prov#")


def _setup_statement(tmp_path: Path, *, atype: str, exact: str, frag: str = "s1"):
    """Minimal project: a papers/p.source.md sidecar with one OPEN statement annotation.

    Also authors the `paper:p` entity that the default `--paper-ref` records in the
    minted entity's `source_refs`; without it, `materialize_graph` hard-fails on the
    unresolved `paper:p` reference (the audit gate), masking the wasDerivedFrom check.
    """
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    papers_dir = tmp_path / "entities" / "papers"
    papers_dir.mkdir(parents=True)
    (papers_dir / "p.md").write_text(
        "---\nid: paper:p\ntype: paper\ntitle: Demo Paper\nstatus: active\n"
        'created: "2026-06-16"\nupdated: "2026-06-16"\n---\n# Demo Paper\n\nSummary.\n',
        encoding="utf-8",
    )
    (tmp_path / "papers").mkdir()
    md = tmp_path / "papers" / "p.source.md"
    md.write_text(f"{exact}.\n", encoding="utf-8")
    sp = anno_io.sidecar_for_markdown(md)
    ann = Annotation(
        id=frag,
        target=SpecificResource(source="p.source.md",
                                selector=TextQuoteSelector(exact=exact, prefix="", suffix="")),
        bodies=(TextualBody(value='{"section":"abstract","stance":"asserted"}', format="application/json"),),
        motivation=Motivation.CLASSIFYING, annotation_type=atype,
        source="llm-annot:m:paper-annotate-v1", status=Status.OPEN,
        creator="paper-annotate", created=datetime(2026, 6, 16, tzinfo=timezone.utc),
        content_hash="0" * 64,  # required for llm-annot: source
    )
    anno_io.write_sidecar(sp, anno_io.Sidecar(annotations=(ann,)))
    return md, sp


def test_question_promote_round_trip(tmp_path):
    md, sp = _setup_statement(tmp_path, atype="question", exact="What regulates X", frag="q1")
    r = CliRunner().invoke(annotate_group, ["promote", str(md), "--root", str(tmp_path), "--apply"])
    assert r.exit_code == 0, r.output

    qdir = tmp_path / "entities" / "questions"
    minted = list(qdir.glob("*.md"))                # count ALL question files, not just 0001-*
    assert len(minted) == 1
    text = minted[0].read_text(encoding="utf-8")
    assert minted[0].name.startswith("0001-")
    assert "status: active" in text and "phase:" not in text
    assert "paper:p" in text
    assert "annotation:papers/p.source#q1" in text
    assert "## Summary" in text and "What regulates X" in text
    # provenance: the annotation ref mints a stable wasDerivedFrom URI (same minter 4a uses)
    assert str(_annotation_uri("annotation:papers/p.source#q1")).endswith("#q1")
    # backlink set, status untouched
    ann = read_sidecar_strict(sp).annotations[0]
    assert ann.promoted_to is not None and ann.promoted_to.startswith("question:0001-")
    assert ann.status == Status.OPEN
    # graph provenance: the promoted question points back to the exact source annotation.
    trig_path = materialize_graph(tmp_path)
    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])
    question_local_part = ann.promoted_to.split(":", 1)[1]
    question_uri = PROJECT_NS[f"question/{question_local_part}"]
    assert (question_uri, PROV.wasDerivedFrom, _annotation_uri("annotation:papers/p.source#q1")) in provenance

    # second --apply is a no-op (idempotent): still exactly one question entity total
    r2 = CliRunner().invoke(annotate_group, ["promote", str(md), "--root", str(tmp_path), "--apply"])
    assert r2.exit_code == 0, r2.output
    assert len(list(qdir.glob("*.md"))) == 1


def test_hypothesis_promote_is_candidate_phase(tmp_path):
    md, sp = _setup_statement(tmp_path, atype="hypothesis", exact="X drives Y", frag="h1")
    r = CliRunner().invoke(annotate_group, ["promote", str(md), "--root", str(tmp_path), "--apply"])
    assert r.exit_code == 0, r.output
    minted = list((tmp_path / "entities" / "hypotheses").glob("*.md"))
    assert len(minted) == 1
    text = minted[0].read_text(encoding="utf-8")
    assert "status: proposed" in text and "phase: candidate" in text
    assert "## Organizing Conjecture" in text and "X drives Y" in text


def test_idempotent_second_apply_via_json(tmp_path):
    md, sp = _setup_statement(tmp_path, atype="question", exact="What regulates X", frag="q1")
    CliRunner().invoke(annotate_group, ["promote", str(md), "--root", str(tmp_path), "--apply"])
    res = CliRunner().invoke(annotate_group,
                             ["promote", str(md), "--root", str(tmp_path), "--apply", "--format", "json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["minted"] == 0 and payload["linked"] == 0
    assert payload["skipped"].get("promote-already-promoted") == 1
