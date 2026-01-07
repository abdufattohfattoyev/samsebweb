# payments/payme_utils.py - TUZATILGAN (settings.PAYME_SETTINGS bilan)
import base64
import time
from django.conf import settings
import logging



logger = logging.getLogger("payme")


def create_payme_link(order_id, amount):
    """
    Payme to'lov havolasini yaratish (sandbox test uchun)
    Args:
        order_id: UNIQUE chek ID
        amount: so'mda (float yoki int)
    """

    try:
        payme_settings = getattr(settings, 'PAYME_SETTINGS', {})
        merchant_id = payme_settings.get('MERCHANT_ID', '')

        if not merchant_id:
            print("❌ ERROR: PAYME_MERCHANT_ID not configured")
            return ""

        if not order_id:
            print("❌ ERROR: order_id is required")
            return ""

        amount_tiyin = int(float(amount) * 100)

        # Sandbox test uchun faqat order_id va summa yuboriladi
        params_list = [
            f"m={merchant_id}",
            f"ac.order_id={order_id}",
            f"a={amount_tiyin}",
        ]

        params_str = ";".join(params_list)
        encoded = base64.b64encode(params_str.encode("utf-8")).decode("utf-8")
        payme_url = payme_settings.get('PAYME_URL', 'https://checkout.paycom.uz')
        url = f"{payme_url}/{encoded}"

        print("✅ PAYME URL:", url)
        print("📋 PAYME PARAMS:", params_str)
        return url

    except Exception as e:
        print("❌ PAYME LINK ERROR:", e)
        return ""


def check_payme_auth(request) -> bool:
    """
    Authorization: Basic base64("Paycom:SECRET_KEY")
    """
    try:
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")

        if not auth_header.startswith("Basic "):
            return False

        encoded = auth_header.split(" ", 1)[1]
        decoded = base64.b64decode(encoded).decode("utf-8")

        secret_key = settings.PAYME_SETTINGS.get("SECRET_KEY")
        expected = f"Paycom:{secret_key}"

        logger.warning(f"🔐 PAYME AUTH DECODED: {decoded}")
        logger.warning(f"🔐 PAYME AUTH EXPECTED: {expected}")

        return decoded == expected

    except Exception:
        logger.exception("❌ PAYME AUTH ERROR")
        return False


def tiyin_to_sum(amount_tiyin):
    """Tiyinni so'mga o'tkazish"""
    try:
        return float(amount_tiyin) / 100
    except:
        return 0.0


def sum_to_tiyin(amount_sum):
    """So'mni tiyinga o'tkazish"""
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


def get_payme_settings():
    """
    Payme sozlamalarini olish (debug uchun)
    """
    payme_settings = getattr(settings, 'PAYME_SETTINGS', {})
    return {
        'merchant_id': payme_settings.get('MERCHANT_ID', 'NOT_SET'),
        'secret_key': '***' if payme_settings.get('SECRET_KEY') else 'NOT_SET',
        'payme_url': payme_settings.get('PAYME_URL', 'NOT_SET'),
        'callback_url': payme_settings.get('CALLBACK_URL', 'NOT_SET'),
        'min_amount': payme_settings.get('MIN_AMOUNT', 0)
    }