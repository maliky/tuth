"""Friendly HTTP error handlers."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def _render_error(
    request: HttpRequest,
    status_code: int,
    title: str,
    message: str,
    details: str = "",
) -> HttpResponse:
    context = {
        "code": status_code,
        "title": title,
        "message": message,
        "details": details,
        "cta_label": "Back to dashboard",
        "cta_url": "/portal/",
    }
    return render(request, "errors/generic.html", context=context, status=status_code)


def bad_request(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    return _render_error(
        request,
        400,
        "We couldn't understand that request",
        "Double-check the form or try again in a moment.",
    )


def unauthorized(
    request: HttpRequest, exception: Exception | None = None
) -> HttpResponse:
    return _render_error(
        request,
        401,
        "Please sign in",
        "Your session expired or you tried to open a protected resource without logging in.",
    )


def forbidden(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    return _render_error(
        request,
        403,
        "You don't have access to this page",
        "If you believe this is incorrect, contact IT Support.",
    )


def not_found(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    return _render_error(
        request,
        404,
        "We can't find that page",
        "The link might be outdated or the resource has moved.",
    )


def request_timeout(
    request: HttpRequest, exception: Exception | None = None
) -> HttpResponse:
    return _render_error(
        request,
        408,
        "That took too long",
        "Please refresh the page or try again on a faster connection.",
    )


def too_many_requests(
    request: HttpRequest, exception: Exception | None = None
) -> HttpResponse:
    return _render_error(
        request,
        429,
        "Too many requests",
        "Please wait a moment before trying again. We rate-limit to keep the portal responsive.",
    )
