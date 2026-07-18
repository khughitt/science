#!/usr/bin/env bash
# Design acceptance test 10 / §6.2: `science validate` exit code, result count, and
# error/warning counts must be unchanged by the curation_scope change on real
# downstream projects. Run once with the main toolkit and once with the branch toolkit.
set -euo pipefail

case "${1:-}" in
  baseline | branch) OUT="$1" ;;
  *)
    echo "usage: verify_downstream_scope.sh <baseline|branch>" >&2
    exit 2
    ;;
esac

# Toolkit package to run; defaults to the science/ dir that contains this script.
SCIENCE_PKG="${SCIENCE_PKG:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

MM=~/d/cancer/cancer-types/multiple-myeloma
NS=~/d/natural-systems
STAMP="/tmp/curation-scope-verify-$OUT.txt"
tmpdir="$(mktemp -d /tmp/curation-scope-verify.XXXXXX)"
trap 'rm -rf "$tmpdir"' EXIT
tmp_stamp="$tmpdir/stamp.txt"
: >"$tmp_stamp"

# A failed run must not leave a stamp that can compare equal to another failed run.
echo "INCOMPLETE $OUT" >"$STAMP"

for proj in "$MM" "$NS"; do
  name="$(basename "$proj")"
  json="$tmpdir/$name.json"
  set +e # A nonzero validate exit is comparison data, not a script failure.
  (
    cd "$SCIENCE_PKG"
    uv run --frozen science validate --format json --project-root "$proj"
  ) >"$json" 2>/dev/null
  code=$?
  set -e

  if ! counts=$(
    jq --slurp -er '
      if length != 1 then
        error("validate must emit exactly one top-level JSON value")
      else
        .[0]
      end
      | if (.results | type) != "array" then
        error(".results must be an array")
      elif (.summary.errors | type) != "number" then
        error(".summary.errors must be numeric")
      elif .summary.errors < 0 or .summary.errors != (.summary.errors | floor) then
        error(".summary.errors must be a nonnegative integer")
      elif (.summary.warnings | type) != "number" then
        error(".summary.warnings must be numeric")
      elif .summary.warnings < 0 or .summary.warnings != (.summary.warnings | floor) then
        error(".summary.warnings must be a nonnegative integer")
      else
        [(.results | length), .summary.errors, .summary.warnings] | @tsv
      end
    ' "$json"
  ); then
    echo "$name: validate output is not the expected JSON payload" >&2
    exit 1
  fi
  IFS=$'\t' read -r n e w <<<"$counts"
  echo "$name exit=$code results=$n errors=$e warnings=$w" | tee -a "$tmp_stamp"
done

mv "$tmp_stamp" "$STAMP"
echo "wrote $STAMP (toolkit: $SCIENCE_PKG)"
