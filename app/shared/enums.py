from django.db.models import IntegerChoices


class SEMESTER_NUMBER(IntegerChoices):
    FIRST = 1, "First"
    SECOND = 2, "Second"
    VACATION = 3, "Vacation"
    REMEDIAL = 4, "Remedial"


class TERM_NUMBER(IntegerChoices):
    FIRST = 1, "First"
    SECOND = 2, "Second"


class CREDIT_NUMBER(IntegerChoices):
    ONE = 1, "1"
    TWO = 2, "2"
    THREE = 3, "3"
    FOUR = 4, "4"
    SIX = 6, "6"
    TEN = 10, "10"


class LEVEL_NUMBER(IntegerChoices):
    ONE = 1, "freshman"
    TWO = 2, "sophomore"
    THREE = 3, "junior"
    FOUR = 4, "senior"
    FIVE = 5, "senior"
