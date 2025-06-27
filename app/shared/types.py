from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias
from django.db.models import QuerySet

if TYPE_CHECKING:
    from app.timetable.models import Section
    from app.academics.models import Course
    from app.people.models.profile import StudentProfile
    from app.registry.models import Registration

SectionQuery: TypeAlias = QuerySet["Section"]
CourseQuery: TypeAlias = QuerySet["Course"]
StudentProfileQuery: TypeAlias = QuerySet["StudentProfile"]
RegistrationQuery: TypeAlias = QuerySet["Registration"]
