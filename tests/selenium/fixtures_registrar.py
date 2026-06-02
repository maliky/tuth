"""Shared registrar fixtures for Selenium tests."""

from __future__ import annotations

import pytest
from django.core.paginator import Paginator

from app.website.services import registrar_portal as registrar_portal_services


@pytest.fixture
def tiny_paginator(monkeypatch: pytest.MonkeyPatch):
    """Force the registrar dashboard to paginate after one record."""

    class TinyPaginator(Paginator):
        """Paginator that ignores the requested per-page size."""

        def __init__(self, object_list, per_page, **kwargs):
            super().__init__(object_list, 1, **kwargs)

    # I need clarifications here
    # Monkeypatch replaces the service paginator for this test session only.
    monkeypatch.setattr(registrar_portal_services, "Paginator", TinyPaginator)
