import json
from datetime import datetime, timezone
from pathlib import Path

from click.testing import CliRunner

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


def _setup(tmp_path: Path):
    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    (tmp_path / "papers").mkdir()
    md = tmp_path / "papers" / "p.source.md"
    md.write_text("Genes encode proteins.\n", encoding="utf-8")
    sp = anno_io.sidecar_for_markdown(md)
    ann = Annotation(
        id="a-1",
        target=SpecificResource(source="p.source.md", selector=TextQuoteSelector(exact="Genes encode proteins", prefix="", suffix="")),
        bodies=(TextualBody(value='{"section":"abstract","stance":"asserted"}', format="application/json"),),
        motivation=Motivation.CLASSIFYING, annotation_type="proposition",
        source="llm-annot:m:paper-annotate-v1", status=Status.OPEN,
        creator="paper-annotate", created=datetime(2026, 6, 16, tzinfo=timezone.utc),
        content_hash="0" * 64,  # required for llm-annot: source
    )
    anno_io.write_sidecar(sp, anno_io.Sidecar(annotations=(ann,)))
    return md, sp


def test_promote_readonly_writes_nothing(tmp_path):
    md, sp = _setup(tmp_path)
    r = CliRunner().invoke(annotate_group, ["promote", str(md), "--root", str(tmp_path), "--format", "json"])
    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    assert payload["candidates"][0]["decision"] == "MINT"
    # nothing written
    assert not list((tmp_path / "entities" / "propositions").glob("*.md"))
    assert read_sidecar_strict(sp).annotations[0].promoted_to is None


def test_promote_apply_mints_and_backlinks(tmp_path):
    md, sp = _setup(tmp_path)
    r = CliRunner().invoke(annotate_group, ["promote", str(md), "--root", str(tmp_path),
                                            "--paper-ref", "paper:p", "--apply"])
    assert r.exit_code == 0, r.output
    prop = (tmp_path / "entities" / "propositions" / "genes-encode-proteins.md")
    assert prop.exists()
    assert "annotation:papers/p.source#a-1" in prop.read_text(encoding="utf-8")
    assert read_sidecar_strict(sp).annotations[0].promoted_to == "proposition:genes-encode-proteins"


def test_promote_apply_input_override_links(tmp_path):
    # End-to-end --input contract: read-only JSON → edit a row to LINK → feed back via --apply.
    md, sp = _setup(tmp_path)
    (tmp_path / "entities" / "propositions" / "preexisting.md").write_text(
        '---\nid: proposition:preexisting\ntype: proposition\ntitle: Preexisting\n'
        'status: draft\ncreated: "2026-06-16"\nupdated: "2026-06-16"\n---\n# Preexisting\n',
        encoding="utf-8",
    )
    ro = CliRunner().invoke(annotate_group, ["promote", str(md), "--root", str(tmp_path), "--format", "json"])
    assert ro.exit_code == 0, ro.output
    payload = json.loads(ro.output)
    payload["candidates"][0]["decision"] = "LINK"
    payload["candidates"][0]["slug"] = "proposition:preexisting"
    edited = tmp_path / "edited.json"
    edited.write_text(json.dumps(payload), encoding="utf-8")
    r = CliRunner().invoke(annotate_group, ["promote", str(md), "--root", str(tmp_path),
                                            "--apply", "--input", str(edited)])
    assert r.exit_code == 0, r.output
    assert read_sidecar_strict(sp).annotations[0].promoted_to == "proposition:preexisting"
    assert "annotation:papers/p.source#a-1" in (tmp_path / "entities" / "propositions" / "preexisting.md").read_text(encoding="utf-8")


def test_promote_malformed_input_fails_loud(tmp_path):
    md, _ = _setup(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json", encoding="utf-8")
    r = CliRunner().invoke(annotate_group, ["promote", str(md), "--root", str(tmp_path),
                                            "--apply", "--input", str(bad)])
    assert r.exit_code != 0


def test_promote_input_without_apply_fails_loud(tmp_path):
    # --input without --apply must fail loud, not silently discard the curator's overrides.
    md, _ = _setup(tmp_path)
    edited = tmp_path / "edited.json"
    edited.write_text('{"candidates": []}', encoding="utf-8")
    r = CliRunner().invoke(annotate_group, ["promote", str(md), "--root", str(tmp_path),
                                            "--input", str(edited)])
    assert r.exit_code != 0
    assert "--input requires --apply" in r.output


def test_minted_proposition_materializes_wasderivedfrom(tmp_path):
    # After apply, the minted proposition's annotation: + paper: refs materialize wasDerivedFrom;
    # a cite: ref would not (regression guard).
    from science_tool.graph.materialize import _annotation_uri
    md, sp = _setup(tmp_path)
    CliRunner().invoke(annotate_group, ["promote", str(md), "--root", str(tmp_path),
                                        "--paper-ref", "paper:p", "--apply"])
    text = (tmp_path / "entities" / "propositions" / "genes-encode-proteins.md").read_text(encoding="utf-8")
    assert "annotation:papers/p.source#a-1" in text and "paper:p" in text
    # URI minter is stable + distinct from a bibliography ref
    assert str(_annotation_uri("annotation:papers/p.source#a-1")).endswith("#a-1")


def test_promote_apply_without_paper_ref_uses_adapter_default(tmp_path):
    # No --paper-ref: the default must come from PaperSourceAdapter.source_ref,
    # i.e. p.source.md -> paper:p, recorded in the minted proposition body.
    md, sp = _setup(tmp_path)
    r = CliRunner().invoke(annotate_group, ["promote", str(md), "--root", str(tmp_path), "--apply"])
    assert r.exit_code == 0, r.output
    text = (tmp_path / "entities" / "propositions" / "genes-encode-proteins.md").read_text(encoding="utf-8")
    assert "paper:p" in text


def test_promote_explicit_paper_ref_does_not_touch_adapter(tmp_path, monkeypatch):
    # An explicit --paper-ref must bypass resolve_adapter entirely (High-severity guard):
    # if the code wrongly resolves an adapter, this raises and the command fails.
    import science_tool.annotation.text_source_adapter as sa

    def boom(_source_md):
        raise sa.TextSourceAdapterError("resolve_adapter must not be called when --paper-ref is given")

    monkeypatch.setattr(sa, "resolve_adapter", boom)
    md, sp = _setup(tmp_path)
    r = CliRunner().invoke(annotate_group, ["promote", str(md), "--root", str(tmp_path),
                                            "--paper-ref", "paper:x", "--apply"])
    assert r.exit_code == 0, r.output
    text = (tmp_path / "entities" / "propositions" / "genes-encode-proteins.md").read_text(encoding="utf-8")
    assert "paper:x" in text


def test_promote_unhandled_source_fails_loud(tmp_path):
    # No adapter handles a non-.source.md file and no --paper-ref given:
    # the TextSourceAdapterError must surface as a clean CLI error, not a traceback.
    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    notes = tmp_path / "notes.md"
    notes.write_text("Some prose.\n", encoding="utf-8")
    r = CliRunner().invoke(annotate_group, ["promote", str(notes), "--root", str(tmp_path)])
    assert r.exit_code != 0
    assert "no text source adapter handles" in r.output
