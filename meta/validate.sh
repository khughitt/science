#!/usr/bin/env bash
# science-managed-artifact: validate.sh
# science-managed-version: 2026.05.21.1
# science-managed-source-sha256: c12f881185d8359f3dbc1e4c3b166ce55475c22471a7c9739e088a07aab0618f
exec uv run science validate "$@"
