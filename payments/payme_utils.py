# payments/payme_utils.py
import base64
import time
from django.conf import settings


def create_payme_link(telegram_id, amount, order_id=None):
    """
    Payme to'lov havolasini yaratish (TO‘G‘RI FORMAT)

    Args:
        telegram_id: Telegram user ID
        amount: so'mda (float yoki int)
        order_id: UNIQUE chek ID (ixtiyoriy, bo‘lmasa avtomatik yaratiladi)
    """

    try:
        merchant_id = getattr(settings, 'PAYME_MERCHANT_ID', '')
        if not merchant_id:
            raise ValueError("PAYME_MERCHANT_ID not configured")

        # 🔑 UNIQUE ORDER ID (chek)
        if not order_id:
            order_id = int(time.time() * 1000)  # unique ID

        # 💰 so'm → tiyin
        amount_tiyin = int(float(amount) * 100)

        # 📌 PARAMETRLAR (PAYME TALABI)
        params_list = [
            f"m={merchant_id}",
            f"ac.order_id={order_id}",          # 🔴 MAJBURIY
            f"ac.telegram_id={telegram_id}",    # ✅ ruxsat etilgan
            f"a={amount_tiyin}",
        ]

        params_str = ";".join(params_list)

        # 🔐 Base64 encode
        encoded = base64.b64encode(
            params_str.encode("utf-8")
        ).decode("utf-8")

        url = f"https://checkout.paycom.uz/{encoded}"

        print("✅ PAYME URL:", url)
        print("📋 PAYME PARAMS:", params_str)

        return url

    except Exception as e:
        print("❌ PAYME LINK ERROR:", e)
        return ""


def check_payme_auth(request):
    """
    Payme callback autentifikatsiyasi
    """
    try:
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")

        if not auth_header.startswith("Basic "):
            return False

        encoded = auth_header.split(" ")[1]
        decoded = base64.b64decode(encoded).decode("utf-8")

        secret_key = getattr(settings, "PAYME_SECRET_KEY", "")
        if not secret_key:
            return False

        return decoded == f"Paycom:{secret_key}"

    except Exception as e:
        print("❌ PAYME AUTH ERROR:", e)
        return False


def tiyin_to_sum(amount_tiyin):
    try:
        return float(amount_tiyin) / 100
    except:
        return 0.0


def sum_to_tiyin(amount_sum):
    try:
        return int(float(amount_sum) * 100)
    except:
        return 0


def decode_payme_params(params_base64):
    """
    Debug uchun: Base64 → parametrlar
    """
    try:
        decoded = base64.b64decode(params_base64).decode("utf-8")
        result = {}

        for item in decoded.split(";"):
            if "=" in item:
                k, v = item.split("=", 1)
                result[k] = v

        return result
    except:
        return {}
