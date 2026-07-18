"""Fingerprint `extra_css` assets so content changes bust browser caches.

MkDocs serves `extra_css` entries at stable, unhashed URLs (unlike the theme's
own stylesheets, which carry a content hash). A returning visitor can therefore
render against a stale cached copy after the file changes — which is exactly how
an edited `palette.css` can leave figures unstyled until a manual cache clear.

This hook renames each local `extra_css` file to `<stem>.<hash><suffix>` at
build time and rewrites the `extra_css` reference to match, so every content
change produces a fresh URL and old caches are bypassed automatically.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def on_files(files, config):
    remap: dict[str, str] = {}
    for entry in config["extra_css"]:
        if entry.startswith(("http://", "https://", "//")):
            continue
        file = files.get_file_from_path(entry)
        if file is None:
            continue
        digest = hashlib.sha256(Path(file.abs_src_path).read_bytes()).hexdigest()[:8]
        dest = Path(file.dest_uri)
        file.dest_uri = dest.with_name(f"{dest.stem}.{digest}{dest.suffix}").as_posix()
        remap[entry] = file.url
    config["extra_css"] = [remap.get(entry, entry) for entry in config["extra_css"]]
    return files
