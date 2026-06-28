# Porting `validate.local.sh` to `validate_local.py`

This guide covers porting project-local validation hooks from the deprecated
`validate.local.sh` sidecar to the Python `validate_local.py` sidecar imported
by `science validate`.

The managed `validate.sh` artifact is now a small shim that delegates to
`science validate`. `validate.local.sh` is no longer executed by managed
validation; its presence is reported as an error so projects finish the
migration explicitly. Treat `validate_local.py` as the sidecar shape for new
work. When both `validate_local.py` and `validate.local.sh` exist in a project,
the Python sidecar can still run, but the stale bash sidecar still produces the
removal error until `validate.local.sh` is deleted or renamed.

For the durable validator contract, see
[`science validate`](../conventions/validate.md).

## Worked Example: `health/meta`

The canonical example is `~/d/health/meta/validate.local.sh`, committed on
2026-05-19. It registers one `extra_checks` hook for
`task:t024`, enforcing the `reviews-are-not-evidence` guardrail:

- provenance records pointing at `status: background` papers must mark the
  source as review-typed and set `evidence_tier: background`;
- `evidence_refs:` blocks in themes, synthesis reports, and hypotheses must not
  cite background review papers directly.

The old sidecar is a bash function that mostly shells into Python, then converts
`WARN:` and `INFO:` text prefixes back into validator messages.

```bash
check_reviews_are_not_evidence_guardrail() {
    echo ""
    echo "Checking reviews-are-not-evidence guardrail (t024)..."

    if [ ! -d "doc/papers" ]; then
        info "doc/papers/ not present; guardrail checks skipped"
        return
    fi

    local output
    output=$(python3 - <<'PYEOF'
import re
import sys
from pathlib import Path

bg_papers = set()
papers_dir = Path("doc/papers")
for p in papers_dir.glob("*.md"):
    text = p.read_text()
    # parse frontmatter, collect status: background papers

violations = []
# scan doc/provenance/*.yaml and evidence_refs blocks

for v in violations:
    print(v)

if not violations:
    print("INFO:0 reviews-are-not-evidence violations")
PYEOF
)

    while IFS= read -r line; do
        [ -z "$line" ] && continue
        case "$line" in
            WARN:*) warn "${line#WARN:}" ;;
            INFO:*) info "${line#INFO:}" ;;
            *)      info "$line" ;;
        esac
    done <<< "$output"
}

register_validation_hook "extra_checks" "check_reviews_are_not_evidence_guardrail"
```

In `validate_local.py`, the hook returns structured `Result` objects directly.
There is no subprocess, no heredoc, no string prefix protocol, and no ANSI
formatting in the sidecar.

```python
import re
from collections.abc import Iterable
from pathlib import Path

from science_tool.validate import Result, Severity, ValidateContext, hook

RULE = "reviews-are-not-evidence"
TASK = "task:t024"
REF_RE = re.compile(r"(?:paper|cite):([A-Za-z0-9_]+)")
EVIDENCE_REFS_RE = re.compile(r"(?m)^evidence_refs:\s*\n((?:[ \t]+-.*(?:\n|$))+)")


@hook("extra_checks")
def check_reviews_are_not_evidence_guardrail(ctx: ValidateContext) -> Iterable[Result]:
    if not ctx.papers_dir.is_dir():
        yield _info(Path("doc/papers"), "doc/papers/ not present; guardrail checks skipped")
        return

    background_papers = {
        path.stem
        for path in ctx.papers_dir.glob("*.md")
        if ctx.frontmatter(path).get("status") == "background"
    }
    if not background_papers:
        yield _info(
            Path("doc/papers"),
            "no status: background papers under doc/papers/; guardrail checks pass",
        )
        return

    emitted = False
    for result in _check_provenance(ctx, background_papers):
        emitted = True
        yield result
    for result in _check_evidence_refs(ctx, background_papers):
        emitted = True
        yield result
    if not emitted:
        yield _info(None, f"{len(background_papers)} status: background paper(s); 0 violations")


def _check_provenance(ctx: ValidateContext, background_papers: set[str]) -> Iterable[Result]:
    provenance_dir = ctx.doc_dir / "provenance"
    if not provenance_dir.exists():
        return
    for yaml_path in sorted(provenance_dir.glob("*.yaml")):
        record = ctx.read_yaml(yaml_path)
        if not isinstance(record, dict):
            continue
        source_ref = str(record.get("source_ref", ""))
        if not source_ref.startswith("paper:"):
            continue
        if source_ref.removeprefix("paper:") not in background_papers:
            continue
        if record.get("review_typed_source") is not True:
            yield _warn(yaml_path, f"{source_ref} must set review_typed_source: true")
        if record.get("evidence_tier") != "background":
            yield _warn(yaml_path, f"{source_ref} must set evidence_tier: background")


def _check_evidence_refs(ctx: ValidateContext, background_papers: set[str]) -> Iterable[Result]:
    roots = (ctx.doc_dir / "themes", ctx.doc_dir / "reports/synthesis", ctx.specs_dir / "hypotheses")
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.md")):
            for block in EVIDENCE_REFS_RE.findall(ctx.read_text_cached(path)):
                for key in sorted({match.group(1) for match in REF_RE.finditer(block)}):
                    if key in background_papers:
                        yield _warn(path, f"evidence_refs cites paper:{key} (status: background)")


def _info(path: Path | None, message: str) -> Result:
    return Result(Severity.INFO, path, None, message, RULE, TASK)


def _warn(path: Path, message: str) -> Result:
    return Result(Severity.WARN, path, None, message, RULE, TASK)
```

This is the same check in roughly half the size: the bash sidecar was about 145
lines, including an embedded Python program and text-prefix adapter; the Python
sidecar is about 80 lines of validator code plus imports and constants.

## Cookbook

### Register Hooks With `@hook`

Replace `register_validation_hook "extra_checks" "my_check"` with a decorated
function:

```python
from science_tool.validate import Result, Severity, hook


@hook("extra_checks")
def my_check(ctx):
    return [Result(Severity.INFO, None, None, "my_check ran", "my-rule", None)]
```

Valid hook names are `pre_validation`, `extra_checks`, and `post_validation`.
Hook functions receive a `ValidateContext` and return an iterable of `Result`
objects.

`post_validation` has one current caveat: the runner dispatches Python
`post_validation` hooks in a `finally` block and discards returned `Result`
objects. Use `post_validation` for cleanup or other side effects. Do not rely on
returned WARN, ERROR, or INFO results being included in `science validate`
output unless the runner behavior changes.

### Stale Bash Sidecars

Current `science validate` does not source or execute `validate.local.sh`.
If the file exists, validation reports an error pointing back to this guide.
That error is independent of `validate_local.py`: a port is not complete until
the stale bash sidecar is removed or renamed.

Set `SCIENCE_VALIDATE_DISABLE_SIDECAR=1` only when you intentionally need to
skip project-local sidecar discovery during troubleshooting or tests. Do not
use it as a migration strategy; it skips `validate_local.py` too.

During a port, replace bash helper calls and counter mutations with returned
`Result` objects from Python hooks.

### Environment Variables

Most old sidecars used environment variables because bash had no shared context.
Prefer `ctx` fields now:

| Bash shape | Python sidecar shape |
|---|---|
| `"$PWD"` | `ctx.project_root` |
| `"${DOC_DIR:-doc}"` | `ctx.doc_dir` |
| `"${SPECS_DIR:-specs}"` | `ctx.specs_dir` |
| `STRICT=1` | `ctx.strict` |
| `VERBOSE=1` | `ctx.verbose` |

Keep `os.environ[...]` only for genuinely external configuration. Use
`os.environ["NAME"]` for required values so missing configuration fails early,
or `os.environ.get("NAME")` when absence is a real supported state.

### File Globs

Replace shell globs and `find` with `Path.glob()` or `Path.rglob()`:

```python
for path in sorted((ctx.doc_dir / "papers").glob("*.md")):
    ...

for path in sorted((ctx.specs_dir / "hypotheses").rglob("*.md")):
    ...
```

Sort glob results when result ordering matters. Check `path.exists()` or
`path.is_dir()` when an optional project directory should be skipped.

### YAML and Frontmatter

Use the cached readers on `ValidateContext`:

```python
record = ctx.read_yaml(ctx.doc_dir / "provenance" / "example.yaml")
frontmatter = ctx.frontmatter(ctx.doc_dir / "papers" / "Example2026.md")
text = ctx.read_text_cached(ctx.doc_dir / "themes" / "theme.md")
```

`ctx.frontmatter(path)` returns a mapping for markdown frontmatter. `ctx.read_yaml(path)`
parses normal YAML files. Both are cached for the validation run.

### Multi-Line Warnings

Do not pre-format warning blocks with shell indentation, bullets, or manual
line wrapping. Put the durable diagnostic into `message`, and put stable
classification into `rule` and `task`:

```python
Result(
    Severity.WARN,
    yaml_path,
    None,
    "source_ref=paper:Smith2026 must set evidence_tier: background",
    "reviews-are-not-evidence",
    "task:t024",
)
```

If a single logical issue needs details, keep them in one sentence or emit
multiple focused `Result`s. The CLI owns terminal formatting.

### ANSI and Color

Drop ANSI escape codes entirely. Sidecars return data, not styled terminal
text. The `science validate` formatter applies the shared Science CLI color
policy, including `NO_COLOR` and the root `--color` option.

### Result Fields

Construct results with:

```python
Result(Severity.WARN, path, line, message, rule, task)
```

Use `Severity.ERROR` for blocking failures, `Severity.WARN` for non-blocking
issues, and `Severity.INFO` for diagnostics. `path` may be a `Path` or `None`.
`line` may be an integer or `None` when the check does not resolve a line
number. Prefer stable rule names such as `reviews-are-not-evidence`; use the
project task id in `task` when the check enforces a documented task.

## Migration Checklist

1. Create `validate_local.py` at the project root.
2. Move each registered bash hook to a Python function decorated with the same
   hook point.
3. Replace heredoc Python and `WARN:` / `INFO:` line protocols with direct
   `Result(...)` returns.
4. Replace shell path state with `ValidateContext` fields and helpers.
5. Compare warnings/errors against the old `validate.local.sh` behavior before
   adding `validate_local.py`, or temporarily move/disable one sidecar at a
   time.
6. Remove `validate.local.sh` once the Python sidecar is producing the intended
   results. Leaving it in place keeps `science validate` in the Phase 3 removal
   error state.
