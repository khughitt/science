# /annotate-paper

Extract sub-article **statements** (propositions/questions/hypotheses) and **figures**
(metaphors/analogies) from a paper that already has a persisted `.source.md` and PubTator
annotations, via the `paper-annotate` subagent.

## Usage

`/annotate-paper <pmid|doi|citekey>` — optionally `--force` to re-run even if unchanged.

## Workflow

1. **Resolve the paper** to its `<citekey>.source.md` path and directory. If no `.source.md`
   exists, stop and tell the user to run `science paper persist-source <id>` first (this command
   does not auto-persist).

2. **Precheck the document guard** (skip burning the model on unchanged text):

   ```bash
   uv run science annotate extract --source-md <path> --model <model-id> --check
   ```

   If it prints `{"status":"unchanged"}` and `--force` was not given, stop: report "already
   extracted, source unchanged." Otherwise continue.

3. **Dispatch the `paper-annotate` subagent** with `--source-md <path>` and `--model <model-id>`.
   The subagent reads existing annotations + the source text, emits `candidates.json`, and runs
   `science annotate extract`.

4. **Surface the report** the subagent returns (written / skipped / grounding_dropped). For bulk
   runs, dispatch one subagent per paper (they are independent; the deterministic command
   serializes its own writes per sidecar).

## Notes

- The `paper-annotate-v1` source version means a prompt/schema change later (a `v2` bump) will
  correctly re-run all papers; the `--check` guard is keyed per source version.
- Promotion of statements into epistemic entities is a separate, later step — this command only
  writes raw evidence annotations.
