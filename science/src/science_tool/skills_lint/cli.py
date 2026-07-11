from pathlib import Path

import click

from science_tool.output import emit
from science_tool.skills_lint.lint import SkillIssue, check_skills


@click.group(name="skills")
def skills_group() -> None:
    """Skills library tooling."""


@skills_group.command(name="lint")
@click.option("--root", type=click.Path(exists=True, file_okay=False), default="skills")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def lint_cmd(root: str, fmt: str) -> None:
    """Lint the skills/ tree for structural conformance."""
    issues = check_skills(Path(root))

    def _render() -> None:
        for issue in issues:
            click.echo(_format_text_issue(issue))

    emit(
        output_format=fmt,
        payload={"issues": [issue.to_json() for issue in issues]},
        render_text=_render,
    )
    if issues:
        raise click.exceptions.Exit(1)


def _format_text_issue(issue: SkillIssue) -> str:
    parts = [issue.path.as_posix(), issue.kind]
    if issue.field is not None:
        parts.append(issue.field)
    if issue.detail:
        parts.append(issue.detail)
    return ": ".join(parts)
