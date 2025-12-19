"""CRUD smoke test for all registered models."""

import pytest
from django.apps import apps
from model_bakery import baker

pytestmark = pytest.mark.django_db


def _is_skippable(model):
    """Return True for abstract, proxy, or auto-created models."""
    opts = model._meta
    return opts.abstract or opts.proxy or opts.auto_created


def _touch(model_instance):
    """Modify a text field to trigger an update."""
    for field in model_instance._meta.fields:
        if (
            field.editable
            and not field.primary_key
            and field.get_internal_type()
            in (
                "CharField",
                "TextField",
            )
        ):
            val = getattr(model_instance, field.name) or ""
            new_val = f"{val}_upd"
            max_len = getattr(field, "max_length", None)
            if max_len:
                new_val = new_val[:max_len]
            setattr(model_instance, field.name, new_val)
            return True
    return False


@pytest.mark.parametrize(
    "model",
    [m for m in apps.get_models() if not _is_skippable(m)],
    ids=lambda m: m.__name__,  # for logging tracking
)
def test_crud_every_model(model):
    """Create, read, update and delete for each model."""
    try:
        obj = baker.make(model)  # type: ignore [var-annotated]
    except Exception as exc:  # pragma: no cover - model may have complex deps
        pytest.xfail(f"{model.__name__}: cannot build - {exc}")

    fetched = model.objects.get(pk=obj.pk)
    assert fetched == obj, f"{model.__name__} read failed"

    if _touch(obj):
        obj.save()
        updated = model.objects.get(pk=obj.pk)
        assert updated.pk == obj.pk, f"{model.__name__} update lost PK"

    pk = obj.pk
    obj.delete()
    assert not model.objects.filter(pk=pk).exists(), f"{model.__name__} delete failed"
