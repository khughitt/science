"""Enumerate the registry, classify/project each project, and assemble the coverage report."""

from __future__ import annotations

import os
from pathlib import Path

from science_model.data_products import load_catalog
from science_model.frontmatter import project_config_path
from science_model.skill_coverage import EnrollmentStatus, build_skill_overlay
from science_model.skill_coverage.coverage import (
    CoverageReport,
    ProjectEvidence,
    ReportScope,
    SkippedProject,
    compute_coverage,
)

from science_tool.graph.skill_inventory import load_skill_inventory
from science_tool.graph.sources import load_project_sources
from science_tool.project_config import domain_enrollment, load_project_config
from science_tool.registry.config import load_global_config
from science_tool.skills_coverage.evidence import SkillCoverageScanError, project_evidence

# v1 ships exactly the molecular-measurement domain (GENERATION_3_DOMAINS).
COVERAGE_DOMAIN = "molecular-measurement"


def scan_portfolio(
    config_path: Path | None = None, *, only: str | None = None
) -> CoverageReport:
    config = load_global_config(config_path)
    projects = list(config.projects)
    if not projects:
        raise SkillCoverageScanError("no registered projects (empty or absent registry)")

    if only is not None:
        projects = [rp for rp in projects if (rp.id or rp.name) == only]
        if not projects:
            raise SkillCoverageScanError(f"--project {only!r} matched no registered project")

    catalog = load_catalog()
    overlay = build_skill_overlay(load_skill_inventory(), catalog)

    skipped: list[SkippedProject] = []
    selected: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for rp in projects:
        identifier = rp.id or rp.name
        root = Path(rp.path).expanduser()
        if not root.exists() or not project_config_path(root).is_file():
            skipped.append(SkippedProject(str(rp.path), "path missing or no science.yaml"))
            continue
        if identifier in seen:
            raise SkillCoverageScanError(
                f"duplicate project identifier {identifier!r} in the registry"
            )
        seen.add(identifier)
        selected.append((identifier, root))

    evidences: list[ProjectEvidence] = []
    for identifier, root in selected:
        try:
            project_config = load_project_config(root)
        except Exception as exc:  # present-but-invalid config -> abort (never reclassify)
            raise SkillCoverageScanError(f"{identifier}: invalid science.yaml: {exc}") from exc
        status = domain_enrollment(project_config, COVERAGE_DOMAIN)
        if status == EnrollmentStatus.ENROLLED:
            try:
                sources = load_project_sources(root, include_commons=True)
            except Exception as exc:
                raise SkillCoverageScanError(
                    f"{identifier}: sources failed to load: {exc}"
                ) from exc
            evidences.append(project_evidence(identifier, sources))
        else:
            evidences.append(ProjectEvidence(identifier, status))

    scope = (
        ReportScope("single-project", only)
        if only is not None
        else ReportScope("portfolio")
    )
    return compute_coverage(
        evidences,
        overlay,
        catalog,
        scope=scope,
        skipped_projects=tuple(sorted(skipped, key=lambda s: s.path)),
    )


def write_report_atomically(path: Path, text: str) -> None:
    # Serialize-then-replace: a plain write_text truncates before it can fail on I/O, which would
    # leave a stale report half-overwritten. os.replace onto the target is atomic on the same fs.
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
