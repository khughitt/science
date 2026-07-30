"""Step 4 of the search slice: certify the candidate profile over the real corpus.

Every authored `search` record in every Science project on this machine is validated
against the composed candidate profile with `unevaluatedProperties: false` armed. If a
record would be refused after step 7, it is refused here first.

Scope of what this file proves, stated plainly so it is not over-read:

- It reproduces the MARKDOWN ADAPTER's authored boundary (`raw` minus
  `MarkdownAdapter.INJECTED_KEYS`) rather than validating raw frontmatter, because the
  boundary -- not the frontmatter -- is what `build` hands the schema.
- It does NOT run `load_project_sources`; that is measured separately in step 6 with
  `search` armed for real rather than monkeypatched.
  `~/d/health/processes/post-acute-infection` cannot be loaded at all today -- it
  predates the task storage split and fails on `tasks/active.md` on `main` as well --
  so its 9 searches are certified here at the schema boundary only, exactly as the
  `method` slice certified its 6.

`search` is armed here by patching the two names `validate_as` actually reads.
Six modules bind `PROJECT_MIXIN_NAMES` by value at import time, so a patch-based
simulation of the FULL load path would have to hit all six and would silently certify
nothing if it missed one. The control at the bottom is what keeps this file honest:
it fails loudly if the arming did not take.
"""

from __future__ import annotations

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

from science_tool.graph.storage_adapters.markdown import MarkdownAdapter

CANDIDATE = ProfileString(
    base=ProfileComponent(BASE_NAME, "2.0"),
    mixin=ProfileComponent("search", "1.0"),
    extensions=(),
)

# Frozen identities and counts, measured 2026-07-30. A project that has moved, or whose
# count has drifted, must be reconciled -- not quietly re-measured.
#
# Note the granularity: a repo-level scan reports "cancer 19", which is FOUR projects.
# Certification is per project root, because that is the unit that owns a `science.yaml`
# and therefore the unit whose extensions compose.
EXPECTED: dict[str, int] = {
    "cancer/cancer-types/multiple-myeloma": 8,
    "cancer/data-sources/cbioportal": 8,
    "cancer/mechanisms/evolution": 2,
    "cancer/meta": 1,
    "health/processes/cycles": 1,
    "health/processes/post-acute-infection": 9,
    "natural-systems": 7,
}

CORPUS_TOTAL = 36

_SKIP_DIRS = {
    ".venv",
    "venv",
    ".git",
    "node_modules",
    "__pycache__",
    "site-packages",
    ".worktrees",
    ".tox",
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


def _search_records(root: Path) -> list[tuple[Path, dict]]:
    """Authored search records under `root`.

    Unlike `method`, there is no packaged `templates/search.md` to exclude -- this kind
    ships no template at all. The `_template` guard is kept anyway: its absence is a fact
    about today's tree, not a property of the walk, and a template added later must not
    silently start reading as a record.
    """
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
        if frontmatter.get("kind") != "search" or "_template" in frontmatter:
            continue
        found.append((path, frontmatter))
    return found


@pytest.fixture
def strict(monkeypatch) -> EntityValidator:
    monkeypatch.setattr(validator_module, "PROJECT_MIXIN_NAMES", PROJECT_MIXIN_NAMES | {"search"})
    monkeypatch.setattr(loader_module, "TYPE_MIXIN_NAMES", TYPE_MIXIN_NAMES | {"search"})
    return EntityValidator()


def _project_root(relative: str) -> Path:
    root = Path.home() / "d" / relative
    # Not a skip. This module only runs when `-m real_projects` selects it, so reaching
    # this line IS the explicit request -- and "the 6 available projects passed" must
    # never be able to masquerade as "all 7 passed".
    assert (root / "science.yaml").is_file(), (
        f"expected Science project at {root}; certification cannot be partial"
    )
    return root


def _authored(frontmatter: dict) -> dict:
    return {k: v for k, v in frontmatter.items() if k not in MarkdownAdapter.INJECTED_KEYS}


@pytest.mark.real_projects
@pytest.mark.parametrize("relative", sorted(EXPECTED))
def test_every_authored_search_satisfies_the_candidate_profile(relative, strict):
    root = _project_root(relative)
    records = _search_records(root)
    assert len(records) == EXPECTED[relative], (
        f"{relative}: expected {EXPECTED[relative]} searches, found {len(records)}"
    )

    failures: list[str] = []
    for path, frontmatter in records:
        try:
            strict.validate_as(_authored(frontmatter), CANDIDATE)
        except EntityValidationError as exc:
            failures.append(f"{path.relative_to(root)}: {exc}")
    assert not failures, "\n".join(failures)


@pytest.mark.real_projects
def test_the_corpus_total_is_the_frozen_36():
    """The per-project counts sum to the inventory's total.

    Cheap, and it catches the failure the per-project assertions cannot: a project
    dropping out of `EXPECTED` entirely. A deleted row makes every remaining row pass.
    """
    assert sum(EXPECTED.values()) == CORPUS_TOTAL


@pytest.mark.real_projects
@pytest.mark.parametrize("relative", sorted(EXPECTED))
def test_no_search_record_still_carries_a_retired_task_key(relative):
    """Certifies the step-3 corpus migration against the real files.

    `task:` (5 records, mm30) and `task_ref:` (2, natural-systems) were migrated to
    `related` -- or, where the target was an unresolvable `tasks/archive.md` alias, to
    prose. The mixin omits both keys, so a record that regrows one is refused at load.
    Asserted by NAME here so the reason is legible; the profile check above would report
    it only as an anonymous `unevaluatedProperties` refusal.
    """
    root = _project_root(relative)
    offenders = [
        f"{path.relative_to(root)}: {sorted(set(fm) & {'task', 'task_ref'})}"
        for path, fm in _search_records(root)
        if {"task", "task_ref"} & set(fm)
    ]
    assert not offenders, "\n".join(offenders)


@pytest.mark.real_projects
@pytest.mark.parametrize("relative", sorted(EXPECTED))
def test_no_search_record_authors_an_adapter_injected_key(relative):
    """Why the authored view above equals the frontmatter for this kind.

    `sources.py:434` passes `MarkdownAdapter.INJECTED_KEYS` unconditionally, while every
    other call site passes `INJECTED_KEYS - authored`. So an author who writes `content:`
    in frontmatter has it hidden from the schema rather than judged by it. That blind
    spot is real, is kind-agnostic, is tracked as F1 in the slice procedure, and is out
    of scope here; this assertion pins the fact that no search record exercises it, so
    the subtraction above is currently a no-op rather than a silent drop.
    """
    root = _project_root(relative)
    offenders = [
        str(path.relative_to(root))
        for path, fm in _search_records(root)
        if set(fm) & MarkdownAdapter.INJECTED_KEYS
    ]
    assert not offenders, "\n".join(offenders)


@pytest.mark.real_projects
def test_the_whole_corpus_is_status_active():
    """The uniformity that makes this corpus unable to certify `status`, pinned as a fact.

    All 36 records are `active`, so every value probe over this corpus passes whether or
    not the schema enum-locks the field -- which is exactly how `mixin-concept-1.0`'s
    premature enum survived its own certification. This test does not defend the ruling
    (the mixin's probes do); it records the measurement the ruling was made against, so
    that if the corpus ever DOES vary, the ruling is revisited deliberately rather than
    by a probe quietly starting to mean something.
    """
    statuses = {
        fm.get("status")
        for relative in EXPECTED
        for _, fm in _search_records(_project_root(relative))
    }
    assert statuses == {"active"}, (
        f"the search corpus is no longer uniformly `active` "
        f"({sorted(str(s) for s in statuses)}); "
        "re-read the status ruling in the slice inventory before changing the mixin"
    )


@pytest.mark.real_projects
def test_no_project_declares_a_search_extension():
    """Certification composes base + mixin only, and that must be the whole story.

    The `method` slice found both extensions in its corpus were `hypothesis`-scoped --
    read, not assumed. Same check here: if a project ever scopes an extension to
    `search`, this file's composition is incomplete and would certify the wrong schema.
    """
    declared: list[str] = []
    for relative in EXPECTED:
        schemas = _project_root(relative) / "schemas"
        if not schemas.is_dir():
            continue
        for path in schemas.glob("*.json"):
            if '"search"' in path.read_text(encoding="utf-8"):
                declared.append(str(path))
    assert not declared, "\n".join(declared)


@pytest.mark.real_projects
def test_the_certification_harness_is_actually_armed(strict):
    """The control. Without it, every assertion above could be passing vacuously.

    An unarmed validator resolves `search` to `extension-search-1.0.json`, which does not
    exist -- so the records would not be leniently accepted, they would error. But a
    future refactor could make the lookup fall back rather than raise, and then a green
    run would mean nothing. This pins the two properties arming must have: the mixin is
    reachable, AND composition closes.
    """
    base = {
        "id": "search:0001-probe",
        "kind": "search",
        "title": "Probe",
        "status": "active",
        "created": "2026-07-30",
        "updated": "2026-07-30",
    }
    strict.validate_as(base, CANDIDATE)
    with pytest.raises(EntityValidationError):
        strict.validate_as({**base, "shadow_key": "unvouched"}, CANDIDATE)
