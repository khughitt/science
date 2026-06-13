import pytest
from science_qa.config import QAConfig
from science_qa.context import TableContext
from science_qa.program import ProgramError, resolve_program


def test_scrna_program_lists_aspects_in_order():
    prog = resolve_program("scrna-qc-table")
    assert prog.substrate is TableContext
    aspects = [c.aspect for c in prog.checks]
    # general first, scrna gates after gene-expression, project-local last
    assert aspects[0] == "general"
    assert aspects.index("tabular") < aspects.index("numeric-column")
    assert aspects.index("gene-expression-qc-table") < aspects.index("scrna-qc-table")


def test_unknown_program_errors():
    with pytest.raises(ProgramError, match="unknown program"):
        resolve_program("nope")


def test_ranges_family_expands_one_invocation_per_declared_range():
    prog = resolve_program("scrna-qc-table")
    ranges_spec = next(c for c in prog.checks if c.check_id == "numeric-column/range")
    config = QAConfig(program="scrna-qc-table", ranges={"g": {"min": 1, "max": 9}})
    invs = ranges_spec.expand(config)
    assert len(invs) == 1 and invs[0].columns == ["g"] and invs[0].requires == ("g",)


def test_unconfigured_family_expands_to_zero_invocations():
    prog = resolve_program("scrna-qc-table")
    cat_spec = next(c for c in prog.checks if c.check_id == "tabular/categoricals")
    assert cat_spec.expand(QAConfig(program="scrna-qc-table")) == []


def test_doublet_family_expands_with_optional_required_column():
    prog = resolve_program("scrna-qc-table")
    doublet = next(c for c in prog.checks if c.check_id == "scrna-qc-table/doublet_ceiling")
    invs = doublet.expand(QAConfig(program="scrna-qc-table"))
    assert len(invs) == 1 and invs[0].requires == ("doublet_score",) and invs[0].optional is True
