---
id: topic:evidence-grading-and-belief-ceilings
kind: topic
title: Evidence Grading and Belief Ceilings
status: active
related: []
source_refs: []
created: '2026-07-25'
updated: '2026-07-25'
---
# Evidence Grading and Belief Ceilings

## Summary

Several independent lines of practice have converged on the same architectural move:
letting a property of the *evidence's provenance* impose a **ceiling** on how much
certainty any amount of that evidence can produce — as opposed to a penalty that more
evidence can overcome. Clinical evidence grading does this with quality downgrade factors;
software supply-chain integrity does it with graduated trust levels for build artifacts.

The toolkit already implements one instance (a reproduction verdict capping belief,
mirroring the dataset-QA ceiling) without treating ceilings as a general mechanism.

> **Intake status.** Every reference below was surfaced by the 2026-07-25
> `explore-ideas` lens pass and is **unverified**: the identifiers are
> model-generated and no source has been read. Nothing here should be cited or
> treated as evidence until the intake task promotes it to a real paper entity.
> This topic is a scoped reading brief, not a synthesis.

## Key Concepts

**Ceiling, not penalty.** The load-bearing distinction. A penalty is additive and can be
outweighed by volume; a ceiling cannot. If simulation evidence is capped, a thousand
consistent simulation runs still do not reach the certainty of a replicated empirical
result. If it is merely penalized, they do.

**Indirectness.** A downgrade applied when the available evidence concerns a population,
setting, or outcome adjacent to the target rather than the target itself. This maps
directly onto simulation output as indirect evidence about real-world tool behaviour.

**Graduated trust tiers.** Rather than a binary admissible/inadmissible gate, a ladder of
provenance levels — no record, versioned script, declared and logged inputs, hermetic and
bit-reproducible — letting partially provenanced work contribute proportionally.

**Elapsed confirmation opportunity.** A third candidate axis: evidence that has not yet
existed long enough for confirmation at its claimed strength to be possible. Agent-speed
evidence and decade-old replicated evidence are not interchangeable even at equal quality.

**The provenance regress.** What is the provenance of the tool that records provenance?
Supply-chain framing makes this explicit where epistemic framing tends to hide it.

## Current State of Knowledge

The toolkit enforces graph-level reproducibility (source content-hashing, deterministic
serialisation, bundle integrity) and caps belief on dataset-QA and reproduction verdicts.
It does not have a general ceiling mechanism, and the three candidate axes above have
never been considered together. No source in this topic has been read.

## Controversies & Open Questions

- Are quality, hermeticity, and elapsed-validation genuinely independent axes, or does one
  dominate the others in practice?
- Does a ceiling compose with the ordinal/continuous boundary question, or does it belong
  strictly to one side of it?
- Is a graduated ladder actually better than a binary gate, or does it just relocate the
  arbitrary threshold into the tier boundaries?

## Relevance to This Project

Primary consumer is `question:0051`, which asks whether ceilings generalize into one
multi-axis mechanism. It extends `question:0016` (reproduction verdicts capping belief,
the existing single-axis instance) and `question:0013` (representing robustness and
reproducibility claims), and bears on `question:0018` and `question:0057`.

## Key References

- Guyatt et al. (2004) — founding GRADE paper; the downgrade-factor ceiling mechanism
  *(unverified intake)*
- Guyatt et al. (2011) — GRADE indirectness as a downgrade factor *(unverified intake)*
- Lamb & Zacchiroli (2022) — reproducible builds and the source-to-artifact integrity
  chain *(unverified intake)*
- Malka et al. (2025) — attainable hermetic reproducibility at scale *(unverified intake)*
