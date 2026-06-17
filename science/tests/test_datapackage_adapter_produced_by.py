from pathlib import Path

from science_model.source_ref import SourceRef

from science_tool.graph.storage_adapters.datapackage import DatapackageAdapter


def test_adapter_surfaces_produced_by(tmp_path: Path) -> None:
    dp = tmp_path / "data" / "x" / "datapackage.yaml"
    dp.parent.mkdir(parents=True)
    dp.write_text(
        "profiles: [science-pkg-entity-1.0]\n"
        "id: dataset:x\n"
        "type: dataset\n"
        "title: X\n"
        "status: active\n"
        "origin: derived\n"
        "tier: use-now\n"
        "produced_by: [code-file:stages/run.py]\n",
        encoding="utf-8",
    )
    raw = DatapackageAdapter().load_raw(SourceRef(adapter_name="datapackage", path=str(dp)))
    assert raw["produced_by"] == ["code-file:stages/run.py"]


def test_adapter_surfaces_tier_and_update_cadence(tmp_path: Path) -> None:
    dp = tmp_path / "data" / "y" / "datapackage.yaml"
    dp.parent.mkdir(parents=True)
    dp.write_text(
        "profiles: [science-pkg-entity-1.0]\n"
        "id: dataset:y\n"
        "type: dataset\n"
        "title: Y\n"
        "status: active\n"
        "origin: derived\n"
        "tier: use-now\n"
        "update_cadence: quarterly\n",
        encoding="utf-8",
    )
    raw = DatapackageAdapter().load_raw(SourceRef(adapter_name="datapackage", path=str(dp)))
    assert raw["tier"] == "use-now"
    assert raw["update_cadence"] == "quarterly"
