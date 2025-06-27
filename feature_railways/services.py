from .models import Station, SeatClass, Passenger, Route, RouteHalt, RouteSeatClass, Train, TrainSegment, TrainSeat, SeatBooking
from django.core.exceptions import ValidationError
from django.db import models
from datetime import datetime, timedelta
from decimal import Decimal
import random 

def validate_route_for_train_generation(route):
    errors = []
    
    if not route.source_station:
        errors.append("Route must have a source station")
    if not route.destination_station:
        errors.append("Route must have a destination station")
    
    if not route.running_days:
        errors.append("Route must have running days configured")
    
    seat_classes = RouteSeatClass.objects.filter(route=route)
    if not seat_classes.exists():
        errors.append("Route must have at least one seat class configured")
    
    if not route.departure_time:
        errors.append("Route must have departure time configured")
    if not route.journey_duration:
        errors.append("Route must have journey duration configured")
    
    is_valid = len(errors) == 0
    return is_valid, errors

def has_bookings(train):
    booking_count = train.bookings.count()
    seat_booking_count = SeatBooking.objects.filter(train_seat__train=train).count()
    
    return {
        'has_bookings': booking_count > 0 or seat_booking_count > 0,
        'booking_count': booking_count,
        'seat_booking_count': seat_booking_count
    }

def get_ordered_halt_stations(route_pk):
    try:
        route = Route.objects.get(pk=route_pk)
    except Route.DoesNotExist:
        raise ValidationError("Route Doesn't Exist")
    
    halt_stations = [halt.station for halt in RouteHalt.objects.filter(route=route).order_by('sequence_number')]

    return halt_stations

def generate_trains_on_route(route_pk):
    try:
        route = Route.objects.get(pk=route_pk)
    except Route.DoesNotExist:
        raise ValidationError("Route does not exist")

    is_valid, errors = validate_route_for_train_generation(route)
    if not is_valid:
        error_message = "Route validation failed:\n- " + "\n- ".join(errors)
        raise ValidationError(error_message)
    
    running_days = route.running_days

    today = datetime.today()

    counter = 0
    while counter < 14:
        date = today + timedelta(days=counter)
        weekday = date.weekday()

        if running_days[weekday] == '1':
            departure_date_time = datetime.combine(date, route.departure_time)
            arrival_date_time = departure_date_time + route.journey_duration

            existing_train = Train.objects.filter(
                route=route,
                departure_date_time=departure_date_time
            ).first()

            if existing_train:
                booking_status = has_bookings(existing_train)
                if booking_status['has_bookings']:
                    pass
                else:
                    create_complete_train_infrastructure(existing_train)
            else:
                train = Train.objects.create(
                    route=route,
                    departure_date_time=departure_date_time,
                    arrival_date_time=arrival_date_time
                )
                
                create_complete_train_infrastructure(train)

        counter += 1
    cleanup_incomplete_trains(route)

def create_train_segments_for_train(train):
    booking_count = train.bookings.count()
    seat_booking_count = SeatBooking.objects.filter(train_seat__train=train).count()
    
    if booking_count > 0 or seat_booking_count > 0:
        return
    
    existing_segments = train.segments.count()
    if existing_segments > 0:
        return

    route = train.route
    num_of_halts = route.halt_stations.count()
    
    halt_stations_list = []
    ordered_halts = get_ordered_halt_stations(route.pk)
    
    halt_stations_list.append(route.source_station)
    halt_stations_list.extend(ordered_halts)
    halt_stations_list.append(route.destination_station)

    for i in range(len(halt_stations_list) - 1):
        train_segment = TrainSegment.objects.create(
            train=train, 
            segment_source=halt_stations_list[i],
            segment_destination=halt_stations_list[i + 1],
            segment_number=(i + 1)
        )

def create_train_seats_for_train(train):
    booking_count = train.bookings.count()
    seat_booking_count = SeatBooking.objects.filter(train_seat__train=train).count()
    
    if booking_count > 0 or seat_booking_count > 0:
        return
    
    route = train.route
    seat_classes = RouteSeatClass.objects.filter(route=route)
    
    if not seat_classes.exists():
        return
    
    total_seats_created = 0
    for seat_class_entry in seat_classes:
        seat_class = seat_class_entry.seat_class
        num_seats = seat_class_entry.num_of_available_seats
        seat_class_code = seat_class.code.upper()
        
        seats_created_for_class = 0
        for i in range(1, num_seats + 1):
            seat_number = f"{seat_class_code}{i:02d}"  
            
            seat, created = TrainSeat.objects.get_or_create(
                train=train,
                seat_class=seat_class,
                seat_number=seat_number
            )
            
            if created:
                seats_created_for_class += 1
                total_seats_created += 1
    
    return total_seats_created

def cleanup_incomplete_trains(route):
    trains_with_segments = Train.objects.filter(
        route=route,
        segments__isnull=False
    ).distinct()
    
    trains_with_seats = Train.objects.filter(
        route=route,
        seats__isnull=False
    ).distinct()
    
    complete_trains = trains_with_segments.filter(
        id__in=trains_with_seats.values_list('id', flat=True)
    )
    
    incomplete_trains = Train.objects.filter(route=route).exclude(
        id__in=complete_trains.values_list('id', flat=True)
    )
    
    for train in incomplete_trains:
        booking_status = has_bookings(train)
        if not booking_status['has_bookings']:
            train.delete()

def create_complete_train_infrastructure(train):
    create_train_segments_for_train(train)
    create_train_seats_for_train(train)

def get_train_generation_summary(route):
    total_seat_classes = RouteSeatClass.objects.filter(route=route).count()
    total_seats_per_train = RouteSeatClass.objects.filter(route=route).aggregate(
        total_seats=models.Sum('num_of_available_seats')
    )['total_seats'] or 0
    
    running_days_count = route.running_days.count('1') if route.running_days else 0
    trains_to_generate = running_days_count * 2
    
    return {
        'route': route,
        'total_seat_classes': total_seat_classes,
        'total_seats_per_train': total_seats_per_train,
        'running_days_count': running_days_count,
        'trains_to_generate': trains_to_generate,
    }
