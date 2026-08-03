# Agent Workflows

Claude Code plugin workflows and the generated Agent Skills used by Codex,
Crush, and OpenCode are the main agent interfaces. The CLI is the durable
tooling layer that creates files, validates structure, builds graphs, and reads
project state.

For command-family semantics, write classes, and canonical vs migration-only
surfaces, see [CLI And Workflows](cli-and-workflows.md). This chapter maps user
intent to agent workflows and representative CLI commands.

| Intent | Claude Code | Agent Skill | CLI |
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

An unattended run is bracketed by two supervisor commands. What happens between them can
be yours or Science's: drive the actor with a harness of your own, or use the supervised
harness Science ships — `science autonomy run`, described [below](#running-a-supervised-audit)
— which is these two commands plus one fixed actor in a single invocation.

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

**Every commit the actor makes has to be marked, or the run quarantines.** `finish` walks
`base_commit..head_commit` and requires two things of *each* commit in it:

- a `Science-Run: <run-id>` trailer, whose value is the full run id `start` reported —
  `run:` prefix included, and the same id on every commit in the range;
- an author of `<agent-role> <agent@science.local>` — the role you passed to
  `--agent`, and that exact mailbox. The committer is not inspected; the author is.

So a run opened with `--agent curation-sweep` commits like this:

```bash
git commit -m "docs: refresh venue

Science-Run: run:2026-07-25-curation-sweep-a3f1" \
    --author "curation-sweep <agent@science.local>"
```

An unmarked commit, one naming a different run, or one authored by anybody else is a
commit the run did not account for landing inside its own range — reported as a
commit-mark issue and quarantined. Marks are never *evidence*, though: a process that can
write commits can write any trailer and any author, so a matching mark proves nothing on
its own. The authoritative binding is the supervisor-recorded range.

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

## Running a supervised audit

`science autonomy run` is the whole bracket in one command, with one fixed actor:
`science health`. It opens the run, creates `auto/<run-id>`, runs the actor as a
subprocess, commits its output, judges the run with the same machinery `finish` uses, and
— only if the verdict is `clean` — ingests the report's findings into
`doc/audits/cases/`.

```bash
science autonomy run --project-root . --format table
```

There is no `--actor` flag, and that is the point: every value the run attests is worth
something only because a deterministic supervisor produced it, not a model reasoning about
its own work. Run it from a **named branch** with a **clean tree** — the command returns
you to that branch when it finishes, and a detached HEAD gives it no destination.

Five exit codes, extending `finish`'s three:

| Exit | Meaning |
|---|---|
| 0 | `clean`, and the findings were ingested. |
| 1 | `quarantined` — the actor wrote outside its surface. Nothing was ingested. |
| 2 | `unwired` — no verdict could be rendered. |
| 3 | An orchestration failure: the run never reached a verdict. Every branch and file is left intact for triage. |
| 4 | `clean`, but ingestion refused. Not a success — the run's purpose was an ingestible report, and a refused one did not achieve it. The refusal is printed and carried in the JSON output. |

**Where the output lands.** The actor's report stays on the retained `auto/<run-id>`
branch, and only there. The run record (`runs/<slug>.md`) and any cases are committed on
the branch you started from, so `validate`'s `autonomous-runs` check can see them: it reads
the current tree for records while scanning every branch for marked commits, and a record
committed on the run's own branch would be invisible from yours.

The rebuilt `knowledge/graph.trig` joins them **only on a clean run**. A quarantined run's
graph was re-materialized over a tree the actor had already written to, so publishing it
would carry the denied write's derived effect onto your branch even though the write itself
was correctly left behind.

Nothing is deleted on quarantine — `auto/<run-id>` and its commits stay exactly as the run
left them, for the same reason `finish` keeps them.
