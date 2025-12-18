# payments/views.py - TO'G'RILANGAN VERSIYA
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
    To'lov havolasini yaratish (tarif asosida)
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

        # 2. To'lovni yaratish (lekin Payme ID bilan emas, chunki Payme to'lov paytidagina ID beradi)
        payment = Payment.objects.create(
            user=user,
            tariff=tariff,
            amount=tariff.price,
            pricing_count=tariff.count,
            state=Payment.STATE_CREATED
        )

        logger.info(f"Payment created for tariff: #{payment.id}, user: {telegram_id}, tariff: {tariff.name}")

        # 3. Payme havolasini yaratish (telegram_id bilan)
        payme_url = create_payme_link(
            telegram_id=telegram_id,
            amount=float(tariff.price)
        )

        if not payme_url:
            logger.error(f"Payme URL creation failed for telegram_id: {telegram_id}")
            return Response({
                'success': False,
                'error': 'Payme havolasi yaratishda xatolik'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
            'error': 'Tarif topilmadi yoki faol emas'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Create payment error: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def check_payment_status(request, telegram_id):
    """
    Oxirgi to'lov holatini tekshirish
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
            'created_at': payment.created_at.isoformat() if payment.created_at else None,
            'performed_at': payment.performed_at.isoformat() if payment.performed_at else None,
            'has_payment': True
        })
    except BotUser.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Foydalanuvchi topilmadi'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Check payment status error: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============= PAYME MERCHANT API - TO'G'RILANGAN =============

@csrf_exempt
@require_http_methods(["POST"])
def payme_callback(request):
    """
    Payme Merchant API callback - TO'G'RI JSONRPC 2.0 FORMATDA
    """
    logger.info(f"Payme callback received from {request.META.get('REMOTE_ADDR')}")

    # 1. Autentifikatsiyani tekshirish
    if not check_payme_auth(request):
        logger.warning("Payme: Authentication failed")
        return JsonResponse({
            'jsonrpc': '2.0',
            'error': {
                'code': -32504,
                'message': "Insufficient privilege"
            },
            'id': None
        })

    try:
        # 2. JSON ma'lumotlarni o'qish
        try:
            data = json.loads(request.body.decode('utf-8'))
        except:
            data = json.loads(request.body)

        method = data.get('method')
        params = data.get('params', {})
        request_id = data.get('id')

        logger.info(f"Payme request: id={request_id}, method={method}, params={params}")

        # 3. Metodni bajarish
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
        else:
            logger.error(f"Unknown Payme method: {method}")
            return JsonResponse({
                'jsonrpc': '2.0',
                'error': {
                    'code': -32601,
                    'message': 'Method not found'
                },
                'id': request_id
            })

        # 4. Natijani qaytarish
        if 'error' in result:
            logger.warning(f"Payme error response: {result['error']}")
            return JsonResponse({
                'jsonrpc': '2.0',
                'error': result['error'],
                'id': request_id
            })
        else:
            logger.info(f"Payme success response: {result}")
            return JsonResponse({
                'jsonrpc': '2.0',
                'result': result,
                'id': request_id
            })

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return JsonResponse({
            'jsonrpc': '2.0',
            'error': {
                'code': -32700,
                'message': 'Parse error'
            },
            'id': None
        })
    except Exception as e:
        logger.error(f"Payme callback error: {e}", exc_info=True)
        return JsonResponse({
            'jsonrpc': '2.0',
            'error': {
                'code': -32400,
                'message': 'System error'
            },
            'id': None
        })


def check_perform_transaction(params):
    """To'lov mumkinligini tekshirish"""
    try:
        amount = params.get('amount')
        account = params.get('account', {})
        telegram_id = account.get('telegram_id')

        logger.info(f"CheckPerformTransaction: telegram_id={telegram_id}, amount={amount}")

        if not telegram_id:
            return {
                'error': {
                    'code': -31050,
                    'message': 'telegram_id not found'
                }
            }

        try:
            telegram_id_int = int(telegram_id)
        except ValueError:
            return {
                'error': {
                    'code': -31050,
                    'message': 'Invalid telegram_id'
                }
            }

        # Foydalanuvchini tekshirish
        try:
            BotUser.objects.get(telegram_id=telegram_id_int)
        except BotUser.DoesNotExist:
            logger.warning(f"User not found: {telegram_id_int}")
            return {
                'error': {
                    'code': -31050,
                    'message': 'User not found'
                }
            }

        # Minimal summa tekshiruvi (5000 so'm = 500000 tiyin)
        min_amount_tiyin = 500000

        if amount < min_amount_tiyin:
            return {
                'error': {
                    'code': -31001,
                    'message': f'Minimal summa {min_amount_tiyin / 100} so\'m'
                }
            }

        logger.info(f"CheckPerformTransaction successful for user {telegram_id_int}")

        # Muvaffaqiyatli javob
        return {
            'allow': True,
            'detail': {
                'receipt_type': 0,
                'items': [{
                    'title': 'iPhone narxlash',
                    'price': amount,
                    'count': 1.0,
                    'code': 'iphone_pricing',
                    'vat_percent': 0
                }]
            }
        }

    except Exception as e:
        logger.error(f"CheckPerformTransaction error: {e}", exc_info=True)
        return {
            'error': {
                'code': -31008,
                'message': str(e)[:100]
            }
        }


def create_transaction(params):
    """Tranzaksiya yaratish"""
    try:
        payme_id = params.get('id')
        amount = params.get('amount')
        time = params.get('time')
        account = params.get('account', {})
        telegram_id = account.get('telegram_id')

        logger.info(f"CreateTransaction: payme_id={payme_id}, telegram_id={telegram_id}, amount={amount}")

        # Parametrlarni tekshirish
        if not all([payme_id, amount, telegram_id]):
            return {
                'error': {
                    'code': -31008,
                    'message': 'Missing required parameters'
                }
            }

        try:
            telegram_id_int = int(telegram_id)
        except ValueError:
            return {
                'error': {
                    'code': -31050,
                    'message': 'Invalid telegram_id'
                }
            }

        # Foydalanuvchini topish
        try:
            user = BotUser.objects.get(telegram_id=telegram_id_int)
        except BotUser.DoesNotExist:
            logger.warning(f"User not found in CreateTransaction: {telegram_id_int}")
            return {
                'error': {
                    'code': -31050,
                    'message': 'User not found'
                }
            }

        # Mavjud tranzaksiyani tekshirish
        existing = Payment.objects.filter(payme_transaction_id=payme_id).first()
        if existing:
            logger.info(f"Transaction already exists: {payme_id} -> Payment #{existing.id}")
            return {
                'create_time': int(existing.created_at.timestamp() * 1000),
                'transaction': str(existing.id),
                'state': existing.state
            }

        # YANGI TRANZAKSIYA YARATISH
        amount_sum = tiyin_to_sum(amount)  # Tiyindan so'mga

        # Pricing count ni hisoblash (5000 so'm = 1 ta narxlash)
        pricing_count = max(1, int(amount_sum / 5000))

        with db_transaction.atomic():
            # Tarifni topish yoki yo'qligini tekshirish
            # Summa asosida mos keladigan tarifni topish
            tariff = None
            try:
                # 5000 so'm = 1 ta narxlash tarifini topish
                tariff = PricingTariff.objects.filter(
                    price=amount_sum,
                    is_active=True
                ).first()

                if not tariff:
                    # Eng yaqin tarifni topish
                    tariff = PricingTariff.objects.filter(
                        is_active=True
                    ).order_by('price').first()
            except Exception as e:
                logger.warning(f"Tariff not found, using default: {e}")

            # To'lovni yaratish
            payment = Payment.objects.create(
                user=user,
                tariff=tariff,
                amount=amount_sum,
                pricing_count=pricing_count,
                payme_transaction_id=payme_id,
                state=Payment.STATE_CREATED
            )

            logger.info(
                f"Transaction created: {payme_id} -> Payment #{payment.id}, amount: {amount_sum} sum, count: {pricing_count}")

        create_time = int(payment.created_at.timestamp() * 1000)

        return {
            'create_time': create_time,
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

                logger.info(f"Payment completed: #{payment.id}, user: {user.telegram_id}, "
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


# payments/views.py ga qo'shimcha funksiya (agar kerak bo'lsa)
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