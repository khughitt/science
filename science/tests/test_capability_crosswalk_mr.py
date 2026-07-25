"""The packaged crosswalk maps the pai Mendelian-randomization GWAS shapes.

`analysis_role: mr_exposure|mr_outcome` is analysis-design intent, not a molecular
data-product, so it must not survive into the gen-3 capability. These shapes were
formerly `refuse`d (author must re-model); they now map to
`data-product:gwas-summary-statistics`, dropping `analysis_role`/`outcome` and
keeping only descriptive molecular qualifiers (`trait`, `cohort_design`, `trigger`,
`stratification`). The MR exposure/outcome role lives in the Wave-1 estimand doc and
each entity's `ontology_terms`/prose, not in the capability shape.
"""

from pathlib import Path

import science_tool.datasets as datasets_pkg
from science_model.data_products import load_catalog
from science_tool.datasets.capability_crosswalk import Crosswalk, Mapped

_CROSSWALK = Path(datasets_pkg.__file__).parent / "capability_crosswalk.yaml"

_GWAS = "data-product:gwas-summary-statistics"

# The six refused MR shapes observed across the seven pai entities (3 datasets +
# 3 hypotheses + 1 question), keyed to their expected surviving qualifiers.
_MR_SHAPES = [
    (
        {"analysis_role": "mr_exposure", "trait": "autoimmune-disease"},
        {"trait": "autoimmune-disease"},
    ),
    (
        {"modality": "genetics", "assay": "gwas-sumstats", "cohort_design": "summary-stats",
         "analysis_role": "mr_exposure", "trait": "sex-hormone-biomarker",
         "outcome": "sex-hormone-level", "stratification": "sex"},
        {"cohort_design": "summary-stats", "stratification": "sex", "trait": "sex-hormone-biomarker"},
    ),
    (
        {"modality": "genetics", "assay": "gwas-sumstats", "cohort_design": "summary-stats",
         "analysis_role": "mr_exposure", "trait": "autoimmune-disease"},
        {"cohort_design": "summary-stats", "trait": "autoimmune-disease"},
    ),
    (
        {"analysis_role": "mr_exposure", "trait": "sex-hormone-biomarker"},
        {"trait": "sex-hormone-biomarker"},
    ),
    (
        {"modality": "genetics", "assay": "gwas-sumstats", "cohort_design": "summary-stats",
         "trigger": "sars-cov-2", "analysis_role": "mr_outcome", "trait": "long-covid"},
        {"cohort_design": "summary-stats", "trait": "long-covid", "trigger": "sars-cov-2"},
    ),
    (
        {"analysis_role": "mr_outcome", "trait": "long-covid"},
        {"trait": "long-covid"},
    ),
]


def _crosswalk() -> Crosswalk:
    return Crosswalk.load(_CROSSWALK, catalog_ids=set(load_catalog().by_id))


def test_mr_shapes_map_to_gwas_dropping_analysis_role() -> None:
    cw = _crosswalk()
    for shape, expected_quals in _MR_SHAPES:
        result = cw.rewrite(shape)
        assert isinstance(result, Mapped), f"{shape} should map, not {type(result).__name__}"
        assert result.capability["data_product"] == _GWAS, shape
        quals = result.capability["qualifiers"]
        assert "analysis_role" not in quals, f"analysis_role leaked into {shape}"
        assert "outcome" not in quals, f"MR outcome facet leaked into {shape}"
        assert quals == expected_quals, shape
