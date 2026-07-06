# `explore-ideas` Seed Representativeness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the first slice of `docs/plans/2026-07-05-explore-ideas-seed-representativeness-design.md` — a deterministic `science project topic-coverage` inspector plus the `explore-ideas` Phase-1/Phase-4 markdown edits that consume it — so a stub-dominated topic seed becomes a *visible, non-fatal* caveat and the blind brief is broadened only with blindness-safe scope signals. Addresses `fb-2026-07-05-002`.

**Architecture:** A pure, read-only function `compute_topic_coverage(project_root)` classifies every `entities/topics/*.md` as substantive-or-stub (handling both stub shapes: comment-only template stubs and promoted placeholder-prose stubs), and returns per-topic rows plus aggregate counts. A thin `science project topic-coverage` CLI wraps it (text + JSON). The `explore-ideas` command markdown is edited so Phase 1 broadens the blind brief (fuller `science.yaml`, all topic *titles*) and Phase 4 emits the coverage diagnostic in the report header. No schema change, no graph change, no new `validate` check.

**Tech Stack:** Python 3.11, `click` (CLI), `pytest`, `uv`. Monorepo `~/d/science`; work in a worktree `~/d/science/.worktrees/explore-ideas-seed-representativeness` (branch `explore-ideas-seed-representativeness`).

## Global Constraints

- Run all `science` commands with `uv run --frozen`.
- Tool tests run from `science/` (`cd science && uv run --frozen pytest tests/...`; `testpaths = ["tests"]`).
- The measurement is **deterministic and in code** — never agent discretion (mirrors the Phase-3 slug-pre-pass reasoning in `fb-2026-07-05-003`).
- **Blindness invariant (unchanged):** nothing this slice adds may cause Phase 1 to read `entities/hypotheses/`, `entities/questions/`, or `entities/papers/` into the brief. The coverage diagnostic is orchestrator-only and is surfaced *in the report*, never in a Phase-2 dispatch prompt.
- Reuse existing helpers where their semantics fit:
  - `science_tool.markdown_utils.rendered_prose(markdown)` (strips HTML comments + fenced code) — used for body normalization.
  - **Not** `parse_frontmatter`: it swallows `yaml.YAMLError` and returns `({}, 1)`, which is indistinguishable from "no frontmatter." Fail-early requires distinguishing them, so this slice uses a **local strict frontmatter reader** (Task 1) that raises on a present-but-unparseable / non-mapping / unterminated block and only returns `({}, …)` when a block is genuinely absent or validly empty.
- **Generated-mirror rule:** `commands/explore-ideas.md` has a committed Codex mirror at `codex-skills/science-explore-ideas/SKILL.md`. After any `commands/` edit, regenerate with `python scripts/generate_codex_skills.py` (never hand-edit the mirror); `science/tests/test_codex_skills.py` asserts on the committed mirror's content.
- Commit-message rule (user global): **no AI-attribution trailer or footer**.
- Paths in docs use `~/d/` (not `/home/keith/d/` or `/mnt/ssd/Dropbox/`).
- Do not commit unless the human asks.

---

## File Structure

**Create:**
- `science/src/science_tool/topic_coverage.py` — pure classifier + result types.
- `science/tests/test_topic_coverage.py` — classifier + CLI tests, with fixtures.
- `science/tests/fixtures/topic_coverage/` — a fixture `entities/topics/` tree (see Task 1).

**Modify:**
- `science/src/science_tool/cli.py` — add `@project.command("topic-coverage")` under the existing `project` group (`cli.py:4438`).
- `commands/explore-ideas.md` — Phase 1 (broaden brief sources; use all topic titles) and Phase 4 (emit coverage header block).
- `codex-skills/science-explore-ideas/SKILL.md` — **generated mirror**; regenerate via `python scripts/generate_codex_skills.py` after the `commands/` edit (never hand-edit).
- `docs/plans/2026-07-05-explore-ideas-seed-representativeness-design.md` — check the boxes as tasks land (optional).

**Out of scope for this slice (design §Non-goals):** cluster-coverage comparison against the question/hypothesis index; next-run lens/area biasing; auto-generating topic content; reading project pipeline/config into the brief; centralizing the sentinel constant with the promotion emitter.

---

## Task 1: `compute_topic_coverage` core (pure classifier)

**Files:**
- Create: `science/src/science_tool/topic_coverage.py`
- Create fixtures: `science/tests/fixtures/topic_coverage/entities/topics/*.md`
- Test: `science/tests/test_topic_coverage.py`

**Interfaces (produces):**
- `TopicRow` (frozen dataclass): `id: str`, `title: str`, `path: str` (project-root-relative, POSIX), `substantive: bool`.
- `TopicCoverage` (frozen dataclass): `n_topics: int`, `n_substantive: int`, `stub_ratio: float | None`, `stub_dominated: bool`, `note: str | None`, `topics: tuple[TopicRow, ...]`; plus `to_dict() -> dict` emitting exactly the design's JSON shape.
- `compute_topic_coverage(project_root: Path) -> TopicCoverage`.

**Detection contract (design §"Substantive vs. stub"):**
- Only `entities/topics/*.md`, non-recursive; skip files whose name starts with `_`; skip files whose frontmatter `kind` is present and not `topic`.
- `id`/`title` from frontmatter. **Fail-early split:** a *genuinely absent* or validly-empty frontmatter block falls back to the file stem (`topic:<stem>` / `<stem>`) and is counted; a *present-but-unparseable* block (YAML error, unterminated, or non-mapping) raises `MalformedTopicError` naming the file. Never fabricate a `topic:<stem>` row over corrupt frontmatter — that would hide the broken source while polluting the diagnostic.
- Normalize the body: `rendered_prose(body)` (drops HTML comments + fenced code), then per line strip ATX headings (`^#+ `), list markers (`^([-*+]|\d+\.)\s+`), and blanks → **residual content lines**.
- A residual line is a **placeholder** if it *contains* (`re.search`) a sentinel from `STUB_SENTINELS` — case-insensitive `(has|have) not yet been (curated|added|separately curated)`. (`search`, not full-match, so the promoted combined line `"This topic exists as a promoted project term. A focused narrative summary has not yet been curated."` is caught.)
- **Stub** iff no residual content lines *or* every residual line is a placeholder; **substantive** otherwise (any real prose → substantive).
- `stub_ratio = 1 - n_substantive/n_topics`; when `n_topics == 0`: `stub_ratio = None`, `stub_dominated = False`, `note = "no topics"`, `topics = ()`.
- `stub_dominated = stub_ratio is not None and stub_ratio > 0.5`.
- `topics` sorted deterministically by `id`.

- [ ] **Step 1: Build the fixture topic tree**

Create `science/tests/fixtures/topic_coverage/entities/topics/` with five files:

- `template-stub.md` — packaged-template shape: frontmatter + headings + `<!-- … -->` comment prompts only, no prose. (Copy the body shape of `science/model/src/science_model/templates/background-topic.md`.)
- `promoted-stub.md` — the MM30 shape: headings + one HTML comment + the five placeholder sentences (`A focused narrative summary has not yet been curated.`, `Curated key concepts have not yet been added.`, `The current state of knowledge for this topic has not yet been separately curated.`, `Project-specific relevance has not yet been separately curated.`, `Curated key references have not yet been added.`).
- `substantive.md` — real multi-sentence prose under `## Summary` and `## Key Concepts`.
- `partial.md` — real prose under `## Summary` **plus** a leftover `Curated key references have not yet been added.` line under `## Key References`. Must classify **substantive**.
- `_index.md` — a non-topic file (name starts with `_`) that must be **skipped**.

- [ ] **Step 2: Write the failing tests**

```python
# science/tests/test_topic_coverage.py
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.topic_coverage import MalformedTopicError, compute_topic_coverage

FIX = Path(__file__).parent / "fixtures" / "topic_coverage"


def _by_id(cov):
    return {r.id: r for r in cov.topics}


def test_counts_and_ratio() -> None:
    cov = compute_topic_coverage(FIX)
    # template-stub, promoted-stub, substantive, partial  (_index.md skipped)
    assert cov.n_topics == 4
    assert cov.n_substantive == 2  # substantive + partial
    assert cov.stub_ratio == 0.5
    assert cov.stub_dominated is False  # strictly > 0.5


def test_both_stub_shapes_detected() -> None:
    rows = _by_id(compute_topic_coverage(FIX))
    assert rows["topic:template-stub"].substantive is False
    assert rows["topic:promoted-stub"].substantive is False


def test_partial_curation_counts_substantive() -> None:
    rows = _by_id(compute_topic_coverage(FIX))
    assert rows["topic:partial"].substantive is True


def test_rows_sorted_by_id_and_have_paths() -> None:
    cov = compute_topic_coverage(FIX)
    ids = [r.id for r in cov.topics]
    assert ids == sorted(ids)
    for r in cov.topics:
        assert r.path.startswith("entities/topics/")


def test_zero_topics_branch(tmp_path: Path) -> None:
    (tmp_path / "entities" / "topics").mkdir(parents=True)
    cov = compute_topic_coverage(tmp_path)
    assert cov.n_topics == 0
    assert cov.stub_ratio is None
    assert cov.stub_dominated is False
    assert cov.note == "no topics"
    assert cov.to_dict()["stub_ratio"] is None


def test_malformed_frontmatter_raises(tmp_path: Path) -> None:
    # Own tmp dir — a malformed file in the shared FIX tree would break every test.
    topics = tmp_path / "entities" / "topics"
    topics.mkdir(parents=True)
    (topics / "broken.md").write_text("---\ntitle: [unterminated\n---\n\n# X\n", encoding="utf-8")
    with pytest.raises(MalformedTopicError):
        compute_topic_coverage(tmp_path)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_topic_coverage.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.topic_coverage'`.

- [ ] **Step 4: Implement `topic_coverage.py`.**

```python
# science/src/science_tool/topic_coverage.py
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from science_tool.markdown_utils import rendered_prose

# Placeholder sentences emitted by the promotion / substrate-retirement path.
# NOTE: duplicates a string that path owns; centralizing this constant with the
# emitter is deferred (design §Follow-ups).
STUB_SENTINEL = re.compile(r"(has|have) not yet been (curated|added|separately curated)", re.IGNORECASE)
_HEADING = re.compile(r"^#+\s")
_LIST_MARKER = re.compile(r"^([-*+]|\d+\.)\s+")


class MalformedTopicError(ValueError):
    """A topic file has a frontmatter block that does not parse to a mapping."""


@dataclass(frozen=True)
class TopicRow:
    id: str
    title: str
    path: str  # project-root-relative, POSIX
    substantive: bool

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "path": self.path, "substantive": self.substantive}


@dataclass(frozen=True)
class TopicCoverage:
    n_topics: int
    n_substantive: int
    stub_ratio: float | None
    stub_dominated: bool
    note: str | None
    topics: tuple[TopicRow, ...]

    def to_dict(self) -> dict:
        out: dict = {
            "n_topics": self.n_topics,
            "n_substantive": self.n_substantive,
            "stub_ratio": self.stub_ratio,
            "stub_dominated": self.stub_dominated,
            "topics": [r.to_dict() for r in self.topics],
        }
        if self.note is not None:
            out["note"] = self.note
        return out


def _read_frontmatter_strict(path: Path) -> tuple[dict, int]:
    """(frontmatter, body_start_line). Absent/empty block -> ({}, 1); a present
    block that fails to parse or is not a mapping raises MalformedTopicError.

    Unlike markdown_utils.parse_frontmatter, YAML errors are NOT swallowed."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, 1  # genuinely no frontmatter block
    for i, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            try:
                data = yaml.safe_load("\n".join(lines[1 : i - 1]))
            except yaml.YAMLError as exc:
                raise MalformedTopicError(f"{path}: unparseable frontmatter: {exc}") from exc
            if data is None:
                return {}, i + 1  # validly empty block -> stem fallback upstream
            if not isinstance(data, dict):
                raise MalformedTopicError(f"{path}: frontmatter is not a mapping")
            return data, i + 1
    raise MalformedTopicError(f"{path}: unterminated frontmatter block")


def _residual_content_lines(body: str) -> list[str]:
    lines: list[str] = []
    for raw in rendered_prose(body).splitlines():
        line = raw.strip()
        if not line or _HEADING.match(line):
            continue
        line = _LIST_MARKER.sub("", line).strip()
        if line:
            lines.append(line)
    return lines


def _is_stub(body: str) -> bool:
    residual = _residual_content_lines(body)
    if not residual:
        return True
    return all(STUB_SENTINEL.search(line) for line in residual)  # search: catches combined sentences


def _load_row(path: Path, project_root: Path) -> TopicRow | None:
    data, body_start = _read_frontmatter_strict(path)
    kind = data.get("kind")
    if kind is not None and kind != "topic":
        return None
    stem = path.stem
    body = "\n".join(path.read_text(encoding="utf-8").splitlines()[body_start - 1 :])
    return TopicRow(
        id=data.get("id") or f"topic:{stem}",
        title=data.get("title") or stem,
        path=path.relative_to(project_root).as_posix(),
        substantive=not _is_stub(body),
    )


def compute_topic_coverage(project_root: Path) -> TopicCoverage:
    project_root = project_root.resolve()
    topics_dir = project_root / "entities" / "topics"
    rows: list[TopicRow] = []
    if topics_dir.is_dir():
        for path in sorted(topics_dir.glob("*.md")):
            if path.name.startswith("_"):
                continue
            row = _load_row(path, project_root)
            if row is not None:
                rows.append(row)
    rows.sort(key=lambda r: r.id)

    n_topics = len(rows)
    n_substantive = sum(1 for r in rows if r.substantive)
    if n_topics == 0:
        return TopicCoverage(0, 0, None, False, "no topics", ())
    stub_ratio = 1 - n_substantive / n_topics
    return TopicCoverage(n_topics, n_substantive, stub_ratio, stub_ratio > 0.5, None, tuple(rows))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_topic_coverage.py -q`
Expected: PASS.

---

## Task 2: `science project topic-coverage` CLI command

**Files:**
- Modify: `science/src/science_tool/cli.py` (add under the `project` group, near `project_serialize`)
- Test: extend `science/tests/test_topic_coverage.py`

**Interface:** `science project topic-coverage [--project-root PATH] [--format text|json]`, default `--format text`. JSON is `TopicCoverage.to_dict()` (design shape). Text is a one-line summary plus, when `stub_dominated`, a `⚠ stub-dominated` marker and the stub ids.

- [ ] **Step 1: Write the failing CLI test**

```python
# append to science/tests/test_topic_coverage.py
import json
from click.testing import CliRunner
from science_tool.cli import main


def test_cli_json_shape() -> None:
    res = CliRunner().invoke(
        main, ["project", "topic-coverage", "--project-root", str(FIX), "--format", "json"]
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["n_topics"] == 4
    assert payload["n_substantive"] == 2
    assert {t["id"] for t in payload["topics"]} >= {"topic:promoted-stub", "topic:partial"}
    assert all({"id", "title", "path", "substantive"} <= set(t) for t in payload["topics"])


def test_cli_text_default() -> None:
    res = CliRunner().invoke(main, ["project", "topic-coverage", "--project-root", str(FIX)])
    assert res.exit_code == 0, res.output
    assert "topics" in res.output.lower()
```

- [ ] **Step 2: Run to verify failure** — `cd science && uv run --frozen pytest tests/test_topic_coverage.py -q` (new tests fail on missing command).

- [ ] **Step 3: Add the command** to `cli.py` under `@project` (near `project_serialize`). `json` is already imported at module top.

```python
@project.command("topic-coverage")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    envvar="SCIENCE_PROJECT_ROOT",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root containing entities/topics/.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
def project_topic_coverage(project_root: Path, output_format: str) -> None:
    """Report how much of entities/topics/ is curated (substantive vs. stub)."""
    from science_tool.topic_coverage import MalformedTopicError, compute_topic_coverage

    try:
        cov = compute_topic_coverage(project_root)
    except MalformedTopicError as exc:
        raise click.ClickException(str(exc)) from exc

    if output_format == "json":
        click.echo(json.dumps(cov.to_dict(), indent=2))
        return
    if cov.n_topics == 0:
        click.echo("topics: 0 (no topics)")
        return
    warn = "  ⚠ stub-dominated" if cov.stub_dominated else ""
    click.echo(
        f"topics: {cov.n_topics} (substantive {cov.n_substantive}, "
        f"stubs {cov.n_topics - cov.n_substantive}) — stub_ratio {cov.stub_ratio:.2f}{warn}"
    )
    if cov.stub_dominated:
        for r in cov.topics:
            if not r.substantive:
                click.echo(f"  stub: {r.id}")
```

- [ ] **Step 4: Run to verify pass**, then the full file: `cd science && uv run --frozen pytest tests/test_topic_coverage.py -q`.

- [ ] **Step 5: Smoke-test against MM30** (real data, sanity only — no commit):
  `cd science && uv run --frozen science project topic-coverage --project-root ~/d/cancer/cancer-types/multiple-myeloma --format json`
  Expected: `n_topics ≈ 37`, `n_substantive == 3`, `stub_ratio ≈ 0.92`, `stub_dominated true`, and the 3 substantive rows are the translation/ribosome/PRC2 topics.

---

## Task 3: `explore-ideas` command markdown (consume the diagnostic, broaden the brief)

**Files:**
- Modify: `commands/explore-ideas.md`

- [ ] **Step 1: Phase 1 — Frame.** Amend §"Generate — Phase 1: Frame":
  - Under the read list, keep `science.yaml`, `specs/research-question.md`, `specs/scope-boundaries.md`, `entities/topics/` — but instruct the orchestrator to use `science.yaml` **more fully** (fold `summary`, `tags`, `aspects`, `data_sources`, `ontologies` into the brief as scope terms) and to use **all topic titles for breadth** plus substantive topic bodies for depth.
  - Add a step: run `uv run science project topic-coverage --format json`; when `stub_dominated`, lean harder on the blindness-safe breadth sources so a stubby `topics/` does not collapse the brief.
  - Restate the blindness boundary: **only the two named `specs/` files**, never all of `specs/`; never `hypotheses/`/`questions/`/`papers/`.

- [ ] **Step 2: Phase 4 — Report.** Amend the report format so its header carries a coverage block:
  ```yaml
  seed_coverage:
    n_topics: 37
    n_substantive: 3
    stub_ratio: 0.92
    stub_dominated: true   # brief was stub-dominated; novelty judgments account for thin seed
  ```
  with a one-line human caveat when `stub_dominated`.

- [ ] **Step 3: Consistency check.** Grep `commands/explore-ideas.md` to confirm no remaining instruction implies reading `entities/hypotheses|questions|papers` in Phase 1, and that the `specs/` wording names exactly the two files.

- [ ] **Step 4: Regenerate the Codex mirror.** Run `python scripts/generate_codex_skills.py` (regenerates all `codex-skills/*/SKILL.md`, including `science-explore-ideas`). Confirm `codex-skills/science-explore-ideas/SKILL.md` reflects the edits and that `git status` shows only expected mirror churn. Do **not** hand-edit the mirror.

---

## Task 4: Validation sweep + feedback bookkeeping

- [ ] **Step 1:** From `science/`: `uv run --frozen pytest tests/test_topic_coverage.py tests/test_codex_skills.py -q` green (the codex-skills test guards the regenerated mirror); then `uv run --frozen ruff check src/science_tool/topic_coverage.py src/science_tool/cli.py` and `uv run --frozen ruff format --check src/science_tool/topic_coverage.py` clean. (Paths are repo-root-relative under `science/`, i.e. `src/science_tool/…`, not `science/src/…`.)
- [ ] **Step 2:** Mark the feedback addressed (meta-scoped, run from `~/d/science/meta`, separate from any tool-code commit):
  `uv run science feedback update fb-2026-07-05-002 --status addressed --resolution "…commit/branch + one-line summary…"` (confirm exact `feedback update` flags with `--help` first).
- [ ] **Step 3:** Check the design-doc boxes if any were left unchecked; note in the design doc that the deferred items (cluster-coverage, next-run biasing, sentinel centralization) remain open.

---

## Done criteria

- `science project topic-coverage` exists, is pure/read-only, and returns the design's JSON shape including the zero-topics branch.
- Both stub shapes and the partial-curation case are classified correctly, and a present-but-unparseable frontmatter block raises `MalformedTopicError` (no fabricated stem row) — all proven by tests; MM30 smoke-test reports `stub_dominated: true`.
- `codex-skills/science-explore-ideas/SKILL.md` is regenerated from the edited command and `tests/test_codex_skills.py` passes.
- `commands/explore-ideas.md` Phase 1 broadens the brief with blindness-safe sources only, and Phase 4 surfaces the coverage diagnostic; the blindness boundary is intact (two named `specs/` files; no hypotheses/questions/papers).
- No schema, graph, or `validate` changes; deferred items remain explicitly out of scope.
