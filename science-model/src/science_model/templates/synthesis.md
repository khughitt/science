---
id: "synthesis:{{slug}}"           # synthesis:<hyp-id> | synthesis:rollup | synthesis:emergent-threads
type: "synthesis"
report_kind: "{{kind}}"            # hypothesis-synthesis | synthesis-rollup | emergent-threads
generated_at: "{{ISO 8601}}"
source_commit: "{{40-char sha}}"

# Required only when report_kind == synthesis-rollup:
synthesized_from:                  # cross-hypothesis sha-tracked source-of-truth list
  - hypothesis: "hypothesis:<slug>"
    file: "specs/hypotheses/<slug>.md"
    sha: "{{40-char sha}}"
emergent_threads_sha: "{{40-char sha}}"   # rollup links to its companion threads file

# Required only when report_kind == hypothesis-synthesis:
hypothesis: "hypothesis:<slug>"
provenance_coverage: "{{full|partial|none}}"

# Required only when report_kind == emergent-threads:
orphan_question_count: 0
orphan_interpretation_count: 0
orphan_ids: []                     # full list per the scaling rule in the agent file

# Optional, all kinds:
phase: "active"
---

# Synthesis: {{Short Title}}

<!--
  Body skeleton — `science:big-picture` writes these procedurally. Hand-edits
  may populate the same headings to keep the shape consistent across runs.
-->

## TL;DR

<!-- Two-sentence summary: what the synthesis finds, what it leaves open. -->

## State

<!-- Current evidence weight per claim/hypothesis covered by this synthesis. -->

## Arc

<!-- How the picture has changed over time — earlier vs. later evidence. -->

## Research fronts

<!-- Open lines of inquiry the synthesis surfaces. -->

## Candidate frames

<!-- Alternative interpretations or models that fit the evidence. -->

## Knowledge Gaps

<!-- What's missing that would change the picture. -->

## Emergent threads

<!-- Cross-hypothesis patterns; only on rollup / emergent-threads kinds. -->
