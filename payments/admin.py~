# payments/admin.py
from django.contrib import admin
from .models import PricingTariff, BotUser, Payment, PricingHistory


@admin.register(PricingTariff)
class PricingTariffAdmin(admin.ModelAdmin):
    list_display = ['name', 'count', 'price', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name']
    list_editable = ['is_active']


@admin.register(BotUser)
class BotUserAdmin(admin.ModelAdmin):
    list_display = ['telegram_id', 'full_name', 'username', 'balance', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['telegram_id', 'full_name', 'username']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'amount', 'pricing_count', 'state', 'created_at']
    list_filter = ['state', 'created_at']
    search_fields = ['user__full_name', 'transaction_id', 'payme_transaction_id']
    readonly_fields = ['created_at', 'performed_at', 'cancelled_at']


@admin.register(PricingHistory)
class PricingHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone_model', 'price', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__full_name', 'phone_model']
    readonly_fields = ['created_at']