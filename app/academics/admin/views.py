"""Views for the academics admin."""

from admin_searchable_dropdown.views import AutocompleteJsonView
from app.academics.models import Curriculum


class CurriculumBySemester(AutocompleteJsonView):
    """Returns the curriculums with section offered during a specific semester."""

    model_admin = None

    @staticmethod
    def display_text(obj):
        """Set the text to show in the dropdown box."""
        return f"{obj}"

    def get_queryset(self):
        """Returns the filter queryset using semeter id passed in the url."""
        semester_id = self.request.GET.get("semester")
        if not semester_id:
            return Curriculum.objects.all()

        return Curriculum.objects.filter(
            curriculum_course__sections__semester_id=semester_id
        )
