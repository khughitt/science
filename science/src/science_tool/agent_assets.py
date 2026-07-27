from __future__ import annotations

import re
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

COMMAND_PREAMBLE_HEADING = "## Science Command Preamble"
COMMAND_SUPPORT_SKILL = "science-command-preamble"
COMMAND_ROLE_RE = re.compile(
    r"Follow `(?:\$\{CLAUDE_PLUGIN_ROOT\}/)?references/command-preamble\.md`"
    r"(?:\s+\(role:\s*|\s+with role\s+)`?"
    r"(research-assistant|discussant)`?",
    re.MULTILINE,
)
_EXPLICIT_COMMAND_ROLE_RE = re.compile(
    r"Follow `(?:\$\{CLAUDE_PLUGIN_ROOT\}/)?references/command-preamble\.md`"
    r"(?:\s+\(role:\s*|\s+with role\s+)`?([^`\s)]+)`?",
    re.MULTILINE,
)
_COMMAND_PREAMBLE_INSTRUCTION_RE = re.compile(
    r"^(?:>\s*-\s*)?Follow "
    r"`(?:\$\{CLAUDE_PLUGIN_ROOT\}/)?references/command-preamble\.md`"
    r"[^\n]*(?:\n`?(?:research-assistant|discussant)`?[^\n]*)?\n?",
    re.MULTILINE,
)


@dataclass(frozen=True)
class GenerationResult:
    skill_paths: Mapping[str, Path]
    opencode_command_paths: Mapping[str, Path]


def validate_repo_root(candidate: Path) -> Path:
    root = candidate.expanduser().resolve()
    sentinels = (
        root / "commands",
        root / "skills" / "INDEX.md",
        root / "references" / "command-preamble.md",
        root / "aspects",
    )
    if not (sentinels[0].is_dir() and sentinels[1].is_file() and sentinels[2].is_file() and sentinels[3].is_dir()):
        raise ValueError(f"not a Science toolkit root: {root}")
    return root


def generate_agent_assets(
    repo_root: Path,
    skills_output_root: Path,
    opencode_commands_output_root: Path,
) -> GenerationResult:
    repo_root = validate_repo_root(repo_root)
    _validate_output_root(
        repo_root / "skills",
        skills_output_root,
        repo_root / "skills" / "generated",
    )
    _validate_output_root(
        repo_root / "commands",
        opencode_commands_output_root,
        repo_root / "commands" / "opencode",
    )
    command_paths = sorted((repo_root / "commands").glob("*.md"))
    skills_output_root.mkdir(parents=True, exist_ok=True)
    opencode_commands_output_root.mkdir(parents=True, exist_ok=True)

    skill_paths = _generate_command_skills(
        repo_root,
        skills_output_root,
        command_paths,
    )
    skill_paths[COMMAND_SUPPORT_SKILL] = _generate_command_support_skill(
        repo_root,
        skills_output_root,
    )
    return GenerationResult(
        skill_paths=skill_paths,
        opencode_command_paths={},
    )


def command_to_skill_name(command_path: Path) -> str:
    return f"science-{command_path.stem}"


def _validate_output_root(
    canonical_root: Path,
    output_root: Path,
    committed_root: Path,
) -> None:
    resolved = output_root.resolve()
    if resolved == committed_root.resolve():
        return
    try:
        resolved.relative_to(canonical_root.resolve())
    except ValueError:
        return
    raise ValueError(f"generated output inside canonical source tree: {resolved}")


def _generate_command_skills(
    repo_root: Path,
    output_root: Path,
    command_paths: list[Path],
) -> dict[str, Path]:
    preamble = _load_command_preamble(repo_root)
    generated = {}
    for command_path in command_paths:
        name = command_to_skill_name(command_path)
        title, description, body = _parse_command(command_path)
        role = _command_role(body)
        skill_dir = output_root / name
        _replace_generated_directory(skill_dir)
        skill_path = skill_dir / "SKILL.md"
        skill_path.write_text(
            _render_command_skill(
                name=name,
                title=title,
                description=description,
                body=body,
                preamble=preamble,
                role=role,
            ),
            encoding="utf-8",
        )
        generated[name] = skill_path
    return generated


def _load_command_preamble(repo_root: Path) -> str:
    text = (repo_root / "references" / "command-preamble.md").read_text(encoding="utf-8").strip()
    text = re.sub(r"^#\s+Command Preamble\n\n", "", text)
    text = re.sub(
        r"^2\. Load role prompt:.*$",
        (
            "2. Load the `science-command-preamble` skill. Use its\n"
            "   `references/role-prompts/<role>.md` role prompt and its aspect definitions."
        ),
        text,
        flags=re.MULTILINE,
    )
    text = text.replace(
        "Load the `scientific-writing` skill.",
        "Load the `science-scientific-writing` skill.",
    )
    text = text.replace(
        "`${CLAUDE_PLUGIN_ROOT}/skills/INDEX.md`",
        ("the `science-command-preamble` skill's `references/methodology-index.md`"),
    )
    text = text.replace(
        "and load the leaves relevant to the task",
        "and load the relevant generated methodology router skills",
    )
    text = text.replace(
        "`${CLAUDE_PLUGIN_ROOT}/aspects/<name>/<name>.md`",
        ("the `science-command-preamble` skill's `references/aspects/<name>/<name>.md`"),
    )
    text = text.replace(
        "`${CLAUDE_PLUGIN_ROOT}/aspects/`",
        "the `science-command-preamble` skill's `references/aspects/`",
    )
    return _rewrite_agent_specific_text(text)


def _parse_command(command_path: Path) -> tuple[str, str, str]:
    text = command_path.read_text(encoding="utf-8")
    frontmatter_match = re.match(r"^---\n(.*?)\n---\n\n?", text, re.DOTALL)
    if frontmatter_match is None:
        raise ValueError(f"Command file is missing frontmatter: {command_path}")

    frontmatter = frontmatter_match.group(1)
    description_match = re.search(
        r"^description:\s*(.+)$",
        frontmatter,
        re.MULTILINE,
    )
    if description_match is None:
        raise ValueError(f"Command file is missing description: {command_path}")

    body = text[frontmatter_match.end() :].strip()
    title_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    if title_match is None:
        raise ValueError(f"Command file is missing a top-level heading: {command_path}")

    return title_match.group(1).strip(), description_match.group(1).strip(), body


def _command_role(body: str) -> str:
    match = COMMAND_ROLE_RE.search(body)
    if match is not None:
        return match.group(1)

    explicit = _EXPLICIT_COMMAND_ROLE_RE.search(body)
    if explicit is not None:
        raise ValueError(f"unsupported Science command role: {explicit.group(1)}")
    return "research-assistant"


def _render_command_skill(
    *,
    name: str,
    title: str,
    description: str,
    body: str,
    preamble: str,
    role: str,
) -> str:
    rewritten_preamble = preamble.replace("<role>", role)
    rewritten_body = _COMMAND_PREAMBLE_INSTRUCTION_RE.sub("", body)
    rewritten_body = _rewrite_agent_specific_text(rewritten_body)
    rewritten_body = _rebase_command_body_links(rewritten_body)
    rewritten_body = re.sub(r"^#\s+.+\n\n", "", rewritten_body)

    escaped_description = description.replace('"', '\\"')
    header = [
        "---",
        f"name: {name}",
        f'description: "{escaped_description}"',
        "user-invocable: true",
        "---",
        "",
    ]
    sections = [
        f"# {title}",
        "",
        COMMAND_PREAMBLE_HEADING,
        "",
        rewritten_preamble,
        "",
        rewritten_body,
        "",
    ]
    return "\n".join(header + sections)


def _rewrite_agent_specific_text(text: str) -> str:
    replacements = (
        ("${CLAUDE_PLUGIN_ROOT}/science", "<science-toolkit-root>/science"),
        ("${CLAUDE_PLUGIN_ROOT}/", ""),
        ("${CLAUDE_PLUGIN_ROOT}", "<science-toolkit-root>"),
        (
            "Write a structured background synthesis on the topic specified by `$ARGUMENTS`.",
            "Write a structured background synthesis on the topic specified by the user.",
        ),
        (
            "Write a structured paper synthesis for the paper specified by `$ARGUMENTS`.",
            "Write a structured paper synthesis for the paper specified by the user.",
        ),
        (
            "If `$ARGUMENTS` contains `--save`",
            "If the user explicitly asks to save the output or includes `--save`",
        ),
        (
            "The output goes to the terminal unless `$ARGUMENTS` contains `--save`.",
            "The output goes to the terminal unless the user explicitly asks to save it or includes `--save`.",
        ),
        (
            "Output goes to the terminal unless the user input contains `--save`.",
            "Output goes to the terminal unless the user explicitly asks to save it or includes `--save`.",
        ),
        (
            "unless the user input contains `--save`",
            "unless the user explicitly asks to save it or includes `--save`",
        ),
        ("`$ARGUMENTS`", "the user input"),
        ("$ARGUMENTS", "the user input"),
    )
    for source, target in replacements:
        text = text.replace(source, target)
    return re.sub(r"/science:([a-z0-9-]+)", r"science-\1", text)


def _rebase_command_body_links(body: str) -> str:
    return re.sub(r"]\(\.\./", "](../../", body)


def _generate_command_support_skill(repo_root: Path, output_root: Path) -> Path:
    skill_dir = output_root / COMMAND_SUPPORT_SKILL
    _replace_generated_directory(skill_dir)
    _copy_tree(
        repo_root / "references" / "role-prompts",
        skill_dir / "references" / "role-prompts",
    )
    _copy_tree(
        repo_root / "aspects",
        skill_dir / "references" / "aspects",
    )
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            (
                "---",
                f"name: {COMMAND_SUPPORT_SKILL}",
                'description: "Support resources loaded by Science command skills; not invoked directly."',
                "---",
                "",
                "# Science Command Support Resources",
                "",
                "Use the named role prompt, aspect definitions, and methodology index requested by the loading Science command skill.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return skill_dir / "SKILL.md"


def _replace_generated_directory(path: Path) -> None:
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise ValueError(f"generated package path is not a directory: {path}")
    if path.is_dir():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def _copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise ValueError(f"generated resource source is not a directory: {source}")
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
