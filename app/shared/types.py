"""Personal Types."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

from django.db.models import QuerySet

if TYPE_CHECKING:
    from app.academics.models.course import Course
    from app.people.models.profile import StudentProfile
    from app.registry.models import Registration
    from app.timetable.models import Section

SectionQuery: TypeAlias = QuerySet["Section"]
CourseQuery: TypeAlias = QuerySet["Course"]
StudentProfileQuery: TypeAlias = QuerySet["StudentProfile"]
RegistrationQuery: TypeAlias = QuerySet["Registration"]
