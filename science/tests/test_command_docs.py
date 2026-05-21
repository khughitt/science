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


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("path", "expected_strings"),
    [
        (
            "commands/add-hypothesis.md",
            (
                "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
                "${CLAUDE_PLUGIN_ROOT}/docs/proposition-and-evidence-model.md",
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
                "${CLAUDE_PLUGIN_ROOT}/docs/proposition-and-evidence-model.md",
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
                "${CLAUDE_PLUGIN_ROOT}/docs/proposition-and-evidence-model.md",
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
            ("${CLAUDE_PLUGIN_ROOT}/docs/proposition-and-evidence-model.md",),
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


def test_plan_analysis_command_defines_methodology_readiness_workflow() -> None:
    text = _read("commands/plan-analysis.md")

    expected_strings = (
        "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
        "${CLAUDE_PLUGIN_ROOT}/skills/INDEX.md",
        "doc/plans/YYYY-MM-DD-<slug>-analysis-plan.md",
        "type: analysis-plan",
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


def test_plan_analysis_is_integrated_with_neighbor_commands() -> None:
    expected_by_path = {
        "commands/plan-pipeline.md": (
            "/science:plan-analysis",
            "methodological readiness",
            "analysis-plan:<slug>",
        ),
        "commands/pre-register.md": (
            "analysis-plan:<slug>",
            "doc/plans/*-analysis-plan.md",
            "/science:plan-analysis",
        ),
        "commands/status.md": (
            "analysis-plan:<slug>",
            "/science:plan-analysis",
        ),
        "commands/next-steps.md": (
            "analysis-plan:<slug>",
            "doc/plans/*-analysis-plan.md",
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
                "Read `docs/claim-and-evidence-model.md`.",
            ),
        ),
        ("commands/bias-audit.md", ("Follow `references/command-preamble.md`",)),
        (
            "commands/compare-hypotheses.md",
            (
                "Follow `references/command-preamble.md`",
                "Read `docs/claim-and-evidence-model.md`.",
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
                "Read `docs/claim-and-evidence-model.md`.",
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
        ("commands/status.md", ("If present, read `docs/claim-and-evidence-model.md`.",)),
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
                "docs/claim-and-evidence-model.md",
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


def test_bias_audit_templates_emit_report_not_task() -> None:
    for path in ("templates/bias-audit.md", "science/model/src/science_model/templates/bias-audit.md"):
        text = _read(path)
        assert 'id: "report:bias-audit-{{slug}}"' in text
        assert 'type: "report"' in text
        assert 'id: "task:{{slug}}"' not in text
        assert 'type: "task"' not in text


def test_bias_audit_commit_step_is_conditional() -> None:
    text = _read("commands/bias-audit.md")
    assert "Only commit if the user explicitly requested a commit or the session has commit approval." in text
    assert "Otherwise, report the changed files and leave the workspace uncommitted." in text
    assert 'Commit: `git add -A && git commit -m "doc: bias audit <slug>"`' not in text


def test_sketch_model_documents_existing_inquiry_upgrade() -> None:
    text = _read("commands/sketch-model.md")
    expected_strings = (
        "Existing Inquiry Upgrade",
        "doc/inquiries/<slug>.md",
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
