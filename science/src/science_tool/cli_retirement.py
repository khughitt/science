"""Which CLI commands are retired, and what replaces them.

This module is the sole declaration of that fact. Two consumers derive from it: the CLI
registers the manifests as real commands, and ``budget/registry.py`` computes its
retired exemptions from ``RETIREMENTS`` rather than repeating the list.

The classes here are the *enforcement mechanism*, not the declaration. A retired command
must be unreachable by discovery (``hidden=True``, no parameters) and must answer before
click validates anything (``parse_args``), because the defect this replaces was a
retirement message that only appeared once the caller had already constructed a
completely correct invocation.
"""

from __future__ import annotations

import click

#: Shared by the five retired inquiry mutators. The slug is deliberately absent: the
#: error fires before parsing, so we have not read one, and the caller supplied it.
INQUIRY_MUTATION_FORWARD = (
    "Edit the inquiry's patch source under `entities/patches/`, then run `science graph build`."
)

_GRAPH_BUILD = "then run `science graph build`."

#: Invocation path -> the complete message tail after "<path> is retired. ".
#:
#: Each value is the whole tail, including the trailing build step. An earlier design
#: factored that step into a shared formatter; keeping it inline lets a message that
#: should NOT end in a build step say so, and keeps these strings byte-identical to what
#: the previous per-command helpers emitted.
RETIREMENTS: dict[str, str] = {
    "inquiry add-node": INQUIRY_MUTATION_FORWARD,
    "inquiry add-edge": INQUIRY_MUTATION_FORWARD,
    "inquiry add-assumption": INQUIRY_MUTATION_FORWARD,
    "inquiry add-transformation": INQUIRY_MUTATION_FORWARD,
    "inquiry set-estimand": INQUIRY_MUTATION_FORWARD,
    "graph migrate-addresses": f"Address direction is canonical at build, {_GRAPH_BUILD}",
    "graph stamp-revision": f"The compiler stamps revisions, {_GRAPH_BUILD}",
    "graph import": f"Raw-triple import is retired; author the source records, {_GRAPH_BUILD}",
    "graph add concept": (
        "Run `science entity create concept <title>` "
        f"(or edit entities/concepts/<slug>.md), {_GRAPH_BUILD}"
    ),
    "graph add article": (
        "Run `science entity create paper <title> --id <citekey>` "
        f"(or edit entities/papers/<citekey>.md with a doi: field), {_GRAPH_BUILD}"
    ),
    "graph add proposition": f"Run `science propositions create <title>`, {_GRAPH_BUILD}",
    "graph add observation": f"Run `science entity create observation <title>`, {_GRAPH_BUILD}",
    "graph add evidence": (
        "Run `science evidence-lines create --target <ref> --stance <supports|disputes>`, "
        f"{_GRAPH_BUILD}"
    ),
    "graph add hypothesis": f"Run `science hypotheses create <title>`, {_GRAPH_BUILD}",
    "graph add question": f"Run `science questions create <title>`, {_GRAPH_BUILD}",
    "graph add edge": (
        "Author the relation in `relations.yaml` (or `relations:` frontmatter) with the "
        f"target graph_layer; claim-cited edges use inquiry flow_edges, {_GRAPH_BUILD}"
    ),
    "graph add finding": f"Run `science entity create finding <title>`, {_GRAPH_BUILD}",
    "graph add interpretation": f"Run `science interpretations create <title>`, {_GRAPH_BUILD}",
    "graph add discussion": f"Run `science discussions create <title>`, {_GRAPH_BUILD}",
    "graph add falsification": (
        "Run `science entity create falsification <title>` "
        f"(set falsifies: to the proposition ref), {_GRAPH_BUILD}"
    ),
    "graph add story": (
        "Run `science entity create story <title>` "
        f"(author synthesizes/organizedBy edges in relations.yaml), {_GRAPH_BUILD}"
    ),
    "graph add mechanism": f"Run `science entity create mechanism <title>`, {_GRAPH_BUILD}",
}

#: Groups retired in their own right, for the cases where no child is named.
#:
#: The text names executable replacements rather than a category. Because the group is
#: hidden, this message is the only thing an agent working from an old transcript sees
#: for a name that no longer resolves -- telling it what it may not do without telling it
#: what to do would reproduce, one level up, the defect this module exists to remove.
RETIRED_GROUPS: dict[str, str] = {
    "graph add": (
        "Author the entity instead — `science entity create <kind> <title>`, or a typed "
        "wrapper such as `science hypotheses create <title>`; author edges in "
        "`relations.yaml` or `relations:` frontmatter. Then run `science graph build`."
    ),
}


class RetiredCommand(click.Command):
    """A command that exists only to name its replacement."""

    def __init__(self, name: str, *, path: str, forward: str) -> None:
        super().__init__(name, params=[], hidden=True, help=f"Retired. {forward}")
        self.path = path
        self.forward = forward

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        if ctx.resilient_parsing:
            return super().parse_args(ctx, args)
        raise click.ClickException(f"{self.path} is retired. {self.forward}")


class RetiredGroup(click.Group):
    """A group whose every child is retired, answering for the cases naming no child."""

    def __init__(self, name: str, *, path: str, forward: str, **kwargs: object) -> None:
        super().__init__(name, hidden=True, **kwargs)  # type: ignore[arg-type]
        self.path = path
        self.forward = forward

    def _message(self) -> str:
        return f"{self.path} is retired. {self.forward}"

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        if ctx.resilient_parsing:
            return super().parse_args(ctx, args)
        if not args or args[0] in ("-h", "--help"):
            raise click.ClickException(self._message())
        return super().parse_args(ctx, args)

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            # Naming a command that does not exist is a usage error: UsageError exits 2,
            # ClickException exits 1, and downgrading that would change the contract for
            # every mistyped subcommand.
            raise click.UsageError(self._message(), ctx) from None


def _resolve_parent(root: click.Group, parts: list[str]) -> click.Group:
    node: click.Command = root
    for part in parts:
        if not isinstance(node, click.Group):
            raise RuntimeError(f"cannot attach retirement: {node.name!r} is not a group")
        child = node.commands.get(part)
        if child is None:
            raise RuntimeError(f"cannot attach retirement: no command {part!r} under {node.name!r}")
        node = child
    if not isinstance(node, click.Group):
        # The loop only checks nodes it must descend *through*; the terminal node is
        # never tested by it. Without this, a manifest path naming a leaf as a parent
        # returns a Command and fails later with AttributeError on .add_command --
        # far from the malformed declaration that caused it.
        raise RuntimeError(f"cannot attach retirement: {node.name!r} is not a group")
    return node


def register_retirements(root: click.Group) -> None:
    """Attach every declared retirement to the live command tree.

    Groups first: a retired leaf may name a retired group as its parent.
    """
    for path, forward in RETIRED_GROUPS.items():
        *parent_parts, name = path.split()
        parent = _resolve_parent(root, parent_parts)
        existing = parent.commands.get(name)
        if existing is not None:
            raise RuntimeError(
                f"cannot attach retirement {path!r}: existing command {existing.name!r}"
            )
        parent.add_command(RetiredGroup(name, path=path, forward=forward))
    for path, forward in RETIREMENTS.items():
        *parent_parts, name = path.split()
        parent = _resolve_parent(root, parent_parts)
        existing = parent.commands.get(name)
        if existing is not None:
            raise RuntimeError(
                f"cannot attach retirement {path!r}: existing command {existing.name!r}"
            )
        parent.add_command(RetiredCommand(name, path=path, forward=forward))
