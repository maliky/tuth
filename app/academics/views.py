"""Views for academics utilities."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render


@staff_member_required
def prereq_graph_view(request: HttpRequest, slug: str) -> HttpResponse:
    """Render the prerequisite graph viewer for a curriculum slug."""
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
