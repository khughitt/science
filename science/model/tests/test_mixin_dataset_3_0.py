import json
from pathlib import Path
from jsonschema import Draft202012Validator

SCHEMAS = Path(__file__).resolve().parents[1] / "src" / "science_model" / "schemas"


def _schema():
    return json.loads((SCHEMAS / "mixin-dataset-3.0.json").read_text())


def _base(**caps):
    return {"id": "dataset:demo", "kind": "dataset", "origin": "derived", "tier": "track",
            "datapackage": "dp",
            "derivation": {"kind": "member_of", "parent_dataset": "dataset:parent", "member_key": "k"},
            **caps}


def test_object_capability_validates():
    Draft202012Validator(_schema()).validate(_base(provided_capabilities=[
        {"data_product": "data-product:gene-expression-bulk-rna",
         "qualifiers": {"cohort_design": "case-control"}}]))


def test_legacy_string_capability_is_rejected():
    errors = list(Draft202012Validator(_schema()).iter_errors(
        _base(provided_capabilities=["gene-expression"])))
    assert errors


def test_unknown_key_in_capability_is_rejected():
    errors = list(Draft202012Validator(_schema()).iter_errors(_base(provided_capabilities=[
        {"data_product": "data-product:gene-expression", "assay": "x"}])))
    assert errors


def test_2_0_still_types_strings():
    two = json.loads((SCHEMAS / "mixin-dataset-2.0.json").read_text())
    assert two["properties"]["provided_capabilities"]["items"] == {"type": "string"}
