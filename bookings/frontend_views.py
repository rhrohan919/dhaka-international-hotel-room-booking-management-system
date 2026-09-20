import re
from datetime import datetime

from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import Booking, ContactMessage, Review
from rooms.models import Room


# ============================================================================
# AUTHENTICATION VIEWS
# ============================================================================

def register_view(request):
    """User registration view"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Set additional fields if provided
            if request.POST.get('first_name'):
                user.first_name = request.POST.get('first_name')
            if request.POST.get('last_name'):
                user.last_name = request.POST.get('last_name')
            if request.POST.get('email'):
                user.email = request.POST.get('email')
            user.save()
            
            login(request, user)
            messages.success(request, f'Welcome {user.username}! Your account has been created.')
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    
    return render(request, 'register.html', {'form': form})


def login_view(request):
    """User login view"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {user.first_name or user.username}!')
                next_url = request.GET.get('next', 'dashboard')
                return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password')
    else:
        form = AuthenticationForm()
    
    return render(request, 'login.html', {'form': form})


@login_required
def logout_view(request):
    """User logout view"""
    if request.method == 'POST':
        logout(request)
        messages.success(request, 'You have been logged out successfully.')
        return redirect('login')
    return redirect('dashboard')


# ============================================================================
# DASHBOARD VIEW
# ============================================================================

@login_required
def dashboard_view(request):
    """User dashboard with statistics"""
    user = request.user
    now = timezone.now()
    
    # Get booking statistics
    total_bookings = Booking.objects.filter(user=user).count()
    
    upcoming_bookings = Booking.objects.filter(
        user=user,
        status__in=['pending', 'confirmed'],
        start_time__gt=now
    ).count()
    
    active_bookings = Booking.objects.filter(
        user=user,
        status__in=['confirmed', 'checked_in'],
        start_time__lte=now,
        end_time__gte=now
    ).count()
    
    past_bookings = Booking.objects.filter(
        user=user,
        status__in=['checked_out', 'cancelled']
    ).count()
    
    # Get recent bookings
    recent_bookings = Booking.objects.filter(
        user=user
    ).select_related('room').order_by('-created_at')[:5]
    
    context = {
        'total_bookings': total_bookings,
        'upcoming_bookings': upcoming_bookings,
        'active_bookings': active_bookings,
        'past_bookings': past_bookings,
        'recent_bookings': recent_bookings,
    }
    
    return render(request, 'dashboard.html', context)


# ============================================================================
# ROOM VIEWS
# ============================================================================

@login_required
def rooms_view(request):
    """List all available rooms with filters"""
    rooms = Room.objects.filter(status='available')
    
    # Apply filters
    room_type = request.GET.get('room_type')
    if room_type:
        rooms = rooms.filter(room_type=room_type)
    
    min_capacity = request.GET.get('min_capacity')
    if min_capacity:
        try:
            rooms = rooms.filter(capacity__gte=int(min_capacity))
        except ValueError:
            pass
    
    max_hourly_rate = request.GET.get('max_hourly_rate')
    if max_hourly_rate:
        try:
            rooms = rooms.filter(hourly_rate__lte=float(max_hourly_rate))
        except ValueError:
            pass
    
    max_daily_rate = request.GET.get('max_daily_rate')
    if max_daily_rate:
        try:
            rooms = rooms.filter(daily_rate__lte=float(max_daily_rate))
        except ValueError:
            pass
    
    context = {
        'rooms': rooms.order_by('room_number')
    }
    
    return render(request, 'rooms.html', context)


@login_required
def book_room_view(request, room_id):
    """Book a specific room"""
    room = get_object_or_404(Room, id=room_id)
    
    if request.method == 'POST':
        try:
            booking_type = request.POST.get('booking_type')
            start_time = request.POST.get('start_time')
            end_time = request.POST.get('end_time')
            guest_name = request.POST.get('guest_name', '').strip()
            guest_email = request.POST.get('guest_email', '').strip()
            guest_phone = request.POST.get('guest_phone', '').strip()
            number_of_guests = request.POST.get('number_of_guests')
            special_requests = request.POST.get('special_requests', '').strip()

            if not all([booking_type, start_time, end_time, guest_name, guest_email, guest_phone]):
                raise ValueError('Please fill in all required booking fields.')

            normalized_phone = guest_phone.replace(' ', '').replace('-', '')
            if not re.fullmatch(r'^(?:\+?88|88)?01[3-9]\d{8}$', normalized_phone):
                raise ValueError('Please enter a valid Bangladeshi mobile number.')

            from .services import BookingService
            
            start_dt = parse_datetime(start_time)
            end_dt = parse_datetime(end_time)

            if start_dt is None:
                start_dt = datetime.fromisoformat(start_time.replace('Z', ''))
            if end_dt is None:
                end_dt = datetime.fromisoformat(end_time.replace('Z', ''))

            if timezone.is_naive(start_dt):
                start_dt = timezone.make_aware(start_dt)

            if timezone.is_naive(end_dt):
                end_dt = timezone.make_aware(end_dt)

            is_available, message = BookingService.check_room_availability(
                room_id, start_dt, end_dt
            )
            
            if not is_available:
                messages.error(request, message)
                return redirect('book_room', room_id=room_id)
            
            total_price = BookingService.calculate_price(
                room, booking_type, start_dt, end_dt
            )

            parsed_guest_count = int(number_of_guests)
            if parsed_guest_count < 1 or parsed_guest_count > room.capacity:
                raise ValueError(f'Number of guests must be between 1 and {room.capacity}.')
            
            booking = Booking.objects.create(
                user=request.user,
                room=room,
                booking_type=booking_type,
                start_time=start_dt,
                end_time=end_dt,
                guest_name=guest_name,
                guest_email=guest_email,
                guest_phone=normalized_phone,
                number_of_guests=parsed_guest_count,
                total_price=total_price,
                special_requests=special_requests,
                status='confirmed'
            )
            
            messages.success(request, f'Booking confirmed! Booking ID: #{booking.id}')
            return redirect('booking_confirmation', booking_id=booking.id)
            
        except Exception as e:
            messages.error(request, f'Error creating booking: {str(e)}')
            return redirect('book_room', room_id=room_id)
    
    context = {
        'room': room
    }
    
    return render(request, 'book_room.html', context)


# ============================================================================
# BOOKING VIEWS
# ============================================================================

@login_required
def my_bookings_view(request):
    """List user's bookings with filters"""
    bookings = Booking.objects.filter(user=request.user).select_related('room')
    
    # Apply filter
    filter_type = request.GET.get('filter', 'all')
    now = timezone.now()
    
    if filter_type == 'upcoming':
        bookings = bookings.filter(
            status__in=['pending', 'confirmed'],
            start_time__gt=now
        )
    elif filter_type == 'active':
        bookings = bookings.filter(
            status__in=['confirmed', 'checked_in'],
            start_time__lte=now,
            end_time__gte=now
        )
    elif filter_type == 'past':
        bookings = bookings.filter(
            Q(status__in=['checked_out', 'cancelled', 'expired']) |
            Q(end_time__lt=now)
        )
    
    bookings = bookings.order_by('-created_at')
    
    context = {
        'bookings': bookings,
        'filter': filter_type
    }
    
    return render(request, 'my_bookings.html', context)


@login_required
def booking_detail_view(request, booking_id):
    """View booking details"""
    booking = get_object_or_404(
        Booking.objects.select_related('room'), 
        id=booking_id, 
        user=request.user
    )
    
    context = {
        'booking': booking
    }
    
    return render(request, 'booking_detail.html', context)


@login_required
def booking_confirmation_view(request, booking_id):
    """View booking confirmation summary after successful reservation."""
    booking = get_object_or_404(
        Booking.objects.select_related('room'),
        id=booking_id,
        user=request.user,
    )

    return render(request, 'booking_confirmation.html', {'booking': booking})


@login_required
def invoice_view(request, booking_id):
    """Generate invoice for a confirmed booking."""
    booking = get_object_or_404(
        Booking.objects.select_related('room'),
        id=booking_id,
        user=request.user,
    )

    return render(request, 'invoice.html', {'booking': booking})


@login_required
def checkin_booking_view(request, booking_id):
    """Check-in to a booking"""
    if request.method == 'POST':
        booking = get_object_or_404(Booking, id=booking_id, user=request.user)
        
        from .services import BookingService
        success, message = BookingService.perform_checkin(booking)
        
        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)
    
    return redirect('my_bookings')


@login_required
def checkout_booking_view(request, booking_id):
    """Check-out from a booking"""
    if request.method == 'POST':
        booking = get_object_or_404(Booking, id=booking_id, user=request.user)
        
        from .services import BookingService
        success, message, extra_charges = BookingService.perform_checkout(booking)
        
        if success:
            if extra_charges > 0:
                messages.warning(request, f'{message} Extra charges: ৳{extra_charges}')
            else:
                messages.success(request, message)
        else:
            messages.error(request, message)
    
    return redirect('my_bookings')


@login_required
def cancel_booking_view(request, booking_id):
    """Cancel a booking"""
    if request.method == 'POST':
        booking = get_object_or_404(Booking, id=booking_id, user=request.user)
        
        from .services import BookingService
        success, message = BookingService.cancel_booking(booking)
        
        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)
    
    return redirect('my_bookings')


@login_required
def profile_view(request):
    """User profile view"""
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')
    
    return render(request, 'profile.html')


@login_required
def submit_review_view(request, room_id):
    """Submit a review for a room."""
    room = get_object_or_404(Room, id=room_id)

    if request.method == 'POST':
        rating = request.POST.get('rating')
        comment = request.POST.get('comment', '').strip()

        if not rating:
            messages.error(request, 'Please provide a rating.')
            return redirect('rooms')

        Review.objects.update_or_create(
            room=room,
            user=request.user,
            defaults={'rating': int(rating), 'comment': comment}
        )
        messages.success(request, 'Your review has been submitted successfully.')
        return redirect('rooms')

    return redirect('rooms')


def contact_message_view(request):
    """Store visitor support messages from the home contact form."""
    if request.method != 'POST':
        return redirect('home')

    name = request.POST.get('name', '').strip()
    email = request.POST.get('email', '').strip()
    phone = request.POST.get('phone', '').strip()
    subject = request.POST.get('subject', '').strip()
    message = request.POST.get('message', '').strip()

    if not all([name, email, subject, message]):
        messages.error(request, 'Please complete all required fields before sending your message.')
        return redirect('home')

    ContactMessage.objects.create(
        name=name,
        email=email,
        phone=phone,
        subject=subject,
        message=message,
    )
    messages.success(request, 'Thank you! Your message has been received and our team will contact you soon.')
    return redirect('home')


# ============================================================================
# STAFF ADMIN VIEWS
# ============================================================================

@login_required
@user_passes_test(lambda user: user.is_staff)
def admin_dashboard_view(request):
    """Staff analytics dashboard for hotel operations."""
    total_rooms = Room.objects.count()
    available_rooms = Room.objects.filter(status='available').count()
    maintenance_rooms = Room.objects.filter(status='maintenance').count()

    total_bookings = Booking.objects.count()
    confirmed_bookings = Booking.objects.filter(status='confirmed').count()
    checked_in_bookings = Booking.objects.filter(status='checked_in').count()
    cancelled_bookings = Booking.objects.filter(status='cancelled').count()

    recent_bookings = Booking.objects.select_related('room', 'user').order_by('-created_at')[:6]

    context = {
        'total_rooms': total_rooms,
        'available_rooms': available_rooms,
        'maintenance_rooms': maintenance_rooms,
        'total_bookings': total_bookings,
        'confirmed_bookings': confirmed_bookings,
        'checked_in_bookings': checked_in_bookings,
        'cancelled_bookings': cancelled_bookings,
        'recent_bookings': recent_bookings,
    }
    return render(request, 'admin_dashboard.html', context)


@login_required
@user_passes_test(lambda user: user.is_staff)
def admin_rooms_view(request):
    """Staff room management panel for updating room status."""
    rooms = Room.objects.all().order_by('room_number')

    if request.method == 'POST':
        room_id = request.POST.get('room_id')
        new_status = request.POST.get('status')
        if room_id and new_status:
            room = get_object_or_404(Room, id=room_id)
            room.status = new_status
            room.save(update_fields=['status', 'updated_at'])
            messages.success(request, f'Room {room.room_number} status updated to {room.get_status_display()}.')
            return redirect('admin_rooms')

    context = {
        'rooms': rooms,
        'status_choices': Room.STATUS_CHOICES,
    }
    return render(request, 'admin_rooms.html', context)


# ============================================================================
# HEALTH CHECK
# ============================================================================

def health_check(request):
    """Simple health check for deployment monitoring."""
    return JsonResponse({'status': 'ok', 'service': 'hotel-booking-system'})


# ============================================================================
# HOME VIEW
# ============================================================================

def home_view(request):
    """Home page view. Always keep the landing page accessible so section links work."""
    featured_rooms = Room.objects.filter(status='available').order_by('room_number')[:3]
    return render(request, 'home.html', {'featured_rooms': featured_rooms})