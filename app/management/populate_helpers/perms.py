from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from guardian.shortcuts import assign_perm
from app.constants import OBJECT_PERM_MATRIX
from app.models import RoleAssignment


def grant_model_level_perms(groups):
    for model, perms in OBJECT_PERM_MATRIX.items():
        try:
            ct = ContentType.objects.get(app_label="app", model=model)
        except Exception:
            print(f">> model={model} <<")

        for perm_name, roles in perms.items():
            perm = Permission.objects.get(
                codename=f"{perm_name}_{model}", content_type=ct
            )
            for role in roles:
                groups[role].permissions.add(perm)


def grant_college_object_perms():
    for ra in RoleAssignment.objects.select_related("college"):
        if ra.college is None:
            continue
        for perm_name, roles in OBJECT_PERM_MATRIX["college"].items():
            if ra.role in roles:
                assign_perm(f"{perm_name}_college", ra.user, ra.college)
