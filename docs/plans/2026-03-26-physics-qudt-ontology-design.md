# Physics & QUDT Ontology Design Spec

**Date:** 2026-03-26
**Status:** Draft
**Process:** Follows `doc/process/adding-a-domain.md`
**Reference implementation:** biolink (`docs/specs/2026-03-24-ontology-consumption-design.md`)

## Problem

The science knowledge model currently supports biology via the biolink ontology
but has no vocabulary for physics research. Projects studying physical systems,
dynamical processes, particles, fields, or measurements have no standard entity
types or relation predicates to use — everything falls into the local profile
as untyped entities.

## Goal

Add two new ontology entries to the science knowledge model:

1. **`physics`** — entity types and relation predicates for physics research,
   covering the major sub-domains at a useful general-purpose level.
2. **`qudt`** — quantity kinds (mass, energy, temperature, ...) extracted from
   the QUDT ontology, providing domain-agnostic measurement vocabulary usable
   by physics, chemistry, engineering, and any other quantitative domain.

## Multiscale Strategy

These ontologies provide a **broad foundation** for physics, not exhaustive
depth in any sub-domain. Representative terms from major sub-domains (mechanics,
electromagnetism, quantum mechanics, particle physics, thermodynamics,
astrophysics, condensed matter) are included to be immediately useful.

Future sub-domain extensions (e.g., `hep`, `condensed_matter`, `astro`) can
add deeper vocabulary. How sub-domain extension works will be designed
separately.

---

## 1. Architecture

Two independent ontology registry entries:

| Entry | Source | Authoring method | Purpose |
|-------|--------|-----------------|---------|
| `physics` | Hand-authored, Wikidata-referenced | Direct YAML | Entity types and predicates for physics research |
| `qudt` | QUDT ontology v3.2 | Extraction script | Quantity kinds as entity types; measurement predicates |

Projects declare what they need in `science.yaml`:

```yaml
# Physics research project
ontologies: [physics]

# Physics project with explicit measurement modeling
ontologies: [physics, qudt]

# Interdisciplinary project
ontologies: [biolink, physics]

# Any project needing formal quantity modeling
ontologies: [qudt]
```

`qudt` is intentionally domain-agnostic. `physics` is domain-specific.

### The boundary rule (unchanged)

Same as biolink: ontologies provide **vocabulary** (entity types and relation
predicates). Users provide **knowledge** (assertions, claims, evidence). No
external knowledge graph assertions are auto-imported.

---

## 2. `physics` Ontology

### 2.1 Catalog format

Hand-authored YAML following the standard `OntologyCatalog` schema:

```yaml
ontology: physics
version: "1.0.0"
prefix: "physics"
prefix_uri: "https://science-tool.dev/ontologies/physics/"
entity_types: [...]
predicates: [...]
```

No extraction script — the catalog YAML is authored directly. Wikidata's
class taxonomy is used as the reference for entity type definitions and
correctness, but is not a runtime dependency.

### 2.2 Registry entry

```yaml
- name: physics
  version: "1.0.0"
  source_url: "project-authored"
  description: "Physics — entity types and predicates for physical systems research"
  catalog_path: "physics/catalog.yaml"
```

### 2.3 Entity types

57 entity types. 34 marked `recommended: true`.

**Fundamental particles & matter**

| Entity type | Description | CURIE prefixes | Recommended |
|---|---|---|---|
| `elementary_particle` | A particle with no known substructure | `PDGID`, `WD` | yes |
| `quark` | A fundamental fermion that interacts via the strong force | `PDGID`, `WD` | yes |
| `lepton` | A fundamental fermion that does not interact via the strong force | `PDGID`, `WD` | yes |
| `boson` | A particle with integer spin | `PDGID`, `WD` | yes |
| `neutrino` | A nearly massless lepton | `PDGID`, `WD` | no |
| `hadron` | A composite particle made of quarks | `PDGID`, `WD` | yes |
| `baryon` | A hadron composed of three quarks | `PDGID`, `WD` | no |
| `meson` | A hadron composed of a quark-antiquark pair | `PDGID`, `WD` | no |
| `atom` | A nucleus surrounded by an electron cloud | `WD` | yes |
| `isotope` | An atom with a specific number of neutrons | `WD` | no |
| `ion` | An atom or molecule with net electric charge | `WD` | no |
| `molecule` | A group of atoms bonded together | `WD` | yes |
| `plasma` | An ionized gas with collective behavior | `WD` | no |
| `antiparticle` | A particle with opposite quantum numbers to its counterpart | `PDGID`, `WD` | no |

**Forces & interactions**

| Entity type | Description | CURIE prefixes | Recommended |
|---|---|---|---|
| `fundamental_force` | One of the four fundamental interactions | `WD` | yes |
| `gravitational_interaction` | The force between masses | `WD` | yes |
| `electromagnetic_interaction` | The force between electric charges | `WD` | yes |
| `strong_interaction` | The force binding quarks into hadrons | `WD` | yes |
| `weak_interaction` | The force responsible for radioactive decay | `WD` | yes |

**Fields & waves**

| Entity type | Description | CURIE prefixes | Recommended |
|---|---|---|---|
| `field` | A physical quantity with a value at every point in space | `WD` | yes |
| `electric_field` | A field produced by electric charges | `WD` | yes |
| `magnetic_field` | A field produced by moving charges and magnets | `WD` | yes |
| `gravitational_field` | A field produced by mass-energy | `WD` | no |
| `quantum_field` | A field whose excitations are particles | `WD` | no |
| `wave` | A propagating disturbance in a medium or field | `WD` | yes |
| `electromagnetic_wave` | A wave of oscillating electric and magnetic fields | `WD` | yes |
| `gravitational_wave` | A ripple in spacetime curvature | `WD` | no |

**Classical mechanics & dynamics**

| Entity type | Description | CURIE prefixes | Recommended |
|---|---|---|---|
| `physical_system` | A portion of the physical universe chosen for analysis | `WD` | yes |
| `dynamical_system` | A system whose state evolves in time according to a rule | `WD` | yes |
| `rigid_body` | An idealized solid body with no deformation | `WD` | no |
| `oscillator` | A system exhibiting periodic motion | `WD` | yes |
| `fluid` | A substance that flows under applied shear stress | `WD` | no |

**Thermodynamics & statistical mechanics**

| Entity type | Description | CURIE prefixes | Recommended |
|---|---|---|---|
| `thermodynamic_system` | A system described by macroscopic state variables | `WD` | yes |
| `phase` | A distinct state of matter (solid, liquid, gas, etc.) | `WD` | yes |
| `phase_transition` | A transformation between phases | `WD` | yes |
| `statistical_ensemble` | A collection of microstates for statistical analysis | `WD` | no |

**Quantum mechanics**

| Entity type | Description | CURIE prefixes | Recommended |
|---|---|---|---|
| `quantum_state` | A state in a quantum-mechanical Hilbert space | `WD` | yes |
| `quantum_system` | A physical system governed by quantum mechanics | `WD` | yes |
| `wave_function` | A complex-valued function describing a quantum state | `WD` | no |
| `observable` | A measurable physical quantity in quantum mechanics | `WD` | no |
| `quantum_operator` | A mathematical operator acting on quantum states | `WD` | no |

**Spacetime & relativity**

| Entity type | Description | CURIE prefixes | Recommended |
|---|---|---|---|
| `spacetime` | The four-dimensional continuum of space and time | `WD` | no |
| `reference_frame` | A coordinate system for describing motion and events | `WD` | yes |
| `black_hole` | A region of spacetime with gravity too strong for light to escape | `WD` | no |

**Materials & condensed matter**

| Entity type | Description | CURIE prefixes | Recommended |
|---|---|---|---|
| `crystal` | A solid with atoms arranged in a periodic lattice | `COD`, `WD` | yes |
| `lattice` | A periodic arrangement of points in space | `WD` | no |
| `semiconductor` | A material with conductivity between a conductor and insulator | `WD` | no |
| `superconductor` | A material with zero electrical resistance below a critical temperature | `WD` | no |

**Astrophysical objects**

| Entity type | Description | CURIE prefixes | Recommended |
|---|---|---|---|
| `star` | A luminous body of plasma held together by gravity | `WD` | yes |
| `galaxy` | A gravitationally bound system of stars and matter | `WD` | no |
| `nebula` | A cloud of gas and dust in interstellar space | `WD` | no |

**Cross-cutting**

| Entity type | Description | CURIE prefixes | Recommended |
|---|---|---|---|
| `symmetry` | An invariance of a system under a transformation | `WD` | yes |
| `conservation_law` | A law stating that a quantity is conserved | `WD` | yes |
| `physical_constant` | A universal constant of nature | `CODATA`, `WD` | yes |
| `equation` | A mathematical relationship between physical quantities | `WD` | yes |
| `measurement` | A quantitative observation of a physical property | `WD` | yes |
| `physical_property` | A measurable characteristic of a physical system | `WD` | yes |

**Totals:** 57 entity types, 34 recommended.

### 2.4 Relation predicates

~25-30 predicates. ~20 marked `recommended: true`.

**Composition & structure**

| Predicate | Description | Domain | Range | Recommended |
|---|---|---|---|---|
| `composed_of` | Entity is made of components | `physics:NamedThing` | `physics:NamedThing` | yes |
| `has_component` | Entity contains a component (inverse of composed_of) | `physics:NamedThing` | `physics:NamedThing` | yes |
| `is_form_of` | Entity is a variant of another | `physics:NamedThing` | `physics:NamedThing` | no |

**Interactions & forces**

| Predicate | Description | Domain | Range | Recommended |
|---|---|---|---|---|
| `interacts_via` | Two entities interact through a force or field | `physics:NamedThing` | `physics:NamedThing` | yes |
| `mediates` | A particle mediates a fundamental force | `physics:NamedThing` | `physics:NamedThing` | yes |
| `exerts_force_on` | One entity exerts a force on another | `physics:NamedThing` | `physics:NamedThing` | yes |
| `couples_to` | A field or particle couples to another entity | `physics:NamedThing` | `physics:NamedThing` | yes |

**Transformations & processes**

| Predicate | Description | Domain | Range | Recommended |
|---|---|---|---|---|
| `decays_to` | A particle or state decays into others | `physics:NamedThing` | `physics:NamedThing` | yes |
| `transforms_to` | A system or state changes into another | `physics:NamedThing` | `physics:NamedThing` | yes |
| `emits` | A source produces a particle or radiation | `physics:NamedThing` | `physics:NamedThing` | yes |
| `absorbs` | An entity absorbs a particle or radiation | `physics:NamedThing` | `physics:NamedThing` | yes |
| `scatters_from` | An entity scatters from another | `physics:NamedThing` | `physics:NamedThing` | no |

**Spatial & structural**

| Predicate | Description | Domain | Range | Recommended |
|---|---|---|---|---|
| `part_of` | Structural containment | `physics:NamedThing` | `physics:NamedThing` | yes |
| `located_in` | Spatial relationship | `physics:NamedThing` | `physics:NamedThing` | yes |
| `confined_to` | Quantum or spatial confinement | `physics:NamedThing` | `physics:NamedThing` | no |

**Properties & description**

| Predicate | Description | Domain | Range | Recommended |
|---|---|---|---|---|
| `has_property` | Entity has a physical property | `physics:NamedThing` | `physics:NamedThing` | yes |
| `has_symmetry` | System exhibits a symmetry | `physics:NamedThing` | `physics:NamedThing` | yes |
| `obeys` | System obeys a law or equation | `physics:NamedThing` | `physics:NamedThing` | yes |
| `described_by` | Entity is described by an equation or model | `physics:NamedThing` | `physics:NamedThing` | yes |
| `violates` | System violates a symmetry or law | `physics:NamedThing` | `physics:NamedThing` | no |

**Causal & temporal**

| Predicate | Description | Domain | Range | Recommended |
|---|---|---|---|---|
| `causes` | Causal relationship between physical events | `physics:NamedThing` | `physics:NamedThing` | yes |
| `precedes` | Temporal ordering of events | `physics:NamedThing` | `physics:NamedThing` | no |
| `induces` | One phenomenon induces another | `physics:NamedThing` | `physics:NamedThing` | yes |

**Classification & equivalence**

| Predicate | Description | Domain | Range | Recommended |
|---|---|---|---|---|
| `is_antiparticle_of` | Particle-antiparticle pairing | `physics:NamedThing` | `physics:NamedThing` | yes |
| `is_dual_to` | Duality relationship (wave-particle, electric-magnetic) | `physics:NamedThing` | `physics:NamedThing` | no |
| `is_subtype_of` | Classification hierarchy | `physics:NamedThing` | `physics:NamedThing` | yes |

**Totals:** 26 predicates, 20 recommended.

---

## 3. `qudt` Ontology

### 3.1 Scope

Entity types are **quantity kinds** — what is being measured (mass, energy,
temperature), not units of measure (kilogram, joule, kelvin). Users create
entities like `type: mass`, not `type: kilogram`.

The full QUDT ontology has ~1,200 quantity kinds. The catalog filters to those
commonly encountered in physics and general science.

### 3.2 Registry entry

```yaml
- name: qudt
  version: "3.2.0"
  source_url: "https://github.com/qudt/qudt-public-repo"
  description: "QUDT — quantity kinds for measurement and quantitative modeling"
  catalog_path: "qudt/catalog.yaml"
```

### 3.3 Catalog format

```yaml
ontology: qudt
version: "3.2.0"
prefix: "qudt"
prefix_uri: "https://qudt.org/vocab/quantitykind/"
entity_types: [...]
predicates: [...]
```

### 3.4 Entity types (quantity kinds)

~60-80 total after filtering. ~25-35 marked `recommended: true`.

**Mechanics**

| Entity type | Description | CURIE prefixes | Recommended |
|---|---|---|---|
| `mass` | Quantity of matter | `QUDT` | yes |
| `length` | Spatial extent in one dimension | `QUDT` | yes |
| `time` | Duration of an event | `QUDT` | yes |
| `velocity` | Rate of change of position | `QUDT` | yes |
| `acceleration` | Rate of change of velocity | `QUDT` | yes |
| `force` | Interaction that changes motion | `QUDT` | yes |
| `momentum` | Product of mass and velocity | `QUDT` | yes |
| `angular_momentum` | Rotational analog of momentum | `QUDT` | yes |
| `torque` | Rotational analog of force | `QUDT` | no |
| `energy` | Capacity to do work | `QUDT` | yes |
| `power` | Rate of energy transfer | `QUDT` | yes |
| `pressure` | Force per unit area | `QUDT` | yes |
| `density` | Mass per unit volume | `QUDT` | yes |

**Electromagnetism**

| Entity type | Description | CURIE prefixes | Recommended |
|---|---|---|---|
| `electric_charge` | Quantity of electricity | `QUDT` | yes |
| `electric_current` | Flow of electric charge | `QUDT` | yes |
| `voltage` | Electric potential difference | `QUDT` | yes |
| `resistance` | Opposition to electric current | `QUDT` | no |
| `capacitance` | Ability to store electric charge | `QUDT` | no |
| `magnetic_flux` | Total magnetic field through a surface | `QUDT` | no |
| `magnetic_field_strength` | Intensity of a magnetic field | `QUDT` | no |
| `inductance` | Tendency to oppose changes in current | `QUDT` | no |

**Thermodynamics**

| Entity type | Description | CURIE prefixes | Recommended |
|---|---|---|---|
| `temperature` | Measure of thermal energy | `QUDT` | yes |
| `entropy` | Measure of disorder | `QUDT` | yes |
| `heat_capacity` | Energy required to raise temperature | `QUDT` | no |
| `thermal_conductivity` | Ability to conduct heat | `QUDT` | no |

**Quantum / atomic / wave**

| Entity type | Description | CURIE prefixes | Recommended |
|---|---|---|---|
| `frequency` | Number of oscillations per unit time | `QUDT` | yes |
| `wavelength` | Spatial period of a wave | `QUDT` | yes |
| `spin_quantum_number` | Intrinsic angular momentum quantum number | `QUDT` | no |
| `luminosity` | Total energy radiated per unit time | `QUDT` | no |

**General**

| Entity type | Description | CURIE prefixes | Recommended |
|---|---|---|---|
| `area` | Extent of a two-dimensional surface | `QUDT` | yes |
| `volume` | Extent of a three-dimensional region | `QUDT` | yes |
| `angle` | Figure formed by two rays | `QUDT` | yes |
| `dimensionless_ratio` | A ratio with no physical dimension | `QUDT` | no |

The above is a representative sample (~33 shown). The full catalog will
include ~60-80 quantity kinds extracted from QUDT, filtered to those relevant
to physics, chemistry, and engineering.

### 3.5 Predicates

Minimal set — 6 predicates, 4 recommended:

| Predicate | Description | Domain | Range | Recommended |
|---|---|---|---|---|
| `has_quantity_kind` | Measurement has a quantity kind | `qudt:NamedThing` | `qudt:NamedThing` | yes |
| `has_dimension` | Quantity kind has a dimension vector | `qudt:NamedThing` | `qudt:NamedThing` | yes |
| `has_unit` | Measurement is expressed in a unit | `qudt:NamedThing` | `qudt:NamedThing` | yes |
| `measured_in` | Entity is measured in a quantity kind | `qudt:NamedThing` | `qudt:NamedThing` | yes |
| `proportional_to` | Two quantities are proportional | `qudt:NamedThing` | `qudt:NamedThing` | no |
| `inversely_proportional_to` | Two quantities are inversely proportional | `qudt:NamedThing` | `qudt:NamedThing` | no |

### 3.6 Extraction script

`scripts/extract_qudt_catalog.py` — unlike the hand-authored physics catalog,
QUDT has clean OWL/Turtle source data suitable for programmatic extraction.

The script:
1. Fetches QUDT quantity kind vocabulary from the GitHub release (Turtle)
2. Parses with `rdflib`
3. Filters to relevant quantity kinds (skip highly specialized entries)
4. Extracts labels, descriptions, CURIE mappings
5. Applies recommended flags from a curated set (defined as a constant)
6. Outputs `catalog.yaml`

---

## 4. CURIE Prefixes

### `physics` prefixes

| Prefix | System | Scope |
|--------|--------|-------|
| `PDGID` | Particle Data Group Monte Carlo IDs | Particle entities |
| `WD` | Wikidata Q-numbers | Any physics concept |
| `ARXIV` | arXiv preprint identifiers | Publications |
| `DOI` | Digital Object Identifiers | Publications |
| `CODATA` | CODATA recommended values | Physical constants |
| `COD` | Crystallography Open Database | Crystal structures |

### `qudt` prefixes

| Prefix | System | Scope |
|--------|--------|-------|
| `QUDT` | QUDT quantity kind URIs | Quantity kinds |
| `UNIT` | QUDT unit URIs | Units of measure |

---

## 5. Affected Files

### New files

```
science-model/src/science_model/ontologies/physics/
  catalog.yaml                                        # hand-authored physics catalog
science-model/src/science_model/ontologies/qudt/
  catalog.yaml                                        # extracted QUDT catalog
scripts/extract_qudt_catalog.py                       # QUDT extraction script
```

### Modified files

```
science-model/src/science_model/ontologies/registry.yaml  # add physics + qudt entries
science-model/tests/test_ontologies.py                     # add physics + qudt tests
science-tool/tests/test_ontology_suggest.py                # add suggestion tests
references/science-yaml-schema.md                          # list new ontologies
commands/create-project.md                                 # update available ontologies
```

### No changes needed

The ontology infrastructure (Pydantic models, loading functions, profile
routing, materialization, suggestion mechanism) was designed to be
ontology-agnostic. Adding new ontologies requires only new catalog data and
registry entries — no code changes to the framework.

---

## 6. Explicit Scope Boundaries (v1)

- **No ontology hierarchy** — `quark` is not automatically a subtype of
  `elementary_particle`. Same limitation as biolink v1.
- **No deep sub-domain catalogs** — no attempt to enumerate all decay modes,
  crystal space groups, or astrophysical object types. Future sub-domain
  extensions (`hep`, `condensed_matter`, `astro`) will add depth.
- **No QUDT unit catalog** — quantity kinds only. The 2,900 unit definitions
  are not included. Can be added as a QUDT extension if needed.
- **No cross-ontology predicates** — no formal predicates connecting `physics`
  and `qudt` entities. Users express cross-ontology relations through their
  own entities.
- **No equation encoding** — `equation` is an entity type but the catalog
  doesn't define how to represent mathematical content. Equations are
  referenced by name/description.
- **No Wikidata runtime dependency** — Wikidata is a reference for authoring
  the physics catalog. It is not fetched at runtime.

---

## 7. Future Direction

1. **Sub-domain extensions** — `hep` (particle physics), `condensed_matter`,
   `astro`, `plasma` catalogs adding deeper vocabulary for specific fields.
   How sub-domain extension interacts with the base `physics` catalog needs
   separate design work.
2. **Ontology hierarchy (v2)** — `is_a` relationships for type compatibility
   reasoning, shared with the biolink v2 effort.
3. **QUDT unit catalog** — extend QUDT entry to include unit definitions,
   enabling formal unit conversion and dimensional analysis.
4. **Cross-ontology predicates** — formal predicates connecting entities across
   `physics`, `qudt`, and potentially `biolink` (biophysics use cases).
