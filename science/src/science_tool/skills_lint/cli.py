import os
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import click

from science_tool.output import emit
from science_tool.skills_lint.lint import SkillIssue, check_skills
from science_tool.skills_lint.sources import (
    FETCH_HOST_ALLOWLIST,
    REFERENCE_KINDS,
    SHA_RE,
    SourcesRegistry,
    leaf_source_refs,
    load_sources,
)


@click.group(name="skills")
def skills_group() -> None:
    """Skills library tooling."""


@skills_group.command(name="lint")
@click.option("--root", type=click.Path(exists=True, file_okay=False), default="skills")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def lint_cmd(root: str, fmt: str) -> None:
    """Lint the skills/ tree for structural conformance."""
    issues = check_skills(Path(root))

    def _render() -> None:
        for issue in issues:
            click.echo(_format_text_issue(issue))

    emit(
        output_format=fmt,
        payload={"issues": [issue.to_json() for issue in issues]},
        render_text=_render,
    )
    if _has_error(issues):
        raise click.exceptions.Exit(1)


def _format_text_issue(issue: SkillIssue) -> str:
    parts = [issue.severity, issue.path.as_posix(), issue.kind]
    if issue.field is not None:
        parts.append(issue.field)
    if issue.detail:
        parts.append(issue.detail)
    return ": ".join(parts)


def _has_error(issues: list[SkillIssue]) -> bool:
    return any(issue.severity == "error" for issue in issues)


def build_dependency_views(
    root: Path, registry: SourcesRegistry
) -> tuple[dict[str, list[str]], dict[str, list[str]], list[tuple[str, str]]]:
    by_source: dict[str, list[str]] = {sid: [] for sid in registry.declared_ids}
    by_leaf: dict[str, list[str]] = {}
    leaf_errors: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*.md")):
        refs, error = leaf_source_refs(path)
        rel = path.relative_to(root).as_posix()
        if error is not None:
            leaf_errors.append((rel, error))
            continue
        if not refs:
            continue
        by_leaf[rel] = list(refs)
        for ref in refs:
            by_source.setdefault(ref, []).append(rel)
    return by_source, by_leaf, leaf_errors


def _run_git(args: list[str], *, timeout: float, env: dict[str, str], max_bytes: int) -> tuple[int | None, bytes]:
    """Run a git command, reading at most ``max_bytes + 1`` bytes. The child is
    always reaped: on a read that outlasts ``timeout`` we kill and wait (returning
    ``None``); once the reader returns we never block on ``wait()`` for a still-live
    child holding a full pipe — we kill it first, then reap. ``returncode`` is
    ``None`` on timeout or spawn failure."""
    try:
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env)
    except OSError:
        return None, b""
    box: dict[str, bytes] = {}

    def _read() -> None:
        assert proc.stdout is not None
        box["out"] = proc.stdout.read(max_bytes + 1)

    reader = threading.Thread(target=_read, daemon=True)
    reader.start()
    reader.join(timeout)
    if reader.is_alive():
        # Read outlasted the deadline; kill so the blocked read unwinds, then reap.
        proc.kill()
        proc.wait()
        return None, b""
    # Reader returned (EOF or byte cap). If the child is still live it is blocked
    # writing to a pipe we have stopped reading — kill it rather than wait() forever.
    if proc.poll() is None:
        proc.kill()
    proc.wait()
    return proc.returncode, box.get("out", b"")


def fetch_remote_head_sha(url: str, *, timeout: float = 10, max_bytes: int = 4096, run=_run_git) -> tuple[str | None, str]:
    if urlparse(url).hostname not in FETCH_HOST_ALLOWLIST:
        return None, "host not in allowlist"
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    code, out = run(["git", "ls-remote", url, "HEAD"], timeout=timeout, env=env, max_bytes=max_bytes)
    if code is None:
        return None, "unreachable (timeout or spawn error)"
    if len(out) > max_bytes:
        # Checked before the return code: an over-budget read means the child was
        # killed mid-write, so its exit status is a signal, not "success"/"failure".
        return None, "ls-remote output too large"
    if code != 0:
        return None, "git ls-remote failed"
    first = out.decode("utf-8", "replace").split("\n", 1)[0]
    sha = first.split("\t", 1)[0].strip()
    if not SHA_RE.match(sha):
        return None, "unexpected ls-remote output"
    return sha, ""


@dataclass(frozen=True)
class SourceStatus:
    id: str
    validation: str
    freshness: str
    last_checked: str = ""
    citing_leaves: tuple[str, ...] = ()
    detail: str = ""


@dataclass(frozen=True)
class RefStatus:
    leaf: str
    ref: str
    status: str


@dataclass
class CheckReport:
    sources: list[SourceStatus] = field(default_factory=list)
    refs: list[RefStatus] = field(default_factory=list)
    leaf_errors: list[tuple[str, str]] = field(default_factory=list)

    def failed(self) -> bool:
        if self.leaf_errors:
            return True
        if any(s.validation == "invalid" or s.freshness in ("stale", "unreachable") for s in self.sources):
            return True
        return any(r.status == "unresolved" for r in self.refs)


def check_sources(root: Path, *, fetch_upstream: bool, fetch=None) -> CheckReport:
    # Resolve the fetch seam from the module global at call time (not as a bound
    # default), so the CLI path — which omits `fetch` — honours a monkeypatched
    # `fetch_remote_head_sha` and fetch-mode is testable without network.
    if fetch is None:
        fetch = fetch_remote_head_sha
    registry = load_sources(root / "sources.yaml")
    by_source, by_leaf, leaf_errors = build_dependency_views(root, registry)
    report = CheckReport(leaf_errors=list(leaf_errors))
    # File-level registry errors (unparseable YAML, non-mapping document) live in
    # registry.errors under a key that is not a declared id — surface them so a
    # corrupt registry fails the check instead of yielding an empty, clean report.
    for key in sorted(set(registry.errors) - registry.declared_ids):
        report.sources.append(SourceStatus(key, "invalid", "unknown", "", (), "; ".join(registry.errors[key])))
    for sid in sorted(registry.declared_ids):
        citing = tuple(by_source.get(sid, []))
        if sid in registry.errors:
            report.sources.append(SourceStatus(sid, "invalid", "unknown", "", citing, "; ".join(registry.errors[sid])))
            continue
        record = registry.records[sid]
        if record.kind in REFERENCE_KINDS:
            report.sources.append(SourceStatus(sid, "valid", "not_applicable", record.last_checked, citing))
        elif not fetch_upstream:
            report.sources.append(SourceStatus(sid, "valid", "not_checked", record.last_checked, citing))
        else:
            remote, detail = fetch(record.url)
            if remote is None:
                report.sources.append(SourceStatus(sid, "valid", "unreachable", record.last_checked, citing, detail))
            elif remote == record.upstream_ref:
                report.sources.append(SourceStatus(sid, "valid", "fresh", record.last_checked, citing))
            else:
                report.sources.append(
                    SourceStatus(sid, "valid", "stale", record.last_checked, citing, f"upstream {remote[:8]} != pinned {(record.upstream_ref or '')[:8]}")
                )
    for leaf, ref_list in sorted(by_leaf.items()):
        for ref in ref_list:
            status = "resolved" if ref in registry.declared_ids else "unresolved"
            report.refs.append(RefStatus(leaf, ref, status))
    return report


@skills_group.group(name="sources")
def sources_group() -> None:
    """Skill source-provenance tooling."""


@sources_group.command(name="list")
@click.option("--root", type=click.Path(exists=True, file_okay=False), default="skills")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def sources_list_cmd(root: str, fmt: str) -> None:
    """List the source → leaf dependency tree (both directions)."""
    registry = load_sources(Path(root) / "sources.yaml")
    by_source, by_leaf, _ = build_dependency_views(Path(root), registry)

    def _render() -> None:
        click.echo("By source:")
        for sid in sorted(by_source):
            leaves = by_source[sid]
            click.echo(f"  {sid}: {', '.join(leaves) if leaves else '(unused)'}")
        click.echo("By leaf:")
        for leaf in sorted(by_leaf):
            click.echo(f"  {leaf}: {', '.join(by_leaf[leaf])}")

    emit(
        output_format=fmt,
        payload={
            "by_source": {sid: by_source[sid] for sid in sorted(by_source)},
            "by_leaf": {leaf: by_leaf[leaf] for leaf in sorted(by_leaf)},
        },
        render_text=_render,
    )


@sources_group.command(name="check")
@click.option("--root", type=click.Path(exists=True, file_okay=False), default="skills")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
@click.option("--fetch-upstream", is_flag=True, default=False, help="Compare pinned SHA against upstream HEAD (network).")
def sources_check_cmd(root: str, fmt: str, fetch_upstream: bool) -> None:
    """Validate the registry and (optionally) check upstream freshness."""
    report = check_sources(Path(root), fetch_upstream=fetch_upstream)

    def _render() -> None:
        for status in report.sources:
            line = f"{status.id}: validation={status.validation} freshness={status.freshness} last_checked={status.last_checked}"
            if status.citing_leaves:
                line += f" cited_by={', '.join(status.citing_leaves)}"
            if status.detail:
                line += f" ({status.detail})"
            click.echo(line)
        for ref in report.refs:
            if ref.status == "unresolved":
                click.echo(f"{ref.leaf}: unresolved-source-ref {ref.ref}")
        for leaf, error in report.leaf_errors:
            click.echo(f"{leaf}: invalid sources field ({error})")

    emit(
        output_format=fmt,
        payload={
            "sources": [
                {
                    "id": s.id, "validation": s.validation, "freshness": s.freshness,
                    "last_checked": s.last_checked, "citing_leaves": list(s.citing_leaves), "detail": s.detail,
                }
                for s in report.sources
            ],
            "refs": [{"leaf": r.leaf, "ref": r.ref, "status": r.status} for r in report.refs],
            "leaf_errors": [{"leaf": leaf, "error": error} for leaf, error in report.leaf_errors],
        },
        render_text=_render,
    )
    if report.failed():
        raise click.exceptions.Exit(1)
