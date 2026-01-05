# payments/models.py
import uuid

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal


class PricingTariff(models.Model):
    """Narxlash tariflari"""
    name = models.CharField(max_length=100, verbose_name="Tarif nomi")
    count = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Narxlashlar soni"
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Narxi (so'm)"
    )
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan")

    class Meta:
        verbose_name = "Narxlash tarifi"
        verbose_name_plural = "Narxlash tariflari"
        ordering = ['count']
        db_table = 'pricing_tariffs'

    def __str__(self):
        return f"{self.name} - {self.count} marta - {self.price:,.0f} so'm"

    @property
    def price_per_one(self):
        """Bitta narxlash narxi"""
        return self.price / self.count if self.count > 0 else 0


class BotUser(models.Model):
    """Bot foydalanuvchilari"""
    telegram_id = models.BigIntegerField(
        unique=True,
        db_index=True,
        verbose_name="Telegram ID"
    )
    username = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Username"
    )
    full_name = models.CharField(max_length=255, verbose_name="To'liq ismi")
    phone = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name="Telefon"
    )
    balance = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Balans (narxlashlar soni)"
    )
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ro'yxatdan o'tgan")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan")

    class Meta:
        verbose_name = "Bot foydalanuvchisi"
        verbose_name_plural = "Bot foydalanuvchilari"
        ordering = ['-created_at']
        db_table = 'bot_users'

    def __str__(self):
        username_display = f"@{self.username}" if self.username else "username yo'q"
        return f"{self.full_name} ({username_display})"

    def has_balance(self):
        """Balans borligini tekshirish"""
        return self.balance > 0

    def use_pricing(self):
        """Narxlashdan foydalanish"""
        if self.balance > 0:
            self.balance -= 1
            self.save(update_fields=['balance', 'updated_at'])
            return True
        return False

    def add_balance(self, count):
        """Balansni to'ldirish"""
        if count > 0:
            self.balance += count
            self.save(update_fields=['balance', 'updated_at'])
            return True
        return False


class Payment(models.Model):
    """To'lovlar tarixi (Payme mos)"""

    # ===== PAYME STATE =====
    STATE_CREATED = 1
    STATE_COMPLETED = 2
    STATE_CANCELLED = -1
    STATE_CANCELLED_AFTER_COMPLETE = -2

    STATE_CHOICES = [
        (STATE_CREATED, "Yaratildi"),
        (STATE_COMPLETED, "To'landi"),
        (STATE_CANCELLED, "Bekor qilindi"),
        (STATE_CANCELLED_AFTER_COMPLETE, "To'lovdan keyin bekor qilindi"),
    ]

    # ===== 🔴 PAYME ORDER ID =====
    order_id = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        default=uuid.uuid4,
        verbose_name="Chek ID (Payme)"
    )

    # ===== ALOQALAR =====
    user = models.ForeignKey(
        BotUser,
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name="Foydalanuvchi"
    )

    tariff = models.ForeignKey(
        PricingTariff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Tarif"
    )

    # ===== SUMMA =====
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Summa (so'm)"
    )

    pricing_count = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Narxlashlar soni"
    )

    # ===== PAYME TRANSACTION =====
    payme_transaction_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        verbose_name="Payme tranzaksiya ID"
    )

    # 🔴 MUHIM: Payme yuborgan create_time (millisekund)
    payme_create_time = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name="Payme create_time (ms)"
    )

    state = models.IntegerField(
        choices=STATE_CHOICES,
        default=STATE_CREATED,
        db_index=True,
        verbose_name="Holati"
    )

    # ===== VAQT MAYDONLARI =====
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan")
    performed_at = models.DateTimeField(null=True, blank=True, verbose_name="To'langan vaqt")
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name="Bekor qilingan vaqt")
    reason = models.IntegerField(null=True, blank=True, verbose_name="Bekor qilish sababi")

    class Meta:
        verbose_name = "To'lov"
        verbose_name_plural = "To'lovlar"
        ordering = ["-created_at"]
        db_table = "payments"
        indexes = [
            models.Index(fields=["order_id"]),
            models.Index(fields=["state", "created_at"]),
            models.Index(fields=["user", "state"]),
        ]

    def __str__(self):
        return f"#{self.order_id} | {self.user.full_name} | {self.amount:,.0f} so'm"

    # ===== TO‘LOVNI TASDIQLASH =====
    def complete_payment(self, transaction_id=None):
        """
        Payme PerformTransaction uchun
        """
        if self.state != self.STATE_CREATED:
            return False

        if transaction_id:
            self.payme_transaction_id = transaction_id

        self.state = self.STATE_COMPLETED
        self.performed_at = timezone.now()
        self.save(update_fields=[
            "state",
            "performed_at",
            "payme_transaction_id"
        ])

        self.user.add_balance(self.pricing_count)
        return True

    # ===== TO‘LOVNI BEKOR QILISH =====
    def cancel_payment(self, reason=None):
        """
        Payme CancelTransaction uchun
        """
        if self.state == self.STATE_CREATED:
            self.state = self.STATE_CANCELLED

        elif self.state == self.STATE_COMPLETED:
            self.state = self.STATE_CANCELLED_AFTER_COMPLETE

            if self.user.balance >= self.pricing_count:
                self.user.balance -= self.pricing_count
                self.user.save(update_fields=["balance", "updated_at"])

        self.cancelled_at = timezone.now()
        if reason is not None:
            self.reason = reason

        self.save(update_fields=[
            "state",
            "cancelled_at",
            "reason"
        ])
        return True


class PricingHistory(models.Model):
    """Narxlash tarixi"""
    user = models.ForeignKey(
        BotUser,
        on_delete=models.CASCADE,
        related_name='pricing_history',
        verbose_name="Foydalanuvchi"
    )
    phone_model = models.CharField(max_length=255, verbose_name="Telefon modeli")
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Narxi"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Narxlangan vaqt")

    class Meta:
        verbose_name = "Narxlash tarixi"
        verbose_name_plural = "Narxlash tarixi"
        ordering = ['-created_at']
        db_table = 'pricing_history'
        indexes = [
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"{self.user.full_name} - {self.phone_model}"