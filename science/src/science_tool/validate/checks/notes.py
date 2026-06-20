r"""Port of validate.sh notes block.

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
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_NOTE_DIRS = (
    ("topics", "topic"),
    ("articles", "article"),
    ("questions", "question"),
    ("methods", "method"),
    ("datasets", "dataset"),
)
_REQUIRED_FIELDS = (
    "id",
    "type",
    "title",
    "status",
    "tags",
    "ontology_terms",
    "source_refs",
    "related",
    "created",
    "updated",
)
_COMMON_SECTIONS = ("## Summary", "## Thoughts", "## Connections to Project", "## Related")
_TOP_LEVEL_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*:")


def _result(severity: Severity, path: str | None, message: str) -> Result:
    return Result(severity, Path(path) if path is not None else None, None, message, "notes", None)


def _field_value(frontmatter: list[str], field: str) -> str | None:
    pattern = re.compile(rf"^{re.escape(field)}:[ \t]*['\"]?([^'\"]*)['\"]?[ \t]*$")
    for line in frontmatter:
        match = pattern.fullmatch(line)
        if match is not None:
            return match.group(1)
    return None


def _has_block_list(frontmatter: list[str], field: str) -> bool:
    in_field = False
    for line in frontmatter:
        if line.startswith(f"{field}:"):
            in_field = True
            continue
        if in_field and _TOP_LEVEL_KEY_RE.match(line):
            return False
        if in_field and re.match(r"^\s+-\s+", line):
            return True
    return False


def _datasets_is_list(frontmatter: list[str]) -> bool:
    for line in frontmatter:
        if re.match(r"^datasets:\s*(\[[^]]*\]|$)", line):
            return True
    return _has_block_list(frontmatter, "datasets")


@Check(section="notes...", order=16)
def check_notes(ctx: ValidateContext) -> Iterator[Result]:
    notes_dir = ctx.project_root / "notes"
    if not notes_dir.is_dir():
        return

    if not (notes_dir / "index.md").is_file():
        yield _result(Severity.WARN, "notes/index.md", "notes/index.md missing — add a notes coverage index")

    for directory, expected_type in _NOTE_DIRS:
        for path in sorted((notes_dir / directory).glob("*.md")):
            if not path.is_file():
                continue
            relative = path.relative_to(ctx.project_root).as_posix()
            yield _result(Severity.INFO, relative, f"Checking {relative}...")

            text = ctx.read_text_cached(path)
            lines = text.splitlines()
            if not lines or lines[0] != "---":
                yield _result(
                    Severity.WARN,
                    relative,
                    f"{relative} missing YAML frontmatter start marker (---)",
                )
                continue

            try:
                end_index = lines.index("---", 1)
            except ValueError:
                yield _result(
                    Severity.WARN,
                    relative,
                    f"{relative} missing YAML frontmatter end marker (---)",
                )
                continue

            frontmatter = lines[1:end_index]
            for field in _REQUIRED_FIELDS:
                if not any(line.startswith(f"{field}:") for line in frontmatter):
                    yield _result(
                        Severity.WARN,
                        relative,
                        f"{relative} frontmatter missing field: {field}",
                    )

            if any(line.startswith("datasets:") for line in frontmatter) and not _datasets_is_list(frontmatter):
                yield _result(Severity.WARN, relative, f"{relative} datasets field should be an array/list")

            parsed_type = _field_value(frontmatter, "type")
            if parsed_type and parsed_type != expected_type:
                yield _result(
                    Severity.WARN,
                    relative,
                    f"{relative} type '{parsed_type}' does not match expected '{expected_type}'",
                )

            parsed_id = _field_value(frontmatter, "id")
            if parsed_id and not parsed_id.startswith(f"{expected_type}:"):
                yield _result(
                    Severity.WARN,
                    relative,
                    f"{relative} id '{parsed_id}' should start with '{expected_type}:'",
                )

            for section in _COMMON_SECTIONS:
                if section not in text:
                    yield _result(Severity.WARN, relative, f"{relative} missing section: {section}")
