"""The guard: the live command tree and the retirement manifest cannot drift.

Assertions are parametrized over the manifests, so a twenty-third retirement is
covered the moment it is declared rather than when someone remembers to add a case.
"""

from __future__ import annotations

import click
import pytest

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
