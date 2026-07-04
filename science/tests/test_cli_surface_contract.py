from __future__ import annotations

import importlib
from collections.abc import Iterator

import click

from science_tool.cli import main as science_cli


_PROJECT_OPTION_ALLOWLIST: dict[str, tuple[str, str]] = {
    "benchmark gap-calibration": (
        "multi-project label=path specs, not a project root selector",
        "label=path",
    ),
    "commons show": (
        "named registered project overlay selector",
        "registered project",
    ),
    "commons validate": (
        "named registered project overlay selector",
        "registered project",
    ),
    "dag audit": (
        "older DAG filesystem-root flag; prefer --project-root for new commands",
        "project root",
    ),
    "dag init": (
        "older DAG filesystem-root flag; prefer --project-root for new commands",
        "project root",
    ),
    "dag number": (
        "older DAG filesystem-root flag; prefer --project-root for new commands",
        "project root",
    ),
    "dag render": (
        "older DAG filesystem-root flag; prefer --project-root for new commands",
        "project root",
    ),
    "dag retired-edges": (
        "older DAG filesystem-root flag for explicit retired YAML migration inspection",
        "project root",
    ),
    "dag retired-edge-migration-plan": (
        "older DAG filesystem-root flag for explicit retired YAML migration planning",
        "project root",
    ),
    "dag staleness": (
        "older DAG filesystem-root flag; prefer --project-root for new commands",
        "project root",
    ),
    "dag validate": (
        "older DAG filesystem-root flag; prefer --project-root for new commands",
        "project root",
    ),
    "data audit": (
        "older filesystem-root flag; prefer --project-root for new commands",
        "project root",
    ),
    "entities audit-identifiers": (
        "older filesystem-root flag; prefer --project-root for new commands",
        "project root",
    ),
    "entities inventory": (
        "older filesystem-root flag; prefer --project-root for new commands",
        "project root",
    ),
    "entities register-kind": (
        "older filesystem-root flag; prefer --project-root for new commands",
        "project root",
    ),
    "feedback add": (
        "project name metadata, not a filesystem root",
        "project name",
    ),
    "feedback list": (
        "project name filter, not a filesystem root",
        "project name",
    ),
    "feedback report": (
        "project name filter, not a filesystem root",
        "project name",
    ),
}

_JSON_WITHOUT_FORMAT_ALLOWLIST: dict[str, str] = {}

_PROJECT_ROOT_ALIAS_COMMANDS: set[str] = {
    "dag audit",
    "dag init",
    "dag number",
    "dag render",
    "dag retired-edges",
    "dag retired-edge-migration-plan",
    "dag staleness",
    "dag validate",
    "data audit",
    "entities audit-identifiers",
    "entities inventory",
    "entities register-kind",
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


def _option_for_path(command_path: str, flag: str) -> click.Option:
    path_parts = command_path.split()
    command: click.Command = science_cli
    for part in path_parts:
        if not isinstance(command, click.Group):
            raise AssertionError(f"{command_path!r} descends through non-group {part!r}")
        command = command.commands[part]

    for parameter in command.params:
        if isinstance(parameter, click.Option) and flag in parameter.opts:
            return parameter
    raise AssertionError(f"{command_path!r} has no {flag} option")


def _commands_with_option_without_option(flag: str, missing_flag: str) -> list[str]:
    paths: list[str] = []
    for path, command in _walk_commands(science_cli, ()):
        options = {
            option
            for parameter in command.params
            if isinstance(parameter, click.Option)
            for option in parameter.opts
        }
        if flag in options and missing_flag not in options:
            paths.append(" ".join(path))
    return sorted(paths)


def test_project_option_usage_is_intentionally_classified() -> None:
    actual = set(_commands_with_option("--project"))
    documented = set(_PROJECT_OPTION_ALLOWLIST)

    assert actual == documented, (
        "`--project` is ambiguous. Existing uses must be classified here; new "
        "project-root selectors should use `--project-root` instead."
    )
    assert all(reason.strip() and help_phrase.strip() for reason, help_phrase in _PROJECT_OPTION_ALLOWLIST.values())


def test_project_option_help_text_names_what_project_means() -> None:
    unclear: list[str] = []
    for command_path, (_, help_phrase) in sorted(_PROJECT_OPTION_ALLOWLIST.items()):
        option = _option_for_path(command_path, "--project")
        help_text = option.help or ""
        if help_phrase.lower() not in help_text.lower():
            unclear.append(f"{command_path}: expected {help_phrase!r} in help {help_text!r}")

    assert not unclear


def test_project_root_aliases_exist_for_touched_filesystem_project_flags() -> None:
    missing: list[str] = []
    for command_path in sorted(_PROJECT_ROOT_ALIAS_COMMANDS):
        option = _option_for_path(command_path, "--project")
        if "--project-root" not in option.opts:
            missing.append(command_path)

    assert not missing


def test_json_only_option_usage_is_intentionally_classified() -> None:
    actual = set(_commands_with_option_without_option("--json", "--format"))
    documented = set(_JSON_WITHOUT_FORMAT_ALLOWLIST)

    assert actual == documented, (
        "`--format` is canonical for new multi-format commands. Existing "
        "`--json`-only commands must be classified here before adding more."
    )
    assert all(reason.strip() for reason in _JSON_WITHOUT_FORMAT_ALLOWLIST.values())


def test_extracted_telemetry_group_is_registered_from_split_module() -> None:
    telemetry_cli = importlib.import_module("science_tool.telemetry_cli")

    assert science_cli.commands["telemetry"] is telemetry_cli.telemetry_group


def test_extracted_feedback_group_is_registered_from_split_module() -> None:
    feedback_cli = importlib.import_module("science_tool.feedback_cli")

    assert science_cli.commands["feedback"] is feedback_cli.feedback_group


def test_extracted_labnote_group_is_registered_from_split_module() -> None:
    labnote_cli = importlib.import_module("science_tool.labnote_cli")

    assert science_cli.commands["labnote"] is labnote_cli.labnote_group


def test_extracted_search_command_is_registered_from_split_module() -> None:
    search_cli = importlib.import_module("science_tool.search_cli")

    assert science_cli.commands["search"] is search_cli.search_command


def test_extracted_data_group_is_registered_from_split_module() -> None:
    data_cli = importlib.import_module("science_tool.data_cli")

    assert science_cli.commands["data"] is data_cli.data_group


def test_extracted_distill_group_is_registered_from_split_module() -> None:
    distill_cli = importlib.import_module("science_tool.distill_cli")

    assert science_cli.commands["distill"] is distill_cli.distill_group


def test_extracted_book_split_command_is_registered_from_split_module() -> None:
    book_split_cli = importlib.import_module("science_tool.book_split_cli")

    assert science_cli.commands["book-split"] is book_split_cli.book_split_command


def test_extracted_doi_group_is_registered_from_split_module() -> None:
    doi_cli = importlib.import_module("science_tool.doi_cli")

    assert science_cli.commands["doi"] is doi_cli.doi_group
