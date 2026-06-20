import json
from datetime import datetime, timezone
from pathlib import Path

from click.testing import CliRunner

from science_tool.annotation import io as anno_io
from science_tool.annotation.cli import annotate_group
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.entities import _parse_markdown_file
from science_tool.validate import ValidateContext
from science_tool.validate.checks.propositions import (
    check_canonical_enum_binding,
    check_polarity_predicate_aptitude,
)


def _project_with_statement(tmp_path: Path, exact: str):
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    papers = tmp_path / "entities" / "papers"
    papers.mkdir(parents=True)
    (papers / "p.md").write_text(
        "---\nid: paper:p\ntype: paper\ntitle: Demo\nstatus: active\n"
        'created: "2026-06-16"\nupdated: "2026-06-16"\n---\n# Demo\n\nx\n', encoding="utf-8")
    (tmp_path / "papers").mkdir()
    md = tmp_path / "papers" / "p.source.md"
    md.write_text(f"{exact}\n", encoding="utf-8")
    sp = anno_io.sidecar_for_markdown(md)
    ann = Annotation(
        id="s1",
        target=SpecificResource(source="p.source.md",
                                selector=TextQuoteSelector(exact=exact, prefix="", suffix="")),
        bodies=(TextualBody(value='{"section":"results","stance":"asserted",'
                            '"subject":"BRCA1","object":"genomic instability"}',
                            format="application/json"),),
        motivation=Motivation.CLASSIFYING, annotation_type="proposition",
        source="llm-annot:m:paper-annotate-v1", status=Status.OPEN,
        creator="paper-annotate", created=datetime(2026, 6, 16, tzinfo=timezone.utc),
        content_hash="0" * 64)
    anno_io.write_sidecar(sp, Sidecar(annotations=(ann,)))
    return md


def test_promote_then_synthesize_validates_clean(tmp_path):
    md = _project_with_statement(tmp_path, "BRCA1 affects genomic instability")
    runner = CliRunner()

    # 4a promote → mints a proposition with predicate/polarity/claim_layer UNSET
    rp = runner.invoke(annotate_group, ["promote", str(md), "--root", str(tmp_path), "--apply"])
    assert rp.exit_code == 0, rp.output
    [prop_file] = list((tmp_path / "entities" / "propositions").glob("*.md"))
    fm0, _ = _parse_markdown_file(prop_file)
    assert "predicate" not in fm0
    prop_ref = fm0["id"]

    # read-only scaffold sees the in-scope proposition + its statement
    rs = runner.invoke(annotate_group, ["synthesize", str(md), "--root", str(tmp_path)])
    assert rs.exit_code == 0, rs.output
    assert prop_ref in rs.output

    # curator candidates → apply
    cand = {"source": "llm-synth:m:proposition-synthesize-v1", "candidates": [{
        "proposition": prop_ref, "annotation": "annotation:papers/p.source#s1",
        "subject": "BRCA1", "object": "genomic instability",
        "predicate": "affects", "polarity": "positive", "claim_layer": "causal_effect"}]}
    cpath = tmp_path / "cand.json"
    cpath.write_text(json.dumps(cand), encoding="utf-8")
    ra = runner.invoke(annotate_group, ["synthesize", str(md), "--root", str(tmp_path),
                                        "--apply", "--input", str(cpath)])
    assert ra.exit_code == 0, ra.output

    fm1, _ = _parse_markdown_file(prop_file)
    assert fm1["predicate"] == "affects" and fm1["polarity"] == "positive"
    assert fm1["claim_layer"] == "causal_effect"
    assert fm1["reasoning_source"] == "llm-synth:m:proposition-synthesize-v1"

    # corpus QA checks pass on the synthesized proposition
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
    assert list(check_polarity_predicate_aptitude(ctx)) == []
    assert list(check_canonical_enum_binding(ctx)) == []

    # idempotent re-apply
    ra2 = runner.invoke(annotate_group, ["synthesize", str(md), "--root", str(tmp_path),
                                         "--apply", "--input", str(cpath), "--format", "json"])
    assert ra2.exit_code == 0, ra2.output
    assert json.loads(ra2.output)["updated"] == 0
