"""The entity WRITE BOUNDARY — one mechanism, in two halves, and both halves are private.

`_prepare_write` merges, renders, and validates; `_commit_write` writes. The split is what makes
`mark_superseded`'s all-or-none claim true rather than aspirational — every rejection lands before
the first byte does.

**A public commit half would not be a hole in the boundary; it would BE a second, unvalidated
writer**, because by contract it writes whatever `.text` it is handed without re-deciding anything.
And a frozen dataclass is not unforgeable: privacy-by-underscore is a convention the interpreter
does not enforce. So the token carries an HMAC over `(entity_id, path, text)`, and the guarantee is
stated honestly — this does not make forgery *impossible* (`_SEAL_KEY` is importable by anyone
determined to), it makes it **inexpressible by accident**: not by a plausible refactor, not by a
helpful `replace()`, not by a caller who thought this was the supported path.

The tests below are the four ways in, closed.
"""

from __future__ import annotations

import dataclasses
from inspect import Parameter, signature
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from science_tool import entities
from science_tool.entities import _commit_write, _PreparedWrite, _prepare_write, edit_entity

REF = "interpretation:i-v1"


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: wb\n", encoding="utf-8")
    path = tmp_path / "entities" / "interpretations" / "i-v1.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        + yaml.safe_dump(
            {"id": REF, "kind": "interpretation", "title": "v1", "status": "active"},
            sort_keys=False,
        )
        + "---\n\nbody\n",
        encoding="utf-8",
    )
    return tmp_path


def test_a_PreparedWrite_cannot_be_CONSTRUCTED_only_earned() -> None:
    # An invalid token must fail IMMEDIATELY. Python has no private constructors, so the constructor
    # itself has to refuse anything that is not the output of `_prepare_write`.
    with pytest.raises(TypeError, match="not constructible"):
        _PreparedWrite(
            entity_id=REF,
            path=Path("x.md"),
            text="anything at all",
            warnings=(),
            seal="not-a-seal",
        )


def test_the_seal_does_NOT_TRAVEL_to_content_it_never_vouched_for(tmp_project: Path) -> None:
    # A BEARER token -- "hold this object and you are trusted" -- can be carried onto content it
    # never vouched for, with no private import at all: `replace()` copies the sentinel and re-runs
    # `__post_init__`, so an identity check on a sentinel sees the SAME trusted object and waves
    # through text that never met the validator. The seal is therefore a statement ABOUT THE PAYLOAD.
    prepared = _prepare_write(tmp_project, REF, {"title": "legitimate"})

    with pytest.raises(TypeError, match="does not travel"):
        dataclasses.replace(prepared, text="superseded_by: whatever-i-like\n")
    # And it covers the PATH, not just the bytes -- otherwise validated text could be redirected at
    # an unvalidated file.
    with pytest.raises(TypeError, match="does not travel"):
        dataclasses.replace(prepared, path=tmp_project / "entities/interpretations/0002-y.md")

    # CONTROL: the guard admits the value whose payload is unchanged. Without this, every assertion
    # above is satisfied by a boundary that refuses everything.
    assert _commit_write(prepared).entity_id == REF


def test_commit_refuses_an_object_that_only_LOOKS_prepared(tmp_project: Path) -> None:
    # The type annotation is ERASED at runtime. Attribute compatibility is not authentication.
    fake = SimpleNamespace(
        entity_id=REF,
        path=tmp_project / "entities/interpretations/i-v1.md",
        text="superseded_by: whatever-i-like\n",
        warnings=(),
        seal="irrelevant",
    )
    with pytest.raises(TypeError, match="earned from _prepare_write"):
        _commit_write(fake)  # type: ignore[arg-type]  -- the runtime boundary IS the subject


def test_commit_RECHECKS_the_seal_after_construction(tmp_project: Path) -> None:
    # CONSTRUCTION-TIME VERIFICATION IS NOT THE WRITE BOUNDARY. `frozen=True` blocks ordinary
    # assignment, not mutation through Python's object protocol -- so a legitimately prepared value
    # can still be changed AFTER its constructor check ran. The commit boundary must authenticate the
    # state it consumes, not trust a check that happened earlier.
    prepared = _prepare_write(tmp_project, REF, {"title": "legitimate"})
    object.__setattr__(prepared, "text", "superseded_by: whatever-i-like\n")

    with pytest.raises(TypeError, match="seal does not cover"):
        _commit_write(prepared)


def test_the_SEAL_is_never_a_default_and_never_exported() -> None:
    # A default would make the seal optional, which is the same as not having one.
    assert signature(_PreparedWrite).parameters["seal"].default is Parameter.empty
    exported = set(getattr(entities, "__all__", ()))
    assert {"_SEAL_KEY", "_seal", "_PreparedWrite", "_prepare_write", "_commit_write"} & exported == set()


def test_edit_entity_cannot_express_the_DERIVED_field(tmp_project: Path) -> None:
    # `superseded_by` is DERIVED. On the AUTHORED-edit surface it would recreate the second authored
    # spelling design rev 10 deleted: an author could write a resolvable `superseded_by` with NO
    # canonical edge behind it -- schema passes, resolution passes, and the entity is superseded
    # according to nothing.
    #
    # ☠️ THE VAR_KEYWORD CHECK IS THE LOAD-BEARING HALF. A `**kwargs` signature does not merely fail
    # to close the door -- it makes the named-parameter assertion ANTI-INFORMATIVE, because the
    # absence of the name is exactly what a VAR_KEYWORD signature guarantees whether or not the field
    # is reachable. A guard that passes BECAUSE the hole is open is worse than no guard.
    params = signature(edit_entity).parameters
    assert "superseded_by" not in params
    assert not any(p.kind is Parameter.VAR_KEYWORD for p in params.values())

    with pytest.raises(TypeError):
        edit_entity(tmp_project, REF, superseded_by="interpretation:i-v2")  # type: ignore[call-arg]
