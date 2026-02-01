"""Prerequisite graph export helpers."""

from __future__ import annotations

import csv
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence, TypeAlias

from django.conf import settings
from django.core.management.base import CommandError
from django.utils.text import slugify

from app.academics.models.curriculum import Curriculum
from app.academics.models.curriculum_course import CurriculumCourse
from app.academics.models.prerequisite import Prerequisite

CsvRowT: TypeAlias = dict[str, str | int]
NodeMapT: TypeAlias = dict[int, str]
EdgeListT: TypeAlias = set[tuple[int, int]]
LevelMapT: TypeAlias = dict[int, int]

CSV_HEADERS: Sequence[str] = (
    "curriculum_short_name",
    "course_id",
    "course_short_code",
    "course_title",
    "course_level_number",
    "course_department_code",
    "course_college_code",
    "prerequisite_course_id",
    "prerequisite_short_code",
    "prerequisite_title",
    "prerequisite_level_number",
    "prerequisite_department_code",
    "prerequisite_college_code",
)


@dataclass(frozen=True)
class PrereqGraphPaths:
    """Paths generated for a curriculum prerequisite graph export."""

    csv_path: Path
    dot_path: Path
    png_path: Path


def resolve_curriculum(short_name: str) -> Curriculum:
    """Return curriculum for a short name, raising if not found."""
    curriculum = Curriculum.objects.filter(short_name=short_name).first()
    if curriculum is None:
        raise CommandError(f"Curriculum not found: {short_name}")
    return curriculum


def _output_dir() -> Path:
    """Return output directory for prerequisite graphs."""
    return Path(settings.MEDIA_ROOT) / "Prereq"


def _safe_curriculum_slug(curriculum: Curriculum) -> str:
    """Build a safe filename slug from curriculum short name."""
    return slugify(curriculum.short_name, allow_unicode=False) or str(curriculum.pk)


def _build_course_maps(
    curriculum: Curriculum,
) -> tuple[NodeMapT, LevelMapT, dict[int, CurriculumCourse]]:
    """Return node/level maps for all curriculum courses."""
    course_map: dict[int, CurriculumCourse] = {}
    node_map: NodeMapT = {}
    level_map: LevelMapT = {}

    qs = (
        CurriculumCourse.objects.filter(curriculum=curriculum)
        .select_related("course__department__college")
        .order_by("course__short_code")
    )
    for curriculum_course in qs:
        course = curriculum_course.course
        course_map[course.id] = curriculum_course
        label = course.short_code or course.code or str(course)
        node_map[course.id] = label
        level_value = curriculum_course.level_number
        if level_value is not None:
            level_map[course.id] = int(level_value)

    return node_map, level_map, course_map


def _build_csv_rows(
    curriculum: Curriculum,
    prerequisites: Iterable[Prerequisite],
    course_map: dict[int, CurriculumCourse],
) -> list[CsvRowT]:
    """Build CSV rows for prerequisite edges in a curriculum."""
    rows: list[CsvRowT] = []
    for prereq in prerequisites:
        course = prereq.course
        prereq_course = prereq.prerequisite_course

        course_cc = course_map.get(course.id)
        prereq_cc = course_map.get(prereq_course.id)

        course_dept = course.department
        prereq_dept = prereq_course.department
        course_college = course_dept.college if course_dept else None
        prereq_college = prereq_dept.college if prereq_dept else None

        rows.append(
            {
                "curriculum_short_name": curriculum.short_name,
                "course_id": course.id,
                "course_short_code": course.short_code or course.code or str(course),
                "course_title": course.title,
                "course_level_number": (
                    int(course_cc.level_number)
                    if course_cc and course_cc.level_number is not None
                    else ""
                ),
                "course_department_code": course_dept.code if course_dept else "",
                "course_college_code": course_college.code if course_college else "",
                "prerequisite_course_id": prereq_course.id,
                "prerequisite_short_code": prereq_course.short_code
                or prereq_course.code
                or str(prereq_course),
                "prerequisite_title": prereq_course.title,
                "prerequisite_level_number": (
                    int(prereq_cc.level_number)
                    if prereq_cc and prereq_cc.level_number is not None
                    else ""
                ),
                "prerequisite_department_code": prereq_dept.code if prereq_dept else "",
                "prerequisite_college_code": (
                    prereq_college.code if prereq_college else ""
                ),
            }
        )
    return rows


def _write_csv(path: Path, rows: list[CsvRowT]) -> None:
    """Write CSV rows to disk."""
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CSV_HEADERS))
        writer.writeheader()
        writer.writerows(rows)


def _build_edges(prerequisites: Iterable[Prerequisite]) -> EdgeListT:
    """Return prerequisite edges as (src, dst) course ids."""
    edges: EdgeListT = set()
    for prereq in prerequisites:
        edges.add((prereq.prerequisite_course_id, prereq.course_id))
    return edges


def _build_dot(node_map: NodeMapT, edges: EdgeListT, level_map: LevelMapT) -> str:
    """Return DOT contents for prerequisite graph."""
    lines: list[str] = [
        "digraph prereq {",
        "  rankdir=LR;",
        "  node [shape=box];",
    ]

    for course_id in sorted(node_map):
        label = node_map[course_id].replace('"', "'")
        lines.append(f'  C{course_id} [label="{label}"];')

    for src, dst in sorted(edges):
        lines.append(f"  C{src} -> C{dst};")

    levels: dict[int, list[int]] = {}
    for course_id, level_value in level_map.items():
        if level_value == 99:
            continue
        levels.setdefault(level_value, []).append(course_id)

    for level_value in sorted(levels):
        level_nodes = " ".join(
            f"C{course_id}" for course_id in sorted(levels[level_value])
        )
        lines.append(f"  {{ rank=same; {level_nodes}; }}")

    lines.append("}")
    return "\n".join(lines)


def _render_png(dot_path: Path, png_path: Path) -> None:
    """Call Graphviz dot to render a PNG from the dot file."""
    if not shutil.which("dot"):
        raise CommandError("Graphviz 'dot' not found in PATH.")
    subprocess.run(
        ["dot", "-Tpng", str(dot_path), "-o", str(png_path)],
        check=True,
    )


def export_prereq_graph(curriculum: Curriculum) -> PrereqGraphPaths:
    """Export prerequisite CSV + DOT + PNG for a curriculum."""
    node_map, level_map, course_map = _build_course_maps(curriculum)

    prerequisites = (
        Prerequisite.objects.filter(curriculum=curriculum)
        .select_related(
            "course__department__college",
            "prerequisite_course__department__college",
        )
        .order_by("course__short_code", "prerequisite_course__short_code")
    )

    output_dir = _output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = _safe_curriculum_slug(curriculum)
    csv_path = output_dir / f"{slug}.csv"
    dot_path = output_dir / f"{slug}.dot"
    png_path = output_dir / f"{slug}.png"

    rows = _build_csv_rows(curriculum, prerequisites, course_map)
    _write_csv(csv_path, rows)

    edges = _build_edges(prerequisites)
    dot_contents = _build_dot(node_map, edges, level_map)
    dot_path.write_text(dot_contents, encoding="utf-8")

    _render_png(dot_path, png_path)

    return PrereqGraphPaths(
        csv_path=csv_path,
        dot_path=dot_path,
        png_path=png_path,
    )
