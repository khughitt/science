"""Bind a project's declared entity extensions to the schema layer.

A project owns fields that are its alone — mm30's assessment labels, evolution's source
provenance. It declares them in `science.yaml`:

```yaml
entity_extensions:
  hypothesis: ["mm30.assessment/1.0"]   # -> schemas/extension-mm30-assessment-1.0.json
```

The profile and the loader are handed out **together**, as one object, because they are only
correct together: a profile resolved WITH extensions but validated through a package-only loader
raises `SchemaNotFoundError` on a schema the project does own, and a package-only profile validated
through a project loader silently ignores the extension entirely. Pairing them here means a caller
cannot hold one without the other.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import yaml

from science_model.entity_schema import (
    EntityValidator,
    ProfileParseError,
    ProfileString,
    SchemaLoader,
    filename_for,
    parse_component,
    resolve_profile,
)
from science_model.frontmatter import project_config_path

from science_tool.project_config import (
    ProjectConfig,
    load_project_config,
    validated_entity_schema_version,
)

SCHEMAS_DIRNAME = "schemas"

# The generations that ARM schema-first validation. A project DECLARES one of these as its
# `entity_schema_version` before any of this is applied to its files; absent or 1 means unmigrated
# and is left untouched. Each armed generation selects a whole mixin-version row via the generation
# matrix (science_model.entity_schema.profile).
ARMED_SCHEMA_GENERATIONS = frozenset({2, 3})


class EntityExtensionsError(ValueError):
    """`science.yaml` declares an entity extension that cannot be honored."""


@dataclass(frozen=True, slots=True)
class ProjectSchema:
    """A project's view of the entity schema system: its extensions, and a loader that finds them."""

    validator: EntityValidator
    _extensions: dict[str, list[str]]
    _loader: SchemaLoader
    _generation: int = 2

    def profile_for(self, kind: str) -> ProfileString:
        """The profile for `kind` in THIS project — core, plus whatever the project declares."""
        return resolve_profile(
            kind,
            extensions=self._extensions.get(kind, []),
            loader=self._loader,
            generation=self._generation,
        )


def load_project_schema(
    project_root: Path, config: ProjectConfig | None = None, *, generation: int = 2
) -> ProjectSchema:
    """Load the schema view for `project_root`, reading `entity_extensions` from science.yaml.

    Every declared entry is resolved EAGERLY. A stanza is a claim about how this project's entities
    are validated; a claim nobody reads is not a claim. `hypothsis:` -- one letter out -- would
    otherwise sit in `science.yaml` forever, matching no kind, silently validating nothing, and
    looking exactly like a project whose fields are protected.
    """
    config = config or load_project_config(project_root)
    schemas_dir = project_root / SCHEMAS_DIRNAME
    schema = _assemble_project_schema(
        config.entity_extensions,
        loader=SchemaLoader(project_dir=schemas_dir),
        generation=generation,
    )
    _certify_declarations(
        config.entity_extensions,
        schema,
        owns_schema=lambda filename: (schemas_dir / filename).is_file(),
        schema_location=lambda filename: str(schemas_dir / filename),
    )
    return schema


def project_schema_from_documents(
    *,
    extensions: Mapping[str, list[str]],
    schema_documents: Mapping[str, dict[str, Any]],
    generation: int,
) -> ProjectSchema:
    """Build a project schema from already-read extension documents.

    The caller owns I/O. Descriptor-anchored readers can therefore supply bytes
    read without pathname reopens while sharing the same composition and eager
    declaration certification as the ordinary project loader.
    """
    extension_map = {kind: list(components) for kind, components in extensions.items()}
    documents = dict(schema_documents)
    schema = _assemble_project_schema(
        extension_map,
        loader=SchemaLoader(project_schemas=documents),
        generation=generation,
    )
    _certify_declarations(
        extension_map,
        schema,
        owns_schema=documents.__contains__,
        schema_location=lambda filename: f"{SCHEMAS_DIRNAME}/{filename}",
    )
    return schema


def _assemble_project_schema(
    extensions: dict[str, list[str]],
    *,
    loader: SchemaLoader,
    generation: int,
) -> ProjectSchema:
    return ProjectSchema(
        validator=EntityValidator(loader),
        _extensions=extensions,
        _loader=loader,
        _generation=generation,
    )


def load_project_schema_if_pinned(project_root: Path) -> ProjectSchema | None:
    """The project's composed schema — or None if its declared `entity_schema_version` is not armed.

    ONE gate, shared by the LOAD path (`graph/sources.py`) and the WRITE path (`entities.py`). The
    pin is the authority and the file shape never is, so "does this project speak schema 2?" must
    have exactly one answer: a writer that answered it differently from the loader would validate
    writes against a schema the loader does not enforce, or refuse writes the loader would accept.

    THE SHAPE HEURISTIC IS NOT A FALLBACK, it is the bug. natural-systems — the project that opened
    this arc — authored `status: retired` and `status: active` onto UNMIGRATED hypotheses, where
    `retired` MEANT `refuted`. Every one of those is a lifecycle word, so a "does it look migrated?"
    test calls the corpus migrated and reads its verdicts as closures.

    ☠️ THE PIN DECISION COMES FROM THE ONE NARROW AUTHORITY, `validated_entity_schema_version`, which
    the LOAD path reads it through too. An earlier revision compared a raw-YAML read to `2` here --
    cheaper, and it routed straight around the key AND value checks. `entity_schema_verison: 2` (a
    typo) or `entity_schema_version: "2"` (a stray quote) then parsed as "no pin", every schema check
    on the write path went quietly silent, and the project was left believing it had migrated. That is
    not a degraded read of the pin; it is the fail-silent the pin exists to abolish. A near-miss key or
    an illegal value must FAIL, never fall back to "unpinned". `load_project_config` runs only once the
    authority has ruled the project PINNED -- it is how the entity_extensions are read, not a second
    opinion on the pin.
    """
    path = project_config_path(project_root)
    if not path.is_file():
        return None  # no config at all is not a typo — it is a project that never claimed anything
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    version = validated_entity_schema_version(raw)
    if version not in ARMED_SCHEMA_GENERATIONS:
        return None
    return load_project_schema(
        project_root, load_project_config(project_root), generation=version
    )


def _certify_declarations(
    extensions: Mapping[str, list[str]],
    schema: ProjectSchema,
    *,
    owns_schema: Callable[[str], bool],
    schema_location: Callable[[str], str],
) -> None:
    for kind, components in extensions.items():
        for raw in components:
            try:
                component = parse_component(raw)
            except ProfileParseError as exc:
                raise EntityExtensionsError(
                    f"science.yaml: entity_extensions[{kind!r}] entry {raw!r} is malformed: {exc}"
                ) from exc

            # A project's extension MUST be a schema the project OWNS. There is deliberately no
            # fallback to a packaged extension: the loader searches the project dir first, so a
            # silent fallback would mean a project whose schema file is missing or misnamed quietly
            # validates against a TOOLKIT schema of the same name -- a field it does not own,
            # governed by a contract it cannot see. Packaged extensions (`bio.*`) belong to commons
            # records, which carry their own `schema_profile` and never come through here.
            filename = filename_for(component)
            if not owns_schema(filename):
                raise EntityExtensionsError(
                    f"science.yaml declares entity extension {raw!r} for kind {kind!r}, but "
                    f"{schema_location(filename)} does not exist. A project extension must be a schema this project "
                    "owns; there is no fallback to a packaged extension."
                )

        try:
            schema.profile_for(kind)
        except ProfileParseError as exc:
            raise EntityExtensionsError(
                f"science.yaml: entity_extensions declares kind {kind!r}, which is not a known "
                f"entity kind ({exc})."
            ) from exc
