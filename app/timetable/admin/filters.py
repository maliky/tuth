"""Filters for the registry models in Admin."""

from admin_searchable_dropdown.filters import (
    AutocompleteFilterFactory,
    AutocompleteFilter,
    _get_rel_model,
)
from app.shared.admin.filters import BaseCollegeFilter
from app.timetable.models import semester
from app.timetable.models.semester import Semester
from django.contrib import admin
from django.urls import reverse
from urllib.parse import urlencode

# GradeSemesterFilterAc = AutocompleteFilterFactory(
#     "Semester",
#     "section__semester",  # look-up path (Grade → Section → Semester)
#     use_pk_exact=False,
# )

# SectionSemesterFilterAc = AutocompleteFilterFactory(
#     "Semester",
#     "semester",
#     use_pk_exact=False,
# )

SemesterAcademicYearFilterAc = AutocompleteFilterFactory(
    "Academic year",
    "academic_year",
    use_pk_exact=False,  # > what advantages is there to use_pk_exact ?
)


SEMESTER_FIELD_LOOKPS = (
    ("semester", "semester"),
    ("section", "section__semester"),
    ("curriculum_course", "curriculum_course__sections__semester"),
    ("payment", "payment_student__current_enrolled_semester"),
    ("student", "student__current_enrolled_semester"),
)


def _get_semester_lookup_path(model):
    """Return the lookup path pointing to a semester for a given model."""
    field_names = {f.name for f in model._meta.get_fields()}
    for field_name, lookup_path in SEMESTER_FIELD_LOOKPS:
        if field_name in field_names:
            return lookup_path


def _semester_qs_from_model_admin(model_admin, request):
    """Return only semesters that appear in the current changelist queryset."""
    qs = model_admin.get_queryset(request)
    lookup_path = _get_semester_lookup_path(qs.model)
    if not lookup_path:
        return Semester.objects.none()

    semester_ids = (
        qs.filter(**{f"{lookup_path}__isnull": False})
        .values_list(f"{lookup_path}__id", flat=True)
        .distinct()
    )
    return Semester.objects.filter(id__in=semester_ids).order_by("-start_date")


class SectionCollegeFilter(BaseCollegeFilter):
    field_path = "curriculum_course__curriculum__college"
    parameter_name = "curriculum_course__curriculum__college__id__exact"


SectionDepartmentFilterAc = AutocompleteFilterFactory(
    "Department", "curriculum_course__course__department"
)

SectionFacultyFilterAc = AutocompleteFilterFactory("Faculty", "faculty")


class SectionBySemesterFilter(AutocompleteFilter):
    """Dropdow for Section dependings on Semester filter."""

    title = "Section"
    field_name = "section"

    def get_autocomplete_url(self, request, model_admin):
        """Get the url registered in GradeAdmin.get_urls."""
        base = reverse("admin:section_by_semester_autocomplete")
        semester_id = request.GET.get("section__semester")
        return (
            f"{base}?{urlencode({'section__semester': semester_id})}"
            if semester_id
            else base
        )


class SemesterFilterAC(AutocompleteFilter):
    title = "semester"
    parameter_name = "semester"
    field_name = "semester"
    use_pk_exact = False

    def __init__(self, request, params, model, model_admin):
        """Prepare a limited autocomplet filter for semester fields.

        Keyword Arguments:
        request     --
        params      --
        models      --
        model_admin --
        """
        # is model lower case ?
        self.lookup_path = _get_semester_lookup_path(model)
        self.parameter_name = self.lookup_path or self.parameter_name
        self.field_name = (self.lookup_path or self.field_name).split("_")[-1]
        self.rel_model = (
            _get_rel_model(model, self.lookup_path) if self.lookup_path else None
        )
        self._semester_qs = _semester_qs_from_model_admin(model_admin, request)
        super().__init__(request, params, model, model_admin)
        self.title = "semester"

        def get_queryset_for_field(self, model, name):
            """Limit autocomplete results to semester present in the admin qs."""
            if name == self.field_name:
                # this looks like a circular stuff.
                return self._semester_qs
            return super().get_queryset_for_field(model, name)

        def queryset(self, request, qs):
            """Filter the changelist by the selected semester."""
            filtered_qs = _get_semester_qs(self, request, qs)
            return filtered_qs


def _get_semester_qs(afilter, request, qs):
    """Return the filtered query set."""

    lookup_path = afilter.lookup_path
    value = afilter.value()
    if not lookup_path or not value:
        return qs
    try:
        semester_id = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return qs
    return qs.filter(**{lookup_path: semester_id})


class SemesterFilter(admin.SimpleListFilter):
    """Filter queryset by semester with a current semester default."""

    title = "semester"
    parameter_name = "semester"

    def __init__(self, request, params, model, model_admin):
        """Prepare the SimpletList Filter."""
        self.lookup_path = _get_semester_lookup_path(model)
        super().__init__(request, params, model, model_admin)

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
        semesters = _semester_qs_from_model_admin(model_admin, request)
        if not semesters.exists():
            semesters = Semester.objects.order_by("start_date")
        return [(s.id, str(s)) for s in semesters]

    def queryset(self, request, qs):
        """Filter the results of different model based on the related semester.

        Returns the filtered queryset based on the value.
        provided in the query string and retrievable via
        `self.value()`.
        """
        filtered_qs = _get_semester_qs(self, request, qs)
        return filtered_qs
