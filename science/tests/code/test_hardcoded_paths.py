from science_tool.code.hardcoded_paths import (
    DEFAULT_HARDCODED_PREFIXES,
    find_hardcoded_paths,
)


def test_flags_home_and_mnt_paths() -> None:
    findings = find_hardcoded_paths(
        'p = "/home/keith/data/x.tsv"\nq = "/mnt/ssd/Dropbox/y.tsv"\n'
    )
    patterns = {f.pattern for f in findings}
    assert "/home/" in patterns
    assert "/mnt/" in patterns


def test_clean_relative_path_has_no_findings() -> None:
    assert find_hardcoded_paths("x = read('data/in.tsv')\n") == []


def test_extra_prefixes_extend_builtins() -> None:
    findings = find_hardcoded_paths(
        "P = 'site/proj/special/x'\n", extra_prefixes=("site/proj/special/",)
    )
    assert any(f.pattern == "site/proj/special/" for f in findings)


def test_line_numbers_are_one_based() -> None:
    findings = find_hardcoded_paths('a = 1\nb = "/home/keith/x"\n')
    assert findings[0].line_number == 2
    assert findings[0].line == 'b = "/home/keith/x"'


def test_windows_drive_is_flagged() -> None:
    findings = find_hardcoded_paths('p = "C:\\\\Users\\\\keith\\\\x"\n')
    assert any(f.pattern == "<windows-drive>" for f in findings)


def test_default_prefixes_are_absolute_roots() -> None:
    assert "/home/" in DEFAULT_HARDCODED_PREFIXES
    assert all(p.startswith("/") for p in DEFAULT_HARDCODED_PREFIXES)
