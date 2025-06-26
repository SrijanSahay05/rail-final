"""
Booking Services Module
Handles all booking-related business logic including seat availability,
pricing calculations, and booking confirmations with ACID compliance.
"""

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
    Passenger, RouteSeatClass, SeatClass
)

logger = logging.getLogger(__name__)


class BookingService:
    """Service class to handle all booking operations"""
    
    @staticmethod
    @transaction.atomic
    def check_seat_availability(train, seat_class, passenger_count, journey_source=None, journey_destination=None):
        """
        Check if enough seats are available for the given train and seat class.
        Implements segment-wise availability to enable optimal seat utilization.
        
        SEGMENT-WISE AVAILABILITY ALGORITHM:
        =====================================
        
        EXAMPLE: Train A→B→C with 10 seats, 1 seat booked A→B
        
        QUERY 1: B→C (1 passenger)
        - Step 1: Map B→C to segments → [S2(B→C)]
        - Step 2: Check S2 availability → 0 bookings → 10 available
        - Result: 10 seats available ✓ (Seat reuse from A→B passenger)
        
        QUERY 2: A→C (1 passenger)  
        - Step 1: Map A→C to segments → [S1(A→B), S2(B→C)]
        - Step 2: Check S1 availability → 1 booking → 9 available
        - Step 3: Check S2 availability → 0 bookings → 10 available
        - Step 4: Return minimum → min(9,10) = 9 available
        - Result: 9 seats available ✓ (Prevents conflict with A→B booking)
        
        BENEFITS:
        - Optimal seat utilization (B→C can use A→B passenger's seat)
        - Conflict prevention (A→C respects existing A→B bookings)
        - Accurate availability display for users
        
        Args:
            train: Train instance
            seat_class: SeatClass instance
            passenger_count: Number of passengers requesting seats
            journey_source: Source station for journey segment (optional)
            journey_destination: Destination station for journey segment (optional)
            
        Returns:
            dict: {
                'available': bool (True if enough seats for passenger_count),
                'available_seats': int (number of seats available),
                'total_seats': int (total seats configured),
                'message': str (human-readable status message)
            }
        """
        try:
            # STEP 1: Use database locking to prevent race conditions during concurrent bookings
            with transaction.atomic():
                logger.info(f"AVAILABILITY CHECK START: Train {train.id}, Class {seat_class.class_type}, "
                           f"Passengers: {passenger_count}, Journey: {journey_source} → {journey_destination}")
                
                # STEP 2: Get total seats configured for this train and seat class
                total_seats = TrainSeat.objects.select_for_update().filter(
                    train=train,
                    seat_class=seat_class
                ).count()
                
                if total_seats == 0:
                    logger.warning(f"No seats configured for {seat_class.class_type} on train {train.id}")
                    return {
                        'available': False,
                        'available_seats': 0,
                        'total_seats': 0,
                        'message': f"No seats configured for {seat_class.class_type} on this train"
                    }
                
                # STEP 3: Handle segment-wise availability (halt station bookings)
                if journey_source and journey_destination:
                    logger.info(f"SEGMENT BOOKING: Checking availability for halt station journey")
                    
                    # STEP 3A: Map journey to overlapping train segments
                    segments_to_check = BookingService._get_overlapping_segments(
                        train, journey_source, journey_destination
                    )
                    
                    if not segments_to_check.exists():
                        logger.error(f"No valid segments found for journey {journey_source} → {journey_destination}")
                        return {
                            'available': False,
                            'available_seats': 0,
                            'total_seats': total_seats,
                            'message': "No valid segments found for this journey"
                        }
                    
                    # STEP 3B: Calculate minimum availability across all journey segments
                    segment_availability = BookingService._get_segment_availability(
                        train, seat_class, segments_to_check
                    )
                    available_seats = segment_availability['available_seats']
                    
                    logger.info(f"SEGMENT RESULT: Journey {journey_source.name} → {journey_destination.name} "
                               f"across {len(segments_to_check)} segments: {available_seats} seats available")
                    
                    # STEP 3C: Log detailed segment information for debugging
                    for seg_info in segment_availability['segment_availability']:
                        logger.debug(f"  Segment {seg_info['segment'].id}: "
                                   f"{seg_info['available_seats']}/{seg_info['total_seats']} available")
                
                # STEP 4: Handle full route availability (direct bookings)
                else:
                    logger.info(f"FULL ROUTE BOOKING: Checking availability for complete route")
                    
                    # STEP 4A: Get all segments for this train
                    segments_to_check = TrainSegment.objects.filter(train=train)
                    
                    if not segments_to_check.exists():
                        logger.error(f"No segments configured for train {train.id}")
                        return {
                            'available': False,
                            'available_seats': 0,
                            'total_seats': total_seats,
                            'message': "No segments configured for this train"
                        }
                    
                    # STEP 4B: Calculate minimum availability across all train segments
                    segment_availability = BookingService._get_segment_availability(
                        train, seat_class, segments_to_check
                    )
                    available_seats = segment_availability['available_seats']
                    
                    logger.info(f"FULL ROUTE RESULT: Train {train.id} across all segments: "
                               f"{available_seats} seats available")
                
                # STEP 5: Determine if booking can be accommodated
                can_accommodate = available_seats >= passenger_count
                
                # STEP 6: Generate appropriate response message
                if can_accommodate:
                    message = f"{available_seats} seats available for your journey"
                else:
                    message = f"Only {available_seats} seats available, cannot accommodate {passenger_count} passengers"
                
                logger.info(f"FINAL RESULT: Available={can_accommodate}, Seats={available_seats}/{total_seats}, "
                           f"Requested={passenger_count}")
                
                return {
                    'available': can_accommodate,
                    'available_seats': available_seats,
                    'total_seats': total_seats,
                    'message': message
                }
                
        except Exception as e:
            logger.error(f"ERROR in seat availability check: {str(e)}", exc_info=True)
            return {
                'available': False,
                'available_seats': 0,
                'total_seats': 0,
                'message': f"Error checking availability: {str(e)}"
            }
    
    @staticmethod
    def calculate_fare(train, seat_class, passenger_count, journey_source=None, journey_destination=None):
        """
        Calculate total fare for the booking
        
        Args:
            train: Train instance
            seat_class: SeatClass instance
            passenger_count: Number of passengers
            journey_source: Source station for journey segment (optional)
            journey_destination: Destination station for journey segment (optional)
            
        Returns:
            dict: {
                'base_fare': Decimal,
                'per_passenger_fare': Decimal,
                'total_fare': Decimal,
                'breakdown': list
            }
        """
        try:
            route = train.route
            
            # Get route seat class configuration
            try:
                route_seat_class = RouteSeatClass.objects.get(
                    route=route,
                    seat_class=seat_class
                )
                base_fare_per_hour = route_seat_class.base_fare_per_hour
            except RouteSeatClass.DoesNotExist:
                # Fallback to route base fare
                base_fare_per_hour = Decimal('50.00')  # Default rate
            
            # Calculate journey duration (for segment or full route)
            if journey_source and journey_destination:
                # Calculate segment duration for halt station booking
                from .models import RouteHalt
                
                # Build station sequence with timing
                station_sequence = []
                
                # Add source station
                station_sequence.append({
                    'station': route.source_station,
                    'sequence': 0,
                    'duration_from_start': timedelta(seconds=0)
                })
                
                # Add halt stations
                for halt in RouteHalt.objects.filter(route=route).order_by('sequence_number'):
                    station_sequence.append({
                        'station': halt.station,
                        'sequence': halt.sequence_number,
                        'duration_from_start': halt.journey_duration_from_source
                    })
                
                # Add destination station
                station_sequence.append({
                    'station': route.destination_station,
                    'sequence': len(station_sequence),
                    'duration_from_start': route.journey_duration
                })
                
                # Find source and destination timing
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
                    # Fallback to full route duration if stations not found
                    journey_duration = route.journey_duration
            else:
                # Use full route duration
                journey_duration = route.journey_duration
            
            duration_hours = Decimal(journey_duration.total_seconds() / 3600)
            
            # Calculate fare components
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
    @transaction.atomic
    def create_booking(user, train, seat_class, passengers_data, emergency_contact, journey_source=None, journey_destination=None):
        """
        Create a complete booking with seat assignments using ACID compliance
        
        ACID Compliance:
        - Atomicity: All operations succeed or fail together
        - Consistency: Data validation and business rules enforced
        - Isolation: Database locks prevent race conditions
        - Durability: All changes are committed to database
        
        Args:
            user: User instance
            train: Train instance
            seat_class: SeatClass instance
            passengers_data: List of passenger dictionaries
            emergency_contact: Emergency contact number
            journey_source: Source station for the journey segment (optional)
            journey_destination: Destination station for the journey segment (optional)
            
        Returns:
            dict: {
                'success': bool,
                'booking': Booking instance or None,
                'message': str,
                'booking_details': dict
            }
        """
        try:
            # Set isolation level to prevent phantom reads
            with transaction.atomic():
                # Step 1: Data Validation (Consistency)
                passenger_count = len(passengers_data)
                
                if passenger_count == 0:
                    raise ValidationError("At least one passenger is required")
                
                if passenger_count > 10:  # Business rule
                    raise ValidationError("Maximum 10 passengers allowed per booking")
                
                # Validate passenger data
                for i, passenger_data in enumerate(passengers_data):
                    if not passenger_data.get('name', '').strip():
                        raise ValidationError(f"Passenger {i+1}: Name is required")
                    if not passenger_data.get('age') or passenger_data['age'] < 1 or passenger_data['age'] > 120:
                        raise ValidationError(f"Passenger {i+1}: Valid age (1-120) is required")
                    if not passenger_data.get('gender') in ['M', 'F']:
                        raise ValidationError(f"Passenger {i+1}: Valid gender is required")
                    
                    # Check name length and characters
                    name = passenger_data['name'].strip()
                    if len(name) < 2 or len(name) > 50:
                        raise ValidationError(f"Passenger {i+1}: Name must be between 2-50 characters")
                
                # Validate train is still available for booking
                if train.departure_date_time < timezone.now():
                    raise ValidationError("Cannot book tickets for past trains")
                
                # Check if booking window is still open (e.g., not more than 120 days in advance)
                max_advance_days = 120
                if train.departure_date_time > timezone.now() + timezone.timedelta(days=max_advance_days):
                    raise ValidationError(f"Bookings open only {max_advance_days} days in advance")
                
                logger.info(f"Starting booking creation for user {user.id}, train {train.id}, "
                           f"seat_class {seat_class.id}, passengers {passenger_count}")
                
                # Step 2: Seat Availability Check with Locking (Isolation)
                # Use select_for_update to lock the relevant rows
                train_segments = list(TrainSegment.objects.select_for_update().filter(train=train))
                
                if not train_segments:
                    raise ValidationError("No segments configured for this train")
                
                # Check availability with row-level locking
                availability = BookingService.check_seat_availability(
                    train, seat_class, passenger_count, journey_source, journey_destination
                )
                
                if not availability['available']:
                    raise ValidationError(f"Not enough seats available. {availability['message']}")
                
                # Step 3: Calculate Fare (Consistency)
                fare_info = BookingService.calculate_fare(train, seat_class, passenger_count, journey_source, journey_destination)
                
                if 'error' in fare_info:
                    raise ValidationError(f"Fare calculation failed: {fare_info['error']}")
                
                # Step 4: Reserve Seats (Atomicity + Isolation)
                # Get available seats with locking
                all_seats = list(TrainSeat.objects.select_for_update().filter(
                    train=train,
                    seat_class=seat_class
                ).order_by('seat_number'))
                
                if len(all_seats) == 0:
                    raise ValidationError(f"No seats of class {seat_class.class_type} found on this train")
                
                # Determine which segments to check based on journey
                if journey_source and journey_destination:
                    segments_to_check = BookingService._get_overlapping_segments(
                        train, journey_source, journey_destination
                    )
                else:
                    segments_to_check = train_segments
                
                # Get seat availability for each segment and find seats available across all segments
                if journey_source and journey_destination:
                    # For segment bookings, find seats that are free across ALL required segments
                    segment_availability = BookingService._get_segment_availability(
                        train, seat_class, segments_to_check
                    )
                    
                    # Get seats that are available across all segments
                    all_seat_ids = set(seat.id for seat in all_seats)
                    available_seat_ids = all_seat_ids.copy()  # Start with all seat IDs
                    
                    for segment in segments_to_check:
                        segment_booked_seats = set(SeatBooking.objects.select_for_update().filter(
                            train_segment=segment,
                            train_seat__seat_class=seat_class
                        ).values_list('train_seat_id', flat=True))
                        
                        # Remove seats that are booked in this segment
                        available_seat_ids -= segment_booked_seats
                    
                    available_seats = [seat for seat in all_seats if seat.id in available_seat_ids]
                else:
                    # For full route bookings, find seats not booked in any segment
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
                
                # Select seats to assign
                selected_seats = available_seats[:passenger_count]
                
                # Step 5: Calculate journey segment if source/destination provided
                departure_datetime = None
                arrival_datetime = None
                
                if journey_source and journey_destination:
                    # Calculate timing for journey segment (halt station booking)
                    route = train.route
                    
                    # Build station sequence with timing
                    station_sequence = []
                    
                    # Add source station
                    station_sequence.append({
                        'station': route.source_station,
                        'sequence': 0,
                        'duration_from_start': timedelta(seconds=0)
                    })
                    
                    # Add halt stations
                    from .models import RouteHalt
                    for halt in RouteHalt.objects.filter(route=route).order_by('sequence_number'):
                        station_sequence.append({
                            'station': halt.station,
                            'sequence': halt.sequence_number,
                            'duration_from_start': halt.journey_duration_from_source
                        })
                    
                    # Add destination station
                    station_sequence.append({
                        'station': route.destination_station,
                        'sequence': len(station_sequence),
                        'duration_from_start': route.journey_duration
                    })
                    
                    # Find source and destination in sequence
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
                
                # Step 6: Create Booking Record (Atomicity)
                booking_data = {
                    'user': user,
                    'train': train,
                    'seat_class': seat_class,
                    'passenger_count': passenger_count,
                    'total_fare': fare_info['total_fare'],
                    'booking_status': 'PENDING_PAYMENT'  # Awaiting payment
                }
                
                # Add journey segment fields if available
                if journey_source:
                    booking_data['journey_source'] = journey_source
                if journey_destination:
                    booking_data['journey_destination'] = journey_destination
                if departure_datetime:
                    booking_data['departure_datetime'] = departure_datetime
                if arrival_datetime:
                    booking_data['arrival_datetime'] = arrival_datetime
                
                booking = Booking.objects.create(**booking_data)
                
                logger.info(f"Created booking {booking.booking_id} with status PENDING_PAYMENT")
                
                # Step 7: Create Passengers and Seat Bookings (Atomicity)
                created_passengers = []
                created_seat_bookings = []
                
                try:
                    for i, passenger_data in enumerate(passengers_data):
                        # Create passenger
                        passenger = Passenger.objects.create(
                            booking_by=user,
                            name=passenger_data['name'].strip().title(),
                            age=passenger_data['age'],
                            gender=passenger_data['gender']
                        )
                        created_passengers.append(passenger)
                        
                        # Assign seat
                        assigned_seat = selected_seats[i]
                        
                        # Determine which segments to book based on journey
                        if journey_source and journey_destination:
                            # For halt station bookings, only book overlapping segments
                            segments_to_book = BookingService._get_overlapping_segments(
                                train, journey_source, journey_destination
                            )
                        else:
                            # For full route bookings, book all segments
                            segments_to_book = train_segments
                        
                        # Create seat bookings for relevant segments
                        for segment in segments_to_book:
                            seat_booking = SeatBooking.objects.create(
                                train_seat=assigned_seat,
                                train_segment=segment,
                                passenger=passenger,
                                price_for_segment=fare_info['per_passenger_fare']
                            )
                            created_seat_bookings.append(seat_booking)
                    
                    # Step 8: Final Validation (Consistency)
                    # Update expected bookings calculation
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
                    
                    # The booking is now ready for payment, so we return it
                    logger.info(f"Successfully created booking {booking.booking_id} pending payment.")
                    
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
                    # If anything fails, the transaction will be rolled back automatically
                    logger.error(f"Error during booking creation: {str(e)}")
                    raise ValidationError(f"Booking creation failed: {str(e)}")
            
        except ValidationError as e:
            logger.warning(f"Booking validation failed: {str(e)}")
            return {
                'success': False,
                'booking': None,
                'message': str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error during booking: {str(e)}")
            return {
                'success': False,
                'booking': None,
                'message': f"Booking failed due to system error. Please try again."
            }
    
    @staticmethod
    @transaction.atomic
    def cancel_booking(booking_id, user):
        """
        Cancel a booking and issue refund to wallet
        Ensures booking can only be cancelled at least 1 hour before departure from source station
        
        Args:
            booking_id: Booking ID to cancel
            user: User requesting cancellation
            
        Returns:
            dict: Result with success status and message
        """
        try:
            with transaction.atomic():
                # Get booking with validation
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
                
                # Check if booking is in a cancellable state
                if booking.booking_status != 'CONFIRMED':
                    return {
                        'success': False,
                        'message': f'Cannot cancel booking in {booking.booking_status} status'
                    }
                
                # Get the train information
                train = booking.train
                
                # Get current time
                current_time = timezone.now()
                
                # Calculate departure time from booking's source station
                # This might be different from train's departure time if using a halt station
                departure_time = train.departure_date_time
                
                # Check if there's at least 1 hour before departure
                if current_time + timedelta(hours=1) > departure_time:
                    return {
                        'success': False,
                        'message': 'Bookings can only be cancelled at least 1 hour before departure'
                    }
                
                # Mark booking as cancelled
                booking.booking_status = 'CANCELLED'
                booking.save()
                
                # Process refund if there was a payment
                from feature_transaction.services import WalletService
                
                try:
                    # Get original payment transaction
                    payment_transaction = Transaction.objects.select_related('user').get(
                        user=booking.user,
                        transaction_type='DEBIT',
                        purpose='PAYMENT',
                        status='COMPLETED'
                    )
                    
                    # Process refund through WalletService
                    refund_result = WalletService.credit_wallet(
                        user=booking.user,
                        amount=payment_transaction.amount,
                        purpose='REFUND',
                        description=f'Refund for cancelled booking {booking.booking_id}'
                    )
                    
                    if not refund_result.get('success'):
                        # Rollback if refund fails
                        raise ValidationError("Refund processing failed")
                    
                    return {
                        'success': True,
                        'message': 'Booking cancelled successfully and amount refunded to wallet',
                        'refund_amount': payment_transaction.amount
                    }
                    
                except Transaction.DoesNotExist:
                    # No payment found, just mark as cancelled
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
            logger.error(f"Error cancelling booking {booking_id}: {str(e)}")
            return {
                'success': False,
                'message': f"Failed to cancel booking: {str(e)}"
            }
    
    @staticmethod
    @transaction.atomic
    def get_booking_with_lock(booking_id, user):
        """
        Get booking details with database lock for consistent reads
        
        Args:
            booking_id: Booking ID
            user: User requesting the booking
            
        Returns:
            dict: Booking details or error
        """
        try:
            with transaction.atomic():
                booking = Booking.objects.select_for_update().get(
                    booking_id=booking_id,
                    user=user
                )
                
                # Get seat assignments with locks
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
            logger.error(f"Error getting booking {booking_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def validate_booking_integrity():
        """
        Validate booking system integrity - can be run as a maintenance task
        
        Returns:
            dict: Integrity check results
        """
        issues = []
        
        try:
            # Check for orphaned seat bookings
            orphaned_bookings = SeatBooking.objects.filter(
                passenger__isnull=True
            ).count()
            
            if orphaned_bookings > 0:
                issues.append(f"{orphaned_bookings} orphaned seat bookings found")
            
            # Check for bookings without seat assignments
            bookings_without_seats = Booking.objects.filter(
                booking_status='CONFIRMED'
            ).exclude(
                user__passenger__seatbooking__isnull=False
            ).count()
            
            if bookings_without_seats > 0:
                issues.append(f"{bookings_without_seats} confirmed bookings without seat assignments")
            
            # Check for double bookings (same seat, overlapping segments)
            # This is a complex query but important for integrity
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT train_seat_id, train_segment_id, COUNT(*) as booking_count
                    FROM feature_railways_seatbooking 
                    GROUP BY train_seat_id, train_segment_id 
                    HAVING COUNT(*) > 1
                """)
                
                double_bookings = cursor.fetchall()
                if double_bookings:
                    issues.append(f"{len(double_bookings)} double bookings detected")
            
            return {
                'success': True,
                'issues_found': len(issues),
                'issues': issues,
                'message': 'No integrity issues found' if not issues else f'{len(issues)} issues found'
            }
            
        except Exception as e:
            logger.error(f"Error during integrity check: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def get_booking_summary(booking):
        """
        Get detailed booking summary using ACID-compliant methods
        
        Args:
            booking: Booking instance
            
        Returns:
            dict: Booking summary with seat assignments
        """
        try:
            # Use the ACID-compliant method to get booking details
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
            logger.error(f"Error getting booking summary for {booking.booking_id}: {str(e)}")
            return {
                'error': str(e)
            }
    
    @staticmethod
    def _get_overlapping_segments(train, journey_source, journey_destination):
        """
        Get train segments that overlap with the journey from source to destination.
        
        SEGMENT OVERLAP LOGIC:
        For a train A→B→C with segments S1(A→B) and S2(B→C):
        - Journey A→B: Uses segment S1 only
        - Journey B→C: Uses segment S2 only  
        - Journey A→C: Uses segments S1 AND S2 (both needed for full journey)
        
        PRACTICAL EXAMPLE:
        - Booking 1: A→B uses S1 (1 seat occupied in S1)
        - Query B→C: Checks S2 only → 10 seats available (S1 booking doesn't affect S2)
        - Query A→C: Checks S1 AND S2 → min(9,10) = 9 seats available
        
        Args:
            train: Train instance
            journey_source: Source station for the journey
            journey_destination: Destination station for the journey
            
        Returns:
            QuerySet of TrainSegment objects that overlap with the journey
        """
        from .models import RouteHalt
        
        route = train.route
        
        # STEP 1: Build complete station sequence with their positions in the route
        station_sequence = []
        
        # Add route source station (position 0)
        station_sequence.append({
            'station': route.source_station,
            'sequence': 0
        })
        
        # Add halt stations in order
        for halt in RouteHalt.objects.filter(route=route).order_by('sequence_number'):
            station_sequence.append({
                'station': halt.station,
                'sequence': halt.sequence_number
            })
        
        # Add route destination station (final position)
        station_sequence.append({
            'station': route.destination_station,
            'sequence': len(station_sequence)
        })
        
        # STEP 2: Find positions of journey source and destination stations
        journey_start_pos = None
        journey_end_pos = None
        
        for station_item in station_sequence:
            if station_item['station'] == journey_source:
                journey_start_pos = station_item['sequence']
            if station_item['station'] == journey_destination:
                journey_end_pos = station_item['sequence']
        
        # STEP 3: Validate journey stations exist in route
        if journey_start_pos is None or journey_end_pos is None:
            logger.warning(f"Journey stations not found in route. Source: {journey_source}, Dest: {journey_destination}")
            return TrainSegment.objects.none()
        
        if journey_start_pos >= journey_end_pos:
            logger.warning(f"Invalid journey: source position {journey_start_pos} >= destination position {journey_end_pos}")
            return TrainSegment.objects.none()
        
        # STEP 4: Map journey to train segments using proportional coverage
        # Since TrainSegment doesn't store start/end stations, we use proportional mapping
        all_segments = TrainSegment.objects.filter(train=train)
        needed_segments = []
        total_segments = all_segments.count()
        
        if total_segments == 0:
            logger.warning(f"No segments found for train {train.id}")
            return TrainSegment.objects.none()
        
        # Calculate proportional segment coverage
        total_stations = len(station_sequence)
        
        if total_stations <= 1:
            # Edge case: only one station, return all segments
            return all_segments
        
        # PROPORTIONAL MAPPING LOGIC:
        # If we have 5 stations (A→B→C→D→E) and 4 segments:
        # - Segment 1 covers station 0→1 (A→B)  
        # - Segment 2 covers station 1→2 (B→C)
        # - Segment 3 covers station 2→3 (C→D)
        # - Segment 4 covers station 3→4 (D→E)
        # For journey A→B (pos 0→1): need segment 1 only
        # For journey B→C (pos 1→2): need segment 2 only
        # For journey A→C (pos 0→2): need segments 1 AND 2
        
        # Calculate which segments are needed for this journey
        # Each segment covers exactly one station-to-station hop
        start_segment_idx = journey_start_pos
        end_segment_idx = journey_end_pos - 1  # Exclusive end, so subtract 1
        
        # Validate segment indices
        if start_segment_idx < 0:
            start_segment_idx = 0
        if end_segment_idx >= total_segments:
            end_segment_idx = total_segments - 1
        if start_segment_idx > end_segment_idx:
            logger.warning(f"Invalid segment range: {start_segment_idx} > {end_segment_idx}")
            return TrainSegment.objects.none()
        
        # STEP 5: Get the segments that cover the journey
        segments_list = list(all_segments.order_by('id'))
        for i in range(start_segment_idx, end_segment_idx + 1):
            if i < len(segments_list):
                needed_segments.append(segments_list[i])
        
        logger.info(f"SEGMENT MAPPING: Journey {journey_source.name}→{journey_destination.name} "
                   f"(stations {journey_start_pos}→{journey_end_pos}) maps to "
                   f"segments {start_segment_idx}→{end_segment_idx} ({len(needed_segments)} segments)")
        
        return TrainSegment.objects.filter(id__in=[s.id for s in needed_segments])
    
    @staticmethod
    def _get_segment_availability(train, seat_class, segments):
        """
        Calculate seat availability for each segment and return the minimum.
        
        SEAT REUSE LOGIC EXPLANATION:
        For train A→B→C with 10 seats and segments S1(A→B), S2(B→C):
        
        SCENARIO 1: 1 seat booked A→B
        - S1 has 1 booking → 9 available in S1
        - S2 has 0 bookings → 10 available in S2
        
        QUERIES:
        - B→C (uses S2 only): Returns 10 available ✓ Seat reuse works!
        - A→C (uses S1+S2): Returns min(9,10) = 9 available ✓ Prevents conflict!
        
        This enables optimal seat utilization while preventing double-booking.
        
        Args:
            train: Train instance
            seat_class: SeatClass instance  
            segments: QuerySet of TrainSegment objects to check
            
        Returns:
            dict: {
                'available_seats': int (minimum across all segments),
                'segment_availability': list of dict with per-segment details
            }
        """
        # STEP 1: Get total seats for this train and seat class
        total_seats = TrainSeat.objects.filter(
            train=train,
            seat_class=seat_class
        ).count()
        
        if total_seats == 0:
            logger.warning(f"No seats configured for {seat_class.class_type} on train {train.id}")
            return {
                'available_seats': 0,
                'segment_availability': []
            }
        
        # STEP 2: Check availability in each segment individually
        segment_availability = []
        min_available = total_seats  # Start with maximum possible
        
        logger.info(f"AVAILABILITY CHECK: Train {train.id}, Class {seat_class.class_type}, "
                   f"Total seats: {total_seats}, Checking {len(segments)} segments")
        
        for segment in segments:
            # STEP 3: Count booked seats in this specific segment
            booked_seats_count = SeatBooking.objects.filter(
                train_segment=segment,
                train_seat__seat_class=seat_class
            ).values('train_seat').distinct().count()
            
            # STEP 4: Calculate available seats in this segment
            available_in_segment = total_seats - booked_seats_count
            
            # STEP 5: Track minimum availability across all segments
            # This is the key to segment-wise availability!
            min_available = min(min_available, available_in_segment)
            
            # STEP 6: Store detailed information for debugging
            segment_availability.append({
                'segment': segment,
                'total_seats': total_seats,
                'booked_seats': booked_seats_count,
                'available_seats': available_in_segment
            })
            
            logger.debug(f"Segment {segment.id}: {booked_seats_count} booked, "
                        f"{available_in_segment} available")
        
        logger.info(f"RESULT: Minimum availability across all segments: {min_available}")
        
        return {
            'available_seats': min_available,
            'segment_availability': segment_availability
        }
    
    # ...existing code...
