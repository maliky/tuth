"""Shared registrar fixtures for Selenium tests."""

from __future__ import annotations

import pytest
from django.core.paginator import Paginator

from app.website.views import registrar as registrar_views


@pytest.fixture
def tiny_paginator(monkeypatch: pytest.MonkeyPatch):
    """Force the registrar dashboard to paginate after one record."""

    class TinyPaginator(Paginator):
        """Paginator that ignores the requested per-page size."""

        def __init__(self, object_list, per_page, **kwargs):
            super().__init__(object_list, 1, **kwargs)

    # I need clarifications here
    # Monkeypatch replaces the view's paginator for this test session only.
    monkeypatch.setattr(registrar_views, "Paginator", TinyPaginator)
