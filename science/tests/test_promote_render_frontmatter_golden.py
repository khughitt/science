"""Test A (emitter equivalence): a permanent regression oracle pinning
render_frontmatter_block's output byte-for-byte over a corpus of realistic
frontmatter dicts. The golden strings were harvested from the former
commons/promote._render_frontmatter (now deleted, folded into the canonical
renderer) at migration time, so this test proves the canonical renderer still
reproduces promote's historical bytes exactly."""

from datetime import date

import pytest

from science_model.frontmatter import render_frontmatter_block

_CORPUS = [
    (
        {"schema_profile": "science-entity-1.0", "id": "paper:smith2020", "kind": "paper",
         "title": "A Study", "version": "1.0.0", "created": date(2026, 7, 10),
         "updated": date(2026, 7, 10), "bibkey": "smith2020", "tags": []},
        'schema_profile: science-entity-1.0\nid: paper:smith2020\nkind: paper\n'
        'title: A Study\nversion: "1.0.0"\ncreated: "2026-07-10"\n'
        'updated: "2026-07-10"\nbibkey: smith2020\ntags: []\n',
    ),
    (
        {"id": "topic:cell-cycle", "overlay_of": "topic:cell-cycle", "pin_version": "2.3",
         "notes": "café — long " + "x" * 300},
        "id: topic:cell-cycle\noverlay_of: topic:cell-cycle\npin_version: \"2.3\"\n"
        "notes: café — long " + "x" * 300 + "\n",
    ),
    (
        {"id": "theme:x", "kind": "theme", "title": "t", "version": "0.1",
         "created": "2026-01-01", "updated": "2026-01-02", "related": ["a", "b"]},
        'id: theme:x\nkind: theme\ntitle: t\nversion: "0.1"\ncreated: "2026-01-01"\n'
        'updated: "2026-01-02"\nrelated:\n- a\n- b\n',
    ),
    (
        {"id": "empty-version", "version": None, "created": date(2026, 7, 10)},
        'id: empty-version\nversion: null\ncreated: "2026-07-10"\n',
    ),
]


@pytest.mark.parametrize("fields, expected", _CORPUS)
def test_render_frontmatter_block_matches_promote(fields, expected):
    assert render_frontmatter_block(dict(fields)) == expected
