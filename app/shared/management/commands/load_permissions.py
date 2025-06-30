"""Management command that set Django-/guardian group permissions from the YAML file.

Usage
-----
$ python manage.py load_permissions
is automatically invoked by *import_resources* so a fresh dataset always
ships with a coherent permission matrix.
"""

import logging
from pathlib import Path
from typing import Any

import yaml
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError

from app.people.choices import UserRole  # authoritative list of roles


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
        path = Path("app/shared/auth/perms.yaml")
        self.spec = yaml.safe_load(path.read_text())
        self.roles_defined = {role.value for role in UserRole}

        # ---------- 1. fail-hard validation ---------------------------
        # ensure every role / model mentioned in YAML truly exists
        unknown_roles = self.get_unknown_roles()
        unknown_models = self.get_unknow_models()
        if unknown_roles or unknown_models:
            raise CommandError(
                f"✖ unknown roles: {unknown_roles} | unknown models: {unknown_models}"
            )

        # ---------- 2. purge existing relations ----------------------
        # bulk-clear permissions; guardian object-perms are untouched
        Group.permissions.through.objects.all().delete()

        # ---------- 3. rebuild model-level perms ---------------------
        ct_cache: dict[str, ContentType] = {}  # memo-ise ContentType look-ups

        # walk over every model described in perms.yaml
        for model, acts in self.spec["object_perm_matrix"].items():

            # Get the class and the model
            app_label = self.spec["model_app"][model]
            my_models = apps.get_model(app_label, model)

            _ct = ContentType.objects.get_for_model(my_models)
            # return _ct if model is not a key of the dict & insert it.
            # else return the value of the model key
            ct = ct_cache.setdefault(model, _ct)

            # Iterate create, read, update, delete actions
            for action, role_list in acts.items():
                # Django auto-creates permissions named "<action>_<model>"
                # e.g.  view_course, change_course …
                perm, _created = Permission.objects.get_or_create(
                    codename=f"{action}_{model}", content_type=ct
                )

                #  Attach that permission to every group listed in role_list
                for role in role_list:
                    grp, _created = Group.objects.get_or_create(
                        name=" ".join([r.capitalize() for r in role.split("_")])
                    )
                    grp.permissions.add(perm)  # final grant

        logging.info("✔ permissions rebuilt from perms.yaml")

    def get_unknown_roles(self):
        """Return the unknow roles from the YAML file."""
        return {
            role
            for perms in self.spec["object_perm_matrix"].values()  # models
            for acts in perms.values()  # actions (view, add...)
            for role in acts  # roles for each actions (dean, chair...)
            if role not in self.roles_defined
        }

    def get_unknow_models(self):
        """Return the unknow models from the YAML file."""
        return {
            model
            for model in self.spec["model_app"]
            if not apps.is_installed(f"app.{self.spec['model_app'][model]}")
        }
