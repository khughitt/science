import click


@click.group(name="skills")
def skills_group() -> None:
    """Skills library tooling."""


@skills_group.command(name="lint")
@click.option("--root", type=click.Path(exists=True, file_okay=False), default="skills")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def lint_cmd(root: str, fmt: str) -> None:
    """Lint the skills/ tree for structural conformance."""
    click.echo("skills lint: no rules registered yet")
