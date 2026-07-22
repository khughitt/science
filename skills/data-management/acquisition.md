---
name: data-management-acquisition
description: Use when acquiring or registering a new data source for a project, or scripting reproducible preprocessing before data enters analysis.
archetype: practice-guide
provenance: internal
---

# Data Acquisition & Preprocessing Workflow

Answers: how do I bring new data into a project reproducibly?

## When to apply

When acquiring or registering a new data source for a project, before it enters
analysis, and whenever writing preprocessing that transforms raw data into
analysis-ready files.

## Workflow steps

1. **Register the durable dataset entity** through the singular lifecycle:
   ```bash
   science dataset add <slug> \
     --title "<dataset title>" \
     --source-url "<landing-page-or-accession-url>" \
     --level <public|registration|controlled|commercial|mixed> \
     --tier <use-now|evaluate-next|track>
   ```
2. **Verify access evidence** before pipeline planning consumes the dataset:
   ```bash
   science dataset verify-access <slug> \
     --license <spdx-or-unknown> \
     --method <retrieved|credential-confirmed|landing-confirmed|metadata-confirmed> \
     --source-url "<landing-page-or-download-url>"
   ```
3. **Link the dataset** to the question or hypothesis it supports:
   ```bash
   science dataset link <dataset-ref> <question-or-hypothesis-ref>
   ```
4. **Add acquisition scripts** to `code/scripts/` or workflow rules under
   `code/workflows/`.
5. **Create or update runtime datapackage descriptors** in the appropriate data
   directory — the descriptor *format* is [`frictionless.md`](frictionless.md);
   *where* the files live is [`conventions.md`](conventions.md).

## Judgment rules

- **Prefer the CLI.** Manual template authoring is a fallback. Use `science dataset add` /
  `verify-access` whenever the current CLI fields can express the record. Write
  `entities/datasets/<slug>.md` by hand only when the CLI cannot represent a
  needed field, for a deliberate legacy backfill, or a project-specific review
  template — keep unknown evidence visibly marked, then run
  `science dataset verify-access <slug>` or record the blocked verification
  reason.
- **Manual download is a degraded mode.** When automated download support is
  unavailable, download by hand into the **resolved data root's** `raw/` (logical
  `data/raw`, physically `<resolved-root>/raw` — the root resolves per
  `SCIENCE_DATA_ROOT` / `science.yaml` `data.root`; see
  [`conventions.md`](conventions.md)), never a literal `./data` when a root is
  configured.
- **Keep descriptors current** for raw and processed directories as data changes.

## Quality criteria

- **Preprocessing is reproducible:** every transformation is scripted (in
  `code/scripts/` or `code/workflows/`) and documented with provenance — which
  script produced each processed file, from what inputs.
- **Raw data is untouched:** transformations write to `data/processed/`, never
  back into `raw/` (the invariant is defined in [`conventions.md`](conventions.md)).

## Common pitfalls

- **Unbounded untrusted input before parsing.** When a step feeds real-world,
  heterogeneous, or externally-sourced content to a parser (LaTeX, HTML, XML,
  regex, etc.), cap the input length up front with a per-step budget. Many real
  parsers are super-linear, so a single pathological record can exhaust memory
  and OOM-kill the whole run — a failure mode small fixtures never exhibit.
  Verify the bound is output-neutral on normal records.
- **Acquiring data without registering the durable `dataset:<slug>` entity** —
  the entity is what pipeline planning and provenance consume.
- **Silent manual edits to raw data** — any change belongs in a scripted
  `data/processed/` step, not an in-place edit.

## Outputs

- A registered `dataset:<slug>` entity with verified access evidence, linked to
  the question or hypothesis it supports.
- Acquisition/preprocessing scripts under version control in `code/scripts/` or
  `code/workflows/`.
- Current runtime datapackage descriptors for the raw and processed data
  directories.

## Success test

Did the agent carry out the acquisition workflow per its steps, judgment rules,
and quality criteria — dataset registered, access verified, preprocessing
scripted, descriptors present?

## Companion Skills

- `../INDEX.md` — the skill index.
- [`SKILL.md`](SKILL.md) — the data-management router.
- [`conventions.md`](conventions.md) — where acquired data and results must live.
- [`frictionless.md`](frictionless.md) — the descriptor format this workflow produces.
- [`../literature/literature-evaluation.md`](../literature/literature-evaluation.md) — source-choice evaluation for data-source provenance.
- [`../literature/citation-discipline.md`](../literature/citation-discipline.md) — citation conformance for data-source references.
