"""Core Admin module for academics."""

from typing import Iterable, Literal, TypeAlias, cast, no_type_check

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.db import transaction
from django.db.models import Count
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from app.academics.models.curriculum_course import CurriculumCourse
from app.academics.models import (
    CurriculumStudentEnrollment,
    College,
    Course,
    Curriculum,
    CurriculumStatus,
    Department,
    Prerequisite,
)
from app.people.models.student import Student
from app.people.models.student_curriculum_enrollment import StudentCurriculumEnrollment
from app.finance.models.invoice import Invoice
from app.shared.admin.filters import BaseCollegeFilter
from app.shared.admin.mixins import (
    CollegeRestrictedAdmin,
    DepartmentRestrictedAdmin,
    ProtectedDeleteAdminMixin,
)
from app.people.admin.mixins import MergeWizardMixin, ModelT

from .actions import (
    attach_fee_stacks,
    update_curriculum,
    update_department,
    update_level_number,
)
from .filters import (
    CourseCollegeFilter,
    CourseCurriculumFilter,
    CurriculumFilterAC,
    CurriculumCourseFacultyFilterAC,
    CurriculumCourseStudentFilterAC,
    DepartmentCurriculumFilterAC,
    DepartmentFilterAC,
)
from .inlines import (
    CourseCurriculumInline,
    CourseFeeStackInline,
    CurriculumCourseInline,
    DepartmentCourseInline,
    PrerequisiteInline,
    RequiresInline,
)
from .merges import (
    MERGE_CHOICE_KEEP_SOURCE,
    MERGE_CHOICE_KEEP_TARGET,
    MERGE_CHOICE_MERGE,
    MERGE_CHOICE_SKIP,
    ConflictChoiceByCourseIdT,
    merge_courses_action,
    merge_courses_by_short_code_action,
    merge_curricula,
    merge_departments,
    merge_curriculum_courses,
    list_curriculum_course_conflicts,
)
from app.academics.prereq_graph import export_prereq_graph
from .resources import (
    CollegeResource,
    CourseResource,
    CurriculumCourseResource,
    CurriculumResource,
    DepartmentResource,
    PrerequisiteResource,
)
from django.utils.text import Truncator
from django.conf import settings
from app.timetable.admin.filters import SemesterFilterAC

ModelChoiceFieldT: TypeAlias = forms.ModelChoiceField | forms.ModelMultipleChoiceField
MergeFieldSourceChoiceT = Literal["target", "source"]


class CurriculumMergeConflictForm(forms.Form):
    """Collect target selection, curriculum field picks, and conflict decisions."""

    FIELD_FROM_TARGET: MergeFieldSourceChoiceT = "target"
    FIELD_FROM_SOURCE: MergeFieldSourceChoiceT = "source"
    CONFLICT_FIELD_PREFIX = "conflict__"
    MERGE_FIELD_PREFIX = "field__"

    def __init__(
        self,
        *,
        curricula: list[Curriculum],
        merge_fields: tuple[str, ...],
        conflict_course_ids: list[int],
        data=None,
    ) -> None:
        super().__init__(data=data)
        self._curriculum_map = {
            str(item.pk): item for item in curricula if item.pk is not None
        }
        self._merge_fields = merge_fields
        self._conflict_course_ids = conflict_course_ids
        target_choices = [
            (str(item.pk), self._curriculum_label(item))
            for item in curricula
            if item.pk is not None
        ]
        self.fields["target_id"] = forms.ChoiceField(
            label="Target curriculum",
            choices=target_choices,
            required=True,
        )
        self.fields["target_id"].initial = (
            target_choices[0][0] if target_choices else None
        )
        for field_name in merge_fields:
            self.fields[self.merge_field_key(field_name)] = forms.ChoiceField(
                label=self._field_label(field_name),
                choices=(
                    (self.FIELD_FROM_TARGET, "Keep target value"),
                    (self.FIELD_FROM_SOURCE, "Use source value"),
                ),
                widget=forms.RadioSelect,
                required=True,
                initial=self.FIELD_FROM_TARGET,
            )
        for course_id in conflict_course_ids:
            self.fields[self.conflict_field_key(course_id)] = forms.ChoiceField(
                label=f"Conflict action for course #{course_id}",
                choices=(
                    (MERGE_CHOICE_KEEP_TARGET, "Keep target row"),
                    (MERGE_CHOICE_KEEP_SOURCE, "Keep source values"),
                    (MERGE_CHOICE_MERGE, "Merge sections/grades"),
                    (MERGE_CHOICE_SKIP, "Skip this course"),
                ),
                required=True,
                initial=MERGE_CHOICE_MERGE,
            )

    @staticmethod
    def _curriculum_label(item: Curriculum) -> str:
        """Build a compact curriculum label for merge choices."""
        college_code = getattr(getattr(item, "college", None), "code", "-")
        return f"{item.short_name} ({college_code})"

    @classmethod
    def merge_field_key(cls, field_name: str) -> str:
        """Return the POST key used by one curriculum field merge choice."""
        return f"{cls.MERGE_FIELD_PREFIX}{field_name}"

    @classmethod
    def conflict_field_key(cls, course_id: int) -> str:
        """Return the POST key used by one conflicting course choice."""
        return f"{cls.CONFLICT_FIELD_PREFIX}{course_id}"

    @staticmethod
    def _field_label(field_name: str) -> str:
        """Convert a model field name to a readable admin label."""
        return field_name.replace("_", " ").title()

    def clean_target_id(self) -> str:
        """Validate target_id against selected curricula."""
        target_id = str(self.cleaned_data["target_id"])
        if target_id not in self._curriculum_map:
            raise forms.ValidationError("Selected target is not in the action selection.")
        return target_id

    def field_value_source(self, field_name: str) -> MergeFieldSourceChoiceT:
        """Return whether a field should come from target or source curriculum."""
        key = self.merge_field_key(field_name)
        selected = self.cleaned_data.get(key, self.FIELD_FROM_TARGET)
        if selected == self.FIELD_FROM_SOURCE:
            return self.FIELD_FROM_SOURCE
        return self.FIELD_FROM_TARGET

    def get_conflict_choices(self) -> ConflictChoiceByCourseIdT:
        """Return validated conflict choices keyed by course id."""
        choices: ConflictChoiceByCourseIdT = {}
        for course_id in self._conflict_course_ids:
            field_name = self.conflict_field_key(course_id)
            raw_choice = self.cleaned_data.get(field_name, MERGE_CHOICE_MERGE)
            if raw_choice not in {
                MERGE_CHOICE_KEEP_TARGET,
                MERGE_CHOICE_KEEP_SOURCE,
                MERGE_CHOICE_MERGE,
                MERGE_CHOICE_SKIP,
            }:
                continue
            choices[course_id] = raw_choice
        return choices


@admin.register(College)
class CollegeAdmin(SimpleHistoryAdmin, ImportExportModelAdmin, GuardedModelAdmin):
    """Admin settings for :class:~app.academics.models.College.

    Displays the college code and name and provides search capability on both
    fields via list_display and search_fields.
    """

    resource_class = CollegeResource
    list_display = (
        "code",
        "long_name",
        # "faculty_count_link",
        # "course_count_link",
        # "curriculum_count_link",
        # "department_chair_links",
        # "student_counts_by_level_link"
    )
    search_fields = ("code", "long_name")

    @admin.display(description="Curricula")
    def curriculum_count_link(self, obj: College):
        count = obj.curricula.count()
        url = reverse("admin:academics_curriculum_changelist") + (
            f"?college__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)

    @admin.display(description="Faculty")
    def faculty_count_link(self, obj: College):
        count = obj.faculty_count
        url = reverse("admin:people_faculty_changelist") + (
            f"?college__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)

    @admin.display(description="Courses")
    def course_count_link(self, obj: College):
        count = obj.course_count
        url = reverse("admin:academics_course_changelist") + (
            f"?department__college__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)

    @admin.display(description="Departments")
    def department_chair_links(self, obj: College):
        """Link departments filtered by college."""
        qs = obj.departments.all().order_by("shortname")
        rows = []
        for dept in qs:
            url = reverse("admin:academics_department_changelist") + (
                f"?college__id__exact={obj.id}&id__exact={dept.id}"
            )
            rows.append((url, dept.code))
        if not rows:
            return ""
        return format_html_join(", ", '<a href="{}">{}</a>', rows)

    @admin.display(description="Active curricula")
    def active_curricula_list(self, obj: College):
        if not getattr(obj, "pk", None):
            return "Save the college to view curricula."
        active = obj.curricula.filter(is_active=True).order_by("short_name")
        rows = [
            (
                reverse("admin:academics_curriculum_change", args=[cur.pk]),
                cur.short_name,
            )
            for cur in active
        ]
        if not rows:
            return "None"
        return format_html_join(", ", '<a href="{}">{}</a>', rows)

    @admin.display(description="Inactive curricula")
    def inactive_curricula_list(self, obj: College):
        if not getattr(obj, "pk", None):
            return "Save the college to view curricula."
        inactive = obj.curricula.filter(is_active=False).order_by("short_name")
        rows = [
            (
                reverse("admin:academics_curriculum_change", args=[cur.pk]),
                cur.short_name,
            )
            for cur in inactive
        ]
        if not rows:
            return "None"
        return format_html_join(", ", '<a href="{}">{}</a>', rows)

    fields = ("code", "long_name", "active_curricula_list", "inactive_curricula_list")
    readonly_fields = ("active_curricula_list", "inactive_curricula_list")

    @admin.display(description="Students by level")
    def student_counts_by_level_link(self, obj: College):
        """Link to students filtered by college and computed level."""
        rows = []
        students = list(Student.objects.filter(curriculum__college=obj))
        for level in ("Freshman", "Sophomore", "Junior", "Senior"):
            count = sum(1 for s in students if getattr(s, "class_level", "") == level)
            url = reverse("admin:people_student_changelist") + (
                f"?curriculum__college__id__exact={obj.id}&class_level={level}"
            )
            rows.append((url, level, count))
        return format_html_join(" | ", '<a href="{}">{}</a>: {}', rows)


@admin.register(Course)
class CourseAdmin(DepartmentRestrictedAdmin):
    """Admin interface for Course.

    Provides course management with extra tools:
    - list_display shows the code, title, credits and college fields.
    - list_filter allows filtering by curriculum.
    - inlines embed related sections and prerequisite relations.
    - actions exposes the update_college bulk action.

    Example:
        Select multiple courses and choose Update college from the actions
        dropdown to assign them all to a different college.
    """

    resource_class = CourseResource
    list_display = (
        "short_code",
        "title",
        "department",
        "grade_count",
    )
    # Curricula column removed from list_display; keep helper for reuse elsewhere.
    # Use list filters for curricula to avoid reverse M2M autocomplete errors.
    # > TODO: Add the list of student enrolled in this course the current semester.
    inlines = [
        CourseFeeStackInline,
        RequiresInline,
        PrerequisiteInline,
        CourseCurriculumInline,
    ]
    list_select_related = ("department",)
    list_editable = ("department",)
    list_filter = (
        SemesterFilterAC,
        DepartmentFilterAC,
        CourseCurriculumFilter,
        CourseCollegeFilter,
    )

    list_per_page = 100
    list_max_show_all = 500

    search_fields = ("short_code", "department__code", "title")
    fields = ("short_code", "department", "number", "title", "description")
    # Actions include manual merge and short_code-based merge helpers.
    actions = [
        update_department,
        attach_fee_stacks,
        merge_courses_action,
        merge_courses_by_short_code_action,
    ]

    def get_queryset(self, request):
        """Prefetch curricula for link rendering in list_display."""
        qs = super().get_queryset(request)
        qs = qs.prefetch_related("curricula").annotate(
            grade_total=Count("in_curriculum_courses__sections__grade", distinct=True)
        )
        curriculum_id = request.GET.get("curricula__id__exact") or request.GET.get(
            "in_curriculum_courses__curriculum"
        )
        if curriculum_id:
            try:
                curriculum_id = int(curriculum_id)
            except (TypeError, ValueError):
                return qs
            return qs.filter(curricula__id=curriculum_id)
        return qs

    def lookup_allowed(self, lookup, value, request=None):
        """Allow legacy curriculum lookup for course filters."""
        if lookup == "in_curriculum_courses__curriculum":
            return True
        return super().lookup_allowed(lookup, value, request)

    @admin.display(description="Curricula")
    def curricula_links(self, obj: Course):
        """Link each curriculum name to its admin change page."""
        rows = [
            (reverse("admin:academics_curriculum_change", args=[cur.pk]), cur.short_name)
            for cur in obj.curricula.all().order_by("short_name")
        ]
        if not rows:
            return "-"
        return format_html_join(", ", '<a href="{}">{}</a>', rows)

    @admin.display(description="Grades", ordering="grade_total")
    def grade_count(self, obj: Course) -> int:
        """Return the number of grades recorded for this course."""
        return int(getattr(obj, "grade_total", 0) or 0)

    def get_form(self, request, obj=None, **kwargs):
        """Return the admin form with dep ordered by their shortname."""
        form = super().get_form(request, obj, **kwargs)
        department_field = form.base_fields.get("department")

        if isinstance(
            department_field,
            (forms.ModelChoiceField, forms.ModelMultipleChoiceField),
        ):
            # Mypy: cast to model choice fields before ordering the queryset.
            department_field = cast(ModelChoiceFieldT, department_field)
            if department_field.queryset is not None:
                # Mypy: ensure queryset is set before chaining queryset methods.
                department_field.queryset = department_field.queryset.select_related(
                    "college"
                ).order_by("college__code", "shortname")
        return form


@admin.register(Curriculum)
class CurriculumAdmin(MergeWizardMixin, CollegeRestrictedAdmin):
    """Admin options for Curriculum.

    Key features:
    - inlines manage related curriculum courses inline.
    - list_display includes short and long names with the college.
    - list_filter allows filtering by college and active state.
    """

    resource_class = CurriculumResource
    # add the action button on the import form
    list_display = (
        "short_name",
        "long_name",
        "college",
        "is_active",
        "status",
        "course_count_link",
        "student_count",
    )
    list_filter = (SemesterFilterAC, "college")
    list_editable = ("status", "is_active", "college")
    autocomplete_fields = ("college",)
    inlines = [CurriculumCourseInline]

    # list_selected_relate reduces the number of queries in db
    list_select_related = ("college",)
    search_fields = ("short_name", "long_name")
    # Keep short_name out of the wizard to avoid active-name uniqueness collisions.
    merge_fields = ("long_name", "college", "status", "is_active", "description")
    actions = ["export_prereq_graph_action", "copy_curriculum_action"]

    def student_count(self, obj):
        """Adding a link to the student number."""
        count = obj.student_count()
        url = reverse("admin:people_student_changelist") + (
            f"?student_registrations__section__curriculum_course__curriculum={obj.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)

    @admin.display(description="Courses")
    def course_count_link(self, obj):
        """Link course counts to the course changelist for this curriculum."""
        count = obj.course_count()
        url = reverse("admin:academics_course_changelist") + (
            f"?curricula__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)

    @admin.action(description="Export prerequisite graph (JSON/JS + DOT + PNG)")
    def export_prereq_graph_action(self, request, queryset):
        """Export prerequisite graphs for selected curricula."""
        if not queryset:
            self.message_user(request, "No curricula selected.", level=messages.WARNING)
            return

        outputs = []
        for curriculum in queryset:
            try:
                outputs.append(export_prereq_graph(curriculum))
            except Exception as exc:  # pragma: no cover - admin message path
                self.message_user(
                    request,
                    f"Failed for {curriculum.short_name}: {exc}",
                    level=messages.ERROR,
                )
                continue

        if not outputs:
            return

        links = []
        for output in outputs:
            slug = output.json_path.stem
            view_url = reverse("academics_prereq_graph", args=[slug])
            png_url = f"{settings.MEDIA_URL}Prereq/{output.png_path.name}"
            links.append(
                format_html(
                    '<a href="{view}">{label}</a> (<a href="{png}">PNG</a>)',
                    view=view_url,
                    png=png_url,
                    label=f"View graph {slug}",
                )
            )
        msg = format_html_join(" · ", "{}", ((link,) for link in links))
        self.message_user(
            request,
            format_html("Generated prerequisite graphs: {}.", msg),
            level=messages.SUCCESS,
        )

    def _build_copy_short_name(self, source: Curriculum) -> str:
        """Return a readable short name for a copied curriculum."""
        max_len = int(Curriculum._meta.get_field("short_name").max_length or 40)
        base_seed = source.short_name.strip() or "Curriculum"
        base = f"{base_seed} copy".strip()[:max_len]
        candidate = base
        idx = 2
        while Curriculum.objects.filter(
            college=source.college, short_name=candidate
        ).exists():
            suffix = f" {idx}"
            keep_len = max(1, max_len - len(suffix))
            candidate = f"{base[:keep_len]}{suffix}"
            idx += 1
        return candidate

    @admin.action(description="Copy curriculum with courses")
    def copy_curriculum_action(self, request, queryset):
        """Duplicate selected curricula and clone their programmed courses."""
        if not queryset:
            self.message_user(request, "No curricula selected.", level=messages.WARNING)
            return

        created_rows: list[tuple[str, str, int]] = []
        selected = queryset.select_related("college")
        for source in selected:
            try:
                with transaction.atomic():
                    target = Curriculum.objects.create(
                        short_name=self._build_copy_short_name(source),
                        long_name=source.long_name,
                        college=source.college,
                        description=source.description,
                        status_id="pending",
                        is_active=False,
                    )
                    source_rows = CurriculumCourse.objects.filter(curriculum=source)
                    for row in source_rows:
                        CurriculumCourse.objects.create(
                            curriculum=target,
                            course_id=row.course_id,
                            is_required=row.is_required,
                            is_elective=row.is_elective,
                            credit_hours_id=row.credit_hours_id,
                            semester_number=row.semester_number,
                            level_number=row.level_number,
                            year_number=row.year_number,
                            required_group_number=row.required_group_number,
                            min_validated_credits=row.min_validated_credits,
                        )
                    copy_count = source_rows.count()
                copy_url = reverse("admin:academics_curriculum_change", args=[target.pk])
                created_rows.append((copy_url, target.short_name, copy_count))
            except Exception as exc:  # pragma: no cover - admin message path
                self.message_user(
                    request,
                    f"Failed to copy {source.short_name}: {exc}",
                    level=messages.ERROR,
                )

        if not created_rows:
            return
        links = format_html_join(
            " · ",
            '<a href="{}">{}</a> ({} courses)',
            created_rows,
        )
        self.message_user(
            request,
            format_html("Created curriculum copies: {}.", links),
            level=messages.SUCCESS,
        )

    def merge_records_action(self, request, queryset):
        """Merge exactly two curricula with per-conflict decisions."""
        selected_ids = request.POST.getlist(ACTION_CHECKBOX_NAME)
        candidates = list(
            queryset.filter(pk__in=selected_ids).select_related("college").order_by("id")
        )
        if len(candidates) != 2:
            self.message_user(
                request,
                "Select exactly two curricula to run the guided merge.",
                level=messages.WARNING,
            )
            return None

        target_id_hint = request.POST.get("target_id")
        target = candidates[0]
        if target_id_hint:
            hinted = next(
                (item for item in candidates if str(item.pk) == str(target_id_hint)),
                None,
            )
            if hinted is not None:
                target = hinted
        source = next(item for item in candidates if item.pk != target.pk)
        conflicts, non_conflicting = list_curriculum_course_conflicts(target, source)
        conflict_course_ids = [
            source_row.course_id for _target_row, source_row in conflicts
        ]
        form_data = request.POST if request.POST.get("apply_merge") else None
        form = CurriculumMergeConflictForm(
            data=form_data,
            curricula=candidates,
            merge_fields=self.get_merge_fields(request),
            conflict_course_ids=conflict_course_ids,
        )
        if request.POST.get("apply_merge") and form.is_valid():
            target_id = form.cleaned_data["target_id"]
            target = next(item for item in candidates if str(item.pk) == str(target_id))
            source = next(item for item in candidates if item.pk != target.pk)
            # Recompute conflicts for the selected target/source orientation.
            conflicts, _ = list_curriculum_course_conflicts(target, source)
            updated_fields: list[str] = []
            merge_fields = self.get_merge_fields(request)
            for field_name in merge_fields:
                if form.field_value_source(field_name) != form.FIELD_FROM_SOURCE:
                    continue
                source_value = getattr(source, field_name)
                if getattr(target, field_name) == source_value:
                    continue
                setattr(target, field_name, source_value)
                updated_fields.append(field_name)
            conflict_choices = form.get_conflict_choices()
            # Keep a stable transaction for both target updates and merge moves.
            with transaction.atomic():
                if updated_fields:
                    target.save(update_fields=updated_fields)
                summary = merge_curricula(
                    target,
                    [source],
                    conflict_choices=conflict_choices,
                )
            self._message_curriculum_merge_summary(request, target, summary)
            return None

        merge_field_rows = [
            {
                "label": field_name.replace("_", " ").title(),
                "field": form[CurriculumMergeConflictForm.merge_field_key(field_name)],
            }
            for field_name in self.get_merge_fields(request)
        ]
        conflict_rows = []
        for target_row, source_row in conflicts:
            field_key = CurriculumMergeConflictForm.conflict_field_key(
                source_row.course_id
            )
            conflict_rows.append(
                {
                    "target_row": target_row,
                    "source_row": source_row,
                    "target_sections": target_row.sections.count(),
                    "source_sections": source_row.sections.count(),
                    "source_invoices": Invoice.objects.filter(
                        curriculum_course=source_row
                    ).count(),
                    "field": form[field_key],
                }
            )

        context = {
            "title": "Guided curriculum merge",
            "form": form,
            "objects": candidates,
            "action_name": "merge_records_action",
            "action_checkbox_name": ACTION_CHECKBOX_NAME,
            "target": target,
            "source": source,
            "merge_field_rows": merge_field_rows,
            "conflict_rows": conflict_rows,
            "non_conflicting": non_conflicting,
            "merge_choice_merge": MERGE_CHOICE_MERGE,
            "merge_choice_keep_target": MERGE_CHOICE_KEEP_TARGET,
            "merge_choice_keep_source": MERGE_CHOICE_KEEP_SOURCE,
            "merge_choice_skip": MERGE_CHOICE_SKIP,
        }
        return TemplateResponse(
            request,
            "admin/academics/curriculum/merge_curricula_conflicts.html",
            context,
        )

    merge_records_action.short_description = "Guided merge selected curricula"  # type: ignore[attr-defined]

    def _message_curriculum_merge_summary(
        self,
        request,
        target: Curriculum,
        summary: dict[str, int],
    ) -> None:
        """Emit consistent merge feedback messages for curriculum merges."""
        self.message_user(
            request,
            (
                f"Merged {summary['curricula_merged']} curriculum/curricula into "
                f"{target.short_name}."
            ),
            level=messages.SUCCESS,
        )
        if summary["curricula_retained"]:
            self.message_user(
                request,
                (
                    "Some source curricula were retained due to conflicts. "
                    "Review the per-course choices and invoice blockers."
                ),
                level=messages.WARNING,
            )
        if summary["conflicts_merged"]:
            self.message_user(
                request,
                f"Merged {summary['conflicts_merged']} conflicting course row(s).",
                level=messages.INFO,
            )
        if summary["conflicts_kept_target"]:
            self.message_user(
                request,
                (
                    "Kept the target programmed course for "
                    f"{summary['conflicts_kept_target']} conflict(s)."
                ),
                level=messages.INFO,
            )
        if summary["conflicts_kept_source"]:
            self.message_user(
                request,
                (
                    "Applied source programmed-course values for "
                    f"{summary['conflicts_kept_source']} conflict(s)."
                ),
                level=messages.INFO,
            )
        if summary["conflicts_skipped"]:
            self.message_user(
                request,
                f"Skipped {summary['conflicts_skipped']} conflict(s) by choice.",
                level=messages.WARNING,
            )
        if summary["sections_merged"]:
            self.message_user(
                request,
                f"Merged {summary['sections_merged']} conflicting section(s).",
                level=messages.WARNING,
            )
        if summary["sections_skipped_grade_conflict"]:
            self.message_user(
                request,
                (
                    "Skipped "
                    f"{summary['sections_skipped_grade_conflict']} section merge(s) "
                    "because overlapping students had different grade values."
                ),
                level=messages.WARNING,
            )
        if summary["prerequisites_skipped"]:
            self.message_user(
                request,
                f"Skipped {summary['prerequisites_skipped']} duplicate prerequisite(s).",
                level=messages.WARNING,
            )
        if summary["skipped_invoices"]:
            self.message_user(
                request,
                f"Skipped {summary['skipped_invoices']} curriculum course(s) with invoices.",
                level=messages.WARNING,
            )
        if summary["credit_hours_conflicts"]:
            self.message_user(
                request,
                (
                    "Credit hours differ on "
                    f"{summary['credit_hours_conflicts']} curriculum course(s)."
                ),
                level=messages.WARNING,
            )
        if summary["is_required_conflicts"]:
            self.message_user(
                request,
                (
                    "Required flag differs on "
                    f"{summary['is_required_conflicts']} curriculum course(s)."
                ),
                level=messages.WARNING,
            )
        if summary["is_elective_conflicts"]:
            self.message_user(
                request,
                (
                    "Elective flag differs on "
                    f"{summary['is_elective_conflicts']} curriculum course(s)."
                ),
                level=messages.WARNING,
            )
        if summary["sections_retained_protected"]:
            self.message_user(
                request,
                (
                    "Retained "
                    f"{summary['sections_retained_protected']} conflicting section(s) "
                    "because grades still protect them."
                ),
                level=messages.WARNING,
            )
        if summary["protected_deletes"]:
            self.message_user(
                request,
                (
                    "Could not delete "
                    f"{summary['protected_deletes']} source object(s) because grades "
                    "protect related sections."
                ),
                level=messages.WARNING,
            )

    def merge_records(self, target: ModelT, sources: Iterable[ModelT]) -> dict[str, int]:
        """Merge curricula using the shared merge helper."""
        target_curriculum = cast(Curriculum, target)
        source_curricula = cast(Iterable[Curriculum], sources)
        request = getattr(self, "_merge_request", None)
        self._warn_curriculum_merge_precheck(
            request,
            target_curriculum,
            source_curricula,
        )
        summary = merge_curricula(target_curriculum, source_curricula)
        if request and summary.get("curricula_retained", 0):
            self.message_user(
                request,
                (
                    "Some source curricula were retained due to invoice conflicts. "
                    "Review scripts/curriculum_merge_conflicts.sql before retrying."
                ),
                level=messages.WARNING,
            )
        return {
            "merged": summary.get("curricula_merged", 0),
            "sections_merged": summary.get("sections_merged", 0),
            "sections_skipped_grade_conflict": summary.get(
                "sections_skipped_grade_conflict", 0
            ),
            "skipped_invoices": summary.get("skipped_invoices", 0),
            "credit_hours_conflicts": summary.get("credit_hours_conflicts", 0),
            "is_required_conflicts": summary.get("is_required_conflicts", 0),
            "is_elective_conflicts": summary.get("is_elective_conflicts", 0),
        }

    # Avoid mypy internal error on the nested curriculum overlap query.
    @no_type_check
    def _warn_curriculum_merge_precheck(
        self,
        request,
        target: Curriculum,
        sources: Iterable[Curriculum],
    ) -> None:
        """Warn when the pre-merge SQL check should be reviewed."""
        if request is None:
            return
        source_ids = [cur.pk for cur in sources if cur.pk]
        if not source_ids or not target.pk:
            return
        overlap_count = CurriculumCourse.objects.filter(
            curriculum=target,
            course_id__in=CurriculumCourse.objects.filter(
                curriculum_id__in=source_ids
            ).values("course_id"),
        ).count()
        if overlap_count:
            self.message_user(
                request,
                (
                    "Course overlaps detected; run "
                    "scripts/curriculum_merge_conflicts.sql before merging."
                ),
                level=messages.WARNING,
            )


@admin.register(CurriculumCourse)
class CurriculumCourseAdmin(
    ProtectedDeleteAdminMixin, MergeWizardMixin, CollegeRestrictedAdmin
):
    """Admin screen for :class:~app.academics.models.CurriculumCourse.

    list_display shows the curriculum and related course while
    autocomplete_fields make lookups faster. list_select_related joins
    both relations for efficient queries.
    """

    resource_class = CurriculumCourseResource
    college_field = "curriculum__college"
    merge_fields = (
        "curriculum",
        "course",
        "credit_hours",
        "is_required",
        "is_elective",
    )
    list_display = (
        "course_display",
        "department_link",
        "curriculum",
        "level_number",
        # Keep list compact; min_validated_credits remains editable on the form view.
        "section_count_link",
        "faculties_links",
    )
    list_filter = (
        SemesterFilterAC,
        "curriculum__college",
        CurriculumFilterAC,
        DepartmentFilterAC,
        "level_number",
        CurriculumCourseFacultyFilterAC,
        CurriculumCourseStudentFilterAC,
    )

    list_editable = ("curriculum", "level_number")
    autocomplete_fields = ("curriculum", "course")
    list_select_related = ("curriculum", "course")
    # Include short_code to support curriculum course autocomplete lookups.
    search_fields = ("curriculum__short_name", "course__code", "course__short_code")
    list_per_page = 100
    list_max_show_all = 500

    # Optional inline to list all curricula for this curriculum_course.
    # Advanced requirement-group UI is intentionally hidden for now.
    inlines = ()

    ordering = ("course__short_code",)
    actions = [update_curriculum, update_level_number]

    def get_queryset(self, request):
        """Annotate section totals and prefetch faculty for list_display."""
        qs = super().get_queryset(request)
        return (
            qs.select_related("course__department")
            .prefetch_related("sections__faculty__staff_profile__user")
            .annotate(section_total=Count("sections", distinct=True))
        )

    def get_protected_delete_single_message(
        self, request, obj, protected_count: int
    ) -> str:
        """Return curriculum-course specific message for protected single deletes."""
        return (
            "Cannot delete programmed course because grades depend on one or more "
            f"related sections ({protected_count} protected record(s)). Reassign "
            "grades first."
        )

    def get_protected_delete_bulk_message(self, request, protected_count: int) -> str:
        """Return curriculum-course specific message for protected bulk deletes."""
        return (
            "Bulk delete stopped: some programmed courses still have grade-protected "
            f"sections ({protected_count} protected record(s)). Reassign grades first."
        )

    def merge_object_label(self, obj) -> str:
        """Return a label for merge choices."""
        curriculum_course = cast(CurriculumCourse, obj)
        course = curriculum_course.course
        curriculum = curriculum_course.curriculum
        course_label = course.short_code or course.code or str(course)
        curriculum_label = curriculum.short_name or curriculum.long_name
        return f"{curriculum_label} | {course_label}"

    def merge_records(self, target, sources):
        """Merge curriculum courses into the target selection."""
        target_course = cast(CurriculumCourse, target)
        return merge_curriculum_courses(target_course, sources)

    @admin.display(description="Course")
    def course_display(self, obj: CurriculumCourse) -> str:
        """Truncate course display to avoid very long values in list view."""
        return Truncator(str(obj.course)).chars(50)

    @admin.display(description="Department")
    def department_link(self, obj: CurriculumCourse):
        """Link to departments filtered to this course's department."""
        dept = getattr(obj.course, "department", None)
        if not dept:
            return "-"
        url = reverse("admin:academics_course_changelist") + (f"?department={dept.id}")
        return format_html('<a href="{}">{}</a>', url, dept.shortname)

    @admin.display(description="Sections", ordering="section_total")
    def section_count_link(self, obj):
        """Link to sections filtered by this curriculum course."""
        count = getattr(obj, "section_total", None)
        if count is None:
            count = obj.sections.count()
        url = reverse("admin:timetable_section_changelist") + (
            f"?curriculum_course__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)

    # Advanced requirement-group link is kept dormant until the model is re-enabled.
    @admin.display(description="Requirement groups")
    def requirement_groups_link(self, obj: CurriculumCourse):
        """Return requirement-group count when dormant advanced UI is re-enabled."""
        return obj.requirement_groups.count()

    @admin.display(description="Faculties")
    def faculties_links(self, obj):
        """List linked faculty teaching sections for this curriculum course."""
        faculties = []
        seen = set()
        for section in obj.sections.all():
            faculty = section.faculty
            if not faculty or faculty.pk in seen:
                continue
            seen.add(faculty.pk)
            faculties.append(
                (
                    reverse("admin:people_faculty_change", args=[faculty.pk]),
                    faculty.staff_profile.long_name,
                )
            )
        if not faculties:
            return "-"
        return format_html_join(", ", '<a href="{}">{}</a>', faculties)


@admin.register(CurriculumStatus)
class CurriculumStatusAdmin(admin.ModelAdmin):
    """Lookup admin for CurriculumStatus."""

    search_fields = ("code", "label")
    list_display = ("code", "label")


@admin.register(CurriculumStudentEnrollment)
class CurriculumStudentEnrollmentAdmin(CollegeRestrictedAdmin):
    """Admin interface for student program enrollments."""

    college_field = "curriculum__college"
    list_display = (
        "student",
        "curriculum",
        "is_primary",
        "is_active",
        "entry_semester",
    )
    list_filter = (
        "curriculum__college",
        CurriculumFilterAC,
        "is_primary",
        "is_active",
    )
    search_fields = (
        "student__student_id",
        "student__long_name",
        "curriculum__short_name",
        "curriculum__long_name",
    )
    autocomplete_fields = ("student", "curriculum", "entry_semester", "exit_semester")
    list_select_related = ("student__user", "curriculum__college")
    actions = ("merge_two_selected_rows", "merge_selected_rows_by_student_id")

    @staticmethod
    def _rows_blocked_by_entry_semester(
        target_row: StudentCurriculumEnrollment,
        source_row: StudentCurriculumEnrollment,
    ) -> bool:
        """Return True when both rows carry different non-null entry semesters."""
        target_entry_id = target_row.entry_semester_id
        source_entry_id = source_row.entry_semester_id
        return bool(
            target_entry_id and source_entry_id and target_entry_id != source_entry_id
        )

    @staticmethod
    def _merge_row_pair(
        target_row: StudentCurriculumEnrollment,
        source_row: StudentCurriculumEnrollment,
    ) -> bool:
        """Merge source row into target row and delete source.

        Returns:
            bool: True when merge happened, False when blocked by entry semester rule.
        """
        if CurriculumStudentEnrollmentAdmin._rows_blocked_by_entry_semester(
            target_row,
            source_row,
        ):
            return False

        update_fields: list[str] = []
        # Keep the non-null semester when one side is missing, otherwise keep target.
        if not target_row.entry_semester_id and source_row.entry_semester_id:
            target_row.entry_semester_id = source_row.entry_semester_id
            update_fields.append("entry_semester")
        if not target_row.exit_semester_id and source_row.exit_semester_id:
            target_row.exit_semester_id = source_row.exit_semester_id
            update_fields.append("exit_semester")
        if not target_row.is_primary and source_row.is_primary:
            target_row.is_primary = True
            update_fields.append("is_primary")
        if not target_row.is_active and source_row.is_active:
            target_row.is_active = True
            update_fields.append("is_active")
        if target_row.creation_date > source_row.creation_date:
            target_row.creation_date = source_row.creation_date
            update_fields.append("creation_date")

        if target_row.is_primary:
            StudentCurriculumEnrollment.objects.filter(
                student_id=target_row.student_id,
                is_primary=True,
            ).exclude(pk=target_row.pk).update(is_primary=False)
        if update_fields:
            target_row.save(update_fields=update_fields)
        source_row.delete()
        return True

    @admin.action(description="Merge 2 selected enrollment rows")
    @transaction.atomic
    def merge_two_selected_rows(self, request, queryset):
        """Merge exactly two selected rows when semester rule allows it."""
        rows = list(queryset.select_related("student", "entry_semester").order_by("id"))
        if len(rows) != 2:
            self.message_user(
                request,
                "Select exactly 2 rows for this merge action.",
                level=messages.WARNING,
            )
            return
        target_row, source_row = rows[0], rows[1]
        if target_row.student_id != source_row.student_id:
            self.message_user(
                request,
                "Selected rows belong to different students; merge cancelled.",
                level=messages.WARNING,
            )
            return
        merged = self._merge_row_pair(target_row, source_row)
        if not merged:
            self.message_user(
                request,
                "Merge blocked: both rows have different non-null entry semesters.",
                level=messages.WARNING,
            )
            return
        self.message_user(
            request,
            "Merged 2 enrollment rows into the lowest-id row.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Merge selected rows grouped by student id")
    @transaction.atomic
    def merge_selected_rows_by_student_id(self, request, queryset):
        """Merge selected rows per student id using the same semester guard."""
        rows = list(
            queryset.select_related("student", "entry_semester")
            .order_by("student_id", "id")
            .all()
        )
        if len(rows) < 2:
            self.message_user(
                request,
                "Select at least 2 rows to run grouped merge.",
                level=messages.WARNING,
            )
            return

        merged_count = 0
        blocked_count = 0
        grouped_count = 0
        by_student_id: dict[int, list[StudentCurriculumEnrollment]] = {}
        for row in rows:
            by_student_id.setdefault(row.student_id, []).append(row)

        for student_rows in by_student_id.values():
            if len(student_rows) < 2:
                continue
            grouped_count += 1
            target_row = student_rows[0]
            for source_row in student_rows[1:]:
                if self._merge_row_pair(target_row, source_row):
                    merged_count += 1
                    continue
                blocked_count += 1

        if merged_count:
            self.message_user(
                request,
                (
                    f"Merged {merged_count} row(s) across {grouped_count} student group(s)."
                ),
                level=messages.SUCCESS,
            )
        if blocked_count:
            self.message_user(
                request,
                (
                    "Skipped "
                    f"{blocked_count} row(s) because entry semesters were both set and "
                    "different."
                ),
                level=messages.WARNING,
            )
        if not merged_count and not blocked_count:
            self.message_user(
                request,
                "No student groups with at least 2 selected rows were found.",
                level=messages.INFO,
            )


@admin.register(Department)
class DepartmentAdmin(MergeWizardMixin, CollegeRestrictedAdmin):
    """Admin interface for :class:~app.academics.models.Department.

    Shows department code, name and college. autocomplete_fields speeds up
    college selection when editing a department.
    """

    resource_class = DepartmentResource
    merge_fields = ("code", "long_name", "college")
    list_display = (
        "code",
        "long_name",
        "college",
        "course_count_link",
        "faculty_count_link",
    )
    list_filter = [
        "college",
        DepartmentCurriculumFilterAC,
    ]
    list_editable = ("college",)
    search_fields = ("code", "long_name", "college")
    inlines = [DepartmentCourseInline]

    def get_queryset(self, request):
        # > explain the djangonic logic here
        qs = super().get_queryset(request)
        return qs.annotate(
            course_count=Count("courses", distinct=True),
            faculty_total=Count(
                "courses__in_curriculum_courses__sections__faculty", distinct=True
            ),
        ).prefetch_related("courses__curricula")

    @admin.display(description="Courses", ordering="course_count")
    def course_count_link(self, obj):
        """Adding a link to the course number."""
        count = getattr(obj, "course_count", None)
        if count is None:
            count = obj.courses.count()
        url = reverse("admin:academics_course_changelist") + (
            f"?department__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)

    @admin.display(description="Teaching Faculty", ordering="faculty_total")
    def faculty_count_link(self, obj):
        """Link to faculty teaching sections in this department."""
        count = getattr(obj, "faculty_total", None)
        if count is None:
            count = (
                obj.courses.filter(in_curriculum_courses__sections__faculty__isnull=False)
                .values_list("in_curriculum_courses__sections__faculty_id", flat=True)
                .distinct()
                .count()
            )
        url = reverse("admin:people_faculty_changelist") + (
            f"?section__curriculum_course__course__department={obj.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)

    # > Curricula list removed from list_display to reduce page load.

    def merge_records(self, target: ModelT, sources: Iterable[ModelT]) -> dict[str, int]:
        """Merge departments using the shared merge helper."""
        target_department = cast(Department, target)
        source_departments = cast(Iterable[Department], sources)
        summary = merge_departments(target_department, source_departments)
        return {"merged": summary.get("merged", 0)}

    def merge_records_action(self, request, queryset):
        """Warn about college alignment before showing the merge form."""
        response = super().merge_records_action(request, queryset)
        if request.method == "POST" and request.POST.get("apply_merge"):
            return response
        messages.warning(
            request,
            (
                "Review the selected departments carefully. "
                "Departments should belong to the same college before merging."
            ),
        )
        return response


@admin.register(Prerequisite)
class PrerequisiteAdmin(SimpleHistoryAdmin, ImportExportModelAdmin, GuardedModelAdmin):
    """Admin interface for :class:~app.academics.models.Prerequisite.

    Options configured:
    - list_display shows the course, the prerequisite and the curriculum.
    - list_filter uses :class:CurriculumFilter to narrow by curriculum.
    - actions provides update_curriculum for bulk updates.

    Example:
        On the prerequisites list page, select rows and run
        Attach / update curriculum to set a curriculum for them.
    """

    resource_class = PrerequisiteResource
    actions = [update_curriculum]

    # search_fields = ("course", "prerequisite_course") # not permitted no search of fk
    list_display = ("course", "prerequisite_course", "curriculum")
    autocomplete_fields = ("course", "prerequisite_course", "curriculum")
    list_filter = (CurriculumFilterAC,)
    # search_fields = ("course", "prerequisite_course", "curriculum")


# NOTE:
# Advanced grouped prerequisite/corequisite admin stays intentionally unregistered.
# Keep this implementation nearby for later re-activation once the simple model
# transition is complete.
