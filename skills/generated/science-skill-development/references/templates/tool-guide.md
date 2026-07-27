---
name: <subject>-<operation>
description: Use when operating <this tool/service> for <purpose>.
archetype: tool-guide
provenance: internal
---

# <Subject> <Operation>

Answers: how do I operate this specific product, library, service, or CLI?
Name the skill for the operation-on-subject it teaches, not for the tool
(e.g. `variant-calling`, not `gatk`) — doctrine forbids tool-based names.

## Setup & version assumptions

<Install, version pin, environment. If externally sourced, replace provenance with: sources: [<registered-id>].>

## Command / API surface

<The commands/API calls that matter.>

## Failure handling

<Common failures and their fixes.>

## Rate limits (where relevant)

<Throughput limits, backoff; "none" if not applicable.>

## Verification / smoke-test

<A representative operation to run, and how to confirm it worked.>

## Success test

Does the skill complete and verify a representative operation end-to-end, including recovery from a common failure?

## Companion Skills

- `../INDEX.md` — the skill index.
