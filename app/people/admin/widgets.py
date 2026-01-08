"""People.Admin.Widgets module.

Usage::

    >>> from app.people.admin.widgets import StaffProfileWidget
    >>> widget = StaffProfileWidget()
    >>> staff = widget.clean("Dr. Jane Doe")
    >>> print(staff.long_name)
"""

from typing import Any, Hashable, Optional, cast

from django.contrib.auth.models import User
from import_export import widgets

from app.academics.admin.widgets import CurriculumWidget
from app.academics.models.curriculum import Curriculum
from app.people.ensure_people import ensure_faculty
from app.people.models.donor import Donor
from app.people.models.faculty import Faculty
from app.people.models.staffs import Staff
from app.people.models.student import Student
from app.people.utils import (
    NameParts,
    cached_entity,
    create_person_factory,
    get_name_parts,
    mk_password,
    parse_name,
    split_name,
)
from app.shared.utils import get_in_row


class StaffProfileWidget(widgets.ForeignKeyWidget):

    def __init__(self):
        self._cache_staff: dict[Hashable, Staff] = {}
        # super().__init__(Staff, field="staff_id")
        super().__init__(Staff)

    def clean(self, value, row=None, *args, **kwargs) -> Optional[Staff]:
        """Create or fetch a Staff from a username.

        The widget get the staff from the username.
        It return or creates a Staff.
        """
        username = (value or "").strip()
        _d, _, last = get_name_parts(row)
        
        if not username and not last:
            return None  # Staff.get_unique_default()

        _create_staff = create_person_factory(username, Staff, _d, lambda s: s.user)
        staff_obj = cached_entity(self._cache_staff, username, _create_staff)
        return staff_obj

    def render(self, value, obj=None) -> str:
        """For the value (staff) for export."""
        return value.long_name if value else ""  # type: ignore[no-any-return]

    def after_import(self, dataset, result, **kwargs):
        """Remove any cache which may be present after import."""
        self._cache_staff = dict()


class UserWidget(widgets.ForeignKeyWidget):
    """Create or resolve a User from a username or the name in ther row."""

    def __init__(self):
        super().__init__(User)
        self._cache_user: dict[Hashable, User] = {}

    def clean(self, value, row=None, *args, **kwargs) -> Optional[User]:
        """Return or create a User from the donor name."""
        username = (value or "").strip()
        _d, _first, _last = get_name_parts(row)

        if not username and not _last:
            return None

        cached = self._cache_user.get(username) if username else False
        if cached:
            return cached

        def _create_user() -> User:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"first_name": _first, "last_name": _last},
            )
            if created:
                user.set_password(mk_password(_first, _last))
                user.save(update_fields=["password"])
            return user

        user_obj = cached_entity(self._cache_user, username, _create_user)

        return user_obj

    def after_import(self, dataset, result, **kwargs):
        """Remove any cache which may be present after import."""
        self.cache_user = dict()


class FacultyUsernameWidget(widgets.ForeignKeyWidget):
    """Ensure a Faculty entry exists for the given username."""

    def __init__(self):
        # field is "id" by default
        self._cache_faculty: dict[Hashable, Faculty] = {}
        super().__init__(Faculty)

    def clean(self, value: str, row=None, *args, **kwargs) -> Faculty:
        """From the username, tries to get a faculty object.

        Create user and faculty if necessary.
        """
        username = (value or "").strip()

        if not username:
            return Faculty.get_unique_default()

        _d, _first, _last = get_name_parts(row)

        _create_faculty = create_person_factory(
            username, Faculty, _d, lambda f: f.staff_profile.user
        )

        faculty_obj = cached_entity(self._cache_faculty, username, _create_faculty)
        return faculty_obj

    def after_import(self, dataset, result, **kwargs):
        """Remove any cache which may be present after import."""
        self.cache_faculty = dict()


class StudentUserWidget(widgets.ForeignKeyWidget):
    """Ensure a Student User exists."""

    def __init__(self):
        # field is "id" by default
        self._cache_student: dict[Hashable, Student] = {}
        super().__init__(Student)

    def clean(self, value: str, row=None, *args, **kwargs) -> Student | None:
        """From the student name (and an id), gets a Student object.

        Create user and student objects if necessary.
        Use the extra column student_id to desambiguate sames names
        and create uniq username.
        """
        username = (value or "").strip()
        _stdid = row.get("student_id")

        if not username or not _stdid:
            return None

        _d, _first, _last = get_name_parts(row)

        def _create_student() -> Student:
            student, _created = Student.objects.get_or_create(
                username=username,
                student_id=_stdid,
                defaults=_d,
            )
            if _created:
                student.user.set_password(mk_password(_first, _last))
                student.user.save(update_fields=["password"])

            return cast(Student, student)

        # _create_student = create_person_factory(username, Student, _d, lambda s: s.user)

        student_obj = cached_entity(self._cache_student, username, _create_student)
        return student_obj

    def after_import(self, dataset, result, **kwargs):
        """Remove any cache which may be present after import."""
        self.cache_student = dict()


class GradeStudentWidget(widgets.ForeignKeyWidget):
    """Create or resolve a Student using a student_id when missing."""

    def __init__(self):
        super().__init__(Student, field="student_id")
        self._cache_student: dict[str, Student] = {}
        self.curriculum_w = CurriculumWidget()

    def clean(self, value, row=None, *args, **kwargs) -> Student:
        """Return the Student tied to the identifier, creating it if needed."""
        student_id = (value or "").strip()
        if not student_id:
            return Student.get_default()

        cached = self._cache_student.get(student_id)
        if cached is not None:
            return cached

        existing = Student.objects.filter(student_id=student_id).first()
        if existing:
            self._cache_student[student_id] = existing
            return existing

        # Here it means student does not exists and we need to create it

        curriculum_value = get_in_row("curriculum", row)
        curriculum = self.curriculum_w.clean(value=curriculum_value, row=row)
        if curriculum is None:
            curriculum = Curriculum.get_default()

        first_name = get_in_row("student_first_name", row)
        last_name = get_in_row("student_last_name", row)
        _n = parse_name(
            # Return vars with something.
            " ".join(filter(None, [first_name, last_name])).strip(),
            fallback_first="Student",
            fallback_last=student_id,
        )

        username = Student.mk_username(_n.first, _n.last)
        password = mk_password(_n.first, _n.last)
        user = User.objects.create_user(
            username=username,
            first_name=_n.first,
            last_name=_n.last,
            password=password,
        )

        student = Student(
            user=user,
            curriculum=curriculum,
            student_id=student_id,
        )
        student.save()

        self._cache_student[student_id] = student

        return student


class DonorUserWidget(widgets.ForeignKeyWidget):
    """Create or resolve a User for Donor imports."""

    def __init__(self):
        super().__init__(User)
        self._cache_user: dict[str, User] = {}

    def clean(self, value, row=None, *args, **kwargs) -> User:
        """Return or create a User from the donor name."""
        raw_name = (value or "").strip()
        if not raw_name:
            return Donor.get_default().user

        cached = self._cache_user.get(raw_name)
        if cached:
            return cached

        _n = parse_name(raw_name, fallback_last="Donor")
        username = Donor.mk_username(_n.first, _n.last)

        _defaults = {"first_name": _n.first, "last_name": _n.last}
        user, created = User.objects.get_or_create(username=username, defaults=_defaults)
        if created:
            user.set_password(mk_password(_n.first, _n.last))
            user.save(update_fields=["password"])

        self._cache_user[raw_name] = user
        return user


class UserStudentWidget(widgets.ForeignKeyWidget):
    """Import a User from an existing student."""

    def __init__(self):
        # field is "id" by default
        super().__init__(User)
        self._cache_username: dict[str, str] = dict()
        self._exclude_username = set()
        self._cache_user: dict[str, User] = dict()

    def clean(self, value: str, row=None, *args, **kwargs) -> User | None:
        """From the student name (and an id), gets a Student object."""
        if not value:
            return None

        stdid = get_in_row("student_id", row)
        if not stdid:
            return None

        fullname = (value or "").strip()
        _n = parse_name(fullname, fallback_first="Student", fallback_last=fullname)

        if stdid not in self._cache_user:
            username = get_in_row("username", row)
            if not username:
                username = Student.mk_username(
                    _n.first, _n.last, _n.middle, exclude=self._exclude_username
                )
            self._cache_username[stdid] = username
            self._exclude_username |= {username}
            user, _ = User.objects.get_or_create(
                username=username, defaults={"first_name": _n.first, "last_name": _n.last}
            )
            user.set_password(mk_password(_n.first, _n.last))
            user.save(update_fields=["password"])

            self._cache_user[stdid] = user

        return self._cache_user[stdid]

    def after_import(self, dataset, result, **kwargs):
        """Remove any cache which may be present after import."""
        self._exclude_username = set()
        self.cache_username = dict()
        self.cache_student = dict()


class FacultyFullnameWidget(widgets.ForeignKeyWidget):
    """Ensure a Faculty entry exists for the given username."""

    def __init__(self):
        # field is "id" by default
        super().__init__(Faculty)

    def clean(self, value: str, row=None, *args, **kwargs) -> Faculty:
        """From the username or name, tries to get a faculty object.

        Create user and faculty if necessary.
        """
        username = get_in_row("username", row)
        faculty_name = get_in_row("faculty", row)
        name_parts = split_name(faculty_name)

        updated_name = NameParts(
            prefix=get_in_row("prefix_name", row) or name_parts.prefix,
            first=get_in_row("first_name", row) or name_parts.first,
            middle=get_in_row("middle_name", row) or name_parts.middle,
            last=get_in_row("last_name", row) or name_parts.last,
            suffix=get_in_row("suffix_name", row) or name_parts.suffix,
        )

        faculty_obj = ensure_faculty(username, name=updated_name)
        return faculty_obj
