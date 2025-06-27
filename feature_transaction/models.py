from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
import uuid

from core_users.models import CustomUser


class OTPVerification(models.Model):
    """
    OTP verification for all wallet transactions
    """
    OTP_PURPOSE_CHOICES = [
        ('WALLET_TOPUP', 'Wallet Top-up'),
        ('PAYMENT', 'Payment'),
        ('REFUND', 'Refund'),
        ('TRANSFER', 'Transfer'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='otp_verifications')
    otp_code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, choices=OTP_PURPOSE_CHOICES)
    phone_number = models.CharField(max_length=15)
    
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_verified']),
            models.Index(fields=['otp_code', 'expires_at']),
        ]
    
    def __str__(self):
        return f"OTP for {self.user.username} - {self.purpose}"
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def verify(self):
        if not self.is_expired():
            self.is_verified = True
            self.verified_at = timezone.now()
            self.save()
            return True
        return False


class Wallet(models.Model):

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                check=models.Q(balance__gte=0),
                name='wallet_balance_non_negative'
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['balance']),
        ]
    
    def __str__(self):
        return f"Wallet for {self.user.username} - Balance: ₹{self.balance}"
    
    def clean(self):
        if self.balance < 0:
            raise ValidationError("Wallet balance cannot be negative")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class Transaction(models.Model):

    TRANSACTION_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    TRANSACTION_TYPE_CHOICES = [
        ('CREDIT', 'Credit'),
        ('DEBIT', 'Debit'),
    ]
    
    TRANSACTION_PURPOSE_CHOICES = [
        ('TOPUP', 'Wallet Top-up'),
        ('PAYMENT', 'Payment'),
        ('REFUND', 'Refund'),
        ('TRANSFER', 'Transfer'),
    ]
    
    transaction_id = models.CharField(max_length=50, unique=True, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='transactions')
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    purpose = models.CharField(max_length=20, choices=TRANSACTION_PURPOSE_CHOICES)
    status = models.CharField(max_length=20, choices=TRANSACTION_STATUS_CHOICES, default='PENDING')
    
    # TODO : Rahul Mausaji asked to add this for better record maintaince of user balance after every transaction
    wallet_balance_before = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    wallet_balance_after = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    description = models.TextField(blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    booking_id = models.CharField(max_length=20, blank=True)
    
    otp_verification = models.ForeignKey(OTPVerification, on_delete=models.SET_NULL, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gt=0),
                name='transaction_amount_positive'
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['transaction_type', 'purpose']),
        ]
    
    def __str__(self):
        return f"Transaction {self.transaction_id} - {self.user.username} - ₹{self.amount}"
    
    def save(self, *args, **kwargs):
        if not self.transaction_id:
            self.transaction_id = f"TXN{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)
    
    def mark_processing(self):
        """Mark transaction as processing"""
        self.status = 'PROCESSING'
        self.processed_at = timezone.now()
        self.save()
    
    def mark_completed(self):
        """Mark transaction as completed"""
        self.status = 'COMPLETED'
        self.completed_at = timezone.now()
        self.save()
    
    def mark_failed(self, reason=None):
        """Mark transaction as failed"""
        self.status = 'FAILED'
        if reason:
            self.description = f"{self.description}\nFailure reason: {reason}"
        self.save()

#TODO shift to feature_transaction.signals
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=CustomUser)
def create_user_wallet(sender, instance, created, **kwargs):
    if created:
        Wallet.objects.create(
            user=instance, 
            balance=Decimal('0.00'),
            is_active=True
        )
