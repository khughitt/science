from science_qa.flags import Flag, build_flag_id


def test_build_flag_id_two_sided():
    assert build_flag_id("generic", "range", "glucose", "max") == "generic/range/glucose/max"


def test_build_flag_id_no_side():
    assert build_flag_id("generic", "unique_key", "SUBJECT_ID", None) == "generic/unique_key/SUBJECT_ID/-"


def test_build_flag_id_table_level_tuple_subject():
    assert build_flag_id("generic", "exclusive_flags", "on_drug_a+on_drug_b", None) == (
        "generic/exclusive_flags/on_drug_a+on_drug_b/-"
    )


def test_flag_id_property_matches_builder():
    flag = Flag(
        source="scrna", check="threshold", subject="pct_counts_mt", side="max",
        severity="distribution", value="33.0", threshold="20", message="high mito",
    )
    assert flag.flag_id == "scrna/threshold/pct_counts_mt/max"


def test_flag_to_dict_is_json_ready():
    flag = Flag(
        source="generic", check="range", subject="glucose", side="max",
        severity="distribution", value="600", threshold="500", message="above max",
    )
    assert flag.to_dict() == {
        "flag_id": "generic/range/glucose/max",
        "source": "generic", "check": "range", "subject": "glucose", "side": "max",
        "severity": "distribution", "value": "600", "threshold": "500", "message": "above max",
    }
