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

# ─── Path resolution from science.yaml ─────────────────────────────
# Read paths: section if present, otherwise use defaults
DOC_DIR="doc"
CODE_DIR="code"
DATA_DIR="data"
SPECS_DIR="specs"
PAPERS_DIR="papers"
KNOWLEDGE_DIR="knowledge"
TASKS_DIR="tasks"
MODELS_DIR="models"

if [ -f "science.yaml" ] && command -v python3 &>/dev/null; then
    _resolve_path() {
        python3 -c "
import yaml
with open('science.yaml') as f:
    d = yaml.safe_load(f) or {}
p = (d.get('paths') or {}).get('${1}', '${2}')
print(p.rstrip('/'))
" 2>/dev/null || echo "$2"
    }
    DOC_DIR=$(_resolve_path doc_dir doc)
    CODE_DIR=$(_resolve_path code_dir code)
    DATA_DIR=$(_resolve_path data_dir data)
    SPECS_DIR=$(_resolve_path specs_dir specs)
    PAPERS_DIR=$(_resolve_path papers_dir papers)
    KNOWLEDGE_DIR=$(_resolve_path knowledge_dir knowledge)
    TASKS_DIR=$(_resolve_path tasks_dir tasks)
    MODELS_DIR=$(_resolve_path models_dir models)
fi

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

for dir in "$SPECS_DIR" "$DOC_DIR" "$PAPERS_DIR" "$DATA_DIR" "$CODE_DIR"; do
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

if [ ! -f "$SPECS_DIR/research-question.md" ]; then
    error "$SPECS_DIR/research-question.md not found — every project needs a research question"
fi

# ─── 4. Template conformance for background docs ──────────────────
echo ""
echo "Checking document structure..."

if [ -d "$DOC_DIR/background" ]; then
    for doc_file in "$DOC_DIR/background/"*.md; do
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

if [ -d "$SPECS_DIR/hypotheses" ]; then
    for hyp_file in "$SPECS_DIR/hypotheses/"h*.md; do
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

        # Check for status in YAML frontmatter or inline format
        if ! grep -q "^\- \*\*Status:\*\*" "$hyp_file" 2>/dev/null && \
           ! grep -q "^status:" "$hyp_file" 2>/dev/null; then
            warn "${hyp_file} missing Status field"
        fi
    done
fi

# ─── 6. Citation integrity ───────────────────────────────────────
echo ""
echo "Checking citations..."

if [ -f "$PAPERS_DIR/references.bib" ]; then
    # Collect all [@Key] citations across docs and summaries
    cited_keys=""
    if [ -d "$DOC_DIR" ]; then
        cited_keys=$(grep -roh '\[@[A-Za-z0-9_-]*\]' "$DOC_DIR/" 2>/dev/null \
            | sed 's/\[@//;s/\]//' | sort -u || true)
    fi
    if [ -d "$PAPERS_DIR/summaries" ]; then
        summary_keys=$(grep -roh '\[@[A-Za-z0-9_-]*\]' "$PAPERS_DIR/summaries/" 2>/dev/null \
            | sed 's/\[@//;s/\]//' | sort -u || true)
        if [ -n "$summary_keys" ]; then
            cited_keys=$(printf "%s\n%s" "$cited_keys" "$summary_keys" | sort -u)
        fi
    fi

    for key in $cited_keys; do
        [ -z "$key" ] && continue
        if ! grep -q "@.*{${key}," "$PAPERS_DIR/references.bib" 2>/dev/null; then
            warn "Citation [@${key}] used in docs but not found in $PAPERS_DIR/references.bib"
        fi
    done
    info "Citation check complete"
else
    # Check if any citations exist without a bib file
    has_citations=$(grep -rl '\[@' "$DOC_DIR/" 2>/dev/null | head -1 || true)
    if [ -n "$has_citations" ]; then
        warn "Citations found in docs but $PAPERS_DIR/references.bib does not exist"
    fi
fi

# ─── 7. Paper summary template conformance ───────────────────────
echo ""
echo "Checking paper summaries..."

if [ -d "$PAPERS_DIR/summaries" ]; then
    for summary_file in "$PAPERS_DIR/summaries/"*.md; do
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

if [ -d "$DOC_DIR" ]; then
    unverified_count=$(grep -rc '\[UNVERIFIED\]' "$DOC_DIR/" 2>/dev/null \
        | awk -F: '{s+=$2} END {print s+0}' || true)
    needs_citation_count=$(grep -rc '\[NEEDS CITATION\]' "$DOC_DIR/" 2>/dev/null \
        | awk -F: '{s+=$2} END {print s+0}' || true)
    # Ensure we have valid integers (awk always outputs via END, || true just suppresses pipefail)
    unverified_count=${unverified_count:-0}
    needs_citation_count=${needs_citation_count:-0}
fi

if [ -d "$PAPERS_DIR/summaries" ]; then
    uv_extra=$(grep -rc '\[UNVERIFIED\]' "$PAPERS_DIR/summaries/" 2>/dev/null \
        | awk -F: '{s+=$2} END {print s+0}' || true)
    nc_extra=$(grep -rc '\[NEEDS CITATION\]' "$PAPERS_DIR/summaries/" 2>/dev/null \
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

if [ -f "$DOC_DIR/10-research-gaps.md" ]; then
    info "Checking $DOC_DIR/10-research-gaps.md..."

    for section in \
        "## Scope Reviewed" \
        "## Coverage Map (Strong / Partial / Missing)" \
        "## High-Impact Gaps" \
        "## Recommended Next Tasks (Prioritized)" \
        "## Rationale and Evidence Links"; do
        if ! grep -q "$section" "$DOC_DIR/10-research-gaps.md" 2>/dev/null; then
            warn "$DOC_DIR/10-research-gaps.md missing section: ${section}"
        fi
    done

    if ! grep -Eq '\bP[123]\b' "$DOC_DIR/10-research-gaps.md" 2>/dev/null; then
        warn "$DOC_DIR/10-research-gaps.md has no explicit P1/P2/P3 priorities"
    fi
fi

# Legacy path — also check new path
if [ ! -f "$DOC_DIR/10-research-gaps.md" ]; then
    # Check for new-style next-steps files
    if ! ls "$DOC_DIR/meta/next-steps-"*.md 1>/dev/null 2>&1; then
        info "No gap analysis found ($DOC_DIR/10-research-gaps.md or $DOC_DIR/meta/next-steps-*.md)"
    fi
fi

# --- Next-steps documents (new format) ---
for f in "$DOC_DIR/meta/next-steps-"*.md; do
    [ -f "$f" ] || continue
    for section in "Recent Progress" "Current State" "Coverage Gaps" "Recommended Next Actions"; do
        if ! grep -q "## $section" "$f"; then
            warn "Next-steps $f missing section: $section"
        fi
    done
done

# ─── 10. RESEARCH_PLAN conventions ───────────────────────────────
echo ""
echo "Checking research plan conventions..."

if [ -f "RESEARCH_PLAN.md" ]; then
    info "RESEARCH_PLAN.md exists"

    # Check for legacy task-queue sections (should now live in tasks/active.md)
    legacy_sections=(
        "## Current Priorities"
        "## Next Review Trigger"
    )
    for section in "${legacy_sections[@]}"; do
        if grep -q "$section" "RESEARCH_PLAN.md" 2>/dev/null; then
            warn "RESEARCH_PLAN.md contains legacy task-queue section '${section}' — migrate tasks to $TASKS_DIR/active.md via /science:tasks"
        fi
    done
else
    warn "RESEARCH_PLAN.md not found (expected as high-level research strategy document)"
fi

# ─── 11. Discussion document conformance ──────────────────────────
echo ""
echo "Checking discussion documents..."

if [ -d "$DOC_DIR/discussions" ]; then
    for discussion_file in "$DOC_DIR/discussions/"*.md; do
        [ -f "$discussion_file" ] || continue
        # Skip comparison documents — validated separately below
        case "$discussion_file" in
            *comparison-*) continue ;;
        esac
        info "Checking ${discussion_file}..."

        for section in \
            "## Focus" \
            "## Current Position" \
            "## Critical Analysis" \
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

# --- Pre-registration documents ---
for f in "$DOC_DIR/meta/pre-registration-"*.md; do
    [ -f "$f" ] || continue
    for section in "Hypotheses Under Test" "Expected Outcomes" "Decision Criteria" "Null Result Plan"; do
        if ! grep -q "## $section" "$f"; then
            warn "Pre-registration $f missing section: $section"
        fi
    done
done

# --- Hypothesis comparison documents ---
for f in "$DOC_DIR/discussions/comparison-"*.md; do
    [ -f "$f" ] || continue
    for section in "Hypotheses Compared" "Evidence Inventory" "Discriminating Predictions" "Current Verdict"; do
        if ! grep -q "## $section" "$f"; then
            warn "Comparison $f missing section: $section"
        fi
    done
done

# --- Bias audit documents ---
for f in "$DOC_DIR/meta/bias-audit-"*.md; do
    [ -f "$f" ] || continue
    for section in "Cognitive Biases" "Methodological Biases" "Summary"; do
        if ! grep -q "## $section" "$f"; then
            warn "Bias audit $f missing section: $section"
        fi
    done
done

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

if [ -f "$KNOWLEDGE_DIR/graph.trig" ]; then
    # Resolve science-tool command
    # Priority: SCIENCE_TOOL_PATH env var → science-tool on PATH → uv run --with
    SCIENCE_TOOL=""
    if [ -n "${SCIENCE_TOOL_PATH:-}" ] && command -v uv &>/dev/null; then
        SCIENCE_TOOL="uv run --with ${SCIENCE_TOOL_PATH} science-tool"
    elif command -v science-tool &>/dev/null; then
        SCIENCE_TOOL="science-tool"
    fi

    if [ -z "$SCIENCE_TOOL" ]; then
        error "$KNOWLEDGE_DIR/graph.trig exists but science-tool is not available (set SCIENCE_TOOL_PATH or install science-tool)"
    else
        info "Using: ${SCIENCE_TOOL}"

        # 13a-d: Run graph validate (parseable, provenance, acyclicity, orphaned)
        validate_output=$($SCIENCE_TOOL graph validate --format json --path "$KNOWLEDGE_DIR/graph.trig" 2>&1) || true
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
        diff_output=$($SCIENCE_TOOL graph diff --format json --path "$KNOWLEDGE_DIR/graph.trig" 2>&1) || true
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
    info "No $KNOWLEDGE_DIR/graph.trig — skipping graph checks"
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

# ─── 15. Task queue ──────────────────────────────────────────────
echo ""
echo "Checking task queue..."

if [ ! -f "$TASKS_DIR/active.md" ]; then
    warn "$TASKS_DIR/active.md not found (use /science:tasks to create)"
else
    info "$TASKS_DIR/active.md exists"
    # Check for duplicate task IDs
    task_ids=$(grep -oP '^\#\# \[\Kt\d+' "$TASKS_DIR/active.md" 2>/dev/null || true)
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
            block=$(sed -n "/^## \[${tid}\]/,/^## \[t/p" "$TASKS_DIR/active.md" | head -n -1)
            if [ -z "$block" ]; then
                block=$(sed -n "/^## \[${tid}\]/,\$p" "$TASKS_DIR/active.md")
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
