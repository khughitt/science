"""science-qa: a light, config-driven pipeline QA-check runtime.

Implements the qa: schema and structural/distribution severity split from
docs/conventions/pipeline-qa-checkpoints.md. Deliberately depends on nothing
from science_tool so a project's pipeline stays light.
"""

from __future__ import annotations
