# C4 — Variant Identity (VRS 2.0), Liftover & Compatibility Relations (decomposition + C4a design)

Date: 2026-05-28

Status: C4a implemented; C4b implemented in liftover, assembly-compatibility, and identity-context
validation code; C4c-1 rsID input implemented locally via
`docs/plans/2026-05-31-c4c-rsid-variant-label-plan.md`, with full dbSNP artifact build/operator smoke pending
(Pillar C, sub-phase 4 of the bio data architecture)

Related (builds on):
- `docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md` — Pillar C; this details its C4 row (§8)
- `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md` — umbrella (C4 = the heavyweight sub-phase, "decompose before planning")
- `docs/plans/historical/2026-05-26-reference-collection-member-promotion-design.md` — foundation primitive; the assembly registry / sequence store are instances; guardrail-2 (RCM-D6) is the compatibility-relation home (C4b)
- `science/src/science_tool/commons/assembly.py`, `assembly_registry_build.py` — C1 seqcol registry + level-2 build (the per-contig digests C4a materializes)
- `science/model/src/science_model/schemas/extension-bio-identity_context-1.0.json` — `molecular_ids` open map (variant tier needs no schema edit)
- C2/C3 precedent: `science/src/science_tool/commons/` gene/protein resolvers + `evaluate_tier_identity` (declaration-level tier check)

---

## 1. Purpose & decomposition

C4 is the variant-identity arm of Pillar C: canonical, deterministic, **assembly-anchored** variant
identity, plus the cross-assembly machinery (liftover + seqcol compatibility relations) that supplies the
remedy C1's check 3 defers. The umbrella flags C4 as the heavyweight sub-phase and requires it be
decomposed before planning. It splits into three independently-testable increments:

| Increment | Locks | External weight |
|---|---|---|
| **C4a — Variant identity (VRS 2.0)** | assembly-anchored `ga4gh:VA…` minting from genomic HGVS / VCF / SPDI, over a pinned, offline refget sequence store; variant-tier declaration + row-level resolvability check | heavy: `ga4gh.vrs` + reference-sequence bytes |
| **C4b — Cross-assembly** | pinned liftover (GRCh37→GRCh38 default) + seqcol **compatibility relations** (RCM-D6 guardrail-2, first instance) + the check-3 *remedy* | medium: pinned chain files |
| **C4c — External label / projection inputs** | rsID input (pinned dbSNP snapshot); transcript/protein HGVS projection (pinned transcript/protein-ref snapshot) | heavy: large pinned snapshots |

This document specifies **C4a** in full (§3–§9) and scopes C4b/C4c as named increments (§10). C4a led
because variant identity is the headline "unblocks AlphaMissense-class data" deliverable, and because
liftover (C4b) relates ids that C4a must first be able to mint. C4b is now implemented, and C4c-1 rsID
input is implemented locally; transcript/protein projection remains deferred.

**Locked sequencing decisions (this review):**
1. **C4a before C4b before C4c.**
2. **Sequence access = a refget proxy over C1's per-contig digests**, not a parallel SeqRepo store —
   one source of assembly truth.
3. **C4a pins GRCh38 + GRCh37 sequence** (both first-class declared assemblies, C-D5), so a variant on
   either assembly gets an id without waiting for C4b; cross-assembly *relating* is C4b.

---

## 2. What C4a added

| Before C4a (post C1–C3) | C4a implemented |
|---|---|
| Assembly registry keyed by `seqcol_digest`; `assemblies.csv` carries `seqcol_digest, label, accession, n_sequences, source_url` only | A per-contig resource (`contigs.csv`) materializing the seqcol level-2 record the digest already rolls up over, **plus a contig alias table** (§3) |
| `assembly_registry_build.py` fetches the level-2 record (`names`, per-contig `SQ.` digests, `lengths`) then **discards** it | The build persists level-2 (names + `SQ.` digests + lengths + ordinal); contig **aliases** come from a pinned NCBI assembly report added by C4a |
| No reference-sequence bytes anywhere | A pinned, content-addressed, **locally-materialized** sequence store for GRCh38 + GRCh37 (§5) |
| No variant identity | `vrs_id(expr, assembly_seqcol)` over an injected, offline refget proxy (§6/§7) |
| `molecular_ids` accepts arbitrary tiers; C2/C3 `evaluate_tier_identity` validates a tier *declaration* | A `variant` tier convention **with an explicit row-level locator contract** + a row-level minting check (§8) |

---

## 3. C4a-D1 — Contig resolution: a registry contig + alias table

`(assembly, contig name) → refget_digest` is **not** a sufficient contract: accepted inputs name contigs
in incompatible ways — genomic HGVS uses a **sequence accession** (`NC_000001.11`), VCF `CHROM` uses a
bare or prefixed label (`1`, `chr1`). C4a therefore materialized two registry resources in the
`assembly-registry` collection (dogfooding C1). The `name`/`refget_digest`/`length`/`sequence_index`
columns come from the seqcol **level-2 record** C1 already fetches; the **alias** columns (RefSeq/GenBank
accession, UCSC/Ensembl names) are **not** in seqcol level-2, so C4a added a **pinned, dated NCBI assembly
report** (`GCF_…_assembly_report.txt`) as a build input and joins it on sequence name. C4a added and
pinned this source because C1 originally pinned only label/accession/digest:

**`contigs.csv`** — one row per sequence in a collection:

| column | meaning |
|---|---|
| `seqcol_digest` | parent collection (FK to `assemblies.csv`) |
| `sequence_index` | ordinal position; makes `names`/`lengths`/`sequences` alignment auditable |
| `name` | the seqcol canonical name |
| `refget_digest` | the `SQ.` per-contig digest (the sequence-store key) |
| `length` | contig length (bounds checks) |

**`contig_aliases.csv`** — the accepted-input alias table:

| column | meaning |
|---|---|
| `seqcol_digest` | parent collection |
| `refget_digest` | the contig this alias resolves to |
| `alias` | the accepted string (`NC_000001.11`, `chr1`, `1`, `CM000663.2`) |
| `alias_kind` | `refseq_accession` \| `genbank_accession` \| `ucsc` \| `ensembl` \| `seqcol_name` |
| `sequence_accession` | the underlying INSDC/RefSeq accession when `alias` is an accession |

**Resolution contract (fail-early, no guessing):**
- An input contig string resolves to **exactly one** `refget_digest` *within the declared assembly's
  collection*; a string matching zero or ≥2 contigs is an **error** (ambiguous/unknown alias), never a
  silent pick.
- A genomic-HGVS sequence accession that resolves to a contig **outside** the declared
  `assembly.seqcol_digest` is an **accession/assembly mismatch** error — caught here, not downstream.
- **Hard build-time errors:** duplicate `name` per collection, duplicate `(seqcol_digest, alias)`,
  `sequence_index`/`name`/`length` length-mismatch against the level-2 record.

## 4. C4a-D2 — Assemblies are identified by seqcol digest, labels are aliases

C4a pins the **exact** GRCh38 and GRCh37 collections by `seqcol_digest` (the build asserts the recomputed
digest against the pinned value, as C1 already does). `GRCh38`/`hg38` and `GRCh37` are advisory labels
resolved through the registry to a pinned digest, **never** the identity key (C-D2). Crucially, `b37`,
`hs37d5`, and decoy/alt/patch flavors are **distinct sequence collections, not aliases for the plain
GRCh37 digest** — they are **rejected as unknown** unless their exact seqcol collection is itself pinned as
its own assembly row. No label may resolve to two digests. A dataset declares its source
assembly by digest; the canonical analysis target remains GRCh38 (C-D5), but **C4a does not lift** — it
mints on whatever assembly is declared.

## 5. C4a-D3 — Pinned reference-sequence store (digests committed, bytes built locally)

A `reference` dataset providing per-contig sequence **bytes** for GRCh38 + GRCh37, content-addressed by
refget `SQ.` digest.

- **The bytes are not committed to git** (~6 GB; the commons holds only MB-scale artifacts, no LFS). C4a
  commits the **recipe + a datapackage manifest of per-contig `SQ.` digests** (and file hashes/bytes once
  built); `recipe/build.py` materializes and **content-verifies** the store locally against those digests.
  The committed digests are the pinned authority — content-addressing makes any local store fully
  verifiable; the bytes are reproducible, not archived.
- **Honest caveat (state in the recipe README):** this is *pinned and verifiable, not archival*. A rebuild
  may fail if the upstream FASTA disappears; but any store that *is* produced is byte-verified against the
  committed digests, so identity is reproducible wherever the store exists.
- **Format:** a **flat refget store** keyed by `SQ.` digest, sliced by byte offset — preferred over
  bgzip+faidx to avoid C-heavy dependencies, since the only access pattern the proxy needs is
  "substring of one contig."

## 6. C4a-D4 — Refget-backed DataProxy (pure, offline, fail-loud)

`commons/refget_proxy.py` implements the small `ga4gh.vrs` `DataProxy` interface
(`get_sequence(refget_id, start, end)`, `translate_sequence_identifier`, `get_metadata`) over the local
sequence store + the registry contig/alias map.

- **No network at runtime is a *tested invariant*** (a test asserts no outbound call), not just a
  convention.
- If the sequence store is **missing or incomplete, the proxy fails loudly** (raises) — it never falls
  back to fetching. Absence is an error, not a slow path.

## 7. C4a-D5 — VRS dependency + variant resolver (spike-gated)

- **Dependency spike ran first.** Before committing to `ga4gh.vrs`, C4a proved on a synthetic contig that
  the pinned package can **parse → normalize → `ga4gh_identify`** an allele *through the injected proxy*
  with **no SeqRepo and no network**. `vrs-python`'s translation/extras stack commonly assumes SeqRepo/UTA
  backing data; the spike confirmed the core models + identifier generation work over a custom
  `DataProxy`.
  - **Fallback if the spike fails:** local parsers for the accepted simple forms (SPDI / genomic-HGVS /
    VCF small alleles) feeding `vrs-python` **core models + identifier generation only** (not its
    translators). The computed-identifier guarantee survives; only the parsing layer changes.
- **Pin both** the `ga4gh.vrs` **package version** and the **VRS spec/schema version** (in code or
  metadata), and **avoid yanked releases** (2.1.x are yanked; 2.x is the actively-maintained line that maps
  to VRS 2.x). C4a pinned the exact package surface with golden ids.
- `commons/variant.py` exposes `vrs_id(expr, assembly_seqcol) -> "ga4gh:VA…"`: parse the expression,
  resolve its contig via §3, normalize (fully-justified) against the proxy, compute the id.
- **Flags, never silently drops** (mirrors C-D6 check 4): reference-base mismatch (provided REF ≠ pinned
  sequence), out-of-bounds coordinate, ambiguous/unknown contig alias, accession/assembly mismatch,
  unsupported allele (see §8 accepted set).

## 8. C4a-D6 — Variant-tier declaration, locator contract & resolvability check

**Accepted allele set (C4a):** precise small alleles only — SNV/MNV/small indel, expressed as SPDI,
genomic HGVS (`g.`), or VCF `CHROM-POS-REF-ALT`. VCF must be **biallelic or pre-split multiallelic**
(one ALT per row); **rejected**: symbolic alleles (`<DEL>`), breakends, imprecise SVs, and any row whose
REF cannot be validated against the pinned sequence.

**Declaration (convention; `molecular_ids` stays an open map, no schema edit).** The bare tier flag says
only "this dataset's variant ids are VRS" — it cannot drive row-level minting. C4a therefore defines an
explicit **locator** so the check knows *where and in what form* the variant expressions live:

```yaml
identity_context:
  taxon: 9606
  molecular_ids:
    variant:
      namespace: vrs
      canonical: true
      resolution_status: resolved
      locator:
        resource: variants.csv             # a resource named in the dataset datapackage
        format: spdi                       # spdi | hgvs | vcf
        column: variant                    # single-expression column (spdi | hgvs)
        # for format: vcf, use columns instead of column:
        # columns: {chrom: CHROM, pos: POS, ref: REF, alt: ALT}
        multiallelic: split                # split (one ALT/row) — required for vcf
  assembly:
    seqcol_digest: SQ...                   # the source assembly, by digest (§4)
    registry: dataset:assembly-registry
    resolution_status: resolved
```

The convention is enforced by the check, not the JSON schema (it may be promoted to schema later). A
`variant` tier without a well-formed `locator` (missing resource/format/column(s)) is a declaration
**error**. `locator.resource` names a resource **in the dataset's datapackage** (resolved through it, not
an arbitrary filesystem path). C4a reads **CSV/TSV** rows only — the repo has no
parquet/arrow/pandas/polars dependency; parquet support is deferred unless a later increment explicitly
adds the dependency.

**Two-layer check** (new validate check):
1. **Declaration layer** — reuse the small **tier-independent shape validator** (`_tier_defect`:
   `namespace` present/non-blank, optional `registry` a `dataset:` ref, valid `resolution_status`) plus a
   variant-specific namespace check (`vrs`) and `locator` validity. **Not** the full
   `evaluate_tier_identity`: that helper is crosswalk-registry-shaped (a `_TierSpec` with
   `key_column`/`profile_token`/`default_registry`, and it resolves the declared registry to a crosswalk
   collection), but C4a's variant tier has **no registry** (deferred to C4c). The plan factors the shared
   declaration-shape check out of the crosswalk path into a small no-registry validator both call, rather
   than bending the crosswalk helper.
2. **Row layer** — open the located resource/column(s), parse each expression in the declared `format`,
   and mint via §7 against the declared assembly. Report **counts**: minted, ref-mismatch, out-of-bounds,
   ambiguous-alias, accession-mismatch, unsupported-allele. Unresolved rows are flagged with counts, never
   silently passed. A tier marked `resolution_status: declared_unresolved` skips the row layer (honored,
   not minted).

## 9. C4a-D7 — Tests & fixtures

- A tiny **synthetic refget contig** fixture (a few hundred bp, its own `SQ.` digest) + a flat-store
  fixture, so unit tests mint real VRS ids **without** the multi-GB store.
- **Golden ids** for an SNV and a **left-shiftable indel**, tied to the pinned `vrs-python`/VRS version
  (the pin is part of the golden contract — a version bump regenerates and re-reviews them).
- **Negative tests:** accession/assembly mismatch, REF mismatch, out-of-bounds, ambiguous contig alias,
  symbolic allele, multiallelic-not-split, missing sequence store (proxy fails loud), and a no-network
  assertion.
- Recipe-level QA: every materialized contig's computed `SQ.` digest equals the committed manifest digest.

---

## 10. Deferred increments (named, not half-built)

- **C4b — Cross-assembly (implemented).** Pinned UCSC GRCh37→GRCh38 liftover chains as a `reference`
  dataset; a same-strand chain-block `lift_interval` resolver that **flags** unliftable / multi-mapping /
  strand-ambiguous coordinates rather than dropping them; **seqcol compatibility relations** (RCM-D6
  guardrail-2: distinct digests related with provenance, never collapsed) — the first realization of the
  primitive's compatibility side; and the **remedy for C1 check 3** (cross-dataset assembly mismatch is now
  resolvable when exact pinned liftover provenance is present). A lifted variant is a *distinct, linked*
  identity (assembly-anchored VRS id on the target), recorded with liftover provenance (C-D5), never the
  source id by assertion. Reverse-strand allele reminting, broad interval/BED liftover, rsID,
  transcript HGVS, and protein projection remain outside C4b.
- **C4c — External label / projection inputs.** C4c-1 rsID input via a pinned dbSNP / NCBI Variation
  snapshot is implemented locally through `dataset:variant-labels-dbsnp-human`; full dbSNP artifact
  build, lockfile pinning, datapackage hash refresh, and resolver smoke remain operator-pending.
  Transcript/protein HGVS via a pinned transcript/protein-reference snapshot plus an explicit projection
  policy remains deferred. These add input *surface*, not new identity semantics.

## 11. Stress-test recheck (umbrella §5)

- **AlphaMissense** (the C4 driver): per-variant table, assembly-anchored coordinates → C4a mints VRS ids
  for its GRCh38 variants directly; GRCh37-sourced variants get GRCh37-anchored ids in C4a and a lifted
  GRCh38 re-identification in C4b. **AlphaMissense *ingestion* is out of C4a** — C4a ships the identity
  machinery + checks + fixtures; ingesting the real dataset is a later instantiation (like Reactome/E)
  carrying A's `model_output` source-class + D/B provenance semantics.

## 12. Status & next step

C4a is implemented and merged. C4b is merged locally: it added cross-assembly
liftover, seqcol compatibility relations, lifted VRS reminting, and the C1 check-3 provenance-verified
liftover remedy in `science/src/science_tool/commons/liftover.py`,
`science/src/science_tool/commons/assembly_compatibility.py`, and
`science/src/science_tool/validate/checks/identity_context.py`. C4c-1 rsID input is implemented
locally in `~/d/science` and `~/d/science-commons` via
`docs/plans/2026-05-31-c4c-rsid-variant-label-plan.md`; full dbSNP artifact build/operator smoke is still
pending, and transcript/protein HGVS projection remains a later C4c increment.
