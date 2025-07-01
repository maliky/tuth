"""Helpers to grant permissions during initial data population."""

import logging

from pathlib import Path

import yaml
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from guardian.shortcuts import assign_perm

from app.people.models.role_assignment import RoleAssignment

# def get_content_type(model_name):
#     model = apps.get_model("shared", model_name)  # Adjust "shared" to match actual app name
#     return ContentType.objects.get_for_model(model)


PERMS_FILE = Path("app/shared/auth/perms.yaml")

logger = logging.getLogger(__name__)


def _load_perms_spec():
    """Return the parsed permissions specification."""
    return yaml.safe_load(PERMS_FILE.read_text())


def grant_model_level_perms(groups):
    """Assign model-level permissions to the provided groups."""
    spec = _load_perms_spec()
    for model, perms in spec["object_perm_matrix"].items():
        try:
            ct = ContentType.objects.get(
                app_label=spec["model_app"][model],
                model=model,
            )
        except Exception:
            logger.exception("Unable to get content type '%s'", model)
            continue

        for perm_name, roles in perms.items():
            perm = Permission.objects.get(
                codename=f"{perm_name}_{model}", content_type=ct
            )
            for role in roles:
                groups[role].permissions.add(perm)


def grant_college_object_perms():
    """Grant object-level college permissions to role assignments."""
    spec = _load_perms_spec()
    college_perms = spec["object_perm_matrix"].get("college", {})
    for ra in RoleAssignment.objects.select_related("college"):
        if ra.college is None:
            continue
        for perm_name, roles in college_perms.items():
            if ra.role in roles:
                assign_perm(f"{perm_name}_college", ra.user, ra.college)
