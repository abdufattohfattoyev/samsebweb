# payments/admin.py - TO'LIQ TUZATILGAN VA XATOLAR TUZATILGAN

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Q

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
        'order_id_display',
        'show_user',  # Метод nomini o'zgartirdik
        'show_tariff',
        'show_amount',
        'show_pricing_count',
        'show_state',
        'show_transaction_id',
        'created_at'
    ]

    list_filter = ['state', 'created_at']

    search_fields = [
        'order_id',
        'payme_transaction_id',
        'user__telegram_id',
        'user__full_name',
        'user__username',
    ]

    readonly_fields = [
        'id',
        'created_at',
        'performed_at',
        'cancelled_at',
        'order_id_copy_button',
    ]

    ordering = ['-created_at']

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

    # ========== DISPLAY METHODS ==========

    def order_id_display(self, obj):
        """Order ID ni ko'rsatish"""
        if not obj or not obj.order_id:
            return "—"

        oid = str(obj.order_id)
        # Agar order_id uzun bo'lsa, qisqartirib ko'rsatish
        if len(oid) > 16:
            short = oid[:8] + "..." + oid[-8:]
        else:
            short = oid

        return format_html(
            '<span style="font-family:monospace;background:#f2f2f2;'
            'padding:3px 6px;border-radius:4px;" title="{}">{}</span>',
            oid,
            short
        )

    order_id_display.short_description = "Order ID"
    order_id_display.admin_order_field = 'order_id'  # Tartiblash imkoniyati

    def order_id_copy_button(self, obj):
        """Order ID ni nusxalash tugmasi"""
        if not obj or not obj.order_id:
            return "—"

        return mark_safe(f"""
        <div style="margin: 10px 0;">
            <input id="order_id_copy_{obj.id}"
                   value="{obj.order_id}"
                   style="width:100%;padding:6px;font-family:monospace;border:1px solid #ccc;border-radius:4px;"
                   readonly>
            <button type="button"
                    onclick="copyToClipboard('order_id_copy_{obj.id}')"
                    style="margin-top:6px;padding:6px 14px;background:#417690;color:white;border:none;border-radius:4px;cursor:pointer;">
                📋 Nusxalash
            </button>
            <span id="copy_status_{obj.id}" style="margin-left:10px;color:green;"></span>
        </div>
        <script>
        function copyToClipboard(elementId) {{
            var copyText = document.getElementById(elementId);
            copyText.select();
            copyText.setSelectionRange(0, 99999); // For mobile devices
            document.execCommand("copy");

            var statusSpan = document.getElementById("copy_status_" + elementId.split('_')[2]);
            statusSpan.innerHTML = "✅ Nusxalandi!";
            setTimeout(function() {{
                statusSpan.innerHTML = "";
            }}, 2000);
        }}
        </script>
        """)

    order_id_copy_button.short_description = "Order ID nusxalash"

    def show_user(self, obj):
        """Foydalanuvchini ko'rsatish"""
        if not obj.user:
            return format_html('<span style="color:#999">Foydalanuvchi yoʻq</span>')

        url = reverse("admin:payments_botuser_change", args=[obj.user.id])
        return format_html(
            '<a href="{}" title="Telegram ID: {}">{}</a>',
            url,
            obj.user.telegram_id,
            obj.user.full_name
        )

    show_user.short_description = "Foydalanuvchi"
    show_user.admin_order_field = 'user__full_name'  # Tartiblash imkoniyati

    def show_tariff(self, obj):
        """Tarif ma'lumotlari"""
        if not obj.tariff:
            return "—"

        return format_html(
            '<span title="{}">{} ta</span>',
            obj.tariff.name,
            obj.tariff.count
        )

    show_tariff.short_description = "Tarif"
    show_tariff.admin_order_field = 'tariff__count'

    def show_amount(self, obj):
        """Summani formatlash"""
        if not obj.amount:
            return "—"
        return f"{obj.amount:,.0f} so'm"

    show_amount.short_description = "Summa"
    show_amount.admin_order_field = 'amount'

    def show_pricing_count(self, obj):
        """Narxlashlar soni"""
        if not obj.pricing_count:
            return "—"
        return f"{obj.pricing_count} ta"

    show_pricing_count.short_description = "Narxlashlar"
    show_pricing_count.admin_order_field = 'pricing_count'

    def show_transaction_id(self, obj):
        """Payme transaction ID"""
        if not obj.payme_transaction_id:
            return "—"

        tx = obj.payme_transaction_id
        # Agar transaction ID uzun bo'lsa, qisqartirib ko'rsatish
        if len(tx) > 15:
            short = tx[:12] + "..."
        else:
            short = tx

        return format_html(
            '<span style="font-family:monospace;font-size:11px;" title="{}">{}</span>',
            tx,
            short
        )

    show_transaction_id.short_description = "Payme TX"
    show_transaction_id.admin_order_field = 'payme_transaction_id'

    def show_state(self, obj):
        """Holatni rangli badge ko'rinishida ko'rsatish"""
        if not obj:
            return "—"

        colors = {
            Payment.STATE_CREATED: "#ff9800",  # Orange
            Payment.STATE_COMPLETED: "#4caf50",  # Green
            Payment.STATE_CANCELLED: "#f44336",  # Red
            Payment.STATE_CANCELLED_AFTER_COMPLETE: "#b71c1c",  # Dark Red
        }

        color = colors.get(obj.state, "#9e9e9e")
        # STATE_CHOICES dan state nomini olish
        state_name = dict(Payment.STATE_CHOICES).get(obj.state, "Noma'lum")

        return format_html(
            '<span style="background:{};color:white;padding:4px 10px;'
            'border-radius:12px;font-size:11px;font-weight:bold;">{}</span>',
            color,
            state_name
        )

    show_state.short_description = "Holati"
    show_state.admin_order_field = 'state'


@admin.register(PricingHistory)
class PricingHistoryAdmin(admin.ModelAdmin):
    list_display = ['show_user', 'phone_model', 'show_price', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__telegram_id', 'user__full_name', 'phone_model']
    readonly_fields = ['user', 'phone_model', 'price', 'created_at']
    ordering = ['-created_at']

    def show_user(self, obj):
        """Foydalanuvchi ma'lumotlari"""
        if not obj.user:
            return format_html('<span style="color:#999">Foydalanuvchi yoʻq</span>')

        url = reverse("admin:payments_botuser_change", args=[obj.user.id])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.user.full_name
        )

    show_user.short_description = "Foydalanuvchi"
    show_user.admin_order_field = 'user__full_name'

    def show_price(self, obj):
        """Narxni formatlash"""
        if not obj.price:
            return "—"
        return f"{obj.price:,.2f} so'm"

    show_price.short_description = "Narxi"
    show_price.admin_order_field = 'price'

    def has_add_permission(self, request):
        """Qo'shish taqiqlangan"""
        return False

    def has_change_permission(self, request, obj=None):
        """O'zgartirish taqiqlangan"""
        return False