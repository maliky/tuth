"""Test imports module."""

import pytest
from django.conf import settings
from django.apps import apps


@pytest.mark.parametrize("app_name", settings.INSTALLED_APPS)
def test_import_and_check_models(app_name):
    pytest.importorskip(app_name)
    apps.check_models_ready()
