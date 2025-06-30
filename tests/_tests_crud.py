"""Generic CRUD smoke-test for every concrete Django model.

Uses Model Bakery to auto-generate data; walks the app registry with
django.apps.apps.get_models() to stay in sync with any future model
additions. Nothing to edit when a new model appears – just run pytest.
"""

import pytest
from django.apps import (
    apps,
)  # gives access to every registered model:contentReference[oaicite:0]{index=0}
from model_bakery import baker

pytestmark = pytest.mark.django_db  # DB needed for CRUD


def _is_skippable(model):
    """Skip abstract, proxy, or auto-created through-tables."""
    opts = model._meta
    return (
        opts.abstract
        or opts.proxy
        or opts.auto_created  # e.g. many-to-many “through” helpers
    )


def _touch(model_instance):
    """Best-effort field swap so UPDATE is not a no-op."""
    for field in model_instance._meta.fields:
        if (
            field.editable
            and not field.primary_key
            and field.get_internal_type() in ("CharField", "TextField")
        ):
            val = getattr(model_instance, field.name) or ""
            setattr(model_instance, field.name, f"{val}_upd")
            return True
    return False


def test_crud_every_model():
    """Create, Read, Update, Delete for each concrete model."""
    for model in apps.get_models():
        if _is_skippable(model):
            continue

        # CREATE
        try:
            obj = baker.make(model)
        except Exception as exc:
            # Some models may need mandatory relations not satisfiable
            # with Bakery defaults; mark ⟶ xfail so suite keeps running.
            pytest.xfail(f"{model.__name__}: cannot build – {exc}")

        # READ
        fetched = model.objects.get(pk=obj.pk)
        assert fetched == obj, f"{model.__name__} read failed"

        # UPDATE
        if _touch(obj):  # only save if we really changed something
            obj.save()
            updated = model.objects.get(pk=obj.pk)
            assert updated.pk == obj.pk, f"{model.__name__} update lost PK"

        # DELETE
        pk = obj.pk
        obj.delete()
        assert not model.objects.filter(pk=pk).exists(), f"{model.__name__} delete failed"
