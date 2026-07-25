"""Mechanics of the retirement classes, against a synthetic tree.

Deliberately does not import the real CLI: this file proves the classes behave,
`test_cli_retirement.py` proves the real tree uses them.
"""

from __future__ import annotations

import click
import pytest
from click.shell_completion import ShellComplete
from click.testing import CliRunner

from science_tool.cli_retirement import RetiredCommand, RetiredGroup


GROUP_FORWARD = "Author the entity instead."
LEAF_FORWARD = "Run `science entity create concept <title>`."
SOLO_FORWARD = "Run `science entity create thing <title>`."


@pytest.fixture
def tree() -> click.Group:
    @click.group()
    def root() -> None:
        """Root."""

    outer = click.Group("outer")
    root.add_command(outer)

    group = RetiredGroup("add", path="outer add", forward=GROUP_FORWARD)
    outer.add_command(group)
    group.add_command(RetiredCommand("concept", path="outer add concept", forward=LEAF_FORWARD))

    outer.add_command(RetiredCommand("solo", path="outer solo", forward=SOLO_FORWARD))
    return root


def test_leaf_errors_before_parameter_validation(tree: click.Group) -> None:
    """The defect this sub-project exists to fix: no correct call is required first."""
    result = CliRunner().invoke(tree, ["outer", "solo"])

    assert result.exit_code == 1
    assert "outer solo is retired" in result.output
    assert "Missing" not in result.output


def test_leaf_errors_on_direct_help(tree: click.Group) -> None:
    result = CliRunner().invoke(tree, ["outer", "solo", "--help"])

    assert result.exit_code == 1
    assert "outer solo is retired" in result.output


def test_leaf_ignores_arbitrary_arguments(tree: click.Group) -> None:
    result = CliRunner().invoke(tree, ["outer", "solo", "a", "b", "--nope", "x"])

    assert result.exit_code == 1
    assert "outer solo is retired" in result.output


def test_leaf_declares_no_parameters(tree: click.Group) -> None:
    assert tree.commands["outer"].commands["solo"].params == []


def test_retired_nodes_are_hidden(tree: click.Group) -> None:
    listing = CliRunner().invoke(tree, ["outer", "--help"]).output

    assert "solo" not in listing
    assert "add" not in listing


@pytest.mark.parametrize(
    ("args", "owner", "forward"),
    [
        (["outer", "add"], "outer add", GROUP_FORWARD),
        (["outer", "add", "--help"], "outer add", GROUP_FORWARD),
        (["outer", "add", "bogus"], "outer add", GROUP_FORWARD),
        (["outer", "add", "concept"], "outer add concept", LEAF_FORWARD),
        (["outer", "add", "concept", "--help"], "outer add concept", LEAF_FORWARD),
        (["outer", "add", "concept", "x", "--path", "/tmp"], "outer add concept", LEAF_FORWARD),
    ],
)
def test_group_and_leaf_cases_are_answered_by_their_owner(
    tree: click.Group, args: list[str], owner: str, forward: str
) -> None:
    """A named child answers for itself; only the unnamed cases fall to the group.

    Asserts the complete message, not just the path. A hard-coded group message that
    ignored its `forward` argument entirely would satisfy a path-only assertion.
    """
    result = CliRunner().invoke(tree, args)

    assert f"{owner} is retired. {forward}" in result.output


def test_unknown_child_keeps_usage_exit_code(tree: click.Group) -> None:
    """Naming a command that does not exist is a usage error: exit 2, not 1."""
    result = CliRunner().invoke(tree, ["outer", "add", "bogus"])

    assert result.exit_code == 2


def test_completion_does_not_raise(tree: click.Group) -> None:
    """Click builds contexts with resilient_parsing=True; raising there is a crash."""
    completer = ShellComplete(tree, {}, "root", "_ROOT_COMPLETE")

    for args in (["outer", "add"], ["outer", "add", "concept"], ["outer", "solo"]):
        completer.get_completions(args, "")


def test_registering_under_a_missing_parent_fails_at_the_boundary(tree: click.Group) -> None:
    from science_tool import cli_retirement

    with pytest.raises(RuntimeError, match="no command 'nope'"):
        cli_retirement._resolve_parent(tree, ["nope"])


def test_registering_under_a_leaf_fails_at_the_boundary(tree: click.Group) -> None:
    """A manifest path naming a leaf as a parent must fail here, not later.

    The descent loop only checks nodes it passes *through*; the terminal node needs its
    own check, or this returns a Command and blows up on `.add_command` far from the
    malformed declaration.
    """
    from science_tool import cli_retirement

    with pytest.raises(RuntimeError, match="is not a group"):
        cli_retirement._resolve_parent(tree, ["outer", "solo"])


def test_registering_leaf_at_existing_destination_fails(
    tree: click.Group, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool import cli_retirement

    outer = tree.commands["outer"]
    assert isinstance(outer, click.Group)
    existing = outer.commands["solo"]
    monkeypatch.setattr(cli_retirement, "RETIRED_GROUPS", {})
    monkeypatch.setattr(
        cli_retirement,
        "RETIREMENTS",
        {"outer solo": "Run `science entity create thing <title>`."},
    )

    with pytest.raises(
        RuntimeError,
        match="cannot attach retirement 'outer solo': existing command 'solo'",
    ):
        cli_retirement.register_retirements(tree)

    assert outer.commands["solo"] is existing


def test_registering_group_at_existing_destination_fails(
    tree: click.Group, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool import cli_retirement

    outer = tree.commands["outer"]
    assert isinstance(outer, click.Group)
    existing = outer.commands["add"]
    monkeypatch.setattr(
        cli_retirement,
        "RETIRED_GROUPS",
        {"outer add": "Author the entity instead."},
    )
    monkeypatch.setattr(cli_retirement, "RETIREMENTS", {})

    with pytest.raises(
        RuntimeError,
        match="cannot attach retirement 'outer add': existing command 'add'",
    ):
        cli_retirement.register_retirements(tree)

    assert outer.commands["add"] is existing
