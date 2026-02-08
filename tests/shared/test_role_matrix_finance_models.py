"""Tests for finance permission matrix model names."""

from __future__ import annotations

import pytest
from django.apps import apps
from django.core.management import call_command

from app.shared.auth.perms import ROLE_MATRIX, expand_rights

pytestmark = pytest.mark.django_db

LEGACY_FINANCE_TOKENS = {"invoice", "coursefee", "curriculumcoursefee"}


def test_role_matrix_has_no_legacy_finance_alias_tokens() -> None:
    """Role matrix should use explicit current finance model names."""
    raw_tokens = {
        model_name
        for rights in ROLE_MATRIX.values()
        for models in rights.values()
        for model_name in models
    }
    assert LEGACY_FINANCE_TOKENS.isdisjoint(raw_tokens)


def test_expand_rights_resolves_to_existing_models() -> None:
    """Expanded role models should map to real Django models."""
    for rights in ROLE_MATRIX.values():
        for models in rights.values():
            for model_name in expand_rights(models):
                found = any(
                    model_name in [m._meta.model_name for m in config.get_models()]
                    for config in apps.get_app_configs()
                )
                assert found, f"Model token {model_name} does not map to a model."


def test_load_roles_runs_with_explicit_finance_model_names() -> None:
    """load_roles command should run without relying on alias expansion."""
    call_command("load_roles", verbosity=0)
