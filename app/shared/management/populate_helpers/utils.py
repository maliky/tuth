from app.academics.models import College
from typing import Dict

from django.core.management.base import BaseCommand

from app.shared.constants import COLLEGE_CHOICES, STYLE_DEFAULT


def log(cmd: BaseCommand, msg: str, style: str = STYLE_DEFAULT) -> None:
    style_obj = getattr(cmd.style, style, cmd.style.NOTICE)
    cmd.stdout.write(style_obj(msg))


def populate_colleges(cmd: BaseCommand) -> Dict[str, College]:
    mapping: Dict[str, College] = {}
    for code, fullname in COLLEGE_CHOICES:
        obj, _ = College.objects.get_or_create(code=code, defaults={"fullname": fullname})
        mapping[code] = obj
        log(cmd, f"  ↳ {code:<4} {fullname}")
    return mapping
