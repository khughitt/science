"""Typed schema for science.yaml. Non-breaking: extra fields are allowed."""

from __future__ import annotations

import difflib
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.functional_validators import BeforeValidator

from science_model.frontmatter import parse_frontmatter, project_config_path
from science_model.skill_coverage import DOMAIN_KEYS, GENERATION_3_DOMAINS, EnrollmentStatus
from science_tool.data_policy import DataPolicy, DEFAULT_DATA_POLICY
from science_tool.datasets.semantics import OrdinalReproClass


class ProjectRole(StrEnum):
    META = "meta"
    CANCER_TYPE = "cancer-type"
    DATA_SOURCE = "data-source"
    MECHANISM = "mechanism"
    CONDITION = "condition"
    STANDALONE = "standalone"


def _coerce_role(value: Any) -> Any:
    """Accept known enum values or free-form strings."""
    if value is None:
        return ProjectRole.STANDALONE
    if isinstance(value, ProjectRole):
        return value
    if isinstance(value, str):
        try:
            return ProjectRole(value)
        except ValueError:
            return value
    raise TypeError(f"role must be string, got {type(value).__name__}")


RoleField = Annotated[ProjectRole | str, BeforeValidator(_coerce_role)]


class PeerEntry(BaseModel):
    """Declares another project this one references.

    `id` must match the peer project's own self-declared `id:` (validated by
    `validate_peers()` at use time, not at parse time, so configs with
    transient inconsistencies still load).

    `path` is a local filesystem path. Three accepted shapes:
      - absolute (`/...`)
      - `~`-anchored (`~/d/...`)
      - relative to this project's root (`../mm30`)

    Reserved fields (`git`, `repo`, `url`, `doi`, `ref`, `version`) are
    accepted at parse time (extra="allow") but flagged by `validate_peers()`
    until their respective specs ship. See project-peers design Decision 2.
    """

    model_config = ConfigDict(extra="allow")

    id: str
    path: str


DEFAULT_ANCHOR_PATTERNS: list[str] = [
    "task:",
    "pipeline/",
    r"\[@",
    "data/",
    "scripts/",
]

DEFAULT_SPEC_CLASS_KINDS: list[str] = ["pre-registration", "plan"]
DEFAULT_PROVENANCE_FIELDS: list[str] = ["source_refs", "task_links", "input"]

# numeric-verification (Part B) artifact-read caps, forwarded to
# `resolve_artifact`/`read_scalar` via `run_numeric_verification`.
DEFAULT_MAX_JSON_BYTES: int = 50 * 1024 * 1024
DEFAULT_MAX_FEATHER_BYTES: int = 256 * 1024 * 1024


class ProseLintConfig(BaseModel):
    """Configuration for `science prose lint`."""

    model_config = ConfigDict(extra="forbid")

    enabled_checks: list[str] | None = None
    anchor_patterns: list[str] = Field(default_factory=lambda: list(DEFAULT_ANCHOR_PATTERNS))
    # Additive vocabulary merged on top of whatever `anchor_patterns` resolves to.
    # Unlike `anchor_patterns` (a full-override escape hatch), this always applies,
    # so shared vocabulary reaches projects that have overridden anchor_patterns.
    additional_anchor_patterns: list[str] = Field(default_factory=list)
    spec_class_kinds: list[str] = Field(default_factory=lambda: list(DEFAULT_SPEC_CLASS_KINDS))
    provenance_fields: list[str] = Field(default_factory=lambda: list(DEFAULT_PROVENANCE_FIELDS))
    exclude_paths: list[str] = Field(default_factory=list)
    short_form_ids_deny: list[str] = Field(default_factory=list)
    bare_author_year_deny: list[str] = Field(default_factory=list)
    max_json_bytes: int = DEFAULT_MAX_JSON_BYTES
    max_feather_bytes: int = DEFAULT_MAX_FEATHER_BYTES


class EntityIndexSource(StrEnum):
    """Truth source for `science refs check --include-body` entity-ref validation."""

    FRONTMATTER = "frontmatter"
    KNOWLEDGE_GRAPH = "knowledge_graph"


# Directories whose DOI/PMID identifiers are NOT citations requiring a
# bibliography entry. `entities/papers` notes are corpus contributors (they
# declare DOIs), and `doc/searches` are literature-discovery logs full of
# candidate identifiers the project has surveyed but not adopted. All are exempt
# from the DOI/PMID broken-ref check by default; a project may override via
# `refs.doi_pmid_exempt_dirs`.
DEFAULT_DOI_PMID_EXEMPT_DIRS: tuple[str, ...] = (
    "doc/searches",
    "entities/papers",
    "entities/searches",
)


class RefsConfig(BaseModel):
    """Configuration for `science refs check`."""

    model_config = ConfigDict(extra="forbid")

    entity_index_source: EntityIndexSource = EntityIndexSource.FRONTMATTER
    scan_roots: list[str] = Field(default_factory=list)
    doi_pmid_exempt_dirs: list[str] = Field(default_factory=lambda: list(DEFAULT_DOI_PMID_EXEMPT_DIRS))


class DataPolicyConfig(BaseModel):
    """Per-project override of the data-tracking policy (`science data audit`)."""

    model_config = ConfigDict(extra="forbid")

    record_patterns: list[str] = Field(default_factory=lambda: list(DEFAULT_DATA_POLICY.record_patterns))
    payload_extensions: list[str] = Field(default_factory=lambda: list(DEFAULT_DATA_POLICY.payload_extensions))
    size_threshold: int = DEFAULT_DATA_POLICY.size_threshold

    def to_policy(self) -> DataPolicy:
        return DataPolicy(
            record_patterns=tuple(self.record_patterns),
            payload_extensions=tuple(self.payload_extensions),
            size_threshold=self.size_threshold,
        )


class ProjectDataConfig(BaseModel):
    """Per-project bulk-data root configuration."""

    model_config = ConfigDict(extra="forbid")

    root: Path | None = None


class ReproducibilityPolicyConfig(BaseModel):
    """Project reproducibility gate policy (science.yaml)."""

    model_config = ConfigDict(extra="forbid")

    bar: OrdinalReproClass = "third-party-reproducible"
    unknown: Literal["halt", "warn"] = "halt"
    below_bar: Literal["halt", "warn"] = "halt"


class ReproducibilityWaiver(BaseModel):
    """A dated, scoped plan-level acceptance of one below-bar dataset."""

    model_config = ConfigDict(extra="forbid")

    dataset: str
    accepted_class: OrdinalReproClass
    decision_date: str = ""
    rationale: str = ""
    mitigation: str = ""


class PlanReproducibilityPolicy(BaseModel):
    """Plan-frontmatter reproducibility_policy: bar override + waivers."""

    model_config = ConfigDict(extra="forbid")

    bar: OrdinalReproClass | None = None
    unknown: Literal["halt", "warn"] | None = None
    below_bar: Literal["halt", "warn"] | None = None
    waivers: list[ReproducibilityWaiver] = Field(default_factory=list)


def effective_reproducibility_policy(
    project: ReproducibilityPolicyConfig | None,
    plan: PlanReproducibilityPolicy | None,
) -> ReproducibilityPolicyConfig | None:
    """Merge plan policy over project policy. Returns None only when BOTH are absent."""
    if project is None and plan is None:
        return None
    base = project or ReproducibilityPolicyConfig()
    if plan is None:
        return base
    return ReproducibilityPolicyConfig(
        bar=plan.bar or base.bar,
        unknown=plan.unknown or base.unknown,
        below_bar=plan.below_bar or base.below_bar,
    )


def load_plan_reproducibility_policy(plan_path: Path) -> PlanReproducibilityPolicy | None:
    """Parse a plan file's frontmatter `reproducibility_policy` into a model, or None."""
    result = parse_frontmatter(plan_path)
    if result is None:
        return None
    fm, _ = result
    raw = fm.get("reproducibility_policy")
    if not isinstance(raw, dict):
        return None
    return PlanReproducibilityPolicy.model_validate(raw)


class SkillCoverageConfig(BaseModel):
    """The `skill_coverage:` block of science.yaml -- a CLOSED enrollment declaration.

    `domains` maps a closed domain key to its enrollment STATUS as the value. `domains` is REQUIRED:
    a block present without it is malformed, not an empty declaration -- an intentionally empty block
    is `{domains: {}}`. Absence of a KEY within `domains` means `undeclared` for that domain, never
    `out-of-domain` (an explicit value a project must author). The block is closed (`extra="forbid"`):
    the only key inside it is `domains`.
    """

    model_config = ConfigDict(extra="forbid")

    domains: dict[str, EnrollmentStatus]

    @field_validator("domains")
    @classmethod
    def _known_domains(cls, value: dict[str, EnrollmentStatus]) -> dict[str, EnrollmentStatus]:
        unknown = sorted(set(value) - DOMAIN_KEYS)
        if unknown:
            raise ValueError(
                f"skill_coverage.domains has unknown domain key(s) {unknown!r}; "
                f"known domains: {sorted(DOMAIN_KEYS)}. An unknown domain is refused rather than "
                "preserved: a misnamed domain would silently drop a project out of coverage."
            )
        return value


class ProjectConfig(BaseModel):
    """Typed view of science.yaml. Non-listed fields are preserved as-is."""

    model_config = ConfigDict(extra="allow")

    name: str
    id: str | None = None
    role: RoleField = ProjectRole.STANDALONE
    peers: list[PeerEntry] = Field(default_factory=list)
    prose_lint: ProseLintConfig | None = None
    refs: RefsConfig | None = None
    data: ProjectDataConfig | None = None
    data_policy: DataPolicyConfig | None = None
    reproducibility_policy: ReproducibilityPolicyConfig | None = None
    skill_coverage: SkillCoverageConfig | None = None
    entity_extensions: dict[str, list[str]] = Field(default_factory=dict)
    # The project's ENTITY SCHEMA generation. Absent means 1 -- unmigrated -- and that is the only
    # thing absence may mean: this is an AUTHORED DECLARATION of which version a project is on, never
    # an inference from its files. Nothing guesses; a project says.
    #
    # DECLARED, not merely tolerated, so the VALUE is checked: the vocabulary is closed to the
    # versions that EXIST, and an unconstrained `int` would make `4` a silent no-op the day someone
    # types it.
    #
    # Declaring the field does NOT, on its own, catch a MISSPELLED one -- `extra="allow"` carries
    # `entity_schema_verison: 2` into `model_extra`, preserved and ignored, leaving the project
    # silently unmigrated while its author believes otherwise. That is what `_reject_near_miss_keys`
    # below is for. A pin nobody can typo is the whole value of "a project says".
    entity_schema_version: Literal[1, 2, 3] | None = None

    @model_validator(mode="before")
    @classmethod
    def _reject_removed_fields(cls, raw: Any) -> Any:
        if isinstance(raw, dict):
            illegal = [k for k in ("parent", "children") if k in raw]
            if illegal:
                raise ValueError(
                    f"science.yaml uses removed field(s) {illegal!r}. "
                    "Use `peers:` instead; `parent:` and `children:` are removed project-config fields."
                )
        return raw

    @model_validator(mode="before")
    @classmethod
    def _reject_null_skill_coverage(cls, raw: Any) -> Any:
        if isinstance(raw, dict) and "skill_coverage" in raw and raw["skill_coverage"] is None:
            raise ValueError(
                "science.yaml: skill_coverage is present but null. An authored-but-empty declaration "
                "is `skill_coverage: {domains: {}}`, not null -- null would collapse to the same state "
                "as absence (undeclared), hiding a malformed declaration."
            )
        return raw

    @model_validator(mode="before")
    @classmethod
    def _reject_near_miss_keys(cls, raw: Any) -> Any:
        reject_near_miss_keys(raw)
        return raw

    @model_validator(mode="after")
    def _enrolled_requires_generation_3(self) -> ProjectConfig:
        coverage = self.skill_coverage
        if coverage is None:
            return self
        needs_generation_3 = sorted(
            domain
            for domain, status in coverage.domains.items()
            if status is EnrollmentStatus.ENROLLED and domain in GENERATION_3_DOMAINS
        )
        if needs_generation_3 and self.entity_schema_version != 3:
            raise ValueError(
                f"skill_coverage: domain(s) {needs_generation_3!r} are enrolled but require "
                f"entity_schema_version: 3 (currently {self.entity_schema_version!r}). Coverage reads "
                "the generation-3 capability shape, so enrolling without the gen-3 pin is refused "
                "rather than run against a shape the project does not speak."
            )
        return self


def reject_near_miss_keys(raw: Any) -> None:
    """A key that ALMOST names a declared field is a typo, and `extra="allow"` would keep it.

    `extra="allow"` is deliberate: science.yaml carries project-owned keys this model has no opinion
    about (`summary`, `tags`, `aspects`, `layout_version`, ...), and preserving them is the point.
    But that same permissiveness turns `entity_schema_verison: 2` into a key that is accepted,
    preserved, and ignored -- leaving a project silently on schema 1 while its author believes it
    migrated, which is precisely the fail-silent this arc exists to close. A pin nobody can typo is
    what "nothing guesses; a project says" actually costs.

    Near-miss, not unknown: an unknown key is legal by design, so only keys that are one plausible
    slip away from a DECLARED field are refused.

    ☠️ MODULE-LEVEL, and not a private validator, because the pin is read on TWO paths and only one
    of them can afford full `ProjectConfig` validation. The graph loader cannot: `name` is required,
    and demanding it of every graph build is a real tightening that is not this arc's. So the loader
    calls THIS, on the raw dict, and gets the typo guard without the rest. A near-miss pin must FAIL
    on both paths -- degrading it to "unpinned" is the fail-open, wearing the pin's own clothes.
    """
    if not isinstance(raw, dict):
        return
    declared = sorted(ProjectConfig.model_fields)
    for key in raw:
        if not isinstance(key, str) or key in ProjectConfig.model_fields:
            continue
        near = difflib.get_close_matches(key, declared, n=1, cutoff=0.85)
        if near:
            raise ValueError(
                f"science.yaml: unknown key {key!r} -- did you mean {near[0]!r}? "
                "A near-miss key is refused rather than preserved: silently ignoring it would "
                "leave the project unconfigured while its author believed otherwise."
            )


_LEGAL_ENTITY_SCHEMA_VERSIONS: frozenset[int] = frozenset({1, 2, 3})


def validated_entity_schema_version(raw: Any) -> int | None:
    """The pin's value, checked against the closed vocabulary, WITHOUT full ``ProjectConfig``.

    ☠️ THE ONE AUTHORITY BOTH PATHS READ THE PIN THROUGH. The graph loader and the write boundary
    each ask "does this project speak schema 2?" -- and a `2` that armed the writer but not the
    loader, or the reverse, is two answers to one question. The loader cannot afford full
    ``ProjectConfig`` (it requires `name`, and demanding that of every graph build is a tightening
    that is not this arc's), so BOTH call this, on the raw dict.

    It validates the KEY (near-miss, via ``reject_near_miss_keys``) and the VALUE. A present pin must
    be a version that EXISTS: `"2"` (a quoted string), `4`, `1.0`, `True`, or an explicit `null` is
    REFUSED, not silently read as "unpinned". That degrade-to-unpinned was the fail-open -- the load
    path enforced nothing while the write path raised on the very same file.

    ☠️ ABSENCE is the ONLY thing that means "unpinned" -- so the test is KEY PRESENCE, never
    ``raw.get()``, which cannot tell a missing key from an authored `entity_schema_version: null`.
    And the value must be a strict ``int``: `type(value) is int` rejects `bool` (`type(True) is int` is
    ``False``) AND `float`, which plain membership would wave through because `1.0 == 1` and
    `1.0 in {1, 2, 3}` is ``True``. A present-but-wrong value is a project to FIX, never one silently
    read as unmigrated.

    Returns the version (1, 2, or 3) for a legal pin, or ``None`` when the pin is ABSENT.
    """
    reject_near_miss_keys(raw)
    if not isinstance(raw, dict):
        return None
    if "entity_schema_version" not in raw:
        return None  # ABSENCE, and only absence, is "unpinned"
    value = raw["entity_schema_version"]
    if type(value) is not int or value not in _LEGAL_ENTITY_SCHEMA_VERSIONS:
        raise ValueError(
            f"science.yaml: entity_schema_version must be 1, 2, or 3 (an integer), not {value!r}. "
            "A present pin with an illegal value is refused rather than read as 'unpinned' -- that "
            "silent degrade let the loader skip schema validation while the writer rejected the file."
        )
    return value


def load_project_config(project_root: Path) -> ProjectConfig:
    """Load and validate science.yaml at ``project_root``. Defaults id to dirname."""
    yaml_path = project_config_path(project_root)
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    if "id" not in raw or raw["id"] is None:
        raw["id"] = project_root.resolve().name
    return ProjectConfig.model_validate(raw)


def domain_enrollment(
    config: ProjectConfig, domain: str
) -> EnrollmentStatus | Literal["undeclared"]:
    """Resolve a project's enrollment status for one coverage domain.

    Absence of the `skill_coverage` block, or of this domain key within it, is `undeclared` -- never
    `out-of-domain`, which a project must author explicitly. A `domain` outside the closed vocabulary
    is a programming error at the call site, not a project state, so it raises rather than returning
    `undeclared`.
    """
    if domain not in DOMAIN_KEYS:
        raise ValueError(
            f"unknown skill-coverage domain {domain!r}; known domains: {sorted(DOMAIN_KEYS)}"
        )
    if config.skill_coverage is None:
        return "undeclared"
    status = config.skill_coverage.domains.get(domain)
    if status is None:
        return "undeclared"
    return status


def resolve_data_policy(config: ProjectConfig) -> DataPolicy:
    """Return the effective DataPolicy: the project override or the framework default."""
    if config.data_policy is not None:
        return config.data_policy.to_policy()
    return DEFAULT_DATA_POLICY


def paths_equivalent(a: Path, b: Path) -> bool:
    """Compare two paths after symlink resolution."""
    try:
        return a.expanduser().resolve() == b.expanduser().resolve()
    except OSError:
        return False
