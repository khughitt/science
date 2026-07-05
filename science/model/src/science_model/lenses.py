"""Packaged vocabulary of generative analytical lenses.

A lens is a *view* over a shared research idea - the analytical perspective the
idea was framed through. This module is the single source of truth for lens
slugs; schema validation, explore-ideas apply, graph materialization, and the
validation checks all read from here. Slugs are stable identifiers; names and
descriptions may evolve, but a slug change is an explicit migration, not silent
aliasing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Lens:
    slug: str
    name: str
    description: str
    kind: str = "generative-analytical"


LENSES: tuple[Lens, ...] = (
    Lens("mechanism", "Mechanism", "causal/biological mechanism and pathway"),
    Lens("methodology", "Methodology", "measurement, assay, study-design, analysis method"),
    Lens("population", "Population", "population, context, subgroup, setting, boundary conditions"),
    Lens("contrarian", "Contrarian", "what if the dominant assumption is wrong; null/negative framing"),
    Lens("analogy", "Analogy", "cross-disciplinary analogy - how an adjacent field would frame it"),
    Lens("temporal", "Temporal", "temporal/longitudinal/dynamics dimension"),
)

LENS_BY_SLUG: dict[str, Lens] = {lens.slug: lens for lens in LENSES}
LENS_SLUGS: frozenset[str] = frozenset(LENS_BY_SLUG)


def is_valid_lens(slug: str) -> bool:
    return slug in LENS_SLUGS
