from django.contrib import admin

from app.finance.models import Payment, Scholarship


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("reservation", "amount", "method", "recorded_by", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Scholarship)
class ScholarshipAdmin(admin.ModelAdmin):
    list_display = ("student", "donor", "amount", "start_date", "end_date")
    autocomplete_fields = ("donor", "student")
