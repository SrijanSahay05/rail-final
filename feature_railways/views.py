from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum
import json
import base64
import io
import qrcode
from decimal import Decimal
from datetime import timedelta
from .models import Station, Train, Route, SeatClass, RouteHalt, RouteSeatClass, TrainSegment, TrainSeat, Booking
from .forms import (
    TrainSearchForm, BookingForm, StationForm, SeatClassForm, RouteForm,
    RouteHaltForm, RouteSeatClassForm, TrainGenerationForm, PassengerDetailForm, PassengerFormSet, BookingConfirmationForm
)
from .services import generate_trains_on_route, generate_train_seats_for_route, get_train_generation_summary
from .booking_services import BookingService
from feature_transaction.services import WalletService
def is_staff(user):
    return user.is_staff
def index(request):
    return render(request, 'feature_railways/index.html')
def search_trains(request):

    form = TrainSearchForm(request.GET or None)
    trains = []

    if form.is_valid():
        source = form.cleaned_data['source']
        destination = form.cleaned_data['destination']
        date = form.cleaned_data['date']

        date_trains = Train.objects.filter(departure_date_time__date=date).select_related(
            'route',
            'route__source_station',
            'route__destination_station'
        )

        direct_trains = date_trains.filter(
            route__source_station=source,
            route__destination_station=destination
        )

        halt_trains = []

        for train in date_trains.exclude(id__in=direct_trains.values_list('id', flat=True)):
            route = train.route

            station_sequence = []

            station_sequence.append({
                'station': route.source_station,
                'sequence': 0,
                'duration_from_start': timedelta(seconds=0)
            })

            for halt in RouteHalt.objects.filter(route=route).order_by('sequence_number'):
                station_sequence.append({
                    'station': halt.station,
                    'sequence': halt.sequence_number,
                    'duration_from_start': halt.journey_duration_from_source
                })

            station_sequence.append({
                'station': route.destination_station,
                'sequence': len(station_sequence),
                'duration_from_start': route.journey_duration
            })

            source_in_sequence = None
            destination_in_sequence = None

            for station_item in station_sequence:
                if station_item['station'] == source:
                    source_in_sequence = station_item
                if station_item['station'] == destination:
                    destination_in_sequence = station_item

                if source_in_sequence and destination_in_sequence:
                    if source_in_sequence['sequence'] < destination_in_sequence['sequence']:
                        train.segment_departure = train.departure_date_time + source_in_sequence['duration_from_start']
                        train.segment_arrival = train.departure_date_time + destination_in_sequence['duration_from_start']
                        train.segment_duration = destination_in_sequence['duration_from_start'] - source_in_sequence['duration_from_start']
                        halt_trains.append(train)
                    break

        trains = list(direct_trains) + halt_trains

        trains.sort(key=lambda t: getattr(t, 'segment_departure', t.departure_date_time))

        for train in trains:
            journey_source = source
            journey_destination = destination
            
            available_seat_classes = RouteSeatClass.objects.filter(route=train.route).select_related('seat_class')
            seat_availability = {}
            
            for route_seat in available_seat_classes:
                availability = BookingService.check_seat_availability(
                    train=train,
                    seat_class=route_seat.seat_class,
                    passenger_count=1,
                    journey_source=journey_source,
                    journey_destination=journey_destination
                )
                
                seat_availability[route_seat.seat_class] = {
                    'available_seats': availability['available_seats'],
                    'total_seats': availability['total_seats']
                }
            train.seat_availability = seat_availability

    return render(request, 'feature_railways/search_results.html', {
        'form': form,
        'trains': trains
    })
@login_required
def book_train(request, train_id, source_id=None, destination_id=None):
    train = get_object_or_404(Train, id=train_id)
    
    journey_source = None
    journey_destination = None
    segment_duration = None
    
    if source_id and destination_id:
        journey_source = get_object_or_404(Station, id=source_id)
        journey_destination = get_object_or_404(Station, id=destination_id)
        route = train.route
        station_sequence = []
        
        station_sequence.append({
            'station': route.source_station,
            'sequence': 0,
            'duration_from_start': timedelta(seconds=0)
        })
        
        for halt in RouteHalt.objects.filter(route=route).order_by('sequence_number'):
            station_sequence.append({
                'station': halt.station,
                'sequence': halt.sequence_number,
                'duration_from_start': halt.journey_duration_from_source
            })
        
        station_sequence.append({
            'station': route.destination_station,
            'sequence': len(station_sequence),
            'duration_from_start': route.journey_duration
        })
        
        source_timing = None
        destination_timing = None
        
        for station_item in station_sequence:
            if station_item['station'] == journey_source:
                source_timing = station_item
            if station_item['station'] == journey_destination:
                destination_timing = station_item
        
        if source_timing and destination_timing:
            segment_duration = destination_timing['duration_from_start'] - source_timing['duration_from_start']
    

    seat_availability = {}
    available_seat_classes = RouteSeatClass.objects.filter(route=train.route).select_related('seat_class')
    
    for route_seat in available_seat_classes:
        availability = BookingService.check_seat_availability(
            train=train,
            seat_class=route_seat.seat_class,
            passenger_count=1,
            journey_source=journey_source,
            journey_destination=journey_destination
        )
        
        seat_availability[route_seat.seat_class.id] = {
            'seat_class': route_seat.seat_class,
            'available_seats': availability['available_seats'],
            'total_seats': availability['total_seats'],
            'price': route_seat.base_fare_per_hour
        }
    
    if request.method == 'POST':
        form = BookingForm(request.POST)
        if form.is_valid():
            selected_seat_class = form.cleaned_data['seat_class']
            passenger_count = form.cleaned_data['passenger_count']
            availability = BookingService.check_seat_availability(
                train=train,
                seat_class=selected_seat_class,
                passenger_count=passenger_count,
                journey_source=journey_source,
                journey_destination=journey_destination
            )
            
            if not availability['available']:
                messages.error(request, f"Not enough seats available: {availability['message']}")
                for route_seat in available_seat_classes:
                    availability_refresh = BookingService.check_seat_availability(
                        train=train,
                        seat_class=route_seat.seat_class,
                        passenger_count=1,
                        journey_source=journey_source,
                        journey_destination=journey_destination
                    )
                    seat_availability[route_seat.seat_class.id] = {
                        'seat_class': route_seat.seat_class,
                        'available_seats': availability_refresh['available_seats'],
                        'total_seats': availability_refresh['total_seats'],
                        'price': route_seat.base_fare_per_hour
                    }
            else:
                booking_details = {
                    'train_id': train.id,
                    'seat_class_id': form.cleaned_data['seat_class'].id,
                    'passenger_count': form.cleaned_data['passenger_count']
                }
                if journey_source and journey_destination:
                    booking_details['journey_source_id'] = journey_source.id
                    booking_details['journey_destination_id'] = journey_destination.id
                request.session['booking_details'] = booking_details
                return redirect('feature_railways:passenger_details')
    else:
        form = BookingForm()
    
    return render(request, 'feature_railways/book_train.html', {
        'train': train,
        'form': form,
        'journey_source': journey_source,
        'journey_destination': journey_destination,
        'segment_duration': segment_duration,
        'seat_availability': seat_availability
    })
@login_required
def passenger_details(request):
    booking_details = request.session.get('booking_details')
    if not booking_details:
        messages.error(request, 'Booking session expired. Please start again.')
        return redirect('feature_railways:index')
    
    train = get_object_or_404(Train, id=booking_details['train_id'])
    seat_class = get_object_or_404(SeatClass, id=booking_details['seat_class_id'])
    passenger_count = booking_details['passenger_count']
    
    journey_source = None
    journey_destination = None
    
    if booking_details and 'journey_source_id' in booking_details and 'journey_destination_id' in booking_details:
        journey_source = get_object_or_404(Station, id=booking_details['journey_source_id'])
        journey_destination = get_object_or_404(Station, id=booking_details['journey_destination_id'])
    
    availability = BookingService.check_seat_availability(train, seat_class, passenger_count, journey_source, journey_destination)
    if not availability['available']:
        messages.error(request, f"Seats no longer available: {availability['message']}")
        return redirect('feature_railways:search_trains')
    
    fare_info = BookingService.calculate_fare(train, seat_class, passenger_count, journey_source, journey_destination)
    if request.method == 'POST':
        formset = PassengerFormSet(request.POST)
        if formset.is_valid():
            passengers_data = []
            for form in formset:
                if form.cleaned_data:
                    passengers_data.append(form.cleaned_data)
            request.session['passengers_data'] = passengers_data
            return redirect('feature_railways:booking_confirmation')
    else:
        formset = PassengerFormSet(initial=[{} for _ in range(passenger_count)])
    return render(request, 'feature_railways/passenger_details.html', {
        'formset': formset,
        'train': train,
        'seat_class': seat_class,
        'passenger_count': passenger_count,
        'fare_info': fare_info,
        'availability': availability
    })
@login_required
def booking_confirmation(request):
    booking_details = request.session.get('booking_details')
    passengers_data = request.session.get('passengers_data')
    
    if not booking_details or not passengers_data:
        messages.error(request, 'Booking session expired. Please start again.')
        return redirect('feature_railways:index')
    
    train = get_object_or_404(Train, id=booking_details['train_id'])
    seat_class = get_object_or_404(SeatClass, id=booking_details['seat_class_id'])
    
    journey_source = None
    journey_destination = None
    
    if 'journey_source_id' in booking_details and 'journey_destination_id' in booking_details:
        journey_source = get_object_or_404(Station, id=booking_details['journey_source_id'])
        journey_destination = get_object_or_404(Station, id=booking_details['journey_destination_id'])
    
    fare_info = BookingService.calculate_fare(train, seat_class, len(passengers_data), journey_source, journey_destination)
    if request.method == 'POST':
        form = BookingConfirmationForm(request.POST)
        if form.is_valid():
            journey_source = None
            journey_destination = None
            if 'journey_source_id' in booking_details and 'journey_destination_id' in booking_details:
                journey_source = get_object_or_404(Station, id=booking_details['journey_source_id'])
                journey_destination = get_object_or_404(Station, id=booking_details['journey_destination_id'])
            result = BookingService.create_booking(
                user=request.user,
                train=train,
                seat_class=seat_class,
                passengers_data=passengers_data,
                emergency_contact=form.cleaned_data['emergency_contact'],
                journey_source=journey_source,
                journey_destination=journey_destination
            )
            if result['success']:
                if 'booking_details' in request.session:
                    del request.session['booking_details']
                if 'passengers_data' in request.session:
                    del request.session['passengers_data']
                booking = result['booking']
                messages.success(request, result['message'])
                return redirect('feature_transaction:payment_page', booking_id=booking.booking_id)
            else:
                messages.error(request, result['message'])
    else:
        form = BookingConfirmationForm()
    journey_source = None
    journey_destination = None
    if 'journey_source_id' in booking_details and 'journey_destination_id' in booking_details:
        journey_source = get_object_or_404(Station, id=booking_details['journey_source_id'])
        journey_destination = get_object_or_404(Station, id=booking_details['journey_destination_id'])
    return render(request, 'feature_railways/booking_confirmation.html', {
        'form': form,
        'train': train,
        'seat_class': seat_class,
        'passengers_data': passengers_data,
        'fare_info': fare_info,
        'journey_source': journey_source,
        'journey_destination': journey_destination
    })
@login_required
def booking_success(request, booking_id):
    booking = get_object_or_404(Booking, booking_id=booking_id, user=request.user)
    booking_summary = BookingService.get_booking_summary(booking)
    return render(request, 'feature_railways/booking_success.html', {
        'booking_summary': booking_summary
    })
@login_required
@user_passes_test(is_staff)
def railway_staff_dashboard(request):
    total_stations = Station.objects.count()
    total_routes = Route.objects.count()
    total_trains = Train.objects.count()
    total_bookings = Booking.objects.count()
    confirmed_bookings = Booking.objects.filter(booking_status='CONFIRMED').count()
    total_revenue = Booking.objects.filter(booking_status='CONFIRMED').aggregate(total=Sum('total_fare'))['total'] or 0
    context = {
        'total_stations': total_stations,
        'total_routes': total_routes,
        'total_trains': total_trains,
        'total_bookings': total_bookings,
        'confirmed_bookings': confirmed_bookings,
        'total_revenue': total_revenue,
    }
    return render(request, 'feature_railways/railway_staff_dashboard.html', context)
@login_required
@user_passes_test(is_staff)
def add_station(request):
    if request.method == 'POST':
        form = StationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Station added successfully!')
            return redirect('feature_railways:railway_staff_dashboard')
    else:
        form = StationForm()
    return render(request, 'feature_railways/add_station.html', {'form': form})
@login_required
@user_passes_test(is_staff)
def add_seat_class(request):
    if request.method == 'POST':
        form = SeatClassForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Seat class added successfully!')
            return redirect('feature_railways:railway_staff_dashboard')
    else:
        form = SeatClassForm()
    return render(request, 'feature_railways/add_seat_class.html', {'form': form})
@login_required
@user_passes_test(is_staff)
def add_route(request):
    if request.method == 'POST':
        form = RouteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Route added successfully!')
            return redirect('feature_railways:railway_staff_dashboard')
    else:
        form = RouteForm()
    return render(request, 'feature_railways/add_route.html', {'form': form})
@login_required
@user_passes_test(is_staff)
def add_route_halt(request):
    if request.method == 'POST':
        form = RouteHaltForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Route halt added successfully!')
            return redirect('feature_railways:railway_staff_dashboard')
    else:
        form = RouteHaltForm()
    return render(request, 'feature_railways/add_route_halt.html', {'form': form})
@login_required
@user_passes_test(is_staff)
def add_route_seat_class(request):
    if request.method == 'POST':
        form = RouteSeatClassForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Route seat class added successfully!')
            return redirect('feature_railways:railway_staff_dashboard')
    else:
        form = RouteSeatClassForm()
    return render(request, 'feature_railways/add_route_seat_class.html', {'form': form})
@login_required
@user_passes_test(is_staff)
def generate_trains(request):
    if request.method == 'POST':
        form = TrainGenerationForm(request.POST)
        if form.is_valid():
            route = form.cleaned_data['route']
            summary = get_train_generation_summary(route)
            try:
                generate_trains_on_route(route.pk)
                success_msg = (
                    f'Complete train infrastructure generated successfully for route {route.name}! '
                    f'Generated {summary["trains_to_generate"]} trains with '
                    f'{summary["total_seats_per_train"]} seats each.'
                )
                messages.success(request, success_msg)
                return redirect('feature_railways:railway_staff_dashboard')
            except ValidationError as e:
                messages.error(request, f'Error generating trains: {e}')
    else:
        form = TrainGenerationForm()
    return render(request, 'feature_railways/generate_trains.html', {'form': form})
@login_required
@user_passes_test(is_staff)
def view_stations(request):
    stations = Station.objects.all()
    return render(request, 'feature_railways/view_stations.html', {'stations': stations})
@login_required
@user_passes_test(is_staff)
def view_routes(request):
    routes = Route.objects.all()
    return render(request, 'feature_railways/view_routes.html', {'routes': routes})
@login_required
@user_passes_test(is_staff)
def view_trains(request):
    trains = Train.objects.all()
    context = {
        'trains': trains,
        'now': timezone.now()
    }
    return render(request, 'feature_railways/view_trains.html', context)
@login_required
@user_passes_test(is_staff)
def view_seat_classes(request):
    seat_classes = SeatClass.objects.all()
    return render(request, 'feature_railways/view_seat_classes.html', {'seat_classes': seat_classes})
@login_required
def user_profile(request):
    user_bookings = Booking.objects.filter(user=request.user).order_by('-booking_date')

    
    wallet_info = WalletService.get_wallet_balance(request.user)
    recent_transactions = WalletService.get_transaction_history(
        user=request.user,
        limit=5
    )
    
    context = {
        'user_bookings': user_bookings,
        'total_bookings': user_bookings.count(),
        'confirmed_bookings': user_bookings.filter(booking_status='CONFIRMED').count(),
        'verified_bookings': user_bookings.filter(is_verified=True).count(),
        'wallet': wallet_info.get('wallet'),
        'wallet_balance': wallet_info.get('balance'),
        'recent_transactions': recent_transactions.get('transactions', []),
    }
    
    return render(request, 'feature_railways/user_profile.html', context)

@login_required
def booking_detail(request, booking_id):
    booking = get_object_or_404(Booking, booking_id=booking_id, user=request.user)
    from .booking_services import BookingService
    booking_summary = BookingService.get_booking_summary(booking)
    show_cancel_button = False
    if booking.booking_status == 'CONFIRMED':
        current_time = timezone.now()
        departure_time = booking.train.departure_date_time
        show_cancel_button = (current_time + timedelta(hours=1) <= departure_time)
    context = {
        'booking': booking,
        'booking_summary': booking_summary,
        'qr_data': booking.get_qr_data(),
        'show_cancel_button': show_cancel_button,
    }
    return render(request, 'feature_railways/booking_detail.html', context)
@login_required
def generate_qr_code(request, booking_id):
    booking = get_object_or_404(Booking, booking_id=booking_id, user=request.user)
    if booking.booking_status != 'CONFIRMED':
        return JsonResponse({'error': 'QR code only available for confirmed bookings'}, status=400)
    qr_data = booking.get_qr_data()
    if not qr_data:
        return JsonResponse({'error': 'QR code data not available'}, status=400)
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(json.dumps(qr_data))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='image/png')
    response['Content-Disposition'] = f'inline; filename="{booking_id}_qr.png"'
    return response
@login_required
@user_passes_test(is_staff)
def qr_scanner(request):
    return render(request, 'feature_railways/qr_scanner.html')
@login_required
@user_passes_test(is_staff) 
def verify_ticket(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    try:
        data = json.loads(request.body)
        qr_data_str = data.get('qr_data')
        if not qr_data_str:
            return JsonResponse({'error': 'QR data is required'}, status=400)
        qr_data = json.loads(qr_data_str)
        booking_id = qr_data.get('booking_id')
        verification_hash = qr_data.get('verification_hash')
        if not booking_id or not verification_hash:
            return JsonResponse({'error': 'Invalid QR code format'}, status=400)
        try:
            booking = Booking.objects.get(booking_id=booking_id)
        except Booking.DoesNotExist:
            return JsonResponse({'error': 'Booking not found'}, status=404)
        stored_qr_data = booking.get_qr_data()
        if not stored_qr_data or stored_qr_data.get('verification_hash') != verification_hash:
            return JsonResponse({'error': 'Invalid or tampered QR code'}, status=400)
        if booking.booking_status != 'CONFIRMED':
            return JsonResponse({
                'error': f'Booking status is {booking.booking_status}, not confirmed',
                'booking_status': booking.booking_status
            }, status=400)
        was_already_verified = booking.is_verified
        first_verification_time = booking.verification_timestamp
        if not booking.is_verified:
            booking.verify_booking()
            verification_status = 'NEWLY_VERIFIED'
            status_message = 'Ticket successfully verified!'
        else:
            verification_status = 'ALREADY_VERIFIED'
            status_message = f'Ticket was already verified on {first_verification_time.strftime("%B %d, %Y at %I:%M %p")}'
        booking_summary = BookingService.get_booking_summary(booking)
        response_data = {
            'success': True,
            'verification_status': verification_status,
            'status_message': status_message,
            'booking_id': booking.booking_id,
            'passenger_count': booking.passenger_count,
            'train_id': booking.train.id,
            'route_name': booking.train.route.name,
            'departure_time': booking.train.departure_date_time.strftime('%Y-%m-%d %H:%M'),
            'seat_class': booking.seat_class.class_type,
            'total_fare': str(booking.total_fare),
            'is_verified': booking.is_verified,
            'verification_timestamp': booking.verification_timestamp.strftime('%Y-%m-%d %H:%M:%S') if booking.verification_timestamp else None,
            'first_verification_time': first_verification_time.strftime('%Y-%m-%d %H:%M:%S') if first_verification_time else None,
            'was_already_verified': was_already_verified,
            'passenger_details': []
        }
        if booking_summary and not booking_summary.get('error'):
            for assignment in booking_summary.get('seat_assignments', []):
                response_data['passenger_details'].append({
                    'name': assignment['passenger'].name,
                    'age': assignment['passenger'].age,
                    'gender': assignment['passenger'].get_gender_display(),
                    'seat_number': assignment['seat_number']
                })
        return JsonResponse(response_data)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Verification failed: {str(e)}'}, status=500)
@login_required
def booking_qr_view(request, booking_id):
    booking = get_object_or_404(Booking, booking_id=booking_id, user=request.user)
    if booking.booking_status != 'CONFIRMED':
        messages.error(request, 'QR code is only available for confirmed bookings.')
        return redirect('feature_railways:user_profile')
    context = {
        'booking': booking,
        'qr_data': booking.get_qr_data(),
    }
    return render(request, 'feature_railways/booking_qr.html', context)
@login_required
@require_http_methods(["POST"])
def cancel_booking(request, booking_id):
    try:
        result = BookingService.cancel_booking(
            booking_id=booking_id,
            user=request.user
        )
        if result['success']:
            refund_amount = result.get('refund_amount', Decimal('0.00'))
            if refund_amount > Decimal('0.00'):
                messages.success(request, f"Booking successfully cancelled. ₹{refund_amount} has been refunded to your wallet.")
            else:
                messages.success(request, "Booking successfully cancelled.")
        else:
            messages.error(request, result.get('message', 'Cancellation failed'))
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
    return redirect('feature_railways:user_profile')