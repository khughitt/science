from __future__ import annotations

import re
import shutil
from posixpath import relpath
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
_PLUGIN_SKILL_PATH_RE = re.compile(r"`?\$\{CLAUDE_PLUGIN_ROOT\}/(skills/[A-Za-z0-9._/-]+\.md)`?")
_PLUGIN_RESOURCE_PATH_RE = re.compile(
    r"`?\$\{CLAUDE_PLUGIN_ROOT\}/"
    r"((?:docs|references|templates)/[A-Za-z0-9._/-]+\.md)`?"
)
_BARE_SKILL_PATH_RE = re.compile(r"`(skills/[A-Za-z0-9._/-]+\.md)`")
_BARE_RESOURCE_PATH_RE = re.compile(r"`((?:docs|references|templates)/[A-Za-z0-9._/-]+\.md)`")
_RELATIVE_MARKDOWN_LINK_RE = re.compile(
    r"\[([^\]]+)\]\((\.\./(?:docs|references|skills|templates)/[^)#]+)"
    r"(#[^)]+)?\)"
)
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


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
                repo_root=repo_root,
                skill_dir=skill_dir,
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
    text = text.replace(
        "`${CLAUDE_PLUGIN_ROOT}/templates/<name>.md`",
        "`references/templates/<name>.md`",
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
    repo_root: Path,
    skill_dir: Path,
    name: str,
    title: str,
    description: str,
    body: str,
    preamble: str,
    role: str,
) -> str:
    rewritten_preamble = preamble.replace("<role>", role)
    rewritten_body = _COMMAND_PREAMBLE_INSTRUCTION_RE.sub("", body)
    rewritten_body = _rewrite_command_toolkit_references(
        rewritten_body,
        repo_root,
        skill_dir,
    )
    rewritten_body = _rewrite_agent_specific_text(rewritten_body)
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


def _rewrite_command_toolkit_references(
    text: str,
    repo_root: Path,
    skill_dir: Path,
) -> str:
    bundled: set[Path] = set()

    def replace_relative_link(match: re.Match[str]) -> str:
        label = match.group(1)
        canonical_path = Path(match.group(2)).relative_to("..")
        anchor = match.group(3) or ""
        if canonical_path.parts[0] == "skills":
            dependency = _methodology_skill_name(repo_root, canonical_path)
            return f"`{label}` guidance from the `{dependency}` skill"
        reference = _bundle_command_resource(
            repo_root,
            skill_dir,
            canonical_path,
            bundled,
        )
        return f"[{label}]({reference}{anchor})"

    def replace_plugin_skill(match: re.Match[str]) -> str:
        dependency = _methodology_skill_name(repo_root, Path(match.group(1)))
        return f"the `{dependency}` skill"

    def replace_bare_skill(match: re.Match[str]) -> str:
        canonical_path = Path(match.group(1))
        if canonical_path == Path("skills/INDEX.md"):
            return "the `science-command-preamble` skill's `references/methodology-index.md`"
        dependency = _methodology_skill_name(repo_root, canonical_path)
        return f"the `{dependency}` skill"

    def replace_plugin_resource(match: re.Match[str]) -> str:
        reference = _bundle_command_resource(
            repo_root,
            skill_dir,
            Path(match.group(1)),
            bundled,
        )
        return f"`{reference}`"

    def replace_bare_resource(match: re.Match[str]) -> str:
        reference = _bundle_command_resource(
            repo_root,
            skill_dir,
            Path(match.group(1)),
            bundled,
        )
        return f"`{reference}`"

    text = _BARE_RESOURCE_PATH_RE.sub(replace_bare_resource, text)
    text = text.replace(
        "`${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md`",
        "the Science Command Preamble above",
    )
    text = text.replace(
        "`${CLAUDE_PLUGIN_ROOT}/skills/INDEX.md`",
        "the `science-command-preamble` skill's `references/methodology-index.md`",
    )
    text = _RELATIVE_MARKDOWN_LINK_RE.sub(replace_relative_link, text)
    text = _PLUGIN_SKILL_PATH_RE.sub(replace_plugin_skill, text)
    text = _BARE_SKILL_PATH_RE.sub(replace_bare_skill, text)
    return _PLUGIN_RESOURCE_PATH_RE.sub(replace_plugin_resource, text)


def _methodology_skill_name(repo_root: Path, canonical_path: Path) -> str:
    if canonical_path == Path("skills/writing/scientific-writing.md"):
        return "science-scientific-writing"
    if len(canonical_path.parts) < 3 or canonical_path.parts[0] != "skills":
        raise ValueError(f"canonical skill reference has no generated owner: {canonical_path}")

    router = repo_root / "skills" / canonical_path.parts[1] / "SKILL.md"
    if not router.is_file():
        raise ValueError(f"canonical skill reference has no generated owner: {canonical_path}")
    match = re.search(
        r"^name:\s*['\"]?([^'\"\n]+)['\"]?\s*$",
        router.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if match is None:
        raise ValueError(f"generated methodology router is missing a name: {router}")
    return f"science-{match.group(1)}"


def _bundle_command_resource(
    repo_root: Path,
    skill_dir: Path,
    canonical_path: Path,
    bundled: set[Path],
) -> str:
    source = (repo_root / canonical_path).resolve()
    try:
        relative = source.relative_to(repo_root)
    except ValueError as error:
        raise ValueError(f"command resource escapes Science toolkit root: {canonical_path}") from error
    if relative.parts[0] == "skills":
        raise ValueError(f"canonical skill resource must be a sibling-skill load: {relative}")
    if not source.is_file():
        raise ValueError(f"command resource is not a file: {source}")

    reference = Path("references") / relative
    if relative in bundled:
        return reference.as_posix()
    bundled.add(relative)

    target = skill_dir / reference
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix != ".md":
        shutil.copy2(source, target)
        return reference.as_posix()

    text = source.read_text(encoding="utf-8")
    text = _rewrite_bundled_resource_links(
        text,
        source,
        relative,
        repo_root,
        skill_dir,
        bundled,
    )
    target.write_text(text, encoding="utf-8")
    return reference.as_posix()


def _rewrite_bundled_resource_links(
    text: str,
    source: Path,
    source_relative: Path,
    repo_root: Path,
    skill_dir: Path,
    bundled: set[Path],
) -> str:
    source_target = skill_dir / "references" / source_relative

    def replace_link(match: re.Match[str]) -> str:
        label, raw_target = match.groups()
        target_path, separator, anchor = raw_target.partition("#")
        if not target_path or target_path.startswith("/") or "://" in target_path or target_path.startswith("mailto:"):
            return match.group(0)

        candidate = (source.parent / target_path).resolve()
        try:
            relative = candidate.relative_to(repo_root)
        except ValueError:
            return label
        if not candidate.is_file():
            return label
        if relative.parts[0] == "skills":
            dependency = _methodology_skill_name(repo_root, relative)
            return f"`{label}` guidance from the `{dependency}` skill"

        _bundle_command_resource(
            repo_root,
            skill_dir,
            relative,
            bundled,
        )
        target = skill_dir / "references" / relative
        rewritten = relpath(target, start=source_target.parent)
        if separator:
            rewritten = f"{rewritten}#{anchor}"
        return f"[{label}]({rewritten})"

    return _MARKDOWN_LINK_RE.sub(replace_link, text)


def _rewrite_agent_specific_text(text: str) -> str:
    replacements = (
        ("`${CLAUDE_PLUGIN_ROOT}`", "the Science toolkit"),
        ("${CLAUDE_PLUGIN_ROOT}", "the Science toolkit"),
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
