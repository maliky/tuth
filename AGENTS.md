# Contributor Guide

Welcome — and thanks for helping grow **Tusis**, Tubman University’s information system.
This guide explains how to spin up the development stack, run checks, write tests, and craft pull requests.

---

### Selenium driver pin

- Use the system `chromedriver` (currently 142.x) when running Selenium. The fixtures look for `/usr/bin/chromedriver` first; do not downgrade to the webdriver-manager default (114) because it breaks local browsers.


## 2 · Conventions

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
---

Do not commit change made to migration files. The will be regenerated with new DB.

### naming
Don't change existing variable names

### Documentation & comments
- Pay close attention to comment using '# >' markers they are for you.
- When editing code, do not remove commented lines.  Add a comment to explain why you suggest removing them, instead.
- Comment your additions, especially if removing code
- Document succintly new class, methods, or functions
- In the reports, do not ad precision, file precision is enough

### Coding style
- Typing: prefer explicit TypeAliases ending with `T` (e.g., `StrIntMapT`), avoid `Any`, and keep mypy happy (no implicit Optional where a concrete type is expected).
- Prefer functional-style helpers (small pure functions) and reuse existing utilities before adding new logic.
- Factor common routines rather than duplicating blocks; keep new code composable.
- for app import prefere three level deep.  using __init___ and __all__ in case of deeper nesting.
- Trying python files size uner 300 lines for readability.  They can be combined latter at deployment or production stage.
- Before finishing a round of edits, run `black .`, `flake8 .`, and `mypy .` to catch formatting/lint/type issues.

### Branching
Propose naming below
Propose consistent naming for git commit but do not commit yourself.
```bash
    feature/... for new functionality
    fix/... for bug fixes
    chore/... for small changes, cleanups, or refactoring
    hotfix/... only if needed urgently on production
```
### Linting and checks
- Check that the code pass 
with black, flake8 and mypy
- you can run `py_compile`,  `black`, `flake8`, and `mypy` at the end of your edits. 
