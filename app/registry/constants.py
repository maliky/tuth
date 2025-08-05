"""Constants used by the registry module."""

from app.registry.choices import StatusDocument, StatusRegistration


STATUS_CHOICES = list(
    set(list(StatusDocument.choices) + list(StatusRegistration.choices))
)

GRADES_NUM = {
    "A": 4,
    "AB": 0,
    "B": 3,
    "C": 2,
    "D": 1,
    "DR": 0,
    "F": 0,
    "I": 0,
    "IP": 0,
    "IP_UPD": 0,  # for test purposes
    "NG": 0,
    "W": 0,
}


GRADES_DESCRIPTION = {
    "A": "Excellent",
    "AB": "Absent",
    "B": "Good",
    "C": "Satisfactory",
    "D": "Insufficiant",
    "DR": "Section Droped",
    "F": "Failed",
    "I": "Incomplete",
    "IP": "In Progress",
    "NG": "No Grade",
    "W": "Semester Withdraw",
}
