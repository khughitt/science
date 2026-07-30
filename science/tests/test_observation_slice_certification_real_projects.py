"""Step 4 of the observation slice: certify the candidate profile over the real corpus.

Every authored `observation` record in every Science project on this machine is validated
against the composed candidate profile with `unevaluatedProperties: false` armed. If a
record would be refused after step 7, it is refused here first.

Scope of what this file proves, stated plainly so it is not over-read:

- It reproduces the MARKDOWN ADAPTER's authored boundary (`raw` minus
  `MarkdownAdapter.INJECTED_KEYS`) rather than validating raw frontmatter, because the
  boundary -- not the frontmatter -- is what `build` hands the schema.
- It does NOT run `load_project_sources`; that is measured separately in step 6 with
  `observation` armed for real rather than monkeypatched.

**This kind's corpus is the weakest in the tranche, and the file says so where it matters.**
All 21 records live under a SINGLE project root. There is no second project whose
divergence could expose an over-tight field set, no second extension composition to
exercise, and no status variation at all. Several assertions below therefore exist to
record what this corpus CANNOT show, so that a green run is not mistaken for evidence it
did not produce.

`observation` is armed here by patching the two names `validate_as` actually reads.
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
    mixin=ProfileComponent("observation", "1.0"),
    extensions=(),
)

# Frozen identities and counts, measured 2026-07-30 over all 17 project roots in the four
# repos. ONE root holds the entire corpus -- see the module docstring.
EXPECTED: dict[str, int] = {
    "health/processes/cycles": 21,
}

CORPUS_TOTAL = 21

# The other 16 roots, enumerated rather than implied. `EXPECTED` alone cannot distinguish
# "one project holds every record" from "I only looked at one project", and that is the
# distinction this slice's whole certification story rests on.
EXPECTED_EMPTY: tuple[str, ...] = (
    "cancer/cancer-types/breast",
    "cancer/cancer-types/head-and-neck",
    "cancer/cancer-types/multiple-myeloma",
    "cancer/cancer-types/ovarian",
    "cancer/cancer-types/prostate",
    "cancer/conditions/pre-cancer",
    "cancer/data-sources/cbioportal",
    "cancer/mechanisms/evolution",
    "cancer/meta",
    "cancer/therapeutics",
    "health/comparisons/pan-disease",
    "health/meta",
    "health/processes/immunity",
    "health/processes/post-acute-infection",
    "natural-systems",
    "protein-landscape",
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


def _observation_records(root: Path) -> list[tuple[Path, dict]]:
    """Authored observation records under `root`.

    Unlike `search`, this kind HAS a packaged template, and it declares `kind: "observation"`
    in its own frontmatter -- so the `_template` guard is not decorative here. It is
    nonetheless currently redundant with `_SKIP_DIRS`: checked, and no project root holds a
    copy of `observation.md` outside `.venv/`, where the installed toolkit ships one at
    `site-packages/science_model/templates/observation.md`. Two independent exclusions cover
    it, and `test_the_template_is_not_counted_as_a_record` pins that the guard would still
    do its job if the directory skip ever stopped covering it.
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
        if frontmatter.get("kind") != "observation" or "_template" in frontmatter:
            continue
        found.append((path, frontmatter))
    return found


@pytest.fixture
def strict(monkeypatch) -> EntityValidator:
    monkeypatch.setattr(
        validator_module, "PROJECT_MIXIN_NAMES", PROJECT_MIXIN_NAMES | {"observation"}
    )
    monkeypatch.setattr(loader_module, "TYPE_MIXIN_NAMES", TYPE_MIXIN_NAMES | {"observation"})
    return EntityValidator()


def _project_root(relative: str) -> Path:
    root = Path.home() / "d" / relative
    # Not a skip. This module only runs when `-m real_projects` selects it, so reaching
    # this line IS the explicit request -- and "the 16 available projects passed" must
    # never be able to masquerade as "all 17 passed".
    assert (root / "science.yaml").is_file(), (
        f"expected Science project at {root}; certification cannot be partial"
    )
    return root


def _authored(frontmatter: dict) -> dict:
    return {k: v for k, v in frontmatter.items() if k not in MarkdownAdapter.INJECTED_KEYS}


@pytest.mark.real_projects
@pytest.mark.parametrize("relative", sorted(EXPECTED))
def test_every_authored_observation_satisfies_the_candidate_profile(relative, strict):
    root = _project_root(relative)
    records = _observation_records(root)
    assert len(records) == EXPECTED[relative], (
        f"{relative}: expected {EXPECTED[relative]} observations, found {len(records)}"
    )

    failures: list[str] = []
    for path, frontmatter in records:
        try:
            strict.validate_as(_authored(frontmatter), CANDIDATE)
        except EntityValidationError as exc:
            failures.append(f"{path.relative_to(root)}: {exc}")
    assert not failures, "\n".join(failures)


@pytest.mark.real_projects
@pytest.mark.parametrize("relative", EXPECTED_EMPTY)
def test_no_other_project_root_holds_an_observation(relative):
    """The claim "one project owns the whole corpus", asserted over the other 16 roots.

    Without this, the single row in `EXPECTED` is indistinguishable from an incomplete
    survey -- and every conclusion this slice draws from the corpus's uniformity would rest
    on not having looked. It also fails the day a second project starts authoring this
    kind, which is exactly when the field set needs re-deriving.
    """
    root = _project_root(relative)
    records = _observation_records(root)
    assert not records, (
        f"{relative} now holds {len(records)} observation(s): "
        f"{[str(p.relative_to(root)) for p, _ in records]}. "
        "The single-project premise of this slice's certification no longer holds."
    )


@pytest.mark.real_projects
def test_the_corpus_total_is_the_frozen_21():
    """The per-project counts sum to the inventory's total.

    Cheap, and it catches the failure the per-project assertions cannot: a project dropping
    out of `EXPECTED` entirely. With only one row here that would empty the table, and a
    table with no rows makes `parametrize` collect nothing and report success.
    """
    assert sum(EXPECTED.values()) == CORPUS_TOTAL
    assert EXPECTED, "EXPECTED emptied; parametrized certification would collect zero tests"


@pytest.mark.real_projects
def test_every_project_root_is_accounted_for():
    """`EXPECTED` and `EXPECTED_EMPTY` together must be the whole survey, with no overlap.

    17 roots were enumerated from the four repos on 2026-07-30 by finding every
    `science.yaml`. A root in neither table is a root nobody certified.
    """
    assert not set(EXPECTED) & set(EXPECTED_EMPTY)
    assert len(EXPECTED) + len(EXPECTED_EMPTY) == 17


@pytest.mark.real_projects
def test_the_template_is_not_counted_as_a_record():
    """The `_template` guard, exercised directly rather than trusted.

    The installed toolkit ships `observation.md` under each project's
    `.venv/.../science_model/templates/`, and it declares `kind: "observation"`. Today
    `_SKIP_DIRS` excludes `.venv` before the guard is ever consulted, so this asserts the
    guard on the packaged template itself: were the directory skip to stop covering it, the
    walk would report 22 records and certify a template as a corpus member.
    """
    template = (
        Path(__file__).resolve().parents[2]
        / "science"
        / "model"
        / "src"
        / "science_model"
        / "templates"
        / "observation.md"
    )
    frontmatter = yaml.safe_load(template.read_text(encoding="utf-8").split("---\n", 2)[1])
    assert frontmatter["kind"] == "observation", (
        "the template no longer declares this kind; the guard below is testing nothing"
    )
    assert "_template" in frontmatter


@pytest.mark.real_projects
def test_no_observation_record_carries_a_writer_stamped_key():
    """Certifies the step-3 writer fix against the real files.

    `consolidated_into` and `superseded_by` are both omitted by the mixin, for different
    reasons -- one is archive-tier bookkeeping now stripped on restore, the other is
    refused because `observation` is `supersedable=False`. Asserted by NAME so the reason
    is legible; the profile check above would report either only as an anonymous
    `unevaluatedProperties` refusal.
    """
    offenders: list[str] = []
    for relative in EXPECTED:
        root = _project_root(relative)
        for path, fm in _observation_records(root):
            stamped = sorted(set(fm) & {"consolidated_into", "superseded_by"})
            if stamped:
                offenders.append(f"{path.relative_to(root)}: {stamped}")
    assert not offenders, "\n".join(offenders)


@pytest.mark.real_projects
def test_no_observation_record_authors_an_adapter_injected_key():
    """Why the authored view above equals the frontmatter for this kind.

    `sources.py:434` passes `MarkdownAdapter.INJECTED_KEYS` unconditionally, while every
    other call site passes `INJECTED_KEYS - authored`. So an author who writes `content:`
    in frontmatter has it hidden from the schema rather than judged by it. That blind spot
    is real, is kind-agnostic, is tracked as F1 in the slice procedure, and is out of scope
    here; this assertion pins the fact that no observation record exercises it, so the
    subtraction above is currently a no-op rather than a silent drop.
    """
    offenders: list[str] = []
    for relative in EXPECTED:
        root = _project_root(relative)
        offenders += [
            str(path.relative_to(root))
            for path, fm in _observation_records(root)
            if set(fm) & MarkdownAdapter.INJECTED_KEYS
        ]
    assert not offenders, "\n".join(offenders)


@pytest.mark.real_projects
def test_no_observation_record_authors_profile():
    """The `profile` omission, certified against the corpus that motivated it.

    Zero of 21, and zero of the 539 entity records in this project across all 19 kinds it
    holds -- this project does not use entity profiles at all. Combined with the measured
    fact that `profile` is NOT injected into the validated key set (see the correction in
    the slice inventory), the field is authored or it is nothing, and nothing authors it.
    """
    offenders: list[str] = []
    for relative in EXPECTED:
        root = _project_root(relative)
        offenders += [
            str(path.relative_to(root))
            for path, fm in _observation_records(root)
            if "profile" in fm
        ]
    assert not offenders, "\n".join(offenders)


@pytest.mark.real_projects
def test_the_whole_corpus_is_status_active():
    """The uniformity that makes this corpus unable to certify `status`, pinned as a fact.

    All 21 records are `active`, so every value probe over this corpus passes whether or
    not the schema enum-locks the field -- which is exactly how `mixin-concept-1.0`'s
    premature enum survived its own certification. This kind is the sharpest case in the
    tranche: `method` had one dissenting record to make the trap visible, and with a single
    project root there is not even a second author here who could disagree.

    This test does not defend the ruling (the mixin's probes do); it records the
    measurement the ruling was made against, so that if the corpus ever DOES vary, the
    ruling is revisited deliberately rather than by a probe quietly starting to mean
    something.
    """
    statuses = {
        fm.get("status")
        for relative in EXPECTED
        for _, fm in _observation_records(_project_root(relative))
    }
    assert statuses == {"active"}, (
        f"the observation corpus is no longer uniformly `active` "
        f"({sorted(str(s) for s in statuses)}); "
        "re-read the status ruling in the slice inventory before changing the mixin"
    )


@pytest.mark.real_projects
def test_the_promoted_from_population_is_the_frozen_14():
    """14 of 21, all one value, naming a file that no longer exists.

    The count is frozen because it is the whole justification for admitting the field on
    this kind: there is no live writer (`science entities triage-aggregate --promote-coined`
    was removed) and no template prescribes it, so the records are the only reason.
    """
    values: list[str] = []
    for relative in EXPECTED:
        for _, fm in _observation_records(_project_root(relative)):
            if "promoted_from" in fm:
                values.append(fm["promoted_from"])
    assert len(values) == 14
    assert set(values) == {"doc/observations/observations.yaml"}


@pytest.mark.real_projects
def test_no_project_declares_an_observation_extension():
    """Certification composes base + mixin only, and that must be the whole story.

    The `method` slice found both extensions in its corpus were `hypothesis`-scoped --
    read, not assumed. Checked across ALL 17 roots here, not just the one holding records:
    an extension scoped to this kind anywhere would mean some project's composition differs
    from what this file certifies.
    """
    declared: list[str] = []
    for relative in (*EXPECTED, *EXPECTED_EMPTY):
        schemas = _project_root(relative) / "schemas"
        if not schemas.is_dir():
            continue
        for path in schemas.glob("*.json"):
            if '"observation"' in path.read_text(encoding="utf-8"):
                declared.append(str(path))
    assert not declared, "\n".join(declared)


@pytest.mark.real_projects
def test_the_certification_harness_is_actually_armed(strict):
    """The control. Without it, every assertion above could be passing vacuously.

    An unarmed validator resolves `observation` to `extension-observation-1.0.json`, which
    does not exist -- so the records would not be leniently accepted, they would error. But
    a future refactor could make the lookup fall back rather than raise, and then a green
    run would mean nothing. This pins the two properties arming must have: the mixin is
    reachable, AND composition closes.
    """
    base = {
        "id": "observation:probe",
        "kind": "observation",
        "title": "Probe",
        "status": "active",
        "created": "2026-07-30",
        "updated": "2026-07-30",
    }
    strict.validate_as(base, CANDIDATE)
    with pytest.raises(EntityValidationError):
        strict.validate_as({**base, "shadow_key": "unvouched"}, CANDIDATE)
