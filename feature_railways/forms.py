from django import forms
from django.forms import formset_factory
from .models import Station, SeatClass, Route, RouteHalt, RouteSeatClass, Train, Passenger

class StationForm(forms.ModelForm):
    class Meta:
        model = Station
        fields = ['name', 'code']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Station Name'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Station Code'})
        }

class SeatClassForm(forms.ModelForm):
    class Meta:
        model = SeatClass
        fields = ['class_type', 'code']
        widgets = {
            'class_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Class Type'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Class Code'})
        }

class RouteForm(forms.ModelForm):
    class Meta:
        model = Route
        fields = ['name', 'code', 'source_station', 'destination_station', 'departure_time', 'journey_duration', 'base_fare', 'running_days']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Route Name'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Route Code'}),
            'source_station': forms.Select(attrs={'class': 'form-control'}),
            'destination_station': forms.Select(attrs={'class': 'form-control'}),
            'departure_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'journey_duration': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'HH:MM:SS'}),
            'base_fare': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'running_days': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1111100'}),
        }

class RouteHaltForm(forms.ModelForm):
    class Meta:
        model = RouteHalt
        fields = ['route', 'station', 'sequence_number', 'journey_duration_from_source']
        widgets = {
            'route': forms.Select(attrs={'class': 'form-control'}),
            'station': forms.Select(attrs={'class': 'form-control'}),
            'sequence_number': forms.NumberInput(attrs={'class': 'form-control'}),
            'journey_duration_from_source': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'HH:MM:SS'}),
        }

class RouteSeatClassForm(forms.ModelForm):
    class Meta:
        model = RouteSeatClass
        fields = ['route', 'seat_class', 'num_of_available_seats', 'base_fare_per_hour']
        widgets = {
            'route': forms.Select(attrs={'class': 'form-control'}),
            'seat_class': forms.Select(attrs={'class': 'form-control'}),
            'num_of_available_seats': forms.NumberInput(attrs={'class': 'form-control'}),
            'base_fare_per_hour': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

class PassengerDetailForm(forms.ModelForm):
    class Meta:
        model = Passenger
        fields = ['name', 'age', 'gender']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'age': forms.NumberInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
        }

PassengerFormSet = formset_factory(PassengerDetailForm, extra=0, min_num=1, max_num=6)

class TrainGenerationForm(forms.Form):
    route = forms.ModelChoiceField(
        queryset=Route.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'})
    )

class TrainSearchForm(forms.Form):
    source = forms.ModelChoiceField(
        queryset=Station.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    destination = forms.ModelChoiceField(
        queryset=Station.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

class BookingForm(forms.Form):
    seat_class = forms.ModelChoiceField(
        queryset=SeatClass.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    passenger_count = forms.IntegerField(
        min_value=1,
        max_value=6,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

class BookingConfirmationForm(forms.Form):
    terms_accepted = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    emergency_contact = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Emergency Contact Number'}),
    )
    otp_code = forms.CharField(
        max_length=6,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter 6-digit OTP'})
    )