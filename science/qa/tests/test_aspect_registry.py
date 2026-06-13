from science_qa.aspects import CHECK_FAMILY, CHECK_REQUIRED, CheckSpec, Invocation
from science_qa.context import TableContext


def test_required_checkspec_defaults():
    spec = CheckSpec(aspect="general", name="non_empty", kind=CHECK_REQUIRED,
                     accepts=TableContext, fn=lambda ctx, params: [])
    assert spec.check_id == "general/non_empty"
    assert spec.expand is None
    assert spec.requires == ()
    assert spec.selector is None


def test_family_checkspec_carries_expand_callable():
    spec = CheckSpec(aspect="numeric-column", name="ranges", kind=CHECK_FAMILY,
                     accepts=TableContext, fn=lambda ctx, params: [],
                     expand=lambda config: [Invocation(params={"x": 1}, requires=("a",), columns=["a"])])
    invs = spec.expand(object())
    assert invs[0].columns == ["a"]
    assert invs[0].requires == ("a",)
