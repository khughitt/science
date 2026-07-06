import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner
from science_model.propositions import PropositionEntity

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
from science_tool.annotation.synthesize import (
    SynthesisApplyError,
    SynthesisCandidate,
    SynthesisOverrideError,
    SynthesisReadError,
    apply_synthesis,
    build_scaffold,
    in_scope_propositions,
    parse_candidates_doc,
    plan_writes,
    relation_hints,
    statement_context,
    validate_candidate,
)
from science_tool.entities import _parse_markdown_file, write_entity_file


def _ann(frag, atype, exact, *, body, promoted_to=None, status=Status.OPEN):
    return Annotation(
        id=frag,
        target=SpecificResource(source="p.source.md",
                                selector=TextQuoteSelector(exact=exact, prefix="", suffix="")),
        bodies=(TextualBody(value=body, format="application/json"),),
        motivation=Motivation.CLASSIFYING, annotation_type=atype,
        source="llm-annot:m:paper-annotate-v1", status=status,
        creator="paper-annotate", created=datetime(2026, 6, 16, tzinfo=timezone.utc),
        content_hash="0" * 64, promoted_to=promoted_to,
    )


def test_in_scope_groups_by_promoted_proposition():
    a = _ann("s1", "proposition", "X drives Y",
             body='{"section":"results","stance":"asserted","subject":"X","object":"Y"}',
             promoted_to="proposition:x-drives-y")
    b = _ann("s2", "proposition", "X drives Y too",
             body='{"section":"results","stance":"asserted"}',
             promoted_to="proposition:x-drives-y")
    q = _ann("q1", "question", "What about Z", body='{"section":"results","stance":"open"}',
             promoted_to="question:0001-z")          # not a proposition → excluded
    u = _ann("s3", "proposition", "Unpromoted",
             body='{"section":"results","stance":"asserted"}')   # promoted_to=None → excluded
    sc = Sidecar(annotations=(a, b, q, u))
    scope = in_scope_propositions(sc)
    assert set(scope) == {"proposition:x-drives-y"}
    assert [x.id for x in scope["proposition:x-drives-y"]] == ["s1", "s2"]


def test_statement_context_extracts_body_fields():
    a = _ann("s1", "proposition", "X drives Y",
             body='{"section":"results","stance":"asserted","subject":"X","object":"Y"}')
    ctx = statement_context(a, "annotation:papers/p.source#s1")
    assert ctx == {
        "annotation": "annotation:papers/p.source#s1",
        "exact": "X drives Y", "section": "results", "stance": "asserted",
        "subject": "X", "object": "Y",
    }


def _rel(frag, exact, *, predicate, subj, obj):
    body = (
        '{"object":"%s","predicate":"%s","predicate_source":"biored",'
        '"subject":"%s"}' % (obj, predicate, subj)
    )
    return _ann(frag, "relation", exact, body=body)


def test_relation_hints_overlap_and_unresolved_count():
    file_text = "alpha BRCA1 affects genomic instability omega"
    stmt = _ann("s1", "proposition", "BRCA1 affects genomic instability",
                body='{"section":"results","stance":"asserted"}',
                promoted_to="proposition:p")
    # overlapping relation (its exact lies inside the statement span)
    hit = _rel("r1", "BRCA1 affects", predicate="biolink:affects",
               subj="ncbigene:672", obj="GO:0006281")
    # relation whose exact is not in file_text → unresolved, counted, omitted
    miss = _rel("r2", "NOT PRESENT", predicate="biolink:regulates",
                subj="a", obj="b")
    hints, unresolved = relation_hints(file_text, [stmt], [hit, miss])
    assert unresolved == 1
    assert hints == [{
        "annotation_frag": "r1", "predicate": "biolink:affects",
        "subject": "ncbigene:672", "object": "GO:0006281",
    }]


def test_build_scaffold_shape():
    file_text = "BRCA1 affects genomic instability"
    stmt = _ann("s1", "proposition", "BRCA1 affects genomic instability",
                body='{"section":"results","stance":"asserted","subject":"BRCA1"}',
                promoted_to="proposition:brca1")
    sc = Sidecar(annotations=(stmt,))
    current = {"proposition:brca1": {"title": "BRCA1 claim", "subject": "BRCA1"}}
    scaffold, unresolved = build_scaffold(
        sc, file_text, current,
        ref_for=lambda frag: f"annotation:papers/p.source#{frag}",
    )
    assert scaffold["source"] == "llm-synth:<MODEL>:proposition-synthesize-v1"
    assert unresolved == 0
    [entry] = scaffold["propositions"]
    assert entry["proposition"] == "proposition:brca1"
    assert entry["title"] == "BRCA1 claim"
    assert entry["current"] == {"subject": "BRCA1", "object": None, "predicate": None,
                                "polarity": None, "claim_layer": None}
    assert entry["statements"][0]["annotation"] == "annotation:papers/p.source#s1"
    assert entry["relation_hints"] == []


# in-scope set + per-proposition supporting-statement refs the parser validates against
SCOPE = {"proposition:p": {"annotation:papers/p.source#s1"}}
SRC = "llm-synth:claude-opus-4-8:proposition-synthesize-v1"


def _doc(candidates, source=SRC):
    return {"source": source, "candidates": candidates}


def test_parse_minimal_candidate():
    doc = _doc([{
        "proposition": "proposition:p", "annotation": "annotation:papers/p.source#s1",
        "predicate": "affects", "subject": "X", "object": "Y", "polarity": "positive",
        "claim_layer": "causal_effect",
    }])
    source, cands = parse_candidates_doc(doc, SCOPE)
    assert source == SRC
    assert cands == [SynthesisCandidate(
        proposition="proposition:p", annotation="annotation:papers/p.source#s1",
        fields={"predicate": "affects", "subject": "X", "object": "Y",
                "polarity": "positive", "claim_layer": "causal_effect"},
        override=frozenset(),
    )]


def test_bad_source_rejected():
    with pytest.raises(SynthesisReadError, match="source"):
        parse_candidates_doc(_doc([], source="llm-synth:<MODEL>:proposition-synthesize-v1"), SCOPE)


def test_duplicate_proposition_rejected():
    row = {"proposition": "proposition:p", "annotation": "annotation:papers/p.source#s1",
           "claim_layer": "causal_effect"}
    with pytest.raises(SynthesisReadError, match="duplicate"):
        parse_candidates_doc(_doc([row, dict(row)]), SCOPE)


def test_explicit_null_field_rejected():
    with pytest.raises(SynthesisReadError, match="null|omit"):
        parse_candidates_doc(_doc([{
            "proposition": "proposition:p", "annotation": "annotation:papers/p.source#s1",
            "claim_layer": None,
        }]), SCOPE)


def test_unknown_enum_value_rejected():
    with pytest.raises(SynthesisReadError, match="claim_layer"):
        parse_candidates_doc(_doc([{
            "proposition": "proposition:p", "annotation": "annotation:papers/p.source#s1",
            "claim_layer": "made_up",
        }]), SCOPE)


def test_out_of_scope_proposition_rejected():
    with pytest.raises(SynthesisReadError, match="in scope|scope"):
        parse_candidates_doc(_doc([{
            "proposition": "proposition:other", "annotation": "annotation:papers/p.source#s1",
            "claim_layer": "causal_effect",
        }]), SCOPE)


def test_annotation_not_supporting_rejected():
    with pytest.raises(SynthesisReadError, match="annotation"):
        parse_candidates_doc(_doc([{
            "proposition": "proposition:p", "annotation": "annotation:papers/p.source#sX",
            "claim_layer": "causal_effect",
        }]), SCOPE)


def test_override_must_name_a_present_field():
    with pytest.raises(SynthesisReadError, match="override"):
        parse_candidates_doc(_doc([{
            "proposition": "proposition:p", "annotation": "annotation:papers/p.source#s1",
            "claim_layer": "causal_effect", "override": ["predicate"],
        }]), SCOPE)


def test_override_rejects_reasoning_source():
    with pytest.raises(SynthesisReadError, match="override"):
        parse_candidates_doc(_doc([{
            "proposition": "proposition:p", "annotation": "annotation:papers/p.source#s1",
            "claim_layer": "causal_effect", "override": ["reasoning_source"],
        }]), SCOPE)


def _cand(fields, override=frozenset(), prop="proposition:p",
          ann="annotation:papers/p.source#s1"):
    return SynthesisCandidate(proposition=prop, annotation=ann, fields=fields, override=override)


def test_plan_writes_fill_only_unset():
    current = {"subject": "X"}                      # object/predicate/... unset
    cand = _cand({"subject": "X2", "object": "Y", "claim_layer": "causal_effect"})
    plan = plan_writes(current, cand)
    # subject already set & different & no override → blocked; object/claim_layer fill
    assert plan.writes == {"object": "Y", "claim_layer": "causal_effect"}
    assert plan.blocked == ("subject",)


def test_plan_writes_override_replaces():
    current = {"claim_layer": "empirical_regularity"}
    cand = _cand({"claim_layer": "causal_effect"}, override=frozenset({"claim_layer"}))
    plan = plan_writes(current, cand)
    assert plan.writes == {"claim_layer": "causal_effect"} and plan.blocked == ()


def test_plan_writes_signless_canonicalizes_polarity():
    current: dict = {}
    cand = _cand({"subject": "X", "object": "Y", "predicate": "binds"})   # sign-less
    plan = plan_writes(current, cand)
    assert plan.writes["polarity"] == "not_applicable"


def test_validate_predicate_requires_operands():
    current: dict = {}
    cand = _cand({"predicate": "affects", "subject": "X", "polarity": "positive"})  # no object
    with pytest.raises(SynthesisApplyError, match="subject and object|object"):
        validate_candidate(current, cand)


def test_validate_polarity_requires_predicate():
    current: dict = {}
    cand = _cand({"polarity": "positive"})         # bare polarity, no predicate
    with pytest.raises(SynthesisApplyError, match="predicate"):
        validate_candidate(current, cand)


def test_validate_sign_meaningful_missing_polarity_fails():
    current: dict = {}
    cand = _cand({"subject": "X", "object": "Y", "predicate": "affects"})  # needs signed polarity
    with pytest.raises(SynthesisApplyError):
        validate_candidate(current, cand)


def test_validate_override_of_unset_field_rejected():
    # override may only name a CURRENTLY-SET field; current={} ⇒ hard error (design §6/§7).
    cand = _cand({"claim_layer": "causal_effect"}, override=frozenset({"claim_layer"}))
    with pytest.raises(SynthesisOverrideError, match="override|unset"):
        validate_candidate({}, cand)


def test_validate_ok_returns_plan():
    current = {"subject": "X", "object": "Y"}
    cand = _cand({"predicate": "regulates", "polarity": "negative", "claim_layer": "causal_effect"})
    plan = validate_candidate(current, cand)
    assert plan.writes == {"predicate": "regulates", "polarity": "negative",
                           "claim_layer": "causal_effect"}


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    return tmp_path


def _write_prop(root: Path, slug: str, *, title: str, body: str = "# t\n\n## Claim\n\nKEEP-ME\n",
                **fields) -> str:
    ref = f"proposition:{slug}"
    write_entity_file(PropositionEntity(id=ref, title=title, **fields),
                      project_root=root, body=body)
    return ref


def test_apply_fills_unset_and_stamps_source(tmp_path):
    root = _project(tmp_path)
    ref = _write_prop(root, "p", title="claim", subject="X", object="Y",
                      body="# claim\n\n## Claim\n\nCURATED PROSE\n")
    cand = _cand({"predicate": "affects", "polarity": "positive", "claim_layer": "causal_effect"},
                 prop=ref)
    report = apply_synthesis(
        [cand], current={ref: _parse_markdown_file(root / "entities/propositions/p.md")[0]},
        project_root=root, source="llm-synth:m:proposition-synthesize-v1", in_scope={ref},
    )
    assert report.updated == 1
    fm, body = _parse_markdown_file(root / "entities/propositions/p.md")
    assert fm["predicate"] == "affects" and fm["polarity"] == "positive"
    assert fm["claim_layer"] == "causal_effect"
    assert fm["reasoning_source"] == "llm-synth:m:proposition-synthesize-v1"
    assert "CURATED PROSE" in body          # body preserved


def test_apply_noop_when_already_filled_leaves_file_untouched(tmp_path):
    root = _project(tmp_path)
    ref = _write_prop(root, "p", title="claim", subject="X", object="Y",
                      claim_layer="causal_effect")
    before = (root / "entities/propositions/p.md").read_text(encoding="utf-8")
    cand = _cand({"claim_layer": "causal_effect"}, prop=ref)
    report = apply_synthesis(
        [cand], current={ref: _parse_markdown_file(root / "entities/propositions/p.md")[0]},
        project_root=root, source="llm-synth:m:proposition-synthesize-v1", in_scope={ref},
    )
    assert report.updated == 0
    assert report.skipped.get("synthesize-nothing-to-fill") == 1
    after = (root / "entities/propositions/p.md").read_text(encoding="utf-8")
    assert after == before                   # untouched: no reasoning_source, no updated bump


def test_apply_existing_value_blocks(tmp_path):
    root = _project(tmp_path)
    ref = _write_prop(root, "p", title="claim", claim_layer="empirical_regularity")
    cand = _cand({"claim_layer": "causal_effect"}, prop=ref)   # differs, no override
    report = apply_synthesis(
        [cand], current={ref: _parse_markdown_file(root / "entities/propositions/p.md")[0]},
        project_root=root, source="llm-synth:m:proposition-synthesize-v1", in_scope={ref},
    )
    assert report.updated == 0
    assert report.skipped.get("synthesize-existing-value-blocks") == 1
    fm, _ = _parse_markdown_file(root / "entities/propositions/p.md")
    assert fm["claim_layer"] == "empirical_regularity"        # unchanged


def test_apply_reports_blocked_fields_even_when_other_fields_write(tmp_path):
    root = _project(tmp_path)
    ref = _write_prop(root, "p", title="claim", claim_layer="empirical_regularity")
    cand = _cand({"subject": "X", "claim_layer": "causal_effect"}, prop=ref)
    report = apply_synthesis(
        [cand], current={ref: _parse_markdown_file(root / "entities/propositions/p.md")[0]},
        project_root=root, source="llm-synth:m:proposition-synthesize-v1", in_scope={ref},
    )
    assert report.updated == 1
    assert report.skipped.get("synthesize-existing-value-blocks") == 1
    fm, _ = _parse_markdown_file(root / "entities/propositions/p.md")
    assert fm["subject"] == "X"
    assert fm["claim_layer"] == "empirical_regularity"        # blocked value preserved
    assert fm["reasoning_source"] == "llm-synth:m:proposition-synthesize-v1"


def test_apply_uncovered_proposition_counted(tmp_path):
    root = _project(tmp_path)
    ref = _write_prop(root, "p", title="claim")
    report = apply_synthesis(
        [], current={ref: _parse_markdown_file(root / "entities/propositions/p.md")[0]},
        project_root=root, source="llm-synth:m:proposition-synthesize-v1", in_scope={ref},
    )
    assert report.skipped.get("synthesize-proposition-uncovered") == 1


def test_apply_is_atomic_on_interlock_error(tmp_path):
    root = _project(tmp_path)
    good = _write_prop(root, "good", title="good claim")
    bad = _write_prop(root, "bad", title="bad claim")
    cur = {
        good: _parse_markdown_file(root / "entities/propositions/good.md")[0],
        bad: _parse_markdown_file(root / "entities/propositions/bad.md")[0],
    }
    good_cand = _cand({"claim_layer": "causal_effect"}, prop=good,
                      ann="annotation:papers/p.source#s1")
    bad_cand = _cand({"polarity": "positive"}, prop=bad,   # bare polarity → Pass-1 abort
                     ann="annotation:papers/p.source#s2")
    with pytest.raises(SynthesisApplyError):
        apply_synthesis([good_cand, bad_cand], current=cur, project_root=root,
                        source="llm-synth:m:proposition-synthesize-v1", in_scope={good, bad})
    # good was NOT written (validate-before-write): no claim_layer on disk
    fm, _ = _parse_markdown_file(root / "entities/propositions/good.md")
    assert "claim_layer" not in fm


def _scaffold_project(tmp_path: Path):
    root = _project(tmp_path)
    _write_prop(root, "brca1", title="BRCA1 affects instability", subject="BRCA1")
    (root / "papers").mkdir()
    md = root / "papers" / "p.source.md"
    md.write_text("BRCA1 affects instability\n", encoding="utf-8")
    sp = anno_io.sidecar_for_markdown(md)
    stmt = Annotation(
        id="s1",
        target=SpecificResource(source="p.source.md",
                                selector=TextQuoteSelector(exact="BRCA1 affects instability",
                                                           prefix="", suffix="")),
        bodies=(TextualBody(value='{"section":"results","stance":"asserted","subject":"BRCA1"}',
                            format="application/json"),),
        motivation=Motivation.CLASSIFYING, annotation_type="proposition",
        source="llm-annot:m:paper-annotate-v1", status=Status.OPEN,
        creator="paper-annotate", created=datetime(2026, 6, 16, tzinfo=timezone.utc),
        content_hash="0" * 64, promoted_to="proposition:brca1",
    )
    anno_io.write_sidecar(sp, Sidecar(annotations=(stmt,)))
    return root, md


def test_cli_scaffold_lists_in_scope_proposition(tmp_path):
    root, md = _scaffold_project(tmp_path)
    r = CliRunner().invoke(annotate_group,
                           ["synthesize", str(md), "--root", str(root), "--format", "json"])
    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    assert payload["source"] == "llm-synth:<MODEL>:proposition-synthesize-v1"
    [entry] = payload["propositions"]
    assert entry["proposition"] == "proposition:brca1"
    assert entry["statements"][0]["annotation"] == "annotation:papers/p.source#s1"


def test_cli_apply_writes_reasoning_fields(tmp_path):
    root, md = _scaffold_project(tmp_path)
    cand = {
        "source": "llm-synth:m:proposition-synthesize-v1",
        "candidates": [{
            "proposition": "proposition:brca1",
            "annotation": "annotation:papers/p.source#s1",
            "subject": "BRCA1", "object": "genomic instability",
            "predicate": "affects", "polarity": "positive", "claim_layer": "causal_effect",
        }],
    }
    cpath = root / "cand.json"
    cpath.write_text(json.dumps(cand), encoding="utf-8")
    r = CliRunner().invoke(annotate_group, ["synthesize", str(md), "--root", str(root),
                                            "--apply", "--input", str(cpath)])
    assert r.exit_code == 0, r.output
    fm, _ = _parse_markdown_file(root / "entities/propositions/brca1.md")
    assert fm["predicate"] == "affects" and fm["polarity"] == "positive"
    assert fm["object"] == "genomic instability"
    assert fm["reasoning_source"] == "llm-synth:m:proposition-synthesize-v1"
    # second apply is a clean no-op (everything filled)
    r2 = CliRunner().invoke(annotate_group, ["synthesize", str(md), "--root", str(root),
                                             "--apply", "--input", str(cpath), "--format", "json"])
    assert r2.exit_code == 0, r2.output
    assert json.loads(r2.output)["updated"] == 0
