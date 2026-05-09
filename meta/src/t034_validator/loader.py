"""YAML payload loader for the t034 validator.

Convention: one payload per .yaml/.yml file. The payload's `core.payload_id` is
the registry key. Files without a payload_id, or with a duplicate id, surface as
load errors.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from . import Store


def load_directory(yaml_dir: Path) -> tuple[Store, list[str]]:
    """Walk yaml_dir (top-level only) and load all .yaml/.yml files into a Store.

    Returns (store, load_errors). load_errors is a list of human-readable strings
    describing files that could not be loaded — duplicate ids, missing
    payload_id, YAML parse errors. Successfully-loaded payloads end up in the
    store regardless.
    """
    store = Store()
    errors: list[str] = []

    if not yaml_dir.exists() or not yaml_dir.is_dir():
        return store, errors

    files = sorted(
        f for f in yaml_dir.iterdir()
        if f.is_file() and f.suffix in {".yaml", ".yml"}
    )

    for path in files:
        try:
            with path.open() as fh:
                doc = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            errors.append(f"{path}: YAML parse error: {exc}")
            continue
        except OSError as exc:
            errors.append(f"{path}: read error: {exc}")
            continue

        if not isinstance(doc, dict):
            errors.append(f"{path}: top-level YAML is not a mapping")
            continue

        core = doc.get("core") or {}
        pid = core.get("payload_id")
        if not pid:
            errors.append(f"{path}: missing core.payload_id")
            continue

        try:
            store.add(pid, doc)
        except ValueError as exc:
            errors.append(f"{path}: {exc}")

    return store, errors
