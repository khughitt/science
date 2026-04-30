import pytest

from science_tool.addressing import Address, is_address, parse_address, render_uri


def test_parse_simple_question() -> None:
    address = parse_address("cbioportal:q014")
    assert address == Address(project_id="cbioportal", artifact_id="q014")


def test_parse_path_artifact() -> None:
    address = parse_address("cbioportal:topics/clonal-hematopoiesis-contamination")
    assert address.artifact_id == "topics/clonal-hematopoiesis-contamination"


def test_render_uri() -> None:
    address = Address(project_id="multiple-myeloma", artifact_id="h003")
    assert render_uri(address) == "<cancer://multiple-myeloma/h003>"


def test_is_address_positive() -> None:
    assert is_address("evolution:t012") is True


def test_is_address_negative() -> None:
    assert is_address("not an address") is False
    assert is_address("just-a-word") is False
    assert is_address("a:") is False
    assert is_address(":x") is False


def test_parse_invalid_raises() -> None:
    with pytest.raises(ValueError):
        parse_address("not an address")
