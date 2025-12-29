# payments/payme_utils.py - TUZATILGAN (settings.PAYME_SETTINGS bilan)
import base64
import time
from django.conf import settings


def create_payme_link(telegram_id, amount, order_id):
    """
    Payme to'lov havolasini yaratish (TO'G'RI FORMAT)

    Args:
        telegram_id: Telegram user ID
        amount: so'mda (float yoki int)
        order_id: UNIQUE chek ID (MAJBURIY)
    """

    try:
        # ✅ PAYME_SETTINGS dan o'qish
        payme_settings = getattr(settings, 'PAYME_SETTINGS', {})
        merchant_id = payme_settings.get('MERCHANT_ID', '')

        if not merchant_id:
            print("❌ ERROR: PAYME_MERCHANT_ID not configured in settings.PAYME_SETTINGS")
            return ""

        # 🔴 order_id MAJBURIY
        if not order_id:
            print("❌ ERROR: order_id is required")
            return ""

        # 💰 so'm → tiyin
        amount_tiyin = int(float(amount) * 100)

        # 📌 PARAMETRLAR (PAYME TALABI)
        params_list = [
            f"m={merchant_id}",
            f"ac.order_id={order_id}",  # 🔴 MAJBURIY
            f"ac.telegram_id={telegram_id}",  # ✅ ruxsat etilgan
            f"a={amount_tiyin}",
        ]

        params_str = ";".join(params_list)

        # 🔐 Base64 encode
        encoded = base64.b64encode(
            params_str.encode("utf-8")
        ).decode("utf-8")

        # Payme URL (settings dan)
        payme_url = payme_settings.get('PAYME_URL', 'https://checkout.paycom.uz')
        url = f"{payme_url}/{encoded}"

        print("✅ PAYME URL:", url)
        print("📋 PAYME PARAMS:", params_str)

        return url

    except Exception as e:
        print("❌ PAYME LINK ERROR:", e)
        import traceback
        traceback.print_exc()
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

        # ✅ PAYME_SETTINGS dan o'qish
        payme_settings = getattr(settings, 'PAYME_SETTINGS', {})
        secret_key = payme_settings.get('SECRET_KEY', '')

        if not secret_key:
            print("❌ ERROR: PAYME_SECRET_KEY not configured in settings.PAYME_SETTINGS")
            return False

        return decoded == f"Paycom:{secret_key}"

    except Exception as e:
        print("❌ PAYME AUTH ERROR:", e)
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