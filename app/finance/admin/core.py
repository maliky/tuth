from django.contrib import admin

from app.finance.models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("reservation", "amount", "method", "recorded_by", "created_at")
    readonly_fields = ("created_at",)
