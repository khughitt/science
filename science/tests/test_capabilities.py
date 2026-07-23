import pytest
from science_model.data_products import build_catalog
from science_tool.datasets.capabilities import capability_fit


def _catalog():
    return build_catalog({"schema_version": "1", "terms": [
        {"id": "data-product:gene-expression", "label": "GE", "assay": "ge", "technology": "", "broader": []},
        {"id": "data-product:gene-expression-bulk-rna", "label": "b", "assay": "ge",
         "technology": "bulk-rna", "broader": ["data-product:gene-expression"]},
        {"id": "data-product:gene-expression-scrna", "label": "s", "assay": "ge",
         "technology": "scrna", "broader": ["data-product:gene-expression"]},
    ]})


def _c(dp, **q):
    return {"data_product": dp, "qualifiers": dict(q)}


# --- gen 3 ---
def test_gen3_exact_term_matches():
    assert capability_fit([_c("data-product:gene-expression-bulk-rna")],
                          [_c("data-product:gene-expression-bulk-rna")],
                          generation=3, catalog=_catalog()).compatible


def test_gen3_provided_descendant_satisfies_broader_requirement():
    assert capability_fit([_c("data-product:gene-expression")],
                          [_c("data-product:gene-expression-bulk-rna")],
                          generation=3, catalog=_catalog()).compatible


def test_gen3_ancestor_does_not_satisfy_specific():
    assert not capability_fit([_c("data-product:gene-expression-bulk-rna")],
                              [_c("data-product:gene-expression")],
                              generation=3, catalog=_catalog()).compatible


def test_gen3_siblings_do_not_match():
    assert not capability_fit([_c("data-product:gene-expression-bulk-rna")],
                              [_c("data-product:gene-expression-scrna")],
                              generation=3, catalog=_catalog()).compatible


def test_gen3_qualifier_subset_gates():
    req = [_c("data-product:gene-expression", analysis_role="mr_exposure")]
    cat = _catalog()
    assert not capability_fit(req, [_c("data-product:gene-expression-bulk-rna")],
                              generation=3, catalog=cat).compatible
    assert capability_fit(req, [_c("data-product:gene-expression-bulk-rna", analysis_role="mr_exposure")],
                          generation=3, catalog=cat).compatible


def test_gen3_requires_catalog():
    with pytest.raises(ValueError):
        capability_fit([_c("data-product:x")], [_c("data-product:x")], generation=3, catalog=None)


# --- gen 2 (unchanged string-map) ---
def test_gen2_string_map_subset_still_matches():
    fit = capability_fit([{"assay": "gene-expression"}],
                         [{"assay": "gene-expression", "modality": "microarray"}], generation=2)
    assert fit.compatible


def test_gen2_string_map_mismatch():
    fit = capability_fit([{"assay": "gene-expression", "modality": "single-cell"}],
                         [{"assay": "gene-expression", "modality": "microarray"}], generation=2)
    assert not fit.compatible
