from app.models import College
from app.constants import COLLEGE_CHOICES, STYLE_DEFAULT


def log(cmd, msg, style=STYLE_DEFAULT):
    style_obj = getattr(cmd.style, style, cmd.style.NOTICE)
    cmd.stdout.write(style_obj(msg))


def populate_colleges(cmd):
    mapping = {}
    for code, fullname in COLLEGE_CHOICES:
        obj, _ = College.objects.get_or_create(code=code, defaults={"fullname": fullname})
        mapping[code] = obj
        log(cmd, f"  ↳ {code:<4} {fullname}")
    return mapping
