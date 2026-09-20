from django.urls import path
from . import frontend_views

urlpatterns = [
    # Home
    path('', frontend_views.home_view, name='home'),
    path('health/', frontend_views.health_check, name='health_check'),
    
    # Authentication
    path('register/', frontend_views.register_view, name='register'),
    path('login/', frontend_views.login_view, name='login'),
    path('logout/', frontend_views.logout_view, name='logout'),
    path('profile/', frontend_views.profile_view, name='profile'),
    
    # Dashboard
    path('dashboard/', frontend_views.dashboard_view, name='dashboard'),
    path('staff/dashboard/', frontend_views.admin_dashboard_view, name='admin_dashboard'),
    path('staff/rooms/', frontend_views.admin_rooms_view, name='admin_rooms'),
    
    # Rooms
    path('rooms/', frontend_views.rooms_view, name='rooms'),
    path('rooms/<int:room_id>/book/', frontend_views.book_room_view, name='book_room'),
    
    # Bookings
    path('my-bookings/', frontend_views.my_bookings_view, name='my_bookings'),
    path('bookings/<int:booking_id>/', frontend_views.booking_detail_view, name='booking_detail'),
    path('bookings/<int:booking_id>/confirmation/', frontend_views.booking_confirmation_view, name='booking_confirmation'),
    path('bookings/<int:booking_id>/invoice/', frontend_views.invoice_view, name='invoice'),
    path('bookings/<int:booking_id>/checkin/', frontend_views.checkin_booking_view, name='checkin_booking'),
    path('bookings/<int:booking_id>/checkout/', frontend_views.checkout_booking_view, name='checkout_booking'),
    path('bookings/<int:booking_id>/cancel/', frontend_views.cancel_booking_view, name='cancel_booking'),
    path('rooms/<int:room_id>/review/', frontend_views.submit_review_view, name='submit_review'),
    path('contact/', frontend_views.contact_message_view, name='contact_message'),
]