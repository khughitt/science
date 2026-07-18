from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.entities import _prepare_write_with_date


def _seed(root: Path) -> Path:
    (root / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = root / "entities" / "interpretations"
    d.mkdir(parents=True)
    p = d / "0001-x.md"
    p.write_text(
        "---\nid: interpretation:0001-x\nkind: interpretation\ntitle: x\nstatus: draft\n---\nbody\n",
        encoding="utf-8",
    )
    return p


def test_injected_updated_default_is_used_when_key_absent(tmp_path: Path) -> None:
    _seed(tmp_path)
    prepared = _prepare_write_with_date(
        tmp_path, "interpretation:0001-x", {"status": "superseded"}, updated_default="2026-07-18"
    )
    fm = yaml.safe_load(prepared.text.split("---\n", 2)[1])
    assert fm["updated"] == "2026-07-18"
    assert fm["status"] == "superseded"


def test_existing_updated_is_preserved_not_overwritten(tmp_path: Path) -> None:
    p = _seed(tmp_path)
    p.write_text(
        "---\nid: interpretation:0001-x\nkind: interpretation\ntitle: x\nstatus: draft\n"
        "updated: 2020-01-01\n---\nbody\n",
        encoding="utf-8",
    )
    prepared = _prepare_write_with_date(
        tmp_path, "interpretation:0001-x", {"status": "superseded"}, updated_default="2026-07-18"
    )
    fm = yaml.safe_load(prepared.text.split("---\n", 2)[1])
    # YAML parses an unquoted ISO date back into a `datetime.date`, not a str -- an artifact of
    # `_parse_markdown_file`'s round-trip, unrelated to this refactor. `str()` normalizes it.
    assert str(fm["updated"]) == "2020-01-01"  # setdefault preserves


def test_two_invocations_with_same_date_produce_identical_bytes(tmp_path: Path) -> None:
    _seed(tmp_path)
    a = _prepare_write_with_date(tmp_path, "interpretation:0001-x", {"status": "superseded"},
                                 updated_default="2026-07-18")
    b = _prepare_write_with_date(tmp_path, "interpretation:0001-x", {"status": "superseded"},
                                 updated_default="2026-07-18")
    assert a.text == b.text


def _seed_pinned_hypothesis(root: Path) -> None:
    # The resolution check (`_resolution_check_or_raise`) is gated on `kind in PROJECT_MIXIN_NAMES`,
    # which today is `{"hypothesis"}` only -- an `interpretation` entity never reaches it, so this
    # boundary-behavior test needs a hypothesis, not the shared `_seed` fixture. `resynthesized_into`
    # is a `_PIN_REQUIRED_FIELDS` member, so the project must be pinned to `entity_schema_version: 2`
    # or the SCHEMA gate (not the resolution gate this test targets) would refuse it first.
    (root / "science.yaml").write_text(
        yaml.safe_dump({"name": "t", "id": "t", "entity_schema_version": 2}), encoding="utf-8"
    )
    d = root / "entities" / "hypotheses"
    d.mkdir(parents=True)
    frontmatter = {
        "id": "hypothesis:0001-x",
        "kind": "hypothesis",
        "title": "H 0001-x",
        "status": "active",
        "created": "2026-07-01",
        "updated": "2026-07-01",
    }
    (d / "0001-x.md").write_text(
        f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n\nBody.\n", encoding="utf-8"
    )


def test_write_boundary_is_retained_dangling_successor_is_refused(tmp_path: Path) -> None:
    # Reaches the RESOLUTION boundary specifically (entities.py:1083), one of the three checks the
    # refactor must retain. `superseded_by` is DERIVED (only `_prepare_supersession` can pass it), so
    # the field a human writer can dangle is `resynthesized_into` -- see
    # `test_edit_entity_refuses_a_DANGLING_successor` in test_hypothesis_consumers.py. This mirrors
    # that call directly against the injectable writer, proving the prospective-write wall survived
    # the extraction.
    _seed_pinned_hypothesis(tmp_path)
    with pytest.raises(Exception, match="9999-nope"):
        _prepare_write_with_date(
            tmp_path,
            "hypothesis:0001-x",
            {"status": "superseded", "resynthesized_into": ["hypothesis:9999-nope"]},
            updated_default="2026-07-18",
        )


def test_prepare_write_legacy_wrapper_injects_today(tmp_path: Path) -> None:
    # The legacy _prepare_write must still exist and default `updated` to today's date.
    from datetime import date

    from science_tool.entities import _prepare_write
    _seed(tmp_path)
    prepared = _prepare_write(tmp_path, "interpretation:0001-x", {"status": "superseded"})
    fm = yaml.safe_load(prepared.text.split("---\n", 2)[1])
    assert fm["updated"] == date.today().isoformat()


def test_all_three_boundary_checks_run_in_order(tmp_path: Path, monkeypatch) -> None:
    # I6: prove the refactor RETAINS all three boundary checks — schema gate, prospective-corpus,
    # successor-resolution — and runs them in the documented order (cheapest authority first). Each
    # spy calls through, so behavior is unchanged; only the call order is recorded.
    import science_tool.entities as e
    _seed(tmp_path)
    order: list[str] = []
    for name in ("_schema_gate_or_raise", "_validate_prospective_write", "_resolution_check_or_raise"):
        real = getattr(e, name)

        def make(n: str, r):
            def spy(*a, **k):
                order.append(n)
                return r(*a, **k)
            return spy

        monkeypatch.setattr(e, name, make(name, real))
    _prepare_write_with_date(tmp_path, "interpretation:0001-x", {"status": "superseded"},
                             updated_default="2026-07-18")
    assert order == ["_schema_gate_or_raise", "_validate_prospective_write", "_resolution_check_or_raise"]


def test_each_boundary_check_is_load_bearing_in_both_prepare_routes(tmp_path: Path, monkeypatch) -> None:
    # I6 / design §480: each of the three boundary checks is LOAD-BEARING — forcing any one to raise
    # aborts the write, through BOTH the injectable writer (preview + apply-plan route) and the legacy
    # `_prepare_write`. Together with the ordering spy above and the dangling-successor behavioral test
    # below, this proves the extraction refuses an illegal corpus write on every route, not just runs
    # the checks.
    import science_tool.entities as e
    from science_tool.entities import _prepare_write

    class _Boom(Exception):
        pass

    _seed(tmp_path)
    for gate in ("_schema_gate_or_raise", "_validate_prospective_write", "_resolution_check_or_raise"):
        def boom(*a, _g=gate, **k):
            raise _Boom(_g)

        monkeypatch.setattr(e, gate, boom)
        with pytest.raises(_Boom):
            _prepare_write_with_date(tmp_path, "interpretation:0001-x", {"status": "superseded"},
                                     updated_default="2026-07-18")
        with pytest.raises(_Boom):
            _prepare_write(tmp_path, "interpretation:0001-x", {"status": "superseded"})
        monkeypatch.undo()


def test_present_but_empty_updated_is_preserved_by_the_writer(tmp_path: Path, monkeypatch) -> None:
    # design §9 (`updated` presence semantics, render layer): a present-but-empty `updated` is
    # preserved by presence, NOT replaced with the injected default — `setdefault` only fills an
    # ABSENT key. (The schema boundary separately REJECTS an empty date on a schema-backed project;
    # that is a different layer, neutralized here to isolate the render behavior.)
    import science_tool.entities as e
    p = _seed(tmp_path)
    p.write_text(
        "---\nid: interpretation:0001-x\nkind: interpretation\ntitle: x\nstatus: draft\n"
        "updated: ''\n---\nbody\n",
        encoding="utf-8")
    monkeypatch.setattr(e, "_schema_gate_or_raise", lambda *a, **k: None)
    monkeypatch.setattr(e, "_validate_prospective_write", lambda **k: ([], object()))
    monkeypatch.setattr(e, "_resolution_check_or_raise", lambda *a, **k: None)
    prepared = _prepare_write_with_date(tmp_path, "interpretation:0001-x", {"status": "superseded"},
                                        updated_default="2026-07-18")
    fm = yaml.safe_load(prepared.text.split("---\n", 2)[1])
    assert fm["updated"] == ""  # empty value preserved, NOT overwritten with 2026-07-18
