"""Views for academics utilities."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from app.shared.auth.perms import UserRole


ACADEMIC_GRAPH_GROUPS = {
    UserRole.CHAIR.value.label,
    UserRole.DEAN.value.label,
    UserRole.VPAA.value.label,
}


def _can_view_prereq_graph(request: HttpRequest) -> bool:
    """Return whether the user may view existing prerequisite graph files."""
    user = request.user
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return user.groups.filter(name__in=ACADEMIC_GRAPH_GROUPS).exists()


@login_required
def prereq_graph_view(request: HttpRequest, slug: str) -> HttpResponse:
    """Render the prerequisite graph viewer for a curriculum slug."""
    if not _can_view_prereq_graph(request):
        raise PermissionDenied("You are not allowed to view prerequisite graphs.")

    json_path = Path(settings.MEDIA_ROOT) / "Prereq" / f"{slug}.json"
    js_path = Path(settings.MEDIA_ROOT) / "Prereq" / f"{slug}.js"
    png_path = Path(settings.MEDIA_ROOT) / "Prereq" / f"{slug}.png"
    dot_path = Path(settings.MEDIA_ROOT) / "Prereq" / f"{slug}.dot"
    if not json_path.exists():
        raise Http404("Prerequisite graph not found.")

    context = {
        "slug": slug,
        "json_url": f"{settings.MEDIA_URL}Prereq/{json_path.name}",
        "js_url": f"{settings.MEDIA_URL}Prereq/{js_path.name}",
        "png_url": f"{settings.MEDIA_URL}Prereq/{png_path.name}",
        "dot_url": f"{settings.MEDIA_URL}Prereq/{dot_path.name}",
    }
    return render(request, "academics/prereq_graph.html", context)
