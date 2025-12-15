"""Core module."""

from django.contrib import admin
from django.contrib import admin as dj_admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.urls import reverse
from django.utils.html import format_html_join
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from app.people.admin.filters import (
    FacultyCollegeFilter,
    FacultyDepartmentFilter,
    FacultyDepartmentFilterAC,
    FacultyGroupAC,
    StaffCollegeFilter,
    StaffDepartmentFilter,
    StudentCollegeFilter,
    StudentCurriculumFilter,
)
from app.people.admin.merges import MergeUsersMixin
from app.people.admin.mixins import (
    DuplicatePreviewMixin,
    MergePeopleMixin,
)
from app.people.admin.resources import FacultyResource
from app.people.forms.base import PersonFormMixin
from app.people.forms.faculty import FacultyForm
from app.people.forms.person import (
    DonorForm,
    StaffForm,
    StudentForm,
)
from app.people.matching import name_similarity
from app.people.models.donor import Donor
from app.people.models.faculty import Faculty
from app.people.models.role_assignment import RoleAssignment
from app.people.models.staffs import Staff
from app.people.models.student import Student
from app.registry.admin.inlines import DocumentStaffInline, DocumentStudentInline
from app.shared.admin.filters import (
    BaseCollegeFilter,
    BaseDepartmentFilter,
    CurriculumByCollegeFilter,
    StudentLevelFilter,
)
from app.shared.admin.mixins import CollegeRestrictedAdmin, DepartmentRestrictedAdmin
from app.timetable.admin.inlines import SectionInline

User = get_user_model()


# ---- User admin with merge action ----


try:
    dj_admin.site.unregister(User)
except Exception:
    pass


@dj_admin.register(User)
class MergeableUserAdmin(MergeUsersMixin, dj_admin.ModelAdmin):
    """Lightweight user admin with merge action."""

    duplicate_threshold = 0.9
    list_display = (
        "username",
        "first_name",
        "last_name",
        "email",
        "is_active",
        "possible_duplicates",
    )
    search_fields = ("username", "first_name", "last_name", "email")

    def possible_duplicates(self, obj):
        """Reuse the duplicate preview logic at the user level."""
        base_name = f"{obj.first_name} {obj.last_name}".strip()
        qs = User.objects.exclude(pk=obj.pk).filter(last_name__iexact=obj.last_name)
        rows = []
        for other in qs[:50]:
            other_name = f"{other.first_name} {other.last_name}".strip()
            score = name_similarity(base_name, other_name)
            if score >= self.duplicate_threshold:
                url = reverse(
                    f"admin:{other._meta.app_label}_{other._meta.model_name}_change",
                    args=[other.pk],
                )
                rows.append((url, other.username, score))
        if not rows:
            return ""
        safe_rows = []
        for url, label, score in rows[:3]:
            safe_rows.append((url, label, f"{score:.2f}"))
        return format_html_join(
            ", ",
            '<a href="{}">{}</a> ({})',
            safe_rows,
        )


@admin.register(Faculty)
class FacultyAdmin(DuplicatePreviewMixin, CollegeRestrictedAdmin):
    """Admin options for :class:~app.people.models.Faculty.

    Displays the staff profile with optional filtering by college. The faculty
    resource is used for import/export operations.
    """

    # form =
    resource_class = FacultyResource
    form = FacultyForm

    list_display = (
        "faculty_name",
        "faculty_staff_id",
        "academic_rank",
        "primary_assignment",
        "get_division",
        "get_department",
        "possible_duplicates",
    )
    list_filter = [
        FacultyDepartmentFilterAC,
        FacultyGroupAC,
        FacultyCollegeFilter,
        # "staff_profile__user__groups",
        # ('college', admin.RelatedOnlyFieldListFilter),
        # ('staff_profile__department', admin.RelatedOnlyFieldListFilter)
    ]

    search_fields = (
        "staff_profile__staff_id",
        "staff_profile__long_name",
        "staff_profile__user__first_name",
        "staff_profile__user__last_name",
        "academic_rank",
    )
    autocomplete_fields = ("staff_profile", "college")
    inlines = [SectionInline]
    fieldsets = [
        (
            "User Information",
            {
                "fields": FacultyForm.USER_FIELDS,
                "description": (
                    "Username / e-mail are auto-generated from the name fields. "
                    "To change the password you need to open the user box."
                ),
            },
        ),
        ("Faculty Information", {"fields": FacultyForm.FACULTY_FIELDS}),
        (
            "Work Information",
            {
                "classes": ["collapse"],
                "fields": FacultyForm.STAFF_FIELDS,
            },
        ),
    ]

    @admin.display(description="Long Name", ordering="staff_profile__user__first_name")
    def faculty_name(self, obj):
        """Add the long name to the admin."""
        return obj.staff_profile.long_name

    @admin.display(description="Faculty Staff ID", ordering="staff_profile__staff_id")
    def faculty_staff_id(self, obj):
        """Add the long name to the admin."""
        return obj.staff_profile.staff_id

    @admin.display(description="Primary Assignment")
    def primary_assignment(self, obj):
        """Show the department/college that receives most sections for the faculty."""
        return obj.primary_assignment_label or "-"


@admin.register(Donor)
class DonorAdmin(SimpleHistoryAdmin, GuardedModelAdmin):
    """Admin management for :class:~app.people.models.Donor.

    Shows each donor's user and ID with autocomplete for the user relation.
    """

    form = DonorForm
    list_display = ("long_name", "donor_id", "username", "donor_bio")
    search_fields = ("donor_id", "long_name", "user__first_name", "user__last_name")
    readonly_fields = ("donor_id",)
    fieldsets = [
        (
            "User Account",
            {
                "classes": ["collapse"],
                "fields": PersonFormMixin.USER_FIELDS,
                "description": (
                    "Username / e-mail are auto-generated from the name fields. "
                    "To change the password you need to open the user box."
                ),
            },
        ),
        (None, {"fields": PersonFormMixin.STANDARD_USER_FIELDS}),
    ]

    @admin.display(description="Bio")
    def donor_bio(self, obj):
        """Show a short excerpt of the donor bio column."""
        if not obj.bio:
            return ""
        return obj.bio if len(obj.bio) <= 80 else f"{obj.bio[:77]}…"


@admin.register(Staff)
class StaffAdmin(MergePeopleMixin, DuplicatePreviewMixin, DepartmentRestrictedAdmin):
    """Admin management for :class:~app.people.models.Staff.

    Provides detailed fieldsets for personal and work information. Important
    fields like staff_id are read-only to avoid accidental edits.
    """

    form = StaffForm
    list_display = (
        "long_name",
        "staff_id",
        "position",
        "roles",
        "possible_duplicates",
    )
    search_fields = (
        "staff_id",
        "long_name",
        "user__username",
        "user__first_name",
        "user__last_name",
        "department__short_name",
    )
    list_filter = (
        StaffCollegeFilter,
        StaffDepartmentFilter,
        "user__groups",
    )
    ordering = ("staff_id",)
    readonly_fields = ("staff_id",)
    inlines = [DocumentStaffInline]
    fieldsets = [
        (
            "User Account",
            {
                "fields": PersonFormMixin.USER_FIELDS,
                "description": (
                    "Username / e-mail are auto-generated from the name fields. "
                    "To change the password you need to open the user box."
                ),
            },
        ),
        ("Personal Details", {"fields": PersonFormMixin.STANDARD_USER_FIELDS}),
        (
            "Work Information",
            {
                "classes": ["collapse"],
                "fields": StaffForm.SPECIFIC_FIELDS,
            },
        ),
    ]


@admin.register(Student)
class StudentAdmin(
    MergePeopleMixin,
    DuplicatePreviewMixin,
    SimpleHistoryAdmin,
    ImportExportModelAdmin,
    GuardedModelAdmin,
):
    """Admin interface for :class:~app.people.models.Student.

    list_display shows the related user and student ID with search enabled
    on both fields. Import/export is supported via ImportExportModelAdmin.
    """

    form = StudentForm
    list_display = (
        "long_name",
        "student_id",
        "birth_date",
        "curriculum",
        "entry_semester",
        "possible_duplicates",
    )
    search_fields = (
        "student_id",
        "long_name",
        "user__username",
        "user__first_name",
        "user__last_name",
    )
    # list_editable = ("curriculum",)
    list_filter = (
        StudentCollegeFilter,
        StudentCurriculumFilter,
        "entry_semester",
        StudentLevelFilter,
    )
    readonly_fields = ("student_id",)
    inlines = [DocumentStudentInline]
    fieldsets = [
        (
            "Student Informations",
            {
                "fields": StudentForm.SPECIFIC_FIELDS,
            },
        ),
        (
            "User Account",
            {
                "classes": ["collapse"],
                "fields": PersonFormMixin.USER_FIELDS,
                "description": (
                    "Username / e-mail are auto-generated from the name fields. "
                    "To change the password you need to open the user box."
                ),
            },
        ),
        (
            "User Details",
            {"classes": ["collapse"], "fields": PersonFormMixin.STANDARD_USER_FIELDS},
        ),
    ]

    # -------------- helpers for readonly panel --------------
    def save_model(self, request, obj, form, change):
        """Save the model."""
        # The form.save() handles creating and linking the User.
        obj.save()


@admin.register(RoleAssignment)
class RoleAssignmentAdmin(SimpleHistoryAdmin, GuardedModelAdmin):
    list_display = ("user", "group", "start_date")
