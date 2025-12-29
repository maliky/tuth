"""Curriculum module."""

from __future__ import annotations
import logging
from django.db.models import Count

from django.apps import apps
from datetime import date
from typing import Optional, Self, cast

from app.shared.fuzzy_matching import token_similarity
from app.shared.mixins import SimpleTableMixin
from app.shared.utils import as_title
from django.db import models
from simple_history.models import HistoricalRecords
from app.academics.models.college import College
from app.shared.status.mixins import StatusableMixin

logger = logging.getLogger(__name__)


class CurriculumStatus(SimpleTableMixin):
    """Code/label pairs for curriculum validation status."""

    DEFAULT_VALUES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("needs_revision", "Needs Revision"),
    ]

    class Meta:
        verbose_name = "Curriculum Status"
        verbose_name_plural = "Curriculum Status"


class CurriculumManager(models.Manager["Curriculum"]):
    """Manager with fuzzy lookup to reduce near-duplicates."""

    def _token(self, short_name: str, long_name: str | None) -> str:
        if long_name and long_name != short_name:
            return long_name + " " + short_name
        return short_name

    def find_fuzzy_match(
        self,
        *,
        short_name: str,
        long_name: str | None,
        college: College,
        threshold: float = 0.9,
    ) -> Curriculum | None:
        """Do a fuzzy curriclum search."""
        token = self._token(short_name, long_name)
        default_code = College.get_default().code

        best: tuple[Curriculum | None, float] = (None, 0.0)
        for cur in self.all():
            # college rule: if both non-default and differ, skip
            # we do not match if college differ and is set.
            if (
                cur.college
                and college
                and cur.college.code != default_code
                and college.code != default_code
                and cur.college.code != college.code
            ):
                continue

            other_token = self._token(cur.short_name, cur.long_name)
            score, ok = token_similarity(token, other_token, threshold=threshold)

            if not ok:
                continue
            choose = False
            if score > best[1]:
                choose = True
            elif score == best[1] and best[0] is not None:
                # tie-breaker: prefer one with long_name, else non-default college, else lower id
                has_long = bool(cur.long_name and cur.long_name != cur.short_name)
                best_long = bool(
                    best[0].long_name and best[0].long_name != best[0].short_name
                )
                if has_long and not best_long:
                    choose = True
                elif has_long == best_long:
                    cur_default = (
                        cur.college.code == default_code if cur.college else True
                    )
                    best_default = (
                        best[0].college.code == default_code if best[0].college else True
                    )
                    if not cur_default and best_default:
                        choose = True
                    elif cur_default == best_default and cur.id and best[0].id:
                        choose = cur.id < best[0].id
            if choose:
                best = (cur, score)
        return best[0]

    def get_or_create(
        self,
        *,
        short_name: str,
        college: College,
        defaults: dict | None = None,
        fuzzy_threshold: float = 1.0,
    ) -> tuple["Curriculum", bool]:
        """Override get_or_create to optionally allow fuzzy curriculum reuse."""

        # this work on default and arguments is a bit cumbersom but good practice
        defaults = defaults.copy() if defaults else {}
        long_name = defaults.get("long_name")

        if fuzzy_threshold < 1:
            _match = self.find_fuzzy_match(
                short_name=short_name,
                college=college,
                long_name=long_name,
                threshold=fuzzy_threshold,
            )
            if _match:
                # optionals infos to trace
                # > There is more to save in description in case of fuzzy match all
                # diff information from one or the other object should to be saved.
                if hasattr(_match, "description") and _match.description is not None:
                    if "fuzzy_curriculum_match" not in _match.description:
                        _match.description += f"\nfuzzy_curriculum_match:{_match.id}"
                        _match.save(update_fields=["description"])
                return _match, False

        created_cur, created = super().get_or_create(
            short_name=short_name,
            college=college,
            defaults=defaults,
        )
        return created_cur, bool(created)


class Curriculum(StatusableMixin, models.Model):
    """Set of courses that make up a degree curriculum/program within a college.

    Example:
        >>> col = College.objects.create(code="COAS", long_name="Arts and Sciences")
        >>> Curriculum.objects.create(short_name="BSCS", college=col)

    We use a default curriculum encompassing all curriculum_courses when none is
    specified; otherwise the student is limited to the courses listed in their
    curriculum.

    Credit hours usually total 120-128 (GE 30-40, Major/Specific 30-60,
    Minor/elective fills the remainder).
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    short_name = models.CharField(max_length=40)

    # ~~~~ Auto-filled ~~~~
    college = models.ForeignKey(
        "academics.College", on_delete=models.CASCADE, related_name="curricula"
    )

    creation_date = models.DateField(default=date.today)
    is_active = models.BooleanField(default=False)

    status = models.ForeignKey(
        "academics.CurriculumStatus",
        on_delete=models.PROTECT,
        default="pending",
        related_name="curricula",
        verbose_name="Validation Status",
    )
    history = HistoricalRecords()

    code = models.CharField(max_length=50, editable=False, default="DFT-CUR")

    # ~~~~~~~~ Optional ~~~~~~~~
    long_name = models.CharField(max_length=255, blank=True, null=True)
    # this is a shortcut from curriculum <- curriculum_courses . course
    # The idea is to have a catalogue C of curriculum course been authorative
    # the list of curriculum_courses.course should be included in C.
    # can a course be not offered  in any curricula ?
    # needs clarification...
    # There is a difference between curriculum and Curriculum Course (programmed course)
    # The curriculum is the set of course
    # A curriculum course is a matching curriculum <-> course with meta

    curriculum_course = models.ManyToManyField(
        "academics.Course",
        through="academics.CurriculumCourse",
        related_name="curricula",  # <-- reverse accessor course.curricula
        blank=True,
    )
    description = models.TextField(blank=True)

    objects: CurriculumManager = CurriculumManager()

    @property
    def courses(self):
        """Backward-compatible alias using the historical field name."""
        return self.curriculum_course

    @courses.setter
    def courses(self, value):
        """Allow assignments from import/export to update the through relation."""
        if value is None:
            self.curriculum_course.clear()
        else:
            self.curriculum_course.set(value)

    def __str__(self) -> str:  # pragma: no cover
        """Return the college (if set): & curriculum short name."""
        _prefix = f"({self.college}) " if self.college_id else ""
        return _prefix + self.short_name

    @classmethod
    def get_default(
        cls, short_name: str = "DFT_CUR", def_college: Optional[College] = None
    ) -> Self:
        """Returns a default curriculum."""
        _college = College.get_default() if def_college is None else def_college
        def_curriculum, _ = cls.objects.get_or_create(
            short_name=short_name, long_name="Default Curriculum", college=_college
        )
        return cast(Self, def_curriculum)

    def _ensure_activity(self):
        """Make sure than only an aproved curriculum can be active."""
        # > TODO would be good to bubble up a warning message to inform user
        # of the change.
        if self.status_id != "approved":
            self.is_active = False

    def _ensure_code(self):
        """Populate the code field. making it defacto a model key."""
        if not self.code:
            _prefix = f"({self.college}) " if self.college_id else ""
            self.code = _prefix + self.short_name

    def _ensure_status(self):
        """Make sure the curriculum has a status set."""
        if not self.status_id:
            # >? given that id is no different from code is it necessary to use _id ?
            # oui si on veux pas faire self.status.code
            self.status_id = "pending"
        # just to make sure it is created.
        CurriculumStatus.objects.get_or_create(
            code=self.status_id,
            defaults={"label": as_title(self.status_id)},
        )

    def course_count(self):
        """Count hown many courses attached to this curriculum."""
        return self.curriculum_course.count()

    def student_count(self):
        """Count the number of student who selected this curriculum."""
        return self.students.count()

    def current_student_count(self):
        """Total number of students currently enrolled in courses of this curriculum."""
        Student = apps.get_model("people", "Student")
        return (
            Student.objects.filter(
                student_registrations__section__curriculum_course__curriculum=self,
            )
            .distinct()
            .count()
        )

    def save(self, *args, **kwargs):
        """Save a curriculum instance while setting defaults."""
        if not self.college_id:
            self.college = College.get_default()
        self._ensure_status()
        self._ensure_activity()
        self._ensure_code()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        """Validate the curriculum and its current status."""
        super().clean()
        self.validate_status(CurriculumStatus.objects.all())

    class Meta:
        ordering = ["college", "short_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["short_name"],
                condition=models.Q(is_active=True),
                name="uniq_active_curriculum_college",
            )
        ]
