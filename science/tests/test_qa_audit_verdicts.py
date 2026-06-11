from science_tool.qa_audit.verdicts import engagement_verdict, iteration_verdict, FlagDisposition


def fd(disposition, change=""):
    return FlagDisposition(disposition=disposition, change=change)


# --- engagement axis ---
def test_engagement_no_qa_when_no_report():
    assert engagement_verdict(has_report=False, flags=[]) == "NO-QA"


def test_engagement_no_flags():
    assert engagement_verdict(has_report=True, flags=[]) == "NO-FLAGS"


def test_engagement_ignored_all_open():
    assert engagement_verdict(has_report=True, flags=[fd("open"), fd("open")]) == "IGNORED"


def test_engagement_responded_all_resolved_engaged():
    flags = [fd("addressed", "min_genes=200"), fd("accepted-real"), fd("wont-fix")]
    assert engagement_verdict(has_report=True, flags=flags) == "RESPONDED"


def test_engagement_partial_for_investigating():
    assert engagement_verdict(has_report=True, flags=[fd("investigating")]) == "PARTIAL"


def test_engagement_partial_for_mix():
    assert engagement_verdict(has_report=True, flags=[fd("open"), fd("addressed", "x")]) == "PARTIAL"


# --- iteration axis ---
def test_iteration_single_run():
    assert iteration_verdict(chain_depth=1, flags=[fd("addressed", "x")]) == "SINGLE-RUN"


def test_iteration_qa_responsive_requires_rerun_and_change():
    assert iteration_verdict(chain_depth=2, flags=[fd("addressed", "min_genes=200")]) == "QA-RESPONSIVE"


def test_iteration_addressed_without_rerun_is_single_run():
    assert iteration_verdict(chain_depth=1, flags=[fd("addressed", "min_genes=200")]) == "SINGLE-RUN"


def test_iteration_rerun_without_qa_change_is_unrelated():
    assert iteration_verdict(chain_depth=2, flags=[fd("open")]) == "RE-RAN-UNRELATED"


def test_iteration_addressed_without_change_not_responsive():
    assert iteration_verdict(chain_depth=2, flags=[fd("addressed", "")]) == "RE-RAN-UNRELATED"
