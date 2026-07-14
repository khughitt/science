"""The D4 supersedable gate — DERIVED from the profile, and executed.

```
supersedable  ⇔  the schema admits `superseded`
              ⇔  the lineage RelationKind admits the kind as an endpoint
              ⇔  the supersession operation handles the kind
```

D5 shipped a `superseded` terminal for `hypothesis` with **none** of the three legs wired: the mixin
did not admit `relations:` (so the canonical edge could not be authored at all),
`sci:supersedes` did not admit `hypothesis` as an endpoint (so authoring it anyway raised
`ValueError` in `materialize`), and `mark_superseded` wrote `status` and no lineage.

**A gate stated in prose is not a gate.** The design named three half-wired kinds
(`topic`/`decision`/`theme`). Executed against `CORE_PROFILE`, the real number is **twelve** — which
is the only reason we know it, and the reason the population below is *derived* rather than listed.

The schema leg is tested in `test_mixin_hypothesis.py`, beside the mixin it constrains.
"""

from __future__ import annotations

from science_model.profiles.core import CORE_PROFILE
from science_model.profiles.schema import RelationKind
from science_model.relations import relation_allows_kinds  # THE authoritative admission rule

# The twelve kinds that declare `superseded` while `sci:supersedes` forbids them as endpoints.
# A SHRINKING allowlist of known-broken kinds -- never a list of what to CHECK. The population is
# DERIVED below; freezing the scope instead of the debt is how a guard grows a hole by construction.
_KNOWN_HALF_WIRED: frozenset[str] = frozenset(
    {
        "decision",
        "inquiry",
        "mechanism",
        "method",
        "observation",
        "plan",
        "pre-registration",
        "proposition",
        "synthesis",
        "theme",
        "topic",
        "workflow-step",
    }
)


def _supersedes() -> RelationKind:
    return next(r for r in CORE_PROFILE.relation_kinds if r.name == "supersedes")


def test_every_supersedable_kind_can_author_the_CANONICAL_edge() -> None:
    # THE GATE. A kind that declares `superseded` and is auto-stamped by `mark_superseded`, but is
    # forbidden as a `sci:supersedes` endpoint, raises ValueError in materialize the moment anyone
    # authors the edge the tool itself calls canonical. The vocabulary and the relation model
    # disagree, and until this test existed, nothing noticed.
    #
    # ASK THE AUTHORITATIVE HELPER. `source_kinds & target_kinds` is NOT the admission rule: when
    # `allowed_kind_pairs` is present it is the authoritative non-Cartesian allow-list and the flat
    # lists do not decide (`relations.py:19-33`). For `supersedes` the two happen to agree on
    # self-pairs today -- which is how a check on the wrong field would have kept agreeing right up
    # until it didn't.
    declares = {k.name for k in CORE_PROFILE.entity_kinds if "superseded" in (k.statuses or [])}
    relation = _supersedes()
    broken = {k for k in declares if not relation_allows_kinds(relation, k, k)}

    # SUBSET, not equality. This is a ratchet on a DEBT: it must forbid the set GROWING while
    # letting any of the twelve be repaired. Exact equality would make fixing `topic` -- a strict
    # improvement -- fail the suite, which is a guard that punishes the thing it exists to cause.
    assert broken <= _KNOWN_HALF_WIRED, f"newly half-wired: {sorted(broken - _KNOWN_HALF_WIRED)}"


def test_hypothesis_is_a_supersedes_ENDPOINT() -> None:
    # DIRECT, and non-vacuous: `hypothesis` is absent from `declares` until Task 8 adds `superseded`
    # to its descriptor, so the derived gate above CANNOT SEE IT YET. Without this test, leg 2 would
    # be certified by a gate that skips it -- and Task 8 would then add the status to a kind whose
    # relation model still forbids the edge, taking the half-wired count from twelve to thirteen.
    assert relation_allows_kinds(_supersedes(), "hypothesis", "hypothesis")
