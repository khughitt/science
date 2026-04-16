from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import re


COMMAND_PREAMBLE_HEADING = "## Science Codex Command Preamble"


def command_to_skill_name(command_path: Path) -> str:
    return f"science-{command_path.stem}"


def generate_codex_skills(repo_root: Path, output_root: Path) -> dict[str, Path]:
    command_preamble = _load_command_preamble(repo_root)
    output_root.mkdir(parents=True, exist_ok=True)

    generated: dict[str, Path] = {}
    for command_path in sorted((repo_root / "commands").glob("*.md")):
        skill_name = command_to_skill_name(command_path)
        title, description, body = _parse_command(command_path)
        skill_text = _build_skill_text(
            skill_name=skill_name,
            command_name=command_path.stem,
            title=title,
            description=description,
            body=body,
            command_preamble=command_preamble,
        )
        skill_dir = output_root / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_path = skill_dir / "SKILL.md"
        skill_path.write_text(skill_text, encoding="utf-8")
        generated[skill_name] = skill_path

    return generated


def _load_command_preamble(repo_root: Path) -> str:
    text = (repo_root / "references" / "command-preamble.md").read_text(encoding="utf-8").strip()
    text = re.sub(r"^#\s+Command Preamble\n\n", "", text)
    return _rewrite_claude_specific_text(text)


def _parse_command(command_path: Path) -> tuple[str, str, str]:
    text = command_path.read_text(encoding="utf-8")
    frontmatter_match = re.match(r"^---\n(.*?)\n---\n\n?", text, re.DOTALL)
    if frontmatter_match is None:
        msg = f"Command file is missing frontmatter: {command_path}"
        raise ValueError(msg)

    frontmatter = frontmatter_match.group(1)
    description_match = re.search(r"^description:\s*(.+)$", frontmatter, re.MULTILINE)
    if description_match is None:
        msg = f"Command file is missing description: {command_path}"
        raise ValueError(msg)

    body = text[frontmatter_match.end() :].strip()
    title_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    if title_match is None:
        msg = f"Command file is missing a top-level heading: {command_path}"
        raise ValueError(msg)

    return title_match.group(1).strip(), description_match.group(1).strip(), body


def _build_skill_text(
    *,
    skill_name: str,
    command_name: str,
    title: str,
    description: str,
    body: str,
    command_preamble: str,
) -> str:
    rewritten_body = _replace_command_preamble_instructions(body)
    rewritten_body = _rewrite_claude_specific_text(rewritten_body)
    rewritten_body = _replace_command_preamble_instructions(rewritten_body)
    rewritten_body = re.sub(r"^#\s+.+\n\n", "", rewritten_body)

    header = [
        "---",
        f"name: {skill_name}",
        f"description: {_build_skill_description(description, command_name, skill_name)}",
        "---",
        "",
    ]

    sections = [
        f"# {title}",
        "",
        f"Converted from Claude command `/science:{command_name}`.",
        "",
        COMMAND_PREAMBLE_HEADING,
        "",
        command_preamble,
        "",
        rewritten_body,
        "",
    ]
    return "\n".join(header + sections)


def _build_skill_description(description: str, command_name: str, skill_name: str) -> str:
    escaped = description.replace('"', '\\"')
    trigger = f" Also use when the user explicitly asks for `{skill_name}` or references `/science:{command_name}`."
    return f'"{escaped}{trigger}"'


def _replace_command_preamble_instructions(text: str) -> str:
    replacements = (
        (
            "Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role: `research-assistant`).",
            "Follow the Science Codex Command Preamble before executing this skill. Use the `research-assistant` role prompt.",
        ),
        (
            "Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role: `discussant`).",
            "Follow the Science Codex Command Preamble before executing this skill. Use the `discussant` role prompt.",
        ),
        (
            "Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md`.",
            "Follow the Science Codex Command Preamble before executing this skill.",
        ),
        (
            "Follow `references/command-preamble.md` (role: `research-assistant`).",
            "Follow the Science Codex Command Preamble before executing this skill. Use the `research-assistant` role prompt.",
        ),
        (
            "Follow `references/command-preamble.md` (role: `discussant`).",
            "Follow the Science Codex Command Preamble before executing this skill. Use the `discussant` role prompt.",
        ),
        (
            "Follow `references/command-preamble.md`.",
            "Follow the Science Codex Command Preamble before executing this skill.",
        ),
    )
    for source, target in replacements:
        text = text.replace(source, target)
    return text


def _rewrite_claude_specific_text(text: str) -> str:
    replacements: Iterable[tuple[str, str]] = (
        ("${CLAUDE_PLUGIN_ROOT}/science-tool", "<science-plugin-root>/science-tool"),
        ("${CLAUDE_PLUGIN_ROOT}/", ""),
        ("${CLAUDE_PLUGIN_ROOT}", "<science-plugin-root>"),
        (
            "Write a structured background synthesis on the topic specified by `$ARGUMENTS`.",
            "Write a structured background synthesis on the topic specified by the user.",
        ),
        (
            "Write a structured paper synthesis for the paper specified by `$ARGUMENTS`.",
            "Write a structured paper synthesis for the paper specified by the user.",
        ),
        ("If `$ARGUMENTS` contains `--save`", "If the user explicitly asks to save the output or includes `--save`"),
        (
            "The output goes to the terminal unless `$ARGUMENTS` contains `--save`.",
            "The output goes to the terminal unless the user explicitly asks to save it or includes `--save`.",
        ),
        (
            "Output goes to the terminal unless the user input contains `--save`.",
            "Output goes to the terminal unless the user explicitly asks to save it or includes `--save`.",
        ),
        ("unless the user input contains `--save`", "unless the user explicitly asks to save it or includes `--save`"),
        ("`$ARGUMENTS`", "the user input"),
    )
    for source, target in replacements:
        text = text.replace(source, target)

    text = re.sub(r"/science:([a-z0-9-]+)", r"science-\1", text)
    return text
