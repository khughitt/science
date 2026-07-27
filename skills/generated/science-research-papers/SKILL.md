---
name: science-research-papers
description: "Research and summarize one or more scientific papers."
user-invocable: true
---

# Research Papers

## Science Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load the `science-command-preamble` skill. Use its
   `references/role-prompts/research-assistant.md` role prompt and its aspect definitions.
3. Load the `science-scientific-writing` skill. For research methodology, read the `science-command-preamble` skill's `references/methodology-index.md` and load the relevant generated methodology router skills (e.g. `literature-evaluation`, `literature-citation-discipline`, `epistemics-proposition-graph-reasoning`).
4. Read project context from current entity roots:
   - `entities/questions/` for active research questions.
   - `entities/hypotheses/` for hypotheses.
5. **Load project aspects:** Read `aspects` from `science.yaml` (default: empty list).
   For each declared aspect, resolve the aspect file in this order:
   1. the `science-command-preamble` skill's `references/aspects/<name>/<name>.md` — canonical Science aspects
   2. `.ai/aspects/<name>.md` — project-local aspect override or addition

   If neither path exists (the project declares an aspect that isn't shipped with
   Science and has no project-local definition), do not block: log a single line
   like `aspect "<name>" declared in science.yaml but no definition found —
   proceeding without it` and continue. Suggest the user either (a) drop the
   aspect from `science.yaml`, (b) author it under `.ai/aspects/<name>.md`, or
   (c) align the name with one shipped under the `science-command-preamble` skill's `references/aspects/`.

   When executing command steps, incorporate the additional sections, guidance,
   and signal categories from loaded aspects. Aspect-contributed sections are
   whole sections inserted at the placement indicated in each aspect file.
6. **Check for missing aspects:** Scan for structural signals that suggest aspects
   the project could benefit from but hasn't declared:

   | Signal | Suggests |
   |---|---|
   | Files in `entities/hypotheses/` | `hypothesis-testing` |
   | Files in `models/` (`.dot`, `.json` DAG files) | `causal-modeling` |
   | Workflow files, notebooks, or benchmark scripts in `code/` | `computational-analysis` |
   | Package manifests (`pyproject.toml`, `package.json`, `Cargo.toml`) at project root with project source code (not just tool dependencies) | `software-development` |

   If a signal is detected and the corresponding aspect is not in the `aspects` list,
   briefly note it to the user before proceeding:
   > "This project has [signal] but the `[aspect]` aspect isn't enabled.
   > This would add [brief description of what the aspect contributes].
   > Want me to add it to `science.yaml`?"

   If the user agrees, add the aspect to `science.yaml` and load the aspect file
   before continuing. If they decline, proceed without it.

   Only check once per command invocation — do not re-prompt for the same aspect
   if the user has previously declined it in this session.
7. **Resolve templates:** When a command says "Read `.ai/templates/<name>.md`",
   check the project's `.ai/templates/` directory first. If not found, read from
   `references/templates/<name>.md`. If neither exists, warn the
   user and proceed without a template — the command's Writing section provides
   sufficient structure.
8. **Verify the project-local Science CLI:** Execute the top-level CLI
   Compatibility Gate below before the command's first Science invocation. It
   uses the consumer's frozen lock; do not route through a toolkit checkout or
   another environment.

## CLI Compatibility Gate

```bash
SCIENCE_REQUIRED_VERSION=0.3.0
if output=$(uv run --frozen science --version 2>&1); then
  SCIENCE_INSTALLED_VERSION=${output##* }
elif uv run --frozen science --help >/dev/null 2>&1; then
  # The CLI runs but has no --version option, so it predates the baseline.
  # Decided by behavior, never by matching Click's version-dependent wording.
  SCIENCE_INSTALLED_VERSION=
else
  # The CLI cannot run at all: missing/stale lock, Git fetch failure, import
  # error. Report the real diagnosis; never advise moving the Science pin.
  printf '%s\n' "$output" >&2
  exit 1
fi

if ! SCIENCE_INSTALLED_VERSION="$SCIENCE_INSTALLED_VERSION" \
     SCIENCE_REQUIRED_VERSION="$SCIENCE_REQUIRED_VERSION" \
     uv run --no-project python - <<'PY'
import os
import re
import sys

def release(name: str) -> tuple[int, int, int] | None:
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", name)
    return tuple(map(int, match.groups())) if match else None

installed = release(os.environ["SCIENCE_INSTALLED_VERSION"])
required = release(os.environ["SCIENCE_REQUIRED_VERSION"])
sys.exit(0 if installed is not None and required is not None and installed >= required else 1)
PY
then
  display=${SCIENCE_INSTALLED_VERSION:-unknown-or-pre-0.3.0}
  echo "This Science agent command requires science >=$SCIENCE_REQUIRED_VERSION; found $display." >&2
  echo "upgrade with: uv lock --upgrade-package science && uv sync --frozen" >&2
  exit 1
fi
```

After the gate succeeds, run the command through the consumer's project-local
environment as `uv run science <command>`. Missing dependency, missing or stale
lock, and Git fetch failures are surfaced directly and must be fixed in the
consumer project.

A CLI that answers `--help` but rejects `--version` predates the baseline;
malformed successful output and a version below the floor are likewise
compatibility failures, and all three stop with the upgrade command. A CLI that
cannot run at all is an environment failure: its output is printed verbatim and
must be fixed as reported.

The `--help` probe is what separates those two classes. Do not substitute a match
against Click's error text — its wording changed in Click 8.4, and `science`
allows any `click>=8.1`, so a freshly locked consumer can emit either form. The
root `--version` probe is the permanent bootstrap surface; do not replace it with
a preflight subcommand, which an older CLI could not recognize either.

Research and summarize one or more papers specified by the user input.
Each paper may be given as a title, author name(s), DOI, URL, or a file path to a PDF.

the user input may contain a single paper or a list. Parse lists liberally:
- Newline-separated items
- Numbered or bulleted items (`1.`, `2.`, `-`, `*`)
- Comma-separated DOIs/titles on one line when unambiguous

If the split is ambiguous (e.g., a title that contains commas), ask the user to confirm before dispatching.

## Dispatch Strategy

This command runs in two roles. Determine which you are before proceeding.

### If you are the orchestrator

(You received the `/research-papers` slash command directly from the user.)

1. **Parse** the user input into a list of paper references. Let `N` be the count.
2. **Pre-dispatch check:** For each paper, look at `entities/papers/` for an existing summary (fuzzy match on title/author/DOI). If any may exist, ask the user whether to overwrite, skip, or supplement — resolve per-paper, then carry each decision into that paper's subagent prompt.
3. **Dispatch** the `paper-researcher` subagent *once per paper*. When `N > 1`, issue Agent calls **in parallel** (multiple tool uses in a single message) so they overlap — the shared rate limiter in `science paper-fetch` keeps per-host traffic polite automatically. **Cap each wave at ~5 concurrent subagents.** Larger waves stall on PDF-heavy work: a subagent that renders a big PDF through the Read tool can hang with "no progress for 600s". For `N > 5`, dispatch in waves of ~5 and steer each subagent to extract text with `pdftotext` (Read only for specific figures), per Source Strategy.
   - `subagent_type: paper-researcher`
   - `description`: a short identifier for that paper
   - `prompt`: the single paper's reference + its overwrite decision + any project-specific context the subagent would not otherwise discover
4. Do **not** perform the Setup / Source Strategy / Writing / After Writing steps below yourself — those are each subagent's job, and dispatching preserves the cost savings this command exists for.
5. When all subagents report back, continue at **Orchestrator Post-Dispatch**. For `N ≥ 2` papers with a shared thematic connection, also run **Batch Processing**.

### If you are the `paper-researcher` subagent

Skip the Dispatch Strategy section and execute Setup → Source Strategy → Writing → After Writing for your one assigned paper. Then report back per the response contract in your agent definition.

## Setup


Additionally:
1. Read `.ai/templates/paper.md` first; if not found, read `references/templates/paper.md`.
2. Check `entities/papers/` for existing summary; ask before overwriting.

## Source Strategy

**If the user supplied a local PDF path, start here — this branch short-circuits the rest of Source Strategy.** Do not run `science paper-fetch` for retrieval, and never treat a `paywalled` / `not_found` status as a stop condition when a PDF is already in hand: the full text is the PDF.

1. Prefer `pdftotext <path> -` (or `pdftotext <path> out.txt`) to extract the body text; use the Read tool only for specific figures/tables you actually need. Reading a large PDF through the Read tool renders every page as an image and can stall a subagent (see the concurrency cap in Dispatch Strategy).
2. Read: Abstract, Introduction, Methods, Results, Discussion/Conclusion. Skip References, supplemental materials, and acknowledgments unless a template field needs them.
3. Extract the required template fields. Only then, if the PDF surfaces a DOI, run `paper-fetch --doi <doi>` **for metadata cross-check only** (fast and safe) — a `paywalled` result there is irrelevant; you already have the text.

Otherwise (no local PDF), retrieval is centralized through `science paper-fetch`, which handles tiered source probing (Crossref → Unpaywall → arXiv → bioRxiv/medRxiv → Europe PMC → direct OA PDF) with cross-process rate limiting. This avoids open-ended scavenging and keeps parallel subagents polite to the same servers.

### Picking the right identifier flag

`paper-fetch` accepts the identifier in whatever form the user provided — pass it through as-is rather than pre-resolving:

| User-supplied form | Flag |
|--------------------|------|
| DOI or `doi.org/…` URL | `--doi <value>` |
| arXiv ID (e.g. `2502.09135`) | `--arxiv <id>` |
| arXiv URL (`arxiv.org/abs/…`) | `--url <url>` |
| PubMed ID | `--pmid <pmid>` |
| PubMed URL (`pubmed.ncbi.nlm.nih.gov/…`) | `--url <url>` |
| PMC ID (e.g. `PMC12934989`) | `--pmcid <pmcid>` |
| PMC URL (`pmc.ncbi.nlm.nih.gov/articles/…`) | `--url <url>` |
| bioRxiv/medRxiv URL | `--url <url>` |
| Title only | One Crossref search, then `--doi <result>` |

When both a DOI and a PMID/PMCID are available (e.g. user gave both, or a PubMed page surfaced both), pass both — `paper-fetch` cross-checks them and returns `status: error` with `metadata.reason: identifier_mismatch` if they conflict, catching wrong-DOI mistakes before you summarize the wrong paper.

### Branching on the result

Run `paper-fetch` once with the chosen flag(s) and branch on `status`:

- **`ok`** — read the file at `pdf_path` / `text_path` and fill the template. Cross-check key metadata via targeted searches only when template fields require it; mark each not-yet-checked detail as `[UNVERIFIED]`; mark paywalled / image-only / DACO-gated source content as `[INACCESSIBLE]`; mark author conjecture as `[SPECULATION]`.
  - **Author-attribution check (before writing).** If the user's request named an author or research group, compare it against `metadata.authors[0]` from the `paper-fetch` result. On a clear mismatch (different surname, or different institutional group), pause and surface the discrepancy to the orchestrator before writing — the user may have had the wrong paper in mind, or the wrong author for the right paper. Don't silently follow either source; flag the conflict so the orchestrator can confirm with the user.

- **`paywalled`** — Unpaywall has no OA record **and** `paper-fetch`'s DOI→PMCID→Europe PMC full-text tier also came up empty (PMC is checked before this verdict, so a `paywalled` status already means no PMC/author-manuscript copy was found — don't WebFetch the publisher page to re-confirm). By default: stop, set `Source: paywalled`, and either (a) defer with `status: paywalled` in frontmatter, or (b) re-run against a PDF if the user supplies one. **If you have independent reason to expect an OA copy** (NIH-funded work, or the user references a PMC URL / PMCID / `nihms-*` file), re-run `paper-fetch` with `--url <pmc-url>` or `--pmcid <PMCID>` before deferring — it can recover full text Unpaywall missed.
  - **Well-known classic exception** — if *all* of the following hold, you may proceed on LLM knowledge instead of stopping:
    - Published more than 3 calendar years ago (i.e. `year ≤ current_year − 3`).
    - Widely cited (>500 citations — quick estimate via Crossref `is-referenced-by-count` or a Google Scholar lookup).
    - Task is conceptual/theoretical synthesis, not data extraction or methods replication.
    - Paper is comprehensively covered by general LLM training (a foundational paper, not a niche follow-up).
  - When proceeding under this exception: set `Source: LLM knowledge`, mark every specific number / figure / method detail as `[UNVERIFIED]` (you may verify later) — but mark conceptual extrapolations beyond what the abstract states as `[SPECULATION]`, and **do not invent quantitative claims** (cohort sizes, effect sizes, fold-changes, accuracies). Stick to conceptual contributions.
  - **Review-paper triangulation** — if the paywalled paper's Crossref `type` indicates a review (or the title says "review" / "perspective"), pull 2-3 citing primary papers via Europe PMC's citations endpoint and triangulate the headline claims rather than relying on the abstract alone.

- **`blocked_but_oa`** — OA copy exists but every agent-accessible tier failed. Before asking the orchestrator for a PDF, try one Europe PMC abstract-level fallback: `WebFetch https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:"<doi>"&format=json` — if it returns an abstract, you have enough for the summary's overview/significance fields (mark methods/results as `[INACCESSIBLE]` — the full text is not reachable from any agent-accessible tier). If that also fails, ask the orchestrator to request a PDF. Do not retry with open-ended search.

- **`not_found`** — no source resolved the identifier. Ask the orchestrator for better metadata; do not fabricate a summary.

- **`error`** — caller-supplied identifiers conflict (`metadata.reason` names the class, e.g. `identifier_mismatch`). Surface the conflict in `access_hint` to the orchestrator and stop — re-checking is the user's call.

### If the paper cannot be found:

1. State that the paper could not be identified reliably.
2. Ask for full title, first author, year, venue, or DOI.
3. Ask for a PDF path if available.
4. Do not fabricate a summary.

## Writing

Follow `.ai/templates/paper.md` first, then `references/templates/paper.md`, and fill every section.

- Include frontmatter `Source:` describing provenance (`LLM knowledge`, `web search`, `PDF`, or combination).
- **Frontmatter must use `kind: paper`, not `type: paper`** — `type:` is dropped and the entity then fails `science validate` with missing `kind`/`status`/`updated`. **Never add a `datasets:` field** (retired); record dataset provenance under `dataset_usage`. When in doubt, scaffold with `science entity create paper --slug <citekey>` and edit the pre-filled frontmatter rather than hand-writing it.
- Generate BibTeX key as `FirstAuthorLastNameYear` (with suffix if needed).
- Save to `entities/papers/<citekey>.md`.
- Use `paper:<citekey>` for the paper note entity and `cite:<citekey>` for the backing BibTeX entry in `source_refs`.

## After Writing

1. Add the BibTeX entry to `papers/references.bib` via `science bib add` — **never** Edit/Write the file directly:
   ```bash
   uv run science bib add --project-root . <<'EOF'
   @article{<citekey>, title={...}, author={...}, year={...}, ... }
   EOF
   ```
   This does a single locked append: it creates the file with a header if missing, is idempotent by key (re-running is a safe no-op; pass `--replace` to overwrite), and serializes concurrent writes from parallel subagents. A direct Edit instead hits "file modified since read" errors under Dropbox sync and races other subagents in a batch.
2. Link relevance to existing hypotheses in `entities/hypotheses/`.
3. Add new questions via `science questions reserve`. **Do not** create files under `entities/questions/` directly — parallel subagents racing on the next q-number cause silent collisions. The CLI uses `O_CREAT|O_EXCL` to atomically claim the next slot, even with multiple subagents writing concurrently.
   Read `.ai/templates/question.md` first; if not found, read
   `references/templates/question.md` before drafting question bodies.

   For each new question:
   ```bash
   uv run science questions reserve \
     --slug "<short-kebab-slug>" \
     --title "<question title>" \
     --source-refs "cite:<this paper's citekey>" \
     [--related "<related-id>,<related-id>"] \
     [--ontology "<term>,<term>"] \
     --json
   ```
   The command returns JSON with the assigned `path`. Read that file (it has frontmatter pre-filled and section scaffolding) and edit the body sections in place. The project's `.ai/templates/question.md` overrides the default body via `--template <path>` if needed.
4. Note approach implications in `doc/04-approach.md` when relevant.
5. Commit: `git add -A && git commit -m "docs(papers): research <citekey> - <short title>"`. The `docs(papers):` prefix is commitlint-conventional compliant out of the box; if your project's commitlint config explicitly allows `papers:` as a custom type, prefer that.

## Annotation tokens

Use the four-token vocabulary defined in `references/docs/conventions/annotation-tokens.md`:

- `[UNVERIFIED]` — the claim is verifiable in principle but you haven't checked.
- `[MISSING_CITATION]` — the claim needs a specific source pointer (the claim itself isn't in dispute).
- `[SPECULATION]` — author conjecture; not from the source.
- `[INACCESSIBLE]` — paywalled / image-only / DACO-gated / private; resolution requires resources you don't have.

Pick by access status, not by reflex. Most paper-summary fields warrant `[UNVERIFIED]` (the PDF is in front of you — it's verifiable). Switch to `[INACCESSIBLE]` only when the source genuinely can't be reached. `[SPECULATION]` is for your own extrapolations, never for things that should have been quoted from the paper.

## Orchestrator Post-Dispatch

After the subagent returns its report:

1. Review any `[UNVERIFIED]` / `[SPECULATION]` fields the subagent flagged and surface them to the user — they may warrant a follow-up web check or a note in `entities/questions/`. (`[INACCESSIBLE]` markers are permanent and don't need follow-up.)
2. If the subagent could not identify the paper, relay its request for additional metadata to the user and stop; do not attempt to fabricate a summary on the orchestrator.
3. Read the written summary only if you need its content for downstream reasoning (e.g., before cross-paper synthesis or hypothesis linking). Otherwise, trust the report.
4. If you hold broader project context than the subagent did — unmerged hypotheses, recent approach decisions in `doc/04-approach.md`, adjacent open questions — make small follow-up edits as a separate commit.

## Batch Processing (orchestrator)

When the dispatched batch contained `N ≥ 2` papers with a shared thematic connection, after all subagent reports return:

1. Produce a brief cross-paper synthesis at `entities/papers/synthesis-YYYY-MM-DD-<theme>.md`. Synthesis is an orchestrator responsibility because it requires holding all papers in context at once — the subagents do not talk to each other.
2. Contents: shared themes, tensions between papers, and combined implications for the project.
3. Cross-reference the individual paper summaries by their `id` fields.

Skip synthesis when the papers are unrelated (e.g., the user dropped a mixed list for cleanup). A shared connection is the trigger, not the count.

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science feedback add \
  --target "command:research-papers" \
  --category <friction|gap|guidance|suggestion|positive> \
  --summary "<one-line summary>" \
  --detail "<optional prose>"
```

Guidelines:
- One entry per distinct issue (not one big dump)
- If the same issue has occurred before, the tool will detect it and
  increment recurrence automatically
- Skip if everything worked smoothly — no feedback is valid feedback
- For template-specific issues, use `--target "template:<name>"` instead
