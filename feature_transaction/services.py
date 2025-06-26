from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
import random
import string

from .models import Wallet, Transaction, OTPVerification


class WalletService:
    """Service class for wallet operations"""
    
    @staticmethod
    @transaction.atomic
    def credit_wallet(user, amount, purpose='TOPUP', description='', otp_verification=None):
        """
        Credit amount to user's wallet
        
        Args:
            user: User instance
            amount: Amount to credit
            purpose: Purpose of transaction
            description: Optional description
            otp_verification: OTP verification instance
            
        Returns:
            dict: Result with transaction details
        """
        try:
            wallet = user.wallet
            
            # Record balance before transaction
            balance_before = wallet.balance
            
            # Create transaction record
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
            
            # Update wallet balance
            wallet.balance += amount
            wallet.save()
            
            # Update transaction with new balance
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
        """
        Debit amount from user's wallet
        
        Args:
            user: User instance
            amount: Amount to debit
            purpose: Purpose of transaction
            description: Optional description
            otp_verification: OTP verification instance
            
        Returns:
            dict: Result with transaction details
        """
        try:
            wallet = user.wallet
            
            # Check sufficient balance
            if wallet.balance < amount:
                return {
                    'success': False,
                    'error': 'Insufficient balance',
                    'message': f'Insufficient balance. Available: ₹{wallet.balance}, Required: ₹{amount}'
                }
            
            # Record balance before transaction
            balance_before = wallet.balance
            
            # Create transaction record
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
            
            # Update wallet balance
            wallet.balance -= amount
            wallet.save()
            
            # Update transaction with new balance
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
    
    @staticmethod
    def get_wallet_balance(user):
        """Get current wallet balance"""
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
        """Get user's transaction history"""
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
    """Service class for OTP operations"""
    
    @staticmethod
    def generate_otp():
        """Generate 6-digit OTP"""
        return ''.join(random.choices(string.digits, k=6))
    
    @staticmethod
    def send_otp(user, purpose, phone_number=None):
        """
        Generate and send OTP to user
        
        Args:
            user: User instance
            purpose: Purpose of OTP
            phone_number: Phone number to send OTP (optional)
            
        Returns:
            dict: Result with OTP details
        """
        try:
            # Use user's phone number if not provided
            if not phone_number:
                phone_number = getattr(user, 'phone_number', '') or '1234567890'
            
            # Generate OTP
            otp_code = OTPService.generate_otp()
            
            # Create expiry time (5 minutes from now)
            expires_at = timezone.now() + timezone.timedelta(minutes=5)
            
            # Create OTP verification record
            otp_verification = OTPVerification.objects.create(
                user=user,
                otp_code=otp_code,
                purpose=purpose,
                phone_number=phone_number,
                expires_at=expires_at
            )
            
            # In a real implementation, you would send SMS here
            # For now, we'll just return the OTP for testing
            
            return {
                'success': True,
                'otp_verification': otp_verification,
                'otp_code': otp_code,  # Remove this in production
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
        """
        Verify OTP for user
        
        Args:
            user: User instance
            otp_code: OTP code to verify
            purpose: Purpose of OTP verification
            
        Returns:
            dict: Verification result
        """
        try:
            # Find matching OTP verification
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
            
            # Verify OTP
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
    """Service class for transaction operations"""
    
    @staticmethod
    def process_wallet_topup(user, amount, otp_code):
        """
        Process wallet top-up with OTP verification
        
        Args:
            user: User instance
            amount: Amount to add to wallet
            otp_code: OTP code for verification
            
        Returns:
            dict: Transaction result
        """
        try:
            # Verify OTP
            otp_result = OTPService.verify_otp(user, otp_code, 'WALLET_TOPUP')
            
            if not otp_result['success']:
                return otp_result
            
            # Credit wallet
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
        """
        Process payment with OTP verification
        
        Args:
            user: User instance
            amount: Amount to debit
            description: Payment description
            otp_code: OTP code for verification
            
        Returns:
            dict: Transaction result
        """
        try:
            # Verify OTP
            otp_result = OTPService.verify_otp(user, otp_code, 'PAYMENT')
            
            if not otp_result['success']:
                return otp_result
            
            # Debit wallet
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
        """
        Process refund (no OTP required for refunds)
        
        Args:
            user: User instance
            amount: Amount to refund
            description: Refund description
            
        Returns:
            dict: Transaction result
        """
        try:
            # Credit wallet
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
