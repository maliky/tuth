# app/academics/admin/forms.py
from django import forms
from django.db import transaction
from django.contrib import admin
from django.contrib.admin.widgets import AutocompleteSelect

from app.academics.models import Course, Curriculum, CurriculumCourse, College
from app.shared.enums import CREDIT_NUMBER
from app.shared.utils import make_course_code


class CourseForm(forms.ModelForm):
    """Admin form exposing a writable 'curricula' field."""

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

    class Meta:
        model = Course
        fields = "__all__"  # keeps our synthetic 'curricula'

    # ──────────────────────────────────────────────────────────
    # initial values & non-required title
    # ──────────────────────────────────────────────────────────
    def __init__(self, *args, **kwargs):
        self.admin_site = kwargs.pop("admin_site", admin.site)
        super().__init__(*args, **kwargs)

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
            name = (self.data.get("name") or "").strip() or self.initial.get("name", "")
            number = (self.data.get("number") or "").strip() or self.initial.get("number", "")
            if name and number:
                code = make_course_code(name, number)
                colleges = list(
                    Course.objects.filter(code=code)
                    .values_list("college_id", flat=True)
                    .distinct()
                )
                if len(colleges) == 1:
                    self.fields["college"].required = False
                    self.initial["college"] = colleges[0]
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
        """
        * Return the Course instance (maybe unsaved).
        * Defer M2M synchronisation until save_m2m().
        """
        self._pending_curricula = set(self.cleaned_data.get("curricula", []))
        course = super().save(commit=commit)
        return course

    def clean(self):
        cleaned = super().clean()
        if (
            not cleaned.get("college")
            and cleaned.get("name")
            and cleaned.get("number")
        ):
            code = make_course_code(cleaned["name"], cleaned["number"])
            colleges = list(
                Course.objects.filter(code=code)
                .values_list("college_id", flat=True)
                .distinct()
            )
            if len(colleges) == 1:
                cleaned["college"] = College.objects.get(pk=colleges[0])
        return cleaned

    @transaction.atomic
    def save_m2m(self):
        """Run *after* the admin has saved the Course (`id` now exists)."""
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
