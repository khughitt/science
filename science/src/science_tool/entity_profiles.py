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
    ProfileString,
    SchemaLoader,
    resolve_profile,
)

from science_tool.project_config import ProjectConfig, load_project_config

SCHEMAS_DIRNAME = "schemas"


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
    """Load the schema view for `project_root`, reading `entity_extensions` from science.yaml."""
    config = config or load_project_config(project_root)
    loader = SchemaLoader(project_dir=project_root / SCHEMAS_DIRNAME)
    return ProjectSchema(
        validator=EntityValidator(loader),
        _extensions=config.entity_extensions,
        _loader=loader,
    )
