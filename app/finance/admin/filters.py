"""Autocomplete filters for finance admin."""

from admin_searchable_dropdown.filters import AutocompleteFilterFactory

FeeStackFltAC = AutocompleteFilterFactory("Fee stack", "fee_stack")
FeeTypeFltAC = AutocompleteFilterFactory("Fee type", "fee_type")
EffectiveSemesterFltAC = AutocompleteFilterFactory(
    "Effective semester",
    "effective_from_semester",
)
