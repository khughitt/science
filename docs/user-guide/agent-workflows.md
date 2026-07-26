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

## Running an unattended run

An unattended run is bracketed by two supervisor commands. Nothing between them is part
of Science: the actor is driven by whatever harness you use.

```bash
science autonomy start --agent curation-sweep --model <model> \
    --short-id a3f1 --baseline-out ~/supervisor-state/a3f1.json

#  ... the actor works on auto/<run-id> ...

science autonomy finish --baseline ~/supervisor-state/a3f1.json \
    --head "$(git rev-parse HEAD)" --tokens 12000 --wall-clock-seconds 900
```

`start` captures the belief basis and writes a **baseline**. It writes no run record: a
supervisor that dies mid-run leaves no attestation, so its branch reads as unattested
rather than clean. The baseline must live **outside the repository** — both commands
refuse a path inside the project root, because the actor's whole job is writing that
tree, and a baseline it can reach is a baseline it can rewrite.

Both commands require the working tree to *be* the commit they name — no uncommitted
edits, no untracked files. The path gate reads committed history while the belief basis
is captured from the tree; a change sitting in neither is judged by neither.

`finish` re-materializes the graph, recaptures the basis, compares it against the
baseline, runs the path gate over the recorded range, verifies the commit marks, and
writes the attested record to `runs/<slug>.md`, where the slug is the run id without its
`run:` prefix. The re-materialization is not optional: `graph.trig` is derived state the
actor controls, so a run that edited entities and never rebuilt would otherwise be judged
against a stale graph. It also means `finish` leaves `graph.trig` rebuilt in the tree,
and a run is finished exactly once — the record is never rewritten.

Three dispositions, and the exit codes match:

| Disposition | Exit | Meaning |
|---|---|---|
| `clean` | 0 | Eligible to merge. |
| `quarantined` | 1 | The branch is held intact and a `science feedback` item is filed naming the entity and the delta. |
| `unwired` | 2 | No verdict could be rendered — an unreadable baseline, a dirty tree, a failed rebuild, an uncomputable basis, or a toolkit that moved under the run. Blocked: a guard that cannot see must not report clean. |

A click usage error on `finish` — a mistyped flag, say — also exits `2`, which a
supervising harness reads the same as `unwired`. That's safe, since no run record is
written in that case, but a harness author should know the exit code alone does not
distinguish the two.

**Nothing is discarded on quarantine.** The branch and its commits stay exactly as the
run left them, so a human triages with the entity and the delta in hand. The first
violations will mostly be design discoveries — a sweep that legitimately needs something
the gate forbids — and destroying the evidence destroys the signal.

`science validate` carries an `autonomous-runs` check so the same violations are
catchable by anyone, independent of the run harness. It verifies record integrity and
coverage — every autonomous commit across every branch has a record, every record's
commits are reachable — without rebuilding the graph or re-deriving any historical basis.
