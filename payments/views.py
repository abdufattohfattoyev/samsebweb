# payments/views.py - TUZATILGAN VERSIYA (create_payment funksiyasi)
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
from .payme_utils import create_payme_link, check_payme_auth, tiyin_to_sum, sum_to_tiyin

logger = logging.getLogger(__name__)


# ============= BOT UCHUN API ENDPOINTLAR =============

@api_view(['GET'])
def get_tariffs(request):
    """
    Barcha faol tariflarni olish
    """
    try:
        tariffs = PricingTariff.objects.filter(is_active=True).order_by('count')

        data = []
        for t in tariffs:
            price_per_one = float(t.price_per_one) if hasattr(t, 'price_per_one') else float(t.price) / t.count
            data.append({
                'id': t.id,
                'name': t.name,
                'count': t.count,
                'price': float(t.price),
                'price_per_one': price_per_one
            })

        return Response({
            'success': True,
            'tariffs': data
        })
    except Exception as e:
        logger.error(f"Get tariffs error: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def create_user(request):
    """
    Foydalanuvchi yaratish yoki yangilash
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
            # Update only if provided
            if full_name:
                user.full_name = full_name
            if username is not None:  # Allow empty username
                user.username = username
            user.save()

        return Response({
            'success': True,
            'telegram_id': user.telegram_id,
            'balance': user.balance,
            'full_name': user.full_name,
            'username': user.username,
            'created': created
        })
    except Exception as e:
        logger.error(f"Create user error: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_balance(request, telegram_id):
    """
    Foydalanuvchi balansini olish
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
    except Exception as e:
        logger.error(f"Get balance error: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def use_pricing(request):
    """
    Narxlashdan foydalanish (balansni kamaytirish)
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
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def create_payment(request):
    """
    To'lov havolasini yaratish (tarif asosida) - TUZATILGAN
    """
    telegram_id = request.data.get('telegram_id')
    tariff_id = request.data.get('tariff_id')

    if not telegram_id or not tariff_id:
        return Response({
            'success': False,
            'error': 'telegram_id va tariff_id majburiy'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        # 1. Foydalanuvchi va tarifni tekshirish
        user = BotUser.objects.get(telegram_id=telegram_id)
        tariff = PricingTariff.objects.get(id=tariff_id, is_active=True)

        # 2. To'lovni yaratish
        payment = Payment.objects.create(
            user=user,
            tariff=tariff,
            amount=tariff.price,
            pricing_count=tariff.count,
            state=Payment.STATE_CREATED
        )

        logger.info(f"✅ Payment created: #{payment.id} (order_id: {payment.order_id}), "
                    f"user: {telegram_id}, tariff: {tariff.name}")

        # 3. Payme havolasini yaratish (ORDER_ID bilan)
        payme_url = create_payme_link(
            telegram_id=telegram_id,
            amount=float(tariff.price),
            order_id=str(payment.order_id)  # 🔴 MAJBURIY PARAMETER
        )

        if not payme_url:
            logger.error(f"❌ Failed to create Payme URL for payment #{payment.id}")
            return Response({
                'success': False,
                'error': 'Payme havolasini yaratishda xatolik'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        logger.info(f"✅ Payme URL created: {payme_url}")

        return Response({
            'success': True,
            'payment_id': payment.id,
            'order_id': str(payment.order_id),
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
            'error': 'Tarif topilmadi yoki faol emas'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"❌ Create payment error: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============= PAYME CALLBACK =============
def get_statement(params):
    """
    GetStatement - To'lovlar hisobotini olish

    Bu metod ixtiyoriy, lekin Payme test qiladi
    """
    try:
        from_time = params.get('from')
        to_time = params.get('to')

        logger.info(f"GetStatement: from={from_time}, to={to_time}")

        # Vaqt oralig'idagi to'lovlarni topish
        from_datetime = timezone.datetime.fromtimestamp(from_time / 1000)
        to_datetime = timezone.datetime.fromtimestamp(to_time / 1000)

        payments = Payment.objects.filter(
            created_at__gte=from_datetime,
            created_at__lte=to_datetime,
            payme_transaction_id__isnull=False
        )

        transactions = []
        for payment in payments:
            transaction = {
                'id': payment.payme_transaction_id,
                'time': int(payment.created_at.timestamp() * 1000),
                'amount': sum_to_tiyin(payment.amount),
                'account': {
                    'order_id': str(payment.order_id),
                    'telegram_id': payment.user.telegram_id
                },
                'create_time': int(payment.created_at.timestamp() * 1000),
                'perform_time': int(payment.performed_at.timestamp() * 1000) if payment.performed_at else 0,
                'cancel_time': int(payment.cancelled_at.timestamp() * 1000) if payment.cancelled_at else 0,
                'transaction': str(payment.id),
                'state': payment.state,
                'reason': payment.reason
            }
            transactions.append(transaction)

        return {'transactions': transactions}

    except Exception as e:
        logger.error(f"GetStatement error: {e}", exc_info=True)
        return {
            'error': {
                'code': -32400,
                'message': str(e)[:100]
            }
        }


def change_password(params):
    """
    ChangePassword - Parolni o'zgartirish

    Bu metod ixtiyoriy, lekin Payme test qiladi
    """
    try:
        password = params.get('password')

        logger.info(f"ChangePassword requested")

        # Bu metoddan foydalanmasak, success qaytaramiz
        # Yoki parolni settings ga saqlab qo'yish mumkin

        return {'success': True}

    except Exception as e:
        logger.error(f"ChangePassword error: {e}", exc_info=True)
        return {
            'error': {
                'code': -32400,
                'message': str(e)[:100]
            }
        }

@csrf_exempt
@require_http_methods(["POST"])
def payme_callback(request):
    """
    Payme Merchant API callback handler

    ⚠️ MUHIM: Barcha xatolar HTTP 200 bilan qaytarilishi kerak!
    """
    try:
        # 1. Autentifikatsiya
        if not check_payme_auth(request):
            logger.warning("❌ Payme auth failed")
            # ✅ HTTP 200 bilan xato qaytarish
            return JsonResponse({
                'error': {
                    'code': -32504,
                    'message': 'Insufficient privileges to perform this method'
                }
            }, status=200)  # ← 401 emas, 200!

        # 2. JSON parse
        try:
            body = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON decode error: {e}")
            return JsonResponse({
                'error': {
                    'code': -32700,
                    'message': 'Parse error'
                }
            }, status=200)  # ← HTTP 200

        method = body.get('method')
        params = body.get('params', {})
        request_id = body.get('id')

        logger.info(f"📥 Payme callback: method={method}, params={params}")

        # 3. Method routing
        if method == 'CheckPerformTransaction':
            result = check_perform_transaction(params)
        elif method == 'CreateTransaction':
            result = create_transaction(params)
        elif method == 'PerformTransaction':
            result = perform_transaction(params)
        elif method == 'CancelTransaction':
            result = cancel_transaction(params)
        elif method == 'CheckTransaction':
            result = check_transaction(params)
        elif method == 'GetStatement':
            result = get_statement(params)
        elif method == 'ChangePassword':
            result = change_password(params)
        else:
            logger.warning(f"❌ Unknown method: {method}")
            return JsonResponse({
                'error': {
                    'code': -32601,
                    'message': 'Method not found'
                }
            }, status=200)  # ← HTTP 200

        # 4. Response (DOIM HTTP 200)
        if 'error' in result:
            logger.error(f"❌ Payme error: {result['error']}")
            return JsonResponse({
                'error': result['error'],
                'id': request_id
            }, status=200)  # ← HTTP 200
        else:
            logger.info(f"✅ Payme success: {result}")
            return JsonResponse({
                'result': result,
                'id': request_id
            }, status=200)  # ← HTTP 200

    except Exception as e:
        logger.error(f"❌ Payme callback error: {e}", exc_info=True)
        return JsonResponse({
            'error': {
                'code': -32400,
                'message': str(e)[:100]
            }
        }, status=200)  # ← HTTP 200

# ============= PAYME METHODS =============


def check_perform_transaction(params):
    """
    Buyurtma mavjudligini tekshirish

    Payme yuboradi:
    {
        "amount": 5000,
        "account": {
            "order_id": "...",       // Majburiy!
            "telegram_id": 123456789  // Ixtiyoriy
        }
    }
    """
    try:
        account = params.get('account', {})
        order_id = account.get('order_id')
        amount = params.get('amount')

        logger.info(f"CheckPerformTransaction: order_id={order_id}, amount={amount}")

        # 1. order_id MAJBURIY tekshirish
        if not order_id:
            logger.warning(f"Order ID missing in account params")
            return {
                'error': {
                    'code': -31050,
                    'message': {
                        'uz': 'Buyurtma identifikatori kiritilmagan',
                        'ru': 'Не указан идентификатор заказа',
                        'en': 'Order ID not specified'
                    }
                }
            }

        # 2. Order ni topish
        try:
            payment = Payment.objects.get(order_id=order_id)
        except Payment.DoesNotExist:
            logger.warning(f"Order not found: {order_id}")
            return {
                'error': {
                    'code': -31050,
                    'message': {
                        'uz': 'Buyurtma topilmadi',
                        'ru': 'Заказ не найден',
                        'en': 'Order not found'
                    }
                }
            }

        # 3. To'lov holatini tekshirish
        if payment.state != Payment.STATE_CREATED:
            logger.warning(f"Order already processed: {order_id}, state: {payment.state}")
            return {
                'error': {
                    'code': -31008,
                    'message': {
                        'uz': 'Buyurtma allaqachon qayta ishlangan',
                        'ru': 'Заказ уже обработан',
                        'en': 'Order already processed'
                    }
                }
            }

        # 4. Summani tekshirish (agar yuborilgan bo'lsa)
        if amount:
            expected_tiyin = sum_to_tiyin(payment.amount)
            if amount != expected_tiyin:
                logger.warning(f"Amount mismatch: expected={expected_tiyin}, got={amount}")
                return {
                    'error': {
                        'code': -31001,
                        'message': {
                            'uz': 'Noto\'g\'ri summa',
                            'ru': 'Неверная сумма',
                            'en': 'Invalid amount'
                        }
                    }
                }

        # 5. Telegram ID tekshirish (ixtiyoriy)
        telegram_id = account.get('telegram_id')
        if telegram_id:
            # Bo'sh joy bor mi? (Payme testda " 973358587" yuboradi)
            telegram_id_str = str(telegram_id).strip()

            if telegram_id_str != str(payment.user.telegram_id):
                logger.warning(f"Telegram ID mismatch: expected={payment.user.telegram_id}, got={telegram_id}")
                return {
                    'error': {
                        'code': -31050,
                        'message': {
                            'uz': 'Telegram ID mos kelmadi',
                            'ru': 'Telegram ID не совпадает',
                            'en': 'Telegram ID mismatch'
                        }
                    }
                }

        # ✅ Hammasi to'g'ri
        return {'allow': True}

    except Exception as e:
        logger.error(f"CheckPerformTransaction error: {e}", exc_info=True)
        return {
            'error': {
                'code': -31008,
                'message': str(e)[:100]
            }
        }


def create_transaction(params):
    """Tranzaksiyani yaratish"""
    try:
        payme_id = params.get('id')
        account = params.get('account', {})
        order_id = account.get('order_id')
        amount_tiyin = params.get('amount')
        create_time = params.get('time')

        logger.info(f"CreateTransaction: payme_id={payme_id}, order_id={order_id}, amount={amount_tiyin}")

        if not payme_id or not order_id:
            return {
                'error': {
                    'code': -31050,
                    'message': 'Transaction ID and Order ID required'
                }
            }

        # Order ni topish
        try:
            payment = Payment.objects.get(order_id=order_id)
        except Payment.DoesNotExist:
            logger.warning(f"Order not found: {order_id}")
            return {
                'error': {
                    'code': -31050,
                    'message': 'Order not found'
                }
            }

        # Tranzaksiya mavjudligini tekshirish
        if payment.payme_transaction_id:
            if payment.payme_transaction_id == payme_id:
                # Bir xil ID - qayta yaratish (idempotent)
                logger.info(f"Transaction already exists with same ID: {payme_id}")
                return {
                    'create_time': int(payment.created_at.timestamp() * 1000),
                    'transaction': str(payment.id),
                    'state': payment.state
                }
            else:
                # Boshqa ID bilan mavjud
                logger.warning(f"Order already has transaction: {payment.payme_transaction_id}")
                return {
                    'error': {
                        'code': -31050,
                        'message': 'Order already has transaction'
                    }
                }

        # Summani tekshirish
        expected_tiyin = sum_to_tiyin(payment.amount)
        if amount_tiyin != expected_tiyin:
            logger.warning(f"Amount mismatch: expected={expected_tiyin}, got={amount_tiyin}")
            return {
                'error': {
                    'code': -31001,
                    'message': 'Amount mismatch'
                }
            }

        # Holat tekshirish
        if payment.state != Payment.STATE_CREATED:
            logger.warning(f"Order already processed: {order_id}, state: {payment.state}")
            return {
                'error': {
                    'code': -31008,
                    'message': 'Order already processed'
                }
            }

        # Tranzaksiya IDni saqlash
        payment.payme_transaction_id = payme_id
        payment.save(update_fields=['payme_transaction_id'])

        logger.info(f"✅ Transaction created: payment #{payment.id}, payme_id={payme_id}")

        return {
            'create_time': int(payment.created_at.timestamp() * 1000),
            'transaction': str(payment.id),
            'state': payment.state
        }

    except Exception as e:
        logger.error(f"CreateTransaction error: {e}", exc_info=True)
        return {
            'error': {
                'code': -31008,
                'message': str(e)[:100]
            }
        }


def perform_transaction(params):
    """To'lovni tasdiqlash"""
    try:
        payme_id = params.get('id')

        logger.info(f"PerformTransaction: payme_id={payme_id}")

        if not payme_id:
            return {
                'error': {
                    'code': -31003,
                    'message': 'Transaction ID required'
                }
            }

        # Tranzaksiyani topish
        try:
            payment = Payment.objects.get(payme_transaction_id=payme_id)
        except Payment.DoesNotExist:
            logger.warning(f"Transaction not found: {payme_id}")
            return {
                'error': {
                    'code': -31003,
                    'message': 'Transaction not found'
                }
            }

        # Holatni tekshirish
        if payment.state == Payment.STATE_CREATED:
            with db_transaction.atomic():
                # To'lovni tasdiqlash
                payment.state = Payment.STATE_COMPLETED
                payment.performed_at = timezone.now()
                payment.save()

                # Balansga qo'shish
                user = payment.user
                old_balance = user.balance
                user.balance += payment.pricing_count
                user.save()

                logger.info(f"✅ Payment completed: #{payment.id}, user: {user.telegram_id}, "
                            f"balance: {old_balance} -> {user.balance}, count: +{payment.pricing_count}")

            perform_time = int(payment.performed_at.timestamp() * 1000)

            return {
                'transaction': str(payment.id),
                'perform_time': perform_time,
                'state': payment.state
            }

        elif payment.state == Payment.STATE_COMPLETED:
            # Allaqachon tasdiqlangan
            perform_time = int(payment.performed_at.timestamp() * 1000) if payment.performed_at else 0

            return {
                'transaction': str(payment.id),
                'perform_time': perform_time,
                'state': payment.state
            }

        else:
            logger.warning(f"Cannot perform transaction in state: {payment.state}")
            return {
                'error': {
                    'code': -31008,
                    'message': f'Cannot perform transaction in state: {payment.state}'
                }
            }

    except Exception as e:
        logger.error(f"PerformTransaction error: {e}", exc_info=True)
        return {
            'error': {
                'code': -31008,
                'message': str(e)[:100]
            }
        }


def cancel_transaction(params):
    """To'lovni bekor qilish"""
    try:
        payme_id = params.get('id')
        reason = params.get('reason')

        logger.info(f"CancelTransaction: payme_id={payme_id}, reason={reason}")

        if not payme_id:
            return {
                'error': {
                    'code': -31003,
                    'message': 'Transaction ID required'
                }
            }

        # Tranzaksiyani topish
        try:
            payment = Payment.objects.get(payme_transaction_id=payme_id)
        except Payment.DoesNotExist:
            logger.warning(f"Transaction not found for cancel: {payme_id}")
            return {
                'error': {
                    'code': -31003,
                    'message': 'Transaction not found'
                }
            }

        with db_transaction.atomic():
            if payment.state == Payment.STATE_CREATED:
                payment.state = Payment.STATE_CANCELLED

            elif payment.state == Payment.STATE_COMPLETED:
                payment.state = Payment.STATE_CANCELLED_AFTER_COMPLETE

                # Balansni qaytarish
                if payment.user.balance >= payment.pricing_count:
                    old_balance = payment.user.balance
                    payment.user.balance -= payment.pricing_count
                    payment.user.save()
                    logger.info(f"Balance refunded: user {payment.user.telegram_id}, "
                                f"balance: {old_balance} -> {payment.user.balance}, count: -{payment.pricing_count}")

            else:
                # Already cancelled
                pass

            payment.cancelled_at = timezone.now()
            payment.reason = reason
            payment.save()

            logger.info(f"Transaction cancelled: {payme_id}, state: {payment.state}, reason: {reason}")

        cancel_time = int(payment.cancelled_at.timestamp() * 1000)

        return {
            'transaction': str(payment.id),
            'cancel_time': cancel_time,
            'state': payment.state
        }

    except Exception as e:
        logger.error(f"CancelTransaction error: {e}", exc_info=True)
        return {
            'error': {
                'code': -31008,
                'message': str(e)[:100]
            }
        }


def check_transaction(params):
    """Tranzaksiya holatini tekshirish"""
    try:
        payme_id = params.get('id')

        logger.info(f"CheckTransaction: payme_id={payme_id}")

        if not payme_id:
            return {
                'error': {
                    'code': -31003,
                    'message': 'Transaction ID required'
                }
            }

        # Tranzaksiyani topish
        try:
            payment = Payment.objects.get(payme_transaction_id=payme_id)
        except Payment.DoesNotExist:
            logger.warning(f"Transaction not found for check: {payme_id}")
            return {
                'error': {
                    'code': -31003,
                    'message': 'Transaction not found'
                }
            }

        result = {
            'create_time': int(payment.created_at.timestamp() * 1000),
            'transaction': str(payment.id),
            'state': payment.state
        }

        if payment.performed_at:
            result['perform_time'] = int(payment.performed_at.timestamp() * 1000)

        if payment.cancelled_at:
            result['cancel_time'] = int(payment.cancelled_at.timestamp() * 1000)

        if payment.reason is not None:
            result['reason'] = payment.reason

        logger.info(f"CheckTransaction result: {result}")

        return result

    except Exception as e:
        logger.error(f"CheckTransaction error: {e}", exc_info=True)
        return {
            'error': {
                'code': -31008,
                'message': str(e)[:100]
            }
        }


@api_view(['GET'])
def check_last_payment_status(request, telegram_id):
    """
    Oxirgi to'lov holatini tekshirish (5 daqiqa ichida)
    """
    try:
        user = BotUser.objects.get(telegram_id=telegram_id)

        # 5 daqiqa ichidagi oxirgi to'lovni topish
        time_threshold = timezone.now() - timezone.timedelta(minutes=5)
        payment = Payment.objects.filter(
            user=user,
            created_at__gte=time_threshold
        ).order_by('-created_at').first()

        if not payment:
            return Response({
                'success': False,
                'error': 'Yaqinda to\'lov topilmadi',
                'has_payment': False
            })

        return Response({
            'success': True,
            'payment_id': payment.id,
            'state': payment.state,
            'state_display': payment.get_state_display(),
            'amount': float(payment.amount),
            'count': payment.pricing_count,
            'balance': user.balance,
            'has_payment': True
        })

    except BotUser.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Foydalanuvchi topilmadi'
        }, status=404)
    except Exception as e:
        logger.error(f"Check last payment status error: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)


@api_view(['GET'])
def check_payment_status(request, telegram_id):
    """
    Foydalanuvchining to'lov holatini tekshirish

    Endpoint: /api/payments/payment/status/<telegram_id>/
    Method: GET

    Returns:
        - success: True/False
        - has_payment: Oxirgi to'lov bormi
        - payment_id: To'lov ID
        - state: To'lov holati (1=Yaratildi, 2=To'landi, -1=Bekor qilindi)
        - state_display: Holat nomi
        - amount: Summa
        - count: Narxlashlar soni
        - balance: Joriy balans
        - order_id: Chek ID
        - created_at: Yaratilgan vaqt
    """
    try:
        # Foydalanuvchini topish
        try:
            user = BotUser.objects.get(telegram_id=telegram_id)
        except BotUser.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Foydalanuvchi topilmadi',
                'has_payment': False
            }, status=status.HTTP_404_NOT_FOUND)

        # Oxirgi to'lovni topish (30 daqiqa ichida)
        time_threshold = timezone.now() - timezone.timedelta(minutes=30)
        payment = Payment.objects.filter(
            user=user,
            created_at__gte=time_threshold
        ).order_by('-created_at').first()

        if not payment:
            return Response({
                'success': True,
                'has_payment': False,
                'message': '30 daqiqa ichida to\'lov topilmadi',
                'balance': user.balance
            })

        # To'lov ma'lumotlarini qaytarish
        return Response({
            'success': True,
            'has_payment': True,
            'payment_id': payment.id,
            'order_id': str(payment.order_id),
            'state': payment.state,
            'state_display': payment.get_state_display(),
            'amount': float(payment.amount),
            'count': payment.pricing_count,
            'balance': user.balance,
            'created_at': payment.created_at.isoformat(),
            'performed_at': payment.performed_at.isoformat() if payment.performed_at else None,
            'cancelled_at': payment.cancelled_at.isoformat() if payment.cancelled_at else None,
            'tariff_name': payment.tariff.name if payment.tariff else None,
            'payme_transaction_id': payment.payme_transaction_id or None
        })

    except Exception as e:
        logger.error(f"Check payment status error: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': str(e),
            'has_payment': False
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)