# Status-vocabulary certification

**Date:** 2026-07-12
**Status:** Phase 1 shipped; Phase 2 (migration) needs a greenlight; Phase 3 (ratchet) follows.
**Motivating incident:** `d2fc4d13` turned `science validate` from exit 0 to exit 1 in five projects.

## 1. What happened

`d2fc4d13` shipped `validate/checks/status_vocabulary.py`, which checks each entity's
`status` against its kind's `statuses` list in the Kind Descriptors. The check derives its
vocabulary from a single source (`_STATUS_VALUES` is a comprehension over
`_KIND_DESCRIPTORS`), so it introduced no second table. It was still wrong.

On the five projects that carry entities, it produced **472 ERROR-severity findings** and,
because `validate/cli.py` exits 1 on `result.errors` regardless of `--fail-on`, it broke
the validate gate everywhere:

| project | ERRORs |
|---|---|
| natural-systems | 198 |
| natural-systems--t664-verdict-field-inventory | 197 |
| seq-feats | 44 |
| 3d-attention-bias | 18 |
| protein-landscape | 15 |

The toolkit's own test suite was green throughout, because this repo holds no `entities/`
of its own. The check could only ever fail on a real project, and it was never run against
one.

## 2. The ruling: the vocabularies were the uncertified instrument

The tempting reading is "472 latent bugs, now visible." That reading is wrong for about
three quarters of them. The evidence is the **conformance signature** per kind:

| kind | valid / invalid | violations look like | verdict |
|---|---|---|---|
| question | 524 / 46 | `open`, `resolved` — synonyms of `active`, `answered` | descriptor is right |
| hypothesis | 43 / 5 | `active`, `retired` — synonyms + the fb-005 mess | descriptor is right |
| interpretation | 423 / 73 | `final` — synonym of the already-legal `complete` | descriptor is right |
| report | 40 / 136 | `complete` ×112 — **no terminal state existed** | descriptor is WRONG |
| plan | 89 / 148 | `draft` ×102 — **a plan could not be drafted** | descriptor is WRONG |
| pre-registration | 7 / 56 | `committed` ×40 — **the freeze point** | descriptor is WRONG |

High conformance + synonym-shaped violations ⇒ the projects drifted.
Low conformance + a **semantically missing state** ⇒ the descriptor is incomplete.

Two facts settle it beyond argument:

1. **`plan` and `interpretation` both declare `complete`; `report` does not.** These
   vocabularies were written ad hoc, per kind, never as a system. `report` losing its
   terminal state is an omission, not a policy.

2. **The toolkit itself prescribes an illegal status.** `templates/pre-registration.md`
   hardcodes `status: "committed"`, and `commands/pre-register.md:258` instructs
   *"`status: \"committed\"` once the user has signed off on the criteria."* Three surfaces
   say `committed`; only the descriptor called it illegal. A pre-registration vocabulary
   without `committed` does not describe a pre-registration — `committed` is the freeze
   point the entire pre-registration doctrine exists to name.

So: **a vocabulary that has never been reconciled against what the toolkit scaffolds and
what projects author is an uncertified instrument, and an uncertified instrument may not
fail anyone's build.** This is the estimator doctrine (`386326c1`) applied to itself —
certify before depending — violated by its own author one merge later.

## 3. The design defect: severity was graded on the wrong axis

The check graded ERROR-vs-WARN by `layout_version >= 3`, copying `entity_conformance`. Its
own docstring named the risk ("turning on a hard error would fail its whole corpus at
once") and then chose a gate that does not address it: **layout version says whether a
project's *layout* is modern, not whether a *kind's vocabulary* is trustworthy.** All five
projects are v3, so the gate graded nothing.

The axis that carries the meaning is **per-kind certification**: a kind's status check may
be ERROR only once that kind's vocabulary has been reconciled and its projects migrated.
Severity is a property of the *kind*, not of the project's layout version.

## 4. Phase 1 — shipped

Additive only, and **every addition justified by design, not by prevalence**. (A first cut
widened by file counts — `pre-registration: complete` because 10 files had it, `plan:
proposed` because 25 did. That is fitting the system to today's entities, and it was
reverted. See §8 for the axis model those words actually belong to.)

- **`report` += `draft`, `complete`.** `report` carries **no semantic axis** — its status
  *is* a document lifecycle, and a finished report must be able to say so. `plan` and
  `interpretation` both declare `complete`; `report` simply never got it. Added as the
  lifecycle words they are.
- **`plan` += `draft`.** Same argument: no semantic axis, and a plan is drafted before it is
  active. **`proposed` deliberately NOT minted** — it is drift toward `draft`, and coining a
  synonym would entrench the ad-hoc divergence this work exists to end. Those 25 stay WARN.
- **`pre-registration` += `committed`.** *Only* `committed`. Required by the contract in §2:
  both `templates/pre-registration.md` and `commands/pre-register.md:258` prescribe
  `status: "committed"`, so it must be **declared or struck from the template** — and
  striking the freeze point is not an option. `committed`/`amended` are a **commitment
  axis**, not a lifecycle. **`draft`/`complete` NOT added** despite 16 files: they are
  lifecycle words, they belong on the lifecycle axis once `status` is split, and adding them
  now would deepen the collapse the split exists to undo.
- `committed` classified **LIVE** in `_LIVE_STATUSES`. The existing
  `test_every_declared_status_still_classified` guard caught the new word and forced the
  live-or-hidden decision — the reconciliation gate working as designed.
- `status_vocabulary` severity → **WARN, unconditionally**; the `layout_version` axis is
  deleted.
- **Guard:** `test_template_status_is_declared_by_the_kind` no longer exempts
  `template_ready=True` kinds. The exemption ("their literal `status:` line is only
  illustration") is exactly what hid `pre-registration: committed`. `status: "{{status}}"`
  is a substitution slot and is still skipped; a template that *bypasses* the slot and
  hardcodes a word is making a claim about the vocabulary, and that claim is now checked.
  **This guard is the value-axis instance of the P0 contract in the unified design.**

**Result: the status check now contributes ZERO errors in every project.** No project file
was touched. The residual findings are WARN, and that warning *is* the migration signal.

### Correction to the blast-radius claim

The 472 findings spanned five projects, but only **natural-systems** and **seq-feats** were
exit-0 before the regression — both are exit 0 again. `3d-attention-bias` (unregistered
`meta` kind, fb-2026-07-10-021), `protein-landscape` (alias collision) and
`natural-systems--t664` (missing datapackage resources) were **already failing for unrelated
pre-existing defects**. The original "five projects broken" claim over-stated it, and the
record should say so.

## 5. Phase 2 — migration (needs a greenlight; touches project repos)

The 169 residual warnings are genuine project drift and should be migrated, not
accommodated. They are synonyms of statuses that already exist:

| kind | drift | migrate to |
|---|---|---|
| interpretation | `final` (71) | `complete` |
| question | `resolved` (26), `open` (18) | `answered`, `active` |
| plan | `ready-with-caveats`, `implemented`, `approved`, `design`, `agreed`, … | `active` / `complete` |
| report | `proposed`, `published`, `applied`, `generated`, `review` | `draft` / `active` / `complete` |
| hypothesis | `active` (3), `retired` (2) | `under-investigation`; `retired` → `disposition: closed` |
| inquiry | `sketch`, `planned`, `specified` | `active` |

`question: open` is not cosmetic. `DEBT_QUESTION_STATUSES` is
`{active, partially-answered, deferred}`, so all 18 `open` questions were **invisible to
open-question debt accounting** — the check found a real bug that had been silently
mis-counting attention.

`hypothesis: retired` is the fb-2026-07-11-005 defect, and its destination is the
`disposition: closed` axis shipped in `d2fc4d13`, not a status at all.

## 6. Phase 3 — the ratchet

Per kind, once (a) its vocabulary is reconciled against templates + commands + real usage,
and (b) its projects carry no drift, promote that kind's finding to ERROR. Track
certification on the kind, not the project.

## 7. Open follow-ons

- **20 core kinds declare no status vocabulary at all** — including `task`, `experiment`,
  `model`, `research-package`. `valid_statuses` raises `KeyError` for them and the check
  skips them silently, so the check is simultaneously too loud (33 kinds) and blind (20).
  Decide per kind whether the open set is deliberate or a gap.
- **`pre-registration.default_status` is `active`**, which is meaningless for a
  pre-registration — a CLI-created pre-reg gets a status the doctrine has no use for. It
  should probably be `draft`. Not changed here: it is a narrowing-shaped change and Phase 1
  is additive only.
- **`Entity` is `extra="ignore"`**, so `committed:` and `spec:` — both declared in
  `templates/pre-registration.md` — are silently dropped at `model_validate` and never
  reach the graph. There is no `PreRegistrationEntity`. This is the same defect class as
  `phase` (fb-2026-07-11-005) and `supersedes:` (fb-2026-07-11-017).
- **`validate/checks/prereg.py` is dead code**: it gates on `^type:\s`, but templates emit
  `kind:`, so its `committed:`/`spec:` warnings can never fire. A silent instrument.
- **The Estimator Certification Gate has no runtime code.** The template says so out loud:
  *"Nothing validates this section."*

The last three are the substrate the pre-registration integrity cluster
(fb-2026-07-11-024/025/026/027/028/033) will have to stand on.
