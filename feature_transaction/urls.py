from django.urls import path
from . import views

app_name = 'feature_transaction'

urlpatterns = [
    # Main wallet views
    path('', views.wallet_dashboard, name='wallet_dashboard'),
    path('topup/', views.topup_wallet, name='topup_wallet'),
    path('history/', views.transaction_history, name='transaction_history'),
    
    # Payment views
    path('payment/<str:booking_id>/', views.payment_page, name='payment_page'),
    path('payment-success/<str:transaction_id>/', views.payment_success, name='payment_success'),
    
    # API endpoints
    path('api/balance/', views.wallet_api_balance, name='wallet_api_balance'),
    path('api/send-otp/', views.send_otp, name='send_otp'),
    path('api/verify-otp/', views.verify_otp, name='verify_otp'),
    path('api/process-payment/', views.process_payment, name='process_payment'),
]
