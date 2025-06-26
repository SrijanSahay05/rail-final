from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    Wallet, Transaction, OTPVerification
)


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'balance', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['transaction_id', 'user', 'amount', 'transaction_type', 'purpose', 'status', 'created_at']
    list_filter = ['transaction_type', 'purpose', 'status', 'created_at']
    search_fields = ['transaction_id', 'user__username', 'description']
    readonly_fields = ['transaction_id', 'created_at', 'processed_at', 'completed_at']


@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'purpose', 'otp_code', 'is_verified', 'expires_at', 'created_at']
    list_filter = ['purpose', 'is_verified', 'created_at']
    search_fields = ['user__username', 'phone_number']
    readonly_fields = ['created_at', 'verified_at']