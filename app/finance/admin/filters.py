"""Autocomplete filters for finance admin."""

from admin_searchable_dropdown.filters import AutocompleteFilterFactory

FeeStackFilterAC = AutocompleteFilterFactory("Fee stack", "fee_stack")
FeeTypeFilterAC = AutocompleteFilterFactory("Fee type", "fee_type")
EffectiveSemesterFilterAC = AutocompleteFilterFactory(
    "Effective semester",
    "effective_from_semester",
)
