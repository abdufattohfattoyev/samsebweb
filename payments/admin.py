# payments/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import PricingTariff, BotUser, Payment, PricingHistory


@admin.register(PricingTariff)
class PricingTariffAdmin(admin.ModelAdmin):
    list_display = ['name', 'count', 'formatted_price', 'formatted_price_per_one', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name']
    ordering = ['count']

    def formatted_price(self, obj):
        return f"{obj.price:,.0f} so'm"

    formatted_price.short_description = 'Narxi'

    def formatted_price_per_one(self, obj):
        return f"{obj.price_per_one:,.2f} so'm"

    formatted_price_per_one.short_description = 'Bitta narxlash narxi'


@admin.register(BotUser)
class BotUserAdmin(admin.ModelAdmin):
    list_display = ['telegram_id', 'full_name', 'username', 'balance', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['telegram_id', 'full_name', 'username']
    readonly_fields = ['telegram_id', 'created_at', 'updated_at']
    ordering = ['-created_at']

    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('telegram_id', 'full_name', 'username', 'phone')
        }),
        ('Balans', {
            'fields': ('balance',)
        }),
        ('Holati', {
            'fields': ('is_active',)
        }),
        ('Vaqt', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'user_link',
        'tariff',
        'formatted_amount',
        'pricing_count',
        'state_badge',
        'payme_transaction_id',
        'created_at'
    ]
    list_filter = ['state', 'created_at']
    search_fields = ['id', 'payme_transaction_id', 'user__telegram_id', 'user__full_name']
    readonly_fields = [
        'id',
        'payme_transaction_id',
        'created_at',
        'performed_at',
        'cancelled_at'
    ]
    ordering = ['-created_at']

    fieldsets = (
        ('Buyurtma ma\'lumotlari', {
            'fields': ('id', 'user', 'tariff')
        }),
        ('To\'lov ma\'lumotlari', {
            'fields': ('amount', 'pricing_count')
        }),
        ('Payme ma\'lumotlari', {
            'fields': ('payme_transaction_id', 'state', 'reason')
        }),
        ('Vaqt', {
            'fields': ('created_at', 'performed_at', 'cancelled_at'),
        }),
    )

    def user_link(self, obj):
        return format_html(
            '<a href="/admin/payments/botuser/{}/change/">{}</a>',
            obj.user.id,
            obj.user.full_name
        )

    user_link.short_description = 'Foydalanuvchi'

    def formatted_amount(self, obj):
        return f"{obj.amount:,.0f} so'm"

    formatted_amount.short_description = 'Summa'

    def state_badge(self, obj):
        colors = {
            1: 'orange',  # Yaratildi
            2: 'green',  # To'landi
            -1: 'red',  # Bekor qilindi
            -2: 'darkred',  # To'lovdan keyin bekor qilindi
        }
        color = colors.get(obj.state, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_state_display()
        )

    state_badge.short_description = 'Holati'


@admin.register(PricingHistory)
class PricingHistoryAdmin(admin.ModelAdmin):
    list_display = ['user_link', 'phone_model', 'formatted_price', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__telegram_id', 'user__full_name', 'phone_model']
    readonly_fields = ['user', 'phone_model', 'price', 'created_at']
    ordering = ['-created_at']

    def user_link(self, obj):
        return format_html(
            '<a href="/admin/payments/botuser/{}/change/">{}</a>',
            obj.user.id,
            obj.user.full_name
        )

    user_link.short_description = 'Foydalanuvchi'

    def formatted_price(self, obj):
        return f"${obj.price:,.2f}"

    formatted_price.short_description = 'Narxi'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False