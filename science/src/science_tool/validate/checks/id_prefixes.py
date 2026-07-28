r"""
# ─── 17. Per-kind id-prefix conformance ──────────────────────────
# Catches drift like `kind: report` paired with `id: doc:...` (audit synthesis
# §9.3 / §5.3). Implemented as a warn (not error): existing downstream projects
# carry violations and an error here would block adoption on first managed
# update. Set SCIENCE_VALIDATE_SKIP_ID_PREFIX=1 to skip for projects mid-migration.
#
# Note: rows for `pre-registration` and `synthesis` are forward-compatible —
# they fire only after those kind-promotions ship downstream (synthesis §3.2/§3.3).
# Until then, files using older shapes (e.g., `kind: plan` for pre-regs,
# `kind: report` with `id: report:synthesis-...`) are unaffected because the
# rule only fires when `kind:` matches a row in PREFIX_RULES.
if [ -z "${SCIENCE_VALIDATE_SKIP_ID_PREFIX:-}" ]; then
    echo ""
    echo "Checking per-kind id-prefix conformance..."
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
        t = extract_field(fm, "kind")
        i = extract_field(fm, "id")
        if not t or not i:
            continue
        if t not in PREFIX_RULES:
            continue
        expected = PREFIX_RULES[t]
        if not i.startswith(expected):
            violations.append(f"{md}: kind={t} but id={i} (expected prefix '{expected}')")

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
        info "  all kind/id prefixes conform"
    fi
fi
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.entities import markdown_entity_kinds
from science_tool.entity_scan import iter_entity_markdown
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

SECTION, RULES = declare_validation_rules(
    section_id="id-prefixes",
    section_title="id prefixes",
    section_order=123,
    rule_ids=("id-prefixes.check",),
    severities=frozenset({"error", "warn", "info"}),
)


def prefix_rules() -> dict[str, str]:
    # Every id-prefixed kind is a markdown policy kind: concept, dataset, and (as of
    # S3a) spec all carry a home/strategy and appear in markdown_entity_kinds(). There
    # is no non-policy fallback set -- the policy table is the single authority.
    kinds = set(markdown_entity_kinds())
    kinds -= {"research-question", "claim-registry"}  # singletons
    return {kind: f"{kind}:" for kind in sorted(kinds)}


PREFIX_RULES = prefix_rules()

QUOTE = "[\"']?"
FRONTMATTER = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def _result(
    severity: Severity,
    message: str,
    *,
    key: list[str],
) -> CheckObservation:
    return validation_observation(
        severity=severity,
        path=None,
        line=None,
        message=message,
        rule=RULES["id-prefixes.check"],
        task=None,
        qualifiers={"key": key},
    )


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


@Check(section=SECTION, order=19, producer_id="validate.id-prefixes", rules=tuple(RULES.values()))
def check_id_prefixes(ctx: ValidateContext) -> Iterator[CheckObservation]:
    if os.environ.get("SCIENCE_VALIDATE_SKIP_ID_PREFIX"):
        return

    violations: list[tuple[str, str, str]] = []
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
            item_type = _extract_field(raw_frontmatter, "kind")
            item_id = _extract_field(raw_frontmatter, "id")
            if not item_type or not item_id:
                continue

            expected = PREFIX_RULES.get(item_type)
            if expected is None:
                continue
            if not item_id.startswith(expected):
                display_path = _display_path(ctx.project_root, path)
                violations.append(
                    (
                        display_path,
                        item_type,
                        f"{display_path}: kind={item_type} but id={item_id} (expected prefix '{expected}')",
                    )
                )

    if violations:
        for path, item_type, violation in violations:
            yield _result(
                Severity.WARN,
                f"id-prefix mismatch: {violation}",
                key=[path, item_type],
            )
    else:
        yield _result(
            Severity.INFO,
            "  all kind/id prefixes conform",
            key=["summary"],
        )
