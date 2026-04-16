from __future__ import annotations

from pathlib import Path
import sys


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "science-tool" / "src"))
    from science_tool.codex_skills import generate_codex_skills

    output_root = repo_root / "codex-skills"
    generate_codex_skills(repo_root, output_root)
    print(f"Generated Codex skills in {output_root}")


if __name__ == "__main__":
    main()
