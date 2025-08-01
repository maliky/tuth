"""Utility helpers for management commands."""

from django.core.management.base import BaseCommand

from app.shared.constants import STYLE_DEFAULT


def log(cmd: BaseCommand, msg: str, style: str = STYLE_DEFAULT) -> None:
    """Write a styled message to the command output."""

    style_obj = getattr(cmd.style, style, cmd.style.NOTICE)
    cmd.stdout.write(style_obj(msg))
