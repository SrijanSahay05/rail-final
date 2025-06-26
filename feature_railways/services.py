from .models import Station, SeatClass, Passenger, Route, RouteHalt, RouteSeatClass, Train, TrainSegment, TrainSeat, SeatBooking
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
from decimal import Decimal
import random 

def validate_route_for_train_generation(route):
    
    print("=== Function Called: validate_route_for_train_generation ===")
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
    
    halt_count = route.halt_stations.count()
    print(f"[i] Route has {halt_count} halt stations")
    
    if not route.departure_time:
        errors.append("Route must have departure time configured")
    if not route.journey_duration:
        errors.append("Route must have journey duration configured")
    
    is_valid = len(errors) == 0
    return is_valid, errors

def has_bookings(train):
   
    print(f"=== Function Called: has_bookings for Train {train.id} ===")

    booking_count = train.bookings.count()
    seat_booking_count = SeatBooking.objects.filter(train_seat__train=train).count()
    
    return {
        'has_bookings': booking_count > 0 or seat_booking_count > 0,
        'booking_count': booking_count,
        'seat_booking_count': seat_booking_count
    }

def get_ordered_halt_stations(route_pk):

    print("=== Function:get_ordered_halt_stations called ===")
    try:
        route = Route.objects.get(pk=route_pk)
        print(f"[✔️] Route Fetched: {route.code.capitalize()}:{route.name.title()}")
    except Route.DoesNotExist:
        raise ValidationError("Route Doesn't Exist")
    
    halt_stations = [halt.station for halt in RouteHalt.objects.filter(route=route).order_by('sequence_number')]

    print(f"Halt Stations : {halt_stations}")
    return halt_stations

def generate_trains_on_route(route_pk):

    print("=== Function Called: generate_trains_on_route ===")
    try:
        route = Route.objects.get(pk=route_pk)
        print(f"[✓] Route fetched: {route.name} ({route.code})")
    except Route.DoesNotExist:
        raise ValidationError("Route does not exist")

    is_valid, errors = validate_route_for_train_generation(route)
    if not is_valid:
        error_message = "Route validation failed:\n- " + "\n- ".join(errors)
        raise ValidationError(error_message)
    
    running_days = route.running_days
    print(f"[i] Running Days Binary: {running_days}")
    print(f"[i] Route from {route.source_station.code} to {route.destination_station.code}")

    today = datetime.today()
    print(f"[i] Today's Date: {today.strftime('%A, %d-%m-%Y')}")

    weekday_map = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    print("[i] Running Days Map:")
    for i, val in enumerate(running_days):
        print(f"  - {weekday_map[i]}: {'Yes' if val == '1' else 'No'}")

    counter = 0
    while counter < 14:
        date = today + timedelta(days=counter)
        weekday = date.weekday()
        print(f"\n[Day {counter}] {date.strftime('%A, %d-%m-%Y')} (weekday={weekday})")

        if running_days[weekday] == '1':
            print("  -> Match found. Checking for existing train...")
            departure_date_time = datetime.combine(date, route.departure_time)
            arrival_date_time = departure_date_time + route.journey_duration

            print(f"     Departure: {departure_date_time.strftime('%H:%M %d-%m-%Y')}")
            print(f"     Arrival:   {arrival_date_time.strftime('%H:%M %d-%m-%Y')}")

          
            existing_train = Train.objects.filter(
                route=route,
                departure_date_time=departure_date_time
            ).first()

            if existing_train:
               
                booking_status = has_bookings(existing_train)
                if booking_status['has_bookings']:
                    print(f"  [!] PROTECTED: Train {existing_train.id} has bookings - skipping any modifications")
                    print(f"      Bookings: {booking_status['booking_count']}, Seat Bookings: {booking_status['seat_booking_count']}")
                else:
                    print(f"  [i] Train exists but has no bookings: {existing_train}")
                    print("  -> Ensuring complete infrastructure...")
                   
                    create_complete_train_infrastructure(existing_train)
                print("  -> Skipping duplicate train creation...")
            else:
                print("  -> Creating new train...")
                train = Train.objects.create(
                    route=route,
                    departure_date_time=departure_date_time,
                    arrival_date_time=arrival_date_time
                )
                print(f"  [✓] Train created successfully: {train}")
                
                create_complete_train_infrastructure(train)
                
        else:
            print("  -> Not a running day. Skipping.")

        counter += 1
    cleanup_incomplete_trains(route)
    
    final_train_count = Train.objects.filter(route=route).count()
    print(f"\n[✓] Final summary: {final_train_count} complete trains exist for route {route.name}")
    print("\n=== Train generation complete ===")

def create_train_segments_for_train(train):
   
    print(f"=== Creating segments for train {train.id} ===")
    
    booking_count = train.bookings.count()
    seat_booking_count = SeatBooking.objects.filter(train_seat__train=train).count()
    
    if booking_count > 0 or seat_booking_count > 0:
        print(f"[!] PROTECTED: Train {train.id} has existing bookings (bookings: {booking_count}, seat bookings: {seat_booking_count})")
        print("    Skipping segment generation to protect booking integrity")
        return
    
    existing_segments = train.segments.count()
    if existing_segments > 0:
        print(f"[i] Train already has {existing_segments} segments. Skipping segment generation...")
        return

    route = train.route
    num_of_halts = route.halt_stations.count()
    print(f"[i] Route has {num_of_halts} halt stations")
    
    halt_stations_list = []
    ordered_halts = get_ordered_halt_stations(route.pk)
    
    halt_stations_list.append(route.source_station)
    halt_stations_list.extend(ordered_halts)
    halt_stations_list.append(route.destination_station)

    print(f"[i] Station sequence: {[station.code for station in halt_stations_list]}")
    
    if num_of_halts == 0:
        print("[i] No halt stations - creating direct segment from source to destination")
    else:
        print(f"[i] Creating {num_of_halts + 1} segments for route with {num_of_halts} halts")

    for i in range(len(halt_stations_list) - 1):
        train_segment = TrainSegment.objects.create(
            train=train, 
            segment_source=halt_stations_list[i],
            segment_destination=halt_stations_list[i + 1],
            segment_number=(i + 1)
        )
        print(f"  [✓] Segment {train_segment.segment_number}: {train_segment.segment_source.code} → {train_segment.segment_destination.code}")
    
    segments_created = len(halt_stations_list) - 1
    print(f"[✓] Successfully created {segments_created} segment(s) for train {train.id}")

def create_train_seats_for_train(train):
   
    print(f"=== Creating seats for train {train.id} ===")
    
    booking_count = train.bookings.count()
    seat_booking_count = SeatBooking.objects.filter(train_seat__train=train).count()
    
    if booking_count > 0 or seat_booking_count > 0:
        print(f"[!] PROTECTED: Train {train.id} has existing bookings (bookings: {booking_count}, seat bookings: {seat_booking_count})")
        print("    Skipping seat generation to protect booking integrity")
        return
    
    route = train.route
    seat_classes = RouteSeatClass.objects.filter(route=route)
    
    if not seat_classes.exists():
        print("[!] Warning: No seat classes configured for this route. No seats created.")
        return
    
    total_seats_created = 0
    for seat_class_entry in seat_classes:
        seat_class = seat_class_entry.seat_class
        num_seats = seat_class_entry.num_of_available_seats
        seat_class_code = seat_class.code.upper()
        
        print(f"[i] Creating {num_seats} seats for class {seat_class.class_type} ({seat_class_code})")
        
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
                print(f"    [✓] Created seat: {seat_number}")
        
        if seats_created_for_class > 0:
            print(f"  [✓] Created {seats_created_for_class} seats for {seat_class.class_type}")
        else:
            print(f"  [i] All seats already exist for {seat_class.class_type}")
    
    print(f"[✓] Total new seats created: {total_seats_created}")
    return total_seats_created

# TODO check this code block later if referenced in any other file
def generate_train_seats_for_route(route_pk):

    print("=== Function Called: generate_train_seats_for_route ===")
    try:
        trains = Train.objects.filter(route_id=route_pk)
        print(f"[✓] Trains fetched for route {route_pk}: {[str(train) for train in trains]}")
    except Train.DoesNotExist:
        print("[✗] No trains found for this route.")
        raise ValidationError("No trains found for this route.")
    
    seat_classes = RouteSeatClass.objects.filter(route_id=route_pk)
    print(f"[i] Seat classes for route {route_pk}: {[str(sc) for sc in seat_classes]}")

    for train in trains:
        print(f"[i] Processing train: {train}")
        create_train_seats_for_train(train)

def cleanup_incomplete_trains(route):

    print("=== Checking for incomplete trains ===")
    
    trains = Train.objects.filter(route=route)
    cleaned_count = 0
    protected_count = 0
    
    for train in trains:
        segments_count = train.segments.count()
        seats_count = train.seats.count()
        
        if segments_count == 0 or seats_count == 0:
            booking_count = train.bookings.count()
            seat_booking_count = SeatBooking.objects.filter(train_seat__train=train).count()
            
            if booking_count > 0 or seat_booking_count > 0:
                print(f"[!] PROTECTED: Train {train.id} has bookings (bookings: {booking_count}, seat bookings: {seat_booking_count}) - skipping cleanup")
                protected_count += 1
            else:
                print(f"[i] Found incomplete train {train.id} - segments: {segments_count}, seats: {seats_count}")
                train.delete()
                cleaned_count += 1
                print(f"  [✓] Cleaned up incomplete train {train.id}")
    
    if cleaned_count > 0:
        print(f"[✓] Cleaned up {cleaned_count} incomplete trains")
    if protected_count > 0:
        print(f"[i] Protected {protected_count} trains with existing bookings")
    if cleaned_count == 0 and protected_count == 0:
        print("[i] No incomplete trains found")

def create_complete_train_infrastructure(train):
    
    print(f"=== Creating complete infrastructure for train {train.id} ===")
    
    print("[1/2] Creating train segments...")
    create_train_segments_for_train(train)
    
    print("[2/2] Creating train seats...")
    create_train_seats_for_train(train)
    
    print(f"[✓] Complete infrastructure created for train {train.id}")

def get_train_generation_summary(route):
    
    summary = {
        'route_name': route.name,
        'route_code': route.code,
        'source_station': route.source_station.name if route.source_station else 'Not set',
        'destination_station': route.destination_station.name if route.destination_station else 'Not set',
        'halt_stations_count': route.halt_stations.count(),
        'seat_classes_count': RouteSeatClass.objects.filter(route=route).count(),
        'total_seats_per_train': sum([sc.num_of_available_seats for sc in RouteSeatClass.objects.filter(route=route)]),
        'running_days': route.running_days,
        'departure_time': route.departure_time,
        'journey_duration': route.journey_duration,
    }
    
    if route.running_days:
        today = datetime.today()
        trains_to_generate = 0
        for counter in range(14):
            date = today + timedelta(days=counter)
            weekday = date.weekday()
            if route.running_days[weekday] == '1':
                trains_to_generate += 1
        summary['trains_to_generate'] = trains_to_generate
    else:
        summary['trains_to_generate'] = 0
    
    return summary
