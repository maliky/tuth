"""Admin registration for enrollment request models."""

from __future__ import annotations

from django.contrib import admin

from app.people.models.enrollment_application import (
    EnrollmentApplication,
    EnrollmentApplicationDoc,
    EnrollmentCommunication,
    EnrollmentEmailTemplate,
)


class EnrollmentApplicationDocInline(admin.TabularInline):
    """Inline review of documents uploaded before final enrollment."""

    model = EnrollmentApplicationDoc
    extra = 0
    fields = ("document_type", "status", "data_file", "uploaded_at")
    readonly_fields = ("uploaded_at",)


class EnrollmentCommunicationInline(admin.TabularInline):
    """Inline audit trail for applicant communications."""

    model = EnrollmentCommunication
    extra = 0
    fields = ("subject", "sender", "sent_at", "email_sent", "error_message")
    readonly_fields = ("subject", "sender", "sent_at", "email_sent", "error_message")
    can_delete = False

    def has_add_permission(self, request, obj=None) -> bool:
        """Keep communication sending in the portal workflow."""
        return False


@admin.register(EnrollmentApplication)
class EnrollmentApplicationAdmin(admin.ModelAdmin):
    """Review pending enrollment applications."""

    list_display = (
        "full_name",
        "personal_email",
        "academic_career",
        "desired_curriculum",
        "status",
        "is_email_verified",
        "documents_reviewed",
        "placement_exam_completed",
        "created_at",
    )
    list_filter = (
        "status",
        "academic_career",
        "documents_reviewed",
        "placement_exam_completed",
        "desired_curriculum__college",
    )
    search_fields = (
        "first_name",
        "middle_name",
        "last_name",
        "personal_email",
        "desired_curriculum__short_name",
        "desired_curriculum__long_name",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "email_verified_at",
        "converted_student",
    )
    autocomplete_fields = ("user", "desired_curriculum", "desired_entry_semester")
    inlines = (EnrollmentApplicationDocInline, EnrollmentCommunicationInline)


@admin.register(EnrollmentApplicationDoc)
class EnrollmentApplicationDocAdmin(admin.ModelAdmin):
    """Standalone application document review."""

    list_display = ("application", "document_type", "status", "uploaded_at")
    list_filter = ("status", "document_type")
    search_fields = (
        "application__first_name",
        "application__last_name",
        "application__personal_email",
    )
    autocomplete_fields = ("application", "document_type", "status")


@admin.register(EnrollmentEmailTemplate)
class EnrollmentEmailTemplateAdmin(admin.ModelAdmin):
    """Edit enrollment email templates."""

    list_display = ("code", "subject", "updated_at")
    search_fields = ("code", "subject", "body")
    readonly_fields = ("updated_at",)


@admin.register(EnrollmentCommunication)
class EnrollmentCommunicationAdmin(admin.ModelAdmin):
    """Audit enrollment communications."""

    list_display = ("application", "subject", "sender", "sent_at", "email_sent")
    list_filter = ("email_sent", "sent_at")
    search_fields = (
        "application__first_name",
        "application__last_name",
        "application__personal_email",
        "subject",
    )
    readonly_fields = ("application", "sender", "subject", "body", "sent_at")


__all__ = [
    "EnrollmentApplicationAdmin",
    "EnrollmentApplicationDocAdmin",
    "EnrollmentCommunicationAdmin",
    "EnrollmentEmailTemplateAdmin",
]
