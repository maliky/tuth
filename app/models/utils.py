from django.core.exceptions import ValidationError
from app.constants import STATUS_CHOICES_PER_MODEL, UNDEFINED_CHOICES


def validate_model_status(instance):
    model_name = instance._meta.model_name  # 'curriculum' or 'document'
    valid_statuses = STATUS_CHOICES_PER_MODEL.get(model_name, [UNDEFINED_CHOICES])
    current_status = instance.current_status()
    if current_status and current_status.state not in valid_statuses:
        raise ValidationError(
            f"Invalid status '{current_status.state}' for model '{model_name}'. "
            f"Allowed statuses: {', '.join(valid_statuses)}."
        )
    return None
