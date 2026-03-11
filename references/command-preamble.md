# Command Preamble

Before executing any research command:

1. **Resolve project paths:** Read `science.yaml`. If it has a `paths:` section, use mapped
   directories throughout this command instead of defaults. Common mappings:
   - `doc_dir` → where research docs live (default: `doc/`)
   - `code_dir` → where code lives (default: `code/`)
   - `specs_dir` → where specs live (default: `specs/`)
   - `papers_dir` → where papers/references live (default: `papers/`)
   - `knowledge_dir` → where graph.trig lives (default: `knowledge/`)
   - `tasks_dir` → where task queue lives (default: `tasks/`)
   - `models_dir` → where models live (default: `models/`)
   - `prompts_dir` → where role prompts live (default: `prompts/`)
   If no `paths:` section exists, use the standard Science directory names.
2. Load role prompt: `<prompts_dir>/roles/<role>.md` if present, else `${CLAUDE_PLUGIN_ROOT}/references/role-prompts/<role>.md`.
3. Load the `research-methodology` and `scientific-writing` skills.
4. Read `<specs_dir>/research-question.md` for project context.
5. **Load project aspects:** Read `aspects` from `science.yaml` (default: empty list).
   For each aspect, read `${CLAUDE_PLUGIN_ROOT}/aspects/<name>/<name>.md`.
   When executing command steps, incorporate the additional sections, guidance,
   and signal categories from loaded aspects. Aspect-contributed sections are
   whole sections inserted at the placement indicated in each aspect file.
6. **Check for missing aspects:** Scan for structural signals that suggest aspects
   the project could benefit from but hasn't declared:

   | Signal | Suggests |
   |---|---|
   | Files in `<specs_dir>/hypotheses/` | `hypothesis-testing` |
   | Files in `<models_dir>/` (`.dot`, `.json` DAG files) | `causal-modeling` |
   | Pipeline files, notebooks, or benchmark scripts in `<code_dir>/` | `computational-analysis` |
   | Package manifests (`pyproject.toml`, `package.json`, `Cargo.toml`) at project root | `software-development` |

   If a signal is detected and the corresponding aspect is not in the `aspects` list,
   briefly note it to the user before proceeding:
   > "This project has [signal] but the `[aspect]` aspect isn't enabled.
   > This would add [brief description of what the aspect contributes].
   > Want me to add it to `science.yaml`?"

   If the user agrees, add the aspect to `science.yaml` and load the aspect file
   before continuing. If they decline, proceed without it.

   Only check once per command invocation — do not re-prompt for the same aspect
   if the user has previously declined it in this session.
7. **Resolve templates:** When a command says "Read `templates/<name>.md`",
   check the project's `templates/` directory first. If not found, read from
   `${CLAUDE_PLUGIN_ROOT}/templates/<name>.md`. If neither exists, warn the
   user and proceed without a template — the command's Writing section provides
   sufficient structure.
