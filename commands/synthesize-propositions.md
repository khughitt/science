---
description: Propose the reasoning fields (predicate, polarity, claim_layer, refined subject/object) of a paper's promoted propositions, via the proposition-synthesize subagent.
---

# /synthesize-propositions

Propose the *reasoning fields* — `predicate`, `polarity`, `claim_layer`, and refined
`subject` / `object` — of the promoted propositions for one paper, via the
`proposition-synthesize` subagent. The agent only proposes; the curator reviews and applies.

## Usage

`/synthesize-propositions <pmid|doi|citekey>`

## Workflow

1. **Resolve the paper** to its `<citekey>.source.md` path and the project `--root`. The paper's
   statements must already have been promoted into proposition entities
   (`science annotate promote`); this command fills the reasoning fields those propositions left
   unset, it does not promote.

2. **Dispatch the `proposition-synthesize` subagent** with `--source-md <path>`, `--root <root>`,
   and `--model <model-id>`. The subagent runs the **read-only scaffold**
   (`science annotate synthesize <path> --root <root> --format json`), reads each proposition's
   `current` fields + verbatim `statements` (+ non-authoritative `relation_hints`), and emits an
   **untrusted** candidates file — exactly one patch per proposition it can factor.

3. **Surface the report** the subagent returns (which propositions it factored, which fields it
   set, what it left untouched).

4. **Hand to the curator.** The flow is: read-only scaffold → agent emits candidates → curator
   reviews → curator applies. After reviewing the candidates file, the curator — not this command,
   not the agent — runs:

   ```bash
   uv run science annotate synthesize <path> --apply --input <candidates-file>
   ```

   `--apply` is a **curator action**.

## Notes

- The `proposition-synthesize-v1` source version (`llm-synth:<model>:proposition-synthesize-v1`)
  means a prompt/vocab/schema change later (a `v2` bump) re-establishes the source identity stamped
  into `PropositionEntity.reasoning_source` on apply.
- By default apply fills only **unset** fields; an already-set field is replaced only when the
  patch lists it in its `override` set. `reasoning_source` is never overrideable.
- For bulk runs, dispatch one subagent per paper (they are independent; the deterministic command
  serializes its own writes).
