"""Shared ``shutil.copytree`` ignore helpers for the validate parity gates.

Real downstream projects carry large binary payload (datasets, archives, PDFs)
that these tests never read -- they only exercise ``validate`` against project
structure, config, and text. Copying that payload into ``tmp_path`` inflated the
per-user ``/tmp`` tmpfs quota (gigabytes per run, which silently broke tooling
that writes there). We skip oversized files at copy time; semantic parity still
holds because both the bash and the python copy see the identical reduced tree.
"""

from __future__ import annotations

import os

# Project source/config/text fixtures sit well under this cap; the real payload
# (PDFs in the tens of MB, dataset tarballs near 1 GB) sits well over it.
MAX_COPIED_FILE_BYTES = 2_000_000


def oversized_payload_names(directory: str, names: list[str]) -> set[str]:
    """Return entries in ``directory`` whose file size exceeds the payload cap.

    Shaped as a ``shutil.copytree(ignore=...)`` predicate. Directories and
    entries that cannot be stat'd are left to copytree to handle.
    """
    skipped: set[str] = set()
    for name in names:
        path = os.path.join(directory, name)
        try:
            if os.path.isfile(path) and os.path.getsize(path) > MAX_COPIED_FILE_BYTES:
                skipped.add(name)
        except OSError:
            continue
    return skipped
