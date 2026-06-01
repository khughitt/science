# science:code
# status: library
# task_ids: [t065]
# science:end
"""Run the L1-patch demonstration on the real q14 slice.

    uv run python -m h00_patch_l1            # print the three views for CMT + HSP
    uv run python -m h00_patch_l1 --trig OUT # also emit each patch as a TriG named graph
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .model import load_fixture, pubgravity_threshold
from .patch import build_patch_report, emit_patch_trig


def _print_disease(fixture: dict, mesh_id: str) -> None:
    disease = fixture["diseases"][mesh_id]
    pubgrav = pubgravity_threshold(fixture)
    rep = build_patch_report(disease, pubgrav)

    print(f"\n{'=' * 72}")
    print(f"PATCH  {mesh_id}  {disease['name']}")
    print(f"  panel: {disease['panel_source']} ({disease['evidence_tier']}); "
          f"clingen_strict_eligible={disease['clingen_strict_eligible']}")
    print(f"  publication-gravity threshold (ubiquity >= q99): {pubgrav} "
          f"of {fixture['n_diseases']} diseases")

    print("\n  [View A] per-edge belief + provenance routes + opinion uncertainty")
    print(f"    {'gene':9s} {'panel':5s} {'routes':18s} {'belief':14s} {'u':>5s}")
    for e in rep["edges"]:
        print(f"    {e.gene:9s} {('yes' if e.in_panel else 'no'):5s} "
              f"{','.join(e.provenance_types):18s} {e.magnitude:14s} "
              f"{e.opinion.uncertainty:5.2f}")

    eo = rep["editorial_only_example"]
    if eo:
        print(f"\n  [View C] honest ignorance: {eo['gene']} EDITORIAL-ONLY (no data yet) "
              f"-> u={eo['opinion']['uncertainty']}, E={eo['opinion']['expected']}")

    f = rep["fusion"]
    print("\n  [View B] publication gravity as independence-discounted fusion")
    print(f"    co-occurring genes: {f['n_genes']}  "
          f"(universal/publication-gravity: {f['n_universal_pubgravity']})")
    print(f"    naive       : {f['naive_support_count']:2d} supports, "
          f"score {f['naive_support_score']:2d}, "
          f"opinion u={f['naive_opinion']['uncertainty']}, E={f['naive_opinion']['expected']}")
    print(f"    discounted  : {f['discounted_support_count']:2d} supports, "
          f"score {f['discounted_support_score']:2d}, "
          f"opinion u={f['discounted_opinion']['uncertainty']}, E={f['discounted_opinion']['expected']}")
    removed = f["naive_support_score"] - f["discounted_support_score"]
    pct = (100.0 * removed / f["naive_support_score"]) if f["naive_support_score"] else 0.0
    print(f"    -> reduction removed {removed} of {f['naive_support_score']} "
          f"support score ({pct:.0f}%) as publication gravity")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trig", type=Path, default=None,
                    help="directory to write one <mesh>.trig named graph per disease")
    args = ap.parse_args(argv)

    fixture = load_fixture()
    for mesh_id in fixture["diseases"]:
        _print_disease(fixture, mesh_id)
        if args.trig:
            out = emit_patch_trig(fixture, mesh_id, args.trig / f"{mesh_id.replace(':', '_')}.trig")
            print(f"\n  wrote patch named graph -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
