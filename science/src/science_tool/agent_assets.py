from __future__ import annotations

import re
import shutil
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from posixpath import relpath

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
_AGENT_COMMAND_RE = re.compile(r"`?/science:([a-z0-9-]+)`?")


@dataclass(frozen=True)
class GenerationResult:
    skill_paths: Mapping[str, Path]
    opencode_command_paths: Mapping[str, Path]


@dataclass(frozen=True)
class MethodologyPackage:
    name: str
    router_source: Path
    owned_sources: tuple[Path, ...]


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
    methodology_packages = _methodology_packages(repo_root)
    _validate_generated_skill_namespace(command_paths, methodology_packages)
    expected_skill_names = {
        *(command_to_skill_name(path) for path in command_paths),
        *(package.name for package in methodology_packages),
        COMMAND_SUPPORT_SKILL,
    }
    expected_adapter_names = {
        command_to_skill_name(path) for path in command_paths
    }
    _prepare_output_roots(
        skills_output_root,
        expected_skill_names,
        opencode_commands_output_root,
        expected_adapter_names,
    )
    skill_owners = _skill_owner_map(methodology_packages, repo_root)
    dependencies: dict[str, set[str]] = {}

    skill_paths = _generate_command_skills(
        repo_root,
        skills_output_root,
        command_paths,
        skill_owners,
        dependencies,
    )
    skill_paths.update(
        _generate_methodology_skills(
            repo_root,
            skills_output_root,
            methodology_packages,
            skill_owners,
            dependencies,
        )
    )
    support_dependencies = dependencies.setdefault(
        COMMAND_SUPPORT_SKILL,
        {package.name for package in methodology_packages},
    )
    skill_paths[COMMAND_SUPPORT_SKILL] = _generate_command_support_skill(
        repo_root,
        skills_output_root,
        tuple(package.name for package in methodology_packages),
        skill_owners,
        support_dependencies,
    )
    _write_distribution_index(
        repo_root,
        skills_output_root,
        command_paths,
        methodology_packages,
    )
    opencode_command_paths = _generate_opencode_adapters(
        command_paths,
        opencode_commands_output_root,
        skill_paths,
        dependencies,
    )
    _validate_dependencies(dependencies, set(skill_paths))
    return GenerationResult(
        skill_paths=skill_paths,
        opencode_command_paths=opencode_command_paths,
    )


def command_to_skill_name(command_path: Path) -> str:
    return f"science-{command_path.stem}"


def _methodology_packages(repo_root: Path) -> tuple[MethodologyPackage, ...]:
    packages = []
    for router in sorted((repo_root / "skills").glob("*/SKILL.md")):
        canonical_name, _, _ = _parse_skill(router)
        owned = tuple(path for path in sorted(router.parent.rglob("*")) if path.is_file())
        if router.parent.name == "writing":
            owned = tuple(path for path in owned if path.name != "scientific-writing.md")
        packages.append(
            MethodologyPackage(
                name=f"science-{canonical_name}",
                router_source=router,
                owned_sources=owned,
            )
        )
    scientific_writing = repo_root / "skills" / "writing" / "scientific-writing.md"
    packages.append(
        MethodologyPackage(
            name="science-scientific-writing",
            router_source=scientific_writing,
            owned_sources=(scientific_writing,),
        )
    )
    _validate_unique_skill_owners(packages, repo_root)
    return tuple(packages)


def _validate_unique_skill_owners(
    packages: Iterable[MethodologyPackage],
    repo_root: Path,
) -> None:
    names: dict[str, Path] = {}
    owners: dict[Path, str] = {}
    canonical_skills = (repo_root / "skills").resolve()
    for package in packages:
        previous_source = names.get(package.name)
        if previous_source is not None:
            raise ValueError(
                "generated skill identity has multiple sources "
                f"for {package.name}: {previous_source}, {package.router_source}"
            )
        names[package.name] = package.router_source
        for source in package.owned_sources:
            resolved = source.resolve()
            try:
                resolved.relative_to(canonical_skills)
            except ValueError:
                continue
            previous_owner = owners.get(resolved)
            if previous_owner is not None:
                raise ValueError(
                    f"canonical skill source has multiple owners for {resolved}: {previous_owner}, {package.name}"
                )
            owners[resolved] = package.name


def _skill_owner_map(
    packages: tuple[MethodologyPackage, ...],
    repo_root: Path,
) -> dict[Path, str]:
    canonical_skills = (repo_root / "skills").resolve()
    owners = {}
    for package in packages:
        for source in package.owned_sources:
            resolved = source.resolve()
            try:
                resolved.relative_to(canonical_skills)
            except ValueError:
                continue
            owners[resolved] = package.name
    return owners


def _validate_dependencies(
    dependencies: Mapping[str, set[str]],
    emitted_names: set[str],
) -> None:
    for owner, targets in sorted(dependencies.items()):
        missing = sorted(targets - emitted_names)
        if missing:
            raise ValueError(f"missing generated skill dependency for {owner}: {missing}")


def _validate_generated_skill_namespace(
    command_paths: list[Path],
    methodology_packages: tuple[MethodologyPackage, ...],
) -> None:
    owners: dict[str, str] = {}

    def add(name: str, source: str) -> None:
        previous = owners.get(name)
        if previous is not None:
            raise ValueError(f"generated skill identity has multiple sources for {name}: {previous}, {source}")
        owners[name] = source

    for command_path in command_paths:
        add(command_to_skill_name(command_path), str(command_path))
    for package in methodology_packages:
        add(package.name, str(package.router_source))
    add(COMMAND_SUPPORT_SKILL, "generated command support package")


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


def _prepare_output_roots(
    skills_output_root: Path,
    expected_skill_names: set[str],
    opencode_commands_output_root: Path,
    expected_adapter_names: set[str],
) -> None:
    _validate_skills_output_entries(skills_output_root)
    _validate_opencode_output_entries(opencode_commands_output_root)
    skills_output_root.mkdir(parents=True, exist_ok=True)
    opencode_commands_output_root.mkdir(parents=True, exist_ok=True)
    for entry in skills_output_root.iterdir():
        if (
            entry.name.startswith("science-")
            and entry.is_dir()
            and entry.name not in expected_skill_names
        ):
            shutil.rmtree(entry)
    for entry in opencode_commands_output_root.iterdir():
        if (
            entry.name.startswith("science-")
            and entry.suffix == ".md"
            and entry.is_file()
            and entry.stem not in expected_adapter_names
        ):
            entry.unlink()


def _validate_skills_output_entries(output_root: Path) -> None:
    if not output_root.exists():
        return
    if not output_root.is_dir():
        raise ValueError(f"generated output root is not a directory: {output_root}")
    for entry in output_root.iterdir():
        declared = (
            entry.name == "INDEX.md"
            and entry.is_file()
            or entry.name.startswith("science-")
            and entry.is_dir()
            and not entry.is_symlink()
        )
        if not declared:
            raise ValueError(f"undeclared generated output file: {entry}")


def _validate_opencode_output_entries(output_root: Path) -> None:
    if not output_root.exists():
        return
    if not output_root.is_dir():
        raise ValueError(f"generated output root is not a directory: {output_root}")
    for entry in output_root.iterdir():
        declared = (
            entry.name.startswith("science-")
            and entry.suffix == ".md"
            and entry.is_file()
            and not entry.is_symlink()
        )
        if not declared:
            raise ValueError(f"undeclared generated output file: {entry}")


def _generate_command_skills(
    repo_root: Path,
    output_root: Path,
    command_paths: list[Path],
    skill_owners: Mapping[Path, str],
    dependencies: dict[str, set[str]],
) -> dict[str, Path]:
    preamble = _load_command_preamble(repo_root)
    generated = {}
    for command_path in command_paths:
        name = command_to_skill_name(command_path)
        dependencies[name] = {
            COMMAND_SUPPORT_SKILL,
            "science-scientific-writing",
        }
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
                skill_owners=skill_owners,
                dependencies=dependencies[name],
            ),
            encoding="utf-8",
        )
        generated[name] = skill_path
    return generated


def _generate_opencode_adapters(
    command_paths: list[Path],
    output_root: Path,
    skill_paths: Mapping[str, Path],
    dependencies: dict[str, set[str]],
) -> dict[str, Path]:
    generated = {}
    for command_path in command_paths:
        name = command_to_skill_name(command_path)
        if name not in skill_paths:
            raise ValueError(
                f"missing generated skill dependency for OpenCode adapter {name}: {name}"
            )
        _, description, _ = _parse_command(command_path)
        path = output_root / f"{name}.md"
        path.write_text(
            _render_opencode_adapter(name, description),
            encoding="utf-8",
        )
        dependencies[f"OpenCode adapter {name}"] = {name}
        generated[name] = path
    return generated


def _render_opencode_adapter(name: str, description: str) -> str:
    return "\n".join(
        (
            "---",
            f"description: {description}",
            "---",
            "",
            f"Load and execute the `{name}` skill using this input:",
            "",
            "$ARGUMENTS",
            "",
        )
    )


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


def _parse_skill(skill_path: Path) -> tuple[str, str, str]:
    text = skill_path.read_text(encoding="utf-8")
    frontmatter_match = re.match(r"^---\n(.*?)\n---\n\n?", text, re.DOTALL)
    if frontmatter_match is None:
        raise ValueError(f"Skill file is missing frontmatter: {skill_path}")

    frontmatter = frontmatter_match.group(1)
    name_match = re.search(r"^name:\s*(.+)$", frontmatter, re.MULTILINE)
    if name_match is None:
        raise ValueError(f"Skill file is missing name: {skill_path}")
    description_match = re.search(
        r"^description:\s*(.+)$",
        frontmatter,
        re.MULTILINE,
    )
    if description_match is None:
        raise ValueError(f"Skill file is missing description: {skill_path}")

    body = text[frontmatter_match.end() :].strip()
    return (
        _unquote_yaml_scalar(name_match.group(1).strip()),
        _unquote_yaml_scalar(description_match.group(1).strip()),
        body,
    )


def _unquote_yaml_scalar(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


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
    skill_owners: Mapping[Path, str],
    dependencies: set[str],
) -> str:
    rewritten_preamble = preamble.replace("<role>", role)
    rewritten_body = _COMMAND_PREAMBLE_INSTRUCTION_RE.sub("", body)
    rewritten_body = _rewrite_command_toolkit_references(
        rewritten_body,
        repo_root,
        skill_dir,
        skill_owners,
        dependencies,
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
    skill_owners: Mapping[Path, str],
    dependencies: set[str],
) -> str:
    bundled: set[Path] = set()

    def replace_relative_link(match: re.Match[str]) -> str:
        label = match.group(1)
        canonical_path = Path(match.group(2)).relative_to("..")
        anchor = match.group(3) or ""
        if canonical_path.parts[0] == "skills":
            dependency = _methodology_skill_name(
                repo_root,
                canonical_path,
                skill_owners,
            )
            dependencies.add(dependency)
            return f"`{label}` guidance from the `{dependency}` skill"
        reference = _bundle_command_resource(
            repo_root,
            skill_dir,
            canonical_path,
            bundled,
            skill_owners,
            dependencies,
        )
        return f"[{label}]({reference}{anchor})"

    def replace_plugin_skill(match: re.Match[str]) -> str:
        dependency = _methodology_skill_name(
            repo_root,
            Path(match.group(1)),
            skill_owners,
        )
        dependencies.add(dependency)
        return f"the `{dependency}` skill"

    def replace_bare_skill(match: re.Match[str]) -> str:
        canonical_path = Path(match.group(1))
        if canonical_path == Path("skills/INDEX.md"):
            return "the `science-command-preamble` skill's `references/methodology-index.md`"
        dependency = _methodology_skill_name(
            repo_root,
            canonical_path,
            skill_owners,
        )
        dependencies.add(dependency)
        return f"the `{dependency}` skill"

    def replace_plugin_resource(match: re.Match[str]) -> str:
        reference = _bundle_command_resource(
            repo_root,
            skill_dir,
            Path(match.group(1)),
            bundled,
            skill_owners,
            dependencies,
        )
        return f"`{reference}`"

    def replace_bare_resource(match: re.Match[str]) -> str:
        reference = _bundle_command_resource(
            repo_root,
            skill_dir,
            Path(match.group(1)),
            bundled,
            skill_owners,
            dependencies,
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


def _methodology_skill_name(
    repo_root: Path,
    canonical_path: Path,
    skill_owners: Mapping[Path, str],
) -> str:
    if len(canonical_path.parts) < 2 or canonical_path.parts[0] != "skills":
        raise ValueError(f"canonical skill reference has no generated owner: {canonical_path}")
    source = (repo_root / canonical_path).resolve()
    owner = skill_owners.get(source)
    if owner is None:
        raise ValueError(f"canonical skill reference has no generated owner: {canonical_path}")
    return owner


def _bundle_command_resource(
    repo_root: Path,
    skill_dir: Path,
    canonical_path: Path,
    bundled: set[Path],
    skill_owners: Mapping[Path, str],
    dependencies: set[str],
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
        skill_owners,
        dependencies,
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
    skill_owners: Mapping[Path, str],
    dependencies: set[str],
) -> str:
    source_target = skill_dir / "references" / source_relative

    def replace_link(match: re.Match[str]) -> str:
        label, raw_target = match.groups()
        target_path, separator, anchor = raw_target.partition("#")
        if not target_path or target_path.startswith("/") or "://" in target_path or target_path.startswith("mailto:"):
            return match.group(0)

        candidate = (source.parent / target_path).resolve()
        unresolved_message = f"unresolved bundled resource link in {source_relative.as_posix()}: {raw_target}"
        try:
            relative = candidate.relative_to(repo_root)
        except ValueError as error:
            raise ValueError(unresolved_message) from error
        if not candidate.is_file():
            raise ValueError(unresolved_message)
        if relative.parts[0] == "skills":
            dependency = _methodology_skill_name(
                repo_root,
                relative,
                skill_owners,
            )
            dependencies.add(dependency)
            return f"`{label}` guidance from the `{dependency}` skill"

        _bundle_command_resource(
            repo_root,
            skill_dir,
            relative,
            bundled,
            skill_owners,
            dependencies,
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


def _generate_methodology_skills(
    repo_root: Path,
    output_root: Path,
    packages: tuple[MethodologyPackage, ...],
    skill_owners: Mapping[Path, str],
    dependencies: dict[str, set[str]],
) -> dict[str, Path]:
    generated = {}
    for package in packages:
        canonical_name, description, body = _parse_skill(package.router_source)
        if package.name != f"science-{canonical_name}":
            raise ValueError(f"generated methodology skill name mismatch: {package.name} != science-{canonical_name}")

        skill_dir = output_root / package.name
        _replace_generated_directory(skill_dir)
        package_dependencies = dependencies.setdefault(package.name, set())
        description = _rewrite_methodology_command_references(
            description,
            package_dependencies,
        )
        source_targets = {
            source.resolve(): _methodology_source_target(
                package,
                source,
                skill_dir,
            )
            for source in package.owned_sources
        }
        bundled: set[Path] = set()

        rewritten_body = _rewrite_methodology_references(
            body,
            package.router_source,
            skill_dir / "SKILL.md",
            skill_dir,
            source_targets,
            repo_root,
            skill_owners,
            package_dependencies,
            bundled,
        )
        escaped_description = description.replace('"', '\\"')
        skill_path = skill_dir / "SKILL.md"
        skill_path.write_text(
            "\n".join(
                (
                    "---",
                    f"name: {package.name}",
                    f'description: "{escaped_description}"',
                    "---",
                    "",
                    rewritten_body,
                    "",
                )
            ),
            encoding="utf-8",
        )

        for source in package.owned_sources:
            if source.resolve() == package.router_source.resolve():
                continue
            target = source_targets[source.resolve()]
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.suffix != ".md":
                shutil.copy2(source, target)
                continue
            target.write_text(
                _rewrite_methodology_references(
                    source.read_text(encoding="utf-8"),
                    source,
                    target,
                    skill_dir,
                    source_targets,
                    repo_root,
                    skill_owners,
                    package_dependencies,
                    bundled,
                ),
                encoding="utf-8",
            )
        generated[package.name] = skill_path
    return generated


def _methodology_source_target(
    package: MethodologyPackage,
    source: Path,
    skill_dir: Path,
) -> Path:
    if source.resolve() == package.router_source.resolve():
        return skill_dir / "SKILL.md"
    relative = source.relative_to(package.router_source.parent)
    return skill_dir / "references" / relative


def _rewrite_methodology_references(
    text: str,
    source: Path,
    emitted_source: Path,
    skill_dir: Path,
    source_targets: Mapping[Path, Path],
    repo_root: Path,
    skill_owners: Mapping[Path, str],
    dependencies: set[str],
    bundled: set[Path],
) -> str:
    def replace_link(match: re.Match[str]) -> str:
        label, raw_target = match.groups()
        target_path, separator, anchor = raw_target.partition("#")
        if not target_path or target_path.startswith("/") or "://" in target_path or target_path.startswith("mailto:"):
            return match.group(0)
        candidate = _resolve_methodology_reference(
            source,
            target_path,
            repo_root,
        )
        rewritten = _methodology_reference_target(
            candidate,
            emitted_source,
            skill_dir,
            source_targets,
            repo_root,
            skill_owners,
            dependencies,
            bundled,
        )
        if rewritten.startswith("Load the "):
            return rewritten
        if separator:
            rewritten = f"{rewritten}#{anchor}"
        return f"[{label}]({rewritten})"

    def replace_backtick(match: re.Match[str]) -> str:
        raw_target = match.group(1)
        candidate = _resolve_methodology_reference(
            source,
            raw_target,
            repo_root,
        )
        if not candidate.is_file():
            return match.group(0)
        target = source_targets.get(candidate)
        if target is not None:
            return f"`{_relative_package_reference(emitted_source, target, skill_dir)}`"
        try:
            relative = candidate.relative_to((repo_root / "skills").resolve())
        except ValueError:
            reference = _bundle_methodology_resource(
                candidate,
                skill_dir,
                source_targets,
                repo_root,
                skill_owners,
                dependencies,
                bundled,
            )
            return f"`{_relative_package_reference(emitted_source, reference, skill_dir)}`"
        if relative == Path("INDEX.md"):
            dependencies.add(COMMAND_SUPPORT_SKILL)
            return f"the `{COMMAND_SUPPORT_SKILL}` skill's `references/methodology-index.md`"
        owner = skill_owners.get(candidate)
        if owner is None:
            raise ValueError(f"canonical skill reference has no generated owner: {relative}")
        dependencies.add(owner)
        return f"the `{owner}` skill"

    rewritten = _MARKDOWN_LINK_RE.sub(replace_link, text)
    rewritten = re.sub(
        r"`((?:skills/|\./|\.\./)?[A-Za-z0-9._/-]+\.md)`",
        replace_backtick,
        rewritten,
    )
    return _rewrite_methodology_command_references(rewritten, dependencies)


def _rewrite_methodology_command_references(
    text: str,
    dependencies: set[str],
) -> str:
    def replace_command(match: re.Match[str]) -> str:
        dependency = f"science-{match.group(1)}"
        dependencies.add(dependency)
        return f"`{dependency}` skill"

    return _AGENT_COMMAND_RE.sub(replace_command, text)


def _resolve_methodology_reference(
    source: Path,
    target: str,
    repo_root: Path,
) -> Path:
    path = Path(target)
    if path.parts and path.parts[0] == "skills":
        return (repo_root / path).resolve()
    return (source.parent / path).resolve()


def _methodology_reference_target(
    candidate: Path,
    emitted_source: Path,
    skill_dir: Path,
    source_targets: Mapping[Path, Path],
    repo_root: Path,
    skill_owners: Mapping[Path, str],
    dependencies: set[str],
    bundled: set[Path],
) -> str:
    unresolved = f"unresolved methodology resource link: {candidate}"
    if not candidate.is_file():
        raise ValueError(unresolved)

    target = source_targets.get(candidate)
    if target is not None:
        return _relative_package_reference(emitted_source, target, skill_dir)

    try:
        relative = candidate.relative_to((repo_root / "skills").resolve())
    except ValueError:
        bundled_target = _bundle_methodology_resource(
            candidate,
            skill_dir,
            source_targets,
            repo_root,
            skill_owners,
            dependencies,
            bundled,
        )
        return _relative_package_reference(
            emitted_source,
            bundled_target,
            skill_dir,
        )

    if relative == Path("INDEX.md"):
        dependencies.add(COMMAND_SUPPORT_SKILL)
        return f"Load the `{COMMAND_SUPPORT_SKILL}` skill and consult its `references/methodology-index.md`"
    owner = skill_owners.get(candidate)
    if owner is None:
        raise ValueError(f"canonical skill reference has no generated owner: {relative}")
    dependencies.add(owner)
    return f"Load the `{owner}` skill"


def _bundle_methodology_resource(
    source: Path,
    skill_dir: Path,
    source_targets: Mapping[Path, Path],
    repo_root: Path,
    skill_owners: Mapping[Path, str],
    dependencies: set[str],
    bundled: set[Path],
) -> Path:
    try:
        relative = source.relative_to(repo_root)
    except ValueError as error:
        raise ValueError(f"methodology resource escapes Science toolkit root: {source}") from error
    if not source.is_file():
        raise ValueError(f"methodology resource is not a file: {source}")

    target = skill_dir / "references" / relative
    if relative in bundled:
        return target
    bundled.add(relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix != ".md":
        shutil.copy2(source, target)
        return target
    target.write_text(
        _rewrite_methodology_references(
            source.read_text(encoding="utf-8"),
            source,
            target,
            skill_dir,
            source_targets,
            repo_root,
            skill_owners,
            dependencies,
            bundled,
        ),
        encoding="utf-8",
    )
    return target


def _relative_package_reference(
    source: Path,
    target: Path,
    skill_dir: Path,
) -> str:
    source_relative = PurePosixPath(source.relative_to(skill_dir).as_posix())
    target_relative = PurePosixPath(target.relative_to(skill_dir).as_posix())
    return relpath(
        target_relative.as_posix(),
        start=source_relative.parent.as_posix(),
    )


def _generate_command_support_skill(
    repo_root: Path,
    output_root: Path,
    methodology_names: tuple[str, ...],
    skill_owners: Mapping[Path, str],
    dependencies: set[str],
) -> Path:
    skill_dir = output_root / COMMAND_SUPPORT_SKILL
    _replace_generated_directory(skill_dir)
    bundled: set[Path] = set()
    _copy_support_tree(
        repo_root / "references" / "role-prompts",
        skill_dir / "references" / "role-prompts",
        skill_dir,
        repo_root,
        skill_owners,
        dependencies,
        bundled,
    )
    _copy_support_tree(
        repo_root / "aspects",
        skill_dir / "references" / "aspects",
        skill_dir,
        repo_root,
        skill_owners,
        dependencies,
        bundled,
    )
    _write_methodology_index(skill_dir, methodology_names)
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


def _copy_support_tree(
    source_root: Path,
    destination_root: Path,
    skill_dir: Path,
    repo_root: Path,
    skill_owners: Mapping[Path, str],
    dependencies: set[str],
    bundled: set[Path],
) -> None:
    if not source_root.is_dir():
        raise ValueError(f"generated resource source is not a directory: {source_root}")
    for source in sorted(source_root.rglob("*")):
        if not source.is_file():
            continue
        target = destination_root / source.relative_to(source_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix != ".md":
            shutil.copy2(source, target)
            continue
        rewritten = _rewrite_methodology_references(
            source.read_text(encoding="utf-8"),
            source,
            target,
            skill_dir,
            {},
            repo_root,
            skill_owners,
            dependencies,
            bundled,
        )
        target.write_text(
            _rewrite_support_skill_references(rewritten, dependencies),
            encoding="utf-8",
        )


def _rewrite_support_skill_references(
    text: str,
    dependencies: set[str],
) -> str:
    replacements = (
        (
            "`scientific-writing`",
            "`science-scientific-writing` skill",
            {"science-scientific-writing"},
        ),
        (
            "`${CLAUDE_PLUGIN_ROOT}/skills/INDEX.md`",
            "the support package's `references/methodology-index.md`",
            set(),
        ),
        (
            "`literature/`/`epistemics/` leaves",
            "`science-literature`/`science-epistemics` skills",
            {"science-literature", "science-epistemics"},
        ),
    )
    for source, replacement, targets in replacements:
        if source not in text:
            continue
        text = text.replace(source, replacement)
        dependencies.update(targets)
    return text


def _write_methodology_index(
    skill_dir: Path,
    methodology_names: tuple[str, ...],
) -> None:
    lines = ["# Science Methodology Skills", ""]
    lines.extend(f"- `{name}`" for name in sorted(methodology_names))
    path = skill_dir / "references" / "methodology-index.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_distribution_index(
    repo_root: Path,
    output_root: Path,
    command_paths: list[Path],
    methodology_packages: tuple[MethodologyPackage, ...],
) -> None:
    command_rows = [
        (
            command_to_skill_name(path),
            path.relative_to(repo_root).as_posix(),
        )
        for path in command_paths
    ]
    methodology_rows = [
        (
            package.name,
            package.router_source.relative_to(repo_root).as_posix(),
        )
        for package in methodology_packages
    ]
    support_rows = [
        (
            COMMAND_SUPPORT_SKILL,
            "references/command-preamble.md",
        )
    ]
    lines = [
        "# Generated Science Agent Skills",
        "",
        "Generated from canonical Science toolkit sources. Do not edit.",
        "",
    ]
    for heading, rows in (
        ("Command Skills", command_rows),
        ("Methodology Skills", methodology_rows),
        ("Support Skills", support_rows),
    ):
        lines.extend(
            (
                f"## {heading}",
                "",
                "| Agent Skill | Canonical Source |",
                "| --- | --- |",
            )
        )
        lines.extend(f"| `{name}` | `{source}` |" for name, source in rows)
        lines.append("")
    (output_root / "INDEX.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def _replace_generated_directory(path: Path) -> None:
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise ValueError(f"generated package path is not a directory: {path}")
    if path.is_dir():
        shutil.rmtree(path)
    path.mkdir(parents=True)
