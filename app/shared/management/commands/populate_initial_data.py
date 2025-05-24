from pathlib import Path
from app.shared.management.populate_helpers.sections import populate_sections_from_csv
from django.core.management.base import BaseCommand
from django.db import transaction

from app.shared.management.populate_helpers import (
    ensure_role_groups,
    ensure_superuser,
    grant_college_object_perms,
    grant_model_level_perms,
    log,
    populate_colleges,
    upsert_test_users_and_roles,
)


class Command(BaseCommand):
    help = "Populate dev DB with reference data and sample academic content."

    @transaction.atomic
    def handle(self, *args, **options):
        log(self, "\n⚙ Initialising seed data")
        ensure_superuser(self)

        log(self, "\n⚙ Colleges")
        colleges = populate_colleges(self)

        log(self, "\n⚙ Sections")
        populate_sections_from_csv(self, Path("Seed_data/sections.csv"))
        log(self, "\n⚙ Groups & Users")
        groups = ensure_role_groups()
        upsert_test_users_and_roles(self, colleges, groups)

        log(self, "\n⚙ Model-level permissions")
        grant_model_level_perms(groups)

        log(self, "\n⚙ College object-level permissions")
        grant_college_object_perms()

        log(self, "\n⚙ Academic calendar")
        # populate_academic_years(self)

        log(self, "\n⚙ Populating Environmental Studies curriculum")
        # populate_environmental_studies_curriculum(self, colleges)

        log(self, "\n✔ All seed data created.\n", "SUCCESS")
