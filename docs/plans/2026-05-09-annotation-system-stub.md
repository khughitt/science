---
id: "plan:2026-05-09-annotation-system-stub"
type: "plan"
title: "Sub-document annotation system — phase-2 token split + phase-3 RFC stub"
status: "draft"
created: "2026-05-09"
updated: "2026-05-09"
---

## Motivation

The current `[UNVERIFIED]` marker convention in `validate.sh` is a single token
that conflates several distinct epistemic states. A triage pass on a
downstream MM project (mm30, 2026-05-09) found 115 occurrences across 56
files, splitting into:

| Implicit category | Who can resolve | Today's signal |
|---|---|---|
| Resolvable from accessible primary | Sub-agent w/ web access | False alarm — should be addressed |
| Inaccessible-by-design (paywalled, image-only, preprint metadata) | Nobody (without paying / OCR) | Permanent — marker is the correct state |
| Speculative reasoning offered alongside the marker | Author judgment | Should become a citation or be softened |
| Empty table cells with no data | Either fetch or delete | Local content fix |
| Source-line provenance preamble | Don't touch | Removing would misrepresent the doc's own provenance |
| Meta-references to the convention itself | Nobody — it's commentary | False positive in `validate.sh` |

Because the token is overloaded, `validate.sh` reports them as one count;
authors can't easily filter the noisy ones from the actionable ones; and
projects accumulate residual permanent markers that clutter every validation
run.

## Phase 2 — token vocabulary split (this RFC's primary scope)

### Token vocabulary

Split the inline marker into four tokens:

- `[UNVERIFIED]` — verifiable in principle but not yet checked.
- `[MISSING_CITATION]` — a specific factual claim that needs a source pointer
  but the underlying claim is not in dispute. (Replaces today's `[NEEDS CITATION]`.)
- `[SPECULATION]` — author conjecture / brainstorming layer. Marks a claim
  as belonging to the speculative tier rather than the evidence tier.
- `[INACCESSIBLE]` — source is paywalled / image-only / private / DACO-gated.
  Marker is the correct epistemic state and is not expected to be resolved.

### Default severity table

> **Open policy question — `[SPECULATION]` default severity.** The table
> below picks INFO-by-default, on the grounds that flagging brainstorming
> as warnings would re-introduce the noise problem this RFC exists to
> solve, and `--strict` is the right surfacing path for pre-merge review.
> The alternative (WARN-by-default) treats unresolved speculation as a
> defect that should block merge until cited or softened. Pick before
> implementation; this RFC's deliverables otherwise unblock either choice.

| Token | Default severity | `--strict` | Notes |
|---|---|---|---|
| `[UNVERIFIED]` | WARN | WARN | Actionable; verify or retag. |
| `[MISSING_CITATION]` | WARN | WARN | Actionable; add citation. |
| `[SPECULATION]` | INFO (counted, not WARN'd) — *pending policy decision; see note above* | WARN | Default rationale: noise control. WARN-by-default is the alternative if the project wants to treat speculation as a merge blocker. |
| `[INACCESSIBLE]` | INFO (counted, not WARN'd) | WARN | Permanent epistemic state; surfaced only in audits. |

### `--strict` semantics (alignment with existing flag)

`validate.sh` already has a `--strict` flag (`validate.sh:44–46`: "emit
WARN for advisory/structural checks that are otherwise silent"). The marker
scanner's `--strict` reuses **the same flag**, with semantics widened to:

> When `--strict` is set, anything currently classified INFO is promoted
> to WARN. This applies uniformly to (a) the existing advisory/structural
> checks and (b) the new INFO-class markers (`[SPECULATION]`,
> `[INACCESSIBLE]`).

Rationale: introducing a separate `--strict-markers` flag would bifurcate
the loop-signal contract and surprise users who already understand
`--strict` as "tell me everything advisory." The marker scanner's behavior
is consistent with that mental model.

`science refs check` gains a matching `--strict` flag with the same
semantics so the two entry points stay aligned.

### Lexical scope: backticked vs bare

A token's *meaning* depends on whether it appears inside an inline-code
span or a fenced code block:

- **Bare token** in prose (e.g., `the n is [UNVERIFIED] in the abstract`)
  is a **document annotation** — counts toward severity tallies.
- **Backticked token** (e.g., `` mark this `[UNVERIFIED]` per the convention ``)
  is **documentation/example use** — referring to the token as a token.
  Excluded from tallies.
- Tokens inside fenced code blocks (`` ``` ``) are also excluded.

This split means meta-references in audit/notes/RFC docs (which discuss the
convention itself) can use the literal token without polluting validation
output, while bare-text annotations keep their meaning.

### Shared scanner (single source of truth)

A single Python scanner is the source of truth, used by both
`science refs check` and `validate.sh`. Implementation lives in
`science_tool/markers.py` (new module) with this surface:

```python
@dataclass(frozen=True)
class MarkerHit:
    file: Path
    line: int
    token: str           # "UNVERIFIED" | "MISSING_CITATION" | "SPECULATION" | "INACCESSIBLE"
    severity: str        # "warn" | "info"
    in_documentation: bool  # True if backticked or inside fenced code

def scan_markers(root: Path, *, include_documentation: bool = False) -> list[MarkerHit]: ...
```

Behaviors:

- Reuses `refs.py`'s existing fenced-block + inline-code stripping logic
  (factored into a shared helper rather than duplicated).
- Strips frontmatter before scanning (matches existing `refs.py` policy).
- Recognizes legacy `[NEEDS CITATION]` as an alias of `[MISSING_CITATION]`
  during the deprecation window (see Migration below).
- `validate.sh` is updated to call `science markers scan --format json`
  and aggregate counts. The bash-side regex is removed entirely; the
  earlier "re-grep with a backtick-exclusion regex" idea is dropped as
  too fragile for markdown.

### Frontmatter changes (separate deliverable, not bundled with token work)

This is *not* inline-token scope — it's a frontmatter-validator change.
Promoting it to its own deliverable:

- `science_model/frontmatter.py`: paper-type frontmatter validator accepts
  either `doi:` or `pmid:` as the canonical identifier; emits a warning
  only if both are missing.
- New CLI: `science paper sync` reads paper notes' frontmatter, calls
  `paper_fetch.py`'s existing DOI/PMID resolution machinery (already
  present at `science_tool/paper_fetch.py`), backfills the missing
  identifier, and writes the file. Idempotent. Tests verify (a) DOI→PMID
  forward fill, (b) PMID→DOI reverse fill, (c) noop when both present,
  (d) noop when neither resolvable.
- Removes the `pmid: "[UNVERIFIED]"` placeholder pattern observed in
  downstream projects (22 such cases in mm30 alone, 2026-05-09).

### Template + skill updates

- `science:research-papers` skill: emit the new tokens during summary
  drafting based on access status. PDF available → `[UNVERIFIED]` if not
  yet checked. Paywalled / image-only → `[INACCESSIBLE]`. LLM-only
  inference → `[SPECULATION]`. Specific factual claim → `[MISSING_CITATION]`.
- Paper-summary template: source-line preamble uses backticks
  (`` `[INACCESSIBLE]` ``) so it counts as documentation, not annotation.
- `science:writing` skill: include token-selection guidance.

### Migration

- `science markers migrate` (new subcommand) reads every doc, infers the
  right token from context (source line, surrounding prose, paper-type
  frontmatter access status), proposes per-line rewrites, and applies on
  `--write`. Heuristic-driven; produces a diff for human review.
- **Legacy alias handling**: scanner recognizes both `[UNVERIFIED]` and
  `[NEEDS CITATION]` as inputs and accepts them as synonyms for
  `[UNVERIFIED]` and `[MISSING_CITATION]` respectively. The CLI surfaces
  them under the new names but tags them as `legacy:true` in JSON output
  so audits can find pre-migration files.
- Deprecation window: legacy aliases recognized for at least one minor
  release; a `migration-status` check reports per-project share of legacy
  vs. new tokens.

### Rollout ordering across the managed-artifact boundary

`validate.sh` is a managed artifact: it is version-stamped at the top
(`science-managed-version`, `science-managed-source-sha256`) and copied
per-project. Upgrading the upstream copy does not touch downstream
projects until they re-sync. Sequencing matters because the new severity
defaults apply to *content*, not just to scanner internals — landing a
new `validate.sh` in a project that hasn't been migrated will reclassify
existing legacy tokens under the new rules.

Recommended sequence:

1. **Upstream — ship the scanner.** Land `science_tool/markers.py`,
   `refs.py` / `refs_cli.py` refactor, and `tests/test_markers.py` +
   updated `tests/test_refs.py`. Legacy aliases (`[NEEDS CITATION]` →
   `[MISSING_CITATION]`, `[UNVERIFIED]` → `[UNVERIFIED]`) recognized
   from day one. No downstream impact yet — `validate.sh` still uses
   bash grep at this stage.
2. **Upstream — bump managed-artifact version.** Update
   `validate.sh`'s canonical body to call `science markers scan
   --format json`, bump `science-managed-version` and recompute the
   source-sha256.
3. **Per downstream project — re-sync `validate.sh`.** Triggered via
   `science health` or the equivalent managed-artifact resync flow.
   At this point, `validate.sh` runs with the new scanner and severity
   defaults; legacy tokens are still recognized but classified under
   the new framework.
4. **Per downstream project — run `science markers migrate`.** Rewrites
   legacy tokens to their new spellings, with a diff for human review.
   This is optional from a correctness standpoint (the scanner accepts
   both) but desirable so that `migration-status` reports can show
   completion and so that future readers see the new vocabulary in
   prose.
5. **After deprecation window — drop legacy alias recognition.** The
   scanner stops accepting `[NEEDS CITATION]`; any project that hasn't
   migrated by then sees its legacy tokens classified as unrecognized.
   Drop is gated on `migration-status` showing zero legacy hits across
   all known downstream projects.

Steps 3 and 4 can interleave per-project; step 4 must not run before
step 1 (the scanner has to exist). Step 2 must not land before step 1.

### Deliverables for phase 2

1. **Shared marker scanner** — `science_tool/markers.py` with
   `scan_markers()` API; per-token severity (default + `--strict`); inline-
   code, fenced-code, and frontmatter exclusion; legacy-alias recognition
   for `[NEEDS CITATION]` → `[MISSING_CITATION]` and the implicit
   `[UNVERIFIED]` → `[UNVERIFIED]` (no-op, clarity only).
2. **`refs.py` + `refs_cli.py` refactor** — replace `_UNVERIFIED_RE` /
   `_NEEDS_CITATION_RE` and `_render_marker_summary`'s hardcoded two-token
   split (`refs_cli.py:55–70`) with calls into the shared scanner.
   `RefIssue` gains a `severity` field. JSON output groups markers by
   token; table output renders per-token counts.
3. **`validate.sh` patch** — replaces the bash grep at the project-template
   `validate.sh:514` with `science markers scan --format json`. Per-token
   counters in the summary block.
4. **`tests/test_refs.py` + `tests/test_markers.py`** — unit tests for:
   bare vs. backticked vs. fenced-code exclusion; each new token; legacy
   `[NEEDS CITATION]` recognized as `[MISSING_CITATION]`; `--strict`
   promotes INFO → WARN; frontmatter exclusion; multi-token-per-line.
5. **Frontmatter `doi:`/`pmid:` mutual-optional validator** + **`science
   paper sync` command** + tests (separate deliverable from the marker
   scanner, but lands in the same release).
6. **Skill + template updates** — `science:research-papers`,
   `science:writing`, paper-summary template.
7. **Documentation** — `docs/conventions/annotation-tokens.md` with the
   severity table, lexical-scope rule, and migration guidance.

Phase 2 is intentionally scoped to inline tokens. No ROI machinery, no
sidecar files, no graph integration. Forward-compatible with phase 3.

## Phase 3 — full sub-document annotation system (deferred RFC)

### Open design questions (need a dedicated `/science:brainstorming` session)

**ROI anchoring.** Three plausible shapes:

- **Pure inline tokens** (extend phase 2): cheap, edit-robust, low precision,
  single-payload. Adequate for uncertainty markers, NER stubs, simple TODOs.
- **Anchored sidecar**: prose carries `{#anchor-id}` attribute spans;
  annotations live in a sidecar `.annotations.yaml` keyed by anchor ID.
  Precise, multi-annotation per ROI, machine-queryable, but authoring cost
  + drift risk if prose is edited without updating the anchor.
- **Hybrid**: inline tokens for the common shallow case; sidecar for rich
  payloads (meta-questions, ontology refs with confidence, multi-annotation
  stacking). The split between "shallow" and "rich" is itself a design call.

**Annotation type taxonomy.** Beyond uncertainty markers (phase 2's scope),
candidate types from the brainstorming conversation:

- Inline entity refs with linked ontologies (NER + canonical-ID resolution).
- "Meta" thoughts — questions about questions, counter-arguments,
  steelman/strawman tags.
- Sub-document tasks (e.g., "expand this section after t099 lands").
- Confidence / provenance annotations on specific claims.
- Replication / contradiction links between specific sentences.

**Multi-annotation per ROI.** `(start, end) → list[Annotation]` was the
informal proposal. In practice ~90% of cases are single-annotation; the
multi case appears for ontology + uncertainty stacking. Start with single,
extend to multi when motivated.

**Graph integration.** Annotations should land as triples so they're
cross-referenceable with the existing entity model in `graph.trig`. Open:
do annotations get their own `annotation:` ID kind, or do they extend
existing entities (e.g., a `claim:` entity carries an annotation block)?

**Migration from phase 2.** The four phase-2 tokens become annotation
*types* under phase 3 (lowest-friction lift). Existing inline tokens
continue to work; richer payloads opt into sidecar form.

### Prior art to scan before designing

- **CriticMarkup** — `{++inserted++}`, `{--deleted--}`, `{>>comment<<}`,
  `{~~old~>new~~}`. Author-friendly inline syntax. Limited type vocabulary.
- **Pandoc spans** — `[text]{.class key=val}`. Inline, typed, attribute-
  bearing. Good lexical fit for typed annotations, no ROI machinery beyond
  span boundaries.
- **JATS `<annotation>` / NLM** — XML-heavy, but the data model
  (annotation type, target, payload) is mature.
- **hypothes.is** — sidecar model, anchors via fuzzy text matching plus
  XPath. Robust to prose edits via fuzzy fallback; complex.
- **Argdown** (https://argdown.org/) — argument-mapping syntax. Specifically
  interesting for the "meta thoughts" / counter-argument annotation type;
  could provide a structured layer for argumentation rather than re-inventing.
- **Semantic line breaks** (https://sembr.org/) — orthogonal but useful as
  an authoring convention that makes line-anchored annotations less brittle
  to whitespace edits.

### Phase 3 deliverables (when scoped)

To be designed in a follow-up RFC. Not in scope for phase 2.

## Phase ordering rationale

Phase 2 is small, low-risk, and forecloses nothing. It addresses the
immediate operational pain (overloaded `[UNVERIFIED]` token, noisy
validate output, `pmid:` placeholder pattern) and provides a forward-
compatible vocabulary for phase 3.

Phase 3 has multiple coupled design decisions (ROI shape, type taxonomy,
multi-annotation, graph integration, migration) that warrant a dedicated
brainstorming pass. Trying to settle them in the same RFC would
either delay phase 2's tactical wins or under-design phase 3.

## References

- mm30 cleanup audit: `[mm30-repo]/doc/audits/2026-05-09-unverified-marker-triage.md`
- `validate.sh` current behavior: section 8 (unresolved markers), grep on
  literal `[UNVERIFIED]` and `[NEEDS CITATION]`.
- Related project conventions: `docs/conventions/`, paper-summary template.
