from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

TOOL_MANIFEST_SNIPPET = """```toml
[project]
name = "<project-slug>-sciences"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[dependency-groups]
dev = []
```"""

USER_GUIDE_DOC = "docs/" + "user-guide.md"
PROJECT_ORGANIZATION_DOC = "docs/" + "project-organization-profiles.md"
PROJECT_WORKING_MODEL_DOC = "docs/conventions/" + "project-working-model-" + "h00.md"
PROJECT_WORKING_MODEL_STEM = "project-working-model-" + "h00"
PROPOSITION_MODEL_DOC = "docs/" + "proposition-and-evidence-model.md"
CLAIM_MODEL_DOC = "docs/" + "claim-and-evidence-model.md"


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_catalog_datasets_setup_is_layout_v3_aware() -> None:
    text = _read("commands/catalog-datasets.md")

    assert "entities/questions/" in text
    assert "entities/hypotheses/" in text
    assert "legacy specs/research-question.md only if it exists" in text
    assert "legacy specs/scope-boundaries.md only if it exists" in text
    assert "- `specs/research-question.md`" not in text
    assert "- `specs/scope-boundaries.md`" not in text


def test_catalog_datasets_connect_warns_about_legacy_metadata_backfill() -> None:
    text = _read("commands/catalog-datasets.md")

    assert "When connecting or backfilling legacy dataset entities" in text
    assert "do not add `origin: external` by itself" in text
    assert "set `license:` at the same time" in text
    assert "`unknown` is acceptable" in text
    assert "source_class: derived" in text
    assert "dataset_usage" in text
    assert "role: \"upstream\"" in text
    assert "role: \"training\"" in text


def test_task_command_docs_use_aspects_for_task_creation() -> None:
    for path in ("commands/tasks.md", "commands/review-tasks.md"):
        text = _read(path)

        assert "tasks add \"<title>\" --type" not in text
        assert "tasks add \"<title>\" --aspects=<aspect>" in text


def test_task_command_docs_allow_task_scoped_aspects_without_project_declaration() -> None:
    text = _read("commands/tasks.md")

    assert "Task-scoped aspects do not need to be declared in `science.yaml`" in text
    assert "project-wide aspect behavior" in text


def test_plan_analysis_guides_blocker_tasks_to_reuse_task_scoped_aspects() -> None:
    text = _read("commands/plan-analysis.md")

    assert "Reuse task-scoped aspects" in text
    assert "do not mutate `science.yaml` solely to create blocker tasks" in text


def test_graph_docs_explain_local_only_build_for_composite_noise_control() -> None:
    user_guide = _read("docs/user-guide/graph-and-derived-state.md")
    federation = _read("docs/federation.md")

    for text in (user_guide, federation):
        assert "science graph build --local-only" in text
        assert "leaves `knowledge/composite.trig` untouched" in text


def test_pipeline_audit_process_documents_clean_base_qa_checkpoint_pattern() -> None:
    text = _read("docs/process/pipeline-audit-and-refactor.md")

    expected_strings = (
        "Clean-base QA checkpoint pattern",
        "prepared gene-by-sample matrices",
        "mapped gene-set universes",
        "matrix sample/audit consistency",
        "unique feature IDs",
        "finite values",
        "no all-NA rows",
        "feature-count agreement with the transform audit",
        "gene-set size-filter compliance",
        "complete theme/annotation coverage",
        "release/hash metadata",
    )
    for expected in expected_strings:
        assert expected in text


def test_pipeline_audit_process_documents_result_bundle_validation_modes() -> None:
    text = _read("docs/process/pipeline-audit-and-refactor.md")

    expected_strings = (
        "Result-bundle QA and wiring verification",
        "`qa_all`",
        "direct result-QA smoke checks",
        "existing ignored outputs",
        "dry-run DAG checks",
        "expensive stale downstream recomputation",
        "full recomputation",
        "intentional pipeline refresh",
    )
    for expected in expected_strings:
        assert expected in text


def test_pipeline_audit_process_documents_derived_artifact_freshness_checks() -> None:
    text = _read("docs/process/pipeline-audit-and-refactor.md")

    expected_strings = (
        "Derived-artifact freshness checks",
        "deterministic artifacts committed for review",
        "authored input",
        "regenerates into memory or a temp file",
        "diffs against the checked-in artifact",
        "raw-data QA",
        "downstream result-bundle QA",
    )
    for expected in expected_strings:
        assert expected in text


@pytest.mark.parametrize(
    ("path", "expected_strings"),
    [
        (
            "commands/add-hypothesis.md",
            (
                "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
                "${CLAUDE_PLUGIN_ROOT}/docs/user-guide/epistemic-model.md",
                ".ai/templates/hypothesis.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/hypothesis.md",
            ),
        ),
        (
            "commands/bias-audit.md",
            (
                "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
                ".ai/templates/bias-audit.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/bias-audit.md",
            ),
        ),
        (
            "commands/compare-hypotheses.md",
            (
                "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
                "${CLAUDE_PLUGIN_ROOT}/docs/user-guide/epistemic-model.md",
                ".ai/templates/comparison.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/comparison.md",
            ),
        ),
        (
            "commands/discuss.md",
            (
                "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
                ".ai/templates/discussion.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/discussion.md",
                ".ai/templates/question.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/question.md",
            ),
        ),
        (
            "commands/find-datasets.md",
            (
                "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
                "${CLAUDE_PLUGIN_ROOT}/skills/data/SKILL.md",
                "${CLAUDE_PLUGIN_ROOT}/skills/data/frictionless.md",
                ".ai/templates/dataset.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/dataset.md",
            ),
        ),
        (
            "commands/interpret-results.md",
            (
                "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
                "${CLAUDE_PLUGIN_ROOT}/docs/user-guide/epistemic-model.md",
                "${CLAUDE_PLUGIN_ROOT}/docs/user-guide/evidence-lines.md",
                ".ai/templates/interpretation.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/interpretation.md",
            ),
        ),
        (
            "commands/next-steps.md",
            ("${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",),
        ),
        (
            "commands/pre-register.md",
            (
                "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
                ".ai/templates/pre-registration.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/pre-registration.md",
            ),
        ),
        (
            "commands/research-papers.md",
            (
                "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
                ".ai/templates/paper.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/paper.md",
                ".ai/templates/question.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/question.md",
            ),
        ),
        (
            "commands/research-topic.md",
            (
                "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
                ".ai/templates/background-topic.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/background-topic.md",
                ".ai/templates/question.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/question.md",
            ),
        ),
        (
            "commands/search-literature.md",
            (
                "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
                "${CLAUDE_PLUGIN_ROOT}/skills/data/sources/openalex.md",
                "${CLAUDE_PLUGIN_ROOT}/skills/data/sources/pubmed.md",
                ".ai/templates/paper.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/paper.md",
            ),
        ),
        (
            "commands/status.md",
            ("${CLAUDE_PLUGIN_ROOT}/docs/user-guide/epistemic-model.md",),
        ),
    ],
)
def test_command_docs_use_explicit_framework_resolution(
    path: str,
    expected_strings: tuple[str, ...],
) -> None:
    text = _read(path)
    for expected in expected_strings:
        assert expected in text


def test_command_docs_do_not_reference_retired_user_docs() -> None:
    retired = (
        USER_GUIDE_DOC,
        PROJECT_ORGANIZATION_DOC,
        PROJECT_WORKING_MODEL_DOC,
        PROJECT_WORKING_MODEL_STEM,
        PROPOSITION_MODEL_DOC,
        CLAIM_MODEL_DOC,
    )
    offenders: list[str] = []
    for path in (ROOT / "commands").glob("*.md"):
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in retired):
            offenders.append(path.relative_to(ROOT).as_posix())

    assert not offenders


def test_plan_analysis_command_defines_methodology_readiness_workflow() -> None:
    text = _read("commands/plan-analysis.md")

    expected_strings = (
        "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
        "${CLAUDE_PLUGIN_ROOT}/skills/INDEX.md",
        "entities/plans/<NNNN>-<slug>-analysis-plan.md",
        'type: "plan"',
        'plan_kind: "analysis-plan"',
        "skills_loaded:",
        "Readiness Decision",
        "ready-with-caveats",
        "science feedback add",
        '--target "command:plan-analysis"',
    )
    for expected in expected_strings:
        assert expected in text


def test_plan_analysis_command_covers_pressure_scenarios() -> None:
    text = _read("commands/plan-analysis.md")

    expected_strings = (
        "MM30 scRNA pseudobulk / entropy analysis",
        "cBioPortal targeted-panel mutation frequency or dN/dS analysis",
        "Natural-systems annotation/curation agreement analysis",
        "Protein-landscape heldout benchmark or embedding-manifold analysis",
        "data-expression-scrna-qa",
        "data-genomics-somatic-mutation-qa",
        "research-annotation-curation-qa",
        "data-protein-sequence-structure-qa",
    )
    for expected in expected_strings:
        assert expected in text


def test_plan_analysis_command_routes_proteomics_and_sensor_time_series() -> None:
    text = _read("commands/plan-analysis.md")
    index = _read("skills/INDEX.md")

    expected_strings = (
        "`data-proteomics-qa`: `skills/data/proteomics-qa.md`",
        "`statistics-time-series-and-longitudinal-models`: `skills/statistics/time-series-and-longitudinal-models.md`",
        "Proteomics, phosphoproteomics, mass spectrometry, peptide intensity, TMT, LFQ",
        "`data-proteomics-qa`, `statistics-bias-vs-variance-decomposition`, `statistics-sensitivity-arbitration`",
        "Wearable, behavioral, actigraphy, EMA, symptom diary, sensor time series, sleep/activity rhythms, or cross-lag coupling",
        "`statistics-time-series-and-longitudinal-models`, `statistics-bias-vs-variance-decomposition`, `statistics-power-floor-acknowledgement`, and `statistics-sensitivity-arbitration`",
    )
    for expected in expected_strings[:2]:
        assert expected in index
    for expected in expected_strings[2:]:
        assert expected in text

    assert "statistics-time-series-and-longitudinal-models` if present" not in text


def test_plan_analysis_is_integrated_with_neighbor_commands() -> None:
    expected_by_path = {
        "commands/plan-pipeline.md": (
            "/science:plan-analysis",
            "methodological readiness",
            "plan:<stem>",
        ),
        "commands/pre-register.md": (
            "plan:<stem>",
            "entities/plans/*-analysis-plan.md",
            "/science:plan-analysis",
        ),
        "commands/status.md": (
            "plan:<stem>",
            "/science:plan-analysis",
        ),
        "commands/next-steps.md": (
            "plan:<stem>",
            "entities/plans/*-analysis-plan.md",
            "/science:plan-analysis",
        ),
    }
    for path, expected_strings in expected_by_path.items():
        text = _read(path)
        for expected in expected_strings:
            assert expected in text


def test_needs_review_resolution_docs_cover_amendment_workflow() -> None:
    expected_by_path = {
        "commands/interpret-results.md": (
            "needs-review resolution",
            "sci:amends",
            "sci:supersedes",
            "sci:supersedesClaim",
            "entity review <target-ref>",
            "flagged entity",
            "status: superseded",
        ),
        "commands/next-steps.md": (
            "needs-review",
            "review prompt",
            "sci:amends",
            "sci:supersedes",
        ),
        "commands/status.md": (
            "needs-review",
            "review workflow",
            "sci:amends",
            "sci:supersedes",
        ),
        "commands/big-picture.md": (
            "sci:amends",
            "sci:supersedes",
            "prior_interpretations",
            "not the machine-readable chain",
        ),
        "templates/interpretation.md": (
            "relations:",
            "sci:amends",
            "sci:supersedes",
        ),
        "templates/interpretation-dev.md": (
            "relations:",
            "sci:amends",
            "sci:supersedes",
        ),
        "science/model/src/science_model/templates/interpretation.md": (
            "relations:",
            "sci:amends",
            "sci:supersedes",
        ),
        "science/model/src/science_model/templates/interpretation-dev.md": (
            "relations:",
            "sci:amends",
            "sci:supersedes",
        ),
    }
    for path, expected_strings in expected_by_path.items():
        text = _read(path)
        for expected in expected_strings:
            assert expected in text


@pytest.mark.parametrize(
    ("path", "expected_strings"),
    [
        (
            "commands/create-project.md",
            (
                TOOL_MANIFEST_SNIPPET,
                'uv add --dev --editable "$SCIENCE_TOOL_PATH"',
                "non-Python repos",
            ),
        ),
        (
            "commands/import-project.md",
            (
                TOOL_MANIFEST_SNIPPET,
                'uv add --dev --editable "$SCIENCE_TOOL_PATH"',
                "non-Python repos",
            ),
        ),
        (
            "references/project-structure.md",
            (
                TOOL_MANIFEST_SNIPPET,
                "tool-only manifest",
                "science",
            ),
        ),
        (
            "references/command-preamble.md",
            (
                "uv run science <command>",
                "project-local install",
                "uv add --dev --editable",
            ),
        ),
        (
            "README.md",
            (
                "pyproject.toml",
                "science",
                "project-local tooling",
            ),
        ),
    ],
)
def test_project_bootstrap_docs_cover_science_tool_install_contract(
    path: str,
    expected_strings: tuple[str, ...],
) -> None:
    text = _read(path)
    for expected in expected_strings:
        assert expected in text


@pytest.mark.parametrize("path", ["commands/create-project.md", "commands/import-project.md"])
def test_project_bootstrap_docs_ignore_managed_artifact_update_backups(path: str) -> None:
    text = _read(path)

    assert "*.pre-update*.bak" in text


def test_validate_cli_reference_documents_shim_contract() -> None:
    reference = _read("docs/conventions/validate.md")
    readme = _read("README.md")
    conventions_index = _read("docs/conventions/README.md")

    expected_reference_strings = (
        "# `science validate`",
        "## Synopsis",
        "science validate [--verbose] [--strict] [--format text|json] [--fail-on TIER] [--project-root PATH]",
        "## Flags",
        "--format text|json",
        "--project-root PATH",
        "## Exit Codes",
        "Warnings alone do not fail the command",
        "## Severity Model",
        "`--strict` enables strict advisory warnings; it does not promote `warn` results to `error`.",
        "## JSON Output Schema",
        '"summary": {"errors": 0, "warnings": 1, "infos": 0}',
        '"severity": "warn"',
        '"path": "doc/example.md"',
        '"line": 12',
        '"message": "example warning"',
        '"rule": "example.rule"',
        '"task": "task:t001"',
        "## Environment Variables",
        "NO_COLOR",
        "SCIENCE_VALIDATE_DISABLE_SIDECAR=1",
        "For `science validate`, disables both Python sidecar discovery and deprecated legacy `validate.local.sh` discovery.",
        "## Discovery",
        "`validate.sh` is the managed project artifact shim that delegates to `science validate`.",
        "`validate_local.py` is imported by default when it exists in the project root.",
        "Because `validate.sh` delegates to `science validate`, this environment variable affects validation reached through the shim as well.",
    )
    for expected in expected_reference_strings:
        assert expected in reference

    assert "[`science validate`](docs/conventions/validate.md)" in readme
    assert "Python sidecar hooks" in readme
    assert "experimental Python sidecars" not in readme
    assert "[`validate.md`](validate.md)" in conventions_index


@pytest.mark.parametrize(
    ("path", "legacy_strings"),
    [
        (
            "commands/add-hypothesis.md",
            (
                "Follow `references/command-preamble.md`",
                f"Read `{CLAIM_MODEL_DOC}`.",
            ),
        ),
        ("commands/bias-audit.md", ("Follow `references/command-preamble.md`",)),
        (
            "commands/compare-hypotheses.md",
            (
                "Follow `references/command-preamble.md`",
                f"Read `{CLAIM_MODEL_DOC}`.",
            ),
        ),
        ("commands/discuss.md", ("Follow `references/command-preamble.md`", "Read `templates/discussion.md`")),
        (
            "commands/find-datasets.md",
            (
                "Follow `references/command-preamble.md`",
                "Read `skills/data/SKILL.md` for data management conventions.",
                "If present, read `skills/data/frictionless.md` for Data Package guidance.",
            ),
        ),
        (
            "commands/interpret-results.md",
            (
                "Follow `references/command-preamble.md`",
                f"Read `{CLAIM_MODEL_DOC}`.",
            ),
        ),
        ("commands/next-steps.md", ("Follow `references/command-preamble.md`",)),
        (
            "commands/pre-register.md",
            ("Follow `references/command-preamble.md`", "Read `templates/pre-registration.md`"),
        ),
        ("commands/research-papers.md", ("Follow `references/command-preamble.md`", "Read `templates/paper.md`")),
        (
            "commands/research-topic.md",
            ("Follow `references/command-preamble.md`", "Read `templates/background-topic.md`"),
        ),
        (
            "commands/search-literature.md",
            (
                "Follow `references/command-preamble.md`",
                "Read `skills/data/sources/openalex.md`.",
                "Read `skills/data/sources/pubmed.md`.",
            ),
        ),
        ("commands/status.md", (f"If present, read `{CLAIM_MODEL_DOC}`.",)),
    ],
)
def test_command_docs_remove_project_local_framework_paths(path: str, legacy_strings: tuple[str, ...]) -> None:
    text = _read(path)
    for legacy in legacy_strings:
        assert legacy not in text


@pytest.mark.parametrize(
    ("path", "legacy_strings"),
    [
        (
            "README.md",
            (
                "claims and relation-claims are the main units of belief",
                CLAIM_MODEL_DOC,
            ),
        ),
        (
            "commands/interpret-results.md",
            (
                "claim-centric way",
                "`relation_claim`",
                "claim updates",
            ),
        ),
        (
            "commands/add-hypothesis.md",
            (
                "the concrete `claim` or `relation_claim` units that would actually be tested",
                "relation_claim`s",
                "claim bundle",
            ),
        ),
        (
            "commands/compare-hypotheses.md",
            (
                "Claim-Centric Evidence Inventory",
                "relation-claims",
                "claim bundle",
            ),
        ),
    ],
)
def test_command_docs_remove_claim_centric_terminology(
    path: str,
    legacy_strings: tuple[str, ...],
) -> None:
    text = _read(path)
    for legacy in legacy_strings:
        assert legacy not in text


def test_command_docs_do_not_reference_legacy_relation_claim_commands() -> None:
    forbidden_strings = (
        "`relation_claim`",
        "relation_claim:",
        "relation-claim",
        "science graph add claim",
        "science graph add relation-claim",
        "graph claim surfaces",
        "Claim And Graph Uncertainty",
    )
    offenders: list[str] = []
    for path in sorted((ROOT / "commands").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for forbidden in forbidden_strings:
            if forbidden in text:
                offenders.append(f"{path.relative_to(ROOT)} contains {forbidden!r}")
    assert not offenders


def test_entity_creation_cookbook_covers_positive_and_negative_examples() -> None:
    text = _read("docs/process/entity-creation-cookbook.md")

    for expected in (
        "gene",
        "protein",
        "family",
        "complex",
        "disease",
        "drug",
        "cell type",
        "phenotype",
        "pathway",
        "histone mark",
        "mechanism",
        "prose-only note",
        "what not to create",
        "concept:high-proliferation-rate",
    ):
        assert expected in text


def test_tasks_command_documents_flat_ids_parent_and_namespace_refs() -> None:
    text = _read("commands/tasks.md")

    expected_strings = (
        "Task IDs are flat local identifiers in the form `tNNN`",
        "`parent: task:t001`",
        "`natural-systems:task:t335`",
        "Bare `t123` always means a local task",
        "`tasks/archive.md` is for historical task aliases",
    )
    for expected in expected_strings:
        assert expected in text


def test_federation_docs_document_canonical_entity_refs_and_artifact_addresses() -> None:
    text = _read("docs/federation.md")

    expected_strings = (
        "<project-id>:<kind>:<slug>",
        "`cbioportal:question:q014`",
        "`multiple-myeloma:hypothesis:h003`",
        "`cbioportal:topics/clonal-hematopoiesis-contamination` is an artifact address",
        "Two-part entity shorthand such as",
        "`cbioportal:q014`",
        "is legacy and non-canonical",
    )
    for expected in expected_strings:
        assert expected in text


def test_comparison_template_satisfies_validator_sections() -> None:
    """Both comparison template copies must carry every section the validator requires.

    Regression for fb-2026-06-02-002 / fb-2026-06-11-001: the template emitted
    'Current Assessment' while hypothesis_comparisons requires 'Current Verdict'.
    """
    from science_tool.validate.checks.hypothesis_comparisons import _SECTIONS

    for path in ("templates/comparison.md", "science/model/src/science_model/templates/comparison.md"):
        text = _read(path)
        for section in _SECTIONS:
            assert f"## {section}" in text, f"{path} missing required section: {section}"


def test_comparison_template_satisfies_discussion_schema_and_numeric_path() -> None:
    """Comparison docs are discussion entities, so the template must satisfy the
    discussion section schema and use the numeric discussion id/path shape."""
    from science_tool.validate.checks.discussions import _REQUIRED_SECTIONS

    for path in ("templates/comparison.md", "science/model/src/science_model/templates/comparison.md"):
        text = _read(path)
        assert 'id: "discussion:{{NNNN}}-{{slug}}"' in text
        assert 'id: "discussion:{{slug}}"' not in text
        for section in _REQUIRED_SECTIONS:
            assert section in text, f"{path} missing required discussion section: {section}"


def test_compare_hypotheses_command_uses_numeric_discussion_output() -> None:
    text = _read("commands/compare-hypotheses.md")

    assert "Save to `entities/discussions/<NNNN>-comparison-<slug>.md`" in text
    assert 'frontmatter `id: "discussion:<NNNN>-comparison-<slug>"`' in text
    assert "entities/discussions/comparison-<slug>.md" not in text


def test_bias_audit_templates_emit_report_not_task() -> None:
    for path in ("templates/bias-audit.md", "science/model/src/science_model/templates/bias-audit.md"):
        text = _read(path)
        assert 'id: "report:{{NNNN}}-bias-audit-{{slug}}"' in text
        assert 'type: "report"' in text
        assert 'id: "task:{{slug}}"' not in text
        assert 'type: "task"' not in text


def test_big_picture_synthesis_frontmatter_includes_profile_required_title() -> None:
    command = _read("commands/big-picture.md")
    assert (
        "Frontmatter: emit `type: synthesis` + `title: \"Synthesis: <hyp-id>\"` + "
        "`report_kind: hypothesis-synthesis`"
    ) in command
    assert (
        "Frontmatter: emit `type: synthesis` + `title: \"Emergent threads - <project name>\"` + "
        "`report_kind: emergent-threads`"
    ) in command
    assert 'title: "Project synthesis - <project name>"' in command

    for path in ("templates/synthesis.md", "science/model/src/science_model/templates/synthesis.md"):
        text = _read(path)
        assert 'title: "{{title}}"' in text


def test_bias_audit_commit_step_is_conditional() -> None:
    text = _read("commands/bias-audit.md")
    assert "Only commit if the user explicitly requested a commit or the session has commit approval." in text
    assert "Otherwise, report the changed files and leave the workspace uncommitted." in text
    assert 'Commit: `git add -A && git commit -m "doc: bias audit <slug>"`' not in text


def test_sketch_model_documents_existing_inquiry_upgrade() -> None:
    text = _read("commands/sketch-model.md")
    expected_strings = (
        "Existing Inquiry Upgrade",
        "entities/inquiries/<slug>.md",
        "preserve its existing slug and frontmatter",
        "Register the existing inquiry before adding graph nodes or edges",
    )
    for expected in expected_strings:
        assert expected in text


def test_critique_approach_documents_pre_dag_mode() -> None:
    text = _read("commands/critique-approach.md")
    expected_strings = (
        "Pre-DAG Critique Mode",
        "Markdown-only or sketch-stage inquiry",
        "Validation unavailable",
        "Do not claim formal adjustment-set review",
        "pre-DAG critique",
    )
    for expected in expected_strings:
        assert expected in text
