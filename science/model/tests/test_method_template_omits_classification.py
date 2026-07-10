"""A scaffolded method is unclassified until a human classifies it (task:t079)."""

from science_model.templates import Renderer


def _render() -> str:
    return Renderer().render(
        "method",
        fields={
            "entity_id": "method:probe",
            "title": "Probe",
            "status": "active",
            "source_refs": [],
            "related": [],
            "created": "2026-07-09",
            "updated": "2026-07-09",
        },
    )


def test_rendered_method_omits_stochasticity_and_seed_params() -> None:
    rendered = _render()
    assert "stochasticity:" not in rendered
    assert "seed_params:" not in rendered


def test_rendered_method_still_carries_its_identity() -> None:
    assert "id: method:probe" in _render()
