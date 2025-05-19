from django.core.management.base import BaseCommand
from django.db import transaction

from app.management.populate_helpers import (
    log,
    populate_colleges,
    ensure_superuser,
    ensure_role_groups,
    upsert_test_users_and_roles,
    grant_model_level_perms,
    grant_college_object_perms,
    populate_academic_years,
    populate_environmental_studies_curriculum,
)


class Command(BaseCommand):
    help = "Populate dev DB with reference data and sample academic content."

    @transaction.atomic
    def handle(self, *args, **options):
        log(self, "\n⚙ Initialising seed data")
        ensure_superuser(self)

        log(self, "\n⚙ Colleges")
        colleges = populate_colleges(self)

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
