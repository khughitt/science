# Feedback Batch Q — the pre-registration provenance pair

**Status:** design, 2026-07-26. Successor to
[`2026-07-26-feedback-batch-p-design.md`](2026-07-26-feedback-batch-p-design.md).

Two downstream filings from natural-systems, both surfaced by the same slice of
work (`task:t891`, adopting numeric-claim bindings). They are independent bugs
with a shared cause: **`vehicles:` is the pre-registration's provenance field,
and nothing outside `check:prereg.vehicle-undeclared` knows that.**

- `fb-2026-07-26-018` — `numeric-anchor` cannot read `vehicles:`, so a
  pre-registration cannot declare entity-scope provenance at all.
- `fb-2026-07-26-019` — the vehicle check's frozen-status gate under-reports,
  so the documents that most need the obligation never get it.

## Owner decisions

- **D1 — `vehicles[].path` anchors, as a kind-scoped identity block.** It joins
  paper identity and interpretation `artifact`/`artifacts` in
  `entity_source_candidates`, rather than loosening `_as_refs` to accept
  mappings everywhere. The filing suggested the looser route; the narrower one
  is chosen because `vehicles` is the only mapping-shaped provenance field, and
  a generic mapping reader would silently legitimise `source_refs:` entries
  that are mappings — a shape nothing declares and no check validates.
- **D2 — only `path` is read.** A malformed entry contributes nothing. An
  unfreezable vehicle must not anchor a document's numbers.
- **D3 — a non-empty `amendments:` list is a freeze signal.** This is a
  sufficient condition, not a heuristic: amending presupposes having committed.
- **D4 — a `committed:` DATE is not a freeze signal.** Measured, not assumed:
  34 of 34 pre-registrations in the surveyed project carry one, including
  genuine drafts, because the template emits it unconditionally. Reading it
  would fire on the entire population.
- **D5 — no second rule for status hygiene.** The under-report is fixed by
  widening the predicate and by making the message state *why* the document
  counts as frozen. A separate `status-contradicts-record` warning was
  considered and dropped: it would make the author fix a bookkeeping field
  before learning about the missing vehicle, which is the defect that actually
  matters.

## Baseline (measured before any change)

Every pre-registration in natural-systems (34 files), by freeze signal:

| signal | count | note |
|---|---|---|
| `committed:` date present | **34 / 34** | discriminates nothing — D4 |
| `status` in {committed, amended} | 27 / 34 | what the check reads today |
| `status: active` | 7 / 34 | invisible to the check |
| non-empty `amendments:` | 5 / 34 | 3 of them also `status: active` |

Of the 7 `status: active` documents, one declares the data-gated gate section
and is legitimately vehicle-free. Three carry amendment records — including
`pre-registration:0026`, **the document `fb-2026-07-11-024` was written
about**, which by then had 12 amendments, a drawn null, and a discharging
interpretation, and had never once been asked for its vehicle.

### Why the population exists

`profiles/core.py` sets `default_status="active"` for this kind, while
`templates/pre-registration.md` displays `status: "committed"`. A tool-created
pre-registration therefore lands on `active` and stays there unless the author
edits it at sign-off, which `commands/pre-register.md` prescribes but nothing
enforces. That is the origin of all 7, and it is why `status` alone cannot be
the whole predicate. The deeper fix is the `status` axis split already
contemplated in `core.py`'s own comment ("`committed`/`amended` are a
COMMITMENT axis, not a document lifecycle … they belong on the lifecycle axis
once `status` is split"). Batch Q does **not** pre-empt that; D3 is chosen
precisely because it stays true either way.

## Per-filing verdicts

### fb-2026-07-26-018 — `vehicles:` is unreachable by numeric-anchor

**Confirmed, including the filer's claim that project config cannot work around
it.** `DEFAULT_PROVENANCE_FIELDS` is `["source_refs", "task_links", "input"]`,
and `_as_refs` accepts a string or a list of strings, so a `{path, sha256}`
mapping filters out. Reproduced against natural-systems'
`pre-registration:0026` with both field lists:

```
('source_refs','task_links','input')            -> []
('source_refs','task_links','input','vehicles') -> []
```

**Fix.** `entity_source_candidates` gains a pre-registration identity block
reading `_vehicle_paths(fm.get("vehicles"))`, gated on `kind` or the
`pre-registration:` id prefix, matching the existing paper and interpretation
blocks.

This makes `vehicles` the *strongest* entity anchor rather than merely another
one: the same entry is content-addressed, and `prereg.vehicle-hash-drift`
fails the build when the file drifts. `source_refs:` gets no such guarantee.

**What it costs.** Nothing is suppressed that was not already declared —
existence is still checked, so a fabricated vehicle path stays unresolved and
the claims stay flagged.

### fb-2026-07-26-019 — the frozen-status gate under-reports

**Confirmed**, and worse than filed: the filing says the gate misses documents
carrying `committed:` and amendments, which is true, but the measured cause is
the `default_status` / template disagreement above, so the gate misses a
standing 7/34 of the corpus rather than an occasional stray.

**Fix.** `_frozen_because(frontmatter) -> str | None` replaces the bare status
test and returns the reason, which the message now quotes ("is frozen (it
records 12 amendments, which presupposes a commitment) but declares no
`vehicles:`"). Severity is unchanged — still WARN, still ungated.

**What it costs.** Projects with amended-but-`active` pre-registrations that
declare no vehicle will see new warnings. That is the intended signal: in the
filing project it immediately surfaced that `pre-registration:0025` reads its
substrate as `glob(content/models/*.yml)` at run time and froze nothing at all
— the same defect class as `fb-2026-07-11-024`, live and previously invisible.

## Downstream effect (natural-systems, measured)

Both runs overlay this branch's code against the same working tree; the
baseline is `main` at `27c0d156`, **not** the project's pinned revision, so the
delta isolates Batch Q from Batches O and P.

`numeric-anchor`: **281 → 184**, and exactly two files move:

| file | before | after |
|---|---|---|
| `pre-registration:0026-fixed-margin-incidence-null-topology` | 90 | 0 |
| `pre-registration:0034-arxiv-paper-skeleton-external-suppression` | 7 | 0 |

Both declare vehicles that resolve (2 and 4 entries respectively; every path
checked to exist). `pre-registration:0025` holds at 50 — correctly, because it
has no vehicle to declare at all, which is what `task:t895` is about. No other
document changed, which is the result to want: the block reads one field on one
kind and cannot reach anything else.

`prereg.vehicle-undeclared`: **0 → 2** (`science validate` total 163 → 165; the
existing corpus produced no vehicle findings at `main`, since the two known
undeclared documents carry `accepted_validation` entries). The two new findings
are `pre-registration:0014` and `pre-registration:0025` — both `status: active`
with amendment records and no vehicle, i.e. exactly the population D3 was
written for, and neither is a false positive.

Note the counts move in opposite directions on purpose: `numeric-anchor` is
`info`-severity and does not appear in a plain `validate` run, so the +2 there
is the whole visible effect until `--strict`.

## Verification

- `tests/test_numeric_provenance.py` — 6 new tests: the anchor, existence
  checking, malformed-entry rejection, kind scoping, id-prefix fallback, and an
  end-to-end assertion that the declaration actually clears the findings.
- `tests/validate/test_checks_prereg_vehicles.py` — 6 new tests: the amendment
  predicate, singular/plural phrasing, `committed:`-alone staying silent, an
  empty `amendments:` list staying silent, a compliant amended document staying
  silent, and the data-gated escape surviving the widened predicate.
- Both sets were run against stashed source to confirm they fail without the
  fixes: 7 of the 12 fail, the other 5 being over-reach guards that must pass
  in both states.
