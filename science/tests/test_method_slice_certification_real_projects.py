"""Step 4 of the method slice: certify the candidate profile over the real corpus.

Every authored `method` record in every Science project on this machine is validated
against the composed candidate profile with `unevaluatedProperties: false` armed. If a
record would be refused after step 7, it is refused here first.

Scope of what this file proves, stated plainly so it is not over-read:

- It reproduces the MARKDOWN ADAPTER's authored boundary (`raw` minus
  `MarkdownAdapter.INJECTED_KEYS`) rather than validating raw frontmatter, because the
  boundary -- not the frontmatter -- is what `build` hands the schema.
- It does NOT run `load_project_sources`; that is measured separately in step 6 with
  `method` armed for real rather than monkeypatched.
  `~/d/health/processes/post-acute-infection` cannot be loaded at all today -- it
  predates the task storage split and fails on `tasks/active.md` on `main` as well --
  so its 6 methods are certified here at the schema boundary only. See the slice
  inventory.

`method` is armed here by patching the two names `validate_as` actually reads.
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
    mixin=ProfileComponent("method", "1.0"),
    extensions=(),
)

# Frozen identities and counts, measured 2026-07-29. A project that has moved, or whose
# count has drifted, must be reconciled -- not quietly re-measured.
EXPECTED: dict[str, int] = {
    "cancer/cancer-types/multiple-myeloma": 25,
    "cancer/data-sources/cbioportal": 2,
    "health/processes/post-acute-infection": 6,
    "protein-landscape": 13,
    "seq-feats": 5,
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


def _method_records(root: Path) -> list[tuple[Path, dict]]:
    """Authored method records under `root`.

    The packaged `science_model/templates/method.md` carries `kind: method` and lives
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
        if frontmatter.get("kind") != "method" or "_template" in frontmatter:
            continue
        found.append((path, frontmatter))
    return found


@pytest.fixture
def strict(monkeypatch) -> EntityValidator:
    monkeypatch.setattr(
        validator_module, "PROJECT_MIXIN_NAMES", PROJECT_MIXIN_NAMES | {"method"}
    )
    monkeypatch.setattr(loader_module, "TYPE_MIXIN_NAMES", TYPE_MIXIN_NAMES | {"method"})
    return EntityValidator()


def _project_root(relative: str) -> Path:
    root = Path.home() / "d" / relative
    # Not a skip. This module only runs when `-m real_projects` selects it, so reaching
    # this line IS the explicit request -- and "the 4 available projects passed" must
    # never be able to masquerade as "all 5 passed".
    assert (root / "science.yaml").is_file(), (
        f"expected Science project at {root}; certification cannot be partial"
    )
    return root


@pytest.mark.real_projects
@pytest.mark.parametrize("relative", sorted(EXPECTED))
def test_every_authored_method_satisfies_the_candidate_profile(relative, strict):
    root = _project_root(relative)
    records = _method_records(root)
    assert len(records) == EXPECTED[relative], (
        f"{relative}: expected {EXPECTED[relative]} methods, found {len(records)}"
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
def test_the_out_of_vocabulary_status_record_is_admitted(strict):
    """The status ruling, certified against the actual file rather than a fixture.

    cbioportal's `method:length-aware-geneset-enrichment` carries `status: proposed`,
    which the descriptor's vocabulary (profiles/core.py:504) does not list. `method` is
    not in `_CERTIFIED_KINDS`, so closure must not refuse it at load -- see the mixin's
    `status` comment. If someone later enum-locks `status`, this fails by NAME instead
    of surfacing as an anonymous corpus refusal.
    """
    root = _project_root("cancer/data-sources/cbioportal")
    path = root / "entities/methods/length-aware-geneset-enrichment.md"
    assert path.is_file(), f"{path} moved; the ruling's witness must be reconciled"
    frontmatter = next(fm for p, fm in _method_records(root) if p == path)
    assert frontmatter["status"] == "proposed", (
        "the witness record no longer carries an out-of-vocabulary status; "
        "re-derive the ruling rather than deleting this test"
    )
    strict.validate_as(
        {k: v for k, v in frontmatter.items() if k not in MarkdownAdapter.INJECTED_KEYS},
        CANDIDATE,
    )


@pytest.mark.real_projects
@pytest.mark.parametrize("relative", sorted(EXPECTED))
def test_no_method_record_authors_an_adapter_injected_key(relative):
    """Why the authored view above equals the frontmatter for this kind.

    `sources.py:434` passes `MarkdownAdapter.INJECTED_KEYS` unconditionally, while every
    other call site passes `INJECTED_KEYS - authored`. So an author who writes `content:`
    in frontmatter has it hidden from the schema rather than judged by it -- the exact
    failure `EntityRegistry.build`'s docstring names. That blind spot is real, is
    kind-agnostic, and is out of scope for this slice; this assertion pins the fact that
    no method record exercises it, so the subtraction above is currently a no-op rather
    than a silent drop.
    """
    root = _project_root(relative)
    offenders = [
        str(path.relative_to(root))
        for path, frontmatter in _method_records(root)
        if set(frontmatter) & MarkdownAdapter.INJECTED_KEYS
    ]
    assert not offenders, offenders


@pytest.mark.real_projects
@pytest.mark.parametrize("relative", sorted(EXPECTED))
def test_no_project_declares_a_method_extension(relative):
    """The precondition for certifying against base + mixin alone.

    Step 4 requires composing each project's own declared extensions. Two projects
    declare one -- mm30's `mm30.assessment` and protein-landscape's
    `protein-landscape.promotion` -- and BOTH are scoped to `hypothesis`. That is why
    all 20 `promoted_from` records depend on this mixin declaring the field:
    protein-landscape's promotion extension does not reach its own methods.
    """
    root = _project_root(relative)
    config = yaml.safe_load((root / "science.yaml").read_text(encoding="utf-8")) or {}
    declared = (config.get("entity_extensions") or {}).get("method")
    assert not declared, f"{relative} declares method extensions {declared!r}"


@pytest.mark.real_projects
def test_the_certification_harness_is_actually_armed(strict):
    """Without this, every assertion above passes just as well unarmed.

    An unarmed composition omits `unevaluatedProperties`, so a corpus sweep finding
    zero violations would prove only that the sweep ran.
    """
    clean = {
        "id": "method:null-model",
        "kind": "method",
        "title": "Null model",
        "status": "active",
        "created": "2026-06-10",
        "updated": "2026-06-10",
    }
    strict.validate_as(clean, CANDIDATE)
    with pytest.raises(EntityValidationError):
        strict.validate_as(dict(clean, shadow_key="unvouched"), CANDIDATE)


@pytest.mark.real_projects
def test_the_corpus_total_is_the_frozen_51():
    total = sum(len(_method_records(_project_root(rel))) for rel in EXPECTED)
    assert total == 51


@pytest.mark.real_projects
def test_the_promoted_from_population_is_the_frozen_20():
    """The single largest reason this mixin declares `promoted_from`.

    Counted across the whole corpus rather than per project, because the field's
    admissibility is a per-KIND ruling: 16 in mm30 and 4 in protein-landscape, and
    neither project has an extension that would admit it.
    """
    carriers = [
        (rel, path)
        for rel in EXPECTED
        for path, fm in _method_records(_project_root(rel))
        if "promoted_from" in fm
    ]
    assert len(carriers) == 20, carriers
