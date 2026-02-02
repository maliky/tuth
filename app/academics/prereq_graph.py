"""Prerequisite graph export helpers."""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence, TypeAlias

from django.conf import settings
from django.db.models import Q
from django.core.management.base import CommandError
from django.utils.text import slugify

from app.academics.models.curriculum import Curriculum
from app.academics.models.curriculum_course import CurriculumCourse
from app.academics.models.prerequisite import Prerequisite

CsvRowT: TypeAlias = dict[str, str | int]
NodeMapT: TypeAlias = dict[int, str]
EdgeListT: TypeAlias = set[tuple[int, int]]
LevelMapT: TypeAlias = dict[int, int]
NodeAttrMapT: TypeAlias = dict[int, dict[str, str]]
GroupMapT: TypeAlias = dict[int, list[int]]
OwnerIdsT: TypeAlias = tuple[int, int]

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


def _course_display(course) -> str:
    """Return the display short code for a course in prereq outputs."""
    return course.short_code or course.code or str(course)


def _dot_safe_label(value: str) -> str:
    """Return a DOT-safe label by normalizing quotes."""
    return value.replace('"', "'")


def _department_color(dept_code: str | None) -> str:
    """Return a stable color for a department code."""
    if not dept_code:
        return "#6c757d"
    palette = [
        "#0d6efd",
        "#198754",
        "#dc3545",
        "#fd7e14",
        "#6f42c1",
        "#20c997",
        "#0dcaf0",
        "#ffc107",
        "#6610f2",
        "#d63384",
    ]
    color_index = abs(hash(dept_code)) % len(palette)
    return palette[color_index]


def _node_shape(is_curriculum_course: bool) -> str:
    """Return the DOT shape for a node type."""
    return "box" if is_curriculum_course else "ellipse"


def _output_dir() -> Path:
    """Return output directory for prerequisite graphs."""
    return Path(settings.MEDIA_ROOT) / "Prereq"


def _safe_curriculum_slug(curriculum: Curriculum) -> str:
    """Build a safe filename slug from curriculum short name."""
    return slugify(curriculum.short_name, allow_unicode=False) or str(curriculum.pk)


def _build_course_maps(
    curriculum: Curriculum,
) -> tuple[NodeMapT, LevelMapT, dict[int, CurriculumCourse], NodeAttrMapT]:
    """Return node/level maps for all curriculum courses."""
    course_map: dict[int, CurriculumCourse] = {}
    node_map: NodeMapT = {}
    level_map: LevelMapT = {}
    node_attrs: NodeAttrMapT = {}

    qs = (
        CurriculumCourse.objects.filter(curriculum=curriculum)
        .select_related("course__department__college")
        .order_by("course__short_code")
    )
    for curriculum_course in qs:
        course = curriculum_course.course
        course_map[course.id] = curriculum_course
        label = _course_display(course)
        node_map[course.id] = label
        node_attrs[course.id] = {
            "shape": _node_shape(True),
            "color": _department_color(
                getattr(course.department, "code", None) if course.department else None
            ),
        }
        level_value = curriculum_course.level_number
        if level_value is not None:
            level_map[course.id] = int(level_value)

    return node_map, level_map, course_map, node_attrs


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
                "course_short_code": _course_display(course),
                "course_title": course.title or "",
                "course_level_number": (
                    int(course_cc.level_number)
                    if course_cc and course_cc.level_number is not None
                    else ""
                ),
                "course_department_code": course_dept.code if course_dept else "",
                "course_college_code": course_college.code if course_college else "",
                "prerequisite_course_id": prereq_course.id,
                "prerequisite_short_code": _course_display(prereq_course),
                "prerequisite_title": prereq_course.title or "",
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


def _build_dot(
    node_map: NodeMapT,
    edges: EdgeListT,
    level_map: LevelMapT,
    node_attrs: NodeAttrMapT,
    group_map: GroupMapT,
    title: str,
) -> str:
    """Return DOT contents for prerequisite graph."""
    safe_title = _dot_safe_label(title)
    lines: list[str] = [
        "digraph prereq {",
        "  rankdir=LR;",
        "  node [shape=box];",
        f'  label="{safe_title}";',
        "  labelloc=top;",
        "  fontsize=20;",
    ]

    for course_id in sorted(node_map):
        label = _dot_safe_label(node_map[course_id])
        attrs = node_attrs.get(course_id, {})
        shape = attrs.get("shape", "box")
        color = attrs.get("color", "#6c757d")
        lines.append(
            f'  C{course_id} [label="{label}" shape="{shape}" color="{color}"];'
        )

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
        lines.append(
            f'  L{level_value} [shape=plaintext label="S-{level_value}"];'
        )
        lines.append(f"  {{ rank=same; L{level_value}; {level_nodes}; }}")

    for group_number, course_ids in sorted(group_map.items()):
        if not course_ids:
            continue
        ports = "|".join(
            f"<c{course_id}> {node_map.get(course_id, f'C{course_id}')}"
            for course_id in course_ids
        )
        lines.append(
            f'  G{group_number} [shape=record label="{ports}"];'
        )
        for course_id in course_ids:
            lines.append(f"  G{group_number}:c{course_id} -> C{course_id};")

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


def _resolve_owner_ids() -> OwnerIdsT:
    """Return uid/gid for exported files using env overrides when present."""
    uid_raw = os.getenv("TUSIS_EXPORT_UID")
    gid_raw = os.getenv("TUSIS_EXPORT_GID")
    uid = int(uid_raw) if uid_raw is not None else os.getuid()
    gid = int(gid_raw) if gid_raw is not None else os.getgid()
    return uid, gid


def _apply_owner(paths: Iterable[Path]) -> None:
    """Apply ownership to generated files when possible."""
    uid, gid = _resolve_owner_ids()
    for path in paths:
        try:
            path.chown(uid, gid)
        except PermissionError:
            continue


def export_prereq_graph(curriculum: Curriculum) -> PrereqGraphPaths:
    """Export prerequisite CSV + DOT + PNG for a curriculum."""
    node_map, level_map, course_map, node_attrs = _build_course_maps(curriculum)
    curriculum_course_ids = list(course_map.keys())

    prerequisites = (
        Prerequisite.objects.filter(course_id__in=curriculum_course_ids)
        .filter(Q(curriculum=curriculum) | Q(curriculum__isnull=True))
        .select_related(
            "course__department__college",
            "prerequisite_course__department__college",
        )
        .order_by("course__short_code", "prerequisite_course__short_code")
    )
    for prereq in prerequisites:
        prereq_course = prereq.prerequisite_course
        if prereq_course.id not in node_map:
            node_map[prereq_course.id] = _course_display(prereq_course)
            node_attrs[prereq_course.id] = {
                "shape": _node_shape(False),
                "color": _department_color(
                    getattr(prereq_course.department, "code", None)
                    if prereq_course.department
                    else None
                ),
            }

    group_map: GroupMapT = {}
    for course_id, curriculum_course in course_map.items():
        group_number = int(getattr(curriculum_course, "required_group_number", 0) or 0)
        if group_number:
            group_map.setdefault(group_number, []).append(course_id)

    output_dir = _output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = _safe_curriculum_slug(curriculum)
    csv_path = output_dir / f"{slug}.csv"
    dot_path = output_dir / f"{slug}.dot"
    png_path = output_dir / f"{slug}.png"

    rows = _build_csv_rows(curriculum, prerequisites, course_map)
    _write_csv(csv_path, rows)

    edges = _build_edges(prerequisites)
    dot_contents = _build_dot(
        node_map,
        edges,
        level_map,
        node_attrs,
        group_map,
        curriculum.long_name or curriculum.short_name or str(curriculum),
    )
    dot_path.write_text(dot_contents, encoding="utf-8")

    _render_png(dot_path, png_path)
    _apply_owner([csv_path, dot_path, png_path])

    return PrereqGraphPaths(
        csv_path=csv_path,
        dot_path=dot_path,
        png_path=png_path,
    )
