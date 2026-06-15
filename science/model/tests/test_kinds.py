from __future__ import annotations

from science_model.kinds import CORE_KINDS, CORE_KINDS_BY_NAME, KindDescriptor


def test_core_kinds_have_unique_names() -> None:
    names = [k.name for k in CORE_KINDS]
    assert len(names) == len(set(names)), "duplicate kind name in CORE_KINDS"
    assert set(CORE_KINDS_BY_NAME) == set(names)
    assert all(isinstance(k, KindDescriptor) for k in CORE_KINDS)


def test_every_descriptor_sets_path_and_strategy() -> None:
    # Keystone CORE_KINDS = file-authored kinds only; all carry path+strategy.
    for k in CORE_KINDS:
        assert k.path is not None, f"{k.name} missing path"
        assert k.strategy is not None, f"{k.name} missing strategy"


def test_singleton_iff_path_is_a_file() -> None:
    for k in CORE_KINDS:
        assert k.path is not None  # narrows Path | None before .suffix
        is_file = k.path.suffix in {".md", ".yaml"}
        assert (k.strategy == "singleton") == is_file, (
            f"{k.name}: strategy/singleton mismatch (path={k.path}, strategy={k.strategy})"
        )


def test_singletons_have_no_status_vocabulary() -> None:
    for k in CORE_KINDS:
        if k.strategy == "singleton":
            assert k.statuses is None and k.default_status is None, (
                f"singleton {k.name} should not declare statuses/default_status"
            )


def test_default_status_is_a_member_of_statuses() -> None:
    for k in CORE_KINDS:
        if k.default_status is not None:
            assert k.statuses is not None, f"{k.name} has default_status but no statuses"
            assert k.default_status in k.statuses, f"{k.name} default_status {k.default_status!r} not in statuses"


def test_shortforms_are_unique_single_characters() -> None:
    shortforms = [k.shortform for k in CORE_KINDS if k.shortform is not None]
    assert all(len(s) == 1 for s in shortforms), "shortform must be a single character"
    assert len(shortforms) == len(set(shortforms)), "duplicate shortform"
