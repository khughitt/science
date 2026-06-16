r"""
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
"""

from __future__ import annotations

from collections.abc import Iterator
import os
from pathlib import Path
import re

from science_tool.entities import markdown_entity_kinds
from science_tool.entity_scan import iter_entity_markdown
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

# Reference/operational kinds NOT governed by the markdown policy table but
# still subject to id-prefix conformance. These must be every kind the static
# PREFIX_RULES covered that is absent from _BUILTIN_MARKDOWN_POLICIES — today
# that is concept, dataset, and spec. (paper IS in the policy table, so it is
# intentionally NOT listed here.) Dropping any of these silently reduces
# validation coverage in repos with concept:/dataset:/spec: records.
_EXTRA_PREFIX_KINDS = ("concept", "dataset", "spec")


def prefix_rules() -> dict[str, str]:
    kinds = set(markdown_entity_kinds()) | set(_EXTRA_PREFIX_KINDS)
    kinds -= {"research-question", "claim-registry"}  # singletons
    return {kind: f"{kind}:" for kind in sorted(kinds)}


PREFIX_RULES = prefix_rules()

QUOTE = "[\"']?"
FRONTMATTER = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def _result(severity: Severity, message: str) -> Result:
    return Result(severity, None, None, message, "id-prefixes", None)


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()


def _project_relative_parts(project_root: Path, path: Path) -> tuple[str, ...]:
    return path.relative_to(project_root).parts


def _extract_field(text: str, name: str) -> str | None:
    match = re.search(rf"^{name}:\s*{QUOTE}([^\"'\n]+){QUOTE}\s*$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


@Check(section="per-type id-prefix conformance...", order=19)
def check_id_prefixes(ctx: ValidateContext) -> Iterator[Result]:
    if os.environ.get("SCIENCE_VALIDATE_SKIP_ID_PREFIX"):
        return

    violations: list[str] = []
    for root in (ctx.project_root / "entities",):
        if not root.is_dir():
            continue
        for path in iter_entity_markdown(root):
            if "templates" in _project_relative_parts(ctx.project_root, path):
                continue
            content = ctx.read_text_cached(path)
            frontmatter = FRONTMATTER.match(content)
            if not frontmatter:
                continue

            raw_frontmatter = frontmatter.group(1)
            item_type = _extract_field(raw_frontmatter, "type")
            item_id = _extract_field(raw_frontmatter, "id")
            if not item_type or not item_id:
                continue

            expected = PREFIX_RULES.get(item_type)
            if expected is None:
                continue
            if not item_id.startswith(expected):
                violations.append(
                    f"{_display_path(ctx.project_root, path)}: type={item_type} but id={item_id} "
                    f"(expected prefix '{expected}')"
                )

    if violations:
        for violation in violations:
            yield _result(Severity.WARN, f"id-prefix mismatch: {violation}")
    else:
        yield _result(Severity.INFO, "  all type/id prefixes conform")
