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
    # ===== PAYME STATE =====
    STATE_CREATED = 1
    STATE_COMPLETED = 2
    STATE_CANCELLED = -1
    STATE_CANCELLED_AFTER_COMPLETE = -2

    STATE_CHOICES = (
        (STATE_CREATED, "Yaratildi"),
        (STATE_COMPLETED, "To'landi"),
        (STATE_CANCELLED, "Bekor qilindi"),
        (STATE_CANCELLED_AFTER_COMPLETE, "To'lovdan keyin bekor qilindi"),
    )

    # 🔴 PAYME ORDER ID (STRING BO‘LISHI SHART)
    order_id = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        default=uuid.uuid4,  # ✅ TO‘G‘RI
        verbose_name="Order ID"
    )

    # 🔴 USER PAYME CREATE DA YO‘Q BO‘LISHI MUMKIN
    user = models.ForeignKey(
        BotUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments"
    )

    tariff = models.ForeignKey(
        PricingTariff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    pricing_count = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    # ===== PAYME TRANSACTION =====
    payme_transaction_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        unique=True,
        db_index=True
    )

    payme_create_time = models.BigIntegerField(null=True, blank=True)
    payme_perform_time = models.BigIntegerField(null=True, blank=True)
    payme_cancel_time = models.BigIntegerField(null=True, blank=True)

    state = models.IntegerField(
        choices=STATE_CHOICES,
        default=STATE_CREATED,
        db_index=True
    )

    reason = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    performed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payments"
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.order_id} | {self.amount:,.0f} so'm"

    # ===== PERFORM =====
    def perform(self):
        print(f"--- DEBUG: Perform boshlandi. State: {self.state}, Pricing count: {self.pricing_count} ---")
        if self.state != self.STATE_CREATED:
            print(f"--- DEBUG: XATO! To'lov holati noto'g'ri: {self.state} ---")
            return False

        self.state = self.STATE_COMPLETED
        self.performed_at = timezone.now()
        self.payme_perform_time = int(timezone.now().timestamp() * 1000)

        self.save(update_fields=[
            "state",
            "performed_at",
            "payme_perform_time"
        ])
        print(f"--- DEBUG: Payment holati COMPLETED ga o'zgartirildi ---")

        if self.user and self.pricing_count:
            print(f"--- DEBUG: Balans oshirilmoqda. User: {self.user.telegram_id}, Miqdor: {self.pricing_count} ---")
            success = self.user.add_balance(self.pricing_count)
            print(f"--- DEBUG: Balans oshirish natijasi: {success} ---")
        else:
            print(f"--- DEBUG: XATO! User yoki pricing_count topilmadi: User={self.user}, Count={self.pricing_count} ---")

        return True

    # ===== CANCEL =====
    def cancel(self, reason=None):
        if self.state == self.STATE_COMPLETED:
            self.state = self.STATE_CANCELLED_AFTER_COMPLETE
        else:
            self.state = self.STATE_CANCELLED

        self.cancelled_at = timezone.now()
        self.payme_cancel_time = int(timezone.now().timestamp() * 1000)
        self.reason = reason

        self.save(update_fields=[
            "state",
            "cancelled_at",
            "payme_cancel_time",
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
