from science_tool.datasets.capability_shape import (
    capability_shape_issue,
    gen3_shape_issue,
    legacy_map_shape_issue,
)


def test_gen3_accepts_data_product_only():
    assert gen3_shape_issue([{"data_product": "data-product:x"}]) is None


def test_gen3_accepts_qualifiers():
    assert gen3_shape_issue([{"data_product": "data-product:x",
                              "qualifiers": {"cohort_design": "case-control"}}]) is None


def test_gen3_rejects_extra_top_level_key():
    assert gen3_shape_issue([{"data_product": "data-product:x", "assay": "y"}]) == "malformed"


def test_gen3_rejects_bad_data_product_pattern():
    assert gen3_shape_issue([{"data_product": "gene-expression"}]) == "malformed"


def test_gen3_rejects_empty_qualifier_value():
    assert gen3_shape_issue([{"data_product": "data-product:x", "qualifiers": {"a": ""}}]) == "malformed"


def test_gen3_missing_and_absent():
    assert gen3_shape_issue([]) == "missing"
    assert gen3_shape_issue(None) == "missing"


def test_legacy_accepts_string_map():
    assert legacy_map_shape_issue([{"assay": "x"}]) is None


def test_dispatch_by_generation():
    assert capability_shape_issue([{"assay": "x"}], generation=2) is None
    assert capability_shape_issue([{"assay": "x"}], generation=3) == "malformed"
