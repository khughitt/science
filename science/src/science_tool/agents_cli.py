"""CLI commands for multi-agent skill and command generation.

Supports generating agent-compatible outputs for:
- Codex (SKILL.md format, written to codex-skills/)
- Crush (SKILL.md with user-invocable frontmatter)
- OpenCode (SKILL.md for skills, .md with frontmatter for commands)
"""

from __future__ import annotations

import shutil
from pathlib import Path

import click

from science_tool.codex_skills import generate_agent_skills


def _resolve_repo_root() -> Path:
    """Find the science toolkit repo root by walking up from CWD."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / "skills" / "INDEX.md").exists() and (parent / "commands").is_dir():
            return parent
    return cwd


@click.group(name="agents")
def agents_group() -> None:
    """Generate agent-compatible skills and commands for Crush, OpenCode, and Codex."""


@agents_group.command(name="generate")
@click.option(
    "--agent",
    type=click.Choice(["codex", "crush", "opencode"]),
    required=True,
    help="Target agent to generate for.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["skill", "command"]),
    default="skill",
    help="Output format: 'skill' generates SKILL.md files, 'command' generates .md command files (OpenCode only).",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory. Defaults to agent-specific location.",
)
@click.option(
    "--repo-root",
    type=click.Path(path_type=Path),
    default=None,
    help="Science toolkit repo root. Defaults to auto-detection.",
)
def generate_cmd(
    *,
    agent: str,
    output_format: str,
    output_dir: Path | None,
    repo_root: Path | None,
) -> None:
    """Generate skills and commands for a specific agent.

    Examples:

        science agents generate --agent codex
        science agents generate --agent crush
        science agents generate --agent opencode --format command
    """
    if repo_root is None:
        repo_root = _resolve_repo_root()

    if output_dir is None:
        output_dir = _default_output_dir(repo_root, agent, output_format)

    # Validate format/agent combinations
    if output_format == "command" and agent != "opencode":
        click.echo(
            "Warning: command format is only supported for OpenCode. Generating skills instead.",
            err=True,
        )
        output_format = "skill"

    generated = generate_agent_skills(
        repo_root=repo_root,
        output_root=output_dir,
        agent=agent,
        format=output_format,
    )

    click.echo(f"Generated {len(generated)} items for {agent} in {output_dir}")


def _default_output_dir(repo_root: Path, agent: str, output_format: str) -> Path:
    """Return the default output directory for an agent/format combination."""
    if agent == "codex":
        return repo_root / "codex-skills"
    if agent == "crush":
        return repo_root / "crush-skills"
    if agent == "opencode":
        if output_format == "command":
            return repo_root / "opencode-commands"
        return repo_root / "opencode-skills"
    return repo_root / f"{agent}-skills"


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
