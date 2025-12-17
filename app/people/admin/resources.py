"""Resources module."""

from __future__ import annotations

import json
import re

from import_export import fields, resources
from import_export.widgets import DateTimeWidget, Widget

from app.academics.admin.widgets import CurriculumWidget
from app.shared.auth.perms import UserRole

from app.people.admin.widgets import (
    StaffProfileWidget,
    UserStudentWidget,
    DonorUserWidget,
)
from app.people.models.staffs import Staff
from app.people.models.faculty import Faculty
from app.people.models.student import Student
from app.people.models.donor import Donor
from app.people.utils import mk_username, split_name
from app.shared.utils import get_in_row, normalize_academic_year
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
        use_bulk = False

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
                kwargs.pop("row", None)
                return self.legacy_widget.clean(legacy_value, row=row, **kwargs)

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
    """Resource for importing Student objects from different csv files."""
    
    user = fields.Field(
        attribute="user", column_name="student_name", widget=UserStudentWidget()
    )
    # to be updated from gp table StudentInfo or registration tables
    current_enrolled_semester = fields.Field(
        attribute="current_enrolled_semester",
        column_name="termlastenrolled",
        widget=StudentInfoTermWidget(fallback_column="current_enrolled_sem"),
    )
    # to be taken from gp table StudentInfo    
    entry_semester = fields.Field(
        attribute="entry_semester",
        column_name="termfirstentered",
        widget=StudentInfoTermWidget(fallback_column="entry_semester"),
    )
    curriculum = fields.Field(
        attribute="curriculum", column_name="major", widget=CurriculumWidget()
    )
    bio = fields.Field(attribute="bio", column_name="bio")
    origin_county = fields.Field(attribute="origin_county", column_name="origin_county")
    birth_place = fields.Field(attribute="birth_place", column_name="birth_place")
    physical_address = fields.Field(attribute="physical_address", column_name="address")
    phone_number = fields.Field(attribute="phone_number", column_name="phone_no")
    last_school_attended = fields.Field(
        attribute="last_school_attended", column_name="last_school_attended"
    )
    reason_for_leaving = fields.Field(
        attribute="reason_for_leaving", column_name="reason_for_leaving"
    )
    father_name = fields.Field(attribute="father_name", column_name="father_name")
    father_address = fields.Field(
        attribute="father_address", column_name="father_address"
    )
    mother_name = fields.Field(attribute="mother_name", column_name="mother_name")
    mother_address = fields.Field(
        attribute="mother_address", column_name="mother_address"
    )
    emergency_contact = fields.Field(
        attribute="emergency_contact", column_name="emergency_contact"
    )

    # ~~~~~~~~~~~~~~~~ demographic fields ~~~~~~~~~~~~~~~~~

    birth_date = fields.Field(
        attribute="birth_date",
        column_name="birth_date",
        widget=DateTimeWidget("%Y-%m-%d %H:%M:%S"),
    )
    # to ignore for now 16/12/2025
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
            "bio",
            "birth_date",
            "birth_place",
            "current_enrolled_semester",  # ->
            "curriculum",  # ->
            "emergency_contact",
            "entry_semester",  # ->
            "father_address",
            "father_name",
            "gender",
            "last_school_attended",
            "marital_status",
            "mother_address",
            "mother_name",
            "nationality",
            "origin_county",
            "phone_number",
            "physical_address",
            "reason_for_leaving",
            "student_id",  #
            "user",  # ->
        )
        skip_unchanged = True
        report_skipped = False
        use_bulk = False  # do not use because ressources is down row by row

    # from studentInfo
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
    GENDER_MAP = {
        "male": "m",
        "m": "m",
        "female": "f",
        "f": "f",
    }

    def before_import_row(self, row, **kwargs):
        """Inject derived columns to capture StudentInfo data."""
        account_id = get_in_row("AccountID", row)
        legacy_id = get_in_row("StudentID", row)
        if (account_id or legacy_id) and not row.get("student_id"):
            row["student_id"] = account_id or legacy_id

        # synthesize student_name when source data provides split columns
        if not row.get("student_name"):
            first = get_in_row("first_name", row) or get_in_row("FirstName", row)
            middle = get_in_row("middle_name", row) or get_in_row("MiddleName", row)
            last = get_in_row("last_name", row) or get_in_row("LastName", row)
            if not first and not last:
                first = "Humpty"
                last = "Dumpty"
                row["first_name"] = first
                row["last_name"] = last
            parts = [first.strip(), middle.strip(), last.strip()]
            fullname = " ".join(part for part in parts if part)
            if fullname:
                row["student_name"] = fullname

        home_country = get_in_row("HomeCountry", row) or get_in_row("nationality", row)
        if home_country:
            row.setdefault("nationality", home_country)

        if account_id and not row.get("student_name"):
            existing_student = Student.objects.filter(student_id=account_id).first()
            if existing_student:
                row["student_name"] = existing_student.long_name

        # > I should not allow creation of new major or curriculum
        # > If a row does not fit because of the major or curriculum, I should log it
        # > and create manual (eventulay the major or curriculum)
        # > I should also do a fuzzy search for a matching curriculum
        major_value = (
            get_in_row("major", row)
            or get_in_row("curriculum_short_name", row)
            or get_in_row("ProgramID", row)
        )
        if major_value:
            row["major"] = major_value[:40]

        gender_raw = get_in_row("gender", row).lower()
        if gender_raw:
            mapped_gender = self.GENDER_MAP.get(gender_raw)
            if mapped_gender:
                row["gender"] = mapped_gender

        enrollment_sem = get_in_row("current_enrolled_sem", row) or get_in_row(
            "enrollement_semester", row
        )
        normalized_year = normalize_academic_year(get_in_row("YearOfEntry", row))
        if enrollment_sem and normalized_year and "_Sem" not in str(enrollment_sem):
            sem_token = str(enrollment_sem).strip()
            try:
                sem_number = int(float(sem_token))
            except ValueError:
                sem_number = None
            if sem_number:
                formatted = f"{normalized_year}_Sem{sem_number}"
                row["current_enrolled_sem"] = formatted
                row.setdefault("entry_semester", formatted)

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
        pass

    def after_save_instance(self, instance, row, **kwargs) -> None:
        """Assign the student group to the user when importing."""
        if kwargs.get("dry_run") or instance.user is None:
            return
        # group = UserRole.STUDENT.value.group
        # instance.user.groups.add(group)
        # import ipdb; ipdb.set_trace()


class DonorResource(resources.ModelResource):
    """Import donors from a simple list of names."""

    user = fields.Field(
        attribute="user",
        column_name="donors",
        widget=DonorUserWidget(),
    )
    bio = fields.Field(
        attribute="bio",
        column_name="bio",
    )

    class Meta:
        model = Donor
        import_id_fields = ("user",)
        fields = ("user", "bio")
        skip_unchanged = True
        report_skipped = False

    def before_import_row(self, row, **kwargs):
        """Keep the original donor column content for auditing."""
        raw_value = get_in_row("donors", row)
        if raw_value:
            row["bio"] = raw_value
        return super().before_import_row(row, **kwargs)
