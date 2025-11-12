"""Authentication helpers for the unified portal."""

from __future__ import annotations

from typing import cast

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View

from .staff_dashboards import ADMIN_PORTAL_GROUPS


@login_required
def portal_redirect(request: HttpRequest) -> HttpResponse:
    """Central landing after authentication; route users by role."""
    user = cast(User, request.user)
    user_groups = set(user.groups.values_list("name", flat=True))

    if user.is_superuser or user_groups.intersection(ADMIN_PORTAL_GROUPS):
        return redirect("admin:index")

    if getattr(user, "student", None):
        return redirect("student_dashboard")

    return redirect("staff_dashboard")


class PortalLoginView(LoginView):
    """Allow any active user to sign in, then hand off to portal redirect."""

    template_name = "website/portal_login.html"

    def get_success_url(self):
        return reverse("portal_redirect")


class PortalLogoutView(View):
    """Explicit logout that always redirects to the unified login."""

    http_method_names = ["get", "post", "head", "options"]

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        logout(request)
        return redirect("portal_login")

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        return self.post(request, *args, **kwargs)
