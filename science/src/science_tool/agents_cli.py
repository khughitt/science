"""CLI commands for generating and installing Science agent assets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import click
import yaml

from science_tool.agent_assets import generate_agent_assets, validate_repo_root

AgentName = Literal["codex", "crush", "opencode"]
InstallScope = Literal["project", "user"]

_FRONTMATTER_RE = re.compile(r"\A---\n(?P<frontmatter>.*?)\n---(?:\n|\Z)", re.DOTALL)


@dataclass(frozen=True)
class LinkSpec:
    source: Path
    destination: Path


@dataclass(frozen=True)
class InstallPlan:
    links: tuple[LinkSpec, ...]
    current: tuple[LinkSpec, ...]


def _resolve_repo_root() -> Path:
    """Find the science toolkit repo root by walking up from CWD."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        try:
            return validate_repo_root(parent)
        except ValueError:
            continue
    raise ValueError(f"could not find a Science toolkit root from: {cwd}")


def _generated_skill_name(skill_file: Path) -> str:
    try:
        text = skill_file.read_text(encoding="utf-8")
    except OSError as error:
        raise click.ClickException(f"could not read generated skill: {skill_file}: {error}") from error
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        raise click.ClickException(f"invalid generated skill frontmatter: {skill_file}")
    try:
        frontmatter = yaml.safe_load(match.group("frontmatter"))
    except yaml.YAMLError as error:
        raise click.ClickException(f"invalid generated skill frontmatter: {skill_file}") from error
    if not isinstance(frontmatter, dict) or not isinstance(frontmatter.get("name"), str):
        raise click.ClickException(f"invalid generated skill frontmatter: {skill_file}")
    return frontmatter["name"]


def _absolute_existing_source(source: Path) -> Path:
    try:
        resolved = source.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise click.ClickException(f"generated install source does not exist: {source}") from error
    if not resolved.is_absolute() or not resolved.exists():
        raise click.ClickException(f"generated install source does not exist: {source}")
    return resolved


def _destination_parent_collisions(
    *,
    destination: Path,
    install_root: Path,
) -> tuple[Path, ...]:
    collisions: list[Path] = []
    current = install_root
    relative_parent = destination.parent.relative_to(install_root)
    for component in (Path(), *(Path(*relative_parent.parts[:index]) for index in range(1, len(relative_parent.parts) + 1))):
        candidate = current / component
        if candidate.is_symlink() or (candidate.exists() and not candidate.is_dir()):
            collisions.append(candidate)
    return tuple(collisions)


def build_install_plan(
    *,
    repo_root: Path,
    agent: AgentName,
    scope: InstallScope,
    project_dir: Path,
    user_home: Path,
) -> InstallPlan:
    """Validate sources and collisions without changing the filesystem."""
    if agent not in {"codex", "crush", "opencode"}:
        raise click.ClickException(f"unsupported agent: {agent}")
    if scope not in {"project", "user"}:
        raise click.ClickException(f"unsupported install scope: {scope}")

    try:
        root = validate_repo_root(repo_root)
    except ValueError as error:
        raise click.ClickException(str(error)) from error

    project_root = project_dir.expanduser().resolve()
    home_root = user_home.expanduser().resolve()
    install_root = project_root if scope == "project" else home_root
    skills_destination = install_root / ".agents" / "skills"

    skill_links: list[LinkSpec] = []
    skill_names: set[str] = set()
    generated_skills = root / "skills" / "generated"
    for package in sorted(generated_skills.glob("science-*")):
        skill_file = package / "SKILL.md"
        if not skill_file.is_file():
            continue
        source = _absolute_existing_source(package)
        name = _generated_skill_name(source / "SKILL.md")
        if name != package.name:
            raise click.ClickException(
                "generated skill name does not match directory: "
                f"{skill_file} declares {name!r}, expected {package.name!r}"
            )
        skill_names.add(package.name)
        skill_links.append(
            LinkSpec(
                source=source,
                destination=skills_destination / package.name,
            )
        )

    if "science-command-preamble" not in skill_names:
        raise click.ClickException(
            "generated install set is missing required skill: science-command-preamble"
        )

    command_links: list[LinkSpec] = []
    if agent == "opencode":
        commands_destination = (
            install_root / ".opencode" / "commands"
            if scope == "project"
            else install_root / ".config" / "opencode" / "commands"
        )
        for adapter in sorted((root / "commands" / "opencode").glob("science-*.md")):
            source = _absolute_existing_source(adapter)
            if adapter.stem not in skill_names:
                raise click.ClickException(
                    f"OpenCode adapter has no matching generated skill: {adapter}"
                )
            command_links.append(
                LinkSpec(
                    source=source,
                    destination=commands_destination / adapter.name,
                )
            )

    links = tuple((*skill_links, *command_links))
    current: list[LinkSpec] = []
    collisions: set[Path] = set()
    for link in links:
        collisions.update(
            _destination_parent_collisions(
                destination=link.destination,
                install_root=install_root,
            )
        )
        if link.destination.is_symlink():
            if link.destination.readlink() == link.source:
                current.append(link)
            else:
                collisions.add(link.destination)
        elif link.destination.exists():
            collisions.add(link.destination)

    if collisions:
        details = "\n".join(f"- {path}" for path in sorted(collisions))
        raise click.ClickException(f"destination collision(s):\n{details}")

    return InstallPlan(links=links, current=tuple(current))


def apply_install_plan(plan: InstallPlan) -> tuple[LinkSpec, ...]:
    """Create only the not-already-current links from a validated plan."""
    current_destinations = {link.destination for link in plan.current}
    pending = tuple(link for link in plan.links if link.destination not in current_destinations)
    for link in pending:
        link.destination.parent.mkdir(parents=True, exist_ok=True)
        link.destination.symlink_to(link.source)
    return pending


@click.group(name="agents")
def agents_group() -> None:
    """Generate and install Science agent assets."""


@agents_group.command(name="generate")
@click.option("--repo-root", type=click.Path(path_type=Path), default=None)
def generate_cmd(*, repo_root: Path | None) -> None:
    """Generate the committed Science agent distributions."""
    try:
        root = validate_repo_root(repo_root or _resolve_repo_root())
        result = generate_agent_assets(
            root,
            root / "skills" / "generated",
            root / "commands" / "opencode",
        )
    except ValueError as error:
        raise click.ClickException(str(error)) from error
    click.echo(
        f"Generated {len(result.skill_paths)} skills and "
        f"{len(result.opencode_command_paths)} OpenCode commands"
    )


@agents_group.command(name="install")
@click.option(
    "--agent",
    type=click.Choice(["codex", "crush", "opencode"]),
    required=True,
    help="Target agent to install for.",
)
@click.option(
    "--scope",
    type=click.Choice(["project", "user"]),
    default="project",
    show_default=True,
    help="Install for the current project or the current user.",
)
@click.option(
    "--project-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Project directory to install into. Defaults to CWD.",
)
@click.option(
    "--repo-root",
    type=click.Path(path_type=Path),
    default=None,
    help="Science toolkit repo root. Defaults to auto-detection.",
)
def install_cmd(
    *,
    agent: AgentName,
    scope: InstallScope,
    project_dir: Path | None,
    repo_root: Path | None,
) -> None:
    """Install the committed Science agent distribution as absolute links."""
    try:
        root = validate_repo_root(repo_root) if repo_root is not None else _resolve_repo_root()
    except ValueError as error:
        raise click.ClickException(str(error)) from error

    resolved_project = (project_dir or Path.cwd()).expanduser().resolve()
    resolved_home = Path.home().expanduser().resolve()
    plan = build_install_plan(
        repo_root=root,
        agent=agent,
        scope=scope,
        project_dir=resolved_project,
        user_home=resolved_home,
    )
    installed = apply_install_plan(plan)
    click.echo(f"Installed {len(installed)} links; {len(plan.current)} already current")
