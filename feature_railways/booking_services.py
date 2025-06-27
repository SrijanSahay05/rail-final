

from django.db import transaction, connection
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import F, Q, Count, Sum
from decimal import Decimal
from datetime import timedelta

from feature_transaction.models import Transaction
import logging
from .models import (
    Train, TrainSeat, TrainSegment, SeatBooking, Booking, 
    Passenger, RouteSeatClass, SeatClass, RouteHalt
)



class BookingService:

    @staticmethod
    def check_seat_availability(train, seat_class, passenger_count, journey_source=None, journey_destination=None):

        try:
            with transaction.atomic():
                total_seats = TrainSeat.objects.select_for_update().filter(
                    train=train,
                    seat_class=seat_class
                ).count()
                
                if total_seats == 0:
                    return {
                        'available': False,
                        'available_seats': 0,
                        'total_seats': 0,
                        'message': f"No seats configured for {seat_class.class_type} on this train"
                    }
                
                if journey_source and journey_destination:
                    segments_to_check = BookingService._get_overlapping_segments(
                        train, journey_source, journey_destination
                    )
                    if not segments_to_check.exists():
                        return {
                            'available': False,
                            'available_seats': 0,
                            'total_seats': total_seats,
                            'message': "No valid segments found for this journey"
                        }
                    
                    segment_availability = BookingService._get_segment_availability(
                        train, seat_class, segments_to_check
                    )
                    available_seats = segment_availability['available_seats']
                    
                else:
                    segments_to_check = TrainSegment.objects.filter(train=train)
                    if not segments_to_check.exists():
                        return {
                            'available': False,
                            'available_seats': 0,
                            'total_seats': total_seats,
                            'message': "No segments configured for this train"
                        }
                    segment_availability = BookingService._get_segment_availability(
                        train, seat_class, segments_to_check
                    )
                    available_seats = segment_availability['available_seats']
                can_accommodate = available_seats >= passenger_count
                if can_accommodate:
                    message = f"{available_seats} seats available for your journey"
                else:
                    message = f"Only {available_seats} seats available, cannot accommodate {passenger_count} passengers"
                
                return {
                    'available': can_accommodate,
                    'available_seats': available_seats,
                    'total_seats': total_seats,
                    'message': message
                }
                
        except Exception as e:
            return {
                'available': False,
                'available_seats': 0,
                'total_seats': 0,
                'message': f"Error checking availability: {str(e)}"
            }
    
    @staticmethod
    def calculate_fare(train, seat_class, passenger_count, journey_source=None, journey_destination=None):
        try:
            route = train.route
            
            try:
                route_seat_class = RouteSeatClass.objects.get(
                    route=route,
                    seat_class=seat_class
                )
                base_fare_per_hour = route_seat_class.base_fare_per_hour
            except RouteSeatClass.DoesNotExist:
                base_fare_per_hour = Decimal('50.00')  # Default rate
            
            if journey_source and journey_destination:
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
                    journey_duration = destination_timing['duration_from_start'] - source_timing['duration_from_start']
                else:
                    journey_duration = route.journey_duration
            else:
                journey_duration = route.journey_duration
            duration_hours = Decimal(journey_duration.total_seconds() / 3600)
            
            base_fare = route.base_fare
            time_fare = base_fare_per_hour * duration_hours
            per_passenger_fare = base_fare + time_fare
            total_fare = per_passenger_fare * passenger_count
            
            return {
                'base_fare': base_fare,
                'time_fare': time_fare,
                'per_passenger_fare': per_passenger_fare,
                'total_fare': total_fare,
                'breakdown': [
                    {'item': 'Base Fare', 'amount': base_fare},
                    {'item': f'Travel Fare ({duration_hours:.1f} hours)', 'amount': time_fare},
                    {'item': f'Per Passenger Total', 'amount': per_passenger_fare},
                    {'item': f'Total for {passenger_count} passenger(s)', 'amount': total_fare},
                ]
            }
            
        except Exception as e:
            return {
                'base_fare': Decimal('0.00'),
                'time_fare': Decimal('0.00'),
                'per_passenger_fare': Decimal('0.00'),
                'total_fare': Decimal('0.00'),
                'breakdown': [],
                'error': str(e)
            }
    
    @staticmethod
    def create_booking(user, train, seat_class, passengers_data, emergency_contact, journey_source=None, journey_destination=None):
        try:
            with transaction.atomic():
                passenger_count = len(passengers_data)
                if passenger_count == 0:
                    raise ValidationError("At least one passenger is required")
                if passenger_count > 10:  # Business rule
                    raise ValidationError("Maximum 10 passengers allowed per booking")
                for i, passenger_data in enumerate(passengers_data):
                    if not passenger_data.get('name', '').strip():
                        raise ValidationError(f"Passenger {i+1}: Name is required")
                    if not passenger_data.get('age') or passenger_data['age'] < 1 or passenger_data['age'] > 120:
                        raise ValidationError(f"Passenger {i+1}: Valid age (1-120) is required")
                    if not passenger_data.get('gender') in ['M', 'F']:
                        raise ValidationError(f"Passenger {i+1}: Valid gender is required")
                    name = passenger_data['name'].strip()
                    if len(name) < 2 or len(name) > 50:
                        raise ValidationError(f"Passenger {i+1}: Name must be between 2-50 characters")
                
                if train.departure_date_time < timezone.now():
                    raise ValidationError("Cannot book tickets for past trains")
                

                train_segments = list(TrainSegment.objects.select_for_update().filter(train=train))
                if not train_segments:
                    raise ValidationError("No segments configured for this train")
                availability = BookingService.check_seat_availability(
                    train, seat_class, passenger_count, journey_source, journey_destination
                )
                if not availability['available']:
                    raise ValidationError(f"Not enough seats available. {availability['message']}")
                fare_info = BookingService.calculate_fare(train, seat_class, passenger_count, journey_source, journey_destination)
                if 'error' in fare_info:
                    raise ValidationError(f"Fare calculation failed: {fare_info['error']}")
                
                all_seats = list(TrainSeat.objects.select_for_update().filter(
                    train=train,
                    seat_class=seat_class
                ).order_by('seat_number'))
                
                if len(all_seats) == 0:
                    raise ValidationError(f"No seats of class {seat_class.class_type} found on this train")
                
                if journey_source and journey_destination:
                    segments_to_check = BookingService._get_overlapping_segments(
                        train, journey_source, journey_destination
                    )
                else:
                    segments_to_check = train_segments
                
                if journey_source and journey_destination:
                    segment_availability = BookingService._get_segment_availability(
                        train, seat_class, segments_to_check
                    )
                    
                    all_seat_ids = set(seat.id for seat in all_seats)
                    available_seat_ids = all_seat_ids.copy()
                    
                    for segment in segments_to_check:
                        segment_booked_seats = set(SeatBooking.objects.select_for_update().filter(
                            train_segment=segment,
                            train_seat__seat_class=seat_class
                        ).values_list('train_seat_id', flat=True))
                        
                        available_seat_ids -= segment_booked_seats
                    
                    available_seats = [seat for seat in all_seats if seat.id in available_seat_ids]
                else:
                    booked_seat_ids = set()
                    for segment in segments_to_check:
                        segment_bookings = SeatBooking.objects.select_for_update().filter(
                            train_segment=segment,
                            train_seat__seat_class=seat_class
                        ).values_list('train_seat_id', flat=True)
                        booked_seat_ids.update(segment_bookings)
                    
                    available_seats = [seat for seat in all_seats if seat.id not in booked_seat_ids]
                
                if len(available_seats) < passenger_count:
                    raise ValidationError("Seats became unavailable during booking process")
                
                selected_seats = available_seats[:passenger_count]
                
                departure_datetime = None
                arrival_datetime = None
                
                if journey_source and journey_destination:
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
                        departure_datetime = train.departure_date_time + source_timing['duration_from_start']
                        arrival_datetime = train.departure_date_time + destination_timing['duration_from_start']
                
                booking_data = {
                    'user': user,
                    'train': train,
                    'seat_class': seat_class,
                    'passenger_count': passenger_count,
                    'total_fare': fare_info['total_fare'],
                    'booking_status': 'PENDING_PAYMENT'  # Awaiting payment
                }
                
                if journey_source:
                    booking_data['journey_source'] = journey_source
                if journey_destination:
                    booking_data['journey_destination'] = journey_destination
                if departure_datetime:
                    booking_data['departure_datetime'] = departure_datetime
                if arrival_datetime:
                    booking_data['arrival_datetime'] = arrival_datetime
                
                booking = Booking.objects.create(**booking_data)
                
                created_passengers = []
                created_seat_bookings = []
                
                try:
                    for i, passenger_data in enumerate(passengers_data):
                        passenger = Passenger.objects.create(
                            booking_by=user,
                            name=passenger_data['name'].strip().title(),
                            age=passenger_data['age'],
                            gender=passenger_data['gender']
                        )
                        created_passengers.append(passenger)
                        
                        assigned_seat = selected_seats[i]
                        
                        if journey_source and journey_destination:
                            segments_to_book = BookingService._get_overlapping_segments(
                                train, journey_source, journey_destination
                            )
                        else:
                            segments_to_book = train_segments
                        
                        for segment in segments_to_book:
                            seat_booking = SeatBooking.objects.create(
                                train_seat=assigned_seat,
                                train_segment=segment,
                                passenger=passenger,
                                price_for_segment=fare_info['per_passenger_fare']
                            )
                            created_seat_bookings.append(seat_booking)
                    
                    if journey_source and journey_destination:
                        segments_to_book = BookingService._get_overlapping_segments(
                            train, journey_source, journey_destination
                        )
                    else:
                        segments_to_book = train_segments
                    
                    expected_bookings = len(segments_to_book) * passenger_count
                    actual_bookings = len(created_seat_bookings)
                    
                    if actual_bookings != expected_bookings:
                        raise ValidationError(f"Booking integrity check failed: expected {expected_bookings}, got {actual_bookings}")
                    
                    return {
                        'success': True,
                        'booking': booking,
                        'message': f'Booking created successfully. Proceed to payment. Booking ID: {booking.booking_id}',
                        'booking_details': {
                            'booking_id': booking.booking_id,
                            'assigned_seats': [f"{seat.seat_class.code}{seat.seat_number}" for seat in selected_seats],
                            'total_fare': fare_info['total_fare'],
                            'passenger_count': passenger_count,
                            'passengers': [
                                {
                                    'name': p.name,
                                    'age': p.age,
                                    'gender': p.get_gender_display(),
                                    'seat': f"{selected_seats[i].seat_class.code}{selected_seats[i].seat_number}"
                                }
                                for i, p in enumerate(created_passengers)
                            ]
                        }
                    }
                    
                except Exception as e:
                    raise ValidationError(f"Booking creation failed: {str(e)}")
            
        except ValidationError as e:
            return {
                'success': False,
                'booking': None,
                'message': str(e)
            }
        except Exception as e:
            return {
                'success': False,
                'booking': None,
                'message': f"Booking failed due to system error. Please try again."
            }
    
    @staticmethod
    def cancel_booking(booking_id, user):
        try:
            with transaction.atomic():
                try:
                    booking = Booking.objects.select_for_update().get(
                        booking_id=booking_id,
                        user=user
                    )
                except Booking.DoesNotExist:
                    return {
                        'success': False,
                        'message': 'Booking not found or does not belong to you'
                    }
                
                if booking.booking_status != 'CONFIRMED':
                    return {
                        'success': False,
                        'message': f'Cannot cancel booking in {booking.booking_status} status'
                    }
                
                train = booking.train
                
                current_time = timezone.now()
                
                departure_time = train.departure_date_time
                
                if current_time + timedelta(hours=1) > departure_time:
                    return {
                        'success': False,
                        'message': 'Bookings can only be cancelled at least 1 hour before departure'
                    }
                
                booking.booking_status = 'CANCELLED'
                booking.save()
                
                from feature_transaction.services import WalletService
                
                try:
                    payment_transaction = Transaction.objects.select_related('user').get(
                        user=booking.user,
                        transaction_type='DEBIT',
                        purpose='PAYMENT',
                        status='COMPLETED'
                    )
                    
                    refund_result = WalletService.credit_wallet(
                        user=booking.user,
                        amount=payment_transaction.amount,
                        purpose='REFUND',
                        description=f'Refund for cancelled booking {booking.booking_id}'
                    )
                    
                    if not refund_result.get('success'):
                        raise ValidationError("Refund processing failed")
                    
                    return {
                        'success': True,
                        'message': 'Booking cancelled successfully and amount refunded to wallet',
                        'refund_amount': payment_transaction.amount
                    }
                    
                except Transaction.DoesNotExist:
                    return {
                        'success': True,
                        'message': 'Booking cancelled successfully. No payment to refund.',
                        'refund_amount': Decimal('0.00')
                    }
                
        except ValidationError as e:
            return {
                'success': False,
                'message': str(e)
            }
        except Exception as e:
            return {
                'success': False,
                'message': f"Failed to cancel booking: {str(e)}"
            }
    
    @staticmethod
    def get_booking_with_lock(booking_id, user):
        try:
            with transaction.atomic():
                booking = Booking.objects.select_for_update().get(
                    booking_id=booking_id,
                    user=user
                )
                
                passengers = Passenger.objects.select_for_update().filter(
                    seatbooking__train_seat__train=booking.train,
                    booking_by=user
                ).distinct()
                
                seat_assignments = []
                for passenger in passengers:
                    seat_booking = SeatBooking.objects.select_for_update().filter(
                        passenger=passenger,
                        train_seat__train=booking.train
                    ).first()
                    
                    if seat_booking:
                        seat_assignments.append({
                            'passenger': passenger,
                            'seat': seat_booking.train_seat,
                            'seat_number': f"{seat_booking.train_seat.seat_class.code}{seat_booking.train_seat.seat_number}"
                        })
                
                return {
                    'success': True,
                    'booking': booking,
                    'seat_assignments': seat_assignments,
                    'train': booking.train,
                    'route': booking.train.route
                }
                
        except Booking.DoesNotExist:
            return {
                'success': False,
                'error': 'Booking not found or access denied'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    @staticmethod
    def get_booking_summary(booking):
        try:
            result = BookingService.get_booking_with_lock(booking.booking_id, booking.user)
            if not result['success']:
                return {
                    'error': result.get('error', 'Failed to get booking details')
                }
            
            return {
                'booking': result['booking'],
                'seat_assignments': result['seat_assignments'],
                'train': result['train'],
                'route': result['route']
            }
            
        except Exception as e:
            return {
                'error': str(e)
            }
    
    @staticmethod
    def _get_overlapping_segments(train, journey_source, journey_destination):

        route = train.route
        
        station_sequence = []
        
        station_sequence.append({
            'station': route.source_station,
            'sequence': 0
        })
        
        for halt in RouteHalt.objects.filter(route=route).order_by('sequence_number'):
            station_sequence.append({
                'station': halt.station,
                'sequence': halt.sequence_number
            })
        
        station_sequence.append({
            'station': route.destination_station,
            'sequence': len(station_sequence)
        })
        
        journey_start_pos = None
        journey_end_pos = None
        
        for station_item in station_sequence:
            if station_item['station'] == journey_source:
                journey_start_pos = station_item['sequence']
            if station_item['station'] == journey_destination:
                journey_end_pos = station_item['sequence']
        
        if journey_start_pos is None or journey_end_pos is None:
            return TrainSegment.objects.none()
        
        if journey_start_pos >= journey_end_pos:
            return TrainSegment.objects.none()
        
        all_segments = TrainSegment.objects.filter(train=train)
        needed_segments = []
        total_segments = all_segments.count()
        
        if total_segments == 0:
            logger.warning(f"No segments found for train {train.id}")
            return TrainSegment.objects.none()
        
        total_stations = len(station_sequence)
        
        if total_stations <= 1:
            return all_segments

        start_segment_idx = journey_start_pos
        end_segment_idx = journey_end_pos - 1
        
        if start_segment_idx < 0:
            start_segment_idx = 0
        if end_segment_idx >= total_segments:
            end_segment_idx = total_segments - 1
        if start_segment_idx > end_segment_idx:
            return TrainSegment.objects.none()
        
        segments_list = list(all_segments.order_by('id'))
        for i in range(start_segment_idx, end_segment_idx + 1):
            if i < len(segments_list):
                needed_segments.append(segments_list[i])
        
        return TrainSegment.objects.filter(id__in=[s.id for s in needed_segments])
    
    @staticmethod
    def _get_segment_availability(train, seat_class, segments):

        total_seats = TrainSeat.objects.filter(
            train=train,
            seat_class=seat_class
        ).count()
        
        if total_seats == 0:
            return {
                'available_seats': 0,
                'segment_availability': []
            }
        
        segment_availability = []
        min_available = total_seats  # Start with maximum possible
        
        for segment in segments:
            booked_seats_count = SeatBooking.objects.filter(
                train_segment=segment,
                train_seat__seat_class=seat_class
            ).values('train_seat').distinct().count()
            
            available_in_segment = total_seats - booked_seats_count
            
            min_available = min(min_available, available_in_segment)
            
            segment_availability.append({
                'segment': segment,
                'total_seats': total_seats,
                'booked_seats': booked_seats_count,
                'available_seats': available_in_segment
            })
            
        return {
            'available_seats': min_available,
            'segment_availability': segment_availability
        }
    
