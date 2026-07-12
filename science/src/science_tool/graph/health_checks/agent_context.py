"""Agent-context health check: session-start context drift (CLAUDE.md/AGENTS.md/overview)."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from science_tool.graph.health_checks.base import HealthCheck
from science_tool.instruments import InstrumentResult


class AgentContextFinding(TypedDict):
    code: str
    source_file: str
    detail: str
    fix: str


OVERVIEW_LINE_BUDGET = 150
OVERVIEW_WORD_BUDGET = 1200


_AGENT_CONTEXT_FILES = ("AGENTS.md", "CLAUDE.md", "core/overview.md")


def collect_agent_context_findings(project_root: Path) -> InstrumentResult[AgentContextFinding]:
    """Return drift that makes session-start agent context too large or fragmented.

    ``unwired`` when none of the files it inspects exists: every branch below is
    guarded on a file being present, so an absent set yields zero findings without
    the check ever having looked at anything.
    """
    from science_tool.curate.agents_md import collect_agents_md_state

    project_root = project_root.resolve()
    if not any((project_root / name).is_file() for name in _AGENT_CONTEXT_FILES):
        return InstrumentResult.unwired(
            code="agent_context_files_absent",
            reason=f"none of {', '.join(_AGENT_CONTEXT_FILES)} exists; no agent context was inspected",
        )
    state = collect_agents_md_state(project_root)
    findings: list[AgentContextFinding] = []

    for include in state.claude_md_legacy_at_includes:
        findings.append(
            {
                "code": "claude_md_legacy_includes",
                "source_file": "CLAUDE.md",
                "detail": f"CLAUDE.md includes {include}; keep CLAUDE.md to a single @AGENTS.md pointer.",
                "fix": "Move durable guidance into AGENTS.md and keep core files as pointers.",
            }
        )
    if state.claude_md_present and not _claude_md_is_minimal(project_root / "CLAUDE.md"):
        findings.append(
            {
                "code": "claude_md_not_minimal",
                "source_file": "CLAUDE.md",
                "detail": "CLAUDE.md should contain only @AGENTS.md.",
                "fix": "Move project-specific guidance into AGENTS.md, then replace CLAUDE.md with @AGENTS.md.",
            }
        )

    for include in state.agents_md_legacy_at_includes:
        findings.append(
            {
                "code": "agents_md_legacy_includes",
                "source_file": "AGENTS.md",
                "detail": f"AGENTS.md includes {include}; @core/* directives inline large files into every session.",
                "fix": "Remove the @core/* directive and keep core files in the Pointers section.",
            }
        )

    if state.agents_md_present and not state.markers_present:
        findings.append(
            {
                "code": "agents_md_digest_markers_missing",
                "source_file": "AGENTS.md",
                "detail": "AGENTS.md is missing the managed load-bearing-constraints digest markers.",
                "fix": "Run /science:curate or add the canonical managed marker block from templates/agents-md.md.",
            }
        )

    overview = project_root / "core" / "overview.md"
    if overview.is_file():
        text = overview.read_text(encoding="utf-8")
        line_count = len(text.splitlines())
        word_count = len(text.split())
        if line_count > OVERVIEW_LINE_BUDGET or word_count > OVERVIEW_WORD_BUDGET:
            findings.append(
                {
                    "code": "overview_too_long",
                    "source_file": "core/overview.md",
                    "detail": (
                        f"core/overview.md is {line_count} lines / {word_count} words; "
                        f"budget is {OVERVIEW_LINE_BUDGET} lines / {OVERVIEW_WORD_BUDGET} words."
                    ),
                    "fix": "Keep overview as boot context and move detailed evidence narratives into canonical docs.",
                }
            )

    return InstrumentResult.from_rows(findings)


def _claude_md_is_minimal(path: Path) -> bool:
    if not path.is_file():
        return False
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return lines == ["@AGENTS.md"]


CHECK = HealthCheck(
    name="agent_context",
    description="Check CLAUDE.md, AGENTS.md, and core/overview.md for session-context drift.",
    requires_sources=False,
    run=lambda context: collect_agent_context_findings(context.project_root),
    empty=lambda _root: [],
)
