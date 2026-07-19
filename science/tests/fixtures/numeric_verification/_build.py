"""Builds the fixtures for tests/test_artifact_value_reader.py::read_scalar.

Committed alongside its generated outputs (results.json, summary.feather,
per_disease.feather) so the fixtures are reproducible and auditable rather
than hand-edited binary/JSON blobs. Run once to (re)generate:

    cd science && uv run --frozen python tests/fixtures/numeric_verification/_build.py

Do not hand-edit the generated files -- change this script and re-run it.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

_DIR = Path(__file__).resolve().parent


def build_results_json() -> None:
    # `that_key` is injected as raw text after json.dumps rather than passed
    # in as a Python float -- routing 0.100000000000000005 through a Python
    # float would collapse it to 0.1 (it is not exactly representable in
    # binary float), which is exactly the corruption the fidelity test
    # exists to catch.
    doc = {
        # Fidelity probe: a decimal literal a binary float round-trip would
        # corrupt. See test_json_scalar_fidelity_survives_binary_float_corruption.
        "that_key": "__FIDELITY_PLACEHOLDER__",
        # Nested array, for numeric list-index pointer resolution (/a/0).
        "a": [1, 2, 3],
        # Keys containing literal '/' and '~', for RFC-6901 ~1/~0 unescaping.
        "nested": {"b/c": 42, "d~e": 43},
        # Non-numeric / non-scalar nodes, for rejection tests.
        "s_node": "hello",
        "bool_node": True,
        "null_node": None,
        "list_node": [1, 2],
        "obj_node": {"x": 1},
    }
    text = json.dumps(doc, indent=2)
    text = text.replace('"__FIDELITY_PLACEHOLDER__"', "0.100000000000000005")
    (_DIR / "results.json").write_text(text + "\n")


def build_nonfinite_json() -> None:
    # A bare `NaN` token anywhere in a JSON document aborts the whole
    # `json.load` parse via `parse_constant` (json.load parses top-to-bottom
    # and raises immediately on the non-finite literal, before any pointer
    # is resolved) -- so this must live in its own file, never mixed into
    # results.json alongside nodes other tests expect to resolve.
    doc = {"n": "__NAN_PLACEHOLDER__"}
    text = json.dumps(doc, indent=2)
    text = text.replace('"__NAN_PLACEHOLDER__"', "NaN")
    (_DIR / "nonfinite.json").write_text(text + "\n")


def build_summary_feather() -> None:
    # Single-row table: a plain no-`where` scalar read.
    df = pd.DataFrame({"metric": ["auc"], "score": [0.978]})
    df.to_feather(_DIR / "summary.feather")


def build_per_disease_feather() -> None:
    # Multi-row table with a key column ("disease") distinct from the value
    # column ("score"), so a keyed read (where={"disease": ...}, column=
    # "score") proves the reader loads the union of [column] + where.keys()
    # rather than just [column]. Includes a duplicated key ("DUP", twice)
    # for the >1-match case and a NaN cell for the finite-scalar rejection
    # case.
    df = pd.DataFrame(
        {
            "disease": ["MESH:D009101", "MESH:D003924", "DUP", "DUP", "NAN_ROW"],
            "score": [0.42, 0.13, 0.55, 0.66, math.nan],
        }
    )
    df.to_feather(_DIR / "per_disease.feather")


def main() -> None:
    build_results_json()
    build_nonfinite_json()
    build_summary_feather()
    build_per_disease_feather()


if __name__ == "__main__":
    main()
