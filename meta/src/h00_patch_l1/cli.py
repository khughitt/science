# science:code
# status: library
# task_ids: [t065]
# science:end
"""Run the L1-patch demonstration on the real q14 slice.

    uv run python -m h00_patch_l1            # print views A–D for CMT + HSP
    uv run python -m h00_patch_l1 --trig OUT # also emit each patch as a TriG named graph

Views A–C are the t065 L1 patch (belief, provenance, honest ignorance, and the
publication-gravity *discount*); View D is the t066 latent-construct *correction*
(subtract the attention axis via PMI); View E is the t067 patch *federation*
(the bias-corrected latent coordinate as the data-driven half of the glue).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .glue import (
    emit_federation_trig,
    federation_link,
    load_federation,
    nearest_patches,
)
from .latent import correct_disease, three_way_report
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

    grand_total = fixture["grand_total"]
    corrected = sorted(correct_disease(disease, grand_total),
                       key=lambda c: (c.pmi if c.pmi is not None else -9e9), reverse=True)
    print("\n  [View D] latent-construct correction: subtract the attention axis (PMI)")
    print(f"    {'gene':9s} {'panel':5s} {'raw_cooc':>8s} {'PMI':>7s}  specific?")
    for c in corrected:
        pmi_s = f"{c.pmi:+.2f}" if c.pmi is not None else "  n/a"
        print(f"    {c.gene:9s} {('yes' if c.in_panel else 'no'):5s} "
              f"{c.raw_cooc:8d} {pmi_s:>7s}  {'YES' if c.specific else '·'}")
    tw = three_way_report(disease, pubgrav, grand_total)
    print(f"    naive {tw['naive']['support_count']:2d} -> discounted "
          f"{tw['discounted']['support_count']:2d} (t065) -> corrected "
          f"{tw['corrected']['support_count']:2d} specific (t066); "
          f"{tw['corrected']['n_attention_only']} genes were attention-only")
    # The flip the raw count gets wrong: highest-raw universal gene vs lowest-raw panel gene.
    univ = [c for c in corrected if not c.in_panel and c.pmi is not None]
    panel = [c for c in corrected if c.in_panel and c.pmi is not None]
    if univ and panel:
        top_u = max(univ, key=lambda c: c.raw_cooc)
        lo_p = min(panel, key=lambda c: c.raw_cooc)
        print(f"    flip: raw ranks {top_u.gene}(cooc={top_u.raw_cooc}) "
              f"over {lo_p.gene}(cooc={lo_p.raw_cooc}); corrected "
              f"{top_u.gene} PMI={top_u.pmi:+.2f} < {lo_p.gene} PMI={lo_p.pmi:+.2f}")


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

    _print_federation(fixture, args.trig)
    return 0


CMT, HSP = "MESH:D002607", "MESH:D015419"


def _print_federation(slice_fix: dict, trig_dir: Path | None) -> None:
    """View E (t067): federate the two patches via the dual common space."""
    fed = load_federation()
    link = federation_link(fed, slice_fix, CMT, HSP)
    ch = fed["cmt_hsp"]
    print(f"\n{'=' * 72}")
    print("FEDERATION (t067)  dual common space: symbolic (panel-gene) + latent (PPMI-SVD)")
    print(f"  PPMI->SVD k={fed['provenance']['k']} "
          f"(var explained {fed['provenance']['var_explained_k']}), {fed['n_diseases']} diseases")
    print(f"\n  [View E] CMT <-> HSP federation link")
    print(f"    symbolic Jaccard (shared panel genes): {link.symbolic_jaccard}  -> disjoint panels")
    print(f"    latent cosine (bias-corrected coord) : {link.latent_cosine}  "
          f"(HSP is CMT's #{ch['hsp_rank_among_cmt_corrected']} neighbor of {fed['n_diseases']})")
    print(f"    glue kind: {link.glue_kind.upper()}  "
          f"<- latent axis federates where gene-id overlap is 0")
    print(f"\n    honesty — correction's marginal effect on federation is modest at the")
    print(f"    profile scale: HSP rank among CMT neighbors  corrected #{ch['hsp_rank_among_cmt_corrected']}"
          f"  vs raw #{ch['hsp_rank_among_cmt_raw']}  "
          f"(cos {ch['cosine_corrected']} vs {ch['cosine_raw']}); a sharpening, not a rescue.")

    for mesh, lbl in [(CMT, "CMT"), (HSP, "HSP")]:
        print(f"\n    {lbl} top-6 latent neighbors (MeSH tree in brackets; all C10 = nervous system):")
        for nb in nearest_patches(fed, mesh)[:6]:
            print(f"      {nb['cosine']:.3f}  [{nb['tree']:14s}] {nb['name']}")

    if trig_dir:
        out = emit_federation_trig(fed, slice_fix, CMT, HSP, trig_dir / "federation.trig")
        print(f"\n  wrote federation named graph -> {out}")


if __name__ == "__main__":
    raise SystemExit(main())
