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

from science_model.entity_schema import (
    EntityValidator,
    ProfileParseError,
    ProfileString,
    SchemaLoader,
    filename_for,
    parse_component,
    resolve_profile,
)

from science_tool.project_config import ProjectConfig, load_project_config

SCHEMAS_DIRNAME = "schemas"


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
