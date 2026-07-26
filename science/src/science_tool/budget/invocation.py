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


def hint_for(stem: str, output_format: str) -> str:
    """Return ``<stem>.<ext>`` with the extension matching the effective output format.

    The escape command reproduces exactly what was truncated, so a text/table run's
    complete output is text (``.txt``) and a ``--format json`` run's is JSON (``.json``).
    A hint that always said ``.json`` would advertise a file whose contents contradict its
    name whenever the caller was viewing the default text render.
    """
    return f"{stem}.{'json' if output_format == 'json' else 'txt'}"


def build_complete_via(
    ctx: click.Context,
    *,
    output_hint: str,
    escape_flag: str = "--output",
    skip_params: frozenset[str] = _OUTPUT_PARAMS,
) -> str:
    """Return ``<command path> <caller-selected options> <escape_flag> <hint>``, shell-safe.

    Values are quoted with ``shlex.join``: the caller's shell already protected a path or
    filter containing spaces, and reconstructing the command by naive joining would strip
    that protection and advertise a command that does something different.

    The command path is reconstructed as tokens from the Click context chain before the
    entire invocation is passed through ``shlex.join``. This preserves an unusual root
    ``prog_name`` containing whitespace or shell metacharacters without collapsing the
    ordinary command hierarchy into one token.

    ``escape_flag``/``skip_params`` default to the ordinary ``--output``/``output_path``
    contract every other budgeted command uses. A command whose own ``--output`` already
    means something else (``research-package build``'s required package directory) must
    override both: skipping only its distinctly-named escape param, so the real
    ``--output <dir>`` value survives the reconstruction, and naming that escape with its
    own flag rather than colliding with ``--output``.
    """
    command_tokens: list[str] = []
    current: click.Context | None = ctx
    while current is not None:
        name = current.info_name or current.command.name
        if not name:
            raise ValueError("cannot reconstruct a Click command path without a name")
        command_tokens.append(name)
        current = current.parent
    command_tokens.reverse()

    tokens = command_tokens
    params_by_name = {param.name: param for param in ctx.command.params}

    for name, value in ctx.params.items():
        if name in skip_params:
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

    tokens.extend([escape_flag, output_hint])
    return shlex.join(tokens)
