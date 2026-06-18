"""Read-only checks for the runtime Tusis MWE workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from django.contrib.auth import authenticate, get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.test import Client
from django.urls import reverse

from app.finance.models.payment import Payment
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration
from app.shared.management.commands.create_test_users import TEST_PASSWORD
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester

RuntimeUserT: TypeAlias = tuple[str, str]

RUNTIME_USERS: tuple[RuntimeUserT, ...] = (
    ("test_student", "Student"),
    ("test_prospecting_student", "Prospecting Student"),
    ("test_staff", "Staff"),
    ("test_faculty", "Faculty"),
    ("test_chair", "Chair"),
    ("test_dean", "Dean"),
    ("test_vpaa", "Vice President Academic Affairs"),
    ("test_registrar", "Registrar"),
    ("test_reg_officer", "Registrar Officer"),
    ("test_finance", "Finance"),
    ("test_finance_officer", "Finance Officer"),
    ("test_cashier", "Cashier"),
    ("test_enrollment", "Enrollment"),
    ("test_enrollment_officer", "Enrollment Officer"),
    ("test_it", "It"),
    ("test_donor", "Donor"),
)


@dataclass(frozen=True)
class RouteCheck:
    """One authenticated portal route that should render for the MWE."""

    username: str
    route_name: str
    args: tuple[object, ...] = ()
    query: str = ""


ROUTE_CHECKS: tuple[RouteCheck, ...] = (
    RouteCheck("test_student", "student_dashboard"),
    RouteCheck("test_enrollment", "staff_role_dashboard", ("enrollment",)),
    RouteCheck("test_finance_officer", "staff_role_dashboard", ("finance_officer",)),
    RouteCheck("test_finance_officer", "finance_officer_invoices"),
    RouteCheck("test_faculty", "staff_role_dashboard", ("faculty",)),
    RouteCheck("test_faculty", "faculty_grade_sections"),
    RouteCheck("test_registrar", "reg_grades_dashboard"),
    RouteCheck("test_reg_officer", "staff_role_dashboard", ("reg_officer",)),
    RouteCheck("test_reg_officer", "reg_crs_wins"),
)


class Command(BaseCommand):
    """Verify that the documented runtime MWE can be demonstrated."""

    help = "Run read-only checks for MWE users, routes, data, and semester windows."

    def add_arguments(self, parser) -> None:
        """Register command-line options."""
        parser.add_argument(
            "--password",
            default=TEST_PASSWORD,
            help="Expected shared MWE password (default: %(default)s)",
        )
        parser.add_argument(
            "--host",
            default="127.0.0.1",
            help="HTTP host passed to Django's test client (default: %(default)s)",
        )
        parser.add_argument(
            "--warn-only",
            action="store_true",
            help="Report failures without returning a non-zero exit status.",
        )
        parser.add_argument(
            "--skip-routes",
            action="store_true",
            help="Skip authenticated portal route checks.",
        )
        parser.add_argument(
            "--skip-data",
            action="store_true",
            help="Skip workflow data count checks.",
        )
        parser.add_argument(
            "--strict-windows",
            action="store_true",
            help="Treat closed registration or grade windows as errors.",
        )

    def handle(self, *args, **options) -> None:
        """Run all selected checks and fail when hard requirements are missing."""
        password = str(options["password"])
        host = str(options["host"])
        errors: list[str] = []
        warnings: list[str] = []

        users = self._check_runtime_users(password, errors)
        if not options["skip_routes"]:
            self._check_routes(users, host, errors)
        if not options["skip_data"]:
            self._check_workflow_data(errors)
        self._check_semester_windows(bool(options["strict_windows"]), errors, warnings)

        for message in warnings:
            self.stdout.write(self.style.WARNING(f"WARN {message}"))
        for message in errors:
            self.stdout.write(self.style.ERROR(f"ERROR {message}"))

        if errors and not options["warn_only"]:
            raise CommandError(f"MWE check failed with {len(errors)} error(s).")

        self.stdout.write(
            self.style.SUCCESS(
                f"MWE check completed with {len(errors)} error(s) and "
                f"{len(warnings)} warning(s)."
            )
        )

    def _check_runtime_users(self, password: str, errors: list[str]):
        """Validate canonical runtime users and their shared password."""
        User = get_user_model()
        users = {
            user.username: user
            for user in User.objects.filter(
                username__in=[username for username, _label in RUNTIME_USERS]
            ).prefetch_related("groups")
        }
        for username, group_name in RUNTIME_USERS:
            user = users.get(username)
            if user is None:
                errors.append(f"missing runtime user {username}")
                continue
            if not user.is_active:
                errors.append(f"runtime user {username} is inactive")
            group_names = set(user.groups.values_list("name", flat=True))
            if group_name not in group_names:
                errors.append(f"runtime user {username} missing group {group_name}")
            if authenticate(username=username, password=password) is None:
                errors.append(f"runtime user {username} does not authenticate")
            else:
                self.stdout.write(f"OK user {username}")
        return users

    def _check_routes(self, users, host: str, errors: list[str]) -> None:
        """Render core authenticated MWE routes with Django's test client."""
        anonymous = Client(HTTP_HOST=host)
        login_response = anonymous.get(reverse("portal_login"))
        if login_response.status_code != 200:
            errors.append(f"portal login returned {login_response.status_code}")
        dashboard_response = anonymous.get(reverse("student_dashboard"))
        if dashboard_response.status_code != 302:
            errors.append(
                f"anonymous student dashboard returned {dashboard_response.status_code}"
            )

        for route_check in ROUTE_CHECKS:
            user = users.get(route_check.username)
            if user is None:
                continue
            client = Client(HTTP_HOST=host)
            client.force_login(user)
            url = reverse(route_check.route_name, args=route_check.args)
            if route_check.query:
                url = f"{url}{route_check.query}"
            response = client.get(url)
            if response.status_code != 200:
                errors.append(
                    f"{route_check.username} {url} returned {response.status_code}"
                )
                continue
            self.stdout.write(f"OK route {route_check.username} {url}")

    def _check_workflow_data(self, errors: list[str]) -> None:
        """Verify that core MWE workflow tables contain demo data."""
        counts = (
            ("registrations", Registration.objects.count()),
            ("grades", Grade.objects.count()),
            ("cleared payments", Payment.objects.filter(status_id="cleared").count()),
            ("faculty sections", Section.objects.exclude(faculty__isnull=True).count()),
        )
        for label, count in counts:
            if count < 1:
                errors.append(f"no {label} found for MWE workflow")
            else:
                self.stdout.write(f"OK data {label}: {count}")

    def _check_semester_windows(
        self,
        strict_windows: bool,
        errors: list[str],
        warnings: list[str],
    ) -> None:
        """Report whether registration and grade-entry windows are open."""
        for status_code, label in (
            ("registration", "registration window"),
            ("grade_entry", "grade-entry window"),
        ):
            count = Semester.objects.filter(status_id=status_code).count()
            if count:
                self.stdout.write(f"OK {label}: {count} open semester(s)")
                continue
            message = f"no semester currently has an open {label}"
            if strict_windows:
                errors.append(message)
            else:
                warnings.append(message)
