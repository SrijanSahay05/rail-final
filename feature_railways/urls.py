from django.urls import path
from . import views

app_name = 'feature_railways'

urlpatterns = [
    path('', views.index, name='index'),
    path('search/', views.search_trains, name='search_trains'),
    
    # Booking Flow
    path('book/<int:train_id>/', views.book_train, name='book_train'),
    path('book/<int:train_id>/<int:source_id>/<int:destination_id>/', views.book_train, name='book_train_segment'),
    path('book/passenger-details/', views.passenger_details, name='passenger_details'),
    path('book/confirmation/', views.booking_confirmation, name='booking_confirmation'),
    path('book/success/<str:booking_id>/', views.booking_success, name='booking_success'),
    
    # Staff Dashboard
    path('staff/dashboard/', views.railway_staff_dashboard, name='railway_staff_dashboard'),
    
    # Add Forms
    path('staff/add-station/', views.add_station, name='add_station'),
    path('staff/add-seat-class/', views.add_seat_class, name='add_seat_class'),
    path('staff/add-route/', views.add_route, name='add_route'),
    path('staff/add-route-halt/', views.add_route_halt, name='add_route_halt'),
    path('staff/add-route-seat-class/', views.add_route_seat_class, name='add_route_seat_class'),
    path('staff/generate-trains/', views.generate_trains, name='generate_trains'),
    
    # View Lists
    path('staff/view-stations/', views.view_stations, name='view_stations'),
    path('staff/view-routes/', views.view_routes, name='view_routes'),
    path('staff/view-trains/', views.view_trains, name='view_trains'),
    path('staff/view-seat-classes/', views.view_seat_classes, name='view_seat_classes'),
    
    # User Profile and QR Code URLs
    path('profile/', views.user_profile, name='user_profile'),
    path('booking/<str:booking_id>/', views.booking_detail, name='booking_detail'),
    path('booking/<str:booking_id>/cancel/', views.cancel_booking, name='cancel_booking'),
    path('booking/<str:booking_id>/qr/', views.booking_qr_view, name='booking_qr'),
    path('booking/<str:booking_id>/qr-image/', views.generate_qr_code, name='generate_qr_code'),
    
    # QR Verification (Staff only)
    path('staff/qr-scanner/', views.qr_scanner, name='qr_scanner'),
    path('staff/verify-ticket/', views.verify_ticket, name='verify_ticket'),
]