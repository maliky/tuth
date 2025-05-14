# app/management/commands/reset_db.py
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    """
    python manage.py reset_db
    python manage.py migrate
    python manage.py populate_initial_data
    """

    help = "Completely resets the database by dropping all tables."

    def handle(self, *args, **options):
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
