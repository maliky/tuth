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

from app.shared.auth.perms import APP_MODELS, UserRole


class Command(BaseCommand):
    """CLI helper available as manage.py load_permissions."""

    help = "Load perms.yaml and rebuild Group → Permission relations."

    # > what's this *_ and **__ ?
    def handle(self, *args, **kwargs) -> None:
        """Read YAML, validate, wipe current grants and recreate them."""

        Group.permissions.through.objects.all().delete()

        # Iterate create, read, update, delete actions
        for ur in UserRole:
            grp = sync_role_group(ur_group=ur.value.group, x_rights=ur.value.rights)
            self.stdout.write(self.style.NOTICE(f"Permissions for {grp} added."))

        self.stdout.write(self.style.SUCCESS("Permissions rebuilt!"))


def sync_role_group(ur_group: Group, x_rights: dict[str, list[str]]) -> Group:
    """Ensure a Django group exists for this role and sync its permissions."""
    perms = []

    for action, models in x_rights.items():
        for model in models:
            app_label = get_app_label(model)
            model_cls = apps.get_model(app_label, model)
            ct = ContentType.objects.get_for_model(model_cls)
            codename = f"{action}_{model}"
            perm, _ = Permission.objects.get_or_create(codename=codename, content_type=ct)
            perms.append(perm)

    ur_group.permissions.set(perms)
    return ur_group


def get_app_label(model):
    """Return the app label for the model based on perms.APP_MODELS."""

    for app_label, models in APP_MODELS.items():
        if model in models:
            return app_label
    raise Exception(f"model {model}  not found in perms.APP_MODELS")
