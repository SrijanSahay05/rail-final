from django.contrib import admin
from .models import *
# Register your models here.
admin.site.register(Station)
admin.site.register(Route)
admin.site.register(RouteHalt)
admin.site.register(RouteSeatClass)
admin.site.register(SeatClass)
admin.site.register(Train)
admin.site.register(TrainSegment)
admin.site.register(TrainSeat)
admin.site.register(Booking)
admin.site.register(Passenger)
admin.site.register(SeatBooking)
# admin.site.register()