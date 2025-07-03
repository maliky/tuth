"""Admin utilities for shared components."""

from django.contrib import admin
from django.utils import timezone

from app.timetable.models.semester import Semester


def get_current_semester() -> Semester | None:
    """Return the semester covering today's date or the latest by start date."""
    today = timezone.now().date()
    sem = Semester.objects.filter(start_date__lte=today, end_date__gte=today).first()
    if sem:
        return sem
    return Semester.objects.order_by("-start_date").first()


class SemesterFilter(admin.SimpleListFilter):
    """Filter queryset by semester with a current semester default."""

    title = "semester"
    parameter_name = "semester"

    def lookups(self, request, model_admin):
        """Get the semesters order in decreasing age.

        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.

        See https://docs.djangoproject.com/en/5.2/ref/contrib/admin/filters/
        """
        # Request and mode_admin are not used but it's ok.
        semesters = Semester.objects.order_by("-start_date")
        return [(s.id, str(s)) for s in semesters]

    def queryset(self, request, qs):
        """Filter the results of different model based on the related semester.

        Returns the filtered queryset based on the value.
        provided in the query string and retrievable via
        `self.value()`.
        """
        if self.value() is None:
            current = get_current_semester()
            if not current:
                return qs
            semester_id = current.id
        else:
            semester_id = int(self.value())  # type: ignore[arg-type]

        model = qs.model
        field_names = {f.name for f in model._meta.get_fields()}
        if "semester" in field_names:
            return qs.filter(semester_id=semester_id)
        if "section" in field_names:
            return qs.filter(section__semester_id=semester_id)
        if "program" in field_names:
            return qs.filter(program__sections__semester_id=semester_id).distinct()
        if "financial_record" in field_names:
            return qs.filter(
                financial_record__student__current_enroled_semester_id=semester_id
            )
        if "student" in field_names:
            return qs.filter(student__current_enroled_semester_id=semester_id)
        return qs
