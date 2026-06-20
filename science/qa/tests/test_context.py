import pandas as pd

from science_qa.context import Context, TableContext


def test_table_context_holds_table_and_columns():
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    ctx = TableContext(table=df, columns=["a"])
    assert isinstance(ctx, Context)
    assert ctx.columns == ["a"]
    assert list(ctx.table.columns) == ["a", "b"]


def test_table_context_allows_empty_column_selection():
    ctx = TableContext(table=pd.DataFrame({"a": [1]}), columns=[])
    assert ctx.columns == []
