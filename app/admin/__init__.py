"""
Tie the admin-site registration together.

We import each concrete admin module explicitly so that Django’s
`admin.autodiscover()` sees the `@admin.register` calls that live there.
Nothing else is executed at import-time.

Keep this file short and **never** use “import *”, so that static
analysis tools understand what gets imported.
"""

from .academic_admin import AcademicYearAdmin, SemesterAdmin, SectionAdmin  # noqa: F401
from .college_admin import (  # noqa: F401
    CollegeAdmin,
    CurriculumAdmin,
    CourseAdmin,
    PrerequisiteAdmin,  # if you added the direct Prerequisite admin
)
from .spaces_admin import BuildingAdmin, RoomAdmin  # noqa: F401
