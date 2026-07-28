"""A pre-registration freezes its vehicle by CONTENT, never by path.

The natural-systems t830 incident (fb-2026-07-11-024): pre-registration:0026
locked its vehicle as a path that was in `.gitignore`. The "frozen" vehicle was
an untracked build product whose content was a pure function of the working
tree, so re-running the registered pipeline regenerated it and destroyed the
registered export irrecoverably.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from science_tool.validate.checks.prereg_vehicles import check_prereg_vehicles
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A real git repository laid out like a Science project."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "science.yaml").write_text("name: f\nprofile: research\n", encoding="utf-8")
    (tmp_path / "entities" / "pre-registrations").mkdir(parents=True)
    return tmp_path


def _ctx(root: Path) -> ValidateContext:
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_vehicle(root: Path, relative: str, content: str = "payload\n") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_prereg(
    root: Path,
    name: str = "0001-a.md",
    *,
    status: str = "committed",
    vehicles: str = "",
    body: str = "",
    committed: str = "",
    amendments: int | None = None,
) -> None:
    frontmatter = ["---", "kind: pre-registration", f"status: {status}"]
    if committed:
        frontmatter.append(f"committed: '{committed}'")
    if amendments is not None:
        frontmatter.append("amendments:" if amendments else "amendments: []")
        for n in range(amendments):
            frontmatter.append(f"- date: '2026-07-1{n}'")
            frontmatter.append(f"  reason: correction {n}")
    if vehicles:
        frontmatter.append(vehicles)
    frontmatter.append("---")
    text = "\n".join([*frontmatter, "", "## Hypotheses Under Test", body])
    root.joinpath("entities", "pre-registrations", name).write_text(text, encoding="utf-8")


def _rules(results: list[Result]) -> list[str]:
    return [result.rule_id or "" for result in results]


def _vehicle_block(path: str, digest: str) -> str:
    return f'vehicles:\n  - path: "{path}"\n    sha256: "{digest}"'


def test_gitignored_vehicle_is_an_error(project: Path) -> None:
    """The t830 incident itself: a vehicle under a gitignored build directory."""
    project.joinpath(".gitignore").write_text("pipeline/**/data/\n", encoding="utf-8")
    vehicle = _write_vehicle(project, "pipeline/graph-analysis/data/graph-export.json")
    _write_prereg(
        project,
        vehicles=_vehicle_block("pipeline/graph-analysis/data/graph-export.json", _sha256(vehicle)),
    )

    results = list(check_prereg_vehicles(_ctx(project)))

    assert _rules(results) == ["prereg.vehicle-gitignored"]
    assert results[0].severity.value == "error"
    assert "graph-export.json" in results[0].message
    assert results[0].path is not None and not results[0].path.is_absolute()


def test_gitignored_vehicle_under_data_is_still_an_error(project: Path) -> None:
    """`data/` is gitignored by design, which is exactly why it cannot freeze a vehicle.

    A vehicle living there must be declared as a content-addressed dataset
    entity; the payload directory alone confers no durability.
    """
    project.joinpath(".gitignore").write_text("data/\n", encoding="utf-8")
    vehicle = _write_vehicle(project, "data/graph-export.json")
    _write_prereg(project, vehicles=_vehicle_block("data/graph-export.json", _sha256(vehicle)))

    results = list(check_prereg_vehicles(_ctx(project)))

    assert _rules(results) == ["prereg.vehicle-gitignored"]


def test_committed_vehicle_with_matching_hash_passes(project: Path) -> None:
    vehicle = _write_vehicle(project, "inputs/graph-export.json")
    _git(project, "add", "inputs/graph-export.json")
    _git(project, "commit", "-qm", "add vehicle")
    _write_prereg(project, vehicles=_vehicle_block("inputs/graph-export.json", _sha256(vehicle)))

    assert list(check_prereg_vehicles(_ctx(project))) == []


def test_hash_drift_is_an_error(project: Path) -> None:
    """The registered content is gone even though the path still resolves."""
    vehicle = _write_vehicle(project, "inputs/graph-export.json", "244 models\n")
    _git(project, "add", "inputs/graph-export.json")
    _git(project, "commit", "-qm", "add vehicle")
    registered = _sha256(vehicle)
    vehicle.write_text("248 models\n", encoding="utf-8")
    _write_prereg(project, vehicles=_vehicle_block("inputs/graph-export.json", registered))

    results = list(check_prereg_vehicles(_ctx(project)))

    assert _rules(results) == ["prereg.vehicle-hash-drift"]
    assert registered[:12] in results[0].message


def test_untracked_vehicle_is_an_error(project: Path) -> None:
    """Not ignored, but never committed — still not durable."""
    vehicle = _write_vehicle(project, "inputs/graph-export.json")
    _write_prereg(project, vehicles=_vehicle_block("inputs/graph-export.json", _sha256(vehicle)))

    results = list(check_prereg_vehicles(_ctx(project)))

    assert _rules(results) == ["prereg.vehicle-untracked"]


def test_absent_vehicle_is_an_error(project: Path) -> None:
    _write_prereg(project, vehicles=_vehicle_block("inputs/gone.json", "0" * 64))

    results = list(check_prereg_vehicles(_ctx(project)))

    assert _rules(results) == ["prereg.vehicle-missing"]


def test_vehicle_without_sha256_is_an_error(project: Path) -> None:
    """A path alone is the defect: freezing by path is what failed."""
    _write_vehicle(project, "inputs/graph-export.json")
    _git(project, "add", "inputs/graph-export.json")
    _git(project, "commit", "-qm", "add vehicle")
    _write_prereg(project, vehicles='vehicles:\n  - path: "inputs/graph-export.json"')

    results = list(check_prereg_vehicles(_ctx(project)))

    assert _rules(results) == ["prereg.vehicle-uncontent-addressed"]


def test_committed_prereg_declaring_no_vehicle_warns(project: Path) -> None:
    """Grandfathered: WARN, so the existing corpus does not turn red retroactively."""
    _write_prereg(project)

    results = list(check_prereg_vehicles(_ctx(project)))

    assert _rules(results) == ["prereg.vehicle-undeclared"]
    assert results[0].severity.value == "warn"


def test_data_gated_prereg_declaring_no_vehicle_is_silent(project: Path) -> None:
    """Data-gated mode commits the decision rule before any vehicle is admissible."""
    _write_prereg(project, body="## Vehicle-Admissibility Gate (data-gated mode)\n")

    assert list(check_prereg_vehicles(_ctx(project))) == []


def test_uncommitted_prereg_declaring_no_vehicle_is_silent(project: Path) -> None:
    """The freeze obligation attaches at commit time, not while drafting."""
    _write_prereg(project, status="active")

    assert list(check_prereg_vehicles(_ctx(project))) == []


def test_amendment_record_freezes_a_prereg_whose_status_says_active(project: Path) -> None:
    """fb-2026-07-26-019: `status` alone under-reports, because it defaults to `active`.

    `default_status` for this kind is `active` while the template displays
    `status: "committed"`, so a tool-created pre-registration lands on `active`
    and stays there unless the author edits it at sign-off. An amendment record
    settles the question regardless: amending presupposes having committed.
    """
    _write_prereg(project, status="active", committed="2026-07-11", amendments=2)

    results = list(check_prereg_vehicles(_ctx(project)))

    assert _rules(results) == ["prereg.vehicle-undeclared"]
    assert results[0].severity.value == "warn"
    assert "records 2 amendments" in results[0].message


def test_a_single_amendment_is_reported_in_the_singular(project: Path) -> None:
    _write_prereg(project, status="active", amendments=1)

    results = list(check_prereg_vehicles(_ctx(project)))

    assert "records 1 amendment," in results[0].message


def test_a_committed_date_alone_does_not_freeze(project: Path) -> None:
    """`committed:` discriminates nothing — the template emits it unconditionally.

    Every pre-registration in the surveyed corpus (34 of 34) carried one,
    including genuine drafts, so reading it as a freeze signal would fire on
    the whole population.
    """
    _write_prereg(project, status="active", committed="2026-07-11")

    assert list(check_prereg_vehicles(_ctx(project))) == []


def test_an_empty_amendments_list_does_not_freeze(project: Path) -> None:
    """The scaffolded field is not itself evidence of a commitment."""
    _write_prereg(project, status="active", amendments=0)

    assert list(check_prereg_vehicles(_ctx(project))) == []


def test_an_amended_prereg_that_declares_its_vehicle_is_silent(project: Path) -> None:
    """Widening the freeze predicate must not fire on a document that complied."""
    vehicle = _write_vehicle(project, "inputs/graph-export.json")
    _git(project, "add", "inputs/graph-export.json")
    _git(project, "commit", "-qm", "add vehicle")
    _write_prereg(
        project,
        status="active",
        amendments=3,
        vehicles=_vehicle_block("inputs/graph-export.json", _sha256(vehicle)),
    )

    assert list(check_prereg_vehicles(_ctx(project))) == []


def test_a_data_gated_prereg_stays_silent_however_it_was_frozen(project: Path) -> None:
    """The data-gated escape must survive the widened predicate."""
    _write_prereg(
        project,
        status="active",
        amendments=2,
        body="## Vehicle-Admissibility Gate (data-gated mode)\n",
    )

    assert list(check_prereg_vehicles(_ctx(project))) == []


def test_the_message_names_status_when_status_is_what_froze_it(project: Path) -> None:
    _write_prereg(project, status="amended")

    results = list(check_prereg_vehicles(_ctx(project)))

    assert "status is 'amended'" in results[0].message


def test_vehicles_outside_a_git_repository_are_reported_unverifiable(tmp_path: Path) -> None:
    """Never claim a vehicle is frozen when durability could not be checked at all."""
    tmp_path.joinpath("science.yaml").write_text("name: f\nprofile: research\n", encoding="utf-8")
    tmp_path.joinpath("entities", "pre-registrations").mkdir(parents=True)
    _write_vehicle(tmp_path, "inputs/graph-export.json")
    _write_prereg(tmp_path, vehicles=_vehicle_block("inputs/graph-export.json", "0" * 64))

    results = list(check_prereg_vehicles(_ctx(tmp_path)))

    assert _rules(results) == ["prereg.vehicle-unverifiable"]


def test_durability_failures_gate_the_build_but_undeclared_does_not() -> None:
    """The five durability defects fail closed; the grandfathered WARN does not.

    Gating these is safe only because the corpus produces zero findings on them
    today — see the note in gates.py.
    """
    from science_tool.validate.gates import cumulative_rules

    gated = cumulative_rules("hygiene")
    assert "prereg.vehicle-gitignored" in gated
    assert "prereg.vehicle-untracked" in gated
    assert "prereg.vehicle-hash-drift" in gated
    assert "prereg.vehicle-missing" in gated
    assert "prereg.vehicle-uncontent-addressed" in gated
    assert "prereg.vehicle-undeclared" not in gated
    assert "prereg.vehicle-unverifiable" not in gated
    assert "prereg.prose-path-nondurable" not in gated


def test_non_prereg_entities_are_ignored(project: Path) -> None:
    project.joinpath("entities", "pre-registrations", "README.md").write_text(
        "---\nkind: note\n---\n", encoding="utf-8"
    )

    assert list(check_prereg_vehicles(_ctx(project))) == []


def test_every_declared_vehicle_is_reported(project: Path) -> None:
    """One finding per vehicle — not one per document."""
    project.joinpath(".gitignore").write_text("build/\n", encoding="utf-8")
    first = _write_vehicle(project, "build/a.json")
    second = _write_vehicle(project, "build/b.json")
    _write_prereg(
        project,
        vehicles=(
            f'vehicles:\n  - path: "build/a.json"\n    sha256: "{_sha256(first)}"\n'
            f'  - path: "build/b.json"\n    sha256: "{_sha256(second)}"'
        ),
    )

    results = list(check_prereg_vehicles(_ctx(project)))

    assert _rules(results) == ["prereg.vehicle-gitignored", "prereg.vehicle-gitignored"]
    assert "build/a.json" in results[0].message
    assert "build/b.json" in results[1].message


def test_git_query_maps_zero_to_true(project: Path) -> None:
    from science_tool.validate.checks.prereg_vehicles import _git_query

    project.joinpath(".gitignore").write_text("build/\n", encoding="utf-8")
    _write_vehicle(project, "build/a.json")

    assert _git_query(project, "check-ignore", "-q", "--", "build/a.json") is True


def test_git_query_maps_one_to_false(project: Path) -> None:
    from science_tool.validate.checks.prereg_vehicles import _git_query

    _write_vehicle(project, "inputs/a.json")

    assert _git_query(project, "check-ignore", "-q", "--", "inputs/a.json") is False


def test_git_query_maps_any_other_exit_to_none(project: Path) -> None:
    """A git failure is not a negative answer.

    `_git_ok` returns False for exit 128, which would let an out-of-worktree
    path or a broken repository be reported as non-durable.
    """
    from science_tool.validate.checks.prereg_vehicles import _git_query

    assert _git_query(project, "check-ignore", "-q", "--", "../outside") is None
    assert _git_query(project, "ls-files", "--error-unmatch", "--", "../outside") is None


def test_candidate_paths_accepts_a_bare_backticked_path() -> None:
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    assert _candidate_paths("uses `data/raw/foo.json` as input") == ["data/raw/foo.json"]


def test_candidate_paths_rejects_a_span_that_is_not_only_a_path() -> None:
    """Path-shaped arguments are not mined out of commands."""
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    assert _candidate_paths("run `python x.py --in data/raw/foo`") == []


def test_candidate_paths_rejects_urls() -> None:
    """`:` is outside the grammar."""
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    assert _candidate_paths("see `https://example.com/x`") == []


def test_candidate_paths_rejects_root_level_names_in_every_normalized_form() -> None:
    """Root-level paths are out of scope, and the GRAMMAR does not enforce it.

    Every form here contains a `/` when the grammar matches it and denotes a
    root-level path once normalized. `././input.parquet` and `build/./` are the
    forms a single `./`-strip and `rstrip('/')` would let through, which is why
    normalization must be fully lexical.
    """
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    body = (
        "`input.parquet` and `./input.parquet` and `input.parquet/` "
        "and `././input.parquet` and `build/./`"
    )

    assert _candidate_paths(body) == []


def test_candidate_paths_rejects_absolute_paths_however_they_are_spelled() -> None:
    """`//etc/passwd` is POSIX-absolute too, and `PurePosixPath` knows it."""
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    assert _candidate_paths("`/etc/passwd` and `//etc/passwd` and `../secrets/x`") == []


def test_candidate_paths_collapses_redundant_separators() -> None:
    """`.//etc/passwd` is relative `etc/passwd` in POSIX, not the absolute path.

    A naive two-character `./` strip would emit `/etc/passwd` and break the
    function's own repo-relative contract.
    """
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    assert _candidate_paths("`.//etc/passwd` and `a//b/c`") == ["etc/passwd", "a/b/c"]


def test_candidate_paths_ignores_fenced_blocks() -> None:
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    body = "before\n\n```\n`data/raw/foo.json`\n```\n\nafter\n"

    assert _candidate_paths(body) == []


def test_candidate_paths_respects_fence_delimiters() -> None:
    """A `~~~` line inside a backtick fence is content, not the closer.

    Toggling on any fence marker would end the block at `~~~` and expose
    `b/two.json`, which is still inside fenced Markdown.
    """
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    body = "```\n`a/one.json`\n~~~\n`b/two.json`\n```\n\nafter `c/three.json`\n"

    assert _candidate_paths(body) == ["c/three.json"]


def test_candidate_paths_does_not_close_a_fence_on_a_marker_with_trailing_text() -> None:
    """Per CommonMark a CLOSING fence may be followed only by whitespace."""
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    body = "```\n`a/one.json`\n```not-a-close\n`b/two.json`\n```\n\nafter `c/three.json`\n"

    assert _candidate_paths(body) == ["c/three.json"]


def test_candidate_paths_does_not_close_a_fence_on_an_over_indented_marker() -> None:
    """Four spaces makes it an indented code block, not a fence delimiter.

    Verified against the alternative: with an unbounded `^[ \\t]*` this returns
    `['b/two.json']` -- a path that is still inside fenced Markdown.
    """
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    body = "```\n`a/one.json`\n    ```\n`b/two.json`\n```\n\nafter `c/three.json`\n"

    assert _candidate_paths(body) == ["c/three.json"]


def test_candidate_paths_accepts_a_three_space_indented_fence() -> None:
    """0-3 spaces is still a fence; the cap must not break ordinary indentation."""
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    body = "   ```\n`a/one.json`\n   ```\n\nafter `c/three.json`\n"

    assert _candidate_paths(body) == ["c/three.json"]


def test_candidate_paths_allows_an_opening_info_string() -> None:
    """The trailing-text rule applies to CLOSERS only; ```python still opens."""
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    body = "```python\n`a/one.json`\n```\n\nafter `c/three.json`\n"

    assert _candidate_paths(body) == ["c/three.json"]


def test_candidate_paths_ignores_html_comments() -> None:
    """A commented-out path is body text but is not something the document says."""
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    assert _candidate_paths("<!-- was `data/raw/foo.json` -->") == []


def test_candidate_paths_ignores_a_fence_inside_an_html_comment() -> None:
    """Comments are stripped first, so a commented fence cannot desynchronise
    the fence state and swallow the rest of the document."""
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    body = "<!--\n```\n-->\n\nuses `data/raw/foo.json`\n"

    assert _candidate_paths(body) == ["data/raw/foo.json"]


def test_candidate_paths_normalizes_leading_dot_slash_and_trailing_slash() -> None:
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    assert _candidate_paths("`./data/raw/` and `data/raw`") == ["data/raw"]


def test_candidate_paths_deduplicates_preserving_first_appearance() -> None:
    from science_tool.validate.checks.prereg_vehicles import _candidate_paths

    body = "`b/two.json` then `a/one.json` then `b/two.json`"

    assert _candidate_paths(body) == ["b/two.json", "a/one.json"]


def test_nondurable_state_reports_an_ignored_file(project: Path) -> None:
    from science_tool.validate.checks.prereg_vehicles import _nondurable_state

    project.joinpath(".gitignore").write_text("build/\n", encoding="utf-8")
    _write_vehicle(project, "build/a.json")

    assert _nondurable_state(project, "build/a.json") == "ignored"


def test_nondurable_state_reports_an_untracked_file(project: Path) -> None:
    from science_tool.validate.checks.prereg_vehicles import _nondurable_state

    _write_vehicle(project, "inputs/a.json")

    assert _nondurable_state(project, "inputs/a.json") == "untracked"


def test_nondurable_state_is_silent_for_a_tracked_file(project: Path) -> None:
    from science_tool.validate.checks.prereg_vehicles import _nondurable_state

    _write_vehicle(project, "inputs/a.json")
    _git(project, "add", "inputs/a.json")
    _git(project, "commit", "-qm", "add")

    assert _nondurable_state(project, "inputs/a.json") is None


def test_nondurable_state_treats_a_directory_with_a_tracked_descendant_as_durable(
    project: Path,
) -> None:
    """`ls-files --error-unmatch` is a pathspec query, so one command answers
    both "is this file tracked" and "does this directory hold a tracked file"."""
    from science_tool.validate.checks.prereg_vehicles import _nondurable_state

    _write_vehicle(project, "inputs/a.json")
    _git(project, "add", "inputs/a.json")
    _git(project, "commit", "-qm", "add")

    assert _nondurable_state(project, "inputs") is None


def test_nondurable_state_reports_a_directory_with_no_tracked_descendant(
    project: Path,
) -> None:
    from science_tool.validate.checks.prereg_vehicles import _nondurable_state

    _write_vehicle(project, "inputs/a.json")

    assert _nondurable_state(project, "inputs") == "untracked"


def test_an_ignored_directory_holding_a_force_added_file_is_treated_as_durable(
    project: Path,
) -> None:
    """Pins the adopted composition, which is emergent rather than written.

    `git check-ignore` suppresses paths git considers tracked, so an ignored
    directory holding a force-added file exits 1 (not ignored) under the
    default query -- `--no-index` would exit 0 -- and falls through to the
    tracked query, which matches the force-added file. Adopted deliberately:
    it keeps this rule in agreement with `_is_ignored` in the declared-vehicle
    rules, and under-reporting is the right error for an advisory rule. Verified
    against natural-systems `data/processed/arxiv`.
    """
    from science_tool.validate.checks.prereg_vehicles import _nondurable_state

    project.joinpath(".gitignore").write_text("build/\n", encoding="utf-8")
    _write_vehicle(project, "build/kept.json")
    _git(project, "add", "-f", "build/kept.json")
    _git(project, "commit", "-qm", "force-add")

    assert _nondurable_state(project, "build") is None


def test_nondurable_state_is_silent_when_the_ignore_query_fails(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """First query fails: a git failure must never become a finding."""
    from science_tool.validate.checks import prereg_vehicles

    monkeypatch.setattr(prereg_vehicles, "_git_query", lambda *args, **kwargs: None)

    assert prereg_vehicles._nondurable_state(project, "inputs/a.json") is None


def test_nondurable_state_is_silent_when_the_tracked_query_fails(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SECOND query fails, which a blanket `lambda: None` never reaches.

    Without this arm the `matched is None` branch is untested: the function
    short-circuits at `check-ignore`, so an implementation written as a bare
    `if matched:` would pass the whole suite while silently reporting every
    unverifiable path as untracked.
    """
    from science_tool.validate.checks import prereg_vehicles

    def fake_query(root: Path, *args: str) -> bool | None:
        return False if args[0] == "check-ignore" else None

    monkeypatch.setattr(prereg_vehicles, "_git_query", fake_query)

    assert prereg_vehicles._nondurable_state(project, "inputs/a.json") is None


def test_frozen_prereg_naming_an_ignored_path_in_prose_warns(project: Path) -> None:
    """The `fb-2026-07-11-024` shape, in a bullet instead of frontmatter."""
    project.joinpath(".gitignore").write_text("pipeline/**/data/\n", encoding="utf-8")
    _write_vehicle(project, "pipeline/graph-analysis/data/graph-export.json")
    vehicle = _write_vehicle(project, "inputs/ok.json")
    _git(project, "add", "inputs/ok.json")
    _git(project, "commit", "-qm", "add vehicle")
    _write_prereg(
        project,
        vehicles=_vehicle_block("inputs/ok.json", _sha256(vehicle)),
        body="- **Source:** `pipeline/graph-analysis/data/graph-export.json`\n",
    )

    results = list(check_prereg_vehicles(_ctx(project)))

    assert _rules(results) == ["prereg.prose-path-nondurable"]
    assert results[0].severity.value == "warn"
    assert "pipeline/graph-analysis/data/graph-export.json" in results[0].message


def test_frozen_prereg_naming_an_untracked_path_in_prose_warns(project: Path) -> None:
    """Not ignored, but never committed -- still not preserved."""
    _write_vehicle(project, "data/processed/frame.parquet")
    _write_prereg(project, body="built from `data/processed/frame.parquet`\n")

    results = list(check_prereg_vehicles(_ctx(project)))

    assert _rules(results) == ["prereg.vehicle-undeclared", "prereg.prose-path-nondurable"]
    assert "not tracked by git" in results[1].message


def test_the_prose_message_does_not_assert_the_path_is_a_substrate(project: Path) -> None:
    """The rule proves a durability fact, not that the path is load-bearing.

    Selecting by rule matters: `vehicle-undeclared` is yielded first for this
    document, so `results[0]` is not the finding under test.
    """
    project.joinpath(".gitignore").write_text("build/\n", encoding="utf-8")
    _write_vehicle(project, "build/out.json")
    _write_prereg(project, body="results land in `build/out.json`\n")

    results = list(check_prereg_vehicles(_ctx(project)))
    prose = [r for r in results if r.rule_id == "prereg.prose-path-nondurable"]

    assert len(prose) == 1
    message = prose[0].message
    # The remedy legitimately names the `vehicles:` FIELD, so a blanket ban on
    # the word would be wrong. What is forbidden is calling the PATH one, and
    # asserting a consequence git does not establish.
    assert "substrate" not in message
    assert f"vehicle {'build/out.json'!r}" not in message
    # Git proves non-preservation. It does NOT prove that regenerating the file
    # changes any bytes, or that no copy exists elsewhere, so the consequence
    # must stay hedged and conditional.
    assert "irrecoverably" not in message
    assert "would leave" not in message
    assert "could leave" in message
    assert "git will not preserve it" in message
    assert "if this document's claims depend on" in message.lower()


def test_a_tracked_prose_path_is_silent(project: Path) -> None:
    _write_vehicle(project, "workflows/breadth/config.yaml")
    _git(project, "add", "workflows/breadth/config.yaml")
    _git(project, "commit", "-qm", "add config")
    _write_prereg(project, body="settings from `workflows/breadth/config.yaml`\n")

    assert _rules(list(check_prereg_vehicles(_ctx(project)))) == ["prereg.vehicle-undeclared"]


def test_a_prose_path_that_does_not_resolve_is_silent(project: Path) -> None:
    """"Destroyed", "illustrative" and "renamed" are indistinguishable."""
    _write_prereg(project, body="once lived at `pipeline/gone/export.json`\n")

    assert _rules(list(check_prereg_vehicles(_ctx(project)))) == ["prereg.vehicle-undeclared"]


def test_a_declared_vehicle_is_not_also_reported_as_a_prose_path(project: Path) -> None:
    """One file, one rule. Exact normalized match, including `./` forms."""
    project.joinpath(".gitignore").write_text("build/\n", encoding="utf-8")
    vehicle = _write_vehicle(project, "build/a.json")
    _write_prereg(
        project,
        vehicles=_vehicle_block("build/a.json", _sha256(vehicle)),
        body="the vehicle is `./build/a.json`\n",
    )

    assert _rules(list(check_prereg_vehicles(_ctx(project)))) == ["prereg.vehicle-gitignored"]


def test_an_ignored_directory_holding_a_defective_declared_vehicle_is_reported(
    project: Path,
) -> None:
    """No parent-directory suppression: the containing root is real information.

    The directory must be NESTED. A bare `build` has no `/` and is out of scope
    by the root-level rule, so it would never be a candidate at all.
    """
    project.joinpath(".gitignore").write_text("artifacts/build/\n", encoding="utf-8")
    vehicle = _write_vehicle(project, "artifacts/build/a.json")
    _write_prereg(
        project,
        vehicles=_vehicle_block("artifacts/build/a.json", _sha256(vehicle)),
        body="under `artifacts/build`\n",
    )

    assert _rules(list(check_prereg_vehicles(_ctx(project)))) == [
        "prereg.vehicle-gitignored",
        "prereg.prose-path-nondurable",
    ]


def test_a_prose_path_named_five_times_is_one_finding(project: Path) -> None:
    project.joinpath(".gitignore").write_text("build/\n", encoding="utf-8")
    _write_vehicle(project, "build/a.json")
    body = "".join(f"line {n} mentions `build/a.json`\n" for n in range(5))
    _write_prereg(project, body=body)

    results = list(check_prereg_vehicles(_ctx(project)))

    assert _rules(results) == ["prereg.vehicle-undeclared", "prereg.prose-path-nondurable"]


def test_an_unfrozen_prereg_naming_an_ignored_path_is_silent(project: Path) -> None:
    """A prose path is an inferred commitment; before freezing it is normal work."""
    project.joinpath(".gitignore").write_text("build/\n", encoding="utf-8")
    _write_vehicle(project, "build/a.json")
    _write_prereg(project, status="active", body="working from `build/a.json`\n")

    assert list(check_prereg_vehicles(_ctx(project))) == []


def test_a_data_gated_prereg_naming_an_ignored_path_is_silent(project: Path) -> None:
    """Data-gated mode legitimately discusses candidate paths."""
    project.joinpath(".gitignore").write_text("build/\n", encoding="utf-8")
    _write_vehicle(project, "build/a.json")
    _write_prereg(
        project,
        body="## Vehicle-Admissibility Gate (data-gated mode)\n\ncandidate `build/a.json`\n",
    )

    assert list(check_prereg_vehicles(_ctx(project))) == []


def test_prose_paths_outside_a_git_repository_are_silent(tmp_path: Path) -> None:
    """Never claim non-durability when git has not answered."""
    tmp_path.joinpath("science.yaml").write_text("name: f\nprofile: research\n", encoding="utf-8")
    tmp_path.joinpath("entities", "pre-registrations").mkdir(parents=True)
    _write_vehicle(tmp_path, "build/a.json")
    _write_prereg(tmp_path, body="from `build/a.json`\n")

    assert _rules(list(check_prereg_vehicles(_ctx(tmp_path)))) == ["prereg.vehicle-undeclared"]


def test_the_rule_is_silent_when_git_cannot_answer(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The caller's half of the tri-state contract."""
    from science_tool.validate.checks import prereg_vehicles

    project.joinpath(".gitignore").write_text("build/\n", encoding="utf-8")
    _write_vehicle(project, "build/a.json")
    _write_prereg(project, body="from `build/a.json`\n")
    monkeypatch.setattr(prereg_vehicles, "_git_query", lambda *args, **kwargs: None)

    assert _rules(list(check_prereg_vehicles(_ctx(project)))) == ["prereg.vehicle-undeclared"]
