# test_payment_creation.py - PAYME_SETTINGS BILAN

"""
Bu script Django serverda to'lov yaratish xatoligini aniqlaydi.

Xatolik: "Payme havolasini yaratishda xatolik"

TEKSHIRISH:
python manage.py shell < test_payment_creation.py
"""

import os
import django

# Django sozlamalarini yuklash
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from payments.models import BotUser, PricingTariff, Payment
from payments.payme_utils import create_payme_link, get_payme_settings

print("\n" + "=" * 60)
print("TO'LOV YARATISH MUAMMOSINI TEKSHIRISH (PAYME_SETTINGS)")
print("=" * 60 + "\n")

# ============= 1. SETTINGS TEKSHIRISH =============
print("1️⃣ PAYME SETTINGS TEKSHIRISH:")
print("-" * 60)

payme_settings = getattr(settings, 'PAYME_SETTINGS', {})

if payme_settings:
    print("✅ PAYME_SETTINGS topildi!")
    print()
    print("Mavjud sozlamalar:")
    for key, value in payme_settings.items():
        if key == 'SECRET_KEY':
            display_value = '***' if value else 'YO\'Q'
        else:
            display_value = value if value else 'YO\'Q'

        status = "✅" if value else "❌"
        print(f"   {status} {key}: {display_value}")
else:
    print("❌ PAYME_SETTINGS MAVJUD EMAS!")

merchant_id = payme_settings.get('MERCHANT_ID', '')
secret_key = payme_settings.get('SECRET_KEY', '')

print()

if not merchant_id:
    print("❌ MERCHANT_ID yo'q! .env faylni tekshiring:")
    print("   PAYME_MERCHANT_ID=your_merchant_id")
    print()

if not secret_key:
    print("❌ SECRET_KEY yo'q! .env faylni tekshiring:")
    print("   PAYME_SECRET_KEY=your_secret_key")
    print()

# ============= 2. TARIF TEKSHIRISH =============
print("2️⃣ TARIF TEKSHIRISH:")
print("-" * 60)

tariffs = PricingTariff.objects.filter(is_active=True)
if tariffs.exists():
    print(f"✅ Faol tariflar: {tariffs.count()} ta")
    for t in tariffs:
        print(f"   • ID: {t.id} | {t.name} | {t.count} ta | {t.price:,.0f} so'm")
else:
    print("❌ FAOL TARIFLAR YO'Q!")
    print("   ➜ Django admin da tarif yarating:")
    print("   python manage.py createsuperuser")
    print("   python manage.py runserver")
    print("   http://localhost:8000/admin")

print()

# ============= 3. TEST FOYDALANUVCHI =============
print("3️⃣ TEST FOYDALANUVCHI YARATISH:")
print("-" * 60)

test_telegram_id = 999999999
test_user, created = BotUser.objects.get_or_create(
    telegram_id=test_telegram_id,
    defaults={
        'full_name': 'Test User',
        'username': 'testuser',
        'balance': 0
    }
)

if created:
    print(f"✅ Yangi foydalanuvchi yaratildi: {test_user.full_name}")
else:
    print(f"✅ Foydalanuvchi mavjud: {test_user.full_name}")

print()

# ============= 4. PAYME URL YARATISH TEST =============
print("4️⃣ PAYME URL YARATISH TESTI:")
print("-" * 60)

if not merchant_id:
    print("❌ Payme URL test qilib bo'lmaydi - MERCHANT_ID yo'q")
    print()
else:
    try:
        # Test parametrlar
        test_order_id = "TEST-ORDER-123"
        test_amount = 5000.0

        print(f"Test parametrlar:")
        print(f"  • order_id: {test_order_id}")
        print(f"  • telegram_id: {test_telegram_id}")
        print(f"  • amount: {test_amount:,.0f} so'm")
        print()

        # Payme URL yaratish
        payme_url = create_payme_link(
            telegram_id=test_telegram_id,
            amount=test_amount,
            order_id=test_order_id
        )

        if payme_url:
            print(f"✅ PAYME URL YARATILDI!")
            print(f"   URL: {payme_url}")
            print()

            # URL ni tekshirish
            expected_start = payme_settings.get('PAYME_URL', 'https://checkout.paycom.uz')
            if payme_url.startswith(expected_start):
                print("✅ URL formati to'g'ri")
            else:
                print(f"⚠️  URL formati kutilmagan. Kutilgan: {expected_start}")
        else:
            print("❌ PAYME URL YARATILMADI!")
            print("   ➜ payme_utils.py ni tekshiring")

    except TypeError as e:
        print("❌ XATOLIK: order_id parametri muammosi!")
        print(f"   Error: {e}")
        print()
        print("   ➜ payme_utils.py faylini almashtiring")

    except Exception as e:
        print(f"❌ XATOLIK: {e}")
        print()
        import traceback

        traceback.print_exc()

print()

# ============= 5. TO'LOV YARATISH TEST =============
print("5️⃣ TO'LOV YARATISH TESTI (DATABASE):")
print("-" * 60)

if tariffs.exists() and merchant_id:
    test_tariff = tariffs.first()

    try:
        # To'lov yaratish
        payment = Payment.objects.create(
            user=test_user,
            tariff=test_tariff,
            amount=test_tariff.price,
            pricing_count=test_tariff.count,
            state=Payment.STATE_CREATED
        )

        print(f"✅ TO'LOV YARATILDI!")
        print(f"   • Payment ID: {payment.id}")
        print(f"   • Order ID: {payment.order_id}")
        print(f"   • Amount: {payment.amount:,.0f} so'm")
        print(f"   • Count: {payment.pricing_count} ta")
        print()

        # Payme URL yaratish (real to'lov uchun)
        try:
            payme_url = create_payme_link(
                telegram_id=test_telegram_id,
                amount=float(payment.amount),
                order_id=str(payment.order_id)
            )

            if payme_url:
                print(f"✅ PAYME URL (real to'lov uchun):")
                print(f"   {payme_url}")
                print()
                print("✅ TO'LOV TIZIMI TO'LIQ ISHLAYDI!")
            else:
                print("❌ PAYME URL yaratilmadi")

        except Exception as e:
            print(f"❌ PAYME URL xatolik: {e}")
            import traceback

            traceback.print_exc()

        # Test to'lovni o'chirish
        payment.delete()
        print("\n(Test to'lov o'chirildi)")

    except Exception as e:
        print(f"❌ TO'LOV YARATISH XATOLIK: {e}")
        import traceback

        traceback.print_exc()

elif not tariffs.exists():
    print("❌ Tarif yo'q - test qilib bo'lmaydi")
elif not merchant_id:
    print("❌ MERCHANT_ID yo'q - test qilib bo'lmaydi")

print()

# ============= 6. .ENV FAYL TEKSHIRISH =============
print("6️⃣ .ENV FAYL TEKSHIRISH:")
print("-" * 60)

from pathlib import Path

env_file = Path(settings.BASE_DIR) / '.env'

if env_file.exists():
    print(f"✅ .env fayl topildi: {env_file}")
    print()

    # .env faylni o'qish
    with open(env_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    payme_lines = [line.strip() for line in lines if 'PAYME' in line.upper() and not line.strip().startswith('#')]

    if payme_lines:
        print("Payme sozlamalari .env da:")
        for line in payme_lines:
            # Secret ni yashirish
            if 'SECRET' in line:
                parts = line.split('=', 1)
                if len(parts) == 2:
                    print(f"   ✅ {parts[0]}=***")
                else:
                    print(f"   ⚠️  {line}")
            else:
                print(f"   ✅ {line}")
    else:
        print("❌ .env faylda Payme sozlamalari topilmadi!")
        print()
        print("Qo'shish kerak:")
        print("   PAYME_MERCHANT_ID=your_merchant_id")
        print("   PAYME_SECRET_KEY=your_secret_key")
else:
    print(f"❌ .env fayl topilmadi: {env_file}")
    print("   ➜ .env faylini yarating va Payme sozlamalarini qo'shing")

print()

# ============= 7. XULOSA =============
print("=" * 60)
print("XULOSA VA TAVSIYALAR:")
print("=" * 60)

problems = []
solutions = []

if not merchant_id:
    problems.append("❌ PAYME_MERCHANT_ID .env da yo'q yoki bo'sh")
    solutions.append("   1. .env faylini oching")
    solutions.append("   2. Qo'shing: PAYME_MERCHANT_ID=your_merchant_id")

if not secret_key:
    problems.append("❌ PAYME_SECRET_KEY .env da yo'q yoki bo'sh")
    solutions.append("   3. Qo'shing: PAYME_SECRET_KEY=your_secret_key")

if not tariffs.exists():
    problems.append("❌ Faol tariflar mavjud emas")
    solutions.append("   4. Django admin da tarif yarating")

if problems:
    print("\n⚠️  MUAMMOLAR:")
    for p in problems:
        print(f"   {p}")
    print()
    print("YECHIMLAR:")
    for s in solutions:
        print(s)
    print()
    print("KEYIN:")
    print("   5. payme_utils.py ni yangilang (PAYME_SETTINGS bilan)")
    print("   6. Django serverni qayta ishga tushiring:")
    print("      sudo systemctl restart gunicorn")
else:
    print("\n✅ HAMMASI TO'G'RI! TO'LOV TIZIMI ISHLAYDI!")

print("\n" + "=" * 60 + "\n")

# Test foydalanuvchini o'chirish
if created:
    test_user.delete()
    print("(Test foydalanuvchi o'chirildi)\n")