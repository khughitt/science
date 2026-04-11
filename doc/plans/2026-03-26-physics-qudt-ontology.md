# Physics & QUDT Ontology Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two ontology entries (`physics` and `qudt`) to the science knowledge model, giving physics research projects standard vocabulary for entity types and relation predicates.

**Architecture:** Two independent ontology catalogs registered in the existing ontology infrastructure. `physics` is a hand-authored YAML catalog of physics entity types and relation predicates. `qudt` is extracted from the QUDT ontology's RDF data, providing quantity kinds as entity types. Both follow the same `OntologyCatalog` Pydantic schema used by biolink.

**Tech Stack:** Python, Pydantic, PyYAML, rdflib (for QUDT extraction), pytest

**Spec:** `doc/specs/2026-03-26-physics-qudt-ontology-design.md`
**Process doc:** `doc/process/adding-a-domain.md`
**Reference implementation:** biolink catalog at `science-model/src/science_model/ontologies/biolink/catalog.yaml`

---

## File Structure

### New files

| File | Responsibility |
|------|---------------|
| `science-model/src/science_model/ontologies/physics/catalog.yaml` | Hand-authored physics entity types and predicates |
| `science-model/src/science_model/ontologies/qudt/catalog.yaml` | Extracted QUDT quantity kind entity types and predicates |
| `scripts/extract_qudt_catalog.py` | One-time script to extract QUDT catalog from RDF source |

### Modified files

| File | Change |
|------|--------|
| `science-model/src/science_model/ontologies/registry.yaml` | Add `physics` and `qudt` entries |
| `science-model/tests/test_ontologies.py` | Add physics and qudt catalog loading tests |
| `science-tool/tests/test_ontology_suggest.py` | Add physics and qudt suggestion tests |
| `references/science-yaml-schema.md` | List new ontologies as available |
| `commands/create-project.md` | No change needed (uses `ontologies: []` — no hardcoded list) |

---

## Task 1: Author the `physics` catalog YAML

**Files:**
- Create: `science-model/src/science_model/ontologies/physics/catalog.yaml`

This is the largest single file. Hand-authored following the biolink catalog format at `science-model/src/science_model/ontologies/biolink/catalog.yaml`.

- [ ] **Step 1: Create the catalog file with header and entity types**

Create `science-model/src/science_model/ontologies/physics/catalog.yaml`:

```yaml
# Physics ontology — hand-authored, Wikidata-referenced
# Entity types and predicates for physical systems research
#
# Source taxonomy reference: Wikidata (https://www.wikidata.org/)
# Not a runtime dependency — used for authoring correctness only

ontology: physics
version: "1.0.0"
prefix: physics
prefix_uri: "https://science-tool.dev/ontologies/physics/"

entity_types:
  # --- Fundamental particles & matter ---
  - id: "physics:ElementaryParticle"
    name: elementary_particle
    description: "A particle with no known substructure"
    curie_prefixes: [PDGID, WD]
    recommended: true
  - id: "physics:Quark"
    name: quark
    description: "A fundamental fermion that interacts via the strong force"
    curie_prefixes: [PDGID, WD]
    recommended: true
  - id: "physics:Lepton"
    name: lepton
    description: "A fundamental fermion that does not interact via the strong force"
    curie_prefixes: [PDGID, WD]
    recommended: true
  - id: "physics:Boson"
    name: boson
    description: "A particle with integer spin that mediates fundamental forces"
    curie_prefixes: [PDGID, WD]
    recommended: true
  - id: "physics:Neutrino"
    name: neutrino
    description: "A nearly massless lepton that interacts only via the weak force"
    curie_prefixes: [PDGID, WD]
  - id: "physics:Hadron"
    name: hadron
    description: "A composite particle made of quarks bound by the strong force"
    curie_prefixes: [PDGID, WD]
    recommended: true
  - id: "physics:Baryon"
    name: baryon
    description: "A hadron composed of three quarks"
    curie_prefixes: [PDGID, WD]
  - id: "physics:Meson"
    name: meson
    description: "A hadron composed of a quark-antiquark pair"
    curie_prefixes: [PDGID, WD]
  - id: "physics:Atom"
    name: atom
    description: "A nucleus of protons and neutrons surrounded by an electron cloud"
    curie_prefixes: [WD]
    recommended: true
  - id: "physics:Isotope"
    name: isotope
    description: "An atom with a specific number of neutrons in its nucleus"
    curie_prefixes: [WD]
  - id: "physics:Ion"
    name: ion
    description: "An atom or molecule with a net electric charge"
    curie_prefixes: [WD]
  - id: "physics:Molecule"
    name: molecule
    description: "A group of atoms bonded together by electromagnetic forces"
    curie_prefixes: [WD]
    recommended: true
  - id: "physics:Plasma"
    name: plasma
    description: "An ionized gas exhibiting collective electromagnetic behavior"
    curie_prefixes: [WD]
  - id: "physics:Antiparticle"
    name: antiparticle
    description: "A particle with the same mass but opposite quantum numbers to its counterpart"
    curie_prefixes: [PDGID, WD]

  # --- Forces & interactions ---
  - id: "physics:FundamentalForce"
    name: fundamental_force
    description: "One of the four fundamental interactions of nature"
    curie_prefixes: [WD]
    recommended: true
  - id: "physics:GravitationalInteraction"
    name: gravitational_interaction
    description: "The attractive force between masses, mediated by spacetime curvature"
    curie_prefixes: [WD]
    recommended: true
  - id: "physics:ElectromagneticInteraction"
    name: electromagnetic_interaction
    description: "The force between electric charges, mediated by photons"
    curie_prefixes: [WD]
    recommended: true
  - id: "physics:StrongInteraction"
    name: strong_interaction
    description: "The force binding quarks into hadrons, mediated by gluons"
    curie_prefixes: [WD]
    recommended: true
  - id: "physics:WeakInteraction"
    name: weak_interaction
    description: "The force responsible for radioactive decay, mediated by W and Z bosons"
    curie_prefixes: [WD]
    recommended: true

  # --- Fields & waves ---
  - id: "physics:Field"
    name: field
    description: "A physical quantity with a value at every point in space and time"
    curie_prefixes: [WD]
    recommended: true
  - id: "physics:ElectricField"
    name: electric_field
    description: "A vector field produced by electric charges"
    curie_prefixes: [WD]
    recommended: true
  - id: "physics:MagneticField"
    name: magnetic_field
    description: "A vector field produced by moving charges and magnetic dipoles"
    curie_prefixes: [WD]
    recommended: true
  - id: "physics:GravitationalField"
    name: gravitational_field
    description: "A field describing the gravitational influence of mass-energy"
    curie_prefixes: [WD]
  - id: "physics:QuantumField"
    name: quantum_field
    description: "A field whose excitations are quantized as particles"
    curie_prefixes: [WD]
  - id: "physics:Wave"
    name: wave
    description: "A propagating disturbance that transfers energy through a medium or field"
    curie_prefixes: [WD]
    recommended: true
  - id: "physics:ElectromagneticWave"
    name: electromagnetic_wave
    description: "A wave of oscillating electric and magnetic fields propagating at the speed of light"
    curie_prefixes: [WD]
    recommended: true
  - id: "physics:GravitationalWave"
    name: gravitational_wave
    description: "A ripple in spacetime curvature propagating at the speed of light"
    curie_prefixes: [WD]

  # --- Classical mechanics & dynamics ---
  - id: "physics:PhysicalSystem"
    name: physical_system
    description: "A portion of the physical universe chosen for analysis"
    curie_prefixes: [WD]
    recommended: true
  - id: "physics:DynamicalSystem"
    name: dynamical_system
    description: "A system whose state evolves in time according to a deterministic or stochastic rule"
    curie_prefixes: [WD]
    recommended: true
  - id: "physics:RigidBody"
    name: rigid_body
    description: "An idealized solid body with no internal deformation"
    curie_prefixes: [WD]
  - id: "physics:Oscillator"
    name: oscillator
    description: "A system exhibiting periodic or quasi-periodic motion"
    curie_prefixes: [WD]
    recommended: true
  - id: "physics:Fluid"
    name: fluid
    description: "A substance that deforms continuously under applied shear stress"
    curie_prefixes: [WD]

  # --- Thermodynamics & statistical mechanics ---
  - id: "physics:ThermodynamicSystem"
    name: thermodynamic_system
    description: "A macroscopic system described by state variables such as temperature, pressure, and volume"
    curie_prefixes: [WD]
    recommended: true
  - id: "physics:Phase"
    name: phase
    description: "A distinct state of matter with uniform physical properties"
    curie_prefixes: [WD]
    recommended: true
  - id: "physics:PhaseTransition"
    name: phase_transition
    description: "A transformation between distinct phases of matter"
    curie_prefixes: [WD]
    recommended: true
  - id: "physics:StatisticalEnsemble"
    name: statistical_ensemble
    description: "A large collection of microstates used for statistical mechanical analysis"
    curie_prefixes: [WD]

  # --- Quantum mechanics ---
  - id: "physics:QuantumState"
    name: quantum_state
    description: "A state vector in a quantum-mechanical Hilbert space"
    curie_prefixes: [WD]
    recommended: true
  - id: "physics:QuantumSystem"
    name: quantum_system
    description: "A physical system governed by the laws of quantum mechanics"
    curie_prefixes: [WD]
    recommended: true
  - id: "physics:WaveFunction"
    name: wave_function
    description: "A complex-valued function whose squared modulus gives probability density"
    curie_prefixes: [WD]
  - id: "physics:Observable"
    name: observable
    description: "A measurable physical quantity represented by a Hermitian operator"
    curie_prefixes: [WD]
  - id: "physics:QuantumOperator"
    name: quantum_operator
    description: "A linear operator acting on quantum states in Hilbert space"
    curie_prefixes: [WD]

  # --- Spacetime & relativity ---
  - id: "physics:Spacetime"
    name: spacetime
    description: "The four-dimensional continuum unifying space and time"
    curie_prefixes: [WD]
  - id: "physics:ReferenceFrame"
    name: reference_frame
    description: "A coordinate system and clock used to describe motion and events"
    curie_prefixes: [WD]
    recommended: true
  - id: "physics:BlackHole"
    name: black_hole
    description: "A region of spacetime where gravity is too strong for anything to escape"
    curie_prefixes: [WD]

  # --- Materials & condensed matter ---
  - id: "physics:Crystal"
    name: crystal
    description: "A solid with atoms arranged in a highly ordered periodic lattice"
    curie_prefixes: [COD, WD]
    recommended: true
  - id: "physics:Lattice"
    name: lattice
    description: "A periodic arrangement of points in space defining crystal structure"
    curie_prefixes: [WD]
  - id: "physics:Semiconductor"
    name: semiconductor
    description: "A material with electrical conductivity between a conductor and an insulator"
    curie_prefixes: [WD]
  - id: "physics:Superconductor"
    name: superconductor
    description: "A material exhibiting zero electrical resistance below a critical temperature"
    curie_prefixes: [WD]

  # --- Astrophysical objects ---
  - id: "physics:Star"
    name: star
    description: "A luminous sphere of plasma held together by its own gravity"
    curie_prefixes: [WD]
    recommended: true
  - id: "physics:Galaxy"
    name: galaxy
    description: "A gravitationally bound system of stars, gas, dust, and dark matter"
    curie_prefixes: [WD]
  - id: "physics:Nebula"
    name: nebula
    description: "An interstellar cloud of gas and dust"
    curie_prefixes: [WD]

  # --- Cross-cutting ---
  - id: "physics:Symmetry"
    name: symmetry
    description: "An invariance of a physical system under a transformation"
    curie_prefixes: [WD]
    recommended: true
  - id: "physics:ConservationLaw"
    name: conservation_law
    description: "A law stating that a physical quantity remains constant in an isolated system"
    curie_prefixes: [WD]
    recommended: true
  - id: "physics:PhysicalConstant"
    name: physical_constant
    description: "A universal constant of nature with a fixed numerical value"
    curie_prefixes: [CODATA, WD]
    recommended: true
  - id: "physics:Equation"
    name: equation
    description: "A mathematical relationship between physical quantities"
    curie_prefixes: [WD]
    recommended: true
  - id: "physics:Measurement"
    name: measurement
    description: "A quantitative observation of a physical property"
    curie_prefixes: [WD]
    recommended: true
  - id: "physics:PhysicalProperty"
    name: physical_property
    description: "A measurable characteristic of a physical system"
    curie_prefixes: [WD]
    recommended: true

predicates:
  # --- Composition & structure ---
  - id: "physics:composed_of"
    name: composed_of
    description: "Entity is made of components"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"
    recommended: true
  - id: "physics:has_component"
    name: has_component
    description: "Entity contains a component (inverse of composed_of)"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"
    recommended: true
  - id: "physics:is_form_of"
    name: is_form_of
    description: "Entity is a variant or form of another"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"

  # --- Interactions & forces ---
  - id: "physics:interacts_via"
    name: interacts_via
    description: "Two entities interact through a force or field"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"
    recommended: true
  - id: "physics:mediates"
    name: mediates
    description: "A particle mediates a fundamental force"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"
    recommended: true
  - id: "physics:exerts_force_on"
    name: exerts_force_on
    description: "One entity exerts a force on another"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"
    recommended: true
  - id: "physics:couples_to"
    name: couples_to
    description: "A field or particle couples to another entity"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"
    recommended: true

  # --- Transformations & processes ---
  - id: "physics:decays_to"
    name: decays_to
    description: "A particle or state decays into others"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"
    recommended: true
  - id: "physics:transforms_to"
    name: transforms_to
    description: "A system or state changes into another"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"
    recommended: true
  - id: "physics:emits"
    name: emits
    description: "A source produces a particle or radiation"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"
    recommended: true
  - id: "physics:absorbs"
    name: absorbs
    description: "An entity absorbs a particle or radiation"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"
    recommended: true
  - id: "physics:scatters_from"
    name: scatters_from
    description: "An entity scatters from another in a collision or interaction"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"

  # --- Spatial & structural ---
  - id: "physics:part_of"
    name: part_of
    description: "Structural containment of one entity within another"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"
    recommended: true
  - id: "physics:located_in"
    name: located_in
    description: "Spatial relationship between entities"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"
    recommended: true
  - id: "physics:confined_to"
    name: confined_to
    description: "An entity is quantum or spatially confined to another"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"

  # --- Properties & description ---
  - id: "physics:has_property"
    name: has_property
    description: "Entity has a measurable physical property"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"
    recommended: true
  - id: "physics:has_symmetry"
    name: has_symmetry
    description: "System exhibits a symmetry"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"
    recommended: true
  - id: "physics:obeys"
    name: obeys
    description: "System obeys a conservation law or equation"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"
    recommended: true
  - id: "physics:described_by"
    name: described_by
    description: "Entity is described by an equation or theoretical model"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"
    recommended: true
  - id: "physics:violates"
    name: violates
    description: "System violates a symmetry or conservation law"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"

  # --- Causal & temporal ---
  - id: "physics:causes"
    name: causes
    description: "Causal relationship between physical events or processes"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"
    recommended: true
  - id: "physics:precedes"
    name: precedes
    description: "Temporal ordering of physical events"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"
  - id: "physics:induces"
    name: induces
    description: "One phenomenon induces another"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"
    recommended: true

  # --- Classification & equivalence ---
  - id: "physics:is_antiparticle_of"
    name: is_antiparticle_of
    description: "Particle-antiparticle pairing"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"
    recommended: true
  - id: "physics:is_dual_to"
    name: is_dual_to
    description: "Duality relationship between physical descriptions"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"
  - id: "physics:is_subtype_of"
    name: is_subtype_of
    description: "Classification hierarchy between entity types"
    domain: "physics:NamedThing"
    range: "physics:NamedThing"
    recommended: true
```

- [ ] **Step 2: Verify the YAML is valid**

Run: `uv run --frozen python -c "import yaml; from pathlib import Path; data = yaml.safe_load(Path('science-model/src/science_model/ontologies/physics/catalog.yaml').read_text()); print(f'Entity types: {len(data[\"entity_types\"])}, Predicates: {len(data[\"predicates\"])}')""`

Expected: `Entity types: 57, Predicates: 26`

- [ ] **Step 3: Commit**

```bash
git add science-model/src/science_model/ontologies/physics/catalog.yaml
git commit -m "feat(ontology): add hand-authored physics catalog

53 entity types (30 recommended) and 26 predicates (20 recommended)
covering fundamental particles, forces, fields, classical mechanics,
thermodynamics, quantum mechanics, relativity, condensed matter,
and astrophysics."
```

---

## Task 2: Write the QUDT extraction script

**Files:**
- Create: `scripts/extract_qudt_catalog.py`

Follows the pattern of `scripts/extract_biolink_catalog.py`. Uses `rdflib` to parse QUDT's Turtle source and extract quantity kinds.

- [ ] **Step 1: Create the extraction script**

Create `scripts/extract_qudt_catalog.py`:

```python
#!/usr/bin/env python3
"""Extract a QUDT quantity-kind catalog from the QUDT RDF source.

One-time dev script — not part of the runtime package.
Produces science-model/src/science_model/ontologies/qudt/catalog.yaml.

Usage:
    uv run scripts/extract_qudt_catalog.py

Requires: rdflib (already a science-tool dependency).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

QUDT_VERSION = "3.2.0"
QUDT_QUANTITYKIND_URL = (
    "https://raw.githubusercontent.com/qudt/qudt-public-repo/"
    f"v{QUDT_VERSION}/vocab/quantitykinds/VOCAB_QUDT-QUANTITY-KINDS-ALL-v{QUDT_VERSION}.ttl"
)
OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent
    / "science-model/src/science_model/ontologies/qudt/catalog.yaml"
)

# Recommended quantity kinds — commonly used in physics and general science.
RECOMMENDED_QUANTITY_KINDS: set[str] = {
    "Mass",
    "Length",
    "Time",
    "Velocity",
    "Acceleration",
    "Force",
    "Momentum",
    "AngularMomentum",
    "Energy",
    "Power",
    "Pressure",
    "Density",
    "ElectricCharge",
    "ElectricCurrent",
    "Voltage",
    "Temperature",
    "Entropy",
    "Frequency",
    "Wavelength",
    "Area",
    "Volume",
    "Angle",
    "Work",
    "Action",
    "MagneticFluxDensity",
    "Luminosity",
    "Viscosity",
    "Impedance",
    "Conductance",
    "Permittivity",
}

# Quantity kinds to exclude — too specialized or redundant for a general catalog.
EXCLUDE_PATTERNS: list[str] = [
    r"^Deprecated",
    r"_IMPERIAL$",
    r"_SI$",
    r"_CGS$",
    r"_Planck$",
]


def _camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case."""
    result: list[str] = []
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            if name[i - 1].islower() or (i + 1 < len(name) and name[i + 1].islower()):
                result.append("_")
        result.append(char.lower())
    return "".join(result)


def _is_excluded(local_name: str) -> bool:
    """Check if a quantity kind should be excluded."""
    return any(re.search(p, local_name) for p in EXCLUDE_PATTERNS)


def main() -> None:
    try:
        from rdflib import Graph, Namespace, URIRef
        from rdflib.namespace import RDF, RDFS, SKOS
    except ImportError:
        print("Error: rdflib not available. Install with: uv add --dev rdflib", file=sys.stderr)
        sys.exit(1)

    QUDT = Namespace("http://qudt.org/schema/qudt/")
    QK = Namespace("http://qudt.org/vocab/quantitykind/")

    print(f"Loading QUDT v{QUDT_VERSION} quantity kinds from {QUDT_QUANTITYKIND_URL} ...")
    g = Graph()
    g.parse(QUDT_QUANTITYKIND_URL, format="turtle")

    entity_types: list[dict[str, object]] = []

    for subject in sorted(set(g.subjects(RDF.type, QUDT.QuantityKind)), key=str):
        if not isinstance(subject, URIRef):
            continue

        local_name = str(subject).replace(str(QK), "")
        if not local_name or "/" in local_name:
            continue
        if _is_excluded(local_name):
            continue

        name = _camel_to_snake(local_name)

        # Get label and description
        labels = list(g.objects(subject, RDFS.label))
        label = str(labels[0]) if labels else local_name
        descriptions = list(g.objects(subject, SKOS.definition)) or list(
            g.objects(subject, RDFS.comment)
        )
        description = str(descriptions[0]).strip()[:200] if descriptions else f"The {label} quantity kind."

        recommended = local_name in RECOMMENDED_QUANTITY_KINDS

        entry: dict[str, object] = {
            "id": f"qudt:{local_name}",
            "name": name,
            "description": description,
            "curie_prefixes": ["QUDT"],
        }
        if recommended:
            entry["recommended"] = True

        entity_types.append(entry)

    # Predicates — minimal measurement-oriented set (hand-authored, not extracted)
    predicates: list[dict[str, object]] = [
        {
            "id": "qudt:hasQuantityKind",
            "name": "has_quantity_kind",
            "description": "A measurement has a quantity kind",
            "domain": "qudt:NamedThing",
            "range": "qudt:NamedThing",
            "recommended": True,
        },
        {
            "id": "qudt:hasDimension",
            "name": "has_dimension",
            "description": "A quantity kind has a dimension vector",
            "domain": "qudt:NamedThing",
            "range": "qudt:NamedThing",
            "recommended": True,
        },
        {
            "id": "qudt:hasUnit",
            "name": "has_unit",
            "description": "A measurement is expressed in a unit",
            "domain": "qudt:NamedThing",
            "range": "qudt:NamedThing",
            "recommended": True,
        },
        {
            "id": "qudt:measuredIn",
            "name": "measured_in",
            "description": "An entity is measured in a quantity kind",
            "domain": "qudt:NamedThing",
            "range": "qudt:NamedThing",
            "recommended": True,
        },
        {
            "id": "qudt:proportionalTo",
            "name": "proportional_to",
            "description": "Two quantities are proportional",
            "domain": "qudt:NamedThing",
            "range": "qudt:NamedThing",
        },
        {
            "id": "qudt:inverselyProportionalTo",
            "name": "inversely_proportional_to",
            "description": "Two quantities are inversely proportional",
            "domain": "qudt:NamedThing",
            "range": "qudt:NamedThing",
        },
    ]

    catalog: dict[str, object] = {
        "ontology": "qudt",
        "version": QUDT_VERSION,
        "prefix": "qudt",
        "prefix_uri": "https://qudt.org/vocab/quantitykind/",
        "entity_types": entity_types,
        "predicates": predicates,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        yaml.dump(catalog, default_flow_style=False, sort_keys=False, allow_unicode=True, width=120),
        encoding="utf-8",
    )

    n_recommended = sum(1 for et in entity_types if et.get("recommended"))
    print(f"Wrote {OUTPUT_PATH}")
    print(f"  Quantity kinds: {len(entity_types)} total, {n_recommended} recommended")
    print(f"  Predicates:     {len(predicates)} total, {sum(1 for p in predicates if p.get('recommended'))} recommended")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the extraction script**

Run: `uv run scripts/extract_qudt_catalog.py`

Expected output: Script prints count of extracted quantity kinds (expect 60-200 depending on QUDT filtering) and the output file path. Verify the counts look reasonable — if far too many (>300), tighten `EXCLUDE_PATTERNS`; if too few (<30), loosen them.

- [ ] **Step 3: Inspect the output**

Run: `uv run --frozen python -c "import yaml; from pathlib import Path; data = yaml.safe_load(Path('science-model/src/science_model/ontologies/qudt/catalog.yaml').read_text()); print(f'Quantity kinds: {len(data[\"entity_types\"])}, Predicates: {len(data[\"predicates\"])}')""`

Verify:
- Entity type count is in range 60-200
- Predicate count is 6
- Spot-check: `mass`, `energy`, `temperature`, `velocity` are present

- [ ] **Step 4: Commit**

```bash
git add scripts/extract_qudt_catalog.py science-model/src/science_model/ontologies/qudt/catalog.yaml
git commit -m "feat(ontology): add QUDT extraction script and quantity-kind catalog

Extracts quantity kinds from QUDT v3.2.0 RDF source.
Includes 6 measurement-oriented predicates (4 recommended)."
```

---

## Task 3: Register both ontologies

**Files:**
- Modify: `science-model/src/science_model/ontologies/registry.yaml`

- [ ] **Step 1: Add physics and qudt entries to the registry**

Edit `science-model/src/science_model/ontologies/registry.yaml`. After the existing biolink entry, add:

```yaml
  - name: physics
    version: "1.0.0"
    source_url: "project-authored"
    description: "Physics — entity types and predicates for physical systems research"
    catalog_path: "physics/catalog.yaml"
  - name: qudt
    version: "3.2.0"
    source_url: "https://github.com/qudt/qudt-public-repo"
    description: "QUDT — quantity kinds for measurement and quantitative modeling"
    catalog_path: "qudt/catalog.yaml"
```

- [ ] **Step 2: Verify loading works**

Run: `uv run --frozen python -c "from science_model.ontologies import load_catalogs_for_names; cats = load_catalogs_for_names(['physics', 'qudt']); print(f'physics: {len(cats[0].entity_types)} types, {len(cats[0].predicates)} preds'); print(f'qudt: {len(cats[1].entity_types)} types, {len(cats[1].predicates)} preds')"`

Expected: Both catalogs load successfully, physics shows 57 entity types and 26 predicates, qudt shows its extracted counts.

- [ ] **Step 3: Commit**

```bash
git add science-model/src/science_model/ontologies/registry.yaml
git commit -m "feat(ontology): register physics and qudt in ontology registry"
```

---

## Task 4: Add physics catalog tests

**Files:**
- Modify: `science-model/tests/test_ontologies.py`

- [ ] **Step 1: Write the failing tests**

Add the following tests to `science-model/tests/test_ontologies.py`:

```python
# --- Physics catalog tests ---


def test_load_physics_catalog_parses_entity_types() -> None:
    catalogs = load_catalogs_for_names(["physics"])
    assert len(catalogs) == 1
    catalog = catalogs[0]
    assert catalog.ontology == "physics"
    type_names = {et.name for et in catalog.entity_types}
    assert "elementary_particle" in type_names
    assert "quantum_state" in type_names
    assert "physical_system" in type_names

    particle = next(et for et in catalog.entity_types if et.name == "elementary_particle")
    assert "PDGID" in particle.curie_prefixes
    assert "WD" in particle.curie_prefixes
    assert particle.recommended is True


def test_load_physics_catalog_parses_predicates() -> None:
    catalogs = load_catalogs_for_names(["physics"])
    catalog = catalogs[0]
    pred_names = {p.name for p in catalog.predicates}
    assert "decays_to" in pred_names
    assert "mediates" in pred_names
    assert "composed_of" in pred_names

    decays = next(p for p in catalog.predicates if p.name == "decays_to")
    assert decays.recommended is True


def test_physics_recommended_counts() -> None:
    catalogs = load_catalogs_for_names(["physics"])
    catalog = catalogs[0]
    rec_types = sum(1 for et in catalog.entity_types if et.recommended)
    rec_preds = sum(1 for p in catalog.predicates if p.recommended)
    assert 20 <= rec_types <= 50, f"Expected 20-50 recommended types, got {rec_types}"
    assert 15 <= rec_preds <= 35, f"Expected 15-35 recommended predicates, got {rec_preds}"


def test_physics_curie_prefixes() -> None:
    catalogs = load_catalogs_for_names(["physics"])
    catalog = catalogs[0]
    quark = next(et for et in catalog.entity_types if et.name == "quark")
    assert len(quark.curie_prefixes) > 0
    crystal = next(et for et in catalog.entity_types if et.name == "crystal")
    assert "COD" in crystal.curie_prefixes
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `uv run --frozen pytest science-model/tests/test_ontologies.py -v -k physics`

Expected: All 4 physics tests pass.

- [ ] **Step 3: Commit**

```bash
git add science-model/tests/test_ontologies.py
git commit -m "test(ontology): add physics catalog loading tests"
```

---

## Task 5: Add QUDT catalog tests

**Files:**
- Modify: `science-model/tests/test_ontologies.py`

- [ ] **Step 1: Write the failing tests**

Add the following tests to `science-model/tests/test_ontologies.py`:

```python
# --- QUDT catalog tests ---


def test_load_qudt_catalog_parses_entity_types() -> None:
    catalogs = load_catalogs_for_names(["qudt"])
    assert len(catalogs) == 1
    catalog = catalogs[0]
    assert catalog.ontology == "qudt"
    type_names = {et.name for et in catalog.entity_types}
    assert "mass" in type_names
    assert "energy" in type_names
    assert "temperature" in type_names
    assert "velocity" in type_names


def test_load_qudt_catalog_parses_predicates() -> None:
    catalogs = load_catalogs_for_names(["qudt"])
    catalog = catalogs[0]
    pred_names = {p.name for p in catalog.predicates}
    assert "has_quantity_kind" in pred_names
    assert "has_unit" in pred_names
    assert "measured_in" in pred_names
    assert len(catalog.predicates) == 6


def test_qudt_recommended_counts() -> None:
    catalogs = load_catalogs_for_names(["qudt"])
    catalog = catalogs[0]
    rec_types = sum(1 for et in catalog.entity_types if et.recommended)
    assert 20 <= rec_types <= 50, f"Expected 20-50 recommended quantity kinds, got {rec_types}"
    rec_preds = sum(1 for p in catalog.predicates if p.recommended)
    assert rec_preds == 4


def test_qudt_curie_prefixes() -> None:
    catalogs = load_catalogs_for_names(["qudt"])
    catalog = catalogs[0]
    mass = next(et for et in catalog.entity_types if et.name == "mass")
    assert "QUDT" in mass.curie_prefixes
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `uv run --frozen pytest science-model/tests/test_ontologies.py -v -k qudt`

Expected: All 4 QUDT tests pass.

- [ ] **Step 3: Commit**

```bash
git add science-model/tests/test_ontologies.py
git commit -m "test(ontology): add QUDT catalog loading tests"
```

---

## Task 6: Update the `available_ontology_names` test

**Files:**
- Modify: `science-model/tests/test_ontologies.py`

- [ ] **Step 1: Update the existing test**

The existing `test_available_ontology_names` asserts `names == ["biolink"]`. Update it:

```python
def test_available_ontology_names() -> None:
    names = available_ontology_names()
    assert "biolink" in names
    assert "physics" in names
    assert "qudt" in names
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run --frozen pytest science-model/tests/test_ontologies.py::test_available_ontology_names -v`

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add science-model/tests/test_ontologies.py
git commit -m "test(ontology): update available_ontology_names for physics and qudt"
```

---

## Task 7: Add physics suggestion tests

**Files:**
- Modify: `science-tool/tests/test_ontology_suggest.py`

- [ ] **Step 1: Write the suggestion tests**

Add the following tests to `science-tool/tests/test_ontology_suggest.py`:

```python
# --- Physics suggestion tests ---


def test_suggests_physics_for_curie_prefixes() -> None:
    entities = [_entity(ontology_terms=["PDGID:11"])]
    suggestions = suggest_ontologies(entities, declared_ontologies=[])
    physics_suggestions = [s for s in suggestions if s.ontology_name == "physics"]
    assert len(physics_suggestions) == 1
    assert physics_suggestions[0].entity_count >= 1
    assert "CURIE" in physics_suggestions[0].reason


def test_suggests_physics_for_kind_match() -> None:
    entities = [_entity(kind="elementary_particle")]
    suggestions = suggest_ontologies(entities, declared_ontologies=[])
    physics_suggestions = [s for s in suggestions if s.ontology_name == "physics"]
    assert len(physics_suggestions) == 1
    assert "kind" in physics_suggestions[0].reason


def test_no_physics_suggestions_when_declared() -> None:
    entities = [_entity(kind="elementary_particle", ontology_terms=["PDGID:11"])]
    suggestions = suggest_ontologies(entities, declared_ontologies=["physics"])
    physics_suggestions = [s for s in suggestions if s.ontology_name == "physics"]
    assert physics_suggestions == []


# --- QUDT suggestion tests ---


def test_suggests_qudt_for_curie_prefixes() -> None:
    entities = [_entity(ontology_terms=["QUDT:Mass"])]
    suggestions = suggest_ontologies(entities, declared_ontologies=[])
    qudt_suggestions = [s for s in suggestions if s.ontology_name == "qudt"]
    assert len(qudt_suggestions) == 1
    assert "CURIE" in qudt_suggestions[0].reason


def test_suggests_qudt_for_kind_match() -> None:
    entities = [_entity(kind="mass")]
    suggestions = suggest_ontologies(entities, declared_ontologies=[])
    qudt_suggestions = [s for s in suggestions if s.ontology_name == "qudt"]
    assert len(qudt_suggestions) == 1
    assert "kind" in qudt_suggestions[0].reason


def test_no_qudt_suggestions_when_declared() -> None:
    entities = [_entity(kind="mass", ontology_terms=["QUDT:Mass"])]
    suggestions = suggest_ontologies(entities, declared_ontologies=["qudt"])
    qudt_suggestions = [s for s in suggestions if s.ontology_name == "qudt"]
    assert qudt_suggestions == []
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `uv run --frozen pytest science-tool/tests/test_ontology_suggest.py -v`

Expected: All tests pass (existing biolink tests + 6 new tests).

- [ ] **Step 3: Commit**

```bash
git add science-tool/tests/test_ontology_suggest.py
git commit -m "test(ontology): add physics and qudt suggestion tests"
```

---

## Task 8: Update documentation

**Files:**
- Modify: `references/science-yaml-schema.md`

- [ ] **Step 1: Update the ontologies field comment**

In `references/science-yaml-schema.md`, update line 28:

```yaml
  - "string"                   # Ontology name, e.g. biolink, physics, qudt. Validated against built-in registry.
```

- [ ] **Step 2: Update the research project example**

In `references/science-yaml-schema.md`, after the existing biolink example at line 77, the `ontologies` line stays as-is (it already shows `[biolink]`). No change needed — the example is illustrative, not exhaustive.

- [ ] **Step 3: Commit**

```bash
git add references/science-yaml-schema.md
git commit -m "docs: list physics and qudt as available ontologies in schema reference"
```

---

## Task 9: Run full test suite

- [ ] **Step 1: Run all tests**

Run: `uv run --frozen pytest`

Expected: All tests pass with no regressions.

- [ ] **Step 2: Run type checks and linting**

Run: `uv run --frozen ruff check .`
Run: `uv run --frozen pyright`

Expected: No errors.

- [ ] **Step 3: Final commit if any fixes were needed**

If any linting or type issues surfaced, fix and commit:

```bash
git add -A
git commit -m "fix: address linting/type issues from physics+qudt integration"
```
