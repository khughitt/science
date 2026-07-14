"""The one hypothesis-mixin vocabulary that `science_model` cannot reconcile against itself.

`capability_scope`'s vocabulary (`VALID_SCOPES`) is owned by **`science_tool`**, and `science_model`
must not import its own consumer. The mixin duplicates that vocabulary because JSON Schema cannot
import Python -- so something has to reconcile the two, and this is the only package that can see
both. Every other mixin vocabulary is reconciled in `model/tests/test_hypothesis_entity.py`, beside
the authority it mirrors.
"""

from __future__ import annotations

import json
from importlib.resources import files

from science_tool.datasets.capability_scope import VALID_SCOPES


def test_the_capability_scope_vocabulary_is_not_a_SECOND_authority() -> None:
    # The mixin hard-codes this enum. Add a scope to `CAPABILITY_SCOPE_VALUES` without regenerating
    # the mixin and every hypothesis that authors the new scope fails validation -- with an error
    # naming the enum, not the vocabulary.
    mixin = json.loads(
        (files("science_model.schemas") / "mixin-hypothesis-1.0.json").read_text(encoding="utf-8")
    )

    assert sorted(mixin["properties"]["capability_scope"]["enum"]) == sorted(VALID_SCOPES)
