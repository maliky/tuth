# Contributor Guide

Welcome — and thanks for helping grow **Tusis**, Tubman University’s information system.
This guide explains how to spin up the development stack, run checks, write tests, and craft pull requests.

---

### Selenium driver pin

- Use the system `chromedriver` (currently 142.x) when running Selenium. The fixtures look for `/usr/bin/chromedriver` first; do not downgrade to the webdriver-manager default (114) because it breaks local browsers.

### Files to leave untouched unless asked
- `TODO.org`
- `journal.org`
- Any file explicitly flagged by the user in a conversation


---

## 2 · Conventions

### Ignore `migrations/` folders in commits

Do not commit change made to migration files. The will be regenerated with new DB.

### naming
Don't change existing variable names

### Documentation & comments
- Comment your additions, especially if removing code
- Document succintly new class, methods, or functions
- In the reports I don't need line precision, file precision is enough

### Coding style
- Prefer functional-style helpers (small pure functions) and reuse existing utilities before adding new logic.
- Factor common routines rather than duplicating blocks; keep new code composable.

### Branching

Always work on a feature branch off of `dev`.
Example:

git checkout -b feature/section-reservations

Use consistent naming:
```bash
    feature/... for new functionality

    fix/... for bug fixes

    chore/... for small changes, cleanups, or refactoring

    hotfix/... only if needed urgently on production
    
```
### Linting and checks
- Check that the code pass 
black, flake8 and mypy
