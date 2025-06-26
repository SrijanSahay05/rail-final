from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from decimal import Decimal
import json

from .models import Wallet, Transaction, OTPVerification
from .services import WalletService, OTPService, TransactionService


@login_required
def wallet_dashboard(request):
    """Wallet dashboard view"""
    wallet_info = WalletService.get_wallet_balance(request.user)
    transaction_history = WalletService.get_transaction_history(request.user, limit=10)
    
    context = {
        'wallet': wallet_info.get('wallet'),
        'balance': wallet_info.get('balance', Decimal('0.00')),
        'transactions': transaction_history.get('transactions', [])
    }
    
    return render(request, 'feature_transaction/wallet_dashboard.html', context)


@login_required
def topup_wallet(request):
    """Wallet top-up view"""
    if request.method == 'POST':
        amount = request.POST.get('amount')
        otp_code = request.POST.get('otp_code')
        
        if not amount:
            messages.error(request, 'Amount is required')
            return render(request, 'feature_transaction/topup_wallet.html')
        
        try:
            amount = Decimal(amount)
            if amount <= 0:
                messages.error(request, 'Amount must be positive')
                return render(request, 'feature_transaction/topup_wallet.html')
            
            if amount > Decimal('10000.00'):
                messages.error(request, 'Maximum top-up amount is ₹10,000')
                return render(request, 'feature_transaction/topup_wallet.html')
            
            if otp_code:
                # Process with OTP
                result = TransactionService.process_wallet_topup(request.user, amount, otp_code)
                
                if result['success']:
                    messages.success(request, result['message'])
                    return redirect('wallet_dashboard')
                else:
                    messages.error(request, result['message'])
            else:
                # Send OTP first
                otp_result = OTPService.send_otp(request.user, 'WALLET_TOPUP')
                
                if otp_result['success']:
                    messages.info(request, f"OTP sent to your phone. OTP: {otp_result['otp_code']}")  # Remove in production
                    return render(request, 'feature_transaction/topup_wallet.html', {
                        'amount': amount,
                        'otp_sent': True
                    })
                else:
                    messages.error(request, otp_result['message'])
                    
        except ValueError:
            messages.error(request, 'Invalid amount format')
    
    return render(request, 'feature_transaction/topup_wallet.html')


@login_required
def transaction_history(request):
    """Transaction history view with pagination"""
    from django.core.paginator import Paginator
    
    transaction_type = request.GET.get('type', None)
    
    transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')
    
    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)
    
    paginator = Paginator(transactions, 20)  # Show 20 transactions per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'transaction_type': transaction_type,
    }
    
    return render(request, 'feature_transaction/transaction_history.html', context)


@login_required
@require_POST
def send_otp(request):
    """AJAX endpoint to send OTP"""
    try:
        data = json.loads(request.body)
        purpose = data.get('purpose')
        
        if purpose not in ['WALLET_TOPUP', 'PAYMENT', 'REFUND', 'TRANSFER']:
            return JsonResponse({
                'success': False,
                'message': 'Invalid OTP purpose'
            })
        
        result = OTPService.send_otp(request.user, purpose)
        
        # For testing, include OTP in response (remove in production)
        if result['success']:
            result['otp_code'] = result.get('otp_code')
        
        return JsonResponse(result)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@login_required
@require_POST
def verify_otp(request):
    """AJAX endpoint to verify OTP"""
    try:
        data = json.loads(request.body)
        otp_code = data.get('otp_code')
        purpose = data.get('purpose')
        
        if not otp_code or not purpose:
            return JsonResponse({
                'success': False,
                'message': 'OTP code and purpose are required'
            })
        
        result = OTPService.verify_otp(request.user, otp_code, purpose)
        return JsonResponse(result)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@login_required
def wallet_api_balance(request):
    """API endpoint to get wallet balance"""
    wallet_info = WalletService.get_wallet_balance(request.user)
    
    return JsonResponse({
        'success': wallet_info['success'],
        'balance': str(wallet_info['balance']),
        'formatted_balance': f"₹{wallet_info['balance']}"
    })


@login_required
@require_POST
def process_payment(request):
    """Process payment from wallet"""
    try:
        data = json.loads(request.body)
        amount = Decimal(data.get('amount', '0'))
        description = data.get('description', '')
        otp_code = data.get('otp_code')
        
        if amount <= 0:
            return JsonResponse({
                'success': False,
                'message': 'Invalid amount'
            })
        
        if not otp_code:
            return JsonResponse({
                'success': False,
                'message': 'OTP is required'
            })
        
        result = WalletService.debit_wallet(
            user=request.user, 
            amount=amount, 
            purpose='PAYMENT',
            description=description
        )
        
        if result['success']:
            result['new_balance'] = str(result['new_balance'])
        
        return JsonResponse(result)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@login_required
def payment_page(request, booking_id):
    """Payment page for booking"""
    from feature_railways.models import Booking
    
    booking = get_object_or_404(Booking, booking_id=booking_id, user=request.user)
    
    if booking.booking_status == 'CONFIRMED':
        messages.info(request, 'This booking is already paid')
        return redirect('feature_railways:booking_detail', booking_id=booking.booking_id)
    
    wallet_info = WalletService.get_wallet_balance(request.user)
    wallet_balance = wallet_info.get('balance', Decimal('0.00'))
    can_pay = wallet_balance >= booking.total_fare
    
    if request.method == 'POST':
        if not can_pay:
            messages.error(request, 'Insufficient wallet balance')
            return redirect('feature_transaction:topup_wallet')
        
        # Process payment using simplified flow
        result = WalletService.debit_wallet(
            user=request.user,
            amount=booking.total_fare,
            purpose='PAYMENT',
            description=f'Payment for booking {booking.booking_id}'
        )
        
        if result['success']:
            booking.booking_status = 'CONFIRMED'
            booking.save()
            messages.success(request, 'Payment successful! Your booking is confirmed.')
            return redirect('feature_railways:booking_detail', booking_id=booking.booking_id)
        else:
            messages.error(request, result['message'])
    
    context = {
        'booking': booking,
        'wallet_balance': wallet_balance,
        'can_pay': can_pay,
    }
    
    return render(request, 'feature_transaction/payment_page.html', context)


@login_required
def payment_success(request, transaction_id):
    """Payment success page"""
    transaction = get_object_or_404(Transaction, transaction_id=transaction_id, user=request.user)
    
    context = {
        'transaction': transaction,
    }
    
    return render(request, 'feature_transaction/payment_success.html', context)
