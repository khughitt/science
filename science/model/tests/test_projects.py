from datetime import date
from science_model.projects import Project, ProjectDetail, GraphSummary


def test_project_model():
    p = Project(
        slug="seq-feats",
        name="seq-feats",
        path="/home/user/d/seq-feats",
        summary="Research on sequence features",
        status="active",
        aspects=["hypothesis-testing"],
        tags=["genomics"],
        entity_counts={"hypothesis": 4, "question": 13},
        created=date(2026, 3, 2),
    )
    assert p.slug == "seq-feats"
    assert p.staleness_days is None


def test_project_detail_extends_project():
    pd = ProjectDetail(
        slug="test",
        name="test",
        path="/tmp/test",
        aspects=[],
        tags=[],
        entity_counts={},
        hypotheses=[],
        questions=[],
        tasks=[],
        graph_summary=GraphSummary(node_count=0, edge_count=0, top_domains=[]),
    )
    assert pd.graph_summary.node_count == 0
