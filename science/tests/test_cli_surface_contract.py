from __future__ import annotations

from collections.abc import Iterator

import click

from science_tool.cli import main as science_cli


_PROJECT_OPTION_ALLOWLIST: dict[str, str] = {
    "benchmark gap-calibration": "multi-project label=path specs, not a project root selector",
    "commons show": "named registered project overlay selector",
    "commons validate": "named registered project overlay selector",
    "dag audit": "older DAG filesystem-root flag; prefer --project-root for new commands",
    "dag init": "older DAG filesystem-root flag; prefer --project-root for new commands",
    "dag number": "older DAG filesystem-root flag; prefer --project-root for new commands",
    "dag render": "older DAG filesystem-root flag; prefer --project-root for new commands",
    "dag staleness": "older DAG filesystem-root flag; prefer --project-root for new commands",
    "dag validate": "older DAG filesystem-root flag; prefer --project-root for new commands",
    "data audit": "older filesystem-root flag; prefer --project-root for new commands",
    "entities audit-identifiers": "older filesystem-root flag; prefer --project-root for new commands",
    "entities inventory": "older filesystem-root flag; prefer --project-root for new commands",
    "entities register-kind": "older filesystem-root flag; prefer --project-root for new commands",
    "feedback add": "project name metadata, not a filesystem root",
    "feedback list": "project name filter, not a filesystem root",
    "feedback report": "project name filter, not a filesystem root",
}


def _walk_commands(command: click.Command, path: tuple[str, ...]) -> Iterator[tuple[tuple[str, ...], click.Command]]:
    yield path, command
    if not isinstance(command, click.Group):
        return

    for name, child in command.commands.items():
        yield from _walk_commands(child, (*path, name))


def _commands_with_option(flag: str) -> list[str]:
    paths: list[str] = []
    for path, command in _walk_commands(science_cli, ()):
        for parameter in command.params:
            if isinstance(parameter, click.Option) and flag in parameter.opts:
                paths.append(" ".join(path))
                break
    return sorted(paths)


def test_project_option_usage_is_intentionally_classified() -> None:
    actual = set(_commands_with_option("--project"))
    documented = set(_PROJECT_OPTION_ALLOWLIST)

    assert actual == documented, (
        "`--project` is ambiguous. Existing uses must be classified here; new "
        "project-root selectors should use `--project-root` instead."
    )
    assert all(reason.strip() for reason in _PROJECT_OPTION_ALLOWLIST.values())
