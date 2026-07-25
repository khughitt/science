"""Reconstruct the caller's invocation, plus ``--output``, as the escape command.

A truncation footer that names a *different* selection than the user asked for is worse
than no footer: it silently substitutes one result set for another. This rebuilds the
command from the live Click context so the escape returns exactly what was truncated.
"""

from __future__ import annotations

import shlex

import click
from click.core import ParameterSource

_OUTPUT_PARAMS = frozenset({"output_path", "output"})


def build_complete_via(ctx: click.Context, *, output_hint: str) -> str:
    """Return ``<command path> <caller-selected options> --output <hint>``, shell-safe.

    Values are quoted with ``shlex.join``: the caller's shell already protected a path or
    filter containing spaces, and reconstructing the command by naive joining would strip
    that protection and advertise a command that does something different.

    The command path itself is not quoted -- it is a sequence of literal words, and
    quoting it would produce ``'science tasks list'`` as one token.
    """
    tokens: list[str] = []
    params_by_name = {param.name: param for param in ctx.command.params}

    for name, value in ctx.params.items():
        if name in _OUTPUT_PARAMS:
            continue
        param = params_by_name.get(name)
        if param is None or not isinstance(param, click.Option):
            continue
        if ctx.get_parameter_source(name) is ParameterSource.DEFAULT:
            continue
        flag = max(param.opts, key=len)
        if value is True:
            tokens.append(flag)
        elif value is False and param.secondary_opts:
            tokens.append(max(param.secondary_opts, key=len))
        elif isinstance(value, (list, tuple)):
            for item in value:
                tokens.extend([flag, str(item)])
        else:
            tokens.extend([flag, str(value)])

    tokens.extend(["--output", output_hint])
    return f"{ctx.command_path} {shlex.join(tokens)}"
