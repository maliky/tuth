"""Management command that set Django-/guardian group permissions from the role_matrix.

Usage
-----
$ python manage.py load_permissions
is automatically invoked by *import_resources* so a fresh dataset always
ships with a coherent permission matrix.
"""

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from app.shared.auth.perms import (
    APP_MODELS,
    ROLE_MATRIX,
)


class Command(BaseCommand):
    """CLI helper available as manage.py load_permissions."""

    help = "Load perms.yaml and rebuild Group → Permission relations."

    # > what's this *_ and **__ ?
    def handle(self, *args, **kwargs) -> None:
        """Read YAML, validate, wipe current grants and recreate them."""

        Group.permissions.through.objects.all().delete()

        # ---------- 3. rebuild model-level perms ---------------------
        ct_cache: dict[str, ContentType] = {}  # memo-ise ContentType look-ups

        # Iterate create, read, update, delete actions
        for role, rights in ROLE_MATRIX.items():
            # Django auto-creates permissions named "<action>_<model>"
            # e.g.  view_course, change_course …
            grp, _ = Group.objects.get_or_create(name=role.capitalize())

            for action, models in rights.items():
                for model in models:
                    app_label = get_app_label(model)
                    my_model = apps.get_model(app_label, model)

                    _ct = ContentType.objects.get_for_model(my_model)
                    # return _ct if model is not a key of the dict & insert it.
                    # else return the value of the model key
                    ct = ct_cache.setdefault(model, _ct)

                    perm, _ = Permission.objects.get_or_create(
                        codename=f"{action}_{model}", content_type=ct
                    )

                    grp.permissions.add(perm)  # final grant
            self.stdout.write(self.style.NOTICE(f"Permissions for {grp} added."))

        self.stdout.write(self.style.SUCCESS("Permissions rebuilt!"))


def get_app_label(model):
    """Return the app label for the model based on perms.APP_MODELS."""

    for app_label, models in APP_MODELS.items():
        if model in models:
            return app_label
    raise Exception(f"model {model}  not found in perms.APP_MODELS")
