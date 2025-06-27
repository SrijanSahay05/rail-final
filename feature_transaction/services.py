from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
import random
import string

from .models import Wallet, Transaction, OTPVerification


class WalletService:

    @staticmethod
    @transaction.atomic
    def credit_wallet(user, amount, purpose='TOPUP', description='', otp_verification=None):
        try:
            wallet = user.wallet
            
            balance_before = wallet.balance
            
            txn = Transaction.objects.create(
                user=user,
                amount=amount,
                transaction_type='CREDIT',
                purpose=purpose,
                description=description,
                wallet_balance_before=balance_before,
                otp_verification=otp_verification,
                status='PROCESSING'
            )
            
            wallet.balance += amount
            wallet.save()
            
            txn.wallet_balance_after = wallet.balance
            txn.mark_completed()
            
            return {
                'success': True,
                'transaction': txn,
                'new_balance': wallet.balance,
                'message': f'Successfully credited ₹{amount} to wallet'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to credit wallet'
            }
    
    @staticmethod
    @transaction.atomic
    def debit_wallet(user, amount, purpose='PAYMENT', description='', otp_verification=None):
        try:
            wallet = user.wallet
            
            if wallet.balance < amount:
                return {
                    'success': False,
                    'error': 'Insufficient balance',
                    'message': f'Insufficient balance. Available: ₹{wallet.balance}, Required: ₹{amount}'
                }
            
            balance_before = wallet.balance
            
            txn = Transaction.objects.create(
                user=user,
                amount=amount,
                transaction_type='DEBIT',
                purpose=purpose,
                description=description,
                wallet_balance_before=balance_before,
                otp_verification=otp_verification,
                status='PROCESSING'
            )
            
            wallet.balance -= amount
            wallet.save()
            
            txn.wallet_balance_after = wallet.balance
            txn.mark_completed()
            
            return {
                'success': True,
                'transaction': txn,
                'new_balance': wallet.balance,
                'message': f'Successfully debited ₹{amount} from wallet'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to debit wallet'
            }

   #TODO add transaction.atomic in the end
    @staticmethod
    def get_wallet_balance(user):
        try:
            return {
                'success': True,
                'balance': user.wallet.balance,
                'wallet': user.wallet
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'balance': Decimal('0.00')
            }
    
    @staticmethod
    def get_transaction_history(user, limit=10):
        try:
            transactions = Transaction.objects.filter(user=user)[:limit]
            return {
                'success': True,
                'transactions': transactions,
                'count': transactions.count()
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'transactions': []
            }


class OTPService:
    @staticmethod
    def generate_otp():
        return ''.join(random.choices(string.digits, k=6))
    
    @staticmethod
    def send_otp(user, purpose, phone_number=None):

        try:
            if not phone_number:
                phone_number = getattr(user, 'phone_number', '') or '1234567890'
            
            otp_code = OTPService.generate_otp()
            
            expires_at = timezone.now() + timezone.timedelta(minutes=5)
            
            otp_verification = OTPVerification.objects.create(
                user=user,
                otp_code=otp_code,
                purpose=purpose,
                phone_number=phone_number,
                expires_at=expires_at
            )
            
            # TODO add sms service (have to learn this for other project)

            return {
                'success': True,
                'otp_verification': otp_verification,
                'otp_code': otp_code,  # TODO Remove this in production
                'message': f'OTP sent to {phone_number}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to send OTP'
            }
    
    @staticmethod
    def verify_otp(user, otp_code, purpose):

        try:
            otp_verification = OTPVerification.objects.filter(
                user=user,
                otp_code=otp_code,
                purpose=purpose,
                is_verified=False
            ).first()
            
            if not otp_verification:
                return {
                    'success': False,
                    'error': 'Invalid OTP',
                    'message': 'Invalid or expired OTP'
                }
            
            if otp_verification.is_expired():
                return {
                    'success': False,
                    'error': 'OTP expired',
                    'message': 'OTP has expired. Please request a new one.'
                }
            
            if otp_verification.verify():
                return {
                    'success': True,
                    'otp_verification': otp_verification,
                    'message': 'OTP verified successfully'
                }
            else:
                return {
                    'success': False,
                    'error': 'Verification failed',
                    'message': 'Failed to verify OTP'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'OTP verification failed'
            }


class TransactionService:

    @staticmethod
    def process_wallet_topup(user, amount, otp_code):
        try:
            otp_result = OTPService.verify_otp(user, otp_code, 'WALLET_TOPUP')
            if not otp_result['success']:
                return otp_result
            
            result = WalletService.credit_wallet(
                user=user,
                amount=amount,
                purpose='TOPUP',
                description=f'Wallet top-up of ₹{amount}',
                otp_verification=otp_result['otp_verification']
            )
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to process wallet top-up'
            }
    
    @staticmethod
    def process_payment(user, amount, description, otp_code):
        try:
            otp_result = OTPService.verify_otp(user, otp_code, 'PAYMENT')
            
            if not otp_result['success']:
                return otp_result
            
            result = WalletService.debit_wallet(
                user=user,
                amount=amount,
                purpose='PAYMENT',
                description=description,
                otp_verification=otp_result['otp_verification']
            )
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to process payment'
            }
    
    @staticmethod
    def process_refund(user, amount, description):
        try:
            result = WalletService.credit_wallet(
                user=user,
                amount=amount,
                purpose='REFUND',
                description=description
            )
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to process refund'
            }
