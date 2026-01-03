"""Resources module."""

from __future__ import annotations

import json
import re

from import_export import fields, resources
from import_export.widgets import DateTimeWidget, DateWidget, Widget

from app.academics.admin.widgets import CurriculumWidget
from app.people.admin.resources_mapping import (
    FACULTY_COLUMN_MAP,
    GENDER_MAP,
    STUDENT_HEADER_MAP,
)
from app.people.admin.widgets import (
    DonorUserWidget,
    StaffProfileWidget,
    UserStudentWidget,
)
from app.people.models.donor import Donor
from app.people.models.faculty import Faculty
from app.people.models.staffs import Staff
from app.people.models.student import Student
from app.people.utils import mk_username, parse_name, split_name
from app.registry.models.registration import Registration
from app.shared.auth.perms import UserRole
from app.shared.utils import get_in_row
from app.timetable.admin.widgets.core import (
    SemesterCodeWidget,
    SemesterWidget,
    ensure_academic_year_code,
)
from app.timetable.models.semester import Semester
from app.timetable.utils import (
    get_academic_year,
    get_semester_code,
    normalize_academic_year,
)


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
        _n = split_name(raw_name)
        row.update(_n.to_dict())

        if not row.get("username"):
            row["username"] = mk_username(_n.first, _n.last, _n.middle, unique=True)


class FacultyResource(resources.ModelResource):
    """Import-Export Faculty staff.

    CSV columns:
    faculty        :long display name (“Dr. Jane A. Doe PhD”…)
    college_code   :optional – defaults to “COAS”
    """

    staff_profile = fields.Field(
        attribute="staff_profile",
        column_name="staff_profile",
        widget=StaffProfileWidget(),
    )

    # Instructor, name_prefix,first_n, middle_n, last_n, name_suffix, username
    class Meta:
        model = Faculty
        import_id_fields = ("staff_profile",)
        fields = "staff_profile"
        skip_unchanged = True
        report_skipped = False
        use_bulk = False

    def before_import_row(self, row, **kwargs):
        """Normalize incoming faculty columns and build a full name."""
        for incoming, canonical in FACULTY_COLUMN_MAP.items():
            if incoming in row and canonical not in row:
                row[canonical] = row.get(incoming, "")
                row.pop(incoming, None)

        prefix = get_in_row("name_prefix", row)
        first = get_in_row("first_name", row)
        middle = get_in_row("middle_name", row)
        last = get_in_row("last_name", row)
        suffix = get_in_row("name_suffix", row)

        tokens = [prefix, first, middle, last, suffix]
        full_name = " ".join(t for t in tokens if t).strip()
        if full_name:
            row["faculty_fullname"] = full_name
            if "staff_profile" not in row:
                row["staff_profile"] = full_name
        row.pop("faculty", None)

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
        self.legacy_widget = SemesterCodeWidget()

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None

        _match = self.term_pattern.match(value.strip())
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

    # columns needs to be created on the fly
    user = fields.Field(
        attribute="user", column_name="student_name", widget=UserStudentWidget()
    )
    # to be taken from gp table StudentInfo
    curriculum = fields.Field(
        attribute="curriculum",
        column_name="curriculum_short_name",
        widget=CurriculumWidget(),
    )
    birth_date = fields.Field(
        attribute="birth_date",
        column_name="birth_date",
        widget=DateWidget(["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]),
    )
    entry_semester = fields.Field(
        attribute="entry_semester",
        column_name="entry_semester",
        widget=SemesterCodeWidget(),
    )
    last_enrolled_semester = fields.Field(
        attribute="last_enrolled_semester",
        column_name="last_enrolled_semester",
        widget=SemesterCodeWidget(),
    )

    class Meta:
        model = Student
        import_id_fields = ("student_id",)
        fields = (
            "bio",
            "birth_date",
            "birth_place",
            "curriculum",  # ->
            "emergency_contact",
            "entry_semester",  # ->
            "father_address",
            "father_name",
            "gender",
            "last_enrolled_semester",
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
        use_bulk = False

    def before_import_row(self, row, **kwargs):
        """Inject derived columns to capture StudentInfo data."""
        for legacy_col, canonic_col in STUDENT_HEADER_MAP.items():
            value = get_in_row(legacy_col, row)
            if value and not row.get(canonic_col):
                row[canonic_col] = value
            row.pop(legacy_col, None)
        # From them on we use canonic_col names

        student_name = get_in_row("student_name", row)

        # Synthesize student_name when source data provides split columns
        if not student_name:
            first = get_in_row("first_name", row)
            middle = get_in_row("middle_name", row)
            last = get_in_row("last_name", row)
            row["student_name"] = parse_name(f"{first} {middle} {last}")

        # > I should not allow creation of new major or curriculum
        # > If a row does not fit because of the major or curriculum, I should log it
        # > and create manual (eventulay the major or curriculum)
        # > I should also do a fuzzy search for a matching curriculum
        curri_value = get_in_row("curriculum_short_name", row)
        if len(curri_value) > 40:
            row["curriculum_short_name"] = curri_value[:40]

        _g = get_in_row("gender", row).lower()
        row["gender"] = GENDER_MAP.get(_g, _g)

        # entry_semester normalization
        entry_year_val = get_in_row("entry_year", row)
        entry_sem_val = get_in_row("entry_semester_no", row)
        if not entry_sem_val:
            entry_sem_val = get_semester_code(
                sem_value=get_in_row("entry_semester_no", row),
                year_value=entry_year_val,
            )
        elif "_Sem" not in entry_sem_val:
            entry_sem_val = get_semester_code(
                sem_value=entry_sem_val, year_value=entry_year_val
            )
        if entry_sem_val:
            row["entry_semester"] = entry_sem_val

        # last_enrolled_semester normalization
        last_sem_val = get_in_row("last_enrolled_semester_no", row)
        if not last_sem_val:
            last_sem_val = get_semester_code(
                sem_value=get_in_row("last_enrolled_semester_no", row),
                year_value=get_academic_year(),
            )
        if last_sem_val:
            row["last_enrolled_semester"] = last_sem_val

        bio_keys = [(k, v) for k, v in STUDENT_HEADER_MAP.items() if "bio_" in v]
        bio_info = {v: row.get(k) for (k, v) in bio_keys if row.get(k, None) is None}
        row["bio"] = json.dumps(bio_info)

        return super().before_import_row(row, **kwargs)

    def do_instance_save(self, instance, is_create) -> None:
        """Overide the instance save operation."""
        instance.save()
        pass

    def before_save_instance(self, instance, row, **kwargs) -> None:
        """Overide operation juste before save."""
        pass

    def after_save_instance(self, instance, row, **kwargs):
        """Assign the student group to the user when importing."""
        if kwargs.get("dry_run") or instance.user is None:
            return
        group = UserRole.STUDENT.value.group
        instance.user.groups.add(group)
        return super().after_save_instance(instance, row, **kwargs)


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
