from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from rdflib import URIRef
from science_model.reasoning import EvidenceRole, EvidenceStance, EvidenceStrength, EvidenceType, IndependenceTag

from science_tool.annotation.io import markdown_for_sidecar
from science_tool.annotation.model import TextualBody
from science_tool.annotation.query import entity_relpath_for_sidecar, iter_sidecars
from science_tool.annotation.text_source_adapter import TextSourceAdapterError, resolve_adapter
from science_tool.graph.io import PROJECT_NS


@dataclass(frozen=True)
class LiteratureAssertion:
    proposition_ref: str
    paper_ref: str
    stance: str
    annotation_id: str
    sidecar: str


@dataclass(frozen=True)
class AssertionFault:
    sidecar: str
    annotation_id: str
    reason: str
    detail: str


class CrossPaperEvidenceError(Exception):
    def __init__(self, faults: tuple[AssertionFault, ...]) -> None:
        self.faults = faults
        super().__init__(str(self))

    def __str__(self) -> str:
        lines = ["cross-paper evidence faults:"]
        lines.extend(
            f"{idx}. {fault.sidecar}:{fault.annotation_id} {fault.reason}: {fault.detail}"
            for idx, fault in enumerate(self.faults, start=1)
        )
        return "\n".join(lines)


ACTIVE_STATUSES: frozenset[str] = frozenset({"open", "ack"})
DERIVED_STANCES: frozenset[str] = frozenset({"asserted", "negated", "hypothesized"})
KNOWN_STANCES: frozenset[str] = DERIVED_STANCES | {"open"}
_PROP_PREFIX = "proposition:"

LITERATURE_TYPE = EvidenceType.LITERATURE.value
INDEPENDENT = IndependenceTag.INDEPENDENT.value
STANCE_EMIT: dict[str, tuple[str, str, str]] = {
    "asserted": (
        EvidenceStance.SUPPORTS.value,
        EvidenceRole.PROXY_SUPPORT.value,
        EvidenceStrength.MODERATE.value,
    ),
    "negated": (
        EvidenceStance.DISPUTES.value,
        EvidenceRole.PROXY_SUPPORT.value,
        EvidenceStrength.MODERATE.value,
    ),
    "hypothesized": (
        EvidenceStance.SUPPORTS.value,
        EvidenceRole.BACKGROUND_CONSTRAINT.value,
        EvidenceStrength.WEAK.value,
    ),
}


def lit_assertion_uri(proposition_ref: str, paper_ref: str, stance: str) -> URIRef:
    key = f"{proposition_ref}\0{paper_ref}\0{stance}".encode()
    digest = hashlib.sha256(key).hexdigest()
    return URIRef(PROJECT_NS[f"evidence-line/lit-assertion/{digest}"])


def collapse_assertions(assertions: list[LiteratureAssertion]) -> list[LiteratureAssertion]:
    by_key: dict[tuple[str, str, str], LiteratureAssertion] = {}
    for assertion in sorted(
        assertions,
        key=lambda a: (a.proposition_ref, a.paper_ref, a.stance, a.annotation_id, a.sidecar),
    ):
        key = (assertion.proposition_ref, assertion.paper_ref, assertion.stance)
        if key not in by_key:
            by_key[key] = assertion

    return [by_key[key] for key in sorted(by_key)]


def _statement_stance(ann) -> str:
    for body in ann.bodies:
        if isinstance(body, TextualBody) and body.format == "application/json":
            try:
                data = json.loads(body.value)
            except json.JSONDecodeError:
                return ""
            if isinstance(data, dict):
                return str(data.get("stance", ""))
    return ""


def _resolve_paper_ref(sidecar_path: Path) -> str | None:
    try:
        md = markdown_for_sidecar(sidecar_path)
        return resolve_adapter(md).source_ref(md)
    except (ValueError, TextSourceAdapterError):
        return None


def scan_literature_assertions(
    project_root: Path,
    proposition_source_refs: dict[str, frozenset[str]],
) -> tuple[list[LiteratureAssertion], list[AssertionFault]]:
    assertions: list[LiteratureAssertion] = []
    faults: list[AssertionFault] = []

    for sidecar_path, sidecar in iter_sidecars(project_root):
        sidecar_ref = str(sidecar_path)
        paper_ref: str | None = None
        paper_resolved = False
        for ann in sidecar.annotations:
            if ann.annotation_type != "proposition":
                continue
            if ann.promoted_to is None:
                continue
            if str(ann.status) not in ACTIVE_STATUSES:
                continue
            if not ann.promoted_to.startswith(_PROP_PREFIX):
                faults.append(
                    AssertionFault(sidecar_ref, ann.id, "non-proposition-target", ann.promoted_to)
                )
                continue
            if ann.promoted_to not in proposition_source_refs:
                faults.append(
                    AssertionFault(
                        sidecar_ref,
                        ann.id,
                        "stale-proposition",
                        f"{ann.promoted_to} not found",
                    )
                )
                continue

            stance = _statement_stance(ann)
            if stance == "open":
                continue
            if stance not in DERIVED_STANCES:
                faults.append(
                    AssertionFault(sidecar_ref, ann.id, "invalid-stance", f"stance {stance!r}")
                )
                continue

            if not paper_resolved:
                paper_ref = _resolve_paper_ref(sidecar_path)
                paper_resolved = True
            if paper_ref is None:
                faults.append(
                    AssertionFault(sidecar_ref, ann.id, "adapter-unresolvable", "no text source adapter")
                )
                continue

            proposition_refs = proposition_source_refs[ann.promoted_to]
            ann_ref = f"annotation:{entity_relpath_for_sidecar(sidecar_path, project_root)}#{ann.id}"
            if paper_ref not in proposition_refs or ann_ref not in proposition_refs:
                faults.append(
                    AssertionFault(
                        sidecar_ref,
                        ann.id,
                        "ownership-mismatch",
                        f"{paper_ref} and/or {ann_ref} absent from {ann.promoted_to} source_refs",
                    )
                )
                continue

            assertions.append(
                LiteratureAssertion(ann.promoted_to, paper_ref, stance, ann.id, sidecar_ref)
            )

    return assertions, faults
