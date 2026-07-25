"""Load autonomous run records from `runs/` and emit them into graph/provenance.

The disk and rdflib half of the run record; the persisted shape itself lives in
`science_model.autonomous_runs`. Mirrors `graph/skill_loads.py`: a reified
non-entity record collected at load and emitted into the provenance layer.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError
from rdflib import Graph, URIRef
from rdflib import Literal as RDFLiteral
from rdflib.namespace import PROV, RDF, XSD
from science_model.autonomous_runs import RUN_ID_PREFIX, AutonomousRunRecord, RunRecordError
import yaml

from science_tool.graph.store import PROJECT_NS, SCI_NS

RUNS_DIRNAME = "runs"


def _reject_duplicate_and_merge_keys(node: yaml.Node, path: Path) -> None:
    """Refuse duplicate keys and YAML merge keys anywhere in the document.

    Recursive, unlike `skill_loads._reject_duplicate_keys`: a run record nests
    `policy_identity` and `budget`, and a duplicate inside either is exactly as
    silent as one at the top level.

    Operates on the NODE tree from `yaml.compose`, which builds no Python objects
    (so no `!!python/object` exposure) while still seeing what `safe_load` would
    collapse to last-wins.
    """
    if isinstance(node, yaml.MappingNode):
        seen: set[object] = set()
        for key_node, value_node in node.value:
            if key_node.tag == "tag:yaml.org,2002:merge":
                raise RunRecordError(f"{path}: YAML merge keys are not allowed in a run record")
            key = getattr(key_node, "value", None)
            if key in seen:
                raise RunRecordError(f"{path}: duplicate key {key!r} in run record")
            seen.add(key)
            _reject_duplicate_and_merge_keys(value_node, path)
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            _reject_duplicate_and_merge_keys(item, path)


def _parse_run_record_frontmatter(path: Path) -> dict[str, object]:
    """Parse one run record's frontmatter under attestation-grade rules.

    Deliberately NOT `science_model.frontmatter.parse_frontmatter`: that reaches
    `yaml.safe_load`, which silently collapses a duplicate `tier:` to last-wins
    BEFORE pydantic runs, so `extra="forbid"` never sees the conflict. An
    attestation that says two things must not be read as saying one.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RunRecordError(f"{path}: run record is unreadable: {exc}") from exc
    # Delimiters are whole LINES. `text.startswith("---")` would accept
    # `---not-a-delimiter` as an opening, and `text.split("---", 2)` would cut the block
    # at the first `---` appearing INSIDE a value (`model: claude---5` truncates to
    # `model: claude`). Both are silent corruptions of an attestation.
    lines = text.splitlines()
    # Two distinct failures share the first line: text that never attempted frontmatter
    # at all (no leading `---` of any kind) has no frontmatter to parse, whereas text
    # that attempted an opening delimiter but got the line wrong is malformed.
    if not lines or not lines[0].startswith("---"):
        raise RunRecordError(f"{path}: run record has no frontmatter")
    if lines[0].strip() != "---":
        raise RunRecordError(f"{path}: run record must open with a '---' delimiter line")
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing = index
            break
    else:
        raise RunRecordError(f"{path}: run record frontmatter is unterminated")
    block = "\n".join(lines[1:closing])
    try:
        node = yaml.compose(block, Loader=yaml.SafeLoader)
        if node is not None:
            _reject_duplicate_and_merge_keys(node, path)
        # Parse the SAME text again rather than constructing from the node tree: the two
        # passes must agree, and safe_load is the parser whose result pydantic validates.
        data = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        raise RunRecordError(f"{path}: run record frontmatter is not valid YAML: {exc}") from exc
    if not isinstance(data, dict) or not data:
        raise RunRecordError(f"{path}: run record has no frontmatter")
    return data


def load_run_records(project_root: Path) -> list[AutonomousRunRecord]:
    """Every finalized run record under `<project_root>/runs/`, in filename order.

    A genuinely absent directory yields no records -- most projects never run
    unattended. Everything else fails loudly, and the distinctions matter:

    * `runs` present but not a directory is a broken project, not an empty one.
    * A symlink -- on the directory or on any record -- is refused, so an
      out-of-tree file can never become an accepted attestation.
    * Any child that is not a flat regular `*.md` file raises, so a record filed
      one level down is never silently unscanned.

    No duplicate-id check: `slug == path.stem` plus filesystem uniqueness already
    makes duplicates impossible within one directory, so such a check would be a
    branch no test can reach.
    """
    runs_dir = project_root / RUNS_DIRNAME
    # Symlink first: a symlink to a missing target reports `exists() is False`, so an
    # existence check would return "no records" for a redirected runs directory.
    if runs_dir.is_symlink():
        raise RunRecordError(f"{runs_dir}: runs must not be a symlink")
    if not runs_dir.exists():
        return []
    if not runs_dir.is_dir():
        raise RunRecordError(f"{runs_dir}: runs exists but is not a directory")
    records: list[AutonomousRunRecord] = []
    for child in sorted(runs_dir.iterdir()):
        if child.is_symlink():
            raise RunRecordError(f"{child}: run records must not be symlinks")
        if not child.is_file() or child.suffix != ".md":
            raise RunRecordError(f"{child}: runs/ holds only flat *.md run records")
        frontmatter = _parse_run_record_frontmatter(child)
        try:
            record = AutonomousRunRecord.model_validate(frontmatter)
        except ValidationError as exc:
            raise RunRecordError(f"{child}: invalid run record: {exc}") from exc
        if record.slug != child.stem:
            raise RunRecordError(
                f"{child}: run id {record.id!r} disagrees with filename stem {child.stem!r}"
            )
        records.append(record)
    return records


def run_node_uri(run_id: str) -> URIRef:
    """The provenance node for a run id.

    Takes the id string, not the record, so the record pass and the entity-edge
    pass cannot drift into two spellings of one URI. The slug is already
    constrained to lowercase alphanumerics, hyphens, and the leading date, so no
    escaping is needed.
    """
    if not run_id.startswith(RUN_ID_PREFIX):
        raise RunRecordError(f"run id must start with {RUN_ID_PREFIX!r}, got {run_id!r}")
    return URIRef(PROJECT_NS[f"run/{run_id[len(RUN_ID_PREFIX):]}"])


def add_run_record_to_graph(record: AutonomousRunRecord, graph: Graph) -> None:
    """Write one run record's triples. Caller supplies the PROVENANCE graph.

    Dual-typed `sci:AutonomousRun` + `prov:Activity`: the PROV type makes the run
    legible to any PROV reader, and the Science type is what our own queries key on.
    """
    node = run_node_uri(record.id)
    graph.add((node, RDF.type, SCI_NS.AutonomousRun))
    graph.add((node, RDF.type, PROV.Activity))
    graph.add((node, SCI_NS.runId, RDFLiteral(record.id)))
    graph.add((node, SCI_NS.runAgent, RDFLiteral(record.agent)))
    graph.add((node, SCI_NS.runModel, RDFLiteral(record.model)))
    graph.add((node, SCI_NS.runTier, RDFLiteral(record.tier.value)))
    graph.add((node, SCI_NS.runBranch, RDFLiteral(record.branch)))
    graph.add((node, SCI_NS.runBaseCommit, RDFLiteral(record.base_commit)))
    graph.add((node, SCI_NS.runHeadCommit, RDFLiteral(record.head_commit)))
    graph.add((node, SCI_NS.runToolkitRevision, RDFLiteral(record.toolkit_revision)))
    graph.add((node, SCI_NS.runPolicyId, RDFLiteral(record.policy_identity.id)))
    graph.add((node, SCI_NS.runPolicyVersion, RDFLiteral(record.policy_identity.version)))
    graph.add((node, SCI_NS.runBasisDigest, RDFLiteral(record.basis_digest)))
    graph.add(
        (node, PROV.startedAtTime, RDFLiteral(record.started.isoformat(), datatype=XSD.dateTime))
    )
    graph.add(
        (node, PROV.endedAtTime, RDFLiteral(record.ended.isoformat(), datatype=XSD.dateTime))
    )
    graph.add((node, SCI_NS.runDisposition, RDFLiteral(record.disposition.value)))
    if record.triggered_by is not None:
        graph.add((node, SCI_NS.runTriggeredBy, RDFLiteral(record.triggered_by)))
    if record.budget.tokens is not None:
        graph.add((node, SCI_NS.runBudgetTokens, RDFLiteral(record.budget.tokens)))
    if record.budget.wall_clock_seconds is not None:
        graph.add(
            (node, SCI_NS.runBudgetWallClockSeconds, RDFLiteral(record.budget.wall_clock_seconds))
        )
