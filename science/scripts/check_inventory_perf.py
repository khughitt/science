from __future__ import annotations

import argparse
from pathlib import Path
from time import perf_counter

from science_tool.entities_inventory import build_inventory


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", action="append", required=True)
    parser.add_argument("--max-seconds", type=float, required=True)
    args = parser.parse_args()

    failures: list[str] = []
    for raw_project in args.project:
        project = Path(raw_project)
        build_inventory(project)
        started = perf_counter()
        build_inventory(project)
        elapsed = perf_counter() - started
        print(f"{project}: {elapsed:.3f}s")
        if elapsed > args.max_seconds:
            failures.append(f"{project}: {elapsed:.3f}s > {args.max_seconds:.3f}s")
    if failures:
        raise SystemExit("\n".join(failures))


if __name__ == "__main__":
    main()
