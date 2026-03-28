#!/usr/bin/env python3
"""Extract a units (QUDT) quantity-kind catalog from the RDF/Turtle source.

One-time dev script — not part of the runtime package.
Produces science-model/src/science_model/ontologies/units/catalog.yaml.

Usage:
    uv run --with rdflib scripts/extract_units_catalog.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

import yaml

try:
    from rdflib import Graph, Namespace, URIRef
    from rdflib.namespace import DCTERMS, RDF, RDFS, SKOS
except ImportError:
    print("Error: rdflib not available. Run with: uv run --with rdflib scripts/extract_units_catalog.py", file=sys.stderr)
    sys.exit(1)

QUDT_VERSION = "3.2.0"
# QUDT publishes quantity-kind vocabulary as Turtle; the 2.1 URL serves current content.
QUDT_QK_URL = "https://qudt.org/2.1/vocab/quantitykind"
QUDT_QK_NS = "http://qudt.org/vocab/quantitykind/"

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "science-model/src/science_model/ontologies/units/catalog.yaml"

# Namespace for QUDT schema properties
QUDT = Namespace("http://qudt.org/schema/qudt/")

# --- Recommended quantity kinds: commonly used in physics and general science ---
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
    "LuminousIntensity",
    "Viscosity",
    "Impedance",
    "Conductance",
    "Permittivity",
}

# Curated inclusion list: quantity kinds relevant to physics and general science.
# QUDT contains ~1200 quantity kinds; we keep only those useful for a broad
# physics / science ontology, skipping highly specialized engineering,
# aerospace, monetary, IT, and medical sub-domains.
_INCLUDED_QUANTITY_KINDS: set[str] = {
    # --- Mechanics (kinematics & dynamics) ---
    "Mass", "Length", "Time", "Area", "Volume", "Angle",
    "Velocity", "Speed", "Acceleration", "AccelerationOfGravity",
    "AngularVelocity", "AngularAcceleration", "AngularFrequency",
    "Force", "Weight", "Torque", "Momentum", "AngularMomentum",
    "Impulse", "AngularImpulse",
    "Pressure", "Stress", "Strain",
    "Density", "MassDensity", "SpecificVolume",
    "MassFlowRate", "VolumeFlowRate",
    "Work", "Energy", "KineticEnergy", "PotentialEnergy",
    "Power", "Action",
    "Compressibility", "BulkModulus", "ModulusOfElasticity",
    "Friction", "StaticFriction",
    "SurfaceTension", "Viscosity",
    "Curvature", "Displacement",
    # --- Oscillations & waves ---
    "Frequency", "Wavelength", "Wavenumber", "Period",
    # --- Thermodynamics ---
    "Temperature", "ThermodynamicTemperature", "CelsiusTemperature",
    "Entropy", "ThermodynamicEntropy",
    "ThermodynamicEnergy", "InternalEnergy",
    "HeatCapacity", "SpecificHeatCapacity",
    "ThermalConductivity", "ThermalDiffusivity",
    "ThermalExpansionCoefficient", "HeatFlowRate",
    "BoilingPoint", "MeltingPoint",
    # --- Electromagnetism ---
    "ElectricCharge", "ElectricCurrent", "Voltage",
    "ElectricField", "ElectricFieldStrength",
    "ElectricPotential", "ElectricDipoleMoment",
    "Resistance", "Resistivity", "Conductance", "Conductivity",
    "Capacitance", "Inductance", "Impedance", "Admittance",
    "MagneticField", "MagneticFlux", "MagneticFluxDensity",
    "MagneticDipoleMoment", "Magnetization",
    "Permeability", "Permittivity",
    "ElectricCurrentDensity", "ElectricChargeDensity",
    "ElectricPolarization", "Polarizability",
    "Reactance", "Susceptance",
    # --- Optics & radiation ---
    "LuminousIntensity", "LuminousFlux", "LuminousEfficacy", "Luminance", "Illuminance",
    "RadiantIntensity", "RadiantFlux", "RadiantEnergy", "Irradiance", "Radiance",
    "Reflectance", "Transmittance", "Absorptance",
    "RefractiveIndex",
    # --- Atomic & nuclear physics ---
    "AtomicMass", "AtomicNumber", "AtomicEnergy",
    "BindingFraction",
    "Half-Life", "DecayConstant",
    "CrossSection", "MeanFreePath",
    "Activity",
    "AbsorbedDose", "AbsorbedDoseRate",
    # --- Quantum & statistical mechanics ---
    "Spin", "SpinQuantumNumber",
    "StatisticalWeight",
    # --- Gravitation & astrophysics ---
    "GravitationalAttraction",
    "Altitude",
    # --- Chemistry ---
    "AmountOfSubstance", "AmountOfSubstanceConcentration",
    "MolarMass", "MolarEnergy", "MolarEntropy", "MolarHeatCapacity",
    "MolarVolume", "MolalityOfSolute",
    "ChemicalPotential",
    "ActivityCoefficient", "CatalyticActivity",
    "Concentration",
    "Acidity", "Basicity",
    # --- Acoustics ---
    "SoundPressure", "SoundIntensity",
    "SpeedOfSound", "AcousticImpedance",
    "SoundPowerLevel", "SoundPressureLevel",
    # --- Fluid mechanics ---
    "Circulation", "Vorticity",
    "DynamicViscosity", "KinematicViscosity",
    "MachNumber", "ReynoldsNumber",
    # --- Dimensionless & general ---
    "Dimensionless", "Ratio", "Efficiency",
    "EnergyDensity",
    "MassPerLength", "MassPerArea",
    "ForcePerLength", "ForcePerArea",
    "EnergyPerArea",
    "SpecificEnergy", "SpecificEntropy",
    "LinearMomentum",
    "MomentOfInertia",
    "AngularDistance",
    "SolidAngle",
    "Breadth", "Height", "Width", "Thickness", "Depth",
    "Distance", "Radius",
    "SpeedOfLight",
    "Count",
    "MassRatio", "LengthRatio",
    "TimeRatio", "VolumeStrain",
    "ComplexPower", "ApparentPower", "ActivePower", "ReactivePower",
}


def _camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case."""
    # Normalize hyphens to underscores first
    name = name.replace("-", "_")
    result: list[str] = []
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            # Don't add underscore between consecutive uppercase (e.g., RNA -> rna)
            if name[i - 1].islower() or (i + 1 < len(name) and name[i + 1].islower()):
                result.append("_")
        result.append(char.lower())
    # Collapse double underscores
    return re.sub(r"_+", "_", "".join(result))


def _is_included(local_name: str) -> bool:
    """Return True if this quantity kind is in the curated inclusion list."""
    return local_name in _INCLUDED_QUANTITY_KINDS


def _clean_latex(text: str) -> str:
    """Strip common LaTeX markup from QUDT descriptions."""
    # Remove \textit{...}, \textbf{...}, \emph{...}
    text = re.sub(r"\\(?:textit|textbf|emph)\{([^}]*)\}", r"\1", text)
    # Remove inline math delimiters but keep content
    text = re.sub(r"\$([^$]*)\$", r"\1", text)
    # Remove remaining backslash commands like \times, \rho, etc. — keep the command name
    text = re.sub(r"\\([a-zA-Z]+)", r"\1", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _get_description(g: Graph, subject: URIRef) -> str:
    """Extract description from an RDF subject, trying multiple predicates."""
    # Try QUDT plainTextDescription first, then dcterms:description, rdfs:comment, skos:definition
    for pred in [QUDT.plainTextDescription, DCTERMS.description, RDFS.comment, SKOS.definition]:
        for obj in g.objects(subject, pred):
            text = str(obj).strip()
            if text:
                text = _clean_latex(text)
                return text[:200]
    return ""


def main() -> None:
    print(f"Fetching QUDT quantity-kind vocabulary from {QUDT_QK_URL} ...")

    # Fetch the Turtle content — request Turtle content type
    req = Request(QUDT_QK_URL, headers={"Accept": "text/turtle, application/x-turtle, */*"})
    with urlopen(req, timeout=60) as resp:
        data = resp.read()

    print(f"  Downloaded {len(data)} bytes, parsing RDF ...")
    g = Graph()
    g.parse(data=data, format="turtle")

    print(f"  Graph has {len(g)} triples")

    # --- Extract quantity kinds ---
    entity_types: list[dict[str, object]] = []
    seen_names: set[str] = set()

    # Find all subjects that are typed as qudt:QuantityKind
    quantity_kind_type = QUDT.QuantityKind
    qk_subjects: set[URIRef] = set()

    for s in g.subjects(RDF.type, quantity_kind_type):
        if isinstance(s, URIRef):
            qk_subjects.add(s)

    # Also check for subjects in the quantitykind namespace that have rdfs:label
    for s, _p, _o in g.triples((None, RDFS.label, None)):
        if isinstance(s, URIRef) and str(s).startswith(QUDT_QK_NS):
            qk_subjects.add(s)

    print(f"  Found {len(qk_subjects)} candidate quantity kinds")

    for subject in sorted(qk_subjects, key=str):
        uri = str(subject)
        if not uri.startswith(QUDT_QK_NS):
            continue

        local_name = uri[len(QUDT_QK_NS):]
        if not local_name or "/" in local_name:
            continue

        if not _is_included(local_name):
            continue

        # Get label — prefer rdfs:label, fall back to local name
        label = ""
        for obj in g.objects(subject, RDFS.label):
            label = str(obj).strip()
            break
        if not label:
            label = local_name

        name = _camel_to_snake(local_name)
        if name in seen_names:
            continue
        seen_names.add(name)

        description = _get_description(g, subject)
        recommended = local_name in RECOMMENDED_QUANTITY_KINDS

        entry: dict[str, object] = {
            "id": f"qudt:{local_name}",
            "name": name,
            "description": description if description else f"The {label.lower()} quantity kind.",
            "curie_prefixes": ["QUDT"],
        }
        if recommended:
            entry["recommended"] = True

        entity_types.append(entry)

    # Sort: recommended first, then alphabetical
    entity_types.sort(key=lambda e: (not e.get("recommended", False), e["name"]))

    # --- Hand-authored predicates ---
    predicates: list[dict[str, object]] = [
        {
            "id": "qudt:has_quantity_kind",
            "name": "has_quantity_kind",
            "description": "Associates a quantity or measurement with its quantity kind.",
            "domain": "qudt:Quantity",
            "range": "qudt:QuantityKind",
            "recommended": True,
        },
        {
            "id": "qudt:has_dimension",
            "name": "has_dimension",
            "description": "Associates a quantity kind with its dimensional analysis vector.",
            "domain": "qudt:QuantityKind",
            "range": "qudt:DimensionVector",
            "recommended": True,
        },
        {
            "id": "qudt:has_unit",
            "name": "has_unit",
            "description": "Associates a quantity or quantity kind with a measurement unit.",
            "domain": "qudt:Quantity",
            "range": "qudt:Unit",
            "recommended": True,
        },
        {
            "id": "qudt:measured_in",
            "name": "measured_in",
            "description": "Indicates the unit in which a measurement is expressed.",
            "domain": "qudt:Quantity",
            "range": "qudt:Unit",
            "recommended": True,
        },
        {
            "id": "qudt:proportional_to",
            "name": "proportional_to",
            "description": "Indicates that one quantity kind is directly proportional to another.",
            "domain": "qudt:QuantityKind",
            "range": "qudt:QuantityKind",
        },
        {
            "id": "qudt:inversely_proportional_to",
            "name": "inversely_proportional_to",
            "description": "Indicates that one quantity kind is inversely proportional to another.",
            "domain": "qudt:QuantityKind",
            "range": "qudt:QuantityKind",
        },
    ]

    # --- Build catalog ---
    header = (
        "# QUDT Quantity Kind catalog — extracted from QUDT v%s\n"
        "# https://qudt.org/\n"
        "#\n"
        "# Refresh with: uv run --with rdflib scripts/extract_units_catalog.py\n"
        "# Entity types: QUDT quantity kinds relevant to physics and general science\n"
        "# Predicates: hand-authored measurement-oriented relations\n"
        "# recommended: true marks commonly-used terms highlighted by the suggestion system\n"
    ) % QUDT_VERSION

    catalog: dict[str, object] = {
        "ontology": "units",
        "version": QUDT_VERSION,
        "prefix": "qudt",
        "prefix_uri": "https://qudt.org/vocab/quantitykind/",
        "entity_types": entity_types,
        "predicates": predicates,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    yaml_content = yaml.dump(catalog, default_flow_style=False, sort_keys=False, allow_unicode=True, width=120)
    # Ensure version is quoted to prevent YAML parsing issues with versions like "4.0"
    yaml_content = yaml_content.replace(f"version: {QUDT_VERSION}", f'version: "{QUDT_VERSION}"')
    OUTPUT_PATH.write_text(header + "\n" + yaml_content, encoding="utf-8")

    n_recommended_types = sum(1 for et in entity_types if et.get("recommended"))
    n_recommended_preds = sum(1 for p in predicates if p.get("recommended"))
    print(f"\nWrote {OUTPUT_PATH}")
    print(f"  Entity types: {len(entity_types)} total, {n_recommended_types} recommended")
    print(f"  Predicates:   {len(predicates)} total, {n_recommended_preds} recommended")

    # --- Verification ---
    required_names = {"mass", "energy", "temperature", "velocity"}
    found_names = {str(et["name"]) for et in entity_types}
    missing = required_names - found_names
    if missing:
        print(f"\n  WARNING: Missing expected entity types: {missing}", file=sys.stderr)
    else:
        print(f"  Spot-check passed: {required_names} all present")

    if not (60 <= len(entity_types) <= 200):
        print(f"\n  WARNING: Entity type count {len(entity_types)} outside expected range [60, 200]", file=sys.stderr)
    if n_recommended_types < 20 or n_recommended_types > 50:
        print(
            f"\n  WARNING: Recommended count {n_recommended_types} outside expected range [20, 50]", file=sys.stderr
        )


if __name__ == "__main__":
    main()
