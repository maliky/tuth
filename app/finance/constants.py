"""Constants for the :mod:`finance` app.

This module defines enumerations representing various aspects of the
financial domain such as payment methods, fee types and student
clearance statuses.  It also exposes the ``TUITION_RATE_PER_CREDIT``
value used when computing tuition.
"""

from decimal import Decimal


TUITION_RATE_PER_CREDIT = Decimal("5.00")
