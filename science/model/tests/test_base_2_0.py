"""`science-entity-base-2.0` — the base that admits project-authored kinds.

WHY A NEW BASE AT ALL. Profile composition is a pure `allOf` (`validator.py:82-87`), and **an
`allOf` can only NARROW**. Base 1.0 enum-locks `kind` to `[dataset, paper, topic, theme]` and pins
`id` to `^(dataset|paper|topic|theme):…`. No mixin, and no extension, can widen either — so
`hypothesis` cannot be expressed under base 1.0 no matter what is added to it. The bump is forced by
the composition model, not chosen.

WHY A PATTERN, NOT AN ENUM. There are ~50 core kinds. An enum would have to be edited every time a
kind is added — mutating a *versioned* schema, which is the one thing versioning exists to forbid.
So the base constrains `kind` **syntactically** and each mixin supplies the exact `const`. Adding a
kind means adding a mixin; base 2.0 is never touched again.

WHY THAT IS SAFE. Every mixin already pins its own kind (`mixin-dataset-1.0.json` has
`"kind": {"const": "dataset"}`), and `validate_as` rejects a base-only profile — so a mixin is
always present. **The base's job is shape; the mixin's job is identity.** That argument is executed
in `test_project_profiles.py::test_a_mixin_const_still_narrows_the_kind_under_base_2`, which needs
`validate_as` and therefore lives in the task that introduces it.

WHY COMMONS DOES NOT MOVE. 369 live commons records pin `science-entity-base/1.0`. They stay there.
Two base versions coexisting is what versioning is *for* — zero commons churn.
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any


def _load(name: str) -> dict[str, Any]:
    return json.loads((files("science_model.schemas") / name).read_text(encoding="utf-8"))


def test_base_2_0_constrains_kind_syntactically_not_by_enum() -> None:
    kind = _load("science-entity-base-2.0.json")["properties"]["kind"]

    assert "enum" not in kind
    assert kind["pattern"] == "^[a-z][a-z0-9-]*$"


def test_base_2_0_does_not_require_version_or_schema_profile() -> None:
    # `version` is a COMMONS concept: semver on a record that travels between repos. A project
    # entity is versioned by the git history of the repo that contains it.
    # `schema_profile` is DERIVED for project kinds (`default_profile_for_kind`), not authored --
    # commons records carry it because the profile must travel with the record.
    required = _load("science-entity-base-2.0.json")["required"]

    assert sorted(required) == ["created", "id", "kind", "title", "updated"]


def test_base_2_0_admits_the_id_shapes_the_corpus_ACTUALLY_uses() -> None:
    # Base 1.0 caps the id suffix at 64 chars and forbids `.` and `_`. Real hypothesis slugs blow
    # straight through that: `0009-local-structure-globalization-obstruction` is 45, and longer ones
    # exist. A base that rejects the corpus it is meant to admit is not a migration, it is an outage.
    import re

    pattern = re.compile(_load("science-entity-base-2.0.json")["properties"]["id"]["pattern"])

    assert pattern.match("hypothesis:0009-local-structure-globalization-obstruction")
    assert pattern.match("dataset:opentargets-associations")
    assert not pattern.match("hypothesis:")  # a prefix with no suffix is not an id
    assert not pattern.match("0009-no-prefix")


def test_base_1_0_is_UNTOUCHED() -> None:
    # 369 live commons records pin base 1.0. If this fails, they are the blast radius.
    base1 = _load("science-entity-base-1.0.json")

    assert base1["properties"]["kind"]["enum"] == ["dataset", "paper", "topic", "theme"]
    assert "version" in base1["required"]
    assert "schema_profile" in base1["required"]


def test_base_2_0_keeps_schema_profile_and_version_as_OPTIONAL_properties() -> None:
    # Deliberate, and load-bearing for Task 6: the base cannot FORBID these -- it is shared, and
    # commons records legitimately author both. So "derived, never authored" cannot be said here;
    # `mixin-hypothesis` must say it, with `"schema_profile": false` / `"version": false`.
    # Recorded as a test so a later "cleanup" cannot delete them from the base and quietly move the
    # prohibition to a layer that does not apply to commons.
    properties = _load("science-entity-base-2.0.json")["properties"]

    assert properties["schema_profile"]["type"] == "string"
    assert properties["version"]["type"] == "string"


def test_the_merge_annotations_survive_the_copy() -> None:
    # `science:merge` drives commons overlay merging. A base 2.0 that silently dropped an
    # annotation would change merge SEMANTICS while looking like a copy.
    base1 = _load("science-entity-base-1.0.json")
    base2 = _load("science-entity-base-2.0.json")

    def merges(schema: dict[str, Any]) -> dict[str, str]:
        return {
            name: spec["science:merge"]
            for name, spec in schema["properties"].items()
            if isinstance(spec, dict) and "science:merge" in spec
        }

    assert merges(base2) == merges(base1)
    assert base2["$defs"] == base1["$defs"]
