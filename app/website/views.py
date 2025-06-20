"""Website views for the student dashboard."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def landing_page(request: HttpRequest) -> HttpResponse:
    """Render the website landing page."""
    return render(request, "website/landing.html")
