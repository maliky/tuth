from __future__ import (
    annotations,
)  # to postpone evaluation of type hints

from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from app.models.academics import Course


@admin.register(Course)
class CourseAdmin(GuardedModelAdmin):
    """
    Admin interface for the ``Course`` model that
    • uses ``GuardedModelAdmin`` to respect django-guardian
      object-level permissions,
    • ensures each staff user only sees or edits courses
      they have been granted explicit permissions for,
    • can be extended with list filters, inlines, etc.,
      while retaining Guardian’s access control.

    Add customisations such as::

        list_display = ("code", "title", "curriculum", "credit_hours")
        search_fields = ("code", "title")
        autocomplete_fields = ("curriculum",)
    """

    pass
