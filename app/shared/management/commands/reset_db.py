"""Management command for resetting the database.

Drops all tables from the current schema so you can start from a clean
database. The operation is irreversible and should only be used in
development. There is no confirmation prompt.

Example:
    To rebuild the schema after removing all tables run::

        python manage.py reset_db
        python manage.py migrate
        python manage.py populate_initial_data
"""

from app.shared.auth.helpers import ensure_superuser
from django.core.management.base import BaseCommand
from django.db import connection


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

    def handle(self, *args, **options):
        """Reset the Database. Erase all history."""
        self.stdout.write(self.style.WARNING("Resetting the database..."))

        with connection.cursor() as cursor:
            cursor.execute(
                """
            DO $$
            DECLARE
                rec RECORD;
            BEGIN
                FOR rec IN (SELECT tablename FROM pg_tables WHERE schemaname = current_schema()) LOOP
                    EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(rec.tablename) || ' CASCADE';
                END LOOP;
            END $$;
            """
            )

        self.stdout.write(self.style.SUCCESS("Database reset successfully."))
        
        ensure_superuser(self)
