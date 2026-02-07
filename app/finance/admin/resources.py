"""Import/export resources for finance admin."""

from __future__ import annotations

from import_export import fields, resources

from app.academics.admin.widgets import CurriculumCourseWidget
from app.finance.admin.widgets import (
    InvoiceStatusWidget,
    InvoiceWidget,
    PaymentMethodWidget,
    PaymentStatusWidget,
    StaffWidget,
)
from app.finance.models.invoice import Invoice
from app.finance.models.payment import Payment
from app.people.admin.widgets import StudentUserWidget
from app.shared.utils import parse_str
from app.timetable.admin.core_widgets import SemesterWidget


class InvoiceResource(resources.ModelResource):
    """Import/export resource for Invoice using readable columns."""

    student = fields.Field(
        column_name="student_id",
        attribute="student",
        widget=StudentUserWidget(),
    )
    curriculum_course = fields.Field(
        column_name="curriculum",
        attribute="curriculum_course",
        widget=CurriculumCourseWidget(),
    )
    semester = fields.Field(
        column_name="semester_no",
        attribute="semester",
        widget=SemesterWidget(),
    )
    status = fields.Field(
        column_name="status_code",
        attribute="status",
        widget=InvoiceStatusWidget(),
    )
    recorded_by = fields.Field(
        column_name="recorded_by",
        attribute="recorded_by",
        widget=StaffWidget(),
    )
    academic_year = fields.Field(attribute=None, column_name="academic_year")
    course_no = fields.Field(attribute=None, column_name="course_no")
    dept_code = fields.Field(attribute=None, column_name="dept_code")
    college_code = fields.Field(attribute=None, column_name="college_code")
    student_name = fields.Field(attribute=None, column_name="student_name")

    class Meta:
        model = Invoice
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

    def dehydrate_course_no(self, obj):
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

    def dehydrate_student_name(self, obj):
        student = getattr(obj, "student", None)
        return getattr(student, "long_name", "") if student else ""

    def dehydrate_curriculum_course(self, obj):
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

    invoice = fields.Field(
        column_name="invoice",
        attribute="invoice",
        widget=InvoiceWidget(),
    )
    payment_method = fields.Field(
        column_name="payment_method",
        attribute="payment_method",
        widget=PaymentMethodWidget(),
    )
    status = fields.Field(
        column_name="status",
        attribute="status",
        widget=PaymentStatusWidget(),
    )
    recorded_by = fields.Field(
        column_name="recorded_by",
        attribute="recorded_by",
        widget=StaffWidget(),
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
        import_id_fields = ("invoice", "amount_paid", "payment_method", "status")
        fields = (
            "invoice",
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
        invoice = getattr(obj, "invoice", None)
        if not invoice:
            return ""
        return parse_str(field(invoice))

    def dehydrate_student_id(self, obj):
        return self._invoice_value(obj, lambda inv: inv.student.student_id)

    def dehydrate_curriculum(self, obj):
        return self._invoice_value(
            obj, lambda inv: inv.curriculum_course.curriculum.short_name
        )

    def dehydrate_course_no(self, obj):
        return self._invoice_value(obj, lambda inv: inv.curriculum_course.course.number)

    def dehydrate_dept_code(self, obj):
        return self._invoice_value(
            obj, lambda inv: inv.curriculum_course.course.department.code
        )

    def dehydrate_college_code(self, obj):
        return self._invoice_value(
            obj, lambda inv: inv.curriculum_course.course.department.college.code
        )

    def dehydrate_semester_no(self, obj):
        return self._invoice_value(obj, lambda inv: inv.semester.number)

    def dehydrate_academic_year(self, obj):
        return self._invoice_value(obj, lambda inv: inv.semester.academic_year.code)
