from __future__ import annotations

from science_tool.validate.checks.dataset_lineage import evaluate_dataset_lineage


def _ds(id_, **kw):
    return {"_path": f"doc/datasets/{id_.split(':')[1]}.md", "type": "dataset", "id": id_, **kw}


def test_parent_dataset_unresolved_in_project_and_commons_is_error():
    # commons_cache pins the resolver: False == commons is available but lacks the id.
    results = list(
        evaluate_dataset_lineage(
            [_ds("dataset:ukb-ppp", parent_dataset="dataset:nope")], commons_cache={"dataset:nope": False}
        )
    )
    assert any(r.severity.name == "ERROR" and "does not resolve" in r.message for r in results)


def test_parent_dataset_nonlocal_with_unavailable_commons_is_info_not_error():
    # None == commons root not configured/available -> INFO, never a false ERROR.
    results = list(
        evaluate_dataset_lineage(
            [_ds("dataset:ukb-ppp", parent_dataset="dataset:commons-parent")],
            commons_cache={"dataset:commons-parent": None},
        )
    )
    assert [r.severity.name for r in results] == ["INFO"]


def test_parent_dataset_resolved_in_commons_is_clean():
    results = list(
        evaluate_dataset_lineage(
            [_ds("dataset:ukb-ppp", parent_dataset="dataset:commons-parent")],
            commons_cache={"dataset:commons-parent": True},
        )
    )
    assert results == []


def test_cycle_is_error():
    dss = [_ds("dataset:a", parent_dataset="dataset:b"), _ds("dataset:b", parent_dataset="dataset:a")]
    results = list(evaluate_dataset_lineage(dss))
    assert any(r.severity.name == "ERROR" and "cycle" in r.message.lower() for r in results)


def test_parent_may_not_be_member_of_collection_member():
    member = _ds("dataset:row", derivation={"kind": "member_of", "parent_dataset": "dataset:coll", "member_key": "k"})
    child = _ds("dataset:c", parent_dataset="dataset:row")
    results = list(evaluate_dataset_lineage([member, child]))
    assert any(r.severity.name == "ERROR" and "member_of" in r.message for r in results)


def test_non_dataset_parent_ref_is_error():
    results = list(evaluate_dataset_lineage([_ds("dataset:x", parent_dataset="collection:y")]))
    assert any(r.severity.name == "ERROR" and "must be a 'dataset:' reference" in r.message for r in results)


def test_well_formed_chain_is_clean():
    dss = [
        _ds("dataset:uk-biobank", siblings=["dataset:ukb-ppp"]),
        _ds("dataset:ukb-ppp", parent_dataset="dataset:uk-biobank"),
    ]
    assert list(evaluate_dataset_lineage(dss)) == []
