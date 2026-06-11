import pytest

from science_qa.config import QAConfig, QAConfigError


def test_loads_full_qa_block(tmp_path):
    cfg = tmp_path / "qa.yaml"
    cfg.write_text(
        "qa:\n"
        "  unique_key: SUBJECT_ID\n"
        "  required_complete: [stratum, psu]\n"
        "  categoricals:\n"
        "    stage: {allowed: [1, 2, 3]}\n"
        "  exclusive_flags: [[on_drug_a, on_drug_b]]\n"
        "  ranges:\n"
        "    glucose: {min: 30, max: 500}\n"
        "  missing_sentinels: [-9]\n"
        "  packs: [scrna]\n"
        "  pack_params:\n"
        "    scrna: {max_mito_pct: 20}\n"
    )
    config = QAConfig.from_file(cfg)
    assert config.unique_key == "SUBJECT_ID"
    assert config.required_complete == ["stratum", "psu"]
    assert config.categoricals == {"stage": {"allowed": [1, 2, 3]}}
    assert config.exclusive_flags == [["on_drug_a", "on_drug_b"]]
    assert config.ranges == {"glucose": {"min": 30, "max": 500}}
    assert config.missing_sentinels == [-9]
    assert config.packs == ["scrna"]
    assert config.pack_params == {"scrna": {"max_mito_pct": 20}}


def test_missing_qa_block_is_error(tmp_path):
    cfg = tmp_path / "qa.yaml"
    cfg.write_text("other: {}\n")
    with pytest.raises(QAConfigError, match="no 'qa:' block"):
        QAConfig.from_file(cfg)


def test_absent_file_is_error(tmp_path):
    with pytest.raises(QAConfigError, match="not found"):
        QAConfig.from_file(tmp_path / "missing.yaml")


def test_empty_qa_block_yields_empty_config(tmp_path):
    cfg = tmp_path / "qa.yaml"
    cfg.write_text("qa: {}\n")
    config = QAConfig.from_file(cfg)
    assert config.unique_key is None
    assert config.required_complete == []
    assert config.packs == []
