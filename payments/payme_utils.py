# payments/payme_utils.py - TO'G'RILANGAN
import base64
import json
from django.conf import settings


def create_payme_link(telegram_id, amount):
    """
    Payme to'lov havolasini yaratish

    Args:
        telegram_id: Foydalanuvchi telegram ID (int yoki str)
        amount: Summa (so'mda, float)

    Returns:
        str: Payme to'lov havolasi
    """
    try:
        # Settings dan merchant_id ni olish
        merchant_id = getattr(settings, 'PAYME_MERCHANT_ID', '')
        if not merchant_id:
            print("ERROR: PAYME_MERCHANT_ID setting not configured")
            return ""

        # Summa tiyinga (1 so'm = 100 tiyin)
        try:
            amount_float = float(amount)
            amount_tiyin = int(amount_float * 100)
        except (ValueError, TypeError):
            print(f"ERROR: Invalid amount: {amount}")
            return ""

        # Account parametrlari - FAQAT telegram_id
        # Payme uchun: ac.{key}={value}
        account_params = {
            'telegram_id': str(telegram_id)
        }

        # Parametrlarni string formatga o'tkazish
        params_list = [f"m={merchant_id}"]

        # Account parametrlarini qo'shish
        for key, value in account_params.items():
            if value:  # Faqat bo'sh bo'lmagan qiymatlarni qo'shamiz
                params_list.append(f"ac.{key}={value}")

        # Summa parametri
        params_list.append(f"a={amount_tiyin}")

        # Barcha parametrlarni birlashtirish
        params_str = ";".join(params_list)

        # Base64 kodlash
        encoded = base64.b64encode(params_str.encode('utf-8')).decode('utf-8')

        # URL yaratish
        url = f"https://checkout.paycom.uz/{encoded}"

        print(f"Payme URL created: {url}")
        print(f"Params: {params_str}")

        return url

    except Exception as e:
        print(f"ERROR creating Payme link: {e}")
        return ""


def check_payme_auth(request):
    """
    Payme dan kelayotgan so'rovni autentifikatsiya qilish

    Authorization: Basic base64(Paycom:secret_key)
    """
    try:
        # Authorization header ni olish
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if not auth_header.startswith('Basic '):
            print(f"Invalid auth header: {auth_header[:50]}...")
            return False

        # Base64 dan decode qilish
        encoded_credentials = auth_header.split(' ')[1]
        decoded_credentials = base64.b64decode(encoded_credentials).decode('utf-8')

        # Format: "Paycom:secret_key"
        # Payme secret key ni settings dan olish
        secret_key = getattr(settings, 'PAYME_SECRET_KEY', '')
        if not secret_key:
            print("ERROR: PAYME_SECRET_KEY not configured")
            return False

        expected_credentials = f"Paycom:{secret_key}"

        # Tekshirish
        is_valid = decoded_credentials == expected_credentials

        if not is_valid:
            print(f"Invalid credentials. Expected: {expected_credentials}, Got: {decoded_credentials}")

        return is_valid

    except Exception as e:
        print(f"ERROR checking Payme auth: {e}")
        return False


def tiyin_to_sum(amount_tiyin):
    """
    Tiyindan so'mga o'tkazish

    Args:
        amount_tiyin: Tiyindagi summa

    Returns:
        float: So'mdagi summa
    """
    try:
        return float(amount_tiyin) / 100.0
    except:
        return 0.0


def sum_to_tiyin(amount_sum):
    """
    So'mdan tiyinga o'tkazish

    Args:
        amount_sum: So'mdagi summa

    Returns:
        int: Tiyindagi summa
    """
    try:
        return int(float(amount_sum) * 100)
    except:
        return 0


def decode_payme_params(params_base64):
    """
    Payme parametrlarini decode qilish (debug uchun)
    """
    try:
        decoded = base64.b64decode(params_base64).decode('utf-8')
        params = {}

        for param in decoded.split(';'):
            if '=' in param:
                key, value = param.split('=', 1)
                params[key] = value

        return params
    except:
        return {}