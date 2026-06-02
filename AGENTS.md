# Contributor Guide

Welcome — and thanks for helping grow **Tusis**, Tubman University’s Student Information System.
This guide explains how to spin up the development stack, run checks, write tests, and craft pull requests.

## 2 · Conventions

- Growing codebase habit: re-read AGENTS.md and related task files regularly to align with evolving patterns and instructions.
- Do not create commits unless the user explicitly asks for a commit in the current conversation.

### Files to leave untouched unless asked
The folders: 
- `migrations/`
- `Seed_data`
 and all files under them
 
The files:
- `TODO.org`
- `journal.org`
- all `.gitignore` files
- Any file explicitly flagged by the user in a conversation

### naming
Do not change existing variable names

### Documentation & comments
- Pay close attention to comment using '# >' markers.  They are specificaly for agents.  You should read them but not write or delete them yourself.
- When editing code, do not remove commented lines.  Add a comment to explain why you suggest removing them, instead.
- Comment your additions with concise inline comments on key logic blocks, especially when removing or replacing code.
- Document succintly new class, methods, or functions even internal ones
- In the reports, do not add line precision, file precision is enough

### Coding style
- Typing: prefer explicit TypeAliases ending with `T` (e.g., `StrIntMapT`), avoid `Any`, and keep mypy happy.
- Prefer functional-style helpers and reuse existing utilities before adding new logic.
- Factor common routines rather than duplicating blocks; keep new code composable.
- Favor abstraction and simplification together: remove redundant parameters/paths and centralize repeated behavior into shared units when it reduces duplication.
- If two options express the same behavior (e.g., alias parameters), keep one canonical option and update call sites instead of carrying both.
- For app imports, prefer up to three levels when practical.
- It is acceptable to use deeper imports (e.g., `from app.finance.models.course_fee import ...`) when needed for clarity or to avoid circular imports.
- Use `__init__` and `__all__` to simplify  import paths when it improves maintainability.
- Trying keep python files size under 300 lines for readability.  They can be bundled together latter at deployment or production stage.

### Linting and checks
- Check that the code passes with `py_compile`, `ruff format --check`, `ruff check`, and `mypy` at the end of your edits.
- If a model change requires migrations, stop at code changes and report the required migration; do not create or edit migration files unless explicitly asked.

## Codebase style snapshot
- Favor small functional helpers (`ensure_*`, `normalize_*`, `pipeline`, widgets) and `get_or_create`/`update_or_create` patterns with in-memory caches for imports and admin helpers.
- Commands lean on `transaction.atomic`, emit progress/stats via `stdout`, and write CSV logs for skipped/invalid rows; docstrings are descriptive and comments with `# >` capture intent/TODOs.

## Debugging  and  Tests

- check function/class signatures and expected types/formats early; prefer settings-driven defaults over hardcoded formats.

### Selenium driver pin

- Use the system `chromedriver` (currently 142.x) when running Selenium. The fixtures look for `/usr/bin/chromedriver` first; do not downgrade to the webdriver-manager default (114) because it breaks local browsers.

### Environment notes
- You may see harmless `pyenv: cannot rehash` warnings in some environments.
- `rg` (ripgrep) is not always available; fall back to `python`/`grep` when needed.
- Some sessions can be read-only; if you cannot write files, provide patch instructions instead of applying changes.
