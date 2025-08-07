"""Management command that set Django-/guardian group permissions from the role_matrix.

Usage
-----
$ python manage.py load_permissions
is automatically invoked by *import_resources* so a fresh dataset always
ships with a coherent permission matrix.
"""

import logging
from typing import Any

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from app.shared.auth.perms import (
    APP_MODELS,
    ROLE_MATRIX,
    UserRole,
)  # authoritative list of roles


class Command(BaseCommand):
    """CLI helper available as manage.py load_permissions."""

    help = "Load perms.yaml and rebuild Group → Permission relations."

    def __init__(self, *args, **kwargs):
        super(*args, **kwargs)
        self.roles_defined = set()
        self.spec: Any = None

    # ------------------------------------------------------------------
    # entry point
    # ------------------------------------------------------------------
    # > what's this *_ and **__ ?
    def handle(self, *_, **__) -> None:
        """Read YAML, validate, wipe current grants and recreate them."""
        # path = Path("app/shared/auth/perms.yaml")
        # self.spec = yaml.safe_load(path.read_text())
        self.spec = ROLE_MATRIX
        self.roles_defined = {ur.value.code for ur in UserRole}

        Group.permissions.through.objects.all().delete()

        # ---------- 3. rebuild model-level perms ---------------------
        ct_cache: dict[str, ContentType] = {}  # memo-ise ContentType look-ups

        for app_label, models in APP_MODELS.items():
            for model in models:
                my_model = apps.get_model(app_label, model)

                _ct = ContentType.objects.get_for_model(my_model)
                # return _ct if model is not a key of the dict & insert it.
                # else return the value of the model key
                ct = ct_cache.setdefault(model, _ct)

                # Iterate create, read, update, delete actions
                for role, rights in self.spec.items():
                    # Django auto-creates permissions named "<action>_<model>"
                    # e.g.  view_course, change_course …
                    for action, model in rights.items():
                        perm, _created = Permission.objects.get_or_create(
                            codename=f"{action}_{model}", content_type=ct
                        )

                        grp, _created = Group.objects.get_or_create(name=role)
                        grp.permissions.add(perm)  # final grant

        logging.info("✔ permissions rebuilt")
