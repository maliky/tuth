"""Resources module."""

from __future__ import annotations

import json
import re

from import_export import fields, resources
from import_export.widgets import DateWidget, Widget

from app.academics.admin.widgets import CurriWgt
from app.people.admin.resources_mapping import (
    FACULTY_HEADER_MAP,
    GENDER_MAP,
    STUDENT_HEADER_MAP,
    USER_HEADER_MAP,
)
from app.people.admin.widgets import (
    StaffProfileWgt,
    UserStdWgt,
    UserWgt,
)
from app.people.models.donor import Donor
from app.people.models.faculty import Faculty
from app.people.models.staffs import Staff
from app.people.models.student import Student
from app.shared.auth.perms import UserRole
from app.shared.utils import get_in_row
from app.timetable.admin.core_widgets import SemCodeWgt
from app.timetable.ensures import ensure_academic_year_code
from app.timetable.models.semester import Semester
from app.timetable.utils import (
    get_academic_year,
    normalize_sem_code,
)

# > widgets : columns name first (from the resource) and then the model field/attribute


class StaffResource(resources.ModelResource):
    """Import staff directory rows and create/update Staff profiles."""

    user = fields.Field(
        column_name="username", attribute="user", widget=UserWgt(model=Staff)
    )

    class Meta:
        model = Staff
        import_id_fields = ("username",)
        fields = ("user", "username", "middle_name", "prefix_name", "suffix_name")
        skip_unchanged = True
        report_skipped = False

    def after_save_instance(self, instance, row, **kwargs):
        """Assign the Staff group to the related user."""
        if kwargs.get("dry_run"):
            return None

        user = instance.user
        group = UserRole.STAFF.value.group
        user.groups.add(group)

        return super().after_save_instance(instance, row, **kwargs)


class FacultyResource(resources.ModelResource):
    """Import-Export Faculty staff.

    CSV columns:
    faculty        :long display name (“Dr. Jane A. Doe PhD”…)
    college_code   :optional – defaults to “COAS”
    """

    staff_profile = fields.Field(
        column_name="username",
        attribute="staff_profile",
        widget=StaffProfileWgt(),
    )

    class Meta:
        model = Faculty
        import_id_fields = ("staff_profile",)
        fields = ("staff_profile",)
        skip_unchanged = True
        report_skipped = False
        use_bulk = False

    def before_import(self, dataset):
        headers = dataset.headers or []
        dataset.headers = [FACULTY_HEADER_MAP.get(h, h) for h in headers]

    def after_save_instance(self, instance, row, **kwargs):
        """Assign the faculty group to the related user."""
        if kwargs.get("dry_run"):
            return None

        user = instance.staff_profile.user
        group = UserRole.FACULTY.value.group
        user.groups.add(group)

        return super().after_save_instance(instance, row, **kwargs)


class StdResource(resources.ModelResource):
    """Resource for importing Student objects from different csv files."""

    # Columns needs to be created on the fly
    user = fields.Field(column_name="username", attribute="user", widget=UserStdWgt())
    # to be taken from gp table StudentInfo
    curriculum = fields.Field(
        column_name="curriculum_shortname",
        attribute="primary_curriculum",
        widget=CurriWgt(),
    )
    birth_date = fields.Field(
        column_name="birth_date", attribute="birth_date", widget=DateWidget()
    )
    entry_semester = fields.Field(
        column_name="entry_semester_no",
        attribute="entry_semester",
        widget=SemCodeWgt(),
    )
    last_enrolled_semester = fields.Field(
        column_name="last_enrolled_semester",
        attribute="last_enrolled_semester",
        widget=SemCodeWgt(),
    )

    class Meta:
        model = Student
        import_id_fields = ("student_id",)
        fields = (
            "user",
            "bio",
            "long_name",
            "birth_date",
            "birth_place",
            "curriculum",
            "emergency_contact",
            "entry_semester",
            "father_address",
            "father_name",
            "first_name",
            "gender",
            "last_enrolled_semester",
            "last_name",
            "last_school_attended",
            "marital_status",
            "middle_name",
            "mother_address",
            "mother_name",
            "nationality",
            "origin_county",
            "personal_email",
            "phone_no",
            "physical_address",
            "prefix_name",
            "student_id",
            "suffix_name",
            "username",
        )
        skip_unchanged = True
        report_skipped = False
        use_bulk = False

    def before_import(self, dataset):
        headers = dataset.headers or []
        dataset.headers = [STUDENT_HEADER_MAP.get(h, h) for h in headers]

    def before_import_row(self, row, **kwargs):
        """Inject derived columns to capture StudentInfo data."""
        # student_name = get_in_row("student_name", row)

        # Synthesize student_name when source data provides split columns
        # if not student_name:
        #     first = get_in_row("first_name", row)
        #     middle = get_in_row("middle_name", row)
        #     last = get_in_row("last_name", row)
        #     row["student_name"] = parse_name(f"{first} {middle} {last}").to_string()

        # > I should not allow creation of new major or curriculum
        # > If a row does not fit because of the major or curriculum, I should log it
        # > and create manual (eventulay the major or curriculum)
        # > I should also do a fuzzy search for a matching curriculum
        # curri_value = get_in_row("curriculum_short_name", row)
        # if len(curri_value) > 40:
        #     row["curriculum_short_name"] = curri_value[:40]

        _g = get_in_row("gender", row).lower()
        row["gender"] = GENDER_MAP.get(_g, _g)

        # entry_semester normalization
        entry_year_val = get_in_row("entry_year", row)
        entry_sem_val = get_in_row("entry_semester", row) or get_in_row(
            "entry_semester_no", row
        )
        entry_sem_val = normalize_sem_code(
            entry_sem_val,
            year_value=entry_year_val,
            sem_value=get_in_row("entry_semester_no", row),
        )
        if entry_sem_val:
            row["entry_semester"] = entry_sem_val

        # last_enrolled_semester normalization
        last_sem_val = get_in_row("last_enrolled_semester", row) or get_in_row(
            "last_enrolled_semester_no", row
        )
        last_sem_val = normalize_sem_code(
            last_sem_val,
            year_value=get_academic_year(),
            sem_value=get_in_row("last_enrolled_semester_no", row),
        )
        if last_sem_val:
            row["last_enrolled_semester"] = last_sem_val

        bio_keys = [(k, v) for k, v in STUDENT_HEADER_MAP.items() if "bio_" in v]
        bio_info = {v: row.get(k) for (k, v) in bio_keys if row.get(k, None) is not None}
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
        column_name="username", attribute="user", widget=UserWgt(model=Donor)
    )

    class Meta:
        model = Donor
        import_id_fields = ("username",)
        fields = ("user", "username", "bio")
        skip_unchanged = True
        report_skipped = False

    def before_import_row(self, row, **kwargs):
        """Keep the original donor column content for auditing."""
        username = get_in_row("username", row)
        if not username:
            row["username"] = ""

        raw_value = get_in_row("donors", row)
        if raw_value:
            row["bio"] = raw_value
        return super().before_import_row(row, **kwargs)
