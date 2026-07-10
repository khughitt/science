from science_model.frontmatter import parse_frontmatter, split_frontmatter


def test_preserves_body_verbatim_unlike_parse_frontmatter(tmp_path):
    text = "---\nid: q:demo\nkind: question\n---\n\n  leading and trailing spaces  \n\n"
    fm, body = split_frontmatter(text)
    assert fm == {"id": "q:demo", "kind": "question"}
    # verbatim: the newline after the closing fence, the blank line, the
    # surrounding whitespace, and the trailing blank are ALL kept. The closing
    # marker is "\n---\n"; the body is everything after it, so it starts with
    # the "\n" that preceded the blank line below the fence.
    assert body == "\n  leading and trailing spaces  \n\n"
    # contrast: the lossy reader strips them
    p = tmp_path / "q.md"
    p.write_text(text, encoding="utf-8")
    _, stripped = parse_frontmatter(p)
    assert stripped == "leading and trailing spaces"


def test_crlf_frontmatter_supported():
    text = "---\r\nid: x\r\n---\r\nbody line\r\n"
    fm, body = split_frontmatter(text)
    assert fm == {"id": "x"}
    assert body == "body line\r\n"


def test_no_frontmatter_returns_text_unchanged():
    text = "no frontmatter here\n"
    assert split_frontmatter(text) == ({}, "no frontmatter here\n")


def test_unterminated_frontmatter_returns_text_unchanged():
    text = "---\nid: x\nnever closes\n"
    assert split_frontmatter(text) == ({}, text)


def test_non_mapping_frontmatter_returns_body_only():
    text = "---\n- just\n- a\n- list\n---\nbody\n"
    fm, body = split_frontmatter(text)
    assert fm == {}
    assert body == "body\n"


def test_adjacent_fences_are_not_a_block():
    # Adjacent fences ("---\n" immediately followed by "---\n") contain no
    # "\n---\n" closing marker, so the hand-rolls treat the whole text as
    # having no parseable frontmatter and return it unchanged. split_frontmatter
    # must match that byte-for-byte.
    text = "---\n---\nbody\n"
    assert split_frontmatter(text) == ({}, "---\n---\nbody\n")
