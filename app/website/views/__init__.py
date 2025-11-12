"""Modularized views exposed under the legacy import path."""

from .auth import PortalLoginView, PortalLogoutView, portal_redirect
from .enrollment import (
    create_student,
    student_admin_edit,
    student_delete,
    student_detail,
    student_list,
)
from .registrar import registrar_course_windows
from .staff_dashboards import staff_dashboard, staff_role_dashboard
from .student_dashboard import student_dashboard
from .student_portal import course_dashboard, landing_page

__all__ = [
    "PortalLoginView",
    "PortalLogoutView",
    "course_dashboard",
    "create_student",
    "landing_page",
    "portal_redirect",
    "registrar_course_windows",
    "staff_dashboard",
    "staff_role_dashboard",
    "student_dashboard",
    "student_admin_edit",
    "student_delete",
    "student_detail",
    "student_list",
]
