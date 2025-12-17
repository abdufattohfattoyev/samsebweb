# payments/urls.py
from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Bot uchun API
    path('tariffs/', views.get_tariffs, name='tariffs'),
    path('user/create/', views.create_user, name='create_user'),
    path('user/<int:telegram_id>/balance/', views.get_balance, name='balance'),
    path('pricing/use/', views.use_pricing, name='use_pricing'),
    path('payment/create/', views.create_payment, name='create_payment'),

    # Payme callback (Payme serveridan)
    path('payme/callback/', views.payme_callback, name='payme_callback'),
]