"""The guard: the live command tree and the retirement manifest cannot drift.

Assertions are parametrized over the manifests, so a twenty-third retirement is
covered the moment it is declared rather than when someone remembers to add a case.
"""

from __future__ import annotations

import click
import pytest
from click.shell_completion import ShellComplete
from click.testing import CliRunner

from science_tool.cli import main
from science_tool.cli_retirement import RETIRED_GROUPS, RETIREMENTS, RetiredCommand, RetiredGroup


def _nodes(cmd: click.Command, path: tuple[str, ...] = ()) -> list[tuple[str, click.Command]]:
    found = [(" ".join(path), cmd)]
    if isinstance(cmd, click.Group):
        for name, sub in sorted(cmd.commands.items()):
            found.extend(_nodes(sub, (*path, name)))
    return found


def _live_retired_leaves() -> dict[str, RetiredCommand]:
    return {
        path: cmd
        for path, cmd in _nodes(main)
        if isinstance(cmd, RetiredCommand)
    }


def _live_retired_groups() -> dict[str, RetiredGroup]:
    return {
        path: cmd
        for path, cmd in _nodes(main)
        if isinstance(cmd, RetiredGroup)
    }


def test_live_retired_leaves_match_the_manifest() -> None:
    assert set(_live_retired_leaves()) == set(RETIREMENTS)


def test_live_retired_groups_match_the_manifest() -> None:
    assert set(_live_retired_groups()) == set(RETIRED_GROUPS)


@pytest.mark.parametrize("path", sorted(RETIREMENTS))
def test_retired_command_declares_no_parameters(path: str) -> None:
    """Unreachable parameters are not documentation; they are maintenance."""
    assert _live_retired_leaves()[path].params == []


@pytest.mark.parametrize("path", sorted(RETIREMENTS) + sorted(RETIRED_GROUPS))
def test_retired_node_is_hidden(path: str) -> None:
    """--help must not be able to disagree with the manifest about what is live."""
    nodes = {**_live_retired_leaves(), **_live_retired_groups()}
    assert nodes[path].hidden is True


@pytest.mark.parametrize("path", sorted(RETIREMENTS))
@pytest.mark.parametrize("suffix", [[], ["--help"]], ids=["bare", "help"])
def test_retired_command_answers_without_a_correct_invocation(path: str, suffix: list[str]) -> None:
    """The regression test for the original defect.

    Every pre-existing test invoked these with full valid arguments, which is exactly
    why nobody noticed that constructing a correct call was a precondition for learning
    the call was impossible. The `--help` case additionally covers a behaviour this
    change makes deliberately, replacing the coverage lost with the old vocabulary test.
    """
    result = CliRunner().invoke(main, path.split() + suffix)

    assert result.exit_code != 0
    assert f"{path} is retired. {RETIREMENTS[path]}" in result.output


@pytest.mark.parametrize(
    ("args", "owner"),
    [
        (["graph", "add"], "graph add"),
        (["graph", "add", "--help"], "graph add"),
        (["graph", "add", "bogus"], "graph add"),
        (["graph", "add", "concept"], "graph add concept"),
        (["graph", "add", "concept", "--help"], "graph add concept"),
        (["graph", "add", "concept", "x", "--path", "/tmp"], "graph add concept"),
    ],
)
def test_group_owned_and_leaf_owned_cases_stay_distinct(args: list[str], owner: str) -> None:
    """Only the shapes naming no child fall to the group; the rest keep their own path.

    Asserts the complete manifest text for whichever owner answers, so a group message
    that ignored `RETIRED_GROUPS` and hard-coded its guidance would fail here.
    """
    forward = RETIRED_GROUPS.get(owner) or RETIREMENTS[owner]
    result = CliRunner().invoke(main, args)

    assert f"{owner} is retired. {forward}" in result.output


def test_unknown_subcommand_keeps_the_usage_exit_code() -> None:
    assert CliRunner().invoke(main, ["graph", "add", "bogus"]).exit_code == 2


def test_shell_completion_over_retired_surfaces_does_not_raise() -> None:
    """Completion builds contexts with resilient_parsing=True.

    Invisible to every other assertion here, because completion never goes through
    normal invocation. Measured against an unguarded draft, both of these raised
    ClickException straight out of ShellComplete.
    """
    completer = ShellComplete(main, {}, "science", "_SCIENCE_COMPLETE")

    for args in (["graph", "add"], ["graph", "add", "concept"], ["inquiry", "add-node"]):
        completer.get_completions(args, "")
