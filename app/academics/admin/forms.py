from django import forms

from app.academics.models import Course
from app.shared.enums import CREDIT_NUMBER


class CourseForm(forms.ModelForm):
    credit_hours = forms.TypedChoiceField(
        coerce=int,
        choices=CREDIT_NUMBER.choices,
        empty_value=None,  # show blank to type anything
        widget=forms.NumberInput(attrs={"min": 1}),  # numeric input
    )

    class Meta:
        model = Course
        fields = "__all__"
