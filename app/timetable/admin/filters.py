"""Filters for the registry models in Admin."""

from admin_searchable_dropdown.filters import AutocompleteFilterFactory, AutocompleteFilter
from django.contrib import admin
from django.urls import reverse
from urllib.parse import urlencode

class SectionBySemesterFilter(AutocompleteFilter):
    """Dropdow for Section dependings on Semester filter."""

    title = "Section"
    field_name = "section"

    def get_autocomplete_url(self, request, model_admin):
        """Get the url registered in GradeAdmin.get_urls."""
        base = reverse("admin:section_by_semester_autocomplete")
        semester_id = request.GET.get("section__semester")
        return f"{base}?{urlencode({'section__semester': semester_id})}" if semester_id else base


SemesterFilterAutocomplete = AutocompleteFilterFactory(
    'Semester',                # title
    'section__semester',        # look-up path (Grade → Section → Semester)
    use_pk_exact=False
)


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
            # current = get_current_semester()  # should I default to current
            # if so the All keyword has no use
            # if not current:
            return qs
            # semester_id = current.id
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
