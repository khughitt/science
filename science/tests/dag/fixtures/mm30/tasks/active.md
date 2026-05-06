## [t055] MMRF longitudinal cytogenetic change detection (causal identification test)
- priority: P2
- status: done
- aspects: [hypothesis-testing, causal-modeling, computational-analysis]
- related: [interpretation:2026-04-02-stratified-meta-analysis, hypothesis:h4-attractor-convergence, hypothesis:h2-cytogenetic-distinct-entities, inquiry:h2-subtype-architecture]
- group: h2-cytogenetic
- created: 2026-04-02
- completed: 2026-04-11

**Result:** Longitudinal virtual FISH across 87 paired baseline/relapse MMRF patients.
Key findings:

1. **gain(1q) acquisition: 13 patients (26.5% of initially-negative).** PHF19 increases
   significantly within acquirers (Wilcoxon p=0.020), chr1q arm score also increases
   (Wilcoxon p=0.003, Mann-Whitney p=0.046). Supports gain(1q) **causation** of 1q
   transcriptomic architecture.
2. **Translocations are fixed:** 0 acquired t(4;14) or t(11;14) — confirmed as founding
   events, consistent with disease biology.
3. **del(17p) acquisition: 12 patients (16.2%).** Net gain at relapse, consistent with
   clonal evolution under treatment selection.
4. **HD net loss at relapse:** 5 acquired, 12 lost. Biologically interesting — may
   reflect HD clone contraction under therapy.
5. **Baseline cross-validation:** 98.8% agreement with existing virtual FISH calls.

Between-group PHF19 test is borderline (Mann-Whitney p=0.072) because persistent-neg
patients also show modest PHF19 drift (+0.23) — consistent with general disease
progression. Within-patient paired test is the stronger design.

Script: scripts/hypotheses/h2/longitudinal_virtual_fish.py

## [t086] Cross-reference H→MGUS DEGs with GC B cell and Boiarsky NMF programs
- priority: P1
- status: done
- aspects: [hypothesis-testing, causal-modeling, computational-analysis]
- related: [question:global-transcriptional-upregulation, discussion:2026-04-07-upstream-of-cytogenetic-events, topic:progression, topic:developmental-origin, topic:germinal-center]
- group: h1-epigenetic
- created: 2026-04-07
- completed: 2026-04-11

**Result:** The H→MGUS upregulation is NOT explained by specific NMF programs or
developmental signatures. Key findings:

1. **W16 (normal PC signature) is NOT selectively lost in MGUS.** 78% of W16 genes
   have positive SumZ (vs 86% background). All 7 W16 DEGs are UP, not down. Binomial
   test for downregulation enrichment: p=0.11. Boiarsky's "normal PC loss" does not
   correspond to the H→MGUS transition in bulk data.

2. **W16 and CXCR4 (W28) show downward bias** in MW rank enrichment (FDR=0.035 and
   0.23 respectively). These are the only programs with mean SumZ below background.
   W16 genes are globally less upregulated than average — consistent with partial
   PC-identity loss, but not the dominant signal.

3. **Plasma cell maturation signature enriched.** TARTE_PLASMA_CELL_VS_PLASMABLAST_UP
   is the strongest overlap (38 genes, OR=2.1, FDR=0.011). H→MGUS DEGs include genes
   marking mature PC differentiation. This suggests the H→MGUS transition captures
   ongoing PC maturation, not dedifferentiation.

4. **No NMF program strongly enriched among upregulated DEGs.** W3 (t(11;14)-associated)
   and W9 (extracellular signaling) have marginal overlaps (p~0.05, FDR>0.2). The
   665 DEGs are not dominated by any single NMF program — supporting the "global,
   non-specific upregulation" interpretation from the Hallmark analysis.

**Interpretation for H1-C4:** The global upregulation at H→MGUS is real biology
(not dominated by normalization artifact), but it is non-specific — it doesn't map
onto any single transcriptional program. The slight downward bias of W16 genes is
consistent with partial PC-identity erosion superimposed on global transcriptional
amplification. The normalization artifact hypothesis (C) is weakened but not fully
excluded; scRNA-seq cross-reference (Boiarsky per-cell data) remains the definitive test.

Script: scripts/hypotheses/h1/h_mgus_boiarsky_crossref.py

## [t094] OIP5-E2F1 correlation test in MMRF
- priority: P2
- status: done
- aspects: [hypothesis-testing, causal-modeling, computational-analysis]
- related: [hypothesis:h2-cytogenetic-distinct-entities, topic:gain1q-neg-unique-genes, topic:E2F, topic:OIP5, topic:correlation, topic:feedback-loop]
- created: 2026-04-08
- completed: 2026-04-09

**Result:** OIP5-E2F1 correlation is identical between strata (gain(1q)+: rho=0.602,
gain(1q)-: rho=0.607, Fisher z p=0.92). The E2F circuit operates equally in both
strata — the stratum-specific E2F enrichment reflects different downstream gene-set
compositions, not different upstream circuit coupling. Evidence type: neutral for H2-C2.
Script: scripts/hypotheses/h2/oip5_e2f1_correlation.py

## [t098] Literature: matched molecular + symptom/phenotype datasets in MM
- priority: P2
- status: proposed
- aspects: [hypothesis-testing, causal-modeling, computational-analysis]
- related: [question:overlooked-phenotype-heterogeneity, hypothesis:h2-cytogenetic-distinct-entities, topic:clinical-phenotype, topic:datasets, topic:symptoms, topic:subtypes]
- group: phenotype
- created: 2026-04-08

Search for MM cohorts that have both deep molecular profiling (WGS/RNA-seq + cytogenetics)
AND granular clinical phenotype data (bone disease severity, renal function, symptom scores,
QoL, EMD). Check MMRF CoMMpass clinical annotation depth (patient-reported outcomes? bone
survey data?). Check Connect MM registry, IFM cohorts, and SEER-linked genomic datasets.
Goal: identify data sources where we can test whether molecular subtypes have distinct
symptom profiles.

## [t099] Extract Samur 2024 subtype transition matrix
- priority: P2
- status: active
- aspects: [hypothesis-testing, causal-modeling, computational-analysis]
- related: [question:subtype-transition-directionality, hypothesis:h2-cytogenetic-distinct-entities, hypothesis:h4-attractor-convergence, topic:subtype-transition, topic:relapse, topic:convergence, topic:Samur2024]
- group: h4-attractor
- created: 2026-04-08

From Skerget/Samur 2024 (Nature Genetics): extract the full expression subtype transition
matrix (diagnosis → relapse). Paper reports 13/49 (26.5%) transition INTO PR (convergence),
but non-PR transitions are only shown in Figure 5a (alluvial) — not quantified in text.
Remaining work: access Supplementary Fig 15 or digitize alluvial to get the full matrix.
Key questions: (a) what happens to the 73.5% who don't go to PR? (b) Is it block-diagonal
(within-cytogenetic-group)? (c) Does transition rate correlate with treatment intensity?

## [t105] MMRF mutation x expression interaction model (upgraded t071)
- priority: P2
- status: done
- aspects: [software-development]
- related: [task:t067, task:t071, interpretation:2026-04-04-mmrf-mutation-integration, topic:mutations, topic:interaction, topic:Cox, topic:MMRF]
- created: 2026-04-09
- completed: 2026-04-09

**Result:** KRAS: 53 genes with significant interaction (BH<0.1 / 4999 tested).
MAPK_combined: 14 significant (BH<0.1 / 4998). KRAS more specifically modifies
expression-survival slopes than the heterogeneous MAPK group. Top interaction genes:
C1QB, BATF2, BET1, MSMO1, IGF1R, BCL2L11, TMEM165. Provides per-gene statistical
evidence that t067's stratification approach could not. Subsumes t071.
Script: scripts/stages/progression/mmrf_mutation_interaction.py

## [t106] Mutation stratification permutation calibration (upgraded t088)
- priority: P2
- status: done
- aspects: [software-development]
- related: [task:t067, task:t088, interpretation:2026-04-04-mmrf-mutation-integration, topic:mutations, topic:permutation, topic:null-model, topic:statistics]
- created: 2026-04-09
- completed: 2026-04-09

**Result:** Null result. Random equal-size splits produce comparably low rho (null
means 0.08-0.32). No driver reaches significance (all empirical p>0.05, TP53 closest
at p=0.075). The t067 ranking divergence (rho<0.35) is primarily a sample-size artifact,
not evidence of mutation-specific biology. The interaction model (t105) is the appropriate
test. Subsumes t088.
Script: scripts/hypotheses/h3/mutation_permutation_calibration.py

# ── New Tasks (2026-04-11 backlog review) ──────────────────────────────────────

## [t110] PHF19 mediation analysis: proliferation vs immune evasion
- priority: P2
- status: done
- aspects: [hypothesis-testing, causal-modeling, computational-analysis]
- related: [hypothesis:h1-epigenetic-commitment, inquiry:h1-prognosis, question:phf19-survival-mechanism-mediation, topic:PHF19, topic:mediation, topic:survival, topic:proliferation, topic:immune-evasion]
- group: h1-epigenetic
- created: 2026-04-11
- completed: 2026-04-11

**Result:** Both pathways contribute, but proliferation dominates.

| Model | PHF19 coef | PHF19 p | Retention |
|-------|-----------|---------|-----------|
| A: PHF19 only (total) | 0.569 | 2.3e-17 | 100% |
| B: + gain(1q) | 0.533 | 7.4e-15 | 93.7% |
| C: + E2F+G2M (proliferation) | 0.438 | 5.9e-7 | 77.0% |
| D: + IFN-gamma | 0.593 | 5.4e-18 | 104.3% |
| F: + E2F+G2M + IFN-gamma | 0.448 | 3.0e-7 | 78.8% |
| H: + gain(1q) + E2F+G2M + IFN-gamma | 0.416 | 2.5e-6 | 73.1% |

Key findings:
- **77% of PHF19 effect retained** after controlling for proliferation (p=5.9e-7)
- **~23% mediated by proliferation** (E2F/G2M pathway scores)
- **IFN-gamma alone does NOT mediate** PHF19 effect (104% retention — slight suppression)
- **BUT IFN-gamma adds significant info beyond proliferation** (LRT p=0.034)
- **PHF19 highly significant in all models** including the fully adjusted (p=2.5e-6)
- PHF19 strongly correlated with proliferation (r=0.62-0.65) but weakly with IFN (r=0.15-0.20)

Interpretation: PHF19's prognostic value is partially but not primarily mediated by
proliferation. The IFN pathway is NOT a mediator in the Baron-Kenny sense (controlling
for it increases PHF19's effect), but it adds independent survival information beyond
proliferation (LRT p=0.034). This is consistent with the dual-branch model: the two
mechanisms operate in parallel, not sequentially. The IFN-gamma score may be acting as
a negative confounder (suppressor variable) — PHF19 increases IFN silencing while low
IFN independently predicts worse survival, creating a suppression effect.

Script: scripts/hypotheses/h1/phf19_mediation_analysis.py

## [t112] PHF19 survival effect stratified by t(4;14) status
- priority: P2
- status: proposed
- aspects: [hypothesis-testing, causal-modeling, computational-analysis]
- related: [hypothesis:h1-epigenetic-commitment, inquiry:h1-prognosis, question:nsd2-phf19-mirror-polycomb, topic:PHF19, topic:t414, topic:NSD2, topic:confounding, topic:stratification]
- group: h1-phf19-mechanism
- created: 2026-04-11

The mirror-image Polycomb test showed NSD2 and PHF19 operate at different genomic
loci (question:nsd2-phf19-mirror-polycomb, resolved). But the population-level
confound (t(4;14) -> survival via non-PHF19 mechanisms) is not yet tested.

**Approach:** Repeat t082-style Cox model (PHF19 ~ survival) stratified by virtual
FISH t(4;14) status. If PHF19 retains significance in t(4;14)- patients, the
other_high_risk_lesions backdoor is closed at both locus and population levels.

# ── DAG-Derived Tasks (2026-04-11 H2 model formalization) ─────────────────────
# Source: doc/discussions/2026-04-11-h2-dag-implications.md

## [t113] Stratum-specific Cox covariate comparison (gain(1q)+/- in MMRF)
- priority: P2
- status: done
- aspects: [hypothesis-testing, causal-modeling, computational-analysis]
- related: [hypothesis:h2-cytogenetic-distinct-entities, inquiry:h2-subtype-architecture, topic:stratification, topic:Cox, topic:distinct-entities, topic:covariates]
- group: h2-cytogenetic
- created: 2026-04-11
- completed: 2026-04-11

Test the "distinct entities" claim by comparing which covariates are significant
in gain(1q)+ vs gain(1q)- Cox survival models. If the significant predictors
differ qualitatively (not just quantitatively), these are structurally different
diseases — the strongest model-based evidence for H2.

**Approach (MMRF):**
1. Fit identical Cox models in gain(1q)+ and gain(1q)- strata
2. Covariates: ISS, top pathway scores (E2F, G2M, IFN-gamma, MITOTIC_SPINDLE),
   PHF19, key 1q genes (CKS1B, MCL1)
3. Compare: which covariates are significant in each stratum? Do the rankings of
   covariate importance differ?
4. Formal test: interaction model (gene × stratum) for top-10 covariates

**Result:** H2 "distinct entities" claim **weakened by this test**.

- **0/10 discordant covariates.** No covariate is significant in one stratum and
  non-significant (p>0.1) in the other. Pre-registered criterion not met.
- **Coefficient correlation r=0.93 (p=0.0001).** The covariate importance structure
  is nearly identical between strata.
- PHF19, CKS1B, MELK, E2F_TARGETS, G2M_CHECKPOINT: significant in BOTH strata
- MCL1, IFN-gamma, IFN-alpha: non-significant in BOTH strata
- MITOTIC_SPINDLE: borderline (p=0.017 in 1q+, p=0.051 in 1q-) — closest to
  discordance but doesn't meet the pre-registered threshold

**Interpretation:** gain(1q)+/- strata have the SAME survival architecture at the
covariate level — same predictors matter in both, with quantitative (not qualitative)
differences. This supports "risk strata of the same disease" over "distinct entities."

**Caveat:** This tests univariate importance of 10 pre-selected covariates. A broader
or multivariate analysis might reveal differences.

Script: scripts/hypotheses/h2/stratum_specific_cox_comparison.py

## [t114] Characterize the ~13 genuinely stratum-specific gain(1q)- genes
- priority: P2
- status: done
- aspects: [hypothesis-testing, causal-modeling, computational-analysis]
- related: [hypothesis:h2-cytogenetic-distinct-entities, inquiry:h2-subtype-architecture, question:non-1q-program-driver, topic:stratum-specific, topic:gain-1q-negative, topic:characterization]
- group: h2-cytogenetic
- created: 2026-04-11
- completed: 2026-04-11

**Reframed (2026-04-11):** The original scope (TF screen for E2F program driver)
was based on the assumption that E2F enrichment in gain(1q)- unique genes was
stratum-specific. Investigation showed it is **rank displacement** — all E2F genes
are prognostic in both strata. The truly stratum-specific genes (~13 with p>0.05
in gain(1q)+) are NOT E2F targets: NT5C, RPF2, HMGB1P12, GSR, CCNB1IP1, etc.

**Reframed approach:**
1. Extract the ~13 genes with p>0.05 in gain(1q)+ from the stratified analysis
2. Gene-set enrichment: do they form a coherent program? (nucleotide metabolism?
   ribosome biogenesis? Something else?)
3. Literature validation: are any known MM biology genes?
4. Chromosomal location: are they clustered on a specific locus?
5. Expression comparison: are they differentially expressed between strata, or
   only differentially prognostic?

**Result:** The 13 genes form a **coherent program** centered on ribosome
biogenesis and protein synthesis regulation.

- 125 gene sets at FDR<0.1; 12/13 genes appear in at least one significant set
- Top enrichments: GOBP_PROTEIN_LOCALIZATION_TO_NUCLEOLUS (RPF2, POLR1A),
  GOBP_RIBOSOMAL_LARGE_SUBUNIT_BIOGENESIS (RPF2, FASTKD2),
  GOBP_PROTEIN_COMPLEX_BIOGENESIS (6 genes)
- Chromosomal: 3 genes on chrX (MID1IP1, VCX2, HMGB1P12), 2 on chr8 (GSR, CYRIB)
- RPF2 (ribosome biogenesis), POLR1A (RNA polymerase I), FASTKD2 (mitochondrial
  RNA processing), SCAP (SREBP pathway, lipid/cholesterol)
- The program is ribosome/translation/biosynthesis — a different proliferation
  strategy than the 1q+ mitotic spindle/PRC2 pathway

**Interpretation:** The `sci:Unknown: non_1q_driver` node is real but small.
The gain(1q)- specific biology is a ribosome/translation program, not E2F.
This is consistent with an alternative proliferation strategy: gain(1q)+ disease
proliferates via mitotic machinery + epigenetic silencing; gain(1q)- disease
may proliferate via translation/ribosome amplification.

Script: scripts/hypotheses/h2/stratum_specific_gene_characterization.py

## [t115] HD stratification characterization (H2 upgrade gate)
- priority: P1
- status: done
- aspects: [hypothesis-testing, causal-modeling, computational-analysis]
- related: [hypothesis:h2-cytogenetic-distinct-entities, inquiry:h2-subtype-architecture, question:hyperdiploidy-mechanism, topic:hyperdiploidy, topic:stratification, topic:replication]
- group: h2-cytogenetic
- created: 2026-04-11
- completed: 2026-04-11

**Result:** HD stratification partially replicates the gain(1q)+/- architecture
model (2/3 criteria met). Key findings:

1. **HD+ unique genes dominated by cancer-testis antigens** (GAGE/MAGE/SSX on chrXp,
   OR=11.4, FDR<0.001). NOT odd-chromosome dosage. Novel finding.
2. **HD- specific genes form hypoxia/metabolism program** (DDIT4, PFKP, OPN3; 161
   enriched sets FDR<0.1). Zero overlap with gain(1q)- ribosome program.
3. **Cox architecture shared** (0 discordant covariates, r=0.794). Near-miss on
   r>0.80 threshold (gain(1q) was r=0.93).
4. **Cross-stratification overlap low** (Jaccard 0.098-0.183). Each stratification
   reveals distinct biology.

H2 upgrade recommendation: partial. Qualitative pattern supports the model;
quantitative threshold is a near-miss.

Script: scripts/hypotheses/h2/hd_stratification_characterization.py
Interpretation: doc/interpretations/2026-04-11-hd-stratification-characterization.md

# ── Evidence Chain Weak Points (2026-04-11) ───────────────────────────────────
# Source: systematic review of upstream weak points in H1/H2 DAGs

## [t116] PRC2 retargeting mechanistic verification using public ChIP-seq
- priority: P1
- status: done
- aspects: [hypothesis-testing, causal-modeling, computational-analysis]
- related: [hypothesis:h1-epigenetic-commitment, inquiry:h1-prognosis, topic:PRC2, topic:H3K27me3, topic:ChIP-seq, topic:mechanism, topic:verification]
- group: h1-epigenetic
- created: 2026-04-11
- completed: 2026-04-11

**The most consequential unverified node in H1.** Every downstream claim flows
through PRC2 retargeting (PHF19 → PRC2 → IFN silencing + cell-cycle silencing),
but we've never observed H3K27me3 changes at IFN loci in MM cells. All evidence
is external (Ren 2019 knockdown in cell line) + correlational (mirror-image test).

**Approach (using public data):**
1. Obtain published H3K27me3 ChIP-seq data from MM cell lines (check ENCODE,
   Roadmap, or MM-specific datasets — e.g., Ledergor, Ordoñez 2020)
2. Classify genes as H3K27me3-marked vs unmarked at their promoters
3. Test: is PHF19 expression specifically anti-correlated with H3K27me3-marked
   genes (not unmarked genes) in MMRF RNA-seq?
4. If yes: circumstantial evidence that PHF19's effect operates through PRC2
5. If no: PHF19 may affect gene expression through a non-PRC2 mechanism

**What's at stake:** If PRC2 is NOT the mechanism, H1's title claim ("epigenetic
commitment") is wrong, the ratcheting model loses its basis, and the H1-H2
connection (via epigenetic architecture) breaks. The correlation-level findings
(PHF19 predicts survival, IFN is suppressed) would still hold.

**Result (MSigDB proxy approach):** PRC2 mediation **supported** with caveats.

| Test | Result | Interpretation |
|------|--------|---------------|
| IFN PRC2-target vs non-target | mean r=0.025 vs 0.085, MW p=0.011 | PRC2-target IFN genes have MORE suppressed PHF19 correlation |
| KONDO_EZH2_TARGETS × IFN | mean r=-0.007 vs 0.083, p=0.026 | Strongest per-set signal; IFN∩KONDO genes actually anti-correlated with PHF19 |
| Controls (OXPHOS, MYC) | Zero PRC2 overlap | PRC2 targets are developmental regulators, not metabolic genes — controls uninformative |

Key findings:
- 17 IFN genes are PRC2 consensus targets. These show PHF19 correlations pulled
  toward zero/negative relative to the 207 non-target IFN genes.
- The effect is modest (Δr ≈ 0.06) but consistent across PRC2 set definitions.
- KONDO_EZH2_TARGETS (cancer-specific) shows the clearest signal.
- Direction matches prediction: PHF19 specifically suppresses PRC2-targetable
  IFN genes more than non-targetable IFN genes.

**Caveats:**
- PRC2 sets are from ES cells (BENPORATH) or non-MM contexts. MM-specific
  H3K27me3 landscapes (Ren 2019 GSE135890) would be stronger evidence.
- Effect is small — PRC2 is likely one mechanism among several.
- PHF19 brings PRC2 to NEW loci; constitutive PRC2 targets may not fully
  capture PHF19-specific retargeting.

**Next step:** Download Ren 2019 Supplemental Table S2 (2,366 PHF19-dependent
genes from MM cell line ChIP-seq) for MM-specific validation.

Script: scripts/hypotheses/h1/prc2_locus_specificity.py

## [t117] Boiarsky scRNA-seq per-cell normalization artifact test
- priority: P2
- status: done
- aspects: [hypothesis-testing, causal-modeling, computational-analysis]
- related: [hypothesis:h1-epigenetic-commitment, question:global-transcriptional-upregulation, inquiry:h1-progression, topic:normalization, topic:scRNA-seq, topic:Boiarsky, topic:per-cell, topic:artifact]
- group: h1-epigenetic
- created: 2026-04-11
- completed: 2026-04-11

**The definitive test for H1-C4 (global transcriptional upregulation).** t086
showed the bulk upregulation is non-specific and not driven by any NMF program.
But bulk RNA-seq cannot distinguish real per-cell upregulation from composition
changes (fewer non-PC cells in MGUS samples → apparent upregulation of PC genes).

**Approach (using GSE193531 data, already downloaded):**
1. Load Boiarsky scRNA-seq UMI count matrix (/data/raw/geo/GSE193531/)
2. Compare per-cell total UMI counts between healthy PC and MGUS PC
   (BEFORE normalization — this is the key: does each MGUS cell produce more
   transcripts than each healthy cell?)
3. Compare per-cell gene detection rates (n_genes) between healthy and MGUS
4. If MGUS cells have higher UMI/gene counts at the per-cell level, the global
   upregulation is real biology (chromatin opening → more transcription)
5. If counts are similar, the bulk signal is a composition/normalization artifact

**Data available:** GSE193531_umi-count-matrix.csv.gz (54MB) +
GSE193531_cell-level-metadata.csv.gz (cell-level disease stage annotations).
The metadata already has `n_counts` and `n_genes` per cell.

**Result:** Global transcriptional upregulation is **real per-cell biology**, not a
normalization artifact.

| Comparison | Metric | Ratio | p-value | Effect r |
|------------|--------|-------|---------|----------|
| Healthy normal vs MGUS neoplastic | n_counts | 1.55 | 1.2e-21 | 0.32 |
| Healthy normal vs MGUS neoplastic | n_genes | 1.46 | 3.4e-44 | 0.47 |
| Healthy normal vs MGUS normal | n_counts | 1.07 | 0.41 | 0.02 |
| MGUS normal vs MGUS neoplastic | n_counts | 1.45 | 2.1e-11 | 0.28 |

Key findings:
- MGUS neoplastic cells produce 55% more UMI and detect 46% more genes per cell
  than healthy normal PCs (p<1e-21). This is BEFORE any normalization.
- MGUS normal cells are NOT significantly different from healthy normal cells
  (p=0.41 for UMI counts). The upregulation is specific to neoplastic cells.
- Within MGUS biopsies, neoplastic cells have 45% more UMI than normal cells from
  the same patient (p=2.1e-11). This controls for batch/capture differences.

**Caveat:** Patient-level MW test is non-significant (p=0.37) due to only 3 MGUS
patients with neoplastic cells. The cell-level test is highly significant but
pseudoreplication inflates it. Truth is between the two: real effect, uncertain
magnitude.

**For H1-C4:** Normalization artifact hypothesis is **substantially weakened**.
The global upregulation reflects real per-cell transcriptional amplification in
neoplastic PCs. The within-biopsy comparison (neoplastic vs normal from same MGUS
patient) is the strongest evidence — eliminates batch, capture, and sequencing depth
confounds.

Script: scripts/hypotheses/h1/normalization_artifact_test.py

# ── H2 Reframing Tasks (2026-04-11) ──────────────────────────────────────────
# Source: doc/discussions/2026-04-11-h2-reframing-synthesis.md

## [t118] Stratum-specific mediation: PHF19 vs ribosome program per stratum
- priority: P2
- status: done
- aspects: [hypothesis-testing, causal-modeling, computational-analysis]
- related: [hypothesis:h2-cytogenetic-distinct-entities, inquiry:h2-subtype-architecture, discussion:2026-04-11-h2-reframing-synthesis, topic:mediation, topic:stratification, topic:ribosome, topic:PHF19, topic:divergent-mechanisms]
- group: h2-cytogenetic
- created: 2026-04-11
- completed: 2026-04-11

The key discriminating test for the "convergent endpoints, divergent mechanisms"
model. Run t110-style mediation SEPARATELY in each gain(1q) stratum, adding a
ribosome program score (mean of RPF2, POLR1A, FASTKD2, SCAP, CYRIB, + other t114
genes) as an additional mediator.

**Result:** Partially confirmed — reveals a more nuanced picture than predicted.

**Pre-registered predictions and outcomes:**
1. PHF19 effect larger in 1q+: **YES** (coef 0.788 vs 0.338) ✓
2. Ribosome effect larger in 1q-: **NO** (coef 0.424 vs 0.444) ✗

**The surprise: the ribosome program's RELATIONSHIP to proliferation differs.**

| Metric | gain(1q)+ | gain(1q)- |
|--------|-----------|-----------|
| PHF19 total coef | **0.788** | 0.338 |
| PHF19 % mediated by proliferation | 12.0% | 25.3% |
| Ribosome total coef | 0.444 | **0.424** |
| Ribosome % mediated by proliferation | **81.5%** | **12.8%** |

Key finding: The ribosome program has similar total effects in both strata (~0.44),
but its relationship to proliferation is completely different:
- In gain(1q)+: ribosome effect is 81.5% mediated by proliferation (redundant with E2F/G2M)
- In gain(1q)-: ribosome effect is only 12.8% mediated (largely INDEPENDENT of proliferation)

In gain(1q)+, the ribosome program is a passenger of proliferation (controlling
for E2F/G2M eliminates it). In gain(1q)-, the ribosome program provides independent
survival information beyond proliferation. This is the divergent mechanism: not a
different total effect size, but a different causal structure.

Also: in gain(1q)-, ribosome score (p=0.0012) DISPLACES PHF19 (p=0.042→0.054 when
both included). The ribosome program is the dominant independent predictor in 1q-.

Script: scripts/hypotheses/h2/stratum_specific_mediation.py

## [t124] Ren 2019 PHF19-dependent gene cross-reference (H1 upgrade gate)
- priority: P1
- status: done
- aspects: [hypothesis-testing, causal-modeling, computational-analysis]
- related: [hypothesis:h1-epigenetic-commitment, inquiry:h1-prognosis, task:t116, topic:PHF19, topic:PRC2, topic:IFN, topic:ChIP-seq, topic:knockdown, topic:mechanism, topic:verification]
- group: h1-epigenetic
- created: 2026-04-11
- completed: 2026-04-11

**The final H1 upgrade gate.** Re-analyzed Ren 2019 PHF19-KD RNA-seq from MM1S
myeloma cells (GSE136410) to validate the PRC2 retargeting -> IFN silencing
mechanism with MM-specific data. Could not download the paper's Supplemental
Table S2 (2,366 genes) due to PMC JS challenge; re-derived from deposited
Salmon counts using rank-based enrichment (more appropriate than thresholding
given n=3 vs n=4 replicates).

**Result:** IFN pathway genes are **strongly derepressed** upon PHF19 knockdown
in MM1S cells:

| Test | Result | Interpretation |
|------|--------|----------------|
| IFN (union) rank shift | MW p=6.4e-09, d=0.49 | IFN genes shift UP on PHF19 KD — PRC2 normally silences them |
| IFN-alpha rank shift | MW p=3.4e-08, d=0.72 | IFN-alpha response most affected |
| IFN-gamma rank shift | MW p=8.2e-07, d=0.43 | IFN-gamma also significantly derepressed |
| E2F targets rank shift | MW p=8.3e-89, d=-1.83 | E2F targets massively DOWN — cell cycle arrest on PHF19 loss |
| OXPHOS (control) | p=1.0 | No derepression — negative control holds |
| mTORC1 (control) | p=1.0 | No derepression — negative control holds |
| gain(1q)- ribosome (neg ctrl) | p=0.92 | PHF19-independent — negative control holds |
| Rescue validation (IFN) | MW p=3.0e-10 | IFN genes go back DOWN on PHF19 rescue — reversible |
| Rescue validation (E2F) | MW p=2.1e-83 | E2F targets go back UP on rescue — reversible |

Top derepressed IFN genes: GBP2 (3.3x), RSAD2 (3.2x), IFI44L (2.9x), GBP4
(2.8x), XAF1 (2.7x) — canonical interferon-stimulated genes.

**Key nuance:** ES-cell PRC2 consensus targets are NOT preferentially derepressed
(MW p=0.55), suggesting PHF19's IFN silencing may be MM-specific PRC2 retargeting
rather than activation at constitutive PRC2 sites. This is consistent with the
"retargeting" model: PHF19 brings PRC2 to NEW loci in MM, not the same loci as
in ES cells.

Fisher test (threshold-based, secondary): IFN enriched among FC>=1.5 KD-derepressed
genes (OR=1.92, p=0.002; IFN-alpha OR=3.72, p=2.8e-6). 28 IFN genes derepressed
at FC>=1.5 threshold.

**H1 upgrade assessment:** This was the final remaining gate. Combined with:
- C2 replication (5/5 via t091)
- C4 single-cell evidence (t117)
- PRC2 proxy (t116, p=0.011)
- Mediation analysis (t110)
- Bayesian edges (t107, t120)
H1 is ready for upgrade to "supported."

Script: scripts/hypotheses/h1/ren2019_phf19_crossref.py

## [t125] Mediation asymmetry null model (retraction)
- priority: P2
- status: done
- aspects: [hypothesis-testing, causal-modeling, computational-analysis]
- related: [hypothesis:h2-cytogenetic-distinct-entities, task:t118, task:t121, task:t123, discussion:2026-04-11-mediation-asymmetry-general, topic:mediation, topic:null-model, topic:artifact, topic:selection-bias]
- group: h2-cytogenetic
- created: 2026-04-11
- completed: 2026-04-11

**Result:** The observed 80/20 mediation asymmetry across three stratum-specific
programs (ribosome, hypoxia, CTA) does NOT survive a matched-effect null.

- 0/6 observations are significant outliers (p<0.05)
- 2/3 "home" stratum observations identical to null (p=1.000)
- Ribosome is closest to significance (home p=0.058)
- Null means for "other" strata already substantial (23-49%), driven by baseline
  Cox-proliferation correlation differences between strata
- All 3 "other" observations are directionally above null (+32 to +56 pts) but
  none reach p<0.05 due to wide null variance

**Implication:** The cross-program quantitative pattern is largely a selection
+ multicollinearity artifact. The underlying biological interpretation (divergent
upstream mechanisms) is NOT affected — it rests on gene set enrichment,
longitudinal FISH (t055), and stratum-specific rankings, not on mediation %.

Script: scripts/hypotheses/h2/mediation_null_model.py
Interpretation: doc/interpretations/2026-04-11-mediation-null-model-result.md

## [t197] Execute GSE155135 replication of Ren 2019 PHF19-KD signature (Priority 1 from t191 triage) — pre-register concordance metric + GSEA
- priority: P1
- status: done
- aspects: [hypothesis-testing, causal-modeling, computational-analysis]
- related: [hypothesis:h1-epigenetic-commitment, task:t124, task:t190, task:t191, pre-registration:2026-04-14-t197-gse155135-ezh2i-replication, interpretation:2026-04-14-t197-gse155135-ezh2i-replication]
- group: causal-identification
- created: 2026-04-14
- completed: 2026-04-14

**Verdict: Weakly_replicated (1/2)** under the §10 entry-2 adjusted rubric (EPZ-6438
turned out not to be in GSE155135 — only GSK126 — so the contrast set drops 4→2 and
"Replicated" becomes 2/2). **No formal H1 identification upgrade.** But the
per-pathway breakdown is informative: IFN-α/IFN-γ HALLMARK + Ren-2019-derived IFN-up
sets all replicate strongly in BOTH cell lines (NES > +2.0, padj < 1e-4 across the
board); E2F-targets only replicates in RPMI-8226 (NES=−1.47 padj=0.0075), not MM.1S
(NES=−1.09 padj=0.32). H1 IFN arm of edge 5 now has 3 interventional anchors (Ren
2019 PHF19-KD + Ishiguro 2021 GSK126 in MM.1S + Ishiguro 2021 GSK126 in RPMI-8226);
H1 E2F arm of edge 6 remains effectively single-anchor (Ren 2019 MM.1S only).
Cross-line Spearman ρ = 0.235 (just above the §8 0.2 floor) — pathway-level
coordinated responses replicate while gene-level signatures are largely
line-specific. Joint with the t190 CRISPR null, the picture sharpens: PRC2
perturbation reactivates IFN broadly but doesn't engage the cell-cycle inhibitor
circuit consistently. See `interpretation:2026-04-14-t197-gse155135-ezh2i-replication`
for the full breakdown and `doc/figures/dags/h1-prognosis.edges.yaml` edges 5/6 for
the data_support updates.

Scripts: scripts/hypotheses/h1/_t197_derive_ren_gene_sets.py;
scripts/hypotheses/h1/_t197_limma_fgsea.R; scripts/hypotheses/h1/_t197_robustness.R;
scripts/hypotheses/h1/gse155135_ezh2i_replication.py.

Surfaced by t191 (PRC2/PHF19 perturbation dataset inventory). Given t190 ruled out the
viability path, the transcriptomic-intervention path is the remaining route to an H1
identification upgrade. **GSE155135** is the single highest-value replication target:
- Ishiguro 2021, PMID 33579913, DOI 10.1038/s41420-020-00400-0
- MM.1S + RPMI-8226, GSK126 + EPZ-6438 (= tazemetostat)
- n=16; microarray
- Paper's own conclusion names IFN-signal activation as the mechanism
- Same cell line as Ren 2019 (MM.1S) plus RPMI-8226 for robustness

**Pre-register BEFORE any fits (extend doc/pre-registrations/):**
- Concordance metrics: fraction of Ren 2019 IFN-derepressed set also up in GSE155135;
  fraction of Ren 2019 E2F-target set also down; both per-arm (GSK126, EPZ-6438) and
  per-cell-line (MM.1S, RPMI-8226).
- Verdict rubric:
  - Replicated: ≥2 of 4 (arm × cell line) combinations show concordant direction at FDR<0.05.
  - Weakly replicated: exactly 1/4 combination concordant at FDR<0.05.
  - Null: 0/4 concordant.
  - Opposite: any combination significantly inverted.
- Decision: If replicated, H1 edges 4/5/6/12 identification axis upgrades
  `observational` → `interventional-replicated`. If null, flag H1 mechanism as
  single-anchor-interventional (Ren 2019 MM.1S only).

**Pipeline:**
1. Download GSE155135 series matrix + metadata from GEO.
2. QC + limma differential expression (GSK126 vs DMSO; EPZ-6438 vs DMSO; per cell line).
3. GSEA against HALLMARK_INTERFERON_ALPHA_RESPONSE, HALLMARK_INTERFERON_GAMMA_RESPONSE,
   HALLMARK_E2F_TARGETS, HALLMARK_G2M_CHECKPOINT.
4. Also: Ren 2019-specific gene set (the IFN-up genes with d>+0.5 from t124 — extract
   from the t124 outputs if available, else derive from GSE136410).
5. Score concordance; write interpretation.

**After t197:** if replicated, open a small follow-up to update edge identifications
via the existing `doc/figures/dags/_add_identification.py` (it only currently detects
t124 as interventional — extend its rule to include t197 + dataset hit).

## [t203] Ledergor 2018 scRNA-seq replication of t174 Q1/Q2/Q3 — cohort independence for PC-maturity findings
- priority: P1
- status: active
- aspects: [hypothesis-testing, causal-modeling, computational-analysis]
- related: [task:t174, task:t172, task:t204, task:t214, hypothesis:h1-epigenetic-commitment, hypothesis:h2-cytogenetic-distinct-entities, question:ribosome-axis-pc-continuum-vs-nucleolar-stress, report:2026-04-16-scrna-replication-shortlist, interpretation:2026-04-17-t203-ledergor-replication]
- group: causal-dag-validation
- created: 2026-04-14

**Panel executed 2026-04-17** (`interpretation:2026-04-17-t203-ledergor-replication`).
Formal verdict = `inconclusive_protocol_failure` (Q1/Q2 student-t continuous fits
fail PPC shape statistics). Face-value Q3 (NB, PPC pass) does **not** replicate
the t174 per-cell collapse: β\_ribosome = +0.544 under PC-maturity + phase +
library-size adjustment, P(β > 0) = 0.983. Q1 tumor-vs-healthy sign-flip does
not replicate: both Ledergor cohorts give positive β\_pc\_mature. Q2 face-value
nucleolar-stress signal positive, but RPL-removal sensitivity not fit.

**Narrow follow-ups queued:** refit Q1/Q2 with NB likelihood on raw ribosome-gene
counts (PPC-fix without changing sign/magnitude story), and add the
`sens_no_rpl` Q2 variant on the existing cache. Both are cheap reruns on the
staged infrastructure.

t174 used Boiarsky 2022 scRNA-seq (17 tumor + 8 NBM). Replication in an independent
MM scRNA-seq cohort is pre-committed (pre-reg §8.6 queued action) and tests whether:

(i) Q3 Full collapse replicates (PC-maturity + phase sufficient per-cell adjuster)
(ii) Tumor/NBM β_pc_mature sign-flip (t174 P7; tumor −0.31 vs NBM +0.51) replicates
(iii) Q2 RPL-corrected nucleolar-stress signal (β_ns ≈ +0.18) replicates

**Data source:** Ledergor et al. 2018 *Nat Med* (GSE117156, ~40 patients incl.
MGUS/SMM/MM/plasma-cell-leukemia + healthy BM); access patterns as in t173 scope.

**Approach:** reuse the t174 orchestrator infrastructure verbatim — the loader
module (boiarsky_loader) can be generalized or cloned for Ledergor. Signatures
are already locked in data/signatures/. Full-precision wall-clock estimate ~4-6
hrs based on t174 timings.

**Dataset triage (2026-04-16):** from `archive/mm_singlecell_datasets.tsv`, use
Ledergor2018 as the **primary low-friction replication cohort**. Processed counts
are available via HCA / CELLxGENE, it includes healthy + MM, and it is genuinely
independent of Boiarsky. Keep DeJong2021 as the first backup if Ledergor is
inconclusive for protocol reasons; defer EGA/dbGaP cohorts (Walker2024, Dang2023,
John2023, Landau2020) unless the low-friction path fails. See
`report:2026-04-16-scrna-replication-shortlist`.

**Output:** independent verdict JSON + interpretation doc. If (ii) replicates,
upgrade P7 to 'well-supported'. If (ii) fails, cohort-specific; downgrade to
'Boiarsky-specific' until a third cohort.

## [t250] Create H4 attractor-convergence DAG scaffold using TaherianFard2017 basin ops, Huang2013 PCA-proxy, Parreno2024 biophysical-lock
- priority: P1
- status: proposed
- aspects: [causal-modeling]
- related: [hypothesis:h4-attractor-convergence, discussion:2026-04-19-dag-iteration-and-refinement, article:TaherianFard2017, article:Parreno2024, article:Huang2013]
- group: dag-refresh
- created: 2026-04-20

Per discussion:2026-04-19-dag-iteration-and-refinement Q4. Min viable: attractor landscape with basins per lineage (HD/t(4;14)/t(11;14)), depth=delta-E pre-vs-post Hopfield convergence, width=mean pairwise Euclidean distance, irreversibility=TF occupancy at newly-open chromatin, convergent endpoint=proliferation. Keep <=10 edges. Scope-adjacent to t220 (proposition scaffolding) but narrower — the DAG artifact, not the proposition set.

## [t251] Create H6 positive-selection DAG scaffold with 4 sub-claim branches (S1 pre-treatment selection / S2 treatment regime-change / S3 transcriptomic convergence / S4 niche-MGUS)
- priority: P1
- status: proposed
- aspects: [causal-modeling]
- related: [discussion:2026-04-19-dag-iteration-and-refinement, article:Diamond2021, article:Persi2025, article:Cooperrider2025, article:Misund2022, article:Henry2025]
- group: dag-refresh
- created: 2026-04-20

Per discussion:2026-04-19-dag-iteration-and-refinement Q4. Literature anchors: Diamond 2021 (98.2% non-neutral MM), Persi 2025 (dN/dS stable MGUS->MM, post-treatment shift toward neutrality), Cooperrider 2025 (LEN->TP53 selection), Misund 2022 (pathway convergence on proliferation), Henry 2025 (adaptive oncogenesis). Depends on t216 creating specs/hypotheses/h6-positive-selection-mm-progression.md. Scope: build doc/figures/dags/h6-positive-selection.{dot,edges.yaml} exposing the 4 sub-claims as branches.

## [t252] Split h2-subtype-architecture DAG into upstream + downstream sub-figures; expose lineage-conditioned branches per proposition p13
- priority: P2
- status: proposed
- aspects: [causal-modeling]
- related: [discussion:2026-04-19-dag-iteration-and-refinement, inquiry:h2-subtype-architecture]
- group: dag-refresh
- created: 2026-04-20

Per discussion:2026-04-19-dag-iteration-and-refinement Q2/Q3. 43 edges in a single rankdir=TB graph is too dense. Share node identifiers across the split. Make the three lineage-conditioned branches first-class (gain(1q) PHF19/IFN-silencing + HD CTA/chrXp + t(11;14) APOBEC3B/BCL2) per the p13 reframing. Candidate: keep h2-subtype-architecture.{dot,edges.yaml} as upstream half; add h2-subtype-outcomes.{dot,edges.yaml} for downstream half.

## [t253] Promote h1-h2-bridge DAG to a real doc/inquiries/h1-h2-bridge.md inquiry file; link to propositions p07-p11
- priority: P2
- status: proposed
- aspects: [causal-modeling]
- related: [discussion:2026-04-19-dag-iteration-and-refinement, interpretation:2026-04-18-t204-bulk-composition-beyond-pc-maturity-verdict]
- group: dag-refresh
- created: 2026-04-20

Per discussion:2026-04-19-dag-iteration-and-refinement Q2. Bridge DAG is currently 'synthesized-only' (README.md flags this) but is now the primary adjudication battleground for the project's most-contested mechanism question (H1<->H2 link, decision D8). Scope: create doc/inquiries/h1-h2-bridge.md with estimand, assumed DAG, and explicit proposition linkage (p07 through p11). Downstream: graph.trig re-materialization.

## [t254] Encode identification axis via arrow-head shape in _render_styled.py; add persistent footer legend strip to auto-PNG
- priority: P2
- status: proposed
- aspects: [software-development]
- related: [discussion:2026-04-19-dag-iteration-and-refinement]
- group: dag-refresh
- created: 2026-04-20

Per discussion:2026-04-19-dag-iteration-and-refinement Q3. Currently _render_styled.py encodes identification via double-line color (interventional) and vee arrow (longitudinal); the [I]/[L] markers inside labels remain easy to miss. Proposal: use arrow-head shape alone (normal / diamond / odot) for the identification axis so that color (edge_status) and shape (identification) are independently legible. Add a persistent footer legend to the PNG so readers don't need README.md to decode.
