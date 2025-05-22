from .core import AcademicYearAdmin, SectionAdmin, SemesterAdmin
from .inlines import SemesterInline, SectionInline
from .resources import SectionResource, SemesterResource

__all__ = [
    "AcademicYearAdmin",
    "SemesterAdmin",
    "SectionAdmin",
    "SemesterInline",
    "SectionInline",
    "SectionResource",
    "SemesterResource",
]
