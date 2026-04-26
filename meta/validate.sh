#!/usr/bin/env bash
# science-managed: shim for validate.sh (path convenience; not a managed artifact)
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec uv run --project "$here/../science-tool" \
     science-tool project artifacts exec validate.sh -- "$@"
