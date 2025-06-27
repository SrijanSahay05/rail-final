from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q, Count, Sum
from decimal import Decimal
from datetime import timedelta

from feature_transaction.models import Transaction
from .models import (
    Train, TrainSeat, TrainSegment, SeatBooking, Booking, 
    Passenger, RouteSeatClass, SeatClass, RouteHalt
)


class BookingService:

    @staticmethod
    def check_seat_availability(train, seat_class, passenger_count, journey_source=None, journey_destination=None):
        try:
            total_seats = TrainSeat.objects.filter(
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
                base_fare_per_hour = Decimal('50.00')
            
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
            passenger_count = len(passengers_data)
            if passenger_count == 0:
                raise ValidationError("At least one passenger is required")
            if passenger_count > 10:
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
            

            train_segments = list(TrainSegment.objects.filter(train=train))
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
            
            all_seats = list(TrainSeat.objects.filter(
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
                    segment_booked_seats = set(SeatBooking.objects.filter(
                        train_segment=segment,
                        train_seat__seat_class=seat_class
                    ).values_list('train_seat_id', flat=True))
                    
                    available_seat_ids -= segment_booked_seats
                
                available_seats = [seat for seat in all_seats if seat.id in available_seat_ids]
            else:
                booked_seat_ids = set()
                for segment in segments_to_check:
                    segment_bookings = SeatBooking.objects.filter(
                        train_segment=segment,
                        train_seat__seat_class=seat_class
                    ).values_list('train_seat_id', flat=True)
                    booked_seat_ids.update(segment_bookings)
                
                available_seats = [seat for seat in all_seats if seat.id not in booked_seat_ids]
            
            if len(available_seats) < passenger_count:
                raise ValidationError(f"Not enough available seats. Only {len(available_seats)} seats available, need {passenger_count}")
            
            selected_seats = available_seats[:passenger_count]
            
            # Create booking first (temporarily without passengers)
            booking = Booking.objects.create(
                user=user,
                train=train,
                seat_class=seat_class,
                passenger_count=passenger_count,
                total_fare=fare_info['total_fare'],
                booking_status='PENDING_PAYMENT',
                journey_source=journey_source,
                journey_destination=journey_destination
            )
            
            # Now create passengers and link them to the booking
            passengers = []
            for passenger_data in passengers_data:
                passenger = Passenger.objects.create(
                    name=passenger_data['name'].strip(),
                    age=passenger_data['age'],
                    gender=passenger_data['gender'],
                    booking_by=user,
                    booking=booking
                )
                passengers.append(passenger)
            
            if journey_source and journey_destination:
                timing = BookingService._get_segment_timing(train, journey_source, journey_destination)
                if timing:
                    booking.departure_datetime = timing['departure']
                    booking.arrival_datetime = timing['arrival']
                    booking.save()
            
            for i, passenger in enumerate(passengers):
                seat = selected_seats[i]
                for segment in segments_to_check:
                    SeatBooking.objects.create(
                        train_seat=seat,
                        train_segment=segment,
                        passenger=passenger,
                        price_for_segment=fare_info['per_passenger_fare']
                    )
            
            return {
                'success': True,
                'booking': booking,
                'message': f'Booking created successfully with ID: {booking.booking_id}'
            }
            
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
                'message': f'An error occurred while creating booking: {str(e)}'
            }
    
    @staticmethod
    def cancel_booking(booking_id, user):
        try:
            booking = Booking.objects.get(booking_id=booking_id, user=user)
            
            if booking.booking_status == 'CANCELLED':
                return {'success': False, 'message': 'Booking is already cancelled'}
            
            if booking.booking_status != 'CONFIRMED':
                return {'success': False, 'message': 'Only confirmed bookings can be cancelled'}
            
            current_time = timezone.now()
            departure_time = booking.train.departure_date_time
            
            if departure_time <= current_time:
                return {'success': False, 'message': 'Cannot cancel booking for departed trains'}
            
            time_until_departure = departure_time - current_time
            if time_until_departure < timedelta(hours=1):
                return {'success': False, 'message': 'Cannot cancel booking less than 1 hour before departure'}
            
            # Delete seat bookings for this specific booking
            seat_bookings = SeatBooking.objects.filter(
                train_seat__train=booking.train,
                passenger__booking=booking
            )
            seat_bookings.delete()
            
            # Delete passengers for this specific booking
            passengers = booking.passengers.all()
            passengers.delete()
            
            booking.booking_status = 'CANCELLED'
            booking.save()
            
            try:
                # Check if there was a payment for this booking
                payment_transaction = Transaction.objects.filter(
                    user=user,
                    amount=booking.total_fare,
                    purpose='PAYMENT',
                    status='COMPLETED',
                    booking_id=booking.booking_id
                ).first()
                
                if payment_transaction:
                    # Process refund using TransactionService
                    from feature_transaction.services import TransactionService
                    refund_result = TransactionService.process_refund(
                        user=user,
                        amount=booking.total_fare,
                        description=f'Refund for cancelled booking {booking.booking_id}',
                        booking_id=booking.booking_id
                    )
                    
                    if refund_result['success']:
                        refund_amount = booking.total_fare
                    else:
                        refund_amount = Decimal('0.00')
                else:
                    refund_amount = Decimal('0.00')
                    
            except Exception as e:
                refund_amount = Decimal('0.00')
            
            return {
                'success': True,
                'message': 'Booking cancelled successfully',
                'refund_amount': refund_amount
            }
            
        except Booking.DoesNotExist:
            return {'success': False, 'message': 'Booking not found'}
        except Exception as e:
            return {'success': False, 'message': f'Error cancelling booking: {str(e)}'}
    
    @staticmethod
    def get_booking_with_lock(booking_id, user):
        try:
            booking = Booking.objects.get(booking_id=booking_id, user=user)
            return {'success': True, 'booking': booking}
        except Booking.DoesNotExist:
            return {'success': False, 'booking': None, 'message': 'Booking not found'}
    
    @staticmethod
    def get_booking_summary(booking):
        try:
            # Get passengers directly from the booking relationship
            passengers = booking.passengers.all()
            
            seat_assignments = []
            segment_details = []
            
            for passenger in passengers:
                # Get the seat booking for this passenger
                seat_booking = SeatBooking.objects.filter(
                    passenger=passenger,
                    train_seat__train=booking.train
                ).first()
                
                if seat_booking:
                    seat_assignments.append({
                        'passenger': passenger,
                        'seat_number': seat_booking.train_seat.seat_number
                    })
            
            # Get segment information for segment bookings
            if booking.journey_source and booking.journey_destination:
                # This is a segment booking
                segments = SeatBooking.objects.filter(
                    passenger__booking=booking,
                    train_seat__train=booking.train
                ).values_list('train_segment', flat=True).distinct()
                
                for segment_id in segments:
                    try:
                        from .models import TrainSegment
                        segment = TrainSegment.objects.get(id=segment_id)
                        segment_details.append({
                            'segment_number': segment.segment_number,
                            'source': segment.segment_source,
                            'destination': segment.segment_destination,
                            'departure_time': segment.departure_date_time,
                            'arrival_time': segment.arrival_date_time
                        })
                    except:
                        continue
            
            # Calculate fare breakdown
            fare_breakdown = {
                'total_fare': booking.total_fare,
                'per_passenger_fare': booking.total_fare / booking.passenger_count if booking.passenger_count > 0 else 0,
                'passenger_count': booking.passenger_count
            }
            
            return {
                'booking': booking,
                'passengers': passengers,
                'seat_assignments': seat_assignments,
                'passenger_count': passengers.count(),
                'segment_details': segment_details,
                'fare_breakdown': fare_breakdown,
                'is_segment_booking': booking.journey_source is not None and booking.journey_destination is not None,
                'route': booking.train.route,
                'train': booking.train
            }
            
        except Exception as e:
            return {'error': str(e)}
    
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
        
        source_sequence = None
        destination_sequence = None
        
        for station_item in station_sequence:
            if station_item['station'] == journey_source:
                source_sequence = station_item['sequence']
            if station_item['station'] == journey_destination:
                destination_sequence = station_item['sequence']
        
        if source_sequence is None or destination_sequence is None:
            return TrainSegment.objects.none()
        
        if source_sequence >= destination_sequence:
            return TrainSegment.objects.none()
        
        overlapping_segments = TrainSegment.objects.filter(
            train=train,
            segment_number__gt=source_sequence,
            segment_number__lte=destination_sequence
        )
        
        return overlapping_segments
    
    @staticmethod
    def _get_segment_availability(train, seat_class, segments):
        try:
            total_seats = TrainSeat.objects.filter(
                train=train,
                seat_class=seat_class
            ).count()
            
            if not segments.exists():
                return {
                    'total_seats': total_seats,
                    'available_seats': total_seats
                }
            
            min_available = total_seats
            
            for segment in segments:
                booked_count = SeatBooking.objects.filter(
                    train_segment=segment,
                    train_seat__seat_class=seat_class
                ).count()
                
                available_in_segment = total_seats - booked_count
                if available_in_segment < min_available:
                    min_available = available_in_segment
            
            return {
                'total_seats': total_seats,
                'available_seats': max(0, min_available)
            }
            
        except Exception:
            return {
                'total_seats': 0,
                'available_seats': 0
            }
    
    @staticmethod
    def _get_segment_timing(train, journey_source, journey_destination):
        route = train.route
        
        station_sequence = []
        station_sequence.append({
            'station': route.source_station,
            'duration_from_start': timedelta(seconds=0)
        })
        
        for halt in RouteHalt.objects.filter(route=route).order_by('sequence_number'):
            station_sequence.append({
                'station': halt.station,
                'duration_from_start': halt.journey_duration_from_source
            })
        
        station_sequence.append({
            'station': route.destination_station,
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
            departure = train.departure_date_time + source_timing['duration_from_start']
            arrival = train.departure_date_time + destination_timing['duration_from_start']
            
            return {
                'departure': departure,
                'arrival': arrival
            }
        
        return None
    
