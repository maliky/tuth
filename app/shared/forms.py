from django import forms
from django.forms import ChoiceField

from app.shared.constants import STATUS_CHOICES_PER_MODEL

from .mixins import StatusHistory
from .utils import make_choices


class StatusHistoryForm(forms.ModelForm):
    """
    limite the choice to those allowed for the model
    """

    class Meta:
        model = StatusHistory
        fields = ["state", "author"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ct = self.initial.get("content_type") or getattr(
            self.instance, "content_type", None
        )
        if ct:
            # probablement à revoir à cause de ma nouvelle structure
            allowed = STATUS_CHOICES_PER_MODEL.get(ct.model, [])

            field = self.fields["state"]
            assert isinstance(field, ChoiceField)
            field.choices = make_choices(allowed)
