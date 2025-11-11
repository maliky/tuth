"""Custom site-wide format definitions for English.

Any directive allowed by Django’s date template filter is valid.
"""
# ─── app/formats/en/formats.py ──────────────────────────────────────────────

TIME_FORMAT = "H:i"  # 14:05
SHORT_DATETIME_FORMAT = "d M Y H:i"  # 16 Jun 2025 14:05 (optional)
TIME_INPUT_FORMATS = ["%H:%M"]
# If I need seconds: ["%H:%M", "%H:%M:%S"]
