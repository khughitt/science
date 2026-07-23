import json
from pathlib import Path
from jsonschema import Draft202012Validator

SCHEMAS = Path(__file__).resolve().parents[1] / "src" / "science_model" / "schemas"


def _schema():
    return json.loads((SCHEMAS / "mixin-hypothesis-2.0.json").read_text())


def _base(caps):
    return {"id": "hypothesis:0001", "kind": "hypothesis", "status": "active",
            "required_capabilities": caps}


def test_object_required_capability_validates():
    Draft202012Validator(_schema()).validate(_base([
        {"data_product": "data-product:gene-expression",
         "qualifiers": {"analysis_role": "mr_exposure"}}]))


def test_legacy_string_map_capability_is_rejected():
    assert list(Draft202012Validator(_schema()).iter_errors(
        _base([{"assay": "gene-expression", "modality": "bulk-rna"}])))


def test_unknown_key_in_capability_is_rejected():
    assert list(Draft202012Validator(_schema()).iter_errors(
        _base([{"data_product": "data-product:x", "modality": "bulk-rna"}])))


def test_1_0_capability_map_unchanged():
    one = json.loads((SCHEMAS / "mixin-hypothesis-1.0.json").read_text())
    assert one["$defs"]["capability_map"]["additionalProperties"] == {"type": "string", "pattern": "\\S"}
