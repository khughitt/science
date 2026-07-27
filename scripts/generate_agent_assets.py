from __future__ import annotations

from pathlib import Path
import sys


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "science" / "src"))
    from science_tool.agent_assets import generate_agent_assets

    result = generate_agent_assets(
        repo_root,
        repo_root / "skills" / "generated",
        repo_root / "commands" / "opencode",
    )
    print(
        f"Generated {len(result.skill_paths)} skills and "
        f"{len(result.opencode_command_paths)} OpenCode commands"
    )


if __name__ == "__main__":
    main()
