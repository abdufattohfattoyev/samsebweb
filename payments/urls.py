# payments/urls.py - TO'LIQ KONFIGURATSIYA
from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # ============= BOT API ENDPOINTLAR =============

    # Tariflar
    path('tariffs/', views.get_tariffs, name='get_tariffs'),

    # Foydalanuvchi
    path('user/create/', views.create_user, name='create_user'),
    path('user/<int:telegram_id>/balance/', views.get_balance, name='get_balance'),
    path('user/update-phone/', views.update_phone, name='update_phone'),

    # Narxlash
    path('pricing/use/', views.use_pricing, name='use_pricing'),

    # To'lov yaratish va tekshirish
    path('payment/create/', views.create_payment, name='create_payment'),
    # payments/urls.py
    path('payment/status/<str:order_id>/', views.check_payment_status, name='check_payment_status'),

    # ============= PAYME MERCHANT API =============
    path('payme/callback/', views.payme_callback, name='payme_callback'),
]