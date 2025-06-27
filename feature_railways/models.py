from core_users.models import CustomUser
from datetime import datetime, timedelta
from django.db import models


class Station(models.Model):
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=6, unique=True)

    def __str__(self):
        return f"{self.code}:{self.name}"


class SeatClass(models.Model):
    class_type = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=6, unique=True)

    def __str__(self):
        return f"{self.code}:{self.class_type}"


class Passenger(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
    ]

    name = models.CharField(max_length=50)
    age = models.PositiveIntegerField()
    gender = models.CharField(choices=GENDER_CHOICES, max_length=1)
    booking_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    booking = models.ForeignKey('Booking', on_delete=models.CASCADE, related_name='passengers', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Passenger:{self.name} | Age:{self.age} | Gender:{self.gender}"


class Route(models.Model):
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=6, unique=True)
    base_fare = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    source_station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name='route_as_source')
    departure_time = models.TimeField()
    journey_duration = models.DurationField()
    destination_station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name='route_as_destination')
    arrival_time = models.TimeField(null=True)
    running_days = models.CharField(max_length=7, null=True, blank=True)

    def __str__(self):
        return f"{self.code} : {self.name} ({self.source_station.code} to {self.destination_station.code})"


class RouteHalt(models.Model):
    station = models.ForeignKey(Station, on_delete=models.CASCADE)
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='halt_stations')
    sequence_number = models.PositiveIntegerField()
    journey_duration_from_source = models.DurationField()

    def __str__(self):
        return f"Halt Station {self.station.code} on route {self.route.code}"


class RouteSeatClass(models.Model):
    seat_class = models.ForeignKey(SeatClass, on_delete=models.CASCADE)
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    num_of_available_seats = models.PositiveIntegerField(default=100)
    base_fare_per_hour = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.seat_class} on {self.route} [seats available: {self.num_of_available_seats}]"


class Train(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='trains_on_route')
    departure_date_time = models.DateTimeField()
    arrival_date_time = models.DateTimeField()

    def __str__(self):
        return f"{self.route} [{self.departure_date_time.strftime('%H:%M %d-%m-%Y')}]"


class TrainSegment(models.Model):
    train = models.ForeignKey(Train, on_delete=models.CASCADE, related_name='segments')
    segment_source = models.ForeignKey(Station, on_delete=models.CASCADE, related_name='segments_as_source')
    departure_date_time = models.DateTimeField(null=True)
    segment_destination = models.ForeignKey(Station, on_delete=models.CASCADE, related_name='segment_as_destination')
    arrival_date_time = models.DateTimeField(null=True)
    segment_number = models.PositiveIntegerField()
    segment_journey_duration = models.DurationField(null=True)

    def __str__(self):
        return f"Train Segment on {self.train.route.code} [{self.segment_source.code} to {self.segment_destination.code} ({self.segment_number})]"


class TrainSeat(models.Model):
    train = models.ForeignKey(Train, on_delete=models.CASCADE, related_name='seats')
    seat_class = models.ForeignKey(SeatClass, on_delete=models.CASCADE)
    seat_number = models.CharField(max_length=10)

    def __str__(self):
        return f"{self.train} - {self.seat_class.code} {self.seat_number}"


class SeatBooking(models.Model):
    train_seat = models.ForeignKey(TrainSeat, on_delete=models.CASCADE, related_name='bookings')
    train_segment = models.ForeignKey(TrainSegment, on_delete=models.CASCADE, related_name='bookings')
    passenger = models.ForeignKey(Passenger, on_delete=models.CASCADE)
    booked_at = models.DateTimeField(auto_now_add=True)
    price_for_segment = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.train_seat} booked for {self.train_segment} by {self.passenger.booking_by}"


class Booking(models.Model):
    BOOKING_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PENDING_PAYMENT', 'Pending Payment'),
        ('CONFIRMED', 'Confirmed'),
        ('CANCELLED', 'Cancelled'),
        ('COMPLETED', 'Completed'),
    ]

    booking_id = models.CharField(max_length=20, unique=True)
    user = models.ForeignKey('core_users.CustomUser', on_delete=models.CASCADE, related_name='bookings')
    train = models.ForeignKey(Train, on_delete=models.CASCADE, related_name='bookings')
    seat_class = models.ForeignKey(SeatClass, on_delete=models.CASCADE)
    passenger_count = models.PositiveIntegerField()
    total_fare = models.DecimalField(max_digits=10, decimal_places=2)
    booking_status = models.CharField(max_length=20, choices=BOOKING_STATUS_CHOICES, default='PENDING')
    booking_date = models.DateTimeField(auto_now_add=True)
    journey_source = models.ForeignKey(Station, on_delete=models.CASCADE, related_name='bookings_as_source', null=True, blank=True)
    journey_destination = models.ForeignKey(Station, on_delete=models.CASCADE, related_name='bookings_as_destination', null=True, blank=True)
    departure_datetime = models.DateTimeField(null=True, blank=True)
    arrival_datetime = models.DateTimeField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    verification_timestamp = models.DateTimeField(null=True, blank=True)
    qr_code_data = models.TextField(blank=True)

    def __str__(self):
        return f"Booking {self.booking_id} - {self.user.username} - {self.train}"

    def save(self, *args, **kwargs):
        if not self.booking_id:
            import random
            import string
            self.booking_id = 'BK' + ''.join(random.choices(string.digits, k=8))
        super().save(*args, **kwargs)

    def get_qr_data(self):
        if self.booking_status == 'CONFIRMED':
            import json
            import hashlib
            
            qr_data = {
                'booking_id': self.booking_id,
                'user_id': self.user.id,
                'train_id': self.train.id,
                'passenger_count': self.passenger_count,
                'total_fare': str(self.total_fare)
            }
            
            qr_string = json.dumps(qr_data, sort_keys=True)
            verification_hash = hashlib.sha256(qr_string.encode()).hexdigest()[:16]
            qr_data['verification_hash'] = verification_hash
            
            return qr_data
        return None

    def verify_booking(self):
        from django.utils import timezone
        self.is_verified = True
        self.verification_timestamp = timezone.now()
        self.save()
