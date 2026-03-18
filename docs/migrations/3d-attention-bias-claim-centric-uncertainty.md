# 3D-Attention-Bias Claim-Centric Uncertainty Migration Guide

Project: `/home/keith/d/3d-attention-bias`

## Why This Project Is The Best Pilot

This is the best first migration target because it has:

- a smaller hypothesis surface than `seq-feats`
- clear inquiry structure
- benchmark-oriented experimentation
- obvious separation between literature motivation and project-run results

That makes it the cleanest place to establish the claim/evidence/study/result workflow end-to-end.

## Current Shape

Relevant files:

- `/home/keith/d/3d-attention-bias/specs/hypotheses/h01-3d-attention-improves-performance.md`
- `/home/keith/d/3d-attention-bias/specs/hypotheses/h02-attention-scale-structure.md`
- `/home/keith/d/3d-attention-bias/doc/inquiries/`
- `/home/keith/d/3d-attention-bias/doc/questions/`
- `/home/keith/d/3d-attention-bias/knowledge/sources/project_specific/entities.yaml`
- `/home/keith/d/3d-attention-bias/knowledge/sources/project_specific/relations.yaml`

Observed migration pressure:

- hypotheses are still broad conjectures with literature-heavy motivation
- inquiry artifacts already exist and should become natural homes for claim-backed experiment paths
- `relations.yaml` currently uses mostly `sci:relatedTo` topic links, which organize the project but do not express evidential stance
- authored confidence is still present on hypotheses/questions/inquiries

## Migration Goal

Keep `H01` and `H02` as organizing hypotheses, but migrate the project’s real reasoning into:

- explicit performance and mechanism claims
- explicit empirical benchmark evidence
- explicit literature evidence
- explicit missing-empirical-support flags for claims still motivated only by papers or design intuition

## Recommended First Migration Targets

Migrate in this order:

1. `H01` in `/home/keith/d/3d-attention-bias/specs/hypotheses/h01-3d-attention-improves-performance.md`
2. the `inquiry:3d_attention_effect` pathway
3. `H02` and `inquiry:attention_scale_analysis`
4. only then the broader topic/question network

## Suggested Claim Decomposition

For `H01`, split the hypothesis into narrower claims such as:

- 3D bias improves structure-sensitive benchmark performance
- 3D bias does not improve sequence-local control tasks
- the effect depends on structure source quality
- the best bias function differs by task or modality
- any gains may reflect shortcutting rather than improved representation quality

For `H02`, split into claims such as:

- pretrained attention heads exhibit interpretable distance-scale structure
- fine-tuning shifts attention toward task-relevant spatial scales
- attention profiles can act as priors for bias-function design

## Evidence Migration Rules

Use these mappings:

- completed benchmark runs and measured task deltas -> `empirical_data_evidence`
- ablation studies on bias functions -> `empirical_data_evidence`
- null benchmark outcomes -> `negative_result`
- literature motivation and structural precedents -> `literature_evidence`
- simulation-only analyses, if introduced later -> `simulation_evidence`

Important:

- do not let inquiry edges stand in for support
- inquiry edges should point to explicit relation claims
- benchmark tables and experiment summaries should become typed `study` / `result` records when possible

## Concrete Migration Steps

1. Demote authored confidence on `H01`, `H02`, questions, and inquiries in `/home/keith/d/3d-attention-bias/knowledge/sources/project_specific/entities.yaml`.
2. Add first-pass claim-backed edges for `inquiry:3d_attention_effect` and `inquiry:attention_scale_analysis`.
3. Introduce relation claims for the main benchmark and mechanism assertions.
4. Reclassify existing topic links in `/home/keith/d/3d-attention-bias/knowledge/sources/project_specific/relations.yaml`:
   keep `sci:relatedTo` only for topical organization, not evidential support.
5. Represent actual experimental outcomes as support/dispute evidence against those claims.
6. Mark claims that still rely only on papers or design arguments as “lacking empirical data evidence”.

## Success Criteria

The migration is successful when:

- `H01` and `H02` read as claim bundles instead of monolithic verdict objects
- inquiry graphs can show which relation claims they are testing
- the dashboard can separate:
  - literature-only claims
  - empirically supported claims
  - null-result claims
  - neighborhoods where uncertainty is concentrated

## Recommended Validation Commands

Run in `/home/keith/d/3d-attention-bias`:

```bash
uv run --frozen science-tool graph audit --project-root . --format json
uv run --frozen science-tool graph build --project-root .
uv run --frozen science-tool graph validate --format json --path knowledge/graph.trig
uv run --frozen science-tool graph dashboard-summary --path knowledge/graph.trig --format json
uv run --frozen science-tool inquiry show 3d_attention_effect --format json --path knowledge/graph.trig
```

## Main Risk

The biggest migration mistake here would be to treat “experiment exists” as equivalent to “claim supported.” This project is exactly where explicit benchmark design, control tasks, and null results need to update belief rather than harden the graph.
