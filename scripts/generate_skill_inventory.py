from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "science" / "src"))
    sys.path.insert(0, str(repo_root / "science" / "model" / "src"))
    from science_model.data_products import load_catalog
    from science_tool.graph.skill_inventory import build_skill_inventory, serialize_inventory

    inventory = build_skill_inventory(repo_root, load_catalog())
    out = repo_root / "science" / "src" / "science_tool" / "graph" / "skill_inventory.json"
    out.write_text(serialize_inventory(inventory), encoding="utf-8")
    print(f"Wrote {out} ({len(inventory['skills'])} skills)")


if __name__ == "__main__":
    main()
