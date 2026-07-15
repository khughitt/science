r"""Port of validate.sh knowledge graph and inquiry validation block.

echo "Checking knowledge graph..."

# Gate: when science is unavailable, $SCIENCE_TOOL is empty and the entire
# block below is skipped — so promoting "unparseable output" from warn to error
# below cannot fire spuriously on environments without the tool installed.
if [ -n "$SCIENCE_TOOL" ]; then
    peer_output=$($SCIENCE_TOOL peers check --project-root . 2>&1)
    peer_status=$?
    if [ "$peer_status" -eq 0 ]; then
        info "peer check: declared peers valid"
    else
        while IFS= read -r line; do
            if [ -n "$line" ]; then
                error "peer check failed: ${line}"
            fi
        done < <(printf "%s\n" "$peer_output")
    fi

    audit_output=$($SCIENCE_TOOL graph audit --project-root . --format json 2>/dev/null) || true
    if printf "%s" "$audit_output" | python3 -c "import sys,json; json.load(sys.stdin)" &>/dev/null; then
        audit_rows=$(printf "%s" "$audit_output" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['rows']))")
        if [ "$audit_rows" -eq 0 ]; then
            info "graph audit: all canonical references resolved"
        else
            while IFS= read -r row; do
                check=$(printf "%s" "$row" | python3 -c "import sys,json; print(json.load(sys.stdin)['check'])")
                status=$(printf "%s" "$row" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
                source=$(printf "%s" "$row" | python3 -c "import sys,json; print(json.load(sys.stdin)['source'])")
                field=$(printf "%s" "$row" | python3 -c "import sys,json; print(json.load(sys.stdin)['field'])")
                target=$(printf "%s" "$row" | python3 -c "import sys,json; print(json.load(sys.stdin)['target'])")
                details=$(printf "%s" "$row" | python3 -c "import sys,json; print(json.load(sys.stdin)['details'])")

                if [ "$status" = "fail" ]; then
                    error "graph audit: ${check} — ${source} ${field} -> ${target} (${details})"
                else
                    warn "graph audit: ${check} — ${source} ${field} -> ${target} (${details})"
                fi
            done < <(printf "%s" "$audit_output" | python3 -c "
import sys, json
for row in json.load(sys.stdin)['rows']:
    print(json.dumps(row))
")
        fi
    else
        error "graph audit produced unparseable output"
    fi

    if [ -f "$KNOWLEDGE_DIR/graph.trig" ]; then
        info "Using: ${SCIENCE_TOOL}"

        # 13a-d: Run graph validate (parseable, provenance, acyclicity, orphaned)
        validate_output=$($SCIENCE_TOOL graph validate --format json --path "$KNOWLEDGE_DIR/graph.trig" 2>/dev/null) || true
        if printf "%s" "$validate_output" | python3 -c "import sys,json; json.load(sys.stdin)" &>/dev/null; then
            while IFS= read -r row; do
                check=$(printf "%s" "$row" | python3 -c "import sys,json; print(json.load(sys.stdin)['check'])")
                status=$(printf "%s" "$row" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
                details=$(printf "%s" "$row" | python3 -c "import sys,json; print(json.load(sys.stdin)['details'])")

                if [ "$status" = "fail" ]; then
                    error "graph validate: ${check} — ${details}"
                elif [ "$status" = "warn" ]; then
                    warn "graph validate: ${check} — ${details}"
                else
                    info "graph validate: ${check} — ${details}"
                fi
            done < <(printf "%s" "$validate_output" | python3 -c "
import sys, json
for row in json.load(sys.stdin)['rows']:
    print(json.dumps(row))
")
        else
            error "graph validate produced unparseable output"
        fi

        # 13e: Graph-prose sync staleness
        diff_output=$($SCIENCE_TOOL graph diff --format json --path "$KNOWLEDGE_DIR/graph.trig" 2>/dev/null) || true
        if printf "%s" "$diff_output" | python3 -c "import sys,json; json.load(sys.stdin)" &>/dev/null; then
            stale_count=$(printf "%s" "$diff_output" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['rows']))")
            if [ "$stale_count" -gt 0 ]; then
                stale_files=$(printf "%s" "$diff_output" | python3 -c "
import sys, json
for row in json.load(sys.stdin)['rows']:
    print(f\"  {row['path']} ({row['reason']})\")
")
                warn "graph has ${stale_count} stale input file(s) — run /science:update-graph"
                if [ "$VERBOSE" = "--verbose" ]; then
                    printf "%s\n" "$stale_files"
                fi
            else
                info "graph-prose sync: all inputs up to date"
            fi
        else
            # diff may fail if no revision metadata exists yet (fresh graph)
            info "graph diff: no revision metadata (expected for new graphs)"
        fi
    fi
fi

# ─── 14. Inquiry validation ──────────────────────────────────────
if [ -f "$KNOWLEDGE_DIR/graph.trig" ] && [ -n "${SCIENCE_TOOL:-}" ]; then
    inquiry_list=$($SCIENCE_TOOL inquiry list --path "$KNOWLEDGE_DIR/graph.trig" --format json 2>/dev/null || echo "[]")
    inquiry_count=$(printf "%s" "$inquiry_list" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

    if [ "$inquiry_count" -gt 0 ]; then
        echo ""
        echo "Checking inquiries (${inquiry_count})..."

        inquiry_slugs=$(printf "%s" "$inquiry_list" | python3 -c "
import sys, json
for inq in json.load(sys.stdin):
    print(inq['slug'])
" 2>/dev/null)

        while IFS= read -r slug; do
            [ -z "$slug" ] && continue
            validate_out=$($SCIENCE_TOOL inquiry validate "$slug" --path "$KNOWLEDGE_DIR/graph.trig" --format json 2>&1) || true

            if printf "%s" "$validate_out" | python3 -c "import sys,json; json.load(sys.stdin)" &>/dev/null; then
                while IFS= read -r row; do
                    check=$(printf "%s" "$row" | python3 -c "import sys,json; print(json.load(sys.stdin)['check'])")
                    row_status=$(printf "%s" "$row" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
                    msg=$(printf "%s" "$row" | python3 -c "import sys,json; print(json.load(sys.stdin)['message'])")

                    if [ "$row_status" = "fail" ]; then
                        error "inquiry '${slug}': ${check} — ${msg}"
                    elif [ "$row_status" = "warn" ]; then
                        warn "inquiry '${slug}': ${check} — ${msg}"
                    else
                        if [ "$VERBOSE" = "--verbose" ]; then
                            info "inquiry '${slug}': ${check} — ${msg}"
                        fi
                    fi
                done < <(printf "%s" "$validate_out" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for row in data:
    print(json.dumps(row))
")
            else
                error "inquiry '${slug}' validation produced unparseable output"
            fi
        done <<< "$inquiry_slugs"
    fi
fi
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from science_tool.graph.materialize import materialization_audit
from science_tool.graph.store import (
    diff_graph_inputs_dataset,
    list_inquiries_dataset,
    validate_graph,
    validate_graph_dataset,
    validate_inquiry_dataset,
)
from science_tool.instruments import ValidationVerdict
from science_tool.peers_validate import PeerIssue, validate_peers
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def _result(severity: Severity, message: str) -> Result:
    return Result(severity, None, None, message, "graph", None)


def _graph_validation_results(verdict: ValidationVerdict[dict[str, str]]) -> Iterator[Result]:
    for row in verdict.rows:
        status = _status(row, context="graph validate", accepted={"fail", "warn", "pass"})
        check = row["check"]
        severity = Severity.ERROR if status == "fail" else Severity.WARN if status == "warn" else Severity.INFO
        yield _result(severity, f"graph validate: {check} — {row['details']}")


@Check(section="knowledge graph...", order=17)
def check_graph(ctx: ValidateContext) -> Iterator[Result]:
    peer_issues = validate_peers(ctx.project_root)
    yield from _peer_results(ctx, peer_issues)

    audit_verdict = materialization_audit(ctx.project_root)
    if audit_verdict.status == "unwired":
        yield _result(
            Severity.ERROR,
            f"graph audit: could not run ({audit_verdict.code}): {audit_verdict.reason}",
        )
        return
    audit_rows = audit_verdict.rows
    if not audit_rows:
        yield _result(Severity.INFO, "graph audit: all canonical references resolved")
    else:
        for row in audit_rows:
            if row["check"] == "identity_collision":
                # Owned by the dedicated forbidden-second-declaration conformance
                # check (deprecation-aware, design §B1/§B4). materialization_audit
                # still computes the row for has_failures (the build gate); we just
                # do not double-report it here with a contradictory severity.
                continue
            status = _status(row, context="graph audit", accepted={"fail", "warn"})
            severity = Severity.ERROR if status == "fail" else Severity.WARN
            yield _result(
                severity,
                f"graph audit: {row['check']} — {row['source']} {row['field']} -> {row['target']} ({row['details']})",
            )

    graph_path = ctx.project_root / "knowledge" / "graph.trig"
    if not graph_path.is_file():
        return

    try:
        dataset = ctx.graph_dataset(graph_path)
    except Exception:  # noqa: BLE001
        verdict = validate_graph(graph_path)
        if verdict.status == "unwired":
            yield _result(Severity.ERROR, f"graph validate: could not run ({verdict.code}): {verdict.reason}")
            return
        yield from _graph_validation_results(verdict)
        return

    verdict = validate_graph_dataset(dataset)
    if verdict.status == "unwired":
        yield _result(Severity.ERROR, f"graph validate: could not run ({verdict.code}): {verdict.reason}")
        return

    yield from _graph_validation_results(verdict)

    # This INFO branch used to be UNREACHABLE: read_revision_manifest never raised, it
    # returned {} -- so a manifest-less graph took the "N stale input file(s)" path or,
    # worse, the "all inputs up to date" path. The unwired status makes the case the
    # branch was always written for actually detectable.
    diff = diff_graph_inputs_dataset(dataset, graph_path=graph_path, mode="hybrid")
    if diff.status == "unwired":
        yield _result(
            Severity.INFO,
            f"graph diff: could not compare inputs ({diff.code}) — expected for a new graph",
        )
    else:
        diff_rows = diff.rows
        if diff_rows:
            for row in diff_rows:
                _status(row, context="graph diff", accepted={"stale"})
            yield _result(
                Severity.WARN,
                f"graph has {len(diff_rows)} stale input file(s) — run /science:update-graph",
            )
            if ctx.verbose:
                for row in diff_rows:
                    yield _result(Severity.INFO, f"  {row['path']} ({row['reason']})")
        else:
            yield _result(Severity.INFO, "graph-prose sync: all inputs up to date")

    inquiry_result = list_inquiries_dataset(dataset)
    if inquiry_result.status == "unwired":
        yield _result(Severity.INFO, f"inquiry checks skipped ({inquiry_result.code})")
        return
    inquiries = inquiry_result.rows
    if not inquiries:
        return

    yield _result(Severity.INFO, f"Checking inquiries ({len(inquiries)})...")
    for inquiry in inquiries:
        slug = inquiry["slug"]
        if not slug:
            continue
        inquiry_validation = validate_inquiry_dataset(dataset, slug)
        if inquiry_validation.status == "unwired":
            # The inquiry has no compiled boundary/flow subgraph. Its structural checks
            # did NOT run -- and they used to report four passes over an empty Graph().
            yield _result(
                Severity.WARN,
                f"inquiry '{slug}': structural checks did not run ({inquiry_validation.code})",
            )
            continue

        for row in inquiry_validation.rows:
            status = _status(row, context="inquiry validate", accepted={"fail", "warn", "pass", "skip", "info"})
            message = f"inquiry '{slug}': {row['check']} — {row['message']}"
            if status == "fail":
                yield _result(Severity.ERROR, message)
            elif status == "warn":
                yield _result(Severity.WARN, message)
            elif ctx.verbose:
                yield _result(Severity.INFO, message)


def _peer_results(ctx: ValidateContext, issues: list[PeerIssue]) -> Iterator[Result]:
    errors = [issue for issue in issues if issue.severity == "error"]
    if not errors:
        yield _result(Severity.INFO, "peer check: declared peers valid")
        return

    for issue in issues:
        yield _result(
            Severity.ERROR,
            f"peer check failed: {issue.severity.upper()} [{issue.peer_id}] {issue.kind.value}: {issue.detail}",
        )

    peer_count = _peer_count(ctx)
    warning_count = sum(1 for issue in issues if issue.severity == "warning")
    error_count = len(errors)
    yield _result(
        Severity.ERROR,
        f"peer check failed: failed: {peer_count} peers, {warning_count} warning, {error_count} error",
    )


def _peer_count(ctx: ValidateContext) -> int:
    peers = ctx.manifest.get("peers")
    return len(peers) if isinstance(peers, list) else 0


def _status(row: dict[str, Any], *, context: str, accepted: set[str]) -> str:
    status = row["status"]
    if not isinstance(status, str):
        raise TypeError(f"{context} returned non-string status: {status!r}")
    if status not in accepted:
        raise ValueError(f"{context} returned unknown status: {status}")
    return status
