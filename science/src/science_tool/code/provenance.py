"""Normalize an MM30-style provenance tool reference to a code-file canonical id.

A tool reference like ``scripts/signatures/build.py::build_combined_corpus`` becomes
``code-file:signatures/build.py``: the ``::function`` suffix is dropped, the declared
code-root prefix is stripped (matching CodeAdapter._local_id), and the ``code-file:``
prefix is added. This mirrors how CodeAdapter assigns code-file ids so authored
``produced_by`` refs line up with the registered entities.
"""

from __future__ import annotations


def code_file_id_from_tool_path(tool_path: str, *, code_root_names: tuple[str, ...]) -> str:
    path = tool_path.split("::", 1)[0].strip()
    for root in code_root_names:
        prefix = f"{root}/"
        if path == root:
            path = path.rsplit("/", 1)[-1]
            break
        if path.startswith(prefix):
            path = path[len(prefix):]
            break
    return f"code-file:{path}"
