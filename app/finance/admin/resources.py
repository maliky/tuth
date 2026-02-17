"""Import/export resources for finance admin."""

from __future__ import annotations

from import_export import fields, resources

from app.academics.admin.widgets import CurriCrsWgt
from app.finance.admin.widgets import (
    InvoiceStatusWgt,
    PayerWgt,
    PaymentMethodWgt,
    PaymentStatusWgt,
    StaffWgt,
    StdSemInvoiceWgt,
)
from app.finance.models.invoice import CrsInvoice
from app.finance.models.payment import Payment
from app.people.admin.widgets import StdUserWgt
from app.shared.utils import parse_str
from app.timetable.admin.core_widgets import SemWgt


class InvoiceResource(resources.ModelResource):
    """Import/export resource for CrsInvoice using readable columns."""

    student = fields.Field(
        column_name="student_id",
        attribute="student",
        widget=StdUserWgt(),
    )
    curriculum_course = fields.Field(
        column_name="curriculum",
        attribute="curriculum_course",
        widget=CurriCrsWgt(),
    )
    semester = fields.Field(
        column_name="semester_no",
        attribute="semester",
        widget=SemWgt(),
    )
    status = fields.Field(
        column_name="status_code",
        attribute="status",
        widget=InvoiceStatusWgt(),
    )
    recorded_by = fields.Field(
        column_name="recorded_by",
        attribute="recorded_by",
        widget=StaffWgt(),
    )
    academic_year = fields.Field(attribute=None, column_name="academic_year")
    course_no = fields.Field(attribute=None, column_name="course_no")
    dept_code = fields.Field(attribute=None, column_name="dept_code")
    college_code = fields.Field(attribute=None, column_name="college_code")
    student_name = fields.Field(attribute=None, column_name="student_name")

    class Meta:
        model = CrsInvoice
        import_id_fields = ("student", "curriculum_course", "semester")
        fields = (
            "student",
            "curriculum_course",
            "semester",
            "initial_amount_due",
            "balance",
            "status",
            "recorded_by",
            "academic_year",
            "course_no",
            "dept_code",
            "college_code",
            "student_name",
        )

    def dehydrate_academic_year(self, obj):
        semester = getattr(obj, "semester", None)
        return str(semester.academic_year.code) if semester else ""

    def dehydrate_crs_no(self, obj):
        course = getattr(obj.curriculum_course, "course", None)
        return getattr(course, "number", "") if course else ""

    def dehydrate_dept_code(self, obj):
        course = getattr(obj.curriculum_course, "course", None)
        department = getattr(course, "department", None)
        return getattr(department, "code", "") if department else ""

    def dehydrate_college_code(self, obj):
        course = getattr(obj.curriculum_course, "course", None)
        department = getattr(course, "department", None)
        college = getattr(department, "college", None)
        return getattr(college, "code", "") if college else ""

    def dehydrate_std_name(self, obj):
        student = getattr(obj, "student", None)
        return getattr(student, "long_name", "") if student else ""

    def dehydrate_curri_crs(self, obj):
        curriculum = getattr(obj.curriculum_course, "curriculum", None)
        return getattr(curriculum, "short_name", "") if curriculum else ""

    def dehydrate_status(self, obj):
        status = getattr(obj, "status", None)
        return getattr(status, "code", "") if status else ""

    def dehydrate_recorded_by(self, obj):
        staff = getattr(obj, "recorded_by", None)
        return getattr(staff, "long_name", "") if staff else ""


class PaymentResource(resources.ModelResource):
    """Import/export resource for Payment with readable invoice keys."""

    student_semester_invoice = fields.Field(
        column_name="student_semester_invoice",
        attribute="student_semester_invoice",
        widget=StdSemInvoiceWgt(),
    )
    payment_method = fields.Field(
        column_name="payment_method",
        attribute="payment_method",
        widget=PaymentMethodWgt(),
    )
    payer = fields.Field(
        column_name="payer",
        attribute="payer",
        widget=PayerWgt(),
    )
    status = fields.Field(
        column_name="status",
        attribute="status",
        widget=PaymentStatusWgt(),
    )
    recorded_by = fields.Field(
        column_name="recorded_by",
        attribute="recorded_by",
        widget=StaffWgt(),
    )
    student_id = fields.Field(attribute=None, column_name="student_id")
    curriculum = fields.Field(attribute=None, column_name="curriculum")
    course_no = fields.Field(attribute=None, column_name="course_no")
    dept_code = fields.Field(attribute=None, column_name="dept_code")
    college_code = fields.Field(attribute=None, column_name="college_code")
    semester_no = fields.Field(attribute=None, column_name="semester_no")
    academic_year = fields.Field(attribute=None, column_name="academic_year")

    class Meta:
        model = Payment
        import_id_fields = (
            "student_semester_invoice",
            "payer",
            "amount_paid",
            "payment_method",
            "status",
        )
        fields = (
            "student_semester_invoice",
            "payer",
            "amount_paid",
            "payment_method",
            "status",
            "recorded_by",
            "student_id",
            "curriculum",
            "course_no",
            "dept_code",
            "college_code",
            "semester_no",
            "academic_year",
        )

    def _invoice_value(self, obj, field):
        invoice = getattr(obj, "student_semester_invoice", None)
        if not invoice:
            return ""
        return parse_str(field(invoice))

    def dehydrate_std_id(self, obj):
        return self._invoice_value(obj, lambda inv: inv.student.student_id)

    def dehydrate_curri(self, obj):
        # Parent invoices can span multiple curricula, so keep this export column blank.
        return ""

    def dehydrate_crs_no(self, obj):
        # Parent invoices can span multiple courses, so keep this export column blank.
        return ""

    def dehydrate_dept_code(self, obj):
        return ""

    def dehydrate_college_code(self, obj):
        return ""

    def dehydrate_sem_no(self, obj):
        return self._invoice_value(obj, lambda inv: inv.semester.number)

    def dehydrate_academic_year(self, obj):
        return self._invoice_value(obj, lambda inv: inv.semester.academic_year.code)
