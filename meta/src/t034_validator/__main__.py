"""CLI for the t034 validator. Invoked from validate.local.sh.

Usage: python -m t034_validator <yaml-dir>

Walks <yaml-dir> for .yaml/.yml payload files, loads them into a Store, runs
all v1.4 rules per payload, and prints any issues. Exits 0 only if there are no
load errors and no validation errors. Empty directories pass silently
(0 payloads, 0 errors).
"""
from __future__ import annotations

import sys
from pathlib import Path

from . import Issue, validate_payload
from .loader import load_directory


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m t034_validator <yaml-dir>", file=sys.stderr)
        return 2

    yaml_dir = Path(argv[1])
    store, load_errors = load_directory(yaml_dir)

    all_issues: list[Issue] = []
    for pid in sorted(store.payloads):
        all_issues.extend(validate_payload(store, pid))

    n_payloads = len(store.payloads)
    n_errors = sum(1 for i in all_issues if i.severity == "error")

    for issue in all_issues:
        print(issue)
    for err in load_errors:
        print(f"[error] LOAD                                  {err}")

    print(f"\nt034: {n_payloads} payload(s), {n_errors} error(s), {len(load_errors)} load error(s)")
    return 0 if (n_errors == 0 and not load_errors) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
