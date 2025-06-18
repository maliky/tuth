"""Admin forms for the academics app."""

# app/academics/admin/forms.py
from typing import Any, MutableMapping, cast
from django import forms
from django.db import transaction
from django.contrib import admin
from django.contrib.admin.widgets import AutocompleteSelect
from app.shared.utils import make_course_code
from app.academics.models import Course, Curriculum, CurriculumCourse, College
from app.shared.enums import CREDIT_NUMBER
from import_export.forms import ImportForm


class BulkActionImportForm(ImportForm):
    """Import form allowing bulk actions on curricula data."""

    ACTION_CHOICES = (("merge", "Merge (append)"), ("replace", "Replace (wipe first)"))
    action = forms.ChoiceField(
        choices=ACTION_CHOICES, initial="merge", label="Action for existing curricula"
    )


class CourseForm(forms.ModelForm):
    """Admin form used to create or edit ``Course`` instances.

    The form exposes a writable ``curricula`` field and populates several
    defaults to streamline data entry in the admin.
    """

    credit_hours = forms.TypedChoiceField(
        coerce=int,
        choices=CREDIT_NUMBER.choices,
        required=False,  # allow blank ⇒ model default (3)
        widget=forms.NumberInput(attrs={"min": 1}),
    )
    curricula = forms.ModelMultipleChoiceField(
        queryset=Curriculum.objects.all(),
        required=False,
        help_text="Programmes that include this course",
    )

    # ──────────────────────────────────────────────────────────
    # initial values & non-required title
    # ──────────────────────────────────────────────────────────
    def __init__(self, *args, **kwargs):
        """Initialize the form with dynamic defaults.

        Parameters
        ----------
        *args, **kwargs
            Standard Django ``ModelForm`` arguments.
        """

        self.admin_site = kwargs.pop("admin_site", admin.site)
        super().__init__(*args, **kwargs)

        # shortcuts that are always safe to call
        init: dict[str, Any] = dict(self.initial or {})

        # pre-select curricula for existing courses
        if self.instance.pk:
            self.fields["curricula"].initial = self.instance.curricula.all()

        # show “3” by default when creating
        if not self.instance.pk:
            self.fields["credit_hours"].initial = CREDIT_NUMBER.THREE

        # make title optional in the *form* even if model says otherwise
        self.fields["title"].required = False

        # prefill college if the course code uniquely maps to one college
        if not self.instance.pk:

            name = (self.data.get("name") or "").strip() or init.get("name", "")
            number = (self.data.get("number") or "").strip() or init.get("number", "")
            if name and number:
                code = make_course_code(name=name, number=number)
                colleges = list(
                    Course.objects.filter(code=code)
                    .values_list("college_id", flat=True)
                    .distinct()
                )
                if len(colleges) == 1:
                    self.fields["college"].required = False
                    self.fields["college"].initial = colleges[0]
                elif len(colleges) > 1:
                    remote_field = Course._meta.get_field("college").remote_field
                    self.fields["college"].widget = AutocompleteSelect(
                        remote_field, self.admin_site
                    )

    # ──────────────────────────────────────────────────────────
    # save logic
    # ──────────────────────────────────────────────────────────
    def save(self, commit=True):
        """Save the form and stage curricula updates.

        Parameters
        ----------
        commit : bool, optional
            Whether to persist the ``Course`` immediately. Defaults to ``True``.

        Returns
        -------
        Course
            The created or updated course instance.
        """
        self._pending_curricula = set(self.cleaned_data.get("curricula", []))
        course = super().save(commit=commit)
        return course

    def clean(self):
        """Validate and enhance cleaned data.

        Returns
        -------
        dict[str, Any]
            The cleaned data with inferred ``college`` when possible.
        """

        cleaned = cast(MutableMapping[str, Any], super().clean())  # ← FIX #2/3

        if not cleaned.get("college") and cleaned.get("name") and cleaned.get("number"):
            code = make_course_code(name=cleaned["name"], number=cleaned["number"])
            colleges = list(
                Course.objects.filter(code=code)
                .values_list("college_id", flat=True)
                .distinct()
            )
            if len(colleges) == 1:
                cleaned["college"] = College.objects.get(pk=colleges[0])
        return cleaned

    class Meta:
        model = Course
        fields = "__all__"  # keeps our synthetic 'curricula'

    @transaction.atomic
    def save_m2m(self):
        """Synchronize curricula relationships.

        Called by Django after ``save()`` when handling many-to-many data.

        Returns
        -------
        None
        """
        super().save_m2m()  # default Django stuff

        course = self.instance
        chosen = self._pending_curricula
        current = set(course.curricula.all())

        # deletions
        CurriculumCourse.objects.filter(
            course=course, curriculum__in=current - chosen
        ).delete()

        # additions
        for curriculum in chosen - current:
            CurriculumCourse.objects.get_or_create(course=course, curriculum=curriculum)
