import pytest

from app.shared.auth.perms import APP_MODELS, expand_role_model


def test_expand_role_model_app_expansion():
    models = ["Academics"]
    result = expand_role_model(models)
    assert result == APP_MODELS["academics"]


def test_expand_role_model_with_exclusions():
    models = ["Academics-college-department"]
    expected = [m for m in APP_MODELS["academics"] if m not in {"college", "department"}]
    result = expand_role_model(models)
    assert result == expected


def test_expand_role_model_exclusion_limit():
    models = ["Academics-college-department-course"]
    with pytest.raises(ValueError):
        expand_role_model(models)


def test_expand_role_model_mixed_tokens():
    models = ["student", "Academics-college"]
    expected = ["student"] + [m for m in APP_MODELS["academics"] if m != "college"]
    result = expand_role_model(models)
    assert result == expected
