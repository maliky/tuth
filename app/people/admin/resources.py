"""Resources module."""

from __future__ import annotations

import json
import re

from import_export import fields, resources
from import_export.widgets import DateTimeWidget, Widget

from app.academics.admin.widgets import CurriculumWidget
from app.shared.auth.perms import UserRole

from app.people.admin.widgets import StaffProfileWidget, UserStudentWidget
from app.people.models.staffs import Staff
from app.people.models.faculty import Faculty
from app.people.models.student import Student
from app.people.utils import mk_username, split_name
from app.registry.models.registration import Registration
from app.timetable.admin.widgets.core import (
    SemesterCodeWidget,
    ensure_academic_year_code,
)
from app.timetable.models.semester import Semester


class DirectoryContactResource(resources.ModelResource):
    """Import staff directory rows and create/update Staff profiles."""

    username = fields.Field(column_name="username", attribute="user__username")
    first_name = fields.Field(column_name="first_name", attribute="user__first_name")
    last_name = fields.Field(column_name="last_name", attribute="user__last_name")
    middle_name = fields.Field(column_name="middle_name", attribute="middle_name")
    name_prefix = fields.Field(column_name="name_prefix", attribute="name_prefix")
    name_suffix = fields.Field(column_name="name_suffix", attribute="name_suffix")

    class Meta:
        model = Staff
        import_id_fields = ("user__username",)
        fields = (
            "username",
            "first_name",
            "last_name",
            "middle_name",
            "name_prefix",
            "name_suffix",
        )
        skip_unchanged = True
        report_skipped = True

    def before_import_row(self, row, **kwargs):
        """Get the faculty name and populate the username if empty."""
        raw_name = (row.get("faculty") or row.get("name") or "").strip()
        prefix, first, middle, last, suffix = split_name(raw_name)
        row.update(
            {
                "name_prefix": prefix,
                "first_name": first,
                "middle_name": middle,
                "last_name": last,
                "name_suffix": suffix,
            }
        )
        if not row.get("username"):
            row["username"] = mk_username(first, last, unique=True)


class FacultyResource(resources.ModelResource):
    """Import-Export Faculty staff.

    CSV columns:
    faculty        :long display name (“Dr. Jane A. Doe PhD”…)
    college_code   :optional – defaults to “COAS”
    """

    staff_profile = fields.Field(
        attribute="staff_profile",
        column_name="faculty",
        widget=StaffProfileWidget(),
    )

    class Meta:
        model = Faculty
        import_id_fields = ("staff_profile",)
        fields = ("staff_profile",)
        skip_unchanged = True
        report_skipped = False
        use_bulk = True

    def after_save_instance(self, instance, row, **kwargs):
        """Assign the faculty group to the related user."""
        if kwargs.get("dry_run"):
            return None

        user = instance.staff_profile.user
        group = UserRole.FACULTY.value.group
        user.groups.add(group)

        return super().after_save_instance(instance, row, **kwargs)


class StudentInfoTermWidget(Widget):
    """Parse StudentInfo term strings (e.g. '2022/2023, 2nd Semes')."""

    term_pattern = re.compile(
        r"(?P<start>\d{4})/(?P<end>\d{4}),\s*(?P<label>[A-Za-z0-9\s/]+)", re.IGNORECASE
    )

    def __init__(self, fallback_column: str | None = None) -> None:
        super().__init__()
        self.fallback_column = fallback_column
        self.legacy_widget = SemesterCodeWidget()

    def clean(self, value, row=None, *args, **kwargs):
        semester = self._parse_student_info_term(value)
        if semester:
            return semester

        if self.fallback_column and row:
            legacy_value = row.get(self.fallback_column)
            if legacy_value:
                return self.legacy_widget.clean(
                    legacy_value,
                    row=row,
                    *args,
                    **kwargs,
                )

        return None

    def _parse_student_info_term(self, raw_value: str | None) -> Semester | None:
        if not raw_value:
            return None

        _match = self.term_pattern.match(raw_value.strip())
        if not _match:
            return None

        label = _match.group("label").lower()

        if "1st" in label or "first" in label:
            sem_no = 1
        elif "2nd" in label or "second" in label:
            sem_no = 2
        elif "vac" in label:
            sem_no = 3
        else:
            return None

        code = f"{_match.group('start')[-2:]}-{_match.group('end')[-2:]}"
        academic_year = ensure_academic_year_code(code)
        semester, _ = Semester.objects.get_or_create(
            academic_year=academic_year,
            number=sem_no,
        )
        return semester


class StudentResource(resources.ModelResource):
    """Resource for bulk importing Student rows."""

    # I only see Long_name student ID and date of birth
    # Should populate the pk field directly
    user = fields.Field(
        attribute="user", column_name="student_name", widget=UserStudentWidget()
    )

    current_enrolled_semester = fields.Field(
        attribute="current_enrolled_semester",
        column_name="TermLastEnrolled",
        widget=StudentInfoTermWidget(fallback_column="current_enrolled_sem"),
    )
    entry_semester = fields.Field(
        attribute="entry_semester",
        column_name="TermFirstEntered",
        widget=StudentInfoTermWidget(fallback_column="entry_semester"),
    )
    curriculum = fields.Field(
        attribute="curriculum", column_name="major", widget=CurriculumWidget()
    )
    bio = fields.Field(attribute="bio", column_name="bio")

    # ~~~~~~~~~~~~~~~~ demographic fields ~~~~~~~~~~~~~~~~~

    birth_date = fields.Field(
        attribute="birth_date",
        column_name="birth_date",
        widget=DateTimeWidget("%Y-%m-%d %H:%M:%S"),
    )
    # marital_status = fields.Field(
    #     attribute="marital_status",
    #     column_name="marital_status",
    # )
    # nationality = fields.Field(attribute="nationality", column_name="nationality")
    # gender = fields.Field(attribute="gender", column_name="gender")

    class Meta:
        model = Student
        import_id_fields = ("student_id",)
        fields = (
            "student_id",
            "user",
            "curriculum",
            "current_enrolled_semester",
            "entry_semester",
            "nationality",
            "birth_date",
            "marital_status",
            "gender",
            "bio",
        )
        skip_unchanged = True
        report_skipped = False
        use_bulk = False  # do not use because ressources is down row by row

    METRIC_COLUMNS = [
        "CumAttemptedHours",
        "CumRetainedHours",
        "CumEarnedHours",
        "CumQualityHours",
        "CumQualityPoints",
        "CumGPA",
        "CumAttemptedHoursLocal",
        "CumRetainedHoursLocal",
        "CumEarnedHoursLocal",
        "CumQualityHoursLocal",
        "CumQualityPointsLocal",
        "CumGPALocal",
        "ClassLevel",
        "EnrollmentStatusID",
        "HomeCountry",
        "TermFirstEntered",
        "TermLastEnrolled",
        "NumDependents",
        "ConfidentialInfoFlag",
        "PENVerified",
        "DisableWebConnectPortal",
        "VeteranStatusID",
        "TimeCreated",
        "TimeModified",
    ]

    def before_import_row(self, row, **kwargs):
        """Inject derived columns to capture StudentInfo data."""
        account_id = row.get("AccountID")
        if account_id and not row.get("student_id"):
            row["student_id"] = account_id

        home_country = row.get("HomeCountry")
        if home_country:
            row.setdefault("nationality", home_country)

        if account_id and not row.get("student_name"):
            existing_student = Student.objects.filter(student_id=account_id).first()
            if existing_student:
                row["student_name"] = existing_student.long_name

        # ensure legacy columns receive a value for backward compatibility
        if row.get("current_enrolled_sem") and not row.get("TermLastEnrolled"):
            row["TermLastEnrolled"] = row["current_enrolled_sem"]
        if row.get("entry_semester") and not row.get("TermFirstEntered"):
            row["TermFirstEntered"] = row["entry_semester"]

        metrics = {}
        for column in self.METRIC_COLUMNS:
            value = row.get(column)
            if value not in (None, ""):
                metrics[column] = value

        if metrics:
            row["bio"] = json.dumps(metrics)

        return super().before_import_row(row, **kwargs)

    def do_instance_save(self, instance, is_create) -> None:
        """Overide the instance save operation."""
        instance.save()
        pass

    def before_save_instance(self, instance, row, **kwargs) -> None:
        """Overide operation juste before save."""
        # import ipdb; ipdb.set_trace()
        pass

    def after_save_instance(self, instance, row, **kwargs) -> None:
        """Assign the student group to the user when importing."""
        if kwargs.get("dry_run") or instance.user is None:
            return
        # group = UserRole.STUDENT.value.group
        # instance.user.groups.add(group)
        # import ipdb; ipdb.set_trace()
