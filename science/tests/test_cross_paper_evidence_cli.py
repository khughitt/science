import json
from datetime import datetime, timezone

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

_CREATED = datetime(2026, 6, 30, tzinfo=timezone.utc)


def _manifest(root):
    (root / "science.yaml").write_text(
        "name: test\nknowledge_profiles:\n  local: local\n",
        encoding="utf-8",
    )


def _paper_entity(root, citekey):
    path = root / "entities" / "papers" / f"{citekey}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nid: paper:{citekey}\ntype: paper\ntitle: {citekey}\nstatus: active\n---\n\nAbstract.\n",
        encoding="utf-8",
    )


def _proposition_entity(root, slug, source_refs):
    path = root / "entities" / "propositions" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    refs = "".join(f"  - {ref}\n" for ref in source_refs)
    path.write_text(
        f"---\nid: proposition:{slug}\ntype: proposition\ntitle: {slug}\nstatus: active\n"
        f"source_refs:\n{refs}---\n\nClaim.\n",
        encoding="utf-8",
    )


def _promoted_ann(frag, *, stance, slug="claim"):
    body = json.dumps({"section": "results", "stance": stance})
    return Annotation(
        id=frag,
        target=SpecificResource(
            source="x.source.md",
            selector=TextQuoteSelector(exact=frag, prefix="", suffix=""),
        ),
        bodies=(TextualBody(value=body, format="application/json"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="proposition",
        source="llm-annot:m:paper-annotate-v1",
        status=Status.OPEN,
        creator="paper-annotate",
        created=_CREATED,
        content_hash="0" * 64,
        promoted_to=f"proposition:{slug}",
    )


def _paper_with_promoted(root, citekey, *, stance, slug="claim"):
    _paper_entity(root, citekey)
    md = root / "entities" / "papers" / f"{citekey}.source.md"
    md.write_text("Results show the claim.\n", encoding="utf-8")
    anno_io.write_sidecar(
        anno_io.sidecar_for_markdown(md),
        anno_io.Sidecar(
            annotations=(_promoted_ann(f"{citekey}-1", stance=stance, slug=slug),)
        ),
    )


def _ann_ref(citekey):
    return f"annotation:entities/papers/{citekey}.source#{citekey}-1"


def _scaffold(root):
    _manifest(root)
    _proposition_entity(
        root,
        "claim",
        ["paper:A2020", "paper:B2021", _ann_ref("A2020"), _ann_ref("B2021")],
    )
    _paper_with_promoted(root, "A2020", stance="asserted")
    _paper_with_promoted(root, "B2021", stance="negated")


def test_cli_project_wide_json_lists_assertions(tmp_path):
    _scaffold(tmp_path)
    result = CliRunner().invoke(
        annotate_group, ["cross-paper-evidence", "--root", str(tmp_path), "--format", "json"]
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["faults"] == []
    props = {p["proposition"]: p for p in payload["propositions"]}
    assert props["proposition:claim"]["supporting_papers"] == 1
    assert props["proposition:claim"]["disputing_papers"] == 1


def test_cli_project_wide_counts_same_paper_support_stances_once(tmp_path):
    _manifest(tmp_path)
    _proposition_entity(
        tmp_path,
        "claim",
        [
            "paper:A2020",
            _ann_ref("A2020"),
            "annotation:entities/papers/A2020.source#A2020-2",
        ],
    )
    _paper_with_promoted(tmp_path, "A2020", stance="asserted")
    md = tmp_path / "entities" / "papers" / "A2020.source.md"
    anno_io.write_sidecar(
        anno_io.sidecar_for_markdown(md),
        anno_io.Sidecar(
            annotations=(
                _promoted_ann("A2020-1", stance="asserted"),
                _promoted_ann("A2020-2", stance="hypothesized"),
            )
        ),
    )

    result = CliRunner().invoke(
        annotate_group, ["cross-paper-evidence", "--root", str(tmp_path), "--format", "json"]
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    props = {p["proposition"]: p for p in payload["propositions"]}
    assert props["proposition:claim"]["supporting_papers"] == 1
    assert props["proposition:claim"]["disputing_papers"] == 0


def test_cli_single_ref_json_lists_units(tmp_path):
    _scaffold(tmp_path)
    result = CliRunner().invoke(
        annotate_group,
        [
            "cross-paper-evidence",
            "--source",
            "proposition:claim",
            "--root",
            str(tmp_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    units = {(u["paper"], u["stance"]) for u in payload["units"]}
    assert units == {("paper:A2020", "asserted"), ("paper:B2021", "negated")}
    by_stance = {u["stance"]: u for u in payload["units"]}
    assert by_stance["asserted"]["role"] == "proxy_support"
    assert by_stance["asserted"]["strength"] == "moderate"
    assert by_stance["asserted"]["independence_group"] == "literature-paper:A2020"
    assert by_stance["negated"]["role"] == "proxy_support"
    assert by_stance["negated"]["strength"] == "moderate"
    assert by_stance["negated"]["independence_group"] == "literature-paper:B2021"
    assert payload["belief"]["contested"] is True
    assert payload["belief"]["contested_groups"] == []
    assert payload["belief"]["support_units"] == 1
    assert payload["belief"]["dispute_units"] == 1
    assert payload["belief"]["belief_magnitude"] == "fragile"


def test_cli_reports_faults_without_raising(tmp_path):
    _manifest(tmp_path)
    _proposition_entity(tmp_path, "claim", ["paper:A2020"])
    _paper_with_promoted(tmp_path, "A2020", stance="asserted", slug="ghost")
    result = CliRunner().invoke(
        annotate_group, ["cross-paper-evidence", "--root", str(tmp_path), "--format", "json"]
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert [f["reason"] for f in payload["faults"]] == ["stale-proposition"]


def test_cli_table_format_runs(tmp_path):
    _scaffold(tmp_path)
    result = CliRunner().invoke(annotate_group, ["cross-paper-evidence", "--root", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "proposition:claim" in result.output


def test_cli_rejects_non_proposition_source(tmp_path):
    _manifest(tmp_path)
    result = CliRunner().invoke(
        annotate_group, ["cross-paper-evidence", "--source", "question:q", "--root", str(tmp_path)]
    )

    assert result.exit_code != 0
