class StatusHistoryForm(forms.ModelForm):
    """
    limite the choice to those allowed for the model
    """
    class Meta:
        model = StatusHistory
        fields = ["state", 'author']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ct = self.initial.get("content_type") or getattr(
            self.instance, "content_type", None
        )
        if ct:
            key = f"app.{ct.model}"
            allowed = STATE_MAP.get(key, [])
            self.fields["state"].choices = [
                (state, state.replace("_", " ").title()) for state in allowed
            ]
