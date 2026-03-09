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
