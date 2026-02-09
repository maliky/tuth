"""Prerequisite graph export helpers."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, TypeAlias

from django.conf import settings
from django.db.models import Prefetch, Q
from django.core.management.base import CommandError
from django.utils.text import slugify

from app.academics.models.curriculum import Curriculum
from app.academics.models.curriculum_course import CurriculumCourse
from app.academics.models.prerequisite import Prerequisite
from app.academics.models.requirement_group import (
    CurriculumCourseRequirementGroup,
    CurriculumCourseRequirementMember,
    RequirementKind,
)

EdgeListT: TypeAlias = set[tuple[int, int]]
NodeAttrMapT: TypeAlias = dict[int, dict[str, str]]
GroupMapT: TypeAlias = dict[int, list[int]]
OwnerIdsT: TypeAlias = tuple[int, int]
JsonPayloadT: TypeAlias = dict[str, object]
CoreqGroupPayloadT: TypeAlias = dict[str, object]
logger = logging.getLogger(__name__)


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


def _node_shape(is_curriculum_course: bool, college_code: str | None = None) -> str:
    """Return the DOT shape for a node type."""
    code = (college_code or "").upper()
    shape_map = {
        "COAS": "box",
        "COHS": "egg",
        "CAFS": "triangle",
        "COET": "house",
        "COED": "ellipse",
        "COAB": "diamond",
    }
    fallback_shape = "box" if is_curriculum_course else "ellipse"
    return shape_map.get(code, fallback_shape)


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
        dept = course.department
        college = dept.college if dept else None
        college_code = college.code if college else None
        course_map[course.id] = curriculum_course
        node_attrs[course.id] = {
            "shape": _node_shape(True, college_code=college_code),
            "color": _department_color(getattr(dept, "code", None) if dept else None),
        }
    return course_map, node_attrs


def _build_json_payload(
    curriculum: Curriculum,
    prerequisites: Iterable[Prerequisite],
    coreq_groups: Iterable[CurriculumCourseRequirementGroup],
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
        group_number = 0
        if curriculum_course and curriculum_course.required_group_number:
            group_number = int(curriculum_course.required_group_number)
        dept = course.department
        college = dept.college if dept else None
        college_code = college.code if college else None
        title_text = course.title or course.code or course.short_code or str(course)
        attrs = node_attrs.get(course.id, {})
        nodes.append(
            {
                "id": f"C{course.id}",
                "course_id": course.id,
                "label": _course_display(course),
                "title": title_text,
                "level_number": (
                    int(curriculum_course.level_number)
                    if curriculum_course and curriculum_course.level_number is not None
                    else None
                ),
                "group_number": group_number,
                "department_code": dept.code if dept else "",
                "college_code": college.code if college else "",
                "is_in_curriculum": is_in_curriculum,
                "shape": attrs.get(
                    "shape", _node_shape(is_in_curriculum, college_code=college_code)
                ),
                "color": attrs.get(
                    "color", _department_color(dept.code if dept else None)
                ),
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

    coreq_payload: list[CoreqGroupPayloadT] = []
    for group in coreq_groups:
        target_course = group.curriculum_course.course
        member_courses = [target_course]
        member_courses.extend(member.required_course for member in group.members.all())
        # Keep stable order while removing duplicates.
        seen_member_ids: set[int] = set()
        member_ids: list[str] = []
        for course in member_courses:
            if course.id in seen_member_ids:
                continue
            seen_member_ids.add(course.id)
            _append_node(course, course.id in course_map)
            member_ids.append(f"C{course.id}")
        coreq_payload.append(
            {
                "id": f"COREQ{group.id}",
                "group_id": group.id,
                "kind": group.kind,
                "label": group.label or f"COREQ {group.id}",
                "member_ids": member_ids,
            }
        )

    payload: JsonPayloadT = {
        "meta": {
            "curriculum_id": curriculum.id,
            "curriculum_short_name": curriculum.short_name,
            "curriculum_title": curriculum.long_name
            or curriculum.short_name
            or str(curriculum),
        },
        "nodes": nodes,
        "links": links,
        "coreq_groups": coreq_payload,
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


def _course_id_sort_key(node: dict[str, object]) -> int:
    """Return a course id for stable group sorting."""
    course_id = node.get("course_id")
    return course_id if isinstance(course_id, int) else 0


def _build_dot(payload: JsonPayloadT) -> str:
    """Return DOT contents for prerequisite graph."""
    meta = payload.get("meta", {})
    title = ""
    if isinstance(meta, dict):
        title = str(
            meta.get("curriculum_title") or meta.get("curriculum_short_name") or ""
        )
    safe_title = _dot_safe_label(title)
    lines: list[str] = [
        "digraph prereq {",
        "  rankdir=LR;",
        "  compound=true;",
        "  node [shape=box];",
        f'  label="{safe_title}";',
        "  labelloc=top;",
        "  fontsize=20;",
    ]

    nodes = payload.get("nodes", [])
    links = payload.get("links", [])
    coreq_groups = payload.get("coreq_groups", [])
    if (
        not isinstance(nodes, list)
        or not isinstance(links, list)
        or not isinstance(coreq_groups, list)
    ):
        raise CommandError("Invalid prerequisite graph payload.")

    node_by_id: dict[str, dict[str, object]] = {}
    for node in nodes:
        if isinstance(node, dict):
            node_by_id[str(node.get("id", ""))] = node

    def _node_line(node_id: str, indent: str = "  ") -> str:
        node = node_by_id.get(node_id)
        if not node:
            return f"{indent}{node_id};"
        label = str(node.get("label", "")).replace('"', "'")
        shape = str(node.get("shape", "box"))
        color = str(node.get("color", "#6c757d"))
        is_in_curriculum = bool(node.get("is_in_curriculum", True))
        style_attr = ' style="dashed"' if not is_in_curriculum else ""
        return (
            f'{indent}{node_id} [label="{label}" shape="{shape}" '
            f'color="{color}"{style_attr}];'
        )

    edges = _build_edges(links)
    node_levels: dict[str, int] = {}
    for node in nodes:
        level_value = node.get("level_number")
        if isinstance(level_value, int):
            node_levels[str(node.get("id", ""))] = level_value

    levels: dict[int, list[str]] = {}
    for node_id, level_value in node_levels.items():
        if level_value == 99:
            continue
        levels.setdefault(level_value, []).append(node_id)

    alt_group_map: dict[int, list[str]] = {}
    for node in nodes:
        group_number = node.get("group_number")
        if isinstance(group_number, int) and group_number > 0:
            alt_group_map.setdefault(group_number, []).append(str(node.get("id", "")))

    node_to_coreq_cluster: dict[str, str] = {}
    coreq_cluster_nodes: dict[str, list[str]] = {}
    coreq_cluster_labels: dict[str, str] = {}
    for group_entry in coreq_groups:
        if not isinstance(group_entry, dict):
            continue
        cluster_name = f"cluster_COREQ{group_entry.get('group_id')}"
        member_ids = group_entry.get("member_ids", [])
        if not isinstance(member_ids, list):
            continue
        valid_member_ids = [
            str(node_id)
            for node_id in member_ids
            if str(node_id) in node_by_id and str(node_id)
        ]
        deduped_member_ids = list(dict.fromkeys(valid_member_ids))
        coreq_cluster_nodes[cluster_name] = deduped_member_ids
        coreq_cluster_labels[cluster_name] = str(
            group_entry.get("label") or group_entry.get("id") or "COREQ"
        )

    node_to_cluster: dict[str, str] = {}
    cluster_nodes: dict[str, list[str]] = {}
    cluster_labels: dict[str, str] = {}
    cluster_types: dict[str, str] = {}

    # Corequisite clusters get priority when a node belongs to both domains.
    for cluster_name, member_ids in coreq_cluster_nodes.items():
        free_member_ids: list[str] = []
        for node_id in member_ids:
            existing = node_to_coreq_cluster.get(node_id)
            if existing and existing != cluster_name:
                warning_msg = (
                    "Node assigned to multiple corequisite groups in DOT export: "
                    f"node={node_id}, keep={existing}, skip={cluster_name}."
                )
                logger.warning(warning_msg)
                lines.append(f"  // WARNING: {warning_msg}")
                continue
            free_member_ids.append(node_id)
        if len(free_member_ids) < 2:
            node_label = (
                str(node_by_id.get(free_member_ids[0], {}).get("label", ""))
                if free_member_ids
                else ""
            )
            warning_msg = (
                "Singleton corequisite group detected for DOT export: "
                f"group={cluster_name}, node={node_label}. "
                "Rendering as simple node(s), no COREQ cluster."
            )
            logger.warning(warning_msg)
            lines.append(f"  // WARNING: {warning_msg}")
            continue
        cluster_nodes[cluster_name] = free_member_ids
        cluster_labels[cluster_name] = coreq_cluster_labels.get(cluster_name, "COREQ")
        cluster_types[cluster_name] = "coreq"
        for node_id in free_member_ids:
            node_to_coreq_cluster[node_id] = cluster_name
            node_to_cluster[node_id] = cluster_name

    for group_number in sorted(alt_group_map):
        member_ids = sorted(alt_group_map[group_number])
        member_ids = [
            node_id for node_id in member_ids if node_id in node_by_id and node_id
        ]
        free_member_ids = [
            node_id for node_id in member_ids if node_id not in node_to_cluster
        ]
        if len(free_member_ids) < 2:
            node_label = (
                str(node_by_id.get(free_member_ids[0], {}).get("label", ""))
                if free_member_ids
                else ""
            )
            warning_msg = (
                "Singleton required_group_number detected for DOT export: "
                f"group={group_number}, node={node_label}. "
                "Rendering as simple node(s), no ALT cluster."
            )
            logger.warning(warning_msg)
            lines.append(f"  // WARNING: {warning_msg}")
            continue
        cluster_name = f"cluster_ALT{group_number}"
        cluster_nodes[cluster_name] = free_member_ids
        cluster_labels[cluster_name] = f"ALT {group_number}"
        cluster_types[cluster_name] = "alt"
        for node_id in free_member_ids:
            node_to_cluster[node_id] = cluster_name

    for cluster_name in sorted(cluster_nodes):
        cluster_label = _dot_safe_label(cluster_labels.get(cluster_name, cluster_name))
        cluster_kind = cluster_types.get(cluster_name, "alt")
        if cluster_kind == "coreq":
            lines.extend(
                [
                    f"  subgraph {cluster_name} {{",
                    f'    label="{cluster_label}";',
                    "    style=rounded;",
                    '    color="#198754";',
                    "    penwidth=2;",
                ]
            )
            member_text = " ".join(cluster_nodes[cluster_name])
            lines.append(f"    {{ rank=same; {member_text}; }}")
        else:
            lines.extend(
                [
                    f"  subgraph {cluster_name} {{",
                    f'    label="{cluster_label}";',
                    '    style="rounded,dashed";',
                    '    color="#6c757d";',
                    "    penwidth=1.4;",
                ]
            )
        for node_id in cluster_nodes[cluster_name]:
            lines.append(_node_line(node_id, indent="    "))
        lines.append("  }")

    for node in nodes:
        node_id = str(node.get("id", ""))
        if not node_id or node_id in node_to_cluster:
            continue
        lines.append(_node_line(node_id))

    for src, dst in sorted(edges):
        src_id = f"C{src}"
        dst_id = f"C{dst}"
        src_cluster = node_to_coreq_cluster.get(src_id)
        dst_cluster = node_to_coreq_cluster.get(dst_id)
        attrs: list[str] = []
        # Use cluster boundary routing only for corequisite groups.
        if src_cluster and src_cluster != dst_cluster:
            attrs.append(f'ltail="{src_cluster}"')
        if dst_cluster and src_cluster != dst_cluster:
            attrs.append(f'lhead="{dst_cluster}"')
        attrs_text = f" [{', '.join(attrs)}]" if attrs else ""
        lines.append(f"  {src_id} -> {dst_id}{attrs_text};")

    level_values = sorted(levels)
    for level_value in level_values:
        level_nodes = []
        for node_id in sorted(levels[level_value]):
            if node_id not in node_by_id:
                continue
            level_nodes.append(node_id)
        lines.append(f'  L{level_value} [shape=plaintext label="S-{level_value}"];')
        lines.append(f"  {{ rank=same; L{level_value}; {' '.join(level_nodes)}; }}")

    # Keep level bands ordered left-to-right with invisible edges.
    for index in range(len(level_values) - 1):
        src_level = level_values[index]
        dst_level = level_values[index + 1]
        lines.append(f"  L{src_level} -> L{dst_level} [style=invis];")

    # Legend for shapes and curriculum inclusion style.
    lines.extend(
        [
            "  subgraph cluster_legend {",
            '    label="Legend";',
            "    labelloc=b;",
            "    labeljust=l;",
            "    fontsize=12;",
            "    style=rounded;",
            '    color="#ced4da";',
            "    rank=sink;",
            '    LEG_COAS [label="COAS" shape=box];',
            '    LEG_COHS [label="COHS" shape=egg];',
            '    LEG_CAFS [label="CAFS" shape=triangle];',
            '    LEG_COET [label="COET" shape=house];',
            '    LEG_COED [label="COED" shape=ellipse];',
            '    LEG_COAB [label="COAB" shape=diamond];',
            '    LEG_OUT [label="Not in curriculum" shape=ellipse style="dashed"];',
            "    { rank=same; LEG_COAS; LEG_COHS; LEG_CAFS; LEG_COET; "
            "LEG_COED; LEG_COAB; LEG_OUT; }",
            "    LEG_COAS -> LEG_COHS -> LEG_CAFS -> LEG_COET -> LEG_COED "
            "-> LEG_COAB -> LEG_OUT [style=invis];",
            "  }",
        ]
    )

    lines.append("}")
    return "\n".join(lines)


def _render_png(dot_path: Path, png_path: Path) -> None:
    """Call Graphviz dot to render a PNG from the dot file."""
    if not shutil.which("dot"):
        raise CommandError("Graphviz 'dot' not found in PATH.")
    result = subprocess.run(
        ["dot", "-T", "png", str(dot_path), "-o", str(png_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        err_text = (result.stderr or "").strip() or "dot failed without stderr output."
        raise CommandError(
            f"Graphviz dot failed for {dot_path.name}: {err_text}"
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
        except OSError:
            continue


def export_prereq_graph(curriculum: Curriculum) -> PrereqGraphPaths:
    """Export prerequisite JSON + DOT + PNG for a curriculum."""
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
    coreq_groups = (
        CurriculumCourseRequirementGroup.objects.filter(
            curriculum_course__curriculum=curriculum,
            kind=RequirementKind.COREQ_ALL,
        )
        .select_related("curriculum_course__course__department__college")
        .prefetch_related(
            Prefetch(
                "members",
                queryset=CurriculumCourseRequirementMember.objects.select_related(
                    "required_course__department__college"
                ),
            )
        )
        .order_by("id")
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

    payload = _build_json_payload(
        curriculum,
        prerequisites,
        coreq_groups,
        course_map,
        node_attrs,
    )
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    js_path.write_text(f"window.PREREQ_GRAPH = {json.dumps(payload)};", encoding="utf-8")

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
