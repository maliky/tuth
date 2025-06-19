"""Utility forms shared across the project."""

from django import forms
from django.core.exceptions import FieldDoesNotExist
from django.forms import ChoiceField

from .mixins import StatusHistory


class StatusHistoryForm(forms.ModelForm):
    """ModelForm for creating status history records.

    The form limits the ``state`` choices to those defined on the related
    model so only valid transitions are offered.
    """

    class Meta:
        model = StatusHistory
        fields = ["state", "author"]

    def __init__(self, *args, **kwargs):
        """Initialize the form and adjust state choices.

        Parameters
        ----------
        *args, **kwargs
            Standard Django ``ModelForm`` arguments.
        """

        super().__init__(*args, **kwargs)
        content_type = self.initial.get("content_type") or getattr(
            self.instance, "content_type", None
        )
        if content_type:

            field = self.fields["state"]
            if not isinstance(field, ChoiceField):
                raise TypeError("state field must be a ChoiceField")
            model_cls = content_type.model_class()
            if model_cls:
                try:
                    # where is this getting the field status from?
                    # it may not have been defined in the
                    status_field = model_cls._meta.get_field("status")
                    field.choices = status_field.choices
                except FieldDoesNotExist:
                    pass
