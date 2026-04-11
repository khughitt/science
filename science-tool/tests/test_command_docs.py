from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

TOOL_MANIFEST_SNIPPET = """```toml
[project]
name = "<project-slug>-science-tools"
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
            (
                "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
            ),
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
            "commands/research-paper.md",
            (
                "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
                ".ai/templates/paper-summary.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/paper-summary.md",
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
                ".ai/templates/paper-summary.md",
                "${CLAUDE_PLUGIN_ROOT}/templates/paper-summary.md",
            ),
        ),
        (
            "commands/status.md",
            (
                "${CLAUDE_PLUGIN_ROOT}/docs/proposition-and-evidence-model.md",
            ),
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
                "science-tool",
            ),
        ),
        (
            "references/command-preamble.md",
            (
                "uv run science-tool <command>",
                "project-local install",
                "uv add --dev --editable",
            ),
        ),
        (
            "README.md",
            (
                "pyproject.toml",
                "science-tool",
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
        ("commands/pre-register.md", ("Follow `references/command-preamble.md`", "Read `templates/pre-registration.md`")),
        ("commands/research-paper.md", ("Follow `references/command-preamble.md`", "Read `templates/paper-summary.md`")),
        ("commands/research-topic.md", ("Follow `references/command-preamble.md`", "Read `templates/background-topic.md`")),
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
