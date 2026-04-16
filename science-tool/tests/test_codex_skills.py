from __future__ import annotations

from pathlib import Path

from science_tool.codex_skills import command_to_skill_name, generate_codex_skills

ROOT = Path(__file__).resolve().parents[2]


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
