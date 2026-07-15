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
from pathlib import Path

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

# The version a project must DECLARE before any of this is applied to its files.
ENTITY_SCHEMA_VERSION = 2


class EntityExtensionsError(ValueError):
    """`science.yaml` declares an entity extension that cannot be honored."""


@dataclass(frozen=True, slots=True)
class ProjectSchema:
    """A project's view of the entity schema system: its extensions, and a loader that finds them."""

    validator: EntityValidator
    _extensions: dict[str, list[str]]
    _loader: SchemaLoader

    def profile_for(self, kind: str) -> ProfileString:
        """The profile for `kind` in THIS project — core, plus whatever the project declares."""
        return resolve_profile(
            kind, extensions=self._extensions.get(kind, []), loader=self._loader
        )


def load_project_schema(
    project_root: Path, config: ProjectConfig | None = None
) -> ProjectSchema:
    """Load the schema view for `project_root`, reading `entity_extensions` from science.yaml.

    Every declared entry is resolved EAGERLY. A stanza is a claim about how this project's entities
    are validated; a claim nobody reads is not a claim. `hypothsis:` -- one letter out -- would
    otherwise sit in `science.yaml` forever, matching no kind, silently validating nothing, and
    looking exactly like a project whose fields are protected.
    """
    config = config or load_project_config(project_root)
    schemas_dir = project_root / SCHEMAS_DIRNAME
    loader = SchemaLoader(project_dir=schemas_dir)
    schema = ProjectSchema(
        validator=EntityValidator(loader),
        _extensions=config.entity_extensions,
        _loader=loader,
    )
    _certify_declarations(config.entity_extensions, schemas_dir, schema)
    return schema


def load_project_schema_if_pinned(project_root: Path) -> ProjectSchema | None:
    """The project's composed schema — or None if it has not DECLARED `entity_schema_version: 2`.

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
    if validated_entity_schema_version(raw) != ENTITY_SCHEMA_VERSION:
        return None
    return load_project_schema(project_root, load_project_config(project_root))


def _certify_declarations(
    extensions: dict[str, list[str]], schemas_dir: Path, schema: ProjectSchema
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
            path = schemas_dir / filename_for(component)
            if not path.is_file():
                raise EntityExtensionsError(
                    f"science.yaml declares entity extension {raw!r} for kind {kind!r}, but "
                    f"{path} does not exist. A project extension must be a schema this project "
                    "owns; there is no fallback to a packaged extension."
                )

        try:
            schema.profile_for(kind)
        except ProfileParseError as exc:
            raise EntityExtensionsError(
                f"science.yaml: entity_extensions declares kind {kind!r}, which is not a known "
                f"entity kind ({exc})."
            ) from exc
