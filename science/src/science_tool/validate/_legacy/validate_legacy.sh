#!/usr/bin/env bash
# science-managed-artifact: validate.sh
# science-managed-version: 2026.05.12.1
# science-managed-source-sha256: ec986621008863cffd749c59e5478722ca7d6f3ea75b497a4d49b801639e0be1
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

SCIENCE_LEGACY_EFFECTIVE_DISPATCH_PHASE="${SCIENCE_LEGACY_DISPATCH_PHASE:-both}"
SCIENCE_LEGACY_EFFECTIVE_COUNT_POST_VALIDATION="${SCIENCE_LEGACY_COUNT_POST_VALIDATION:-1}"

if [[ -f "validate.local.sh" ]]; then
  # shellcheck source=/dev/null
  source "validate.local.sh"
fi

# Trap post_validation hooks so they fire on every exit path
# (success, failure, signal). Set AFTER sidecar source so any hooks
# the sidecar registered are visible.
dispatch_post_validation_trap() {
  if [[ "${SCIENCE_LEGACY_EFFECTIVE_COUNT_POST_VALIDATION}" = "0" ]]; then
    local exit_status=$?
    (dispatch_hook post_validation >/dev/null 2>/dev/null) || true
    return "$exit_status"
  else
    dispatch_hook post_validation
  fi
}

trap 'dispatch_post_validation_trap' EXIT

# === canonical body ===
# validate.sh — Structural validation for Science research projects
# Returns non-zero on failure. Used as backpressure in research loops.
#
# Usage: bash validate.sh [--verbose] [--strict]
#
# Flags:
#   --verbose   Print info-level lines for passing checks (default: only WARN/ERROR).
#   --strict    Emit WARN for advisory/structural checks that are otherwise silent
#               (e.g. missing optional sections in templates). Off by default so
#               the loop signal stays scoped to canonical violations.
#
# Env opt-outs (managed-artifact contract):
#   SCIENCE_VALIDATE_SKIP_DOTENV=1    skip auto-sourcing of project-local .env
#   SCIENCE_VALIDATE_SKIP_ID_PREFIX=1 skip per-type id-prefix conformance check

# Note: intentionally NOT using set -e — we count errors and report at the end.
set -uo pipefail

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"

# Source .env for SCIENCE_TOOL_PATH and other project-local settings.
# Set SCIENCE_VALIDATE_SKIP_DOTENV=1 to skip (e.g., when SCIENCE_TOOL_PATH is
# already exported in the developer's shell).
if [ -z "${SCIENCE_VALIDATE_SKIP_DOTENV:-}" ] && [ -f ".env" ]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
fi

VERBOSE=0
STRICT=0
ERRORS=0
WARNINGS=0

usage() {
    printf "Usage: bash validate.sh [--verbose] [--strict]\n"
}

for arg in "$@"; do
    case "$arg" in
        --verbose) VERBOSE=1 ;;
        --strict)  STRICT=1 ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf "ERROR: Unknown argument: %s\n" "$arg" >&2
            usage >&2
            exit 2
            ;;
    esac
done

red() {
    if [ "${SCIENCE_VALIDATE_NO_COLOR:-}" = "1" ]; then
        printf "%s\n" "$1"
    else
        printf "\033[31m%s\033[0m\n" "$1"
    fi
}

yellow() {
    if [ "${SCIENCE_VALIDATE_NO_COLOR:-}" = "1" ]; then
        printf "%s\n" "$1"
    else
        printf "\033[33m%s\033[0m\n" "$1"
    fi
}

green() {
    if [ "${SCIENCE_VALIDATE_NO_COLOR:-}" = "1" ]; then
        printf "%s\n" "$1"
    else
        printf "\033[32m%s\033[0m\n" "$1"
    fi
}

error() {
    red "ERROR: $1"
    ERRORS=$((ERRORS + 1))
}

warn() {
    yellow "WARN: $1"
    WARNINGS=$((WARNINGS + 1))
}

# Emit a WARN only when --strict is set. Used for advisory/structural checks
# (missing optional template sections, etc.) that should not contribute to the
# default loop signal but are useful when explicitly requested.
strict_warn() {
    if [ "$STRICT" -eq 1 ]; then
        warn "$1"
    fi
}

info() {
    if [ "$VERBOSE" -eq 1 ]; then
        echo "  $1"
    fi
}

if [ "${SCIENCE_LEGACY_SIDECAR_ONLY:-}" = "1" ]; then
    case "${SCIENCE_LEGACY_EFFECTIVE_DISPATCH_PHASE}" in
        pre_validation)
            dispatch_hook "pre_validation"
            ;;
        extra_checks)
            dispatch_hook "extra_checks"
            ;;
        both)
            dispatch_hook "pre_validation"
            dispatch_hook "extra_checks"
            ;;
        *)
            printf "ERROR: Unknown SCIENCE_LEGACY_DISPATCH_PHASE: %s\n" "${SCIENCE_LEGACY_EFFECTIVE_DISPATCH_PHASE}" >&2
            exit 2
            ;;
    esac
    exit 0
fi

resolve_science_tool() {
    if [ -n "${SCIENCE_TOOL_PATH:-}" ] && command -v uv &>/dev/null; then
        printf "uv run --project %s science" "${SCIENCE_TOOL_PATH}"
        return
    fi

    if command -v uv &>/dev/null; then
        for candidate in \
            "./science" \
            "../../../science/science" \
            "../science/science" \
            "../science"
        do
            if [ -f "${candidate}/pyproject.toml" ]; then
                printf "uv run --project %s science" "${candidate}"
                return
            fi
        done
    fi

    if command -v science &>/dev/null; then
        printf "science"
        return
    fi

    printf ""
}

SCIENCE_TOOL="${SCIENCE_TOOL:-$(resolve_science_tool)}"
if [ -z "$SCIENCE_TOOL" ]; then
    error "science is required for task management, feedback, and graph workflows"
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

# Hook point: pre_validation. Fires after helpers and banner are set up,
# before any canonical-section runs.
dispatch_hook "pre_validation"

# ─── 0. Tooling scaffold ──────────────────────────────────────────
# Self-contained bash check (no dependency on science itself, so this
# still fires when the scaffold is broken). Mirrors the static portion of
# `science health`'s tooling_scaffold check.
echo ""
echo "Checking tooling scaffold..."

if [ ! -f "pyproject.toml" ]; then
    warn "pyproject.toml missing — \`uv run science ...\` cannot resolve (fix: see commands/create-project.md, then \`uv add --dev --editable \"\$SCIENCE_TOOL_PATH\"\`)"
else
    info "pyproject.toml present"
    if ! grep -q 'science' pyproject.toml; then
        warn "pyproject.toml does not reference science (fix: \`uv add --dev --editable \"\$SCIENCE_TOOL_PATH\"\`)"
    else
        info "  science reference present"
    fi
fi

if [ ! -f ".env" ]; then
    warn ".env missing — SCIENCE_TOOL_PATH is unset (fix: create .env with \`SCIENCE_TOOL_PATH=<absolute-path-to-science>\`)"
elif ! grep -q '^SCIENCE_TOOL_PATH=' .env; then
    warn ".env exists but does not define SCIENCE_TOOL_PATH (fix: add \`SCIENCE_TOOL_PATH=<absolute-path>\` to .env)"
else
    info ".env defines SCIENCE_TOOL_PATH"
fi

# Smoke test: confirm `uv run science` resolves. Skipped if `uv` is
# absent (e.g. minimal CI image) or if the project hasn't been synced yet
# (no `.venv`) — the static checks above already cover the scaffold contract.
if [ -d ".venv" ] && command -v uv >/dev/null 2>&1; then
    if uv run --quiet science --help >/dev/null 2>&1; then
        info "  \`uv run science --help\` succeeds"
    else
        warn "\`uv run science --help\` failed — scaffold may be incomplete or stale (fix: run \`uv run science health\` for a structured diagnosis)"
    fi
fi

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
    # Additive check: knowledge_profiles.curated must be a list when present.
    # The legacy top-level `ontologies` list-shape check is preserved; removing
    # it is a separate downstream-migration cycle (see Plan #7 Task 3).
    curated = profiles.get("curated")
    ontologies = data.get("ontologies")
    if curated is not None and not isinstance(curated, list):
        print("invalid-curated")
    elif ontologies is not None and not isinstance(ontologies, list):
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
        invalid-curated)
            error "science.yaml knowledge_profiles.curated must be a list"
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

if [ -f "CLAUDE.md" ]; then
    claude_nonblank=$(grep -v '^[[:space:]]*$' CLAUDE.md 2>/dev/null || true)
    if [ "$claude_nonblank" != "@AGENTS.md" ]; then
        warn "CLAUDE.md should contain only @AGENTS.md"
    fi
    if awk '
        /^[[:space:]]*$/ { next }
        /^@core\// { found=1; next }
        /^@/ { next }
        { exit }
        END { exit found ? 0 : 1 }
    ' CLAUDE.md 2>/dev/null; then
        warn "CLAUDE.md contains legacy @core/* include(s) — keep core files as pointers from AGENTS.md"
    fi
fi

if [ -f "AGENTS.md" ]; then
    if awk '
        /^[[:space:]]*$/ { next }
        /^@core\// { found=1; next }
        /^@/ { next }
        { exit }
        END { exit found ? 0 : 1 }
    ' AGENTS.md 2>/dev/null; then
        warn "AGENTS.md contains legacy @core/* include(s) — use the Pointers section instead"
    fi
    if ! grep -q 'BEGIN: load-bearing-constraints' AGENTS.md 2>/dev/null || \
       ! grep -q 'END: load-bearing-constraints' AGENTS.md 2>/dev/null; then
        warn "AGENTS.md missing managed load-bearing-constraints markers — run /science:curate or refresh from templates/agents-md.md"
    fi
fi

if [ -f "core/overview.md" ]; then
    overview_lines=$(awk 'END { print NR }' "core/overview.md")
    overview_words=$(wc -w < "core/overview.md" | tr -d ' ')
    if [ "$overview_lines" -gt 150 ] || [ "$overview_words" -gt 1200 ]; then
        warn "core/overview.md is ${overview_lines} lines / ${overview_words} words; keep it under 150 lines / 1200 words and move evidence narratives into canonical docs"
    fi
fi

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
    # Sanction the agent-vs-human authoring split: docs/ that contains only
    # the docs/superpowers/ subtree (plans/specs authored via skills) is not
    # a duplicate-root violation. Any other content under docs/ still warns.
    # Adding a new sanctioned subtree requires a separate plan (see
    # docs/audits/downstream-project-conventions/synthesis.md §4.5).
    if find docs -type f ! -path 'docs/superpowers/*' -print -quit 2>/dev/null | grep -q .; then
        warn "Duplicate document roots detected: ${DOC_DIR}/ and docs/"
    fi
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

# ─── 5a. review_state.review_horizon_days shape validation ───────
# Pydantic rejects non-positive values at parse time; this check gives faster
# feedback during the edit/validate loop (before graph build runs).
for f in $(find "$DOC_DIR" "$SPECS_DIR" -name "*.md" -type f 2>/dev/null); do
    horizon=$(awk '
        /^---$/ {
            if (in_fm == 0) { in_fm=1; next }
            else { exit }
        }
        in_fm && /^review_state:/ { in_rs=1; next }
        in_fm && in_rs && /^[^ \t]/ { in_rs=0 }
        in_fm && in_rs && /^[ \t]+review_horizon_days:/ { print $2 }
    ' "$f" | head -1 | tr -d '"')
    if [ -n "$horizon" ] && [ "$horizon" -le 0 ] 2>/dev/null; then
        warn "$f: review_state.review_horizon_days must be positive (got $horizon)"
    fi
done

# ─── 6. Reference integrity ──────────────────────────────────────
echo ""
echo "Checking reference integrity..."

if [ -n "${SCIENCE_TOOL:-}" ]; then
    # `science refs check` exits 1 when broken refs exist; capture stdout
    # regardless of exit code, then fall back only if invocation produced
    # no output (binary missing, project not loadable, etc.).
    refs_json=$($SCIENCE_TOOL refs check --root . --format json 2>/dev/null) || true
    if [ -z "$refs_json" ]; then
        refs_json='{"summary":{"broken":0,"by_type":{}},"broken":[],"markers":[]}'
    fi
    while IFS=$'\t' read -r ref_type count; do
        [ -z "$ref_type" ] && continue
        if [ "$count" -gt 0 ]; then
            warn "${count} broken refs: ${ref_type}"
        fi
    done < <(printf '%s' "$refs_json" | python3 -c '
import json, sys
data = json.load(sys.stdin)
by_type = data.get("summary", {}).get("by_type", {})
for ref_type, count in sorted(by_type.items()):
    print(f"{ref_type}\t{count}")
')
    total=$(printf '%s' "$refs_json" | python3 -c 'import json, sys; print(json.load(sys.stdin).get("summary", {}).get("broken", 0))')
    if [ "$total" -eq 0 ]; then
        info "Reference integrity check complete (no broken refs)"
    fi
elif [ -f "$PAPERS_DIR/references.bib" ] && [ -d "$DOC_DIR" ]; then
    # Fallback when SCIENCE_TOOL is unavailable: minimal bash bibtex check.
    cited_keys=$(grep -roh '\[@[A-Za-z0-9_-]*\]' "$DOC_DIR/" 2>/dev/null \
        | sed 's/\[@//;s/\]//' | sort -u || true)
    for key in $cited_keys; do
        [ -z "$key" ] && continue
        if ! grep -q "@.*{${key}," "$PAPERS_DIR/references.bib" 2>/dev/null; then
            warn "Citation [@${key}] used in docs but not found in $PAPERS_DIR/references.bib"
        fi
    done
fi

# ─── 7. Paper summary template conformance ───────────────────────
echo ""
echo "Checking paper summaries..."
info "Paper summary structure is checked in $DOC_DIR/background/papers/"

# ─── 8. Unresolved annotation markers ──────────────────────────────
echo ""
echo "Checking for unresolved markers..."

if command -v science >/dev/null 2>&1 && [ -d "$DOC_DIR" ]; then
    SCIENCE_MARKERS_FLAGS=(--ignore-lifted)
    if [ "$STRICT" -eq 1 ]; then
        SCIENCE_MARKERS_FLAGS+=("--strict")
    fi
    markers_json=$(science markers scan --root . --format json "${SCIENCE_MARKERS_FLAGS[@]}" 2>/dev/null || echo '{"counts":{},"hits":[]}')
    while IFS=$'\t' read -r token count severity; do
        [ -z "$token" ] && continue
        if [ "$severity" = "warn" ] && [ "$count" -gt 0 ]; then
            warn "${count} [${token}] marker(s) found in documents"
        fi
    done < <(printf '%s' "$markers_json" | python3 -c '
import json, sys
data = json.load(sys.stdin)
sev = {}
for h in data.get("hits", []):
    sev.setdefault(h["token"], h["severity"])
for token, count in sorted(data.get("counts", {}).items()):
    s = sev.get(token, "warn")
    print(f"{token}\t{count}\t{s}")
')
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

# ─── 15. Task queue ──────────────────────────────────────────────
echo ""
echo "Checking task queue..."

if [ ! -f "$TASKS_DIR/active.md" ]; then
    warn "$TASKS_DIR/active.md not found (use /science:tasks to create)"
else
    info "$TASKS_DIR/active.md exists"
    task_check_result=$(XREF_TASKS="$TASKS_DIR" python3 <<'PYEOF' 2>/dev/null
import os
import re
from pathlib import Path

tasks_dir = Path(os.environ["XREF_TASKS"])
header_any = re.compile(r"^##\s+\[([^\]]+)\]\s+(.+)$")
header_valid = re.compile(r"^##\s+\[(t[0-9]{3,})\]\s+(.+)$")
task_ref = re.compile(r"\bt\d+[A-Za-z.]*\b")
local_parent = re.compile(r"^task:t[0-9]{3,}$")
required = ("aspects", "priority", "status", "created")
ref_fields = {"related", "blocked-by", "blocked_by", "parent"}


def display_path(path):
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def split_list_value(raw):
    value = raw.strip()
    if value.startswith("[") and value.endswith("]"):
        return [item.strip() for item in value[1:-1].split(",") if item.strip()]
    return [value] if value else []


paths = [tasks_dir / "active.md"]
done_dir = tasks_dir / "done"
if done_dir.is_dir():
    paths.extend(sorted(done_dir.glob("*.md")))

declared = set()
blocks = []
for path in paths:
    if not path.is_file():
        continue
    lines = path.read_text(encoding="utf-8").splitlines()
    current = None
    for line_no, line in enumerate(lines, start=1):
        any_match = header_any.match(line)
        if any_match:
            task_id = any_match.group(1)
            valid_match = header_valid.match(line)
            if valid_match is None:
                print(
                    f"ERROR:Invalid task id '{task_id}' in {display_path(path)}: task ids must match tNNN. "
                    "Use parent: task:t001 for fragments or subtasks."
                )
                current = None
                continue
            current = {"path": display_path(path), "line": line_no, "id": task_id, "lines": []}
            blocks.append(current)
            declared.add(task_id)
            continue
        if current is not None:
            current["lines"].append(line)

seen = {}
for task_id in sorted(declared):
    count = sum(1 for block in blocks if block["id"] == task_id)
    if count > 1:
        seen[task_id] = count
for task_id in sorted(seen):
    print(f"ERROR:duplicate task IDs in active.md: {task_id}")

for block in blocks:
    fields = {}
    for line in block["lines"]:
        match = re.match(r"^-\s+([\w-]+):\s*(.*)$", line)
        if match:
            fields[match.group(1)] = match.group(2).strip()
    for field in required:
        if field not in fields:
            print(f"ERROR:task {block['id']} missing required field: {field}")
    parent = fields.get("parent", "")
    if parent and not local_parent.match(parent):
        print(f"ERROR:task {block['id']} parent must be local task ref like task:t001")
    refs_to_check = []
    for field_name in ref_fields:
        for value in split_list_value(fields.get(field_name, "")):
            refs_to_check.append(value)
    for raw_ref in refs_to_check:
        if ":" in raw_ref:
            if not raw_ref.startswith("task:"):
                continue
            raw_ref = raw_ref.split(":", 1)[1]
        for match in task_ref.finditer(raw_ref):
            raw = match.group(0)
            if raw in declared:
                continue
            if re.fullmatch(r"t[0-9]{3,}", raw):
                print(f"ERROR:stale task ref '{raw}' in {block['path']}")
            elif raw.startswith("t"):
                print(f"ERROR:stale or invalid task ref '{raw}' in {block['path']}")

if blocks:
    print(f"OK:{len(blocks)}")
else:
    print("EMPTY:0")
PYEOF
) || task_check_result="SKIP"

    if [ "$task_check_result" = "SKIP" ]; then
        warn "Task queue check skipped (python3 error)"
    else
        task_count=0
        while IFS=: read -r status detail; do
            case "$status" in
                ERROR)
                    error "$detail"
                    ;;
                OK)
                    task_count="$detail"
                    ;;
                EMPTY)
                    task_count=0
                    ;;
            esac
        done <<< "$task_check_result"
        if [ "$task_count" = "0" ]; then
            info "  no tasks in active.md"
        else
            info "  ${task_count} task(s) validated"
        fi
    fi
fi

# ─── 17. Per-type id-prefix conformance ──────────────────────────
# Catches drift like `type: report` paired with `id: doc:...` (audit synthesis
# §9.3 / §5.3). Implemented as a warn (not error): existing downstream projects
# carry violations and an error here would block adoption on first managed
# update. Set SCIENCE_VALIDATE_SKIP_ID_PREFIX=1 to skip for projects mid-migration.
#
# Note: rows for `pre-registration` and `synthesis` are forward-compatible —
# they fire only after those type-promotions ship downstream (synthesis §3.2/§3.3).
# Until then, files using legacy shapes (e.g., `type: plan` for pre-regs,
# `type: report` with `id: report:synthesis-...`) are unaffected because the
# rule only fires when `type:` matches a row in PREFIX_RULES.
if [ -z "${SCIENCE_VALIDATE_SKIP_ID_PREFIX:-}" ]; then
    echo ""
    echo "Checking per-type id-prefix conformance..."
    id_prefix_result=$(IDP_DOC="$DOC_DIR" IDP_SPECS="$SPECS_DIR" python3 - <<'PYEOF'
import os
import re
from pathlib import Path

PREFIX_RULES = {
    "hypothesis": "hypothesis:",
    "question": "question:",
    "paper": "paper:",
    "interpretation": "interpretation:",
    "report": "report:",
    "discussion": "discussion:",
    "plan": "plan:",
    "spec": "spec:",
    "topic": "topic:",
    "concept": "concept:",
    "dataset": "dataset:",
    "method": "method:",
    "synthesis": "synthesis:",
    "pre-registration": "pre-registration:",
}

QUOTE = "[\"']?"


def extract_field(text, name):
    m = re.search(rf'^{name}:\s*{QUOTE}([^"\'\n]+){QUOTE}\s*$', text, re.MULTILINE)
    return m.group(1).strip() if m else None


violations = []
roots = [os.environ.get("IDP_DOC", "doc"), os.environ.get("IDP_SPECS", "specs")]
for root in roots:
    p = Path(root)
    if not p.is_dir():
        continue
    for md in p.rglob("*.md"):
        # Skip templates (mirrors Section 16 exclusion).
        if "templates" in md.parts:
            continue
        try:
            content = md.read_text(encoding="utf-8")
        except Exception:
            continue
        m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not m:
            continue
        fm = m.group(1)
        t = extract_field(fm, "type")
        i = extract_field(fm, "id")
        if not t or not i:
            continue
        if t not in PREFIX_RULES:
            continue
        expected = PREFIX_RULES[t]
        if not i.startswith(expected):
            violations.append(f"{md}: type={t} but id={i} (expected prefix '{expected}')")

for v in violations:
    print(v)
PYEOF
2>/dev/null || true)
    if [ -n "$id_prefix_result" ]; then
        while IFS= read -r line; do
            [ -z "$line" ] && continue
            warn "id-prefix mismatch: ${line}"
        done <<< "$id_prefix_result"
    else
        info "  all type/id prefixes conform"
    fi
fi

# ─── 16. Frontmatter cross-reference validation ──────────────────
echo ""
echo "Checking frontmatter cross-references..."

xref_result=$(XREF_SPECS="$SPECS_DIR" XREF_DOC="$DOC_DIR" XREF_TASKS="$TASKS_DIR" XREF_ENTITIES="$LOCAL_PROFILE_DIR/entities.yaml" XREF_TERMS="$LOCAL_PROFILE_DIR/terms.yaml" XREF_SCIENCE_YAML="science.yaml" python3 << 'PYEOF'
import os, re

try:
    import yaml
except Exception:  # pragma: no cover - shell fallback
    yaml = None

QUOTE = "[\"']?"
NOT_QUOTE = "[^\"'\n]+"
LOCAL_KINDS = {
    "assumption", "concept", "data-package", "dataset", "discussion", "experiment",
    "finding", "hypothesis", "inquiry", "interpretation", "mechanism", "method",
    "model", "observation", "paper", "pre-registration", "proposition", "question",
    "report", "source", "story", "task", "theme", "topic", "validation-report",
    "workflow", "workflow-run", "meta",
}

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


def load_project_ids(path):
    if yaml is None or not os.path.isfile(path):
        return set()
    try:
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except Exception:
        return set()
    ids = set()
    project_id = data.get("id")
    if isinstance(project_id, str) and project_id:
        ids.add(project_id)
    peers = data.get("peers")
    if isinstance(peers, list):
        for peer in peers:
            if isinstance(peer, dict) and isinstance(peer.get("id"), str):
                ids.add(peer["id"])
    return ids


def classify_ref(ref, project_ids):
    parts = ref.split(":")
    if re.fullmatch(r"t[0-9]{3,}", ref):
        return "local"
    if len(parts) == 2:
        first, _slug = parts
        if first in LOCAL_KINDS:
            return "local"
        if first in project_ids:
            return "legacy"
        return "local"
    if len(parts) == 3:
        project_id, _kind, _slug = parts
        if project_id in project_ids:
            return "cross"
        return "unknown-namespace"
    return "local"


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


def load_terms_ids(path):
    ids = set()
    if yaml is None or not os.path.isfile(path):
        return ids
    try:
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except Exception:
        return ids
    items = data.get("terms") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return ids
    for item in items:
        if not isinstance(item, dict):
            continue
        term_id = item.get("id") or item.get("canonical_id")
        if isinstance(term_id, str) and term_id:
            ids.add(term_id)
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
all_ids.update(load_terms_ids(os.environ["XREF_TERMS"]))
project_ids = load_project_ids(os.environ["XREF_SCIENCE_YAML"])


def emit(*parts):
    print("\t".join(str(part) for part in parts))


broken = 0
for path, refs in refs_by_file.items():
    for ref in refs:
        shape = classify_ref(ref, project_ids)
        if shape == "cross":
            continue
        if shape == "unknown-namespace":
            project_id = ref.split(":", 1)[0]
            emit("UNKNOWN_NAMESPACE", os.path.basename(path), project_id, "-", ref)
            broken += 1
            continue
        if shape == "legacy":
            project_id, slug = ref.split(":", 1)
            emit("LEGACY_PROJECT_REF", os.path.basename(path), project_id, slug, ref)
            continue
        if ref not in all_ids:
            emit("BROKEN", os.path.basename(path), ref, "-", ref)
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
    while IFS=$'\t' read -r status filename project_id slug raw; do
        if [ "$status" = "BROKEN" ]; then
            ref="$project_id"
            warn "Broken reference in $filename: related ID '$ref' not found"
        elif [ "$status" = "UNKNOWN_NAMESPACE" ]; then
            error "Unknown project namespace '${project_id}' in ref '${raw}'. Add it to science.yaml peers: or use a local ref."
        elif [ "$status" = "LEGACY_PROJECT_REF" ]; then
            warn "Legacy cross-project ref '${raw}' is missing an entity kind. Use '${project_id}:question:${slug}' or another explicit <project-id>:<kind>:<slug> ref."
        fi
    done < <(echo "$xref_result")
fi

# ─── 18. Prose lints ──────────────────────────────────────────────
echo ""
echo "Checking prose quality lints..."

if [ -n "${SCIENCE_TOOL:-}" ] && [ -d "$DOC_DIR" ]; then
    SCIENCE_PROSE_FLAGS=()
    if [ "$STRICT" -eq 1 ]; then
        SCIENCE_PROSE_FLAGS+=("--strict")
    fi
    prose_json=$($SCIENCE_TOOL prose lint --root . --format json "${SCIENCE_PROSE_FLAGS[@]}" 2>/dev/null || echo '{"counts":{},"hits":[]}')
    while IFS=$'\t' read -r check count severity; do
        [ -z "$check" ] && continue
        if [ "$severity" = "warn" ] && [ "$count" -gt 0 ]; then
            warn "${count} prose lint issue(s): ${check}"
        elif [ "$count" -gt 0 ]; then
            info "${count} prose lint issue(s): ${check} (use --strict to promote)"
        fi
    done < <(printf '%s' "$prose_json" | python3 -c '
import json, sys
data = json.load(sys.stdin)
sev = {}
for h in data.get("hits", []):
    sev.setdefault(h["check"], h["severity"])
for check, count in sorted(data.get("counts", {}).items()):
    s = sev.get(check, "warn")
    print(f"{check}\t{count}\t{s}")
')
fi

# ─── 19. Annotation drift ────────────────────────────────────────
echo ""
echo "Checking annotation drift..."

if [ -z "${SCIENCE_TOOL:-}" ]; then
    info "annotation drift skipped: SCIENCE_TOOL not available"
else
    # `science annotate verify` exits 1 when broken/parse-error issues
    # exist; capture stdout with `|| true` (Section 6 pattern) so a
    # nonzero exit doesn't truncate the assignment, then fall back to
    # an empty-summary stub only when stdout was empty (binary missing,
    # crash before output, etc.).
    annotate_json=$($SCIENCE_TOOL annotate verify --root . --format json --summary-only 2>/dev/null) || true
    if [ -z "$annotate_json" ]; then
        annotate_json='{"summary":{"broken":0,"degraded":0,"fuzzy":0,"source_missing":0,"parse_errors":0,"sidecars":0,"annotations":0,"superseded_skipped":0}}'
    fi

    # Extract counts via python3 (matches Section 6/18 pattern).
    annotate_counts=$(python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
s = data.get('summary', {})
print(f\"{s.get('broken', 0)} {s.get('degraded', 0)} {s.get('fuzzy', 0)} {s.get('source_missing', 0)} {s.get('parse_errors', 0)} {s.get('sidecars', 0)} {s.get('annotations', 0)}\")
" <<< "$annotate_json")
    read -r ANNOT_BROKEN ANNOT_DEGRADED ANNOT_FUZZY ANNOT_SRC_MISSING ANNOT_PARSE ANNOT_SIDECARS ANNOT_TOTAL <<< "$annotate_counts"

    if [ "$ANNOT_SIDECARS" = "0" ]; then
        info "no annotation sidecars (*.anno.trig) in this project"
    else
        if [ "$ANNOT_BROKEN" -gt 0 ]; then
            warn "${ANNOT_BROKEN} annotation(s) with broken selectors (run \`science annotate verify --apply --actor <you>\` to mark superseded)"
        fi
        if [ "$ANNOT_PARSE" -gt 0 ]; then
            warn "${ANNOT_PARSE} sidecar parse error(s)"
        fi
        if [ "$ANNOT_DEGRADED" -gt 0 ]; then
            strict_warn "${ANNOT_DEGRADED} annotation(s) with degraded selectors (anchors no longer match)"
        fi
        if [ "$ANNOT_FUZZY" -gt 0 ]; then
            strict_warn "${ANNOT_FUZZY} annotation(s) resolved via fuzzy match"
        fi
        if [ "$ANNOT_SRC_MISSING" -gt 0 ]; then
            strict_warn "${ANNOT_SRC_MISSING} annotation(s) point at missing source files"
        fi
        if [ "$ANNOT_BROKEN" = "0" ] && [ "$ANNOT_PARSE" = "0" ] && [ "$ANNOT_DEGRADED" = "0" ] && [ "$ANNOT_FUZZY" = "0" ] && [ "$ANNOT_SRC_MISSING" = "0" ]; then
            info "${ANNOT_TOTAL} annotation(s) across ${ANNOT_SIDECARS} sidecar(s); all selectors clean"
        fi
    fi
fi

# Hook point: extra_checks. Fires after all canonical sections complete,
# before the pass/fail summary. Use for project-specific structural checks.
dispatch_hook "extra_checks"

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
