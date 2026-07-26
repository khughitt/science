from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main
from science_tool.resolve_refs import build_ref_index

_ROWS = [
    {"id": "question:0037-m6a-proliferation-axis", "title": "m6A proliferation axis"},
    {"id": "question:0100-glutamine-dependency", "title": "Glutamine dependency in MM"},
    {"id": "hypothesis:0005-prc2-silencing", "title": "PRC2 silencing drives relapse"},
    {"id": "question:0101-m6a-splicing", "title": "m6A and splicing regulators"},
]


def test_id_exact_match() -> None:
    idx = build_ref_index(_ROWS)
    res = idx.resolve("question:0037-m6a-proliferation-axis")
    assert res.resolved == "question:0037-m6a-proliferation-axis"
    assert res.match_kind == "id-exact"


def test_id_slug_match_when_keyword_only_in_id() -> None:
    # "glutamine" lives in both id-slug and title here, but the point is the
    # id-slug tier fires even for a bare keyword.
    idx = build_ref_index(_ROWS)
    res = idx.resolve("glutamine-dependency")
    assert res.resolved == "question:0100-glutamine-dependency"
    assert res.match_kind == "id-slug"


def test_title_slug_match() -> None:
    idx = build_ref_index(_ROWS)
    res = idx.resolve("PRC2 silencing drives relapse")
    assert res.resolved == "hypothesis:0005-prc2-silencing"
    assert res.match_kind == "title-slug"


def test_ambiguous_returns_candidates_and_null() -> None:
    idx = build_ref_index(_ROWS)
    res = idx.resolve("m6a")  # matches 0037 and 0101 id-slugs
    assert res.resolved is None
    assert res.match_kind == "ambiguous"
    assert res.candidates == (
        "question:0037-m6a-proliferation-axis",
        "question:0101-m6a-splicing",
    )


def test_unresolved_returns_null() -> None:
    idx = build_ref_index(_ROWS)
    res = idx.resolve("no-such-topic-xyz")
    assert res.resolved is None
    assert res.match_kind == "unresolved"
    assert res.candidates == ()


def test_empty_query_is_unresolved() -> None:
    idx = build_ref_index(_ROWS)
    res = idx.resolve("   ")
    assert res.resolved is None
    assert res.match_kind == "unresolved"


def test_to_dict_shape() -> None:
    idx = build_ref_index(_ROWS)
    assert idx.resolve("no-such-topic-xyz").to_dict() == {
        "query": "no-such-topic-xyz",
        "resolved": None,
        "match_kind": "unresolved",
        "candidates": [],
    }


def _seed(tmp_path: Path) -> None:
    from _fixtures.entity_helpers import seed_project, write_markdown_entity

    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/questions/0037-m6a-proliferation-axis.md",
        {
            "id": "question:0037-m6a-proliferation-axis",
            "kind": "question",
            "title": "Proliferation axis",  # note: 'm6a' only in the id-slug
            "status": "open",
            "created": "2026-07-01",
            "updated": "2026-07-01",
        },
        "Body.\n",
    )


def test_cli_json_resolves_id_slug(tmp_path: Path) -> None:
    from science_tool.cli import main

    _seed(tmp_path)
    res = CliRunner().invoke(
        main,
        [
            "project",
            "resolve-refs",
            "--project-root",
            str(tmp_path),
            "--query",
            "m6a",
            "--format",
            "json",
        ],
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload == [
        {
            "query": "m6a",
            "resolved": "question:0037-m6a-proliferation-axis",
            "match_kind": "id-slug",
            "candidates": ["question:0037-m6a-proliferation-axis"],
        }
    ]


def test_cli_text_reports_unresolved(tmp_path: Path) -> None:
    from science_tool.cli import main

    _seed(tmp_path)
    res = CliRunner().invoke(
        main,
        ["project", "resolve-refs", "--project-root", str(tmp_path), "--query", "nope-xyz"],
    )
    assert res.exit_code == 0, res.output
    assert "nope-xyz" in res.output
    assert "unresolved" in res.output


def test_project_commands_fail_outside_a_project_root(tmp_path: Path) -> None:
    """A subdirectory is not an empty project (fb-2026-07-25-008).

    Run from `entities/questions/`, these commands resolved `--project-root` to
    `.`, found no entities, and answered `unresolved` / `n_topics: 0`. Those are
    well-formed negatives to a question that was never asked, and the empty
    answer gets copied into a report as fact. They must fail instead.
    """
    project = tmp_path / "proj"
    (project / "entities" / "questions").mkdir(parents=True)
    (project / "science.yaml").write_text("name: guard-test\n", encoding="utf-8")
    subdir = project / "entities" / "questions"

    runner = CliRunner()
    invocations = [
        ["project", "resolve-refs", "--project-root", str(subdir), "--query", "question:0037-x"],
        ["project", "topic-coverage", "--project-root", str(subdir)],
        ["project", "index", "--project-root", str(subdir)],
    ]
    for argv in invocations:
        res = runner.invoke(main, argv)
        assert res.exit_code != 0, f"{argv[1]} reported success outside a project: {res.output}"
        assert "is not a Science project" in res.output

    # The same commands succeed against the root itself, so the guard is
    # rejecting the location and not the invocation.
    for argv in invocations:
        rooted = [*argv[:3], str(project), *argv[4:]]
        assert runner.invoke(main, rooted).exit_code == 0, rooted
