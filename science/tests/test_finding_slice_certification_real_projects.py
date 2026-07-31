"""Step 4 of the finding slice: certify the candidate profile over the real corpus.

Every authored `finding` record in every Science project on this machine is validated
against the composed candidate profile with `unevaluatedProperties: false` armed. If a
record would be refused after step 7, it is refused here first.

**This kind reaches the schema by TWO paths, and both are certified here.** 52 markdown
records across 3 project roots, and 149 structured source rows in `~/d/natural-systems`
whose authored boundary is computed differently (`_STRUCTURED_INJECTED_KEYS - authored`,
not `MarkdownAdapter.INJECTED_KEYS`). A file that certified only the markdown half would
cover a quarter of the corpus while reporting success.

Scope, stated plainly so a green run is not over-read:

- It reproduces each adapter's AUTHORED boundary rather than validating raw rows, because
  the boundary -- not the file -- is what `build` hands the schema. For the structured path
  that reproduction is pinned against the key set an instrumented REAL load produced, so it
  cannot quietly certify this file's idea of the loader.
- It does NOT run `load_project_sources`; that is step 6, with `finding` armed for real
  rather than monkeypatched.
- Every record is `status: active` after the migration, so no probe here distinguishes a
  correct status vocabulary from an over-tight one. Asserted below rather than implied.

`finding` is armed here by patching the two names `validate_as` actually reads. Six modules
bind `PROJECT_MIXIN_NAMES` by value at import, so a patch-based simulation of the full load
path would have to hit all six; the control at the bottom fails loudly if arming did not
take.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from science_model.entity_schema import loader as loader_module
from science_model.entity_schema import validator as validator_module
from science_model.entity_schema.profile import (
    BASE_NAME,
    PROJECT_MIXIN_NAMES,
    TYPE_MIXIN_NAMES,
    ProfileComponent,
    ProfileString,
)
from science_model.entity_schema.validator import EntityValidationError, EntityValidator

from science_tool.graph.source_normalization import normalize_structured_row
from science_tool.graph.sources import _STRUCTURED_INJECTED_KEYS
from science_tool.graph.storage_adapters.markdown import MarkdownAdapter

CANDIDATE = ProfileString(
    base=ProfileComponent(BASE_NAME, "2.0"),
    mixin=ProfileComponent("finding", "1.0"),
    extensions=(),
)

# Frozen identities and counts, measured 2026-07-30 over all 18 project roots in the five
# repos, by parsing frontmatter rather than grepping `kind:`.
EXPECTED: dict[str, int] = {
    "cancer/cancer-types/multiple-myeloma": 3,
    "natural-systems": 23,
    "protein-landscape": 26,
}

CORPUS_MARKDOWN_TOTAL = 52
CORPUS_STRUCTURED_TOTAL = 149

# The other 15 roots, enumerated rather than implied.
EXPECTED_EMPTY: tuple[str, ...] = (
    "cancer/cancer-types/breast",
    "cancer/cancer-types/head-and-neck",
    "cancer/cancer-types/ovarian",
    "cancer/cancer-types/prostate",
    "cancer/conditions/pre-cancer",
    "cancer/data-sources/cbioportal",
    "cancer/mechanisms/evolution",
    "cancer/meta",
    "cancer/therapeutics",
    "health/comparisons/pan-disease",
    "health/meta",
    "health/processes/cycles",
    "health/processes/immunity",
    "health/processes/post-acute-infection",
    "science-commons",
)

STRUCTURED_SOURCE = (
    "natural-systems",
    "knowledge/sources/project_specific/finding.yaml",
)

# The key set an instrumented REAL `load_project_sources` handed the schema for these rows,
# measured before the migration and extended by the two keys it adds. Pinning it is what
# keeps `_structured_authored` below from certifying a reimplementation of the loader.
STRUCTURED_AUTHORED_KEYS = frozenset(
    {
        "id",
        "kind",
        "title",
        "status",
        "created",
        "updated",
        "profile",
        "file_path",
        "description",
        "evidence_refs",
        "related",
        "source_refs",
        "aliases",
        "ontology_terms",
    }
)

_SKIP_DIRS = {
    ".venv",
    "venv",
    ".git",
    "node_modules",
    "__pycache__",
    "site-packages",
    ".worktrees",
    ".tox",
    "templates",
}


def _walk(directory: Path):
    try:
        entries = list(directory.iterdir())
    except (PermissionError, OSError):
        return
    for entry in entries:
        if entry.is_symlink():
            continue
        if entry.is_dir():
            if entry.name not in _SKIP_DIRS:
                yield from _walk(entry)
        elif entry.suffix == ".md":
            yield entry


def _finding_records(root: Path) -> list[tuple[Path, dict]]:
    found: list[tuple[Path, dict]] = []
    for path in _walk(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if not text.startswith("---\n"):
            continue
        end = text.find("\n---", 4)
        if end == -1:
            continue
        try:
            frontmatter = yaml.safe_load(text[4:end])
        except yaml.YAMLError:
            continue
        if not isinstance(frontmatter, dict):
            continue
        if frontmatter.get("kind") != "finding" or "_template" in frontmatter:
            continue
        found.append((path, frontmatter))
    return found


@pytest.fixture
def strict(monkeypatch) -> EntityValidator:
    monkeypatch.setattr(
        validator_module, "PROJECT_MIXIN_NAMES", PROJECT_MIXIN_NAMES | {"finding"}
    )
    monkeypatch.setattr(loader_module, "TYPE_MIXIN_NAMES", TYPE_MIXIN_NAMES | {"finding"})
    return EntityValidator()


def _project_root(relative: str) -> Path:
    root = Path.home() / "d" / relative
    # Not a skip: this module only runs when `-m real_projects` selects it, so reaching
    # this line IS the explicit request, and "the 16 available roots passed" must never be
    # able to masquerade as "all 18 passed".
    assert (root / "science.yaml").is_file(), (
        f"expected Science project at {root}; certification cannot be partial"
    )
    return root


def _markdown_authored(frontmatter: dict) -> dict:
    return {k: v for k, v in frontmatter.items() if k not in MarkdownAdapter.INJECTED_KEYS}


def _structured_authored(row: dict, *, default_path: str, local_profile: str) -> dict:
    """Reproduce `sources.py`'s authored boundary for one structured row.

    Mirrors `_structured_entities`: normalize (the REAL function), capture `authored`
    BEFORE the loader's backfills, apply the backfills, then subtract
    `_STRUCTURED_INJECTED_KEYS - authored`. The resulting key set is pinned against
    `STRUCTURED_AUTHORED_KEYS`, which came from instrumenting a real load.
    """
    raw = normalize_structured_row(row)
    authored = frozenset(raw)
    raw["kind"] = "finding"
    raw["type"] = "finding"
    raw.setdefault("canonical_id", row["canonical_id"])
    raw.setdefault("title", row.get("title") or row["canonical_id"])
    raw.setdefault("profile", row.get("profile") or local_profile)
    raw.setdefault("file_path", default_path)
    for key in ("related", "source_refs", "evidence_refs", "aliases", "ontology_terms"):
        raw.setdefault(key, list(row.get(key, [])))
    injected = _STRUCTURED_INJECTED_KEYS - authored
    return {k: v for k, v in raw.items() if k not in injected}


def _structured_rows() -> list[dict]:
    root = _project_root(STRUCTURED_SOURCE[0])
    return json.loads((root / STRUCTURED_SOURCE[1]).read_text())["finding"]


# --- the markdown path ------------------------------------------------------------


@pytest.mark.real_projects
@pytest.mark.parametrize("relative", sorted(EXPECTED))
def test_every_authored_markdown_finding_satisfies_the_candidate_profile(relative, strict):
    root = _project_root(relative)
    records = _finding_records(root)
    assert len(records) == EXPECTED[relative], (
        f"{relative}: expected {EXPECTED[relative]} findings, found {len(records)}"
    )

    failures: list[str] = []
    for path, frontmatter in records:
        try:
            strict.validate_as(_markdown_authored(frontmatter), CANDIDATE)
        except EntityValidationError as exc:
            failures.append(f"{path.relative_to(root)}: {exc}")
    assert not failures, "\n".join(failures)


@pytest.mark.real_projects
@pytest.mark.parametrize("relative", EXPECTED_EMPTY)
def test_no_other_project_root_holds_a_finding(relative):
    """The 3-root premise, asserted over the other 15 rather than assumed."""
    root = _project_root(relative)
    records = _finding_records(root)
    assert not records, (
        f"{relative} now holds {len(records)} finding(s): "
        f"{[str(p.relative_to(root)) for p, _ in records]}"
    )


# --- the structured path ----------------------------------------------------------


@pytest.mark.real_projects
def test_every_structured_row_satisfies_the_candidate_profile(strict):
    rows = _structured_rows()
    assert len(rows) == CORPUS_STRUCTURED_TOTAL

    failures: list[str] = []
    for row in rows:
        authored = _structured_authored(
            row,
            default_path=STRUCTURED_SOURCE[1],
            local_profile="project_specific",
        )
        try:
            strict.validate_as(authored, CANDIDATE)
        except EntityValidationError as exc:
            failures.append(f"{row['canonical_id']}: {exc}")
    assert not failures, "\n".join(failures[:10])


@pytest.mark.real_projects
def test_the_reproduced_structured_boundary_matches_the_instrumented_one():
    """Pins `_structured_authored` against a real load, so it cannot drift into fiction.

    Without this, the certification above would prove only that rows satisfy the profile
    under THIS FILE's idea of what the loader hands the schema.
    """
    rows = _structured_rows()
    seen = {
        frozenset(
            _structured_authored(
                row, default_path=STRUCTURED_SOURCE[1], local_profile="project_specific"
            )
        )
        for row in rows
    }
    assert seen == {STRUCTURED_AUTHORED_KEYS}


@pytest.mark.real_projects
def test_the_structured_path_is_the_only_one_of_its_kind():
    """`finding` is the only CORE kind routed through the structured loader.

    This is why the slice carries a source migration at all. If a second core kind gains a
    `core_structured_sources` entry, its own slice inherits this whole second path -- and
    this assertion is where that becomes visible.
    """
    manifest = yaml.safe_load(
        (
            _project_root(STRUCTURED_SOURCE[0])
            / "knowledge/sources/project_specific/manifest.yaml"
        ).read_text()
    )
    declared = {entry["kind"] for entry in manifest.get("core_structured_sources") or []}
    assert declared == {"finding"}


# --- what this corpus cannot show, and the extension composition ------------------


@pytest.mark.real_projects
def test_no_project_extension_covers_finding():
    """Slice 2's lesson: read the project's extension declarations, do not assume them.

    Both extensions in the tree (`mm30.assessment`, `protein-landscape.promotion`) are
    hypothesis-scoped, so the composed profile for a `finding` in those projects IS the
    candidate -- there is no project-side escape hatch, and every corpus field had to be
    admitted by the core mixin. If a project ever scopes an extension to `finding`, this
    fails and the field set needs re-deriving.
    """
    for relative in sorted(EXPECTED):
        config = yaml.safe_load((_project_root(relative) / "science.yaml").read_text())
        scoped = (config.get("entity_extensions") or {}).get("finding")
        assert not scoped, f"{relative} now scopes an extension to finding: {scoped}"


@pytest.mark.real_projects
def test_the_whole_corpus_is_status_active_so_the_vocabulary_is_uncertified():
    """Recorded as a test so a green suite is not read as vocabulary evidence.

    `finding` declares four statuses and the corpus exercises exactly one. `superseded` in
    particular is authored by nobody on a `supersedable=True` kind. No probe over this
    corpus distinguishes a correct vocabulary from an over-tight one -- which is why the
    mixin declares `status` with no enum.
    """
    markdown = {
        fm.get("status")
        for relative in EXPECTED
        for _, fm in _finding_records(_project_root(relative))
    }
    structured = {row["status"] for row in _structured_rows()}
    assert markdown == {"active"}
    assert structured == {"active"}


@pytest.mark.real_projects
def test_every_project_root_is_accounted_for():
    assert not set(EXPECTED) & set(EXPECTED_EMPTY)
    assert len(EXPECTED) + len(EXPECTED_EMPTY) == 18
    assert sum(EXPECTED.values()) == CORPUS_MARKDOWN_TOTAL
    assert EXPECTED, "EXPECTED emptied; parametrized certification would collect zero tests"


@pytest.mark.real_projects
def test_the_arming_patch_actually_took(strict):
    """The control, and it is load-bearing rather than decorative -- measured.

    Six modules bind `PROJECT_MIXIN_NAMES` by value at import, so a patch that failed to
    apply would leave every certification above validating against a profile that admits
    anything: a green check over an unchecked corpus.

    Verified by removing the `PROJECT_MIXIN_NAMES` patch from the fixture and re-running
    this file: **only this test failed.** All 24 corpus certifications still reported
    success. That is precisely the failure mode the control exists to catch, and it is why
    a passing certification suite without a working control proves nothing at all.
    """
    with pytest.raises(EntityValidationError):
        strict.validate_as(
            {
                "id": "finding:0001-x",
                "kind": "finding",
                "title": "t",
                "status": "active",
                "created": "2026-01-01",
                "updated": "2026-01-01",
                "shadow_key": "unvouched",
            },
            CANDIDATE,
        )
