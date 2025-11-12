# Contributor Guide

Welcome — and thanks for helping grow **Tusis**, Tubman University’s information system.
This guide explains how to spin up the development stack, run checks, write tests, and craft pull requests.

---

## 1 · Dev Environment Tips

| Task                          | One-liner                                                                                                                                     |
|-------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------|
| Spin up dev stack             | `docker-compose -f docker-compose-dev.yml up --build`                                                                                         |
| Drop into web container       | `docker-compose -f docker-compose-dev.yml exec web bash`                                                                                      |
| Reset DB schema (drop all)    | `docker-compose -f docker-compose-dev.yml exec web python manage.py reset_db`                                                                 |
| Generate new migration files  | `docker-compose -f docker-compose-dev.yml exec web python manage.py makemigrations academics finance people registry shared spaces timetable` |
| Apply all migrations          | `docker-compose -f docker-compose-dev.yml exec web python manage.py migrate`                                                                  |
| Seed the DB with initial data | `docker-compose -f docker-compose-dev.yml exec web python manage.py populate_initial_data`                                                    |

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
