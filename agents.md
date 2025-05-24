# Contributor Guide

Welcome — and thanks for helping grow **Tuth**, Tubman University’s information system.
This guide explains how to spin up the stack, run checks, write tests, and craft pull-requests.

---

## 1 · Dev Environment Tips

| Task                        | One-liner                                                |
|-----------------------------|----------------------------------------------------------|
| Spin up dev stack           | `docker-compose -f docker-compose-dev.yml up --build`    |
| Drop into the web container | `docker-compose -f docker-compose-dev.yml exec web bash` |
| Create data fixtures        | `python manage.py populate_initial_data`                 |
| Reset DB (⚠ destructive)    | ./reset_dev_db.sh                                        |

* Ignore migrations folder and file
In dev setting I restart from a fresh db using reset_dev_db.sh before running tests.
If you are using the django default memory it's the same, no need migrate or touche the files inside the migrations folder.


* **Branching**: work on a feature branch off *dev*.  
  Example: `git checkout -b feature/section-reservations`.

* **New Python deps**: add to *requirements.txt* **and** *requirements-dev.txt* if needed.

---

## 2 · Static Checks & Formatting

Run them **before every commit**:

```bash
black app/                       # auto-format
flak8 check app/                 # lint (PEP 8 + isort)
mypy app/                        # strict typing
