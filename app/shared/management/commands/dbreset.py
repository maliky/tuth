"""Management command for resetting the database."""

from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection

from app.shared.auth.helpers import ensure_superuser
from app.shared.file_utils import iter_migration_files


class Command(BaseCommand):
    """Drop all tables from the default database.

    This command iterates over every table in the current schema and issues a
    DROP TABLE ... CASCADE statement. It is useful for resetting a local
    database when starting development from scratch.

    Warning:
        This operation is destructive and should never be executed on a
        production database.
    """

    help = "Completely resets the database by dropping all tables."

    def add_arguments(self, parser):
        parser.add_argument(
            "--project-root",
            default=str(Path(settings.BASE_DIR).resolve()),
            help="Path to project root used to locate */migrations/* (default: BASE_DIR).",
        )
        parser.add_argument(
            "--no-migrations-delete",
            action="store_true",
            help="Delete all migration files (keeps migrations/__init__.py).",
        )
        parser.add_argument(
            "--delete-sqlite-db",
            action="store_true",
            help="If using SQLite, delete the database file on disk.",
        )
        parser.add_argument(
            "--no-seed",
            action="store_true",
            help="create_states / ensure_superuser / load_roles steps.",
        )

    def handle(self, *args, **opts):
        """Reset the Database. Erase all history."""

        project_root = Path(opts["project_root"]).resolve()
        print(opts)

        if opts["delete_sqlite_db"]:
            self._delete_sqldb(settings)

        call_command("reset_db", interactive=True, verbosity=0)

        if not opts["no_migrations_delete"]:
            self._delete_migrations(project_root)

        call_command(
            "makemigrations",
            "academics",
            "finance",
            "people",
            "registry",
            "shared",
            "spaces",
            "timetable",
            "website",
            interactive=False,
            verbosity=1,
        )
        call_command("migrate", interactive=False, verbosity=1)
        ensure_superuser(self)

        if not opts["no_seed"]:
            call_command("create_states")
            call_command("load_roles", verbosity=0)

    def _delete_migrations(self, project_root):
        """Delete unlink the files."""
        deleted = []
        for p in iter_migration_files(project_root):
            try:
                p.unlink()
                deleted.append(p)
            except FileNotFoundError:
                pass
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} migration file(s)."))

    def _delete_sqldb(self, settings):
        """Delete the SQL DB."""
        engine = settings.DATABASES["default"]["ENGINE"]
        if engine != "django.db.backends.sqlite3":
            self.stdout.write("Not SQLite; skipping DB file deletion.")
        else:
            db_path = Path(settings.DATABASES["default"]["NAME"]).expanduser()
            if db_path.exists():
                db_path.unlink()
                self.stdout.write(
                    self.style.SUCCESS(f"Deleted SQLite DB file: {db_path}")
                )
            else:
                self.stdout.write(f"SQLite DB file not found: {db_path}")
