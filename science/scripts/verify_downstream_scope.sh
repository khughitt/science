#!/usr/bin/env bash
# Design acceptance test 10 / §6.2: `science validate` exit code, result count, and
# error/warning counts must be unchanged by the curation_scope change on real
# downstream projects. Run once with the main toolkit and once with the branch toolkit.
set -euo pipefail

# Toolkit package to run; defaults to the science/ dir that contains this script.
SCIENCE_PKG="${SCIENCE_PKG:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

MM=~/d/cancer/cancer-types/multiple-myeloma
NS=~/d/natural-systems
OUT="${1:?usage: verify_downstream_scope.sh <baseline|branch>}"
STAMP="/tmp/curation-scope-verify-$OUT.txt"
: > "$STAMP"

for proj in "$MM" "$NS"; do
  name="$(basename "$proj")"
  json="/tmp/$name-$OUT.json"
  set +e # A nonzero validate exit is comparison data, not a script failure.
  (
    cd "$SCIENCE_PKG"
    uv run --frozen science validate --format json --project-root "$proj"
  ) >"$json" 2>/dev/null
  code=$?
  set -e

  n=$(jq -er '.results | length' "$json" 2>/dev/null || echo PARSE_ERR)
  e=$(jq -er '.summary.errors' "$json" 2>/dev/null || echo PARSE_ERR)
  w=$(jq -er '.summary.warnings' "$json" 2>/dev/null || echo PARSE_ERR)
  echo "$name exit=$code results=$n errors=$e warnings=$w" | tee -a "$STAMP"
done

echo "wrote $STAMP (toolkit: $SCIENCE_PKG)"
