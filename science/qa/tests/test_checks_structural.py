import pandas as pd

from science_qa.config import QAConfig
from science_qa.checks import run_structural_checks


def _ids(flags):
    return sorted(f.flag_id for f in flags)


def test_unique_key_violation_is_structural():
    table = pd.DataFrame({"SUBJECT_ID": [1, 1, 2]})
    flags = run_structural_checks(table, QAConfig(unique_key="SUBJECT_ID"))
    assert _ids(flags) == ["generic/unique_key/SUBJECT_ID/-"]
    assert flags[0].severity == "structural"


def test_unique_key_ok_yields_no_flag():
    table = pd.DataFrame({"SUBJECT_ID": [1, 2, 3]})
    assert run_structural_checks(table, QAConfig(unique_key="SUBJECT_ID")) == []


def test_required_complete_missing_value_flags():
    table = pd.DataFrame({"stratum": [1, None, 3]})
    flags = run_structural_checks(table, QAConfig(required_complete=["stratum"]))
    assert _ids(flags) == ["generic/required_complete/stratum/-"]


def test_categorical_allowed_violation_flags():
    table = pd.DataFrame({"stage": [1, 2, 9]})
    cfg = QAConfig(categoricals={"stage": {"allowed": [1, 2, 3]}})
    flags = run_structural_checks(table, cfg)
    assert _ids(flags) == ["generic/allowed/stage/-"]


def test_categorical_allowed_from_registry_subset(tmp_path):
    registry = tmp_path / "contrasts.csv"
    registry.write_text("name\na\nb\n")
    table = pd.DataFrame({"contrast": ["a", "z"]})
    cfg = QAConfig(categoricals={"contrast": {"allowed_from": f"{registry}#name"}})
    flags = run_structural_checks(table, cfg, base_dir=tmp_path)
    assert _ids(flags) == ["generic/allowed/contrast/-"]


def test_exclusive_flags_cooccurrence():
    table = pd.DataFrame({"on_drug_a": [1, 0], "on_drug_b": [1, 0]})
    cfg = QAConfig(exclusive_flags=[["on_drug_a", "on_drug_b"]])
    flags = run_structural_checks(table, cfg)
    assert _ids(flags) == ["generic/exclusive_flags/on_drug_a+on_drug_b/-"]


def test_missing_sentinel_survivor_flags():
    table = pd.DataFrame({"age": [40, -9, 55]})
    flags = run_structural_checks(table, QAConfig(missing_sentinels=[-9]))
    assert _ids(flags) == ["generic/missing_sentinel/age/-"]


def test_config_column_absent_raises():
    import pytest
    from science_qa.checks import QACheckError
    table = pd.DataFrame({"other": [1]})
    with pytest.raises(QACheckError, match="SUBJECT_ID"):
        run_structural_checks(table, QAConfig(unique_key="SUBJECT_ID"))
