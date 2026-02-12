"""Admin customization for Group model."""

from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as DjangoGpAdmin
from django.contrib.auth.models import Group


class GpAdmin(DjangoGpAdmin):
    """Show group members in the admin detail view."""

    # List the users belonging to the group
    readonly_fields = ("user_list",)
    # DjangoGpAdmin defines fieldsets, so we override to ensure user_list renders.
    fieldsets = ((None, {"fields": ("name", "permissions", "user_list")}),)

    def user_list(self, obj: Group) -> str:
        """Return a comma-separated list of usernames."""
        return ", ".join(user.username for user in obj.user_set.all())


# Replace the default admin with the customized one
admin.site.unregister(Group)
admin.site.register(Group, GpAdmin)
