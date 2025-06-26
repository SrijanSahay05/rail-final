from core_users.models import CustomUser
from datetime import datetime, timedelta
from django.core.exceptions import ValidationError
from django.db import models


class Station(models.Model):

    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=6, unique=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code.capitalize()}:{self.name.title()}"
    

class SeatClass(models.Model):

    class_type = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=6, unique=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code.capitalize()}:{self.class_type.title()}"
    

class Passenger(models.Model):

    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
    ]

    name = models.CharField(max_length=50)
    age = models.PositiveIntegerField()
    gender = models.CharField(choices=GENDER_CHOICES, max_length=1)

    booking_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

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
    arrival_time = models.TimeField()

    running_days = models.CharField(max_length=7, null=True, blank=True)

    halt_stations_m2m = models.ManyToManyField(
        Station, 
        through='RouteHalt',
        through_fields=('route', 'station'),
    )

    available_seat_class = models.ManyToManyField(
        SeatClass,
        through='RouteSeatClass',
        through_fields=('route', 'seat_class')
    )

    class Meta:
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code.capitalize()} : {self.name.title()} ({self.source_station.code.capitalize()} to {self.destination_station.code.capitalize()})"
    
    def clean(self):
        if self.source_station == self.destination_station: 
            raise ValidationError("Source & Destination can not be same")
        
    def save(self, *args, **kwargs):

        if self.departure_time and self.journey_duration:
            self.arrival_time = (datetime.combine(datetime.min, self.departure_time) + self.journey_duration).time()
        super().save(*args, **kwargs)


class RouteHalt(models.Model):
    
    station = models.ForeignKey(Station, on_delete=models.CASCADE)
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='halt_stations')

    sequence_number = models.PositiveIntegerField()
    journey_duration_from_source = models.DurationField()

    class Meta:
        ordering = ['route', 'sequence_number']
        unique_together = [['station', 'route'], ['route', 'sequence_number']]

    def __str__(self):
         return f"Halt Station {self.station.code.capitalize()} on route {self.route.code.capitalize()}"
    

class RouteSeatClass(models.Model):

    seat_class = models.ForeignKey(SeatClass, on_delete=models.CASCADE)
    route = models.ForeignKey(Route, on_delete=models.CASCADE)

    num_of_available_seats = models.PositiveIntegerField(default=100)
    base_fare_per_hour = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        ordering = ['route', 'seat_class__class_type']
        unique_together = [['route', 'seat_class']]

    def __str__(self):
        return f"{self.seat_class} on {self.route} [seats available: {self.num_of_available_seats}]"
    

class Train(models.Model):

    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='trains_on_route')

    departure_date_time = models.DateTimeField()
    arrival_date_time = models.DateTimeField()

    class Meta:
        ordering = ['departure_date_time', 'route']

    def __str__(self):
        return f"{self.route} [{self.departure_date_time.strftime('%H:%M %d-%m-%Y')}]"

    def save(self, *args, **kwargs):
        if self.route and self.departure_date_time:
            original_date = self.departure_date_time.date()
            route_time = self.route.departure_time
            self.departure_date_time = datetime.combine(original_date, route_time)

            if self.route.journey_duration:
                self.arrival_date_time = self.departure_date_time + self.route.journey_duration

        super().save(*args, **kwargs)


class TrainSegment(models.Model):

    train = models.ForeignKey(Train, on_delete=models.CASCADE, related_name='segments')

    segment_source = models.ForeignKey(Station, on_delete=models.CASCADE, related_name='segments_as_source')
    departure_date_time = models.DateTimeField()

    segment_destination = models.ForeignKey(Station, on_delete=models.CASCADE, related_name='segment_as_destination')
    arrival_date_time = models.DateTimeField()

    segment_number = models.PositiveIntegerField()

    segment_journey_duration = models.DurationField()

    class Meta:
        ordering = ['train', 'segment_number']
    
    def __str__(self):
        return f"Train Segment on {self.train.route.code.capitalize()} [{self.segment_source.code.capitalize()} to {self.segment_destination.code.capitalize()} ({self.segment_number})]"
    
    def save(self, *args, **kwargs):

        if self.train and self.segment_source and self.segment_destination:
            route = self.train.route

            if self.segment_source == self.segment_destination:
                raise ValidationError("Segment source and destination cannot be the same")

            if self.segment_source == route.source_station:
                source_duration_from_start = timedelta(0)
            else:
                try:
                    source_halt = RouteHalt.objects.get(route=route, station=self.segment_source)
                    source_duration_from_start = source_halt.journey_duration_from_source
                except RouteHalt.DoesNotExist:
                    raise ValidationError(f"Station '{self.segment_source.code}' is not a valid station on route '{route.code}'")
            
            if self.segment_destination == route.destination_station:
                destination_duration_from_start = route.journey_duration
            else:
                try:
                    dest_halt = RouteHalt.objects.get(route=route, station=self.segment_destination)
                    destination_duration_from_start = dest_halt.journey_duration_from_source
                except RouteHalt.DoesNotExist:
                    raise ValidationError(f"Station '{self.segment_destination.code}' is not a valid station on route '{route.code}'")
            
            self.departure_date_time = self.train.departure_date_time + source_duration_from_start
            self.arrival_date_time = self.train.departure_date_time + destination_duration_from_start
            self.segment_journey_duration = self.arrival_date_time - self.departure_date_time

        super().save(*args, **kwargs)

# TODO check and fix the logic for train seat number generation
class TrainSeat(models.Model): # TODO write services to auto generate the seats based off the available_seat from each of the seat class on the train route

    train = models.ForeignKey(Train, on_delete=models.CASCADE, related_name='seats')
    seat_class = models.ForeignKey(SeatClass, on_delete=models.CASCADE)
    seat_number = models.CharField(max_length=10)

    class Meta:
        unique_together = ('train', 'seat_class', 'seat_number')

    def __str__(self):
        return f"{self.train} - {self.seat_class.code} {self.seat_number}"

class SeatBooking(models.Model):

    train_seat = models.ForeignKey(TrainSeat, on_delete=models.CASCADE, related_name='bookings')
    train_segment = models.ForeignKey(TrainSegment, on_delete=models.CASCADE, related_name='bookings')
    passenger = models.ForeignKey(Passenger, on_delete=models.CASCADE)
    booked_at = models.DateTimeField(auto_now_add=True)
    
    price_for_segment = models.DecimalField(max_digits=10, decimal_places=2, default=0.00) # TODO write logic for total price_calculation

    class Meta:
        unique_together = ('train_seat', 'train_segment')
        constraints = [
            models.CheckConstraint(
                check=models.Q(price_for_segment__gte=0),
                name='seatbooking_price_positive'
            ),
        ]
        indexes = [
            models.Index(fields=['train_seat', 'train_segment']),
            models.Index(fields=['passenger', 'booked_at']),
        ]
    
    def __str__(self):
        return f"{self.train_seat} booked for {self.train_segment} by {self.passenger.booking_by}"
    

    # TODO write logic to calculate the price based on the train segment and seat class
    def calculate_price(self):

        if self.train_segment and self.train_seat:
            route = self.train_segment.train.route
            seat_class = self.train_seat.seat_class

            try:
                route_seat_class = RouteSeatClass.objects.get(
                    route=route,
                    seat_class=seat_class
                )
                base_fare_per_hour = route_seat_class.base_fare_per_hour
            except RouteSeatClass.DoesNotExist:
                return 0.00
            
            journey_duration = self.train_segment.segment_journey_duration
            duration_hours = journey_duration.total_seconds()/3600

            calculated_price =(base_fare_per_hour * duration_hours) + route.base_fare

            return calculated_price

        def save(self, *args, **kwargs):

            if not self.price:
                self.price = self.calculate_price()
            super().save(*args, **kwargs)

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
    
    # Journey segment fields for halt station bookings
    journey_source = models.ForeignKey(Station, on_delete=models.CASCADE, related_name='bookings_as_source', null=True, blank=True)
    journey_destination = models.ForeignKey(Station, on_delete=models.CASCADE, related_name='bookings_as_destination', null=True, blank=True)
    departure_datetime = models.DateTimeField(null=True, blank=True)
    arrival_datetime = models.DateTimeField(null=True, blank=True)
    
    is_verified = models.BooleanField(default=False)
    verification_timestamp = models.DateTimeField(null=True, blank=True)
    qr_code_data = models.TextField(blank=True) 
    
    class Meta:
        ordering = ['-booking_date']
        constraints = [
            models.CheckConstraint(
                check=models.Q(passenger_count__gt=0),
                name='booking_passenger_count_positive'
            ),
            models.CheckConstraint(
                check=models.Q(total_fare__gte=0),
                name='booking_total_fare_non_negative'
            ),
            models.CheckConstraint(
                check=models.Q(passenger_count__lte=10),
                name='booking_passenger_count_limit'
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'booking_date']),
            models.Index(fields=['booking_status', 'booking_date']),
            models.Index(fields=['train', 'booking_date']),
            models.Index(fields=['is_verified', 'verification_timestamp']),
        ]
    
    def __str__(self):
        return f"Booking {self.booking_id} - {self.user.username} - {self.train}"
    
    @property
    def actual_source_station(self):
        return self.journey_source or self.train.route.source_station
    
    @property
    def actual_destination_station(self):
        return self.journey_destination or self.train.route.destination_station
    
    @property
    def actual_departure_time(self):
        return self.departure_datetime or self.train.departure_date_time
    
    @property
    def actual_arrival_time(self):
        return self.arrival_datetime or self.train.arrival_date_time
    
    @property
    def actual_journey_duration(self):
        if self.departure_datetime and self.arrival_datetime:
            return self.arrival_datetime - self.departure_datetime
        else:
            return self.train.route.journey_duration
    
    def generate_qr_code_data(self):
        import hashlib
        import json
        from django.utils import timezone
        
        if self.booking_status != 'CONFIRMED':
            return None
            
        qr_data = {
            'booking_id': self.booking_id,
            'user_id': self.user.id,
            'train_id': self.train.id,
            'booking_date': self.booking_date.isoformat() if self.booking_date else timezone.now().isoformat(),
            'passenger_count': self.passenger_count,
            'total_fare': str(self.total_fare)
        }
        
        qr_string = json.dumps(qr_data, sort_keys=True)
        verification_hash = hashlib.sha256(qr_string.encode()).hexdigest()[:16]
        qr_data['verification_hash'] = verification_hash
        
        return json.dumps(qr_data)

    def save(self, *args, **kwargs):
        if not self.booking_id:
            import random
            import string
            self.booking_id = 'BK' + ''.join(random.choices(string.digits, k=8))
        
        if self.booking_status == 'CONFIRMED' and not self.qr_code_data:
            self.qr_code_data = self.generate_qr_code_data()
        
        super().save(*args, **kwargs)
    
    def get_qr_data(self):
        if not self.qr_code_data and self.booking_status == 'CONFIRMED':
            self.qr_code_data = self.generate_qr_code_data()
            self.save()
        
        if self.qr_code_data:
            import json
            return json.loads(self.qr_code_data)
        return None
    
    def verify_booking(self):
        from django.utils import timezone
        self.is_verified = True
        self.verification_timestamp = timezone.now()
        self.save()