"""Fingerprint `extra_css` / `extra_javascript` assets so content changes bust
browser caches.

MkDocs serves `extra_css` and `extra_javascript` entries at stable, unhashed
URLs (unlike the theme's own bundles, which carry a content hash). A returning
visitor can therefore render against a stale cached copy after the file changes
— which is exactly how an edited `palette.css` can leave figures unstyled until
a manual cache clear.

This hook renames each local asset to `<stem>.<hash><suffix>` at build time and
rewrites its reference to match, so every content change produces a fresh URL
and old caches are bypassed automatically.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_EXTERNAL = ("http://", "https://", "//")


def _fingerprint(src_path, files):
    """Rename the referenced file's build destination to include a content hash.

    Returns the new site-root-relative URL, or None if the path is external or
    not a tracked build file.
    """
    if not isinstance(src_path, str) or src_path.startswith(_EXTERNAL):
        return None
    file = files.get_file_from_path(src_path)
    if file is None:
        return None
    digest = hashlib.sha256(Path(file.abs_src_path).read_bytes()).hexdigest()[:8]
    dest = Path(file.dest_uri)
    file.dest_uri = dest.with_name(f"{dest.stem}.{digest}{dest.suffix}").as_posix()
    return file.url


def on_files(files, config):
    config["extra_css"] = [
        _fingerprint(entry, files) or entry for entry in config["extra_css"]
    ]

    for item in config["extra_javascript"]:
        # MkDocs normalizes string entries to ExtraScriptValue objects carrying a
        # mutable `.path`; older plain-string entries are handled just below.
        path = getattr(item, "path", None)
        if path is not None:
            new = _fingerprint(path, files)
            if new:
                item.path = new
    config["extra_javascript"] = [
        (_fingerprint(entry, files) or entry) if isinstance(entry, str) else entry
        for entry in config["extra_javascript"]
    ]

    return files
