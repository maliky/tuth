from django import forms
from django.core.exceptions import FieldDoesNotExist
from django.forms import ChoiceField

from .mixins import StatusHistory


class StatusHistoryForm(forms.ModelForm):
    """
    limite the choice to those allowed for the model
    """

    class Meta:
        model = StatusHistory
        fields = ["state", "author"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        content_type = self.initial.get("content_type") or getattr(
            self.instance, "content_type", None
        )
        if content_type:

            field = self.fields["state"]
            assert isinstance(field, ChoiceField)
            model_cls = content_type.model_class()
            if model_cls:
                try:
                    # where is this getting the field status from?
                    # it may not have been defined in the
                    status_field = model_cls._meta.get_field("status")
                    field.choices = status_field.choices
                except FieldDoesNotExist:
                    pass
