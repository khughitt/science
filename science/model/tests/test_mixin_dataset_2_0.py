from __future__ import annotations

from science_model.entity_schema import MergePolicy, default_profile_for_kind, parse_profile, read_merge_policy


_V1 = parse_profile("science-entity-base/1.0+dataset/1.0")
_V2 = parse_profile("science-entity-base/1.0+dataset/2.0")


def test_dataset_2_declares_status_project_only() -> None:
    assert read_merge_policy(_V2)["status"] is MergePolicy.PROJECT_ONLY


def test_dataset_2_declares_dates_project_only() -> None:
    # `created`/`updated` are project_only on 2.0, matching paper/theme/topic 2.0. A dataset was
    # the one 2.0 kind that annotated status alone, so an overlay's dates raised OverlayMergeError
    # where the same overlay merged cleanly on a paper. Completed here while 2.0 is unshipped and
    # a policy fix costs no new version.
    policy = read_merge_policy(_V2)
    assert policy["created"] is MergePolicy.PROJECT_ONLY
    assert policy["updated"] is MergePolicy.PROJECT_ONLY


def test_dataset_1_keeps_its_pinned_status_semantics() -> None:
    assert read_merge_policy(_V1)["status"] is MergePolicy.REPLACE


def test_dataset_1_keeps_its_pinned_date_semantics() -> None:
    # The atomicity pin: 1.0 mentions neither date, so both resolve to default replace. A project
    # pinned to 1.0 must keep seeing that after 2.0 ships.
    policy = read_merge_policy(_V1)
    assert policy["created"] is MergePolicy.REPLACE
    assert policy["updated"] is MergePolicy.REPLACE


def test_dataset_default_moves_atomically_to_2_0() -> None:
    assert default_profile_for_kind("dataset").render() == "science-entity-base/1.0+dataset/2.0"
