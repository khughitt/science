"""Truth path for a plan's `skills_loaded`: validation, canonicalization, and
reified skill-load records materialized into the graph/provenance layer.

Mirrors `dataset_usage.py`: a frozen record with a deterministic content-hash URI.
The record's identity deliberately EXCLUDES `reason` (only `plan_id`,
`canonical_skill_id`, and the categorical `source` participate), so two loads of
the same skill under one plan collide instead of minting two nodes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

from rdflib import URIRef

from science_tool.graph.store import PROJECT_NS


@dataclass(frozen=True, slots=True)
class SkillLoadRecord:
    plan_id: str
    canonical_skill_id: str
    reason: str
    # Categorical projection source. Narrowed to the single `UsageSource` value this path emits,
    # so a caller can never mint a second identity for one (plan, skill) load by varying `source`.
    source: Literal["authored"] = "authored"

    def identity_payload(self) -> dict[str, str]:
        return {
            "plan_id": self.plan_id,
            "canonical_skill_id": self.canonical_skill_id,
            "source": self.source,
        }

    def payload(self) -> dict[str, str]:
        return {**self.identity_payload(), "reason": self.reason}


def skill_load_node_uri(record: SkillLoadRecord) -> URIRef:
    payload = json.dumps(record.identity_payload(), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return URIRef(PROJECT_NS[f"skill-load/{digest}"])
