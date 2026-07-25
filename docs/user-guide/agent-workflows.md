# Agent Workflows

Claude and Codex workflows are the main user interface. The CLI is the durable
tooling layer that creates files, validates structure, builds graphs, and reads
project state.

For command-family semantics, write classes, and canonical vs migration-only
surfaces, see [CLI And Workflows](cli-and-workflows.md). This chapter maps user
intent to agent workflows and representative CLI commands.

| Intent | Claude | Codex | CLI |
|---|---|---|---|
| Start a project | `/science:create-project` | `science-create-project` | project scaffold workflows |
| Adopt a project | `/science:import-project` | `science-import-project` | project scaffold workflows |
| Orient | `/science:status` | `science-status` | `science graph dashboard-summary` |
| Plan next work | `/science:next-steps` | `science-next-steps` | `science tasks list`, `science tasks summary` |
| Research a topic | `/science:research-topic` | `science-research-topic` | source-authored docs |
| Search literature | `/science:search-literature` | `science-search-literature` | `science bib add` |
| Summarize papers | `/science:research-papers` | `science-research-papers` | source-authored docs |
| Add hypotheses | `/science:add-hypothesis` | `science-add-hypothesis` | `science hypotheses create` |
| Add themes | `/science:add-theme` | `science-add-theme` | `science entity create theme` |
| Pre-register | `/science:pre-register` | `science-pre-register` | source-authored docs |
| Compare alternatives | `/science:compare-hypotheses` | `science-compare-hypotheses` | source-authored docs |
| Discuss critically | `/science:discuss` | `science-discuss` | `science discussions create` |
| Audit bias | `/science:bias-audit` | `science-bias-audit` | source-authored docs |
| Create propositions | workflow-guided | workflow-guided | `science propositions create` |
| Add evidence lines | workflow-guided | workflow-guided | `science evidence-lines create` |
| Sketch a model | `/science:sketch-model` | `science-sketch-model` | `science inquiry init` |
| Specify a model | `/science:specify-model` | `science-specify-model` | edit `entities/patches/<slug>.md`, then `science graph build` and `science inquiry validate` |
| Critique approach | `/science:critique-approach` | `science-critique-approach` | `science inquiry validate` |
| Plan analysis | `/science:plan-analysis` | `science-plan-analysis` | source-authored plans |
| Plan pipeline | `/science:plan-pipeline` | `science-plan-pipeline` | source-authored plans |
| Review pipeline | `/science:review-pipeline` | `science-review-pipeline` | validation and review docs |
| Interpret results | `/science:interpret-results` | `science-interpret-results` | source-authored interpretations |
| Build/update graph | `/science:create-graph`, `/science:update-graph` | `science-create-graph`, `science-update-graph` | `science graph build` |
| Validate health | `/science:health` | `science-health` | `science validate`, `science health` |
| Catalog benchmarks | `/science:catalog-benchmarks` | `science-catalog-benchmarks` | `science benchmark list`, `science benchmark opportunities`, `science benchmark gaps`, `science benchmark tests` |
| File feedback / inspect telemetry | `/science:post-mortem` | `science-post-mortem` | `science feedback ...`, `science telemetry ...` |
| Package or verify a project | workflow-guided | workflow-guided | `science project serialize`, `science project verify` |
| Sync projects | `/science:sync` | `science-sync` | `science peers list`, `science sync status`, `science sync run` |

## The autonomy path gate

An unattended run is confined to a write surface decided by
`science autonomy path-gate`, which compares the run's recorded `base..head` commit
range against a **default-deny** policy: every repository path, and every entity
frontmatter field, that is not explicitly allowed is denied — including fields nobody
has invented yet.

```bash
science autonomy path-gate --base <sha> --head <sha> --tier belief-neutral
```

Exit `0` means every change was inside the tier's surface, `1` means something was not
(each denial names the path, the reason, and the field when applicable), and `2` means the range could
not be read. Exit `2` is deliberately not exit `0`: a gate that cannot see must not
report clean.

Two tiers exist. `report-only` may write only the run's own report path. `belief-neutral`
may additionally edit allowlisted fields on pre-existing entities. There is no third
tier — changing belief is human work by definition.

The allowlist is small on purpose and is **not project-overridable**. A field is added
only after a human traces its materialization path and its belief dependencies; a
perturbation test that observes no movement is not sufficient grounds. The reverse is
automatic: if perturbing an allowed field is ever found to move the belief basis, the
field comes off the list.

The gate is one of four layers. It is syntactic and complete by construction, but it
does not prove belief-neutrality — `science graph belief-basis` does that, and it is
authoritative precisely because it does not depend on this allowlist being correct.
