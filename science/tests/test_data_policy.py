"""Tests for the data-policy classifier SSOT."""
from pathlib import Path

from science_tool.data_policy import (
    DEFAULT_DATA_POLICY,
    DataPolicy,
    FileClass,
    classify,
)

KB = 1024


def test_payload_extension_is_payload_regardless_of_size():
    # A tiny .feather is still a payload — extension wins over size.
    assert classify(Path("data/processed/exp1/m.feather"), 10) is FileClass.PAYLOAD
    assert classify(Path("data/processed/exp1/big.feather"), 5_000_000) is FileClass.PAYLOAD


def test_known_record_under_threshold_is_record():
    assert classify(Path("data/processed/exp1/RESULTS.md"), 2 * KB) is FileClass.RECORD
    assert classify(Path("data/processed/exp1/datapackage.yaml"), 1 * KB) is FileClass.RECORD
    assert classify(Path("data/processed/exp1/qa/precision.json"), 500) is FileClass.RECORD


def test_known_record_over_threshold_is_flag():
    # Large record → FLAG (irreplaceable hand-authored? author decides).
    assert classify(Path("data/processed/exp1/RESULTS.md"), 300_000) is FileClass.FLAG


def test_unknown_large_is_payload():
    assert classify(Path("data/processed/exp1/dump.bin"), 5_000_000) is FileClass.PAYLOAD


def test_unknown_small_is_flag():
    # Bare .csv matching no record pattern is NOT auto-tracked — surfaced for decision.
    assert classify(Path("data/processed/exp1/scratch.csv"), 1 * KB) is FileClass.FLAG


def test_threshold_boundary_is_inclusive_record():
    # size == threshold counts as "under" (≤) → RECORD for a known record.
    pol = DEFAULT_DATA_POLICY
    assert classify(Path("notes-notes.md"), pol.size_threshold) is FileClass.RECORD
    assert classify(Path("notes-notes.md"), pol.size_threshold + 1) is FileClass.FLAG


def test_default_policy_values():
    assert DEFAULT_DATA_POLICY.size_threshold == 150_000
    assert ".feather" in DEFAULT_DATA_POLICY.payload_extensions


def test_custom_policy_overrides_threshold():
    pol = DataPolicy(
        record_patterns=("RESULTS*.md",),
        payload_extensions=(".feather",),
        size_threshold=10,
    )
    assert classify(Path("RESULTS.md"), 5, pol) is FileClass.RECORD
    assert classify(Path("RESULTS.md"), 20, pol) is FileClass.FLAG
