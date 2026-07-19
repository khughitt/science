import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main
from science_tool.skills_lint import cli as sources_cli
from science_tool.skills_lint.cli import check_sources, fetch_remote_head_sha


def _make_repo(tmp_path: Path) -> Path:
    root = tmp_path / "skills"
    root.mkdir()
    (root / "sources.yaml").write_text(
        'git:\n  title: G\n  authors: [A]\n'
        '  url: https://github.com/o/r\n  kind: skill-repo\n  license: MIT\n'
        f'  upstream_ref: {"a" * 40}\n  last_checked: 2026-07-18\n'
        "ref:\n  title: R\n  authors: [A]\n  url: https://doi.org/x\n"
        "  kind: book\n  last_checked: 2026-07-18\n",
        encoding="utf-8",
    )
    (root / "INDEX.md").write_text("`skills/leaf.md`\n", encoding="utf-8")
    (root / "leaf.md").write_text(
        "---\nname: leaf\ndescription: d\nsources: [git, ref]\n---\n"
        "# Leaf\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    return root


def test_check_offline_is_clean(tmp_path: Path) -> None:
    report = check_sources(_make_repo(tmp_path), fetch_upstream=False)
    by_id = {s.id: s for s in report.sources}
    assert by_id["git"].freshness == "not_checked"
    assert by_id["ref"].freshness == "not_applicable"
    assert by_id["git"].citing_leaves == ("leaf.md",)
    assert by_id["git"].last_checked == "2026-07-18"
    assert all(r.status == "resolved" for r in report.refs)
    assert report.failed() is False


def test_check_fetch_stale_names_citing_leaves(tmp_path: Path) -> None:
    report = check_sources(_make_repo(tmp_path), fetch_upstream=True, fetch=lambda url: ("b" * 40, ""))
    git = {s.id: s for s in report.sources}["git"]
    assert git.freshness == "stale"
    assert git.citing_leaves == ("leaf.md",)
    assert report.failed() is True


def test_check_fetch_fresh_is_clean(tmp_path: Path) -> None:
    report = check_sources(_make_repo(tmp_path), fetch_upstream=True, fetch=lambda url: ("a" * 40, ""))
    assert {s.id: s.freshness for s in report.sources}["git"] == "fresh"
    assert report.failed() is False


def test_check_fetch_unreachable_fails(tmp_path: Path) -> None:
    report = check_sources(_make_repo(tmp_path), fetch_upstream=True, fetch=lambda url: (None, "timeout"))
    assert {s.id: s.freshness for s in report.sources}["git"] == "unreachable"
    assert report.failed() is True


def test_unresolved_ref_fails(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)
    (root / "leaf.md").write_text(
        "---\nname: leaf\ndescription: d\nsources: [git, gone]\n---\n"
        "# Leaf\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    report = check_sources(root, fetch_upstream=False)
    statuses = {(r.ref, r.status) for r in report.refs}
    assert ("gone", "unresolved") in statuses
    assert ("git", "resolved") in statuses
    assert report.failed() is True


def test_cli_list_json_has_both_directions(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)
    result = CliRunner().invoke(main, ["skills", "sources", "list", "--root", str(root), "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["by_source"]["git"] == ["leaf.md"]
    assert payload["by_leaf"]["leaf.md"] == ["git", "ref"]


def test_cli_check_json_pins_axes_offline(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)
    result = CliRunner().invoke(main, ["skills", "sources", "check", "--root", str(root), "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert {"sources", "refs"} <= set(payload)
    for entry in payload["sources"]:
        assert set(entry) >= {"id", "validation", "freshness", "last_checked", "citing_leaves"}
        assert entry["validation"] in {"valid", "invalid"}
        assert entry["freshness"] in {"fresh", "stale", "unreachable", "not_checked", "not_applicable", "unknown"}
    for ref in payload["refs"]:
        assert set(ref) >= {"leaf", "ref", "status"}
        assert ref["status"] in {"resolved", "unresolved"}
    assert "leaf_errors" in payload


def test_cli_check_exit_nonzero_on_unresolved(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)
    (root / "leaf.md").write_text(
        "---\nname: leaf\ndescription: d\nsources: [gone]\n---\n"
        "# Leaf\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    result = CliRunner().invoke(main, ["skills", "sources", "check", "--root", str(root)])
    assert result.exit_code == 1


def test_check_corrupt_registry_fails_not_silently_clean(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    root.mkdir()
    (root / "sources.yaml").write_text("just a string, not a mapping\n", encoding="utf-8")
    (root / "INDEX.md").write_text("`skills/x.md`\n", encoding="utf-8")
    report = check_sources(root, fetch_upstream=False)
    # A file-level error must surface as an invalid source, not an empty clean report.
    assert any(s.validation == "invalid" for s in report.sources)
    assert report.failed() is True
    result = CliRunner().invoke(main, ["skills", "sources", "check", "--root", str(root)])
    assert result.exit_code == 1


def test_check_invalid_record_reports_unknown_freshness_and_fails(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    root.mkdir()
    (root / "sources.yaml").write_text(
        # git-backed but missing upstream_ref/license → invalid; freshness is not
        # "not_applicable" (that is reserved for reference-only), it is "unknown".
        "brokengit:\n  title: B\n  authors: [A]\n"
        "  url: https://github.com/o/r\n  kind: skill-repo\n  last_checked: 2026-07-18\n",
        encoding="utf-8",
    )
    (root / "INDEX.md").write_text("`skills/x.md`\n", encoding="utf-8")
    report = check_sources(root, fetch_upstream=False)
    broken = {s.id: s for s in report.sources}["brokengit"]
    assert broken.validation == "invalid"
    assert broken.freshness == "unknown"
    assert report.failed() is True


def test_spec_and_software_report_not_applicable_freshness(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    root.mkdir()
    (root / "sources.yaml").write_text(
        "spec1:\n  title: S\n  authors: [Org]\n  url: https://specs.example.org/x\n"
        "  kind: spec\n  last_checked: 2026-07-18\n"
        "soft1:\n  title: T\n  authors: [Org]\n  url: https://tool.example.org/\n"
        "  kind: software\n  last_checked: 2026-07-18\n",
        encoding="utf-8",
    )
    (root / "INDEX.md").write_text("`skills/leaf.md`\n", encoding="utf-8")
    (root / "leaf.md").write_text(
        "---\nname: leaf\ndescription: d\nsources: [spec1, soft1]\n---\n"
        "# Leaf\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    # fetch_upstream=True proves reference kinds are never fetched (fetch raises if called).
    def _boom(url):  # pragma: no cover - must not be invoked
        raise AssertionError("reference kinds must not be fetched")
    report = check_sources(root, fetch_upstream=True, fetch=_boom)
    freshness = {s.id: s.freshness for s in report.sources}
    assert freshness["spec1"] == "not_applicable"
    assert freshness["soft1"] == "not_applicable"
    assert report.failed() is False


def test_check_malformed_leaf_sources_field_fails(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)
    (root / "leaf.md").write_text(
        "---\nname: leaf\ndescription: d\nsources: not-a-list\n---\n"
        "# Leaf\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    report = check_sources(root, fetch_upstream=False)
    assert any(leaf == "leaf.md" for leaf, _ in report.leaf_errors)
    assert report.failed() is True
    result = CliRunner().invoke(main, ["skills", "sources", "check", "--root", str(root)])
    assert result.exit_code == 1


# --- fetch-mode CLI contract (monkeypatch the module fetch; no network) ---


def test_cli_check_fetch_flag_forwarded_to_fetch(tmp_path: Path, monkeypatch) -> None:
    root = _make_repo(tmp_path)
    calls = {"n": 0}

    def spy(url):
        calls["n"] += 1
        return ("a" * 40, "")

    monkeypatch.setattr(sources_cli, "fetch_remote_head_sha", spy)
    # Offline (no flag): fetch must NOT run.
    CliRunner().invoke(main, ["skills", "sources", "check", "--root", str(root)])
    assert calls["n"] == 0
    # --fetch-upstream: fetch runs once for the git-backed source.
    CliRunner().invoke(main, ["skills", "sources", "check", "--root", str(root), "--fetch-upstream"])
    assert calls["n"] == 1


def test_cli_check_fetch_stale_json_exits_nonzero(tmp_path: Path, monkeypatch) -> None:
    root = _make_repo(tmp_path)
    monkeypatch.setattr(sources_cli, "fetch_remote_head_sha", lambda url: ("b" * 40, ""))
    result = CliRunner().invoke(
        main, ["skills", "sources", "check", "--root", str(root), "--fetch-upstream", "--format", "json"]
    )
    payload = json.loads(result.output)
    assert {s["id"]: s["freshness"] for s in payload["sources"]}["git"] == "stale"
    assert result.exit_code == 1


def test_cli_check_fetch_fresh_json_exits_zero(tmp_path: Path, monkeypatch) -> None:
    root = _make_repo(tmp_path)
    monkeypatch.setattr(sources_cli, "fetch_remote_head_sha", lambda url: ("a" * 40, ""))
    result = CliRunner().invoke(
        main, ["skills", "sources", "check", "--root", str(root), "--fetch-upstream", "--format", "json"]
    )
    payload = json.loads(result.output)
    assert {s["id"]: s["freshness"] for s in payload["sources"]}["git"] == "fresh"
    assert result.exit_code == 0


def test_cli_check_fetch_unreachable_exits_nonzero(tmp_path: Path, monkeypatch) -> None:
    root = _make_repo(tmp_path)
    monkeypatch.setattr(sources_cli, "fetch_remote_head_sha", lambda url: (None, "timeout"))
    result = CliRunner().invoke(main, ["skills", "sources", "check", "--root", str(root), "--fetch-upstream"])
    assert result.exit_code == 1


# --- fetch_remote_head_sha hardening (no network; inject the run seam) ---

def test_fetch_forwards_hardened_args() -> None:
    captured: dict = {}

    def fake_run(args, *, timeout, env, max_bytes):
        captured.update(args=args, timeout=timeout, env=env, max_bytes=max_bytes)
        return 0, (b"a" * 40) + b"\tHEAD\n"

    sha, detail = fetch_remote_head_sha("https://github.com/o/r", timeout=7, max_bytes=99, run=fake_run)
    assert sha == "a" * 40 and detail == ""
    assert captured["args"] == ["git", "ls-remote", "https://github.com/o/r", "HEAD"]
    assert captured["timeout"] == 7 and captured["max_bytes"] == 99
    assert captured["env"]["GIT_TERMINAL_PROMPT"] == "0"


def test_fetch_rejects_non_github_host_without_running() -> None:
    called = {"n": 0}

    def fake_run(*a, **k):
        called["n"] += 1
        return 0, b""

    sha, detail = fetch_remote_head_sha("https://gitlab.com/o/r", run=fake_run)
    assert sha is None and "allowlist" in detail
    assert called["n"] == 0


def test_fetch_oversized_output_is_unreachable() -> None:
    sha, detail = fetch_remote_head_sha(
        "https://github.com/o/r", max_bytes=8, run=lambda *a, **k: (0, b"x" * 100)
    )
    assert sha is None and "large" in detail


def test_fetch_malformed_output_is_unreachable() -> None:
    sha, detail = fetch_remote_head_sha(
        "https://github.com/o/r", run=lambda *a, **k: (0, b"not-a-sha\tHEAD\n")
    )
    assert sha is None and "unexpected" in detail


def test_fetch_timeout_is_unreachable() -> None:
    sha, detail = fetch_remote_head_sha("https://github.com/o/r", run=lambda *a, **k: (None, b""))
    assert sha is None


def test_run_git_sets_env_and_bounds_read(monkeypatch, tmp_path) -> None:
    seen: dict = {}

    class FakeStdout:
        def read(self, n):
            seen["read_n"] = n
            return (b"a" * 40) + b"\tHEAD\n"

    class FakeProc:
        returncode = 0
        stdout = FakeStdout()

        def __init__(self, args, **kwargs):
            seen["args"] = args
            seen["env"] = kwargs["env"]

        def poll(self):  # already exited → runner skips the extra kill
            return 0

        def wait(self):
            seen["waited"] = True
            return 0

        def kill(self):
            seen["killed"] = True

    monkeypatch.setattr(sources_cli.subprocess, "Popen", FakeProc)
    code, out = sources_cli._run_git(
        ["git", "ls-remote", "https://github.com/o/r", "HEAD"],
        timeout=5,
        env={"GIT_TERMINAL_PROMPT": "0"},
        max_bytes=16,
    )
    assert code == 0
    assert out.startswith(b"a" * 40)
    assert seen["read_n"] == 17  # max_bytes + 1
    assert seen["waited"] is True  # child is always reaped
    assert seen["env"]["GIT_TERMINAL_PROMPT"] == "0"


def test_run_git_timeout_kills_and_reaps(monkeypatch) -> None:
    # A read that outlasts the deadline must kill the child AND wait() to reap it,
    # returning None. The old code that skipped this reaping would leave a zombie.
    import threading

    seen: dict = {}
    release = threading.Event()

    class FakeStdout:
        def read(self, n):
            release.wait(2)  # blocks past the tiny timeout; kill() releases it
            return b""

    class FakeProc:
        returncode = -9
        stdout = FakeStdout()

        def __init__(self, args, **kwargs):
            pass

        def poll(self):
            return None  # still running

        def wait(self):
            seen["waited"] = True
            return -9

        def kill(self):
            seen["killed"] = True
            release.set()  # let the blocked reader unwind so the thread can exit

    monkeypatch.setattr(sources_cli.subprocess, "Popen", FakeProc)
    code, out = sources_cli._run_git(
        ["git", "ls-remote", "https://github.com/o/r", "HEAD"],
        timeout=0.05,
        env={"GIT_TERMINAL_PROMPT": "0"},
        max_bytes=16,
    )
    assert code is None
    assert out == b""
    assert seen.get("killed") is True
    assert seen.get("waited") is True


def test_run_git_capped_live_child_is_killed_before_wait(monkeypatch) -> None:
    # Reader returns at the byte cap while the child is still live (blocked writing
    # to a pipe we stopped reading). It must be killed BEFORE wait(), never an
    # unbounded wait() on a live child, and the capped bytes flow back to the caller.
    seen: dict = {}
    order: list[str] = []

    class FakeStdout:
        def read(self, n):
            seen["read_n"] = n
            return b"x" * n  # fills the cap → over budget, EOF not reached

    class FakeProc:
        returncode = -9
        stdout = FakeStdout()

        def __init__(self, args, **kwargs):
            pass

        def poll(self):
            return None  # still running: blocked on the full pipe

        def kill(self):
            order.append("kill")

        def wait(self):
            order.append("wait")
            return -9

    monkeypatch.setattr(sources_cli.subprocess, "Popen", FakeProc)
    code, out = sources_cli._run_git(
        ["git", "ls-remote", "https://github.com/o/r", "HEAD"],
        timeout=5,
        env={"GIT_TERMINAL_PROMPT": "0"},
        max_bytes=16,
    )
    assert seen["read_n"] == 17
    assert order == ["kill", "wait"]  # kill precedes wait; no unbounded wait on a live child
    assert len(out) == 17  # the over-budget bytes propagate (fetch layer rejects them)
