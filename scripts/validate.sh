#!/usr/bin/env bash
# science-managed: shim for validate.sh (path convenience; not a managed artifact)
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec uv run --project "$here/../science" \
     science project artifacts exec validate.sh -- "$@"
