"""Views for the  admin timetable module."""

from admin_searchable_dropdown.views import AutocompleteJsonView
from app.timetable.models import Section


class SectionBySemesterAutocomplete(AutocompleteJsonView):
    """Returns the sections belonging to the semester passed in the query."""

    model_admin = None

    @staticmethod
    def display_text(obj):
        """Set how the option appears in the dropdown."""
        return f"{obj.course.code}s{obj.number}"  # f"{obj.course.short_code}"

    def get_queryset(self):
        """Returns a Filtered queryset using the semester_id present in the url."""
        # ! line below not clear. Needs epxlainations.
        qs = Section.objects.select_related("curriculum_course__course", "semester")
        semester_id = self.request.GET.get("section__semester") or self.request.GET.get(
            "section__semester__pk__exact"
        )
        # or self.request.GET.get("semester")

        if not semester_id:
            return qs

        return qs.filter(semester_id=semester_id).order_by(
            "curriculum_course__course__code"
        )
