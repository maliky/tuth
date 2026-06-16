# Academics

Handles courses, curricula, colleges, and prerequisite rules. This app stores the academic catalog used by other modules.

## College Codes

Canonical college acronyms in TUSIS are `CAS`, `CBA`, `EDRCE`, `CET`, `CHS`, and `CAFS`.
Older import values such as `COAS`, `COBA`, `COED`, `CED`, `COET`, and `COHS` remain accepted as aliases, but importers and generated truth bundles should save the canonical codes.

Run `python manage.py normalize_college_codes` after loading or restoring a database that may still contain legacy college rows. `create_states` also runs this normalization during standard initialization.
