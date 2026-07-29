"""Step 4 of the concept slice: certify the candidate profile over the real corpus.

Every authored `concept` record in every Science project on this machine is validated
against the composed candidate profile with `unevaluatedProperties: false` armed. If a
record would be refused after step 7, it is refused here first.

Scope of what this file proves, stated plainly so it is not over-read:

- It reproduces the MARKDOWN ADAPTER's authored boundary (`raw` minus
  `MarkdownAdapter.INJECTED_KEYS`) rather than validating raw frontmatter, because the
  boundary -- not the frontmatter -- is what `build` hands the schema.
- It does NOT run `load_project_sources`. That was verified by hand against the two
  projects that currently load, with `concept` temporarily armed for real rather than
  monkeypatched: entity and concept counts were byte-identical before and after
  (mm30 4028/285, natural-systems 4160/7), and a virtual record carrying an
  undeclared key was refused through the real adapter. `~/d/health/processes/
  post-acute-infection` cannot be loaded at all today -- it predates the task storage
  split and fails on `tasks/active.md` on `main` as well -- so its 37 concepts are
  certified here at the schema boundary only. See the slice inventory.

`concept` is armed here by patching the two names `validate_as` actually reads.
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
    mixin=ProfileComponent("concept", "1.1"),
    extensions=(),
)

# Frozen identities and counts, measured 2026-07-28. A project that has moved, or whose
# count has drifted, must be reconciled -- not quietly re-measured.
EXPECTED: dict[str, int] = {
    "cancer/cancer-types/multiple-myeloma": 285,
    "health/processes/post-acute-infection": 37,
    "natural-systems": 7,
}

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


def _concept_records(root: Path) -> list[tuple[Path, dict]]:
    """Authored concept records under `root`.

    The packaged `science_model/templates/concept.md` carries `kind: concept` and lives
    inside every consumer's `.venv`, so it reads as a record and is not one. `_SKIP_DIRS`
    excludes it by directory; the `_template` guard excludes it if a copy ever escapes.
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
        if frontmatter.get("kind") != "concept" or "_template" in frontmatter:
            continue
        found.append((path, frontmatter))
    return found


@pytest.fixture
def strict(monkeypatch) -> EntityValidator:
    monkeypatch.setattr(
        validator_module, "PROJECT_MIXIN_NAMES", PROJECT_MIXIN_NAMES | {"concept"}
    )
    monkeypatch.setattr(loader_module, "TYPE_MIXIN_NAMES", TYPE_MIXIN_NAMES | {"concept"})
    return EntityValidator()


def _project_root(relative: str) -> Path:
    root = Path.home() / "d" / relative
    # Not a skip. This module only runs when `-m real_projects` selects it, so reaching
    # this line IS the explicit request -- and "the 2 available projects passed" must
    # never be able to masquerade as "all 3 passed".
    assert (root / "science.yaml").is_file(), (
        f"expected Science project at {root}; certification cannot be partial"
    )
    return root


@pytest.mark.real_projects
@pytest.mark.parametrize("relative", sorted(EXPECTED))
def test_every_authored_concept_satisfies_the_candidate_profile(relative, strict):
    root = _project_root(relative)
    records = _concept_records(root)
    assert len(records) == EXPECTED[relative], (
        f"{relative}: expected {EXPECTED[relative]} concepts, found {len(records)}"
    )

    failures: list[str] = []
    for path, frontmatter in records:
        authored = {
            key: value
            for key, value in frontmatter.items()
            if key not in MarkdownAdapter.INJECTED_KEYS
        }
        try:
            strict.validate_as(authored, CANDIDATE)
        except EntityValidationError as exc:
            failures.append(f"{path.relative_to(root)}: {exc}")
    assert not failures, "\n".join(failures)


@pytest.mark.real_projects
@pytest.mark.parametrize("relative", sorted(EXPECTED))
def test_no_concept_record_authors_an_adapter_injected_key(relative):
    """Why the authored view above equals the frontmatter for this kind.

    `MarkdownAdapter.INJECTED_KEYS` is subtracted unconditionally, so an author who
    writes `content:` in frontmatter has it hidden from the schema rather than judged
    by it. That blind spot is real and out of scope for this slice -- this assertion
    pins the fact that no concept record exercises it, so the subtraction above is
    currently a no-op rather than a silent drop.
    """
    root = _project_root(relative)
    offenders = [
        str(path.relative_to(root))
        for path, frontmatter in _concept_records(root)
        if set(frontmatter) & MarkdownAdapter.INJECTED_KEYS
    ]
    assert not offenders, offenders


@pytest.mark.real_projects
@pytest.mark.parametrize("relative", sorted(EXPECTED))
def test_no_project_declares_a_concept_extension(relative):
    """The precondition for certifying against base + mixin alone.

    Step 4 requires composing each project's own declared extensions. No project
    declares one for `concept` -- mm30's `mm30.assessment` is scoped to `hypothesis` --
    so the candidate above IS the production composition. If that ever changes, this
    fails and the extension must be composed rather than assumed away.
    """
    root = _project_root(relative)
    config = yaml.safe_load((root / "science.yaml").read_text(encoding="utf-8")) or {}
    declared = (config.get("entity_extensions") or {}).get("concept")
    assert not declared, f"{relative} declares concept extensions {declared!r}"


@pytest.mark.real_projects
def test_the_certification_harness_is_actually_armed(strict):
    """Without this, every assertion above passes just as well unarmed.

    An unarmed composition omits `unevaluatedProperties`, so a corpus sweep finding
    zero violations would prove only that the sweep ran.
    """
    clean = {
        "id": "concept:age",
        "kind": "concept",
        "title": "Age",
        "status": "active",
        "created": "2026-06-10",
        "updated": "2026-06-10",
    }
    strict.validate_as(clean, CANDIDATE)
    with pytest.raises(EntityValidationError):
        strict.validate_as(dict(clean, shadow_key="unvouched"), CANDIDATE)


@pytest.mark.real_projects
def test_the_corpus_total_is_the_frozen_329():
    total = sum(len(_concept_records(_project_root(rel))) for rel in EXPECTED)
    assert total == 329
