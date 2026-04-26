#!/usr/bin/env bash
# science-managed-artifact: validate.sh
# science-managed-version: 2026.04.26
# science-managed-source-sha256: f4596de3e9b2696066097621d5aef5606f247d144c5530409433427949c830d1
# === managed-artifact: hook infrastructure ===
declare -A SCIENCE_VALIDATE_HOOKS=()

register_validation_hook() {
  local hook_name="$1"
  local fn_name="$2"
  if [[ -z "${SCIENCE_VALIDATE_HOOKS[$hook_name]:-}" ]]; then
    SCIENCE_VALIDATE_HOOKS[$hook_name]="$fn_name"
  else
    SCIENCE_VALIDATE_HOOKS[$hook_name]+=" $fn_name"
  fi
}

dispatch_hook() {
  local hook_name="$1"
  local fns="${SCIENCE_VALIDATE_HOOKS[$hook_name]:-}"
  for fn in $fns; do
    "$fn"
  done
}

if [[ -f "validate.local.sh" ]]; then
  # shellcheck source=/dev/null
  source "validate.local.sh"
fi

# === canonical body ===
# validate.sh — Structural validation for Science research projects
# Returns non-zero on failure. Used as backpressure in research loops.
#
# Usage: bash validate.sh [--verbose]

# Note: intentionally NOT using set -e — we count errors and report at the end.
set -uo pipefail

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"

# Source .env for SCIENCE_TOOL_PATH and other project-local settings
if [ -f ".env" ]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
fi

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

resolve_science_tool() {
    if [ -n "${SCIENCE_TOOL_PATH:-}" ] && command -v uv &>/dev/null; then
        printf "uv run --project %s science-tool" "${SCIENCE_TOOL_PATH}"
        return
    fi

    if command -v uv &>/dev/null; then
        for candidate in \
            "./science-tool" \
            "../science/science-tool" \
            "../science-tool"
        do
            if [ -f "${candidate}/pyproject.toml" ]; then
                printf "uv run --project %s science-tool" "${candidate}"
                return
            fi
        done
    fi

    if command -v science-tool &>/dev/null; then
        printf "science-tool"
        return
    fi

    printf ""
}

SCIENCE_TOOL="${SCIENCE_TOOL:-$(resolve_science_tool)}"
if [ -z "$SCIENCE_TOOL" ]; then
    error "science-tool is required for task management, feedback, and graph workflows"
fi

# ─── Canonical path/profile resolution from science.yaml ───────────
DOC_DIR="doc"
CODE_DIR="code"
DATA_DIR="data"
SPECS_DIR="specs"
PAPERS_DIR="papers"
KNOWLEDGE_DIR="knowledge"
TASKS_DIR="tasks"
MODELS_DIR="models"
RESULTS_DIR="results"
PROFILE="research"
LOCAL_PROFILE="local"
LOCAL_PROFILE_DIR="$KNOWLEDGE_DIR/sources/$LOCAL_PROFILE"

if [ -f "science.yaml" ] && command -v python3 &>/dev/null; then
    PROFILE=$(python3 -c "
import yaml
with open('science.yaml') as f:
    d = yaml.safe_load(f) or {}
profile = str(d.get('profile') or 'research').strip() or 'research'
print(profile)
" 2>/dev/null || echo "research")

    case "$PROFILE" in
        research)
            CODE_DIR="code"
            ;;
        software)
            CODE_DIR="src"
            ;;
        *)
            CODE_DIR="code"
            ;;
    esac

    LOCAL_PROFILE=$(python3 -c "
import yaml
with open('science.yaml') as f:
    d = yaml.safe_load(f) or {}
profile = ((d.get('knowledge_profiles') or {}).get('local') or 'local')
print(str(profile).strip() or 'local')
" 2>/dev/null || echo "local")
    LOCAL_PROFILE_DIR="$KNOWLEDGE_DIR/sources/$LOCAL_PROFILE"
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
    for field in name created last_modified status summary profile layout_version; do
        if ! grep -q "^${field}:" science.yaml 2>/dev/null; then
            error "science.yaml missing required field: ${field}"
        else
            info "  ${field}: present"
        fi
    done

    knowledge_profile_status=$(python3 - <<'PYEOF'
import yaml

with open("science.yaml", encoding="utf-8") as handle:
    data = yaml.safe_load(handle) or {}

profiles = data.get("knowledge_profiles")
if not isinstance(profiles, dict):
    print("missing")
elif not isinstance(profiles.get("local"), str) or not profiles.get("local"):
    print("missing-local")
else:
    ontologies = data.get("ontologies")
    if ontologies is not None and not isinstance(ontologies, list):
        print("invalid-ontologies")
    else:
        print("ok")
PYEOF
2>/dev/null || echo "error")

    case "$knowledge_profile_status" in
        missing)
            error "science.yaml missing required knowledge_profiles section"
            ;;
        missing-local)
            error "science.yaml knowledge_profiles.local missing or empty"
            ;;
        invalid-ontologies)
            error "science.yaml ontologies must be a list"
            ;;
        error)
            error "science.yaml knowledge_profiles could not be parsed"
            ;;
        *)
            info "knowledge_profiles configured"
            ;;
    esac
fi

# ─── 2. Core structure ────────────────────────────────────────────
echo ""
echo "Checking directory structure..."

for dir in "$SPECS_DIR" "$DOC_DIR" "$KNOWLEDGE_DIR" "$TASKS_DIR" "$CODE_DIR"; do
    if [ ! -d "$dir" ]; then
        error "Required directory missing: ${dir}/"
    else
        info "${dir}/ exists"
    fi
done

if [ "$PROFILE" = "research" ]; then
    for dir in "$PAPERS_DIR" "$DATA_DIR" "$MODELS_DIR" "$RESULTS_DIR"; do
        if [ ! -d "$dir" ]; then
            error "Required directory missing: ${dir}/"
        else
            info "${dir}/ exists"
        fi
    done
fi

for file in CLAUDE.md AGENTS.md; do
    if [ ! -f "$file" ]; then
        error "Required file missing: ${file}"
    else
        info "${file} exists"
    fi
done

if [ "$PROFILE" = "research" ]; then
    if [ ! -f "RESEARCH_PLAN.md" ]; then
        warn "RESEARCH_PLAN.md not found (allowed if high-level planning is in README.md)"
    else
        info "RESEARCH_PLAN.md exists"
    fi
fi

if [ "$PROFILE" = "software" ] && [ -f "RESEARCH_PLAN.md" ]; then
    info "RESEARCH_PLAN.md exists"
fi

if [ -d "docs" ] && [ -d "$DOC_DIR" ]; then
    warn "Duplicate document roots detected: ${DOC_DIR}/ and docs/"
fi

if [ "$PROFILE" = "research" ]; then
    for legacy_dir in scripts notebooks workflow; do
        if [ -d "$legacy_dir" ]; then
            warn "Legacy top-level execution root detected: ${legacy_dir}/ — consolidate under ${CODE_DIR}/"
        fi
    done
    if [ -d "$CODE_DIR/pipelines" ]; then
        warn "Legacy workflow directory detected: ${CODE_DIR}/pipelines/ — use ${CODE_DIR}/workflows/"
    fi
fi

if [ "$PROFILE" = "software" ] && [ -d "code" ]; then
    warn "Software-profile project has top-level code/ — keep implementation in native roots such as src/"
fi

for legacy_ai_root in prompts templates; do
    if [ -d "$legacy_ai_root" ]; then
        warn "Legacy top-level AI artifact root detected: ${legacy_ai_root}/ — use .ai/ overrides only when needed"
    fi
done

# ─── 3. Research question ─────────────────────────────────────────
echo ""
echo "Checking research scope..."

if [ "$PROFILE" = "research" ] && [ ! -f "$SPECS_DIR/research-question.md" ]; then
    error "$SPECS_DIR/research-question.md not found — every project needs a research question"
fi

# ─── 4. Template conformance for background docs ──────────────────
echo ""
echo "Checking document structure..."

if [ -d "$DOC_DIR/background/topics" ]; then
    for doc_file in "$DOC_DIR/background/topics/"*.md; do
        [ -f "$doc_file" ] || continue
        info "Checking ${doc_file}..."

        for section in "## Summary" "## Key Concepts" "## Current State of Knowledge" "## Relevance to This Project" "## Key References"; do
            if ! grep -q "$section" "$doc_file" 2>/dev/null; then
                warn "${doc_file} missing section: ${section}"
            fi
        done
    done
fi

if [ -d "$DOC_DIR/background/papers" ]; then
    for summary_file in "$DOC_DIR/background/papers/"*.md; do
        [ -f "$summary_file" ] || continue
        info "Checking ${summary_file}..."

        for section in "## Key Contribution" "## Methods" "## Key Findings" "## Relevance"; do
            if ! grep -q "$section" "$summary_file" 2>/dev/null; then
                warn "${summary_file} missing section: ${section}"
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

        # If phase is present, value must be one of the enumerated values.
        # Absent is fine — defaults to `active` per spec.
        # Tolerates an optional trailing YAML comment (the template ships one).
        phase_value=$(sed -n "s/^phase:[[:space:]]*['\"]\\{0,1\\}\\([^'\"[:space:]]*\\)['\"]\\{0,1\\}[[:space:]]*\\(#.*\\)\\{0,1\\}\$/\\1/p" "$hyp_file" | head -n 1 || true)
        if [ -n "$phase_value" ] && [ "$phase_value" != "candidate" ] && [ "$phase_value" != "active" ]; then
            warn "${hyp_file} has invalid phase '${phase_value}' (must be 'candidate' or 'active')"
        fi
    done
fi

# ─── 6. Citation integrity ───────────────────────────────────────
echo ""
echo "Checking citations..."

if [ -f "$PAPERS_DIR/references.bib" ]; then
    # Collect all [@Key] citations across docs
    cited_keys=""
    if [ -d "$DOC_DIR" ]; then
        cited_keys=$(grep -roh '\[@[A-Za-z0-9_-]*\]' "$DOC_DIR/" 2>/dev/null \
            | sed 's/\[@//;s/\]//' | sort -u || true)
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
info "Paper summary structure is checked in $DOC_DIR/background/papers/"

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

if [ "$unverified_count" -gt 0 ]; then
    warn "${unverified_count} [UNVERIFIED] marker(s) found in documents"
fi

if [ "$needs_citation_count" -gt 0 ]; then
    warn "${needs_citation_count} [NEEDS CITATION] marker(s) found in documents"
fi

# ─── 9. Research gap analysis conformance ────────────────────────
echo ""
echo "Checking research gap analysis..."

for f in "$DOC_DIR/meta/next-steps-"*.md; do
    [ -f "$f" ] || continue
    for section in "Recent Progress" "Current State" "Coverage Gaps" "Recommended Next Actions"; do
        if ! grep -q "## $section" "$f"; then
            warn "Next-steps $f missing section: $section"
        fi
    done

    # Chain link resolution. Accept entity-id (meta:next-steps-YYYY-MM-DD)
    # or relative path (doc/meta/next-steps-YYYY-MM-DD.md). Absence is fine.
    # We deliberately do NOT parse `prior_analyses:` (block- or inline-list);
    # protein-landscape's variant is accepted by silence — broken-link
    # resolution for that field is a future cycle.
    prior_value=$(sed -n "s/^prior:[[:space:]]*['\"]\\{0,1\\}\\([^'\"]*\\)['\"]\\{0,1\\}[[:space:]]*$/\\1/p" "$f" | head -n 1 || true)
    if [ -n "$prior_value" ]; then
        candidate_path=""
        case "$prior_value" in
            meta:next-steps-*) candidate_path="$DOC_DIR/meta/${prior_value#meta:}.md" ;;
            *.md) candidate_path="$prior_value" ;;
            *) candidate_path="$prior_value" ;;
        esac
        if [ ! -f "$candidate_path" ]; then
            warn "${f}: broken prior link '${prior_value}' (resolved to ${candidate_path})"
        fi
    fi
done

if ! ls "$DOC_DIR/meta/next-steps-"*.md 1>/dev/null 2>&1; then
    info "No next-steps analysis found ($DOC_DIR/meta/next-steps-*.md)"
fi

# ─── 10. RESEARCH_PLAN conventions ───────────────────────────────
echo ""
echo "Checking research plan conventions..."

if [ -f "RESEARCH_PLAN.md" ]; then
    info "RESEARCH_PLAN.md exists"

    legacy_sections=(
        "## Current Priorities"
        "## Next Review Trigger"
    )
    for section in "${legacy_sections[@]}"; do
        if grep -q "$section" "RESEARCH_PLAN.md" 2>/dev/null; then
            warn "RESEARCH_PLAN.md contains legacy task-queue section '${section}' — migrate tasks to $TASKS_DIR/active.md via /science:tasks"
        fi
    done
elif [ "$PROFILE" = "research" ]; then
    info "No RESEARCH_PLAN.md — high-level planning may be in README.md or $DOC_DIR/plans/"
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
# Inspect both placements observed across downstream projects (audit §3.2):
#   doc/meta/pre-registration-<slug>.md  (natural-systems, protein-landscape, cbioportal)
#   doc/pre-registrations/<slug>.md      (mm30 canonical)
for f in "$DOC_DIR/meta/pre-registration-"*.md "$DOC_DIR/pre-registrations/"*.md; do
    [ -f "$f" ] || continue

    for section in "Hypotheses Under Test" "Expected Outcomes" "Decision Criteria" "Null Result Plan"; do
        if ! grep -q "## $section" "$f"; then
            warn "Pre-registration $f missing section: $section"
        fi
    done

    # Parse frontmatter type using the same recipe as the notes section.
    # Note: id-prefix conformance is handled by Plan #7 Task 6's PREFIX_RULES
    # table, not here, to avoid duplicate warnings on the same condition.
    pre_type=$(sed -n "s/^type:[[:space:]]*['\"]\\{0,1\\}\\([^'\"]*\\)['\"]\\{0,1\\}[[:space:]]*$/\\1/p" "$f" | head -n 1 || true)

    if [ "$pre_type" = "pre-registration" ]; then
        if ! grep -Eq '^committed:[[:space:]]' "$f" 2>/dev/null; then
            warn "${f} type 'pre-registration' should declare a 'committed:' date in frontmatter"
        fi
        if ! grep -Eq '^spec:[[:space:]]' "$f" 2>/dev/null; then
            warn "${f} type 'pre-registration' should declare a 'spec:' field (empty string is OK if no paired design doc)"
        fi
    fi
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

# ─── 11a. Synthesis frontmatter conformance ───────────────────────
# Gate on `type: synthesis` so legacy `type: report` synthesis files (mm30) and
# project-local `type: emergent-threads` files (protein-landscape) stay silent.
# The per-kind required-field warnings match the test-asserted strings below.
for f in "$DOC_DIR/reports/synthesis"/*.md "$DOC_DIR/reports/synthesis.md"; do
    [ -f "$f" ] || continue
    parsed_type=$(sed -n "s/^type:[[:space:]]*['\"]\\{0,1\\}\\([^'\"]*\\)['\"]\\{0,1\\}[[:space:]]*$/\\1/p" "$f" | head -n 1 || true)
    [ "$parsed_type" = "synthesis" ] || continue
    parsed_kind=$(sed -n "s/^report_kind:[[:space:]]*['\"]\\{0,1\\}\\([^'\"]*\\)['\"]\\{0,1\\}[[:space:]]*$/\\1/p" "$f" | head -n 1 || true)
    case "$parsed_kind" in
        hypothesis-synthesis|synthesis-rollup|emergent-threads) ;;
        "") warn "$f: missing report_kind" ;;
        *)  warn "$f: invalid report_kind '$parsed_kind'" ;;
    esac
    grep -q "^source_commit:" "$f" || warn "$f: missing source_commit"
    case "$parsed_kind" in
        synthesis-rollup)
            grep -q "^synthesized_from:" "$f" || warn "$f: missing synthesized_from"
            ;;
        hypothesis-synthesis)
            grep -q "^hypothesis:" "$f" || warn "$f: missing hypothesis"
            grep -q "^provenance_coverage:" "$f" || warn "$f: missing provenance_coverage"
            ;;
        emergent-threads)
            grep -q "^orphan_question_count:" "$f" || warn "$f: missing orphan_question_count"
            grep -q "^orphan_interpretation_count:" "$f" || warn "$f: missing orphan_interpretation_count"
            grep -q "^orphan_ids:" "$f" || warn "$f: missing orphan_ids"
            ;;
    esac
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

if [ -n "$SCIENCE_TOOL" ]; then
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
        warn "graph audit produced unparseable output (expected for fresh projects)"
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

# ─── 16. Frontmatter cross-reference validation ──────────────────
echo ""
echo "Checking frontmatter cross-references..."

xref_result=$(XREF_SPECS="$SPECS_DIR/hypotheses" XREF_DOC="$DOC_DIR" XREF_TASKS="$TASKS_DIR" XREF_ENTITIES="$LOCAL_PROFILE_DIR/entities.yaml" python3 << 'PYEOF'
import os, re

try:
    import yaml
except Exception:  # pragma: no cover - shell fallback
    yaml = None

QUOTE = "[\"']?"
NOT_QUOTE = "[^\"'\n]+"

def extract_frontmatter(path):
    try:
        with open(path) as f:
            content = f.read()
    except Exception:
        return None, []
    m = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not m:
        return None, []
    fm = m.group(1)
    id_match = re.search(r'^id:\s*' + QUOTE + '(' + NOT_QUOTE + ')' + QUOTE, fm, re.MULTILINE)
    doc_id = id_match.group(1).strip() if id_match else None
    related = []
    rel_match = re.search(r'^related:\s*\[(.*?)\]', fm, re.MULTILINE)
    if rel_match:
        items = rel_match.group(1)
        related = [s.strip().strip('"').strip("'") for s in items.split(',') if s.strip()]
    else:
        in_related = False
        for line in fm.split('\n'):
            if line.startswith('related:'):
                in_related = True
                continue
            if in_related:
                if line.startswith('  - '):
                    val = line[4:].strip().strip('"').strip("'")
                    if '{{' not in val and val:
                        related.append(val)
                elif not line.startswith(' '):
                    in_related = False
    return doc_id, related


def load_task_ids(tasks_dir):
    task_ids = set()
    if not os.path.isdir(tasks_dir):
        return task_ids

    task_paths = [os.path.join(tasks_dir, "active.md")]
    done_dir = os.path.join(tasks_dir, "done")
    if os.path.isdir(done_dir):
        for name in os.listdir(done_dir):
            if name.endswith(".md"):
                task_paths.append(os.path.join(done_dir, name))

    header_re = re.compile(r"^##\s+\[(\w+)\]")
    for path in task_paths:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as handle:
                for line in handle:
                    match = header_re.match(line)
                    if match:
                        task_ids.add(f"task:{match.group(1).lower()}")
        except Exception:
            continue
    return task_ids


def load_structured_ids(path):
    ids = set()
    if yaml is None or not os.path.isfile(path):
        return ids
    try:
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except Exception:
        return ids
    items = data.get("entities") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return ids
    for item in items:
        if not isinstance(item, dict):
            continue
        canonical_id = item.get("canonical_id")
        if isinstance(canonical_id, str) and canonical_id:
            ids.add(canonical_id)
    return ids

search_dirs = [os.environ['XREF_SPECS'], os.environ['XREF_DOC']]
all_ids = set()
refs_by_file = {}
for search_dir in search_dirs:
    if not os.path.isdir(search_dir):
        continue
    for root, dirs, files in os.walk(search_dir):
        for fname in files:
            if not fname.endswith('.md'):
                continue
            path = os.path.join(root, fname)
            doc_id, related = extract_frontmatter(path)
            if doc_id:
                all_ids.add(doc_id)
            if related:
                refs_by_file[path] = related

all_ids.update(load_task_ids(os.environ["XREF_TASKS"]))
all_ids.update(load_structured_ids(os.environ["XREF_ENTITIES"]))

broken = 0
for path, refs in refs_by_file.items():
    for ref in refs:
        if ref not in all_ids:
            print(f'BROKEN:{os.path.basename(path)}:{ref}')
            broken += 1
if broken == 0:
    print('OK')
PYEOF
2>/dev/null || echo "SKIP")

if [ "$xref_result" = "SKIP" ]; then
    info "Frontmatter cross-reference check skipped (python3 error)"
elif [ "$xref_result" = "OK" ]; then
    info "All frontmatter cross-references valid"
else
    echo "$xref_result" | while IFS=: read -r status filename ref; do
        if [ "$status" = "BROKEN" ]; then
            warn "Broken reference in $filename: related ID '$ref' not found"
        fi
    done
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
