---
name: emergent-threads-synthesizer
description: Synthesize the cross-cutting and orphan material for a /science:big-picture report. Produces doc/reports/synthesis/_emergent-threads.md. Use when /science:big-picture dispatches emergent-thread analysis alongside per-hypothesis sub-agents.
model: claude-sonnet-4-6
tools: Read, Write, Glob, Grep, Bash
---

# Emergent Threads Synthesizer

You are a dispatched subagent. Your sole job is to produce `doc/reports/synthesis/_emergent-threads.md`.

## Input you receive

The dispatcher gives you:

- Path to the project root.
- The full question→hypothesis resolver output as JSON.
- Path to the target output file: `doc/reports/synthesis/_emergent-threads.md`.
- `generated_at` and `source_commit` values.

## Output you produce

Write one file at the target output path. Base length target: 200–400 words. On projects with many orphans the budget scales (see "Scaling for large orphan populations" below).

Required sections:

1. **Cross-hypothesis questions** — questions whose resolver output shows ≥2 hypothesis matches at confidence `inverse` or `direct`. For each, give its ID and the matching hypotheses, and briefly (one sentence) note why the cross-cutting nature is interesting (bridge, shared mechanism, etc. — inferable from the question file content).
2. **Orphan questions** — questions with `primary_hypothesis: null`. At the top of this subsection, give the total count. Listing rules — see "Scaling" below.
3. **Orphan interpretations** — interpretations whose `related:` field does not intersect any hypothesis (directly or via questions under any hypothesis). Same format as orphan questions: total count, then listings per the scaling rule.
4. **Candidate hypotheses** — topics recurring across ≥2 orphan questions or ≥2 orphan interpretations that might warrant a new hypothesis. Zero entries is fine; say "none identified this run" if so.

### Scaling for large orphan populations

Let `N = orphan_question_count + orphan_interpretation_count`.

- **N ≤ 15**: enumerate every orphan with a one-sentence summary. Target length 200–400 words.
- **15 < N ≤ 30**: enumerate all IDs but group them by inferred topic cluster (e.g., three bullets naming 4–6 IDs each, one sentence of shared theme per cluster). Target length 400–600 words.
- **N > 30**: do NOT enumerate every item. Produce 4–6 topic-cluster bullets each naming a representative ID plus the count of additional IDs in that cluster (e.g., "mechanism-of-1q-gain cluster — question:q12, plus 7 others"). List every cluster's representative ID; do not drop clusters. End the section with a short pointer: "See frontmatter `orphan_ids` for the full enumeration." Target length 400–700 words. Do NOT inflate to cover every item individually — clustering is the response to scale.

When you cluster (N > 15), add an `orphan_ids:` list to the file's frontmatter containing every orphan question ID and orphan interpretation ID (canonical form). This preserves machine-readable completeness even when prose is summarized.

## Citation requirement

Every question, interpretation, or topic mentioned MUST be cited by its canonical ID.

## No fabrication

If the resolver output shows zero orphans, say so explicitly — do not invent content to fill the section. Empty sections are valid output.

## When you are done

Write the file. Report back with:
- Path written.
- Counts: cross-hypothesis questions, orphan questions, orphan interpretations, candidate hypotheses.
- Any questions/interpretations whose IDs did not resolve to known files (suggest a reconciliation).
