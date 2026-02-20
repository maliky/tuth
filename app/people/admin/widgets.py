"""People.Admin.Wgts module.

Usage::

    >>> from app.people.admin.widgets import StaffProfileWgt
    >>> widget = StaffProfileWgt()
    >>> staff = widget.clean("Dr. Jane Doe")
    >>> print(staff.long_name)

Namnig Convetion XYWgt return a X instance for a YRessource Call.
"""

from typing import Any, Hashable, Optional, cast

from django.contrib.auth.models import User
from import_export import widgets

from app.academics.admin.widgets import CurriWgt
from app.academics.models.curriculum import Curriculum
from app.people.ensure_people import ensure_faculty
from app.people.models.core import AbstractPerson
from app.people.models.donor import Donor
from app.people.models.faculty import Faculty
from app.people.models.staffs import Staff
from app.people.models.student import Student
from app.people.models.student_curriculum_enrollment import set_primary_std_curri_enroll
from app.people.utils import (
    cached_entity,
    create_person_factory,
    name_parts_from_row,
    mk_password,
    mk_username,
)
from app.shared.utils import get_in_row, parse_str


class StaffProfileWgt(widgets.ForeignKeyWidget):

    def __init__(self):
        self._cache_staff: dict[Hashable, Staff] = {}
        super().__init__(Staff)

    def clean(self, value, row=None, *args, **kwargs) -> Optional[Staff]:
        """Create or fetch a Staff from a username.

        The widget get the staff from the username.
        It return or creates a Staff.
        """
        username = parse_str(value)
        name = name_parts_from_row(row, fullname_key="long_name")

        if not username:
            if not name.last:
                return None  # Staff.get_unique_dft()
            username = Staff.mk_username(*name.parts(), unique=False)

        cached = self._cache_staff.get(username)
        if cached:
            return cached

        staff_factory = create_person_factory(
            username, Staff, name.to_dict(), lambda s: s.user
        )
        staff_obj = cached_entity(self._cache_staff, username, staff_factory)

        return staff_obj

    def render(self, value, obj=None) -> str:
        """For the value (staff) for export."""
        return value.long_name if value else ""  # type: ignore[no-any-return]

    def after_import(self, dataset, result, **kwargs):
        """Remove any cache which may be present after import."""
        self.cache_staff = dict()


class UserWgt(widgets.ForeignKeyWidget):
    """Create or resolve a User from a username or the name in ther row."""

    def __init__(self, model: type[AbstractPerson] = Staff):
        super().__init__(User)
        self.model = model
        self._cache_user: dict[Hashable, User] = {}

    def clean(self, value, row=None, *args, **kwargs) -> Optional[User]:
        """Return or create a User from username or name."""
        username = parse_str(value)
        _n = name_parts_from_row(row, fullname_key="donors")

        if not username:
            if not _n.last:
                return None  # Staff.get_unique_dft()
            # it is understood that same user name return the same user
            # even if prefix and suffix differ
            # for bare user there is no fuzzy search.
            username = self.model.mk_username(*_n.parts())

        cached = self._cache_user.get(username)
        if cached:
            return cached

        def _create_user() -> User:
            user, created = User.objects.get_or_create(
                username=username, defaults=_n.to_dict(full=False)
            )
            if created:
                user.set_password(mk_password(_n.first, _n.last))
                user.save(update_fields=["password"])
            return user

        return cached_entity(self._cache_user, username, _create_user)

    def after_import(self, dataset, result, **kwargs):
        """Remove any cache which may be present after import."""
        self.cache_user = dict()


class FacultyUsernameWgt(widgets.ForeignKeyWidget):
    """Get a Faculty give a username or a name in the row."""

    def __init__(self):
        super().__init__(Faculty)

    def clean(self, value: str, row=None, *args, **kwargs) -> Optional[Faculty]:
        """From the username, tries to get a faculty object.

        Create user and faculty if necessary.
        """
        username = parse_str(value)
        name = name_parts_from_row(row, fullname_key="faculty")

        if not username:
            if not name.last:
                return None  # Staff.get_unique_dft()

        faculty = create_person_factory(
            username, Faculty, name.to_dict(), lambda f: f.staff_profile.user
        )
        faculty_obj = faculty()
        return faculty_obj


class FacultyFullnameWgt(widgets.ForeignKeyWidget):
    """Ensure a Faculty entry exists for the given username."""

    def __init__(self):
        # field is "id" by default
        super().__init__(Faculty)

    def clean(self, value: str, row=None, *args, **kwargs) -> Faculty:
        """From the username or name, tries to get a faculty object.

        Create user and faculty if necessary.
        """

        username = get_in_row("username", row)
        updated_name = name_parts_from_row(row, fullname_key="faculty")
        faculty_obj = ensure_faculty(username, name=updated_name)

        return faculty_obj


class StdUserWgt(widgets.ForeignKeyWidget):
    """Ensure a Student User given a username, stid or name."""

    def __init__(self):
        # field is "id" by default
        self._cache_student: dict[Hashable, Student] = {}
        super().__init__(Student)

    def clean(self, value: str, row=None, *args, **kwargs) -> Student | None:
        """Look up for a student based on its username, stdid or name.

        Create user and student objects if necessary.
        Use the extra column student_id to desambiguate sames names
        and create uniq username.
        """
        username = parse_str(value)
        student_id = get_in_row("student_id", row)
        name = name_parts_from_row(
            row,
            fullname_key="long_name",
            fallback_last="Student",
        )

        if not username and not student_id and not name.last:
            return None

        key = username or student_id or name.to_string(full=True)

        # > using get or created in a cached version is a bit useless
        # > as the get will never get called.
        def _get_or_create_std() -> Student:
            student, created = Student.objects.get_or_create(
                username=username,
                student_id=student_id,  # this is why I do not use the factory
                defaults=name.to_dict(),
            )
            if created:
                student.user.set_password(mk_password(name.first, name.last))
                student.user.save(update_fields=["password"])

            return cast(Student, student)

        student_obj = cached_entity(self._cache_student, key, _get_or_create_std)

        return student_obj

    def after_import(self, dataset, result, **kwargs):
        """Remove any cache which may be present after import."""
        self.cache_student = dict()


class StdGradeWgt(widgets.ForeignKeyWidget):
    """Create or resolve a Student using a student_id when missing."""

    def __init__(self):
        super().__init__(Student, field="student_id")
        self._cache_student: dict[Hashable, Student] = {}
        self.curriculum_w = CurriWgt()

    def clean(self, value, row=None, *args, **kwargs) -> Student:
        """Return the Student tied to the identifier, creating it if needed."""
        student_id = parse_str(value)
        if not student_id:
            return Student.get_dft()

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
            curriculum = Curriculum.get_dft()

        first_name = get_in_row("student_first_name", row)
        last_name = get_in_row("student_last_name", row)
        raw_name = " ".join(filter(None, [first_name, last_name])).strip()
        _n = name_parts_from_row(
            row, raw_name=raw_name, fallback_first="Student", fallback_last=student_id
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
            curriculum=Curriculum.get_dft(),
            student_id=student_id,
        )
        student.save()
        # Keep enrollment authoritative for curriculum assignment.
        set_primary_std_curri_enroll(
            student,
            curriculum,
            entry_semester_id=student.entry_semester_id,
            is_active=True,
        )

        self._cache_student[student_id] = student
        return student


class UserDonorWgt(widgets.ForeignKeyWidget):
    """Create or resolve a User for Donor imports."""

    def __init__(self):
        super().__init__(User)
        self._cache_user: dict[Hashable, User] = {}

    def clean(self, value, row=None, *args, **kwargs) -> User:
        """Return or create a User from the donor name."""
        raw_name = parse_str(value)
        if not raw_name:
            return Donor.get_dft().user

        _n = name_parts_from_row(row, raw_name=raw_name)

        donor_factory = create_person_factory(
            raw_name, Donor, _n.to_dict(full=False), lambda s: s.user
        )

        donor_obj = donor_factory()

        return donor_obj.user


class UserStdWgt(widgets.ForeignKeyWidget):
    """Import a User for an existing student based on username, id or name."""

    def __init__(self):
        # field is "id" by default
        super().__init__(User)
        self._cache_user: dict[Hashable, User] = dict()

    def clean(self, value: str, row=None, *args, **kwargs) -> User | None:
        """From the student id, name or username look up or create a Student object."""
        username = parse_str(value)
        student_id = get_in_row("student_id", row)
        _n = name_parts_from_row(
            row,
            fullname_key="long_name",
            fallback_last="Student",
        )

        if not username and not student_id and not _n.last:
            return None

        # for the same name we get the same user back.
        key = username or student_id or _n.to_string(full=True)

        cached = self._cache_user.get(key)
        if cached:
            return cached

        if not username:
            username = Student.mk_username(*_n.parts())

        dfts = _n.to_dict(full=False)

        user_factory = create_person_factory(
            username, User, dfts, user_getter=lambda u: u
        )

        user_obj = cached_entity(self._cache_user, username, user_factory)

        return user_obj

    def after_import(self, dataset, result, **kwargs):
        """Remove any cache which may be present after import."""
        self.cache_user = dict()
