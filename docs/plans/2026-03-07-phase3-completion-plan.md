# Phase 3 Completion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the Phase 3 gate by creating a real research project (3D attention bias for nucleic acid FMs), building a knowledge graph from background research, generating and importing an OpenAlex snapshot, validating everything, and archiving evidence.

**Architecture:** Exemplar-driven — the research project at `~/d/3d-attention-bias/` drives infrastructure needs (OpenAlex snapshot, starter profile). Evidence is archived back in the science plugin repo. Each task produces committed artifacts.

**Tech Stack:** Science plugin commands (`/science:create-project`, `/science:research-topic`, `/science:research-paper`, `/science:create-graph`), `science-tool` CLI, `validate.sh`

**Design doc:** `docs/plans/2026-03-07-phase3-completion-design.md`

## Status

| Task | Description | Status | Commit |
|------|-------------|--------|--------|
| 1 | Scaffold exemplar project | | |
| 2 | Research: nucleic acid foundation models | | |
| 3 | Research: AlphaFold 3 and nucleic acid structure prediction | | |
| 4 | Research: attention bias and positional encoding | | |
| 5 | Research: structure-aware protein language models | | |
| 6 | Research: DNA/RNA 3D structure and function | | |
| 7 | Build knowledge graph from research docs | | |
| 8 | Generate OpenAlex snapshot (infrastructure) | | |
| 9 | Import snapshot into project graph | | |
| 10 | Validate and capture evidence bundle | | |
| 11 | Extract biomedical starter profile (infrastructure) | | |
| 12 | Close Phase 3 gate | | |

---

### Task 1: Scaffold exemplar project

**Working directory:** `~/d/`

**Step 1: Create project directory**

```bash
mkdir -p ~/d/3d-attention-bias
cd ~/d/3d-attention-bias
```

**Step 2: Run `/science:create-project`**

Use these inputs when prompted:

- **Project name:** `3d-attention-bias`
- **Research question:** "Can inferred 3D DNA/RNA structures improve nucleic acid foundation model performance by replacing linear positional attention decay with 3D distance-based attention bias?"
- **Summary:** "Investigate whether incorporating predicted 3D structural distances (via AlphaFold 3) as attention biases in nucleic acid foundation models (DNABERT-2, Nucleotide Transformer, etc.) improves representation quality for tasks where spatial proximity matters — such as regulatory element detection, RNA structure prediction, and chromatin interaction modeling."
- **Tags:** `genomics`, `deep-learning`, `structural-biology`, `attention-mechanisms`, `foundation-models`
- **Data sources:** "AlphaFold 3 predicted structures, existing DNA/RNA benchmark datasets (Genomic Benchmarks, BEACON), pre-trained model weights (DNABERT-2, Nucleotide Transformer, Caduceus)"

**Step 3: Add open questions**

After scaffolding, create `specs/hypotheses/h01-3d-attention-improves-performance.md` using the hypothesis template:

- **Claim:** Replacing linear positional attention bias with 3D structure-derived distance bias improves downstream task performance for nucleic acid foundation models.
- **Falsifiability:** Models fine-tuned with 3D attention bias will show measurably higher accuracy on structure-sensitive benchmark tasks compared to the same models with standard positional encoding.
- **Predictions:** (1) Improvement will be largest on tasks involving distal regulatory interactions. (2) Improvement will be minimal for tasks that are purely sequence-local.

Update `doc/08-open-questions.md` with the 4 open questions from the design doc:
1. Do any existing models already incorporate 3D structural distance effectively?
2. How should 3D distance be incorporated? (pre-training, fine-tuning, regularization)
3. How big of a context window should be considered?
4. When is 3D contextual information more/less important?

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: scaffold 3d-attention-bias research project"
```

---

### Task 2: Research — nucleic acid foundation models

**Working directory:** `~/d/3d-attention-bias/`

**Step 1: Run `/science:research-topic nucleic acid foundation models`**

This should cover: DNABERT-2, Nucleotide Transformer, Caduceus, Evo, RNA-FM, HyenaDNA. Focus on architecture differences (tokenization, context length, pre-training objectives), what positional encoding each uses, and downstream task performance.

**Step 2: Research 3-5 key papers**

Run `/science:research-paper` for each:
1. DNABERT-2 (Zhou et al. 2023) — BPE tokenization, multi-species pre-training
2. Nucleotide Transformer (Dalla-Torre et al. 2023) — large-scale genomic FM
3. Caduceus (Schiff et al. 2024) — bidirectional Mamba for DNA, RC equivariance
4. Evo (Nguyen et al. 2024) — 131k context, StripedHyena architecture
5. HyenaDNA (Nguyen et al. 2023) — long-range genomic modeling with Hyena

Each paper summary goes to `papers/summaries/AuthorYear-short-title.md` and updates `references.bib`.

**Step 3: Verify outputs exist**

```bash
ls doc/background/
ls papers/summaries/
wc -l papers/references.bib
```

Expected: 1 background doc, 3-5 paper summaries, growing references.bib.

---

### Task 3: Research — AlphaFold 3 and nucleic acid structure prediction

**Working directory:** `~/d/3d-attention-bias/`

**Step 1: Run `/science:research-topic AlphaFold 3 and nucleic acid structure prediction`**

Cover: AF3 capabilities for DNA/RNA, RoseTTAFold2NA, trRosettaRNA, RNA secondary vs tertiary structure prediction, accuracy and limitations for nucleic acids specifically.

**Step 2: Research 3-5 key papers**

Run `/science:research-paper` for each:
1. AlphaFold 3 (Abramson et al. 2024) — joint biomolecular structure prediction
2. RoseTTAFold2NA (Baek et al. 2024) — protein-nucleic acid complex prediction
3. trRosettaRNA (Wang et al. 2023) — RNA 3D structure prediction
4. RNA-FM (Chen et al. 2022) — RNA foundation model with structural awareness
5. (Optional) RhoFold (Shen et al. 2024) — RNA structure prediction from sequence

**Step 3: Verify and commit if not auto-committed**

---

### Task 4: Research — attention bias and positional encoding

**Working directory:** `~/d/3d-attention-bias/`

**Step 1: Run `/science:research-topic attention bias mechanisms and positional encoding`**

Cover: absolute vs relative position encodings, ALiBi, RoPE, learned position embeddings, structure-conditioned attention (from protein/molecule domains), attention bias injection techniques.

**Step 2: Research 3-5 key papers**

Run `/science:research-paper` for each:
1. ALiBi (Press et al. 2022) — attention with linear biases
2. RoPE (Su et al. 2024) — rotary position embeddings
3. Relative position encodings in Transformers — Shaw et al. 2018 or Raffel et al. 2020
4. IPA (Invariant Point Attention) from AlphaFold 2 (Jumper et al. 2021) — structure-conditioned attention
5. (Optional) Pair bias in protein structure prediction — Evoformer attention bias mechanism

**Step 3: Verify and commit if not auto-committed**

---

### Task 5: Research — structure-aware protein language models

**Working directory:** `~/d/3d-attention-bias/`

**Step 1: Run `/science:research-topic structure-aware protein language models`**

Cover: ESM-IF, GearNet, SaProt, ESM-2 with structural fine-tuning. Focus on HOW structure information is incorporated — this is the precedent we're building on.

**Step 2: Research 3-5 key papers**

Run `/science:research-paper` for each:
1. ESM-IF (Hsu et al. 2022) — inverse folding with structural conditioning
2. SaProt (Su et al. 2024) — structure-aware protein language model
3. GearNet (Zhang et al. 2023) — geometry-aware relational graph neural network
4. ProTrek (Su et al. 2024) — protein representation with structure-sequence-function alignment
5. (Optional) ESM-2 (Lin et al. 2023) — protein language model at scale

**Step 3: Verify and commit if not auto-committed**

---

### Task 6: Research — DNA/RNA 3D structure and function

**Working directory:** `~/d/3d-attention-bias/`

**Step 1: Run `/science:research-topic DNA and RNA 3D structure and biological function`**

Cover: chromatin looping, enhancer-promoter interactions, TADs, RNA tertiary structure, riboswitches, why 3D context matters for sequence function.

**Step 2: Research 3-5 key papers**

Run `/science:research-paper` for each:
1. Hi-C and chromatin looping — Lieberman-Aiden et al. 2009 or Rao et al. 2014
2. Enhancer-promoter interactions — Furlong & Levine 2018 (review)
3. RNA 3D structure databases — RNA3DHub or similar
4. CTCF and cohesin-mediated looping — relevant review or key paper
5. (Optional) Riboswitches and RNA tertiary structure function

**Step 3: Verify cumulative research**

```bash
ls doc/background/ | wc -l    # expect 5 topic docs
ls papers/summaries/ | wc -l  # expect 15-25 paper summaries
```

---

### Task 7: Build knowledge graph from research docs

**Working directory:** `~/d/3d-attention-bias/`

**Prerequisite:** Tasks 2-6 complete (background docs and paper summaries populated).

**Step 1: Run `/science:create-graph`**

The agent will:
1. Initialize the graph with `graph init`
2. Read all docs in `doc/`, `specs/`, `papers/summaries/`, `notes/`
3. Extract entities, relations, claims with full enrichment flags
4. Use CiTO predicates, Biolink types, rich properties
5. Validate and stamp revision

**Step 2: Verify graph quality**

```bash
uv run --with /mnt/ssd/Dropbox/ai/science/science-tool science-tool graph stats --format json
uv run --with /mnt/ssd/Dropbox/ai/science/science-tool science-tool graph validate --format json
```

Expected:
- `graph stats`: 30+ entities across concept/paper/claim/hypothesis/question types
- `graph validate`: all checks pass

**Step 3: Commit if not auto-committed**

```bash
git add -A
git commit -m "feat: build knowledge graph from background research"
```

---

### Task 8: Generate OpenAlex snapshot (infrastructure)

**Working directory:** `/mnt/ssd/Dropbox/ai/science/science-tool/`

This task runs in the **science plugin repo**, not the exemplar project.

**Step 1: Generate the snapshot**

```bash
cd /mnt/ssd/Dropbox/ai/science/science-tool
uv run --frozen science-tool distill openalex --level subfields
```

This makes a real API call to OpenAlex. Expected output:
- `data/snapshots/openalex-science-map.ttl` (~282 nodes, ~600 triples)
- `data/snapshots/manifest.ttl` (PROV-O metadata)

**Step 2: Verify snapshot**

```bash
wc -l data/snapshots/openalex-science-map.ttl
head -20 data/snapshots/manifest.ttl
```

**Step 3: Commit to science repo**

```bash
cd /mnt/ssd/Dropbox/ai/science
git add science-tool/data/snapshots/openalex-science-map.ttl science-tool/data/snapshots/manifest.ttl
git commit -m "feat: add pre-generated OpenAlex science map snapshot (subfield level)"
```

---

### Task 9: Import snapshot into project graph

**Working directory:** `~/d/3d-attention-bias/`

**Step 1: Import the OpenAlex snapshot**

```bash
uv run --with /mnt/ssd/Dropbox/ai/science/science-tool science-tool graph import /mnt/ssd/Dropbox/ai/science/science-tool/data/snapshots/openalex-science-map.ttl
```

**Step 2: Verify import**

```bash
uv run --with /mnt/ssd/Dropbox/ai/science/science-tool science-tool graph stats --format json
```

Expected: triple counts should increase significantly after import.

**Step 3: Commit**

```bash
git add knowledge/graph.trig
git commit -m "feat: import OpenAlex science map snapshot into knowledge graph"
```

---

### Task 10: Validate and capture evidence bundle

**Working directory:** `~/d/3d-attention-bias/` for running commands, `/mnt/ssd/Dropbox/ai/science/` for archiving.

**Step 1: Run full validation suite in exemplar project**

```bash
cd ~/d/3d-attention-bias

# Graph commands
uv run --with /mnt/ssd/Dropbox/ai/science/science-tool science-tool graph stats --format json > /tmp/exemplar-graph-stats.json
uv run --with /mnt/ssd/Dropbox/ai/science/science-tool science-tool graph validate --format json > /tmp/exemplar-graph-validate.json
uv run --with /mnt/ssd/Dropbox/ai/science/science-tool science-tool graph diff --mode hybrid --format json > /tmp/exemplar-graph-diff.json

# Query presets
uv run --with /mnt/ssd/Dropbox/ai/science/science-tool science-tool graph claims --format json > /tmp/exemplar-query-claims.json
uv run --with /mnt/ssd/Dropbox/ai/science/science-tool science-tool graph coverage --format json > /tmp/exemplar-query-coverage.json

# validate.sh
SCIENCE_TOOL_PATH="/mnt/ssd/Dropbox/ai/science/science-tool" bash validate.sh > /tmp/exemplar-validate-sh.log 2>&1 || true
```

**Step 2: Archive evidence in science repo**

```bash
mkdir -p /mnt/ssd/Dropbox/ai/science/docs/exemplar-evidence
cp /tmp/exemplar-graph-stats.json /mnt/ssd/Dropbox/ai/science/docs/exemplar-evidence/
cp /tmp/exemplar-graph-validate.json /mnt/ssd/Dropbox/ai/science/docs/exemplar-evidence/
cp /tmp/exemplar-graph-diff.json /mnt/ssd/Dropbox/ai/science/docs/exemplar-evidence/
cp /tmp/exemplar-query-claims.json /mnt/ssd/Dropbox/ai/science/docs/exemplar-evidence/
cp /tmp/exemplar-query-coverage.json /mnt/ssd/Dropbox/ai/science/docs/exemplar-evidence/
cp /tmp/exemplar-validate-sh.log /mnt/ssd/Dropbox/ai/science/docs/exemplar-evidence/
```

**Step 3: Write evidence README**

Create `/mnt/ssd/Dropbox/ai/science/docs/exemplar-evidence/README.md`:

```markdown
# Phase 3 Exemplar Evidence Bundle

**Project:** 3D Structure-Aware Attention Bias for Nucleic Acid Foundation Models
**Location:** `~/d/3d-attention-bias/`
**Date:** 2026-03-07

## Artifacts

| File | Command | Description |
|------|---------|-------------|
| `graph-stats.json` | `graph stats --format json` | Entity and triple counts per named graph |
| `graph-validate.json` | `graph validate --format json` | Structural validation checks (all should pass) |
| `graph-diff.json` | `graph diff --mode hybrid --format json` | Change detection against graph revision |
| `query-claims.json` | `graph claims --format json` | All claims with provenance and confidence |
| `query-coverage.json` | `graph coverage --format json` | Variable/concept coverage status |
| `validate-sh.log` | `validate.sh` | Full structural validation output |

## Phase 3 Gate Verification

- [ ] Project scaffolded via `/science:create-project`
- [ ] Knowledge graph constructed via `/science:create-graph` from research prose
- [ ] OpenAlex snapshot imported via `graph import`
- [ ] Use-case queries run with `--format json`
- [ ] `graph diff --mode hybrid` runs without error
- [ ] `graph validate` passes all checks
- [ ] `validate.sh` passes (exit code 0)
```

**Step 4: Commit evidence to science repo**

```bash
cd /mnt/ssd/Dropbox/ai/science
git add -f docs/exemplar-evidence/
git commit -m "docs: archive Phase 3 exemplar evidence bundle (3d-attention-bias project)"
```

---

### Task 11: Extract biomedical starter profile (infrastructure)

**Working directory:** `/mnt/ssd/Dropbox/ai/science/`

**Step 1: Analyze exemplar graph for patterns**

Review the exemplar's `knowledge/graph.trig` to identify which Biolink types, CURIE prefixes, and entity patterns were actually useful.

**Step 2: Create starter profile reference**

Create `/mnt/ssd/Dropbox/ai/science/references/biomedical-starter-profile.md`:

Content should include:
- Recommended Biolink types for genomics/bioinformatics projects (Gene, Protein, Disease, BiologicalProcess, Pathway, ChemicalEntity, Phenotype)
- Recommended CURIE prefixes and registries (NCBIGene, UniProt, MONDO, GO, SO, CHEBI)
- Example `graph add concept` invocations with full flags drawn from the exemplar
- Recommended predicates by use case (evidence → cito:supports, hierarchy → skos:broader, etc.)
- Tips for entity richness: always use `--note`, `--property`, `--status`, `--source`

**Step 3: Commit**

```bash
cd /mnt/ssd/Dropbox/ai/science
git add references/biomedical-starter-profile.md
git commit -m "docs: add biomedical starter profile reference derived from exemplar"
```

---

### Task 12: Close Phase 3 gate

**Working directory:** `/mnt/ssd/Dropbox/ai/science/`

**Step 1: Update plan.md deliverables**

Mark all remaining 3c and 3d items as done:

- `[x] Pre-generated snapshots` with commit hash
- `[x] Biomedical starter profile` with commit hash
- `[x] Run one biomedical exemplar project` with commit hash
- `[x] Capture exemplar evidence bundle` with commit hash
- `[x] Document friction points and lessons learned`

Update Phase 3 progress snapshot with final note.

**Step 2: Update knowledge-graph design doc**

Update slice status table in `docs/plans/2026-03-01-knowledge-graph-design.md`:
- Slice C: PARTIAL → DONE
- Slice D: PARTIAL → DONE

**Step 3: Update this plan's status table**

Fill in all Status and Commit columns.

**Step 4: Commit**

```bash
cd /mnt/ssd/Dropbox/ai/science
git add -f docs/plan.md docs/plans/2026-03-01-knowledge-graph-design.md docs/plans/2026-03-07-phase3-completion-plan.md
git commit -m "docs: close Phase 3 gate — all deliverables complete"
```
