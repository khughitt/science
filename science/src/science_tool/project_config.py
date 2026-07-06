"""Typed schema for science.yaml. Non-breaking: extra fields are allowed."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.functional_validators import BeforeValidator

from science_model.frontmatter import parse_frontmatter
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


class ProseLintConfig(BaseModel):
    """Configuration for `science prose lint`."""

    model_config = ConfigDict(extra="forbid")

    enabled_checks: list[str] | None = None
    anchor_patterns: list[str] = Field(default_factory=lambda: list(DEFAULT_ANCHOR_PATTERNS))
    short_form_ids_deny: list[str] = Field(default_factory=list)
    bare_author_year_deny: list[str] = Field(default_factory=list)


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


class ProjectConfig(BaseModel):
    """Typed view of science.yaml. Non-listed fields are preserved as-is."""

    model_config = ConfigDict(extra="allow")

    name: str
    id: str | None = None
    role: RoleField = ProjectRole.STANDALONE
    peers: list[PeerEntry] = Field(default_factory=list)
    prose_lint: ProseLintConfig | None = None
    refs: RefsConfig | None = None
    data_policy: DataPolicyConfig | None = None
    reproducibility_policy: ReproducibilityPolicyConfig | None = None

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


def load_project_config(project_root: Path) -> ProjectConfig:
    """Load and validate science.yaml at ``project_root``. Defaults id to dirname."""
    yaml_path = project_root / "science.yaml"
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    if "id" not in raw or raw["id"] is None:
        raw["id"] = project_root.resolve().name
    return ProjectConfig.model_validate(raw)


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
