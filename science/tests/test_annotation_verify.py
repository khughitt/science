"""Tests for the verify orchestration core."""

from __future__ import annotations

from pathlib import Path

from science_tool.annotation.verify import (
    VerifyIssue,
    iter_sidecars,
    verify_path,
)

FIX = Path(__file__).parent / "_fixtures" / "annotation" / "verify"


def test_iter_sidecars_finds_all_anno_trig_files(tmp_path: Path) -> None:
    (tmp_path / "a.anno.trig").write_text("")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.anno.trig").write_text("")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "ignored.anno.trig").write_text("")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "ignored.anno.trig").write_text("")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.anno.trig").write_text("")
    (tmp_path / "unrelated.md").write_text("")

    found = list(iter_sidecars(tmp_path))
    rels = sorted(p.relative_to(tmp_path).as_posix() for p in found)
    assert rels == ["a.anno.trig", "sub/b.anno.trig"]


def test_iter_sidecars_returns_paths_in_sorted_order(tmp_path: Path) -> None:
    (tmp_path / "z.anno.trig").write_text("")
    (tmp_path / "a.anno.trig").write_text("")
    (tmp_path / "m.anno.trig").write_text("")
    found = list(iter_sidecars(tmp_path))
    assert [p.name for p in found] == ["a.anno.trig", "m.anno.trig", "z.anno.trig"]


def test_verify_path_classifies_resolved_degraded_fuzzy_broken_supersession() -> None:
    """The `source.anno.trig` fixture has one annotation per outcome.

    See the fixture for the exact prose and selectors. Outcomes:
      - a-ok            → RESOLVED, no issue
      - a-degraded      → DEGRADED (bare exact unique, anchors don't match)
      - a-fuzzy         → FUZZY (1-char same-length substitution within margin;
                          the resolver only matches same-length windows, so the
                          source typo MUST be a substitution, not an insert/delete)
      - a-broken        → SUPERSEDED (exact text removed from source)
    """
    report = verify_path(FIX)
    sidecar_rel = "source.anno.trig"
    issues_for_source = [i for i in report.issues if i.sidecar.name == sidecar_rel]
    by_kind: dict[str, list[VerifyIssue]] = {}
    for i in issues_for_source:
        by_kind.setdefault(i.kind, []).append(i)
    assert sorted(by_kind.keys()) == ["broken", "degraded", "fuzzy"]
    broken_ids = sorted(i.annotation_id for i in by_kind["broken"])
    degraded_ids = sorted(i.annotation_id for i in by_kind["degraded"])
    fuzzy_ids = sorted(i.annotation_id for i in by_kind["fuzzy"])
    assert broken_ids == ["a-broken"]
    assert degraded_ids == ["a-degraded"]
    assert fuzzy_ids == ["a-fuzzy"]


def test_verify_path_reports_source_missing_when_target_file_absent() -> None:
    report = verify_path(FIX)
    no_source = [i for i in report.issues if i.sidecar.name == "no-source.anno.trig"]
    assert len(no_source) == 1
    assert no_source[0].kind == "source-missing"
    assert no_source[0].annotation_id == "a-orphan"


def test_verify_path_walks_nested_directories() -> None:
    report = verify_path(FIX)
    nested = [i for i in report.issues if i.sidecar.parent.name == "nested"]
    # The nested fixture has one broken annotation.
    assert len(nested) == 1
    assert nested[0].kind == "broken"


def test_verify_path_skips_already_superseded_annotations(tmp_path: Path) -> None:
    """An annotation that is already 'superseded' should not be re-classified."""
    # Copy the broken sidecar but flip its status to 'superseded' first; we
    # expect it to be counted in superseded_skipped, not in issues.
    src_text = (FIX / "source.md").read_text()
    (tmp_path / "source.md").write_text(src_text)
    sidecar = tmp_path / "source.anno.trig"
    sidecar.write_text(_sidecar_with_one_already_superseded())
    report = verify_path(tmp_path)
    assert report.superseded_skipped == 1
    assert all(i.kind != "broken" for i in report.issues)


def test_verify_path_summary_counts_match_issues() -> None:
    report = verify_path(FIX)
    assert report.broken == sum(1 for i in report.issues if i.kind == "broken")
    assert report.degraded == sum(1 for i in report.issues if i.kind == "degraded")
    assert report.fuzzy == sum(1 for i in report.issues if i.kind == "fuzzy")
    assert report.source_missing == sum(
        1 for i in report.issues if i.kind == "source-missing"
    )
    assert report.parse_errors == sum(
        1 for i in report.issues if i.kind == "parse-error"
    )
    assert report.sidecars >= 3  # source, no-source, nested/deep


def test_verify_path_records_parse_error_without_aborting(tmp_path: Path) -> None:
    (tmp_path / "broken.anno.trig").write_text("this is not trig at all {{{")
    (tmp_path / "good.anno.trig").write_text(_minimal_empty_sidecar())
    report = verify_path(tmp_path)
    parse_errors = [i for i in report.issues if i.kind == "parse-error"]
    assert len(parse_errors) == 1
    assert parse_errors[0].sidecar.name == "broken.anno.trig"
    # 'good.anno.trig' was still walked.
    assert report.sidecars == 2


def test_verify_path_marks_uri_sources_distinctly(tmp_path: Path) -> None:
    """Absolute URIs are out of scope for v1 but must be visible to the user.

    Regression: an earlier implementation classified URI sources as bare
    'source-missing' indistinguishable from a missing local file.
    """
    sidecar = tmp_path / "uri.anno.trig"
    sidecar.write_text(_sidecar_with_uri_source())
    report = verify_path(tmp_path)
    uri_issues = [i for i in report.issues if i.annotation_id == "a-uri"]
    assert len(uri_issues) == 1
    assert uri_issues[0].kind == "source-missing"
    assert "[uri-out-of-scope]" in uri_issues[0].exact_preview


def _sidecar_with_uri_source() -> str:
    return (
        "@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n"
        "@prefix oa:   <http://www.w3.org/ns/oa#> .\n"
        "@prefix dc:   <http://purl.org/dc/terms/> .\n"
        "@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .\n"
        "@prefix sci:  <http://example.org/science/vocab/> .\n"
        "@prefix anno: <#> .\n"
        "anno:annotations {\n"
        "  anno:a-uri a oa:Annotation ;\n"
        "    oa:hasTarget [\n"
        "      oa:hasSource <https://example.com/external.html> ;\n"
        "      oa:hasSelector [\n"
        "        a oa:TextQuoteSelector ;\n"
        '        oa:exact "anything" ; oa:prefix "" ; oa:suffix "" ]\n'
        "    ] ;\n"
        '    oa:hasBody [ a oa:TextualBody ; dc:format "text/plain" ; rdf:value "x" ] ;\n'
        "    oa:motivatedBy oa:commenting ;\n"
        '    sci:annotationType "comment" ; sci:source "human:test" ;\n'
        '    sci:status "open" ; dc:creator "test" ;\n'
        '    dc:created "2026-05-11T00:00:00+00:00"^^xsd:dateTime .\n'
        "}\n"
    )


def _minimal_empty_sidecar() -> str:
    return (
        "@prefix oa: <http://www.w3.org/ns/oa#> .\n"
        "@prefix anno: <#> .\n"
        "anno:annotations { }\n"
    )


from datetime import datetime, timezone
import shutil

from science_tool.annotation.io import read_sidecar
from science_tool.annotation.model import Status
from science_tool.annotation.verify import apply_supersessions


def test_apply_supersessions_marks_broken_annotations(tmp_path: Path) -> None:
    work = tmp_path / "project"
    shutil.copytree(FIX, work)
    report = verify_path(work)
    assert report.broken >= 1

    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    rewritten = apply_supersessions(report, actor="ci@science", now=now)

    rewritten_names = sorted(p.name for p in rewritten)
    assert "source.anno.trig" in rewritten_names
    assert "deep.anno.trig" in rewritten_names

    sidecar = read_sidecar(work / "source.anno.trig")
    by_id = {a.id: a for a in sidecar.annotations}
    broken = by_id["a-broken"]
    assert broken.status is Status.SUPERSEDED
    assert broken.modified == now
    assert broken.modified_by == "ci@science"
    assert broken.creator == "test"
    assert len(broken.prior_states) == 1
    assert broken.prior_states[0].status is Status.OPEN

    ok = by_id["a-ok"]
    assert ok.status is Status.OPEN
    assert ok.modified is None


def test_apply_supersessions_is_idempotent(tmp_path: Path) -> None:
    work = tmp_path / "project"
    shutil.copytree(FIX, work)
    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    apply_supersessions(verify_path(work), actor="ci@science", now=now)
    second_report = verify_path(work)
    assert second_report.broken == 0
    second_rewrites = apply_supersessions(
        second_report, actor="ci@science", now=now
    )
    assert second_rewrites == set()


def test_apply_supersessions_does_not_touch_degraded_or_fuzzy(tmp_path: Path) -> None:
    work = tmp_path / "project"
    shutil.copytree(FIX, work)
    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    apply_supersessions(verify_path(work), actor="ci@science", now=now)
    sidecar = read_sidecar(work / "source.anno.trig")
    by_id = {a.id: a for a in sidecar.annotations}
    assert by_id["a-degraded"].status is Status.OPEN
    assert by_id["a-fuzzy"].status is Status.OPEN


def test_apply_supersessions_writes_each_sidecar_at_most_once(tmp_path: Path) -> None:
    """Two broken annotations in one sidecar produce one write, not two."""
    work = tmp_path / "project"
    work.mkdir()
    (work / "src.md").write_text("kept paragraph.\n")
    (work / "src.anno.trig").write_text(_two_broken_in_one_sidecar())
    report = verify_path(work)
    assert report.broken == 2
    rewritten = apply_supersessions(
        report,
        actor="ci@science",
        now=datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
    )
    assert len(rewritten) == 1


def _two_broken_in_one_sidecar() -> str:
    return (
        "@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n"
        "@prefix oa:   <http://www.w3.org/ns/oa#> .\n"
        "@prefix dc:   <http://purl.org/dc/terms/> .\n"
        "@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .\n"
        "@prefix sci:  <http://example.org/science/vocab/> .\n"
        "@prefix anno: <#> .\n"
        "anno:annotations {\n"
        "  anno:a-1 a oa:Annotation ;\n"
        "    oa:hasTarget [ oa:hasSource <src.md> ;\n"
        "      oa:hasSelector [ a oa:TextQuoteSelector ;\n"
        '        oa:exact "deleted one" ; oa:prefix "" ; oa:suffix "" ] ] ;\n'
        '    oa:hasBody [ a oa:TextualBody ; dc:format "text/plain" ; rdf:value "x" ] ;\n'
        "    oa:motivatedBy oa:commenting ;\n"
        '    sci:annotationType "comment" ; sci:source "human:test" ;\n'
        '    sci:status "open" ; dc:creator "test" ;\n'
        '    dc:created "2026-05-11T00:00:00+00:00"^^xsd:dateTime .\n'
        "  anno:a-2 a oa:Annotation ;\n"
        "    oa:hasTarget [ oa:hasSource <src.md> ;\n"
        "      oa:hasSelector [ a oa:TextQuoteSelector ;\n"
        '        oa:exact "deleted two" ; oa:prefix "" ; oa:suffix "" ] ] ;\n'
        '    oa:hasBody [ a oa:TextualBody ; dc:format "text/plain" ; rdf:value "y" ] ;\n'
        "    oa:motivatedBy oa:commenting ;\n"
        '    sci:annotationType "comment" ; sci:source "human:test" ;\n'
        '    sci:status "open" ; dc:creator "test" ;\n'
        '    dc:created "2026-05-11T00:00:00+00:00"^^xsd:dateTime .\n'
        "}\n"
    )


def _sidecar_with_one_already_superseded() -> str:
    """A sidecar whose one annotation has status='superseded'.

    Selector exact text is intentionally absent from source.md, so if
    verify_path mistakenly re-classifies it, we'd see kind='broken'.
    """
    return (
        "@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n"
        "@prefix oa:   <http://www.w3.org/ns/oa#> .\n"
        "@prefix dc:   <http://purl.org/dc/terms/> .\n"
        "@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .\n"
        "@prefix sci:  <http://example.org/science/vocab/> .\n"
        "@prefix anno: <#> .\n"
        "anno:annotations {\n"
        "  anno:a-stale a oa:Annotation ;\n"
        "    oa:hasTarget [\n"
        "      oa:hasSource <source.md> ;\n"
        "      oa:hasSelector [\n"
        "        a oa:TextQuoteSelector ;\n"
        '        oa:exact   "text that has been deleted entirely" ;\n'
        '        oa:prefix  "" ;\n'
        '        oa:suffix  ""\n'
        "      ]\n"
        "    ] ;\n"
        '    oa:hasBody         [ a oa:TextualBody ; dc:format "text/plain" ; rdf:value "x" ] ;\n'
        "    oa:motivatedBy     oa:commenting ;\n"
        '    sci:annotationType "comment" ;\n'
        '    sci:source         "human:test" ;\n'
        '    sci:status         "superseded" ;\n'
        '    dc:creator         "test" ;\n'
        '    dc:created         "2026-05-11T00:00:00+00:00"^^xsd:dateTime ;\n'
        '    dc:modified        "2026-05-11T00:00:00+00:00"^^xsd:dateTime ;\n'
        '    dc:contributor     "test" .\n'
        "}\n"
    )
