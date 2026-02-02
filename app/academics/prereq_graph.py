"""Prerequisite graph export helpers."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, TypeAlias

from django.conf import settings
from django.db.models import Q
from django.core.management.base import CommandError
from django.utils.text import slugify

from app.academics.models.curriculum import Curriculum
from app.academics.models.curriculum_course import CurriculumCourse
from app.academics.models.prerequisite import Prerequisite

EdgeListT: TypeAlias = set[tuple[int, int]]
NodeAttrMapT: TypeAlias = dict[int, dict[str, str]]
OwnerIdsT: TypeAlias = tuple[int, int]
JsonPayloadT: TypeAlias = dict[str, object]

@dataclass(frozen=True)
class PrereqGraphPaths:
    """Paths generated for a curriculum prerequisite graph export."""

    json_path: Path
    js_path: Path
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
) -> tuple[dict[int, CurriculumCourse], NodeAttrMapT]:
    """Return curriculum course map and node attributes."""
    course_map: dict[int, CurriculumCourse] = {}
    node_attrs: NodeAttrMapT = {}

    qs = (
        CurriculumCourse.objects.filter(curriculum=curriculum)
        .select_related("course__department__college")
        .order_by("course__short_code")
    )
    for curriculum_course in qs:
        course = curriculum_course.course
        course_map[course.id] = curriculum_course
        node_attrs[course.id] = {
            "shape": _node_shape(True),
            "color": _department_color(
                getattr(course.department, "code", None) if course.department else None
            ),
        }
    return course_map, node_attrs


def _build_json_payload(
    curriculum: Curriculum,
    prerequisites: Iterable[Prerequisite],
    course_map: dict[int, CurriculumCourse],
    node_attrs: NodeAttrMapT,
) -> JsonPayloadT:
    """Build JSON payload for a curriculum prerequisite graph."""
    nodes: list[dict[str, object]] = []
    seen_nodes: set[int] = set()

    def _append_node(course, is_in_curriculum: bool) -> None:
        if course.id in seen_nodes:
            return
        seen_nodes.add(course.id)
        curriculum_course = course_map.get(course.id)
        dept = course.department
        college = dept.college if dept else None
        attrs = node_attrs.get(course.id, {})
        nodes.append(
            {
                "id": f"C{course.id}",
                "course_id": course.id,
                "label": _course_display(course),
                "level_number": int(curriculum_course.level_number)
                if curriculum_course and curriculum_course.level_number is not None
                else None,
                "department_code": dept.code if dept else "",
                "college_code": college.code if college else "",
                "is_in_curriculum": is_in_curriculum,
                "shape": attrs.get("shape", _node_shape(is_in_curriculum)),
                "color": attrs.get("color", _department_color(dept.code if dept else None)),
            }
        )

    for curriculum_course in course_map.values():
        _append_node(curriculum_course.course, True)

    links: list[dict[str, str]] = []
    for prereq in prerequisites:
        _append_node(
            prereq.prerequisite_course,
            prereq.prerequisite_course_id in course_map,
        )
        links.append(
            {
                "source": f"C{prereq.prerequisite_course_id}",
                "target": f"C{prereq.course_id}",
                "type": "prereq",
            }
        )

    payload: JsonPayloadT = {
        "meta": {
            "curriculum_id": curriculum.id,
            "curriculum_short_name": curriculum.short_name,
        },
        "nodes": nodes,
        "links": links,
    }
    return payload


def _build_edges(links: Iterable[dict[str, str]]) -> EdgeListT:
    """Return prerequisite edges as (src, dst) course ids."""
    edges: EdgeListT = set()
    for link in links:
        src = int(str(link["source"]).lstrip("C"))
        dst = int(str(link["target"]).lstrip("C"))
        edges.add((src, dst))
    return edges


def _build_dot(payload: JsonPayloadT) -> str:
    """Return DOT contents for prerequisite graph."""
    lines: list[str] = [
        "digraph prereq {",
        "  rankdir=LR;",
        "  node [shape=box];",
    ]

    nodes = payload.get("nodes", [])
    links = payload.get("links", [])
    if not isinstance(nodes, list) or not isinstance(links, list):
        raise CommandError("Invalid prerequisite graph payload.")

    for node in nodes:
        node_id = str(node.get("id", ""))
        label = str(node.get("label", "")).replace('"', "'")
        shape = str(node.get("shape", "box"))
        color = str(node.get("color", "#6c757d"))
        lines.append(
            f'  {node_id} [label="{label}" shape="{shape}" color="{color}"];'
        )

    edges = _build_edges(links)
    node_levels: dict[str, int] = {}
    for node in nodes:
        level_value = node.get("level_number")
        if isinstance(level_value, int):
            node_levels[str(node.get("id", ""))] = level_value

    for src, dst in sorted(edges):
        lines.append(f"  C{src} -> C{dst};")

    levels: dict[int, list[str]] = {}
    for node_id, level_value in node_levels.items():
        if level_value == 99:
            continue
        levels.setdefault(level_value, []).append(node_id)

    for level_value in sorted(levels):
        level_nodes = " ".join(sorted(levels[level_value]))
        lines.append(f"  {{ rank=same; {level_nodes}; }}")

    lines.append("}")
    return "\n".join(lines)


def _render_png(dot_path: Path, png_path: Path) -> None:
    """Call Graphviz dot to render a PNG from the dot file."""
    if not shutil.which("dot"):
        raise CommandError("Graphviz 'dot' not found in PATH.")
    subprocess.run(
        ["dot", "-T", "png", str(dot_path), "-o", str(png_path)],
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
            if hasattr(os, "chown"):
                os.chown(path, uid, gid)
        except (PermissionError, OSError):
            continue


def export_prereq_graph(curriculum: Curriculum) -> PrereqGraphPaths:
    """Export prerequisite CSV + DOT + PNG for a curriculum."""
    course_map, node_attrs = _build_course_maps(curriculum)
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
    output_dir = _output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = _safe_curriculum_slug(curriculum)
    json_path = output_dir / f"{slug}.json"
    js_path = output_dir / f"{slug}.js"
    dot_path = output_dir / f"{slug}.dot"
    png_path = output_dir / f"{slug}.png"
    for path in (json_path, js_path, dot_path, png_path):
        if path.exists():
            path.unlink()

    payload = _build_json_payload(curriculum, prerequisites, course_map, node_attrs)
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    js_path.write_text(
        f"window.PREREQ_GRAPH = {json.dumps(payload)};", encoding="utf-8"
    )

    dot_contents = _build_dot(payload)
    dot_path.write_text(dot_contents, encoding="utf-8")

    _render_png(dot_path, png_path)
    _apply_owner([json_path, js_path, dot_path, png_path])

    return PrereqGraphPaths(
        json_path=json_path,
        js_path=js_path,
        dot_path=dot_path,
        png_path=png_path,
    )
