# S4 — Plan Correspondence-Drift Screen (design)

**Status:** design approved 2026-07-17; ready for an implementation plan.
**Program:** curation-scope program, spec S4 (see
`docs/plans/2026-07-17-curation-scope-certification-design.md` for S1 and the program map).
**Branch:** `plan-correspondence-drift-screen` (worktree `.worktrees/`).

## 1. Goal

Ship a **deterministic, advisory `science validate` check** that flags a `plan` entity whose
`status` **under-claims** its real progress — the canonical case being `status: draft` on a plan
whose promised deliverables already exist on disk. The check *screens*; it never adjudicates and
never gates. Its findings feed `science entity review`, where a human or agent decides whether the
status is genuinely stale (fix it) or the signal is a false positive (accept it, evidence-scoped).

This is the operational payoff of the plan correspondence-drift sample
(`docs/plans/2026-07-17-drift-sample/result.md`), which measured — under blinding, on 40 plans
drawn from a pre-registered frame — that the dominant failure of plan status is **stale
under-claim**: plans asserting `draft` while their deliverables are built. S1 gave `plan` a
`curation_scope` and made `science entity review plan:NNNN` succeed; S4 gives the sweep something
to *detect* so that review has a worklist.

## 2. Why this shape

The drift sample's judgment step, `adjudicate()`, is **already deterministic**: given probe results
for a plan's deliverables (present/absent/unknown) plus its task-ref states, it returns one of
`draft | active | complete | superseded | indeterminate`. What the sample needed an LLM for was
**extraction** — deciding *which* files a plan actually promises — because regex extraction
(`extract_deliverables`) is demonstrably unreliable (the `0016` false-mismatch: regex saw one
deliverable, the blinded reviewer saw a 20-file module-boundary list named in prose).

So the design is bound by the program's own doctrine — *an uncertified instrument may not fail
anyone's build* — and by the fact that the deterministic extractor is exactly such an instrument.
A deterministic check that **gates** would betray the doctrine. A deterministic check that
**advises**, screens in the *lower-risk advisory direction*, and hands its output to review, is
sound. The confidence contract in §5 is what makes it sound.

### 2.1 Reconciliation with adjacent, already-landed work

- **Authoritative-entity-schema (merged to local main).** `status` is now the entity lifecycle on
  every kind, and `plan` declares `["draft", "active", "complete", "superseded", "retired",
  "archived"]`. This check consumes that lifecycle; it does not redefine it. Stale under-claim is
  *not* a vocabulary violation — `draft` is a legal status — so `status_vocabulary.py` structurally
  cannot catch it. This check is the missing, orthogonal axis.
- **status-vocabulary certification (Phase 1, unmerged branch `status-vocab-certification`).** That
  arc certifies which *words* a kind may use and ratchets `<kind>.status-vocabulary` per kind.
  Independent of this check on every axis (see §6). S4 does not depend on that branch merging.
- **S1 curation-scope.** `plan.curation_scope == correspondence`. This check applies only to a kind
  the program has already ruled correspondence-scoped, so it is not inventing a new classification.

## 3. Non-goals (v1)

- **No over-claim detection.** `complete` (or `active`) while deliverables are *absent* is excluded.
  It is 2 of 22 measured mismatches and the direction where a moved or illustrative path reads as a
  false absence — the create-vs-reference call only judgment made.
- **No LLM adjudication.** That is the eventual `/science:review-plans` command's job, layered on
  top later. S4 is the deterministic screen only.
- **No gating, ever.** See §7.
- **No kinds other than `plan`.** `plan` is the one kind the sample measured. Extending to another
  correspondence kind is a deliberate future design task (new adjudication semantics + its own
  evidence), not a config toggle — so there is deliberately **no** `_DRIFT_KINDS` set pretending
  otherwise (§4.3).
- **No new suppression subsystem.** False positives are handled by the *existing*
  `accepted_validation` machinery, evidence-scoped (§5.3).

## 4. Architecture

### 4.1 Extract the reusable core into `science_tool/correspondence/`

The reusable status-vs-reality logic is currently trapped under the study-named `drift_sample/`
package and tangled with study-only statistics. Split by responsibility:

**New package `science/src/science_tool/correspondence/`:**
- `probe.py` — **moved** from `drift_sample/probe.py`: `probe_path`, `resolve_task`, `ProbeResult`,
  `TaskState`, `Probe`. Unchanged logic.
- `extract.py` — **moved** from `drift_sample/extract.py`: `extract_deliverables`,
  `extract_task_refs`. Unchanged logic.
- `adjudicate.py` — **lifted** out of `drift_sample/score.py`: `adjudicate`, `Adjudicated`.
  Unchanged logic.

**`drift_sample/` keeps** the one-shot study pieces — `frame`, `blind`, `draw`, `normalize`, and
the statistics in `score.py` (`verdict`, `manski`, `cp_lower`, `cp_upper`, `gate`, `THETA`,
`ALPHA`, `LADDER`, `CENSUS`). The **only** internal import that moves is `score.py:13`
(`from science_tool.drift_sample.probe import ProbeResult, TaskState`); after the split `score.py`
imports `ProbeResult`/`TaskState`/`adjudicate`/`Adjudicated` from `correspondence/`, and its
surviving `verdict` uses the imported `Adjudicated`. `frame`/`blind`/`draw` do not import any moved
symbol and are untouched.

**One definition, no duplication** — the same discipline `status_vocabulary.py` embodies ("there is
deliberately no table here"). Two copies of `adjudicate` would be exactly the drift this codebase
refuses. The frozen study reproduces **identically**: the logic is byte-for-byte the same, only
relocated, and the pre-registered result hashes `prereg.json` (data), not any module path. Its
executable helpers (`build_bundles.py`, `score_run.py`) retarget their imports to `correspondence/`
so they still run (§11); no compatibility shim is added.

### 4.2 Add a canonical `body` accessor to `ValidateContext`

The check needs the plan **body**, not just frontmatter. `ValidateContext` today parses frontmatter
with its own private splitter (`_parse_frontmatter`, split on `---\n`). Do **not** add a second
splitter. Instead:

- Back a single cached `(frontmatter, body)` parse on
  `science_model.frontmatter.split_frontmatter` — the canonical, non-lossy splitter
  (`model/src/science_model/frontmatter.py:113`).
- Expose `ValidateContext.body(path) -> str` from that cached parse, and re-back
  `ValidateContext.frontmatter(path)` on the same parse so both accessors share one splitter.
- **Guard:** the full existing `validate` test suite exercises `frontmatter()` heavily; it must stay
  green through this unification. If unifying `frontmatter()` proves risky in practice, `body()`
  still uses `split_frontmatter` (satisfying "no second splitter") and the `frontmatter()`
  migration may be deferred — but the default is to unify.

### 4.3 The check: `validate/checks/correspondence_drift.py`

A canonical check registered in the runner. Pseudocode (final code lives in the implementation
plan):

```python
_LIFECYCLE_RANK = {"draft": 0, "active": 1, "complete": 2}  # under-claim axis; others are off-axis

@Check(section="plan correspondence drift", order=...)
def check_correspondence_drift(ctx: ValidateContext) -> Iterator[Result]:
    entities_root = ctx.project_root / "entities"
    if not entities_root.is_dir():
        return
    for path in iter_entity_markdown(entities_root):
        fm = ctx.frontmatter(path)
        kind, status = fm.get("kind"), fm.get("status")
        if kind != "plan" or not isinstance(status, str) or not status:
            continue
        claimed_rank = _LIFECYCLE_RANK.get(status)
        if claimed_rank is None:
            continue  # terminal/off-axis claimed status — silent
        body = ctx.body(path)
        deliverables = extract_deliverables(body)
        if not deliverables:
            continue  # nothing probeable -> indeterminate -> silent
        probes = [probe_path(ctx.project_root, d) for d in deliverables]
        task_states = [(t, resolve_task(ctx.project_root, t)) for t in extract_task_refs(body)]
        adjudicated = adjudicate(
            [p.result for p in probes],
            [state for _ref, state in task_states],
            superseded=False,
        )
        adjudicated_rank = _LIFECYCLE_RANK.get(adjudicated.value)
        if adjudicated_rank is None:
            continue  # indeterminate or off-axis -> silent
        if claimed_rank < adjudicated_rank:  # UNDER-CLAIM
            # probes and task_states retain (target, result) / (task_ref, state) pairs so the
            # evidence signature and diagnostic can name them; adjudicate saw only the states.
            yield _drift_result(path, fm, status, adjudicated, probes, task_states)
```

- `kind == "plan"` is a literal, not a set (§3). The emitted rule name is still derived,
  `f"{kind}.correspondence-drift"`, so a future kind extension needs no rename.
- `superseded=False` always — there is no deterministic supersession signal (that was a reviewer
  judgment in the sample), so `adjudicate` returns only `draft | active | complete | indeterminate`
  here.
- Probes run against `ctx.project_root` — the **live** working tree, because the question is "does
  this status match reality *now*," not against a pinned commit (the study pinned for
  reproducibility; the screen does not).

## 5. The confidence contract

### 5.1 Fire only on under-claim, defined by lifecycle rank

Rank `draft=0 < active=1 < complete=2`. Fire **iff** `rank(claimed) < rank(adjudicated)` and both
are on-axis. This captures the measured dominant failure and only it:

| claimed → adjudicated | measured n | fires? |
|---|---|---|
| draft → active | 15 | yes (under-claim) |
| draft → complete | 4 | yes (under-claim) |
| active → complete | 1 | yes (under-claim) |
| complete → active | 2 | no (over-claim, §3) |

**20 of 22** adjudicated mismatches were under-claims — the "claims less progress than reality"
direction. Under-claim is the **lower-risk, advisory** direction to screen, not a safe one. The
deterministic screen's precision is **uncertified**: false under-claims do occur — a plan that
merely *references* an already-existing input file can extract-and-probe as present and adjudicate
past `draft` (the create-vs-reference distinction only the sample's human reviewers made; the `0016`
case is exactly this). Under-extraction is likewise **not** automatically `indeterminate` — a
partial extracted subset whose members all exist adjudicates `complete`. Screen precision is
therefore handled downstream by review (§5.3), not asserted here.

### 5.2 Silence conditions (the check yields nothing)

- No deliverables extracted from the body → the plan names no probeable files.
- Any probe returns `unknown` (path escapes the project) or `adjudicate` returns `indeterminate`.
- Claimed status is terminal/off-axis (`superseded`/`retired`/`archived`) — a superseded plan is not
  under-claiming.
- `rank(claimed) >= rank(adjudicated)` — agreement or over-claim.

### 5.3 The honest v1 recurrence contract (evidence-scoped acceptance)

The check **does not** consult `review_state`: `science entity review` only stamps a review
timestamp, and a review that did not change the status must not silence a still-true correspondence
signal. So findings clear in exactly two ways:

1. **A true positive self-heals.** The author corrects the claimed status to the adjudicated state
   (`draft → active`, `draft → complete`, or `active → complete`); adjudication then agrees
   (`rank(claimed) == rank(adjudicated)`); the WARN disappears. This is the intended review→act loop
   and needs no suppression at all.
2. **A confirmed false positive is suppressed, evidence-scoped, through the *existing*
   `accepted_validation` machinery**, which already filters WARNs. Path-only acceptance is
   **forbidden for this rule** because it would permanently blind that path even after the plan's
   deliverables change. The signature format and the fail-closed policy are specified in §5.5, and
   must be enforced identically on **both** surfaces that read `accepted_validation`.

Anything not acted on **recurs by design** — that is correct for a screen. The calibration in §8
(≈70 candidates on multiple-myeloma) is the intended backlog the sweep exists to surface, not noise.

### 5.4 Mandatory diagnostic content

Every finding's message must be actionable and acceptance-writable from the message alone:
- the plan's entity id (from frontmatter `id`);
- claimed status and adjudicated status;
- the probed evidence (which deliverables are present/absent, which task refs resolved);
- the `evidence-signature: v1:<sha256>` token (§5.5);
- the two remedies: correct the status, or add an evidence-scoped `accepted_validation` entry.

`Result.path` on every finding is **project-relative** (the validation contract requires it), so
acceptance entries and the diagnostic agree on the path spelling.

### 5.5 Evidence-signature format and centralized acceptance

**Signature.** The token is `evidence-signature: v1:<hex>`, where `<hex>` is the **full SHA-256** of
a **versioned canonical JSON** encoding of the evidence tuple —
`{"v": 1, "claimed": <status>, "deliverables": [[<target>, <probe-result>], … sorted],
"tasks": [[<task-ref>, <state>], … sorted], "adjudicated": <status>}`. The hashed bytes are exactly
`json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")` — so
key order, whitespace, and Unicode escaping are all pinned, not implementation-dependent. Because
these signatures are persisted into committed `science.yaml`, the encoding is versioned (`v1:`): a
future change to what the evidence covers is a new signature version, not a silent reinterpretation
of old entries.

**Exact-token acceptance.** An `accepted_validation` entry counts as evidence-scoped only if its
`message_contains` holds a **complete, well-formed** `evidence-signature: v1:<64-hex>` token
(validated by pattern) — not merely the `evidence-signature:` prefix. A truncated or malformed token
does not qualify. A valid entry is `rule: plan.correspondence-drift` + `path` (project-relative) +
that `message_contains` + a non-empty `reason`.

**One acceptance authority, both surfaces.** `science_tool.validate.acceptance` is the authority:
loading, matching, and the evidence-scope policy live there, exposing a field-based match predicate
plus `EVIDENCE_SCOPED_RULES = {"plan.correspondence-drift"}` and an entry-validity policy. **Both**
consumers delegate to it: `validate`'s own `filter_accepted_warnings` **and** `graph/health.py`,
which today carries its **own** independent copy (`health.py:145–173`) and instead **imports** the
authority. (A `graph.health` → `validate.acceptance` import is acceptable; the reverse would not be.) Suppression is granted only
when the shared matcher matches **and** the entry satisfies the evidence-scope policy — so an
unscoped `plan.correspondence-drift` entry fails closed on **both** surfaces. Removing health's
duplicate is required, not optional; otherwise the hole this amendment closes stays open in `health`.

**Malformed acceptance is a canonical finding, not a filter side effect.** The "unscoped acceptance
entry" WARN is emitted by a **canonical validation check** — a new module
`validate/checks/accepted_validation.py`, registered as `"accepted_validation"` — that scans
`accepted_validation`, under the **stable rule id `accepted-validation.evidence-scope-required`**.
It is **not** appended inside
`filter_accepted_warnings`: `validate/cli.py:152` (`_with_accepted_warnings_filtered`) treats
filtering as removal-only and uses `len(filtered) == len(original)` as its unchanged test, which an
appended finding would violate. Keeping the filter pure-removal preserves that invariant.

## 6. Severity: permanent WARN, deliberately not `severity_for_kind`

`status_vocabulary.py` grades via `severity_for_kind(kind)` so a kind ratchets to ERROR once its
*vocabulary* is certified. **Correspondence-drift must not share that axis.** It is a screen — by
design it never gates, imperfect-but-cheap. If it called `severity_for_kind`, then the day `plan`
earns *vocabulary* certification (joining `_CERTIFIED_KINDS`), `plan.correspondence-drift` would
silently promote to ERROR too, because that function keys on **kind**, not rule. Two unrelated axes
would be conflated — the exact class of bug `kind_severity.py`'s own history documents.

Therefore:
- The check emits **`Severity.WARN` unconditionally**, rule `plan.correspondence-drift`.
- The guarantee is phrased **"correspondence-drift findings never gate,"** and it rests on **both**
  (a) unconditional WARN severity and (b) the rule name's **explicit absence from every gate tier**
  (`gated_findings`/`gates.py` key on rule name, not severity — so severity alone is insufficient).
- An **unhandled check exception** still surfaces as `validate.check-error` through the runner. That
  is correct and out of scope of this guarantee — a crashing check should be loud, not silent.

## 7. Canonical registration

A check runs only if it is registered. Add **both** `"correspondence_drift"` and `"accepted_validation"`
(§5.5) to `CANONICAL_CHECK_MODULES` in `science/src/science_tool/validate/checks/__init__.py` (the
tuple `_load_canonical_checks` imports). A **registry test** asserts both are present in
`CANONICAL_CHECKS` after load and appear in a full runner pass — direct unit tests can pass while a
check never runs.

## 8. Testing strategy (four separated concerns)

1. **Unit** (`science/tests/test_correspondence_adjudicate.py` + a rank/direction test): under-claim
   fires; over-claim silent; agreement silent; no-deliverables silent; `indeterminate` silent;
   terminal-status silent. Evidence-signature is deterministic and changes when any evidence element
   changes.
2. **Check-level fixture project** (synthetic `entities/plans/`): a `draft` plan naming a present
   file → one WARN carrying the mandated diagnostic; a `draft` naming only absent files → silent
   (adjudicates `draft`, agrees); a `complete` plan with present files → silent.
3. **Centralized acceptance, asserted on *both* `validate` and `science health`** (§5.5): a
   path-only `accepted_validation` entry does not suppress on either surface; the canonical
   `accepted-validation.evidence-scope-required` WARN fires; a correct full-`v1:<64-hex>`-signature
   entry suppresses on both; a stale-signature entry does not. This is the regression test for the
   duplicated-matcher hole at `health.py:145–173`.
4. **Two separated downstream concerns — never assert on the full suite's exit code** (unrelated
   future errors must not fail the detector's test):
   - **Synthetic CLI exit-code test**, run at the highest `--fail-on` tier, proving a drift WARN
     exits 0. Self-contained fixture, not multiple-myeloma.
   - **`real_projects`-marked exercise** against `~/d/cancer/cancer-types/multiple-myeloma` proving
     the detector fires on real data: assert
     `len([r for r in results if r.rule == "plan.correspondence-drift"]) >= 1` (all such results
     WARN), not the exact count — the corpus is Dropbox-synced and drifts. (Marked so default pytest
     excludes it, per AGENTS.md.)

**Score-test split, not retarget:** move only the *adjudication* cases out of
`test_drift_sample_score.py` into `test_correspondence_adjudicate.py`; leave `normalize`/`verdict`/
`manski`/`gate` coverage in `test_drift_sample_score.py`. `test_drift_sample_probe.py` and
`test_drift_sample_extract.py` retarget their imports to `correspondence/`.

## 9. Companion correction: `result.md` label (label-only)

`docs/plans/2026-07-17-drift-sample/result.md:28`'s confusion matrix labels `active → complete` as
"over-claim." It is **under-claim** (claimed rank 1 < adjudicated 2 — claims less progress than
reality). Two edits: (a) the matrix label `active → complete` → under-claim; (b) the dominant-cell
sentence at `result.md:41` becomes **"20 under-claims: 19 `draft` claims plus one `active` claim,
while their promised deliverables already exist"** (not "19 plans assert `draft`"). This is
**label-only**: the pre-registered n, k_lo/k_hi Manski bounds, θ, and the DEMONSTRATE gate outcome
are unchanged (the gate keys on the mismatch *count*, which already included this case).

## 10. Certification note

Unlike `status_vocabulary`, this rule is **not** on a path to ERROR. It is a screen; a screen that
gates defeats its own imperfect-but-cheap contract. `plan.correspondence-drift` stays WARN
permanently and out of every gate tier regardless of any future `_CERTIFIED_KINDS` change (§6).

## 11. File map

- **Move/relocate:** `drift_sample/probe.py`, `drift_sample/extract.py` → `correspondence/`;
  `adjudicate`/`Adjudicated` out of `drift_sample/score.py` → `correspondence/adjudicate.py`.
  No compatibility shims.
- **Create:** `science/src/science_tool/correspondence/{__init__,probe,extract,adjudicate}.py`;
  `science/src/science_tool/validate/checks/correspondence_drift.py`;
  `science/src/science_tool/validate/checks/accepted_validation.py` (rule
  `accepted-validation.evidence-scope-required`);
  `science/tests/test_correspondence_adjudicate.py`; check-level, both-surface acceptance, CLI
  exit-code, and `real_projects` tests.
- **Modify:**
  - `drift_sample/score.py` — drop the moved `adjudicate`/`Adjudicated`; import
    `ProbeResult`/`TaskState`/`adjudicate`/`Adjudicated` from `correspondence/`.
  - `docs/plans/2026-07-17-drift-sample/build_bundles.py` — retarget `drift_sample.extract` →
    `correspondence.extract` (executable study helper).
  - `docs/plans/2026-07-17-drift-sample/score_run.py` — retarget `drift_sample.probe` →
    `correspondence.probe`, and `Adjudicated`/`adjudicate` → `correspondence.adjudicate` (leaving
    `verdict`/`manski`/`gate` on `drift_sample.score`).
  - `validate/context.py` — `body()` + shared `(frontmatter, body)` parse.
  - `validate/checks/__init__.py` — register `correspondence_drift` and `accepted_validation`.
  - `validate/acceptance.py` — the acceptance authority: loading + matching + evidence-scope policy.
  - `graph/health.py` — import `validate.acceptance` and delegate; **remove** its duplicate
    `_accepted_validation_entries` / `_accepts_validation_finding` / `_text_matches`
    (`health.py:135–173`).
  - `docs/plans/2026-07-17-drift-sample/result.md` — label-only (§9).
- **Retarget tests:** `test_drift_sample_probe.py`, `test_drift_sample_extract.py`,
  `test_drift_sample_score.py` (split adjudication cases out).
