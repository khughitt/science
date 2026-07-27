"""Synthetic probe paths for a declaration.

`--verify-current-tree` can only speak for paths that exist. Probes cover the
shapes that do not exist yet -- a new dataset version, a deeper nesting level.
`git check-ignore --no-index` evaluates hypothetical paths, so probes need no
files on disk.
"""

from __future__ import annotations

from science_tool.boundary.config import BoundaryConfig, StorageClass

_DEEP = "p1/p2/p3"


def probe_paths(cfg: BoundaryConfig) -> list[str]:
    probes: list[str] = []
    for root in sorted(cfg.roots, key=lambda r: r.path):
        probes.append(f"{root.path}/probe.bin")
        probes.append(f"{root.path}/{_DEEP}/probe.bin")
        probes.append(f"{root.path}/probe.parquet")
        probes.append(f"{root.path}/.hidden")
        if root.storage_class is StorageClass.MANIFEST:
            for glob in sorted(root.tracked):
                name = glob.replace("*", "probe")
                probes.append(f"{root.path}/d1/{name}")
                probes.append(f"{root.path}/{_DEEP}/{name}")
    return sorted(set(probes))
