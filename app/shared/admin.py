"""tentative to move the filter by group up in the user admin interface."""

# app/shared/admin.py
# from django.contrib import admin
# from django.contrib.auth.models import User
# from django.contrib.auth.admin import UserAdmin as CoreUserAdmin

# class UserAdmin(CoreUserAdmin):
#     """Override the default UserAdmin to make the first filter be groups."""
#     list_filter = ("groups", "is_staff", "is_superuser", "is_active")

# admin.site.unregister(User)
# admin.site.register(User, UserAdmin)
