# payments/admin.py - TO'LIQ TUZATILGAN VA XATOLAR TUZATILGAN

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

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

    list_display = (
        'id',
        'order_id_display',
        'user_link_safe',
        'tariff_info',
        'formatted_amount',
        'pricing_count_display',
        'state_badge',
        'payme_transaction_short',
        'created_at',
    )

    list_filter = ('state', 'created_at')

    search_fields = (
        'order_id',
        'payme_transaction_id',
        'user__telegram_id',
        'user__full_name',
        'user__username',
    )

    readonly_fields = (
        'id',
        'created_at',
        'performed_at',
        'cancelled_at',
        'order_id_copy_button',
    )

    ordering = ('-created_at',)

    fieldsets = (
        ("📋 Buyurtma ma'lumotlari", {
            'fields': (
                'id',
                'order_id',
                'order_id_copy_button',
                'user',
                'tariff',
            )
        }),
        ("💰 To'lov ma'lumotlari", {
            'fields': ('amount', 'pricing_count')
        }),
        ("🔐 Payme ma'lumotlari", {
            'fields': ('payme_transaction_id', 'state', 'reason')
        }),
        ("🕐 Vaqt", {
            'fields': ('created_at', 'performed_at', 'cancelled_at')
        }),
    )

    # ================= DISPLAY METHODS =================

    def order_id_display(self, obj):
        if not obj.order_id:
            return "—"

        oid = str(obj.order_id)
        short = oid[:8] + "..." + oid[-8:] if len(oid) > 16 else oid

        return format_html(
            '<span style="font-family:monospace;background:#f2f2f2;'
            'padding:3px 6px;border-radius:4px" title="{}">{}</span>',
            oid,
            short,
        )

    order_id_display.short_description = "Order ID"

    def order_id_copy_button(self, obj):
        if not obj or not obj.order_id:
            return "—"

        return mark_safe(f"""
        <input id="order_id_copy"
               value="{obj.order_id}"
               style="width:100%;padding:6px;font-family:monospace"
               readonly>

        <button type="button"
                onclick="navigator.clipboard.writeText(document.getElementById('order_id_copy').value)"
                style="margin-top:6px;padding:6px 14px;
                       background:#417690;color:white;
                       border:none;border-radius:4px;cursor:pointer;">
            📋 Nusxalash
        </button>
        """)

    order_id_copy_button.short_description = "Order ID nusxalash"

    def user_link_safe(self, obj):
        if not obj.user:
            return format_html('<span style="color:#999">Foydalanuvchi yo‘q</span>')

        url = reverse("admin:payments_botuser_change", args=[obj.user.id])
        return format_html(
            '<a href="{}" title="Telegram ID: {}">{}</a>',
            url,
            obj.user.telegram_id,
            obj.user.full_name,
        )

    user_link_safe.short_description = "Foydalanuvchi"

    def tariff_info(self, obj):
        if not obj.tariff:
            return "—"

        return format_html(
            '<span title="{}">{} ta</span>',
            obj.tariff.name,
            obj.tariff.count,
        )

    tariff_info.short_description = "Tarif"

    def formatted_amount(self, obj):
        return f"{obj.amount:,.0f} so'm" if obj.amount else "—"

    formatted_amount.short_description = "Summa"

    def pricing_count_display(self, obj):
        return f"{obj.pricing_count} ta" if obj.pricing_count else "—"

    pricing_count_display.short_description = "Narxlashlar"

    def payme_transaction_short(self, obj):
        if not obj.payme_transaction_id:
            return "—"

        tx = obj.payme_transaction_id
        short = tx[:12] + "..." if len(tx) > 15 else tx

        return format_html(
            '<span style="font-family:monospace;font-size:11px" title="{}">{}</span>',
            tx,
            short,
        )

    payme_transaction_short.short_description = "Payme TX"

    def state_badge(self, obj):
        colors = {
            Payment.STATE_CREATED: "#ff9800",
            Payment.STATE_COMPLETED: "#4caf50",
            Payment.STATE_CANCELLED: "#f44336",
            Payment.STATE_CANCELLED_AFTER_COMPLETE: "#b71c1c",
        }

        color = colors.get(obj.state, "#9e9e9e")
        name = dict(Payment.STATE_CHOICES).get(obj.state, "Noma'lum")

        return format_html(
            '<span style="background:{};color:white;padding:4px 10px;'
            'border-radius:12px;font-size:11px;font-weight:bold">{}</span>',
            color,
            name,
        )

    state_badge.short_description = "Holati"


@admin.register(PricingHistory)
class PricingHistoryAdmin(admin.ModelAdmin):
    list_display = ['user_link_safe', 'phone_model', 'formatted_price', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__telegram_id', 'user__full_name', 'phone_model']
    readonly_fields = ['user', 'phone_model', 'price', 'created_at']
    ordering = ['-created_at']

    def user_link_safe(self, obj):
        """Foydalanuvchi linkini ko'rsatish (safe versiya)"""
        if obj and obj.user:
            return format_html(
                '<a href="/admin/payments/botuser/{}/change/">{}</a>',
                obj.user.id,
                obj.user.full_name
            )
        return format_html('<span style="color: #999;">Foydalanuvchi yo\'q</span>')

    user_link_safe.short_description = 'Foydalanuvchi'

    def formatted_price(self, obj):
        """Narxni formatlash"""
        if obj and obj.price:
            return f"{obj.price:,.2f} so'm"
        return '-'

    formatted_price.short_description = 'Narxi'

    def has_add_permission(self, request):
        """Qo'shish taqiqlangan"""
        return False

    def has_change_permission(self, request, obj=None):
        """O'zgartirish taqiqlangan"""
        return False