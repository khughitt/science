# Feedback Batch O — the 2026-07-26 downstream filings — design

**Status:** design drafted 2026-07-26, awaiting owner review.
**Branch:** `feedback-batch-o` (worktree `.worktrees/feedback-batch-o`, from main `3b72db60`).
**Predecessor:** [`2026-07-20-feedback-triage-2026-07-batch-design.md`](2026-07-20-feedback-triage-2026-07-batch-design.md)
(batches A–N, all closed). Batch O is the next arrival wave, not a re-triage of that doc.

## Scope

The nine `fb-2026-07-26-*` entries — the freshest downstream filings, from
`multiple-myeloma` (4), `post-acute-infection` (3), and `natural-systems` (1),
plus one convention gap filed by `multiple-myeloma`.

Deliberately **not** in scope (see [Out of scope](#out-of-scope-and-handoffs)):
the 20 deferred Batch K+L methodology leaves, the fourteen `07-25` filings, the
two `07-22` filings, and the five stale-open bookkeeping entries.

## Method

Standing method inherited from the predecessor doc, unchanged:

- **Verify every claim empirically before fixing.** Batch O's grounding pass
  overturned two of the nine reports (see `-003` and `-005`). A plausible
  report whose premise no longer holds is a known failure mode of this queue.
- **TDD.** Each instrument fix lands with a test that goes RED against the
  current code first — a hardening test that never demonstrated the defect
  passes vacuously.
- **Certify against the real corpus before gating.** A check whose counts
  change must be measured across the fleet before it ships, so no project's
  `validate` flips from pass to fail unannounced.
- Worktree under `.worktrees/`; merge `--no-ff` to **local** `main`; do not push.

## Owner decisions (confirmed 2026-07-26)

| # | Question | Ruling |
|---|----------|--------|
| **D1** | How to treat the undocumented `[TOKEN: reason]` marker form | **Recognize as first-class** — count it and capture the reason text; document the form. The fleet has already converged on it and it carries strictly more information than the bare token. |
| **D2** | `-005`'s hint-path half is generic to every budgeted command | **Health half here, hand off the hint path** to the context-budget program rather than have two sessions edit one fleet-wide surface. |
| **D3** | How far the PDF-location fix goes | **Document + `ProjectPaths` field** — name `papers/pdfs/` in `docs/conventions/`, add a resolvable path field, note the outlier project without migrating it. |

## Collision check

The other active session holds `context-budget-slice3` and `reverse-lineage-gate`;
both are design-doc-only at the time of writing. Slice 3's declared file scope is
task storage — `tasks/`, `refs.py`, and the two task-specific health checks
(`graph/health_checks/legacy_task_type.py`, `lingering_tags.py`). Batch O touches
none of those except a possible contact point in `refs.py` (which delegates marker
counting to the shared scanner). **`refs.py` is the one file to re-check before
merging.** D2 exists specifically to keep Batch O out of `budget/`.

---

## Tier 0 — instruments that hide or miscount wrong state

Ordered first by the predecessor doc's doctrine: a check or metric that produces
or conceals wrong state outranks ergonomics.

### T0-1 — `fb-2026-07-26-001`: the marker scanner is blind to `[TOKEN: reason]`

**Report:** the markers scan misses the `[TOKEN: reason]` form, so the health
metric undercounts honesty flags "by ~10x".

**Grounded verdict: real; magnitude overstated.** `markers.py:49` is

```python
_RECOGNIZED_INNER = "|".join(sorted(TOKENS, key=len, reverse=True))
_TOKEN_RE = re.compile(rf"\[(?P<inner>{_RECOGNIZED_INNER})\]")
```

— the bare form only. Measured rather than assumed:

| Project | Counted by `markers scan` | `[TOKEN: reason]` occurrences |
|---|---|---|
| `multiple-myeloma` | 114 | 111 |
| `natural-systems` | — | 111 (vs 97 bare) |
| `post-acute-infection` | — | 28 (vs 137 bare) |
| `evolution` | — | 8 (vs 11 bare) |

The undercount is roughly **2x** in `multiple-myeloma`, not 10x. In
`natural-systems` the invisible form **outnumbers** the visible one. The
right-hand column is a `grep` over all `*.md`, whose scope is wider than the
scanner's (which excludes backticked and fenced occurrences and honours
`--ignore-lifted`), so it is an upper bound, not a scanner-equivalent figure.
The defect and its direction are certain; the exact multiplier is not, and the
report's figure should not be repeated as though it were measured.

Secondary finding: the form appears in `docs/conventions/annotation-tokens.md`
nowhere. Its "Lexical scope" section defines bare-vs-backticked and says nothing
about a payload. Authors invented it; the instrument never learned it.

**Fix (D1).** Extend the token pattern to an optional payload, capture it, and
document the form:

- `_TOKEN_RE` gains an optional `:reason` group, bounded by `[^\]]*` so a reason
  containing `]` truncates rather than swallowing the rest of the line — a
  marker still *counts* even when its reason is malformed. An empty reason
  (`[UNVERIFIED:]`) normalizes to `None`.
- `MarkerHit` gains `reason: str | None`.
- `docs/conventions/annotation-tokens.md` documents the form under a new
  "Payload" subsection, beside the existing lexical-scope rules.

**Certification.** Counts rise fleet-wide. Marker findings are `WARN`
(`unresolved_markers.py:52` hardcodes `Severity.WARN`), so no project's
`validate` exit code can change — but this must be *measured*, not asserted:
run the check across the fleet before and after and record both tallies.

**RED first.** A test asserting a `[UNVERIFIED: reason]` line yields one hit
must fail against current `main` (today it yields zero).

### T0-2 — `fb-2026-07-26-007`: raw line indexed with a masked-line column

**Report:** the numeric-anchor `NotClaim` classifier reads the raw line with a
masked-line column, silently misfiring after any inline-code span.

**Grounded verdict: real, and it is worse than reported.** Every masker in the
chain is deliberately column-preserving — `_mask_numeric_identifier_spans`
(`prose_lint.py:513`) is documented "blank identifier spans, preserving columns
for remaining numeric claims", and each sub-pattern substitutes
`" " * len(match.group(0))`. But the chain's *first* step is not:

```python
# markdown_utils.py:47
return _INLINE_CODE_RE.sub("", text)     # deletes; does not blank
```

`numeric_provenance.py:608` then builds `line` from that shortened string and
`:623` classifies against the original:

```python
line = _mask_numeric_identifier_spans(strip_inline_code(raw))
...
reason = classify_structural(value, raw, match.start() + 1)   # col from `line`, text from `raw`
```

`classify_structural` slices `line[:start]` and `line[end:end+24]` to test
adjacency triggers, so after any inline-code span it inspects the wrong window
— misfiring in both directions (a spurious `NotClaim`, or a missed one).

The deletion also corrupts two things the report does not mention, both
downstream of the same shifted column:

1. the **column reported to the author** — `NumericClaim.col = match.start() + 1`
   no longer corresponds to the real file line; and
2. **bound-span suppression** — `_within_bound_span(lineno, match.start() + 1, …)`
   compares that shifted column against spans parsed elsewhere.

**Fix.** Make the chain column-preserving end to end rather than patching the
argument. Add a `blank_inline_code` sibling to `markdown_utils.py` — same regex,
equal-length space substitution — and use it at `numeric_provenance.py:608`.
Once lengths agree, `raw` and `line` columns coincide and all three symptoms
close together. `classify_structural` is then passed `line`, the string its
column was measured on; its adjacency triggers are prose words, never the
identifier spans the maskers blank, so nothing it looks for is lost.

`strip_inline_code` itself is **left alone** — it is shared by other lints whose
correctness does not depend on offsets, and widening the change would enlarge
the blast radius for no gain here.

**Same-class site, flagged not silently changed.** `prose_lint.py:377` builds
its line through the same deleting `strip_inline_code`. It is internally
self-consistent (every offset it uses is measured on the masked line), so it is
not the reported defect; it is recorded here as a place to audit if it ever
starts reporting positions.

**RED first.** A line carrying an inline-code span followed by a
hardware-prefixed number must classify wrongly against current `main`.

### T0-3 — `fb-2026-07-26-008`: the canonical-ID masker is case-brittle

**Report:** the canonical-ID masker is lowercase-only, so sentence-initial
`Hypothesis:0011` leaks its digits as a numeric claim.

**Grounded verdict: real.** `prose_lint.py:205`:

```python
_CANONICAL_ID_SPAN_RE = re.compile(r"\b[a-z][a-z0-9_-]*:[A-Za-z0-9][A-Za-z0-9_.-]*\b")
```

The kind prefix must be entirely lowercase, so `hypothesis:0011` is masked and
`Hypothesis:0011` is not — the lint's verdict depends on whether the reference
happens to begin a sentence, which is arbitrary with respect to what it is
measuring.

**Fix.** Make the prefix case-insensitive. This does not widen the pattern's
*class* — it already matches any lowercase word before the colon, so
case-insensitivity removes a positional artefact rather than admitting a new
category of span. The alternative, deriving the prefix set from the registered
kind vocabulary, is a genuinely better instrument but a different change:
`_CANONICAL_ID_SPAN_RE` is generic today, and narrowing it to a registry is a
scope decision with its own certification burden.

**Second site, same defect class.** `prose_lint.py:198`:

```python
_CANONICAL_PREFIX_RE = re.compile(r"\b(question|hypothesis|task|discussion|interpretation):")
```

Used at `:381` to skip references that are already canonical. It shares the case
bug — `Hypothesis:` does not match — so it is fixed here as part of the reported
class. It *also* enumerates five kinds out of roughly fifty, which is a hole by
construction (a guard that lists its scope has a hole by construction — the
lesson recorded from the toolkit-convergence work). **That widening is flagged,
not silently performed**: enumerating the registry changes which references the
short-form lint skips, which needs its own corpus certification.

**Certification.** Both changes *reduce* findings (more spans masked). Measure
the fleet delta and confirm the drop is confined to genuine canonical IDs.

---

## Tier 1 — correctness and legibility

### T1-1 — `fb-2026-07-26-004`: `references.bib` bypasses `papers_dir`

**Grounded verdict: real, premise accurate.** `ProjectPaths.papers_dir` exists
(`paths.py:44`, built by `resolve_paths`, `:104`). `bibliography.py` hardcodes
`project_root / "papers" / "references.bib"` at **:40, :56, :88, :164**, while
`:256` already resolves through a local `papers_dir` variable — so the module
contradicts itself.

**Fix.** One private `_bib_path(project_root)` resolving through
`resolve_paths(...).papers_dir`, used by all five sites. Fail early if the
manifest cannot be resolved rather than falling back to the literal — a silent
fallback is what produced the inconsistency.

**Two adjacent literals, resolved deliberately:**

- `labnote_export.py:857` builds the same path by hand → routed through the helper.
- `project_package/serialize.py:37` holds `"papers/references.bib"` inside
  `TOP_LEVEL_SINGLES`, a tuple of **relative inventory paths** for the
  deterministic tarball. That is a serialization contract, not a filesystem
  lookup; changing it would make the payload inventory manifest-dependent and
  break the payload-hash guarantee. **Left as a literal, with a comment saying
  why.**

### T1-2 — `fb-2026-07-26-002`: `origins: []` scaffolds without its shape

**Grounded verdict: real, premise accurate.** `templates/theme.md:10-12`:

```yaml
# origins: known originators (user | assistant | literature). Provenance only;
origins: []
```

The comment names three bare words, so the natural completion is
`origins: [literature]`. `OriginRecord` (`entities.py:241`) is
`extra="forbid"` with a required `type: OriginType` — a bare string cannot
validate. The entity is then dropped from the source load
(`graph/sources.py:529`, `reason="core_schema_validation_failed"`), and every
health check requiring sources reports `unwired` — the "~9 unrelated 'could not
run' errors" the reporter saw.

**Fix — two parts, and only the first changes behaviour for the author:**

1. **The scaffold shows the shape.** The template comment carries a concrete
   record (`[{type: literature, ref: paper:Smith2024}]`), so the dict form is
   visible at the point of authoring. Every other template scaffolding
   `origins:` gets the same treatment — checked, not assumed.
2. **The cascade stays.** The `unwired` doctrine is deliberate and correct: a
   check that cannot see its sources must not report a pass. The root cause is
   *already* reported — `health.py:318-328` emits an `entity.schema-invalid`
   error carrying `skipped.details`. What is missing is **ordering/prominence**,
   not information. Scope here is limited to confirming the root-cause finding
   names the offending file and field; if it does, the fix is the template alone
   and the cascade complaint is answered by making the trigger unreachable.

### T1-3 — `fb-2026-07-26-006`: `validation` as an unreconcilable integer

**Grounded verdict: real, and exactly reconcilable once stated.** The health
render prints `Validation (N)` (`health_cli.py:429`) with a separate
`Accepted validation warnings: M` line (`:222`). The check itself
(`health_checks/validate.py:26`) runs the canonical runner:

```python
validate_runner.run(project_root, strict=False, verbose=False, enable_python_sidecar=False)
```

So health's number is `science validate`'s finding set under three specific
narrowings, none of them displayed:

1. `strict=False` — fixed, so `--strict` findings are absent;
2. `enable_python_sidecar=False` — the Python sidecar checks never run;
3. minus entries matched by the project's acceptance ledger.

A user comparing it to `science validate`'s tally is comparing different sets,
with nothing on screen to say so. Health additionally displays a *separate*
`schema_invalid` list (`health.py:318`), which is easily mistaken for part of
the same number.

**Fix — legibility only, no metric change.** Break the count out by severity
(the rows already carry `severity`, per `health_projection.py:168`) and label
the scope: the render states that the figure is non-strict, sidecar-free, and
acceptance-filtered, so it reconciles by construction. No finding is added,
removed, or reweighted.

### T1-4 — `fb-2026-07-26-005` (health half): JSON that cannot print

**Grounded verdict: both halves real; the second is not health's.**

*Half one — "cannot print".* By construction, not a bug in the sense reported.
`BoundedSink.flush()` (`budget/sink.py:133-136`) raises `BudgetExceeded` when
projected output exceeds `max_chars`, with "Nothing was printed." Row projection
caps *rows*; a large project's JSON stays over the ceiling. The budget doctrine
holds that the escape hatch is the file, so **the behaviour is correct and the
defect is that nothing tells the author this is expected for JSON at scale.**

*Half two — the suggested path.* `hint_for` (`budget/invocation.py:26`) returns
`f"{stem}.{'json' if …}"` — a bare relative filename. `--output health.json`
therefore lands in the current directory, untracked, for **every budgeted
command**, not just health.

**Fix (D2).** In Batch O: document the JSON-at-scale expectation where authors
meet it. The generic hint-path decision is **handed to the context-budget
program** — it is that program's surface, one session should own it, and a fix
here would collide with slice 3's neighbourhood. Recorded in
[Out of scope](#out-of-scope-and-handoffs) with the evidence needed to act on it.

### T1-5 — `fb-2026-07-26-003`: no documented home for PDFs

**Grounded verdict: premise partly false.** The convention exists; it is only
undocumented. `commands/create-project.md:210` and `commands/import-project.md:271`
both scaffold `papers/pdfs/` into `.gitignore` under "# Large files", and the
fleet follows it:

| Project | PDF location | Count |
|---|---|---|
| `post-acute-infection` | `papers/pdfs/` | 122 |
| `cycles` | `papers/pdfs/` | 295 |
| `cancer/meta` | `papers/pdfs/` | 109 |
| `natural-systems` | `papers/pdfs/` | 96 |
| `multiple-myeloma` | **top-level `pdfs/`** | 344 |

The sole outlier is the project that filed the report — and its own `.gitignore`
blocks `papers/pdfs` (per the downstream-conventions audit). So "every project
invents its own" is not what the corpus shows: four of five converged, and the
convention is real but reachable only by reading a gitignore block inside a
command doc. No `docs/conventions/` file names it.

**Fix (D3).**

1. Document `papers/pdfs/` in `docs/conventions/` — gitignored payload
   territory, sibling to the tracked `papers/references.bib`, consistent with
   the data-boundary ruling that payloads are legible from location.
2. Add a resolvable `pdfs_dir` to `ProjectPaths` so tooling stops hardcoding —
   the same abstraction gap T1-1 closes for `references.bib`.
3. Record the outlier. **No data-repo migration** — that is not toolkit work and
   would need its own greenlight.

### T1-6 — `fb-2026-07-26-009`: synthesizers regenerate their own warnings

**Grounded verdict: real, confirmed by absence.** `commands/big-picture.md`,
`agents/hypothesis-synthesizer.md`, and `agents/emergent-threads-synthesizer.md`
contain no mention of numeric anchoring, canonical-ID form, or marker tokens. The
synthesizers write entities whose prose is then linted by exactly the check the
reporter sees fire on every regeneration.

**Fix.** Give the two synthesizer agents the prose conventions their output is
held to: bind numbers to a resolvable anchor, use canonical `kind:id` reference
form, and reach for a marker token when a figure genuinely lacks provenance.
Note that T0-2 and T0-3 remove a share of these warnings outright — the false
positives — so this item is authored *after* them, and its scope is whatever
warning classes survive the Tier 0 fixes. Sequencing this before Tier 0 would
mean writing guidance against defective instruments.

**Mirrors.** `commands/big-picture.md` is codex-mirrored — regenerate if edited
(`scripts/generate_codex_skills.py`). `agents/` is **not** mirrored.

---

## Ordering

Tier 0 first (T0-1, T0-2, T0-3), then T1-1 … T1-5 in any order, then **T1-6 last**
— its scope is defined by what Tier 0 leaves behind.

## Out of scope and handoffs

- **Hand off to the context-budget program (D2):** `hint_for`
  (`budget/invocation.py:26`) advertises a bare relative filename, so every
  budgeted command's `--output` escape lands untracked in the caller's
  directory. Needs a conventional gitignored destination; the state-tier work
  (XDG `~/.local/state/science/`) would supply one but is unbuilt.
- **Batch K+L (20 items)** — estimand discipline and estimator certification,
  triaged in the predecessor doc, gated on `skills-phase4` (which has since
  merged). Unblocked, not started.
- **The `07-25` filings (14)** — explore-ideas round two (7), `cli:project`
  cwd-sensitivity, out-of-repo prereg vehicle, `discuss` Q&A section conflict,
  two positives, two methodology items.
- **The `07-22` filings (2)** — dataset artifact location, worktree artifact safety.
- **Five stale-open bookkeeping entries** — `-11-024`, `-11-029`, `-18-011`,
  `-19-001`, `-19-003` are recorded `open` in the store although the predecessor
  batch shipped them (389 of 454 entries are `addressed`). Verify and close; no code.
- **Two latent widenings, flagged in place, deliberately not taken:**
  `_CANONICAL_PREFIX_RE`'s five-kind enumeration (T0-3), and narrowing
  `_CANONICAL_ID_SPAN_RE` to the registered kind vocabulary.

## Validation

From `science/`: `uv run --frozen pytest`, `uv run ruff check`, `uv run pyright`.
From `science/model/`: `uv run --frozen pytest`. Snapshot and `real_projects`
markers are deselected by default and must be run explicitly — a marked snapshot
can rot unnoticed, and T0-1's count change and T0-3's finding reduction are
exactly the kind of drift a text snapshot encodes. Expect the validate-snapshot
count line to move.
