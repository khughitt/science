from __future__ import annotations

from pathlib import Path

from science_tool.codex_skills import command_to_skill_name, generate_codex_skills

ROOT = Path(__file__).resolve().parents[2]


def _read_skill(name: str) -> str:
    return (ROOT / "codex-skills" / name / "SKILL.md").read_text(encoding="utf-8")


def test_command_to_skill_name_uses_science_namespace() -> None:
    assert command_to_skill_name(Path("commands/status.md")) == "science-status"
    assert command_to_skill_name(Path("commands/research-topic.md")) == "science-research-topic"


def test_generate_codex_skills_rewrites_claude_specific_references(tmp_path: Path) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    status_skill = generated["science-status"]
    text = status_skill.read_text(encoding="utf-8")

    assert "name: science-status" in text
    assert "Converted from Claude command `/science:status`." in text
    assert "## Science Codex Command Preamble" in text
    assert "science-sync" in text
    assert "/science:sync" not in text
    assert "${CLAUDE_PLUGIN_ROOT}" not in text
    assert "If the user explicitly asks to save the output or includes `--save`" in text
    assert "project-local install path: `uv run science-tool <command>`" in text
    assert "`uv run --with <science-plugin-root>/science-tool science-tool <command>`" in text


def test_generate_codex_skills_rewrites_arguments_and_template_paths(tmp_path: Path) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    topic_skill = generated["science-research-topic"]
    text = topic_skill.read_text(encoding="utf-8")

    assert "Write a structured background synthesis on the topic specified by the user." in text
    assert "Follow the Science Codex Command Preamble before executing this skill." in text
    assert "templates/background-topic.md" in text
    assert ".ai/templates/background-topic.md" in text
    assert "science-tool feedback add" in text
    assert "$ARGUMENTS" not in text


def test_generate_codex_skills_emits_all_commands(tmp_path: Path) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)

    command_count = len(list((ROOT / "commands").glob("*.md")))
    assert len(generated) == command_count
    assert len(list(tmp_path.glob("science-*/SKILL.md"))) == command_count


def test_plan_analysis_generated_skill_mentions_index_and_readiness() -> None:
    text = _read_skill("science-plan-analysis")

    expected_strings = (
        "name: science-plan-analysis",
        "skills/INDEX.md",
        "doc/plans/YYYY-MM-DD-<slug>-analysis-plan.md",
        "Readiness Decision",
        "science-tool feedback add",
    )
    for expected in expected_strings:
        assert expected in text


def test_science_health_mentions_identity_policy_triage() -> None:
    text = _read_skill("science-health")

    assert "docs/process/entity-creation-cookbook.md" in text
    assert "external-id requirement" in text
    assert "prose-only fallback" in text


def test_create_graph_points_to_cookbook_for_new_entities() -> None:
    text = _read_skill("science-create-graph")

    assert "docs/process/entity-creation-cookbook.md" in text
    assert "check shared kinds" in text
    assert "local `concept:*`" in text


def test_update_graph_mentions_fix_on_touch_for_legacy_entities() -> None:
    text = _read_skill("science-update-graph")

    assert "fix-on-touch" in text
    assert "safe rename/xref addition" in text


def test_sync_mentions_scope_and_collision_warnings() -> None:
    text = _read_skill("science-sync")

    assert "`scope: shared`" in text
    assert "`scope: project`" in text
    assert "primary_external_id collision" in text


# ---------------------------------------------------------------------------
# Smoke tests: generated skills must not inject @core/*.md
# ---------------------------------------------------------------------------

# Phrases that appeared verbatim in the old (pre-Task-2/3) injection guidance.
# Presence of any of these means the generator picked up stale source content.
_INJECTION_PHRASES = (
    "include `@core/overview.md` and `@core/decisions.md` near the top",
    "include @core/overview.md and @core/decisions.md",
)

CODEX_SKILLS_ROOT = ROOT / "codex-skills"


def test_no_generated_skill_has_at_core_injection_guidance() -> None:
    """Generated skills must not instruct agents to insert @core/* includes.

    Prose references to @core/*.md that explain what to *remove* are fine.
    Only positive injection instructions (the old pattern) are forbidden.
    """
    if not CODEX_SKILLS_ROOT.is_dir():
        return  # Repo checkout without generated artifacts; skip silently.
    offenders: list[str] = []
    for skill_md in CODEX_SKILLS_ROOT.rglob("SKILL.md"):
        text = skill_md.read_text(encoding="utf-8")
        if any(phrase in text for phrase in _INJECTION_PHRASES):
            offenders.append(str(skill_md.relative_to(ROOT)))
    assert not offenders, (
        "Generated codex-skills must not instruct agents to insert @core/*.md includes. "
        "Regenerate via scripts/generate_codex_skills.py after editing commands/. "
        f"Offenders: {offenders}"
    )


def test_agents_md_template_has_no_at_core_includes() -> None:
    """The canonical AGENTS.md template must not contain @core/ include directives."""
    template = ROOT / "templates" / "agents-md.md"
    text = template.read_text(encoding="utf-8")
    assert "@core/overview.md" not in text
    assert "@core/decisions.md" not in text
