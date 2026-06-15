"""Helper utilities for finance officer views."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Optional, TypedDict, cast

from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Exists, Max, Min, OuterRef, Q, QuerySet
from django.http import HttpRequest, QueryDict
from django.urls import NoReverseMatch, reverse

from app.finance.models.invoice import CrsInvoice
from app.finance.models.payment import Payment
from app.finance.payment_application import (
    InvoicePaymentApplicationT,
    payment_application_for_parent_invoice,
)
from app.finance.models.status_types_methods import Payer, PaymentMethod, PaymentStatus
from app.finance.course_fee_setup import (
    infer_course_fee_type_code,
    suggested_registration_fee_amount,
)
from app.finance.registration_invoices import (
    INVOICEABLE_REGISTRATION_STATUSES,
    invoice_generation_registration_qs,
    invoiceable_registration_qs,
    missing_registration_invoice_student_ids,
    registration_invoice_amount,
)
from app.people.models.student import Student
from app.registry.models.registration import Registration
from app.timetable.models.semester import Semester
from app.timetable.utils import format_datetime
from app.website.services.portal_types import PortalContextT
from app.website.services.staff_portal import (
    build_staff_role_switcher,
    build_staff_sidebar_links,
)


class StdOptionT(TypedDict):
    """Dropdown option for finance officer student filters."""

    id: int
    label: str
    selected: bool


class InvoiceRowT(TypedDict):
    """Display metadata for one course invoice row."""

    invoice: CrsInvoice
    row_class: str
    created_at: str
    updated_at: str


class InvoiceGpT(TypedDict):
    """Invoice group keyed by student."""

    student: Student
    rows: list[InvoiceRowT]
    total_due: Decimal


class PaymentRowT(TypedDict):
    """Display metadata for one payment row."""

    payment: Payment
    row_class: str
    created_at: str
    updated_at: str
    open_balance: Decimal
    charged_total: Decimal
    applied_clearance: Decimal
    surplus: Decimal
    course_summary: str


class PaymentGpT(TypedDict):
    """Payment group keyed by student."""

    student: Student
    rows: list[PaymentRowT]
    total_paid: Decimal
    charged_total: Decimal
    cleared_records_total: Decimal
    applied_clearance_total: Decimal
    open_balance: Decimal
    pending_total: Decimal
    pending_count: int
    surplus_total: Decimal


class UninvoicedRegistrationGpT(TypedDict):
    """Invoiceable registration group keyed by student."""

    student: Student
    rows: list[Registration]
    total_due: Decimal


class FeeSetupRegistrationRowT(TypedDict):
    """Zero-amount registration row that needs fee setup before invoicing."""

    registration: Registration
    current_amount: Decimal
    suggested_amount: Decimal
    fee_type_code: str


class FeeSetupRegistrationGpT(TypedDict):
    """Fee-setup registration group keyed by student."""

    student: Student
    rows: list[FeeSetupRegistrationRowT]


class FinanceAdminLinkT(TypedDict):
    """Shortcut link into the Django finance admin."""

    label: str
    href: str


class PaginationHiddenFieldT(TypedDict):
    """One preserved GET field used by the pagination form."""

    name: str
    value: str


class PaginationStateT(TypedDict):
    """Encoded links and hidden fields for a paginated panel."""

    query: str
    hidden_fields: list[PaginationHiddenFieldT]


PAGINATION_PAGE_PARAMS = ("page", "registration_page", "fee_setup_page")


def finance_std_ids(*, missing_semester_id: int | None = None) -> set[int]:
    """Return student IDs with invoices or payments."""
    invoice_ids = set(CrsInvoice.objects.values_list("student_id", flat=True))
    payment_ids = set(
        Payment.objects.values_list("student_semester_invoice__student_id", flat=True)
    )
    return (
        invoice_ids
        | payment_ids
        | missing_registration_invoice_student_ids(semester_id=missing_semester_id)
    )


def finance_relevant_std_qs() -> QuerySet[Student]:
    """Return students with direct finance activity or invoiceable registrations."""
    existing_registration_invoice = CrsInvoice.objects.filter(
        student_id=OuterRef("student_id"),
        curriculum_course_id=OuterRef("section__curriculum_course_id"),
        semester_id=OuterRef("section__semester_id"),
    )
    missing_registration = Registration.objects.filter(
        student_id=OuterRef("pk"),
        status_id__in=INVOICEABLE_REGISTRATION_STATUSES,
    ).filter(~Exists(existing_registration_invoice))
    stale_zero_invoice = CrsInvoice.objects.filter(
        initial_amount_due__lte=Decimal("0.00"),
        balance__lte=Decimal("0.00"),
    ).values_list("student_id", flat=True)
    invoice_student_ids = CrsInvoice.objects.values_list("student_id", flat=True)
    payment_student_ids = Payment.objects.values_list(
        "student_semester_invoice__student_id",
        flat=True,
    )
    missing_registration_student_ids = missing_registration.values_list(
        "student_id",
        flat=True,
    )
    # SQL subqueries keep autocomplete responsive without materializing history.
    return Student.objects.select_related("user").filter(
        Q(id__in=invoice_student_ids)
        | Q(id__in=payment_student_ids)
        | Q(id__in=missing_registration_student_ids)
        | Q(id__in=stale_zero_invoice)
    )


def finance_stds(query: str | None = None) -> QuerySet[Student]:
    """Return a queryset of finance-relevant students matching a query."""
    if not query:
        return Student.objects.none()
    qs = finance_relevant_std_qs().filter(
        Q(student_id__icontains=query)
        | Q(long_name__icontains=query)
        | Q(user__first_name__icontains=query)
        | Q(user__last_name__icontains=query)
        | Q(user__username__icontains=query)
    )
    return qs.order_by("long_name")


def finance_std_by_id(student_id: int) -> Optional[Student]:
    """Return a finance-relevant student by ID."""
    return finance_relevant_std_qs().filter(id=student_id).first()


def build_std_options(
    students: Iterable[Student],
    selected_student_id: Optional[int],
) -> list[StdOptionT]:
    """Build dropdown options for the student filter."""
    options: list[StdOptionT] = []
    for student in students:
        label = student.long_name or student.user.get_full_name() or student.student_id
        student_id = student.student_id or "Pending ID"
        options.append(
            {
                "id": student.id,
                "label": f"{label} ({student_id})",
                "selected": student.id == selected_student_id,
            }
        )
    return options


def _status_row_class(status_id: str | None) -> str:
    """Return a Bootstrap table class for finance status emphasis."""
    if status_id == "cleared":
        return "table-success"
    if status_id in {"pending", "initial", "updated"}:
        return "table-warning"
    if status_id == "settled":
        return "table-info"
    return ""


def _invoice_updated_labels(invoices: list[CrsInvoice]) -> dict[int, str]:
    """Return invoice id -> latest history timestamp label."""
    invoice_ids = [invoice.id for invoice in invoices if invoice.id]
    if not invoice_ids:
        return {}
    history_rows = (
        CrsInvoice.history.filter(id__in=invoice_ids)
        .values("id")
        .annotate(last_change=Max("history_date"))
    )
    return {
        int(row["id"]): format_datetime(row["last_change"])
        for row in history_rows
        if row["last_change"]
    }


def _payment_history_labels(payments: list[Payment]) -> dict[int, tuple[str, str]]:
    """Return payment id -> (created, updated) labels from history rows."""
    payment_ids = [payment.id for payment in payments if payment.id]
    if not payment_ids:
        return {}
    history_rows = (
        Payment.history.filter(id__in=payment_ids)
        .values("id")
        .annotate(first_change=Min("history_date"), last_change=Max("history_date"))
    )
    return {
        int(row["id"]): (
            format_datetime(row["first_change"]),
            format_datetime(row["last_change"]),
        )
        for row in history_rows
    }


def _course_label(invoice: CrsInvoice) -> str:
    """Return a compact course label for finance payment summaries."""
    course = invoice.curriculum_course.course
    code = course.short_code or course.code or ""
    title = course.title or ""
    if code and title:
        return f"{code} - {title}"
    return code or title or "Untitled course"


def _parent_course_summary(payment: Payment, limit: int | None = None) -> str:
    """Return child courses covered by a semester payment."""
    parent_invoice = payment.student_semester_invoice
    course_invoices = list(parent_invoice.course_invoices.all())
    visible_invoices = course_invoices if limit is None else course_invoices[:limit]
    labels = [_course_label(invoice) for invoice in visible_invoices]
    remaining_count = len(course_invoices) - len(labels)
    if remaining_count > 0:
        labels.append(f"+{remaining_count} more")
    return "; ".join(labels) if labels else "No course invoices"


def gp_invoices(invoices: Iterable[CrsInvoice]) -> list[InvoiceGpT]:
    """Group invoices by student preserving the incoming order."""
    invoice_list = list(invoices)
    updated_labels = _invoice_updated_labels(invoice_list)
    groups: list[InvoiceGpT] = []
    group_lookup: dict[int, InvoiceGpT] = {}
    parent_seen_by_student: dict[int, set[int]] = {}
    for invoice in invoice_list:
        student_id = invoice.student_id
        group = group_lookup.get(student_id)
        if group is None:
            group = {
                "student": invoice.student,
                "rows": [],
                "total_due": Decimal("0.00"),
            }
            group_lookup[student_id] = group
            groups.append(group)
            parent_seen_by_student[student_id] = set()
        group["rows"].append(
            {
                "invoice": invoice,
                "row_class": _status_row_class(invoice.status_id),
                "created_at": format_datetime(invoice.created_at),
                "updated_at": updated_labels.get(
                    invoice.id,
                    format_datetime(invoice.created_at),
                ),
            }
        )
        parent_invoice_id = invoice.student_semester_invoice_id
        if parent_invoice_id is None:
            group["total_due"] += invoice.get_balance()
            continue
        if parent_invoice_id in parent_seen_by_student[student_id]:
            continue
        parent_seen_by_student[student_id].add(parent_invoice_id)
        parent_invoice = invoice.student_semester_invoice
        if parent_invoice is None:
            group["total_due"] += invoice.get_balance()
            continue
        group["total_due"] += parent_invoice.get_balance()
    return groups


def gp_payments(payments: Iterable[Payment]) -> list[PaymentGpT]:
    """Group payments by student preserving the incoming order."""
    payment_list = list(payments)
    history_labels = _payment_history_labels(payment_list)
    groups: list[PaymentGpT] = []
    group_lookup: dict[int, PaymentGpT] = {}
    parent_seen_by_student: dict[int, set[int]] = {}
    application_by_parent_id: dict[int, InvoicePaymentApplicationT] = {}

    def _application(payment: Payment) -> InvoicePaymentApplicationT:
        """Return cached parent-invoice payment application totals."""
        parent_invoice = payment.student_semester_invoice
        cached = application_by_parent_id.get(parent_invoice.id)
        if cached is not None:
            return cached
        application = payment_application_for_parent_invoice(parent_invoice)
        application_by_parent_id[parent_invoice.id] = application
        return application

    for payment in payment_list:
        student = payment.student_semester_invoice.student
        student_id = student.id
        group = group_lookup.get(student_id)
        if group is None:
            group = {
                "student": student,
                "rows": [],
                "total_paid": Decimal("0.00"),
                "charged_total": Decimal("0.00"),
                "cleared_records_total": Decimal("0.00"),
                "applied_clearance_total": Decimal("0.00"),
                "open_balance": Decimal("0.00"),
                "pending_total": Decimal("0.00"),
                "pending_count": 0,
                "surplus_total": Decimal("0.00"),
            }
            group_lookup[student_id] = group
            groups.append(group)
            parent_seen_by_student[student_id] = set()
        parent_invoice = payment.student_semester_invoice
        application = _application(payment)
        created_at, updated_at = history_labels.get(
            payment.id,
            (
                format_datetime(parent_invoice.created_at),
                format_datetime(parent_invoice.updated_at),
            ),
        )
        group["rows"].append(
            {
                "payment": payment,
                "row_class": _status_row_class(payment.status_id),
                "created_at": created_at,
                "updated_at": updated_at,
                "open_balance": application["open_balance"],
                "charged_total": application["charged_total"],
                "applied_clearance": application["applied_clearance"],
                "surplus": application["surplus"],
                "course_summary": _parent_course_summary(payment),
            }
        )
        parent_invoice_id = payment.student_semester_invoice_id
        if parent_invoice_id not in parent_seen_by_student[student_id]:
            parent_seen_by_student[student_id].add(parent_invoice_id)
            group["charged_total"] += application["charged_total"]
            group["open_balance"] += application["open_balance"]
            group["pending_total"] += application["pending_records_total"]
            group["pending_count"] += application["pending_count"]
            group["cleared_records_total"] += application["cleared_records_total"]
            group["applied_clearance_total"] += application["applied_clearance"]
            group["surplus_total"] += application["surplus"]
            # Backward-compatible alias for existing tests and callers.
            group["total_paid"] = group["cleared_records_total"]
    return groups


def gp_uninvoiced_registrations(
    registrations: Iterable[Registration],
) -> list[UninvoicedRegistrationGpT]:
    """Group invoiceable registrations that do not yet have course invoices."""
    groups: list[UninvoicedRegistrationGpT] = []
    group_lookup: dict[int, UninvoicedRegistrationGpT] = {}
    for registration in registrations:
        amount_due = registration_invoice_amount(registration)
        if amount_due <= Decimal("0.00"):
            continue
        student = registration.student
        group = group_lookup.get(student.id)
        if group is None:
            group = {
                "student": student,
                "rows": [],
                "total_due": Decimal("0.00"),
            }
            group_lookup[student.id] = group
            groups.append(group)
        group["rows"].append(registration)
        group["total_due"] += amount_due
    return groups


def gp_fee_setup_registrations(
    registrations: Iterable[Registration],
) -> list[FeeSetupRegistrationGpT]:
    """Group zero-amount registrations that need a finance fee decision."""
    groups: list[FeeSetupRegistrationGpT] = []
    group_lookup: dict[int, FeeSetupRegistrationGpT] = {}
    for registration in registrations:
        amount_due = registration_invoice_amount(registration)
        if amount_due > Decimal("0.00"):
            continue
        student = registration.student
        group = group_lookup.get(student.id)
        if group is None:
            group = {"student": student, "rows": []}
            group_lookup[student.id] = group
            groups.append(group)
        course = registration.section.curriculum_course.course
        group["rows"].append(
            {
                "registration": registration,
                "current_amount": amount_due,
                "suggested_amount": suggested_registration_fee_amount(registration),
                "fee_type_code": infer_course_fee_type_code(course),
            }
        )
    return groups


def invoice_queryset(
    selected_student_id: Optional[int],
    status_filter: str,
    semester_id: Optional[int],
) -> QuerySet[CrsInvoice]:
    """Return the base invoice queryset for the finance officer view."""
    qs = CrsInvoice.objects.select_related(
        "student",
        "student__user",
        "semester",
        "curriculum_course__course",
        "student_semester_invoice",
    ).order_by("-created_at")
    if selected_student_id:
        qs = qs.filter(student_id=selected_student_id)
    if semester_id:
        qs = qs.filter(semester_id=semester_id)
    if status_filter == "open":
        qs = qs.filter(balance__gt=0)
    return qs


def uninvoiced_registration_queryset(
    selected_student_id: Optional[int],
    semester_id: Optional[int],
) -> QuerySet[Registration]:
    """Return invoiceable registrations that finance still needs to materialize."""
    return invoice_generation_registration_qs(
        student_id=selected_student_id,
        semester_id=semester_id,
    )


def fee_setup_registration_queryset(
    selected_student_id: Optional[int],
    semester_id: Optional[int],
) -> QuerySet[Registration]:
    """Return zero-credit registrations that still need course-fee setup."""
    # Include stale zero invoices; gp_fee_setup_registrations drops rows made billable.
    return invoiceable_registration_qs(
        student_id=selected_student_id,
        semester_id=semester_id,
        missing_only=False,
    ).filter(section__curriculum_course__credit_hours_id__lte=0)


def payment_queryset(
    selected_student_id: Optional[int],
    status_filter: str,
    semester_id: Optional[int],
) -> QuerySet[Payment]:
    """Return the base payment queryset for the finance officer view."""
    qs = (
        Payment.objects.select_related(
            "student_semester_invoice__student",
            "student_semester_invoice__student__user",
            "student_semester_invoice__semester",
            "payer",
            "status",
            "payment_method",
        )
        .prefetch_related(
            "student_semester_invoice__course_invoices__curriculum_course__course",
        )
        .order_by("-id")
    )
    if selected_student_id:
        qs = qs.filter(student_semester_invoice__student_id=selected_student_id)
    if semester_id:
        qs = qs.filter(student_semester_invoice__semester_id=semester_id)
    if status_filter and status_filter != "all":
        qs = qs.filter(status_id=status_filter)
    return qs


def clean_int(value: str | None) -> Optional[int]:
    """Return an int for the incoming value or None."""
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def finance_admin_links(user: User) -> list[FinanceAdminLinkT]:
    """Return finance admin shortcuts when the user can enter Django admin."""
    if not user.is_staff:
        return []
    link_specs = (
        ("Course invoices", "admin:finance_crsinvoice_changelist"),
        ("Semester invoices", "admin:finance_stdsemesterinvoice_changelist"),
        ("Payments", "admin:finance_payment_changelist"),
        ("Course fee stacks", "admin:finance_crsfeestack_changelist"),
        ("Fee stacks", "admin:finance_feestack_changelist"),
        ("Fee lines", "admin:finance_feestackline_changelist"),
    )
    links: list[FinanceAdminLinkT] = []
    for label, route_name in link_specs:
        try:
            href = reverse(route_name)
        except NoReverseMatch:
            continue
        links.append({"label": label, "href": href})
    if not links:
        return []
    return [{"label": "Admin home", "href": reverse("admin:index")}, *links]


def _without_page_params(params: QueryDict) -> QueryDict:
    """Return GET params with all portal pagination keys removed."""
    clean_params = params.copy()
    for page_param in PAGINATION_PAGE_PARAMS:
        clean_params.pop(page_param, None)
    return clean_params


def _pagination_state(
    request: HttpRequest,
    *,
    page_param: str,
    semester_id: Optional[int],
) -> PaginationStateT:
    """Return encoded query and hidden fields for one pagination control."""
    pagination_params = request.GET.copy()
    pagination_params.pop(page_param, None)
    if "semester" not in pagination_params and semester_id:
        pagination_params["semester"] = str(semester_id)
    hidden_fields: list[PaginationHiddenFieldT] = []
    for key, values in pagination_params.lists():
        for value in values:
            hidden_fields.append({"name": key, "value": value})
    return {
        "query": pagination_params.urlencode(),
        "hidden_fields": hidden_fields,
    }


def build_finance_console_context(request: HttpRequest) -> PortalContextT:
    """Build context for the finance officer invoice and payment console."""
    user = cast(User, request.user)
    tab = request.GET.get("tab", "invoices")
    search_query = request.GET.get("q", "").strip()
    selected_student_id = clean_int(request.GET.get("student_id"))
    invoice_status = request.GET.get("invoice_status") or None
    payment_status = request.GET.get("payment_status") or None
    semester_param = request.GET.get("semester")
    semester_id = clean_int(semester_param)
    semester_param_present = "semester" in request.GET
    if semester_param == "all":
        semester_id = None
    if selected_student_id and invoice_status is None:
        invoice_status = "all"
    if not selected_student_id and invoice_status is None:
        invoice_status = "open"
    if selected_student_id and payment_status is None:
        payment_status = "all"
    if not selected_student_id and payment_status is None:
        payment_status = "pending"
    if not semester_param_present:
        current_semester = None if selected_student_id else Semester.get_current_sem()
        if current_semester is not None:
            semester_id = current_semester.id
    all_semesters_selected = semester_param == "all" or (
        selected_student_id is not None and not semester_param_present
    )

    base_params = _without_page_params(request.GET)
    base_params.pop("tab", None)
    base_query = base_params.urlencode()
    if base_query:
        invoice_tab_url = f"?tab=invoices&{base_query}"
        payment_tab_url = f"?tab=payments&{base_query}"
    else:
        invoice_tab_url = "?tab=invoices"
        payment_tab_url = "?tab=payments"
    invoice_all_url = "?tab=invoices&invoice_status=all&semester=all"
    payment_all_url = "?tab=payments&payment_status=all&semester=all"
    pagination_state = _pagination_state(
        request,
        page_param="page",
        semester_id=semester_id,
    )
    registration_pagination_state = _pagination_state(
        request,
        page_param="registration_page",
        semester_id=semester_id,
    )
    fee_setup_pagination_state = _pagination_state(
        request,
        page_param="fee_setup_page",
        semester_id=semester_id,
    )

    student_options = []
    selected_student_label = ""
    if selected_student_id:
        selected_student = finance_std_by_id(selected_student_id)
        if selected_student:
            student_options = build_std_options(
                [selected_student],
                selected_student_id,
            )
            selected_student_label = student_options[0]["label"]
    invoice_qs = invoice_queryset(
        selected_student_id,
        invoice_status or "open",
        semester_id,
    )
    payment_qs = payment_queryset(
        selected_student_id,
        payment_status or "pending",
        semester_id,
    )
    uninvoiced_registration_qs = uninvoiced_registration_queryset(
        selected_student_id,
        semester_id,
    )
    fee_setup_registration_qs = fee_setup_registration_queryset(
        selected_student_id,
        semester_id,
    )

    invoice_page = Paginator(invoice_qs, 100).get_page(request.GET.get("page"))
    payment_page = Paginator(payment_qs, 100).get_page(request.GET.get("page"))
    uninvoiced_registration_page = Paginator(
        uninvoiced_registration_qs,
        100,
    ).get_page(request.GET.get("registration_page"))
    fee_setup_registration_page = Paginator(
        fee_setup_registration_qs,
        100,
    ).get_page(request.GET.get("fee_setup_page"))

    invoice_status_options = [
        {"value": "open", "label": "Open balance"},
        {"value": "all", "label": "All invoices"},
    ]
    payment_status_options = [
        {"value": "all", "label": "All payments"},
    ] + [
        {"value": status.code, "label": status.label}
        for status in PaymentStatus.objects.order_by("label")
    ]
    payment_status_choices = [
        {"code": status.code, "label": status.label}
        for status in PaymentStatus.objects.order_by("label")
    ]
    payment_method_options = [
        {"code": method.code, "label": method.label}
        for method in PaymentMethod.objects.order_by("label")
    ]
    payer_options = [
        {"code": payer.code, "label": payer.label}
        for payer in Payer.objects.order_by("label")
    ]
    semester_options = [
        {
            "value": "all",
            "label": "All semesters",
            "selected": all_semesters_selected,
        }
    ]
    for sem in Semester.objects.select_related("academic_year").order_by(
        "-academic_year__start_date",
        "-number",
    ):
        semester_options.append(
            {
                "value": str(sem.id),
                "label": f"{sem.academic_year.code} · Semester {sem.number}",
                "selected": semester_id == sem.id,
            }
        )

    active_task = "payment_validation" if tab == "payments" else "invoice_console"
    dashboard_url = reverse(
        "staff_role_dashboard",
        kwargs={"role": "finance_officer"},
    )
    return {
        "page_title": "Finance Officer Console",
        "page_summary": "Review invoices, record payments, and clear balances.",
        "eyebrow": "Finance officer",
        "sidebar_links": build_staff_sidebar_links("finance_officer", active_task),
        "role_switcher": build_staff_role_switcher(user, "finance_officer"),
        "breadcrumbs": [
            {"label": "Finance overview", "href": dashboard_url},
            {"label": "Invoice console", "href": ""},
        ],
        "active_tab": tab,
        "search_query": search_query,
        "student_options": student_options,
        "selected_student_id": selected_student_id,
        "selected_student_label": selected_student_label,
        "invoice_status": invoice_status,
        "payment_status": payment_status,
        "invoice_status_options": invoice_status_options,
        "payment_status_options": payment_status_options,
        "payment_status_choices": payment_status_choices,
        "payment_method_options": payment_method_options,
        "payer_options": payer_options,
        "semester_options": semester_options,
        "invoice_groups": gp_invoices(invoice_page),
        "payment_groups": gp_payments(payment_page),
        "uninvoiced_registration_groups": gp_uninvoiced_registrations(
            uninvoiced_registration_page
        ),
        "fee_setup_registration_groups": gp_fee_setup_registrations(
            fee_setup_registration_page
        ),
        "invoice_page": invoice_page,
        "payment_page": payment_page,
        "uninvoiced_registration_page": uninvoiced_registration_page,
        "fee_setup_registration_page": fee_setup_registration_page,
        "current_path": request.get_full_path(),
        "invoice_tab_url": invoice_tab_url,
        "payment_tab_url": payment_tab_url,
        "invoice_all_url": invoice_all_url,
        "payment_all_url": payment_all_url,
        "pagination_query": pagination_state["query"],
        "pagination_hidden_fields": pagination_state["hidden_fields"],
        "registration_pagination_query": registration_pagination_state["query"],
        "registration_pagination_hidden_fields": registration_pagination_state[
            "hidden_fields"
        ],
        "fee_setup_pagination_query": fee_setup_pagination_state["query"],
        "fee_setup_pagination_hidden_fields": fee_setup_pagination_state["hidden_fields"],
        "pagination_action": request.path,
        "student_autocomplete_url": reverse("finance_officer_std_autocomplete"),
        "setup_registration_fee_url": reverse("finance_officer_setup_registration_fee"),
        "finance_admin_links": finance_admin_links(user),
        "dashboard_url": dashboard_url,
    }
