# payments/admin.py - TO'LIQ TUZATILGAN VA XATOLAR TUZATILGAN

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
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
    """
    ✅ Xatolar tuzatildi:
    1. user_link metodida NoneType xatosi tuzatildi
    2. Order ID ko'rsatishda xatolar tuzatildi
    """

    list_display = [
        'id',
        'order_id_display',
        'user_link_safe',  # ✅ Safe versiyasi
        'tariff_info',
        'formatted_amount',
        'pricing_count_display',
        'state_badge',
        'payme_transaction_short',
        'created_at'
    ]

    list_filter = ['state', 'created_at']

    search_fields = [
        'id',
        'order_id',
        'payme_transaction_id',
        'user__telegram_id',
        'user__full_name',
        'user__username'
    ]

    readonly_fields = [
        'id',
        'order_id',
        'payme_transaction_id',
        'created_at',
        'performed_at',
        'cancelled_at',
        'order_id_copy_button'
    ]

    ordering = ['-created_at']

    fieldsets = (
        ('📋 Buyurtma ma\'lumotlari', {
            'fields': (
                'id',
                'order_id',
                'order_id_copy_button',
                'user',
                'tariff'
            )
        }),
        ('💰 To\'lov ma\'lumotlari', {
            'fields': ('amount', 'pricing_count')
        }),
        ('🔐 Payme ma\'lumotlari', {
            'fields': ('payme_transaction_id', 'state', 'reason')
        }),
        ('🕐 Vaqt', {
            'fields': ('created_at', 'performed_at', 'cancelled_at'),
        }),
    )

    def order_id_display(self, obj):
        """Order ID ni qisqartirib ko'rsatish"""
        if obj.order_id:
            order_str = str(obj.order_id)
            if len(order_str) > 16:
                short_id = order_str[:8] + '...' + order_str[-8:]
            else:
                short_id = order_str
            return format_html(
                '<span style="font-family: monospace; background: #f0f0f0; '
                'padding: 2px 6px; border-radius: 3px;" title="{}">{}</span>',
                obj.order_id,
                short_id
            )
        return '-'

    order_id_display.short_description = 'Order ID'

    def order_id_copy_button(self, obj):
        """Order ID ni nusxalash uchun tugma"""
        if obj and obj.order_id:
            return format_html(
                '<div style="margin: 10px 0;">'
                '<input type="text" value="{}" id="order_id_field" '
                'style="width: 100%; padding: 8px; font-family: monospace; '
                'border: 1px solid #ccc; border-radius: 4px;" readonly>'
                '<button type="button" onclick="copyOrderId()" '
                'style="margin-top: 8px; padding: 8px 16px; background: #417690; '
                'color: white; border: none; border-radius: 4px; cursor: pointer;">'
                '📋 Nusxalash</button>'
                '<span id="copy_status" style="margin-left: 10px; color: green;"></span>'
                '</div>'
                '<script>'
                'function copyOrderId() {{'
                '  var field = document.getElementById("order_id_field");'
                '  field.select();'
                '  document.execCommand("copy");'
                '  document.getElementById("copy_status").innerHTML = "✅ Nusxalandi!";'
                '  setTimeout(function() {{'
                '    document.getElementById("copy_status").innerHTML = "";'
                '  }}, 2000);'
                '}}'
                '</script>',
                obj.order_id
            )
        return '-'

    order_id_copy_button.short_description = 'Order ID (test uchun)'

    def user_link_safe(self, obj):
        """✅ Foydalanuvchi linkini ko'rsatish (safe versiya)"""
        if obj and obj.user:
            return format_html(
                '<a href="/admin/payments/botuser/{}/change/" title="Telegram ID: {}">{}</a>',
                obj.user.id,
                obj.user.telegram_id,
                obj.user.full_name
            )
        return format_html('<span style="color: #999;">Foydalanuvchi yo\'q</span>')

    user_link_safe.short_description = 'Foydalanuvchi'

    def user_link(self, obj):
        """⚠️ Eski metod, faqat qo'shimcha xavfsizlik uchun"""
        return self.user_link_safe(obj)

    def tariff_info(self, obj):
        """Tarif ma'lumotlarini ko'rsatish"""
        if obj and obj.tariff:
            return format_html(
                '<span title="{}">{} ta narxlash</span>',
                obj.tariff.name,
                obj.tariff.count
            )
        return '-'

    tariff_info.short_description = 'Tarif'

    def formatted_amount(self, obj):
        """Summani formatlash"""
        if obj and obj.amount:
            return f"{obj.amount:,.0f} so'm"
        return '-'

    formatted_amount.short_description = 'Summa'

    def pricing_count_display(self, obj):
        """Narxlashlar sonini ko'rsatish"""
        if obj and obj.pricing_count:
            return f"{obj.pricing_count} ta"
        return '-'

    pricing_count_display.short_description = 'Narxlashlar'

    def payme_transaction_short(self, obj):
        """Payme transaction ID ni qisqartirib ko'rsatish"""
        if obj and obj.payme_transaction_id:
            tx_id = obj.payme_transaction_id
            if len(tx_id) > 15:
                short = tx_id[:12] + '...'
            else:
                short = tx_id
            return format_html(
                '<span style="font-family: monospace; font-size: 11px;" '
                'title="{}">{}</span>',
                tx_id,
                short
            )
        return '-'

    payme_transaction_short.short_description = 'Payme TX'

    def state_badge(self, obj):
        """Holat ko'rsatkichi"""
        if not obj:
            return '-'

        colors = {
            1: '#ff9800',  # Yaratildi (orange)
            2: '#4caf50',  # To'landi (green)
            -1: '#f44336',  # Bekor qilindi (red)
            -2: '#d32f2f',  # To'lovdan keyin bekor qilindi (dark red)
        }
        color = colors.get(obj.state, '#9e9e9e')

        # State nomini olish
        state_name = dict(Payment.STATE_CHOICES).get(obj.state, "Noma'lum")

        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 12px; '
            'border-radius: 12px; font-weight: bold; font-size: 11px; '
            'display: inline-block;" title="{}">{}</span>',
            color,
            f"State code: {obj.state}",
            state_name
        )

    state_badge.short_description = 'Holati'


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