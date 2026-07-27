---
id: t029
project: ''
title: Improve `science-research-papers` batch workflow
type: ''
aspects:
- software-development
- skills
- research
priority: P2
status: proposed
blocked_by: []
related:
- question:0002-evidence-payload-schema
parent: ''
group: research-papers-workflow
artifacts: []
findings: []
created: '2026-05-05'
completed: null
---

Update the `science-research-papers` skill / command and related tooling based on Batch 1 friction.

Concrete improvements to design and implement:
- resolve software-profile research-layer summaries to `doc/background/papers/`, not `doc/papers/`;
- make `question reserve --source-refs` normalize bare BibTeX keys to `cite:<key>` or reject them early with a clear error;
- add real batch mode where workers write only paper summaries and the orchestrator owns `references.bib`, questions, and synthesis to avoid races;
- add a dedicated batch-synthesis template/location so validation does not treat synthesis files as paper summaries, and silence "paper-summary-only required sections" warnings on synthesis-shape files;
- add an "Implications" section to paper summaries for graph implications, evidence-schema implications, H01/revisiting implications, and command/skill feedback;
- add an `Artifact Semantics` section to the paper-summary template covering output object type (graph estimate, graph posterior, cluster, module, selected feature, predictive model), context/view scope, shared-structure assumptions, approximation class, and validation role (surfaced by Batch 4 methods papers where the artifact type and its causal-use restrictions are load-bearing);
- prompt the orchestrator to propose typed synthesis nodes and reason codes automatically when a batch contains methods papers (graph-estimation, graph-posterior, integrative-clustering, feature-selection, module-discovery, predictive-integration);
- emit a machine-readable batch manifest at end of run with paper keys, local PDF paths, synthesis file path, related question IDs, related task IDs, `[UNVERIFIED]` counts, and citation keys added;
- emit a "remaining PDFs by likely topic" report after each batch to support batch selection for the next run;
- add a post-batch prompt that proposes questions, hypotheses, task groups, and command improvements;
- record `[UNVERIFIED]` counts in the orchestrator report.
- register `synthesis` as a graph entity kind or keep batch synthesis artifacts out of graph-audited entity scans; `hypothesis create` currently reports unknown `synthesis` kind while scanning paper-batch synthesis files.
- add agent/workflow provenance frontmatter to generated summaries and syntheses;
- record explicit `abstention` / `insufficient-context` cases when a PDF does not support a requested claim;
- add a command/skill registry graph with capabilities, expected inputs/outputs, safety constraints, and validation commands.

Start with a design pass before editing generated commands or skills.
