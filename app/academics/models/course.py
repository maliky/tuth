"""Course module."""

from __future__ import annotations

import logging
from itertools import count
from typing import Any, Optional, Self, cast

from django.db import models
from simple_history.models import HistoricalRecords

from app.academics.choices import LEVEL_NUMBER
from app.academics.models.curriculum import Curriculum
from app.academics.models.department import Department
from app.academics.utils import make_crs_code
from app.registry.models import CreditHour
from app.shared.fuzzy_matching import token_similarity
from app.shared.types import CrsQuery

DEFAULT_COURSE_NO = count(start=1, step=1)
logger = logging.getLogger(__name__)


class CrsManager(models.Manager["Course"]):
    """Manager with fuzzy lookup to avoid near-duplicate courses."""

    def _token(self, department: Department, number: str, title: str | None) -> str:
        parts = [department.code, number or ""]
        if title:
            parts.append(title)
        return " ".join(p for p in parts if p)

    def find_fuzzy_match(
        self,
        *,
        department: Department,
        number: str,
        title: str | None = None,
        threshold: float = 0.9,
    ) -> Course | None:
        """Return an existing course with a similar identifier/title."""
        token = self._token(department, number, title)
        candidates = self.filter(department=department)
        best: tuple[Course | None, float] = (None, 0.0)
        # > We can factor this and the one in curriclum,
        # > using a function to handle alternate case
        for course in candidates:
            other_token = self._token(course.department, course.number, course.title)
            score, ok = token_similarity(token, other_token, threshold=threshold)
            if ok and score > best[1]:
                best = (course, score)
        return best[0]

    def get_or_create(
        self,
        defaults=None,
        **kwargs: Any,
    ) -> tuple[Course, bool]:
        """Return a course; if fuzzy_threshold < 1 try fuzzy reuse first.

        Required keys in kwargs: department, number. Optional: title.
        """
        fuzzy_threshold: float = kwargs.pop("fuzzy_threshold", 1.0)

        defaults = defaults.copy() if defaults else {}

        department: Department | None = kwargs.get("department")
        number = kwargs.get("number")
        title = defaults.get("title")

        if fuzzy_threshold < 1 and department is not None and number is not None:
            _match = self.find_fuzzy_match(
                department=department,
                number=str(number),
                title=title,
                threshold=fuzzy_threshold,
            )
            if _match:
                logger.info(
                    "Fuzzy course match reused",
                    extra={
                        "course_id": _match.id,
                        "dept": department.code,
                        "number": number,
                    },
                )
                if title and _match.title != title:
                    _match.title = title
                    _match.save(update_fields=["title"])
                return _match, False

        if title and "title" not in defaults:
            defaults["title"] = title

        created_course, created = super().get_or_create(defaults=defaults, **kwargs)
        return created_course, bool(created)


class Course(models.Model):
    """University catalogue entry describing a single course offering.

    Example:
        >>> COAS = College.get_dft()
        >>> MATH = Departement.objects.create(code=MATH,college=COAS)
        >>> Course.objects.create(department=MATH,number="101",title="Algebra")

    Side Effects:
        save() populates code from name and number.
    """

    objects: CrsManager = CrsManager()
    history = HistoricalRecords()

    # ~~~~~~~~ Mandatory ~~~~~~~~
    number = models.CharField(max_length=10)  # e.g. 101

    # ~~~~ Auto-filled ~~~~
    department = models.ForeignKey(
        "academics.Department",
        on_delete=models.CASCADE,
        related_name="courses",
    )
    # ~~~~ Read-only ~~~~
    #  Code is uniq include the college code + dep + no
    code = models.CharField(max_length=20, editable=False)

    # ~~~~~~~~ Optional ~~~~~~~~
    # Can have duplicate only include dep + no
    short_code = models.CharField(max_length=20, editable=True, null=True, blank=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    description: models.TextField = models.TextField(blank=True, null=True)
    prerequisites = models.ManyToManyField(
        "self",
        symmetrical=False,
        through="academics.Prerequisite",
        related_name="dependent_courses",
        blank=True,
    )

    @classmethod
    def for_curri(cls, curriculum) -> CrsQuery:
        """Return courses included in the given curriculum."""
        return cls.objects.filter(curricula=curriculum).distinct()

    @classmethod
    def get_dft(cls, number: str = "0000") -> Self:
        """Return a default Course."""
        def_crs, _ = cls.objects.get_or_create(
            department=Department.get_dft(),
            number=number,
            defaults={"title": f"Default Course {number}"},
        )
        return cast(Self, def_crs)

    @classmethod
    def get_unique_dft(cls) -> Self:
        """Return a default Course which is unique."""
        # > where do I state the maximun number of courses to create ?
        number = f"{next(DEFAULT_COURSE_NO):04d}"
        return cls.get_dft(number=number)

    @property
    def level(self) -> str:
        """Human-friendly year level derived from the first digit of the course number.

        Returns the enum label or "other" when the pattern does not match a known level.
        """
        try:
            digit = int(self.number.strip()[0])  # "101" → 1
            return LEVEL_NUMBER(digit).label  # "freshman"
        except (ValueError, IndexError):  # non-digit / empty
            return "other"
        except KeyError:  # digit ∉ enum
            return "other"

    def __str__(self) -> str:  # pragma: no cover
        """Return the CODE - Title representation."""
        title = f" - {self.title}" if self.title else ""
        return f"{self.short_code}{title}"

    def _ensure_codes(self):
        if not self.code:
            self.code = make_crs_code(self.department, number=self.number)
        if not self.short_code:
            self.short_code = make_crs_code(
                self.department, number=self.number, short=True
            )

    def _ensure_dept(self):
        if not self.department_id:
            self.department = Department.get_dft()

    def list_curra_str(self, sep: str = ", ") -> str:
        """Return the list of curricula including this course."""
        curricula = (
            self.in_curriculum_courses.select_related("curriculum")  # <- efficiency
            .values_list(
                "curriculum__short_name", flat=True
            )  # <- this is getting the value
            .order_by("curriculum__short_name")
        )
        return sep.join(curricula)

    # ---------- hooks ----------
    def save(self, *args, **kwargs) -> None:
        """Populate code from department shortname and number before saving."""
        self._ensure_dept()
        self._ensure_codes()
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["department", "code", "number"],
                name="uniq_course_codenumber_per_department",
            ),
        ]
        ordering = ["code"]
