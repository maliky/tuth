"""Ensure custom error handlers render friendly pages."""

from __future__ import annotations

import pytest
from django.test import RequestFactory, override_settings
from django.urls import reverse

from app.website.views import errors


def test_error_handlers_render():
    factory = RequestFactory()
    request = factory.get("/")

    for handler, status in [
        (errors.bad_request, 400),
        (errors.unauthorized, 401),
        (errors.forbidden, 403),
        (errors.not_found, 404),
        (errors.request_timeout, 408),
        (errors.too_many_requests, 429),
    ]:
        response = handler(request)
        assert response.status_code == status
        assert b"Tusis" in response.content
