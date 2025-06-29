import pytest
from django.apps import apps
from django.db import connection, models as dj_models
from model_bakery import baker

from app.shared.status.mixins import StatusHistory


def app_models():
    """Return all concrete models in the project."""
    return [
        m
        for m in apps.get_models()
        if not m._meta.abstract
        and m.__module__.startswith("app.")
        and m.__name__ != "StatusHistory"
    ]


def _make_instance(model):
    if model.__name__ == "StatusHistory":
        return baker.make(model, content_object=baker.make("auth.User"))
    if model.__name__ == "Document":
        return baker.make(model, profile=baker.make("people.Student"))
    return baker.make(model)


def _ensure_status_history_table():
    tables = connection.introspection.table_names()
    if StatusHistory._meta.db_table not in tables:
        from django.db import connection as conn
        with conn.schema_editor() as schema:
            schema.create_model(StatusHistory)


def _update_instance(instance):
    model = instance.__class__
    for field in model._meta.fields:
        if field.primary_key or not field.editable or field.auto_created:
            continue
        if isinstance(field, dj_models.CharField):
            setattr(instance, field.name, f"{getattr(instance, field.name)}x")
            instance.save()
            return
        if isinstance(field, dj_models.BooleanField):
            setattr(instance, field.name, not getattr(instance, field.name))
            instance.save()
            return
        if isinstance(field, dj_models.IntegerField):
            setattr(instance, field.name, getattr(instance, field.name) + 1)
            instance.save()
            return
    instance.save()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("model", app_models())
def test_model_crud(model):
    obj = _make_instance(model)
    assert model.objects.filter(pk=obj.pk).exists()
    fetched = model.objects.get(pk=obj.pk)
    assert fetched == obj
    _update_instance(obj)
    assert model.objects.filter(pk=obj.pk).exists()
    _ensure_status_history_table()
    obj.delete()
    assert not model.objects.filter(pk=obj.pk).exists()
