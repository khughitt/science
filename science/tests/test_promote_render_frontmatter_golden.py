"""Test A (emitter equivalence): the canonical render_frontmatter_block must
reproduce commons/promote._render_frontmatter byte-for-byte over a corpus of
realistic frontmatter dicts. Landed BEFORE the migration deletes the local
copy, so the deletion is provably byte-neutral. After Step 4 deletes
promote._render_frontmatter this test is updated to compare against the
harvested golden strings instead (see Step 5)."""

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
