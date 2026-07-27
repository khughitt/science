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
    CompanionSkill("scientific-writing", Path("skills/writing/scientific-writing.md")),
    CompanionSkill("skill-development", Path("skills/meta/SKILL.md")),
)


def command_to_skill_name(command_path: Path) -> str:
    return f"science-{command_path.stem}"


def companion_to_skill_name(canonical_name: str) -> str:
    return f"science-{canonical_name}"


def generate_agent_skills(
    repo_root: Path,
    output_root: Path,
    *,
    agent: str = "codex",
    format: str = "skill",
) -> dict[str, Path]:
    """Generate agent-specific skill files from Science commands and companion skills.

    Args:
        repo_root: Root of the Science toolkit repository
        output_root: Where to write generated skills
        agent: Target agent ("codex", "crush", "opencode")
        format: Output format ("skill" for SKILL.md, "command" for .md commands)

    Returns:
        Dict mapping skill name to generated file path
    """
    command_preamble = _load_command_preamble(repo_root)
    output_root.mkdir(parents=True, exist_ok=True)

    generated: dict[str, Path] = {}

    if format == "skill":
        # Generate skills from commands (SKILL.md format)
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
                agent=agent,
            )
            skill_dir = output_root / skill_name
            skill_dir.mkdir(parents=True, exist_ok=True)
            skill_path = skill_dir / "SKILL.md"
            skill_path.write_text(skill_text, encoding="utf-8")
            generated[skill_name] = skill_path

        # Generate companion skills
        for companion in COMPANION_SKILLS:
            skill_name = companion_to_skill_name(companion.canonical_name)
            skill_path = _generate_companion_skill(repo_root, output_root, companion)
            generated[skill_name] = skill_path

        _write_index(output_root, command_paths, COMPANION_SKILLS, agent)

    elif format == "command":
        # Generate commands (.md files with frontmatter)
        command_paths = sorted((repo_root / "commands").glob("*.md"))
        for command_path in command_paths:
            command_name = command_path.stem
            _, description, body = _parse_command(command_path)
            command_text = _build_command_text(
                command_name=command_name,
                description=description,
                body=body,
                command_preamble=command_preamble,
            )
            command_path_out = output_root / f"{command_name}.md"
            command_path_out.write_text(command_text, encoding="utf-8")
            generated[command_name] = command_path_out

    # Clean up stale files
    if format == "skill":
        generated_dirs = {output_root / name for name in generated}
        for child in output_root.iterdir():
            if child.is_dir() and child.name.startswith("science-") and child not in generated_dirs:
                shutil.rmtree(child)

    return generated


# Backward compatibility
def generate_codex_skills(repo_root: Path, output_root: Path) -> dict[str, Path]:
    """Legacy wrapper for Codex skill generation."""
    return generate_agent_skills(repo_root, output_root, agent="codex", format="skill")


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
    agent: str = "codex",
) -> str:
    rewritten_body = _replace_command_preamble_instructions(body)
    rewritten_body = _rewrite_claude_specific_text(rewritten_body)
    rewritten_body = _rebase_command_body_links(rewritten_body)
    rewritten_body = _replace_command_preamble_instructions(rewritten_body)
    rewritten_body = re.sub(r"^#\s+.+\n\n", "", rewritten_body)

    escaped_description = description.replace('"', '\\"')
    
    # Agent-specific preamble heading
    preamble_heading = {
        "codex": "## Science Codex Command Preamble",
        "crush": "## Science Crush Command Preamble",
        "opencode": "## Science OpenCode Command Preamble",
    }.get(agent, "## Science Command Preamble")
    
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
        preamble_heading,
        "",
        command_preamble,
        "",
        rewritten_body,
        "",
    ]
    return "\n".join(header + sections)


def _build_command_text(
    *,
    command_name: str,
    description: str,
    body: str,
    command_preamble: str,
) -> str:
    """Build OpenCode command format (.md with YAML frontmatter)."""
    rewritten_body = _replace_command_preamble_instructions(body)
    rewritten_body = _rewrite_claude_specific_text(rewritten_body)
    
    # OpenCode uses $ARGUMENTS directly, which matches Claude's format
    # so we don't need to rewrite those
    
    header = [
        "---",
        f"description: {description}",
        "---",
        "",
    ]
    
    sections = [
        rewritten_body,
        "",
    ]
    return "\n".join(header + sections)


def _generate_companion_skill(repo_root: Path, output_root: Path, companion: CompanionSkill, agent: str = "codex") -> Path:
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

    for resource_path in _resource_paths(source_path):
        text = resource_path.read_text(encoding="utf-8")
        (skill_dir / resource_path.name).write_text(
            _rewrite_companion_body_links(text, repo_root), encoding="utf-8"
        )

    templates_dir = source_path.parent / "templates"
    if templates_dir.is_dir():
        shutil.copytree(templates_dir, skill_dir / "templates")

    escaped_description = description.replace('"', '\\"')
    body = _rewrite_companion_body_links(body, repo_root)
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


def _resource_paths(source_path: Path) -> list[Path]:
    """Markdown files bundled as resources beside a companion's SKILL.md.

    Excludes the directory's router (SKILL.md) and the companion's own source
    file, which is emitted as the companion's SKILL.md rather than as a
    resource. This is the single definition of the emitted resource set: the
    copy loop and the link rewriter must agree, or links resolve to files that
    were never copied.
    """
    return [
        path
        for path in sorted(source_path.parent.glob("*.md"))
        if path.name != "SKILL.md" and path != source_path
    ]


def _companion_link_targets(repo_root: Path) -> dict[Path, str]:
    """Map a repo-relative skills/ path to where generation actually emits it."""
    targets: dict[Path, str] = {}
    for companion in COMPANION_SKILLS:
        skill_name = companion_to_skill_name(companion.canonical_name)
        targets[companion.source_path] = f"../{skill_name}/SKILL.md"
        for resource_path in _resource_paths(repo_root / companion.source_path):
            relative = companion.source_path.parent / resource_path.name
            targets[relative] = f"../{skill_name}/{resource_path.name}"
    return targets


def _rewrite_companion_body_links(body: str, repo_root: Path) -> str:
    targets = _companion_link_targets(repo_root)

    def replace_link(match: re.Match[str]) -> str:
        directory, filename = match.group(1), match.group(2)
        emitted = targets.get(Path("skills") / directory / filename)
        if emitted is not None:
            return emitted
        return f"../../skills/{directory}/{filename}"

    return re.sub(r"\.\./([a-z0-9-]+)/([A-Za-z0-9._-]+\.md)", replace_link, body)


def _rebase_command_body_links(body: str) -> str:
    """Re-depth relative links for a command body's generated location.

    Command sources sit at `commands/<name>.md` (depth 1) and are emitted to
    `codex-skills/science-<name>/SKILL.md` (depth 2), so each relative link
    needs one more `../` to reach the same target.
    """
    return re.sub(r"]\(\.\./", "](../../", body)


def _insert_adapted_note(body: str, source_path: Path) -> str:
    note = f"Adapted from canonical Science skill `{source_path.as_posix()}`."
    return re.sub(r"^(#\s+.+\n\n)", rf"\1{note}\n\n", body, count=1)


def _write_index(
    output_root: Path,
    command_paths: list[Path],
    companion_skills: tuple[CompanionSkill, ...],
    agent: str = "codex",
) -> None:
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
    return text.replace(
        "Load the `scientific-writing` skill.",
        "Load the `science-scientific-writing` Codex skill.",
    )


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
        ("${CLAUDE_PLUGIN_ROOT}/skills/INDEX.md", "../../skills/INDEX.md"),
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
