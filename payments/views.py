# payments/views.py
import json
import logging
from decimal import Decimal
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import transaction as db_transaction
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from django.conf import settings
from .models import BotUser, Payment, PricingTariff, PricingHistory
from .payme_utils import create_payme_link, check_payme_auth, tiyin_to_sum

logger = logging.getLogger(__name__)


# ============= BOT UCHUN API ENDPOINTLAR =============

@api_view(['GET'])
def get_tariffs(request):
    """
    Barcha faol tariflarni olish

    GET /api/payments/tariffs/
    """
    tariffs = PricingTariff.objects.filter(is_active=True).order_by('count')

    data = [{
        'id': t.id,
        'name': t.name,
        'count': t.count,
        'price': float(t.price),
        'price_per_one': float(t.price_per_one)
    } for t in tariffs]

    return Response({
        'success': True,
        'tariffs': data
    })


@api_view(['POST'])
def create_user(request):
    """
    Foydalanuvchi yaratish yoki yangilash

    POST /api/payments/user/create/
    """
    telegram_id = request.data.get('telegram_id')
    full_name = request.data.get('full_name', '')
    username = request.data.get('username', '')

    if not telegram_id:
        return Response({
            'success': False,
            'error': 'telegram_id majburiy'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        user, created = BotUser.objects.get_or_create(
            telegram_id=telegram_id,
            defaults={
                'full_name': full_name,
                'username': username
            }
        )

        if not created:
            user.full_name = full_name
            user.username = username
            user.save()

        return Response({
            'success': True,
            'telegram_id': user.telegram_id,
            'balance': user.balance,
            'created': created
        })
    except Exception as e:
        logger.error(f"Create user error: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Xatolik yuz berdi'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_balance(request, telegram_id):
    """
    Foydalanuvchi balansini olish

    GET /api/payments/user/{telegram_id}/balance/
    """
    try:
        user = BotUser.objects.get(telegram_id=telegram_id)
        return Response({
            'success': True,
            'telegram_id': user.telegram_id,
            'balance': user.balance,
            'full_name': user.full_name,
            'username': user.username
        })
    except BotUser.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Foydalanuvchi topilmadi'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
def use_pricing(request):
    """
    Narxlashdan foydalanish (balansni kamaytirish)

    POST /api/payments/pricing/use/
    """
    telegram_id = request.data.get('telegram_id')
    phone_model = request.data.get('phone_model', '')
    price = request.data.get('price', 0)

    if not telegram_id:
        return Response({
            'success': False,
            'error': 'telegram_id majburiy'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = BotUser.objects.get(telegram_id=telegram_id)

        if user.balance <= 0:
            return Response({
                'success': False,
                'error': 'Balans yetarli emas',
                'balance': 0
            }, status=status.HTTP_400_BAD_REQUEST)

        with db_transaction.atomic():
            # Balansni kamaytirish
            user.balance -= 1
            user.save()

            # Tarixga saqlash
            PricingHistory.objects.create(
                user=user,
                phone_model=phone_model,
                price=price
            )

        return Response({
            'success': True,
            'balance': user.balance,
            'message': 'Narxlash muvaffaqiyatli'
        })

    except BotUser.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Foydalanuvchi topilmadi'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Use pricing error: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Xatolik yuz berdi'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def create_payment(request):
    """
    To'lov havolasini yaratish

    POST /api/payments/payment/create/
    Body:
    {
        "telegram_id": 123456789,
        "tariff_id": 1
    }

    Response:
    {
        "success": true,
        "payment_id": 1,
        "payment_url": "https://checkout.paycom.uz/...",
        "amount": 5000.0,
        "count": 1,
        "tariff_name": "1 ta narxlash"
    }
    """
    telegram_id = request.data.get('telegram_id')
    tariff_id = request.data.get('tariff_id')

    if not telegram_id or not tariff_id:
        return Response({
            'success': False,
            'error': 'telegram_id va tariff_id majburiy'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = BotUser.objects.get(telegram_id=telegram_id)
        tariff = PricingTariff.objects.get(id=tariff_id, is_active=True)

        # To'lov yaratish
        payment = Payment.objects.create(
            user=user,
            tariff=tariff,
            amount=tariff.price,
            pricing_count=tariff.count,
            state=Payment.STATE_CREATED
        )

        # Payme havolasi - FAQAT telegram_id
        payme_url = create_payme_link(
            telegram_id=telegram_id,
            amount=float(tariff.price)
        )

        logger.info(f"Payment created: #{payment.id} for user {telegram_id}")

        return Response({
            'success': True,
            'payment_id': payment.id,
            'payment_url': payme_url,
            'amount': float(tariff.price),
            'count': tariff.count,
            'tariff_name': tariff.name
        })

    except BotUser.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Foydalanuvchi topilmadi'
        }, status=status.HTTP_404_NOT_FOUND)
    except PricingTariff.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Tarif topilmadi'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Create payment error: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': 'To\'lov yaratishda xatolik'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def check_payment_status(request, telegram_id):
    """
    Telegram ID bo'yicha oxirgi to'lov holatini tekshirish

    GET /api/payments/payment/status/{telegram_id}/
    """
    try:
        user = BotUser.objects.get(telegram_id=telegram_id)

        # Oxirgi to'lovni topish
        payment = Payment.objects.filter(user=user).order_by('-created_at').first()

        if not payment:
            return Response({
                'success': False,
                'error': 'To\'lov topilmadi'
            }, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'success': True,
            'payment_id': payment.id,
            'state': payment.state,
            'state_display': payment.get_state_display(),
            'amount': float(payment.amount),
            'count': payment.pricing_count,
            'created_at': payment.created_at.isoformat(),
            'performed_at': payment.performed_at.isoformat() if payment.performed_at else None
        })
    except BotUser.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Foydalanuvchi topilmadi'
        }, status=status.HTTP_404_NOT_FOUND)


# ============= PAYME MERCHANT API =============

@csrf_exempt
@require_http_methods(["POST"])
def payme_callback(request):
    """
    Payme Merchant API callback endpoint

    POST /api/payments/payme/callback/
    """

    # 1. Autentifikatsiya
    if not check_payme_auth(request):
        logger.warning("Payme: Unauthorized request")
        return JsonResponse({
            'error': {
                'code': -32504,
                'message': {
                    'uz': "Ruxsat yo'q",
                    'ru': "Недостаточно привилегий",
                    'en': "Insufficient privileges"
                }
            }
        })

    try:
        # 2. JSON parse
        data = json.loads(request.body)
        method = data.get('method')
        params = data.get('params', {})
        request_id = data.get('id')

        logger.info(f"Payme request: method={method}, params={params}")

        # 3. Metodlar
        handlers = {
            'CheckPerformTransaction': check_perform_transaction,
            'CreateTransaction': create_transaction,
            'PerformTransaction': perform_transaction,
            'CancelTransaction': cancel_transaction,
            'CheckTransaction': check_transaction,
        }

        handler = handlers.get(method)
        if handler:
            result = handler(params)

            # result bu dict bo'lsa, to'g'ri format bilan qaytarish
            if isinstance(result, dict):
                if 'error' in result:
                    return JsonResponse({
                        'error': result['error'],
                        'id': request_id
                    })
                else:
                    return JsonResponse({
                        'result': result,
                        'id': request_id
                    })

            # Agar JsonResponse bo'lsa, id qo'shish
            response_data = json.loads(result.content)
            response_data['id'] = request_id
            return JsonResponse(response_data)
        else:
            return JsonResponse({
                'error': {
                    'code': -32601,
                    'message': {
                        'uz': 'Metod topilmadi',
                        'ru': 'Метод не найден',
                        'en': 'Method not found'
                    }
                },
                'id': request_id
            })

    except json.JSONDecodeError:
        return JsonResponse({
            'error': {
                'code': -32700,
                'message': {
                    'uz': 'JSON xato',
                    'ru': 'Ошибка парсинга',
                    'en': 'Parse error'
                }
            }
        })
    except Exception as e:
        logger.error(f"Payme callback error: {e}", exc_info=True)
        return JsonResponse({
            'error': {
                'code': -32400,
                'message': {
                    'uz': 'Ichki xatolik',
                    'ru': 'Внутренняя ошибка',
                    'en': 'Internal error'
                }
            }
        })


def check_perform_transaction(params):
    """1. CheckPerformTransaction - To'lov mumkinligini tekshirish"""
    amount = params.get('amount')
    account = params.get('account', {})
    telegram_id = account.get('telegram_id')

    if not telegram_id:
        return {
            'error': {
                'code': -31050,
                'message': {
                    'uz': 'telegram_id topilmadi',
                    'ru': 'telegram_id не найден',
                    'en': 'telegram_id not found'
                }
            }
        }

    try:
        user = BotUser.objects.get(telegram_id=telegram_id)

        # Minimal summa tekshiruvi (agar kerak bo'lsa)
        min_amount = getattr(settings, 'PAYME_MIN_AMOUNT', 1000)
        min_amount_tiyin = min_amount * 100

        if amount < min_amount_tiyin:
            return {
                'error': {
                    'code': -31001,
                    'message': {
                        'uz': f"Minimal summa {min_amount} so'm",
                        'ru': f"Минимальная сумма {min_amount}",
                        'en': f"Minimum amount {min_amount}"
                    }
                }
            }

        return {'allow': True}

    except BotUser.DoesNotExist:
        return {
            'error': {
                'code': -31050,
                'message': {
                    'uz': 'Foydalanuvchi topilmadi',
                    'ru': 'Пользователь не найден',
                    'en': 'User not found'
                }
            }
        }


def create_transaction(params):
    """2. CreateTransaction - Tranzaksiya yaratish"""
    payme_id = params.get('id')
    amount = params.get('amount')
    account = params.get('account', {})
    telegram_id = account.get('telegram_id')

    try:
        user = BotUser.objects.get(telegram_id=telegram_id)

        # Mavjud tranzaksiyani tekshirish
        existing = Payment.objects.filter(payme_transaction_id=payme_id).first()

        if existing:
            return {
                'create_time': int(existing.created_at.timestamp() * 1000),
                'transaction': str(existing.id),
                'state': existing.state
            }

        # Yangi to'lov yaratish
        # Summa so'mda
        amount_sum = tiyin_to_sum(amount)

        # Tarif orqali pricing_count aniqlash
        # Yoki to'g'ridan-to'g'ri hisoblash
        # Masalan: amount_sum / 5000 = pricing_count
        pricing_count = int(amount_sum / 5000) if amount_sum >= 5000 else 1

        with db_transaction.atomic():
            payment = Payment.objects.create(
                user=user,
                amount=amount_sum,
                pricing_count=pricing_count,
                payme_transaction_id=payme_id,
                state=Payment.STATE_CREATED
            )

        logger.info(f"Transaction created: {payme_id} -> Payment #{payment.id}")

        return {
            'create_time': int(payment.created_at.timestamp() * 1000),
            'transaction': str(payment.id),
            'state': payment.state
        }

    except BotUser.DoesNotExist:
        return {
            'error': {
                'code': -31050,
                'message': {
                    'uz': 'Foydalanuvchi topilmadi',
                    'ru': 'Пользователь не найден',
                    'en': 'User not found'
                }
            }
        }
    except Exception as e:
        logger.error(f"Create transaction error: {e}", exc_info=True)
        return {
            'error': {
                'code': -31008,
                'message': {
                    'uz': 'Xatolik',
                    'ru': 'Ошибка',
                    'en': 'Error'
                }
            }
        }


def perform_transaction(params):
    """3. PerformTransaction - To'lovni tasdiqlash"""
    payme_id = params.get('id')

    try:
        payment = Payment.objects.get(payme_transaction_id=payme_id)

        if payment.state == Payment.STATE_CREATED:
            with db_transaction.atomic():
                payment.state = Payment.STATE_COMPLETED
                payment.performed_at = timezone.now()
                payment.save()

                # Balansga qo'shish
                payment.user.balance += payment.pricing_count
                payment.user.save()

            logger.info(f"Transaction performed: {payme_id} -> Payment #{payment.id}, balance +{payment.pricing_count}")

            return {
                'transaction': str(payment.id),
                'perform_time': int(payment.performed_at.timestamp() * 1000),
                'state': payment.state
            }

        elif payment.state == Payment.STATE_COMPLETED:
            return {
                'transaction': str(payment.id),
                'perform_time': int(payment.performed_at.timestamp() * 1000),
                'state': payment.state
            }

        else:
            return {
                'error': {
                    'code': -31008,
                    'message': {
                        'uz': 'Bajarib bo\'lmaydi',
                        'ru': 'Невозможно выполнить',
                        'en': 'Cannot perform'
                    }
                }
            }

    except Payment.DoesNotExist:
        return {
            'error': {
                'code': -31003,
                'message': {
                    'uz': 'Tranzaksiya topilmadi',
                    'ru': 'Транзакция не найдена',
                    'en': 'Transaction not found'
                }
            }
        }


def cancel_transaction(params):
    """4. CancelTransaction - To'lovni bekor qilish"""
    payme_id = params.get('id')
    reason = params.get('reason')

    try:
        payment = Payment.objects.get(payme_transaction_id=payme_id)

        with db_transaction.atomic():
            if payment.state == Payment.STATE_CREATED:
                payment.state = Payment.STATE_CANCELLED

            elif payment.state == Payment.STATE_COMPLETED:
                payment.state = Payment.STATE_CANCELLED_AFTER_COMPLETE

                # Balansni qaytarish
                if payment.user.balance >= payment.pricing_count:
                    payment.user.balance -= payment.pricing_count
                    payment.user.save()

            payment.cancelled_at = timezone.now()
            payment.reason = reason
            payment.save()

        logger.info(f"Transaction cancelled: {payme_id}, reason={reason}")

        return {
            'transaction': str(payment.id),
            'cancel_time': int(payment.cancelled_at.timestamp() * 1000),
            'state': payment.state
        }

    except Payment.DoesNotExist:
        return {
            'error': {
                'code': -31003,
                'message': {
                    'uz': 'Tranzaksiya topilmadi',
                    'ru': 'Транзакция не найдена',
                    'en': 'Transaction not found'
                }
            }
        }


def check_transaction(params):
    """5. CheckTransaction - Tranzaksiya holatini tekshirish"""
    payme_id = params.get('id')

    try:
        payment = Payment.objects.get(payme_transaction_id=payme_id)

        result = {
            'create_time': int(payment.created_at.timestamp() * 1000),
            'transaction': str(payment.id),
            'state': payment.state
        }

        if payment.performed_at:
            result['perform_time'] = int(payment.performed_at.timestamp() * 1000)

        if payment.cancelled_at:
            result['cancel_time'] = int(payment.cancelled_at.timestamp() * 1000)

        if payment.reason:
            result['reason'] = payment.reason

        return result

    except Payment.DoesNotExist:
        return {
            'error': {
                'code': -31003,
                'message': {
                    'uz': 'Tranzaksiya topilmadi',
                    'ru': 'Транзакция не найдена',
                    'en': 'Transaction not found'
                }
            }
        }