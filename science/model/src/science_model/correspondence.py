"""Evidence-broker correspondence results.

This leaf deliberately imports no ``science_model`` module. ``CorrespondenceQualifiers`` in the
toolkit's validate package is an unrelated spec-1 finding identity and is not this result.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


class Correspondence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["verified", "violated", "unwired"]
    code: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def _code_matches_status(self) -> "Correspondence":
        if self.status == "verified":
            if self.code is not None:
                raise ValueError("verified correspondence must not carry a code")
        elif not self.code:
            raise ValueError(f"{self.status} correspondence requires a code")
        return self
