"""CLI commands for generating and installing Science agent assets."""

from __future__ import annotations

import shutil
from pathlib import Path

import click

from science_tool.agent_assets import generate_agent_assets, validate_repo_root


def _resolve_repo_root() -> Path:
    """Find the science toolkit repo root by walking up from CWD."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        try:
            return validate_repo_root(parent)
        except ValueError:
            continue
    raise ValueError(f"could not find a Science toolkit root from: {cwd}")


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
    "--symlink/--copy",
    default=True,
    help="Use symlinks (default) or copy files.",
)
@click.option(
    "--project-dir",
    type=click.Path(path_type=Path),
    default=Path.cwd(),
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
    agent: str,
    symlink: bool,
    project_dir: Path,
    repo_root: Path | None,
) -> None:
    """Install Science skills into a project's agent discovery directory.

    Creates symlinks (or copies) from the science toolkit's skills/ directory
    into the project's .agents/skills/ directory, making them discoverable by
    Crush, OpenCode, and other agents that support the .agents/skills/ convention.

    Examples:

        science agents install --agent crush
        science agents install --agent opencode --no-symlink
    """
    if repo_root is None:
        repo_root = _resolve_repo_root()

    # Target directory based on agent
    if agent in {"crush", "opencode"}:
        target_dir = project_dir / ".agents" / "skills"
    else:
        # Codex uses its own directory
        target_dir = project_dir / ".codex" / "skills"

    target_dir.mkdir(parents=True, exist_ok=True)

    # Link/copy methodology skills
    skills_source = repo_root / "skills"
    installed = []

    if skills_source.exists():
        for skill_dir in sorted(skills_source.iterdir()):
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                skill_name = skill_dir.name
                target_path = target_dir / f"science-{skill_name}"

                if target_path.exists() or target_path.is_symlink():
                    if target_path.is_symlink():
                        target_path.unlink()
                    else:
                        shutil.rmtree(target_path)

                if symlink:
                    target_path.symlink_to(skill_dir)
                    installed.append(f"{skill_name} (symlink)")
                else:
                    shutil.copytree(skill_dir, target_path)
                    installed.append(f"{skill_name} (copy)")

    click.echo(f"Installed {len(installed)} Science skills to {target_dir}")
    for item in installed[:10]:
        click.echo(f"  - {item}")
    if len(installed) > 10:
        click.echo(f"  ... and {len(installed) - 10} more")
