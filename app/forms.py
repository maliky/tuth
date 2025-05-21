from django import forms

from app.constants import STATUS_CHOICES_PER_MODEL, CREDIT_CHOICES
from app.models.mixins import StatusHistory
from app.app_utils import make_choices
from django.forms import ChoiceField
from app.models import Course


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
            key = f"app.{ct.model}"
            allowed = STATUS_CHOICES_PER_MODEL.get(key, [])

            field = self.fields["state"]
            assert isinstance(field, ChoiceField)
            field.choices = make_choices(allowed)


class CourseForm(forms.ModelForm):
    credit_hours = forms.TypedChoiceField(
        coerce=int,
        choices=CREDIT_CHOICES.choices,
        empty_value=None,  # show blank to type anything
        widget=forms.NumberInput(attrs={"min": 1}),  # numeric input
    )

    class Meta:
        model = Course
        fields = "__all__"
