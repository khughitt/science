from __future__ import annotations

import re
import shutil
from collections.abc import Iterable
from pathlib import Path
from typing import NamedTuple

COMMAND_PREAMBLE_HEADING = "## Science Codex Command Preamble"


class CompanionSkill(NamedTuple):
    canonical_name: str
    source_path: Path


COMPANION_SKILLS: tuple[CompanionSkill, ...] = (
    CompanionSkill("research-methodology", Path("skills/research/SKILL.md")),
    CompanionSkill("scientific-writing", Path("skills/writing/SKILL.md")),
)


def command_to_skill_name(command_path: Path) -> str:
    return f"science-{command_path.stem}"


def companion_to_skill_name(canonical_name: str) -> str:
    return f"science-{canonical_name}"


def generate_codex_skills(repo_root: Path, output_root: Path) -> dict[str, Path]:
    command_preamble = _load_command_preamble(repo_root)
    output_root.mkdir(parents=True, exist_ok=True)

    generated: dict[str, Path] = {}
    command_paths = sorted((repo_root / "commands").glob("*.md"))
    for command_path in command_paths:
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

    for companion in COMPANION_SKILLS:
        skill_name = companion_to_skill_name(companion.canonical_name)
        skill_path = _generate_companion_skill(repo_root, output_root, companion)
        generated[skill_name] = skill_path

    _write_index(output_root, command_paths, COMPANION_SKILLS)

    return generated


def _load_command_preamble(repo_root: Path) -> str:
    text = (repo_root / "references" / "command-preamble.md").read_text(encoding="utf-8").strip()
    text = re.sub(r"^#\s+Command Preamble\n\n", "", text)
    text = _rewrite_claude_specific_text(text)
    return _rewrite_companion_skill_references(text)


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


def _parse_skill(skill_path: Path) -> tuple[str, str, str]:
    text = skill_path.read_text(encoding="utf-8")
    frontmatter_match = re.match(r"^---\n(.*?)\n---\n\n?", text, re.DOTALL)
    if frontmatter_match is None:
        msg = f"Skill file is missing frontmatter: {skill_path}"
        raise ValueError(msg)

    frontmatter = frontmatter_match.group(1)
    name_match = re.search(r"^name:\s*(.+)$", frontmatter, re.MULTILINE)
    if name_match is None:
        msg = f"Skill file is missing name: {skill_path}"
        raise ValueError(msg)

    description_match = re.search(r"^description:\s*(.+)$", frontmatter, re.MULTILINE)
    if description_match is None:
        msg = f"Skill file is missing description: {skill_path}"
        raise ValueError(msg)

    body = text[frontmatter_match.end() :].strip()
    return name_match.group(1).strip(), _unquote_yaml_scalar(description_match.group(1).strip()), body


def _unquote_yaml_scalar(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


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

    escaped_description = description.replace('"', '\\"')
    header = [
        "---",
        f"name: {skill_name}",
        f'description: "{escaped_description}"',
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


def _generate_companion_skill(repo_root: Path, output_root: Path, companion: CompanionSkill) -> Path:
    source_path = repo_root / companion.source_path
    source_name, description, body = _parse_skill(source_path)
    if source_name != companion.canonical_name:
        msg = f"Companion skill name mismatch: expected {companion.canonical_name}, got {source_name} in {source_path}"
        raise ValueError(msg)

    skill_name = companion_to_skill_name(companion.canonical_name)
    skill_dir = output_root / skill_name
    if skill_dir.exists():
        shutil.rmtree(skill_dir)
    skill_dir.mkdir(parents=True, exist_ok=True)

    for resource_path in sorted(source_path.parent.glob("*.md")):
        if resource_path.name == "SKILL.md":
            continue
        shutil.copy2(resource_path, skill_dir / resource_path.name)

    escaped_description = description.replace('"', '\\"')
    body = _rewrite_companion_body_links(body)
    skill_text = "\n".join(
        [
            "---",
            f"name: {skill_name}",
            f'description: "{escaped_description}"',
            "---",
            "",
            _insert_adapted_note(body, companion.source_path),
            "",
        ]
    )
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(skill_text, encoding="utf-8")
    return skill_path


def _rewrite_companion_body_links(body: str) -> str:
    companion_parent_to_skill_name = {
        companion.source_path.parent.name: companion_to_skill_name(companion.canonical_name)
        for companion in COMPANION_SKILLS
    }

    def replace_skill_link(match: re.Match[str]) -> str:
        source_parent = match.group(1)
        if source_parent in companion_parent_to_skill_name:
            return f"../{companion_parent_to_skill_name[source_parent]}/SKILL.md"
        return f"../../skills/{source_parent}/SKILL.md"

    return re.sub(r"\.\./([a-z0-9-]+)/SKILL\.md", replace_skill_link, body)


def _insert_adapted_note(body: str, source_path: Path) -> str:
    note = f"Adapted from canonical Science skill `{source_path.as_posix()}`."
    return re.sub(r"^(#\s+.+\n\n)", rf"\1{note}\n\n", body, count=1)


def _write_index(output_root: Path, command_paths: list[Path], companion_skills: tuple[CompanionSkill, ...]) -> None:
    lines = [
        "# Science Codex Skills",
        "",
        "Generated by `scripts/generate_codex_skills.py`.",
        "",
        "## Command Skills",
        "",
        "| Command | Codex skill | Generated path | Source path |",
        "|---|---|---|---|",
    ]
    for command_path in command_paths:
        command_name = command_path.stem
        skill_name = command_to_skill_name(command_path)
        lines.append(
            f"| `{command_name}` | `{skill_name}` | `{skill_name}/SKILL.md` | `commands/{command_path.name}` |"
        )

    lines.extend(
        [
            "",
            "## Companion Skills",
            "",
            "| Canonical skill | Codex skill | Generated path | Source path |",
            "|---|---|---|---|",
        ]
    )
    for companion in companion_skills:
        skill_name = companion_to_skill_name(companion.canonical_name)
        lines.append(
            f"| `{companion.canonical_name}` | `{skill_name}` | `{skill_name}/SKILL.md` | "
            f"`{companion.source_path.as_posix()}` |"
        )

    (output_root / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _rewrite_companion_skill_references(text: str) -> str:
    text = text.replace(
        "Load the `research-methodology` and `scientific-writing` skills.",
        "Load the `science-research-methodology` and `science-scientific-writing` Codex skills. "
        "If native skill loading is unavailable, use `codex-skills/INDEX.md` to map canonical "
        "Science skill names to generated skill files and source paths.",
    )
    text = text.replace(
        "Load the `research-methodology` skill for evidence standards",
        "Load the `science-research-methodology` Codex skill for evidence standards",
    )
    text = text.replace(
        "Load the `research-methodology` skill",
        "Load the `science-research-methodology` Codex skill",
    )
    return text


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
        ("${CLAUDE_PLUGIN_ROOT}/science", "<science-plugin-root>/science"),
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
    text = _rewrite_companion_skill_references(text)
    return text
