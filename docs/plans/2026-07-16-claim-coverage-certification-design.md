# Claim Coverage Certification — external witness for the silent-instrument ruling

**Date:** 2026-07-16
**Status:** Design — proposed. Not yet greenlit for implementation.
**Motivating incident:** fb-2026-07-16-005 — a `references.bib` entry shadowed a commons
canonical, and both `merge_entity` and `validate_overlay_pin` were skipped for every paper a
project also cited. ~245 overlays across the federation were inert. `science validate`
reported success in every one of them.

**Lineage:** successor to
[`2026-07-11-instrument-result-convergence-plan.md`](2026-07-11-instrument-result-convergence-plan.md)
(the silent-instrument ruling; `InstrumentResult`, the AST boundary guard) and
[`2026-07-12-status-vocabulary-certification-design.md`](2026-07-12-status-vocabulary-certification-design.md)
(certify before depending; the per-kind severity ratchet). This design does **not** replace
either. It supplies the half neither one covers.

---

## 1. The ruling

`InstrumentResult` and `ValidationVerdict` distinguish successful execution from known
non-execution, and make consumers fail closed on `unwired`. This successor makes execution
coverage **independently attestable**, by separating expected subjects, examined subjects, and
applicability, then reconciling them **outside the claim**.

The invariant:

> Every validation claim must expose its applicability denominator and its examined set. If
> applicability is expected but examined is empty, validation fails. Legitimate
> non-applicability must be **explicit** — never inferred from zero work.

And the constraint that gives the invariant its teeth:

> **The denominator may not be produced by the traversal it validates.**

---

## 2. What the shipped arc did, and the one thing it could not do

The convergence work was completed, not abandoned: `_DEFERRED_INSTRUMENTS` is drained to
`frozenset()`, the AST ratchet is live, and `unwired` is honoured across the consumer surface.
It also shipped genuine detectors — declared-versus-resolved topic references, graph-membership
checks, recorded manifest walk sets, missing-directory and catalog preconditions, and
fail-closed consumer handling.

**Every one of those detectors had to anticipate its own blind spot.**

That is the residual defect, and it is not a gap in execution — it is a gap in *authority*. If
an instrument's mental model of the world omits commons topology, nothing outside the
instrument ever challenges that model. The instrument runs. It is wired. It examines the
universe it believes in, finds nothing wrong there, and reports `passed` in complete good
faith.

So the two failure modes look identical from inside an instrument and are opposites from
outside it:

| | the instrument's own view | the truth |
|---|---|---|
| **unwired** | "I did not run" | it did not run |
| **unreachable** | "I ran and found nothing" | it examined the wrong universe |

`unwired` is a state an instrument declares **about itself**. It catches instruments that know
they were never wired up. It cannot catch `status_vocabulary` walking `<project_root>/entities`
against a commons store that has no `entities/` directory — that instrument is wired, executes
cleanly, and passes.

**The shipped arc made anticipated non-runs detectable. It did not make coverage independently
attestable.** An unwired instrument knows it did not run; an unreachable instrument believes it
did.

### 2.1 The doctrine has no runtime

`2026-07-12-status-vocabulary-certification-design.md` §2 rules that *"an uncertified
instrument may not fail anyone's build"*, applying the estimator doctrine (`386326c1`) —
**certify before depending**. The doctrine is sound and it is enforced entirely by hand: per
incident, in prose, in design documents, by human adjudication after the fact.

That same document's §7 names the consequence without flinching:

> **"The Estimator Certification Gate has no runtime code. The template says so out loud:
> *'Nothing validates this section.'*"**

The doctrine "certify before depending" is itself an uncertified instrument. This design gives
certification runtime code.

### 2.2 The population is larger than the motivating incident

Known instances of the class, at time of writing:

| instance | the instrument | why it cannot reach |
|---|---|---|
| fb-2026-07-16-005 (pin) | `validate_overlay_pin` | behind a skip a bib entry triggers |
| fb-2026-07-16-005 (merge) | `merge_entity` | same skip |
| fb-2026-07-12-007 | `status_vocabulary.py` | walks `<root>/entities`; commons has none |
| commons closure | `CommonsValidator` | never had a reference check at all |
| fb-2026-07-12-006 | the `REPLACE` guard | in a branch its comment calls "unreachable" |
| status design §7 | `validate/checks/prereg.py` | gates on `^type:\s`; templates emit `kind:` |
| status design §7 | Estimator Certification Gate | no runtime code exists |

Six-plus, spanning four subsystems, found by four unrelated investigations. This is a class
that regrows wherever attention lapses, which is the argument for structural enforcement over
discipline.

---

## 3. Inherited decisions

This design is founded on the arc and adopts its rulings rather than restating them.

1. **Vocabulary is inherited, not coined.** `instrument`, `unwired`, `certification`,
   `ratchet`, and *certify before depending* keep their established meanings. This document
   introduces exactly three new terms: **claim**, **census**, and **coverage ledger**.

2. **The AST boundary guard is preserved.** C adds a *complementary* claim-certification guard.
   It does not replace, subsume, or relax `test_instrument_boundary`. The two guards check
   different properties: the boundary guard checks that an instrument can *report* its
   non-execution; the certification guard checks that its *coverage* is attested.

3. **C generalizes three local precedents that already exist in this codebase.** The idea is
   not new here; its mandatory and general form is.
   - The **generated allowlist** in `test_instrument_boundary.py` is already an *external work
     order* — a population computed outside the thing it governs.
   - The **revision manifest's `walked` set** is already an *explicit coverage ledger*.
   - **Graph-membership checks** already separate *resolution syntax* from *actual presence*.

---

## 4. The claim contract

### 4.1 The claim is the registry unit

`CheckEntry` is `(section, order, fn)` — a bare function pointer with no declared domain, no
census, and no applicability. That structure does not merely permit the silent-instrument
class; it *is* the class, written as a dataclass.

One validator may make several claims, and each must account for itself separately. "Checked
369 entities" is a true statement that substantiates nothing about references, because
*references expected / examined / unresolved* is a different claim with a different
denominator. So the claim — not the function — is what the registry holds. A module may
register several.

```python
@dataclass(frozen=True)
class _ClaimBase:
    claim: ClaimId                  # "overlay.pin-current", "commons.references-resolve"
    section: str
    order: int
    census: CensusBinding
    applicability: ApplicabilityRule

@dataclass(frozen=True)
class TraversingClaim(_ClaimBase):
    fn: CheckFn                     # walks; self-reports via ctx.examined(...)

@dataclass(frozen=True)
class InjectedClaim(_ClaimBase):
    predicate: SubjectPredicate     # receives one subject; cannot traverse

ClaimEntry = TraversingClaim | InjectedClaim
```

The union is the discriminant: mode is carried by the *type*, not by a `mode` field paired with
a `CheckFn | SubjectPredicate`. An injected claim holds no callable that could walk, so the
invalid pairing is unconstructible rather than merely discouraged.

### 4.2 Census is a binding, not a provider name

A provider such as `parsed_references` contains several possible populations. Naming only the
provider gives claims an over-broad denominator or forces provider proliferation. The selector
is **typed and provider-owned** — never an arbitrary filtering callback, which would let the
claim redefine its own population and restore the circularity.

```python
@dataclass(frozen=True)
class CensusBinding:
    provider: CensusProviderId
    selector: CensusSelector        # typed, provider-owned; closed per provider
```

### 4.3 Providers are the closed axiom set

```python
class CensusProvider(Protocol):
    id: CensusProviderId
    def enumerate(self, binding: CensusBinding, ctx: CensusContext) -> frozenset[SubjectId]: ...

CENSUS_PROVIDERS: Final[Mapping[CensusProviderId, CensusProvider]]
```

Registration is **closed**: a new provider requires an architectural change and a provider
conformance suite. The axiom set stays small enough to audit by hand.

| provider | authority |
|---|---|
| `commons_inventory` | the commons store, per declared topology |
| `source_discovery` | generic source discovery — **never** a check-specific path |
| `graph_identities` | loaded-graph identities |
| `parsed_references` | references parsed from authoritative sources |
| `overlay_inventory` | overlay files + explicit project-scope applicability |

**`parsed_references` censuses from parsed sources, never from resolved edges.** Resolved edges
are survivorship bias: a dangling reference is definitionally not an edge, so a census built
from edges has already deleted the thing the claim is looking for. It would report full
coverage of every reference that was not broken.

Providers consume the topology declaration (see §9, the B prerequisite). They do not hardcode
paths.

### 4.4 SubjectId is the claim's unit of coverage

Subject granularity **is** the denominator. If a reference claim's subject is the target entity
ID, then three authored references to the same target collapse into one subject, the claim
reports full coverage, and two occurrences were never examined. The subject must be the
occurrence:

```python
ReferenceSubject = (source_path, field, position, target)   # scope-qualified
```

`SubjectId` must be scope-qualified wherever identities can coexist across scopes.

### 4.5 Applicability is independent of the census result

`NotApplicable` may **never** mean "the provider returned empty". That is the original defect
wearing a nicer name, and it restores the circularity this design exists to remove.

Applicability is a closed, typed rule evaluated from **independently sourced facts** — manifest
capability, validation profile, topology-declared scope. It carries a machine-readable code and
a human explanation.

```python
@dataclass(frozen=True)
class NotApplicable:
    code: ApplicabilityCode         # closed enum
    reason: str                     # human-facing

ApplicabilityRule = Callable[[ApplicabilityFacts], NotApplicable | None]
```

An empty expected set **with** an applicability ruling passes, and prints the reason. An empty
expected set **without** one is a certification failure.

---

## 5. The coverage ledger

Reconciliation is over **sets**, not counts — equal counts can cover the wrong records — and
the partition is **disjoint**, so a subject cannot occupy two states at once.

```text
expected   = passed ⊎ violated ⊎ unresolved ⊎ errored
examined   = passed ⊎ violated
attempted  = examined ⊎ errored
unexpected = reported_examined - expected
```

- `passed` — evaluated, no violation.
- `violated` — evaluated, the predicate found a violation. **A finding, not an execution failure.**
- `unresolved` — the expected subject could not be instantiated for evaluation. **Never reached.**
- `errored` — evaluation was attempted and crashed. **Reached, then blew up.**

`examined` and `reported_examined` are deliberately distinct and must not be conflated.
`examined` is a **partition of `expected`** — subjects the census predicted and the claim
evaluated. `reported_examined` is the **raw record of what the claim or runner says it looked
at**, which may include subjects outside `expected` entirely. Their difference is precisely
§5.1's signal; if the two were one set, that signal could not exist.

The `unresolved`/`errored` split is load-bearing: it is exactly the distinction between "never
reached" and "reached but failed", which is the distinction the whole design turns on. Findings
remain separate from execution failures throughout.

### 5.1 `unexpected` is a free completeness signal

`reported_examined - expected` must be empty. If a claim examines a subject the census did not
predict, **the census is under-enumerating** — and real traffic reports it, in production,
without anyone having written a test for that case. It does not prove completeness. It detects
a whole class of provider narrowness for free.

### 5.2 The honest limit of TRAVERSING mode

In `INJECTED` mode the runner owns `examined`: it is the call record, and the claim cannot
influence it.

In `TRAVERSING` mode the claim self-reports via `ctx.examined(claim, subject_id)`, because there
is no other way to know what a legacy traversal looked at. Inferring `examined` from findings is
survivorship bias again — a claim that examined 245 subjects and found nothing would report
zero.

Self-reported `examined` is **sound against under-reporting**: missed subjects remain
`unresolved` against the external census, and reconciliation fires. It is **not sound against
over-reporting**: a claim that asserts subjects it never inspected reconciles clean and lies.

That asymmetry is the entire reason `TRAVERSING` is a net and `INJECTED` is the destination.
`expected` stays external in **both** modes. That is the invariant that does not bend.

---

## 6. Certification

### 6.1 Four obligations, and only the pair means anything

A seeded-defect test proves **sensitivity**, not **census completeness**. A provider that walks
`<root>/entities`, with a defect seeded at `<root>/entities`, fires perfectly — while every real
commons record stays invisible. The instrument demonstrably *can* fail, and still sees nothing.
It fails correctly, inside a mistaken universe.

So the obligations are separate, and reachability × sensitivity is the only meaningful product:

| obligation | proves | method |
|---|---|---|
| **Provider reachability** | the census sees the real universe | sentinels across every supported topology → exact ID set |
| **Claim sensitivity** | the claim detects a violation | seed on an enumerated subject → fires, **names that subject** |
| **Framework accounting** | nothing falls out of the ledger | exact disjoint partition of `expected` |
| **Non-applicability** | empty is intentional | typed rule + reason code |

Sensitivity witnesses assert the **named subject**, not merely that something fired. A claim
that fires and blames the wrong subject passes a naive did-it-fire test and is nearly useless in
practice.

### 6.2 The certification key

```text
CertificationKey = claim × census binding / subject partition
```

Examples:

```text
hypothesis.status-vocabulary × kind=hypothesis
commons.references-resolve   × scope=commons, reference-class=entity-reference
```

A claim may be **certified for one partition and uncertified for another**. Severity may ratchet
only on certified partitions.

This preserves the status-vocabulary design's exact ruling — *"Track certification on the kind,
not the project"*; severity is a property of the kind — and generalizes its axis. "Per kind" is
the status-vocabulary *instance* of the key, not a competing doctrine.

### 6.3 The oracle must be structurally independent, not merely documented as such

This is the design's weakest joint and its most important one.

If the provider conformance suite derives sentinel placement from **the same topology
declaration the provider walks**, it is circular: a wrong topology makes both agree, and the
test passes green.

Therefore:

> **Provider conformance cases live in a test-only manifest using literal, hand-authored paths,
> deliberately duplicating the topology declaration.**

This looks like a DRY violation. **The duplication is the entire point.** An independent
restatement is what makes the suite an oracle instead of a tautology. `papers/<slug>.md` and
`datasets/<slug>/entity.md` are written out longhand, by a human, and reviewed as the axioms
they are. There is no escaping an authored oracle at the trust boundary — only making its
assumptions local, visible, and reviewable.

Requirements:

- The manifest module **must not import** the topology declaration, production writers, or any
  layout helper. **A structural test enforces the import restriction.** Discipline will not hold
  this; an import graph will.
- Each placement class gets **positive sentinels** and **plausible decoy paths that must not
  enumerate**. Over-enumeration is as much a provider defect as under-enumeration.
- Assertions compare **exact scoped `SubjectId` sets**.
- A topology change **adds a new versioned case**; old cases remain while that topology remains
  supported.
- A **generic parametrized test executes the cases**.

Small, local corpora — not one large golden federation fixture. A single fixture entangles the
oracles and makes omissions harder to notice; local ones keep each assumption reviewable on its
own.

The second grounding is B's, and it is why sharing the topology declaration with the **writer**
is load-bearing rather than tidy: a wrong topology cannot stay quiet if production writes land
at the declared paths. Tests and real writes, from two directions.

### 6.4 The certification guard

The keystone. It must **execute**, never trust a marker:

```python
def test_every_claim_is_certified() -> None:
    for entry in CLAIM_REGISTRY:
        assert entry.census.provider in CENSUS_PROVIDERS
        assert entry.applicability is not None
        assert sensitivity_cases_for(entry.claim)          # registered, executable cases
        if is_critical(entry.claim):                       # policy, not self-declared
            assert isinstance(entry, InjectedClaim)
```

**The guard checks registry coverage against registered executable cases.** It must not consult
a boolean like `topology_conformance_suite(provider_id)`, which can answer "yes" without
exercising anything — a certification meta-test that trusts a presence marker is itself a silent
instrument. Sensitivity witnesses and provider cases are **registered executable cases run by a
parametrized test**, and the guard asserts registry coverage over that same case registry.

You cannot register a claim without having witnessed it fire. An uncertified claim fails the
build. That inverts today's default, in which a claim that has never once fired is
indistinguishable from a healthy one.

**In `INJECTED` mode, storage placement belongs to the provider suite; claim witnesses cover
distinct *semantic* violation classes.** D supplies the end-to-end wiring witness (§8).

### 6.5 Criticality is policy, not self-declaration

Criticality may **not** live on `ClaimEntry`. A claim could escape the injection requirement by
setting `critical=False` on itself.

It lives in a **separate closed policy**. New claims default to **critical**. Existing claims
require a **justified exemption**. Since no new `TRAVERSING` claims are admitted anyway (§7),
this policy principally controls migration priority.

---

## 7. The sunset is a ratchet, not a date

Structural enforcement, following the precedent of `_DEFERRED_INSTRUMENTS`:

- **No new `TRAVERSING` claims after the migration baseline.**
- **A test locks the traversing set and permits only removals** — `TRAVERSING_CLAIMS ⊆ BASELINE`.
- **Correctness- or security-critical claims cannot be certified while traversing.**
- **C is not complete until D runs in `INJECTED` mode and catches `Persi2025`.**
- Existing multi-claim functions ultimately **split into claim-specific evaluators**; shared
  traversal survives as a **composed helper**, per the house rule (composition over inheritance).

This avoids a permanent transitional execution model without demanding a big-bang conversion of
all 96 check functions.

---

## 8. D — the acceptance slice

A framework exercised only by synthetic claims has not earned completion. D is a separately
bounded claim that **co-ships with C** as its vertical acceptance slice.

| | |
|---|---|
| claim | `commons.references-resolve` |
| census | `parsed_references`, scope=commons |
| subject | `(source_path, field, position, target)`, scope-qualified |
| mode | **`INJECTED`** — required; C is not complete otherwise |
| acceptance | flags `paper:Persi2025 → dataset:persi2025-myeloma` |

### 8.1 Resolution is by permitted authority scope — not by union

The naive rule `target ∈ commons_inventory ∪ graph_identities` **is wrong, and wrong in exactly
the way this design exists to prevent.**

`paper:Persi2025 → dataset:persi2025-myeloma` resolves in `mechanisms/evolution` — because a
project-local `status: candidate` entity happens to sit there — and fails in
`cancer-types/multiple-myeloma`. Under the union rule, D's verdict would **depend on which
project you ran it from**: green in one, red in the other, same reference. That is name capture,
verbatim, baked into the checker as its resolution rule. The instrument would have inherited the
defect it was built to find.

The rule is:

> **Resolve according to the target's permitted authority scope.**

- A **commons-owned** target must exist in `commons_inventory`.
- An **external** target must carry the explicit representation E supplies.
- A **project-local graph identity never legitimizes a commons reference.**

`graph_identities` is admissible as an authority only where it is an independent identity census
— never as a product of successful materialization or reference resolution.

Consequently **D flags both `Persi2025` and `wang2025-mri-gwas` today.** E later makes
`wang2025` valid by supplying the missing authority representation — not by the checker looking
the other way.

---

## 9. Sequence, scope, and non-goals

The wider arc, of which this document specifies **C**:

| | piece | status |
|---|---|---|
| **A** | Identity collapse — separate "who materialized this id" from "who owns this id" | coded and green in `.worktrees/commons-overlay-bib-shadow`; lands under the existing substrate design's owner/borrower/external-reference model (§B3). No separate design doc — it would restate that ruling. |
| **B** | Topology declaration — one declaration, shared by writer, reader, and census | **prerequisite for C's honesty.** Kills the `_TYPE_TO_DIR` / `OverlayAdapter` / `CommonsQuery` triplication. Needs its own spec. |
| **C** | **This document.** | proposed |
| **D** | Commons closure claim | co-ships with C as its acceptance slice (§8) |
| **E** | External pointers for un-promoted entities (`wang2025-mri-gwas`) | independent; different data-model concern. Priority is a function of how many un-promoted external targets exist — worth counting *before* speccing. |

**Ship order: A → B → C+D. E independent.** Spec order differs deliberately: C is written first,
while the invariant is sharp.

C declares the **topology interface it requires**; it does not design B's concrete
representation.

### Non-goals

- C does not design B's topology representation. Interface only.
- C does not migrate all 96 check functions. Ratchet, not big-bang.
- C does not fix E.
- C does not replace or relax the AST boundary guard.

---

## 10. Open questions

- **Provider count.** Five are named in §4.3. Whether `source_discovery` and `graph_identities`
  are genuinely distinct authorities, or one authority with two selectors, should be settled
  before the registry is closed — closing it around the wrong seam is expensive to undo.
- **Cross-provider reconciliation.** Where domains overlap semantically, disagreement should be
  fatal. It is **defence in depth, never proof of completeness**: two providers can share a blind
  spot, and records unique to one domain have no overlap to compare. Worth adding; not worth
  counting as an obligation.
- **`fb-2026-07-12-006` interaction.** C routes overlays through `merge_entity` that have been
  inert, so merge code that has received little real traffic will start receiving it. fb-006's
  `REPLACE` crash path is the known hazard; there may be others. Empirically clean for papers
  today (`meta` and `mechanisms/evolution` build green), and datasets are unaffected because bib
  mints only `paper:`/`book:` ids — but this is A's blast radius arriving, and the mm30 canary is
  the test that would catch it.
- **The 96-function net cost.** Every `TRAVERSING` claim needs `ctx.examined(...)` threading.
  Mechanical, but real, and it is the bulk of the migration labour.
