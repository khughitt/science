#!/usr/bin/env bash
# validate.sh — Structural validation for Science research projects
# Returns non-zero on failure. Used as backpressure in research loops.
#
# Usage: bash validate.sh [--verbose]

# Note: intentionally NOT using set -e — we count errors and report at the end.
set -uo pipefail

VERBOSE="${1:-}"
ERRORS=0
WARNINGS=0

red()    { printf "\033[31m%s\033[0m\n" "$1"; }
yellow() { printf "\033[33m%s\033[0m\n" "$1"; }
green()  { printf "\033[32m%s\033[0m\n" "$1"; }

error() {
    red "ERROR: $1"
    ERRORS=$((ERRORS + 1))
}

warn() {
    yellow "WARN: $1"
    WARNINGS=$((WARNINGS + 1))
}

info() {
    if [ "$VERBOSE" = "--verbose" ]; then
        echo "  $1"
    fi
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Science Project Validation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ─── 1. Project manifest ───────────────────────────────────────────
echo ""
echo "Checking project manifest..."

if [ ! -f "science.yaml" ]; then
    error "science.yaml not found at project root"
else
    info "science.yaml exists"
    for field in name created last_modified status summary; do
        if ! grep -q "^${field}:" science.yaml 2>/dev/null; then
            error "science.yaml missing required field: ${field}"
        else
            info "  ${field}: present"
        fi
    done
fi

# ─── 2. Core structure ────────────────────────────────────────────
echo ""
echo "Checking directory structure..."

for dir in specs doc papers data code; do
    if [ ! -d "$dir" ]; then
        error "Required directory missing: ${dir}/"
    else
        info "${dir}/ exists"
    fi
done

for file in CLAUDE.md AGENTS.md RESEARCH_PLAN.md; do
    if [ ! -f "$file" ]; then
        error "Required file missing: ${file}"
    else
        info "${file} exists"
    fi
done

# ─── 3. Research question ─────────────────────────────────────────
echo ""
echo "Checking research scope..."

if [ ! -f "specs/research-question.md" ]; then
    error "specs/research-question.md not found — every project needs a research question"
fi

# ─── 4. Template conformance for background docs ──────────────────
echo ""
echo "Checking document structure..."

if [ -d "doc/background" ]; then
    for doc_file in doc/background/*.md; do
        [ -f "$doc_file" ] || continue
        info "Checking ${doc_file}..."

        for section in "## Summary" "## Key Concepts" "## Current State of Knowledge" "## Relevance to This Project" "## Key References"; do
            if ! grep -q "$section" "$doc_file" 2>/dev/null; then
                warn "${doc_file} missing section: ${section}"
            fi
        done
    done
fi

# ─── 5. Hypothesis completeness ──────────────────────────────────
echo ""
echo "Checking hypotheses..."

if [ -d "specs/hypotheses" ]; then
    for hyp_file in specs/hypotheses/h*.md; do
        [ -f "$hyp_file" ] || continue
        info "Checking ${hyp_file}..."

        if ! grep -q "## Falsifiability" "$hyp_file" 2>/dev/null; then
            error "${hyp_file} missing ## Falsifiability section"
        else
            # Check if the section has content (not just the header and comments)
            section_content=$(sed -n '/^## Falsifiability/,/^## /p' "$hyp_file" 2>/dev/null \
                | sed '1d;$d' | grep -v '^<!--' | grep -v '^\s*$' | head -1 || true)
            if [ -z "$section_content" ]; then
                warn "${hyp_file} has empty Falsifiability section"
            fi
        fi

        if ! grep -q "^\- \*\*Status:\*\*" "$hyp_file" 2>/dev/null; then
            warn "${hyp_file} missing Status field"
        fi
    done
fi

# ─── 6. Citation integrity ───────────────────────────────────────
echo ""
echo "Checking citations..."

if [ -f "papers/references.bib" ]; then
    # Collect all [@Key] citations across docs and summaries
    cited_keys=""
    if [ -d "doc" ]; then
        cited_keys=$(grep -roh '\[@[A-Za-z0-9_-]*\]' doc/ 2>/dev/null \
            | sed 's/\[@//;s/\]//' | sort -u || true)
    fi
    if [ -d "papers/summaries" ]; then
        summary_keys=$(grep -roh '\[@[A-Za-z0-9_-]*\]' papers/summaries/ 2>/dev/null \
            | sed 's/\[@//;s/\]//' | sort -u || true)
        if [ -n "$summary_keys" ]; then
            cited_keys=$(printf "%s\n%s" "$cited_keys" "$summary_keys" | sort -u)
        fi
    fi

    for key in $cited_keys; do
        [ -z "$key" ] && continue
        if ! grep -q "@.*{${key}," papers/references.bib 2>/dev/null; then
            warn "Citation [@${key}] used in docs but not found in papers/references.bib"
        fi
    done
    info "Citation check complete"
else
    # Check if any citations exist without a bib file
    has_citations=$(grep -rl '\[@' doc/ 2>/dev/null | head -1 || true)
    if [ -n "$has_citations" ]; then
        warn "Citations found in docs but papers/references.bib does not exist"
    fi
fi

# ─── 7. Paper summary template conformance ───────────────────────
echo ""
echo "Checking paper summaries..."

if [ -d "papers/summaries" ]; then
    for summary_file in papers/summaries/*.md; do
        [ -f "$summary_file" ] || continue
        info "Checking ${summary_file}..."

        for section in "## Key Contribution" "## Methods" "## Key Findings" "## Relevance"; do
            if ! grep -q "$section" "$summary_file" 2>/dev/null; then
                warn "${summary_file} missing section: ${section}"
            fi
        done
    done
fi

# ─── 8. Unverified/uncited markers ──────────────────────────────
echo ""
echo "Checking for unresolved markers..."

unverified_count=0
needs_citation_count=0

if [ -d "doc" ]; then
    unverified_count=$(grep -rc '\[UNVERIFIED\]' doc/ 2>/dev/null \
        | awk -F: '{s+=$2} END {print s+0}' || true)
    needs_citation_count=$(grep -rc '\[NEEDS CITATION\]' doc/ 2>/dev/null \
        | awk -F: '{s+=$2} END {print s+0}' || true)
    # Ensure we have valid integers (awk always outputs via END, || true just suppresses pipefail)
    unverified_count=${unverified_count:-0}
    needs_citation_count=${needs_citation_count:-0}
fi

if [ -d "papers/summaries" ]; then
    uv_extra=$(grep -rc '\[UNVERIFIED\]' papers/summaries/ 2>/dev/null \
        | awk -F: '{s+=$2} END {print s+0}' || true)
    nc_extra=$(grep -rc '\[NEEDS CITATION\]' papers/summaries/ 2>/dev/null \
        | awk -F: '{s+=$2} END {print s+0}' || true)
    uv_extra=${uv_extra:-0}
    nc_extra=${nc_extra:-0}
    unverified_count=$((unverified_count + uv_extra))
    needs_citation_count=$((needs_citation_count + nc_extra))
fi

if [ "$unverified_count" -gt 0 ]; then
    warn "${unverified_count} [UNVERIFIED] marker(s) found in documents"
fi

if [ "$needs_citation_count" -gt 0 ]; then
    warn "${needs_citation_count} [NEEDS CITATION] marker(s) found in documents"
fi

# ─── 9. Research gap analysis conformance ────────────────────────
echo ""
echo "Checking research gap analysis..."

if [ -f "doc/10-research-gaps.md" ]; then
    info "Checking doc/10-research-gaps.md..."

    for section in \
        "## Scope Reviewed" \
        "## Coverage Map (Strong / Partial / Missing)" \
        "## High-Impact Gaps" \
        "## Recommended Next Tasks (Prioritized)" \
        "## Rationale and Evidence Links"; do
        if ! grep -q "$section" "doc/10-research-gaps.md" 2>/dev/null; then
            warn "doc/10-research-gaps.md missing section: ${section}"
        fi
    done

    if ! grep -Eq '\bP[123]\b' "doc/10-research-gaps.md" 2>/dev/null; then
        warn "doc/10-research-gaps.md has no explicit P1/P2/P3 priorities"
    fi
fi

# ─── 10. RESEARCH_PLAN conventions ───────────────────────────────
echo ""
echo "Checking research plan conventions..."

if [ -f "RESEARCH_PLAN.md" ]; then
    required_sections=(
        "## Current Priorities"
        "## Priority Rationale"
        "## Deferred / Parked Tasks"
        "## Blockers and Dependencies"
        "## Next Review Trigger"
    )

    missing_sections=0
    for section in "${required_sections[@]}"; do
        if ! grep -q "$section" "RESEARCH_PLAN.md" 2>/dev/null; then
            missing_sections=$((missing_sections + 1))
            warn "RESEARCH_PLAN.md missing section: ${section}"
        fi
    done

    if [ "$missing_sections" -gt 0 ] && grep -q "^## Status" "RESEARCH_PLAN.md" 2>/dev/null; then
        warn "RESEARCH_PLAN.md appears to use legacy '## Status' format — run /science:next-steps to migrate"
    fi

    current_priorities=$(sed -n '/^## Current Priorities/,/^## /p' RESEARCH_PLAN.md 2>/dev/null \
        | sed '1d;$d' || true)
    active_priorities=$(printf "%s\n" "$current_priorities" | grep -E '^- ' \
        | grep -Ev '^- No active priorities yet\.?$' || true)
    priority_count=$(printf "%s\n" "$active_priorities" | grep -E '^- ' | wc -l | tr -d ' ' || true)
    priority_count=${priority_count:-0}

    if [ "$priority_count" -gt 12 ]; then
        warn "RESEARCH_PLAN.md has ${priority_count} active priority bullets; keep active queue compact"
    fi

    if [ "$priority_count" -gt 0 ] && ! printf "%s\n" "$active_priorities" | grep -Eq '\[P[123]\]' 2>/dev/null; then
        warn "RESEARCH_PLAN.md current priorities should use explicit [P1]/[P2]/[P3] markers"
    fi

    priority_rationale=$(sed -n '/^## Priority Rationale/,/^## /p' RESEARCH_PLAN.md 2>/dev/null \
        | sed '1d;$d' || true)
    if [ "$priority_count" -gt 0 ] && [ -z "$(printf "%s\n" "$priority_rationale" | grep -v '^\s*$' | head -1 || true)" ]; then
        warn "RESEARCH_PLAN.md has priorities but empty Priority Rationale section"
    fi

    if [ "$priority_count" -gt 0 ] && ! printf "%s\n" "$priority_rationale" | grep -Eq '\[@|doc/|papers/|specs/|knowledge/' 2>/dev/null; then
        warn "RESEARCH_PLAN.md Priority Rationale should reference evidence or project artifacts"
    fi
fi

# ─── 11. Discussion document conformance ──────────────────────────
echo ""
echo "Checking discussion documents..."

if [ -d "doc/discussions" ]; then
    for discussion_file in doc/discussions/*.md; do
        [ -f "$discussion_file" ] || continue
        info "Checking ${discussion_file}..."

        for section in \
            "## Focus" \
            "## Current Position" \
            "## Critical Analysis" \
            "## Alternative Explanations / Confounders" \
            "## Evidence Needed" \
            "## Prioritized Follow-Ups" \
            "## Synthesis"; do
            if ! grep -q "$section" "$discussion_file" 2>/dev/null; then
                warn "${discussion_file} missing section: ${section}"
            fi
        done

        if grep -Eq '^mode:\s*"?double-blind"?' "$discussion_file" 2>/dev/null; then
            for section in \
                "## Double-Blind Addendum (If mode = double-blind)" \
                "### Agent Independent Draft" \
                "### User Independent Draft" \
                "### Comparison" \
                "### Combined Synthesis"; do
                if ! grep -q "$section" "$discussion_file" 2>/dev/null; then
                    warn "${discussion_file} double-blind mode missing section: ${section}"
                fi
            done
        fi
    done
fi

# ─── 12. Notes conformance ─────────────────────────────────────────
echo ""
echo "Checking notes..."

if [ -d "notes" ]; then
    if [ ! -f "notes/index.md" ]; then
        warn "notes/index.md missing — add a notes coverage index"
    fi

    for note_file in notes/topics/*.md notes/articles/*.md notes/questions/*.md notes/methods/*.md notes/datasets/*.md; do
        [ -f "$note_file" ] || continue
        info "Checking ${note_file}..."

        # Require YAML frontmatter block
        first_line=$(head -n 1 "$note_file" 2>/dev/null || true)
        if [ "$first_line" != "---" ]; then
            warn "${note_file} missing YAML frontmatter start marker (---)"
            continue
        fi

        fm_end_line=$(awk 'NR>1 && $0=="---" {print NR; exit}' "$note_file" 2>/dev/null || true)
        if [ -z "${fm_end_line}" ]; then
            warn "${note_file} missing YAML frontmatter end marker (---)"
            continue
        fi

        frontmatter=$(awk 'NR>1 && $0=="---" {exit} NR>1 {print}' "$note_file" 2>/dev/null || true)

        # Required metadata fields for note interoperability
        for field in id type title status tags ontology_terms source_refs related created updated; do
            if ! printf "%s\n" "$frontmatter" | grep -Eq "^${field}:" 2>/dev/null; then
                warn "${note_file} frontmatter missing field: ${field}"
            fi
        done

        # Optional datasets field should be an array/list when present
        if printf "%s\n" "$frontmatter" | grep -Eq '^datasets:' 2>/dev/null; then
            if ! printf "%s\n" "$frontmatter" | grep -Eq '^datasets:\s*(\[[^]]*\]|$)' 2>/dev/null \
                && ! printf "%s\n" "$frontmatter" | awk '/^datasets:/ {in_ds=1; next} /^[A-Za-z_][A-Za-z0-9_]*:/ {in_ds=0} in_ds && /^\s*-\s+/{found=1} END{exit(found?0:1)}'; then
                warn "${note_file} datasets field should be an array/list"
            fi
        fi

        # type should match directory
        expected_type=""
        case "$note_file" in
            notes/topics/*) expected_type="topic" ;;
            notes/articles/*) expected_type="article" ;;
            notes/questions/*) expected_type="question" ;;
            notes/methods/*) expected_type="method" ;;
            notes/datasets/*) expected_type="dataset" ;;
        esac

        parsed_type=$(printf "%s\n" "$frontmatter" | sed -n "s/^type:[[:space:]]*['\"]\\{0,1\\}\\([^'\"]*\\)['\"]\\{0,1\\}[[:space:]]*$/\\1/p" | head -n 1 || true)
        if [ -n "$expected_type" ] && [ -n "$parsed_type" ] && [ "$parsed_type" != "$expected_type" ]; then
            warn "${note_file} type '${parsed_type}' does not match expected '${expected_type}'"
        fi

        parsed_id=$(printf "%s\n" "$frontmatter" | sed -n "s/^id:[[:space:]]*['\"]\\{0,1\\}\\([^'\"]*\\)['\"]\\{0,1\\}[[:space:]]*$/\\1/p" | head -n 1 || true)
        if [ -n "$parsed_id" ] && [ -n "$expected_type" ] && ! printf "%s\n" "$parsed_id" | grep -Eq "^${expected_type}:"; then
            warn "${note_file} id '${parsed_id}' should start with '${expected_type}:'"
        fi

        # Common section checks from notes organization guidance
        for section in "## Summary" "## Thoughts" "## Connections to Project" "## Related"; do
            if ! grep -q "$section" "$note_file" 2>/dev/null; then
                warn "${note_file} missing section: ${section}"
            fi
        done
    done
fi

# ─── 13. Knowledge graph checks ──────────────────────────────────
echo ""
echo "Checking knowledge graph..."

if [ -f "knowledge/graph.trig" ]; then
    # Resolve science-tool command
    # Priority: SCIENCE_TOOL_PATH env var → science-tool on PATH → uv run --with
    SCIENCE_TOOL=""
    if [ -n "${SCIENCE_TOOL_PATH:-}" ] && command -v uv &>/dev/null; then
        SCIENCE_TOOL="uv run --with ${SCIENCE_TOOL_PATH} science-tool"
    elif command -v science-tool &>/dev/null; then
        SCIENCE_TOOL="science-tool"
    fi

    if [ -z "$SCIENCE_TOOL" ]; then
        error "knowledge/graph.trig exists but science-tool is not available (set SCIENCE_TOOL_PATH or install science-tool)"
    else
        info "Using: ${SCIENCE_TOOL}"

        # 13a-d: Run graph validate (parseable, provenance, acyclicity, orphaned)
        validate_output=$($SCIENCE_TOOL graph validate --format json --path knowledge/graph.trig 2>&1) || true
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
        diff_output=$($SCIENCE_TOOL graph diff --format json --path knowledge/graph.trig 2>&1) || true
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
else
    info "No knowledge/graph.trig — skipping graph checks"
fi

# ─── 14. Inquiry validation ──────────────────────────────────────
if [ -f "knowledge/graph.trig" ] && [ -n "${SCIENCE_TOOL:-}" ]; then
    inquiry_list=$($SCIENCE_TOOL inquiry list --path knowledge/graph.trig --format json 2>/dev/null || echo "[]")
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
            validate_out=$($SCIENCE_TOOL inquiry validate "$slug" --path knowledge/graph.trig --format json 2>&1) || true

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

# ─── 15. Task queue ──────────────────────────────────────────────
echo ""
echo "Checking task queue..."

if [ ! -f "tasks/active.md" ]; then
    warn "tasks/active.md not found (use /science:tasks to create)"
else
    info "tasks/active.md exists"
    # Check for duplicate task IDs
    task_ids=$(grep -oP '^\#\# \[\Kt\d+' "tasks/active.md" 2>/dev/null || true)
    if [ -n "$task_ids" ]; then
        dupes=$(echo "$task_ids" | sort | uniq -d)
        if [ -n "$dupes" ]; then
            error "duplicate task IDs in active.md: ${dupes}"
        else
            info "  no duplicate task IDs"
        fi
        # Check each task has required fields
        while IFS= read -r tid; do
            # Extract the block for this task (from ## [tNNN] to next ## or EOF)
            block=$(sed -n "/^## \[${tid}\]/,/^## \[t/p" "tasks/active.md" | head -n -1)
            if [ -z "$block" ]; then
                block=$(sed -n "/^## \[${tid}\]/,\$p" "tasks/active.md")
            fi
            for field in type priority status created; do
                if ! echo "$block" | grep -qP "^- ${field}:" 2>/dev/null; then
                    error "task ${tid} missing required field: ${field}"
                fi
            done
        done <<< "$task_ids"
        info "  $(echo "$task_ids" | wc -l) task(s) validated"
    else
        info "  no tasks in active.md"
    fi
fi

# ─── Summary ─────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ "$ERRORS" -gt 0 ]; then
    red "FAILED: ${ERRORS} error(s), ${WARNINGS} warning(s)"
    exit 1
elif [ "$WARNINGS" -gt 0 ]; then
    yellow "PASSED with ${WARNINGS} warning(s)"
    exit 0
else
    green "PASSED: all checks clean"
    exit 0
fi
